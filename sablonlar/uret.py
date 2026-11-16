"""Excel yükleme şablonlarını üretir: uygulamada Excel yüklenen her nokta için TEK dosya, üç sayfa
(doldurulacak sayfa + "Örnek" + "Açıklama"). Örnek değerler uydurmadır (şirket verisi yok; kodlar 99. ile başlar).

Biçimler uygulamanın okuyucularından alınmıştır (okuyucu değişirse burası da güncellenmeli; doğrulama: 11-16-2026-dogrula.py):
- Veri Aktar: backend/servisler/aktarim_servisi.py (S.ALMA BF, Üretim Adetleri, Gider Dağıtım), recete_aktarim_servisi.py (ürün sayfası),
  stok_devri_servisi.py (Stokta kalan); fiyat_motoru/excel_okuyucu.py.
- Malzeme Fiyatları › Fiyat listesi yükle: backend/servisler/import_servisi.py (fiyat_listesi_onizle: ilk sayfa, A / F / I).
- Satış geçmişi: satis_okuyucu.py; Liste fiyatları: liste_servisi.py (ikisi de ilk sayfa, ilk satır başlık).
- Maliyet Muhasebesi: smm_veri_servisi.py KAYNAKLAR (aylık kaynaklar), smm_recete_servisi.py (Canias ürün ağacı dökümü).

Doldurulacak sayfanın adı okuyucunun aradığı addır ve kitabın İLK sayfasıdır: kullanıcı doldurup dosyayı doğrudan yükleyebilir
("Örnek" ve "Açıklama" sayfaları sonda durur, okuyucu onları okumaz).

Kullanım (proje kökünden):  .venv\\Scripts\\python.exe sablonlar\\uret.py
Yeniden çalıştırılabilir: yalnız sablonlar/11-16-2026-NN-*.xlsx dosyalarının üzerine yazar.
"""
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

BURASI = Path(__file__).resolve().parent
ON = "11-16-2026-"
sys.path.insert(0, str(BURASI.parent))
from backend.servisler.excel_ortak import SABLONLAR as _KIMLIK_ADLARI, sablon_kimligi_yaz  # noqa: E402

KIMLIKLER = list(_KIMLIK_ADLARI)   # 01 → satin_alma_fiyat_listesi ... 16 → smm_stok_mizani

# ------------------------------------------------------------------------------------------------ stiller
Z_DOLGU = PatternFill("solid", fgColor="1E5631")      # zorunlu: koyu yeşil
Z_YAZI = Font(bold=True, color="FFFFFF")
I_DOLGU = PatternFill("solid", fgColor="E3E3E3")      # isteğe bağlı: açık gri
I_YAZI = Font(bold=True, color="1F1F1F")
O_DOLGU = PatternFill("solid", fgColor="F6F6F6")      # uygulama okumaz: çok açık gri, italik
O_YAZI = Font(bold=True, italic=True, color="8A8A8A")
GIRDI_Z = PatternFill("solid", fgColor="D8EBD9")      # düzen sayfalarında doldurulacak zorunlu hücre
GIRDI_I = PatternFill("solid", fgColor="F0F0F0")      # düzen sayfalarında isteğe bağlı hücre
KALIN = Font(bold=True)
BASLIK_YAZI = Font(bold=True, size=13, color="1E5631")
SOLUK = Font(italic=True, color="6A6A6A")
INCE = Side(style="thin", color="BFBFBF")
CERCEVE = Border(left=INCE, right=INCE, top=INCE, bottom=INCE)
SARMA = Alignment(wrap_text=True, vertical="top")

BICIM = {"metin": "@", "para": "#,##0.00", "sayi": "General", "tarih": "dd.mm.yyyy", "oran": "0.00", "tam": "0", "yil": "0"}
DURUM_ADI = {"Z": "Zorunlu", "I": "İsteğe bağlı", "O": "Okunmaz"}
PARA_BIRIMLERI = "TL,USD,EUR,GBP,CHF,RUB,ZAR"


@dataclass
class Sutun:
    baslik: str
    durum: str            # Z zorunlu, I isteğe bağlı, O uygulama okumaz (yalnız düzen/bilgi için)
    genislik: int
    bicim: str
    aciklama: str
    ornek: str = ""
    liste: str | None = None   # Excel açılır listesi (virgülle ayrılmış)
    liste_kati: bool = True    # False: listede olmayan değer de yazılabilir (yalnız öneri)


@dataclass
class Sablon:
    no: str
    ad: str                   # dosya adı parçası
    baslik: str               # "Ne için"
    nereye: str               # Menü › sayfa › düğme
    kim: str
    siklik: str
    okuma: list[str]          # okuyucunun kuralları
    hatalar: list[str]        # sık hatalar
    sayfa: str = ""           # doldurulacak sayfanın adı
    sutunlar: list[Sutun] = field(default_factory=list)
    ornek: list[list] = field(default_factory=list)
    baslik_satiri: int = 1
    ust_baslik: str | None = None
    ara_satir: list | None = None   # başlığın altında birim satırı (Üretim Adetleri)
    uygulama_sablonu: str | None = None   # uygulamada zaten "Şablonu indir" varsa adresi
    baglanti: str = ""        # "Şablonu indir" bağlantısı nereye eklenmeli
    duzen: str | None = None  # "gider" | "recete": sabit hücre düzeni (tablo değil)

    @property
    def dosya(self) -> Path:
        return BURASI / f"{ON}{self.no}-{self.ad}.xlsx"


# ------------------------------------------------------------------------------------------------ tablo sayfaları
def _baslik_hucresi(c, durum: str) -> None:
    c.font = {"Z": Z_YAZI, "I": I_YAZI, "O": O_YAZI}[durum]
    c.fill = {"Z": Z_DOLGU, "I": I_DOLGU, "O": O_DOLGU}[durum]
    c.alignment = Alignment(wrap_text=True, vertical="center")
    c.border = CERCEVE


def tablo_sayfasi(ws, t: Sablon, satirlar: list[list]) -> None:
    """Başlık satırı (zorunlu yeşil / isteğe bağlı gri / okunmaz soluk), dondurulmuş, sütun biçimli, açılır listeli tablo."""
    r0 = t.baslik_satiri
    if t.ust_baslik:
        ws.cell(row=1, column=1, value=t.ust_baslik).font = SOLUK
    for i, s in enumerate(t.sutunlar, start=1):
        _baslik_hucresi(ws.cell(row=r0, column=i, value=s.baslik), s.durum)
        harf = get_column_letter(i)
        ws.column_dimensions[harf].width = s.genislik
        ws.column_dimensions[harf].number_format = BICIM[s.bicim]
    ws.row_dimensions[r0].height = 32
    veri = r0 + 1
    if t.ara_satir:
        for i, v in enumerate(t.ara_satir, start=1):
            c = ws.cell(row=veri, column=i, value=v or None)
            c.font = SOLUK
        veri += 1
    ws.freeze_panes = f"A{veri}"
    for i, s in enumerate(t.sutunlar, start=1):
        if s.liste:
            dv = DataValidation(type="list", formula1=f'"{s.liste}"', allow_blank=True, showErrorMessage=s.liste_kati,
                                errorTitle="Geçersiz değer", error=f"Şu değerlerden biri olmalı: {s.liste}")
            dv.add(f"{get_column_letter(i)}{veri}:{get_column_letter(i)}{veri + 4999}")
            ws.add_data_validation(dv)
    for n, satir in enumerate(satirlar):
        for i, v in enumerate(satir, start=1):
            if v is None:
                continue
            c = ws.cell(row=veri + n, column=i, value=v)
            c.number_format = BICIM[t.sutunlar[i - 1].bicim] if i <= len(t.sutunlar) else "General"


def aciklama_sayfasi(ws, t: Sablon, hucreler: list[tuple] | None = None) -> None:
    """Sütun (ya da hücre) açıklamaları, uygulamada nereye yüklendiği, okuma kuralları, sık hatalar."""
    for harf, w in zip("ABCDE", (30, 14, 74, 24, 18)):
        ws.column_dimensions[harf].width = w
    ws["A1"] = f"Şablon {t.no} · {t.baslik}"
    ws["A1"].font = BASLIK_YAZI
    satir = 3

    def yaz(etiket: str, metin: str) -> None:
        nonlocal satir
        ws.cell(row=satir, column=1, value=etiket).font = KALIN
        c = ws.cell(row=satir, column=3, value=metin)
        c.alignment = SARMA
        satir += 1

    yaz("Uygulamada nereye yüklenir", t.nereye)
    yaz("Kim doldurur / ne sıklıkla", f"{t.kim} · {t.siklik}")
    if t.duzen is None:
        yaz("Doldurulacak sayfa", f"İlk sayfa ('{t.sayfa}'). Başlık satırı {t.baslik_satiri}. satırdadır; adını ve başlık metinlerini değiştirmeyin. "
            "'Örnek' ve 'Açıklama' sayfaları dosyada kalabilir, uygulama onları okumaz.")
    else:
        yaz("Doldurulacak sayfa", f"'{t.sayfa}' sayfası (sabit hücre düzeni). Yeşil hücreler zorunlu, gri hücreler isteğe bağlıdır. "
            "Satır ve sütun eklemeyin / silmeyin: uygulama değerleri hücre adresinden okur.")
    satir += 1
    ws.cell(row=satir, column=1, value="Uygulama dosyayı nasıl okur").font = KALIN
    satir += 1
    for m in t.okuma:
        c = ws.cell(row=satir, column=3, value="• " + m)
        c.alignment = SARMA
        satir += 1
    satir += 1
    basliklar = ("Sütun", "Durum", "Ne demek", "Örnek değer", "Biçim") if hucreler is None else ("Hücre", "Durum", "Ne demek", "Örnek değer", "Biçim")
    for i, b in enumerate(basliklar, start=1):
        c = ws.cell(row=satir, column=i, value=b)
        c.font = Z_YAZI; c.fill = Z_DOLGU; c.border = CERCEVE
    satir += 1
    kalemler = hucreler if hucreler is not None else [
        (f"{get_column_letter(i)} · {s.baslik}", s.durum, s.aciklama, s.ornek, _bicim_adi(s)) for i, s in enumerate(t.sutunlar, start=1)]
    for hucre, durum, ne, ornek, bicim in kalemler:
        degerler = (hucre, DURUM_ADI.get(durum, durum), ne, ornek, bicim)
        for i, v in enumerate(degerler, start=1):
            c = ws.cell(row=satir, column=i, value=v)
            c.alignment = SARMA; c.border = CERCEVE
            if i == 2:
                c.fill = {"Z": GIRDI_Z, "I": GIRDI_I}.get(durum, PatternFill())
        satir += 1
    satir += 1
    ws.cell(row=satir, column=1, value="Sık hatalar").font = KALIN
    satir += 1
    for m in t.hatalar:
        c = ws.cell(row=satir, column=3, value="• " + m)
        c.alignment = SARMA
        satir += 1
    satir += 1
    ws.cell(row=satir, column=1, value="Renkler").font = KALIN
    ws.cell(row=satir, column=3, value="Koyu yeşil başlık: zorunlu · açık gri: isteğe bağlı · soluk italik: uygulama okumaz (yer tutucu, boş kalabilir).")
    ws.cell(row=satir + 1, column=3, value="Örnek sayfasındaki değerler uydurmadır (99. ile başlayan kodlar); gerçek veri yerine geçmez.").font = SOLUK


def _bicim_adi(s: Sutun) -> str:
    ad = {"metin": "metin", "para": "sayı (TL / para)", "sayi": "sayı", "tarih": "tarih (GG.AA.YYYY)", "oran": "oran (0,40 = %40)",
          "tam": "tam sayı", "yil": "yıl (YYYY)"}[s.bicim]
    return f"{ad}; liste: {s.liste.replace(',', ', ')}" if s.liste else ad


# ------------------------------------------------------------------------------------------------ ortak örnek veri (uydurma)
URUN1 = ("99.03.001", "Test Berrak Turşu 370 ml")
URUN2 = ("99.03.002", "Test Berrak Turşu 720 ml")
URUN3 = ("99.03.003", "Test Közlenmiş Biber 370 ml")

# ------------------------------------------------------------------------------------------------ 01 / 02: S.ALMA BF düzeni
def _salma_sutunlari(fiyat_listesi: bool) -> list[Sutun]:
    o = "O" if fiyat_listesi else None   # fiyat listesi yüklemesi yalnız A, F, I okur
    return [
        Sutun("Malzeme", "Z", 13, "metin", "Malzeme kodu (Canias / ERP kodu). Boş satır atlanır.", "99.10.001"),
        Sutun("Açıklama", o or "Z", 30, "metin", "Malzeme adı. Başlık 'Açıklama' ile başlamalı." if not o else "Bilgi için; bu yükleme okumaz.",
              "Test Taze Hıyar"),
        Sutun("Malzeme Tipi", o or "I", 22, "metin", "Malzeme tipi (kart bilgisi)." if not o else "Bilgi için; bu yükleme okumaz.", "0001-Hammadde"),
        Sutun("Stok Birimi", o or "I", 11, "metin", "Stok birimi (KG, LT, AD...)." if not o else "Bilgi için; bu yükleme okumaz.", "KG"),
        Sutun("Para Birimi", o or "Z", 11, "metin", "Fiyatın para birimi. Başlık 'Para' ile başlamalı." if not o else "Bilgi için; bu yükleme okumaz.",
              "TL", liste=PARA_BIRIMLERI),
        Sutun("Bütçe Birim Fiyatları", "Z", 20, "para",
              "İlk bütçe birim fiyatı (para birimi E sütununda). Sayı hücresi olmalı; negatif olamaz. Boşsa o satıra fiyat yazılmaz."
              + (" Başlıkta 'fiyat' geçmeli." if not o else ""), "18,50"),
        Sutun("Z/S", o or "I", 6, "metin", "Z = zirai (TL fiyata enflasyon eklenmez), S = sanayi (eklenir)." if not o else "Bilgi için; bu yükleme okumaz.",
              "Z", liste="Z,S"),
        Sutun("Not", "O", 18, "metin", "Serbest not; uygulama okumaz.", "Temmuz zammı"),
        Sutun("Revize Bütçe Birim Fiyatı", "I", 22, "para",
              "Sonradan güncellenen fiyat (revize). Doluysa ve F'den farklıysa geçerli fiyat budur; F geçmişte 'ilk bütçe' olarak kalır. "
              "Başlık boş ya da 'fiyat' içermeli, yoksa bu sütun yok sayılır.", "6,90"),
    ]


