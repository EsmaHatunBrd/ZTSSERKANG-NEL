"""Sezon senaryosu için UYDURMA test Excel'lerini ve beklenen sapmaları üretir (gerçek şirket verisi yok).

Hikâye (docs/test-dongusu/11-16-2026-sezon-senaryosu.md): 2026-2027 sezonu.
- Eylül, öngörü: bütçe kitabı (enflasyon %25, USD 42,00, EUR 48,00, satış kârı %20, teklif kârları %20/%17/%14). Yıllık adetler
  geçen yılın satış geçmişinden gelir (uygulama yıllık adedi satış geçmişinden alır).
- Kasım, şok: revize fiyat listesi YALNIZ "Test Kavanoz 370 ml" +%15; USD kuru +%8. Başka hiçbir fiyat değişmez.
- Sezon sonu, gerçekleşen kitabı: bütçeye göre YALNIZ dört bilinen sapma:
    (a) kur:   USD +%8, EUR +%5
    (b) fiyat: kavanoz 370 ml +%15 (şokla aynı), Test Kapya Biber −%10
    (c) fire:  03.99.002'de Test Sirke firesi %2 -> %5
    (d) adet:  03.99.007'de vardiya üretim adedi hedefin %80'i (18.000 -> 14.400)
  Diğer her şey bütçeyle aynıdır.
- SMM: Ekim tam SMM Excel'i (alımlar bütçenin maliyete yansıttığı TL fiyatla), Kasım aylık kaynakları (kavanoz +%15, USD +%8);
  üretim = yıllık adedin 1/12'si; 720/730 bütçe birim işçilik/GÜG x Ekim üretimi; dağıtılmayan %5; Ekim'de Test Taze Hıyar sayımı
  3.000 kg eksik (bilinçli sayım farkı).

Beklenen sapmalar: üretici kendi BAĞIMSIZ maliyet hesabıyla (Excel ürün sayfası formülleri; uygulama kodu kullanılmaz) bütçe,
güncel (şok sonrası) ve gerçekleşen birim maliyetleri ve uygulamanın sapma ayrıştırma sırasıyla (fiyat -> reçete -> üretim -> gider ->
kur -> enflasyon -> diğer; zincirleme ikame) ürün ürün etkileri hesaplar: test-dongusu/11-16-2026-beklenen-sapmalar.json.

Çıktı: test-dongusu/excel/11-16-2026-sezon-*.xlsx (eski senaryonun 11-16-2026-*.xlsx dosyalarına dokunulmaz). Yeniden çalıştırılabilir;
rastgelelik yoktur.

Biçimler uygulamanın okuyucularından alınmıştır (kod değişirse burası da güncellenmeli):
- Fiyat Çalışması tam kitabı: fiyat_motoru/excel_okuyucu.py, backend/servisler/import_servisi.py.
- Veri Aktar: aktarim_servisi.py (satın alma), satis_okuyucu.py / liste_servisi.py.
- SMM: smm_servisi.py (tam SMM Excel'i), smm_veri_servisi.py (aylık kaynaklar), smm_recete_servisi.py (Canias).

Formül hücreleri: openpyxl formülün son hesaplanmış değerini yazamaz; uygulama ise değeri okur. Okunan formül hücrelerinin önbellek
değeri kaydedildikten sonra xlsx XML'ine eklenir (_onbellek_ekle). Kitap 'açılışta yeniden hesapla' işaretlidir.

Kullanım (proje kökünden):  .venv\\Scripts\\python.exe test-dongusu\\uret.py
"""
import json
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
ON = "11-16-2026-sezon-"
BEKLENEN = BURASI / "11-16-2026-beklenen-sapmalar.json"
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
    ("99.11.010", "Test Biber Salçası", "0001-Hammadde", "KG", "TL", None, "S"),          # fiyatsız: satın alma tamamlar (68,00)
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
    ("99.20.015", "Test Shrink Kılıf", "0008-Ambalaj Malzeme", "AD", "TL", None, "S"),    # fiyatsız: satın alma tamamlar (0,35)
]
MZ = {m[0]: m for m in MALZEMELER}
EKSIK_FIYATLAR = {"99.11.010": 68.0, "99.20.015": 0.35}   # satın almanın sezon başında tamamladığı iki fiyat

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
         vardiya=20000, dolum=10, etiketleme=30000, etiket=3, mk=0.55, pyu=True, elle_elektrik=0.11, recete=[
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
         vardiya=3000, dolum=6, etiketleme=0, etiket=0, mk=1.6, pyu=False, recete=[
             (1, "99.10.001", 0.7, 0.05, None, None), (1, "99.10.006", 0.35, 0.05, None, None), (1, "99.10.007", 0.45, 0.05, None, None),
             (1, "99.11.001", 0.12, 0.02, None, None), (1, "99.11.002", 0.25, 0.02, None, None), (1, "99.20.009", 1, 0.01, None, None)]),
    dict(kod="03.99.007", sayfa="007", ad="Test Berrak Kornişon 370 ml", hat="Kavanoz Hattı", sinif="Turşu/Turşu", hacim=370, suzme=0.2,
         vardiya=18000, dolum=12, etiketleme=30000, etiket=3, mk=0.22, pyu=True, recete=[
             (1, "01.99.002", 0.2, 0, None, None), (2, "99.10.002", 0.21, 0.04, None, None), (2, "99.11.001", 0.014, 0.02, None, None),
             (2, "99.11.009", 0.0004, 0, None, None),
             (1, "99.11.002", 0.03, 0.02, None, None), (1, "99.11.005", 0.0008, 0, None, None), (1, "99.20.001", 1, 0.01, None, None),
             (1, "99.20.003", 1, 0.01, None, None), (1, "99.20.005", 1, 0.01, None, None), (1, "99.20.007", 1 / 12, 0, None, None)]),
]
UR = {u["kod"]: u for u in URUNLER}

# ---------------------------------------------------------------- hikâyenin sabitleri
BUTCE_PARAM = dict(enflasyon=0.25, kur={"USD": 42.0, "EUR": 48.0, "GBP": 55.0, "CHF": 50.0},
                   faiz={"TL": (0.40, 6), "USD": (0.06, 6), "EUR": (0.06, 6)}, teklif=(0.20, 0.17, 0.14))
KAVANOZ, BIBER, SIRKE = "99.20.001", "99.10.003", "99.11.002"
SOK_KAVANOZ = 0.15                      # Kasım revize listesi: kavanoz 370 ml +%15
SOK_USD = 0.08                          # Kasım: USD +%8
GERCEK_KUR = {"USD": 0.08, "EUR": 0.05}  # gerçekleşen kurlar bütçeden
GERCEK_FIYAT = {KAVANOZ: 0.15, BIBER: -0.10}
FIRE_URUN, FIRE_MALZEME, FIRE_ONCE, FIRE_SONRA = "03.99.002", SIRKE, 0.02, 0.05
ADET_URUN, ADET_ORANI = "03.99.007", 0.80
SOK_TARIHI = date(2026, 11, 1)

# Yıllık adet = geçen yıl (Haziran 2025 - Mayıs 2026) satış adedi; ayda 1/12'si satıldı. SMM aylık üretimi de aynı (yıllığın 1/12'si).
YILLIK_ADET = {"03.99.001": 3_600_000, "03.99.002": 1_440_000, "03.99.003": 1_080_000, "03.99.004": 1_320_000, "03.99.005": 480_000,
               "03.99.006": 120_000, "03.99.007": 960_000}
MUSTERI_PAYI = (("Test Market A.Ş.", D("0.6")), ("Test Toptan Ltd.", D("0.4")))
# Geçen yıl satış fiyatı = bütçe birim maliyeti x bu çarpan (0,05'e yuvarlı): kârlılık haritasında dört bölge de dolsun;
# 03.99.004 maliyetinin altında satılıyor.
SATIS_CARPANI = {"03.99.001": D("1.18"), "03.99.002": D("1.08"), "03.99.003": D("1.12"), "03.99.004": D("0.95"), "03.99.005": D("1.30"),
                 "03.99.006": D("1.06"), "03.99.007": D("1.15")}


def _sayi(x):
    """Float gürültüsüz yazım: 0.1+0.2 gibi artıkları at."""
    if isinstance(x, float):
        r = round(x, 10)
        return int(r) if r == int(r) and abs(r) < 1e15 else r
    return x


def _d(x) -> Decimal:
    """Excel hücresine yazılan değerin okunduğu hali (float -> _sayi -> str)."""
    return D(str(_sayi(x)))


