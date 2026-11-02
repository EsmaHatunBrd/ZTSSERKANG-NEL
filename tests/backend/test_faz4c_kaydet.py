"""Faz 4c B2: POST /urunler/{kod}/kaydet atomik toplu kayıt + B1 override API köprüsü."""
from decimal import Decimal as D_
import pytest
from fastapi.testclient import TestClient
from backend.depo import modeller as m
from backend.depo.veritabani import oturum_ver
from backend.tohum import parametreleri_tohumla
from backend.uygulama import uygulama_olustur
from tests.backend.test_api import _kur, _senaryo

API = "/api/v1"


@pytest.fixture
def istemci(oturum):
    """oturum_ver ile aynı sözleşme: başarıda commit, hatada rollback (yanıt gönderilmeden önce)."""
    app = uygulama_olustur()

    def _ver():
        try:
            yield oturum
            oturum.commit()
        except Exception:
            oturum.rollback()
            raise
    app.dependency_overrides[oturum_ver] = _ver
    parametreleri_tohumla(oturum); oturum.commit()
    return TestClient(app)


@pytest.fixture
def sid(istemci, oturum):
    s = _senaryo(istemci); _kur(istemci, s, oturum); oturum.commit()
    return s


def _urun_json(ad="Test"):
    return {"ad": ad, "ambalaj_hacmi": "370", "hat": "Niko", "taze_tursu_sinifi": "Turşu/Turşu", "suzme_kg": "0.18"}


def _hedef_json():
    return {"vardiya_uretim_adedi": "65000", "dolum_personel": "13", "etiketleme_adedi": "35000", "etiket_personel": "7", "mal_kabul_miktar_kg": "0.19"}


def _recete_json(fiyat_elle=None):
    return [{"malzeme_kodu": "KAV", "ad": "Kavanoz", "miktar": "1", "birim": "AD", "fire_override": "0.02", "birim_fiyat_elle": fiyat_elle}]


def _kaydet(c, sid, kod="TEST", **gov):
    return c.post(f"{API}/urunler/{kod}/kaydet", json={"senaryo_id": sid, "tarih": "2026-10-21", "neden": "ekrandan düzeltme", **gov}, headers={"X-Kullanici": "esma"})


def test_tam_govde_bes_tabloyu_yazar(istemci, oturum, sid):
    r = _kaydet(istemci, sid, urun=_urun_json("Yeni Ad"), uretim_hedefi={**_hedef_json(), "dolum_personel": "14"}, recete=_recete_json("6.5"),
                parametreler=[{"anahtar": "kur.USD", "deger": "55", "kapsam": "genel"}, {"anahtar": "teklif_kar.1", "deger": "0.3", "kapsam": "urun"}],
                gider_havuzlari=[{"kod": "dolum_iscilik", "toplam_tutar": "90000000"}])
    assert r.status_code == 200, r.text
    g = r.json()
    assert g["yazilan"] == {"urun": 1, "hedef": 1, "recete": 1, "parametre": 2, "havuz": 1}
    assert g["hesap_id"] is not None and g["hesap"]["urun_kodu"] == "TEST"
    assert g["hesap"]["kullanilan_parametreler"]["kur.USD"] == "55" and g["hesap"]["kullanilan_parametreler"]["teklif_kar.1"] == "0.3"
    assert D_(g["hesap"]["satirlar"][0]["birim_fiyat"]) == D_("6.5")   # kalıcı elle fiyat hesaba girdi
    u = oturum.query(m.Urun).filter_by(kod="TEST").one()
    assert u.ad == "Yeni Ad"
    receteler = oturum.query(m.Recete).filter_by(urun_id=u.id).order_by(m.Recete.versiyon).all()
    assert [(x.versiyon, x.aktif, x.kaynak) for x in receteler] == [(1, False, "elle"), (2, True, "ekran")]
    assert receteler[1].satirlar[0].birim_fiyat_elle == D_("6.5")
    pv = oturum.query(m.ParametreDegeri).join(m.Parametre).filter(m.Parametre.anahtar.in_(["kur.USD", "teklif_kar.1"]), m.ParametreDegeri.neden == "ekrandan düzeltme").all()
    assert {(x.kapsam_tipi, x.kapsam_id, str(x.deger)) for x in pv} == {("genel", None, "55"), ("urun", u.id, "0.3")}
    assert all(x.olusturan == "esma" and str(x.gecerlilik_basi) == "2026-10-21" for x in pv)
    for tablo in ("urun", "uretim_hedefi", "gider_havuzu"):
        kayit = oturum.query(m.DegisiklikKaydi).filter_by(tablo=tablo, kullanici="esma").all()
        assert len(kayit) == 1 and kayit[0].yeni["_neden"] == "ekrandan düzeltme", tablo
    assert oturum.query(m.MaliyetHesabi).filter_by(id=g["hesap_id"]).one().olusturan == "esma"


