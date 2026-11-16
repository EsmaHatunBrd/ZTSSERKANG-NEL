"""Önemli malzemeler (80/20): yıllık adetle ağırlıklı malzeme tutarı, pay, kümülatif pay, eşik; adetsiz ürün; ara mamul çift sayılmaz;
Excel çıktısı; gerçek kitap. Şirket verisi test çıktısına yazılmaz (yalnız kod ve sayılar)."""
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal as D_
from io import BytesIO
import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from backend.depo import modeller as m
from backend.depo.veritabani import Base, motor_olustur, oturum_fabrikasi, oturum_ver
from backend.servisler import hesap_servisi as hs, import_servisi as ims, karsilastirma_servisi as ks, satis_servisi
from backend.uygulama import uygulama_olustur
from tests.backend.test_analiz_2 import _satis, _urun
from tests.backend.test_api import _kur, _senaryo, istemci  # noqa: F401  (fixture)

A = "/api/v1"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
ALANLAR = {"sira", "kod", "ad", "tip", "para_birimi", "birim", "yillik_miktar", "yillik_tutar_tl", "pay_yuzde", "kumulatif_yuzde", "esik_icinde",
           "kullanan_urun_sayisi", "birim_fiyat"}
UST = {"senaryo_id", "esik", "tarih", "adet_kaynagi", "toplam_tutar_tl", "adetsiz_urun", "hatali_urun", "satirlar", "esik_icindeki_sayi"}


def _malzeme(c, sid, kod, ad, fiyat, pb="TL"):
    assert c.post(f"{A}/malzemeler", json={"kod": kod, "ad": ad, "tip": "0001-Hammadde", "birim": "KG", "para_birimi": pb, "zs": "S"}).status_code in (200, 201)
    if fiyat is not None:
        assert c.post(f"{A}/malzemeler/{kod}/fiyatlar?senaryo={sid}", json={"onay": True, "fiyat": fiyat, "para_birimi": pb, "gecerlilik_basi": "2026-06-01",
                                                                            "neden": "bütçe"}).status_code == 201


def _kurulum(c, oturum) -> int:
    """Üç fiyatlı malzeme (KAV TL 5,9; ETK USD 0,05; TUZ TL 2) + fiyatsız BOS. P1: KAV + ETK (1000 adet); P2: KAV + TUZ + BOS (100 adet);
    P3: KAV, satışı yok (adetsiz). `_kur`un TEST ürünü de (KAV, satışı yok) adetsizdir."""
    sid = _senaryo(c); _kur(c, sid, oturum)
    _malzeme(c, sid, "ETK", "Etiket", "0.05", "USD")
    _malzeme(c, sid, "TUZ", "Tuz", "2")
    _malzeme(c, sid, "BOS", "Fiyatsız", None)
    kav = {"malzeme_kodu": "KAV", "ad": "Kavanoz", "miktar": "1", "birim": "AD", "fire_override": "0.02"}
    _urun(c, sid, "P1", [kav, {"malzeme_kodu": "ETK", "ad": "Etiket", "miktar": "2", "birim": "AD", "fire_override": "0"}])
    _urun(c, sid, "P2", [kav, {"malzeme_kodu": "TUZ", "ad": "Tuz", "miktar": "0.5", "birim": "KG", "fire_override": "0.1"},
                         {"malzeme_kodu": "BOS", "ad": "Fiyatsız", "miktar": "3", "birim": "KG", "fire_override": "0"}])
    _urun(c, sid, "P3", [kav])
    _satis(oturum, sid, "P1", "100", "TL", "1000")
    _satis(oturum, sid, "P2", "50", "TL", "100")
    return sid


def _beklenen(oturum, sid, adetler: dict[str, int]) -> tuple[dict[str, D_], dict[str, D_]]:
    """Bağımsız yoldan: tek ürün hesabının satırlarından malzeme başına yıllık tutar ve miktar."""
    tutar, miktar = {}, {}
    for kod, adet in adetler.items():
        for r in hs.hesapla(oturum, kod, sid).sonuc.satirlar:
            if r.grup == "malzeme":
                tutar[r.kod] = tutar.get(r.kod, D_(0)) + adet * r.tutar
                miktar[r.kod] = miktar.get(r.kod, D_(0)) + adet * r.brut_miktar
    return tutar, miktar


