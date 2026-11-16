"""Faz 5 T2: satış geçmişi servisi, dosya okuyucu ve /satis-gecmisi uçları."""
from decimal import Decimal as D_
from io import BytesIO
from openpyxl import Workbook, load_workbook
from backend.depo import modeller as m
from tests.backend.test_api import istemci  # noqa: F401

A = "/api/v1/satis-gecmisi"
BASLIK = "urun_kodu;musteri;tarih;fiyat;para_birimi;adet"


def _urunler(c):
    for kod in ("TST-1", "TST-2"):
        assert c.put(f"/api/v1/urunler/{kod}", json={"ad": f"Test {kod}", "ambalaj_hacmi": "370", "hat": "Niko", "taze_tursu_sinifi": "Turşu/Turşu", "suzme_kg": "0.18"}).status_code == 200


def _govde(**ek):
    return {"urun_kodu": "TST-1", "musteri": "Deneme Ltd", "tarih": "2025-03-01", "fiyat": "12.50", "para_birimi": "TL", "adet": "100", **ek}


def _yukle(c, icerik: bytes, ad: str):
    return c.post(f"{A}/yukle", files={"dosya": (ad, icerik)}, headers={"X-Kullanici": "esma"})


def _xlsx(satirlar, baslik=("Ürün Kodu", "Müşteri", "Tarih", "Fiyat", "Para Birimi", "Adet")) -> bytes:
    wb = Workbook(); ws = wb.active
    ws.append(list(baslik))
    for s in satirlar:
        ws.append(s)
    b = BytesIO(); wb.save(b)
    return b.getvalue()


def test_ekle_listele_suzgec(istemci, oturum):
    c = istemci; _urunler(c)
    r = c.post(A, json=_govde(), headers={"X-Kullanici": "esma"})
    assert r.status_code == 201, r.text
    g = r.json()
    assert (g["urun_kodu"], g["urun_ad"], g["fiyat"], g["adet"], g["olusturan"]) == ("TST-1", "Test TST-1", "12.50", "100", "esma")
    c.post(A, json=_govde(urun_kodu="TST-2", musteri="Başka AŞ", tarih="2024-01-10", para_birimi="EUR"))
    assert c.get(A).json()["toplam"] == 2
    assert [k["urun_kodu"] for k in c.get(A).json()["kayitlar"]] == ["TST-1", "TST-2"]   # tarih azalan
    assert c.get(A, params={"urun_kodu": "tst-2"}).json()["toplam"] == 1
    assert c.get(A, params={"musteri": "deneme"}).json()["toplam"] == 1
    assert c.get(A, params={"bas": "2025-01-01"}).json()["toplam"] == 1
    assert c.get(A, params={"son": "2024-12-31"}).json()["kayitlar"][0]["para_birimi"] == "EUR"
    assert c.get(A, params={"boyut": 1, "sayfa": 2}).json()["kayitlar"][0]["urun_kodu"] == "TST-2"
    kayit = oturum.query(m.DegisiklikKaydi).filter_by(tablo="satis_gecmisi", islem="ekle").first()
    assert kayit.kullanici == "esma" and kayit.yeni["urun_kodu"] == "TST-1"


def test_ekle_dogrulama(istemci):
    c = istemci; _urunler(c)
    assert c.post(A, json=_govde(urun_kodu="YOK")).status_code == 404
    assert c.post(A, json=_govde(fiyat="-1")).status_code == 422
    assert c.post(A, json=_govde(adet="0")).status_code == 422
    assert c.post(A, json=_govde(para_birimi="JPY")).status_code == 422
    assert c.post(A, json=_govde(tarih="01.03.2025")).status_code == 422
    assert c.get(A).json()["toplam"] == 0


def test_yukle_csv_noktali_virgul_ve_virgul(istemci):
    c = istemci; _urunler(c)
    r = _yukle(c, f"{BASLIK}\nTST-1;Deneme Ltd;31.12.2024;1.234,56;TL;10\nTST-2;Başka AŞ;2025-02-01;7,5;usd;2000\n".encode("utf-8"), "a.csv")
    assert r.status_code == 200, r.text
    assert r.json() == {"eklenen": 2, "hatalar": [], "atlanan_kayitli": 0}   # 16.11.2026: atlanan_kayitli (ikilenme koruması) eklendi
    k = {x["urun_kodu"]: x for x in c.get(A).json()["kayitlar"]}
    assert (k["TST-1"]["fiyat"], k["TST-1"]["tarih"], k["TST-1"]["adet"]) == ("1234.56", "2024-12-31", "10")
    assert (k["TST-2"]["para_birimi"], k["TST-2"]["adet"]) == ("USD", "2000")
    r = _yukle(c, "Ürün Kodu,MÜŞTERİ,Tarih,Fiyat,Para Birimi,Adet\r\nTST-1,Üçüncü,2025-05-05,1234.56,CHF,3\r\n".encode("utf-8-sig"), "b.csv")
    assert r.status_code == 200 and r.json()["eklenen"] == 1
    assert c.get(A, params={"musteri": "Üçüncü"}).json()["kayitlar"][0]["fiyat"] == "1234.56"


