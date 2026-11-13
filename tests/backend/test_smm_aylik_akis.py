"""SMM aylık akış, uçtan uca: Excel'siz yeni dönem (devirle) → 7 veri kaynağı → kontrol listesi tamam → kalem ve mizan satırı elle
düzeltme → özet / SMM tablosu değişir → fiş Excel'i → kilit → kilitliyken yazma 409 → kilit açılır.

Çalışma kitapları bellekte üretilen uydurma küçük raporlardır (gerçek dosya okunmaz)."""
from decimal import Decimal as D_
from io import BytesIO
from openpyxl import load_workbook
from tests.backend.test_api import istemci  # noqa: F401  (fixture)
from tests.backend.test_smm_veri import ALIM_BASLIK, _ekim, _rapor, _yukle

A = "/api/v1"
H = {"X-Kullanici": "esma"}
MIZAN_BASLIK = ["Hesap Kodu", "Hesap Adı", "B", "A", "BB", "BA", "Bakiye"]
SIRA = ("alim", "iade", "uretim", "sayim", "sahit", "gider_mizan", "stok_mizan")


def _dosyalar() -> dict[str, bytes]:
    return {
        # HM-1: 50 KG 700 TL alım, 5 KG satış; yeni kalem YENI-1
        "alim": _rapor(ALIM_BASLIK, [
            [None, "HM-1", "Biber", 9, 9, "KG", 50, None, None, None, 700, 0] + [None] * 7 + ["Alış"],
            [None, "HM-1", "Biber", 9, 9, "KG", 0, None, None, None, 0, 5] + [None] * 7 + ["Satış"],
            [None, "YENI-1", "Yeni malzeme", 9, 9, "AD", 10, None, None, None, 30, 0] + [None] * 7 + ["Alış"]]),
        # HM-1: 4 KG 56 TL iade
        "iade": _rapor(["Malzeme (Sınıf) Kodu", "Açıklama", "", "", "Birim", "", "", "Miktar", "Tutar"],
                       [["HM-1", "Biber", None, None, "KG", None, None, 4, 56]]),
        "uretim": _rapor(["MalzemeKodu", "Ad"] + [""] * 12 + ["TOPLAM"], [["01-1", "Biber salamura"] + [0] * 12 + [200]]),
        "sayim": _rapor(["StokKartıKodu", "Ad", "Miktar"], [["HM-1", "Biber", 30], ["01-1", "Biber salamura", 20]], "DSS"),
        "sahit": _rapor(["StokKodu", "Ad"] + [""] * 7 + ["Miktar"], [["01-1", "Biber salamura"] + [None] * 7 + [1]]),
        "gider_mizan": _rapor(MIZAN_BASLIK, [["720", "İşçilik", 0, 0, 0, 0, 2000], ["730", "GÜG", 0, 0, 0, 0, 3000]]),
        "stok_mizan": _rapor(MIZAN_BASLIK, [["150.01.001", "Hammadde", 0, 0, 0, 0, 400], ["151.04.002", "Yarı mamul", 0, 0, 0, 0, 150]]),
    }


def _ozet(c, did):
    r = c.get(f"{A}/smm/donemler/{did}/ozet")
    assert r.status_code == 200, r.text
    return r.json()


def _blok(o, hesap):
    return next(b for b in o["tablo"] if b["hesap"] == hesap)


def _satir(blok, bas):
    return D_(next(x for x in blok["satirlar"] if x["ad"].startswith(bas))["tutar"])


