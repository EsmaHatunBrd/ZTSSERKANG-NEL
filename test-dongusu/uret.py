"""Uçtan uca test döngüsü için UYDURMA test Excel'lerini üretir (gerçek şirket verisi yok).

Çıktı: test-dongusu/excel/11-16-2026-*.xlsx. Yeniden çalıştırılabilir; sabit tohumla her seferinde aynı dosyalar üretilir (var olan
test dosyalarının üzerine yazar; başka dosyaya dokunmaz).

Biçimler uygulamanın okuyucularından alınmıştır (kod değişirse burası da güncellenmeli):
- Fiyat Çalışması tam kitabı: fiyat_motoru/excel_okuyucu.py (ürün sayfaları etiket tabanlı; Gider Dağıtım sabit hücreler; S.ALMA BF;
  Üretim Adetleri) ve backend/servisler/import_servisi.py.
- Veri Aktar sekmeleri: backend/servisler/aktarim_servisi.py, recete_aktarim_servisi.py, stok_devri_servisi.py; satış geçmişi ve liste
  fiyatları: satis_okuyucu.py / liste_servisi.py.
- SMM: backend/servisler/smm_servisi.py (tam SMM Excel'i), smm_veri_servisi.py KAYNAKLAR (aylık kaynak dosyaları),
  smm_recete_servisi.py (Canias ürün ağacı dökümü).

Formül hücreleri: openpyxl formülün son hesaplanmış değerini yazamaz; uygulama ise değeri okur. Bu yüzden okunan formül hücrelerinin
(ör. Gider Dağıtım D4 '=6000000*1.35*1.2', reçete K/M) önbellek değeri kaydedildikten sonra xlsx XML'ine eklenir (_onbellek_ekle).
Kitap 'açılışta yeniden hesapla' işaretlidir: Excel'de açınca formüller yeniden hesaplanır.

Kullanım (proje kökünden):  .venv\\Scripts\\python.exe test-dongusu\\uret.py
"""
import random
import re
import shutil
import sys
import zipfile
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import openpyxl
from openpyxl.styles import Font, PatternFill

BURASI = Path(__file__).resolve().parent
CIKTI = BURASI / "excel"
ON = "11-16-2026-"
TOHUM = 20261116
D = Decimal

# ======================================================================================= ortak veri
# (kod, ad, tip, birim, para, bütçe fiyatı | None, Z/S)
MALZEMELER = [
    ("99.10.001", "Test Taze Hıyar", "0001-Hammadde", "KG", "TL", 18.5, "Z"),
    ("99.10.002", "Test Kornişon Hıyar", "0001-Hammadde", "KG", "TL", 26.0, "Z"),
    ("99.10.003", "Test Kapya Biber", "0001-Hammadde", "KG", "TL", 32.0, "Z"),
    ("99.10.004", "Test Domates", "0001-Hammadde", "KG", "TL", 14.0, "Z"),
    ("99.10.005", "Test Siyah Zeytin", "0001-Hammadde", "KG", "TL", 95.0, "Z"),
    ("99.10.006", "Test Havuç", "0001-Hammadde", "KG", "TL", 12.0, "Z"),
    ("99.10.007", "Test Beyaz Lahana", "0001-Hammadde", "KG", "TL", 9.5, "Z"),
    ("99.11.001", "Test Tuz 25 kg", "0017-Yardımcı Malzeme", "KG", "TL", 4.2, "S"),
    ("99.11.002", "Test Sirke %10", "0017-Yardımcı Malzeme", "LT", "TL", 21.0, "S"),
    ("99.11.003", "Test Sitrik Asit", "0017-Yardımcı Malzeme", "KG", "USD", 2.1, "S"),
    ("99.11.004", "Test Sarımsak", "0001-Hammadde", "KG", "TL", 85.0, "Z"),
    ("99.11.005", "Test Baharat Karışımı", "0017-Yardımcı Malzeme", "KG", "EUR", 9.8, "S"),
    ("99.11.006", "Test Toz Şeker", "0017-Yardımcı Malzeme", "KG", "TL", 38.0, "S"),
    ("99.11.007", "Test Ayçiçek Yağı", "0017-Yardımcı Malzeme", "LT", "TL", 72.0, "S"),
    ("99.11.008", "Test Potasyum Sorbat", "0017-Yardımcı Malzeme", "KG", "EUR", 7.4, "S"),
    ("99.11.009", "Test Kalsiyum Klorür", "0017-Yardımcı Malzeme", "KG", "USD", 1.35, "S"),
    ("99.11.010", "Test Biber Salçası", "0001-Hammadde", "KG", "TL", None, "S"),          # fiyatsız (Veri Kontrolü)
    ("99.20.001", "Test Kavanoz 370 ml", "0008-Ambalaj Malzeme", "AD", "TL", 6.4, "S"),
    ("99.20.002", "Test Kavanoz 720 ml", "0008-Ambalaj Malzeme", "AD", "TL", 9.1, "S"),
    ("99.20.003", "Test Kapak 63 mm", "0008-Ambalaj Malzeme", "AD", "TL", 2.15, "S"),
    ("99.20.004", "Test Kapak 82 mm", "0008-Ambalaj Malzeme", "AD", "TL", 2.9, "S"),
    ("99.20.005", "Test Etiket 370 ml", "0008-Ambalaj Malzeme", "AD", "TL", 0.42, "S"),
    ("99.20.006", "Test Etiket 720 ml", "0008-Ambalaj Malzeme", "AD", "TL", 0.55, "S"),
    ("99.20.007", "Test Koli 12'li", "0008-Ambalaj Malzeme", "AD", "TL", 11.5, "S"),
    ("99.20.008", "Test Koli 6'lı", "0008-Ambalaj Malzeme", "AD", "TL", 9.2, "S"),
    ("99.20.009", "Test Teneke 2,5 kg", "0008-Ambalaj Malzeme", "AD", "TL", 24.0, "S"),
    ("99.20.010", "Test Kavanoz 340 g Sos", "0008-Ambalaj Malzeme", "AD", "TL", 5.8, "S"),
    ("99.20.011", "Test Streç Film", "0008-Ambalaj Malzeme", "KG", "TL", 95.0, "S"),
    ("99.20.012", "Test Etiket Zeytin 500 g", "0008-Ambalaj Malzeme", "AD", "TL", 0.48, "S"),
    ("99.20.013", "Test Vakum Poşet 500 g", "0008-Ambalaj Malzeme", "AD", "TL", 3.1, "S"),
    ("99.20.014", "Test Koli Zeytin 10'lu", "0008-Ambalaj Malzeme", "AD", "TL", 10.4, "S"),
    ("99.20.015", "Test Shrink Kılıf", "0008-Ambalaj Malzeme", "AD", "TL", None, "S"),    # fiyatsız (Veri Kontrolü)
]
MZ = {m[0]: m for m in MALZEMELER}
# Ana kitapta revize (S.ALMA BF I sütunu) girilmiş malzemeler: kod -> revize fiyat
REVIZE_KITAP = {"99.20.003": 2.30, "99.11.002": 22.5}

ARA_MAMUL = {"01.99.001": "Test Fermente Hıyar (ara mamul)", "01.99.002": "Test Fermente Kornişon (ara mamul)"}

