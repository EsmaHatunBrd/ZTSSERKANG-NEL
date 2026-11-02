from datetime import date
from decimal import Decimal as D_
import pytest
from backend.depo import modeller as m
from backend.servisler import fiyat_servisi as fs, hesap_servisi as hs, import_servisi as ims, recete_servisi as rs
from backend.tohum import fire_varsayilanlarini_tohumla, parametreleri_tohumla


@pytest.fixture(scope="module")
def yuklu(excel_yolu):
    from backend.depo.veritabani import Base, motor_olustur, oturum_fabrikasi
    engine = motor_olustur("sqlite://"); Base.metadata.create_all(engine)
    s = oturum_fabrikasi(engine)()
    ozet = ims.excel_tam_yukle(s, excel_yolu, "2026-2027", "Berrak fiyat çalışması")
    s.commit()
    yield s, ozet
    s.close()


def test_ozet(yuklu):
    s, o = yuklu
    assert o["malzeme"] >= 800 and o["fiyat"] >= 500 and o["havuz"] == 11 and o["ambalaj"] == 22
    assert o["urun"] >= 60 and o["recete"] >= 60
    assert s.query(m.ReceteSatiri).filter_by(dugum_tipi="ara_mamul").count() == 57
    assert s.query(m.ReceteSatiri).filter(m.ReceteSatiri.fire_override.is_(None)).count() == 0   # G3: Excel paritesi, her satırda override
    assert s.query(m.Urun).filter_by(gecici_kod=True).count() == 12 and o["yeniden_adlandirilan"] == []
    assert any("(2)" in a for a in o["atlanan"])
    assert o["urun"] == 67 and s.query(m.Urun).count() == 67
    assert sum("ürün kodu yok" in u for u in o["uyarilar"]) == 12
    assert s.query(m.Urun).filter(m.Urun.kod.like("SAYFA-%")).count() == 12


def test_parametreler_ve_fire(yuklu):
    s, o = yuklu
    from backend.servisler import parametre_servisi as ps
    p = ps.gecerli_parametreler(s, o["senaryo_id"], date(2026, 10, 21))
    assert p.kurlar["USD"] == D_(50) and p.enflasyon == D_("0.25") and p.teklif_kar_oranlari == (D_("0.2"), D_("0.17"), D_("0.14"))
    assert s.query(m.FireKurali).filter_by(kapsam_tipi="tip", kapsam_deger="0008-Ambalaj Malzeme").one().oran == D_("0.02")


def test_recete_fire_satirdan(yuklu):
    s, o = yuklu
    u = s.query(m.Urun).filter_by(kod="03.004.001.002.00010").one()
    r = rs.aktif_recete(s, u.id, o["senaryo_id"])
    assert r.kaynak == "import" and any(x.fire_override == D_("0.02") for x in r.satirlar)


def test_tohum_tekrar_calisinca_cogalmaz(oturum):
    parametreleri_tohumla(oturum); n = oturum.query(m.Parametre).count()
    parametreleri_tohumla(oturum); assert oturum.query(m.Parametre).count() == n


