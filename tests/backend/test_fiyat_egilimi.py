"""Fiyat eğilimi (analiz önerisi 9): saf pencere/yıllıklandırma hesabı, uç ve şema (küçük kurulum + gerçek kitap), eşik kuralları,
Veri Kontrolü ögesi. Şirket verisi test çıktısına yazılmaz (yalnız kod ve sayılar)."""
from datetime import date
from decimal import Decimal as D_
import pytest
from fastapi.testclient import TestClient
from backend.depo.veritabani import Base, motor_olustur, oturum_fabrikasi, oturum_ver
from backend.servisler import fiyat_egilimi_servisi as fe, import_servisi as ims, tutarlilik_servisi as ts
from backend.servisler.hatalar import DogrulamaHatasi
from backend.uygulama import uygulama_olustur
from tests.backend.test_api import _kur, _senaryo, istemci  # noqa: F401  (fixture)

A = "/api/v1"
ALANLAR = {"kod", "ad", "tip", "para_birimi", "ilk_fiyat", "ilk_tarih", "son_fiyat", "son_tarih", "kayit_sayisi", "degisim_yuzde", "yillik_yuzde",
           "esik_yuzde", "enflasyonu_asiyor", "kullanan_urun_sayisi"}


def test_ay_geri():
    assert fe.ay_geri(date(2026, 11, 10), 12) == date(2025, 11, 10)
    assert fe.ay_geri(date(2026, 3, 31), 1) == date(2026, 2, 28)
    assert fe.ay_geri(date(2026, 1, 15), 13) == date(2024, 12, 15)
    assert fe.ay_geri(date(2024, 3, 31), 1) == date(2024, 2, 29)


def test_pencere_degisimi_saf():
    # 10 -> 13 TL 6 ayda: değişim %30, yıllık (1,3^2 - 1) = %69
    d = fe.pencere_degisimi([(date(2026, 6, 1), D_(10)), (date(2026, 11, 1), D_(13))], date(2026, 6, 1), date(2026, 12, 1), 6)
    assert (d["ilk_fiyat"], d["son_fiyat"], d["kayit_sayisi"]) == (D_(10), D_(13), 2)
    assert d["degisim_yuzde"] == D_("30.00") and d["yillik_yuzde"] == D_("69.00")
    assert d["ilk_tarih"] == date(2026, 6, 1) and d["son_tarih"] == date(2026, 11, 1)
    # 12 ayda aynı artış: yıllık = değişim
    d = fe.pencere_degisimi([(date(2025, 12, 1), D_(10)), (date(2026, 11, 1), D_(13))], date(2025, 12, 1), date(2026, 12, 1), 12)
    assert d["degisim_yuzde"] == d["yillik_yuzde"] == D_("30.00")
    # tek kayıt: değişim 0, kayıt sayısı 1
    d = fe.pencere_degisimi([(date(2026, 6, 1), D_("5.9"))], date(2026, 6, 1), date(2026, 12, 1), 6)
    assert d["kayit_sayisi"] == 1 and d["degisim_yuzde"] == 0 and d["yillik_yuzde"] == 0 and d["ilk_fiyat"] == d["son_fiyat"] == D_("5.9")
    # pencere başındaki geçerli fiyat = pencere öncesindeki son kayıt (8), pencere içindeki eski kayıt (6) ilk sayılmaz
    d = fe.pencere_degisimi([(date(2025, 1, 1), D_(6)), (date(2025, 9, 1), D_(8)), (date(2026, 3, 1), D_(10))], date(2025, 12, 1), date(2026, 12, 1), 12)
    assert d["ilk_fiyat"] == D_(8) and d["son_fiyat"] == D_(10) and d["kayit_sayisi"] == 2 and d["degisim_yuzde"] == D_("25.00")
    # pencere sonundan sonra başlayan kayıt sayılmaz; hiç geçerli kayıt yoksa None
    d = fe.pencere_degisimi([(date(2026, 6, 1), D_(10)), (date(2027, 1, 1), D_(99))], date(2026, 6, 1), date(2026, 12, 1), 6)
    assert d["son_fiyat"] == D_(10) and d["kayit_sayisi"] == 1
    assert fe.pencere_degisimi([(date(2027, 1, 1), D_(99))], date(2026, 6, 1), date(2026, 12, 1), 6) is None
    # ilk fiyat 0: oran tanımsız
    d = fe.pencere_degisimi([(date(2026, 6, 1), D_(0)), (date(2026, 9, 1), D_(5))], date(2026, 6, 1), date(2026, 12, 1), 6)
    assert d["degisim_yuzde"] is None and d["yillik_yuzde"] is None and d["kayit_sayisi"] == 2
    with pytest.raises(DogrulamaHatasi):
        fe.pencere_degisimi([(date(2026, 6, 1), D_(10))], date(2026, 6, 1), date(2026, 12, 1), 0)


