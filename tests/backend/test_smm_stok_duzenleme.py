"""SMM stok kalemi elle düzenleme: alan güncelleme, yeni kalem, günlük kaydı, 'elle' listesi, doğrulamalar."""
from decimal import Decimal
from tests.backend.test_api import istemci  # noqa: F401  (fixture)
from tests.backend.test_smm_asama import _yukle, _urun

A = "/api/v1"
H = {"X-Kullanici": "esma"}


def _stok(c, did, **q):
    r = c.get(f"{A}/smm/donemler/{did}/stok", params={"yalniz_hareketli": "false", **q})
    assert r.status_code == 200, r.text
    return r.json()


def test_kalem_guncelle_sayim_degisince_sarf_ve_dss_yeniden_hesaplanir(istemci):  # noqa: F811
    did = _yukle(istemci)
    once = _stok(istemci, did)
    kod = once["kayitlar"][0]["kod"]
    satir = _urun(once, kod)
    yeni_sayim = str(Decimal(satir["sayim_miktar"]) + 5)
    r = istemci.patch(f"{A}/smm/donemler/{did}/stok/{kod}", json={"sayim_miktar": yeni_sayim, "neden": "sayım düzeltmesi"}, headers=H)
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["degisti"] == ["sayim_miktar"] and v["sayim_miktar"] == yeni_sayim
    sonra = _urun(_stok(istemci, did), kod)
    assert sonra["sayim_miktar"] == yeni_sayim
    assert Decimal(sonra["sarf_miktar"]) == Decimal(satir["sarf_miktar"]) - 5
    # ortalama fiyat değişmez, DSS tutarı sayımla orantılı artar
    assert sonra["ortalama_fiyat"] == satir["ortalama_fiyat"]
    assert Decimal(sonra["dss_tutar"]) >= Decimal(satir["dss_tutar"])
    # 'elle' listesi ve günlük
    e = istemci.get(f"{A}/smm/donemler/{did}/stok/elle").json()["kayitlar"]
    assert e[kod]["alanlar"] == ["sayim_miktar"] and e[kod]["kullanici"] == "esma" and e[kod]["kayit"] == 1
    g = istemci.get(f"{A}/gunluk", params={"q": "sayım düzeltmesi"}).json()
    assert g["toplam"] >= 1


def test_degismeyen_deger_kayit_acmaz_ve_neden_zorunlu(istemci):  # noqa: F811
    did = _yukle(istemci)
    kod = _stok(istemci, did)["kayitlar"][0]["kod"]
    satir = _urun(_stok(istemci, did), kod)
    r = istemci.patch(f"{A}/smm/donemler/{did}/stok/{kod}", json={"sayim_miktar": satir["sayim_miktar"], "neden": "aynı"}, headers=H)
    assert r.status_code == 200 and r.json()["degisti"] == []
    assert istemci.get(f"{A}/smm/donemler/{did}/stok/elle").json()["kayitlar"] == {}
    assert istemci.patch(f"{A}/smm/donemler/{did}/stok/{kod}", json={"sayim_miktar": "1"}, headers=H).status_code == 422
    assert istemci.patch(f"{A}/smm/donemler/{did}/stok/{kod}", json={"sayim_miktar": "-1", "neden": "x"}, headers=H).status_code == 422
    assert istemci.patch(f"{A}/smm/donemler/{did}/stok/{kod}", json={"bilinmeyen": "1", "neden": "x"}, headers=H).status_code == 422
    assert istemci.patch(f"{A}/smm/donemler/{did}/stok/YOK-KOD", json={"sayim_miktar": "1", "neden": "x"}, headers=H).status_code == 404


def test_kalem_ekle_ve_cakisma(istemci):  # noqa: F811
    did = _yukle(istemci)
    govde = {"kod": "YENI-001", "ad": "Yeni kavanoz", "birim": "AD", "tur": "0008-Ambalaj Malzeme", "mizan_kodu": "150.08.001",
             "dbs_miktar": "100", "dbs_tutar": "1000", "sayim_miktar": "40", "neden": "Excel'de yoktu"}
    r = istemci.post(f"{A}/smm/donemler/{did}/stok", json=govde, headers=H)
    assert r.status_code == 201, r.text
    v = r.json()
    assert v["kod"] == "YENI-001" and v["ortalama_fiyat"] == "10" and v["sarf_miktar"] == "60" and v["degisti"] == ["ekle"]
    assert _urun(_stok(istemci, did), "YENI-001")["dss_tutar"] == "400"
    assert istemci.post(f"{A}/smm/donemler/{did}/stok", json=govde, headers=H).status_code == 409
    e = istemci.get(f"{A}/smm/donemler/{did}/stok/elle").json()["kayitlar"]
    assert e["YENI-001"]["alanlar"] == ["ekle"]
    # kart alanı güncelleme de izlenir
    r = istemci.patch(f"{A}/smm/donemler/{did}/stok/YENI-001", json={"ad": "Yeni kavanoz 720", "neden": "ad düzeltme"}, headers=H)
    assert r.status_code == 200 and r.json()["ad"] == "Yeni kavanoz 720"
    e = istemci.get(f"{A}/smm/donemler/{did}/stok/elle").json()["kayitlar"]
    assert e["YENI-001"]["alanlar"] == ["ad", "ekle"] and e["YENI-001"]["kayit"] == 2