def test_fiyat_listesi_onizle_ve_uygula(oturum, tmp_path):
    import openpyxl
    sz = m.Sezon(ad="S", baslangic=date(2026, 6, 1), bitis=date(2027, 5, 31)); oturum.add(sz); oturum.flush()
    sen = m.Senaryo(sezon_id=sz.id, tur="fiyat_calismasi", ad="A"); oturum.add(sen); oturum.flush()
    fs.malzeme_ekle_veya_guncelle(oturum, "A1", "Malzeme A", None, "AD", "TL", "S"); fs.fiyat_ekle(oturum, sen.id, "A1", D_("5"), date(2026, 6, 1), "")
    fs.malzeme_ekle_veya_guncelle(oturum, "B1", "Malzeme B", None, "AD", "TL", "S"); fs.fiyat_ekle(oturum, sen.id, "B1", D_("7"), date(2026, 6, 1), "")
    fs.malzeme_ekle_veya_guncelle(oturum, "C1", "Malzeme C", None, "AD", "TL", "S")   # fiyatsız kart
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["Malzeme", "Açıklama", "Tip", "Birim", "Para", "Fiyat"])
    ws.append(["A1", "a", None, "AD", "TL", 6])        # değişen
    ws.append(["B1", "b", None, "AD", "TL", 7])        # aynı
    ws.append(["C1", "c", None, "AD", "TL", 3])        # kartı var fiyatı yok -> degisen (eski 0)
    ws.append(["YENI", "y", None, "AD", "TL", 9])      # kartı yok -> yeni, uygulanmaz
    ws.append(["A1", "a", None, "AD", "TL", "abc"])    # hatalı
    ws.append(["B1", "b", None, "AD", "TL", -1])       # hatalı (negatif)
    dosya = tmp_path / "liste.xlsx"; wb.save(dosya)
    on = ims.fiyat_listesi_onizle(oturum, sen.id, dosya, date(2026, 9, 1))
    assert {d["kod"] for d in on["degisen"]} == {"A1", "C1"} and on["ayni"] == 1
    assert [d["kod"] for d in on["yeni"]] == ["YENI"] and on["hatali"] == ["A1", "B1"]
    sonuc = ims.fiyat_listesi_uygula(oturum, sen.id, dosya, date(2026, 9, 1), "liste", "esma")
    assert sonuc["yazilan"] == 2 and sorted(sonuc["kodlar"]) == ["A1", "C1"]
    g = fs.gecerli_fiyatlar(oturum, sen.id, date(2026, 10, 1))
    assert g["A1"].fiyat == D_("6") and g["C1"].fiyat == D_("3") and g["B1"].fiyat == D_("7") and "YENI" not in g
    assert fs.gecmis(oturum, sen.id, "A1")[0].kaynak == "import" and fs.gecmis(oturum, sen.id, "A1")[0].olusturan == "esma"


def test_fiyat_listesi_gecerlilik_tarihinde_karsilastirir(oturum, tmp_path):
    import openpyxl
    sz = m.Sezon(ad="S", baslangic=date(2026, 6, 1), bitis=date(2027, 5, 31)); oturum.add(sz); oturum.flush()
    sen = m.Senaryo(sezon_id=sz.id, tur="fiyat_calismasi", ad="A"); oturum.add(sen); oturum.flush()
    fs.malzeme_ekle_veya_guncelle(oturum, "A1", "A", None, "AD", "TL", "S")
    fs.fiyat_ekle(oturum, sen.id, "A1", D_("5"), date(2026, 6, 1), "")
    fs.fiyat_ekle(oturum, sen.id, "A1", D_("6"), date(2026, 9, 1), "zam")
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["Malzeme", "Açıklama", "Tip", "Birim", "Para", "Fiyat"]); ws.append(["A1", "a", None, "AD", "TL", 6])
    dosya = tmp_path / "l.xlsx"; wb.save(dosya)
    # 15 Ağustos'ta fiyat 5 -> 6 değişiklik; 1 Ekim'de fiyat zaten 6 -> aynı
    assert [d["kod"] for d in ims.fiyat_listesi_onizle(oturum, sen.id, dosya, date(2026, 8, 15))["degisen"]] == ["A1"]
    assert ims.fiyat_listesi_onizle(oturum, sen.id, dosya, date(2026, 10, 1))["ayni"] == 1
    assert ims.fiyat_listesi_uygula(oturum, sen.id, dosya, date(2026, 10, 1), "x") == {"yazilan": 0, "kodlar": []}
    assert ims.fiyat_listesi_uygula(oturum, sen.id, dosya, date(2026, 8, 15), "x") == {"yazilan": 1, "kodlar": ["A1"]}


