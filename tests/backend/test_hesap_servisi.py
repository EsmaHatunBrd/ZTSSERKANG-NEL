# tests/backend/test_hesap_servisi.py
from datetime import date
from decimal import Decimal as D_
import pytest
from backend.depo import modeller as m
from backend.servisler import fiyat_servisi as fs, gider_servisi as gs, hesap_servisi as hs, parametre_servisi as ps, recete_servisi as rs
from backend.servisler.hatalar import BulunamadiHatasi, DogrulamaHatasi
from backend.servisler.donusum import decimal_str
from fiyat_motoru.para import yakin
from tests.backend.test_gider_servisi import tohumla as gider_tohumla

T = date(2026, 6, 1)


@pytest.fixture
def ortam(oturum):
    sz = m.Sezon(ad="S", baslangic=T, bitis=date(2027, 5, 31)); oturum.add(sz); oturum.flush()
    sen = m.Senaryo(sezon_id=sz.id, tur="fiyat_calismasi", ad="A"); oturum.add(sen); oturum.flush()
    for a in ["enflasyon", "kur.USD", "kur.EUR", "faiz.TL", "stok_ay.TL", "faiz.USD", "stok_ay.USD", "faiz.EUR", "stok_ay.EUR",
              "satis_kar", "teklif_kar.1", "teklif_kar.2", "teklif_kar.3", "vardiya_saati"]:
        oturum.add(m.Parametre(anahtar=a))
    oturum.flush()
    for a, v in [("enflasyon", "0.25"), ("kur.USD", "50"), ("kur.EUR", "60"), ("faiz.TL", "0.4"), ("stok_ay.TL", "6"), ("faiz.USD", "0.06"),
                 ("stok_ay.USD", "6"), ("faiz.EUR", "0.06"), ("stok_ay.EUR", "6"), ("satis_kar", "0.2"), ("teklif_kar.1", "0.2"),
                 ("teklif_kar.2", "0.17"), ("teklif_kar.3", "0.14"), ("vardiya_saati", "7.5")]:
        ps.deger_ekle(oturum, sen.id, a, D_(v), T, "tohum")
    gider_tohumla(oturum, sen.id)
    fs.malzeme_ekle_veya_guncelle(oturum, "KAV", "Cam Kavanoz 370", "0008-Ambalaj Malzeme", "AD", "TL", "S"); fs.fiyat_ekle(oturum, sen.id, "KAV", D_("5.9"), T, "")
    fs.malzeme_ekle_veya_guncelle(oturum, "ETK", "Etiket", "0008-Ambalaj Malzeme", "AD", "EUR", "S"); fs.fiyat_ekle(oturum, sen.id, "ETK", D_("0.049"), T, "")
    fs.malzeme_ekle_veya_guncelle(oturum, "TAZ", "Sarı Biberiye Taze", "0001-Hammadde", "KG", "TL", "Z"); fs.fiyat_ekle(oturum, sen.id, "TAZ", D_(65), T, "")
    u = hs.urun_kaydet(oturum, "TEST", "Test Ürün", D_(370), "Niko", "Turşu/Turşu", D_("0.18"))
    hs.uretim_hedefi_kaydet(oturum, u.id, sen.id, vardiya_uretim_adedi=D_(65000), dolum_personel=D_(13), etiketleme_adedi=D_(35000),
                            etiket_personel=D_(7), mal_kabul_miktar_kg=D_("0.19013459"), mal_kabul_fire=D_(0), pazarlama_yonetim_uygula=True)
    rs.yeni_versiyon(oturum, u.id, sen.id, [
        {"malzeme_kodu": "KAV", "ad": "Cam Kavanoz 370", "miktar": D_(1), "birim": "AD", "fire_override": D_("0.02")},
        {"malzeme_kodu": "ETK", "ad": "Etiket", "miktar": D_(1), "birim": "AD", "fire_override": D_("0.02")},
        {"malzeme_kodu": "TAZ", "ad": "Sarı Biberiye Taze", "miktar": D_("0.19013459"), "birim": "KG"},
        {"malzeme_kodu": "YOK", "ad": "Fiyatsız Ara Mamul", "miktar": D_(1), "birim": "KG"},
    ], "import")
    return sen, u