# Ürünler: kod, sayfa, ad, hat, sınıf, hacim, süzme kg, vardiya adedi, dolum pers, etiketleme adedi, etiket pers, mal kabul kg,
#          pazarlama/yönetim uygula, reçete [(seviye, kod, miktar, fire, elle_brut, elle_fiyat)]
URUNLER = [
    dict(kod="03.99.001", sayfa="001", ad="Test Berrak Turşu 370 ml", hat="Kavanoz Hattı", sinif="Turşu/Turşu", hacim=370, suzme=0.21,
         vardiya=18000, dolum=12, etiketleme=30000, etiket=3, mk=0.22, pyu=True, recete=[
             (1, "01.99.001", 0.21, 0, None, None), (2, "99.10.001", 0.22, 0.05, None, None), (2, "99.11.001", 0.015, 0.02, None, None),
             (2, "99.11.009", 0.0004, 0, None, None),
             (1, "99.11.002", 0.03, 0.02, None, None), (1, "99.11.003", 0.0005, 0, None, None), (1, "99.20.001", 1, 0.01, None, None),
             (1, "99.20.003", 1, 0.01, None, None), (1, "99.20.005", 1, 0.01, None, None), (1, "99.20.007", 1 / 12, 0, None, None)]),
    dict(kod="03.99.002", sayfa="002", ad="Test Berrak Turşu 720 ml", hat="Kavanoz Hattı", sinif="Turşu/Turşu", hacim=720, suzme=0.42,
         vardiya=12000, dolum=12, etiketleme=20000, etiket=3, mk=0.44, pyu=True, recete=[
             (1, "01.99.001", 0.42, 0, None, None), (2, "99.10.001", 0.44, 0.05, None, None), (2, "99.11.001", 0.03, 0.02, None, None),
             (2, "99.11.009", 0.0008, 0, None, None),
             (1, "99.11.002", 0.06, 0.02, None, None), (1, "99.20.002", 1, 0.01, None, None), (1, "99.20.004", 1, 0.01, None, None),
             (1, "99.20.006", 1, 0.01, None, None), (1, "99.20.008", 1 / 6, 0, None, None), (1, "99.20.015", 1, 0, None, None)]),
    dict(kod="03.99.003", sayfa="003", ad="Test Közlenmiş Biber 370 ml", hat="Kavanoz Hattı", sinif="Taze/Taze", hacim=370, suzme=0.2,
         vardiya=15000, dolum=14, etiketleme=30000, etiket=3, mk=0.25, pyu=True, recete=[
             (1, "99.10.003", 0.25, 0.08, None, None), (1, "99.11.002", 0.02, 0.02, None, None), (1, "99.11.007", 0.01, 0, None, None),
             (1, "99.11.004", 0.003, 0.05, None, 92.0),            # elle birim fiyat (listede 85)
             (1, "99.20.001", 1, 0.01, None, None), (1, "99.20.003", 1, 0.01, None, None), (1, "99.20.005", 1, 0.01, None, None),
             (1, "99.20.007", 1 / 12, 0, None, None)]),
    dict(kod="03.99.004", sayfa="004", ad="Test Domates Sos 340 g", hat="Sos Hattı", sinif="Taze/Taze", hacim=340, suzme=0.34,
         vardiya=20000, dolum=10, etiketleme=30000, etiket=3, mk=0.55, pyu=True, recete=[
             (1, "99.10.004", 0.55, 0.06, None, None), (1, "99.11.006", 0.017, 0, None, None), (1, "99.11.001", 0.005, 0, None, None),
             (1, "99.11.003", 0.0007, 0, None, None), (1, "99.11.005", 0.0015, 0, None, None), (1, "99.11.010", 0.02, 0, None, None),
             (1, "99.20.010", 1, 0.01, None, None), (1, "99.20.003", 1, 0.01, None, None), (1, "99.20.005", 1, 0.01, None, None),
             (1, "99.20.007", 1 / 12, 0, None, None)]),
    dict(kod="03.99.005", sayfa="005", ad="Test Siyah Zeytin 500 g", hat="Kavanoz Hattı", sinif="Taze/Turşu", hacim=500, suzme=0.5,
         vardiya=9000, dolum=8, etiketleme=20000, etiket=2, mk=0.52, pyu=True, recete=[
             (1, "99.10.005", 0.5, 0.03, 0.53, None),               # elle brüt miktar (fire kuralı 0,5155)
             (1, "99.11.007", 0.005, 0, None, None), (1, "99.11.008", 0.0004, 0, None, None),
             (1, "99.20.013", 1, 0.02, None, None), (1, "99.20.012", 1, 0.01, None, None), (1, "99.20.014", 0.1, 0, None, None)]),
    dict(kod="03.99.006", sayfa="006", ad="Test Karışık Turşu 2,5 kg", hat="Teneke Hattı", sinif="Turşu/Turşu", hacim=2.5, suzme=1.5,
         vardiya=3000, dolum=6, etiketleme=0, etiket=0, mk=1.6, pyu=False, enflasyon=0.25, recete=[
             (1, "99.10.001", 0.7, 0.05, None, None), (1, "99.10.006", 0.35, 0.05, None, None), (1, "99.10.007", 0.45, 0.05, None, None),
             (1, "99.11.001", 0.12, 0.02, None, None), (1, "99.11.002", 0.25, 0.02, None, None), (1, "99.20.009", 1, 0.01, None, None)]),
    dict(kod="03.99.007", sayfa="007", ad="Test Berrak Kornişon 370 ml", hat="Kavanoz Hattı", sinif="Turşu/Turşu", hacim=370, suzme=0.2,
         vardiya=18000, dolum=12, etiketleme=30000, etiket=3, mk=0.22, pyu=True, recete=[
             (1, "01.99.002", 0.2, 0, None, None), (2, "99.10.002", 0.21, 0.04, None, None), (2, "99.11.001", 0.014, 0.02, None, None),
             (2, "99.11.009", 0.0004, 0, None, None),
             (1, "99.11.002", 0.03, 0.02, None, None), (1, "99.11.005", 0.0008, 0, None, None), (1, "99.20.001", 1, 0.01, None, None),
             (1, "99.20.003", 1, 0.01, None, None), (1, "99.20.005", 1, 0.01, None, None), (1, "99.20.007", 1 / 12, 0, None, None)]),
]
BUTCE_PARAM = dict(enflasyon=0.30, kur={"USD": 42.5, "EUR": 49.0, "GBP": 56.0, "CHF": 52.0},
                   faiz={"TL": (0.40, 6), "USD": (0.06, 6), "EUR": (0.06, 6)}, teklif=(0.20, 0.17, 0.14))


def _sayi(x):
    """Float gürültüsüz yazım: 0.1+0.2 gibi artıkları at."""
    if isinstance(x, float):
        r = round(x, 10)
        return int(r) if r == int(r) and abs(r) < 1e15 else r
    return x


class Onbellek:
    """Formül hücrelerinin önbellek değerleri: {sayfa adı: {hücre: sayı}}."""

    def __init__(self):
        self.d: dict[str, dict[str, float]] = {}

    def formul(self, ws, hucre: str, formul: str, deger) -> None:
        ws[hucre] = formul
        if deger is not None:
            self.d.setdefault(ws.title, {})[hucre] = deger


def _kaydet(wb, ad: str, onb: Onbellek | None = None) -> Path:
    yol = CIKTI / f"{ON}{ad}.xlsx"
    wb.calculation.fullCalcOnLoad = bool(onb and onb.d)
    wb.save(yol)
    if onb and onb.d:
        _onbellek_ekle(yol, [ws.title for ws in wb.worksheets], onb.d)
    return yol


def _onbellek_ekle(yol: Path, sayfalar: list[str], degerler: dict[str, dict[str, float]]) -> None:
    """openpyxl'in boş bıraktığı <v/> etiketlerine formül önbellek değerini yazar (sayfaN.xml sırası = kitap sırası)."""
    gecici = yol.with_suffix(".tmp")
    with zipfile.ZipFile(yol) as zin, zipfile.ZipFile(gecici, "w", zipfile.ZIP_DEFLATED) as zout:
        for bilgi in zin.infolist():
            veri = zin.read(bilgi.filename)
            e = re.fullmatch(r"xl/worksheets/sheet(\d+)\.xml", bilgi.filename)
            if e and sayfalar[int(e.group(1)) - 1] in degerler:
                metin = veri.decode("utf-8")
                for hucre, v in degerler[sayfalar[int(e.group(1)) - 1]].items():
                    desen = re.compile(rf'(<c r="{hucre}"[^>]*>)(<f>.*?</f>)<v\s*/>', re.S)
                    metin, n = desen.subn(lambda m_: f"{m_.group(1)}{m_.group(2)}<v>{_sayi(v)!r}</v>", metin, count=1)
                    if n != 1:
                        raise RuntimeError(f"önbellek yazılamadı: {yol.name} {hucre}")
                veri = metin.encode("utf-8")
            zout.writestr(bilgi, veri)
    shutil.move(gecici, yol)


KALIN = Font(bold=True)
BASLIK_DOLGU = PatternFill("solid", fgColor="E9ECDB")


def _baslik(ws, satir: int, degerler: list, sutun: int = 1) -> None:
    for i, v in enumerate(degerler):
        c = ws.cell(row=satir, column=sutun + i, value=v)
        c.font = KALIN
        c.fill = BASLIK_DOLGU


# ======================================================================================= Fiyat Çalışması kitabı
def satin_alma_sayfasi(ws, fiyatlar: dict[str, float | None], revize: dict[str, float], malzemeler=MALZEMELER) -> None:
    ws.title = "S.ALMA BF"
    _baslik(ws, 1, ["Malzeme", "Açıklama", "Malzeme Tipi", "Stok Birimi", "Para Birimi", "Bütçe Birim Fiyatları", "Z/S", "Not",
                    "Bütçe Birim Fiyatları"])
    for r, (kod, ad, tip, birim, para, _, zs) in enumerate(malzemeler, start=2):
        ws.append([kod, ad, tip, birim, para, fiyatlar.get(kod), zs, None, revize.get(kod)])
    for col, w in zip("ABCDEFGHI", (12, 30, 22, 10, 10, 20, 6, 10, 20)):
        ws.column_dimensions[col].width = w