SALMA_ORNEK = [
    ["99.10.001", "Test Taze Hıyar", "0001-Hammadde", "KG", "TL", 18.5, "Z", None, None],
    ["99.11.001", "Test Tuz", "0017-Yardımcı Malzeme", "KG", "TL", 4.2, "S", None, None],
    ["99.11.003", "Test Sitrik Asit", "0017-Yardımcı Malzeme", "KG", "USD", 2.1, "S", None, None],
    ["99.20.001", "Test Kavanoz 370 ml", "0008-Ambalaj Malzeme", "AD", "TL", 6.4, "S", "Revize", 6.9],
    ["99.20.003", "Test Kapak 63 mm", "0008-Ambalaj Malzeme", "AD", "TL", 2.15, "S", None, None],
    ["99.20.007", "Test Koli 12'li", "0008-Ambalaj Malzeme", "AD", "TL", 11.5, "S", None, None],
]
FIYAT_LISTESI_ORNEK = [
    ["99.10.001", "Test Taze Hıyar", "0001-Hammadde", "KG", "TL", 19.9, "Z", "Temmuz zammı", None],
    ["99.11.001", "Test Tuz", "0017-Yardımcı Malzeme", "KG", "TL", 4.2, "S", "Değişmedi", None],
    ["99.20.001", "Test Kavanoz 370 ml", "0008-Ambalaj Malzeme", "AD", "TL", 6.4, "S", "Revize", 7.2],
    ["99.20.003", "Test Kapak 63 mm", "0008-Ambalaj Malzeme", "AD", "TL", 2.3, "S", None, None],
]

SATIN_ALMA = Sablon(
    no="01", ad="satin-alma-fiyat-listesi", baslik="Satın alma fiyat listesi (malzeme kartı + bütçe fiyatı)",
    nereye="Fiyat Çalışması › Veri Aktar › 'Satın alma fiyat listesi' sekmesi → dosya seç → Önizle → neden + geçerlilik tarihi → Uygula",
    kim="Satın alma (muhasebe kontrol eder)", siklik="Sezon başında; yeni malzeme açılınca",
    okuma=["'S.ALMA BF' adlı sayfa okunur (ad büyük/küçük harf ve boşluk duyarsız); dosyada tek veri sayfası varsa adı ne olursa olsun o sayfa "
           "okunur. Birden çok sayfa varsa ve hiçbiri 'S.ALMA BF' değilse dosya reddedilir.",
           "Sütunlar BAŞLIK ADIYLA bulunur (sıra serbest; büyük/küçük, Türkçe harf, boşluk farkı önemsiz). Zorunlu: Malzeme (= Malzeme Kodu, "
           "Stok Kodu), Açıklama (= Malzeme Adı), Para Birimi (= Döviz, PB), Bütçe Birim Fiyatları (= Birim Fiyat, Fiyat). İsteğe bağlı: Malzeme "
           "Tipi, Stok Birimi (= Birim), Z/S, Revize (yoksa fiyat sütunundan sonraki ikinci fiyat sütunu, klasik düzende I).",
           "Sistemde olmayan kod için malzeme kartı açılır; var olan kartın farkları yalnız 'kartları güncelle' işaretliyse yazılır.",
           "Fiyatlar seçilen geçerlilik tarihiyle EKLENİR (eski fiyat silinmez, geçmişte kalır). Metin sayı ('18,50 TL') çevrilir; çevrilemeyen "
           "fiyat varsa satır sorunlu listelenir ve düzeltilene kadar hiçbir şey yazılmaz. Önizlemede %15 (TL) / %10 (döviz) üzeri fiyat "
           "değişimleri uyarı olarak çıkar.",
           "Son yükleme geri alınabilir: eklenen fiyatlar silinir, açılan kartlar kaldırılır, güncellenen kartlar eski haline döner."],
    hatalar=["Fiyat hücresine sayı olmayan bir şey yazmak ('yok', '-?'): satır sorunlu listesine düşer ve uygula reddedilir.",
             "Başka ekranın şablonunu (ör. üretim adetleri) bu ekrana yüklemek: 'Bu dosya … şablonu' diye reddedilir.",
             "Kodun başında/sonunda boşluk: uygulama kırpar, ama Excel'deki VLOOKUP'lar bulamaz; kodları temiz yazın.",
             "Aynı kod iki kez: son satır geçerli olur (önizlemede uyarı olarak görünür); tekrarları silin."],
    sayfa="S.ALMA BF", sutunlar=_salma_sutunlari(False), ornek=SALMA_ORNEK,
    baglanti="Veri Aktar › Satın alma fiyat listesi sekmesinin açıklama kutusuna (AktarimFormu) 'Şablonu indir'")

FIYAT_LISTESI = Sablon(
    no="02", ad="malzeme-fiyat-listesi", baslik="Malzeme fiyat listesi (fiyat güncelleme / revize)",
    nereye="Fiyat Çalışması › Malzeme Fiyatları › 'Fiyat listesi yükle' → dosya + geçerlilik tarihi → Önizle → neden → Uygula",
    kim="Satın alma", siklik="Gerektikçe (fiyat değişince, revize gelince)",
    okuma=["'S.ALMA BF' adlı sayfa, yoksa ilk veri sayfası okunur. Başlık satırı ilk 30 satırda aranır; sütunlar BAŞLIK ADIYLA bulunur.",
           "Zorunlu: malzeme kodu (Malzeme / Malzeme Kodu / Stok Kodu) ve fiyat (Bütçe Birim Fiyatları / Birim Fiyat / Fiyat). Revize: 'Revize' "
           "başlıklı sütun ya da fiyat sütunundan sonraki ikinci fiyat sütunu (klasik düzende I). Diğer sütunlar bilgi içindir.",
           "Revize doluysa ve F'den farklıysa geçerli fiyat revizedir; F 'ilk bütçe' olarak yanına kaydedilir.",
           "Yalnız sistemde fiyatı olan ve fiyatı DEĞİŞEN kodlar yazılır. Kartı / fiyatı olmayan kodlar önizlemede 'yeni' görünür ama YAZILMAZ: "
           "onlar için şablon 01 (Veri Aktar › Satın alma fiyat listesi) kullanılır.",
           "Elle girilmiş (Malzeme Fiyatları ekranından yazılmış) geçerli fiyatlar varsayılan olarak KORUNUR; önizlemede 'korunsun / üzerine "
           "yazılsın' seçilir. %15 (TL) / %10 (döviz) üzeri değişimler uyarı olarak listelenir.",
           "Bu dosya şablon 01 ile aynı düzendedir: aynı dosya Veri Aktar'a da yüklenebilir (orada kart bilgileri de okunur). Son yükleme "
           "geri alınabilir (eklenen fiyat kayıtları silinir)."],
    hatalar=["CSV ya da eski .xls yüklemek: dosya seçici yalnız .xlsx / .xlsm gösterir; başka uzantı anlaşılır bir mesajla reddedilir.",
             "Fiyat hücresine sayıya çevrilemeyen bir şey yazmak: satır sorunlu listesine düşer, yazılmaz (0 yazılmaz).",
             "Yeni malzemeyi bu ekrandan eklemeye çalışmak: 'yeni' satırlar yazılmaz; Veri Aktar › Satın alma fiyat listesi kullanın.",
             "Elle düzeltilmiş fiyatı listeyle ezmek istemek: önizlemede 'üzerine yazılsın'ı seçin (varsayılan: korunur)."],
    sayfa="S.ALMA BF", sutunlar=_salma_sutunlari(True), ornek=FIYAT_LISTESI_ORNEK,
    baglanti="Malzeme Fiyatları › 'Fiyat listesi yükle' penceresine (FiyatListesiYukle) 'Şablonu indir'")

# ------------------------------------------------------------------------------------------------ 03 Üretim adetleri
URETIM_ADETLERI = Sablon(
    no="03", ad="uretim-adetleri", baslik="Üretim adetleri (vardiya kapasitesi ve hedef üretim)",
    nereye="Fiyat Çalışması › Veri Aktar › 'Üretim adetleri' sekmesi → dosya → Önizle → neden → Uygula",
    kim="Muhasebe (üretim planlamadan gelen değerlerle)", siklik="Sezon başında; üretim planı değişince",
    okuma=["'Üretim Adetleri' adlı sayfa okunur (ad esnek); dosyada tek veri sayfası varsa o sayfa okunur.",
           "Başlık satırı ilk 30 satırda aranır (şablonda 2. satır); hemen altındaki birim satırı ('(adet)', '(saat)') atlanır.",
           "Sütunlar BAŞLIK ADIYLA bulunur; büyük/küçük harf ve İ/ı farkı önemsiz ('Hedef vardiyalık üretim' = 'HEDEF VARDIYALIK URETIM'). "
           "Zorunlu: ÜRÜN KODU (= Stok Kodu), HEDEF VARDİYALIK ÜRETİM (= Hedef Üretim). Diğerleri isteğe bağlı; klasik düzende (A kod, G hedef) "
           "adı tanınmayan sütunlar C-F, H sırasıyla okunur.",
           "Boş ve '-' hücre 0 sayılır; metin sayı ('18.000,5') çevrilir; çevrilemeyen hücre ('#DIV/0!', 'abc') satırı sorunlu yapar, o satır "
           "yazılmaz. Aynı kod iki kez varsa ilk satır alınır.",
           "Yükleme günceller / ekler, dosyada olmayan ürünlerin kaydı silinmez. Son yükleme geri alınabilir."],
    hatalar=["Hücreye '#DIV/0!' gibi hata değeri bırakmak: o ürün sorunlu listesine düşer ve yazılmaz; önizlemedeki listeyi kontrol edin.",
             "Başka ekranın şablonunu (ör. gider dağıtım) yüklemek: 'Bu dosya … şablonu' diye reddedilir.",
             "Ürün kodu ürün kartındaki kodla aynı olmalı; farklı yazılan kod ayrı satır olarak kaydedilir."],
    sayfa="Üretim Adetleri", baslik_satiri=2, ust_baslik="ÜRETİM ADETLERİ (bu satır serbest; başlıklar 2. satırda)",
    ara_satir=["", "", "(adet)", "(saat)", "(adet)", "(saat)", "(adet)", "(kişi)"],
    sutunlar=[
        Sutun("ÜRÜN KODU", "Z", 13, "metin", "Ürün kodu (ürün kartındaki kodla aynı).", URUN1[0]),
        Sutun("ÜRÜN ADI", "Z", 32, "metin", "Ürün adı. Başlık zorunlu; değer boş kalabilir.", URUN1[1]),
        Sutun("NET SÜREDEKİ VARDİYALIK KAPASİTE", "I", 18, "sayi", "Net çalışma süresinde vardiya başına kapasite (adet). Boş = 0.", "20.700"),
        Sutun("NET SÜRE", "I", 10, "sayi", "Net çalışma süresi (saat). Boş = 0.", "6,5"),
        Sutun("TOPLAM SÜREDEKİ KAPASİTE", "I", 16, "sayi", "Toplam sürede vardiya başına kapasite (adet). Boş = 0.", "23.400"),
        Sutun("TOPLAM SÜRE", "I", 10, "sayi", "Toplam vardiya süresi (saat). Boş = 0.", "7,5"),
        Sutun("HEDEF VARDİYALIK ÜRETİM", "Z", 16, "sayi", "Hedeflenen vardiya üretim adedi. Başlık adı esnek (büyük/küçük harf, İ/ı ve boşluk farkı önemsiz).", "18.000"),
        Sutun("ORTALAMA İŞÇİ SAYISI", "I", 14, "sayi", "Vardiyadaki ortalama işçi sayısı (kişi). Boş = 0.", "17"),
    ],
    ornek=[[URUN1[0], URUN1[1], 20700, 6.5, 23400, 7.5, 18000, 17],
           [URUN2[0], URUN2[1], 13800, 6.5, 15600, 7.5, 12000, 17],
           [URUN3[0], URUN3[1], 17250, 6.5, 19500, 7.5, 15000, 19]],
    baglanti="Veri Aktar › Üretim adetleri sekmesi (AktarimFormu) ve Fiyat Çalışması › Üretim Adetleri sayfası başlığı")

# ------------------------------------------------------------------------------------------------ 04 Gider dağıtım (sabit hücre düzeni)
# Okuyucu: excel_okuyucu.havuzlari_oku + aktarim_servisi._gider_duzen_kontrol. (hücre, durum, ne, örnek)
GIDER_ORNEK = {
    "D4": 9720000, "F4": 360000000, "A6": 2400000, "D13": 1800000, "F13": 90000000, "D18": 5000000, "F18": 30000000,
    "A20": 1200000, "D27": 4000000, "F27": 30000000, "D38": 3640000, "D49": 1500000, "D60": 6000000, "D64": 10400000, "D67": 12500000,
}
GIDER_SINIFLAR = [("Taze/Taze", 1000000, 0.2), ("Taze/Turşu", 1500000, 0.3), ("Turşu/Turşu", 2500000, 0.5)]
GIDER_HATLAR = [("Kavanoz Hattı", 18000000, 0.55), ("Teneke Hattı", 6000000, 0.25), ("Sos Hattı", 6000000, 0.2)]
GIDER_AMBALAJ = [("370 ml", 370, 9000000, 1), ("720 ml", 720, 4000000, 1.6), ("340 g", 340, 3000000, 0.9), ("500 g", 500, 1500000, 1.2),
                 ("2,5 kg", 2.5, 600000, 4)]


