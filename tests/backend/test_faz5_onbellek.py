"""Faz 5 T1: dashboard onbellegi (saf birim + API davranisi + sure)."""
import time
import pytest
from fastapi.testclient import TestClient
from backend.depo.veritabani import Base, motor_olustur, oturum_fabrikasi, oturum_ver
from backend.servisler import import_servisi as ims, onbellek
from backend.uygulama import uygulama_olustur
from backend.tohum import parametreleri_tohumla
from tests.backend.test_api import _kur, _senaryo, istemci  # noqa: F401  (istemci fikstürü)


class Saat:
    def __init__(self): self.t = 1000.0
    def __call__(self): return self.t


@pytest.fixture
def oc():
    saat = Saat()
    return onbellek.Onbellek(ttl=600, zaman=saat), saat


def test_koy_al_ve_istatistik(oc):
    o, _ = oc
    assert o.al((1, "2026-01-01", None)) is None
    o.koy((1, "2026-01-01", None), [{"a": 1}])
    assert o.al((1, "2026-01-01", None)) == [{"a": 1}]
    assert o.istatistik() == {"isabet": 1, "hesap": 1, "girdi": 1}


def test_ttl_dolunca_duser(oc):
    o, saat = oc
    o.koy((1, "x", None), [1])
    saat.t += 599
    assert o.al((1, "x", None)) == [1]
    saat.t += 2
    assert o.al((1, "x", None)) is None


def test_temizle_senaryo_ve_hepsi(oc):
    o, _ = oc
    o.koy((1, "x", None), [1]); o.koy((2, "x", None), [2]); o.koy((1, "y", True), [3])
    o.temizle(1)
    assert o.al((1, "x", None)) is None and o.al((1, "y", True)) is None and o.al((2, "x", None)) == [2]
    o.temizle()
    assert o.al((2, "x", None)) is None


def test_en_cok_10_girdi_eskiden_atar():
    saat = Saat()
    o = onbellek.Onbellek(ttl=600, zaman=saat)
    for i in range(12):
        saat.t += 1
        o.koy((1, str(i), None), [i])
    assert o.istatistik()["girdi"] == 10
    assert o.al((1, "0", None)) is None and o.al((1, "1", None)) is None and o.al((1, "11", None)) == [11]


@pytest.fixture
def temiz():
    onbellek.temizle()
    yield


def _g(c, yol):
    r = c.get(yol)
    assert r.status_code == 200, r.text
    return r


def test_api_isabet_hesap_ve_gecersizleme(istemci, oturum, temiz):  # noqa: F811
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    u = f"/api/v1/urunler?senaryo={sid}"
    r1 = _g(istemci, u)
    assert r1.headers["X-Onbellek"] == "hesap"
    r2 = _g(istemci, u)
    assert r2.headers["X-Onbellek"] == "isabet" and r2.json() == r1.json()
    # salt okunur hesap onbellegi bosaltmaz
    assert istemci.post("/api/v1/urunler/TEST/hesapla", json={"senaryo_id": sid, "tarih": "2026-10-21"}).status_code == 200
    assert _g(istemci, u).headers["X-Onbellek"] == "isabet"
    # yazma bosaltir
    assert istemci.put("/api/v1/urunler/TEST", json={"ad": "Test2", "ambalaj_hacmi": "370", "hat": "Niko", "taze_tursu_sinifi": "Turşu/Turşu", "suzme_kg": "0.18"}).status_code == 200
    r3 = _g(istemci, u)
    assert r3.headers["X-Onbellek"] == "hesap" and r3.json()["kayitlar"][0]["ad"] == "Test2"
    assert _g(istemci, u).headers["X-Onbellek"] == "isabet"
    # yenile
    assert _g(istemci, u + "&yenile=1").headers["X-Onbellek"] == "hesap"
    assert _g(istemci, u).headers["X-Onbellek"] == "isabet"


def test_api_farkli_tarih_ayri_anahtar_ve_sayfalama(istemci, oturum, temiz):  # noqa: F811
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    u = f"/api/v1/urunler?senaryo={sid}"
    assert _g(istemci, u + "&tarih=2026-10-21").headers["X-Onbellek"] == "hesap"
    assert _g(istemci, u + "&tarih=2026-10-22").headers["X-Onbellek"] == "hesap"
    assert _g(istemci, u + "&tarih=2026-10-21").headers["X-Onbellek"] == "isabet"
    r = _g(istemci, u + "&tarih=2026-10-21&sayfa=2&boyut=1")
    assert r.headers["X-Onbellek"] == "isabet" and r.json()["kayitlar"] == [] and r.json()["toplam"] == 1
    assert _g(istemci, u + "&tarih=2026-10-21&gecici=true").headers["X-Onbellek"] == "hesap"