def gider_sayfasi(ws, onb: Onbellek, k: dict | None = None) -> None:
    """Gider Dağıtım sayfası (excel_okuyucu.HAVUZ_TOPLAM_HUCRELERI ve satır aralıkları). k: havuz katsayıları (gerçekleşen/aktarım için)."""
    k = k or {}
    ws.title = "Gider Dağıtım"
    ws["A1"] = "GİDER DAĞITIM TABLOSU (TEST VERİSİ)"; ws["A1"].font = KALIN

    def toplam(hucre, taban, carpanlar, ad):
        carpanlar = list(carpanlar) + ([k[ad]] if ad in k else [])
        deger = D(str(taban))
        for c in carpanlar:
            deger *= D(str(c))
        onb.formul(ws, hucre, "=" + "*".join([str(taban)] + [str(c) for c in carpanlar]), float(deger))

    def etiket(hucre, metin):
        ws[hucre] = metin; ws[hucre].font = KALIN

    etiket("A3", "Dolum Doğrudan İşçilik"); etiket("D3", "Gider Toplamı"); etiket("F3", "Toplam adam-saniye"); etiket("G3", "TL / sn")
    toplam("D4", 6000000, (1.35, 1.2), "dolum"); ws["F4"] = 360000000; ws["G4"] = "=D4/F4"
    etiket("A5", "Mal Kabul ve Fermantasyon İşçilik (toplam A6)")
    ws["A6"] = 2400000 * k.get("mal_kabul", 1)
    for r, (sinif, pay, kg) in zip(range(7, 10), (("Taze/Taze", 0.2, 1000000), ("Taze/Turşu", 0.3, 1500000), ("Turşu/Turşu", 0.5, 2500000))):
        ws[f"C{r}"], ws[f"E{r}"], ws[f"G{r}"] = sinif, kg, pay
        ws[f"F{r}"] = f"=$A$6*G{r}/E{r}"
    etiket("A12", "Etiketleme İşçilik"); etiket("D12", "Gider Toplamı")
    ws["D13"] = 1800000 * k.get("etiket", 1); ws["F13"] = 90000000; ws["G13"] = "=D13/F13"
    etiket("A17", "Endirekt İşçilik"); etiket("D17", "Gider Toplamı")
    toplam("D18", 4000000, (1.25,), "endirekt"); ws["F18"] = 30000000; ws["G18"] = "=D18/F18"
    etiket("A19", "Mal Kabul ve Fermantasyon GÜG (toplam A20)")
    ws["A20"] = 1200000 * k.get("mal_kabul", 1)
    for r, (sinif, pay, kg) in zip(range(21, 24), (("Taze/Taze", 0.2, 1000000), ("Taze/Turşu", 0.3, 1500000), ("Turşu/Turşu", 0.5, 2500000))):
        ws[f"C{r}"], ws[f"E{r}"], ws[f"G{r}"] = sinif, kg, pay
        ws[f"F{r}"] = f"=$A$20*G{r}/E{r}"
    etiket("A26", "Diğer Genel Üretim Giderleri"); etiket("D26", "Gider Toplamı")
    toplam("D27", 3200000, (1.25,), "diger"); ws["F27"] = 30000000; ws["G27"] = "=D27/F27"
    hatlar = (("Kavanoz Hattı", 0.55, 18000000), ("Teneke Hattı", 0.25, 6000000), ("Sos Hattı", 0.20, 6000000))
    for bas, top_hucre, taban, carp, ad in ((30, "D38", 2600000, (1.4,), "elektrik"), (41, "D49", 1000000, (1.5,), "dogalgaz"),
                                             (52, "D60", 6000000, (), "amortisman")):
        etiket(f"A{bas - 1}", {"elektrik": "Elektrik", "dogalgaz": "Doğalgaz", "amortisman": "Amortisman"}[ad] + " (hat payları)")
        for r, (hat, pay, sn) in zip(range(bas, bas + 8), hatlar):
            ws[f"A{r}"], ws[f"E{r}"], ws[f"G{r}"] = hat, sn, pay
            ws[f"F{r}"] = f"=${top_hucre[0]}${top_hucre[1:]}*G{r}/E{r}"
        etiket(f"C{top_hucre[1:]}", "Toplam")
        if carp or ad in k:
            toplam(top_hucre, taban, carp, ad)
        else:
            ws[top_hucre] = taban
    etiket("A63", "Genel Yönetim Giderleri"); etiket("D63", "Gider Toplamı")
    toplam("D64", 8000000, (1.3,), "yonetim")
    etiket("A66", "Pazarlama Satış Giderleri"); etiket("D66", "Gider Toplamı")
    toplam("D67", 10000000, (1.25,), "pazarlama")
    etiket("A69", "Ambalaj"); etiket("B69", "Hacim"); etiket("C69", "Üretim Adedi"); etiket("D69", "Katsayı")
    amb = [("370 ml", 370, 9000000, 1), ("720 ml", 720, 4000000 * k.get("amb720", 1), 1.6), ("340 g", 340, 3000000, 0.9),
           ("500 g", 500, 1500000, 1.2), ("2,5 kg", 2.5, 600000, 4)]
    for r, (ad, hacim, adet, kat) in zip(range(70, 92), amb):
        ws[f"A{r}"], ws[f"B{r}"], ws[f"C{r}"], ws[f"D{r}"] = ad, hacim, adet, kat
    ws.column_dimensions["A"].width = 44
    for col in "CDEFG":
        ws.column_dimensions[col].width = 18


def urun_sayfasi(ws, u: dict, fiyatlar: dict[str, float | None], p: dict, onb: Onbellek, ad: str | None = None,
                 miktar_k: dict | None = None) -> None:
    """Ürün sayfası: satır 6 ürünün kendisi (seviye 0), reçete 7-..., etiket satırları gerçek kitaptaki numaralarda (100-155)."""
    ws.title = ad or u["sayfa"]
    miktar_k = miktar_k or {}
    ws["P2"] = "Yurtiçi"
    ws["D2"] = u["ad"]; ws["D2"].font = KALIN
    _baslik(ws, 5, ["Seviye", None, None, "Malzeme Kodu", "Malzeme Adı", None, None, None, "Miktar", "Fire", "Brüt Miktar", "Birim",
                    "Birim Fiyat", "Z/S", "Para B.", "Tutar"])
    ws["A6"], ws["D6"], ws["E6"], ws["I6"], ws["L6"] = 0, u["kod"], u["ad"], 1, "AD"
    onb.formul(ws, "K6", "=I6/(1-J6)", 1)
    onb.formul(ws, "M6", "=IFERROR(VLOOKUP($D6,'S.ALMA BF'!$A:$F,6,0),0)", 0)
    r = 7
    for sev, kod, miktar, fire, elle_brut, elle_fiyat in u["recete"]:
        miktar = miktar * miktar_k.get(kod, 1)
        if kod in ARA_MAMUL:
            adi, birim, liste = ARA_MAMUL[kod], "KG", None
        else:
            _, adi, _, birim, _, _, _ = MZ[kod]
            liste = fiyatlar.get(kod)
        ws[f"A{r}"], ws[f"D{r}"], ws[f"E{r}"], ws[f"I{r}"], ws[f"L{r}"] = sev, kod, adi, _sayi(miktar), birim
        if fire:
            ws[f"J{r}"] = fire
        if elle_brut is not None:
            ws[f"K{r}"] = elle_brut
        else:
            onb.formul(ws, f"K{r}", f"=I{r}/(1-J{r})", miktar / (1 - fire))
        if elle_fiyat is not None:
            ws[f"M{r}"] = elle_fiyat
        else:
            onb.formul(ws, f"M{r}", f"=IFERROR(VLOOKUP($D{r},'S.ALMA BF'!$A:$F,6,0),0)", liste or 0)
        ws[f"N{r}"] = f"=IFERROR(VLOOKUP($D{r},'S.ALMA BF'!$A:$G,7,0),\"\")"
        ws[f"O{r}"] = f"=IFERROR(VLOOKUP($D{r},'S.ALMA BF'!$A:$E,5,0),\"\")"
        ws[f"P{r}"] = f"=K{r}*M{r}*IF(N{r}=\"S\",IF(O{r}=\"TL\",1+$F$148,IFERROR(VLOOKUP(O{r},$E$150:$F$155,2,0),0)),1)"
        r += 1
    E = lambda satir, metin: ws.__setitem__(f"D{satir}", metin)
    E(100, "HAMMADE - YARDIMCI MALZEME MALİYETİ TOPLAMI"); ws["P100"] = f"=SUM(P7:P{r - 1})"
    E(103, "DİREKT İŞÇİLİK GİDERLERİ")
    E(104, "Mal Kabul ve Fermantasyon Giderleri"); ws["I104"] = u["mk"]
    E(105, "Dolum Doğrudan İşçilik Giderleri"); E(106, "Etiketleme İşçilik Giderleri")
    E(107, "GENEL ÜRETİM GİDERLERİ"); E(108, "Endirekt İşçilik Giderleri"); E(109, "Mal Kabul ve Fermantasyon Genel Üretim Giderleri")
    E(110, "Elektrik Giderleri"); E(111, "Doğalgaz Giderleri"); E(112, "Amortisman Giderleri"); E(113, "Diğer Genel Üretim Giderleri")
    E(114, "GİDER TOPLAMI"); E(116, "TOPLAM BİRİM MALİYET")
    E(118, "PAZARLAMA SATIŞ GİDERLERİ"); E(119, "GENEL YÖNETİM GİDERLERİ")
    ws["K118"] = ws["K119"] = 1
    if u["pyu"]:
        ws["M118"] = "=VLOOKUP($E$146,'Gider Dağıtım'!$B$70:$F$91,5,0)"
        ws["M119"] = "=VLOOKUP($E$146,'Gider Dağıtım'!$B$70:$G$91,6,0)"
        ws["P118"] = "=K118*M118"; ws["P119"] = "=K119*M119"
    else:   # pazarlama/yönetim uygulanmayan ürün (gerçek kitapta 14 sayfa böyle): P118/P119 elle 0
        ws["P118"] = 0; ws["P119"] = 0
    if u.get("elle_elektrik") is not None:   # gider satırında elle birim fiyat (Veri Kontrolü 'Elle girilmiş hücre')
        ws["M110"] = u["elle_elektrik"]
    E(120, "DİĞER GİDERLER TOPLAMI"); E(122, "DİĞER GİDERLER GİYDİRİLMİŞ BİRİM MALİYET")
    E(124, "FİNANSMAN GİDERLERİ")
    for i, (pb, (faiz, ay)) in enumerate(p["faiz"].items()):
        ws[f"I{124 + i}"], ws[f"J{124 + i}"], ws[f"K{124 + i}"] = pb, faiz, ay
    E(130, "FİNANSMAN GİDERİ DAHİL EDİLMİŞ MALİYET")
    E(136, "Süzme Miktar"); ws["E136"] = u["suzme"]
    ws["G137"] = "Satış fiyatı = finansman dahil maliyet × 1,20 (test notu)"
    E(138, "Vardiya Üretim Adedi"); ws["E138"] = u["vardiya"]
    E(140, "Dolum İşçilik Personel Sayısı"); ws["E140"] = u["dolum"]
    E(141, "Etiketleme Adedi (vardiya)"); ws["E141"] = u["etiketleme"]
    E(143, "Etiket İşçilik Personel Sayısı"); ws["E143"] = u["etiket"]
    E(144, "Üretim"); ws["E144"] = u["hat"]
    E(145, "Taze / Turşu"); ws["E145"] = u["sinif"]
    E(146, "Ambalaj"); ws["E146"] = u["hacim"]
    E(147, "Ürün Adı"); ws["E147"] = u["ad"]
    ws["K145"], ws["L145"], ws["L146"], ws["L147"] = "Teklif kâr oranları", *p["teklif"]
    E(148, "Enflasyon"); ws["F148"] = u.get("enflasyon", p["enflasyon"])
    E(149, "Maliyet Sapma"); ws["F149"] = 0.03
    E(150, "Döviz Kurları")
    for i, (pb, kur) in enumerate(p["kur"].items()):
        ws[f"E{150 + i}"], ws[f"F{150 + i}"] = pb, kur
    for col, w in zip("ADEIJKLMNOP", (7, 12, 34, 10, 7, 11, 7, 11, 5, 7, 12)):
        ws.column_dimensions[col].width = w


