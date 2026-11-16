"""Onay çıktısı (yeminli mali müşavir için): Fiyat Çalışması ve SMM'nin değerli Excel'i ve PDF'i.

Fiyat tarafı gerçek kitapla (sayfa listesi, kapak, TASLAK/KESİN, seçili ürün alt kümesi, toplamların uygulamanın hesabıyla eşitliği);
SMM tarafı uydurma küçük dönemle (test_smm_asama._excel). Şirket verisi test çıktısına yazılmaz (yalnız kod ve sayılar)."""
import re
from datetime import date
from decimal import Decimal as D_
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from backend.depo import modeller as m
from backend.depo.veritabani import Base, motor_olustur, oturum_fabrikasi, oturum_ver
from backend.servisler import arsiv_servisi as ar, fiyat_servisi as fs, hesap_servisi as hs, kimlik_servisi as ks, parametre_servisi as ps
from backend.servisler import import_servisi as ims, smm_ozet_servisi as so
from backend.uygulama import onbellegi_temizlemeli_mi, uygulama_olustur
from tests.backend.test_api import istemci  # noqa: F401  (fixture)
from tests.backend.test_kimlik import _istemci, uygulama  # noqa: F401  (fixture)
from tests.backend.test_smm_asama import _excel

A = "/api/v1"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
FIYAT_SABIT = ["Satın Alma Fiyatları", "Parametreler", "Gider Dağıtım", "Elle Değişiklikler", "Günlük Özeti"]
SMM_SAYFALARI = ["Kapak", "Stok ve Envanter", "Üretim 20", "Üretim 40", "Üretim 50", "DSS", "SMM Tablosu", "Gider Mizanı", "Stok Mizanı",
                 "Fiş Taslağı", "Mutabakat", "Elle Değişiklikler", "Günlük Özeti"]


def _yakin(a, b, tol="0.005"):
    assert a is not None and b is not None and abs(D_(str(a)) - D_(str(b))) <= D_(tol), (a, b)


