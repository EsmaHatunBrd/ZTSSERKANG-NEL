"""Toplu Excel çıktısı: tüm ürünlerin maliyet kartları tek dosyada (Özet + ürün başına sayfa). Gerçek kitapla uçtan uca; sayfa adı kuralı.
Şirket verisi test çıktısına yazılmaz (yalnız kod ve sayılar)."""
import re
from datetime import date
from decimal import Decimal as D_
from io import BytesIO
import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from backend.api.disa_aktar import BIRIM_MALIYET_ETIKETI, sayfa_adi
from backend.depo.veritabani import Base, motor_olustur, oturum_fabrikasi, oturum_ver
from backend.servisler import hesap_servisi as hs, import_servisi as ims, recete_servisi as rs
from backend.uygulama import uygulama_olustur

A = "/api/v1"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
OZET_BASLIKLARI = ["Kod", "Ürün", "Hat", "Ambalaj", "Malzeme toplamı", "Üretim gideri", "Faaliyet gideri", "Finansman", "Birim maliyet TL", "Satış TL",
                   "Satış USD", "Satış EUR", "Uyarı sayısı", "Sayfa", "Durum"]
RECETE_BASLIKLARI = ["Satır", "Kod", "Cinsi", "Miktar", "Fire %", "Brüt", "Birim", "Birim fiyat", "Döviz", "Tutar (firesiz)", "Tutar (fireli)"]
HATALI_KOD = "HESAPSIZ-1"   # üretim hedefi olmayan senaryo üyesi: hesaplanamaz


def _yakin(a, b):
    assert a is not None and abs(D_(str(a)) - D_(str(b))) < D_("0.0000001"), (a, b)


def test_sayfa_adi_kurallari():
    k = {"özet"}
    assert sayfa_adi("150.01.0001", k) == "150.01.0001"
    assert sayfa_adi("A/B:C*D?E[F]G\\H", k) == "A-B-C-D-E-F-G-H"
    assert sayfa_adi("150.01.0001", k) == "150.01.0001 (2)" and sayfa_adi("150.01.0001", k) == "150.01.0001 (3)"
    assert sayfa_adi("ÖZET", k) == "ÖZET (2)"                      # "Özet" sayfasıyla çakışmaz (büyük/küçük harf ayırmadan)
    uzun = sayfa_adi("X" * 40, k)
    assert uzun == "X" * 31 and sayfa_adi("X" * 40, k) == "X" * 27 + " (2)"
    assert sayfa_adi("'KOD'", k) == "KOD" and sayfa_adi("", k) == "Ürün"
    assert all(len(x) <= 31 for x in k)


@pytest.fixture(scope="module")
def ortam(excel_yolu):
    engine = motor_olustur("sqlite://"); Base.metadata.create_all(engine)
    s = oturum_fabrikasi(engine)()
    sid = ims.excel_tam_yukle(s, excel_yolu, "2026-2027", "Bütçe")["senaryo_id"]
    s.commit()
    app = uygulama_olustur()
    app.dependency_overrides[oturum_ver] = lambda: s
    c = TestClient(app)
    # hesaplanamayan ürün: reçetesi var (senaryo üyesi) ama üretim hedefi yok
    u = hs.urun_kaydet(s, HATALI_KOD, "Hesapsız Ürün", D_("370"), "Niko", "Turşu/Turşu", D_("0.18"), kullanici="test")
    rs.yeni_versiyon(s, u.id, sid, [{"malzeme_kodu": "YOK-1", "ad": "Deneme", "miktar": "1", "birim": "AD"}], "elle", "test")
    s.commit()
    yield s, sid, c
    s.close()


@pytest.fixture(scope="module")
def kitap(ortam):
    s, sid, c = ortam
    r = c.get(f"{A}/disa-aktar/maliyet-kartlari?senaryo={sid}")
    assert r.status_code == 200, r.text
    return r, load_workbook(BytesIO(r.content))


def _ozet(wb) -> dict[str, dict]:
    return {row[0]: dict(zip(OZET_BASLIKLARI, row)) for row in wb["Özet"].iter_rows(min_row=5, max_col=len(OZET_BASLIKLARI), values_only=True) if row[0]}