def gider_sayfasi(ws, dolu: bool) -> None:
    def etiket(h, metin, kalin=True):
        ws[h] = metin
        if kalin:
            ws[h].font = KALIN

    def girdi(h, deger, zorunlu=True, bicim="#,##0.00"):
        c = ws[h]
        c.fill = GIRDI_Z if zorunlu else GIRDI_I
        c.border = CERCEVE
        c.number_format = bicim
        if dolu and deger is not None:
            c.value = deger

    ws["A1"] = "GİDER DAĞITIM TABLOSU (yeşil hücreler zorunlu; satır/sütun eklemeyin)"
    ws["A1"].font = BASLIK_YAZI
    # Dolum
    etiket("A3", "Dolum Doğrudan İşçilik"); etiket("D3", "Gider Toplamı"); etiket("F3", "Toplam adam-saniye")
    girdi("D4", GIDER_ORNEK["D4"]); girdi("F4", GIDER_ORNEK["F4"], bicim="#,##0")

    etiket("A5", "Mal Kabul ve Fermantasyon İşçilik: toplam A6, sınıf payları C7:G9")
    girdi("A6", GIDER_ORNEK["A6"])
    etiket("C6", "Sınıf (Taze / Turşu)"); etiket("E6", "Baz (kg)"); etiket("G6", "Pay (oran)")
    for i, r in enumerate(range(7, 10)):
        ad, kg, pay = GIDER_SINIFLAR[i]
        girdi(f"C{r}", ad, bicim="@"); girdi(f"E{r}", kg, bicim="#,##0"); girdi(f"G{r}", pay, bicim="0.00")
    etiket("A12", "Etiketleme İşçilik"); etiket("D12", "Gider Toplamı"); etiket("F12", "Toplam adam-saniye")
    girdi("D13", GIDER_ORNEK["D13"]); girdi("F13", GIDER_ORNEK["F13"], bicim="#,##0")
    etiket("A17", "Endirekt İşçilik"); etiket("D17", "Gider Toplamı"); etiket("F17", "Toplam adam-saniye")
    girdi("D18", GIDER_ORNEK["D18"]); girdi("F18", GIDER_ORNEK["F18"], bicim="#,##0")
    etiket("A19", "Mal Kabul ve Fermantasyon GÜG: toplam A20, sınıf payları C21:G23")
    girdi("A20", GIDER_ORNEK["A20"])
    for i, r in enumerate(range(21, 24)):
        ad, kg, pay = GIDER_SINIFLAR[i]
        girdi(f"C{r}", ad, bicim="@"); girdi(f"E{r}", kg, bicim="#,##0"); girdi(f"G{r}", pay, bicim="0.00")
    etiket("A26", "Diğer Genel Üretim Giderleri"); etiket("D26", "Gider Toplamı"); etiket("F26", "Toplam adam-saniye")
    girdi("D27", GIDER_ORNEK["D27"]); girdi("F27", GIDER_ORNEK["F27"], bicim="#,##0")
    for bas, toplam_h, ad in ((30, "D38", "Elektrik"), (41, "D49", "Doğalgaz"), (52, "D60", "Amortisman")):
        etiket(f"A{bas - 1}", f"{ad}: hat adları A{bas}:A{bas + 7}"); etiket(f"E{bas - 1}", "Baz (saniye)"); etiket(f"G{bas - 1}", "Pay (oran)")
        for i, r in enumerate(range(bas, bas + 8)):
            h = GIDER_HATLAR[i] if i < len(GIDER_HATLAR) else None
            ilk = i < len(GIDER_HATLAR)
            girdi(f"A{r}", h[0] if h else None, zorunlu=ilk, bicim="@")
            girdi(f"E{r}", h[1] if h else None, zorunlu=ilk, bicim="#,##0")
            girdi(f"G{r}", h[2] if h else None, zorunlu=ilk, bicim="0.00")
        etiket(f"C{toplam_h[1:]}", "Toplam")
        girdi(toplam_h, GIDER_ORNEK[toplam_h])
    etiket("A63", "Genel Yönetim Giderleri"); etiket("D63", "Gider Toplamı"); girdi("D64", GIDER_ORNEK["D64"])
    etiket("A66", "Pazarlama Satış Giderleri"); etiket("D66", "Gider Toplamı"); girdi("D67", GIDER_ORNEK["D67"])
    etiket("A69", "Ambalaj"); etiket("B69", "Hacim"); etiket("C69", "Üretim Adedi"); etiket("D69", "Katsayı")
    for i, r in enumerate(range(70, 92)):
        a = GIDER_AMBALAJ[i] if i < len(GIDER_AMBALAJ) else None
        ilk = i < len(GIDER_AMBALAJ)
        girdi(f"A{r}", a[0] if a else None, zorunlu=ilk, bicim="@")
        girdi(f"B{r}", a[1] if a else None, zorunlu=ilk, bicim="General")
        girdi(f"C{r}", a[2] if a else None, zorunlu=ilk, bicim="#,##0")
        girdi(f"D{r}", a[3] if a else None, zorunlu=ilk, bicim="0.00")
    ws.column_dimensions["A"].width = 40
    for col in "BCDEFG":
        ws.column_dimensions[col].width = 18
    ws.freeze_panes = "A2"


GIDER_HUCRELERI = [
    ("D3, D12, D17, D26, D63, D66", "Z", "Etiket 'Gider Toplamı' (değiştirmeyin). Uygulama bu etiketlerle düzeni tanır.", "Gider Toplamı", "metin"),
    ("A69", "Z", "Etiket 'Ambalaj' (değiştirmeyin).", "Ambalaj", "metin"),
    ("D4 / F4", "Z", "Dolum doğrudan işçilik: yıllık gider toplamı (TL) / toplam adam-saniye (dağıtım bazı, 0'dan büyük).", "9.720.000 / 360.000.000", "sayı"),
    ("A6", "Z", "Mal kabul ve fermantasyon işçilik gider toplamı (TL).", "2.400.000", "sayı"),
    ("C7:C9, E7:E9, G7:G9", "Z", "Mal kabul işçilik: sınıf adı (ürün kartındaki 'Taze / Turşu' değeriyle birebir), baz kg, pay oranı. En çok 3 sınıf.",
     "Turşu/Turşu · 2.500.000 · 0,50", "metin / sayı / oran"),
    ("D13 / F13", "Z", "Etiketleme işçilik: gider toplamı / toplam adam-saniye.", "1.800.000 / 90.000.000", "sayı"),
    ("D18 / F18", "Z", "Endirekt işçilik: gider toplamı / toplam adam-saniye.", "5.000.000 / 30.000.000", "sayı"),
    ("A20", "Z", "Mal kabul ve fermantasyon genel üretim gideri (GÜG) toplamı.", "1.200.000", "sayı"),
    ("C21:C23, E21:E23, G21:G23", "Z", "Mal kabul GÜG: sınıf adı, baz kg, pay oranı (7-9. satırlarla aynı mantık).", "Taze/Taze · 1.000.000 · 0,20",
     "metin / sayı / oran"),
    ("D27 / F27", "Z", "Diğer genel üretim giderleri: gider toplamı / toplam adam-saniye.", "4.000.000 / 30.000.000", "sayı"),
    ("A30:A37, E30:E37, G30:G37 · D38", "Z", "Elektrik: hat adı (ürün kartındaki 'Üretim' hattıyla birebir), baz saniye, pay oranı; D38 toplam. En çok 8 hat.",
     "Kavanoz Hattı · 18.000.000 · 0,55 · 3.640.000", "metin / sayı / oran"),
    ("A41:A48, E41:E48, G41:G48 · D49", "Z", "Doğalgaz: hat payları ve D49 toplam.", "Teneke Hattı · 6.000.000 · 0,25 · 1.500.000", "metin / sayı / oran"),
    ("A52:A59, E52:E59, G52:G59 · D60", "Z", "Amortisman: hat payları ve D60 toplam.", "Sos Hattı · 6.000.000 · 0,20 · 6.000.000", "metin / sayı / oran"),
    ("D64", "Z", "Genel yönetim giderleri toplamı (adet bazında dağıtılır).", "10.400.000", "sayı"),
    ("D67", "Z", "Pazarlama satış giderleri toplamı (adet bazında dağıtılır).", "12.500.000", "sayı"),
    ("A70:D91", "Z", "Ambalaj sınıfları: A ad, B hacim (ürün kartındaki ambalaj hacmiyle aynı), C yıllık üretim adedi, D katsayı. En çok 22 satır.",
     "720 ml · 720 · 4.000.000 · 1,6", "metin / sayı"),
]

GIDER = Sablon(
    no="04", ad="gider-dagitim", baslik="Gider dağıtım (gider havuzları, dağıtım bazları, ambalaj sınıfları)",
    nereye="Fiyat Çalışması › Veri Aktar › 'Gider dağıtım' sekmesi → dosya → Önizle → neden → Uygula",
    kim="Muhasebe", siklik="Sezon başında (bütçe); gider bütçesi revize olunca",
    okuma=["'Gider Dağıtım' adlı sayfa okunur; dosyada tek sayfa varsa o sayfa okunur.",
           "Değerler SABİT HÜCRE adreslerinden okunur (tablo değil): satır / sütun eklemek ya da silmek değerleri kaydırır.",
           "Düzen denetimi: D3, D12, D17, D26, D63, D66 'Gider Toplamı' ile, A69 'Ambalaj' ile başlamalı; tüm toplamlar boşsa dosya reddedilir.",
           "Toplam hücresine '=49024334,97*1,35*1,3' gibi taban × çarpan formülü yazılırsa çarpanlar uygulamada ayrı ayrı düzenlenebilir kalır; "
           "düz sayı da olur. Formüllü dosyayı Excel'de kaydedip yükleyin (uygulama formülün son hesaplanan değerini okur).",
           "Önizleme yalnız değişen havuzları gösterir; uygula değişen havuzları ve ambalaj tablosunu seçili çalışmaya yazar.",
           "Metin olarak yazılmış sayılar çevrilir; çevrilemeyen hücre sorunlu listelenir ve düzeltilene kadar hiçbir şey yazılmaz.",
           "Ambalaj tablosu dosyadakiyle DEĞİŞTİRİLİR: dosyada mevcut ambalaj sınıflarının yarısından azı varsa 'N kalem silinecek' onayı "
           "istenir. Son yükleme geri alınabilir (havuzlar ve ambalaj tablosu önceki haline döner)."],
    hatalar=["Saniye bazlı havuzda (dolum, etiket, endirekt, diğer GÜG) F hücresini boş bırakmak: uygula 'dağıtım bazı 0'dan büyük olmalı' der.",
             "Sınıf / hat / ambalaj adını ürün kartındakinden farklı yazmak ('Turşu / Turşu' ile 'Turşu/Turşu'): o ürüne pay düşmez.",
             "Satır eklemek: tüm değerler kayar ve yanlış havuza yazılır. Boş satırları kullanın, satır eklemeyin.",
             "Formüllü kitabı Excel dışı bir araçla kaydedip yüklemek: formüllerin hesaplanmış değeri yoksa toplamlar 0 okunur."],
    sayfa="Gider Dağıtım", duzen="gider",
    baglanti="Veri Aktar › Gider dağıtım sekmesi (AktarimFormu)")

# ------------------------------------------------------------------------------------------------ 05 Ürün reçetesi (ürün sayfası düzeni)
RECETE_ORNEK = [  # (seviye, kod, ad, miktar, fire, birim, elle fiyat)
    (1, "99.10.001", "Test Taze Hıyar", 0.22, 0.05, "KG", None),
    (1, "99.11.001", "Test Tuz", 0.015, 0.02, "KG", None),
    (1, "99.11.003", "Test Sitrik Asit", 0.0005, None, "KG", None),
    (1, "99.20.001", "Test Kavanoz 370 ml", 1, 0.01, "AD", None),
    (1, "99.20.003", "Test Kapak 63 mm", 1, 0.01, "AD", 2.3),       # elle birim fiyat örneği
    (1, "99.20.007", "Test Koli 12'li", 0.0833333333, None, "AD", None),
]
RECETE_URUN = {"kod": URUN1[0], "ad": URUN1[1], "mk": 0.22, "suzme": 0.21, "vardiya": 18000, "dolum": 12, "etiketleme": 30000, "etiket": 3,
               "hat": "Kavanoz Hattı", "sinif": "Turşu/Turşu", "hacim": 370, "enflasyon": 0.30, "sapma": 0.03}
RECETE_KUR = [("USD", 42.5), ("EUR", 49.0), ("GBP", 56.0), ("CHF", 52.0)]
RECETE_FAIZ = [("TL", 0.40, 6), ("USD", 0.06, 6), ("EUR", 0.06, 6)]
RECETE_SON = 99   # reçete satırları 7..99; 100. satırda toplam etiketi


def recete_sayfasi(ws, dolu: bool) -> None:
    u = RECETE_URUN

    def girdi(h, deger, zorunlu=True, bicim="General"):
        c = ws[h]
        c.fill = GIRDI_Z if zorunlu else GIRDI_I
        c.number_format = bicim
        if dolu and deger is not None:
            c.value = deger

    ws["A1"] = "ÜRÜN SAYFASI (Fiyat Çalışması düzeni) · yeşil zorunlu, gri isteğe bağlı · D sütunundaki etiketleri değiştirmeyin"
    ws["A1"].font = BASLIK_YAZI
    ws["C2"] = "Ürün adı:"; girdi("D2", u["ad"], zorunlu=False, bicim="@")
    ws["O2"] = "Pazar:"; ws["P2"] = "Yurtiçi"; ws["P2"].fill = GIRDI_I
    dv = DataValidation(type="list", formula1='"Yurtiçi,Yurtdışı"', allow_blank=True)
    dv.add("P2"); ws.add_data_validation(dv)
    basliklar = {"A": ("Seviye", "I"), "D": ("Malzeme Kodu", "Z"), "E": ("Malzeme Adı", "I"), "I": ("Miktar", "Z"), "J": ("Fire", "I"),
                 "K": ("Brüt Miktar", "O"), "L": ("Birim", "I"), "M": ("Birim Fiyat", "I"), "N": ("Z/S", "O"), "O": ("Para B.", "O"),
                 "P": ("Tutar", "O")}
    for sutun, (b, d) in basliklar.items():
        _baslik_hucresi(ws[f"{sutun}5"], d)
        ws[f"{sutun}5"] = b
    # 6. satır: ürünün kendisi (seviye 0, miktar 1)
    ws["A6"] = 0; girdi("D6", u["kod"], bicim="@"); girdi("E6", u["ad"], bicim="@"); ws["I6"] = 1; ws["K6"] = 1; ws["L6"] = "AD"
    for r in range(7, RECETE_SON + 1):
        ws[f"K{r}"] = f'=IF(I{r}="","",I{r}/(1-J{r}))'   # brüt = miktar / (1 - fire); Excel kaydedince değer yazılır
        for sutun, bicim in (("A", "0"), ("D", "@"), ("E", "@"), ("I", "0.000000"), ("J", "0.00"), ("L", "@"), ("M", "#,##0.0000")):
            ws[f"{sutun}{r}"].number_format = bicim
    if dolu:
        for i, (sev, kod, ad, miktar, fire, birim, elle) in enumerate(RECETE_ORNEK):
            r = 7 + i
            ws[f"A{r}"], ws[f"D{r}"], ws[f"E{r}"], ws[f"I{r}"], ws[f"L{r}"] = sev, kod, ad, miktar, birim
            if fire:
                ws[f"J{r}"] = fire
            ws[f"K{r}"] = miktar / (1 - (fire or 0))   # Örnek: formülün hesaplanmış değeri (uygulama değeri okur)
            if elle is not None:
                ws[f"M{r}"] = elle
    E = lambda satir, metin: ws.__setitem__(f"D{satir}", metin)
    E(100, "HAMMADE - YARDIMCI MALZEME MALİYETİ TOPLAMI")
    E(103, "DİREKT İŞÇİLİK GİDERLERİ")
    E(104, "Mal Kabul ve Fermantasyon Giderleri"); ws["H104"] = "kg →"; girdi("I104", u["mk"], bicim="0.000")
    E(105, "Dolum Doğrudan İşçilik Giderleri"); E(106, "Etiketleme İşçilik Giderleri")
    E(107, "GENEL ÜRETİM GİDERLERİ"); E(108, "Endirekt İşçilik Giderleri"); E(109, "Mal Kabul ve Fermantasyon Genel Üretim Giderleri")
    E(110, "Elektrik Giderleri"); E(111, "Doğalgaz Giderleri"); E(112, "Amortisman Giderleri"); E(113, "Diğer Genel Üretim Giderleri")
    E(114, "GİDER TOPLAMI"); E(116, "TOPLAM BİRİM MALİYET")
    E(118, "PAZARLAMA SATIŞ GİDERLERİ"); E(119, "GENEL YÖNETİM GİDERLERİ")
    ws["K118"] = ws["K119"] = 1
    ws["P118"] = "=K118*M118"; ws["P119"] = "=K119*M119"   # formül: pazarlama / yönetim payı uygulanır (0 yazılırsa uygulanmaz)
    E(120, "DİĞER GİDERLER TOPLAMI"); E(122, "DİĞER GİDERLER GİYDİRİLMİŞ BİRİM MALİYET")
    E(124, "FİNANSMAN GİDERLERİ"); ws["I123"], ws["J123"], ws["K123"] = "Para birimi", "Faiz (yıllık)", "Stok süresi (ay)"
    for i, (pb, faiz, ay) in enumerate(RECETE_FAIZ):
        girdi(f"I{124 + i}", pb, zorunlu=False, bicim="@"); girdi(f"J{124 + i}", faiz, zorunlu=False, bicim="0.00")
        girdi(f"K{124 + i}", ay, zorunlu=False, bicim="0")
    E(130, "FİNANSMAN GİDERİ DAHİL EDİLMİŞ MALİYET")
    E(136, "Süzme Miktar"); girdi("E136", u["suzme"], bicim="0.000")
    E(138, "Vardiya Üretim Adedi"); girdi("E138", u["vardiya"], bicim="#,##0")
    E(140, "Dolum İşçilik Personel Sayısı"); girdi("E140", u["dolum"], bicim="0")
    E(141, "Etiketleme Adedi (vardiya)"); girdi("E141", u["etiketleme"], bicim="#,##0")
    E(143, "Etiket İşçilik Personel Sayısı"); girdi("E143", u["etiket"], bicim="0")
    E(144, "Üretim"); girdi("E144", u["hat"], bicim="@")
    E(145, "Taze / Turşu"); girdi("E145", u["sinif"], bicim="@")
    E(146, "Ambalaj"); girdi("E146", u["hacim"])
    E(147, "Ürün Adı"); girdi("E147", u["ad"], zorunlu=False, bicim="@")
    ws["K145"] = "Teklif kâr oranları"
    for r, v in zip((145, 146, 147), (0.20, 0.17, 0.14)):
        girdi(f"L{r}", v, zorunlu=False, bicim="0.00")
    E(148, "Enflasyon"); girdi("F148", u["enflasyon"], zorunlu=False, bicim="0.00")
    E(149, "Maliyet Sapma"); girdi("F149", u["sapma"], zorunlu=False, bicim="0.00")
    E(150, "Döviz Kurları")
    for i in range(6):
        k = RECETE_KUR[i] if i < len(RECETE_KUR) else None
        girdi(f"E{150 + i}", k[0] if k else None, zorunlu=False, bicim="@"); girdi(f"F{150 + i}", k[1] if k else None, zorunlu=False, bicim="0.0000")
    for col, w in zip("ABCDEFGHIJKLMNOP", (7, 4, 9, 14, 34, 10, 6, 6, 11, 7, 11, 7, 11, 5, 7, 12)):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A6"


