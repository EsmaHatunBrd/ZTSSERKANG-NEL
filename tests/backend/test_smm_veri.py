"""SMM: aylık veri girişi (kaynak bazında yükleme, elle düzeltme, kontrol listesi) ve dönem kapanışı (kilit, fiş Excel'i)."""
from decimal import Decimal as D_
from io import BytesIO
from openpyxl import Workbook, load_workbook
from tests.backend.test_api import istemci  # noqa: F401  (fixture)
from tests.backend.test_smm_asama import _excel

A = "/api/v1"


def _rapor(baslik: list, satirlar: list[list], sayfa: str = "Rapor") -> bytes:
    """Tek sayfalık rapor: 1. satır toplam (boş), 2. satır başlık, sonra veriler (SMM Excel sayfa düzeni)."""
    wb = Workbook()
    ws = wb.active
    ws.title = sayfa
    ws.append([])
    ws.append(baslik)
    for r in satirlar:
        ws.append(r)
    b = BytesIO()
    wb.save(b)
    return b.getvalue()


ALIM_BASLIK = ["Tür", "Malzeme(Sınıf)Kodu", "Açıklama", "Varyant", "Varyant", "Birimi", "Giren Miktar", "", "", "", "Giriş Maliyeti",
               "Çıkış Miktarı"] + [""] * 7 + ["Tür"]


def _ekim(istemci):
    r = istemci.post(f"{A}/smm/donemler/yukle", files={"dosya": ("09-2026 SMM.xlsx", _excel())})
    assert r.status_code == 200, r.text
    r = istemci.post(f"{A}/smm/donemler", json={"yil": 2026, "ay": 10})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _yukle(istemci, did, kaynak, icerik):
    return istemci.post(f"{A}/smm/donemler/{did}/veri/{kaynak}", files={"dosya": (f"{kaynak}.xlsx", icerik)})


def test_kontrol_listesi_ve_kaynak_yukleme(istemci):  # noqa: F811
    did = _ekim(istemci)
    v = istemci.get(f"{A}/smm/donemler/{did}/veri").json()
    assert v["donem_basi"]["kaynak"] == "devir" and v["donem_basi"]["hazir"] is True and D_(v["donem_basi"]["tutar"]) == 480
    assert set(v["eksik"]) == {"Alım ve satış", "Üretim miktarları", "Sayım (dönem sonu stok)", "Gider mizanı (720 / 730)"}
    # alım: biber 50 KG 700 TL; ayrıca 5 KG satış; yeni kalem YENI-1
    alim = _rapor(ALIM_BASLIK, [
        [None, "HM-1", "Biber", 9, 9, "KG", 50, None, None, None, 700, 0] + [None] * 7 + ["Alış"],
        [None, "HM-1", "Biber", 9, 9, "KG", 0, None, None, None, 0, 5] + [None] * 7 + ["Satış"],
        [None, "YENI-1", "Yeni malzeme", 9, 9, "AD", 10, None, None, None, 30, 0] + [None] * 7 + ["Alış"],
    ])
    r = _yukle(istemci, did, "alim", alim)
    assert r.status_code == 200, r.text
    st = istemci.get(f"{A}/smm/donemler/{did}/stok", params={"yalniz_hareketli": True}).json()
    hm = next(x for x in st["kayitlar"] if x["kod"] == "HM-1")
    assert D_(hm["alim_miktar"]) == 50 and D_(hm["alim_tutar"]) == 700 and D_(hm["dbs_miktar"]) == 40
    assert any(x["kod"] == "YENI-1" for x in st["kayitlar"])
    # yeniden yükleme eskisinin yerine geçer (toplanmaz)
    _yukle(istemci, did, "alim", alim)
    st = istemci.get(f"{A}/smm/donemler/{did}/stok").json()
    assert D_(next(x for x in st["kayitlar"] if x["kod"] == "HM-1")["alim_miktar"]) == 50
    # sayım, üretim, gider mizanı
    assert _yukle(istemci, did, "sayim", _rapor(["StokKartıKodu", "Ad", "Miktar"], [["HM-1", "Biber", 30]], "DSS")).status_code == 200
    assert _yukle(istemci, did, "uretim", _rapor(["MalzemeKodu", "Ad"] + [""] * 12 + ["TOPLAM"], [["01-1", "Biber salamura"] + [0] * 12 + [200]]
                                                  )).status_code == 200
    r = _yukle(istemci, did, "gider_mizan", _rapor(["Hesap Kodu", "Hesap Adı", "B", "A", "BB", "BA", "Bakiye"],
                                                    [["720", "İşçilik", 0, 0, 0, 0, 2000], ["730", "GÜG", 0, 0, 0, 0, 3000]]))
    v = r.json()
    assert v["eksik"] == [] and D_(v["ayarlar"]["gider_720"]) == 2000
    k = {x["kaynak"]: x for x in v["kaynaklar"]}
    assert k["alim"]["yuklendi"] and k["alim"]["son"]["satir"] == 2 and k["alim"]["son"]["excel"] is False and k["iade"]["yuklendi"] is False
    # yanlış dosya: başlık yok
    r = _yukle(istemci, did, "sayim", _rapor(["Kod", "Miktar"], [["HM-1", 1]]))
    assert r.status_code == 422 and "başlık" in r.json()["mesaj"]
    assert _yukle(istemci, did, "yok", alim).status_code == 422
    # SMM özeti yeni verilerle: 720 = 2000
    o = istemci.get(f"{A}/smm/donemler/{did}/ozet").json()
    uretim = next(b for b in o["tablo"] if b["hesap"] == "72x")
    assert D_(next(x for x in uretim["satirlar"] if x["ad"].startswith("720"))["tutar"]) == 2000


