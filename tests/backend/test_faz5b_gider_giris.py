"""Faz 5b G1: gider havuzunda taban × çarpanlar = toplam; alt kalem tutarından pay; değişiklik kaydı ve günlük."""
from decimal import Decimal as D_
import pytest
from backend.depo import modeller as m
from backend.depo.veritabani import eksik_kolonlari_tamamla, motor_olustur
from backend.servisler import gider_servisi as gs
from backend.servisler.hatalar import DogrulamaHatasi
from tests.backend.test_api import _kur, _senaryo, istemci  # noqa: F401
from tests.backend.test_gider_servisi import senaryo, tohumla  # noqa: F401

A = "/api/v1"
H = {"X-Kullanici": "esma"}


# ------------------------------------------------------------------ servis

def test_taban_carpi_carpanlar_toplami_verir(oturum, senaryo):
    h = gs.havuz_kaydet(oturum, senaryo.id, "dolum_iscilik", "Dolum", None, "saniye", D_(1000), [],
                        taban_tutar=D_("1000.10"), carpanlar=[("SGK", D_("1.35")), ("Zam", D_("1.30"))])
    assert h.toplam_tutar == D_("1000.10") * D_("1.35") * D_("1.30") == D_("1755.175500")
    assert h.taban_tutar == D_("1000.10")
    assert h.carpanlar == [{"ad": "SGK", "deger": "1.35"}, {"ad": "Zam", "deger": "1.30"}]


def test_taban_verilmezse_toplam_dogrudan_ve_carpan_yok(oturum, senaryo):
    h = gs.havuz_kaydet(oturum, senaryo.id, "dolum_iscilik", "Dolum", D_(500), "saniye", D_(1000), [])
    assert h.toplam_tutar == D_(500) and h.taban_tutar is None and h.carpanlar is None


def test_ne_taban_ne_toplam_hata(oturum, senaryo):
    with pytest.raises(DogrulamaHatasi):
        gs.havuz_kaydet(oturum, senaryo.id, "dolum_iscilik", "Dolum", None, "saniye", D_(1000), [])
    with pytest.raises(DogrulamaHatasi):   # çarpan 0 / negatif olamaz
        gs.havuz_kaydet(oturum, senaryo.id, "dolum_iscilik", "Dolum", None, "saniye", D_(1000), [], taban_tutar=D_(1), carpanlar=[("x", D_(0))])


def test_tutardan_pay_ham_bolum(oturum, senaryo):
    """Alt kalem tutarı verilirse pay = tutar / toplam; yuvarlama yok (Decimal bağlam hassasiyeti)."""
    h = gs.havuz_kaydet(oturum, senaryo.id, "elektrik", "Elektrik", D_(300), "saniye", None,
                        [("Niko", None, D_(10), D_(100)), ("Herbort", None, D_(20), D_(200))])
    paylar = {a.alt_kalem: a.pay_orani for a in h.anahtarlar}
    assert paylar["Niko"] == D_(100) / D_(300) and str(paylar["Niko"]).startswith("0.33333333333333333333")
    assert paylar["Herbort"] == D_(200) / D_(300)
    assert gs.pay_toplami_kontrol(oturum, senaryo.id) == []   # 1/3 + 2/3 ≈ 1 (tolerans içinde)


def test_tutar_ve_taban_birlikte(oturum, senaryo):
    """Tutar → pay bölümü, taban × çarpan ile hesaplanan toplam üzerinden yapılır."""
    h = gs.havuz_kaydet(oturum, senaryo.id, "elektrik", "Elektrik", None, "saniye", None,
                        [("Niko", None, D_(10), D_(60))], taban_tutar=D_(100), carpanlar=[("k", D_("1.2"))])
    assert h.toplam_tutar == D_(120) and h.anahtarlar[0].pay_orani == D_("0.5")


def test_tutar_da_pay_da_yoksa_hata(oturum, senaryo):
    with pytest.raises(DogrulamaHatasi):
        gs.havuz_kaydet(oturum, senaryo.id, "elektrik", "Elektrik", D_(300), "saniye", None, [("Niko", None, D_(10), None)])
    with pytest.raises(DogrulamaHatasi):   # toplam 0 iken tutar bölünemez
        gs.havuz_kaydet(oturum, senaryo.id, "elektrik", "Elektrik", D_(0), "saniye", None, [("Niko", None, D_(10), D_(5))])


