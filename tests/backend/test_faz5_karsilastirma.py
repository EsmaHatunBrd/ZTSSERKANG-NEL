"""Faz 5 T3: urun ailesi, karsilastirma servisi, /karsilastirma uclari, dashboard yeni alanlar."""
from datetime import date
from decimal import Decimal as D_
from types import SimpleNamespace
import pytest
from backend.depo import modeller as m
from backend.servisler import aile as aile_s, hesap_servisi as hs, karsilastirma_servisi as ks
from tests.backend.test_api import _kur, _senaryo, istemci  # noqa: F401

A = "/api/v1"
KART = {"ambalaj_hacmi": "370", "hat": "Niko", "taze_tursu_sinifi": "Turşu/Turşu", "suzme_kg": "0.18"}


# ------------------------------------------------------------------ aile_turet
@pytest.mark.parametrize("a,b", [
    ("Biberiye Turşu 370 ml Berrak", "Biberiye Turşu 720 ml Berrak"),
    ("Jalapeno B. Yeşil Dil. Turşu 2,5 kg Torba Berrak", "Jalapeno B. Yeşil Dil. Turşu 370 ml Berrak"),
    ("Salatalık Turşu 5lt Teneke", "Salatalık Turşu 1700 ml Cam"),
    ("Salatalık Turşu 5 lt Pet", "Salatalık Turşu 1062 ml Kavanoz"),
    ("Karışık Turşu 5 kg Fıçı TR", "KARIŞIK TURŞU 720ml Şişe"),
    ("Zeytin 3/1 Teneke", "Zeytin 5/1 Teneke"),
    ("Zeytin A9 Teneke", "Zeytin 370 ml Cam"),
])
def test_ayni_aile(a, b):
    assert aile_s.aile_turet(a) == aile_s.aile_turet(b)


def test_farkli_urunler_farkli_aile_ve_bos_sonuc():
    assert aile_s.aile_turet("Biberiye Turşu 370 ml") != aile_s.aile_turet("Salatalık Turşu 370 ml")
    assert aile_s.aile_turet("Biberiye Turşu 370 ml Berrak") == "biberiye turşu"
    assert aile_s.aile_turet("370 ml Berrak") == "370 ml berrak"   # sonuç boşsa adın kendisi (casefold)
    assert aile_s.aile_turet("IŞIK Turşu İ 1 kg") == "işik turşu i"
    assert aile_s.aile_turet("ZEYTIN 370 ml") == aile_s.aile_turet("Zeytin 720 ml") == aile_s.aile_turet("zeytın Teneke") == "zeytin"


# ------------------------------------------------------------------ aile: kayit, PATCH, doldurma
def test_urun_kaydet_aile_turetir_ve_patch(istemci, oturum):
    c = istemci
    assert c.put(f"{A}/urunler/F-1", json={"ad": "Biberiye Turşu 370 ml Berrak", **KART}).status_code == 200
    assert hs.urun_getir(oturum, "F-1").aile == "biberiye turşu"
    r = c.patch(f"{A}/urunler/F-1/aile", json={"aile": "Özel Aile"}, headers={"X-Kullanici": "esma"})
    # G3: kullanıcı görünen adı yazar, sunucu anahtarı türetir (ı/i katlanmış küçük harf); görünen ad saklanır
    assert r.status_code == 200 and r.json() == {"kod": "F-1", "aile": "özel aile", "aile_ad": "Özel Aile"}
    k = oturum.query(m.DegisiklikKaydi).filter_by(tablo="urun", islem="aile_degistir").one()
    assert (k.kullanici, k.eski, k.yeni) == ("esma", {"aile": "biberiye turşu", "aile_ad": None}, {"aile": "özel aile", "aile_ad": "Özel Aile"})
    # PUT kart güncellemesi elle atanan aileyi ezmez
    c.put(f"{A}/urunler/F-1", json={"ad": "Biberiye Turşu 720 ml Berrak", **KART})
    assert hs.urun_getir(oturum, "F-1").aile == "özel aile"
    r = c.patch(f"{A}/urunler/F-1/aile", json={"aile": None})
    assert r.json() == {"kod": "F-1", "aile": "biberiye turşu", "aile_ad": "Biberiye Turşu"}
    assert hs.urun_getir(oturum, "F-1").aile_ad is None   # yeniden türetince elle ad kalkar
    assert c.patch(f"{A}/urunler/YOK/aile", json={"aile": "x"}).status_code == 404
    assert c.patch(f"{A}/urunler/F-1/aile", json={"aile": "x" * 121}).status_code == 422


