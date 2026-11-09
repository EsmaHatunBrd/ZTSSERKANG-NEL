"""SMM: kalıcı Canias reçeteleri (ürün ağacı dökümü) ve Excel'siz dönem devri."""
from decimal import Decimal as D_
from io import BytesIO
from openpyxl import Workbook
from tests.backend.test_api import istemci  # noqa: F401  (fixture)
from tests.backend.test_smm_asama import _excel, _urun

A = "/api/v1"
BASLIK = ["Alternatif Numarası", "Malzeme Kodu", "Malzeme Açıklaması", "Satır No", "Ürün Ağacı Kalem Tipi", "Tüketim Malzeme Kodu",
          "Tüketim Malzeme Adı", "Tüketim Miktarı", "Tüketim Birimi", "Fire Oranı", "Fireli Miktar"]


def _canias(fire_01_1: float = 10, ekstra: bool = False) -> bytes:
    """test_smm_asama'daki Excel reçeteleriyle aynı ürün ağacı (fire yüzde); 03-1'in '01' alternatifi var."""
    wb = Workbook()
    ws = wb.active
    ws.title = "TBLRESULT"
    ws.append(BASLIK)

    def urun(kod, ad, satirlar, alt="00"):
        ws.append([None, kod, ad, 0, 0, None, None, 0, None, 0, 0])   # ürün başlık satırı
        for i, (mal, mik, br, fire) in enumerate(satirlar, 1):
            ws.append([alt, kod, ad, i, 2, mal, mal, mik, br, fire, mik * (1 + fire / 100)])

    urun("01-1", "Biber salamura", [("HM-1", 0.5, "KG", fire_01_1)])
    urun("02-1", "Biber 370", [("01-1", 0.2, "KG", 0), ("AMB-1", 1, "AD", 0)])
    urun("03-1", "Biber 370 etiketli", [("02-1", 1, "AD", 1), ("ETK-1", 1, "AD", 0)])
    for i, (mal, mik, br, fire) in enumerate([("ETK-1", 2, "AD", 0)], 1):   # 03-1 alternatif 01: yalnız 2 etiket
        ws.append(["01", "03-1", "Biber 370 etiketli", i, 2, mal, mal, mik, br, fire, mik])
    urun("03-2", "Hazır kavanoz", [("ETK-1", 1, "MT", 0)])
    if ekstra:
        urun("03-9", "Yeni ürün", [("ETK-1", 1, "AD", 0)])
    b = BytesIO()
    wb.save(b)
    return b.getvalue()


def _yukle_donem(istemci):
    r = istemci.post(f"{A}/smm/donemler/yukle", files={"dosya": ("09-2026 SMM.xlsx", _excel())})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_recete_onizle_yukle_liste_alternatif(istemci):  # noqa: F811
    r = istemci.post(f"{A}/smm/receteler/onizle", files={"dosya": ("Reçete.xlsx", _canias())})
    assert r.status_code == 200, r.text
    o = r.json()
    assert o["urun_sayisi"] == 4 and o["eklenecek_urun"] == 4 and o["mevcut_urun"] == 0 and o["alternatifli_urun"] == 1
    assert o["asama"] == {"20": 1, "40": 1, "50": 2}
    assert istemci.get(f"{A}/smm/receteler").json()["kayitlar"] == []   # önizleme kaydetmez
    assert istemci.post(f"{A}/smm/receteler/yukle", files={"dosya": ("Reçete.xlsx", _canias())}).status_code == 200
    v = istemci.get(f"{A}/smm/receteler").json()
    assert v["son_yukleme"]["urun_sayisi"] == 4 and v["alternatifli_urun"] == 1
    u = next(x for x in v["kayitlar"] if x["ana_kod"] == "03-1")
    assert u["alternatifler"] == ["00", "01"] and u["secili_alternatif"] == "00" and u["satir_sayisi"] == 2
    d = istemci.get(f"{A}/smm/receteler/01-1").json()
    assert D_(d["alternatifler"][0]["satirlar"][0]["fire_orani"]) == D_("0.1")   # %10 -> 0,1
    r = istemci.put(f"{A}/smm/receteler/03-1/alternatif", json={"alternatif": "01"})
    assert r.status_code == 200 and r.json()["secili_alternatif"] == "01"
    assert istemci.put(f"{A}/smm/receteler/03-1/alternatif", json={"alternatif": "09"}).status_code == 422
    # yeniden yükleme: seçim korunur, yeni ürün sayılır
    o = istemci.post(f"{A}/smm/receteler/onizle", files={"dosya": ("Reçete.xlsx", _canias(ekstra=True))}).json()
    assert o["eklenecek_urun"] == 1 and o["degisecek_urun"] == 0 and o["kalkacak_urun"] == 0
    istemci.post(f"{A}/smm/receteler/yukle", files={"dosya": ("Reçete.xlsx", _canias(ekstra=True))})
    assert istemci.get(f"{A}/smm/receteler/03-1").json()["secili_alternatif"] == "01"
    assert istemci.get(f"{A}/smm/receteler", params={"asama": 50, "arama": "yeni"}).json()["kayitlar"][0]["ana_kod"] == "03-9"


