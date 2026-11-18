"""Giriş, oturum ve roller: giriş zorunlu uygulamada çerezli oturum, hatalı deneme kilidi, geçici şifre, rol izinleri,
Genel Direktör'ün kullanıcı yönetimi ve değişiklik kaydına oturumdaki kullanıcının yazılması."""
from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
from backend.depo import modeller as m
from backend.depo.veritabani import oturum_ver
from backend.servisler import isitici, kimlik_servisi as ks
from backend.tohum import parametreleri_tohumla
from backend.uygulama import uygulama_olustur
from tests.backend.test_api import _kur, _senaryo

API = "/api/v1"


@pytest.fixture
def uygulama(oturum):
    app = uygulama_olustur(giris_zorunlu=True)

    def _ver():
        try:
            yield oturum
            oturum.commit()
        except Exception:
            oturum.rollback()
            raise
    app.dependency_overrides[oturum_ver] = _ver
    parametreleri_tohumla(oturum)
    ks.kullanici_olustur(oturum, "genel", "Genel Direktör", "genel_direktor", "gecici-sifre", sifre_degismeli=False)
    oturum.commit()
    return app


def _istemci(app, kullanici=None, sifre="gecici-sifre") -> TestClient:
    c = TestClient(app)
    if kullanici:
        r = c.post(f"{API}/kimlik/giris", json={"kullanici_adi": kullanici, "sifre": sifre})
        assert r.status_code == 200, r.text
    return c


def test_girissiz_api_kapali_ben_401_giris_cerez_verir(uygulama):
    c = _istemci(uygulama)
    assert c.get(f"{API}/senaryolar").status_code == 401
    assert c.get(f"{API}/kimlik/ben").status_code == 401
    r = c.post(f"{API}/kimlik/giris", json={"kullanici_adi": "GENEL ", "sifre": "gecici-sifre"})
    assert r.status_code == 200 and r.json()["kullanici"]["rol"] == "genel_direktor"
    cerez = r.headers["set-cookie"]
    assert "fc_oturum=" in cerez and "HttpOnly" in cerez and "Max-Age=" in cerez   # tarayıcı kapanınca silinmez
    assert c.get(f"{API}/senaryolar").status_code == 200
    assert c.get(f"{API}/kimlik/ben").json()["kullanici"]["ad"] == "Genel Direktör"
    assert c.post(f"{API}/kimlik/cikis").status_code == 204
    assert c.get(f"{API}/senaryolar").status_code == 401   # çıkıştan sonra oturum kapalı


def test_yanlis_sifre_ayni_mesaj_ve_bes_denemede_kilit(uygulama, oturum):
    c = _istemci(uygulama)
    for _ in range(ks.HATALI_SINIR):
        r = c.post(f"{API}/kimlik/giris", json={"kullanici_adi": "genel", "sifre": "yanlis"})
        assert r.status_code == 401 and r.json()["mesaj"] == "Kullanıcı adı ya da şifre yanlış."
    assert c.post(f"{API}/kimlik/giris", json={"kullanici_adi": "yok", "sifre": "x"}).json()["mesaj"] == "Kullanıcı adı ya da şifre yanlış."
    r = c.post(f"{API}/kimlik/giris", json={"kullanici_adi": "genel", "sifre": "gecici-sifre"})
    assert r.status_code == 401 and r.json()["kod"] == "kilitli"   # doğru şifre de kilit süresince reddedilir
    k = oturum.query(m.Kullanici).filter_by(kullanici_adi="genel").one()
    k.kilit_bitis -= timedelta(minutes=ks.KILIT_DAKIKA + 1); oturum.commit()
    assert c.post(f"{API}/kimlik/giris", json={"kullanici_adi": "genel", "sifre": "gecici-sifre"}).status_code == 200