def test_hesabi_kaydetme(istemci, oturum, sid):
    once = oturum.query(m.MaliyetHesabi).count()
    r = _kaydet(istemci, sid, recete=_recete_json(), hesabi_kaydet=False)
    assert r.status_code == 200 and r.json()["hesap"] is None and r.json()["hesap_id"] is None
    assert r.json()["yazilan"]["recete"] == 1 and oturum.query(m.MaliyetHesabi).count() == once


@pytest.mark.parametrize("kotu", [
    {"parametreler": [{"anahtar": "yok.boyle", "deger": "1"}]},
    {"gider_havuzlari": [{"kod": "yok_havuz", "toplam_tutar": "1"}]},
    {"parametreler": [{"anahtar": "satis_kar", "deger": "0.1"}, {"anahtar": "satis_kar", "deger": "0.2"}]},
])
def test_atomiklik_hata_hicbir_sey_yazmaz(istemci, oturum, sid, kotu):
    u = oturum.query(m.Urun).filter_by(kod="TEST").one()
    sayim = lambda: (oturum.query(m.Recete).count(), oturum.query(m.ParametreDegeri).count(), oturum.query(m.DegisiklikKaydi).count(),
                     oturum.query(m.MaliyetHesabi).count())
    once = sayim()
    r = _kaydet(istemci, sid, urun=_urun_json("Değişen"), uretim_hedefi={**_hedef_json(), "dolum_personel": "20"}, recete=_recete_json("9"), **kotu)
    assert r.status_code == 422, r.text
    oturum.expire_all()
    assert sayim() == once
    assert oturum.get(m.Urun, u.id).ad == "Test"
    assert oturum.query(m.UretimHedefi).filter_by(urun_id=u.id).one().dolum_personel == D_(13)
    assert [x.versiyon for x in oturum.query(m.Recete).filter_by(urun_id=u.id)] == [1]


def test_servis_commit_etmez_rollback_geri_alir(oturum, istemci, sid):
    """Servis yalnız flush eder: hata sonrası çağıranın rollback'i her şeyi geri alır (ön doğrulamadan geçen, geç adımda patlayan girdi)."""
    from backend.api.semalar import TopluKaydetGiris
    from backend.servisler import hesap_servisi as hs
    from backend.servisler.hatalar import DogrulamaHatasi
    g = TopluKaydetGiris(senaryo_id=sid, neden="x", urun=_urun_json("Başka"), recete=_recete_json("9"),
                         parametreler=[{"anahtar": "yok.boyle", "deger": "1"}])
    with pytest.raises(DogrulamaHatasi):
        hs.toplu_kaydet(oturum, "TEST", g, "esma")
    oturum.rollback()
    assert oturum.query(m.Urun).filter_by(kod="TEST").one().ad == "Test"
    assert oturum.query(m.Recete).count() == 1