def _kurulum(c, sid, oturum):
    """KAV (TL) tek kayıt 5,9; TLM (TL) 10 -> 13 (6 ay, enflasyon %25 -> aşıyor); ETK (USD) 1,00 -> 1,05 (3 ay; dövizde eşik 0 -> aşıyor).
    KAV TEST ürününün reçetesinde (1 üründe); diğerleri reçetede yok."""
    _kur(c, sid, oturum)
    for kod, ad, pb in (("TLM", "Tuz", "TL"), ("ETK", "Etiket", "USD")):
        assert c.post(f"{A}/malzemeler", json={"kod": kod, "ad": ad, "tip": "0001-Hammadde", "birim": "KG", "para_birimi": pb, "zs": "S"}).status_code in (200, 201)
    for kod, fiyat, tarih in (("TLM", "10", "2026-06-01"), ("TLM", "13", "2026-11-01"), ("ETK", "1.00", "2026-06-01"), ("ETK", "1.05", "2026-09-01")):
        r = c.post(f"{A}/malzemeler/{kod}/fiyatlar?senaryo={sid}", json={"onay": True, "fiyat": fiyat, "gecerlilik_basi": tarih, "neden": "test"})
        assert r.status_code == 201, r.text


def test_uc_esik_ve_siralama(istemci, oturum):
    sid = _senaryo(istemci); _kurulum(istemci, sid, oturum)
    r = istemci.get(f"{A}/analiz/fiyat-egilimi?senaryo={sid}&ay=6&tarih=2026-12-01")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["senaryo_id"] == sid and d["ay"] == 6 and d["tarih"] == "2026-12-01" and d["pencere_basi"] == "2026-06-01"
    assert D_(d["enflasyon_yuzde"]) == 25
    assert d["toplam"] == 3 and d["asan_sayisi"] == 2
    assert all(set(x) == ALANLAR for x in d["satirlar"])
    k = {x["kod"]: x for x in d["satirlar"]}
    tlm = k["TLM"]
    assert (D_(tlm["ilk_fiyat"]), D_(tlm["son_fiyat"]), tlm["kayit_sayisi"]) == (D_(10), D_(13), 2)
    assert D_(tlm["degisim_yuzde"]) == D_("30.00") and D_(tlm["yillik_yuzde"]) == D_("69.00") and D_(tlm["esik_yuzde"]) == 25
    assert tlm["enflasyonu_asiyor"] is True and tlm["para_birimi"] == "TL" and tlm["kullanan_urun_sayisi"] == 0
    etk = k["ETK"]   # döviz: eşik 0; 1,00 -> 1,05 (pencere 6 ay): yıllık (1,05^2 - 1) = %10,25
    assert etk["para_birimi"] == "USD" and D_(etk["esik_yuzde"]) == 0 and D_(etk["degisim_yuzde"]) == D_("5.00") and D_(etk["yillik_yuzde"]) == D_("10.25")
    assert etk["enflasyonu_asiyor"] is True
    kav = k["KAV"]   # tek kayıt: değişim 0, aşmıyor, 1 üründe
    assert kav["kayit_sayisi"] == 1 and D_(kav["degisim_yuzde"]) == 0 and kav["enflasyonu_asiyor"] is False and kav["kullanan_urun_sayisi"] == 1
    assert [x["kod"] for x in d["satirlar"]] == ["TLM", "ETK", "KAV"]   # aşanlar önce, yıllık % azalan
    # yalniz_asan: yalnız aşanlar, asan_sayisi aynı
    d2 = istemci.get(f"{A}/analiz/fiyat-egilimi?senaryo={sid}&ay=6&tarih=2026-12-01&yalniz_asan=1").json()
    assert [x["kod"] for x in d2["satirlar"]] == ["TLM", "ETK"] and d2["toplam"] == 2 and d2["asan_sayisi"] == 2
    # 12 aylık pencere (varsayılan ay), aynı tarih: TLM yıllık = değişim %30 -> yine aşıyor; ETK %5 > 0 + 1 -> aşıyor
    d3 = istemci.get(f"{A}/analiz/fiyat-egilimi?senaryo={sid}&tarih=2026-12-01").json()
    k3 = {x["kod"]: x for x in d3["satirlar"]}
    assert d3["ay"] == 12 and D_(k3["TLM"]["yillik_yuzde"]) == D_("30.00") and D_(k3["ETK"]["yillik_yuzde"]) == D_("5.00")
    # tolerans: eşiğin 1 puan üstüne kadar aşmıyor sayılır (TL %25 eşik, %26 -> aşmıyor)
    # eşik %28 + 1 puan tolerans = 29 < 30 -> aşıyor
    assert istemci.post(f"{A}/parametreler/enflasyon/degerler?senaryo={sid}", json={"deger": "0.28", "gecerlilik_basi": "2026-06-01", "neden": "test"}).status_code == 201
    k4 = {x["kod"]: x for x in istemci.get(f"{A}/analiz/fiyat-egilimi?senaryo={sid}&tarih=2026-12-01").json()["satirlar"]}
    assert D_(k4["TLM"]["esik_yuzde"]) == 28 and k4["TLM"]["enflasyonu_asiyor"] is True
    assert istemci.post(f"{A}/parametreler/enflasyon/degerler?senaryo={sid}", json={"deger": "0.295", "gecerlilik_basi": "2026-06-01", "neden": "test"}).status_code == 201
    k5 = {x["kod"]: x for x in istemci.get(f"{A}/analiz/fiyat-egilimi?senaryo={sid}&tarih=2026-12-01").json()["satirlar"]}
    assert k5["TLM"]["enflasyonu_asiyor"] is False   # 30 <= 29,5 + 1