def test_gd_kullanici_ekler_gecici_sifre_once_degistirilir_digerleri_yonetemez(uygulama, oturum):
    gd = _istemci(uygulama, "genel")
    r = gd.post(f"{API}/kullanicilar", json={"kullanici_adi": "ayse", "ad": "Ayşe", "rol": "muhasebe", "gecici_sifre": "baslangic1"})
    assert r.status_code == 201 and r.json()["sifre_degismeli"] is True
    assert gd.post(f"{API}/kullanicilar", json={"kullanici_adi": "ayse", "ad": "x", "rol": "muhasebe", "gecici_sifre": "baslangic1"}).status_code == 409
    assert gd.post(f"{API}/kullanicilar", json={"kullanici_adi": "Ay Se", "ad": "x", "rol": "muhasebe", "gecici_sifre": "baslangic1"}).status_code == 422
    assert gd.post(f"{API}/kullanicilar", json={"kullanici_adi": "kisa", "ad": "x", "rol": "muhasebe", "gecici_sifre": "123"}).status_code == 422

    ayse = _istemci(uygulama, "ayse", "baslangic1")
    r = ayse.post(f"{API}/senaryolar", json={"sezon_ad": "2026-2027", "tur": "fiyat_calismasi", "ad": "S"})
    assert r.status_code == 403 and r.json()["kod"] == "sifre_degismeli"   # geçici şifreyle yazamaz
    assert ayse.get(f"{API}/senaryolar").status_code == 200                 # okuyabilir
    assert ayse.post(f"{API}/kimlik/sifre", json={"eski_sifre": "yanlis", "yeni_sifre": "yepyeni-sifre"}).status_code == 422
    r = ayse.post(f"{API}/kimlik/sifre", json={"eski_sifre": "baslangic1", "yeni_sifre": "yepyeni-sifre"})
    assert r.status_code == 200 and r.json()["sifre_degismeli"] is False
    r = ayse.post(f"{API}/senaryolar", json={"sezon_ad": "2026-2027", "tur": "fiyat_calismasi", "ad": "S"})
    assert r.status_code == 201, r.text
    assert ayse.get(f"{API}/kullanicilar").status_code == 403   # muhasebe kullanıcı yönetemez


def test_roller_satin_alma_yalniz_fiyat_izleyici_salt_okunur(uygulama, oturum):
    gd = _istemci(uygulama, "genel")
    sid = _senaryo(gd); _kur(gd, sid, oturum); oturum.commit()
    for ad, rol in (("satin", "satin_alma"), ("izle", "izleyici")):
        ks.kullanici_olustur(oturum, ad, ad, rol, "sifre-1234", sifre_degismeli=False)
    oturum.commit()
    satin, izle = _istemci(uygulama, "satin", "sifre-1234"), _istemci(uygulama, "izle", "sifre-1234")
    fiyat = {"onay": True, "fiyat": "7", "para_birimi": "TL", "gecerlilik_basi": "2026-10-22", "neden": "zam"}
    assert satin.post(f"{API}/malzemeler/KAV/fiyatlar?senaryo={sid}", json=fiyat).status_code == 201
    r = satin.post(f"{API}/parametreler/kur.USD/degerler?senaryo={sid}",
                   json={"deger": "51", "gecerlilik_basi": "2026-10-22", "neden": "x"})
    assert r.status_code == 403 and "Satın alma" in r.json()["mesaj"]
    assert izle.post(f"{API}/malzemeler/KAV/fiyatlar?senaryo={sid}", json=fiyat).status_code == 403
    # önizleme hesabı her rolde serbest (veri yazmaz)
    assert izle.post(f"{API}/urunler/TEST/hesapla", json={"senaryo_id": sid, "tarih": "2026-10-22"}).status_code == 200
    assert izle.get(f"{API}/urunler?senaryo={sid}").status_code == 200
    # değişikliği yapan: oturumdaki kullanıcı (X-Kullanici başlığı yok sayılır)
    satin.post(f"{API}/malzemeler/KAV/fiyatlar?senaryo={sid}", json={"onay": True, **fiyat, "fiyat": "8"}, headers={"X-Kullanici": "sahte"})
    son = oturum.query(m.MalzemeFiyati).order_by(m.MalzemeFiyati.id.desc()).first()
    assert son.olusturan == "satin"