def salma_yardimci_sayfasi(ws) -> None:
    """Ürün sayfasının yanında boş S.ALMA BF: 'elle fiyat' ayrımı fiyat listesine göre yapılsın (M boş = fiyat listesinden)."""
    for i, b in enumerate(("Malzeme", "Açıklama", "Malzeme Tipi", "Stok Birimi", "Para Birimi", "Bütçe Birim Fiyatları", "Z/S"), start=1):
        _baslik_hucresi(ws.cell(row=1, column=i, value=b), "O")
    ws["A3"] = ("BU SAYFAYI SİLMEYİN VE BOŞ BIRAKIN. Ürün sayfasında M (birim fiyat) boşsa fiyat Malzeme Fiyatları'ndan gelir, doluysa "
                "'elle fiyat' sayılır. Bu sayfa dosyada yoksa boş M hücreleri 'elle fiyat 0' sayılır.")
    ws["A3"].font = Font(bold=True, color="9C0006")
    ws.column_dimensions["A"].width = 14


RECETE_HUCRELERI = [
    ("Sayfa adı", "Z", "Ürün sayfasının adı üç haneli sayı olmalı ('001', '015'); '015 (2)' alternatif hesap sayılır. Birden çok ürün için sayfayı "
     "kopyalayıp '002', '003' diye adlandırın.", "001", "metin"),
    ("D6 / E6", "Z", "Ürün kodu ve adı. A6=0, I6=1, K6=1 sabit (ürünün kendisi).", f"{URUN1[0]} / {URUN1[1]}", "metin"),
    ("P2", "I", "Pazar (yeni ürün kartı için). Boşsa Yurtiçi.", "Yurtiçi", "Yurtiçi / Yurtdışı"),
    ("A7:A99", "I", "Reçete seviyesi (1 = doğrudan ürüne giren, 2 = ara mamulün içindeki).", "1", "tam sayı"),
    ("D7:D99", "Z", "Malzeme kodu. D'si boş satır atlanır. Ürün kodunun kendisi yazılırsa ara mamul sayılır.", "99.10.001", "metin"),
    ("E7:E99", "I", "Malzeme adı (bilgi).", "Test Taze Hıyar", "metin"),
    ("I7:I99", "Z", "Net miktar (1 adet ürün için, birim L sütununda).", "0,22", "sayı"),
    ("J7:J99", "I", "Fire oranı (0,05 = %5). Boş = 0.", "0,05", "oran"),
    ("K7:K99", "O", "Brüt miktar = I / (1 − J). Formül hazır: DOKUNMAYIN. Başka bir değer yazarsanız 'elle brüt miktar' sayılır.",
     "=I7/(1-J7)", "formül"),
    ("L7:L99", "I", "Birim (KG, LT, AD).", "KG", "metin"),
    ("M7:M99", "I", "Birim fiyat. BOŞ bırakın: fiyat Malzeme Fiyatları'ndan gelir. Sayı yazarsanız o satır için 'elle fiyat' olur.", "(boş)", "sayı"),
    ("N7:O99", "O", "Z/S ve para birimi: boş bırakın (malzeme kartından gelir). Z/S ya da para birimi yazarsanız o satır için elle sayılır.", "(boş)", "metin"),
    ("D100 ve altı (etiketler)", "Z", "D sütunundaki etiketler (HAMMADE - YARDIMCI MALZEME MALİYETİ TOPLAMI, DİREKT İŞÇİLİK GİDERLERİ, ..., Döviz Kurları) "
     "uygulamanın satırları bulduğu yerlerdir: metnini değiştirmeyin, silmeyin. Satır numarası kayabilir, metin kaymamalı.", "", "metin"),
    ("I104", "Z", "Mal kabul miktarı (kg / adet ürün). Yeni ürün açılırken üretim bilgisine yazılır.", "0,22", "sayı"),
    ("E136, E138, E140, E141, E143", "Z", "Süzme miktar (kg), vardiya üretim adedi, dolum personel sayısı, etiketleme adedi (vardiya), etiket personel sayısı.",
     "0,21 · 18.000 · 12 · 30.000 · 3", "sayı"),
    ("E144 / E145 / E146", "Z", "Üretim hattı (Gider Dağıtım'daki hat adıyla aynı), Taze / Turşu sınıfı (Gider Dağıtım sınıf adıyla aynı), ambalaj hacmi "
     "(Gider Dağıtım ambalaj hacmiyle aynı).", "Kavanoz Hattı · Turşu/Turşu · 370", "metin / sayı"),
    ("P118 / P119", "O", "Pazarlama ve yönetim payı formülü hazır. Bu ürüne pazarlama / yönetim payı UYGULANMAYACAKSA ikisine de 0 yazın.", "=K118*M118",
     "formül"),
    ("I124:K128, F148, F149, E150:F155, L145:L147", "I", "Finansman (para birimi, faiz, stok ayı), enflasyon, maliyet sapma, kurlar, teklif kâr oranları. "
     "Reçete aktarımı bunları OKUMAZ (parametreler Parametreler ekranından gelir); etiketleri silmeyin, değerler boş kalabilir.", "", "sayı"),
    ("S.ALMA BF sayfası", "Z", "Dosyada boş olarak kalmalı (yalnız başlık). Silinirse boş M hücreleri 'elle fiyat 0' sayılır.", "", "—"),
]

RECETE = Sablon(
    no="05", ad="urun-recetesi", baslik="Ürün reçetesi (Fiyat Çalışması ürün sayfası düzeni)",
    nereye="Fiyat Çalışması › Veri Aktar › 'Ürün reçetesi' sekmesi → dosya → Önizle (sayfa sayfa fark) → yazılacak sayfaları seç → neden → Uygula",
    kim="Muhasebe (Ar-Ge / üretimden gelen reçeteyle)", siklik="Gerektikçe (yeni ürün, reçete değişikliği)",
    okuma=["En kolay yol: Fiyat Çalışması kitabını olduğu gibi yükleyin ve önizlemede yalnız değişen sayfaları seçin. Bu şablon, kitabı "
           "olmayan tek bir ürün için hazırlanmıştır.",
           "Adı üç haneli sayı olan sayfalar ('001', '015 (2)') ürün sayfası sayılır; hiç yoksa ve dosya tek sayfalıysa o sayfa okunur.",
           "Satırlar D sütunundaki ETİKETLERLE bulunur: reçete 6. satırdan 'HAMMADE - YARDIMCI MALZEME MALİYETİ TOPLAMI' etiketine kadardır. "
           "Etiketlerden biri eksikse sayfa 'ürün sayfası düzeninde değil' diye hatalı listesine düşer.",
           "Dosyada S.ALMA BF sayfası varsa 'elle fiyat' ayrımı fiyat listesine göre yapılır (M boş = listeden). Bu şablonda o sayfa boş durur.",
           "Var olan ürünün kartına ve üretim bilgilerine dokunulmaz, yalnız yeni reçete versiyonu açılır (eski versiyon geçmişte kalır). "
           "Sistemde olmayan ürün için kart ve üretim bilgileri bu sayfadan açılır.",
           "Son yükleme geri alınabilir: açılan reçete versiyonları silinir, önceki versiyon yeniden aktif olur; bu yüklemede açılan ürün kaldırılır."],
    hatalar=["M (birim fiyat) hücresine sayı yazmak: o satır 'elle fiyat' olur. Boş M artık 'elle 0' SAYILMAZ (fiyat Malzeme Fiyatları'ndan "
             "gelir); önizlemedeki 'elle fiyat' sayısını kontrol edin.",
             "K (brüt miktar) hücresine sayı yazmak: 'elle brüt miktar' olur. Boş K artık 'elle 0' sayılmaz (fire kuralı uygulanır).",
             "I / J / K / M hücresine sayıya çevrilemeyen bir şey yazmak: o sayfa okunamayan sayfalar listesine düşer, hücre sorunlu satırlarda görünür.",
             "Dosyayı Excel'de açıp kaydetmeden (ör. başka araçla doldurup) yüklemek: K formüllerinin değeri hesaplanmamış olur.",
             "D sütunundaki etiket metinlerini değiştirmek ya da satır ekleyip etiketleri reçete alanına kaydırmak.",
             "Reçeteye 93'ten fazla malzeme: 100. satırdaki etiketin üstüne satır ekleyin (etiket aşağı kayar, sorun olmaz)."],
    sayfa="001", duzen="recete",
    baglanti="Veri Aktar › Ürün reçetesi sekmesi (ReceteDosyaAktar)")

# ------------------------------------------------------------------------------------------------ 06 Stokta kalan
STOK = Sablon(
    no="06", ad="stokta-kalan", baslik="Stokta kalan (geçen yıldan devreden ürün stoku)",
    nereye="Fiyat Çalışması › Veri Aktar › 'Stokta kalan' sekmesi → dosya → Önizle → neden → Uygula",
    kim="Muhasebe", siklik="Sezon başında",
    okuma=["'Stokta Kalan' sayfası, yoksa ilk veri sayfası okunur; başlık satırı ilk 30 satırda aranır. Sütunlar BAŞLIK ADIYLA bulunur (sıra "
           "serbest; büyük/küçük, Türkçe harf ve boşluk/alt çizgi farkı önemsiz).",
           "Zorunlu başlıklar: urun_kodu (= Ürün Kodu, Stok Kodu), stok_adet (= Stok Adedi, Miktar), stok_birim_maliyet (= Birim Maliyet). "
           "İsteğe bağlı: enflasyon, uretim_adedi (= Üretim Adedi). Son yükleme geri alınabilir.",
           "Ürün sistemde olmalı ve dosyada bir kez geçmeli. Hatalı satır varsa önizlemede listelenir ve hiçbir satır yazılmaz.",
           "Kayıtlar seçili çalışmaya yazılır; yeni çalışma kopyalanırken taşınmaz.",
           "Uygulamadaki 'Şablonu indir' bağlantısı aynı başlıkları verir (Veri Aktar › Stokta kalan)."],
    hatalar=["Enflasyonu yüzde sayı olarak yazmak (40): %4000 sayılır ve reddedilir; 0,40 ya da %40 yazın.",
             "stok_adet > 0 iken birim maliyeti boş bırakmak.",
             "Ürün kodunu ürün kartından farklı yazmak: 'ürün bulunamadı'.",
             "Başlık satırı olmadan veri yapıştırmak: 'zorunlu sütun bulunamadı'."],
    sayfa="Stokta Kalan",
    sutunlar=[
        Sutun("urun_kodu", "Z", 14, "metin", "Ürün kodu (sistemde kayıtlı).", URUN1[0]),
        Sutun("stok_adet", "Z", 12, "sayi", "Geçen yıldan stokta kalan adet (0 ya da büyük).", "25.000"),
        Sutun("stok_birim_maliyet", "Z", 18, "para", "O stokun birim maliyeti, TL (stok_adet > 0 ise 0'dan büyük).", "15,80"),
        Sutun("enflasyon", "I", 12, "oran", "Oran (0,40 = %40; '%40' yazımı da olur). Boşsa çalışmanın enflasyon parametresi.", "0,35"),
        Sutun("uretim_adedi", "I", 14, "sayi", "Bu yıl üretilecek adet. Boşsa geçen yıl satış adedi − stok adedi (en az 0).", "120.000"),
    ],
    ornek=[[URUN1[0], 25000, 15.8, None, None], [URUN3[0], 8000, 17.2, 0.35, 120000]],
    uygulama_sablonu="/api/v1/aktarim/stok-devri/sablon.xlsx",
    baglanti="Var (Veri Aktar › Stokta kalan › 'Şablonu indir'); bu dosyayla değiştirilebilir")