def test_degisiklik_kaydi_taban_ve_carpanlari_icerir(oturum, senaryo):
    gs.havuz_kaydet(oturum, senaryo.id, "dolum_iscilik", "Dolum", D_(500), "saniye", D_(1000), [], "esma")
    gs.havuz_kaydet(oturum, senaryo.id, "dolum_iscilik", "Dolum", None, "saniye", D_(1000), [], "esma", "çarpanlı giriş",
                    taban_tutar=D_(400), carpanlar=[("SGK", D_("1.5"))])
    k = oturum.query(m.DegisiklikKaydi).filter_by(tablo="gider_havuzu").order_by(m.DegisiklikKaydi.id.desc()).first()
    assert k.eski["taban_tutar"] is None and k.eski["carpanlar"] is None and k.eski["toplam_tutar"] == "500"
    assert k.yeni["taban_tutar"] == "400" and k.yeni["carpanlar"] == [{"ad": "SGK", "deger": "1.5"}]
    assert k.yeni["toplam_tutar"] == "600.0" and k.yeni["_neden"] == "çarpanlı giriş"
    # aynı taban/çarpanla tekrar kaydedince log açılmaz
    n = oturum.query(m.DegisiklikKaydi).filter_by(tablo="gider_havuzu").count()
    gs.havuz_kaydet(oturum, senaryo.id, "dolum_iscilik", "Dolum", None, "saniye", D_(1000), [], "esma", "aynı",
                    taban_tutar=D_(400), carpanlar=[("SGK", D_("1.5"))])
    assert oturum.query(m.DegisiklikKaydi).filter_by(tablo="gider_havuzu").count() == n


def test_toplam_dogrudan_yazilinca_taban_temizlenir(oturum, senaryo):
    """Toplam elle (ya da toplu kaydet/import ile) doğrudan verilince eski taban × çarpan artık toplamı açıklamaz: temizlenir."""
    gs.havuz_kaydet(oturum, senaryo.id, "dolum_iscilik", "Dolum", None, "saniye", D_(1000), [], taban_tutar=D_(400), carpanlar=[("SGK", D_("1.5"))])
    h = gs.havuz_kaydet(oturum, senaryo.id, "dolum_iscilik", "Dolum", D_(700), "saniye", D_(1000), [])
    assert h.toplam_tutar == D_(700) and h.taban_tutar is None and h.carpanlar is None


def test_motor_oranlari_carpanli_toplami_kullanir(oturum, senaryo):
    tohumla(oturum, senaryo.id)
    once = gs.oranlar(oturum, senaryo.id).dolum_iscilik_sn
    gs.havuz_kaydet(oturum, senaryo.id, "dolum_iscilik", "Dolum", None, "saniye", D_(442154500), [],
                    taban_tutar=D_("86037707.86667047"), carpanlar=[("x", D_(2))])
    assert gs.oranlar(oturum, senaryo.id).dolum_iscilik_sn == once * 2


def test_eski_veritabanina_kolonlar_eklenir():
    engine = motor_olustur("sqlite://")
    with engine.begin() as bag:
        bag.exec_driver_sql("CREATE TABLE gider_havuzu (id INTEGER PRIMARY KEY, senaryo_id INTEGER, kod VARCHAR(64), ad VARCHAR(200), "
                            "toplam_tutar VARCHAR(48), baz_tipi VARCHAR(8), baz_miktar VARCHAR(48), olusturan VARCHAR(64))")
        bag.exec_driver_sql("INSERT INTO gider_havuzu (senaryo_id, kod, ad, toplam_tutar, baz_tipi) VALUES (1, 'elektrik', 'E', '10', 'saniye')")
    assert {"gider_havuzu.taban_tutar", "gider_havuzu.carpanlar"} <= set(eksik_kolonlari_tamamla(engine))
    assert eksik_kolonlari_tamamla(engine) == []
    with engine.connect() as bag:
        assert bag.exec_driver_sql("SELECT taban_tutar, carpanlar FROM gider_havuzu").one() == (None, None)


# ------------------------------------------------------------------ API

def _hv(**ek):
    return {"ad": "Elektrik", "neden": "bütçe", "baz_tipi": "saniye", "baz_miktar": None, **ek}