def test_pasiflestirme_ve_sifre_sifirlama_oturumu_kapatir_son_gd_korunur(uygulama, oturum):
    gd = _istemci(uygulama, "genel")
    uid = gd.post(f"{API}/kullanicilar", json={"kullanici_adi": "ali", "ad": "Ali", "rol": "izleyici", "gecici_sifre": "baslangic1"}).json()["id"]
    ali = _istemci(uygulama, "ali", "baslangic1")
    assert ali.get(f"{API}/senaryolar").status_code == 200
    assert gd.post(f"{API}/kullanicilar/{uid}/sifre-sifirla", json={"gecici_sifre": "yeni-gecici"}).status_code == 200
    assert ali.get(f"{API}/senaryolar").status_code == 401   # sıfırlama açık oturumu kapattı
    ali = _istemci(uygulama, "ali", "yeni-gecici")
    r = gd.patch(f"{API}/kullanicilar/{uid}", json={"rol": "muhasebe", "ad": "Ali Veli"})
    assert r.json()["rol"] == "muhasebe" and r.json()["ad"] == "Ali Veli"
    assert gd.patch(f"{API}/kullanicilar/{uid}", json={"aktif": False}).json()["aktif"] is False
    assert ali.get(f"{API}/senaryolar").status_code == 401
    assert TestClient(uygulama).post(f"{API}/kimlik/giris", json={"kullanici_adi": "ali", "sifre": "yeni-gecici"}).status_code == 401
    gd_id = oturum.query(m.Kullanici).filter_by(kullanici_adi="genel").one().id
    assert gd.patch(f"{API}/kullanicilar/{gd_id}", json={"rol": "muhasebe"}).status_code == 409   # son aktif Genel Direktör
    assert gd.patch(f"{API}/kullanicilar/{gd_id}", json={"aktif": False}).status_code == 409
    islemler = [x.islem for x in oturum.query(m.DegisiklikKaydi).filter_by(tablo="kullanici", kayit_id=uid)]
    assert islemler == ["ekle", "sifre_sifirla", "guncelle", "guncelle"]


def test_isitici_ic_anahtarla_yalniz_okur(uygulama):
    c = TestClient(uygulama)
    assert c.get(f"{API}/senaryolar", headers={"X-Ic-Anahtar": isitici.IC_ANAHTAR}).status_code == 200
    assert c.get(f"{API}/senaryolar", headers={"X-Ic-Anahtar": "tahmin"}).status_code == 401
    r = c.post(f"{API}/senaryolar", json={"sezon_ad": "2026-2027", "tur": "fiyat_calismasi", "ad": "S"}, headers={"X-Ic-Anahtar": isitici.IC_ANAHTAR})
    assert r.status_code == 401


def test_giris_kapali_kurulumda_ben_bilgi_verir():
    c = TestClient(uygulama_olustur(giris_zorunlu=False))
    assert c.get(f"{API}/kimlik/ben").json() == {"giris_zorunlu": False, "kullanici": None}


def test_yazabilir_mi_kurallari():
    y = ks.yazabilir_mi
    assert y("izleyici", "GET", "/api/v1/urunler") and not y("izleyici", "POST", "/api/v1/urunler/X/kaydet")
    assert y("izleyici", "POST", "/api/v1/aktarim/recete/onizle") and y("izleyici", "POST", "/api/v1/import/fiyat-listesi")
    assert y("satin_alma", "POST", "/api/v1/malzemeler") and y("satin_alma", "POST", "/api/v1/import/fiyat-listesi/uygula")
    assert not y("satin_alma", "PUT", "/api/v1/gider-havuzlari/elektrik") and not y("satin_alma", "DELETE", "/api/v1/senaryolar/1")
    assert y("muhasebe", "DELETE", "/api/v1/senaryolar/1") and y("genel_direktor", "PATCH", "/api/v1/kullanicilar/3")