# ------------------------------------------------------------------------------------------------ 07 Satış geçmişi
SATIS = Sablon(
    no="07", ad="satis-gecmisi", baslik="Satış geçmişi (geçen yıl satış fiyatları)",
    nereye="Fiyat Çalışması › Satış Geçmişi › dosya seç → Yükle (aynı kart: Veri Aktar › 'Satış geçmişi' sekmesi)",
    kim="Muhasebe (satış raporundan)", siklik="Sezon başında (geçen yılın tamamı); istenirse ay sonunda ek",
    okuma=["İLK veri sayfası okunur; başlık satırı ilk 30 satırda aranır. Sütunlar BAŞLIK ADIYLA bulunur (sıra serbest; 'Ürün Kodu', "
           "'urun_kodu', 'URUNKODU' aynı; eş anlamlılar: Müşteri = Cari, Tarih = Fatura Tarihi, Fiyat = Birim Fiyat, Para Birimi = Döviz, "
           "Adet = Miktar).",
           "Altı başlık da zorunludur: urun_kodu, musteri, tarih, fiyat, para_birimi, adet. .csv (; ya da ,) da kabul edilir.",
           "Tarih: Excel tarih hücresi, YYYY-AA-GG ya da GG.AA.YYYY. Sayı: Excel sayı hücresi, 1234.56, 1234,56 ya da 1.234,56.",
           "Tek işlem: herhangi bir satır hatalıysa hiçbir satır eklenmez, hatalar satır numarasıyla listelenir. En çok 20.000 satır.",
           "Yükleme ekler; sistemde aynısı (ürün, müşteri, tarih, fiyat, adet) olan satırlar ATLANIR: aynı dosyayı iki kez yüklemek satırları "
           "ikilemez ('Önizle' kaç satırın zaten kayıtlı olduğunu gösterir). Son yükleme geri alınabilir (eklenen satırlar silinir).",
           "Uygulamadaki 'Şablonu indir' bağlantısı aynı başlıkları verir."],
    hatalar=["Belirsiz sayı: '2.000' (nokta + 3 hane, virgülsüz) ve '1,234.56' reddedilir; Excel sayı hücresi kullanın.",
             "Para birimini 'TRY' ya da '₺' yazmak: TL, USD, EUR, GBP, CHF, RUB, ZAR'dan biri olmalı.",
             "Ürün kodu sistemde yok: 'ürün bulunamadı' (önce ürün kartı açılmalı).",
             "Yanlış dosya yüklemek: 'Son yükleme — Geri al' ile eklenen satırları kaldırın."],
    sayfa="Satış Geçmişi",
    sutunlar=[
        Sutun("urun_kodu", "Z", 14, "metin", "Ürün kodu (sistemde kayıtlı).", URUN1[0]),
        Sutun("musteri", "Z", 26, "metin", "Müşteri adı (en çok 200 karakter).", "Test Market A.Ş."),
        Sutun("tarih", "Z", 12, "tarih", "Satış (fatura) tarihi.", "15.06.2025"),
        Sutun("fiyat", "Z", 12, "para", "Birim satış fiyatı (KDV hariç), para birimi bir sonraki sütunda. 0 ya da büyük.", "35,40"),
        Sutun("para_birimi", "Z", 12, "metin", "Fiyatın para birimi.", "TL", liste=PARA_BIRIMLERI),
        Sutun("adet", "Z", 10, "sayi", "Satılan adet (0'dan büyük).", "6.000"),
    ],
    ornek=[[URUN1[0], "Test Market A.Ş.", date(2025, 6, 15), 35.4, "TL", 6000],
           [URUN1[0], "Test Export GmbH", date(2025, 7, 15), 0.95, "USD", 2400],
           [URUN2[0], "Test Toptan Ltd.", date(2025, 9, 15), 49.9, "TL", 3000],
           [URUN3[0], "Test Market A.Ş.", date(2026, 1, 15), 36.2, "TL", 4500]],
    uygulama_sablonu="/api/v1/satis-gecmisi/sablon.xlsx",
    baglanti="Var (Satış Geçmişi ve Veri Aktar › Satış geçmişi › 'Şablonu indir'); bu dosyayla değiştirilebilir")

# ------------------------------------------------------------------------------------------------ 08 Liste fiyatları
LISTE = Sablon(
    no="08", ad="liste-fiyatlari", baslik="Geçmiş yılların liste fiyatları (yalnız Berrak)",
    nereye="Fiyat Çalışması › Analiz › 'Liste çalışması' sekmesi › 'Excel'den yükle' → dosya → Yükle",
    kim="Muhasebe / satış", siklik="Sezon başında (yılda bir; önceki yılların listesi)",
    okuma=["İLK sayfa okunur; 1. satır başlıktır. Sütunlar BAŞLIK ADIYLA bulunur (satış geçmişi okuyucusuyla aynı kurallar). .csv de olur.",
           "Zorunlu başlıklar: urun_kodu, yil, liste_fiyati. İsteğe bağlı: birim_maliyet, pazar.",
           "Yalnız Berrak markalı ürünler kabul edilir (ürün kartında marka: Berrak).",
           "Aynı ürün + yıl + pazar yeniden yüklenirse eski değerin yerine geçer. Herhangi bir satır hatalıysa hiçbir satır yazılmaz. "
           "'Önizle' yeni / değişecek / aynı sayılarını gösterir; son yükleme geri alınabilir (eski değerler geri yazılır).",
           "Uygulamadaki 'Şablonu indir' bağlantısı aynı başlıkları verir."],
    hatalar=["Berrak olmayan ürün: 'liste fiyatı yalnız Berrak markalı ürünlere girilir'.",
             "Pazarı 'İhracat' yazmak: yalnız Yurtiçi, Yurtdışı ya da boş (boş = Yurtiçi).",
             "Liste fiyatını KDV dahil girmek: liste fiyatları KDV hariçtir.",
             "Aynı ürün, yıl ve pazar dosyada iki kez: satır hatası."],
    sayfa="Liste Fiyatları",
    sutunlar=[
        Sutun("urun_kodu", "Z", 14, "metin", "Ürün kodu (Berrak markalı, sistemde kayıtlı).", URUN1[0]),
        Sutun("yil", "Z", 8, "yil", "Liste fiyatının yılı (2000-2100).", "2025"),
        Sutun("liste_fiyati", "Z", 14, "para", "O yılın liste fiyatı, TL, KDV hariç (0'dan büyük).", "49,90"),
        Sutun("birim_maliyet", "I", 14, "para", "O yılın birim maliyeti, TL (maliyet artışıyla kıyas için). Boş olabilir.", "22,00"),
        Sutun("pazar", "I", 12, "metin", "Yurtiçi ya da Yurtdışı. Boşsa Yurtiçi.", "Yurtiçi", liste="Yurtiçi,Yurtdışı"),
    ],
    ornek=[[URUN1[0], 2024, 38.9, 17.8, "Yurtiçi"], [URUN1[0], 2025, 49.9, 22.0, "Yurtiçi"], [URUN1[0], 2025, 34.9, 22.0, "Yurtdışı"],
           [URUN2[0], 2025, 72.9, None, None]],
    uygulama_sablonu="/api/v1/liste-fiyatlari/sablon.xlsx",
    baglanti="Var (Liste çalışması › Excel'den yükle › 'Şablonu indir'); bu dosyayla değiştirilebilir")

# ------------------------------------------------------------------------------------------------ 09 Canias ürün ağacı
CANIAS_URUNLER = {"01.99.001": "Test Fermente Hıyar (ara mamul)", "02.99.001": "Test Turşu Yarı Mamul 370 ml", "03.99.001": "Test Berrak Turşu 370 ml"}


def _canias_satirlari() -> list[list]:
    adlar = {"99.10.001": ("Test Taze Hıyar", "KG"), "99.11.001": ("Test Tuz", "KG"), "99.11.003": ("Test Sitrik Asit", "KG"),
             "99.20.001": ("Test Kavanoz 370 ml", "AD"), "99.20.003": ("Test Kapak 63 mm", "AD"), "99.20.007": ("Test Koli 12'li", "AD"),
             "99.20.008": ("Test Koli 6'lı", "AD"), "01.99.001": (CANIAS_URUNLER["01.99.001"], "KG"), "02.99.001": (CANIAS_URUNLER["02.99.001"], "AD")}
    receteler = [
        ("00", "01.99.001", [("99.10.001", 1.05, 2), ("99.11.001", 0.06, 0)]),
        ("00", "02.99.001", [("01.99.001", 0.21, 0), ("99.11.003", 0.0005, 0), ("99.20.001", 1, 1), ("99.20.003", 1, 1)]),
        ("00", "03.99.001", [("02.99.001", 1, 0), ("99.20.007", 0.0833, 0)]),
        ("01", "03.99.001", [("02.99.001", 1, 0), ("99.20.008", 0.1667, 0)]),
    ]
    out = []
    for alt, ana, satirlar in receteler:
        out.append([alt, ana, CANIAS_URUNLER[ana], 0, None, None, None, None, None, None, None])   # ürün başlık satırı
        for i, (mal, mik, fire) in enumerate(satirlar, start=1):
            ad, birim = adlar[mal]
            out.append([alt, ana, CANIAS_URUNLER[ana], i * 10, 1 if mal in CANIAS_URUNLER else 2, mal, ad, mik, birim, fire,
                        round(mik * (1 + fire / 100), 6)])
    return out


CANIAS = Sablon(
    no="09", ad="canias-urun-agaci", baslik="Canias ürün ağacı dökümü (kalıcı üretim reçeteleri)",
    nereye="Maliyet Muhasebesi › Reçeteler › 'Canias ürün ağacı dökümünü yükle' → dosya → Önizle → Yükle",
    kim="Muhasebe", siklik="Gerektikçe (Canias'ta reçete değişince); her ay yeniden yüklenmez",
    okuma=["Canias'tan böyle alınır: ürün ağacı raporu (sonuç tablosu 'TBLRESULT') Excel'e aktarılır; başlıklar bu şablondakiyle aynıdır. "
           "Canias dökümünü olduğu gibi yükleyebilirsiniz; bu şablon elle hazırlanacak ya da düzeltilecek dökümler içindir.",
           "İLK sayfa okunur; başlık satırı aranır. Sütunlar BAŞLIK ADIYLA bulunur (sıra serbest; büyük/küçük harf, Türkçe harf ve boşluk farkı "
           "önemsiz: 'Fire Oranı' = 'FIRE ORANI'; bilinen eş anlamlılar tanınır).",
           "Zorunlu başlıklar: Alternatif Numarası, Malzeme Kodu, Malzeme Açıklaması, Satır No, Ürün Ağacı Kalem Tipi, Tüketim Malzeme Kodu, "
           "Tüketim Malzeme Adı, Tüketim Miktarı, Tüketim Birimi, Fire Oranı. 'Fireli Miktar' okunmaz.",
           "Tüketim Malzeme Kodu boş satır ürün başlığıdır, atlanır. Aşama koddan bulunur: 02 ile başlayan → 40 (üretim hattı), 03 → 50 (etiketleme), "
           "diğerleri → 20.",
           "Yükleme TÜM kalıcı reçeteleri dosyadakilerle değiştirir; ürün başına alternatif seçimleri ve elle düzeltilmiş ürünler korunur. "
           "Önce önizlenir; dosyada mevcut reçetelerin yarısından azı varsa onay istenir; son yükleme geri alınabilir.",
           "Metin olarak yazılmış sayılar çevrilir; çevrilemeyen hücre satırı sorunlu yapar (0 sayılmaz)."],
    hatalar=["Alternatif numarasını sayı olarak girmek: Excel '00'ı 0 yapar ve varsayılan alternatif '00' bulunamaz. Sütun metin biçimlidir; '00' yazın.",
             "Fire oranını oran olarak yazmak (0,02): yüzde beklenir (2 = %2); 0,02 yazılırsa %0,02 sayılır.",
             "Miktara sayıya çevrilemeyen bir şey yazmak: satır sorunlu listelenir, yazılmaz.",
             "Zorunlu bir başlığı hiç koymamak: hangi sütunun eksik olduğu söylenir, hiçbir şey yazılmaz."],
    sayfa="TBLRESULT",
    sutunlar=[
        Sutun("Alternatif Numarası", "Z", 12, "metin", "Reçete alternatifi; boşsa '00' (varsayılan). Metin olarak yazın.", "00"),
        Sutun("Malzeme Kodu", "Z", 13, "metin", "Ana ürün (üretilen) kodu. İlk iki hane aşamayı belirler (01/11-19 → 20, 02 → 40, 03 → 50).", "03.99.001"),
        Sutun("Malzeme Açıklaması", "Z", 34, "metin", "Ana ürün adı. Başlık zorunlu, değer boş olabilir.", "Test Berrak Turşu 370 ml"),
        Sutun("Satır No", "Z", 9, "tam", "Reçete satır numarası (ürün başlık satırında 0).", "10"),
        Sutun("Ürün Ağacı Kalem Tipi", "Z", 12, "tam", "Kalem tipi (Canias: 1 yarı mamul, 2 malzeme). Başlık zorunlu, değer boş olabilir.", "2"),
        Sutun("Tüketim Malzeme Kodu", "Z", 14, "metin", "Reçetedeki malzeme / yarı mamul kodu. Boşsa satır ürün başlığıdır, atlanır.", "99.20.007"),
        Sutun("Tüketim Malzeme Adı", "Z", 30, "metin", "Malzeme adı. Başlık zorunlu, değer boş olabilir.", "Test Koli 12'li"),
        Sutun("Tüketim Miktarı", "Z", 12, "sayi", "1 birim ana ürün için net miktar (sayı hücresi).", "0,0833"),
        Sutun("Tüketim Birimi", "Z", 10, "metin", "Birim (KG, LT, AD). Başlık zorunlu, değer boş olabilir.", "AD"),
        Sutun("Fire Oranı", "Z", 10, "sayi", "Fire YÜZDE olarak (2 = %2). Boş = 0.", "2"),
        Sutun("Fireli Miktar", "O", 12, "sayi", "Canias'ın hesapladığı fireli miktar; uygulama okumaz (kendisi hesaplar).", "1,071"),
    ],
    ornek=_canias_satirlari(),
    baglanti="Maliyet Muhasebesi › Reçeteler › 'Canias ürün ağacı dökümünü yükle' kartına (SmmReceteler)")

# ------------------------------------------------------------------------------------------------ 10-16 SMM aylık kaynaklar
_O = lambda ad="—": Sutun(ad, "O", 9, "metin", "Uygulama okumaz; boş kalabilir (SMM Excel'indeki yerini korur).")
SMM_ORTAK_OKUMA = ("'{sayfa}' adlı sayfa okunur (ad esnek); yoksa İLK sayfa okunur (SMM Excel'inin tamamı da, tek sayfalık rapor da olur).",
                   "Başlık satırı '{baslik}' hücresiyle bulunur; büyük/küçük harf, Türkçe harf (İ/ı) ve boşluk farkı önemsiz, bilinen eş anlamlılar "
                   "tanınır ('Malzeme Kodu' = 'Stok Kodu' = 'Malzeme (Sınıf) Kodu'). Veri onun altından başlar.",
                   "Diğer sütunlar şablondaki yerlerinden okunur: sütun yerlerini değiştirmeyin.",
                   "Metin olarak yazılmış sayılar ('1.234,56') çevrilir; çevrilemeyen hücre satırı sorunlu yapar (0 sayılmaz), önizlemede listelenir.",
                   "Önce önizlenir, sonra uygulanır. Yükleme o kaynağın dönemdeki eski verisinin YERİNE geçer; boş dosya reddedilir, yeni dosyada "
                   "mevcut kalemlerin yarısından azı varsa onay istenir; son yükleme geri alınabilir. Kilitli (kapatılmış) döneme yüklenemez.")