def _q(x, n=4) -> Decimal:
    return D(str(x)).quantize(D(1).scaleb(-n), rounding=ROUND_HALF_UP)


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


# ======================================================================================= bağımsız maliyet hesabı (Excel ürün sayfası)
SANIYE = D("7.5") * 3600           # vardiya 7,5 saat (Excel 27000)
HATLAR = (("Kavanoz Hattı", D("0.55"), D(18000000)), ("Teneke Hattı", D("0.25"), D(6000000)), ("Sos Hattı", D("0.20"), D(6000000)))
SINIFLAR = (("Taze/Taze", D("0.2"), D(1000000)), ("Taze/Turşu", D("0.3"), D(1500000)), ("Turşu/Turşu", D("0.5"), D(2500000)))
AMBALAJ = [("370 ml", 370, 9000000, 1), ("720 ml", 720, 4000000, 1.6), ("340 g", 340, 3000000, 0.9), ("500 g", 500, 1500000, 1.2),
           ("2,5 kg", 2.5, 600000, 4)]
HAVUZ = dict(dolum=D(6000000) * D("1.35") * D("1.2"), dolum_sn=D(360000000), mal_kabul=D(2400000), etiket=D(1800000), etiket_sn=D(90000000),
             endirekt=D(4000000) * D("1.25"), endirekt_sn=D(30000000), mal_kabul_gug=D(1200000), diger=D(3200000) * D("1.25"),
             diger_sn=D(30000000), elektrik=D(2600000) * D("1.4"), dogalgaz=D(1000000) * D("1.5"), amortisman=D(6000000),
             yonetim=D(8000000) * D("1.3"), pazarlama=D(10000000) * D("1.25"))


def gider_oranlari() -> dict:
    h = HAVUZ
    agirlik = sum((D(adet) * _d(kat) for _, _, adet, kat in AMBALAJ), D(0))
    return {"dolum": h["dolum"] / h["dolum_sn"], "etiket": h["etiket"] / h["etiket_sn"], "endirekt": h["endirekt"] / h["endirekt_sn"],
            "diger": h["diger"] / h["diger_sn"],
            "mk": {s: h["mal_kabul"] * p / kg for s, p, kg in SINIFLAR}, "mk_gug": {s: h["mal_kabul_gug"] * p / kg for s, p, kg in SINIFLAR},
            "elektrik": {a: h["elektrik"] * p / sn for a, p, sn in HATLAR}, "dogalgaz": {a: h["dogalgaz"] * p / sn for a, p, sn in HATLAR},
            "amortisman": {a: h["amortisman"] * p / sn for a, p, sn in HATLAR},
            "pazarlama": {_d(hac): h["pazarlama"] / agirlik * _d(kat) for _, hac, _, kat in AMBALAJ},
            "yonetim": {_d(hac): h["yonetim"] / agirlik * _d(kat) for _, hac, _, kat in AMBALAJ}}


ORAN = gider_oranlari()


def _kat(kod: str, p: dict) -> Decimal:
    """Excel P sütunu çarpanı: S ve TL -> 1 + enflasyon; S ve döviz -> kur; Z -> 1."""
    _, _, _, _, para, _, zs = MZ[kod]
    if zs != "S":
        return D(1)
    return D(1) + _d(p["enflasyon"]) if para == "TL" else _d(p["kur"][para])


def maliyet(u: dict, fiyatlar: dict, p: dict, vardiya=None, fire_k: dict | None = None) -> dict:
    """Tek ürünün birim maliyeti (finansman dahil, TL). Dönüş: malzeme satırları ve bloklar (Decimal)."""
    fire_k = fire_k or {}
    satirlar, malz = [], D(0)
    for sev, kod, miktar, fire, elle_brut, elle_fiyat in u["recete"]:
        fire = fire_k.get((u["kod"], kod), fire)
        brut = _d(elle_brut) if elle_brut is not None else _d(miktar) / (1 - _d(fire))
        if kod in ARA_MAMUL:
            tutar = D(0)
        else:
            f = _d(elle_fiyat) if elle_fiyat is not None else _d(fiyatlar.get(kod) or 0)
            tutar = _kat(kod, p) * f * brut
        satirlar.append({"kod": kod, "brut": brut, "tutar": tutar})
        malz += tutar
    v = _d(vardiya if vardiya is not None else u["vardiya"])
    sn = SANIYE / v
    di = _d(u["mk"]) * ORAN["mk"][u["sinif"]] + sn * _d(u["dolum"]) * ORAN["dolum"]
    if u["etiketleme"]:
        di += SANIYE / _d(u["etiketleme"]) * _d(u["etiket"]) * ORAN["etiket"]
    elektrik = _d(u["elle_elektrik"]) if u.get("elle_elektrik") is not None else ORAN["elektrik"][u["hat"]]
    gug = (sn * ORAN["endirekt"] + _d(u["mk"]) * ORAN["mk_gug"][u["sinif"]] + sn * elektrik + sn * ORAN["dogalgaz"][u["hat"]]
           + sn * ORAN["amortisman"][u["hat"]] + sn * ORAN["diger"])
    diger = (ORAN["pazarlama"][_d(u["hacim"])] + ORAN["yonetim"][_d(u["hacim"])]) if u["pyu"] else D(0)
    giy = malz + di + gug + diger
    faiz, ay = p["faiz"]["TL"]
    fin = giy * (_d(faiz) / 12 * _d(ay))
    return {"satirlar": satirlar, "malzeme": malz, "iscilik": di, "gug": gug, "uretim": di + gug, "toplam_birim": malz + di + gug,
            "diger": diger, "giydirilmis": giy, "finansman": fin, "maliyet": giy + fin, "fin_carpani": 1 + _d(faiz) / 12 * _d(ay)}


# ======================================================================================= senaryoların girdileri
def butce_fiyatlari(tamam: bool = False) -> dict[str, float | None]:
    """Bütçe kitabındaki S.ALMA BF fiyatları; tamam=True: satın almanın tamamladığı iki eksik fiyatla."""
    f = {m[0]: m[5] for m in MALZEMELER}
    if tamam:
        f.update(EKSIK_FIYATLAR)
    return f


def _carp(f: float, oran: float, n: int = 4) -> float:
    return float(_q(_d(f) * (1 + _d(oran)), n))


def guncel_fiyatlar() -> dict:
    f = butce_fiyatlari(True)
    f[KAVANOZ] = _carp(f[KAVANOZ], SOK_KAVANOZ)
    return f


def gerceklesen_fiyatlari() -> dict:
    """Sezonun fiilî ortalama alış fiyatları. Uygulama gerçekleşen çalışmada enflasyonu her zaman 0 alır (hesap_servisi); bu yüzden
    stoklu (S) TL malzemelerde bütçenin öngördüğü %25 artış fiyatın içindedir: fiyat = bütçe fiyatı x 1,25 (kavanozda ayrıca x 1,15).
    Ziraat (Z) ve dövizli malzemelerde bütçe enflasyon uygulamaz: fiyat aynıdır (biber −%10). Böylece TL maliyet, bilerek konan
    sapmalar dışında bütçeyle birebir aynıdır."""
    f = butce_fiyatlari(True)
    out = {}
    for kod, v in f.items():
        if v is None:
            out[kod] = None
            continue
        x = _d(v) * _kat_tl(kod) * (1 + _d(GERCEK_FIYAT.get(kod, 0)))
        out[kod] = float(_q(x, 4))
    return out


def _kat_tl(kod: str) -> Decimal:
    _, _, _, _, para, _, zs = MZ[kod]
    return D(1) + _d(BUTCE_PARAM["enflasyon"]) if (zs == "S" and para == "TL") else D(1)


def _param(kur_oranlari: dict, enflasyon=None) -> dict:
    p = json.loads(json.dumps(BUTCE_PARAM))
    for pb, oran in kur_oranlari.items():
        p["kur"][pb] = _carp(p["kur"][pb], oran)
    p["faiz"] = {k: tuple(v) for k, v in p["faiz"].items()}
    if enflasyon is not None:
        p["enflasyon"] = enflasyon
    return p


BUTCE_P = _param({})
GUNCEL_P = _param({"USD": SOK_USD})
GERCEK_P = _param(GERCEK_KUR, enflasyon=0.0)    # uygulama kuralı: gerçekleşende enflasyon 0
GERCEK_VARDIYA = {ADET_URUN: round(UR[ADET_URUN]["vardiya"] * ADET_ORANI)}
GERCEK_FIRE = {(FIRE_URUN, FIRE_MALZEME): FIRE_SONRA}