def test_uc_hatalar(istemci, oturum):
    sid = _senaryo(istemci); _kurulum(istemci, sid, oturum)
    r = istemci.get(f"{A}/analiz/fiyat-egilimi?senaryo={sid}&ay=0")
    assert r.status_code == 422 and set(r.json()) == {"hata", "mesaj", "alanlar", "kod"}
    assert istemci.get(f"{A}/analiz/fiyat-egilimi?senaryo=9999").status_code == 404
    with pytest.raises(DogrulamaHatasi):
        fe.egilim(oturum, sid, 0)


def test_veri_kontrolu_ogesi(istemci, oturum):
    sid = _senaryo(istemci); _kurulum(istemci, sid, oturum)
    k = {x["kod"]: x for x in ts.kontroller(oturum, sid, date(2026, 12, 1))["kontroller"]}
    fk = k["fiyat_egilimi"]
    assert fk["durum"] == "bilgi" and fk["sayi"] == 2 and fk["cozum"] == {"etiket": "Analiz · Fiyat eğilimi", "yol": "/fiyat-egilimi"}
    o = {x["etiket"].split(" · ")[0]: x for x in fk["ogeler"]}
    assert o["TLM"]["aciklama"] == "yıllık %30,0 (eşik %25,0) · 0 üründe" and o["TLM"]["yol"] == "/fiyat-egilimi?arama=TLM"
    assert o["ETK"]["aciklama"] == "yıllık %5,0 (eşik %0,0) · 0 üründe"
    # tarihte aşan yoksa 'tamam' (pencere 2026-06-01 öncesi: yalnız ilk kayıtlar)
    assert {x["kod"]: x for x in ts.kontroller(oturum, sid, date(2026, 6, 1))["kontroller"]}["fiyat_egilimi"]["durum"] == "tamam"


@pytest.fixture(scope="module")
def ortam(excel_yolu):
    engine = motor_olustur("sqlite://"); Base.metadata.create_all(engine)
    s = oturum_fabrikasi(engine)()
    sid = ims.excel_tam_yukle(s, excel_yolu, "2026-2027", "Bütçe")["senaryo_id"]
    s.commit()
    yield s, sid
    s.close()


def test_gercek_kitap_uc_ve_sema(ortam):
    s, sid = ortam
    app = uygulama_olustur()
    app.dependency_overrides[oturum_ver] = lambda: s
    c = TestClient(app)
    r = c.get(f"{A}/analiz/fiyat-egilimi?senaryo={sid}")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ay"] == 12 and d["toplam"] > 100 and d["enflasyon_yuzde"] is not None
    assert all(set(x) == ALANLAR for x in d["satirlar"])
    assert all(x["kayit_sayisi"] >= 1 and x["kullanan_urun_sayisi"] >= 0 for x in d["satirlar"])
    assert all(D_(x["esik_yuzde"]) == (D_(d["enflasyon_yuzde"]) if x["para_birimi"] == "TL" else 0) for x in d["satirlar"])
    asan = [x for x in d["satirlar"] if x["enflasyonu_asiyor"]]
    assert len(asan) == d["asan_sayisi"] and [x["kod"] for x in d["satirlar"][:len(asan)]] == [x["kod"] for x in asan]
    for x in asan:
        assert D_(x["yillik_yuzde"]) > D_(x["esik_yuzde"]) + 1
    yillik = [D_(x["yillik_yuzde"]) for x in d["satirlar"] if x["yillik_yuzde"] is not None and not x["enflasyonu_asiyor"]]
    assert yillik == sorted(yillik, reverse=True)
    d2 = c.get(f"{A}/analiz/fiyat-egilimi?senaryo={sid}&yalniz_asan=1").json()
    assert d2["toplam"] == d["asan_sayisi"] and all(x["enflasyonu_asiyor"] for x in d2["satirlar"])