def test_aylik_akis_uctan_uca(istemci):  # noqa: F811
    # 1) Excel'siz yeni dönem: Eylül (fikstür) üstüne Ekim, dönem başı stok devirle
    did = _ekim(istemci)
    v = istemci.get(f"{A}/smm/donemler/{did}/veri").json()
    assert v["donem"]["kaynak_dosya"] is None and v["donem"]["devir_donem_id"] is not None and v["donem"]["kilitli"] is False
    assert v["donem_basi"]["kaynak"] == "devir" and v["donem_basi"]["hazir"] is True and D_(v["donem_basi"]["tutar"]) == 480
    assert len(v["eksik"]) == 4 and all(not k["yuklendi"] for k in v["kaynaklar"])

    # 2) 7 kaynak sırayla; her yüklemeden sonra o kaynak tamam, eksik listesi kısalır
    dosyalar = _dosyalar()
    assert tuple(k["kaynak"] for k in v["kaynaklar"]) == SIRA
    for kaynak in SIRA:
        r = _yukle(istemci, did, kaynak, dosyalar[kaynak])
        assert r.status_code == 200, f"{kaynak}: {r.text}"
        k = next(x for x in r.json()["kaynaklar"] if x["kaynak"] == kaynak)
        assert k["yuklendi"] is True and k["dolu"] >= 1 and k["son"]["dosya"] == f"{kaynak}.xlsx" and k["elle"] == 0, kaynak

    # 3) kontrol listesi: hepsi tamam
    v = istemci.get(f"{A}/smm/donemler/{did}/veri").json()
    assert v["eksik"] == [] and all(k["yuklendi"] for k in v["kaynaklar"])
    assert D_(v["ayarlar"]["gider_720"]) == 2000 and D_(v["ayarlar"]["gider_730"]) == 3000
    hm = next(x for x in istemci.get(f"{A}/smm/donemler/{did}/stok").json()["kayitlar"] if x["kod"] == "HM-1")
    assert (D_(hm["dbs_miktar"]), D_(hm["alim_miktar"]), D_(hm["alim_tutar"]), D_(hm["iade_miktar"]), D_(hm["iade_tutar"]),
            D_(hm["sayim_miktar"])) == (40, 50, 700, 4, 56, 30)

    # 3b) alım raporuyla ilk kez gelen YENI-1'in türü yok: SMM tablosuna girmez, kontrol listesi bunu söyler; tür elle girilince girer
    assert v["grupsuz"]["ornek"] == ["YENI-1"] and v["grupsuz"]["kalem"] == 1 and D_(v["grupsuz"]["alim_tutar"]) == 30
    assert _satir(_blok(_ozet(istemci, did), "150"), "Dönem içi alım") == 700
    r = istemci.patch(f"{A}/smm/donemler/{did}/stok/YENI-1", json={"tur": "0008-Ambalaj Malzeme", "neden": "kart eksikti"}, headers=H)
    assert r.status_code == 200, r.text
    assert istemci.get(f"{A}/smm/donemler/{did}/veri").json()["grupsuz"]["kalem"] == 0

    # 4) özet: 150 bloğu ve üretim giderleri yüklenen verilerle
    o1 = _ozet(istemci, did)
    b150 = _blok(o1, "150")
    assert _satir(b150, "Dönem başı") == 480 and _satir(b150, "Dönem içi alım") == 730 and _satir(b150, "Alım iadesi") == 56
    assert _satir(_blok(o1, "72x"), "720") == 2000 and _satir(_blok(o1, "72x"), "730") == 3000
    assert D_(o1["uretim_maliyeti"]) == D_(o1["ilk_madde"]) + 5000
    kiyas = {x["hesap"]: D_(x["mizan"]) for x in o1["mizan_kiyas"]}
    assert kiyas["150"] == 400 and kiyas["151"] == 150
    assert D_(o1["fis_borc"]) == D_(o1["fis_alacak"])

    # 5) bir kalem elle: HM-1 sayımı 30 → 20; dönem sonu stok düşer, 710 ve SMM o kadar artar
    r = istemci.patch(f"{A}/smm/donemler/{did}/stok/HM-1", json={"sayim_miktar": "20", "neden": "sayım tutanağı"}, headers=H)
    assert r.status_code == 200 and r.json()["degisti"] == ["sayim_miktar"]
    o2 = _ozet(istemci, did)
    dusus = _satir(_blok(o1, "150"), "Dönem sonu stok") - _satir(_blok(o2, "150"), "Dönem sonu stok")
    assert dusus > 0
    assert D_(o2["ilk_madde"]) == D_(o1["ilk_madde"]) + dusus and D_(o2["smm"]) == D_(o1["smm"]) + dusus

    # 6) bir mizan satırı elle: 720 2000 → 2750; SMM tablosu ve fiş 750 artar; stok mizanı satırı kıyasa yansır
    r = istemci.patch(f"{A}/smm/donemler/{did}/mizan/gider/720", json={"bakiye": "2750", "neden": "mizan kesinleşti"}, headers=H)
    assert r.status_code == 200 and r.json()["degisti"] == ["bakiye"]
    r = istemci.patch(f"{A}/smm/donemler/{did}/mizan/stok/150.01.001", json={"bakiye": "410", "neden": "mizan kesinleşti"}, headers=H)
    assert r.status_code == 200, r.text
    o3 = _ozet(istemci, did)
    assert _satir(_blok(o3, "72x"), "720") == 2750
    assert D_(o3["uretim_maliyeti"]) == D_(o2["uretim_maliyeti"]) + 750 and D_(o3["smm"]) == D_(o2["smm"]) + 750
    assert {x["hesap"]: D_(x["mizan"]) for x in o3["mizan_kiyas"]}["150"] == 410
    assert D_(o3["fis_borc"]) == D_(o3["fis_alacak"])
    yansitma = next(f for f in o3["fis"] if f["hesap"] == "721")
    assert D_(yansitma["alacak"]) == 2750
    v = istemci.get(f"{A}/smm/donemler/{did}/veri").json()
    k = {x["kaynak"]: x for x in v["kaynaklar"]}
    assert k["gider_mizan"]["elle"] == 1 and k["stok_mizan"]["elle"] == 1 and "yükleme bunları siler" in k["gider_mizan"]["elle_uyari"]
    assert v["eksik"] == []
    elle = istemci.get(f"{A}/smm/donemler/{did}/stok/elle").json()["kayitlar"]
    assert elle["HM-1"]["alanlar"] == ["sayim_miktar"]

    # 7) fiş Excel'i: özetteki tutarlarla, borç = alacak
    r = istemci.get(f"{A}/smm/donemler/{did}/fis.xlsx")
    assert r.status_code == 200 and "spreadsheetml" in r.headers["content-type"]
    wb = load_workbook(BytesIO(r.content))
    assert wb.sheetnames == ["SMM Fişi", "SMM Tablosu"]
    ws = wb["SMM Fişi"]
    assert "kilitli değil" in ws["A1"].value
    son = ws.max_row
    assert ws.cell(son, 3).value == "Toplam" and ws.cell(son, 4).value == ws.cell(son, 5).value
    assert abs(D_(str(ws.cell(son, 4).value)) - D_(o3["fis_borc"])) < D_("0.01")
    satirlar = [[c.value for c in row] for row in ws.iter_rows(min_row=3, max_row=son - 1)]
    assert any(s[0] == "721" and s[4] == 2750 for s in satirlar)

    # 8) dönem kilitlenir; yazma uçlarının hepsi 409, okuma serbest
    r = istemci.put(f"{A}/smm/donemler/{did}/kilit", json={"kilitli": True}, headers=H)
    assert r.status_code == 200 and r.json()["kilitli"] is True and r.json()["kilitleyen"] == "esma"
    yazmalar = [
        _yukle(istemci, did, "alim", dosyalar["alim"]),
        _yukle(istemci, did, "gider_mizan", dosyalar["gider_mizan"]),
        istemci.patch(f"{A}/smm/donemler/{did}/stok/HM-1", json={"sayim_miktar": "1", "neden": "x"}, headers=H),
        istemci.post(f"{A}/smm/donemler/{did}/stok", json={"kod": "K-1", "neden": "x"}, headers=H),
        istemci.post(f"{A}/smm/donemler/{did}/mizan/gider", json={"hesap": "731", "bakiye": "1", "neden": "x"}, headers=H),
        istemci.patch(f"{A}/smm/donemler/{did}/mizan/gider/720", json={"bakiye": "1", "neden": "x"}, headers=H),
        istemci.delete(f"{A}/smm/donemler/{did}/mizan/stok/150.01.001", params={"neden": "x"}, headers=H),
        istemci.put(f"{A}/smm/donemler/{did}/ayarlar", json={"finansman": "1"}),
        istemci.put(f"{A}/smm/donemler/{did}/dagitim", json={"havuzlar": {"50_uretim": "1"}}),
        istemci.delete(f"{A}/smm/donemler/{did}"),
    ]
    assert [x.status_code for x in yazmalar] == [409] * len(yazmalar)
    assert all(x.json()["kod"] == "donem_kilitli" for x in yazmalar)
    o4 = _ozet(istemci, did)
    assert o4["smm"] == o3["smm"] and o4["donem"]["kilitli"] is True
    ws = load_workbook(BytesIO(istemci.get(f"{A}/smm/donemler/{did}/fis.xlsx").content))["SMM Fişi"]
    assert "kilitli değil" not in ws["A1"].value

    # 9) kilit açılır, yazma yeniden mümkün
    r = istemci.put(f"{A}/smm/donemler/{did}/kilit", json={"kilitli": False}, headers=H)
    assert r.status_code == 200 and r.json()["kilitli"] is False and r.json()["kilitleyen"] is None
    assert istemci.patch(f"{A}/smm/donemler/{did}/mizan/gider/720", json={"bakiye": "2800", "neden": "son düzeltme"}, headers=H).status_code == 200
    assert D_(_ozet(istemci, did)["smm"]) == D_(o3["smm"]) + 50