def test_yanit_ve_sayfa_sayisi(ortam, kitap):
    s, sid, _c = ortam
    r, wb = kitap
    assert r.headers["content-type"].startswith(XLSX)
    assert re.fullmatch(rf'attachment; filename="maliyet-kartlari-2026-2027-{date.today():%m-%d-%Y}\.xlsx"', r.headers["content-disposition"])
    hesaplar = hs.toplu_hesapla(s, sid)
    hesaplanan = [kod for kod, x in hesaplar if not isinstance(x, Exception)]
    assert len(hesaplanan) > 10 and len(hesaplar) > len(hesaplanan)
    assert wb.sheetnames[0] == "Özet" and len(wb.sheetnames) == len(hesaplanan) + 1   # hesaplanan ürün + Özet
    assert all(len(ad) <= 31 and not re.search(r"[\[\]:*?/\\]", ad) for ad in wb.sheetnames) and len({ad.casefold() for ad in wb.sheetnames}) == len(wb.sheetnames)
    oz = wb["Özet"]
    assert [c.value for c in oz[4]][:len(OZET_BASLIKLARI)] == OZET_BASLIKLARI and oz["A4"].font.bold and oz.freeze_panes == "A5"
    assert oz["A2"].value == f"Değerler {date.today():%d.%m.%Y} itibarıyla uygulamadan alınmıştır (formül yoktur)."
    assert oz.column_dimensions["B"].width == 46
    ozet = _ozet(wb)
    assert list(ozet) == [kod for kod, _x in hesaplar]   # her ürün bir satır, hesap sırasıyla
    # köprü: Sayfa sütunu ürünün sayfasına gider
    satir = 5 + [kod for kod, _x in hesaplar].index(hesaplanan[0])
    hucre = oz.cell(row=satir, column=14)
    assert hucre.value in wb.sheetnames and hucre.hyperlink is not None and hucre.hyperlink.location == f"'{hucre.value}'!A1"


def test_hesaplanamayan_urun_yalniz_ozette(kitap):
    _r, wb = kitap
    x = _ozet(wb)[HATALI_KOD]
    assert x["Durum"].startswith("hesaplanamadı: ") and "üretim bilgisi yok" in x["Durum"]
    assert x["Sayfa"] is None and x["Birim maliyet TL"] is None and x["Malzeme toplamı"] is None
    assert not any(ad.startswith("HESAPSIZ") for ad in wb.sheetnames)   # ayrı sayfa açılmaz