def test_hesapla_faz1_ile_ayni(oturum, ortam):
    sen, _ = ortam
    c = hs.hesapla(oturum, "TEST", sen.id, date(2026, 10, 21))
    assert yakin(c.sonuc.malzeme_toplami, D_("22.884258554081633"))
    assert yakin(c.sonuc.direkt_iscilik_toplami, D_("1.9806745445746057"))
    assert yakin(c.sonuc.gug_toplami, D_("2.83610677949762"))
    assert c.fire_kaynaklari == ["satir", "satir", "yok", "yok"]
    assert any("YOK" in u for u in c.sonuc.uyarilar) and c.kullanilan_parametreler["kur.USD"] == D_(50)


def test_override_kaydetmeden(oturum, ortam):
    sen, _ = ortam
    normal = hs.hesapla(oturum, "TEST", sen.id, date(2026, 10, 21))
    dene = hs.hesapla(oturum, "TEST", sen.id, date(2026, 10, 21), override={"parametreler": {"stok_ay.TL": D_(2)}, "fire": {3: D_("0.05")}})
    assert dene.sonuc.finansman["TL"] < normal.sonuc.finansman["TL"]
    assert dene.girdi.recete[2].fire_orani == D_("0.05") and dene.fire_kaynaklari[2] == "satir"
    assert oturum.query(m.ParametreDegeri).filter_by(kapsam_tipi="urun").count() == 0


def _gerceklesen(oturum, sen, u):
    g = m.Senaryo(sezon_id=sen.sezon_id, tur="gerceklesen", ad="G"); oturum.add(g); oturum.flush()
    for k in oturum.query(m.ParametreDegeri).filter_by(senaryo_id=sen.id):
        ps.deger_ekle(oturum, g.id, k.parametre.anahtar, k.deger, k.gecerlilik_basi, "kopya")
    gider_tohumla(oturum, g.id)
    for kod, f in [("KAV", "5.9"), ("ETK", "0.049"), ("TAZ", "65")]:
        fs.fiyat_ekle(oturum, g.id, kod, D_(f), T, "")
    hs.uretim_hedefi_kaydet(oturum, u.id, g.id, vardiya_uretim_adedi=D_(65000), dolum_personel=D_(13), etiketleme_adedi=D_(35000),
                            etiket_personel=D_(7), mal_kabul_miktar_kg=D_("0.19013459"), mal_kabul_fire=D_(0), pazarlama_yonetim_uygula=True)
    rs.yeni_versiyon(oturum, u.id, g.id, [{"malzeme_kodu": "KAV", "ad": "K", "miktar": D_(1), "birim": "AD", "fire_override": D_("0.02")}], "import")
    return g


def test_gerceklesen_enflasyon_sifir(oturum, ortam):
    sen, u = ortam
    g = _gerceklesen(oturum, sen, u)
    c = hs.hesapla(oturum, "TEST", g.id, date(2026, 10, 21))
    assert c.parametreler.enflasyon == D_(0) and yakin(c.sonuc.malzeme_toplami, D_("5.9") / D_("0.98"))


def test_gerceklesen_enflasyon_override_reddedilir(oturum, ortam):
    sen, u = ortam
    g = _gerceklesen(oturum, sen, u)
    with pytest.raises(DogrulamaHatasi, match="Gerçekleşen çalışmada enflasyon"):
        hs.hesapla(oturum, "TEST", g.id, date(2026, 10, 21), override={"parametreler": {"enflasyon": D_("0.3")}})
    c = hs.hesapla(oturum, "TEST", g.id, date(2026, 10, 21), override={"parametreler": {"kur.USD": D_(55)}})
    assert c.parametreler.enflasyon == D_(0) and c.parametreler.kurlar["USD"] == D_(55)


def test_override_sinirlari(oturum, ortam):
    sen, _ = ortam
    t = date(2026, 10, 21)
    for sira in (0, -1, 5):
        with pytest.raises(DogrulamaHatasi):
            hs.hesapla(oturum, "TEST", sen.id, t, override={"fire": {sira: D_("0.05")}})
    with pytest.raises(DogrulamaHatasi):
        hs.hesapla(oturum, "TEST", sen.id, t, override={"parametreler": {"teklif_kar.0": D_("0.1")}})
    with pytest.raises(DogrulamaHatasi):
        hs.hesapla(oturum, "TEST", sen.id, t, override={"parametreler": {"yok.boyle": D_("0.1")}})
    with pytest.raises(DogrulamaHatasi):
        hs.hesapla(oturum, "TEST", sen.id, t, override={"uretim": {"yok_alan": 1}})
    c = hs.hesapla(oturum, "TEST", sen.id, t, override={"uretim": {"dolum_personel": D_(20), "etiket_personel": None}})
    assert c.girdi.uretim.dolum_personel == D_(20) and c.girdi.uretim.etiket_personel == D_(7)