def uretim_adetleri_sayfasi(ws, satirlar: list[tuple]) -> None:
    ws.title = "Üretim Adetleri"
    ws["A1"] = "ÜRETİM ADETLERİ (TEST)"; ws["A1"].font = KALIN
    # Okuyucu başlığı str.upper() ile karşılaştırır: 'Vardiyalık'.upper() 'VARDIYALIK' olur (İ değil); başlıklar büyük harfle yazılmalı.
    _baslik(ws, 2, ["ÜRÜN KODU", "ÜRÜN ADI", "NET SÜREDEKİ VARDİYALIK KAPASİTE", "NET SÜRE", "TOPLAM SÜREDEKİ KAPASİTE", "TOPLAM SÜRE",
                    "HEDEF VARDİYALIK ÜRETİM", "ORTALAMA İŞÇİ SAYISI"])
    ws.append(["", "", "(adet)", "(saat)", "(adet)", "(saat)", "(adet)", "(kişi)"])
    for s in satirlar:
        ws.append(list(s))
    ws.column_dimensions["B"].width = 30


def uretim_adetleri(degisik: bool = False) -> list[tuple]:
    out = []
    for u in URUNLER:
        hedef = u["vardiya"]
        if degisik and u["kod"] in ("03.99.001", "03.99.004"):
            hedef = int(hedef * (1.1 if u["kod"] == "03.99.001" else 0.9))
        out.append((u["kod"], u["ad"], round(u["vardiya"] * 1.15), 6.5, round(u["vardiya"] * 1.3), 7.5, hedef, u["dolum"] + u["etiket"] + 2))
    if degisik:
        out.append(("03.99.099", "Test Eşleşmeyen Ürün (kartı yok)", 5000, 6.5, 6000, 7.5, 4000, 6))
    return out


def fiyat_kitabi(ad: str, fiyatlar: dict, revize: dict, p: dict, gider_k: dict | None = None, miktar_k: dict | None = None,
                 vardiya_k: dict | None = None) -> Path:
    wb = openpyxl.Workbook()
    onb = Onbellek()
    kapak = wb.active
    kapak.title = "Teklif Kapak"
    kapak["A1"] = "TEST TEKLİF KAPAK SAYFASI (uygulama okumaz; görünüm için)"; kapak["A1"].font = KALIN
    _baslik(kapak, 3, ["Ürün Kodu", "Ürün Adı", "Ambalaj"])
    for u in URUNLER:
        kapak.append([u["kod"], u["ad"], u["hacim"]])
    kapak.column_dimensions["B"].width = 32
    satin_alma_sayfasi(wb.create_sheet(), fiyatlar, revize)
    gider_sayfasi(wb.create_sheet(), onb, gider_k)
    for u in URUNLER:
        uu = dict(u)
        if vardiya_k:
            uu["vardiya"] = round(u["vardiya"] * vardiya_k.get(u["kod"], 1))
        if u["kod"] == "03.99.004":
            uu["elle_elektrik"] = 0.11
        urun_sayfasi(wb.create_sheet(), uu, fiyatlar, p, onb, miktar_k=miktar_k)
    # '(2)' ekli varyant sayfa: içe aktarmada atlanır (özet 'atlanan' listesinde görünmeli)
    urun_sayfasi(wb.create_sheet(), URUNLER[0], fiyatlar, p, onb, ad="001 (2)")
    uretim_adetleri_sayfasi(wb.create_sheet(), uretim_adetleri())
    return _kaydet(wb, ad, onb)


def butce_fiyatlari() -> dict[str, float | None]:
    return {m[0]: m[5] for m in MALZEMELER}


# ======================================================================================= Veri Aktar dosyaları
def fiyat_listesi_revize(rnd: random.Random) -> Path:
    """Malzeme Fiyatları › Fiyat listesi yükle: tek sayfa, S.ALMA BF düzeni. F = bütçe fiyatı, I = revize (8 malzeme)."""
    artis = {"99.10.001": 0.12, "99.10.004": 0.15, "99.11.002": 0.10, "99.11.006": 0.18, "99.20.001": 0.14, "99.20.002": 0.11,
             "99.20.007": 0.20, "99.20.011": 0.40}   # 99.20.011 Streç Film %40 (büyük değişiklik)
    revize = {kod: round(MZ[kod][5] * (1 + a), 2) for kod, a in artis.items()}
    revize["99.20.003"] = 2.30   # kitaptaki revizeyle aynı: değişmez ('aynı' sayılır)
    wb = openpyxl.Workbook()
    satin_alma_sayfasi(wb.active, butce_fiyatlari(), revize)
    return _kaydet(wb, "fiyat-listesi-revize")


def satin_alma_aktarim() -> Path:
    """Veri Aktar › Satın alma fiyat listesi: fiyatsız iki malzemeye fiyat + bir yeni malzeme kartı."""
    yeni = [MZ["99.11.010"][:5] + (68.0, "S"), MZ["99.20.015"][:5] + (0.35, "S"),
            ("99.20.016", "Test Kavanoz 1000 ml", "0008-Ambalaj Malzeme", "AD", "TL", 12.6, "S")]
    wb = openpyxl.Workbook()
    satin_alma_sayfasi(wb.active, {m[0]: m[5] for m in yeni}, {}, malzemeler=yeni)
    return _kaydet(wb, "satin-alma-yeni-malzeme")


def uretim_adetleri_aktarim() -> Path:
    wb = openpyxl.Workbook()
    uretim_adetleri_sayfasi(wb.active, uretim_adetleri(degisik=True))
    return _kaydet(wb, "uretim-adetleri")


def gider_aktarim() -> Path:
    """Elektrik +%15 (yeni çarpan), 720 ml üretim adedi %10 düşük."""
    wb = openpyxl.Workbook()
    onb = Onbellek()
    gider_sayfasi(wb.active, onb, {"elektrik": 1.15, "amb720": 0.9})
    return _kaydet(wb, "gider-dagitim", onb)