def test_bos_aile_doldurulur_idempotent(oturum):
    for kod, ad in (("T-1", "Ürün A 370 ml"), ("T-2", "Ürün A 720 ml")):
        oturum.add(m.Urun(kod=kod, ad=ad, ambalaj_hacmi=D_("370"), hat="H", taze_tursu_sinifi="T", suzme_kg=D_("0.2")))
    oturum.flush()
    assert aile_s.aileleri_doldur(oturum) == 2
    assert {u.aile for u in oturum.query(m.Urun)} == {"ürün a"}
    assert aile_s.aileleri_doldur(oturum) == 0


def test_urun_kaydet_eski_bos_aileyi_doldurur(oturum):
    u = hs.urun_kaydet(oturum, "E-1", "Eski Ürün 5 kg", D_("5000"), "H", "T", D_("5"))
    assert u.aile == "eski ürün"
    u.aile = None
    oturum.flush()
    hs.urun_kaydet(oturum, "E-1", "Eski Ürün 5 kg", D_("5000"), "H", "T", D_("5"))
    assert u.aile == "eski ürün"


def test_eksik_kolon_aile_eklenir():
    from sqlalchemy import text
    from backend.depo.veritabani import eksik_kolonlari_tamamla, motor_olustur
    e = motor_olustur("sqlite://")
    with e.begin() as c:
        c.execute(text("CREATE TABLE urun (id INTEGER PRIMARY KEY, kod TEXT)"))
        c.execute(text("CREATE TABLE recete_satiri (id INTEGER PRIMARY KEY, seviye INTEGER)"))
    # G3: elle yazılan görünen ad kolonu; 11.02.2026: reçete satırında elle Z/S ve para birimi (uretim_hedefi tablosu yok: atlanır)
    assert eksik_kolonlari_tamamla(e) == ["urun.aile", "urun.aile_ad", "recete_satiri.zs_elle", "recete_satiri.para_birimi_elle", "urun.marka"]
    assert eksik_kolonlari_tamamla(e) == []


# ------------------------------------------------------------------ yardimcilar
def _urun(oturum, kod="S-1", ad="Satış Ürünü", hacim="370", kg="0.5"):
    return hs.urun_kaydet(oturum, kod, ad, D_(hacim), "H", "T", D_(kg))


def _senaryo_nesnesi(oturum, sezon="2026-2027"):
    return hs.senaryo_olustur(oturum, sezon, "fiyat_calismasi", "S")


def _satis(oturum, u, tarih, fiyat, pb, adet, musteri="Müşteri A"):
    oturum.add(m.SatisGecmisi(urun_id=u.id, musteri=musteri, tarih=date.fromisoformat(tarih), fiyat=D_(fiyat), para_birimi=pb, adet=D_(adet)))
    oturum.flush()


# ------------------------------------------------------------------ gecen_yil
def test_gecen_yil_agirlikli_ortalama_pencere_ve_musteri(oturum):
    u, sen = _urun(oturum), _senaryo_nesnesi(oturum)   # sezon başı 2026-06-01 -> pencere 2025-06-01 .. 2026-05-31
    _satis(oturum, u, "2025-06-01", "10", "TL", "100")
    _satis(oturum, u, "2026-05-31", "20", "TL", "300", "Müşteri B")
    _satis(oturum, u, "2025-09-01", "2.5", "USD", "40", "Müşteri A")
    _satis(oturum, u, "2025-05-31", "999", "TL", "1")       # pencere dışı (önce)
    _satis(oturum, u, "2026-06-01", "999", "TL", "1")       # pencere dışı (sezon başı)
    g = ks.gecen_yil(oturum, u, sen)
    assert (g["donem_basi"], g["donem_sonu"]) == ("2025-06-01", "2026-05-31")
    tl = g["para_birimleri"]["TL"]
    assert D_(tl["fiyat"]) == (D_("10") * 100 + D_("20") * 300) / D_(400) == D_("17.5")
    assert (tl["adet"], tl["musteri_sayisi"], tl["kayit_sayisi"]) == ("400", 2, 2)
    assert D_(g["para_birimleri"]["USD"]["fiyat"]) == D_("2.5")
    assert (g["kayit_sayisi"], g["musteri_sayisi"]) == (3, 2)
    gb = ks.gecen_yil(oturum, u, sen, musteri="Müşteri B")
    assert set(gb["para_birimleri"]) == {"TL"} and D_(gb["para_birimleri"]["TL"]["fiyat"]) == 20
    assert ks.gecen_yil(oturum, u, sen, musteri="Yok") is None


def test_gecen_yil_kayit_yoksa_none_ve_toplu_tek_sorgu(oturum):
    u1, u2 = _urun(oturum, "S-1"), _urun(oturum, "S-2", "Başka")
    sen = _senaryo_nesnesi(oturum)
    assert ks.gecen_yil(oturum, u1, sen) is None
    _satis(oturum, u1, "2025-07-01", "4", "TL", "10")
    _satis(oturum, u2, "2025-07-01", "5", "TL", "10")
    sorgu = []
    from sqlalchemy import event
    dinleyici = lambda conn, cur, stmt, *a: sorgu.append(stmt)
    event.listen(oturum.get_bind(), "before_cursor_execute", dinleyici)
    try:
        toplu = ks.gecen_yil_toplu(oturum, sen)
    finally:
        event.remove(oturum.get_bind(), "before_cursor_execute", dinleyici)
    assert set(toplu) == {u1.id, u2.id} and len([q for q in sorgu if "satis_gecmisi" in q]) == 1