def _smm_okuma(sayfa: str, baslik: str, ek: list[str]) -> list[str]:
    return [m.format(sayfa=sayfa, baslik=baslik) for m in SMM_ORTAK_OKUMA[:3]] + ek + list(SMM_ORTAK_OKUMA[3:])


SMM_NEREYE = "Maliyet Muhasebesi › Veri Girişi › (dönemi seçin) › '{ad}' satırı › 'Yükle' / 'Yeniden yükle'"
SMM_BAGLANTI = "Maliyet Muhasebesi › Veri Girişi › '{ad}' satırının yanına (SmmVeri KaynakSatiri)"

SMM_ALIM = Sablon(
    no="10", ad="smm-alim-satis", baslik="SMM · Alım ve satış (HM-YM ALIŞ SATIŞ)",
    nereye=SMM_NEREYE.format(ad="Alım ve satış"), kim="Muhasebe (Canias alış / satış raporundan)", siklik="Her ay sonunda (zorunlu kaynak)",
    okuma=_smm_okuma("HM-YM ALIŞ SATIŞ", "Malzeme(Sınıf)Kodu",
                     ["Kod B sütunundadır. Okunan: B kod, C ad, F birim, G giriş (alım) miktarı, K tutar (TL), L çıkış miktarı, T hareket türü.",
                      "Aynı kodun satırları toplanır. T 'Satış' ise L satılan miktara eklenir; diğer satırlarda G ve K alıma eklenir.",
                      "Tutar (K) TL'dir: dövizli alımda kur çevrimini satırda yapın."]),
    hatalar=["Kod sütununu hiç koymamak: 'başlık bulunamadı' (hangi sütunun eksik olduğu söylenir). Başlık yazımı esnektir.",
             "Satış satırında T'yi boş bırakmak: satır alım sayılır ('Satış', 'SATIŞ', 'Satis' satış sayılır).",
             "Tutarı döviz olarak bırakmak: K TL kabul edilir, ortalama maliyet bozulur.",
             "Sütun eklemek / silmek: miktar ve tutar yanlış sütundan okunur."],
    sayfa="HM-YM ALIŞ SATIŞ", baslik_satiri=2, ust_baslik="HAMMADDE - YARI MAMUL ALIŞ / SATIŞ RAPORU (bu satır serbest)",
    sutunlar=[
        Sutun("Fiş No", "O", 12, "metin", "Uygulama okumaz.", "ALS-00001"),
        Sutun("Malzeme(Sınıf)Kodu", "Z", 16, "metin", "Malzeme kodu. Başlık adı esnek (büyük/küçük harf ve boşluk farkı önemsiz).", "99.10.001"),
        Sutun("Malzeme Açıklaması", "I", 30, "metin", "Malzeme adı (kalem dönemde yoksa ad olarak kullanılır).", "Test Taze Hıyar"),
        Sutun("Tarih", "O", 12, "tarih", "Uygulama okumaz.", "05.11.2026"),
        Sutun("Depo", "O", 10, "metin", "Uygulama okumaz.", "Merkez"),
        Sutun("Birim", "I", 8, "metin", "Stok birimi (kalem dönemde yoksa kullanılır).", "KG"),
        Sutun("Giriş Miktarı", "Z", 12, "sayi", "Alım (giriş) miktarı. Satış satırında boş.", "12.000"),
        Sutun("Birim Fiyat", "O", 11, "para", "Uygulama okumaz (bilgi).", "19,20"),
        Sutun("Para Birimi", "O", 9, "metin", "Uygulama okumaz (bilgi).", "TL"),
        Sutun("Kur", "O", 8, "sayi", "Uygulama okumaz (bilgi).", "1"),
        Sutun("Tutar (TL)", "Z", 14, "para", "Alım tutarı, TL (KDV hariç). Satış satırında boş.", "230.400,00"),
        Sutun("Çıkış Miktarı", "I", 12, "sayi", "Hareket türü 'Satış' olan satırda satılan miktar.", "500"),
        _O(), _O(), _O(), _O(), _O(), _O(), _O(),
        Sutun("Hareket Türü", "Z", 12, "metin", "'Satış' yazılan satır satış sayılır; diğerleri (Alış vb.) alım.", "Alış", liste="Alış,Satış",
              liste_kati=False),
    ],
    ornek=[["ALS-00001", "99.10.001", "Test Taze Hıyar", date(2026, 11, 5), "Merkez", "KG", 12000, 19.2, "TL", 1, 230400, None] + [None] * 7 + ["Alış"],
           ["ALS-00002", "99.11.003", "Test Sitrik Asit", date(2026, 11, 7), "Merkez", "KG", 50, 2.15, "USD", 42.8, 4601, None] + [None] * 7 + ["Alış"],
           ["ALS-00003", "99.20.001", "Test Kavanoz 370 ml", date(2026, 11, 10), "Merkez", "AD", 30000, 6.9, "TL", 1, 207000, None] + [None] * 7 + ["Alış"],
           ["ALS-00004", "99.20.001", "Test Kavanoz 370 ml", date(2026, 11, 20), "Merkez", "AD", 10000, 7.0, "TL", 1, 70000, None] + [None] * 7 + ["Alış"],
           ["STS-00005", "99.10.001", "Test Taze Hıyar", date(2026, 11, 25), "Merkez", "KG", None, None, "TL", None, None, 500] + [None] * 7 + ["Satış"]],
    baglanti=SMM_BAGLANTI.format(ad="Alım ve satış"))

SMM_IADE = Sablon(
    no="11", ad="smm-iadeler", baslik="SMM · Alım iadeleri (İADELER)",
    nereye=SMM_NEREYE.format(ad="Alım iadeleri"), kim="Muhasebe", siklik="Her ay sonunda (iade varsa)",
    okuma=_smm_okuma("İADELER", "Malzeme (Sınıf) Kodu",
                     ["Kod A sütunundadır. Okunan: A kod, B ad, E birim, H iade miktarı, I iade tutarı (TL). Aynı kodun satırları toplanır."]),
    hatalar=["Kod sütununu hiç koymamak: 'başlık bulunamadı'. Başlık yazımı esnektir ('Malzeme(Sınıf)Kodu' = 'Malzeme (Sınıf) Kodu').",
             "İade miktarını eksi yazmak: iade zaten düşülür; artı yazın.",
             "Tutar sütununu (I) boş bırakmak: iade tutarı 0 sayılır."],
    sayfa="İADELER", baslik_satiri=2, ust_baslik="ALIM İADELERİ (bu satır serbest)",
    sutunlar=[
        Sutun("Malzeme (Sınıf) Kodu", "Z", 16, "metin", "Malzeme kodu. Başlık adı esnek (büyük/küçük harf ve boşluk farkı önemsiz).", "99.10.001"),
        Sutun("Malzeme Açıklaması", "I", 30, "metin", "Malzeme adı.", "Test Taze Hıyar"),
        Sutun("Tarih", "O", 12, "tarih", "Uygulama okumaz.", "12.11.2026"),
        Sutun("Fiş No", "O", 10, "metin", "Uygulama okumaz.", "IAD-001"),
        Sutun("Birim", "I", 8, "metin", "Stok birimi.", "KG"),
        Sutun("Tedarikçi", "O", 20, "metin", "Uygulama okumaz.", "Test Tedarikçi A.Ş."),
        Sutun("Not", "O", 12, "metin", "Uygulama okumaz.", "Çürük"),
        Sutun("İade Miktarı", "Z", 12, "sayi", "İade edilen miktar (artı).", "300"),
        Sutun("İade Tutarı", "Z", 14, "para", "İade tutarı, TL.", "5.760,00"),
    ],
    ornek=[["99.10.001", "Test Taze Hıyar", date(2026, 11, 12), "IAD-001", "KG", "Test Tedarikçi A.Ş.", "Çürük", 300, 5760],
           ["99.20.001", "Test Kavanoz 370 ml", date(2026, 11, 15), "IAD-002", "AD", "Test Cam San.", "Kırık", 200, 1380]],
    baglanti=SMM_BAGLANTI.format(ad="Alım iadeleri"))

SMM_URETIM = Sablon(
    no="12", ad="smm-uretim", baslik="SMM · Üretim miktarları (ÜRETİM)",
    nereye=SMM_NEREYE.format(ad="Üretim miktarları"), kim="Muhasebe (Canias üretim raporundan)", siklik="Her ay sonunda (zorunlu kaynak)",
    okuma=_smm_okuma("ÜRETİM", "MalzemeKodu",
                     ["Kod A sütunundadır. Okunan: A kod, B ad, O üretim miktarı (15. sütun). Aynı kodun satırları toplanır.",
                      "Hem mamul (03...) hem yarı mamul (02...) hem ara mamul (01...) üretimleri yazılır."]),
    hatalar=["Üretim miktarını C ya da başka bir sütuna yazmak: yalnız O sütunu okunur (C-N boş kalabilir).",
             "Kod sütununu hiç koymamak: 'başlık bulunamadı'. Başlık yazımı esnektir ('MalzemeKodu' = 'Malzeme Kodu').",
             "O sütununa yıl içi toplamı yazmak: SMM Excel'inde bu sütun 'yıl içi toplam' diye anılıyor; dönem hesabında ayın üretimi olarak kullanılır "
             "(muhasebeyle teyit edilmeli, rehberdeki açık soruya bakın)."],
    sayfa="ÜRETİM", baslik_satiri=2, ust_baslik="ÜRETİM MİKTARLARI (bu satır serbest)",
    sutunlar=[
        Sutun("MalzemeKodu", "Z", 14, "metin", "Üretilen mamul / yarı mamul kodu. Başlık adı esnek (büyük/küçük harf ve boşluk farkı önemsiz).", "03.99.001"),
        Sutun("Malzeme Açıklaması", "I", 32, "metin", "Ürün adı.", "Test Berrak Turşu 370 ml"),
        Sutun("Birim", "O", 8, "metin", "Uygulama okumaz (bilgi).", "AD"),
    ] + [_O() for _ in range(11)] + [
        Sutun("Üretim Miktarı", "Z", 14, "sayi", "Dönemde üretilen miktar (O sütunu, 15. sütun).", "18.000"),
    ],
    ornek=[["03.99.001", "Test Berrak Turşu 370 ml", "AD"] + [None] * 11 + [18000],
           ["02.99.001", "Test Turşu Yarı Mamul 370 ml", "AD"] + [None] * 11 + [18100],
           ["01.99.001", "Test Fermente Hıyar (ara mamul)", "KG"] + [None] * 11 + [3900]],
    baglanti=SMM_BAGLANTI.format(ad="Üretim miktarları"))

SMM_SAYIM = Sablon(
    no="13", ad="smm-sayim", baslik="SMM · Dönem sonu sayım (DSS)",
    nereye=SMM_NEREYE.format(ad="Sayım (dönem sonu stok)"), kim="Muhasebe (sayım tutanağından)", siklik="Her ay sonunda (zorunlu kaynak)",
    okuma=_smm_okuma("DSS", "StokKartıKodu",
                     ["Kod A sütunundadır. Okunan: A kod, B ad, C sayım miktarı. Aynı kodun satırları toplanır.",
                      "Sayımda olmayan kalemin sayımı 0 olur (yükleme o kaynağı baştan yazar)."]),
    hatalar=["Kod sütununu hiç koymamak: 'başlık bulunamadı'. Başlık yazımı esnektir ('StokKartıKodu' = 'Stok Kartı Kodu').",
             "Sayım miktarını D ya da E sütununa yazmak: yalnız C okunur.",
             "Sıfır sayımlı kalemi listeden çıkarmak sorun değildir; ama yanlışlıkla bir kalemi atlamak onu 0 yapar."],
    sayfa="DSS", baslik_satiri=2, ust_baslik="DÖNEM SONU SAYIM (bu satır serbest)",
    sutunlar=[
        Sutun("StokKartıKodu", "Z", 14, "metin", "Stok kodu. Başlık adı esnek (büyük/küçük harf, İ/ı ve boşluk farkı önemsiz).", "99.10.001"),
        Sutun("StokKartıAdı", "I", 32, "metin", "Stok adı.", "Test Taze Hıyar"),
        Sutun("Sayım Miktarı", "Z", 13, "sayi", "Dönem sonu sayılan miktar (stok biriminde).", "2.100"),
        Sutun("Birim", "O", 8, "metin", "Uygulama okumaz (bilgi).", "KG"),
        Sutun("Tutar", "O", 13, "para", "Uygulama bu yüklemede okumaz (değerlemeyi kendisi yapar).", ""),
    ],
    ornek=[["99.10.001", "Test Taze Hıyar", 2100, "KG"], ["99.11.003", "Test Sitrik Asit", 18, "KG"], ["99.20.001", "Test Kavanoz 370 ml", 9500, "AD"],
           ["01.99.001", "Test Fermente Hıyar (ara mamul)", 650, "KG"], ["03.99.001", "Test Berrak Turşu 370 ml", 2400, "AD"]],
    baglanti=SMM_BAGLANTI.format(ad="Sayım (dönem sonu stok)"))

SMM_SAHIT = Sablon(
    no="14", ad="smm-sahit-numune", baslik="SMM · Şahit numune (ŞAHİT)",
    nereye=SMM_NEREYE.format(ad="Şahit numune"), kim="Muhasebe (kalite / şahit numune listesinden)", siklik="Her ay sonunda (varsa)",
    okuma=_smm_okuma("ŞAHİT", "StokKodu",
                     ["Kod A sütunundadır. Okunan: A kod, B ad, J toplam miktar (10. sütun, sayı hücresi). Aynı kodun satırları toplanır."]),
    hatalar=["Miktarı C-I sütunlarına yazmak: yalnız J okunur.",
             "J'ye sayıya çevrilemeyen bir şey yazmak: satır sorunlu listelenir, yazılmaz (metin sayı '12' çevrilir).",
             "Kod sütununu hiç koymamak: 'başlık bulunamadı'. Başlık yazımı esnektir ('StokKodu' = 'Stok Kodu')."],
    sayfa="ŞAHİT", baslik_satiri=2, ust_baslik="ŞAHİT NUMUNE (bu satır serbest)",
    sutunlar=[
        Sutun("StokKodu", "Z", 14, "metin", "Ürün kodu. Başlık adı esnek (büyük/küçük harf, İ/ı ve boşluk farkı önemsiz).", "03.99.001"),
        Sutun("StokAdı", "I", 32, "metin", "Ürün adı.", "Test Berrak Turşu 370 ml"),
        Sutun("Birim", "O", 8, "metin", "Uygulama okumaz (bilgi).", "AD"),
    ] + [_O() for _ in range(6)] + [
        Sutun("Toplam Miktar", "Z", 13, "sayi", "Şahit numune olarak ayrılan toplam miktar (J sütunu).", "24"),
    ],
    ornek=[["03.99.001", "Test Berrak Turşu 370 ml", "AD"] + [None] * 6 + [24],
           ["03.99.002", "Test Berrak Turşu 720 ml", "AD"] + [None] * 6 + [12]],
    baglanti=SMM_BAGLANTI.format(ad="Şahit numune"))

