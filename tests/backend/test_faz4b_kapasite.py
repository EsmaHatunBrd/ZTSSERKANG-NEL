"""Faz 4b B2: uretim_kapasitesi tablosu, Excel importu ve /uretim-kapasitesi uçları."""
from decimal import Decimal as D_
import pytest
from backend.depo import modeller as m
from backend.depo.veritabani import Base, motor_olustur, oturum_fabrikasi
from backend.servisler import import_servisi as ims
from tests.backend.test_api import _senaryo, istemci  # noqa: F401

A = "/api/v1"
ALANLAR = {"net_kapasite": "1000", "net_sure": "1.2", "toplam_kapasite": "900", "toplam_sure": "1.1", "hedef_uretim": "800", "ortalama_isci": "12.5"}


@pytest.fixture(scope="module")
def yuklu(excel_yolu):
    engine = motor_olustur("sqlite://"); Base.metadata.create_all(engine)
    s = oturum_fabrikasi(engine)()
    ozet = ims.excel_tam_yukle(s, excel_yolu, "2026-2027", "Berrak fiyat çalışması")
    s.commit()
    yield s, ozet
    s.close()


def test_import_kapasite_yazar_ve_tekrari_uyarir(yuklu, excel_yolu):
    from collections import Counter
    from fiyat_motoru import excel_okuyucu as eo
    s, o = yuklu
    satirlar = eo.uretim_adetlerini_oku(eo.excel_ac(excel_yolu)[1])
    sayac = Counter(x["urun_kodu"] for x in satirlar)
    tekrar = next(k for k, v in sayac.items() if v > 1)
    ilk_tekrar = next(x for x in satirlar if x["urun_kodu"] == tekrar)
    n = s.query(m.UretimKapasitesi).count()
    assert o["kapasite"] == n == len(sayac) and 65 <= n <= 80
    assert any(tekrar in u and "Üretim Adetleri" in u for u in o["uyarilar"])
    ilk = satirlar[0]
    k = s.query(m.UretimKapasitesi).filter_by(urun_kodu=ilk["urun_kodu"]).one()
    assert (k.hedef_uretim, k.ortalama_isci, k.net_sure) == (ilk["hedef_uretim"], ilk["ortalama_isci"], ilk["net_sure"]) and k.senaryo_id == o["senaryo_id"]
    kayit = s.query(m.UretimKapasitesi).filter_by(urun_kodu=tekrar).one()   # tekrarda ilki korunur
    assert (kayit.net_kapasite, kayit.hedef_uretim) == (ilk_tekrar["net_kapasite"], ilk_tekrar["hedef_uretim"])


def test_ozet_geriye_uyumlu_alanlar(yuklu):
    _, o = yuklu
    assert {"malzeme", "fiyat", "havuz", "ambalaj", "urun", "recete", "parametre", "atlanan", "uyarilar", "kart_farklari", "yeniden_adlandirilan",
            "urun_parametre_farklari", "kapasite"} <= set(o)


def _doldur(oturum, sid, n=3):
    for i in range(n):
        oturum.add(m.UretimKapasitesi(senaryo_id=sid, urun_kodu=f"K{i}", urun_ad=f"Ürün {i}", **{a: D_(v) + i for a, v in ALANLAR.items()}))
    oturum.flush()


def test_liste_sayfalama(istemci, oturum):
    sid = _senaryo(istemci); _doldur(oturum, sid, 3)
    r = istemci.get(f"{A}/uretim-kapasitesi?senaryo={sid}&sayfa=1&boyut=2").json()
    assert r["toplam"] == 3 and [x["urun_kodu"] for x in r["kayitlar"]] == ["K0", "K1"]
    assert r["kayitlar"][0] == {"urun_kodu": "K0", "urun_ad": "Ürün 0", **{a: str(D_(v)) for a, v in ALANLAR.items()}}
    assert [x["urun_kodu"] for x in istemci.get(f"{A}/uretim-kapasitesi?senaryo={sid}&sayfa=2&boyut=2").json()["kayitlar"]] == ["K2"]
    assert istemci.get(f"{A}/uretim-kapasitesi?senaryo=999").status_code == 404


def test_guncelle_neden_ve_degisiklik_kaydi(istemci, oturum):
    sid = _senaryo(istemci); _doldur(oturum, sid, 1)
    g = {**ALANLAR, "hedef_uretim": "777", "neden": "plan revizyonu"}
    r = istemci.put(f"{A}/uretim-kapasitesi/K0?senaryo={sid}", json=g, headers={"X-Kullanici": "esma"})
    assert r.status_code == 200 and r.json()["hedef_uretim"] == "777" and r.json()["urun_ad"] == "Ürün 0"
    kayit = oturum.query(m.DegisiklikKaydi).filter_by(tablo="uretim_kapasitesi").one()
    assert kayit.islem == "guncelle" and kayit.kullanici == "esma" and kayit.eski["hedef_uretim"] == "800" and kayit.yeni["hedef_uretim"] == "777"
    assert kayit.yeni["_neden"] == "plan revizyonu"
    assert istemci.get(f"{A}/uretim-kapasitesi?senaryo={sid}").json()["kayitlar"][0]["hedef_uretim"] == "777"
    # değişmeyen gövde yeni kayıt açmaz
    istemci.put(f"{A}/uretim-kapasitesi/K0?senaryo={sid}", json=g)
    assert oturum.query(m.DegisiklikKaydi).filter_by(tablo="uretim_kapasitesi").count() == 1


def test_guncelle_dogrulama(istemci, oturum):
    sid = _senaryo(istemci); _doldur(oturum, sid, 1)
    assert istemci.put(f"{A}/uretim-kapasitesi/K0?senaryo={sid}", json={**ALANLAR, "neden": ""}).status_code == 422
    assert istemci.put(f"{A}/uretim-kapasitesi/K0?senaryo={sid}", json=ALANLAR).status_code == 422
    assert istemci.put(f"{A}/uretim-kapasitesi/K0?senaryo={sid}", json={**ALANLAR, "hedef_uretim": "-1", "neden": "x"}).status_code == 422
    assert istemci.put(f"{A}/uretim-kapasitesi/K0?senaryo=999", json={**ALANLAR, "neden": "x"}).status_code == 404


def test_yeni_kod_olusturur(istemci, oturum):
    sid = _senaryo(istemci)
    r = istemci.put(f"{A}/uretim-kapasitesi/YENI?senaryo={sid}", json={**ALANLAR, "urun_ad": "Yeni ürün", "neden": "eklendi"})
    assert r.status_code == 200 and r.json()["urun_ad"] == "Yeni ürün"
    assert istemci.get(f"{A}/uretim-kapasitesi?senaryo={sid}").json()["toplam"] == 1
    kayit = oturum.query(m.DegisiklikKaydi).filter_by(tablo="uretim_kapasitesi").one()
    assert kayit.islem == "olustur"


def test_acilista_parametre_tanimlari_tohumlanir(monkeypatch):
    from backend.depo import veritabani as vt
    engine = vt.motor_olustur("sqlite://")
    monkeypatch.setattr(vt, "motor_olustur", lambda *a, **k: engine)
    monkeypatch.setattr(vt, "_ENGINE", None); monkeypatch.setattr(vt, "_SESSION", None)
    gen = vt.oturum_ver(); s = next(gen)
    anahtarlar = {a for (a,) in s.query(m.Parametre.anahtar)}
    assert {"maliyet_sapma", "kur.ZAR", "kur.RUB"} <= anahtarlar
    gen.close()