def test_havuz_yalniz_toplam_tutar_degisir(istemci, oturum, sid):
    h0 = oturum.query(m.GiderHavuzu).filter_by(senaryo_id=sid, kod="elektrik").one()
    onceki = (h0.ad, h0.baz_tipi, h0.baz_miktar, [(a.alt_kalem, a.pay_orani, a.baz_miktar) for a in h0.anahtarlar], h0.toplam_tutar)
    r = _kaydet(istemci, sid, gider_havuzlari=[{"kod": "elektrik", "toplam_tutar": "15000000"}], hesabi_kaydet=False)
    assert r.status_code == 200 and r.json()["yazilan"]["havuz"] == 1
    oturum.expire_all()
    h = oturum.query(m.GiderHavuzu).filter_by(senaryo_id=sid, kod="elektrik").one()
    assert h.toplam_tutar == D_(15000000) and onceki[4] != h.toplam_tutar
    assert (h.ad, h.baz_tipi, h.baz_miktar, [(a.alt_kalem, a.pay_orani, a.baz_miktar) for a in h.anahtarlar]) == onceki[:4]
    k = oturum.query(m.DegisiklikKaydi).filter_by(tablo="gider_havuzu", kayit_id=h.id).one()
    assert k.yeni["_neden"] == "ekrandan düzeltme" and k.yeni["toplam_tutar"] == "15000000" and k.eski["toplam_tutar"] == str(onceki[4])
    assert k.eski["anahtarlar"] == k.yeni["anahtarlar"]


def test_degismeyen_havuz_kayit_acmaz(istemci, oturum, sid):
    h = oturum.query(m.GiderHavuzu).filter_by(senaryo_id=sid, kod="elektrik").one()
    r = _kaydet(istemci, sid, gider_havuzlari=[{"kod": "elektrik", "toplam_tutar": str(h.toplam_tutar)}], hesabi_kaydet=False)
    assert r.status_code == 200 and r.json()["yazilan"]["havuz"] == 0
    assert oturum.query(m.DegisiklikKaydi).filter_by(tablo="gider_havuzu", kayit_id=h.id).count() == 0


def test_urun_kapsamli_parametre_baska_urunu_etkilemez(istemci, oturum, sid):
    assert istemci.put(f"{API}/urunler/DIGER", json=_urun_json("Diğer")).status_code == 200
    assert istemci.put(f"{API}/urunler/DIGER/uretim-hedefi?senaryo={sid}", json=_hedef_json()).status_code == 200
    assert istemci.post(f"{API}/urunler/DIGER/recete?senaryo={sid}", json=_recete_json()).status_code == 201
    hesap = lambda kod: istemci.post(f"{API}/urunler/{kod}/hesapla", json={"senaryo_id": sid, "tarih": "2026-10-21"}).json()
    once = hesap("DIGER")
    r = _kaydet(istemci, sid, parametreler=[{"anahtar": "satis_kar", "deger": "0.5", "kapsam": "urun"}])
    assert r.status_code == 200
    assert r.json()["hesap"]["fiyatlar"]["satis_kar_orani"] == "0.5"
    assert hesap("DIGER") == once and hesap("DIGER")["fiyatlar"]["satis_kar_orani"] == "0.2"
    assert hesap("TEST")["fiyatlar"]["satis_kar_orani"] == "0.5"


def test_gerceklesen_senaryoda_enflasyon_yazilamaz(istemci, oturum, sid):
    gs = istemci.post(f"{API}/senaryolar", json={"sezon_ad": "2026-2027", "tur": "gerceklesen", "ad": "G"}).json()["id"]
    r = _kaydet(istemci, gs, parametreler=[{"anahtar": "enflasyon", "deger": "0.3"}], hesabi_kaydet=False)
    assert r.status_code == 422 and r.json()["hata"]


def test_dogrulama_ve_404(istemci, sid):
    assert _kaydet(istemci, sid, kod="YOKTUR").status_code == 404
    assert istemci.post(f"{API}/urunler/TEST/kaydet", json={"senaryo_id": sid, "neden": ""}).status_code == 422
    assert _kaydet(istemci, 9999).status_code == 404
    assert _kaydet(istemci, sid, gider_havuzlari=[{"kod": "elektrik", "toplam_tutar": "-1"}]).status_code == 422
    assert _kaydet(istemci, sid, recete=[]).status_code == 422