def recete_aktarim() -> Path:
    """Veri Aktar › Ürün reçetesi: tek ürün sayfası (004 Domates Sos). Domates 0,55 -> 0,58 kg, şeker satırı çıktı, sarımsak eklendi."""
    u = dict(URUNLER[3])
    u["recete"] = [x for x in u["recete"] if x[1] != "99.11.006"]
    u["recete"] = [(s, k, 0.58 if k == "99.10.004" else m_, f, b, e) for s, k, m_, f, b, e in u["recete"]]
    u["recete"].insert(3, (1, "99.11.004", 0.002, 0.05, None, None))
    wb = openpyxl.Workbook()
    onb = Onbellek()
    urun_sayfasi(wb.active, u, butce_fiyatlari(), BUTCE_PARAM, onb)
    return _kaydet(wb, "urun-recetesi-004", onb)


def stokta_kalan() -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Stokta Kalan"
    _baslik(ws, 1, ["urun_kodu", "stok_adet", "stok_birim_maliyet", "enflasyon", "uretim_adedi"])
    ws.append(["03.99.001", 25000, 15.8, None, None])
    ws.append(["03.99.003", 8000, 17.2, 0.35, 120000])
    ws.append(["03.99.004", 5000, 14.9, None, None])
    return _kaydet(wb, "stokta-kalan")


# Satış fiyatı tabanı: geçen yıl (×0,78) fiyatı bu yılın maliyetine göre bilinçli farklı marjlarla (kârlılık haritası dolu çıksın;
# 03.99.004 maliyetinin altında satılıyor).
SATIS_TABANI = {"03.99.001": 45.2, "03.99.002": 64.0, "03.99.003": 45.8, "03.99.004": 38.9, "03.99.005": 122.8, "03.99.006": 124.4,
                "03.99.007": 46.0}


def satis_gecmisi(rnd: random.Random) -> Path:
    """Haziran 2025 - Ekim 2026 aylık satışlar. 2026-2027 sezonunun 'geçen yılı' = Haziran 2025 - Mayıs 2026."""
    musteriler = (("Test Market A.Ş.", "TL", 1.0), ("Test Toptan Ltd.", "TL", 0.93), ("Test Export GmbH", "USD", None))
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Satış Geçmişi"
    _baslik(ws, 1, ["urun_kodu", "musteri", "tarih", "fiyat", "para_birimi", "adet"])
    n = 0
    for yil, ay in [(2025 + (a > 12), (a - 1) % 12 + 1) for a in range(6, 23)]:
        sezon_k = 0.78 if (yil, ay) < (2026, 6) else 0.95
        for kod, taban in SATIS_TABANI.items():
            for musteri, pb, k in musteriler:
                if pb == "USD" and kod not in ("03.99.001", "03.99.005"):
                    continue
                if pb == "TL" and k < 1 and kod in ("03.99.005",):
                    continue
                fiyat = taban * sezon_k * (k if k else 1 / 38.0) * rnd.uniform(0.97, 1.03)
                adet = rnd.randrange(1500, 9000, 100) * (3 if kod in ("03.99.001", "03.99.004") else 1)
                ws.append([kod, musteri, date(yil, ay, 15), round(fiyat, 4 if pb == "USD" else 2), pb, adet])
                n += 1
    ws.column_dimensions["B"].width = 22
    ws.column_dimensions["C"].width = 12
    for c in ws["C"][1:]:
        c.number_format = "yyyy-mm-dd"
    return _kaydet(wb, "satis-gecmisi")