def test_kart_farklari_ve_yeniden_adlandirma(excel_yolu):
    """Aynı çalışma kitabı tekrar: kart güncellemesi kapalıyken kartlar korunur ve fark raporlanır; kod gelen SAYFA-* ürünü yeniden adlandırılır."""
    import dataclasses
    from backend.depo.veritabani import Base, motor_olustur, oturum_fabrikasi
    engine = motor_olustur("sqlite://"); Base.metadata.create_all(engine)
    s = oturum_fabrikasi(engine)()
    o1 = ims.excel_tam_yukle(s, excel_yolu, "2026-2027", "A"); s.commit()
    assert o1["kart_farklari"] == []
    gecici = s.query(m.Urun).filter_by(gecici_kod=True).order_by(m.Urun.id).first()
    gecici_kod = gecici.kod
    sayfa_adi = gecici_kod.removeprefix("SAYFA-")
    normal = s.query(m.Urun).filter_by(gecici_kod=False).order_by(m.Urun.id).first()
    mz = s.query(m.Malzeme).order_by(m.Malzeme.id).first()
    asil_urun_ad, asil_malzeme_ad = normal.ad, mz.ad
    normal.ad = "ELLE DEGISTI"; mz.ad = "ELLE DEGISTI"; s.commit()

    orijinal = ims.eo.urun_oku
    def yamali(ws_f, ws_v, *ek):
        girdi, p, bek = orijinal(ws_f, ws_v, *ek)
        if ws_f.title == sayfa_adi:
            girdi = dataclasses.replace(girdi, kod="YENI.KOD.001")
        return girdi, p, bek
    ims.eo.urun_oku = yamali
    try:
        o2 = ims.excel_tam_yukle(s, excel_yolu, "2026-2027", "B", kartlari_guncelle=False); s.commit()
    finally:
        ims.eo.urun_oku = orijinal
    assert s.query(m.Urun).filter_by(kod=normal.kod).one().ad == "ELLE DEGISTI"
    assert s.query(m.Malzeme).filter_by(kod=mz.kod).one().ad == "ELLE DEGISTI"
    farklar = {(f["tur"], f["kod"]): f["alanlar"] for f in o2["kart_farklari"]}
    assert farklar[("urun", normal.kod)] == ["ad"] and farklar[("malzeme", mz.kod)] == ["ad"]
    assert o2["yeniden_adlandirilan"] == [{"eski": gecici_kod, "yeni": "YENI.KOD.001"}]
    yeni = s.query(m.Urun).filter_by(kod="YENI.KOD.001").one()
    assert yeni.id == gecici.id and yeni.gecici_kod is False and s.query(m.Urun).filter_by(kod=gecici_kod).count() == 0
    assert s.query(m.Urun).count() == 67
    o3 = ims.excel_tam_yukle(s, excel_yolu, "2026-2027", "C"); s.commit()   # güncelleme açık: kartlar çalışma kitabına döner
    assert s.query(m.Urun).filter_by(kod=normal.kod).one().ad == asil_urun_ad and s.query(m.Malzeme).filter_by(kod=mz.kod).one().ad == asil_malzeme_ad
    assert {(f["tur"], f["kod"]) for f in o3["kart_farklari"]} >= {("urun", normal.kod), ("malzeme", mz.kod)}
    s.close()


def test_calisma_kitabi_beklenen_yapida_degilse_dogrulama_hatasi(oturum, tmp_path):
    import openpyxl
    from backend.servisler.hatalar import DogrulamaHatasi
    wb = openpyxl.Workbook(); wb.active.append(["a", "b"]); yol = tmp_path / "alakasiz.xlsx"; wb.save(yol)
    with pytest.raises(DogrulamaHatasi, match="beklenen yapıda değil"):
        ims.excel_tam_yukle(oturum, yol, "2026-2027", "X")


def test_elle_k_m_degerleri_veri_olarak_tasinir(yuklu, excel_yolu):
    s, o = yuklu
    from fiyat_motoru import excel_okuyucu as eo
    assert s.query(m.ReceteSatiri).filter(m.ReceteSatiri.brut_miktar_elle.is_not(None)).count() > 0
    assert s.query(m.ReceteSatiri).filter(m.ReceteSatiri.birim_fiyat_elle.is_not(None)).count() > 0
    wb_f, wb_v = eo.excel_ac(excel_yolu)
    girdi, _, _ = eo.urun_oku(wb_f["009"], wb_v["009"])
    u = hs.urun_getir(s, girdi.kod)
    r = rs.aktif_recete(s, u.id, o["senaryo_id"])
    beklenen = [x.brut_miktar_elle for x in girdi.recete]
    assert [x.brut_miktar_elle for x in r.satirlar] == beklenen
    assert any(b is not None for b in beklenen)
    c = hs.hesapla(s, girdi.kod, o["senaryo_id"], date(2026, 10, 21))
    assert "elle" in c.fire_kaynaklari and any(x.miktar_kaynagi == "elle" for x in c.sonuc.satirlar if x.grup == "malzeme")