def test_yanlis_dosya_reddedilir(istemci):  # noqa: F811
    r = istemci.post(f"{A}/smm/receteler/onizle", files={"dosya": ("x.xlsx", _excel())})
    assert r.status_code == 422 and "Canias" in r.json()["mesaj"]


def test_kiyas_ve_kalici_receteyle_hesap(istemci):  # noqa: F811
    did = _yukle_donem(istemci)
    istemci.post(f"{A}/smm/receteler/yukle", files={"dosya": ("Reçete.xlsx", _canias(fire_01_1=20))})
    k = istemci.get(f"{A}/smm/receteler/kiyas", params={"donem": did}).json()
    # 01-1'de fire farklı (Canias %20, Excel %10); diğerleri aynı
    assert k["sayilar"]["20"] == {"fire": 1} and k["sayilar"]["40"] == {"ayni": 1} and k["sayilar"]["50"] == {"ayni": 2}
    assert k["farklar"][0]["ana_kod"] == "01-1" and k["farklar"][0]["durum"] == "fire"
    # dönemin reçete kaynağı kalıcı reçetelere çevrilir: 01-1 fire 0,5 × 0,2 × 12 = 1,2 -> 6 + 2 + 1,2 = 9,2
    r = istemci.put(f"{A}/smm/donemler/{did}/recete-kaynagi", json={"kaynak": "ana"})
    assert r.status_code == 200 and r.json()["recete_kaynagi"] == "ana"
    v = istemci.get(f"{A}/smm/donemler/{did}/uretim", params={"asama": 20}).json()
    assert D_(_urun(v, "01-1")["birim_maliyet"]) == D_("9.2")
    assert istemci.put(f"{A}/smm/donemler/{did}/recete-kaynagi", json={"kaynak": "excel"}).status_code == 200
    v = istemci.get(f"{A}/smm/donemler/{did}/uretim", params={"asama": 20}).json()
    assert D_(_urun(v, "01-1")["birim_maliyet"]) == D_("8.6")


def test_yeni_donem_devri(istemci):  # noqa: F811
    did = _yukle_donem(istemci)   # Eylül 2026: biber sayımı 40 KG, değeri 480 TL
    istemci.post(f"{A}/smm/receteler/yukle", files={"dosya": ("Reçete.xlsx", _canias())})
    r = istemci.post(f"{A}/smm/donemler", json={"yil": 2026, "ay": 10})
    assert r.status_code == 201, r.text
    y = r.json()
    assert y["ad"] == "Ekim 2026" and y["recete_kaynagi"] == "ana" and y["devir_donem_id"] == did
    assert y["devir"]["onceki"] == "Eylül 2026" and y["devir"]["kalem"] == 1 and D_(y["devir"]["tutar"]) == 480
    st = istemci.get(f"{A}/smm/donemler/{y['id']}/stok", params={"yalniz_hareketli": True}).json()
    hm = next(x for x in st["kayitlar"] if x["kod"] == "HM-1")
    assert D_(hm["dbs_miktar"]) == 40 and D_(hm["dbs_tutar"]) == 480 and D_(hm["alim_tutar"]) == 0
    # dağıtım havuzları devreder; aşama hesabı kalıcı reçeteyle çalışır
    u = istemci.get(f"{A}/smm/donemler/{y['id']}/uretim", params={"asama": 50}).json()
    assert {h["anahtar"]: D_(h["tutar"]) for h in u["dagitim"]["havuzlar"]}["50_uretim"] == 300
    assert istemci.post(f"{A}/smm/donemler", json={"yil": 2026, "ay": 10}).status_code == 409
    assert istemci.post(f"{A}/smm/donemler", json={"yil": 2026, "ay": 13}).status_code == 422
    assert "SMM dönemi" in istemci.get(f"{A}/gunluk").text


def _yukle_recete(istemci, **kw):  # noqa: F811
    r = istemci.post(f"{A}/smm/receteler/yukle", files={"dosya": ("Reçete.xlsx", _canias(**kw))})
    assert r.status_code == 200, r.text
    return r.json()


