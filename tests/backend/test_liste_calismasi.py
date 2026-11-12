"""Liste fiyatı çalışması: yalnız Berrak ürünleri; liste = satış ÷ pazar böleni (yurtiçi 0,63, yurtdışı 0,90), adıma en yakına yuvarlanır;
geçmiş liste fiyatları (ürün × yıl × pazar; elle / Excel), örnek veri, artış kıyası; parametre, marka ve tablo göçleri."""
from decimal import ROUND_HALF_UP, Decimal as D_
from io import BytesIO
import pytest
from openpyxl import Workbook, load_workbook
from sqlalchemy import text
from backend.depo import modeller as m
from backend.depo.veritabani import liste_fiyati_gocu, motor_olustur
from backend.servisler import hesap_servisi as hs, liste_kurallari as lk, liste_servisi as ls
from backend.servisler.hatalar import DogrulamaHatasi
from backend.tohum import liste_bolen_gocu, markalari_doldur, parametreleri_tohumla
from tests.backend.test_api import _kur, _senaryo, istemci  # noqa: F401  (fixture)

A = "/api/v1"
URUN = {"ad": "Test", "ambalaj_hacmi": "370", "hat": "Niko", "taze_tursu_sinifi": "Turşu/Turşu", "suzme_kg": "0.18"}


def _calisma(c, sid, **q):
    ek = "".join(f"&{k}={v}" for k, v in q.items())
    r = c.get(f"{A}/liste-calismasi?senaryo={sid}{ek}")
    assert r.status_code == 200, r.text
    return r.json()


def _xlsx(satirlar):
    wb = Workbook(); ws = wb.active
    for s in satirlar:
        ws.append(s)
    b = BytesIO(); wb.save(b)
    return b.getvalue()


def _berrak_kur(c, sid, oturum):
    """_kur + TEST ürününü ürün kartından Berrak yapar."""
    _kur(c, sid, oturum)
    r = c.put(f"{A}/urunler/TEST", json={**URUN, "marka": "berrak"})
    assert r.status_code == 200 and r.json()["marka"] == "Berrak", r.text


def _yuvarla(x, adim):
    return ((x / adim).quantize(D_(1), ROUND_HALF_UP) * adim).quantize(adim)


# ---------------------------------------------------------------- kurallar (birim)
@pytest.mark.parametrize("x,adim,beklenen", [
    ("12.37", "0.05", "12.35"), ("12.375", "0.05", "12.40"), ("12.374999", "0.05", "12.35"), ("12.325", "0.05", "12.35"),
    ("12.345", "0.01", "12.35"), ("12.344", "0.01", "12.34"), ("12.05", "0.10", "12.10"), ("12.049", "0.10", "12.00"),
    ("12.125", "0.25", "12.25"), ("12.124", "0.25", "12.00"), ("12.25", "0.50", "12.50"), ("12.2499", "0.50", "12.00"),
    ("12.5", "1", "13"), ("12.49", "1", "12"), ("12.5", "5", "15"), ("12.49", "5", "10"), ("0.024", "0.05", "0.00")])
def test_yuvarlama_sinir_degerleri(x, adim, beklenen):
    assert str(lk.yuvarla(D_(x), D_(adim))) == beklenen


def test_dogrulamalar():
    assert lk.yuvarlama_dogrula("0.1") == D_("0.10") and str(lk.yuvarlama_dogrula(D_("5.00"))) == "5"
    for kotu in ("0.03", "0", "-1", "2", "abc"):
        with pytest.raises(DogrulamaHatasi):
            lk.yuvarlama_dogrula(kotu)
    assert lk.bolen_dogrula("1") == 1 and lk.bolen_dogrula("0.63") == D_("0.63")
    for kotu in ("0", "-0.5", "1.01", "x"):
        with pytest.raises(DogrulamaHatasi):
            lk.bolen_dogrula(kotu)
    with pytest.raises(DogrulamaHatasi):
        lk.pazar_dogrula("abd")
    assert lk.berrak_mi("BERRAK") and lk.berrak_mi(" berrak ") and not lk.berrak_mi("Berrak Plus") and not lk.berrak_mi(None)
    assert lk.marka_turet("BERRAK ZEYTİN 370 ml") == "Berrak" and lk.marka_turet("Zeytin Berrak") == "Berrak" and lk.marka_turet("Zeytin") is None