# ======================================================================================= Fiyat Çalışması kitabı
def satin_alma_sayfasi(ws, fiyatlar: dict[str, float | None], revize: dict[str, float], malzemeler=MALZEMELER) -> None:
    ws.title = "S.ALMA BF"
    _baslik(ws, 1, ["Malzeme", "Açıklama", "Malzeme Tipi", "Stok Birimi", "Para Birimi", "Bütçe Birim Fiyatları", "Z/S", "Not",
                    "Bütçe Birim Fiyatları"])
    for kod, ad, tip, birim, para, _, zs in malzemeler:
        ws.append([kod, ad, tip, birim, para, fiyatlar.get(kod), zs, None, revize.get(kod)])
    for col, w in zip("ABCDEFGHI", (12, 30, 22, 10, 10, 20, 6, 10, 20)):
        ws.column_dimensions[col].width = w


def gider_sayfasi(ws, onb: Onbellek) -> None:
    """Gider Dağıtım sayfası (excel_okuyucu.HAVUZ_TOPLAM_HUCRELERI ve satır aralıkları). Bütçe ve gerçekleşende aynıdır."""
    ws.title = "Gider Dağıtım"
    ws["A1"] = "GİDER DAĞITIM TABLOSU (TEST VERİSİ)"; ws["A1"].font = KALIN

    def toplam(hucre, taban, carpanlar):
        deger = D(str(taban))
        for c in carpanlar:
            deger *= D(str(c))
        onb.formul(ws, hucre, "=" + "*".join([str(taban)] + [str(c) for c in carpanlar]), float(deger))

    def etiket(hucre, metin):
        ws[hucre] = metin; ws[hucre].font = KALIN

    etiket("A3", "Dolum Doğrudan İşçilik"); etiket("D3", "Gider Toplamı"); etiket("F3", "Toplam adam-saniye"); etiket("G3", "TL / sn")
    toplam("D4", 6000000, (1.35, 1.2)); ws["F4"] = 360000000; ws["G4"] = "=D4/F4"
    etiket("A5", "Mal Kabul ve Fermantasyon İşçilik (toplam A6)")
    ws["A6"] = 2400000
    for r, (sinif, pay, kg) in zip(range(7, 10), SINIFLAR):
        ws[f"C{r}"], ws[f"E{r}"], ws[f"G{r}"] = sinif, int(kg), float(pay)
        ws[f"F{r}"] = f"=$A$6*G{r}/E{r}"
    etiket("A12", "Etiketleme İşçilik"); etiket("D12", "Gider Toplamı")
    ws["D13"] = 1800000; ws["F13"] = 90000000; ws["G13"] = "=D13/F13"
    etiket("A17", "Endirekt İşçilik"); etiket("D17", "Gider Toplamı")
    toplam("D18", 4000000, (1.25,)); ws["F18"] = 30000000; ws["G18"] = "=D18/F18"
    etiket("A19", "Mal Kabul ve Fermantasyon GÜG (toplam A20)")
    ws["A20"] = 1200000
    for r, (sinif, pay, kg) in zip(range(21, 24), SINIFLAR):
        ws[f"C{r}"], ws[f"E{r}"], ws[f"G{r}"] = sinif, int(kg), float(pay)
        ws[f"F{r}"] = f"=$A$20*G{r}/E{r}"
    etiket("A26", "Diğer Genel Üretim Giderleri"); etiket("D26", "Gider Toplamı")
    toplam("D27", 3200000, (1.25,)); ws["F27"] = 30000000; ws["G27"] = "=D27/F27"
    for bas, top_hucre, taban, carp, ad in ((30, "D38", 2600000, (1.4,), "Elektrik"), (41, "D49", 1000000, (1.5,), "Doğalgaz"),
                                             (52, "D60", 6000000, (), "Amortisman")):
        etiket(f"A{bas - 1}", ad + " (hat payları)")
        for r, (hat, pay, sn) in zip(range(bas, bas + 8), HATLAR):
            ws[f"A{r}"], ws[f"E{r}"], ws[f"G{r}"] = hat, int(sn), float(pay)
            ws[f"F{r}"] = f"=${top_hucre[0]}${top_hucre[1:]}*G{r}/E{r}"
        etiket(f"C{top_hucre[1:]}", "Toplam")
        if carp:
            toplam(top_hucre, taban, carp)
        else:
            ws[top_hucre] = taban
    etiket("A63", "Genel Yönetim Giderleri"); etiket("D63", "Gider Toplamı")
    toplam("D64", 8000000, (1.3,))
    etiket("A66", "Pazarlama Satış Giderleri"); etiket("D66", "Gider Toplamı")
    toplam("D67", 10000000, (1.25,))
    etiket("A69", "Ambalaj"); etiket("B69", "Hacim"); etiket("C69", "Üretim Adedi"); etiket("D69", "Katsayı")
    for r, (ad, hacim, adet, kat) in zip(range(70, 92), AMBALAJ):
        ws[f"A{r}"], ws[f"B{r}"], ws[f"C{r}"], ws[f"D{r}"] = ad, hacim, adet, kat
    ws.column_dimensions["A"].width = 44
    for col in "CDEFG":
        ws.column_dimensions[col].width = 18


def urun_sayfasi(ws, u: dict, fiyatlar: dict[str, float | None], p: dict, onb: Onbellek, ad: str | None = None,
                 fire_k: dict | None = None) -> None:
    """Ürün sayfası: satır 6 ürünün kendisi (seviye 0), reçete 7-..., etiket satırları gerçek kitaptaki numaralarda (100-155)."""
    ws.title = ad or u["sayfa"]
    fire_k = fire_k or {}
    ws["P2"] = "Yurtiçi"
    ws["D2"] = u["ad"]; ws["D2"].font = KALIN
    _baslik(ws, 5, ["Seviye", None, None, "Malzeme Kodu", "Malzeme Adı", None, None, None, "Miktar", "Fire", "Brüt Miktar", "Birim",
                    "Birim Fiyat", "Z/S", "Para B.", "Tutar"])
    ws["A6"], ws["D6"], ws["E6"], ws["I6"], ws["L6"] = 0, u["kod"], u["ad"], 1, "AD"
    onb.formul(ws, "K6", "=I6/(1-J6)", 1)
    onb.formul(ws, "M6", "=IFERROR(VLOOKUP($D6,'S.ALMA BF'!$A:$F,6,0),0)", 0)
    r = 7
    for sev, kod, miktar, fire, elle_brut, elle_fiyat in u["recete"]:
        fire = fire_k.get((u["kod"], kod), fire)
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
    E(148, "Enflasyon"); ws["F148"] = p["enflasyon"]
    E(149, "Maliyet Sapma"); ws["F149"] = 0.03
    E(150, "Döviz Kurları")
    for i, (pb, kur) in enumerate(p["kur"].items()):
        ws[f"E{150 + i}"], ws[f"F{150 + i}"] = pb, kur
    for col, w in zip("ADEIJKLMNOP", (7, 12, 34, 10, 7, 11, 7, 11, 5, 7, 12)):
        ws.column_dimensions[col].width = w


def uretim_adetleri_sayfasi(ws) -> None:
    """Hedef vardiyalık üretim = bütçedeki vardiya üretim adedi (gerçekleşen kitapta da hedef aynı kalır)."""
    ws.title = "Üretim Adetleri"
    ws["A1"] = "ÜRETİM ADETLERİ (TEST)"; ws["A1"].font = KALIN
    # Okuyucu başlığı str.upper() ile karşılaştırır: başlıklar büyük harfle yazılmalı.
    _baslik(ws, 2, ["ÜRÜN KODU", "ÜRÜN ADI", "NET SÜREDEKİ VARDİYALIK KAPASİTE", "NET SÜRE", "TOPLAM SÜREDEKİ KAPASİTE", "TOPLAM SÜRE",
                    "HEDEF VARDİYALIK ÜRETİM", "ORTALAMA İŞÇİ SAYISI"])
    ws.append(["", "", "(adet)", "(saat)", "(adet)", "(saat)", "(adet)", "(kişi)"])
    for u in URUNLER:
        ws.append([u["kod"], u["ad"], round(u["vardiya"] * 1.15), 6.5, round(u["vardiya"] * 1.3), 7.5, u["vardiya"], u["dolum"] + u["etiket"] + 2])
    ws.column_dimensions["B"].width = 30