def test_yukle_csv_cp1254(istemci):
    c = istemci; _urunler(c)
    r = _yukle(c, f"{BASLIK}\nTST-1;Şahin Gıda;2025-01-02;5;TL;1\n".encode("cp1254"), "t.csv")
    assert r.status_code == 200, r.text
    assert c.get(A).json()["kayitlar"][0]["musteri"] == "Şahin Gıda"


def test_yukle_xlsx(istemci):
    from datetime import datetime
    c = istemci; _urunler(c)
    r = _yukle(c, _xlsx([["TST-1", "Deneme Ltd", datetime(2025, 4, 3), 12.5, "TL", 100], ["TST-2", "Başka AŞ", "03.04.2025", "1.500,25", "EUR", 4], [None] * 6]), "a.xlsx")
    assert r.status_code == 200, r.text
    assert r.json()["eklenen"] == 2
    k = {x["urun_kodu"]: x for x in c.get(A).json()["kayitlar"]}
    assert (k["TST-1"]["tarih"], k["TST-1"]["fiyat"]) == ("2025-04-03", "12.5") and k["TST-2"]["fiyat"] == "1500.25"


def test_hatali_satir_hicbiri_yazilmaz(istemci, oturum):
    c = istemci; _urunler(c)
    icerik = (f"{BASLIK}\nTST-1;Deneme Ltd;2025-01-01;10;TL;5\n"      # satır 2 geçerli
              "YOK-9;Deneme Ltd;2025-01-01;10;TL;5\n"                 # satır 3 bilinmeyen ürün
              "TST-1;Deneme Ltd;2025-01-01;-4;TL;5\n"                 # satır 4 negatif fiyat
              "TST-2;Deneme Ltd;31/13/2025;10;TL;5\n").encode("utf-8")  # satır 5 kötü tarih
    r = _yukle(c, icerik, "h.csv")
    assert r.status_code == 422
    govde = r.json()
    assert govde["hata"] == "dogrulama"
    hatalar = {h["satir_no"]: h["mesaj"] for h in govde["alanlar"]["hatalar"]}
    assert sorted(hatalar) == [3, 4, 5]
    assert "ürün" in hatalar[3] and "fiyat" in hatalar[4] and "tarih" in hatalar[5]
    assert oturum.query(m.SatisGecmisi).count() == 0
    assert c.get(A).json()["toplam"] == 0


def test_eksik_baslik_ve_bozuk_dosya(istemci):
    c = istemci; _urunler(c)
    r = _yukle(c, b"urun_kodu;musteri\nTST-1;X\n", "e.csv")
    assert r.status_code == 422 and "adet" in r.json()["alanlar"]["eksik_basliklar"]
    assert _yukle(c, b"PK bozuk", "x.xlsx").status_code == 422


def test_sablon_indirilir_ve_geri_yuklenir(istemci):
    c = istemci
    r = c.get(f"{A}/sablon.xlsx")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/vnd.openxmlformats")
    ws = load_workbook(BytesIO(r.content)).active
    satirlar = list(ws.iter_rows(values_only=True))
    assert list(satirlar[0]) == ["urun_kodu", "musteri", "tarih", "fiyat", "para_birimi", "adet"] and len(satirlar) == 2
    ornek_kod = satirlar[1][0]
    assert c.put(f"/api/v1/urunler/{ornek_kod}", json={"ad": "Örnek", "ambalaj_hacmi": "370", "hat": "Niko", "taze_tursu_sinifi": "Turşu/Turşu", "suzme_kg": "0.18"}).status_code == 200
    r = _yukle(c, r.content, "sablon.xlsx")
    assert r.status_code == 200 and r.json()["eklenen"] == 1, r.text
    assert c.get(A).json()["kayitlar"][0]["urun_kodu"] == ornek_kod


def test_sil(istemci, oturum):
    c = istemci; _urunler(c)
    kid = c.post(A, json=_govde()).json()["id"]
    assert c.delete(f"{A}/{kid}", headers={"X-Kullanici": "esma"}).status_code == 204
    assert c.get(A).json()["toplam"] == 0
    kayit = oturum.query(m.DegisiklikKaydi).filter_by(tablo="satis_gecmisi", islem="sil", kayit_id=kid).one()
    assert kayit.kullanici == "esma" and kayit.eski["fiyat"] == "12.50"
    assert D_(kayit.eski["adet"]) == 100
    assert c.delete(f"{A}/{kid}").status_code == 404