def test_api_taban_carpan_ve_tutar(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    g = _hv(taban_tutar="1000", carpanlar=[{"ad": "SGK", "deger": "1.35"}, {"ad": "Zam", "deger": "1.2"}],
            anahtarlar=[{"alt_kalem": "Niko", "tutar": "810", "baz_miktar": "10"}, {"alt_kalem": "Herbort", "tutar": "810", "baz_miktar": "5"}])
    r = istemci.put(f"{A}/gider-havuzlari/elektrik?senaryo={sid}", json=g, headers=H)
    assert r.status_code == 200, r.text
    y = r.json()
    assert y["toplam_tutar"] == "1620.000" and y["taban_tutar"] == "1000" and y["carpanlar"] == [{"ad": "SGK", "deger": "1.35"}, {"ad": "Zam", "deger": "1.2"}]
    assert [a["pay_orani"] for a in y["anahtarlar"]] == ["0.5", "0.5"]
    assert "elektrik" not in {p["havuz"] for p in y["pay_kontrol"]}   # tohumdaki diğer havuzlar (dogalgaz/amortisman) zaten %100 değil
    liste = istemci.get(f"{A}/gider-havuzlari?senaryo={sid}").json()["kayitlar"]
    e = next(h for h in liste if h["kod"] == "elektrik")
    assert e["taban_tutar"] == "1000" and len(e["carpanlar"]) == 2
    d = next(h for h in liste if h["kod"] == "dolum_iscilik")
    assert d["taban_tutar"] is None and d["carpanlar"] == []   # eski kayıt: çarpan yok


def test_api_dogrulamalar(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    u = f"{A}/gider-havuzlari/elektrik?senaryo={sid}"
    # ne toplam ne taban
    assert istemci.put(u, json=_hv(anahtarlar=[]), headers=H).status_code == 422
    # anahtarda ne pay ne tutar
    assert istemci.put(u, json=_hv(toplam_tutar="100", anahtarlar=[{"alt_kalem": "Niko", "baz_miktar": "1"}]), headers=H).status_code == 422
    # çarpan 0
    assert istemci.put(u, json=_hv(taban_tutar="100", carpanlar=[{"ad": "x", "deger": "0"}], anahtarlar=[]), headers=H).status_code == 422
    # negatif tutar
    assert istemci.put(u, json=_hv(toplam_tutar="100", anahtarlar=[{"alt_kalem": "Niko", "tutar": "-1", "baz_miktar": "1"}]), headers=H).status_code == 422
    # taban + toplam birlikte, ya da tabansız çarpan: sessiz veri kaybı yerine 422
    assert istemci.put(u, json=_hv(toplam_tutar="100", taban_tutar="50", anahtarlar=[]), headers=H).status_code == 422
    assert istemci.put(u, json=_hv(toplam_tutar="100", carpanlar=[{"ad": "x", "deger": "1.1"}], anahtarlar=[]), headers=H).status_code == 422
    # pay_orani eski biçim hâlâ geçerli; ikisi birden gelirse pay_orani kazanır
    assert istemci.put(u, json=_hv(toplam_tutar="100", anahtarlar=[{"alt_kalem": "Niko", "pay_orani": "1", "baz_miktar": "1"}]), headers=H).status_code == 200
    r = istemci.put(u, json=_hv(toplam_tutar="100", anahtarlar=[{"alt_kalem": "Niko", "pay_orani": "0.4", "tutar": "90", "baz_miktar": "1"}]), headers=H)
    assert r.status_code == 200 and r.json()["anahtarlar"][0]["pay_orani"] == "0.4"


def test_api_gunluk_havuz_satiri_taban_gosterir(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    g = _hv(ad="Dolum", baz_miktar="1000", taban_tutar="400", carpanlar=[{"ad": "SGK", "deger": "1.5"}], anahtarlar=[], neden="çarpanlı")
    assert istemci.put(f"{A}/gider-havuzlari/dolum_iscilik?senaryo={sid}", json=g, headers=H).status_code == 200
    r = istemci.get(f"{A}/gunluk", params={"senaryo": sid, "tur": "havuz"})
    assert r.status_code == 200, r.text
    satir = r.json()["kayitlar"][0]
    assert satir["baslik"].startswith("Gider havuzu") and satir["neden"] == "çarpanlı"
    assert "toplam_tutar: 400,00 × 1,50 (SGK) = 600,00" in satir["yeni"]   # G3: taban × çarpan okunur metin (ham JSON yok)


def test_toplu_kaydet_taban_temizlenince_uyarir(istemci, oturum):
    """Ürün ekranından yalnız toplam yazılınca taban × çarpan silinir; bu sessiz olmaz, yanıt uyarı taşır."""
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    g = _hv(ad="Dolum", baz_miktar="1000", taban_tutar="400", carpanlar=[{"ad": "SGK", "deger": "1.5"}], anahtarlar=[])
    assert istemci.put(f"{A}/gider-havuzlari/dolum_iscilik?senaryo={sid}", json=g, headers=H).status_code == 200
    r = istemci.post(f"{A}/urunler/TEST/kaydet", json={"senaryo_id": sid, "neden": "toplam ölçekle", "hesabi_kaydet": False,
                                                       "gider_havuzlari": [{"kod": "dolum_iscilik", "toplam_tutar": "900"}]}, headers=H)
    assert r.status_code == 200, r.text
    assert any("taban × çarpan bilgisi temizlendi" in u for u in r.json()["uyarilar"])
    d = next(h for h in istemci.get(f"{A}/gider-havuzlari?senaryo={sid}").json()["kayitlar"] if h["kod"] == "dolum_iscilik")
    assert d["toplam_tutar"] == "900" and d["taban_tutar"] is None and d["carpanlar"] == []