def test_urun_sayfasi_hesapla_ucuyla_ayni(ortam, kitap):
    s, sid, c = ortam
    _r, wb = kitap
    ozet = _ozet(wb)
    kod = next(k for k, x in ozet.items() if x["Sayfa"] is not None)
    h = c.post(f"{A}/urunler/{kod}/hesapla", json={"senaryo_id": sid})
    assert h.status_code == 200, h.text
    h = h.json()
    ws = wb[ozet[kod]["Sayfa"]]
    # başlık bloğu, dondurulmuş reçete başlığı, sütun genişliği
    assert ws["A1"].font.bold and ws["A2"].value.startswith(f"Kod: {kod} · Çalışma: 2026-2027 — ") and f"Hesap tarihi: {date.today():%d.%m.%Y}" in ws["A2"].value
    assert ws["A3"].value.startswith("Değerler ") and ws["K1"].hyperlink.location == "'Özet'!A1"
    assert [x.value for x in ws[4]] == RECETE_BASLIKLARI and all(x.font.bold for x in ws[4]) and ws.freeze_panes == "A5"
    assert ws.column_dimensions["C"].width == 46
    satirlar = list(ws.iter_rows(min_row=1, max_col=11))
    etiketli = {r[2].value: r for r in satirlar if isinstance(r[2].value, str)}
    basliklar = [r[0].value for r in satirlar if r[0].value in ("Gider kalemleri", "Toplamlar", "Satış fiyatı ve teklif fiyatları")]
    assert basliklar == ["Gider kalemleri", "Toplamlar", "Satış fiyatı ve teklif fiyatları"]
    # birim maliyet hücresi = hesapla ucunun sonucu, sayı tipinde
    hucre = etiketli[BIRIM_MALIYET_ETIKETI][10]
    assert isinstance(hucre.value, float) and hucre.data_type == "n" and hucre.number_format == "#,##0.00"
    _yakin(hucre.value, h["toplamlar"]["maliyet_tl"])
    _yakin(etiketli[BIRIM_MALIYET_ETIKETI][9].value, h["toplamlar_firesiz"]["maliyet_tl"])
    _yakin(etiketli["Hammadde-yardımcı malzeme toplamı"][10].value, h["toplamlar"]["malzeme"])
    _yakin(etiketli["Gider toplamı"][10].value, h["toplamlar"]["uretim_gideri"])
    _yakin(etiketli["Toplam birim maliyet"][10].value, D_(h["toplamlar"]["malzeme"]) + D_(h["toplamlar"]["uretim_gideri"]))
    _yakin(etiketli["Giydirilmiş maliyet"][10].value, h["toplamlar"]["giydirilmis"])
    satis = next(v for k, v in etiketli.items() if k.startswith("Satış fiyatı TL"))
    _yakin(satis[10].value, h["fiyatlar"]["satis_tl"])
    if h["fiyatlar"]["teklifler_usd"]:
        teklif = next(v for k, v in etiketli.items() if k.startswith("1. teklif USD/adet"))
        _yakin(teklif[10].value, h["fiyatlar"]["teklifler_usd"][0])
        assert teklif[10].number_format == "#,##0.0000"
    # reçete satırları: ekrandaki malzeme satırlarıyla bire bir, sayılar sayı tipinde
    malzeme = [x for x in h["satirlar"] if x["grup"] == "malzeme"]
    recete = satirlar[4:4 + len(malzeme)]
    assert [r[0].value for r in recete] == [x["sira"] for x in malzeme] and [r[2].value for r in recete] == [x["kalem"] for x in malzeme]
    for r, x in zip(recete, malzeme):
        for sutun, alan in ((3, "miktar"), (5, "brut_miktar"), (7, "birim_fiyat"), (9, "tutar_firesiz"), (10, "tutar")):
            assert isinstance(r[sutun].value, (int, float)), (alan, r[sutun].value)
            _yakin(r[sutun].value, x[alan])
        _yakin(r[4].value, x["fire_orani"])
        assert r[6].value == x["birim"] and r[8].value == x["doviz"]
    assert recete[0][3].number_format == "#,##0.0000" and recete[0][10].number_format == "#,##0.00" and recete[0][4].number_format == "0.00%"
    toplam = satirlar[4 + len(malzeme)]
    assert toplam[2].value == "Malzeme toplamı"
    _yakin(toplam[10].value, sum(D_(x["tutar"]) for x in malzeme))
    # gider kalemleri: ekrandaki gider satırlarıyla aynı tutarlar
    for x in (x for x in h["satirlar"] if x["grup"] != "malzeme"):
        _yakin(etiketli[x["kalem"]][10].value, x["tutar"])
    # formül yok
    assert not any(isinstance(c_.value, str) and c_.value.startswith("=") for r in satirlar for c_ in r)
    # Özet satırı aynı hesap
    o = ozet[kod]
    _yakin(o["Birim maliyet TL"], h["toplamlar"]["maliyet_tl"]); _yakin(o["Malzeme toplamı"], h["toplamlar"]["malzeme"])
    _yakin(o["Üretim gideri"], h["toplamlar"]["uretim_gideri"]); _yakin(o["Faaliyet gideri"], h["toplamlar"]["diger"])
    _yakin(o["Finansman"], h["toplamlar"]["finansman_tl"]); _yakin(o["Satış TL"], h["fiyatlar"]["satis_tl"])
    _yakin(o["Satış USD"], h["fiyatlar"]["satis_usd"]); _yakin(o["Satış EUR"], h["fiyatlar"]["satis_eur"])
    assert o["Uyarı sayısı"] == len(h["uyarilar"]) and all(isinstance(o[a], float) for a in ("Birim maliyet TL", "Malzeme toplamı", "Satış TL"))


def test_bilinmeyen_senaryo_404(ortam):
    _s, _sid, c = ortam
    assert c.get(f"{A}/disa-aktar/maliyet-kartlari?senaryo=999999").status_code == 404
