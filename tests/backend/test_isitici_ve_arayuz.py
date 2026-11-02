"""Yazma sonrası arka plan ısıtma (debounce, uçlar, kilitli senaryo atlanır) ve üretim derlemesinin aynı sunucudan sunulması."""
import threading
from backend.servisler import isitici as I


def _isitici(senaryolar):
    cagrilar, bitti = [], threading.Event()
    def getir(url): cagrilar.append(url)
    def getir_json(url): return {"kayitlar": senaryolar}
    uykular = []
    def uyku(sn): uykular.append(sn)
    o = I.Isitici(getir=getir, getir_json=getir_json, gecikme_sn=0.01, uyku=uyku)
    return o, cagrilar, uykular


def test_tek_tetik_tum_acik_senaryolari_isitir():
    o, cagrilar, _ = _isitici([{"id": 1, "kilitli": False}, {"id": 2, "kilitli": True}, {"id": 3, "kilitli": False}])
    o.tetikle("http://127.0.0.1:8000/")
    for _ in range(200):
        if not o._calisiyor: break
        threading.Event().wait(0.01)
    assert o.isitma_sayisi == 1
    assert cagrilar == ["http://127.0.0.1:8000/api/v1/urunler?senaryo=1&boyut=1", "http://127.0.0.1:8000/api/v1/uyarilar?senaryo=1",
                        "http://127.0.0.1:8000/api/v1/urunler?senaryo=3&boyut=1", "http://127.0.0.1:8000/api/v1/uyarilar?senaryo=3"]


def test_pes_pese_tetikler_birlesir_ve_son_adres_kullanilir():
    kapi = threading.Event()
    cagrilar = []
    def getir(url): cagrilar.append(url)
    def getir_json(url): return {"kayitlar": [{"id": 1, "kilitli": False}]}
    def uyku(sn): kapi.wait(1)   # ilk uyku tetikler bitene kadar bekler
    o = I.Isitici(getir=getir, getir_json=getir_json, gecikme_sn=0.01, uyku=uyku)
    for _ in range(5):
        o.tetikle("http://a/")
    o.tetikle("http://b/")
    kapi.set()
    for _ in range(200):
        if not o._calisiyor: break
        threading.Event().wait(0.01)
    assert o.isitma_sayisi == 1 and cagrilar[0].startswith("http://b/")


def test_getir_hatasi_dongu_dusurmez():
    def getir(url): raise OSError("bağlantı yok")
    def getir_json(url): return {"kayitlar": [{"id": 1, "kilitli": False}]}
    o = I.Isitici(getir=getir, getir_json=getir_json, gecikme_sn=0.01, uyku=lambda sn: None)
    o.tetikle("http://x")
    for _ in range(200):
        if not o._calisiyor: break
        threading.Event().wait(0.01)
    assert o.isitma_sayisi == 1 and o._calisiyor is False


def test_testserver_adresi_isitmaz(monkeypatch):
    tetikler = []
    monkeypatch.setattr(I.ISITICI, "tetikle", lambda taban: tetikler.append(taban))
    I.yazma_sonrasi("http://testserver/")
    assert tetikler == []


def test_arayuz_dist_varsa_sunulur(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from backend import uygulama
    (tmp_path / "assets").mkdir(); (tmp_path / "index.html").write_text("<html>arayuz</html>", encoding="utf-8")
    (tmp_path / "assets" / "a.js").write_text("1", encoding="utf-8")
    monkeypatch.setattr(uygulama, "ARAYUZ_DIZINI", tmp_path)
    c = TestClient(uygulama.uygulama_olustur())
    assert c.get("/").status_code == 200 and "arayuz" in c.get("/").text
    assert "arayuz" in c.get("/urunler/ABC?senaryo=1").text          # SPA yolu → index.html
    assert c.get("/assets/a.js").text == "1"
    assert c.get("/api/v1/olmayan").status_code == 404 and c.get("/api/v1/olmayan").json()["hata"] == "bulunamadi"


def test_arayuz_dist_yoksa_baglanmaz(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from backend import uygulama
    monkeypatch.setattr(uygulama, "ARAYUZ_DIZINI", tmp_path / "yok")
    c = TestClient(uygulama.uygulama_olustur())
    assert c.get("/").status_code == 404