# ------------------------------------------------------------------ enflasyon_esigi
def _sahte_hesap(enf, tl, doviz):
    return SimpleNamespace(parametreler=SimpleNamespace(enflasyon=D_(enf)),
                           sonuc=SimpleNamespace(satis_fiyati_tl=D_(tl), satis_fiyati_doviz={k: D_(v) for k, v in doviz.items()}))


def test_enflasyon_esigi_altinda_ve_dovizde_sifir(oturum):
    u, sen = _urun(oturum), _senaryo_nesnesi(oturum)
    _satis(oturum, u, "2025-07-01", "100", "TL", "10")
    _satis(oturum, u, "2025-07-01", "2", "USD", "10")
    e = ks.enflasyon_esigi(oturum, u, sen, _sahte_hesap("0.25", "120", {"USD": "2.2"}))
    assert D_(e["TL"]["oran"]) == D_("0.96") and e["TL"]["durum"] == "altinda" and D_(e["TL"]["fark_yuzde"]) == D_("-4")
    assert D_(e["USD"]["oran"]) == D_("1.1") and e["USD"]["durum"] == "ustunde"   # döviz: enflasyon 0
    assert (e["TL"]["gecen_yil"], e["TL"]["yeni"]) == ("100", "120")
    e2 = ks.enflasyon_esigi(oturum, u, sen, _sahte_hesap("0.25", "125", {}))
    assert D_(e2["TL"]["oran"]) == 1 and e2["TL"]["durum"] == "ustunde" and "USD" not in e2   # eşit: üstünde (>= eşik)


def test_enflasyon_esigi_gecen_yil_yoksa_none(oturum):
    u, sen = _urun(oturum), _senaryo_nesnesi(oturum)
    assert ks.enflasyon_esigi(oturum, u, sen, _sahte_hesap("0.25", "120", {})) is None


# ------------------------------------------------------------------ uretim_adedi_etkisi
def _kapasite(oturum, sid, kod, hedef):
    oturum.add(m.UretimKapasitesi(senaryo_id=sid, urun_kodu=kod, urun_ad=kod, net_kapasite=D_(1), net_sure=D_(1), toplam_kapasite=D_(1), toplam_sure=D_(1),
                                  hedef_uretim=D_(hedef), ortalama_isci=D_(1)))
    oturum.flush()