def liste_fiyatlari() -> Path:
    """Liste Çalışması › Excel'den yükle: Berrak ürünlerinin 2023-2025 liste fiyatları (iki pazar)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Liste Fiyatları"
    _baslik(ws, 1, ["urun_kodu", "yil", "liste_fiyati", "birim_maliyet", "pazar"])
    taban = {"03.99.001": (49.9, 22.0), "03.99.002": (72.9, 35.0), "03.99.007": (52.9, 23.5)}   # 2025 liste, 2025 maliyet
    for kod, (liste, maliyet) in taban.items():
        for yil, k_l, k_m in ((2023, 1 / (1.42 * 1.38), 1 / (1.46 * 1.35)), (2024, 1 / 1.42, 1 / 1.46), (2025, 1.0, 1.0)):
            ws.append([kod, yil, round(liste * k_l, 2), round(maliyet * k_m, 2), "Yurtiçi"])
            ws.append([kod, yil, round(liste * k_l * 0.7, 2), round(maliyet * k_m, 2), "Yurtdışı"])
    return _kaydet(wb, "liste-fiyatlari-gecmis")


def gerceklesen_kitabi(rnd: random.Random) -> Path:
    """Aynı ürünler; fiyatlar bütçeden sapmış (TL S %3-25 artış, Z %-10..+20, döviz %-5..+8), kurlar fiili, enflasyon 0,
    vardiya adedi %-15..+10, gider havuzları %-8..+12."""
    fiyatlar = {}
    for kod, _, _, _, para, f, zs in MALZEMELER:
        if f is None:
            fiyatlar[kod] = None
            continue
        k = rnd.uniform(0.95, 1.08) if para != "TL" else (rnd.uniform(0.90, 1.20) if zs == "Z" else rnd.uniform(1.03, 1.25))
        fiyatlar[kod] = round(f * k, 2 if f >= 10 else 4)
    p = dict(BUTCE_PARAM, enflasyon=0.0, kur={"USD": 44.9, "EUR": 52.3, "GBP": 59.4, "CHF": 55.1})
    gider_k = {ad: round(rnd.uniform(0.92, 1.12), 3) for ad in ("dolum", "endirekt", "diger", "elektrik", "dogalgaz", "yonetim", "pazarlama")}
    vardiya_k = {u["kod"]: round(rnd.uniform(0.85, 1.10), 3) for u in URUNLER}
    miktar_k = {"99.10.001": 1.04, "99.20.001": 1.0, "99.10.004": 1.06}
    return fiyat_kitabi("fiyat-calismasi-gerceklesen", fiyatlar, {}, p, gider_k, miktar_k, vardiya_k)


# ======================================================================================= SMM
TUR = {"0001": "0001-Hammadde", "0008": "0008-Ambalaj Malzeme", "0017": "0017-Yardımcı Malzeme", "0015": "0015-Üretim Yarı Mamulü",
       "0002": "0002-Yarı Mamul", "0003": "0003-Mamul"}
MIZAN = {"0001": "150.01", "0008": "150.02", "0017": "150.03", "0015": "151.01", "0002": "151.02", "0003": "152.01"}
# Aşama ürünleri: kod -> (ad, birim, aşama, tür); reçeteler ana birim (1 KG / 1 AD) başına: [(malzeme, miktar)], fire oranı
SMM_URUN = {
    "01.99.001": ("Test Fermente Hıyar", "KG", 20, "0015"), "01.99.002": ("Test Fermente Kornişon", "KG", 20, "0015"),
    "01.99.003": ("Test Közlenmiş Biber Yarı Mamul", "KG", 20, "0015"), "01.99.004": ("Test Domates Sos Bazı", "KG", 20, "0015"),
    "02.99.001": ("Test Berrak Turşu 370 ml Dolu Kavanoz", "AD", 40, "0002"), "02.99.002": ("Test Berrak Turşu 720 ml Dolu Kavanoz", "AD", 40, "0002"),
    "02.99.003": ("Test Közlenmiş Biber 370 ml Dolu Kavanoz", "AD", 40, "0002"), "02.99.004": ("Test Domates Sos 340 g Dolu Kavanoz", "AD", 40, "0002"),
    "02.99.007": ("Test Berrak Kornişon 370 ml Dolu Kavanoz", "AD", 40, "0002"),
    "03.99.001": ("Test Berrak Turşu 370 ml", "AD", 50, "0003"), "03.99.002": ("Test Berrak Turşu 720 ml", "AD", 50, "0003"),
    "03.99.003": ("Test Közlenmiş Biber 370 ml", "AD", 50, "0003"), "03.99.004": ("Test Domates Sos 340 g", "AD", 50, "0003"),
    "03.99.007": ("Test Berrak Kornişon 370 ml", "AD", 50, "0003"),
}
SMM_RECETE = {
    "01.99.001": ([("99.10.001", 1.08), ("99.11.001", 0.07), ("99.11.009", 0.002)], 0.02),
    "01.99.002": ([("99.10.002", 1.08), ("99.11.001", 0.07), ("99.11.009", 0.002)], 0.02),
    "01.99.003": ([("99.10.003", 1.25)], 0.03),
    "01.99.004": ([("99.10.004", 1.6), ("99.11.006", 0.05), ("99.11.001", 0.015), ("99.11.003", 0.002), ("99.11.005", 0.004)], 0.02),
    "02.99.001": ([("01.99.001", 0.21), ("99.20.001", 1), ("99.20.003", 1), ("99.11.002", 0.03), ("99.11.001", 0.008), ("99.11.003", 0.0005)], 0.01),
    "02.99.002": ([("01.99.001", 0.42), ("99.20.002", 1), ("99.20.004", 1), ("99.11.002", 0.06), ("99.11.001", 0.016)], 0.01),
    "02.99.003": ([("01.99.003", 0.20), ("99.20.001", 1), ("99.20.003", 1), ("99.11.002", 0.02), ("99.11.007", 0.01), ("99.11.004", 0.003)], 0.01),
    "02.99.004": ([("01.99.004", 0.34), ("99.20.010", 1), ("99.20.003", 1), ("99.11.008", 0.0003)], 0.01),
    "02.99.007": ([("01.99.002", 0.20), ("99.20.001", 1), ("99.20.003", 1), ("99.11.002", 0.03), ("99.11.001", 0.008), ("99.11.005", 0.001)], 0.01),
    "03.99.001": ([("02.99.001", 1), ("99.20.005", 1), ("99.20.007", 0.0833), ("99.20.011", 0.002)], 0.003),
    "03.99.002": ([("02.99.002", 1), ("99.20.006", 1), ("99.20.008", 0.1667), ("99.20.011", 0.003)], 0.003),
    "03.99.003": ([("02.99.003", 1), ("99.20.005", 1), ("99.20.007", 0.0833), ("99.20.011", 0.002)], 0.003),
    "03.99.004": ([("02.99.004", 1), ("99.20.005", 1), ("99.20.007", 0.0833), ("99.20.011", 0.002)], 0.003),
    "03.99.007": ([("02.99.007", 1), ("99.20.005", 1), ("99.20.007", 0.0833), ("99.20.011", 0.002)], 0.003),
}
SMM_MALZEME = [m for m in MALZEMELER if m[5] is not None and m[0] not in ("99.10.005", "99.10.006", "99.10.007", "99.20.009", "99.20.012",
                                                                         "99.20.013", "99.20.014")]
# Aylık üretim (mamul, AD) ve 40 / 20 aşamasının üretimi bundan türetilir
URETIM = {"ekim": {"03.99.001": 320000, "03.99.002": 120000, "03.99.003": 90000, "03.99.004": 110000, "03.99.007": 80000},
          "kasim": {"03.99.001": 300000, "03.99.002": 105000, "03.99.003": 85000, "03.99.004": 118000, "03.99.007": 76000}}
KUR_AY = {"ekim": {"USD": 42.8, "EUR": 49.6}, "kasim": {"USD": 43.3, "EUR": 50.2}}
GIDER_MIZAN = {"ekim": {"710": 0, "720": 1850000, "730": 2450000, "760": 920000, "770": 1310000},
               "kasim": {"710": 0, "720": 1920000, "730": 2450000, "760": 880000, "770": 1290000}}
DAGITIM = {"20_stok": 0, "20_uretim": 600000, "40_stok_iscilik": 0, "40_iscilik": 1250000, "40_stok_gug": 0, "40_gug": 1900000,
           "50_stok": 0, "50_uretim": 550000}   # toplam 4.300.000 = Ekim 720 + 730
SURELER = {   # mamul -> (yarı mamul, vardiya üretim, dolum işçi, etiket işçi, dolum sn, dolum adam sn, etiket sn, etiket adam sn)
    "03.99.001": ("02.99.001", 18000, 12, 3, 1.5, 18.0, 0.9, 2.7), "03.99.002": ("02.99.002", 12000, 12, 3, 2.25, 27.0, 1.35, 4.05),
    "03.99.003": ("02.99.003", 15000, 14, 3, 1.8, 25.2, 0.9, 2.7), "03.99.004": ("02.99.004", 20000, 10, 3, 1.35, 13.5, 0.9, 2.7),
    "03.99.007": ("02.99.007", 18000, 12, 3, 1.5, 18.0, 0.9, 2.7),
}
IADE = {"ekim": {"99.20.001": 2400, "99.10.001": 1800}, "kasim": {"99.20.003": 3000}}
HM_SATIS = {"ekim": {"99.11.001": 1500}, "kasim": {}}
SAHIT = {"ekim": {"03.99.001": 120, "03.99.004": 60}, "kasim": {"03.99.001": 110, "03.99.002": 40}}
FINANSMAN = {"ekim": 85000, "kasim": 0}


def _q(x, n=4) -> Decimal:
    return D(str(x)).quantize(D(1).scaleb(-n), rounding=ROUND_HALF_UP)


def smm_ay(ay: str, onceki: dict | None, rnd: random.Random) -> dict:
    """Bir ayın kaynak verisi: kod -> {dbs_m, dbs_t, alim_m, alim_t, iade_m, iade_t, uretim, sayim, satis, sahit}."""
    u50 = URETIM[ay]
    uretim = dict(u50)
    for kod, n in u50.items():
        uretim["02" + kod[2:]] = round(n * 1.006)
    ihtiyac: dict[str, float] = {}

    def tuket(ana, n):
        satirlar, fire = SMM_RECETE[ana]
        for mal, mik in satirlar:
            ihtiyac[mal] = ihtiyac.get(mal, 0) + n * mik * (1 + fire)
    for kod in [k for k in uretim if k.startswith("02")] + list(u50):
        tuket(kod, uretim[kod])
    for kod in ("01.99.001", "01.99.002", "01.99.003", "01.99.004"):
        uretim[kod] = int(round(ihtiyac.get(kod, 0) * 1.01, -2))
        tuket(kod, uretim[kod])
    kur = KUR_AY[ay]
    veri = {}
    kodlar = [m[0] for m in SMM_MALZEME] + list(SMM_URUN)
    for kod in kodlar:
        tuketim = ihtiyac.get(kod, 0)
        uretilen = uretim.get(kod, 0)
        if onceki is None:
            if kod in MZ:
                dbs_m = round(tuketim * rnd.uniform(0.25, 0.6), 1 if MZ[kod][3] != "AD" else 0)
                dbs_f = MZ[kod][5] * (kur.get(MZ[kod][4], 1) - (0.6 if MZ[kod][4] != "TL" else 0)) * 0.96
            else:
                dbs_m = round(uretilen * (0.15 if kod.startswith("03") else 0.03))
                dbs_f = {"01": 24.0, "02": 17.5, "03": 19.0}[kod[:2]] * (2 if "002" in kod[-3:] and kod[:2] != "01" else 1)
            dbs_t = float(_q(dbs_m * dbs_f, 2))
        else:
            dbs_m, dbs_t = onceki[kod]["sayim"], None
        x = {"dbs_m": dbs_m, "dbs_t": dbs_t, "alim_m": 0, "alim_t": 0.0, "iade_m": 0, "iade_t": 0.0, "uretim": uretilen, "satis": 0,
             "sahit": SAHIT[ay].get(kod, 0)}
        if kod in MZ:
            fiyat = MZ[kod][5] * kur.get(MZ[kod][4], 1) * (1.06 if ay == "ekim" else 1.09) * rnd.uniform(0.98, 1.03)
            if MZ[kod][6] == "Z":
                fiyat /= 1.0
            hedef_stok = tuketim * rnd.uniform(0.3, 0.5)
            alim = max(0.0, tuketim + hedef_stok - dbs_m)
            alim = round(alim, 0 if MZ[kod][3] == "AD" else 1)
            x["alim_m"], x["alim_t"] = alim, float(_q(alim * fiyat, 2))
            x["fiyat"] = fiyat
            if kod in IADE[ay]:
                x["iade_m"] = IADE[ay][kod]; x["iade_t"] = float(_q(IADE[ay][kod] * fiyat, 2))
            x["satis"] = HM_SATIS[ay].get(kod, 0)
            # sayım: elde olan − reçeteye göre tüketim × (1 ± sapma)  -> sarf farkı ekranında görünür fark
            sapma = {"99.10.001": 0.035, "99.20.001": -0.012, "99.11.002": 0.06, "99.10.004": 0.025}.get(kod, rnd.uniform(-0.004, 0.006))
            sayim = dbs_m + alim - x["iade_m"] - x["satis"] - tuketim * (1 + sapma)
            x["sayim"] = round(max(sayim, 0), 0 if MZ[kod][3] == "AD" else 1)
        else:
            satilan = uretilen * 0.93 if kod.startswith("03") else 0
            x["sayim"] = round(max(dbs_m + uretilen - tuketim - satilan - x["sahit"], 0), 0 if SMM_URUN[kod][1] == "AD" else 1)
        veri[kod] = x
    return {"veri": veri, "uretim": uretim}


def _ad(kod):
    return MZ[kod][1] if kod in MZ else SMM_URUN[kod][0]


def _birim(kod):
    return MZ[kod][3] if kod in MZ else SMM_URUN[kod][1]


def _tur(kod):
    return MZ[kod][2][:4] if kod in MZ else SMM_URUN[kod][3]


def _alim_sayfasi(ws, ay_veri, ay_ad: str) -> None:
    ws.title = "HM-YM ALIŞ SATIŞ"
    ws["A1"] = f"HAMMADDE - YARI MAMUL ALIŞ / SATIŞ RAPORU · {ay_ad} (TEST)"; ws["A1"].font = KALIN
    b = ["Fiş No", "Malzeme(Sınıf)Kodu", "Malzeme Açıklaması", "Tarih", "Depo", "Birim", "Giriş Miktarı", "Birim Fiyat", "Para Birimi",
         "Kur", "Tutar (TL)", "Çıkış Miktarı", None, None, None, None, None, None, None, "Hareket Türü"]
    _baslik(ws, 2, b)
    n = 1
    for kod, x in ay_veri.items():
        if x["alim_m"]:
            parca = 2 if x["alim_m"] > 1000 else 1
            m1 = round(x["alim_m"] / parca, 1)
            for i in range(parca):
                mik = m1 if i < parca - 1 else round(x["alim_m"] - m1 * (parca - 1), 1)
                tutar = round(x["alim_t"] * mik / x["alim_m"], 2) if i < parca - 1 else round(x["alim_t"] - round(x["alim_t"] * m1 / x["alim_m"], 2) * (parca - 1), 2)
                ws.append([f"ALS-{n:05d}", kod, _ad(kod), None, "Merkez", _birim(kod), _sayi(mik), round(tutar / mik, 4) if mik else None,
                           MZ[kod][4], None, tutar, None] + [None] * 7 + ["Alış"])
                n += 1
        if x["satis"]:
            ws.append([f"STS-{n:05d}", kod, _ad(kod), None, "Merkez", _birim(kod), None, None, "TL", None, None, x["satis"]] + [None] * 7 + ["Satış"])
            n += 1
    ws.column_dimensions["B"].width = 18; ws.column_dimensions["C"].width = 34


def _iade_sayfasi(ws, ay_veri) -> None:
    ws.title = "İADELER"
    ws["A1"] = "ALIM İADELERİ (TEST)"; ws["A1"].font = KALIN
    _baslik(ws, 2, ["Malzeme (Sınıf) Kodu", "Malzeme Açıklaması", "Tarih", "Fiş No", "Birim", "Tedarikçi", "Not", "İade Miktarı", "İade Tutarı"])
    for kod, x in ay_veri.items():
        if x["iade_m"]:
            ws.append([kod, _ad(kod), None, "IAD-001", _birim(kod), "Test Tedarikçi A.Ş.", None, x["iade_m"], x["iade_t"]])
    ws.column_dimensions["B"].width = 30


def _uretim_sayfasi(ws, uretim: dict) -> None:
    ws.title = "ÜRETİM"
    ws["A1"] = "ÜRETİM MİKTARLARI (TEST)"; ws["A1"].font = KALIN
    _baslik(ws, 2, ["MalzemeKodu", "Malzeme Açıklaması", "Birim"] + [None] * 11 + ["Üretim Miktarı"])
    for kod, n in uretim.items():
        ws.append([kod, _ad(kod), _birim(kod)] + [None] * 11 + [n])
    ws.column_dimensions["B"].width = 38


def _sayim_sayfasi(ws, ay_veri) -> None:
    ws.title = "DSS"
    ws["A1"] = "DÖNEM SONU SAYIM (TEST)"; ws["A1"].font = KALIN
    _baslik(ws, 2, ["StokKartıKodu", "StokKartıAdı", "Sayım Miktarı", "Birim", "Tutar"])
    for kod, x in ay_veri.items():
        if x["sayim"]:
            ws.append([kod, _ad(kod), x["sayim"], _birim(kod), None])
    ws.column_dimensions["B"].width = 38


def _sahit_sayfasi(ws, ay_veri) -> None:
    ws.title = "ŞAHİT"
    ws["A1"] = "ŞAHİT NUMUNE (TEST)"; ws["A1"].font = KALIN
    _baslik(ws, 2, ["StokKodu", "StokAdı", "Birim", None, None, None, None, None, None, "Toplam Miktar"])
    for kod, x in ay_veri.items():
        if x["sahit"]:
            ws.append([kod, _ad(kod), _birim(kod)] + [None] * 6 + [x["sahit"]])


def _gider_mizan_sayfasi(ws, ay: str) -> None:
    ws.title = "GİDER MİZAN"
    _baslik(ws, 1, ["Hesap Kodu", "Hesap Adı", "Borç", "Alacak", None, None, "Bakiye"])
    adlar = {"710": "Direkt İlk Madde ve Malzeme Giderleri", "720": "Direkt İşçilik Giderleri", "730": "Genel Üretim Giderleri",
             "760": "Pazarlama Satış ve Dağıtım Giderleri", "770": "Genel Yönetim Giderleri"}
    for h, v in GIDER_MIZAN[ay].items():
        ws.append([h, adlar[h], v, 0, None, None, v])
        if h in ("720", "730"):   # alt hesaplar (3 haneli olmayan satırlar okunmaz)
            ws.append([f"{h}.01", adlar[h] + " - Üretim", round(v * 0.7, 2), 0, None, None, round(v * 0.7, 2)])
            ws.append([f"{h}.02", adlar[h] + " - Diğer", round(v * 0.3, 2), 0, None, None, round(v * 0.3, 2)])
    ws.column_dimensions["B"].width = 40


def _stok_mizan_sayfasi(ws, bakiyeler: dict[str, float], tarih: str) -> None:
    ws.title = "STOK MİZAN"
    ws["A1"] = "STOK MİZANI (TEST)"; ws["A1"].font = KALIN
    _baslik(ws, 2, ["Hesap Kodu", "Hesap Adı", "Borç", "Alacak", None, None, "Bakiye", None, "Fiş Tarihi"])
    ws["J2"] = tarih
    adlar = {"150.01": "Hammadde", "150.02": "Ambalaj Malzemesi", "150.03": "Yardımcı Malzeme", "151.01": "Üretim Yarı Mamulü",
             "151.02": "Yarı Mamul", "152.01": "Mamul"}
    for h, v in bakiyeler.items():
        ws.append([h, adlar[h], v, 0, None, None, v])
    ws.column_dimensions["B"].width = 26


# Stok mizanı bakiyeleri: kuru koşudaki dönem sonu stok (sayım) değerlemesine yakın tutulmuştur (bilinçli küçük farklarla).
# Ekim 150 toplamı, senaryodaki sayım düzeltmesinden (Kavanoz 370 ml +500) SONRAKİ değerlemeye eşittir: düzeltmeden önce fark 3.230,60 TL.
STOK_MIZAN = {"ekim": {"150.01": 2000000.00, "150.02": 2500000.00, "150.03": 616894.84, "151.01": 500000.00, "151.02": 246056.16,
                       "152.01": 3850000.00},
              "kasim": {"150.01": 2200000.00, "150.02": 2800000.00, "150.03": 656106.63, "151.01": 600000.00, "151.02": 289474.62,
                        "152.01": 5290000.00}}   # boşsa _stok_mizan_tahmini kullanılır


def _stok_mizan_tahmini(ay_veri) -> dict[str, float]:
    """Kaba tahmin: sayım × (malzemede alım fiyatı, üründe tipik birim maliyet). Kuru koşuda gerçek değerleme ile kıyaslanır."""
    t: dict[str, float] = {h: 0.0 for h in ("150.01", "150.02", "150.03", "151.01", "151.02", "152.01")}
    for kod, x in ay_veri.items():
        f = x.get("fiyat") or {"01": 22.0, "02": 16.0, "03": 17.5}[kod[:2]]
        t[MIZAN[_tur(kod)]] += x["sayim"] * f
    return {h: round(v, 2) for h, v in t.items()}


def _tablo_degerleri(ay_veri, finansman: float) -> dict[str, tuple]:
    """Excel TABLO satırı (smm_servisi.stok_hesabi ile aynı formül): DBS miktar, alım tutarı, ort. fiyat, DSS tutarı, sarf, sarf maliyeti."""
    alim_top = sum(D(str(x["alim_t"])) for x in ay_veri.values())
    out = {}
    for kod, x in ay_veri.items():
        dbs_m, dbs_t = D(str(x["dbs_m"])), D(str(x["dbs_t"]))
        alim_m, alim_t = D(str(x["alim_m"])), D(str(x["alim_t"]))
        fin = alim_t / alim_top * D(str(finansman)) if alim_top and finansman else D(0)
        top_m, top_t = dbs_m + alim_m, dbs_t + alim_t + fin
        ort = top_t / top_m if top_m else D(0)
        sayim = D(str(x["sayim"]))
        sarf = top_m - D(str(x["iade_m"])) - sayim
        out[kod] = (float(dbs_m), float(alim_t), float(ort), float(sayim * ort), float(sarf), float(sarf * ort))
    return out


def smm_ekim_kitabi(ekim: dict) -> Path:
    v = ekim["veri"]
    wb = openpyxl.Workbook()
    onb = Onbellek()
    env = wb.active
    env.title = "ENVANTER"
    env["A1"] = "ENVANTER (TEST) · Ekim 2026"; env["A1"].font = KALIN
    _baslik(env, 2, ["Stok Kodu", "Stok Adı", "Birim", "Malzeme Türü", "Mizan Kodu"] + [None] * 10 + ["Üretim Birim Fiyatı"])
    for kod in v:
        satir = [kod, _ad(kod), _birim(kod), TUR[_tur(kod)], MIZAN[_tur(kod)]]
        env.append(satir)
        if kod in SMM_URUN:
            r = env.max_row
            sayfa, sut = {20: ("20 KOD", 21), 40: ("40 KOD", 23), 50: ("50 KOD", 23)}[SMM_URUN[kod][2]]
            env[f"P{r}"] = f"=IFERROR(VLOOKUP(A{r},'{sayfa}'!$A:$W,{sut},0),0)"
    env.column_dimensions["B"].width = 38; env.column_dimensions["D"].width = 24
    dbs = wb.create_sheet("DBS")
    dbs["A1"] = "DÖNEM BAŞI STOK · 1 Ekim 2026 (TEST)"; dbs["A1"].font = KALIN
    _baslik(dbs, 2, ["Stok Kodu", "Stok Adı", "Miktar", "Tutar"])
    for kod, x in v.items():
        if x["dbs_m"]:
            dbs.append([kod, _ad(kod), x["dbs_m"], x["dbs_t"]])
    dbs.column_dimensions["B"].width = 38
    _alim_sayfasi(wb.create_sheet(), v, "Ekim 2026")
    _iade_sayfasi(wb.create_sheet(), v)
    _uretim_sayfasi(wb.create_sheet(), ekim["uretim"])
    _sayim_sayfasi(wb.create_sheet(), v)
    _sahit_sayfasi(wb.create_sheet(), v)
    tablo = wb.create_sheet("TABLO")
    tablo["A1"] = "STOK TABLOSU (TEST)"; tablo["A1"].font = KALIN
    tablo["I1"] = "Finansman:"; tablo["J1"] = FINANSMAN["ekim"]
    _baslik(tablo, 2, ["", "Stok Kodu", "Stok Adı", "DBS Miktar", None, None, None, "Alım Tutarı"] + [None] * 6 + ["Ortalama Fiyat"]
            + [None] * 5 + ["DSS Tutarı", "Sarf Miktarı", "Sarf Maliyeti"])
    for kod, t in _tablo_degerleri(v, FINANSMAN["ekim"]).items():
        satir = [None, kod, _ad(kod), t[0], None, None, None, t[1]] + [None] * 6 + [t[2]] + [None] * 5 + [t[3], t[4], t[5]]
        tablo.append(satir)
    for asama, (sayfa, fire_i) in {20: ("20 KOD", 23), 40: ("40 KOD", 31), 50: ("50 KOD", 25)}.items():
        ws = wb.create_sheet(sayfa)
        havuz = {20: {16: "20_stok", 19: "20_uretim"}, 40: {16: "40_stok_iscilik", 21: "40_iscilik", 26: "40_stok_gug", 29: "40_gug"},
                 50: {16: "50_stok", 21: "50_uretim"}}[asama]
        ws["A1"] = f"{sayfa} · aşama {asama} (TEST)"; ws["A1"].font = KALIN
        for sut, ad in havuz.items():
            ws.cell(row=1, column=sut, value=DAGITIM[ad])
        b = ["Ana Kod", "Ana Ad", "Ana Miktar", "Ana Birim", "Malzeme Kodu", "Malzeme Adı", "Miktar", "Birim"]
        b += [None] * (fire_i - len(b)) + ["Fire Oranı"]
        _baslik(ws, 2, b)
        for ana, (satirlar, fire) in SMM_RECETE.items():
            if SMM_URUN[ana][2] != asama:
                continue
            for mal, mik in satirlar:
                satir = [ana, SMM_URUN[ana][0], 1, SMM_URUN[ana][1], mal, _ad(mal), mik, _birim(mal)]
                satir += [None] * (fire_i - len(satir)) + [fire]
                ws.append(satir)
        ws.column_dimensions["B"].width = 34; ws.column_dimensions["F"].width = 30
    s51 = wb.create_sheet("51")
    s51["A1"] = "ÜRETİM SÜRELERİ (TEST)"; s51["A1"].font = KALIN
    _baslik(s51, 2, ["", "Mamul Kodu", "Yarı Mamul Kodu", "Ürün Adı", None, None, None, None, None, "Vardiya Üretim", None, "Dolum İşçi",
                     "Etiket İşçi", None, None, "Dolum sn", "Dolum adam sn", "Etiket sn", "Etiket adam sn"])
    for mamul, (yari, vard, di, ei, dsn, dasn, esn, easn) in SURELER.items():
        s51.append([None, mamul, yari, SMM_URUN[mamul][0], None, None, None, None, None, vard, None, di, ei, None, None, dsn, dasn, esn, easn])
    _gider_mizan_sayfasi(wb.create_sheet(), "ekim")
    _stok_mizan_sayfasi(wb.create_sheet(), STOK_MIZAN["ekim"] or _stok_mizan_tahmini(v), "31.10.2026")
    return _kaydet(wb, "smm-ekim-2026", onb)


def smm_kasim_dosyalari(kasim: dict) -> list[Path]:
    v = kasim["veri"]
    out = []
    for ad, fn in (("alim-satis", lambda ws: _alim_sayfasi(ws, v, "Kasım 2026")), ("iadeler", lambda ws: _iade_sayfasi(ws, v)),
                   ("uretim", lambda ws: _uretim_sayfasi(ws, kasim["uretim"])), ("sayim", lambda ws: _sayim_sayfasi(ws, v)),
                   ("sahit-numune", lambda ws: _sahit_sayfasi(ws, v)), ("gider-mizan", lambda ws: _gider_mizan_sayfasi(ws, "kasim")),
                   ("stok-mizan", lambda ws: _stok_mizan_sayfasi(ws, STOK_MIZAN["kasim"] or _stok_mizan_tahmini(v), "30.11.2026"))):
        wb = openpyxl.Workbook()
        fn(wb.active)
        out.append(_kaydet(wb, f"smm-kasim-2026-{ad}"))
    return out


def canias_receteleri() -> Path:
    """Reçeteler › Canias ürün ağacı dökümü (TBLRESULT). Tüketim malzemesi boş satır = ürün başlığı. 03.99.001'in '01' alternatifi
    (koli 12'li yerine 6'lı) seçim denemesi içindir."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "TBLRESULT"
    _baslik(ws, 1, ["Alternatif Numarası", "Malzeme Kodu", "Malzeme Açıklaması", "Satır No", "Ürün Ağacı Kalem Tipi", "Tüketim Malzeme Kodu",
                    "Tüketim Malzeme Adı", "Tüketim Miktarı", "Tüketim Birimi", "Fire Oranı", "Fireli Miktar"])

    def yaz(ana, alt, satirlar, fire):
        ws.append([alt, ana, SMM_URUN[ana][0], 0, None, None, None, None, None, None, None])
        for i, (mal, mik) in enumerate(satirlar, 1):
            ws.append([alt, ana, SMM_URUN[ana][0], i * 10, 1 if mal in SMM_URUN else 2, mal, _ad(mal), mik, _birim(mal), fire * 100,
                       _sayi(round(mik * (1 + fire), 6))])
    for ana, (satirlar, fire) in SMM_RECETE.items():
        yaz(ana, "00", satirlar, fire)
        if ana == "03.99.001":
            yaz(ana, "01", [(m_, k) if m_ != "99.20.007" else ("99.20.008", 0.1667) for m_, k in satirlar], fire)
    for col, w in zip("BCFG", (12, 38, 14, 34)):
        ws.column_dimensions[col].width = w
    return _kaydet(wb, "smm-receteler-canias")


# ======================================================================================= ana
def main() -> None:
    CIKTI.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(TOHUM)
    dosyalar = [
        fiyat_kitabi("fiyat-calismasi-butce", butce_fiyatlari(), REVIZE_KITAP, BUTCE_PARAM),
        fiyat_listesi_revize(rnd), satin_alma_aktarim(), uretim_adetleri_aktarim(), gider_aktarim(), recete_aktarim(),
        stokta_kalan(), satis_gecmisi(rnd), liste_fiyatlari(), gerceklesen_kitabi(rnd),
    ]
    rnd_smm = random.Random(TOHUM + 1)
    ekim = smm_ay("ekim", None, rnd_smm)
    kasim = smm_ay("kasim", ekim["veri"], rnd_smm)
    dosyalar += [smm_ekim_kitabi(ekim), canias_receteleri()] + smm_kasim_dosyalari(kasim)
    for d in dosyalar:
        print(f"yazıldı: {d.relative_to(BURASI.parent)}")
    print(f"{len(dosyalar)} dosya")


if __name__ == "__main__":
    sys.exit(main())