def _y(x: D_) -> str:
    return str(x.quantize(D_("0.01"), ROUND_HALF_UP))


def test_tutar_pay_kumulatif_esik(istemci, oturum):
    sid = _kurulum(istemci, oturum)
    r = istemci.get(f"{A}/analiz/onemli-malzemeler?senaryo={sid}")
    assert r.status_code == 200, r.text
    d = r.json()
    assert set(d) == UST and all(set(x) == ALANLAR for x in d["satirlar"])
    assert d["senaryo_id"] == sid and D_(d["esik"]) == D_("0.8") and d["adet_kaynagi"] == "satis_gecmisi"
    assert d["adetsiz_urun"] == 2 and d["hatali_urun"] == 0   # P3 ve _kur'un TEST ürünü: satışı yok, hesaba girmez
    tutar, miktar = _beklenen(oturum, sid, {"P1": 1000, "P2": 100})
    k = {x["kod"]: x for x in d["satirlar"]}
    assert set(k) == {"KAV", "ETK", "TUZ", "BOS"}
    for kod in k:
        assert D_(k[kod]["yillik_tutar_tl"]) == tutar[kod] and D_(k[kod]["yillik_miktar"]) == miktar[kod]
    # elle doğrulama: KAV TL "S" -> fiyat x (1 + enflasyon 0,25) x brüt (1 / 0,98); ETK USD -> 0,05 x kur 50 x 2
    assert D_(k["KAV"]["yillik_tutar_tl"]) == D_("5.9") * D_("1.25") * (D_(1) / D_("0.98")) * 1100
    assert D_(k["ETK"]["yillik_tutar_tl"]) == D_("0.05") * 50 * 2 * 1000
    assert D_(k["ETK"]["yillik_miktar"]) == 2000 and D_(k["BOS"]["yillik_miktar"]) == 300
    toplam = sum(tutar.values())
    assert D_(d["toplam_tutar_tl"]) == toplam
    # toplam = Σ (adet x ürünün malzeme toplamı): yeni hesap kuralı yok
    assert toplam == sum(a * hs.hesapla(oturum, kod, sid).sonuc.malzeme_toplami for kod, a in (("P1", 1000), ("P2", 100)))
    # sıra: tutar azalan; fiyatsız sonda, payı 0
    assert [x["kod"] for x in d["satirlar"]] == ["KAV", "ETK", "TUZ", "BOS"] and [x["sira"] for x in d["satirlar"]] == [1, 2, 3, 4]
    assert D_(k["BOS"]["yillik_tutar_tl"]) == 0 and k["BOS"]["pay_yuzde"] == "0.00" and k["BOS"]["esik_icinde"] is False
    kum = D_(0)
    for x in d["satirlar"]:
        kum += tutar[x["kod"]]
        assert x["pay_yuzde"] == _y(tutar[x["kod"]] / toplam * 100) and x["kumulatif_yuzde"] == _y(kum / toplam * 100)
    assert d["satirlar"][-1]["kumulatif_yuzde"] == "100.00"
    # KAV ~%61, ETK ~%38: %80 eşiğinde KAV (altında) + ETK (eşiği aşan ilk satır)
    assert D_(k["KAV"]["kumulatif_yuzde"]) < 80 < D_(k["ETK"]["kumulatif_yuzde"])
    assert [x["kod"] for x in d["satirlar"] if x["esik_icinde"]] == ["KAV", "ETK"] and d["esik_icindeki_sayi"] == 2
    # kart bilgileri
    assert (k["KAV"]["kullanan_urun_sayisi"], k["ETK"]["kullanan_urun_sayisi"], k["TUZ"]["kullanan_urun_sayisi"]) == (2, 1, 1)
    assert D_(k["KAV"]["birim_fiyat"]) == D_("5.9") and k["KAV"]["para_birimi"] == "TL" and k["ETK"]["para_birimi"] == "USD"
    assert k["TUZ"]["birim"] == "KG" and k["TUZ"]["tip"] == "0001-Hammadde" and k["TUZ"]["ad"] == "Tuz"