def fiyat_kitabi(ad: str, fiyatlar: dict, p: dict, vardiya: dict | None = None, fire_k: dict | None = None) -> Path:
    wb = openpyxl.Workbook()
    onb = Onbellek()
    kapak = wb.active
    kapak.title = "Teklif Kapak"
    kapak["A1"] = "TEST TEKLİF KAPAK SAYFASI (uygulama okumaz; görünüm için)"; kapak["A1"].font = KALIN
    _baslik(kapak, 3, ["Ürün Kodu", "Ürün Adı", "Ambalaj"])
    for u in URUNLER:
        kapak.append([u["kod"], u["ad"], u["hacim"]])
    kapak.column_dimensions["B"].width = 32
    satin_alma_sayfasi(wb.create_sheet(), fiyatlar, {})
    gider_sayfasi(wb.create_sheet(), onb)
    for u in URUNLER:
        uu = dict(u)
        if vardiya and u["kod"] in vardiya:
            uu["vardiya"] = vardiya[u["kod"]]
        urun_sayfasi(wb.create_sheet(), uu, fiyatlar, p, onb, fire_k=fire_k)
    # '(2)' ekli varyant sayfa: içe aktarmada atlanır (özet 'atlanan' listesinde görünmeli)
    urun_sayfasi(wb.create_sheet(), URUNLER[0], fiyatlar, p, onb, ad="001 (2)")
    uretim_adetleri_sayfasi(wb.create_sheet())
    return _kaydet(wb, ad, onb)


# ======================================================================================= Veri Aktar ve diğer FÇ dosyaları
def satin_alma_eksik_fiyatlar() -> Path:
    """Veri Aktar › Satın alma fiyat listesi: bütçe kitabında fiyatı boş iki malzemeye fiyat (Satın alma tamamlar)."""
    satirlar = [MZ[k][:5] + (f, MZ[k][6]) for k, f in EKSIK_FIYATLAR.items()]
    wb = openpyxl.Workbook()
    satin_alma_sayfasi(wb.active, {m[0]: m[5] for m in satirlar}, {}, malzemeler=satirlar)
    return _kaydet(wb, "satin-alma-eksik-fiyatlar")


def fiyat_listesi_kasim() -> Path:
    """Malzeme Fiyatları › Fiyat listesi yükle (Kasım revize listesi): tüm malzemeler F = bütçe fiyatı (eksikler tamamlanmış),
    yalnız kavanoz 370 ml'de I (revize) = +%15. Başka hiçbir fiyat değişmez."""
    wb = openpyxl.Workbook()
    satin_alma_sayfasi(wb.active, butce_fiyatlari(True), {KAVANOZ: guncel_fiyatlar()[KAVANOZ]})
    return _kaydet(wb, "fiyat-listesi-kasim-revize")


def satis_fiyatlari() -> dict[str, Decimal]:
    """Geçen yıl satış fiyatı (TL): bütçe birim maliyeti x SATIS_CARPANI, 0,05'e yuvarlı."""
    out = {}
    for u in URUNLER:
        m = maliyet(u, butce_fiyatlari(True), BUTCE_P)["maliyet"] * SATIS_CARPANI[u["kod"]]
        out[u["kod"]] = (m / D("0.05")).quantize(D(1), rounding=ROUND_HALF_UP) * D("0.05")
    return out


def satis_gecmisi() -> Path:
    """Geçen yıl (sezon 2025-2026: Haziran 2025 - Mayıs 2026) aylık satışlar: her ay yıllık adedin 1/12'si, iki müşteri (%60 / %40),
    aynı TL fiyat. Uygulama yıllık adedi buradan alır (kur riski, kârlılık, önemli malzemeler, yönetim özeti)."""
    fiyat = satis_fiyatlari()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Satış Geçmişi"
    _baslik(ws, 1, ["urun_kodu", "musteri", "tarih", "fiyat", "para_birimi", "adet"])
    for yil, ay in [(2025, a) for a in range(6, 13)] + [(2026, a) for a in range(1, 6)]:
        for kod, yillik in YILLIK_ADET.items():
            for musteri, pay in MUSTERI_PAYI:
                ws.append([kod, musteri, date(yil, ay, 15), float(fiyat[kod]), "TL", int(D(yillik) / 12 * pay)])
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
    for kod, (liste, mal) in taban.items():
        for yil, k_l, k_m in ((2023, 1 / (1.42 * 1.38), 1 / (1.46 * 1.35)), (2024, 1 / 1.42, 1 / 1.46), (2025, 1.0, 1.0)):
            ws.append([kod, yil, round(liste * k_l, 2), round(mal * k_m, 2), "Yurtiçi"])
            ws.append([kod, yil, round(liste * k_l * 0.7, 2), round(mal * k_m, 2), "Yurtdışı"])
    return _kaydet(wb, "liste-fiyatlari-gecmis")


# ======================================================================================= SMM
TUR = {"0001": "0001-Hammadde", "0008": "0008-Ambalaj Malzeme", "0017": "0017-Yardımcı Malzeme", "0015": "0015-Üretim Yarı Mamulü",
       "0002": "0002-Yarı Mamul", "0003": "0003-Mamul"}
MIZAN = {"0001": "150.01", "0008": "150.02", "0017": "150.03", "0015": "151.01", "0002": "151.02", "0003": "152.01"}
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
SMM_MAMUL = ("03.99.001", "03.99.002", "03.99.003", "03.99.004", "03.99.007")
SMM_MALZEME = [m for m in MALZEMELER if m[5] is not None and m[0] not in ("99.10.005", "99.10.006", "99.10.007", "99.20.009", "99.20.012",
                                                                         "99.20.013", "99.20.014")]