def _pdf_sayfa(icerik: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page\b", icerik))


def _kapak(ws) -> dict:
    """Kapak'taki etiket -> değer satırları (5. satırdan ilk boş satıra kadar)."""
    out, r = {}, 5
    while ws.cell(row=r, column=1).value:
        out[ws.cell(row=r, column=1).value] = ws.cell(row=r, column=2).value
        r += 1
    return out


def _satir_bul(ws, metin: str, sutun: int = 1):
    return next(r for r in ws.iter_rows(values_only=True) if r[sutun - 1] == metin)


def _kirmizi(hucre) -> bool:
    return hucre.font.color is not None and str(hucre.font.color.rgb).endswith("C00000")


# ---------------------------------------------------------------- Fiyat Çalışması (gerçek kitap)
@pytest.fixture(scope="module")
def ortam(excel_yolu):
    engine = motor_olustur("sqlite://"); Base.metadata.create_all(engine)
    s = oturum_fabrikasi(engine)()
    sid = ims.excel_tam_yukle(s, excel_yolu, "2026-2027", "Bütçe")["senaryo_id"]
    # elle değişiklik: bir malzemeye aynı fiyatla yeni kayıt (eski değeri olan günlük kaydı; tutarlar değişmez)
    kod, kayit = sorted(fs.gecerli_kayitlar_kodla(s, sid, date.today()).items())[0]
    fs.fiyat_ekle(s, sid, kod, kayit.fiyat, date.today(), "onay çıktısı testi", olusturan="test")
    s.commit()
    app = uygulama_olustur()
    app.dependency_overrides[oturum_ver] = lambda: s
    yield s, sid, TestClient(app), kod
    s.close()


@pytest.fixture(scope="module")
def tum_kitap(ortam):
    s, sid, c, _ = ortam
    r = c.post(f"{A}/onay-ciktisi/fiyat", json={"senaryo_id": sid, "tur": "excel", "imzalar": {"hazirlayan": "  Deneme Hazırlayan  "}},
               headers={"X-Kullanici": "deneme"})
    assert r.status_code == 200, r.text
    return r, load_workbook(BytesIO(r.content))


def test_fiyat_excel_sayfalar_ve_kapak(ortam, tum_kitap):
    s, sid, _c, _ = ortam
    r, wb = tum_kitap
    assert r.headers["content-type"].startswith(XLSX)
    assert re.search(rf'filename="onay-ciktisi-fiyat-2026-2027-{date.today():%m-%d-%Y}\.xlsx"', r.headers["content-disposition"])
    hesaplanan = [kod for kod, x in hs.toplu_hesapla(s, sid) if not isinstance(x, Exception)]
    assert wb.sheetnames[:3] == ["Kapak", "Teklif Kapak", "Özet"] and wb.sheetnames[-5:] == FIYAT_SABIT
    kartlar = wb.sheetnames[3:-5]
    assert len(kartlar) == len(hesaplanan) > 10
    assert len({x.casefold() for x in wb.sheetnames}) == len(wb.sheetnames) and all(len(x) <= 31 for x in wb.sheetnames)
    k = wb["Kapak"]
    assert k["A1"].value == "Zeytursan" and k["A2"].value == "Fiyat Çalışması Onay Çıktısı"
    assert k["A3"].value == "TASLAK — çalışma kapatılmadı" and _kirmizi(k["A3"])
    b = _kapak(k)
    assert b["Durum"] == "TASLAK" and b["Kapatan"] == "—" and b["Çıktıyı alan"] == "deneme" and b["Hesap tarihi"] == f"{date.today():%d.%m.%Y}"
    assert b["Kapsam"].endswith(f"tüm ürünler ({len(hs.toplu_hesapla(s, sid))})") and b["Uygulama sürümü"]
    # içindekiler köprüleri ve imza tablosu
    baglar = {c_.value: c_.hyperlink.location for row in k.iter_rows() for c_ in row if c_.hyperlink is not None}
    assert set(FIYAT_SABIT + ["Teklif Kapak", "Özet"]) <= set(baglar) and baglar["Parametreler"] == "'Parametreler'!A1"
    assert _satir_bul(k, "Hazırlayan")[1] == "Deneme Hazırlayan" and _satir_bul(k, "Onaylayan")[1] is None
    # TASLAK damgası her sayfanın başında (kırmızı); yazdırma ayarı
    assert _kirmizi(wb["Teklif Kapak"]["L1"]) and wb["Teklif Kapak"]["L1"].value.startswith("TASLAK")
    assert wb["Özet"]["A3"].value.startswith("TASLAK") and wb[kartlar[0]]["A3"].value.startswith("TASLAK — çalışma kapatılmadı · Değerler")
    for ad in FIYAT_SABIT:
        assert wb[ad]["A2"].value.startswith("TASLAK") and _kirmizi(wb[ad]["A2"]), ad
    for ws in wb.worksheets:
        assert ws.page_setup.orientation == "landscape" and ws.page_setup.fitToWidth == 1 and "TASLAK" in ws.oddHeader.center.text
        assert ws.oddFooter.center.text == "Sayfa &P / &N"
    assert wb["Parametreler"].freeze_panes == "A6" and wb["Parametreler"]["A5"].font.bold


def test_fiyat_excel_toplamlar_uygulamayla_esit(ortam, tum_kitap):
    s, sid, _c, kod = ortam
    _r, wb = tum_kitap
    hesaplar = {k: x for k, x in hs.toplu_hesapla(s, sid) if not isinstance(x, Exception)}
    # Özet: birim maliyet (TL) ürün başına; toplam
    oz = {row[0]: row for row in wb["Özet"].iter_rows(min_row=5, values_only=True) if row[0]}
    for k_, x in hesaplar.items():
        _yakin(oz[k_][8], x.sonuc.finansman_dahil_maliyet_tl, "0.0000001")
    _yakin(sum(D_(str(oz[k_][8])) for k_ in hesaplar), sum(x.sonuc.finansman_dahil_maliyet_tl for x in hesaplar.values()), "0.001")
    # Teklif Kapak: L sütunu (birim maliyet TL) toplamı
    tk = wb["Teklif Kapak"]
    l_toplam = sum(D_(str(tk[f"L{i}"].value)) for i in range(4, tk.max_row + 1) if isinstance(tk[f"L{i}"].value, (int, float)))
    _yakin(l_toplam, sum(x.sonuc.finansman_dahil_maliyet_tl for x in hesaplar.values()), "0.001")
    # Parametreler: geçerli değerler
    pr = {row[0]: row[3] for row in wb["Parametreler"].iter_rows(min_row=6, values_only=True) if row[0]}
    gecerli = ps.gecerli_degerler(s, sid, date.today())
    assert set(pr) == set(gecerli)
    for a, v in gecerli.items():
        _yakin(pr[a], v, "0.0000001")
    assert wb["Parametreler"].cell(row=6, column=4).number_format == "#,##0.0000"
    # Satın alma fiyatları: geçerli fiyat malzeme ekranıyla aynı; sayı tipinde
    sa = {row[0]: row for row in wb["Satın Alma Fiyatları"].iter_rows(min_row=6, values_only=True) if row[0]}
    for k_, g in fs.gecerli_kayitlar_kodla(s, sid, date.today()).items():
        _yakin(sa[k_][6], g.fiyat, "0.0000001")
    # elle değişiklikler ve günlük özeti
    elle = [row for row in wb["Elle Değişiklikler"].iter_rows(min_row=6, values_only=True) if row[0]]
    assert any(row[2] == f"Malzeme fiyatı: {kod}" and row[6] == "onay çıktısı testi" for row in elle)
    gn = wb["Günlük Özeti"]
    assert gn["A5"].value == "Tür bazında" and gn["A6"].value == "Tür" and gn["B6"].value == "Kayıt sayısı"
    assert _satir_bul(gn, "Toplam")[1] >= 1


def test_fiyat_alt_kume_kilitli_kesin_ve_pdf(ortam):
    s, sid, c, _ = ortam
    hesaplanan = [kod for kod, x in hs.toplu_hesapla(s, sid) if not isinstance(x, Exception)]
    secim = hesaplanan[:3]
    ar.kilitle(s, sid, "onay testi", "kapatan-kisi")
    s.commit()
    try:
        r = c.post(f"{A}/onay-ciktisi/fiyat", json={"senaryo_id": sid, "tur": "excel", "urunler": secim,
                                                     "ekler": {"elle_degisiklikler": False, "gunluk_ozeti": False}})
        assert r.status_code == 200, r.text
        wb = load_workbook(BytesIO(r.content))
        assert wb.sheetnames == ["Kapak", "Teklif Kapak", "Özet"] + [x for x in wb.sheetnames[3:-3]] + FIYAT_SABIT[:3]
        assert len(wb.sheetnames) == 3 + len(secim) + 3
        b = _kapak(wb["Kapak"])
        assert b["Durum"] == "KESİN" and b["Kapatan"] == "kapatan-kisi" and b["Kapanış tarihi"].startswith(f"{date.today():%d.%m.%Y}")
        assert b["Kapsam"].endswith(f"seçili {len(secim)} ürün (çalışmada {len(hs.toplu_hesapla(s, sid))})")
        assert wb["Kapak"]["A3"].value.startswith("KESİN — çalışma kapatıldı (kapatan-kisi") and not _kirmizi(wb["Kapak"]["A3"])
        assert "KESİN" in wb["Parametreler"].oddHeader.center.text
        tk = wb["Teklif Kapak"]
        assert sorted(tk[f"C{i}"].value for i in range(4, tk.max_row + 1) if tk[f"C{i}"].value) == sorted(secim)
        # PDF (kilitli çalışmada da üretilir; filigran yok)
        r = c.post(f"{A}/onay-ciktisi/fiyat", json={"senaryo_id": sid, "tur": "pdf", "urunler": secim})
        assert r.status_code == 200, r.text
        assert r.headers["content-type"] == "application/pdf" and r.content.startswith(b"%PDF") and len(r.content) > 10_000
        assert _pdf_sayfa(r.content) > 1
        assert re.search(r'filename="onay-ciktisi-fiyat-2026-2027-.*\.pdf"', r.headers["content-disposition"])
    finally:
        ar.kilit_ac(s, sid, "onay testi bitti", "test")
        s.commit()


def test_fiyat_hatalari(ortam):
    s, sid, c, _ = ortam
    assert c.post(f"{A}/onay-ciktisi/fiyat", json={"senaryo_id": 99999, "tur": "excel"}).status_code == 404
    r = c.post(f"{A}/onay-ciktisi/fiyat", json={"senaryo_id": sid, "tur": "excel_formullu"})
    assert r.status_code == 422 and "body.tur" in r.json()["alanlar"]
    r = c.post(f"{A}/onay-ciktisi/fiyat", json={"senaryo_id": sid, "tur": "excel", "urunler": ["YOK-KOD-1"]})
    assert r.status_code == 422 and r.json()["alanlar"]["urunler"] == ["YOK-KOD-1"]
    assert c.post(f"{A}/onay-ciktisi/fiyat", json={"senaryo_id": sid, "tur": "excel", "urunler": []}).status_code == 422


# ---------------------------------------------------------------- SMM (uydurma küçük dönem)
def _donem(istemci):
    r = istemci.post(f"{A}/smm/donemler/yukle", files={"dosya": ("09-2026 SMM.xlsx", _excel())})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_smm_excel_sayfalar_mutabakat_ve_kesin(istemci, oturum):  # noqa: F811
    did = _donem(istemci)
    # mutabakat farkı: stok mizanına elle satır; elle değişiklik: finansman
    r = istemci.post(f"{A}/smm/donemler/{did}/mizan/stok", json={"hesap": "150.01.001", "ad": "Hammadde", "bakiye": "1000", "neden": "test"},
                     headers={"X-Kullanici": "muhasebe1"})
    assert r.status_code == 201, r.text
    assert istemci.put(f"{A}/smm/donemler/{did}/ayarlar", json={"finansman": "10"}, headers={"X-Kullanici": "muhasebe1"}).status_code == 200
    r = istemci.post(f"{A}/onay-ciktisi/smm", json={"donem_id": did, "tur": "excel", "imzalar": {"onaylayan": "Onaylayan Kişi"}})
    assert r.status_code == 200, r.text
    assert re.search(rf'filename="onay-ciktisi-smm-2026-09-{date.today():%m-%d-%Y}\.xlsx"', r.headers["content-disposition"])
    wb = load_workbook(BytesIO(r.content))
    assert wb.sheetnames == SMM_SAYFALARI
    o = so.smm_ozeti(oturum, did)
    b = _kapak(wb["Kapak"])
    assert b["Belge"] == "Maliyet Muhasebesi Onay Çıktısı" and b["Dönem"] == "Eylül 2026" and b["Durum"] == "TASLAK"
    assert wb["Kapak"]["A3"].value == "TASLAK — dönem kapatılmadı"
    kaynaklar = [row[1] for row in wb["Kapak"].iter_rows(values_only=True)]
    assert "09-2026 SMM.xlsx" in kaynaklar
    assert _satir_bul(wb["Kapak"], "Onaylayan")[1] == "Onaylayan Kişi"
    for ad in SMM_SAYFALARI[1:]:
        assert wb[ad]["A2"].value == "TASLAK — dönem kapatılmadı" and _kirmizi(wb[ad]["A2"]), ad
    # SMM tablosu ve DSS toplamları uygulamanın hesabıyla aynı
    st = wb["SMM Tablosu"]
    _yakin(_satir_bul(st, "Satılan mamul maliyeti (620)")[1], o["smm"])
    _yakin(_satir_bul(st, "Üretim maliyeti")[1], o["uretim_maliyeti"])
    _yakin(_satir_bul(wb["DSS"], "Toplam")[3], o["donem_sonu_stok"])
    # fiş: borç = alacak
    fis = _satir_bul(wb["Fiş Taslağı"], "Toplam", 3)
    _yakin(fis[3], o["fis_borc"])
    _yakin(fis[4], o["fis_alacak"])
    # mutabakat: stok mizanı ile sayım farkı (150)
    mt = wb["Mutabakat"]
    k150 = next(x for x in o["mizan_kiyas"] if x["hesap"] == "150")
    satir = _satir_bul(mt, "150")
    _yakin(satir[2], 1000)
    _yakin(satir[3], k150["sayim"])
    _yakin(satir[4], k150["fark"])
    assert D_(k150["fark"]) != 0
    _yakin(_satir_bul(mt, "Fark")[1], D_(o["fis_borc"]) - D_(o["fis_alacak"]))
    # stok ve envanter: toplam satırı stok tablosuyla aynı
    sv = _satir_bul(wb["Stok ve Envanter"], "Dönem toplamı (tüm kalemler)")
    assert sv[6] is not None and wb["Stok ve Envanter"].freeze_panes == "A6"
    # elle değişiklikler ve günlük
    elle = [row for row in wb["Elle Değişiklikler"].iter_rows(min_row=6, values_only=True) if row[0]]
    assert {row[1] for row in elle} == {"muhasebe1"} and len(elle) == 2
    assert any(row[2] == "SMM mizan satırı eklendi" and row[3] == "150.01.001" for row in elle)
    assert _satir_bul(wb["Günlük Özeti"], "Toplam")[1] >= 3   # yükleme + mizan + ayar
    # kilitli dönem: KESİN, kapatan
    assert istemci.put(f"{A}/smm/donemler/{did}/kilit", json={"kilitli": True, "zorla": True}, headers={"X-Kullanici": "kapatan"}).status_code == 200
    r = istemci.post(f"{A}/onay-ciktisi/smm", json={"donem_id": did, "tur": "excel", "ekler": {"mutabakat": False, "kapak": False}})
    assert r.status_code == 200, r.text
    wb = load_workbook(BytesIO(r.content))
    assert wb.sheetnames == [x for x in SMM_SAYFALARI if x not in ("Kapak", "Mutabakat")]
    assert wb["DSS"]["A2"].value.startswith("KESİN — dönem kapatıldı (kapatan") and not _kirmizi(wb["DSS"]["A2"])


def test_smm_pdf_ve_hatalar(istemci):  # noqa: F811
    did = _donem(istemci)
    r = istemci.post(f"{A}/onay-ciktisi/smm", json={"donem_id": did, "tur": "pdf"})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf" and r.content.startswith(b"%PDF") and _pdf_sayfa(r.content) > 1
    assert istemci.post(f"{A}/onay-ciktisi/smm", json={"donem_id": 9999, "tur": "pdf"}).status_code == 404
    assert istemci.post(f"{A}/onay-ciktisi/smm", json={"donem_id": did, "tur": "word"}).status_code == 422
    assert istemci.post(f"{A}/onay-ciktisi/smm", json={"donem_id": did}).status_code == 422


def test_izleyici_indirebilir_onbellek_bosalmaz(uygulama, oturum):  # noqa: F811
    assert ks.yazabilir_mi("izleyici", "POST", "/api/v1/onay-ciktisi/fiyat") and ks.yazabilir_mi("izleyici", "POST", "/api/v1/onay-ciktisi/smm")
    assert not ks.yazabilir_mi("izleyici", "POST", "/api/v1/onay-ciktisi/fiyat/baska")
    assert not onbellegi_temizlemeli_mi("POST", "/api/v1/onay-ciktisi/fiyat") and onbellegi_temizlemeli_mi("POST", "/api/v1/urunler")
    gd = _istemci(uygulama, "genel")
    did = _donem(gd)
    ks.kullanici_olustur(oturum, "izle", "izle", "izleyici", "sifre-1234", sifre_degismeli=False)
    oturum.commit()
    izle = _istemci(uygulama, "izle", "sifre-1234")
    r = izle.post(f"{A}/onay-ciktisi/smm", json={"donem_id": did, "tur": "excel"})
    assert r.status_code == 200, r.text
    assert _kapak(load_workbook(BytesIO(r.content))["Kapak"])["Çıktıyı alan"] == "izle"
    sid = gd.post(f"{A}/senaryolar", json={"sezon_ad": "2026-2027", "tur": "fiyat_calismasi", "ad": "A"}).json()["id"]
    r = izle.post(f"{A}/onay-ciktisi/fiyat", json={"senaryo_id": sid, "tur": "excel", "ekler": {"kapak": False}})
    assert r.status_code == 200, r.text
    assert load_workbook(BytesIO(r.content)).sheetnames[0] == "Teklif Kapak"
    assert izle.put(f"{A}/smm/donemler/{did}/ayarlar", json={"finansman": "1"}).status_code == 403   # yazma yine kapalı
    assert oturum.query(m.DegisiklikKaydi).filter_by(kullanici="izle").count() == 0