def test_esik_degisimi_ve_dogrulama(istemci, oturum):
    sid = _kurulum(istemci, oturum)
    al = lambda e: istemci.get(f"{A}/analiz/onemli-malzemeler?senaryo={sid}&esik={e}").json()
    assert [x["kod"] for x in al("0.5")["satirlar"] if x["esik_icinde"]] == ["KAV"]            # ilk satır tek başına %50'yi aşıyor
    assert [x["kod"] for x in al("0.995")["satirlar"] if x["esik_icinde"]] == ["KAV", "ETK", "TUZ"]
    d = al("1")
    assert [x["kod"] for x in d["satirlar"] if x["esik_icinde"]] == ["KAV", "ETK", "TUZ"] and d["esik_icindeki_sayi"] == 3   # fiyatsız hiç girmez
    for e in ("0", "1.2", "-0.1"):
        assert istemci.get(f"{A}/analiz/onemli-malzemeler?senaryo={sid}&esik={e}").status_code == 422
    assert istemci.get(f"{A}/analiz/onemli-malzemeler?senaryo=999999").status_code == 404


def test_adetsiz_urunler_ve_bos_sonuc(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    _urun(istemci, sid, "P1", [{"malzeme_kodu": "KAV", "ad": "Kavanoz", "miktar": "1", "birim": "AD"}])
    d = istemci.get(f"{A}/analiz/onemli-malzemeler?senaryo={sid}").json()
    assert d["satirlar"] == [] and d["adetsiz_urun"] == 2 and D_(d["toplam_tutar_tl"]) == 0 and d["esik_icindeki_sayi"] == 0


def test_ara_mamul_cift_sayilmaz(istemci, oturum):
    """Başlık satırı (alt satırı olan, fiyatsız yarı mamul) listeye girmez; tutar ve miktar yalnız alt (yaprak) satırlardan gelir."""
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    _malzeme(istemci, sid, "TUZ", "Tuz", "2")
    _urun(istemci, sid, "P1", [{"malzeme_kodu": "YM1", "ad": "Salamura", "miktar": "1", "birim": "KG", "seviye": 1, "dugum_tipi": "ara_mamul"},
                               {"malzeme_kodu": "TUZ", "ad": "Tuz", "miktar": "0.5", "birim": "KG", "seviye": 2, "fire_override": "0"},
                               {"malzeme_kodu": "KAV", "ad": "Kavanoz", "miktar": "1", "birim": "AD", "seviye": 1, "fire_override": "0"}])
    _satis(oturum, sid, "P1", "100", "TL", "10")
    d = istemci.get(f"{A}/analiz/onemli-malzemeler?senaryo={sid}").json()
    k = {x["kod"]: x for x in d["satirlar"]}
    assert set(k) == {"KAV", "TUZ"}   # YM1 yok
    c = hs.hesapla(oturum, "P1", sid).sonuc
    assert D_(d["toplam_tutar_tl"]) == 10 * c.malzeme_toplami == D_(k["KAV"]["yillik_tutar_tl"]) + D_(k["TUZ"]["yillik_tutar_tl"])
    assert D_(k["TUZ"]["yillik_miktar"]) == 5 and D_(k["KAV"]["yillik_miktar"]) == 10


def test_excel(istemci, oturum):
    sid = _kurulum(istemci, oturum)
    d = istemci.get(f"{A}/analiz/onemli-malzemeler?senaryo={sid}&esik=0.9").json()
    r = istemci.get(f"{A}/disa-aktar/onemli-malzemeler?senaryo={sid}&esik=0.9")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith(XLSX) and r.headers["content-disposition"] == 'attachment; filename="onemli-malzemeler.xlsx"'
    wb = load_workbook(BytesIO(r.content))
    assert wb.sheetnames == ["Önemli Malzemeler", "Özet"]
    ws = wb.worksheets[0]
    assert ws["A2"].value.startswith("Eşik: %90 · ")
    basliklar = [c.value for c in ws[4]]
    assert basliklar == ["Sıra", "Kod", "Malzeme", "Tip", "Birim", "Para Birimi", "Birim Fiyat", "Yıllık Miktar", "Yıllık Tutar TL", "Pay %",
                         "Kümülatif %", "Eşik İçinde", "Kullanan Ürün"]
    assert ws["A4"].font.bold and ws.freeze_panes == "A5"
    satirlar = [dict(zip(basliklar, row)) for row in ws.iter_rows(min_row=5, values_only=True)]
    assert [x["Kod"] for x in satirlar] == [x["kod"] for x in d["satirlar"]]
    for x, y in zip(satirlar, d["satirlar"]):
        for baslik, alan in (("Yıllık Miktar", "yillik_miktar"), ("Yıllık Tutar TL", "yillik_tutar_tl"), ("Pay %", "pay_yuzde"), ("Kümülatif %", "kumulatif_yuzde")):
            assert isinstance(x[baslik], (int, float)) and abs(D_(str(x[baslik])) - D_(y[alan])) < D_("0.000001")   # sayı tipi
        assert x["Eşik İçinde"] == ("Evet" if y["esik_icinde"] else None) and x["Kullanan Ürün"] == y["kullanan_urun_sayisi"] and x["Sıra"] == y["sira"]
    assert isinstance(satirlar[0]["Birim Fiyat"], (int, float)) and ws["G5"].number_format == "#,##0.0000" and ws["I5"].number_format == "#,##0.00"
    ozet = {row[0]: row[1] for row in wb["Özet"].iter_rows(min_row=4, values_only=True) if row[0]}
    assert ozet["Malzeme sayısı"] == 4 and ozet["Toplam tutarın %90 kadarını oluşturan malzeme"] == d["esik_icindeki_sayi"]
    assert ozet["Yıllık adedi olmayan ürün (hesaba girmedi)"] == 2
    assert abs(D_(str(ozet["Toplam yıllık malzeme tutarı TL"])) - D_(d["toplam_tutar_tl"])) < D_("0.000001")


@pytest.fixture(scope="module")
def ortam(excel_yolu):
    engine = motor_olustur("sqlite://"); Base.metadata.create_all(engine)
    s = oturum_fabrikasi(engine)()
    sid = ims.excel_tam_yukle(s, excel_yolu, "2026-2027", "Bütçe")["senaryo_id"]
    s.commit()
    yield s, sid
    s.close()


def test_gercek_kitap(ortam):
    s, sid = ortam
    app = uygulama_olustur()
    app.dependency_overrides[oturum_ver] = lambda: s
    c = TestClient(app)
    hesaplanan = [(kod, x) for kod, x in hs.toplu_hesapla(s, sid) if not isinstance(x, Exception)]
    assert len(hesaplanan) > 10
    # kitapta satış geçmişi yok: ilk 8 ürüne geçen yıl satışı ekle (yıllık adet kaynağı)
    bas, _ = ks.pencere(s.get(m.Senaryo, sid))
    adetler = {}
    for i, (kod, _x) in enumerate(hesaplanan[:8]):
        adetler[kod] = D_(1000 * (i + 1))
        satis_servisi.ekle(s, kod, "Müşteri A", bas + timedelta(days=30), D_("10"), "TL", adetler[kod])
    s.commit()
    r = c.get(f"{A}/analiz/onemli-malzemeler?senaryo={sid}")
    assert r.status_code == 200, r.text
    d = r.json()
    assert all(set(x) == ALANLAR for x in d["satirlar"]) and len(d["satirlar"]) > 5
    assert d["adetsiz_urun"] == len(hesaplanan) - 8
    assert abs(D_(d["satirlar"][-1]["kumulatif_yuzde"]) - 100) <= D_("0.01")
    tutarlar = [D_(x["yillik_tutar_tl"]) for x in d["satirlar"]]
    assert tutarlar == sorted(tutarlar, reverse=True) and all(t >= 0 for t in tutarlar)
    beklenen = sum(adetler[kod] * x.sonuc.malzeme_toplami for kod, x in hesaplanan[:8])
    assert abs(sum(tutarlar) - beklenen) < D_("0.0001") and abs(D_(d["toplam_tutar_tl"]) - beklenen) < D_("0.0001")
    icinde = [x for x in d["satirlar"] if x["esik_icinde"]]
    assert len(icinde) == d["esik_icindeki_sayi"] and 0 < len(icinde) < len(d["satirlar"])
    assert d["satirlar"][:len(icinde)] == icinde                                   # eşik içindekiler başta, kesintisiz
    assert D_(icinde[-1]["kumulatif_yuzde"]) >= 80 and all(D_(x["kumulatif_yuzde"]) < 80 for x in icinde[:-1])
    kumulatifler = [D_(x["kumulatif_yuzde"]) for x in d["satirlar"]]
    assert kumulatifler == sorted(kumulatifler)
    assert c.get(f"{A}/disa-aktar/onemli-malzemeler?senaryo={sid}").status_code == 200
