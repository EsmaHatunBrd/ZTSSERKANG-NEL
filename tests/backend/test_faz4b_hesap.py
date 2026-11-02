"""Faz 4b B1: hesap yanıtının Excel blokları (üretim, parametre özeti, döviz, birim/ZS/düğüm tipi, notlar)."""
from decimal import Decimal as D_
from tests.backend.test_api import _kur, _senaryo, istemci  # noqa: F401  (fixture yeniden kullanımı)

A = "/api/v1"


def _hesap(c, sid, **ek):
    r = c.post(f"{A}/urunler/TEST/hesapla", json={"senaryo_id": sid, "tarih": "2026-10-21", **ek})
    assert r.status_code == 200, r.text
    return r.json()


def _doviz_param(c, sid, anahtar, deger):
    assert c.post(f"{A}/parametreler/{anahtar}/degerler?senaryo={sid}", json={"deger": deger, "gecerlilik_basi": "2026-06-01", "neden": "t"}).status_code == 201


def test_uretim_ve_parametre_ozeti(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    g = _hesap(istemci, sid)
    u = g["uretim"]
    assert u["pazar"] == "Yurtiçi" and u["hat"] == "Niko" and u["taze_tursu_sinifi"] == "Turşu/Turşu"
    assert D_(u["ambalaj_hacmi"]) == 370 and D_(u["suzme_kg"]) == D_("0.18")
    assert D_(u["vardiya_uretim_adedi"]) == 65000 and D_(u["vardiya_saati"]) == D_("7.5")
    assert D_(u["dolum_personel"]) == 13 and D_(u["etiketleme_adedi"]) == 35000 and D_(u["etiket_personel"]) == 7
    assert D_(u["mal_kabul_miktar_kg"]) == D_("0.19") and D_(u["mal_kabul_fire"]) == 0 and u["pazarlama_yonetim_uygula"] is True
    p = g["parametreler"]
    assert D_(p["enflasyon"]) == D_("0.25") and p["maliyet_sapma"] is None
    assert D_(p["kurlar"]["USD"]) == 50 and D_(p["faiz"]["TL"]) == D_("0.4") and D_(p["stok_ay"]["USD"]) == 6
    assert D_(p["satis_kar"]) == D_("0.2") and [D_(x) for x in p["teklif_kar"]] == [D_("0.2")]
    assert g["notlar"] == []


def test_override_uretim_ve_parametre_yansir(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    g = _hesap(istemci, sid, override={"uretim": {"dolum_personel": "20"}, "parametreler": {"kur.USD": "55", "maliyet_sapma": "0.05"}})
    assert D_(g["uretim"]["dolum_personel"]) == 20 and D_(g["parametreler"]["kurlar"]["USD"]) == 55
    assert D_(g["parametreler"]["maliyet_sapma"]) == D_("0.05")


def test_doviz_finansman_ve_oranlar(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    for a, v in [("kur.GBP", "68"), ("faiz.GBP", "0.06"), ("stok_ay.GBP", "6"), ("kur.ZAR", "3"), ("faiz.ZAR", "0.1"), ("stok_ay.ZAR", "6")]:
        _doviz_param(istemci, sid, a, v)
    g = _hesap(istemci, sid)
    t, f = g["toplamlar"], g["fiyatlar"]
    assert set(t["finansman"]) == {"TL", "USD", "EUR", "GBP", "ZAR"} and t["finansman"]["TL"] == t["finansman_tl"]
    assert t["maliyet_gbp"] is not None and t["maliyet_zar"] is not None and f["satis_gbp"] is not None and f["satis_zar"] is not None
    assert D_(f["satis_gbp"]) > D_(t["maliyet_gbp"]) and D_(f["satis_zar"]) > D_(t["maliyet_zar"])
    assert D_(f["satis_kar_orani"]) == D_("0.2") and [D_(x) for x in f["teklif_kar_oranlari"]] == [D_("0.2")]
    assert g["toplamlar_firesiz"]["maliyet_gbp"] is not None and g["fiyatlar_firesiz"]["satis_kar_orani"] == f["satis_kar_orani"]


def test_doviz_yoksa_null(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    g = _hesap(istemci, sid)
    assert g["toplamlar"]["maliyet_gbp"] is None and g["toplamlar"]["maliyet_zar"] is None
    assert g["fiyatlar"]["satis_gbp"] is None and g["fiyatlar"]["satis_zar"] is None


def test_satir_birim_zs_dugum_tipi(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    satirlar = {(x["kod"], x["grup"]): x for x in _hesap(istemci, sid)["satirlar"]}
    kav = satirlar[("KAV", "malzeme")]
    assert kav["birim"] == "AD" and kav["zs"] == "S" and kav["dugum_tipi"] == "yaprak"
    beklenen = {"mal_kabul_iscilik": "KG", "mal_kabul_gug": "KG", "dolum_iscilik": "SN", "etiket_iscilik": "SN", "endirekt_iscilik": "SN", "elektrik": "SN",
                "dogalgaz": "SN", "amortisman": "SN", "diger_gug": "SN", "pazarlama": "ADET", "yonetim": "ADET"}
    for (kod, grup), x in satirlar.items():
        if grup != "malzeme":
            assert x["birim"] == beklenen.get(kod), kod
            assert x["zs"] is None and x["dugum_tipi"] is None
    assert set(beklenen) <= {k for k, _ in satirlar}


def test_ara_mamul_dugum_tipi(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    assert istemci.post(f"{A}/urunler/TEST/recete?senaryo={sid}", json=[
        {"malzeme_kodu": "TEST", "ad": "Ürün", "miktar": "1", "birim": "KG", "dugum_tipi": "ara_mamul", "birim_fiyat_elle": "1"},
        {"malzeme_kodu": "KAV", "ad": "Kavanoz", "miktar": "1", "birim": "AD"}]).status_code == 201
    s = _hesap(istemci, sid)["satirlar"]
    assert s[0]["dugum_tipi"] == "ara_mamul" and s[0]["birim"] == "KG" and s[1]["dugum_tipi"] == "yaprak"


def test_kayitli_gorunum_canli_ile_ayni_ve_eski_snapshot_null(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    hid = istemci.post(f"{A}/urunler/TEST/hesaplar", json={"senaryo_id": sid, "tarih": "2026-10-21"}).json()["id"]
    d = istemci.get(f"{A}/hesaplar/{hid}").json()
    canli = _hesap(istemci, sid)
    assert d["gorunum"] == canli and d["gorunum"]["uretim"]["hat"] == "Niko" and d["gorunum"]["parametreler"]["satis_kar"] == "0.2"
    # eski snapshot: uretim/parametreler/notlar anahtarları yok
    from backend.depo import modeller as m
    h = oturum.get(m.MaliyetHesabi, hid)
    gs = dict(h.girdi_snapshot); gs["girdi"] = {k: v for k, v in gs["girdi"].items() if k != "uretim"}
    gs.pop("parametreler"); gs.pop("notlar", None)
    h.girdi_snapshot = gs; oturum.flush()
    eski = istemci.get(f"{A}/hesaplar/{hid}").json()["gorunum"]
    assert eski["uretim"] is None and eski["parametreler"] is None and eski["notlar"] == []


def test_metin_parametre_ve_notlar(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    assert istemci.get(f"{A}/metin-parametreler?senaryo={sid}").json() == {"kayitlar": [], "toplam": 0}
    r = istemci.post(f"{A}/metin-parametreler?senaryo={sid}", json={"anahtar": "satis_fiyati_notu", "deger": "not bir", "gecerlilik_basi": "2026-06-01", "neden": "ilk"},
                     headers={"X-Kullanici": "esma"})
    assert r.status_code == 201 and r.json()["deger"] == "not bir" and r.json()["olusturan"] == "esma"
    istemci.post(f"{A}/metin-parametreler?senaryo={sid}", json={"anahtar": "satis_fiyati_notu", "deger": "not iki", "gecerlilik_basi": "2026-10-01", "neden": "yeni"})
    g = istemci.get(f"{A}/metin-parametreler?senaryo={sid}&tarih=2026-10-21").json()
    assert g["toplam"] == 1 and g["kayitlar"][0]["deger"] == "not iki"
    assert istemci.get(f"{A}/metin-parametreler?senaryo={sid}&tarih=2026-07-01").json()["kayitlar"][0]["deger"] == "not bir"
    gecmis = istemci.get(f"{A}/metin-parametreler?senaryo={sid}&gecmis=true").json()
    assert [x["deger"] for x in gecmis["kayitlar"]] == ["not iki", "not bir"]
    assert _hesap(istemci, sid)["notlar"] == ["not iki"]
    hid = istemci.post(f"{A}/urunler/TEST/hesaplar", json={"senaryo_id": sid, "tarih": "2026-10-21"}).json()["id"]
    istemci.post(f"{A}/metin-parametreler?senaryo={sid}", json={"anahtar": "satis_fiyati_notu", "deger": "not uc", "gecerlilik_basi": "2026-10-10", "neden": "x"})
    assert istemci.get(f"{A}/hesaplar/{hid}").json()["gorunum"]["notlar"] == ["not iki"]   # snapshot kayıt anındaki notu saklar


def test_metin_parametre_dogrulama(istemci, oturum):
    sid = _senaryo(istemci)
    g = {"anahtar": "yok_boyle", "deger": "x", "gecerlilik_basi": "2026-06-01", "neden": "x"}
    assert istemci.post(f"{A}/metin-parametreler?senaryo={sid}", json=g).status_code == 422
    assert istemci.post(f"{A}/metin-parametreler?senaryo={sid}", json={**g, "anahtar": "satis_fiyati_notu", "neden": ""}).status_code == 422
    assert istemci.post(f"{A}/metin-parametreler?senaryo=999", json={**g, "anahtar": "satis_fiyati_notu"}).status_code == 404


def test_tohum_maliyet_sapma_ve_kurlar(istemci, oturum):
    t = {x["anahtar"] for x in istemci.get(f"{A}/parametreler/tanimlar").json()["kayitlar"]}
    assert {"maliyet_sapma", "kur.ZAR", "kur.RUB"} <= t
