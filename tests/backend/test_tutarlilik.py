"""Veri Kontrolü (D7): gerçek kitap yüklenince bilinen veri sorunları doğru kontrollerde görünür; bir sorun yaratılınca ilgili kontrol
'dikkat'/'hata'ya döner; uç önbellekli. Şirket verisi test çıktısına yazılmaz (yalnız sayılar ve kodlar)."""
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select
from backend.depo import modeller as m
from backend.depo.veritabani import Base, motor_olustur, oturum_fabrikasi, oturum_ver
from backend.servisler import import_servisi as ims, tutarlilik_servisi as ts
from backend.uygulama import uygulama_olustur

KODLAR = ["hesaplanamayan", "parametre_eksik", "fiyatsiz", "eksik_fiyat_etkisi", "hedef_alti", "malzeme_karti", "pay", "hat", "olagan_disi_parametre", "parametre_uyari", "recetesiz", "gecici_kod",
          "uretim_adetleri", "ambalaj_tutarsiz", "fiyat_egilimi", "elle_hucre"]


@pytest.fixture(scope="module")
def ortam(excel_yolu):
    engine = motor_olustur("sqlite://"); Base.metadata.create_all(engine)
    s = oturum_fabrikasi(engine)()
    sid = ims.excel_tam_yukle(s, excel_yolu, "2026-2027", "Bütçe")["senaryo_id"]
    s.commit()
    yield s, sid
    s.close()


def test_ambalaj_tutarsizliklari_saf():
    D = __import__("decimal").Decimal
    satir = lambda kod, ml, tl, aile="turşu": {"kod": kod, "ad": f"Turşu {ml} ml", "aile": aile, "ambalaj_ml": D(ml), "satis_tl": D(tl)}
    # 370 ml 10 TL (27,03/lt), 720 ml 25 TL (34,72/lt) → büyük boy pahalı; 1700 ml 50 TL (29,41/lt) → bir öncekinden ucuz, uyarı yok
    out = ts.ambalaj_tutarsizliklari([satir("B", 720, 25), satir("A", 370, 10), satir("C", 1700, 50)])
    assert [o["etiket"].split(" · ")[0] for o in out] == ["B"]
    assert "34,72 TL" in out[0]["aciklama"] and "(A) 27,03 TL" in out[0]["aciklama"] and "%28,5" in out[0]["aciklama"]
    assert out[0]["yol"] == "/karsilastirma?aile=tur%C5%9Fu"
    # tolerans: %1 içindeki fark uyarı değil; eşit hacim kıyaslanmaz; aile/fiyat/hacim boş satırlar atlanır
    assert ts.ambalaj_tutarsizliklari([satir("A", 370, 10), satir("B", 740, D("20.1"))]) == []
    assert ts.ambalaj_tutarsizliklari([satir("A", 370, 10), satir("B", 370, 12)]) == []
    assert ts.ambalaj_tutarsizliklari([satir("A", 370, 10), {"kod": "X", "ad": "x", "aile": None, "ambalaj_ml": D(720), "satis_tl": D(99)},
                                       {"kod": "Y", "ad": "y", "aile": "turşu", "ambalaj_ml": None, "satis_tl": D(99)},
                                       {"kod": "Z", "ad": "z", "aile": "turşu", "ambalaj_ml": D(720), "satis_tl": None}]) == []


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
    # eksik fiyatın ürüne etkisi: fiyatsız malzemeyi kullanan ürünler, en çok fiyatsız satırı olan üstte
    etki = k["eksik_fiyat_etkisi"]["ogeler"]
    assert k["eksik_fiyat_etkisi"]["durum"] == "dikkat" and etki and all("reçete satırının fiyatı yok" in o["aciklama"] for o in etki)
    sayilar = [int(o["aciklama"].split(" ", 1)[0]) for o in etki]
    assert sayilar == sorted(sayilar, reverse=True)
    assert k["hedef_alti"]["durum"] == "tamam"   # kitapta kâr oranı %20 (eşik %10)
    assert k["olagan_disi_parametre"]["durum"] == "tamam"   # kitaptaki kur ve oranlar olağan
    assert {o["etiket"] for o in k["pay"]["ogeler"]} == {"elektrik", "dogalgaz"}   # %100,1 ve %99,5 (muhasebeye soruldu)
    assert k["gecici_kod"]["sayi"] == 12 and all(o["etiket"].startswith("SAYFA-") for o in k["gecici_kod"]["ogeler"])
    eslesmeyen = k["uretim_adetleri"]["ogeler"]   # 02/03 kod sorunu: neredeyse hepsi 02.* (birkaç kodun da kartı yok)
    assert eslesmeyen and sum(o["etiket"].startswith("02.") for o in eslesmeyen) > len(eslesmeyen) * 0.9
    assert any("Mısır" in o["etiket"] for o in k["hat"]["ogeler"])
    assert k["malzeme_karti"]["sayi"] > 0
    # Excel'de formül yerine elle yazılmış hücreler sorun değil, bilgi: 022'de dolum tutarı 20 ve diğer GÜG tutarı 10
    assert k["elle_hucre"]["durum"] == "bilgi"
    assert any("Dolum işçilik: tutar (P) 20" in o["aciklama"] and "Diğer GÜG: tutar (P) 10" in o["aciklama"] for o in k["elle_hucre"]["ogeler"])
    assert d["ozet"] == {d_: sum(1 for x in d["kontroller"] if x["durum"] == d_) for d_ in ("hata", "dikkat", "tamam", "bilgi")}


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


def test_olagan_disi_parametre_dikkat(ortam):
    """Kur 0 (sınırdan önce kaydedilmiş eski değer gibi) ve %250 enflasyon 'dikkat' olarak listelenir; çözüm Parametreler."""
    from datetime import date
    from decimal import Decimal
    from backend.servisler import parametre_servisi as ps
    s, sid = ortam
    try:
        ps.deger_ekle(s, sid, "enflasyon", Decimal("2.5"), date(2000, 1, 2), "yanlış yazım")
        kur = s.scalar(select(m.Parametre).where(m.Parametre.anahtar == "kur.USD"))
        s.add(m.ParametreDegeri(parametre_id=kur.id, senaryo_id=sid, kapsam_tipi="genel", deger=Decimal(0), gecerlilik_basi=date(2000, 1, 2), neden="eski"))
        s.flush()
        k = _k(ts.kontroller(s, sid, date(2000, 1, 3)))["olagan_disi_parametre"]
        assert k["durum"] == "dikkat" and k["cozum"]["yol"] == "/parametreler"
        metin = {o["etiket"]: o["aciklama"] for o in k["ogeler"]}
        assert metin["Enflasyon öngörüsü (tüm ürünler)"].startswith("değer %250: %100'ün üstünde")
        assert metin["USD kuru (tüm ürünler)"].startswith("değer 0 TL: kur 0 ya da eksi")
        assert all("." not in e.split(" (")[0] for e in metin)   # teknik anahtar (kur.USD) gösterilmez
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