def test_uretim_adedi_etkisi_motorla_birebir(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    u, sen = hs.urun_getir(oturum, "TEST"), hs.senaryo_getir(oturum, sid)
    t = date(2026, 10, 21)
    assert ks.uretim_adedi_etkisi(oturum, u, sen, t) is None   # kapasite kaydı yok
    _kapasite(oturum, sid, "TEST", "130000")
    e = ks.uretim_adedi_etkisi(oturum, u, sen, t)
    ref = hs.hesapla(oturum, "TEST", sid, t, override={"uretim": {"vardiya_uretim_adedi": D_("130000")}}).sonuc
    bu = hs.hesapla(oturum, "TEST", sid, t).sonuc
    assert D_(e["butce_adedi"]) == 65000 and D_(e["hedef_adedi"]) == 130000 and D_(e["oran"]) == 2
    assert abs(D_(e["maliyet_tl_hedef"]) - ref.finansman_dahil_maliyet_tl) < D_("1e-9")
    assert abs(D_(e["satis_tl_hedef"]) - ref.satis_fiyati_tl) < D_("1e-9")
    assert abs(D_(e["maliyet_usd_hedef"]) - ref.doviz_maliyet["USD"]) < D_("1e-9")
    assert abs(D_(e["maliyet_tl_butce"]) - bu.finansman_dahil_maliyet_tl) < D_("1e-9")
    assert D_(e["maliyet_tl_hedef"]) < D_(e["maliyet_tl_butce"])   # daha çok adet -> birim maliyet düşer


# ------------------------------------------------------------------ ambalaj_kg_trendi
def test_ambalaj_kg_trendi_sirali_fark_ve_hata(istemci, oturum):
    c = istemci
    sid = _senaryo(c); _kur(c, sid, oturum)
    sen = hs.senaryo_getir(oturum, sid)
    assert c.patch(f"{A}/urunler/TEST/aile", json={"aile": "trend"}).status_code == 200
    for kod, hacim, kg in (("TR-720", "720", "0.36"), ("TR-BOS", "1700", "1.0")):
        assert c.put(f"{A}/urunler/{kod}", json={"ad": kod, "ambalaj_hacmi": hacim, "hat": "Niko", "taze_tursu_sinifi": "Turşu/Turşu", "suzme_kg": kg}).status_code == 200
        assert c.patch(f"{A}/urunler/{kod}/aile", json={"aile": "trend"}).status_code == 200
    h = {"vardiya_uretim_adedi": "65000", "dolum_personel": "13", "etiketleme_adedi": "35000", "etiket_personel": "7", "mal_kabul_miktar_kg": "0.19"}
    assert c.put(f"{A}/urunler/TR-720/uretim-hedefi?senaryo={sid}", json=h).status_code == 200
    assert c.post(f"{A}/urunler/TR-720/recete?senaryo={sid}", json=[{"malzeme_kodu": "KAV", "ad": "Kavanoz", "miktar": "2", "birim": "AD", "fire_override": "0.02"}]).status_code == 201
    assert [x["kod"] for x in ks.ambalaj_kg_trendi(oturum, "trend", sen, date(2026, 10, 21))] == ["TEST", "TR-720"]   # Faz 5c: TR-BOS reçetesiz, üye değil
    t = ks.ambalaj_kg_trendi(oturum, "trend", sen, date(2026, 10, 21), tum=True)
    assert [x["kod"] for x in t] == ["TEST", "TR-720", "TR-BOS"]      # ambalaj hacmine göre
    assert t[0]["hata"] is None and t[1]["hata"] is None and t[2]["hata"]
    assert t[2]["satis_tl"] is None and t[2]["kg_basi_satis_tl"] is None and t[2]["onceki_ile_fark_yuzde"] is None
    ref = hs.hesapla(oturum, "TEST", sid, date(2026, 10, 21)).sonuc
    assert D_(t[0]["satis_tl"]) == ref.satis_fiyati_tl and D_(t[0]["kg_basi_satis_tl"]) == ref.satis_fiyati_tl / D_("0.18")
    assert t[0]["onceki_ile_fark_yuzde"] is None
    kg0, kg1 = D_(t[0]["kg_basi_satis_tl"]), D_(t[1]["kg_basi_satis_tl"])
    assert D_(t[1]["onceki_ile_fark_yuzde"]) == (kg1 / kg0 - 1) * 100
    assert D_(t[1]["suzme_kg_fiyati"]) > 0 and t[1]["suzme_kg"] == "0.36"


# ------------------------------------------------------------------ aile gorunen ad (I-2)
def test_aile_ad_turkce_kucuk_harf():
    assert aile_s.aile_turet("KARIŞIK TURŞU 370 ml") == "karişik turşu"
    assert aile_s.aile_ad_turet("KARIŞIK TURŞU 370 ml") == "karışık turşu"
    assert aile_s.aile_ad_turet("KIRMIZI SOĞAN Turşusu 1 kg Cam") == "kırmızı soğan turşusu"
    assert aile_s.aile_ad_turet("İzmir Biber 370 ml") == "izmir biber"
    assert aile_s.aile_ad_turet("370 ml Berrak") == "370 ml berrak"


def test_aile_gorunen_ad_bas_harf_buyuk():
    """B6: türetilen görünen ad Türkçe baş harf büyük; anahtar küçük harf kalır, birimler değişmez."""
    assert aile_s._baslik_tr("karışık turşu") == "Karışık Turşu"
    assert aile_s._baslik_tr("izmir biber") == "İzmir Biber"
    assert aile_s._baslik_tr("ılık çorba") == "Ilık Çorba"
    assert aile_s._baslik_tr("370 ml berrak") == "370 ml Berrak"
    from types import SimpleNamespace as N
    u = N(ad="İzmir Biber 370 ml", aile=aile_s.aile_turet("İzmir Biber 370 ml"), aile_ad=None)
    assert u.aile == "izmir biber" and aile_s.aile_gorunen_ad(u.aile, [u]) == "İzmir Biber"


def test_api_aile_ad(istemci, oturum):
    c = istemci
    sid = _senaryo(c)
    for kod, ad, hacim in (("K-1", "KARIŞIK TURŞU 370 ml", "370"), ("K-2", "KARIŞIK TURŞU 720 ml", "720")):
        r = c.put(f"{A}/urunler/{kod}", json={"ad": ad, **{**KART, "ambalaj_hacmi": hacim}})
        assert r.status_code == 200 and r.json()["aile"] == "karişik turşu" and r.json()["aile_ad"] == "Karışık Turşu"
    assert c.get(f"{A}/urunler/K-1").json()["aile_ad"] == "Karışık Turşu"
    l = c.get(f"{A}/karsilastirma/aileler?senaryo={sid}&tum=1").json()   # Faz 5c: reçetesiz ürünler, tum=1
    assert (l[0]["aile"], l[0]["aile_ad"]) == ("karişik turşu", "Karışık Turşu")
    r = c.get(f"{A}/karsilastirma/aile/kari%C5%9Fik%20tur%C5%9Fu?senaryo={sid}&tum=1")
    assert r.status_code == 200 and (r.json()["aile"], r.json()["aile_ad"]) == ("karişik turşu", "Karışık Turşu")
    # elle atanan aile: görünen ad anahtarın kendisi
    assert c.patch(f"{A}/urunler/K-1/aile", json={"aile": "Özel Aile"}).status_code == 200
    assert c.get(f"{A}/urunler/K-1").json()["aile_ad"] == "Özel Aile"


# ------------------------------------------------------------------ API
def test_api_aileler(istemci, oturum):
    c = istemci
    sid = _senaryo(c)
    for kod, ad, hacim in (("A-720", "Biberiye Turşu 720 ml Berrak", "720"), ("A-370", "Biberiye Turşu 370 ml Berrak", "370"), ("B-1", "Tek Ürün 5 kg", "5000")):
        assert c.put(f"{A}/urunler/{kod}", json={"ad": ad, **{**KART, "ambalaj_hacmi": hacim}}).status_code == 200
    assert c.get(f"{A}/karsilastirma/aileler?senaryo={sid}").json() == []   # Faz 5c: reçetesiz ürünler üye değil
    r = c.get(f"{A}/karsilastirma/aileler?senaryo={sid}&tum=1")
    assert r.status_code == 200, r.text
    assert r.json() == [
        {"aile": "biberiye turşu", "aile_ad": "Biberiye Turşu", "urun_sayisi": 2, "tek_uyeli": False,
         "urunler": [{"kod": "A-370", "ad": "Biberiye Turşu 370 ml Berrak", "ambalaj_hacmi": "370", "ambalaj_etiket": "370 ml"}, {"kod": "A-720", "ad": "Biberiye Turşu 720 ml Berrak", "ambalaj_hacmi": "720", "ambalaj_etiket": "720 ml"}]},
        {"aile": "tek ürün", "aile_ad": "Tek Ürün", "urun_sayisi": 1, "tek_uyeli": True, "urunler": [{"kod": "B-1", "ad": "Tek Ürün 5 kg", "ambalaj_hacmi": "5000", "ambalaj_etiket": "5 kg"}]}]
    assert c.get(f"{A}/karsilastirma/aileler?senaryo=999").status_code == 404


def test_api_urun_karsilastirma(istemci, oturum):
    c = istemci
    sid = _senaryo(c); _kur(c, sid, oturum)
    u = f"{A}/karsilastirma/urun/TEST?senaryo={sid}&tarih=2026-10-21"
    assert c.get(u).json() == {"gecen_yil": None, "enflasyon_esigi": None, "uretim_adedi_etkisi": None, "hesap_hatasi": None}
    tl = D_(c.post(f"{A}/urunler/TEST/hesapla", json={"senaryo_id": sid, "tarih": "2026-10-21"}).json()["fiyatlar"]["satis_tl"])
    for tarih, fiyat, adet, mus in (("2025-08-01", "10", "100", "A"), ("2026-02-01", "20", "300", "B")):
        assert c.post(f"{A}/satis-gecmisi", json={"urun_kodu": "TEST", "musteri": mus, "tarih": tarih, "fiyat": fiyat, "para_birimi": "TL", "adet": adet, "neden": "test"}).status_code == 201
    _kapasite(oturum, sid, "TEST", "130000")
    r = c.get(u)
    assert r.status_code == 200, r.text
    g = r.json()
    assert D_(g["gecen_yil"]["para_birimleri"]["TL"]["fiyat"]) == D_("17.5") and g["gecen_yil"]["musteri_sayisi"] == 2
    e = g["enflasyon_esigi"]["TL"]
    assert D_(e["oran"]) == tl / (D_("17.5") * D_("1.25")) and e["durum"] == "altinda"
    assert D_(g["uretim_adedi_etkisi"]["oran"]) == 2
    assert D_(c.get(u + "&musteri=B").json()["gecen_yil"]["para_birimleri"]["TL"]["fiyat"]) == 20
    assert c.get(f"{A}/karsilastirma/urun/YOK?senaryo={sid}").status_code == 404
    assert c.get(f"{A}/karsilastirma/urun/TEST?senaryo=999").status_code == 404


def test_api_urun_karsilastirma_hedefsiz_urun(istemci, oturum):
    c = istemci
    sid = _senaryo(c)
    assert c.put(f"{A}/urunler/H-1", json={"ad": "Hedefsiz", **KART}).status_code == 200
    r = c.get(f"{A}/karsilastirma/urun/H-1?senaryo={sid}")
    assert r.status_code == 200 and r.json()["hesap_hatasi"] and r.json()["enflasyon_esigi"] is None


def test_api_aile_trendi(istemci, oturum):
    c = istemci
    sid = _senaryo(c); _kur(c, sid, oturum)
    p = c.patch(f"{A}/urunler/TEST/aile", json={"aile": "Aile / Eğik"})
    assert p.status_code == 200 and p.json()["aile"] == "aile / eğik"   # G3: yol anahtarı türetilen küçük harfli anahtardır, ad ayrı döner
    r = c.get(f"{A}/karsilastirma/aile/aile%20%2F%20e%C4%9Fik?senaryo={sid}&tarih=2026-10-21")
    assert r.status_code == 200, r.text
    assert (r.json()["aile"], r.json()["aile_ad"]) == ("aile / eğik", "Aile / Eğik")
    assert [x["kod"] for x in r.json()["satirlar"]] == ["TEST"] and r.json()["satirlar"][0]["hata"] is None
    assert c.get(f"{A}/karsilastirma/aile/yok?senaryo={sid}").status_code == 404


def test_dashboard_yeni_alanlar_null_ve_dolu(istemci, oturum):
    c = istemci
    sid = _senaryo(c); _kur(c, sid, oturum)
    assert c.put(f"{A}/urunler/BOS", json={"ad": "Bos", **KART}).status_code == 200   # hesap hatası satırı
    yeni = ("gecen_yil_tl", "enflasyon_durumu", "enflasyon_fark_yuzde", "hedef_adet_maliyet_tl")
    satirlar = {x["kod"]: x for x in c.get(f"{A}/urunler?senaryo={sid}&tarih=2026-10-21&tum=1").json()["kayitlar"]}   # Faz 5c: BOS reçetesiz, tum=1
    assert all(satirlar["TEST"][a] is None for a in yeni) and all(satirlar["BOS"][a] is None for a in yeni)
    for tarih, fiyat, adet in (("2025-08-01", "10", "100"), ("2026-02-01", "20", "300")):
        c.post(f"{A}/satis-gecmisi", json={"urun_kodu": "TEST", "musteri": "A", "tarih": tarih, "fiyat": fiyat, "para_birimi": "TL", "adet": adet, "neden": "test"})
    _kapasite(oturum, sid, "TEST", "130000"); _kapasite(oturum, sid, "BOS", "1000")
    c.post(f"{A}/satis-gecmisi", json={"urun_kodu": "BOS", "musteri": "A", "tarih": "2025-08-01", "fiyat": "1", "para_birimi": "TL", "adet": "1", "neden": "test"})  # yazma -> önbellek boşalır
    satirlar = {x["kod"]: x for x in c.get(f"{A}/urunler?senaryo={sid}&tarih=2026-10-21&tum=1").json()["kayitlar"]}
    t = satirlar["TEST"]
    assert D_(t["gecen_yil_tl"]) == D_("17.5") and t["enflasyon_durumu"] == "altinda" and D_(t["enflasyon_fark_yuzde"]) < 0
    ref = hs.hesapla(oturum, "TEST", sid, date(2026, 10, 21), override={"uretim": {"vardiya_uretim_adedi": D_("130000")}}).sonuc
    assert abs(D_(t["hedef_adet_maliyet_tl"]) - ref.finansman_dahil_maliyet_tl) < D_("1e-9")
    b = satirlar["BOS"]
    assert b["hata"] and all(b[a] is None for a in yeni)   # hata satırı kırılmaz


# ------------------------------------------------------------------ düzeltme turu 1
def test_dashboard_satis_gecmisi_tek_sorgu_satissiz_urunlerle(istemci, oturum):
    """N+1 yok: satışı olmayan ürünler için enflasyon_esigi geçen yılı yeniden sorgulamaz."""
    from sqlalchemy import event
    from backend.api import urunler as api_urunler
    c = istemci
    sid = _senaryo(c); _kur(c, sid, oturum)
    for kod in ("D-1", "D-2", "D-3"):
        assert c.put(f"{A}/urunler/{kod}", json={"ad": kod, **KART}).status_code == 200
        h = {"vardiya_uretim_adedi": "65000", "dolum_personel": "13", "etiketleme_adedi": "35000", "etiket_personel": "7", "mal_kabul_miktar_kg": "0.19"}
        assert c.put(f"{A}/urunler/{kod}/uretim-hedefi?senaryo={sid}", json=h).status_code == 200
        assert c.post(f"{A}/urunler/{kod}/recete?senaryo={sid}", json=[{"malzeme_kodu": "KAV", "ad": "Kavanoz", "miktar": "1", "birim": "AD"}]).status_code == 201
    sorgu = []
    dinleyici = lambda conn, cur, stmt, *a: sorgu.append(stmt)
    event.listen(oturum.get_bind(), "before_cursor_execute", dinleyici)
    try:
        satirlar = api_urunler.dashboard_satirlari(oturum, sid, date(2026, 10, 21))
    finally:
        event.remove(oturum.get_bind(), "before_cursor_execute", dinleyici)
    assert len([x for x in satirlar if x["hata"] is None]) >= 4          # TEST + 3 ürün, hiçbirinin satışı yok
    assert len([q for q in sorgu if "satis_gecmisi" in q]) == 1


def test_api_urun_karsilastirma_override_hesabi_patlarsa_500_degil(istemci, oturum, monkeypatch):
    from decimal import InvalidOperation
    c = istemci
    sid = _senaryo(c); _kur(c, sid, oturum)
    c.post(f"{A}/satis-gecmisi", json={"urun_kodu": "TEST", "musteri": "A", "tarih": "2025-08-01", "fiyat": "10", "para_birimi": "TL", "adet": "100", "neden": "test"})
    _kapasite(oturum, sid, "TEST", "130000")
    gercek = hs.hesapla

    def sahte(s, kod, *a, override=None, **k):
        if override:
            raise InvalidOperation("test")
        return gercek(s, kod, *a, override=override, **k)
    monkeypatch.setattr(hs, "hesapla", sahte)
    r = c.get(f"{A}/karsilastirma/urun/TEST?senaryo={sid}&tarih=2026-10-21")
    assert r.status_code == 200, r.text
    g = r.json()
    assert g["gecen_yil"] is not None and g["enflasyon_esigi"] is not None       # diğer bölümler dolu kalır
    assert g["uretim_adedi_etkisi"] is None and "üretim adedi etkisi" in g["hesap_hatasi"]


def test_toplam_adet_sifir_ve_esik_paydasi_sifir(oturum):
    u, sen = _urun(oturum), _senaryo_nesnesi(oturum)
    oturum.add(m.SatisGecmisi(urun_id=u.id, musteri="A", tarih=date(2025, 7, 1), fiyat=D_("5"), para_birimi="TL", adet=D_("0")))
    oturum.flush()
    assert ks.gecen_yil(oturum, u, sen) is None                                   # Σadet = 0: bölme yok, para birimi atlanır
    _satis(oturum, u, "2025-07-02", "100", "TL", "10")
    assert ks.enflasyon_esigi(oturum, u, sen, _sahte_hesap("-1", "120", {})) is None   # eşik paydası 0


# ------------------------------------------------------------------ düzeltme turu 2: türetilmiş ambalaj alanları
@pytest.mark.parametrize("ad,etiket", [("Turşu 5 lt Teneke", "5 lt"), ("Turşu 2,5 kg Torba", "2,5 kg"), ("Turşu 1062ml Kavanoz", "1062 ml"),
                                       ("Turşu 370 ML", "370 ml"), ("Konserve 4 x 125 gr", "125 gr"), ("Zeytin 3/1 Teneke", None), ("Salça", None)])
def test_ambalaj_etiket(ad, etiket):
    assert aile_s.ambalaj_etiket(ad) == etiket


@pytest.mark.parametrize("ad,hacim,ml", [("Turşu 1062ml", "0.54", 1062), ("Turşu 5 lt", "5", 5000), ("Turşu 2,5 kg", "2.5", 2500), ("Konserve 4 x 125 gr", "300", 125),
                                         ("Turşu 370 ML", "370", 370), ("Zeytin 3/1", "3", 3000), ("Zeytin Teneke", "720", 720), ("Zeytin Teneke", "0.54", 540)])
def test_ambalaj_ml(ad, hacim, ml):
    assert aile_s.ambalaj_ml(ad, D_(hacim)) == ml


def test_aile_trend_siralamasi_ambalaj_ml_ve_yeni_alanlar(istemci, oturum):
    c = istemci
    sid = _senaryo(c)
    # ambalaj_hacmi birim tutarsız: 5 (lt), 370 (ml), 0.54 (1062 ml kavanoz) -> sıralama etiketten: 370, 1062, 5000
    for kod, ad, hacim in (("M-5", "Mix Turşu 5 lt", "5"), ("M-370", "Mix Turşu 370 ml", "370"), ("M-1062", "Mix Turşu 1062ml", "0.54")):
        assert c.put(f"{A}/urunler/{kod}", json={"ad": ad, **{**KART, "ambalaj_hacmi": hacim}}).status_code == 200
    u = c.get(f"{A}/urunler/M-5").json()
    assert u["aile"] == "mix turşu" and u["ambalaj_etiket"] == "5 lt"
    assert c.get(f"{A}/karsilastirma/aileler?senaryo={sid}").json() == []   # Faz 5c: reçetesiz ürünler senaryo üyesi değil; tum=1 eski davranış
    ail = c.get(f"{A}/karsilastirma/aileler?senaryo={sid}&tum=1").json()[0]
    assert [x["kod"] for x in ail["urunler"]] == ["M-370", "M-1062", "M-5"] and [x["ambalaj_etiket"] for x in ail["urunler"]] == ["370 ml", "1062 ml", "5 lt"]
    tr = c.get(f"{A}/karsilastirma/aile/mix%20turşu?senaryo={sid}&tum=1").json()["satirlar"]
    assert [x["kod"] for x in tr] == ["M-370", "M-1062", "M-5"]
    assert [x["ambalaj_ml"] for x in tr] == ["370", "1062", "5000"] and tr[0]["ambalaj_etiket"] == "370 ml"
    d = {x["kod"]: x for x in c.get(f"{A}/urunler?senaryo={sid}&tum=1").json()["kayitlar"]}
    assert d["M-5"]["ambalaj_etiket"] == "5 lt"


def test_dashboard_enflasyon_altinda_toplam_tum_satirlar(istemci, oturum):
    c = istemci
    sid = _senaryo(c); _kur(c, sid, oturum)
    assert c.get(f"{A}/urunler?senaryo={sid}&tarih=2026-10-21").json()["enflasyon_altinda_toplam"] == 0
    c.post(f"{A}/satis-gecmisi", json={"urun_kodu": "TEST", "musteri": "A", "tarih": "2025-08-01", "fiyat": "20", "para_birimi": "TL", "adet": "10", "neden": "test"})  # önbellek boşalır
    r = c.get(f"{A}/urunler?senaryo={sid}&tarih=2026-10-21&boyut=1&sayfa=2")   # TEST ilk sayfada değil/boş sayfa: yine de toplam tüm satırlardan
    assert r.json()["kayitlar"] == [] and r.json()["enflasyon_altinda_toplam"] == 1


# ------------------------------------------------------------------ aile görünen adla düzenleme (G3)
def test_aile_adi_yazilir_anahtar_turetilir(istemci, oturum):
    """Kullanıcı 'Karışık Turşu' yazar: anahtar addan türeyen ailelerle aynı ('karişik turşu'), görünen ad yazıldığı gibi kalır."""
    c = istemci
    sid = _senaryo(c)
    assert c.put(f"{A}/urunler/K-1", json={"ad": "KARIŞIK TURŞU 720 ml", **{**KART, "ambalaj_hacmi": "720"}}).status_code == 200
    assert c.put(f"{A}/urunler/K-2", json={"ad": "Bambaşka Ürün 370 ml", **KART}).status_code == 200
    r = c.patch(f"{A}/urunler/K-2/aile", json={"aile": "  Karışık   Turşu "})
    assert r.status_code == 200 and r.json() == {"kod": "K-2", "aile": "karişik turşu", "aile_ad": "Karışık Turşu"}
    u = c.get(f"{A}/urunler/K-2").json()
    assert (u["aile"], u["aile_ad"]) == ("karişik turşu", "Karışık Turşu")
    aileler = c.get(f"{A}/karsilastirma/aileler?senaryo={sid}&tum=1").json()   # Faz 5c: reçetesiz ürünler, tum=1
    grup = next(a for a in aileler if a["aile"] == "karişik turşu")
    assert grup["urun_sayisi"] == 2 and grup["aile_ad"] == "Karışık Turşu"   # elle yazılan ad gruba da ad olur
    assert aile_s.aile_anahtari("ÖZEL Aile") == "özel aile" and aile_s.aile_anahtari("x" * 200) == "x" * aile_s.MAKS_UZUNLUK
    assert c.patch(f"{A}/urunler/K-2/aile", json={"aile": "x" * 121}).status_code == 422
    # türetilen adı değiştirmeden Kaydet: yazım yok, günlük kaydı yok
    assert c.put(f"{A}/urunler/K-3", json={"ad": "KIRMIZI BİBER 370 ml", **KART}).status_code == 200
    n = oturum.query(m.DegisiklikKaydi).filter_by(islem="aile_degistir").count()
    r = c.patch(f"{A}/urunler/K-3/aile", json={"aile": "kırmızı biber"})
    assert r.status_code == 200 and r.json() == {"kod": "K-3", "aile": "kirmizi biber", "aile_ad": "Kırmızı Biber"}
    assert hs.urun_getir(oturum, "K-3").aile_ad is None
    assert oturum.query(m.DegisiklikKaydi).filter_by(islem="aile_degistir").count() == n
    r = c.patch(f"{A}/urunler/K-3/aile", json={"aile": "Kırmızı Biber"})   # B6: ekranda görünen baş harfli ad da "değişmedi"
    assert r.status_code == 200 and r.json()["aile_ad"] == "Kırmızı Biber" and hs.urun_getir(oturum, "K-3").aile_ad is None
    assert oturum.query(m.DegisiklikKaydi).filter_by(islem="aile_degistir").count() == n