def test_elle_duzenleme_ve_yeniden_yuklemede_koruma(istemci):  # noqa: F811
    _yukle_recete(istemci)
    d = istemci.get(f"{A}/smm/receteler/02-1").json()
    assert d["elle"] is False and d["canias_var"] is True
    amb = next(x for x in d["alternatifler"][0]["satirlar"] if x["malzeme_kod"] == "AMB-1")
    # satır güncelle: miktar 1 -> 2, fire %5
    r = istemci.put(f"{A}/smm/recete-satirlari/{amb['id']}", json={"miktar": "2", "fire_orani": "0.05"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["elle"] is True
    amb = next(x for x in d["alternatifler"][0]["satirlar"] if x["malzeme_kod"] == "AMB-1")
    assert D_(amb["miktar"]) == 2 and D_(amb["fire_orani"]) == D_("0.05")
    # satır ekle, sonra sil
    r = istemci.post(f"{A}/smm/receteler/02-1/satirlar", json={"malzeme_kod": "ETK-1", "miktar": "1", "birim": "AD", "fire_orani": "0"})
    assert r.status_code == 201
    yeni = next(x for x in r.json()["alternatifler"][0]["satirlar"] if x["malzeme_kod"] == "ETK-1")
    assert yeni["satir_no"] == 3
    assert istemci.delete(f"{A}/smm/recete-satirlari/{yeni['id']}").status_code == 200
    # doğrulama
    assert istemci.post(f"{A}/smm/receteler/02-1/satirlar", json={"malzeme_kod": "02-1", "miktar": "1", "birim": "AD"}).status_code == 422
    assert istemci.post(f"{A}/smm/receteler/02-1/satirlar", json={"malzeme_kod": "X", "miktar": "0", "birim": "AD"}).status_code == 422
    assert istemci.post(f"{A}/smm/receteler/YOK/satirlar", json={"malzeme_kod": "X", "miktar": "1", "birim": "AD"}).status_code == 404
    # alternatif kopyala
    r = istemci.post(f"{A}/smm/receteler/02-1/alternatif-kopyala", json={"kaynak": "00", "yeni": "02"})
    assert r.status_code == 201 and [a["alternatif"] for a in r.json()["alternatifler"]] == ["00", "02"]
    assert istemci.post(f"{A}/smm/receteler/02-1/alternatif-kopyala", json={"kaynak": "00", "yeni": "02"}).status_code == 409
    # yeni ürün reçetesi
    r = istemci.post(f"{A}/smm/receteler", json={"ana_kod": "03-77", "ana_ad": "Elle ürün", "malzeme_kod": "02-1", "miktar": "1", "birim": "AD"})
    assert r.status_code == 201 and r.json()["asama"] == 50 and r.json()["canias_var"] is False
    assert istemci.post(f"{A}/smm/receteler", json={"ana_kod": "03-77", "malzeme_kod": "02-1", "miktar": "1", "birim": "AD"}).status_code == 409
    # yeniden yükleme: elle ürünler korunur ve önizlemede listelenir
    o = istemci.post(f"{A}/smm/receteler/onizle", files={"dosya": ("Reçete.xlsx", _canias())}).json()
    korunan = {x["ana_kod"]: x for x in o["korunan"]}
    assert set(korunan) == {"02-1", "03-77"} and korunan["02-1"]["canias_farkli"] is True and korunan["03-77"]["caniasta_var"] is False
    _yukle_recete(istemci)
    d = istemci.get(f"{A}/smm/receteler/02-1").json()
    assert D_(next(x for x in d["alternatifler"][0]["satirlar"] if x["malzeme_kod"] == "AMB-1")["miktar"]) == 2
    assert istemci.get(f"{A}/smm/receteler/03-77").status_code == 200
    assert istemci.get(f"{A}/smm/receteler").json()["elle_urun"] == 2
    # Canias'a döndür
    r = istemci.post(f"{A}/smm/receteler/02-1/canias-a-don")
    assert r.status_code == 200 and r.json()["elle"] is False
    assert [a["alternatif"] for a in r.json()["alternatifler"]] == ["00"]
    assert D_(next(x for x in r.json()["alternatifler"][0]["satirlar"] if x["malzeme_kod"] == "AMB-1")["miktar"]) == 1
    assert istemci.post(f"{A}/smm/receteler/03-77/canias-a-don").status_code == 422
    # malzeme arama
    m = istemci.get(f"{A}/smm/malzeme-ara", params={"q": "etk"}).json()
    assert m[0]["kod"] == "ETK-1"
    assert "reçete satırı değişti" in istemci.get(f"{A}/gunluk").text


def test_recete_asamasi_elle(istemci):  # noqa: F811
    _yukle_recete(istemci)
    r = istemci.put(f"{A}/smm/receteler/03-2/asama", json={"asama": 40})
    assert r.status_code == 200 and r.json()["asama"] == 40 and r.json()["kod_asamasi"] == 50 and r.json()["elle"] is True
    assert istemci.get(f"{A}/smm/receteler", params={"asama": 40}).json()["asama_sayilari"]["40"] == 2
    assert istemci.put(f"{A}/smm/receteler/03-2/asama", json={"asama": 30}).status_code == 422
    # yeniden yüklemede korunur
    _yukle_recete(istemci)
    assert istemci.get(f"{A}/smm/receteler/03-2").json()["asama"] == 40