def test_override_yeni_alanlari_api_uzerinden(istemci, oturum, sid):
    hesap = lambda ov: istemci.post(f"{API}/urunler/TEST/hesapla", json={"senaryo_id": sid, "tarih": "2026-10-21", "override": ov})
    temel = hesap({}).json()
    r = hesap({"satirlar": {"1": {"birim_fiyat_elle": "8"}}, "gider_oranlari": {"dolum_iscilik_sn": "1"}, "urun": {"suzme_kg": "0.5"}})
    assert r.status_code == 200, r.text
    g = r.json()
    assert D_(g["satirlar"][0]["birim_fiyat"]) == D_(8) and g["satirlar"][0]["fiyat_kaynagi"] == "elle"
    assert D_(g["toplamlar"]["maliyet_tl"]) != D_(temel["toplamlar"]["maliyet_tl"]) and g["uretim"]["suzme_kg"] == "0.5"
    h = istemci.post(f"{API}/urunler/TEST/hesaplar", json={"senaryo_id": sid, "tarih": "2026-10-21", "override": {"satirlar": {"1": {"miktar": "2"}}}})
    assert h.status_code == 201
    sn = istemci.get(f"{API}/hesaplar/{h.json()['id']}").json()["girdi_snapshot"]["override"]
    assert sn["satirlar"]["1"]["miktar"] == "2"
    for kotu in ({"satirlar": {"0": {"miktar": "1"}}}, {"satirlar": {"1": {"bilinmeyen": 1}}}, {"gider_oranlari": {"yok": "1"}}, {"satirlar": {"1": {"miktar": "-1"}}},
                 {"urun": {"pazar": "Mars"}}, {"satirlar": {"5": {"miktar": "1"}}}):
        assert hesap(kotu).status_code == 422, kotu
    assert hesap({"satirlar": {"1": {"elle_fiyat_kaldir": True}}}).status_code == 200


# ---- B2 follow-up: kaydet'e override (kalıcı olmayan what-if değerleri yalnız bu hesapta) ----
_OV = {"gider_oranlari": {"elektrik_sn.Niko": "50"}}


def test_kaydet_override_snapshota_girer_kalici_yazmaz(istemci, oturum, sid):
    temel = istemci.post(f"{API}/urunler/TEST/hesapla", json={"senaryo_id": sid, "tarih": "2026-10-21"}).json()
    pd_once, gh_once, dk_once = (oturum.query(x).count() for x in (m.ParametreDegeri, m.GiderHavuzu, m.DegisiklikKaydi))
    r = _kaydet(istemci, sid, override=_OV)
    assert r.status_code == 200, r.text
    g = r.json()
    assert D_(g["hesap"]["toplamlar"]["maliyet_tl"]) != D_(temel["toplamlar"]["maliyet_tl"])   # yanıt override'ı yansıtır
    h = oturum.query(m.MaliyetHesabi).filter_by(id=g["hesap_id"]).one()
    assert h.girdi_snapshot["override"]["gider_oranlari"] == {"elektrik_sn.Niko": "50"}
    temel_id = istemci.post(f"{API}/urunler/TEST/hesaplar", json={"senaryo_id": sid, "tarih": "2026-10-21"}).json()["id"]
    assert h.sonuc_snapshot != oturum.query(m.MaliyetHesabi).filter_by(id=temel_id).one().sonuc_snapshot
    assert (oturum.query(m.ParametreDegeri).count(), oturum.query(m.GiderHavuzu).count(), oturum.query(m.DegisiklikKaydi).count()) == (pd_once, gh_once, dk_once)
    assert g["yazilan"] == {"urun": 0, "hedef": 0, "recete": 0, "parametre": 0, "havuz": 0}


def test_kaydet_override_ve_kalici_parametre_birlikte(istemci, oturum, sid):
    r = _kaydet(istemci, sid, override=_OV, parametreler=[{"anahtar": "kur.USD", "deger": "55", "kapsam": "genel"}])
    assert r.status_code == 200, r.text
    g = r.json()
    assert g["hesap"]["kullanilan_parametreler"]["kur.USD"] == "55"
    h = oturum.query(m.MaliyetHesabi).filter_by(id=g["hesap_id"]).one()
    assert h.girdi_snapshot["override"]["gider_oranlari"] == {"elektrik_sn.Niko": "50"}
    assert "kur.USD" not in (h.girdi_snapshot["override"].get("parametreler") or {})   # sunucu kalıcı değeri override'a kopyalamaz
    assert h.girdi_snapshot["kullanilan_parametreler"]["kur.USD"] == "55"


