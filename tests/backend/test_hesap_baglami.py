"""toplu_hesapla paylaşılan bağlam: sonuçlar tek tek hesapla ile aynı, senaryo geneli yükler bir kez çekilir."""
from decimal import Decimal
from backend.servisler import fiyat_servisi, gider_servisi, hesap_servisi as hs, parametre_servisi
from tests.backend.test_api import _kur, _senaryo, istemci  # noqa: F401 — fixture


def _ikinci_urun(c, sid):
    assert c.put("/api/v1/urunler/TEST2", json={"ad": "Test 2", "ambalaj_hacmi": "720", "hat": "Herbort", "taze_tursu_sinifi": "Taze/Turşu", "suzme_kg": "0.45"}).status_code == 200
    assert c.put(f"/api/v1/urunler/TEST2/uretim-hedefi?senaryo={sid}", json={"vardiya_uretim_adedi": "30000", "dolum_personel": "10", "etiketleme_adedi": "20000",
                 "etiket_personel": "5", "mal_kabul_miktar_kg": "0.4"}).status_code == 200
    assert c.post(f"/api/v1/urunler/TEST2/recete?senaryo={sid}", json=[{"malzeme_kodu": "KAV", "ad": "Kavanoz", "miktar": "2", "birim": "AD"}]).status_code == 201
    # ürün kapsamlı parametre: bağlam paylaşımı ürün kapsamını karıştırmamalı
    test2_id = c.get(f"/api/v1/urunler/TEST2?senaryo={sid}").json()["id"]
    assert c.post(f"/api/v1/parametreler/stok_ay.TL/degerler?senaryo={sid}", json={"deger": "2", "gecerlilik_basi": "2026-06-01", "neden": "hızlı dönen",
                  "kapsam_tipi": "urun", "kapsam_id": test2_id}).status_code == 201


def test_toplu_hesap_tek_tek_hesapla_ile_ayni(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum); _ikinci_urun(istemci, sid)
    toplu = dict(hs.toplu_hesapla(oturum, sid))
    assert set(toplu) == {"TEST", "TEST2"}
    for kod in ("TEST", "TEST2"):
        tek = hs.hesapla(oturum, kod, sid)
        assert toplu[kod].sonuc == tek.sonuc, kod
        assert toplu[kod].kullanilan_parametreler == tek.kullanilan_parametreler, kod
        assert toplu[kod].notlar == tek.notlar and toplu[kod].fire_kaynaklari == tek.fire_kaynaklari
    assert toplu["TEST2"].kullanilan_parametreler["stok_ay.TL"] == Decimal("2") and toplu["TEST"].kullanilan_parametreler["stok_ay.TL"] != Decimal("2")


def test_senaryo_geneli_yukler_toplu_hesapta_bir_kez(istemci, oturum, monkeypatch):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum); _ikinci_urun(istemci, sid)
    sayac = {"fiyat": 0, "oran": 0, "param": 0, "metin": 0}
    for ad, modul, isim in (("fiyat", fiyat_servisi, "gecerli_fiyatlar"), ("oran", gider_servisi, "oranlar"),
                            ("param", parametre_servisi, "parametre_satirlari"), ("metin", parametre_servisi, "metin_gecerli")):
        orj = getattr(modul, isim)
        def sarmal(*a, _orj=orj, _ad=ad, **k):
            sayac[_ad] += 1
            return _orj(*a, **k)
        monkeypatch.setattr(modul, isim, sarmal)
    sonuc = hs.toplu_hesapla(oturum, sid)
    assert len(sonuc) == 2 and all(not isinstance(c, Exception) for _, c in sonuc)
    assert sayac == {"fiyat": 1, "oran": 1, "param": 1, "metin": 1}


def test_tek_hesapla_baglamsiz_calisir(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    c = hs.hesapla(oturum, "TEST", sid)
    assert c.sonuc.toplam_birim_maliyet > 0