# ---------------------------------------------------------------- çalışma
def test_yalniz_berrak_varsayilanlar_ve_deneme(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    d = _calisma(istemci, sid)
    assert d["kayitlar"] == [] and d["berrak_disi"] == 1 and d["ozet"]["urun_sayisi"] == 0   # TEST Berrak değil
    assert istemci.put(f"{A}/liste-fiyatlari", json={"urun_kodu": "TEST", "yil": 2025, "liste_fiyati": "1"}).status_code == 422
    assert istemci.put(f"{A}/urunler/TEST", json={**URUN, "marka": "Berrak"}).status_code == 200
    d = _calisma(istemci, sid)
    assert (d["pazar"], d["bolen"], d["bolen_kayitli"], d["varsayilan_bolen"], d["yil"], d["berrak_disi"]) == ("yurtici", "0.63", False, "0.63", 2026, 0)
    assert d["bolenler"] == {"yurtici": "0.63", "yurtdisi": "0.90"}
    assert (d["yuvarlama"], d["yuvarlama_kayitli"], d["varsayilan_yuvarlama"]) == ("0.01", False, "0.01")
    assert d["yuvarlama_secenekleri"] == ["0.01", "0.05", "0.10", "0.25", "0.50", "1", "5"]
    r = d["kayitlar"][0]
    satis = D_(r["satis_tl"])
    assert r["kod"] == "TEST" and abs(D_(r["yeni_liste_ham"]) - satis / D_("0.63")) < D_("0.000001")
    assert r["yeni_liste"] == str(_yuvarla(satis / D_("0.63"), D_("0.01")))
    assert r["onceki_liste"] is None and r["liste_artis"] is None and d["ornek_var"] is False and d["yillar"] == []
    # kaydetmeden deneme: ?bolen= ve ?yuvarlama=
    d2 = _calisma(istemci, sid, bolen="0.7", yuvarlama="0.05")
    assert (d2["bolen"], d2["yuvarlama"], d2["bolen_kayitli"]) == ("0.7", "0.05", False)
    assert d2["bolenler"]["yurtici"] == "0.63"   # deneme kayıtlıyı değiştirmez
    assert d2["kayitlar"][0]["yeni_liste"] == str(_yuvarla(satis / D_("0.7"), D_("0.05")))
    assert D_(d2["kayitlar"][0]["yeni_liste"]) % D_("0.05") == 0
    for kotu in ("bolen=0", "bolen=1.5", "yuvarlama=0.03", "pazar=abd"):
        assert istemci.get(f"{A}/liste-calismasi?senaryo={sid}&{kotu}").status_code == 422, kotu
    # yurtdışı pazarı
    dy = _calisma(istemci, sid, pazar="yurtdisi")
    assert (dy["pazar"], dy["bolen"], dy["varsayilan_bolen"]) == ("yurtdisi", "0.90", "0.90")
    assert dy["kayitlar"][0]["yeni_liste"] == str(_yuvarla(satis / D_("0.90"), D_("0.01")))


def test_parametreler_kayitli_ve_dogrulama(istemci, oturum):
    sid = _senaryo(istemci); _berrak_kur(istemci, sid, oturum)

    def ekle(a, v):
        return istemci.post(f"{A}/parametreler/{a}/degerler?senaryo={sid}", json={"deger": v, "gecerlilik_basi": "2026-01-01", "neden": "liste politikası"})
    for a, v in [("liste_bolen_yurtici", "0"), ("liste_bolen_yurtici", "1.2"), ("liste_bolen_yurtdisi", "-1"), ("liste_yuvarlama", "0.03"),
                 ("liste_yuvarlama", "0")]:
        assert ekle(a, v).status_code == 422, (a, v)
    assert ekle("liste_bolen", "0.6").status_code == 422   # eski anahtar artık yok
    assert ekle("liste_bolen_yurtici", "0.6").status_code == 201 and ekle("liste_bolen_yurtdisi", "1").status_code == 201
    assert ekle("liste_yuvarlama", "0.1").status_code == 201
    d = _calisma(istemci, sid)
    assert (d["bolen"], d["bolen_kayitli"], d["yuvarlama"], d["yuvarlama_kayitli"]) == ("0.6", True, "0.10", True)
    assert d["bolenler"] == {"yurtici": "0.6", "yurtdisi": "1"}
    assert D_(d["kayitlar"][0]["yeni_liste"]) == _yuvarla(D_(d["kayitlar"][0]["satis_tl"]) / D_("0.6"), D_("0.10"))
    assert _calisma(istemci, sid, pazar="yurtdisi")["bolen"] == "1"
    assert _calisma(istemci, sid, bolen="0.5")["bolen_kayitli"] is False


def test_elle_gecmis_iki_pazar_artis_ve_maliyet_kiyasi(istemci, oturum):
    sid = _senaryo(istemci); _berrak_kur(istemci, sid, oturum)
    r0 = _calisma(istemci, sid)["kayitlar"][0]
    yeni, maliyet = D_(r0["yeni_liste"]), D_(r0["maliyet_tl"])
    # 2025: liste yeni/1.4, maliyet maliyet/1.5 -> liste %40, maliyet %50 artmış; fark -10 puan
    liste25, mal25 = (yeni / D_("1.4")).quantize(D_("0.0001")), (maliyet / D_("1.5")).quantize(D_("0.0001"))
    r = istemci.put(f"{A}/liste-fiyatlari?senaryo={sid}", json={"urun_kodu": "TEST", "yil": 2025, "liste_fiyati": str(liste25), "birim_maliyet": str(mal25)})
    assert r.status_code == 200 and r.json()["pazar"] == "yurtici" and r.json()["bolen"] == "0.63"
    assert istemci.put(f"{A}/liste-fiyatlari", json={"urun_kodu": "TEST", "yil": 2024, "liste_fiyati": str(liste25 / 2)}).json()["bolen"] == "0.63"
    # aynı yıl yurtdışı: ayrı kayıt, bölen girişten
    ry = istemci.put(f"{A}/liste-fiyatlari", json={"urun_kodu": "TEST", "yil": 2025, "pazar": "yurtdisi", "liste_fiyati": "3", "bolen": "0.85"})
    assert ry.status_code == 200 and (ry.json()["pazar"], ry.json()["bolen"]) == ("yurtdisi", "0.85")
    d = _calisma(istemci, sid)
    r = d["kayitlar"][0]
    assert r["onceki_yil"] == 2025 and D_(r["onceki_liste"]) == liste25
    assert abs(D_(r["liste_artis"]) - D_("0.4")) < D_("0.001") and abs(D_(r["maliyet_artis"]) - D_("0.5")) < D_("0.001")
    assert abs(D_(r["fark"]) + D_("0.1")) < D_("0.002") and d["ozet"]["gerisinde"] == 1 and d["ozet"]["karsilastirilan"] == 1
    assert [(g["yil"], g["pazar"], g["bolen"]) for g in r["gecmis"]] == [(2025, "yurtici", "0.63"), (2024, "yurtici", "0.63")]
    assert [(y["yil"], y["maliyet_artis_ort"] is None) for y in d["yillar"]] == [(2025, True), (2026, False)]
    dy = _calisma(istemci, sid, pazar="yurtdisi")["kayitlar"][0]
    assert [(g["yil"], g["liste_fiyati"]) for g in dy["gecmis"]] == [(2025, "3")] and D_(dy["liste_artis"]) == D_(dy["yeni_liste"]) / 3 - 1
    # güncelleme + günlük; silme (pazara göre)
    assert istemci.put(f"{A}/liste-fiyatlari", json={"urun_kodu": "TEST", "yil": 2025, "liste_fiyati": "1"}).status_code == 200
    k = oturum.query(m.DegisiklikKaydi).filter_by(tablo="liste_fiyati", islem="guncelle").one()
    assert k.yeni["yil"] == 2025 and k.yeni["pazar"] == "yurtici" and k.eski["liste_fiyati"] == str(liste25)
    assert istemci.delete(f"{A}/liste-fiyatlari/TEST/2025?pazar=yurtdisi").status_code == 204
    assert istemci.delete(f"{A}/liste-fiyatlari/TEST/2025?pazar=yurtdisi").status_code == 404
    assert oturum.query(m.ListeFiyati).filter_by(yil=2025, pazar="yurtici").count() == 1
    assert istemci.delete(f"{A}/liste-fiyatlari/TEST/2024").status_code == 204
    assert oturum.query(m.DegisiklikKaydi).filter_by(tablo="liste_fiyati", islem="sil").count() == 2
    assert istemci.delete(f"{A}/liste-fiyatlari/TEST/2025?pazar=abd").status_code == 422
    assert istemci.put(f"{A}/liste-fiyatlari", json={"urun_kodu": "YOK", "yil": 2025, "liste_fiyati": "1"}).status_code == 404
    assert istemci.put(f"{A}/liste-fiyatlari", json={"urun_kodu": "TEST", "yil": 2025, "liste_fiyati": "0"}).status_code == 422
    assert istemci.put(f"{A}/liste-fiyatlari", json={"urun_kodu": "TEST", "yil": 2025, "liste_fiyati": "1", "pazar": "abd"}).status_code == 422


def test_excel_yukleme_pazar_sutunu_tek_islem(istemci, oturum):
    sid = _senaryo(istemci); _berrak_kur(istemci, sid, oturum)
    sablon = istemci.get(f"{A}/liste-fiyatlari/sablon.xlsx")
    ws = load_workbook(BytesIO(sablon.content)).active
    assert sablon.status_code == 200 and [c.value for c in ws[1]] == ["urun_kodu", "yil", "liste_fiyati", "birim_maliyet", "pazar"]
    assert [ws.cell(row=i, column=5).value for i in (2, 3)] == ["Yurtiçi", "Yurtdışı"]
    # pazar sütunu olmadan da okunur (yurtiçi); hatalı satırlar
    hatali = _xlsx([["Ürün Kodu", "Yıl", "Liste Fiyatı"], ["TEST", 2025, "40,5"], ["YOK", 2025, 10], ["TEST", 2025, 41]])
    r = istemci.post(f"{A}/liste-fiyatlari/yukle", files={"dosya": ("l.xlsx", hatali)})
    assert r.status_code == 422 and [h["satir_no"] for h in r.json()["alanlar"]["hatalar"]] == [3, 4]
    kotu_pazar = _xlsx([["urun_kodu", "yil", "liste_fiyati", "pazar"], ["TEST", 2025, 1, "Avrupa"]])
    r = istemci.post(f"{A}/liste-fiyatlari/yukle", files={"dosya": ("l.xlsx", kotu_pazar)})
    assert r.status_code == 422 and "pazar" in r.json()["alanlar"]["hatalar"][0]["mesaj"]
    assert oturum.query(m.ListeFiyati).count() == 0
    iyi = _xlsx([["urun_kodu", "yil", "liste_fiyati", "birim_maliyet", "Pazar"], ["TEST", 2025, "40,5", "", ""], ["TEST", 2024, 30, 18.2, "Yurtiçi"],
                 ["TEST", 2025, 28, "", "YURTDIŞI"], ["TEST", 2024, 21, "", "yurtdisi"]])
    r = istemci.post(f"{A}/liste-fiyatlari/yukle?senaryo={sid}", files={"dosya": ("l.xlsx", iyi)})
    assert r.status_code == 200 and r.json()["yazilan"] == 4
    g = {(k.yil, k.pazar): k for k in oturum.query(m.ListeFiyati)}
    assert g[(2025, "yurtici")].liste_fiyati == D_("40.5") and g[(2025, "yurtici")].birim_maliyet is None and g[(2024, "yurtici")].birim_maliyet == D_("18.2")
    assert g[(2025, "yurtdisi")].liste_fiyati == 28 and g[(2025, "yurtdisi")].bolen == D_("0.90") and g[(2025, "yurtici")].bolen == D_("0.63")
    # Berrak olmayan ürün dosyada: satır hatası
    hs.urun_kaydet(oturum, "DIGER", "Diğer Turşu", D_(370), "Niko", "Turşu/Turşu", D_("0.18"))
    r = istemci.post(f"{A}/liste-fiyatlari/yukle", files={"dosya": ("l.xlsx", _xlsx([["urun_kodu", "yil", "liste_fiyati"], ["DIGER", 2025, 5]]))})
    assert r.status_code == 422 and "Berrak" in r.json()["alanlar"]["hatalar"][0]["mesaj"]


def test_ornek_veri_iki_pazar_uret_sil_gercegi_ezmez(istemci, oturum):
    sid = _senaryo(istemci); _berrak_kur(istemci, sid, oturum)
    assert istemci.put(f"{A}/liste-fiyatlari", json={"urun_kodu": "TEST", "yil": 2024, "liste_fiyati": "7.77"}).status_code == 200
    r = istemci.post(f"{A}/liste-calismasi/ornek?senaryo={sid}")
    assert r.status_code == 200 and r.json()["yazilan"] == 5   # yurtiçi 2025, 2023 (2024 gerçek); yurtdışı 2025, 2024, 2023
    d = _calisma(istemci, sid)
    assert d["ornek_var"] is True and [(g["yil"], g["ornek"]) for g in d["kayitlar"][0]["gecmis"]] == [(2025, True), (2024, False), (2023, True)]
    l = D_(d["kayitlar"][0]["liste_artis"])
    assert D_("0.37") < l < D_("0.47")   # 2025 -> 2026 örnek artışı %42 ± 4 puan
    dy = _calisma(istemci, sid, pazar="yurtdisi")
    assert [g["yil"] for g in dy["kayitlar"][0]["gecmis"]] == [2025, 2024, 2023] and all(g["bolen"] == "0.90" for g in dy["kayitlar"][0]["gecmis"])
    assert D_("0.37") < D_(dy["kayitlar"][0]["liste_artis"]) < D_("0.47")
    # tekrar üretmek aynı sonucu verir (sapma koddan türetilir)
    istemci.post(f"{A}/liste-calismasi/ornek?senaryo={sid}")
    assert _calisma(istemci, sid)["kayitlar"][0]["liste_artis"] == d["kayitlar"][0]["liste_artis"]
    # örnek satıra elle yazılınca gerçek olur
    assert istemci.put(f"{A}/liste-fiyatlari", json={"urun_kodu": "TEST", "yil": 2023, "liste_fiyati": "5"}).json()["ornek"] is False
    assert istemci.delete(f"{A}/liste-calismasi/ornek").json()["yazilan"] == 4
    assert sorted(k.yil for k in oturum.query(m.ListeFiyati)) == [2023, 2024]
    assert oturum.query(m.DegisiklikKaydi).filter_by(tablo="liste_fiyati", islem="ornek_sil").count() == 1


# ---------------------------------------------------------------- marka
def test_marka_urun_kartinda_turetilir_duzenlenir_gunluge_duser(istemci, oturum):
    sid = _senaryo(istemci)
    r = istemci.put(f"{A}/urunler/B1", json={**URUN, "ad": "BERRAK Zeytin 370 ml"})
    assert r.status_code == 200 and r.json()["marka"] == "Berrak"   # addan türetildi
    assert istemci.put(f"{A}/urunler/N1", json={**URUN, "ad": "Niko Turşu"}).json()["marka"] is None
    # marka gönderilmeden güncelleme mevcut markayı korur
    assert istemci.put(f"{A}/urunler/B1", json={**URUN, "ad": "BERRAK Zeytin 370 ml", "hat": "Diğer"}).json()["marka"] == "Berrak"
    # bilerek boşaltma; açılış göçü geri yazmaz
    assert istemci.put(f"{A}/urunler/B1", json={**URUN, "ad": "BERRAK Zeytin 370 ml", "marka": ""}).json()["marka"] is None
    k = oturum.query(m.DegisiklikKaydi).filter_by(tablo="urun").order_by(m.DegisiklikKaydi.id.desc()).first()
    assert k.eski["marka"] == "Berrak" and k.yeni["marka"] == ""
    assert markalari_doldur(oturum) == 0 and oturum.query(m.Urun).filter_by(kod="B1").one().marka == ""
    assert istemci.put(f"{A}/urunler/N1", json={**URUN, "ad": "Niko Turşu", "marka": "x" * 65}).status_code == 422
    assert istemci.get(f"{A}/urunler/B1").json()["marka"] is None
    # Veri Girişi toplu kaydet yolu
    g = {"senaryo_id": sid, "hesabi_kaydet": False, "urun": {**URUN, "ad": "Niko Turşu", "marka": "Berrak"}, "neden": "marka düzeltme"}
    assert istemci.post(f"{A}/urunler/N1/kaydet?senaryo={sid}", json=g).status_code == 200
    assert istemci.get(f"{A}/urunler/N1").json()["marka"] == "Berrak"


def test_marka_gocu(oturum):
    for kod, ad, marka in [("A", "BERRAK ZEYTİN 1 kg", None), ("B", "Siyah Zeytin Berrak", None), ("C", "Niko Turşu", None), ("D", "Berrak Biber", "")]:
        oturum.add(m.Urun(kod=kod, ad=ad, ambalaj_hacmi=D_(1), hat="H", taze_tursu_sinifi="T", suzme_kg=D_(1), marka=marka))
    oturum.flush()
    assert markalari_doldur(oturum) == 2
    assert {u.kod: u.marka for u in oturum.query(m.Urun)} == {"A": "Berrak", "B": "Berrak", "C": None, "D": ""}
    assert markalari_doldur(oturum) == 0   # idempotent
    assert oturum.query(m.DegisiklikKaydi).filter_by(tablo="urun", islem="marka_turet").count() == 1


# ---------------------------------------------------------------- parametre göçü
def _sen(oturum):
    from datetime import date
    sz = m.Sezon(ad="2026-2027", baslangic=date(2026, 9, 1), bitis=date(2027, 8, 31)); oturum.add(sz); oturum.flush()
    sen = m.Senaryo(sezon_id=sz.id, tur="fiyat_calismasi", ad="A"); oturum.add(sen); oturum.flush()
    return sen


def test_parametre_gocu_eski_bolen_yurticiye_tasinir(oturum):
    from datetime import date
    eski = m.Parametre(anahtar="liste_bolen", aciklama="eski", birim="oran"); oturum.add(eski); oturum.flush()
    sen = _sen(oturum)
    oturum.add(m.ParametreDegeri(parametre_id=eski.id, senaryo_id=sen.id, deger=D_("0.6"), gecerlilik_basi=date(2026, 1, 1), neden="eski"))
    oturum.flush()
    parametreleri_tohumla(oturum)
    anahtarlar = {p.anahtar for p in oturum.query(m.Parametre)}
    assert "liste_bolen" not in anahtarlar and {"liste_bolen_yurtici", "liste_bolen_yurtdisi", "liste_yuvarlama"} <= anahtarlar
    assert ls.bolen_gecerli(oturum, sen.id, date(2026, 10, 1), "yurtici") == (D_("0.6"), True)
    assert ls.bolen_gecerli(oturum, sen.id, date(2026, 10, 1), "yurtdisi") == (D_("0.90"), False)
    assert liste_bolen_gocu(oturum) == 0 and parametreleri_tohumla(oturum) == 0   # idempotent
    assert oturum.query(m.DegisiklikKaydi).filter_by(tablo="parametre", islem="yeniden_adlandir").count() == 1


def test_parametre_gocu_ikisi_birden_varsa_degerler_tasinir(oturum):
    from datetime import date
    parametreleri_tohumla(oturum)
    eski = m.Parametre(anahtar="liste_bolen", aciklama="eski", birim="oran"); oturum.add(eski); oturum.flush()
    sen = _sen(oturum)
    oturum.add(m.ParametreDegeri(parametre_id=eski.id, senaryo_id=sen.id, deger=D_("0.7"), gecerlilik_basi=date(2026, 1, 1), neden="eski"))
    oturum.flush()
    assert liste_bolen_gocu(oturum) == 1
    assert oturum.query(m.Parametre).filter_by(anahtar="liste_bolen").count() == 0
    assert ls.bolen_gecerli(oturum, sen.id, date(2026, 10, 1), "yurtici") == (D_("0.7"), True)


# ---------------------------------------------------------------- liste_fiyati tablo göçü
ESKI_DDL = """CREATE TABLE liste_fiyati (id INTEGER NOT NULL, olusturma_zamani DATETIME DEFAULT (CURRENT_TIMESTAMP), olusturan VARCHAR(64) NOT NULL,
urun_id INTEGER NOT NULL, yil INTEGER NOT NULL, liste_fiyati VARCHAR(48) NOT NULL, birim_maliyet VARCHAR(48), ornek BOOLEAN DEFAULT '0' NOT NULL,
PRIMARY KEY (id), UNIQUE (urun_id, yil), FOREIGN KEY(urun_id) REFERENCES urun (id))"""


def test_liste_fiyati_tablo_gocu(tmp_path):
    e = motor_olustur(f"sqlite:///{tmp_path / 'eski.db'}")
    m.Urun.__table__.create(e)
    with e.begin() as c:
        c.execute(text(ESKI_DDL))
        c.execute(text("INSERT INTO urun (id, olusturan, kod, ad, ambalaj_hacmi, hat, suzme_kg, pazar, aktif, gecici_kod) "
                       "VALUES (1, 'x', 'U1', 'Berrak', '1', 'H', '1', 'Yurtiçi', 1, 0)"))
        c.execute(text("INSERT INTO liste_fiyati (id, olusturan, urun_id, yil, liste_fiyati, birim_maliyet, ornek) VALUES "
                       "(7, 'esma', 1, 2024, '10.5', '6', 0), (8, 'sistem', 1, 2025, '14.25', NULL, 1)"))
    assert liste_fiyati_gocu(e) is True
    with e.begin() as c:
        satirlar = c.execute(text("SELECT id, olusturan, urun_id, yil, pazar, liste_fiyati, birim_maliyet, bolen, ornek FROM liste_fiyati ORDER BY id")).all()
        assert [tuple(s) for s in satirlar] == [(7, "esma", 1, 2024, "yurtici", "10.5", "6", None, 0), (8, "sistem", 1, 2025, "yurtici", "14.25", None, None, 1)]
        # yeni kısıt: aynı ürün-yıl farklı pazar olur, aynı pazar olmaz
        c.execute(text("INSERT INTO liste_fiyati (olusturan, urun_id, yil, pazar, liste_fiyati, ornek) VALUES ('x', 1, 2024, 'yurtdisi', '9', 0)"))
        assert c.execute(text("SELECT name FROM sqlite_master WHERE name = 'liste_fiyati_eski'")).first() is None
    with pytest.raises(Exception), e.begin() as c:
        c.execute(text("INSERT INTO liste_fiyati (olusturan, urun_id, yil, pazar, liste_fiyati, ornek) VALUES ('x', 1, 2024, 'yurtdisi', '9', 0)"))
    assert liste_fiyati_gocu(e) is False   # idempotent: zaten yeni şema
    with e.begin() as c:
        assert c.execute(text("SELECT COUNT(*) FROM liste_fiyati")).scalar() == 3
    # yeni şemayla oluşturulmuş tabloda ve tablo yokken hiçbir şey yapmaz
    e2 = motor_olustur(f"sqlite:///{tmp_path / 'yeni.db'}")
    assert liste_fiyati_gocu(e2) is False
    m.Urun.__table__.create(e2); m.ListeFiyati.__table__.create(e2)
    assert liste_fiyati_gocu(e2) is False
    e.dispose(); e2.dispose()