def test_override_snapshota_yazilir(oturum, ortam):
    sen, _ = ortam
    t = date(2026, 10, 21)
    ov = {"parametreler": {"stok_ay.TL": D_(2)}, "fire": {3: D_("0.05")}}
    h = hs.kaydet(oturum, hs.hesapla(oturum, "TEST", sen.id, t, override=ov), "TEST", sen.id, t)
    assert h.girdi_snapshot["override"] == decimal_str(ov) == {"parametreler": {"stok_ay.TL": "2"}, "fire": {"3": "0.05"}}
    h2 = hs.kaydet(oturum, hs.hesapla(oturum, "TEST", sen.id, t), "TEST", sen.id, t)
    assert h2.girdi_snapshot["override"] is None


def test_snapshot_tamligi(oturum, ortam):
    sen, _ = ortam
    t = date(2026, 10, 21)
    h = hs.kaydet(oturum, hs.hesapla(oturum, "TEST", sen.id, t), "TEST", sen.id, t)
    sn = h.girdi_snapshot
    assert set(sn["malzemeler"]) == {"KAV", "ETK", "TAZ"} and sn["malzemeler"]["KAV"]["fiyat"] == "5.9"
    assert sn["recete"]["versiyon"] == 1 and sn["recete"]["id"] == rs.aktif_recete(oturum, h.urun_id, sen.id).id
    assert "override" in sn


def test_pasiflestirme_ve_guncelleme_aktifligi_bozmaz(oturum, ortam):
    sen, u = ortam
    hs.urun_pasiflestir(oturum, "TEST", "esma")
    assert hs.urun_getir(oturum, "TEST").aktif is False
    k = oturum.query(m.DegisiklikKaydi).filter_by(tablo="urun", islem="pasiflestir").one()
    assert k.kullanici == "esma" and k.eski == {"aktif": True} and k.yeni == {"aktif": False}
    hs.urun_kaydet(oturum, "TEST", "Test Ürün 2", D_(370), "Niko", "Turşu/Turşu", D_("0.18"))
    assert hs.urun_getir(oturum, "TEST").aktif is False
    fs.malzeme_pasiflestir(oturum, "KAV", "esma")
    assert oturum.query(m.Malzeme).filter_by(kod="KAV").one().aktif is False
    assert oturum.query(m.DegisiklikKaydi).filter_by(tablo="malzeme", islem="pasiflestir").count() == 1
    fs.malzeme_ekle_veya_guncelle(oturum, "KAV", "Cam Kavanoz 370 yeni", "0008-Ambalaj Malzeme", "AD", "TL", "S")
    assert oturum.query(m.Malzeme).filter_by(kod="KAV").one().aktif is False


def test_urun_kod_degistir(oturum, ortam):
    sen, u = ortam
    t = date(2026, 10, 21)
    h = hs.kaydet(oturum, hs.hesapla(oturum, "TEST", sen.id, t), "TEST", sen.id, t)
    hs.urun_kaydet(oturum, "DIGER", "Diğer", D_(370), "Niko", "Turşu/Turşu", D_("0.18"))
    with pytest.raises(DogrulamaHatasi):
        hs.urun_kod_degistir(oturum, "TEST", "DIGER", "esma")
    with pytest.raises(BulunamadiHatasi):
        hs.urun_kod_degistir(oturum, "YOKTU", "YENI", "esma")
    yeni = hs.urun_kod_degistir(oturum, "TEST", "03.001", "esma")
    assert yeni.id == u.id and yeni.kod == "03.001" and yeni.gecici_kod is False
    assert hs.getir(oturum, h.id).urun_id == u.id
    assert hs.hesapla(oturum, "03.001", sen.id, t).sonuc.malzeme_toplami == hs.hesapla(oturum, "03.001", sen.id, t).sonuc.malzeme_toplami
    k = oturum.query(m.DegisiklikKaydi).filter_by(tablo="urun", islem="kod_degistir").one()
    assert k.eski == {"kod": "TEST"} and k.yeni == {"kod": "03.001"}