def test_sayi_kabul_edilen_bicimler(istemci):
    from backend.servisler.satis_okuyucu import _sayi
    for metin, beklenen in [("1234.56", "1234.56"), ("1.234,56", "1234.56"), ("1234,56", "1234.56"), ("2000", "2000"), ("1.234.567", "1234567"),
                            ("0,5", "0.5"), ("12.5", "12.5"), ("1.2345", "1.2345"), (12.5, "12.5"), (2000, "2000")]:
        assert _sayi(metin) == D_(beklenen), metin
    assert _sayi("abc") is None


def test_sayi_belirsiz_bicimler_satir_hatasi(istemci, oturum):
    c = istemci; _urunler(c)
    icerik = (f"{BASLIK}\nTST-1;X;2025-01-01;2.000;TL;1\n"        # satır 2: nokta + 3 hane
              "TST-1;X;2025-01-01;5;TL;1,234.56\n"                  # satır 3: virgül noktadan önce
              "TST-1;X;2025-01-01;1.234,56;TL;2\n").encode("utf-8")  # satır 4 geçerli
    r = _yukle(c, icerik, "b.csv")
    assert r.status_code == 422
    hatalar = {h["satir_no"]: h["mesaj"] for h in r.json()["alanlar"]["hatalar"]}
    assert sorted(hatalar) == [2, 3]
    assert "belirsiz sayı biçimi '2.000'" in hatalar[2] and "belirsiz sayı biçimi '1,234.56'" in hatalar[3]
    assert oturum.query(m.SatisGecmisi).count() == 0


def test_xlsx_sayi_hucresi_belirsiz_degil(istemci):
    c = istemci; _urunler(c)
    from datetime import date
    r = _yukle(c, _xlsx([["TST-1", "X", date(2025, 1, 1), 2.0, "TL", 2000]]), "n.xlsx")
    assert r.status_code == 200, r.text


def test_en_fazla_20000_satir(istemci, oturum):
    c = istemci; _urunler(c)
    satir = "TST-1;X;2025-01-01;1;TL;1\n"
    r = _yukle(c, (BASLIK + "\n" + satir * 20001).encode("utf-8"), "buyuk.csv")
    assert r.status_code == 422 and "20000" in r.json()["mesaj"]
    assert oturum.query(m.SatisGecmisi).count() == 0
    r = _yukle(c, (BASLIK + "\n" + satir * 20000).encode("utf-8"), "sinir.csv")
    assert r.status_code == 200 and r.json()["eklenen"] == 20000


def test_toplu_yukleme_tek_denetim_kaydi(istemci, oturum):
    c = istemci; _urunler(c)
    r = _yukle(c, f"{BASLIK}\nTST-1;X;2025-01-01;1;TL;1\nTST-1;Y;2025-01-02;2;TL;1\nTST-2;Z;2025-01-03;3;TL;1\n".encode("utf-8"), "uc.csv")
    assert r.status_code == 200 and r.json()["eklenen"] == 3
    kayitlar = oturum.query(m.DegisiklikKaydi).filter_by(tablo="satis_gecmisi").all()
    assert len(kayitlar) == 1
    assert (kayitlar[0].islem, kayitlar[0].kullanici, kayitlar[0].yeni) == ("toplu_yukle", "esma", {"eklenen": 3, "atlanan_kayitli": 0, "dosya": "uc.csv"})


def test_cok_noktali_degerler_gruplama_denetimi(istemci, oturum):
    from backend.servisler.satis_okuyucu import BelirsizSayi, _sayi
    assert _sayi("1.234.567") == D_("1234567") and _sayi("1.234.567,5") == D_("1234567.5")
    for kotu in ("1.234.56", "1.2.3", "01.02.2025", "1.2.3,5", "1234.567.890"):
        try:
            _sayi(kotu)
        except BelirsizSayi:
            continue
        raise AssertionError(f"{kotu} reddedilmeliydi")
    c = istemci; _urunler(c)
    satirlar = [BASLIK, "TST-1;X;2025-01-01;1.234.56;TL;1", "TST-1;X;2025-01-01;5;TL;1.2.3", "TST-1;X;2025-01-01;5;TL;01.02.2025"]
    r = _yukle(c, chr(10).join(satirlar).encode("utf-8"), "n.csv")
    assert r.status_code == 422
    assert sorted(h["satir_no"] for h in r.json()["alanlar"]["hatalar"]) == [2, 3, 4]
    assert oturum.query(m.SatisGecmisi).count() == 0
