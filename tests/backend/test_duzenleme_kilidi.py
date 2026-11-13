"""Düzenleme kilidi: kilidi açma olayı Değişiklik Günlüğü'ne yazılır; izleyici açamaz (403), satın alma açabilir."""
from backend.depo import modeller as m
from backend.servisler import kimlik_servisi as ks
from tests.backend.test_api import _senaryo, istemci  # noqa: F401
from tests.backend.test_kimlik import _istemci, uygulama  # noqa: F401

A = "/api/v1"


def test_kilit_ac_gunluge_yazilir(istemci, oturum):
    sid = _senaryo(istemci)
    r = istemci.post(f"{A}/duzenleme-kilidi/ac", json={"senaryo_id": sid, "sayfa": "/fiyatlar"}, headers={"X-Kullanici": "esma"})
    assert r.status_code == 201, r.text
    assert r.json()["sayfa"] == "/fiyatlar" and r.json()["senaryo_id"] == sid and r.json()["kullanici"] == "esma"
    k = oturum.get(m.DegisiklikKaydi, r.json()["kayit_id"])
    assert (k.tablo, k.islem, k.kullanici) == ("duzenleme_kilidi", "kilit_ac", "esma")
    assert k.yeni == {"sayfa": "/fiyatlar", "senaryo_id": sid}
    g = istemci.get(f"{A}/gunluk", params={"senaryo": sid}).json()
    satir = next(x for x in g["kayitlar"] if x["id"] == f"degisiklik:{k.id}")
    assert satir["baslik"] == "Düzenleme kilidi açıldı" and satir["tur"] == "diger"
    assert satir["kullanici"] == "esma" and satir["senaryo_id"] == sid and "/fiyatlar" in (satir["yeni"] or "")


def test_baska_senaryonun_gunlugunde_gorunmez_senaryosuz_her_yerde_gorunur(istemci):
    sid = _senaryo(istemci)
    r2 = istemci.post(f"{A}/senaryolar", json={"sezon_ad": "2026-2027", "tur": "fiyat_calismasi", "ad": "B"})
    assert r2.status_code == 201, r2.text
    diger = r2.json()["id"]
    a = istemci.post(f"{A}/duzenleme-kilidi/ac", json={"senaryo_id": sid, "sayfa": "/parametreler"}).json()["kayit_id"]
    b = istemci.post(f"{A}/duzenleme-kilidi/ac", json={"sayfa": "/satis-gecmisi"}).json()["kayit_id"]
    idler = {x["id"] for x in istemci.get(f"{A}/gunluk", params={"senaryo": diger}).json()["kayitlar"]}
    assert f"degisiklik:{a}" not in idler and f"degisiklik:{b}" in idler


def test_dogrulama_ve_bilinmeyen_senaryo(istemci):
    assert istemci.post(f"{A}/duzenleme-kilidi/ac", json={"senaryo_id": 999999, "sayfa": "/fiyatlar"}).status_code == 404
    assert istemci.post(f"{A}/duzenleme-kilidi/ac", json={"sayfa": ""}).status_code == 422


def test_izleyici_acamaz_satin_alma_acabilir(uygulama, oturum):
    for ad, rol in (("satin", "satin_alma"), ("izle", "izleyici")):
        ks.kullanici_olustur(oturum, ad, ad, rol, "sifre-1234", sifre_degismeli=False)
    oturum.commit()
    satin, izle = _istemci(uygulama, "satin", "sifre-1234"), _istemci(uygulama, "izle", "sifre-1234")
    r = izle.post(f"{A}/duzenleme-kilidi/ac", json={"sayfa": "/fiyatlar"})
    assert r.status_code == 403, r.text
    assert oturum.query(m.DegisiklikKaydi).filter_by(tablo="duzenleme_kilidi").count() == 0
    r = satin.post(f"{A}/duzenleme-kilidi/ac", json={"sayfa": "/fiyatlar"}, headers={"X-Kullanici": "sahte"})
    assert r.status_code == 201 and r.json()["kullanici"] == "satin"   # yazan: oturumdaki kullanıcı