def test_kaydet_override_hesabi_kaydetme_ile_422(istemci, oturum, sid):
    once = oturum.query(m.ParametreDegeri).count()
    r = _kaydet(istemci, sid, override=_OV, hesabi_kaydet=False, parametreler=[{"anahtar": "kur.USD", "deger": "56"}])
    assert r.status_code == 422
    assert oturum.query(m.ParametreDegeri).count() == once


def test_kaydet_kotu_override_422(istemci, sid):
    assert _kaydet(istemci, sid, override={"gider_oranlari": {"yok": "1"}}).status_code == 422
    assert _kaydet(istemci, sid, override={"satirlar": {"0": {"miktar": "1"}}}).status_code == 422


def test_genel_yazim_urun_kapsamli_deger_golgelemez_urun_de_guncellenir(istemci, oturum, sid):
    from backend.servisler import parametre_servisi as ps
    from datetime import date
    assert istemci.put(f"{API}/urunler/DIGER", json=_urun_json("Diğer")).status_code == 200
    assert istemci.put(f"{API}/urunler/DIGER/uretim-hedefi?senaryo={sid}", json=_hedef_json()).status_code == 200
    assert istemci.post(f"{API}/urunler/DIGER/recete?senaryo={sid}", json=_recete_json()).status_code == 201
    test_id = oturum.query(m.Urun).filter_by(kod="TEST").one().id
    diger_id = oturum.query(m.Urun).filter_by(kod="DIGER").one().id
    ps.deger_ekle(oturum, sid, "kur.USD", D_("38"), date(2026, 10, 1), "eski ürün değeri", kapsam_tipi="urun", kapsam_id=test_id); oturum.commit()
    once = oturum.query(m.ParametreDegeri).count()
    r = _kaydet(istemci, sid, parametreler=[{"anahtar": "kur.USD", "deger": "40", "kapsam": "genel"}])
    assert r.status_code == 200, r.text
    g = r.json()
    assert oturum.query(m.ParametreDegeri).count() == once + 2
    assert g["hesap"]["kullanilan_parametreler"]["kur.USD"] == "40"
    assert ps.gecerli_degerler(oturum, sid, date(2026, 10, 21), test_id)["kur.USD"] == D_("40")
    assert ps.gecerli_degerler(oturum, sid, date(2026, 10, 21), diger_id)["kur.USD"] == D_("40")
    assert "kur.USD: bu ürüne özel değer vardı; ürün değeri de güncellendi" in g["uyarilar"]


def test_kaydet_kalici_yazimlar_ve_kotu_override_422_sayilar_degismez(istemci, oturum, sid):
    p0, r0 = oturum.query(m.ParametreDegeri).count(), oturum.query(m.Recete).count()
    r = _kaydet(istemci, sid, recete=_recete_json("6.5"), parametreler=[{"anahtar": "kur.USD", "deger": "77", "kapsam": "genel"}],
                override={"gider_oranlari": {"yok": "1"}})
    assert r.status_code == 422
    assert oturum.query(m.ParametreDegeri).count() == p0 and oturum.query(m.Recete).count() == r0


def test_commit_hatasi_200_degil_hata_doner(oturum, monkeypatch):
    """N1: OturumDep scope="function" -> commit yanıttan önce çalışır; başarısız commit istemciye 500 olarak yansır."""
    app = uygulama_olustur()

    def _ver():
        try:
            yield oturum
            oturum.commit()
        except Exception:
            oturum.rollback()
            raise
    app.dependency_overrides[oturum_ver] = _ver
    parametreleri_tohumla(oturum); oturum.commit()
    c = TestClient(app, raise_server_exceptions=False)
    monkeypatch.setattr(oturum, "commit", lambda: (_ for _ in ()).throw(RuntimeError("commit patladı")))
    r = c.post(f"{API}/senaryolar", json={"sezon_ad": "2026-2027", "tur": "fiyat_calismasi", "ad": "X"})
    assert r.status_code == 500
