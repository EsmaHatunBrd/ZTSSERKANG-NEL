"""Veri Kontrolü (D7): gerçek kitap yüklenince bilinen veri sorunları doğru kontrollerde görünür; bir sorun yaratılınca ilgili kontrol
'dikkat'/'hata'ya döner; uç önbellekli. Şirket verisi test çıktısına yazılmaz (yalnız sayılar ve kodlar)."""
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select
from backend.depo import modeller as m
from backend.depo.veritabani import Base, motor_olustur, oturum_fabrikasi, oturum_ver
from backend.servisler import import_servisi as ims, tutarlilik_servisi as ts
from backend.uygulama import uygulama_olustur

KODLAR = ["hesaplanamayan", "parametre_eksik", "fiyatsiz", "malzeme_karti", "pay", "hat", "parametre_uyari", "recetesiz", "gecici_kod",
          "uretim_adetleri"]


@pytest.fixture(scope="module")
def ortam(excel_yolu):
    engine = motor_olustur("sqlite://"); Base.metadata.create_all(engine)
    s = oturum_fabrikasi(engine)()
    sid = ims.excel_tam_yukle(s, excel_yolu, "2026-2027", "Bütçe")["senaryo_id"]
    s.commit()
    yield s, sid
    s.close()


def _k(d: dict) -> dict:
    return {k["kod"]: k for k in d["kontroller"]}


def test_gercek_kitapta_bilinen_sorunlar(ortam):
    s, sid = ortam
    d = ts.kontroller(s, sid)
    assert [k["kod"] for k in d["kontroller"]] == KODLAR
    k = _k(d)
    assert k["hesaplanamayan"]["durum"] == k["parametre_eksik"]["durum"] == k["recetesiz"]["durum"] == "tamam"
    assert k["fiyatsiz"]["durum"] == "dikkat" and k["fiyatsiz"]["sayi"] > 100
    assert all(o["yol"].startswith("/fiyatlar?fiyatsiz=1&arama=") and "üründe kullanılıyor" in o["aciklama"] for o in k["fiyatsiz"]["ogeler"])
    assert {o["etiket"] for o in k["pay"]["ogeler"]} == {"elektrik", "dogalgaz"}   # %100,1 ve %99,5 (muhasebeye soruldu)
    assert k["gecici_kod"]["sayi"] == 12 and all(o["etiket"].startswith("SAYFA-") for o in k["gecici_kod"]["ogeler"])
    eslesmeyen = k["uretim_adetleri"]["ogeler"]   # 02/03 kod sorunu: neredeyse hepsi 02.* (birkaç kodun da kartı yok)
    assert eslesmeyen and sum(o["etiket"].startswith("02.") for o in eslesmeyen) > len(eslesmeyen) * 0.9
    assert any("Mısır" in o["etiket"] for o in k["hat"]["ogeler"])
    assert k["malzeme_karti"]["sayi"] > 0
    assert d["ozet"] == {d_: sum(1 for x in d["kontroller"] if x["durum"] == d_) for d_ in ("hata", "dikkat", "tamam")}


def test_sorun_yaratilinca_ilgili_kontrol_doner(ortam):
    s, sid = ortam
    urunler = list(s.scalars(select(m.Urun).where(m.Urun.gecici_kod == False).order_by(m.Urun.kod).limit(2)))
    r = s.scalar(select(m.Recete).where(m.Recete.urun_id == urunler[0].id, m.Recete.senaryo_id == sid, m.Recete.aktif == True))
    h = s.scalar(select(m.UretimHedefi).where(m.UretimHedefi.urun_id == urunler[1].id, m.UretimHedefi.senaryo_id == sid))
    r.aktif = False
    s.delete(h); s.flush()
    try:
        k = _k(ts.kontroller(s, sid))
        assert k["recetesiz"]["durum"] == "dikkat" and [o["etiket"].split(" · ")[0] for o in k["recetesiz"]["ogeler"]] == [urunler[0].kod]
        assert k["hesaplanamayan"]["durum"] == "hata"
        o = k["hesaplanamayan"]["ogeler"][0]
        assert o["etiket"].startswith(urunler[1].kod) and "üretim bilgileri" in o["aciklama"] and o["yol"] == f"/urunler/{urunler[1].kod}"
    finally:
        s.rollback()


def test_uc_onbellek_ve_hatalar(ortam):
    s, sid = ortam
    app = uygulama_olustur()
    app.dependency_overrides[oturum_ver] = lambda: s
    c = TestClient(app)
    r = c.get(f"/api/v1/tutarlilik?senaryo={sid}")
    assert r.status_code == 200, r.text
    assert r.headers["X-Onbellek"] == "hesap" and c.get(f"/api/v1/tutarlilik?senaryo={sid}").headers["X-Onbellek"] == "isabet"
    assert [k["kod"] for k in r.json()["kontroller"]] == KODLAR
    assert c.get("/api/v1/tutarlilik?senaryo=9999").status_code == 404