def test_senaryo_olustur(oturum):
    sen = hs.senaryo_olustur(oturum, "2026-2027", "fiyat_calismasi", "Yeni", "açıklama", "esma")
    assert sen.id and sen.sezon.ad == "2026-2027" and sen.olusturan == "esma"
    with pytest.raises(DogrulamaHatasi):
        hs.senaryo_olustur(oturum, "yanlis", "fiyat_calismasi", "X", None, "esma")


def test_hesap_listesi_ve_degisiklikler(oturum, ortam):
    sen, u = ortam
    t = date(2026, 10, 21)
    h1 = hs.kaydet(oturum, hs.hesapla(oturum, "TEST", sen.id, t), "TEST", sen.id, t)
    h2 = hs.kaydet(oturum, hs.hesapla(oturum, "TEST", sen.id, t), "TEST", sen.id, t)
    assert [x.id for x in hs.hesaplar_listele(oturum, u.id, sen.id)] == [h2.id, h1.id]
    hs.urun_pasiflestir(oturum, "TEST")
    assert [k.islem for k in hs.degisiklikler(oturum, "urun", None)] == ["pasiflestir"]
    assert hs.degisiklikler(oturum, "urun", u.id)[0].kayit_id == u.id
    assert hs.degisiklikler(oturum, "malzeme", None) == []


def test_kaydet_ve_getir_snapshot(oturum, ortam):
    sen, _ = ortam
    c = hs.hesapla(oturum, "TEST", sen.id, date(2026, 10, 21))
    h = hs.kaydet(oturum, c, "TEST", sen.id, date(2026, 10, 21), "esma")
    ps.deger_ekle(oturum, sen.id, "kur.USD", D_(99), date(2026, 10, 22), "sonradan")
    g = hs.getir(oturum, h.id)
    assert g.sonuc_snapshot["finansman_dahil_maliyet_tl"] == str(c.sonuc.finansman_dahil_maliyet_tl)
    assert g.girdi_snapshot["parametreler"]["kurlar"]["USD"] == "50" and g.olusturan == "esma"


def test_toplu_hesapla_hata_izole(oturum, ortam):
    sen, _ = ortam
    hs.urun_kaydet(oturum, "RECETESIZ", "Reçetesiz", D_(370), "Niko", "Turşu/Turşu", D_("0.1"))
    assert list(dict(hs.toplu_hesapla(oturum, sen.id, date(2026, 10, 21)))) == ["TEST"]   # Faz 5c: reçetesiz ürün senaryo üyesi değil
    out = dict(hs.toplu_hesapla(oturum, sen.id, date(2026, 10, 21), tum=True))
    assert isinstance(out["TEST"], hs.HesapCiktisi) and isinstance(out["RECETESIZ"], BulunamadiHatasi)   # hedefi de yok: önce 'üretim hedefi yok'


def test_elle_brut_satira_fire_override_reddedilir_ve_firesiz_sonuc(oturum, ortam):
    sen, u = ortam
    rs.yeni_versiyon(oturum, u.id, sen.id, [
        {"malzeme_kodu": "KAV", "ad": "Cam Kavanoz 370", "miktar": D_(1), "birim": "AD", "fire_override": D_("0.02"), "brut_miktar_elle": D_("1.1")},
        {"malzeme_kodu": "TAZ", "ad": "Sarı Biberiye Taze", "miktar": D_("0.19013459"), "birim": "KG", "birim_fiyat_elle": D_(70)},
    ], "elle")
    c = hs.hesapla(oturum, "TEST", sen.id, date(2026, 10, 21))
    assert c.fire_kaynaklari[0] == "elle"
    kav, taz = c.sonuc.satirlar[0], c.sonuc.satirlar[1]
    assert kav.miktar_kaynagi == "elle" and kav.brut_miktar == D_("1.1") and kav.tutar_firesiz < kav.tutar
    assert taz.fiyat_kaynagi == "elle" and taz.birim_fiyat == D_(70)
    assert c.sonuc.firesiz is not None and c.sonuc.firesiz.malzeme_toplami < c.sonuc.malzeme_toplami
    with pytest.raises(DogrulamaHatasi, match="brüt miktarı elle girilmiş"):
        hs.hesapla(oturum, "TEST", sen.id, date(2026, 10, 21), override={"fire": {1: "0.1"}})
    c2 = hs.hesapla(oturum, "TEST", sen.id, date(2026, 10, 21), override={"fire": {2: "0.1"}})   # elle brütsüz satır serbest
    assert c2.fire_kaynaklari[1] == "satir"