_MIZAN_SUTUNLARI = lambda hesap_aciklama, bakiye_aciklama, ornek_hesap: [
    Sutun("Hesap Kodu", "Z", 12, "metin", hesap_aciklama, ornek_hesap),
    Sutun("Hesap Adı", "I", 40, "metin", "Hesap adı (bilgi).", ""),
    Sutun("Borç", "O", 15, "para", "Uygulama okumaz (bilgi).", ""),
    Sutun("Alacak", "O", 15, "para", "Uygulama okumaz (bilgi).", ""),
    _O(), _O(),
    Sutun("Bakiye", "Z", 16, "para", bakiye_aciklama, ""),
]

SMM_GIDER_MIZAN = Sablon(
    no="15", ad="smm-gider-mizani", baslik="SMM · Gider mizanı (GİDER MİZAN, 720 / 730)",
    nereye=SMM_NEREYE.format(ad="Gider mizanı (720 / 730)"), kim="Muhasebe (Canias mizanından)", siklik="Her ay sonunda (zorunlu kaynak)",
    okuma=_smm_okuma("GİDER MİZAN", "Hesap Kodu",
                     ["A hesap kodu, G bakiye. Yalnız 3 haneli hesaplar (710, 720, 730, 760, 770...) okunur; alt hesaplar (720.01) atlanır.",
                      "720 ve / veya 730 bulunmazsa dosya reddedilir. Aynı hesap iki kez varsa ilk satır alınır.",
                      "720 / 730 aşama işçilik ve genel üretim gideri dağıtımına gider; Veri Girişi'nde elle de düzeltilebilir.",
                      "Yükleme bu mizanın elle girilmiş satırlarını SİLER (ekran önce sorar)."]),
    hatalar=["Hesap kodunu sayı olarak yazmak sorun değildir (720), ama alt hesapları sayı yazarsanız 720.10 → 720.1 olur; sütun metin biçimlidir.",
             "Bakiyeyi G dışında bir sütuna yazmak: yalnız G okunur.",
             "Yalnız alt hesapları (720.01, 720.02) vermek: 3 haneli ana hesap satırı gerekir."],
    sayfa="GİDER MİZAN", baslik_satiri=2, ust_baslik="GİDER MİZANI (bu satır serbest)",
    sutunlar=_MIZAN_SUTUNLARI("3 haneli hesap kodu (alt hesaplar okunmaz). 720 ya da 730 zorunlu.",
                              "Hesap bakiyesi, TL (sayı hücresi).", "720"),
    ornek=[["710", "Direkt İlk Madde ve Malzeme Giderleri", 1250000, 0, None, None, 1250000],
           ["720", "Direkt İşçilik Giderleri", 480000, 0, None, None, 480000],
           ["720.01", "Direkt İşçilik Giderleri - Üretim", 336000, 0, None, None, 336000],
           ["720.02", "Direkt İşçilik Giderleri - Diğer", 144000, 0, None, None, 144000],
           ["730", "Genel Üretim Giderleri", 610000, 0, None, None, 610000],
           ["760", "Pazarlama Satış ve Dağıtım Giderleri", 95000, 0, None, None, 95000],
           ["770", "Genel Yönetim Giderleri", 140000, 0, None, None, 140000]],
    baglanti=SMM_BAGLANTI.format(ad="Gider mizanı (720 / 730)"))

SMM_STOK_MIZAN = Sablon(
    no="16", ad="smm-stok-mizani", baslik="SMM · Stok mizanı (STOK MİZAN, 150 / 151 / 152)",
    nereye=SMM_NEREYE.format(ad="Stok mizanı (150 / 151 / 152)"), kim="Muhasebe (Canias mizanından)", siklik="Her ay sonunda",
    okuma=_smm_okuma("STOK MİZAN", "Hesap Kodu",
                     ["A hesap kodu, B hesap adı, G bakiye. Yalnız '15' ile başlayan hesaplar okunur (150.01, 151.01, 152.01...).",
                      "15x hesabı yoksa dosya reddedilir. Mizan, SMM özetinde stok değerlemesiyle karşılaştırılır.",
                      "Yükleme bu mizanın elle girilmiş satırlarını SİLER (ekran önce sorar)."]),
    hatalar=["Hesap kodunu sayı yazmak: 150.10 → 150.1 olur; sütun metin biçimlidir.",
             "Toplam satırını da '15' ile başlayan kodla yazmak: toplam ikinci kez sayılır. Toplam satırı koymayın ya da A'yı boş bırakın.",
             "Bakiyeyi G dışında bir sütuna yazmak."],
    sayfa="STOK MİZAN", baslik_satiri=2, ust_baslik="STOK MİZANI (bu satır serbest)",
    sutunlar=_MIZAN_SUTUNLARI("Stok hesabı (15 ile başlayan: 150.01, 151.01, 152.01...).", "Hesap bakiyesi, TL (sayı hücresi).", "150.01"),
    ornek=[["150.01", "Hammadde", 2000000, 0, None, None, 2000000], ["150.02", "Ambalaj Malzemesi", 2500000, 0, None, None, 2500000],
           ["150.03", "Yardımcı Malzeme", 616894.84, 0, None, None, 616894.84], ["151.01", "Üretim Yarı Mamulü", 500000, 0, None, None, 500000],
           ["152.01", "Mamul", 3850000, 0, None, None, 3850000]],
    baglanti=SMM_BAGLANTI.format(ad="Stok mizanı (150 / 151 / 152)"))

SABLONLAR = [SATIN_ALMA, FIYAT_LISTESI, URETIM_ADETLERI, GIDER, RECETE, STOK, SATIS, LISTE, CANIAS,
             SMM_ALIM, SMM_IADE, SMM_URETIM, SMM_SAYIM, SMM_SAHIT, SMM_GIDER_MIZAN, SMM_STOK_MIZAN]


# ------------------------------------------------------------------------------------------------ kitap
def kitap(t: Sablon, dolu: bool = False) -> Workbook:
    """Şablon kitabı. dolu=True: doldurulacak sayfaya da örnek satırlar yazılır (doğrulamada 'kullanıcı doldurdu' benzetimi)."""
    wb = Workbook()
    ws = wb.active
    ws.title = t.sayfa
    if t.duzen == "gider":
        gider_sayfasi(ws, dolu)
        gider_sayfasi(wb.create_sheet("Örnek"), True)
        aciklama_sayfasi(wb.create_sheet("Açıklama"), t, GIDER_HUCRELERI)
    elif t.duzen == "recete":
        recete_sayfasi(ws, dolu)
        salma_yardimci_sayfasi(wb.create_sheet("S.ALMA BF"))
        recete_sayfasi(wb.create_sheet("Örnek"), True)
        aciklama_sayfasi(wb.create_sheet("Açıklama"), t, RECETE_HUCRELERI)
    else:
        tablo_sayfasi(ws, t, t.ornek if dolu else [])
        tablo_sayfasi(wb.create_sheet("Örnek"), t, t.ornek)
        aciklama_sayfasi(wb.create_sheet("Açıklama"), t)
    # Gizli '_sablon' sayfası (en sonda): uygulama yanlış ekrana yüklenen şablonu bununla tanır. Kimlik sırası = şablon numarası.
    sablon_kimligi_yaz(wb, KIMLIKLER[int(t.no) - 1])
    wb.active = 0
    return wb


# ------------------------------------------------------------------------------------------------ rehber (Markdown)
# Doldurulacak sayfa boş bırakılıp yüklenirse ne olur (11-16-2026-dogrula.py ile uygulamanın okuyucularında denendi).
_BOS_ORTAK = " Mevcut veri değişmez."
BOS_DAVRANIS = {
    "01": "Hata: 'Dosyada okunabilen malzeme satırı yok'." + _BOS_ORTAK,
    "02": "Hata: 'Dosyada okunabilen fiyat satırı yok'." + _BOS_ORTAK,
    "03": "Hata: 'Üretim Adetleri sayfasında satır yok'." + _BOS_ORTAK,
    "04": "Hata: 'Gider Dağıtım sayfası beklenen düzen değil' (bütün toplamlar boş)." + _BOS_ORTAK,
    "05": "Önizlemede '001' sayfası 'reçete satırı yok' diye okunamayan sayfalar listesinde görünür; yazılacak sayfa olmaz." + _BOS_ORTAK,
    "06": "Hata: 'Dosyada okunabilen stok satırı yok'." + _BOS_ORTAK,
    "07": "Hata: 'dosyada veri satırı yok'." + _BOS_ORTAK,
    "08": "Hata: 'dosyada veri satırı yok'." + _BOS_ORTAK,
    "09": "Hata: 'dosyada reçete satırı yok'." + _BOS_ORTAK,
    "15": "Hata: 'gider mizanında 720 / 730 bulunamadı'." + _BOS_ORTAK,
    "16": "Hata: 'stok mizanında 15x hesabı bulunamadı'." + _BOS_ORTAK,
}
SMM_BOS = ("Hata verir (boş dosya); bu kaynağın dönemdeki değerleri DEĞİŞMEZ. Yeni dosyada mevcut kalemlerin yarısından azı varsa "
           "'N kalem silinecek. Emin misiniz?' diye sorulur. Yanlış yüklemede 'Son yükleme — Geri al' ile önceki duruma dönülür.")
for _no in ("10", "11", "12", "13", "14"):
    BOS_DAVRANIS[_no] = SMM_BOS

ORNEK_KLASOR = "test-dongusu/excel/"


def _sutun_ozeti(t: Sablon) -> str:
    if t.duzen == "gider":
        return "Sabit hücreler: toplamlar D4, A6, D13, D18, A20, D27, D38, D49, D60, D64, D67; saniye bazları F4, F13, F18, F27; paylar C7:G9, C21:G23, A30:G37, A41:G48, A52:G59; ambalaj A70:D91."
    if t.duzen == "recete":
        return ("Ürün: D6 kod, E6 ad. Reçete 7. satırdan: A seviye, D malzeme kodu (zorunlu), E ad, I miktar (zorunlu), J fire, K brüt (formül, "
                "dokunmayın), L birim, M birim fiyat (boş = fiyat listesinden). Üretim bilgileri I104, E136-E146; P118/P119 pazarlama-yönetim formülü.")
    z = [f"{get_column_letter(i)} {s.baslik}" for i, s in enumerate(t.sutunlar, 1) if s.durum == "Z"]
    i_ = [f"{get_column_letter(i)} {s.baslik}" for i, s in enumerate(t.sutunlar, 1) if s.durum == "I"]
    metin = "Zorunlu: " + ", ".join(z) + "."
    if i_:
        metin += " İsteğe bağlı: " + ", ".join(i_) + "."
    if any(s.durum == "O" for s in t.sutunlar):
        metin += " Diğer sütunlar okunmaz (yer tutucu)."
    return metin