URETIM_AY = {k: YILLIK_ADET[k] // 12 for k in SMM_MAMUL}          # Ekim ve Kasım aynı: yıllık hedefin 1/12'si
SURELER = {   # mamul -> (yarı mamul, vardiya üretim, dolum işçi, etiket işçi, dolum sn, dolum adam sn, etiket sn, etiket adam sn)
    "03.99.001": ("02.99.001", 18000, 12, 3, 1.5, 18.0, 0.9, 2.7), "03.99.002": ("02.99.002", 12000, 12, 3, 2.25, 27.0, 1.35, 4.05),
    "03.99.003": ("02.99.003", 15000, 14, 3, 1.8, 25.2, 0.9, 2.7), "03.99.004": ("02.99.004", 20000, 10, 3, 1.35, 13.5, 0.9, 2.7),
    "03.99.007": ("02.99.007", 18000, 12, 3, 1.5, 18.0, 0.9, 2.7),
}
IADE = {"ekim": {KAVANOZ: 2400}, "kasim": {"99.20.003": 3000}}
HM_SATIS = {"ekim": {"99.11.001": 1500}, "kasim": {}}
SAHIT = {"ekim": {"03.99.001": 120, "03.99.004": 60}, "kasim": {"03.99.001": 110, "03.99.002": 40}}
SAYIM_EKSIGI = {"ekim": {"99.10.001": 3000}, "kasim": {}}       # bilinçli sayım farkı: Ekim'de 3.000 kg hıyar eksik
STOK_ORANI = D("0.4")                                             # ay sonu malzeme stoku = ayın tüketiminin %40'ı
DAGITILMAYAN_ORAN = D("0.05")                                     # 720+730'un %5'i ürünlere dağıtılmaz


def smm_fiyatlari(ay: str) -> dict[str, Decimal]:
    """SMM alım birim fiyatı (TL). Ekim: bütçenin maliyete yansıttığı TL fiyat (S ve TL: x(1+enflasyon); S ve döviz: x bütçe kuru;
    Z: liste). Kasım: Ekim x 1,15 (kavanoz 370 ml) ve x 1,08 (USD'li malzemeler); diğerleri aynı."""
    f = butce_fiyatlari(True)
    out = {}
    for kod, *_ in SMM_MALZEME:
        x = _q(_d(f[kod]) * _kat(kod, BUTCE_P), 4)
        if ay == "kasim":
            if kod == KAVANOZ:
                x = _q(x * (1 + _d(SOK_KAVANOZ)), 4)
            if MZ[kod][4] == "USD":
                x = _q(x * (1 + _d(SOK_USD)), 4)
        out[kod] = x
    return out


def _yuvarla_miktar(kod, x: Decimal) -> Decimal:
    birim = MZ[kod][3] if kod in MZ else SMM_URUN[kod][1]
    return _q(x, 0 if birim == "AD" else 1)


def smm_ay(ay: str, onceki: dict | None, butce_birim: dict[str, Decimal]) -> dict:
    """Bir ayın kaynak verisi: kod -> {dbs_m, dbs_t, alim_m, alim_t, iade_m, iade_t, uretim, sayim, satis, sahit, fiyat}."""
    uretim: dict[str, int] = dict(URETIM_AY)
    for kod, n in URETIM_AY.items():
        uretim["02" + kod[2:]] = round(n * 1.006)
    ihtiyac: dict[str, Decimal] = {}

    def tuket(ana, n):
        satirlar, fire = SMM_RECETE[ana]
        for mal, mik in satirlar:
            ihtiyac[mal] = ihtiyac.get(mal, D(0)) + D(n) * _d(mik) * (1 + _d(fire))
    for kod in [k for k in uretim if k.startswith("02")] + list(URETIM_AY):
        tuket(kod, uretim[kod])
    for kod in ("01.99.001", "01.99.002", "01.99.003", "01.99.004"):
        uretim[kod] = int(_q(ihtiyac.get(kod, D(0)) * D("1.01") / 100, 0) * 100)
        tuket(kod, uretim[kod])
    fiyat = smm_fiyatlari(ay)
    veri = {}
    for kod in [m[0] for m in SMM_MALZEME] + list(SMM_URUN):
        tuketim = ihtiyac.get(kod, D(0))
        uretilen = D(uretim.get(kod, 0))
        if onceki is None:
            if kod in MZ:
                dbs_m = _yuvarla_miktar(kod, tuketim * STOK_ORANI)
                dbs_t = _q(dbs_m * fiyat[kod], 2)
            elif kod.startswith("03"):
                dbs_m = _q(uretilen * D("0.15"), 0)
                dbs_t = _q(dbs_m * butce_birim[kod], 2)
            else:
                dbs_m, dbs_t = D(0), D(0)
        else:   # devir: açılış = önceki ayın sayımı x önceki ayın ortalama fiyatı (ürünlerde tutar uygulamadan gelir; burada kullanılmaz)
            dbs_m = onceki[kod]["sayim"]
            dbs_t = _q(dbs_m * onceki[kod]["ort"], 2) if kod in MZ else D(0)
        x = {"dbs_m": dbs_m, "dbs_t": dbs_t, "alim_m": D(0), "alim_t": D(0), "iade_m": D(0), "iade_t": D(0), "uretim": uretilen,
             "satis": D(0), "sahit": D(SAHIT[ay].get(kod, 0)), "tuketim": tuketim}
        if kod in MZ:
            alim = _yuvarla_miktar(kod, max(D(0), tuketim * (1 + STOK_ORANI) - dbs_m))
            x["fiyat"] = fiyat[kod]
            x["alim_m"], x["alim_t"] = alim, _q(alim * fiyat[kod], 2)
            if kod in IADE[ay]:
                x["iade_m"] = D(IADE[ay][kod]); x["iade_t"] = _q(x["iade_m"] * fiyat[kod], 2)
            x["satis"] = D(HM_SATIS[ay].get(kod, 0))
            sayim = dbs_m + alim - x["iade_m"] - x["satis"] - tuketim - D(SAYIM_EKSIGI[ay].get(kod, 0))
            x["sayim"] = _yuvarla_miktar(kod, max(sayim, D(0)))
        else:
            satilan = uretilen * D("0.93") if kod.startswith("03") else D(0)
            x["sayim"] = _yuvarla_miktar(kod, max(dbs_m + uretilen - tuketim - satilan - x["sahit"], D(0)))
        if kod in MZ:
            top_m = x["dbs_m"] + x["alim_m"]
            x["ort"] = (x["dbs_t"] + x["alim_t"]) / top_m if top_m else D(0)
        veri[kod] = x
    return {"veri": veri, "uretim": uretim}


def _ad(kod):
    return MZ[kod][1] if kod in MZ else SMM_URUN[kod][0]


def _birim(kod):
    return MZ[kod][3] if kod in MZ else SMM_URUN[kod][1]


def _tur(kod):
    return MZ[kod][2][:4] if kod in MZ else SMM_URUN[kod][3]


def _f(x):
    return None if x is None else _sayi(float(x))


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
            m1 = _yuvarla_miktar(kod, x["alim_m"] / parca)
            for i in range(parca):
                mik = m1 if i < parca - 1 else x["alim_m"] - m1 * (parca - 1)
                tutar = _q(x["alim_t"] * mik / x["alim_m"], 2) if i < parca - 1 else x["alim_t"] - _q(x["alim_t"] * m1 / x["alim_m"], 2) * (parca - 1)
                ws.append([f"ALS-{n:05d}", kod, _ad(kod), None, "Merkez", _birim(kod), _f(mik), _f(_q(tutar / mik, 4)) if mik else None,
                           MZ[kod][4], None, _f(tutar), None] + [None] * 7 + ["Alış"])
                n += 1
        if x["satis"]:
            ws.append([f"STS-{n:05d}", kod, _ad(kod), None, "Merkez", _birim(kod), None, None, "TL", None, None, _f(x["satis"])] + [None] * 7 + ["Satış"])
            n += 1
    ws.column_dimensions["B"].width = 18; ws.column_dimensions["C"].width = 34


def _iade_sayfasi(ws, ay_veri) -> None:
    ws.title = "İADELER"
    ws["A1"] = "ALIM İADELERİ (TEST)"; ws["A1"].font = KALIN
    _baslik(ws, 2, ["Malzeme (Sınıf) Kodu", "Malzeme Açıklaması", "Tarih", "Fiş No", "Birim", "Tedarikçi", "Not", "İade Miktarı", "İade Tutarı"])
    for kod, x in ay_veri.items():
        if x["iade_m"]:
            ws.append([kod, _ad(kod), None, "IAD-001", _birim(kod), "Test Tedarikçi A.Ş.", None, _f(x["iade_m"]), _f(x["iade_t"])])
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
            ws.append([kod, _ad(kod), _f(x["sayim"]), _birim(kod), None])
    ws.column_dimensions["B"].width = 38


def _sahit_sayfasi(ws, ay_veri) -> None:
    ws.title = "ŞAHİT"
    ws["A1"] = "ŞAHİT NUMUNE (TEST)"; ws["A1"].font = KALIN
    _baslik(ws, 2, ["StokKodu", "StokAdı", "Birim", None, None, None, None, None, None, "Toplam Miktar"])
    for kod, x in ay_veri.items():
        if x["sahit"]:
            ws.append([kod, _ad(kod), _birim(kod)] + [None] * 6 + [_f(x["sahit"])])


GIDER_ADLARI = {"710": "Direkt İlk Madde ve Malzeme Giderleri", "720": "Direkt İşçilik Giderleri", "730": "Genel Üretim Giderleri",
                "760": "Pazarlama Satış ve Dağıtım Giderleri", "770": "Genel Yönetim Giderleri"}


def _gider_mizan_sayfasi(ws, mizan: dict[str, Decimal]) -> None:
    ws.title = "GİDER MİZAN"
    _baslik(ws, 1, ["Hesap Kodu", "Hesap Adı", "Borç", "Alacak", None, None, "Bakiye"])
    for h, v in mizan.items():
        ws.append([h, GIDER_ADLARI[h], _f(v), 0, None, None, _f(v)])
        if h in ("720", "730"):   # alt hesaplar (3 haneli olmayan satırlar okunmaz)
            ws.append([f"{h}.01", GIDER_ADLARI[h] + " - Üretim", _f(_q(v * D("0.7"), 2)), 0, None, None, _f(_q(v * D("0.7"), 2))])
            ws.append([f"{h}.02", GIDER_ADLARI[h] + " - Diğer", _f(v - _q(v * D("0.7"), 2)), 0, None, None, _f(v - _q(v * D("0.7"), 2))])
    ws.column_dimensions["B"].width = 40


def _stok_mizan_sayfasi(ws, bakiyeler: dict[str, Decimal], tarih: str) -> None:
    ws.title = "STOK MİZAN"
    ws["A1"] = "STOK MİZANI (TEST)"; ws["A1"].font = KALIN
    _baslik(ws, 2, ["Hesap Kodu", "Hesap Adı", "Borç", "Alacak", None, None, "Bakiye", None, "Fiş Tarihi"])
    ws["J2"] = tarih
    adlar = {"150.01": "Hammadde", "150.02": "Ambalaj Malzemesi", "150.03": "Yardımcı Malzeme", "151.01": "Üretim Yarı Mamulü",
             "151.02": "Yarı Mamul", "152.01": "Mamul"}
    for h, v in bakiyeler.items():
        ws.append([h, adlar[h], _f(v), 0, None, None, _f(v)])
    ws.column_dimensions["B"].width = 26


# Stok mizanı hesap toplamları (150 / 151 / 152) = uygulamanın sayım değerlemesi: mizan ile sayım farkı 0,00 çıksın diye kuru koşudan
# alındı (kuru_kosu_sezon.py sonunda '[stok mizanı ayarı]' satırı). Veri değişirse oradaki değerlerle güncelleyin; None: üreticinin
# kendi tahmini (150 kuruş farkıyla, 151/152 kaba tahmin) kullanılır. Alt hesaplara (150.01 ...) üreticinin tahmini oranında dağıtılır.
STOK_MIZAN_AYARI = {"ekim": {"150": "5918597.40", "151": "92650.99", "152": "3553385.45"},
                    "kasim": {"150": "6158479.73", "151": "187785.61", "152": "4776361.50"}}


def _ortalama_fiyatlar(ay_veri) -> dict[str, Decimal]:
    """Malzemelerin ay ortalama fiyatı (TABLO formülü, finansman 0): (DBS tutarı + alım tutarı) / (DBS miktarı + alım miktarı)."""
    out = {}
    for kod, x in ay_veri.items():
        if kod in MZ:
            top_m = x["dbs_m"] + x["alim_m"]
            out[kod] = (x["dbs_t"] + x["alim_t"]) / top_m if top_m else D(0)
    return out


def _stok_mizani(ay: str, ay_veri, butce_birim: dict[str, Decimal]) -> dict[str, Decimal]:
    """150: sayım x ortalama fiyat (üretici kendisi hesaplar; uygulamanın değerlemesiyle aynı formül). 151/152: STOK_MIZAN_URUN ya da
    tahmin (sayım x bütçe birim maliyeti)."""
    ort = _ortalama_fiyatlar(ay_veri)
    t = {h: D(0) for h in ("150.01", "150.02", "150.03", "151.01", "151.02", "152.01")}
    for kod, x in ay_veri.items():
        if kod in MZ:
            t[MIZAN[_tur(kod)]] += x["sayim"] * ort[kod]
        else:
            t[MIZAN[_tur(kod)]] += x["sayim"] * butce_birim.get("03" + kod[2:], D(20)) * (D("0.3") if kod.startswith("01") else D(1))
    out = {h: _q(v, 2) for h, v in t.items()}
    for ana, hedef in STOK_MIZAN_AYARI[ay].items():
        if hedef is None:
            continue
        alt = [h for h in out if h.startswith(ana + ".")]
        tahmin = sum((out[h] for h in alt), D(0))
        kalan = D(hedef)
        for h in alt[1:]:
            out[h] = _q(D(hedef) * out[h] / tahmin, 2) if tahmin else D(0)
            kalan -= out[h]
        out[alt[0]] = kalan
    return out


def _tablo_degerleri(ay_veri) -> dict[str, tuple]:
    """Excel TABLO satırı (smm_servisi.stok_hesabi ile aynı formül, finansman 0): DBS miktar, alım tutarı, ort. fiyat, DSS tutarı, sarf,
    sarf maliyeti."""
    out = {}
    for kod, x in ay_veri.items():
        top_m, top_t = x["dbs_m"] + x["alim_m"], x["dbs_t"] + x["alim_t"]
        ort = top_t / top_m if top_m else D(0)
        sarf = top_m - x["iade_m"] - x["sayim"]
        out[kod] = (float(x["dbs_m"]), float(x["alim_t"]), float(ort), float(x["sayim"] * ort), float(sarf), float(sarf * ort))
    return out


def gider_mizani(butce: dict[str, dict]) -> tuple[dict[str, Decimal], dict[str, Decimal]]:
    """Ay gider mizanı: 720/730/760/770 = bütçe birim işçilik / GÜG / pazarlama / yönetim x aylık üretim (bin TL'ye yuvarlı).
    Dağıtım havuzları: 720+730'un %95'i (20 üretim, 40 işçilik, 40 GÜG, 50 üretim)."""
    t = {k: D(0) for k in ("720", "730", "760", "770")}
    for kod, n in URETIM_AY.items():
        b = butce[kod]
        t["720"] += b["iscilik"] * n
        t["730"] += b["gug"] * n
        pz = ORAN["pazarlama"][_d(UR[kod]["hacim"])]
        t["760"] += pz * n
        t["770"] += (b["diger"] - pz) * n
    mizan = {"710": D(0), **{k: _q(v / 1000, 0) * 1000 for k, v in t.items()}}
    k = 1 - DAGITILMAYAN_ORAN
    i720, i730 = mizan["720"] * k, mizan["730"] * k
    havuz = {"20_stok": D(0), "20_uretim": _q(i720 * D("0.15") / 1000, 0) * 1000, "40_stok_iscilik": D(0),
             "40_iscilik": _q(i720 * D("0.60") / 1000, 0) * 1000, "40_stok_gug": D(0), "40_gug": _q(i730 / 1000, 0) * 1000, "50_stok": D(0)}
    havuz["50_uretim"] = _q(i720 / 1000, 0) * 1000 - havuz["20_uretim"] - havuz["40_iscilik"]
    return mizan, havuz


def smm_ekim_kitabi(ekim: dict, mizan: dict, havuz: dict, stok_mizan: dict) -> Path:
    v = ekim["veri"]
    wb = openpyxl.Workbook()
    onb = Onbellek()
    env = wb.active
    env.title = "ENVANTER"
    env["A1"] = "ENVANTER (TEST) · Ekim 2026"; env["A1"].font = KALIN
    _baslik(env, 2, ["Stok Kodu", "Stok Adı", "Birim", "Malzeme Türü", "Mizan Kodu"] + [None] * 10 + ["Üretim Birim Fiyatı"])
    for kod in v:
        env.append([kod, _ad(kod), _birim(kod), TUR[_tur(kod)], MIZAN[_tur(kod)]])
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
            dbs.append([kod, _ad(kod), _f(x["dbs_m"]), _f(x["dbs_t"])])
    dbs.column_dimensions["B"].width = 38
    _alim_sayfasi(wb.create_sheet(), v, "Ekim 2026")
    _iade_sayfasi(wb.create_sheet(), v)
    _uretim_sayfasi(wb.create_sheet(), ekim["uretim"])
    _sayim_sayfasi(wb.create_sheet(), v)
    _sahit_sayfasi(wb.create_sheet(), v)
    tablo = wb.create_sheet("TABLO")
    tablo["A1"] = "STOK TABLOSU (TEST)"; tablo["A1"].font = KALIN
    tablo["I1"] = "Finansman:"; tablo["J1"] = 0
    _baslik(tablo, 2, ["", "Stok Kodu", "Stok Adı", "DBS Miktar", None, None, None, "Alım Tutarı"] + [None] * 6 + ["Ortalama Fiyat"]
            + [None] * 5 + ["DSS Tutarı", "Sarf Miktarı", "Sarf Maliyeti"])
    for kod, t in _tablo_degerleri(v).items():
        tablo.append([None, kod, _ad(kod), t[0], None, None, None, t[1]] + [None] * 6 + [t[2]] + [None] * 5 + [t[3], t[4], t[5]])
    for asama, (sayfa, fire_i) in {20: ("20 KOD", 23), 40: ("40 KOD", 31), 50: ("50 KOD", 25)}.items():
        ws = wb.create_sheet(sayfa)
        hucre = {20: {16: "20_stok", 19: "20_uretim"}, 40: {16: "40_stok_iscilik", 21: "40_iscilik", 26: "40_stok_gug", 29: "40_gug"},
                 50: {16: "50_stok", 21: "50_uretim"}}[asama]
        ws["A1"] = f"{sayfa} · aşama {asama} (TEST)"; ws["A1"].font = KALIN
        for sut, ad in hucre.items():
            ws.cell(row=1, column=sut, value=_f(havuz[ad]))
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
    _gider_mizan_sayfasi(wb.create_sheet(), mizan)
    _stok_mizan_sayfasi(wb.create_sheet(), stok_mizan, "31.10.2026")
    return _kaydet(wb, "smm-ekim-2026", onb)


def smm_kasim_dosyalari(kasim: dict, mizan: dict, stok_mizan: dict) -> list[Path]:
    v = kasim["veri"]
    out = []
    for ad, fn in (("alim-satis", lambda ws: _alim_sayfasi(ws, v, "Kasım 2026")), ("iadeler", lambda ws: _iade_sayfasi(ws, v)),
                   ("uretim", lambda ws: _uretim_sayfasi(ws, kasim["uretim"])), ("sayim", lambda ws: _sayim_sayfasi(ws, v)),
                   ("sahit-numune", lambda ws: _sahit_sayfasi(ws, v)), ("gider-mizan", lambda ws: _gider_mizan_sayfasi(ws, mizan)),
                   ("stok-mizan", lambda ws: _stok_mizan_sayfasi(ws, stok_mizan, "30.11.2026"))):
        wb = openpyxl.Workbook()
        fn(wb.active)
        out.append(_kaydet(wb, f"smm-kasim-2026-{ad}"))
    return out


def canias_receteleri() -> Path:
    """Reçeteler › Canias ürün ağacı dökümü (TBLRESULT). Tüketim malzemesi boş satır = ürün başlığı. 03.99.001'in '01' alternatifi
    (koli 12'li yerine 6'lı) seçim denemesi içindir; varsayılan '00' seçili kalır."""
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


def smm_birim_miktarlar(kod: str) -> dict[str, Decimal]:
    """SMM reçetesiyle ürünün 1 biriminde fireli malzeme miktarı (aşama firesi her aşamada malzeme tutarına eklenir)."""
    satirlar, fire = SMM_RECETE[kod]
    out: dict[str, Decimal] = {}
    for mal, mik in satirlar:
        alt = smm_birim_miktarlar(mal) if mal in SMM_RECETE else {mal: D(1)}
        for m_, q in alt.items():
            out[m_] = out.get(m_, D(0)) + _d(mik) * q * (1 + _d(fire))
    return out


# ======================================================================================= beklenen sapmalar
def _s(x: Decimal, n: int = 6) -> str:
    return str(_q(x, n))


def ayristir(u: dict) -> dict:
    """Uygulamanın zincirleme ikame sırası (kiyas_servisi.ayristir) bağımsız hesapla: A = bütçe, B = gerçekleşen."""
    fa, fb = butce_fiyatlari(True), gerceklesen_fiyatlari()
    va, vb = u["vardiya"], GERCEK_VARDIYA.get(u["kod"], u["vardiya"])
    adimlar = [("fiyat", dict(fiyatlar=fb, p=BUTCE_P, vardiya=va, fire_k=None)),
               ("recete", dict(fiyatlar=fb, p=BUTCE_P, vardiya=va, fire_k=GERCEK_FIRE)),
               ("uretim", dict(fiyatlar=fb, p=BUTCE_P, vardiya=vb, fire_k=GERCEK_FIRE)),
               ("gider", dict(fiyatlar=fb, p=BUTCE_P, vardiya=vb, fire_k=GERCEK_FIRE)),
               ("kur", dict(fiyatlar=fb, p=_param(GERCEK_KUR), vardiya=vb, fire_k=GERCEK_FIRE)),
               ("enflasyon", dict(fiyatlar=fb, p=GERCEK_P, vardiya=vb, fire_k=GERCEK_FIRE)),
               ("diger", dict(fiyatlar=fb, p=GERCEK_P, vardiya=vb, fire_k=GERCEK_FIRE))]
    onceki = maliyet(u, fa, BUTCE_P)["maliyet"]
    a = onceki
    out = {}
    for kaynak, k in adimlar:
        simdi = maliyet(u, k["fiyatlar"], k["p"], k["vardiya"], k["fire_k"])["maliyet"]
        out[kaynak] = simdi - onceki
        onceki = simdi
    return {"a": a, "b": onceki, "adimlar": out}


def _kalem_etkileri(u: dict) -> list[dict]:
    """Sapmanın malzeme satırı düzeyinde kapalı form açıklaması (finansman dahil): kontrol için, ayrıştırmayla toplamı aynıdır."""
    fa = butce_fiyatlari(True)
    fin = 1 + _d(BUTCE_P["faiz"]["TL"][0]) / 12 * _d(BUTCE_P["faiz"]["TL"][1])
    out = []
    for sev, kod, miktar, fire, elle_brut, elle_fiyat in u["recete"]:
        if kod in ARA_MAMUL or elle_fiyat is not None:
            continue
        brut = _d(elle_brut) if elle_brut is not None else _d(miktar) / (1 - _d(fire))
        if kod in GERCEK_FIYAT:
            out.append({"kaynak": "fiyat", "malzeme": kod, "ad": MZ[kod][1],
                        "aciklama": f"bütçede maliyete giren {_q(_d(fa[kod]) * _kat(kod, BUTCE_P), 4)} TL, fiilî {gerceklesen_fiyatlari()[kod]} TL",
                        "_d": (brut * _d(fa[kod]) * _d(GERCEK_FIYAT[kod]) * _kat(kod, BUTCE_P) * fin)})
        if (u["kod"], kod) in GERCEK_FIRE:
            b2 = _d(miktar) / (1 - _d(FIRE_SONRA))
            out.append({"kaynak": "recete", "malzeme": kod, "ad": MZ[kod][1], "aciklama": f"fire {FIRE_ONCE} -> {FIRE_SONRA}",
                        "_d": ((b2 - brut) * _d(fa[kod]) * _kat(kod, BUTCE_P) * fin)})
        para = MZ[kod][4]
        if MZ[kod][6] == "S" and para in GERCEK_KUR:
            out.append({"kaynak": "kur", "malzeme": kod, "ad": MZ[kod][1], "aciklama": f"{para} {BUTCE_P['kur'][para]} -> {GERCEK_P['kur'][para]}",
                        "_d": (brut * _d(fa[kod]) * (_d(GERCEK_P["kur"][para]) - _d(BUTCE_P["kur"][para])) * fin)})
    return out


def beklenenler(butce: dict, ekim: dict, kasim: dict, mizan: dict, havuz: dict) -> dict:
    fa, fg, fb = butce_fiyatlari(True), guncel_fiyatlar(), gerceklesen_fiyatlari()
    satis = satis_fiyatlari()
    urunler, yillik = {}, {k: D(0) for k in ("fiyat", "recete", "uretim", "gider", "kur", "enflasyon", "diger")}
    yillik_is = {k: D(0) for k in ("kur", "fiyat", "fire", "adet")}
    top_a = top_b = top_g = D(0)
    sok = {}
    sok_kav_yil = sok_usd_yil = kar_a = kar_g = D(0)
    for u in URUNLER:
        kod, adet = u["kod"], D(YILLIK_ADET[u["kod"]])
        ay = ayristir(u)
        mg = maliyet(u, fg, GUNCEL_P)["maliyet"]
        sadece_kav = maliyet(u, fg, BUTCE_P)["maliyet"] - ay["a"]
        sadece_usd = maliyet(u, fa, GUNCEL_P)["maliyet"] - ay["a"]
        hepsi_8 = maliyet(u, fa, _param({k: SOK_USD for k in BUTCE_P["kur"]}))["maliyet"] - ay["a"]
        for k, v in ay["adimlar"].items():
            yillik[k] += v * adet
        kalemler = _kalem_etkileri(u)
        is_ = {k: sum((x["_d"] for x in kalemler if x["kaynak"] == k), D(0)) for k in ("kur", "fiyat", "recete")}
        is_ = {"kur": is_["kur"], "fiyat": is_["fiyat"], "fire": is_["recete"], "adet": ay["adimlar"]["uretim"]}
        if abs(sum(is_.values(), D(0)) - (ay["b"] - ay["a"])) > D("0.00001"):
            raise RuntimeError(f"iş anlamında ayrıştırma toplamı tutmuyor: {kod} {is_} {ay['b'] - ay['a']}")
        for k, v in is_.items():
            yillik_is[k] += v * adet
        top_a += ay["a"] * adet
        top_b += ay["b"] * adet
        top_g += mg * adet
        sok_kav_yil += sadece_kav * adet
        sok_usd_yil += sadece_usd * adet
        kar_a += (satis[kod] - ay["a"]) * adet
        kar_g += (satis[kod] - mg) * adet
        mb = maliyet(u, fa, BUTCE_P)
        urunler[kod] = {
            "ad": u["ad"], "yillik_adet": int(adet), "gecen_yil_satis_fiyati": _s(satis[kod], 2),
            "butce": {"maliyet_tl": _s(ay["a"]), "satis_tl": _s(ay["a"] * D("1.2")), "toplam_birim_maliyet_tl": _s(mb["toplam_birim"]),
                      "malzeme": _s(mb["malzeme"]), "iscilik": _s(mb["iscilik"]), "gug": _s(mb["gug"]), "diger": _s(mb["diger"]),
                      "finansman": _s(mb["finansman"])},
            "guncel_sok_sonrasi": {"maliyet_tl": _s(mg), "fark_tl": _s(mg - ay["a"]), "kavanoz_zammi_tl": _s(sadece_kav),
                                   "usd_artisi_tl": _s(sadece_usd), "tum_kurlar_yuzde8_tl": _s(hepsi_8)},
            "gerceklesen": {"maliyet_tl": _s(ay["b"])},
            "fark_tl": _s(ay["b"] - ay["a"]),
            "ayristirma": {k: _s(v) for k, v in ay["adimlar"].items()},
            "is_anlaminda": {k: _s(v) for k, v in is_.items()},
            "kalemler": [{**{a: b for a, b in x.items() if a != "_d"}, "tl": _s(x["_d"])} for x in kalemler],
            "yillik_fark_tl": _s((ay["b"] - ay["a"]) * adet, 2),
        }
        sok[kod] = {"kavanoz": sadece_kav, "usd": sadece_usd}
    # SMM
    ort_e, ort_k = _ortalama_fiyatlar(ekim["veri"]), _ortalama_fiyatlar(kasim["veri"])
    smm_urun = {}
    for kod in SMM_MAMUL:
        q = smm_birim_miktarlar(kod)
        kav = q.get(KAVANOZ, D(0)) * (ort_k[KAVANOZ] - ort_e[KAVANOZ])
        usd = sum((qq * (ort_k[m_] - ort_e[m_]) for m_, qq in q.items() if m_ in MZ and MZ[m_][4] == "USD"), D(0))
        smm_urun[kod] = {"kavanoz_tl": _s(kav), "usd_tl": _s(usd), "fiyat_etkisi_tl": _s(kav + usd),
                         "butce_toplam_birim_maliyet_tl": _s(butce[kod]["toplam_birim"])}
    hiyar = SAYIM_EKSIGI["ekim"]["99.10.001"]
    m720_730 = mizan["720"] + mizan["730"]
    dagitilan = sum(havuz.values(), D(0))
    return {
        "aciklama": ("Üretici (test-dongusu/uret.py) bağımsız hesabı: Excel ürün sayfası formülleriyle (uygulama kodu kullanılmadan) birim "
                     "maliyetler. 'ayristirma': uygulamanın 'Sapmanın kaynağı' satırları (zincirleme ikame sırası fiyat -> reçete -> üretim -> "
                     "gider -> kur -> enflasyon -> diğer; uygulama gerçekleşende enflasyonu 0 alır). 'is_anlaminda': bilerek konan dört sapmanın "
                     "(kur / fiyat / fire / adet) kapalı formdan etkisi; toplamı aynıdır. Tutarlar TL, finansman dahil birim maliyet; "
                     "yıllık = birim x geçen yıl satış adedi."),
        "kaynak_eslemesi": {"kur": "kur", "adet": "uretim", "fire": "recete (uygulamada x1,25: fiilî fiyata bütçe enflasyonu da uygulanıyor)",
                            "fiyat": "fiyat + enflasyon + (recete - fire)"},
        "parametreler": {"butce": {"enflasyon": BUTCE_P["enflasyon"], "kur": BUTCE_P["kur"], "satis_kar": 0.20, "teklif_kar": BUTCE_P["teklif"]},
                         "guncel_sok_sonrasi": {"kur": GUNCEL_P["kur"], "kavanoz_fiyati": fg[KAVANOZ], "gecerlilik_basi": SOK_TARIHI.isoformat()},
                         "gerceklesen": {"kur": GERCEK_P["kur"], "enflasyon": 0, "fiyat": {k: fb[k] for k in GERCEK_FIYAT},
                                         "not": "stoklu (S) TL malzemelerin fiilî fiyatı = bütçe fiyatı x 1,25 (öngörülen enflasyon gerçekleşti)",
                                         "fire": {f"{FIRE_URUN} {FIRE_MALZEME}": [FIRE_ONCE, FIRE_SONRA]},
                                         "vardiya_uretim_adedi": {ADET_URUN: [UR[ADET_URUN]["vardiya"], GERCEK_VARDIYA[ADET_URUN]]}}},
        "sapmalar": [
            {"id": "a", "kaynak": "kur", "ne": "USD +%8 (42,00 -> 45,36), EUR +%5 (48,00 -> 50,40)", "uygulama_adimi": "Döviz kurları",
             "yillik_tl": _s(yillik_is["kur"], 2)},
            {"id": "b", "kaynak": "fiyat", "ne": "Test Kavanoz 370 ml +%15 (liste 6,40 -> 7,36; maliyete giren 8,00 -> 9,20); Test Kapya Biber −%10 "
                                                "(32,00 -> 28,80)", "uygulama_adimi": "Malzeme fiyatları + Enflasyon (birlikte)", "yillik_tl": _s(yillik_is["fiyat"], 2)},
            {"id": "c", "kaynak": "fire", "ne": "03.99.002'de Test Sirke firesi %2 -> %5", "uygulama_adimi": "Reçete (miktar, fire, elle fiyat)",
             "yillik_tl": _s(yillik_is["fire"], 2)},
            {"id": "d", "kaynak": "adet", "ne": "03.99.007'de vardiya üretim adedi 18.000 -> 14.400 (hedefin %80'i)", "uygulama_adimi": "Üretim bilgileri",
             "yillik_tl": _s(yillik_is["adet"], 2)},
        ],
        "urunler": urunler,
        "toplam": {"butce_yillik_maliyet_tl": _s(top_a, 2), "gerceklesen_yillik_maliyet_tl": _s(top_b, 2),
                   "yillik_sapma_tl": _s(top_b - top_a, 2), "kaynaga_gore_yillik_tl": {k: _s(v, 2) for k, v in yillik.items()},
                   "is_anlaminda_yillik_tl": {k: _s(v, 2) for k, v in yillik_is.items()},
                   "guncel_yillik_maliyet_tl": _s(top_g, 2)},
        "sok": {"kavanoz_yillik_tl": _s(sok_kav_yil, 2), "usd_yillik_tl": _s(sok_usd_yil, 2), "toplam_yillik_tl": _s(top_g - top_a, 2),
                "karlilik_yillik_kar_butce_tl": _s(kar_a, 2), "karlilik_yillik_kar_guncel_tl": _s(kar_g, 2)},
        "smm": {"uretim_ay": URETIM_AY, "mizan": {k: str(v) for k, v in mizan.items()}, "havuz": {k: str(v) for k, v in havuz.items()},
                "dagitilan": str(dagitilan), "dagitilmayan": str(m720_730 - dagitilan),
                "dagitilmayan_orani": _s((m720_730 - dagitilan) / m720_730, 4),
                "sayim_farki": {"kod": "99.10.001", "miktar_kg": hiyar, "tutar_tl": _s(ort_e["99.10.001"] * hiyar, 2)},
                "ekim_alim_fiyati": {k: str(v) for k, v in smm_fiyatlari("ekim").items()},
                "kasim_alim_fiyati": {k: str(v) for k, v in smm_fiyatlari("kasim").items() if v != smm_fiyatlari("ekim")[k]},
                "kavanoz_ortalama_fiyat": {"ekim": _s(ort_e[KAVANOZ]), "kasim": _s(ort_k[KAVANOZ])},
                "kasim_fiyat_etkisi": smm_urun},
    }


# ======================================================================================= ana
def main() -> None:
    CIKTI.mkdir(parents=True, exist_ok=True)
    butce = {u["kod"]: maliyet(u, butce_fiyatlari(True), BUTCE_P) for u in URUNLER}
    butce_birim = {k: v["toplam_birim"] for k, v in butce.items()}
    dosyalar = [
        fiyat_kitabi("fiyat-calismasi-butce", butce_fiyatlari(), BUTCE_P),
        satin_alma_eksik_fiyatlar(), satis_gecmisi(), liste_fiyatlari(), fiyat_listesi_kasim(),
        fiyat_kitabi("fiyat-calismasi-gerceklesen", gerceklesen_fiyatlari(), GERCEK_P, GERCEK_VARDIYA, GERCEK_FIRE),
    ]
    ekim = smm_ay("ekim", None, butce_birim)
    kasim = smm_ay("kasim", ekim["veri"], butce_birim)
    mizan, havuz = gider_mizani(butce)
    dosyalar += [smm_ekim_kitabi(ekim, mizan, havuz, _stok_mizani("ekim", ekim["veri"], butce_birim)), canias_receteleri()]
    dosyalar += smm_kasim_dosyalari(kasim, mizan, _stok_mizani("kasim", kasim["veri"], butce_birim))
    for d in dosyalar:
        print(f"yazıldı: {d.relative_to(BURASI.parent)}")
    BEKLENEN.write_text(json.dumps(beklenenler(butce, ekim, kasim, mizan, havuz), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"yazıldı: {BEKLENEN.relative_to(BURASI.parent)}")
    print(f"{len(dosyalar)} Excel + 1 JSON")


if __name__ == "__main__":
    sys.exit(main())