def test_ayarlar(istemci):  # noqa: F811
    did = _ekim(istemci)
    v = istemci.put(f"{A}/smm/donemler/{did}/ayarlar", json={"finansman": "100", "gider_730": "900"}).json()
    assert D_(v["ayarlar"]["finansman"]) == 100 and D_(v["ayarlar"]["gider_730"]) == 900
    assert istemci.put(f"{A}/smm/donemler/{did}/ayarlar", json={"gider_720": "-5"}).status_code == 422
    assert "finansman / gider tutarı değişti" in istemci.get(f"{A}/gunluk").text


def test_kilit_ve_fis_excel(istemci):  # noqa: F811
    did = _ekim(istemci)
    r = istemci.put(f"{A}/smm/donemler/{did}/kilit", json={"kilitli": True})
    assert r.status_code == 200 and r.json()["kilitli"] is True and r.json()["kilitleyen"]
    # kilitliyken değişiklik yok
    r = istemci.patch(f"{A}/smm/donemler/{did}/stok/HM-1", json={"neden": "deneme", "sayim_miktar": "1"})
    assert r.status_code == 409 and r.json()["kod"] == "donem_kilitli"
    assert istemci.put(f"{A}/smm/donemler/{did}/dagitim", json={"havuzlar": {"50_uretim": "1"}}).status_code == 409
    assert istemci.put(f"{A}/smm/donemler/{did}/ayarlar", json={"finansman": "1"}).status_code == 409
    assert istemci.delete(f"{A}/smm/donemler/{did}").status_code == 409
    assert istemci.get(f"{A}/smm/donemler/{did}/ozet").status_code == 200   # okuma serbest
    # fiş Excel'i
    r = istemci.get(f"{A}/smm/donemler/{did}/fis.xlsx")
    assert r.status_code == 200 and "spreadsheetml" in r.headers["content-type"] and "SMM" in r.headers["content-disposition"]
    wb = load_workbook(BytesIO(r.content))
    assert wb.sheetnames == ["SMM Fişi", "SMM Tablosu"]
    ws = wb["SMM Fişi"]
    assert ws["A2"].value == "Hesap Kodu" and ws.cell(ws.max_row, 3).value == "Toplam"
    assert ws.cell(ws.max_row, 4).value == ws.cell(ws.max_row, 5).value   # borç = alacak
    # kilit açılır
    assert istemci.put(f"{A}/smm/donemler/{did}/kilit", json={"kilitli": False}).json()["kilitli"] is False
    assert istemci.patch(f"{A}/smm/donemler/{did}/stok/HM-1", json={"neden": "deneme", "sayim_miktar": "1"}).status_code == 200