def test_api_uyarilar_onbellekten(istemci, oturum, temiz):  # noqa: F811
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    a = _g(istemci, f"/api/v1/uyarilar?senaryo={sid}&tarih=2026-10-21")
    assert a.headers["X-Onbellek"] == "hesap"
    b = _g(istemci, f"/api/v1/uyarilar?senaryo={sid}&tarih=2026-10-21")
    assert b.headers["X-Onbellek"] == "isabet" and b.json() == a.json()
    # uyarilar hesabi dashboard'u da doldurdu
    assert _g(istemci, f"/api/v1/urunler?senaryo={sid}&tarih=2026-10-21").headers["X-Onbellek"] == "isabet"
    # ve tersi
    onbellek.temizle()
    _g(istemci, f"/api/v1/urunler?senaryo={sid}&tarih=2026-10-21")
    assert _g(istemci, f"/api/v1/uyarilar?senaryo={sid}&tarih=2026-10-21").headers["X-Onbellek"] == "isabet"
    # yazma sonrasi uyarilar da yeniden hesaplanir
    istemci.put("/api/v1/urunler/TEST", json={"ad": "T", "ambalaj_hacmi": "370", "hat": "Niko", "taze_tursu_sinifi": "Turşu/Turşu", "suzme_kg": "0.18"})
    assert _g(istemci, f"/api/v1/uyarilar?senaryo={sid}&tarih=2026-10-21").headers["X-Onbellek"] == "hesap"


def test_fiyat_listesi_onizleme_haric_uygula_dahil():
    from backend.uygulama import onbellegi_temizlemeli_mi as f
    assert f("POST", "/api/v1/urunler/X/hesapla") is False
    assert f("POST", "/api/v1/import/fiyat-listesi") is False
    assert f("POST", "/api/v1/import/fiyat-listesi/uygula") is True
    assert f("PUT", "/api/v1/urunler/X") is True and f("DELETE", "/api/v1/x") is True and f("PATCH", "/api/v1/x") is True
    assert f("GET", "/api/v1/urunler") is False and f("POST", "/baska/yol") is False


def test_gercek_kitap_ikinci_istek_hizli(excel_yolu, temiz):
    engine = motor_olustur("sqlite://"); Base.metadata.create_all(engine)
    s = oturum_fabrikasi(engine)()
    parametreleri_tohumla(s)
    ims.excel_tam_yukle(s, excel_yolu, "2026-2027", "Berrak"); s.commit()
    app = uygulama_olustur(); app.dependency_overrides[oturum_ver] = lambda: s
    c = TestClient(app)
    sid = c.get("/api/v1/senaryolar").json()["kayitlar"][0]["id"]
    yol = f"/api/v1/urunler?senaryo={sid}&boyut=500"
    t0 = time.perf_counter(); r1 = c.get(yol); ilk = time.perf_counter() - t0
    t0 = time.perf_counter(); r2 = c.get(yol); ikinci = time.perf_counter() - t0
    print(f"\nOLCUM ilk={ilk:.3f}s ikinci={ikinci:.3f}s toplam={r1.json()['toplam']}")
    assert r1.status_code == 200 and r1.headers["X-Onbellek"] == "hesap" and r2.headers["X-Onbellek"] == "isabet"
    assert r1.json() == r2.json() and r1.json()["toplam"] > 10
    assert ikinci < 0.5
    s.close()


def test_eski_nesil_koy_yok_sayilir():
    o = onbellek.Onbellek(ttl=600, zaman=Saat())
    n = o.nesil()
    o.temizle()
    assert o.koy((1, "x", None), [1], n) is False
    assert o.al((1, "x", None)) is None
    assert o.koy((1, "x", None), [1], o.nesil()) is True and o.al((1, "x", None)) == [1]
    assert o.koy((1, "y", None), [2]) is True   # nesilsiz koy geriye uyumlu


def test_api_hesap_sirasinda_yazma_eski_sonucu_onbellege_koymaz(istemci, oturum, temiz, monkeypatch):  # noqa: F811
    from backend.api import urunler as api_urunler
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    gercek = api_urunler._hesapla_satirlar

    def yarisli(*a, **k):
        sonuc = gercek(*a, **k)
        onbellek.temizle()   # hesap sürerken başka bir yazma commit oldu
        return sonuc
    monkeypatch.setattr(api_urunler, "_hesapla_satirlar", yarisli)
    u = f"/api/v1/urunler?senaryo={sid}"
    assert _g(istemci, u).headers["X-Onbellek"] == "hesap"
    assert _g(istemci, u).headers["X-Onbellek"] == "hesap"   # eski sonuç konmadı
    monkeypatch.setattr(api_urunler, "_hesapla_satirlar", gercek)
    assert _g(istemci, u).headers["X-Onbellek"] == "hesap"
    assert _g(istemci, u).headers["X-Onbellek"] == "isabet"


def test_hesap_say_yenile_icin():
    o = onbellek.Onbellek()
    o.hesap_say()
    assert o.istatistik()["hesap"] == 1