def rehber_md() -> str:
    y = []
    a = y.append
    a("# Excel yükleme şablonları rehberi")
    a("")
    a("Uygulamada Excel yüklenen her yer için bir şablon: doldurulacak sayfa (adı uygulamanın aradığı ad, kitabın ilk sayfası), **Örnek** "
      "sayfası (uydurma örnek satırlar) ve **Açıklama** sayfası (her sütun ne demek, sık hatalar). Şablonu doldurup dosyayı doğrudan "
      "yükleyebilirsiniz; Örnek ve Açıklama sayfaları dosyada kalabilir, uygulama onları okumaz.")
    a("")
    a("Dosyalar: `sablonlar/` klasörü (proje kökünde). Tarih: 16.11.2026. Okuyucu: muhasebe ekibi ve Esma.")
    a("")
    a("**Renkler:** koyu yeşil başlık = zorunlu sütun · açık gri = isteğe bağlı · soluk italik = uygulama okumaz (yerini korumak için durur, "
      "boş kalabilir). Gider dağıtım ve ürün reçetesi sabit hücre düzenindedir: yeşil hücreler zorunlu, gri hücreler isteğe bağlıdır.")
    a("")
    a("**Genel kurallar (16.11.2026 yükleme güvenliği sonrası):** dosya .xlsx olmalı (satış geçmişi ve liste fiyatları .csv de kabul eder; "
      ".xls ve fiyat listesinde .csv anlaşılır bir hata mesajıyla reddedilir). Kendi Excel'inizi de yükleyebilirsiniz: başlıklar adıyla bulunur; "
      "büyük/küçük harf, Türkçe harf (İ/ı), fazla boşluk ve noktalama fark etmez, bilinen eş anlamlılar tanınır ('Malzeme Kodu' = 'Stok Kodu', "
      "'Birim Fiyat' = 'Fiyat', 'Para Birimi' = 'Döviz' = 'PB'...). Başlık satırı ilk 30 satırda aranır; zorunlu bir sütun yoksa hangisinin eksik "
      "olduğu söylenir. Metin olarak yazılmış sayılar ('1.234,56', '%17', '17 TL') sayıya çevrilir; çevrilemeyen hücre 0 SAYILMAZ, satır "
      "'sorunlu' listesine düşer ve yazılmaz (sorunlu satırların tümü önizlemeden Excel olarak indirilebilir).")
    a("")
    a("**Yanlış dosya ve veri kaybına karşı:** her şablonda gizli bir kimlik sayfası vardır; başka ekranın şablonu yüklenirse 'Bu dosya … şablonu; "
      "burası … yüklemesi' diye reddedilir. Boş dosya hiçbir zaman veriyi silmez (hata verir, mevcut veri değişmez). Yükleme mevcut kayıtları "
      "değiştiriyorsa ve yeni dosyada mevcut kayıtların yarısından azı varsa 'N kalem silinecek. Emin misiniz?' diye sorulur. Her yükleme önce "
      "önizlenir (okunan / yeni / değişen / aynı / silinecek / atlanan sayıları ve sorunlu satırlar). Her yükleme ekranında 'Son yükleme: tarih, "
      "kişi, özet — Geri al' satırı vardır: son yükleme onay sorusuyla geri alınır ve veri yüklemeden önceki haline döner.")
    a("")
    a("Boyut sınırı: Veri Aktar ve Malzeme Fiyatları 25 MB, satış geçmişi ve liste fiyatları 10 MB, Maliyet Muhasebesi 60 MB.")
    a("")
    a("## Sezon başında sırayla")
    a("")
    for m in [
        "Fiyat Çalışması kitabının tamamı varsa: **Veri Aktar › Tüm çalışma kitabı** (malzeme, fiyat, gider, ürün, reçete, parametre, üretim adetleri "
        "tek seferde; şablonu yok, kendi Excel'iniz). Varsa sonraki adımlardan yalnız eksik kalanlar yapılır.",
        "**01 Satın alma fiyat listesi**: malzeme kartları ve bütçe fiyatları. Reçeteden önce gelir: reçetedeki malzemelerin kartı ve fiyatı olsun.",
        "**04 Gider dağıtım**: gider havuzları, hat / sınıf / ambalaj payları (adlar ürün kartlarıyla birebir aynı).",
        "**05 Ürün reçetesi**: her ürün için bir sayfa ('001', '002'...). Yeni ürünün kartı ve üretim bilgileri de buradan açılır.",
        "**03 Üretim adetleri**: vardiya kapasitesi ve hedef üretim.",
        "**06 Stokta kalan**: geçen yıldan devreden stok (ürün kartları açıldıktan sonra).",
        "**07 Satış geçmişi**: geçen yılın satış fiyatları.",
        "**08 Liste fiyatları**: Berrak ürünlerinin önceki yıllardaki liste fiyatları.",
        "Kontrol: **Veri Kontrolü** ekranında fiyatsız malzeme, eksik üretim bilgisi uyarılarını giderin.",
        "Maliyet Muhasebesi tarafı: Canias'ta reçete değiştiyse **09 Canias ürün ağacı** dökümünü yükleyin.",
    ]:
        a(f"- [ ] {m}")
    a("")
    a("Sezon içinde gerektikçe: **02 Malzeme fiyat listesi** (fiyat değişince, revize gelince), **05 Ürün reçetesi** (reçete değişince).")
    a("")
    a("## Her ay sonunda sırayla")
    a("")
    for m in [
        "**Maliyet Muhasebesi › Dönemler › Yeni dönem aç** (açılış stoku önceki ayın sayımından devreder). O ayın SMM Excel'i hazırsa onun yerine "
        "'SMM Excel'inden yükle' (şablonu yok, kendi Excel'iniz; aşağıya bakın).",
        "**Veri Girişi**'nde dönemi seçin, kaynakları yükleyin: **10 Alım ve satış** (zorunlu).",
        "**11 Alım iadeleri** (iade varsa).",
        "**12 Üretim miktarları** (zorunlu).",
        "**13 Sayım** (zorunlu).",
        "**14 Şahit numune** (varsa).",
        "**15 Gider mizanı** (zorunlu; 720 / 730).",
        "**16 Stok mizanı** (150 / 151 / 152; SMM özetindeki stok kıyası için).",
        "Finansman tutarını Veri Girişi'nde elle girin; 'eksik veri', 'türü boş kalem' ve açılış-devir uyarılarını giderin.",
        "Stok ve Envanter, Sarf Farkı ve SMM Özeti'ni kontrol edin; dönemi kapatın (kilit).",
        "Fiyat Çalışması tarafında ay içinde fiyat değiştiyse **02 Malzeme fiyat listesi**; istenirse **07 Satış geçmişi** (ayın satışları).",
    ]:
        a(f"- [ ] {m}")
    a("")
    a("## Şablonlar")
    a("")
    a("| No | Ne için | Uygulamada nereye yüklenir | Dosya | Kim doldurur | Ne sıklıkla |")
    a("|---|---|---|---|---|---|")
    a("| — | Tüm çalışma kitabı (Fiyat Çalışması) | Fiyat Çalışması › Veri Aktar › Tüm çalışma kitabı | Şablon yok: kendi Excel'iniz (aşağıda) | Muhasebe | Sezon başında |")
    for t in SABLONLAR:
        a(f"| {t.no} | {t.baslik} | {t.nereye.split(' → ')[0]} | `{t.dosya.name}` | {t.kim} | {t.siklik} |")
    a("| — | SMM dönem Excel'i | Maliyet Muhasebesi › Dönemler › SMM Excel'inden yükle | Şablon yok: kendi Excel'iniz (aşağıda) | Muhasebe | Ay sonunda, Excel'le çalışılan aylarda |")
    a("")
    for t in SABLONLAR:
        a(f"### {t.no} · {t.baslik}")
        a("")
        a(f"- **Nereye:** {t.nereye}")
        a(f"- **Dosya:** `sablonlar/{t.dosya.name}` · doldurulacak sayfa: '{t.sayfa}'")
        a(f"- **Kim / ne sıklıkla:** {t.kim} · {t.siklik}")
        a(f"- **Sütunlar:** {_sutun_ozeti(t)}")
        a("- **Uygulama nasıl okur:**")
        for m in t.okuma:
            a(f"    - {m}")
        a("- **Sık hatalar:**")
        for m in t.hatalar:
            a(f"    - {m}")
        a(f"- **Boş yüklenirse:** {BOS_DAVRANIS[t.no]}")
        a(f"- **Uygulamada 'Şablonu indir':** {t.baglanti}")
        a("")
    a("## Şablonu olmayan iki yükleme: kendi Excel'inizi olduğu gibi yükleyin")
    a("")
    a("### Tüm çalışma kitabı (Fiyat Çalışması)")
    a("")
    a("**Nereye:** Fiyat Çalışması › Veri Aktar › 'Tüm çalışma kitabı' → dosya, sezon adı (YYYY-YYYY), çalışma adı, tür (Fiyat çalışması / "
      "Gerçekleşen) → Yükle. 'Mevcut çalışmayı tamamla' seçilirse yeni çalışma açılmaz, yalnız eksikler yazılır, var olan hiçbir şey ezilmez.")
    a("")
    a("Muhasebenin kendi Fiyat Çalışması kitabı olduğu gibi yüklenir. Uygulamanın aradığı sayfalar ve hücreler:")
    a("")
    a("| Sayfa | Zorunlu mu | Uygulamanın okuduğu |")
    a("|---|---|---|")
    a("| S.ALMA BF | Evet | 1. satır başlık; A kod, B ad, C tip, D birim, E para birimi, F bütçe fiyatı, G Z/S, I revize fiyat (şablon 01 ile aynı düzen) |")
    a("| Gider Dağıtım | Evet | Sabit hücreler (şablon 04 ile aynı): D4/F4, A6 + C7:G9, D13/F13, D18/F18, A20 + C21:G23, D27/F27, A30:G37 + D38, "
      "A41:G48 + D49, A52:G59 + D60, D64, D67, ambalaj A70:D91. Toplam formülü '=taban*çarpan' kalıbındaysa çarpanlar ayrı saklanır |")
    a("| Ürün sayfaları ('001', '002'...) | En az bir | Şablon 05 düzeni; satırlar D sütunundaki etiketlerle bulunur. '(2)' ekli sayfalar bu yüklemede atlanır. "
      "D6 boşsa ürüne geçici 'SAYFA-001' kodu verilir |")
    a("| İlk ürün sayfası | Evet | Genel parametreler: F148 enflasyon, E150:F155 kurlar, I124:K128 faiz ve stok süresi, L145:L147 teklif kâr oranları, "
      "'Maliyet Sapma' satırının F hücresi (bu etiket ZORUNLU), 'Süzme Miktar'dan sonraki satırın G hücresi (satış fiyatı notu). Diğer sayfalarda farklı olan "
      "parametreler o ürüne özel yazılır |")
    a("| Üretim Adetleri | Hayır | Şablon 03 düzeni; sayfa yoksa kapasite boş kalır |")
    a("| Diğer sayfalar (Teklif Kapak vb.) | — | Okunmaz |")
    a("")
    a("Kritik: kitap Excel'de kaydedilmiş olmalı (uygulama formüllerin son hesaplanan değerini okur). Sayfa adları esnektir (büyük/küçük harf, "
      "Türkçe harf, boşluk); S.ALMA BF, Gider Dağıtım ya da ürün sayfası yoksa hangilerinin eksik olduğu söylenir ve hiçbir şey yazılmaz. "
      "Başka bir şablonun dosyası (ör. 03) buraya yüklenirse reddedilir. 'Tamamla' modunda son yükleme geri alınabilir (eklenen kayıtlar "
      "silinir); 'yeni çalışma' modunda geri almak, açılan çalışmayı silmektir. Uydurma örnek kitap: "
      f"`{ORNEK_KLASOR}11-16-2026-fiyat-calismasi-butce.xlsx` (gerçekleşen için `11-16-2026-fiyat-calismasi-gerceklesen.xlsx`). "
      "Bu klasör test döngüsü için yeniden üretilir; dosya adları değişirse aynı klasördeki 'fiyat-calismasi' dosyalarına bakın.")
    a("")
    a("### SMM dönem Excel'i (Maliyet Muhasebesi)")
    a("")
    a("**Nereye:** Maliyet Muhasebesi › Dönemler › 'SMM Excel'inden yükle (isteğe bağlı)' → dosya → yıl / ay (dosya adında '09-2026' gibi "
      "geçiyorsa oradan bulunur) → Yükle. Dönem zaten yüklüyse üzerine yazma onayı istenir; kilitli döneme yüklenemez.")
    a("")
    a("Muhasebenin aylık SMM Excel'i olduğu gibi yüklenir. Veri sayfalarında başlık 2. satırda, veri 3. satırdan başlar (aylık kaynak şablonları "
      "10-16 da bu düzendedir; sayfaları SMM Excel'ine kopyalanabilir). Aranan sayfalar:")
    a("")
    a("| Sayfa | Zorunlu mu | Uygulamanın okuduğu (3. satırdan) |")
    a("|---|---|---|")
    a("| DBS | Evet | Dönem başı stok: A kod, B ad, C miktar, D tutar |")
    a("| HM-YM ALIŞ SATIŞ | Evet | Şablon 10: B kod, C ad, F birim, G giriş miktarı, K tutar, L çıkış miktarı, T hareket türü ('Satış') |")
    a("| DSS | Evet | Şablon 13: A kod, B ad, C sayım miktarı; E sayım tutarı (Excel'le kıyas için) |")
    a("| TABLO | Evet | J1 finansman tutarı; B kod; D, H, O, U, V, W Excel'in kendi stok tablosu değerleri (uygulamanın hesabıyla kıyaslanır) |")
    a("| ENVANTER | Hayır | A kod, B ad, C birim, D malzeme türü, E mizan kodu; P sütunundaki formülün baktığı '20 KOD' / '40 KOD' / '50 KOD' sayfası üretim aşamasını belirler |")
    a("| İADELER, ÜRETİM, ŞAHİT | Hayır | Şablon 11, 12, 14 ile aynı sütunlar |")
    a("| GİDER MİZAN | Hayır | Şablon 15: 3 haneli hesaplar, G bakiye (720 / 730 aşama dağıtımına gider) |")
    a("| STOK MİZAN | Hayır | Şablon 16: 15x hesaplar, G bakiye; J2 mizan (fiş) tarihi |")
    a("| 20 KOD, 40 KOD, 50 KOD | Hayır | Aşama reçeteleri. 1. satırda dağıtım havuzları (20 KOD: P1, S1 · 40 KOD: P1, U1, Z1, AC1 · 50 KOD: P1, U1). "
      "3. satırdan A ana kod, B ana ad, C ana miktar, D ana birim, E malzeme kodu, F ad, G miktar, H birim; fire oranı 20 KOD X, 40 KOD AF, 50 KOD Z; "
      "Excel'in aşama birim maliyeti 20 KOD U, 40 / 50 KOD W |")
    a("| 51 | Hayır | Üretim süreleri: B mamul, C yarı mamul, D ad, J vardiya üretim, L dolum işçi, M etiket işçi, P-S dolum / etiket saniyeleri |")
    a("")
    a("Kritik: DBS, HM-YM ALIŞ SATIŞ, DSS ve TABLO sayfalarından biri eksikse dosya reddedilir ('SMM Excel'inde beklenen sayfalar yok'). "
      f"Uydurma örnek kitap: `{ORNEK_KLASOR}11-16-2026-smm-ekim-2026.xlsx`; aylık kaynak örnekleri aynı klasörde `11-16-2026-smm-kasim-2026-*.xlsx` "
      "(klasör test döngüsü için yeniden üretilir; adlar değişirse 'smm' ile başlayan dosyalara bakın).")
    a("")
    a("## Muhasebeye açık sorular")
    a("")
    a("- **ÜRETİM sayfası O sütunu:** uygulama bu sütunu dönemin (ayın) üretim miktarı olarak kullanıyor; SMM Excel'indeki açıklamada 'yıl içi toplam' "
      "deniyor. Aylık kaynakta ayın üretimi mi, yıl başından toplam mı yazılacak? Şablon 12 şimdilik 'dönemde üretilen miktar' diyor.")
    a("- **Üretim Adetleri 'NET SÜRE' / 'TOPLAM SÜRE' birimi:** şablonda saat (vardiya başına) varsayıldı; Excel'inizdeki birimle teyit edin.")
    a("")
    a("## Doğrulama")
    a("")
    a("Her şablon uygulamanın kendi okuyucularıyla (sunucu açılmadan, bellek içi veritabanında) üç biçimde denendi: şablon boşken, yalnız Örnek "
      "sayfası tek sayfalık dosya olarak ve doldurulacak sayfaya örnek yazılmış kitap (Örnek / Açıklama sayfaları dosyadayken; uygula / yükle dahil). "
      "16 şablonun 16'sı hatasız okundu ve satır sayıları örnekle aynı çıktı. Ayrıntı: `sablonlar/11-16-2026-dogrulama-sonucu.txt`. "
      "Yeniden denemek için proje kökünden: `.venv\\Scripts\\python.exe sablonlar\\11-16-2026-dogrula.py`.")
    a("")
    a("Ürün reçetesi (05): eskiden yalnız Örnek sayfası tek başına yüklenince boş birim fiyat hücreleri 'elle fiyat 0' sayılıyordu; "
      "16.11.2026'dan beri boş M (birim fiyat) ve boş K (brüt miktar) hücresi 'değer yok' sayılır (fiyat Malzeme Fiyatları'ndan, brüt fire "
      "kuralından gelir). Şablondaki boş 'S.ALMA BF' sayfası yine de silinmemeli (formül yerine sayı yazılmış fiyatların ayrımı için).")
    a("")
    return "\n".join(y)


def main() -> int:
    BURASI.mkdir(exist_ok=True)
    for t in SABLONLAR:
        kitap(t).save(t.dosya)
        print(f"yazıldı: sablonlar/{t.dosya.name}")
    rehber = BURASI / f"{ON}sablonlar-rehberi.md"
    rehber.write_text(rehber_md(), encoding="utf-8")
    print(f"yazıldı: sablonlar/{rehber.name}")
    print(f"{len(SABLONLAR)} şablon")
    return 0


if __name__ == "__main__":
    sys.exit(main())
