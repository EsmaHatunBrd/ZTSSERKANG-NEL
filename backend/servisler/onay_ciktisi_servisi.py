"""Onay çıktısı (yeminli mali müşavir için): Fiyat Çalışması ve aylık SMM'nin "değerli" Excel'i (yalnız rakam, formül yok) ve PDF'i.

YENİ HESAP KURALI YOKTUR. Her rakam var olan bir servisin sonucudur:
    Fiyat: Teklif Kapak ve maliyet kartları (api.disa_aktar üreticileri), malzeme fiyatları (fiyat_servisi), parametreler
           (parametre_servisi), gider havuzları (gider_servisi), değişiklikler (gunluk_servisi).
    SMM:   stok tablosu (smm_servisi.stok_tablosu), aşama maliyetleri (smm_asama_servisi.uretim_maliyeti), dönem sonu stok değerlemesi
           (smm_ozet_servisi._dss), SMM tablosu / fiş / mizan kıyası (smm_ozet_servisi.smm_ozeti), mizanlar (smm_mizan_servisi.liste),
           kaynak yüklemeleri (smm_veri_servisi.veri_durumu), değişiklikler (DegisiklikKaydi).
Mutabakat sayfasındaki "fark" sütunları da servislerin verdiği farklardır (mizan_kiyas.fark, dagitim.dagitilmayan); fiş dengesi
borç − alacak toplamıdır.

Çıktı önce tek bir openpyxl çalışma kitabı olarak kurulur; PDF aynı kitaptan çizilir (onay_pdf): iki türde içerik aynıdır.
Durum: çalışma / dönem kilitliyse KESİN, değilse TASLAK (her sayfanın başında kırmızı damga). Hiçbir kayıt değiştirilmez."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from importlib import metadata
from io import BytesIO
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..depo import modeller as m
from . import fiyat_servisi as fs, gider_servisi as gs, gunluk_servisi as gl, hesap_servisi as hs, parametre_servisi as ps
from . import senaryo_servisi, smm_mizan_servisi as mz, smm_ozet_servisi as so, smm_servisi as ss, smm_veri_servisi as sv
from .hatalar import DogrulamaHatasi, liste_metni
from .smm_asama_servisi import _Baglam, uretim_maliyeti

PROJE = Path(__file__).resolve().parents[2]
SIRKET = "Zeytursan"
BELGE = {"fiyat": "Fiyat Çalışması Onay Çıktısı", "smm": "Maliyet Muhasebesi Onay Çıktısı"}
B_TUTAR, B_FIYAT, B_ORAN, B_ADET = "#,##0.00", "#,##0.0000", "0.00%", "#,##0"
BICIM = {"tutar": B_TUTAR, "fiyat": B_FIYAT, "miktar": B_TUTAR, "oran": B_ORAN, "adet": B_ADET}
KIRMIZI, YESIL = "C00000", "1E6B34"
KALIN = Font(bold=True)
INCE = Side(style="thin", color="999999")
CERCEVE = Border(left=INCE, right=INCE, top=INCE, bottom=INCE)
GUNLUK_GUN = 90          # Fiyat günlük özeti: son 90 gün
SON_KAYIT = 50           # günlük özetinde listelenen son kayıt sayısı
IMZA_GOREVLERI = (("hazirlayan", "Hazırlayan"), ("kontrol_eden", "Kontrol eden"), ("onaylayan", "Onaylayan"))
GUNLUK_TUR_ADI = {"parametre": "Parametre", "fiyat": "Malzeme fiyatı", "fire": "Fire kuralı", "metin": "Metin parametresi", "recete": "Reçete",
                  "hesap": "Kayıtlı hesap", "teklif": "Teklif", "urun": "Ürün kartı", "hedef": "Üretim hedefi", "havuz": "Gider havuzu",
                  "ambalaj": "Ambalaj sınıfı", "kapasite": "Üretim kapasitesi", "satis": "Satış geçmişi", "diger": "Diğer"}
ELLE_DISI_TURLER = {"hesap", "teklif"}   # kayıtlı hesap ve teklif turu bir değer değişikliği değildir
# SMM: dönem kaydındaki (smm_donem) elle değer değişiklikleri; yükleme, kilit, devir gibi işlemler "elle" sayılmaz
SMM_ELLE_ISLEMLER = {"ayar_guncelle", "asama_elle", "dagitim", "sure_ekle", "sure_guncelle", "sure_sil"}
SMM_GRUP_ADI = {**so.GRUP_ADI}


# ---------------------------------------------------------------- girdi ve bağlam
@dataclass
class Ekler:
    kapak: bool = True
    mutabakat: bool = True            # yalnız SMM
    elle_degisiklikler: bool = True
    gunluk_ozeti: bool = True


@dataclass
class Imzalar:
    hazirlayan: str | None = None
    kontrol_eden: str | None = None
    onaylayan: str | None = None


@dataclass
class Tablo:
    """Nötr tablo: kolonlar (başlık, tür); tür metin | tutar | fiyat | miktar | oran | adet. vurgulu: kalın yazılacak satır indeksleri."""
    kolonlar: list[tuple[str, str]]
    satirlar: list[list]
    baslik: str | None = None
    vurgulu: set[int] = field(default_factory=set)


@dataclass
class Cikti:
    """Çıktının üst bilgileri (kapak, damga, yazdırma başlığı) ve PDF çizimi için sayfa düzeni bilgisi."""
    modul: str
    belge: str
    kesin: bool
    kapsam: str
    donem: str
    hesap_tarihi: date
    kapatan: str | None
    kapanis: datetime | None
    alan: str
    zaman: datetime
    surum: str
    kaynaklar: list[list]
    imzalar: Imzalar
    ekler: Ekler
    dosya_koku: str
    tablolar: dict[str, list[tuple[int, int]]] = field(default_factory=dict)   # sayfa -> [(başlık satırı, son satır)]
    aciklamalar: dict[str, str] = field(default_factory=dict)                  # sayfa -> içindekiler açıklaması
    kart_sayfalari: list[str] = field(default_factory=list)
    imza_satiri: int | None = None                                             # Kapak'ta imza tablosunun başladığı satır

    @property
    def durum(self) -> str:
        return "KESİN" if self.kesin else "TASLAK"

    @property
    def damga(self) -> str:
        if not self.kesin:
            return f"TASLAK — {'dönem' if self.modul == 'smm' else 'çalışma'} kapatılmadı"
        ek = " · ".join(x for x in (self.kapatan, _zaman_tr(self.kapanis)) if x)
        return f"KESİN — {'dönem' if self.modul == 'smm' else 'çalışma'} kapatıldı" + (f" ({ek})" if ek else "")


# ---------------------------------------------------------------- yardımcılar
def _n(x) -> Decimal | None:
    """Servis çıktısındaki decimal metni / sayıyı Decimal'e çevirir; boşsa None."""
    if x is None or x == "":
        return None
    return x if isinstance(x, Decimal) else Decimal(str(x))


def _yerel(z: datetime | None) -> datetime | None:
    """Saklanan UTC (naif) zamanı sunucunun yerel saatine çevirir."""
    if z is None:
        return None
    if z.tzinfo is None:
        z = z.replace(tzinfo=timezone.utc)
    return z.astimezone()


def _zaman_tr(z: datetime | str | None) -> str | None:
    if z is None or z == "":
        return None
    if isinstance(z, str):   # ISO metin: ofsetliyse yerele çevrilir; ofsetsizse (veri kaynağı kayıtları) zaten yerel saattir
        try:
            z = datetime.fromisoformat(z)
        except ValueError:
            return z
        z = _yerel(z) if z.tzinfo is not None else z
    else:                    # datetime: naifse veritabanından gelen UTC'dir
        z = _yerel(z)
    return f"{z:%d.%m.%Y %H:%M}"


def _tarih_tr(t: date | None) -> str | None:
    return None if t is None else f"{t:%d.%m.%Y}"


def surum() -> str:
    """Uygulama sürümü: git kısa özeti (.git dosyalarından okunur; git komutu çalıştırılmaz), okunamazsa paket sürümü."""
    try:
        git = PROJE / ".git"
        bas = (git / "HEAD").read_text(encoding="utf-8").strip()
        if bas.startswith("ref:"):
            ref = bas.split(" ", 1)[1].strip()
            yol = git / ref
            if yol.is_file():
                return yol.read_text(encoding="utf-8").strip()[:7]
            for satir in (git / "packed-refs").read_text(encoding="utf-8").splitlines():
                if satir.endswith(" " + ref):
                    return satir.split(" ", 1)[0][:7]
        elif len(bas) >= 7:
            return bas[:7]
    except OSError:
        pass
    try:
        return "sürüm " + metadata.version("fiyat-motoru")
    except metadata.PackageNotFoundError:
        return "bilinmiyor"


def _genislik(tur: str, deger) -> int:
    if tur != "metin":
        return 15
    return min(max(len(str(deger or "")) + 2, 8), 50)


# ---------------------------------------------------------------- Excel: nötr sayfa, damga, yazdırma
def damga_yaz(hucre, c: Cikti, onek: str = "") -> None:
    """Hücreye KESİN (yeşil) / TASLAK (kırmızı) damgası; `onek` doluysa (ör. kart sayfasının notu) damganın arkasına eklenir."""
    hucre.value = c.damga + (" · " + onek if onek else "")
    hucre.font = Font(bold=True, color=YESIL if c.kesin else KIRMIZI, size=11)
    hucre.alignment = Alignment(wrap_text=False, vertical="center")   # Teklif Kapak'ın 1. satırı sarmalıdır; damga tek satır kalsın


def tablo_sayfasi(wb, c: Cikti, ad: str, baslik: str, tablolar: list[Tablo], notlar: list[str] | tuple = (), aciklama: str | None = None):
    """Nötr sayfa: 1. satır başlık, 2. satır KESİN/TASLAK damgası, 3. satır notlar, 5. satırdan tablolar (aralarında bir boş satır).
    İlk tablonun başlık satırı dondurulur; tablo konumları PDF çizimi için `c.tablolar`a yazılır."""
    ws = wb.create_sheet(ad)
    ws["A1"] = baslik
    ws["A1"].font = Font(bold=True, size=13)
    damga_yaz(ws["A2"], c)
    if notlar:
        ws["A3"] = " · ".join(notlar)
        ws["A3"].font = Font(italic=True)
    genislik: dict[int, int] = {}
    satir = 5
    konumlar = []
    for t in tablolar:
        if t.baslik:
            ws.cell(row=satir, column=1, value=t.baslik).font = Font(bold=True, size=12)
            satir += 1
        bas = satir
        for j, (b, tur) in enumerate(t.kolonlar, start=1):
            h = ws.cell(row=satir, column=j, value=b)
            h.font = KALIN
            h.fill = PatternFill("solid", fgColor="E7E6E6")
            h.alignment = Alignment(wrap_text=True, vertical="center", horizontal="left" if tur == "metin" else "right")
            genislik[j] = max(genislik.get(j, 0), min(max(len(b) + 2, 10), 24) if tur == "metin" else 15)
        for i, r in enumerate(t.satirlar):
            satir += 1
            for j, ((_, tur), v) in enumerate(zip(t.kolonlar, r), start=1):
                if tur in BICIM:
                    hc = ws.cell(row=satir, column=j, value=None if _n(v) is None else float(_n(v)))
                    hc.number_format = BICIM[tur]
                else:
                    hc = ws.cell(row=satir, column=j, value=None if v in (None, "") else str(v))
                    genislik[j] = max(genislik.get(j, 0), _genislik(tur, v))
                if i in t.vurgulu:
                    hc.font = KALIN
        konumlar.append((bas, satir))
        satir += 2
    for j, g in genislik.items():
        ws.column_dimensions[get_column_letter(j)].width = g
    if konumlar:
        ws.freeze_panes = f"A{konumlar[0][0] + 1}"
    c.tablolar[ad] = konumlar
    if aciklama:
        c.aciklamalar[ad] = aciklama
    return ws


def yazdirma_ayarla(ws, c: Cikti) -> None:
    """Yatay, sayfa genişliğine sığdır; üst bilgi: belge adı + durum; alt bilgi: sayfa n/N; dondurulmuş satırlar her sayfada tekrar."""
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.oddHeader.center.text = f"{c.belge} — {c.durum}"
    ws.oddHeader.center.color = YESIL if c.kesin else "FF0000"
    ws.oddFooter.center.text = "Sayfa &P / &N"
    if ws.freeze_panes and ws.freeze_panes != "A1":
        son = int("".join(ch for ch in ws.freeze_panes if ch.isdigit())) - 1
        if son >= 1:
            ws.print_title_rows = f"1:{son}"


def kapak_yaz(ws, c: Cikti, wb) -> None:
    """Kapak: şirket, belge adı, durum, kapsam ve tarih bilgileri, kaynak dosyalar, köprülü içindekiler ve imza tablosu."""
    from ..api.disa_aktar import _ic_baglanti
    ws["A1"] = SIRKET
    ws["A1"].font = Font(bold=True, size=16)
    ws["A2"] = c.belge
    ws["A2"].font = Font(bold=True, size=14)
    damga_yaz(ws["A3"], c)
    bilgiler = [("Belge", c.belge), ("Kapsam", c.kapsam), ("Sezon / dönem" if c.modul == "fiyat" else "Dönem", c.donem),
                ("Hesap tarihi", _tarih_tr(c.hesap_tarihi)), ("Durum", c.durum),
                ("Kapatan", c.kapatan or "—"), ("Kapanış tarihi", _zaman_tr(c.kapanis) or "—"),
                ("Çıktıyı alan", c.alan), ("Çıktı zamanı", _zaman_tr(c.zaman)), ("Uygulama sürümü", c.surum)]
    satir = 5
    for etiket, deger in bilgiler:
        ws.cell(row=satir, column=1, value=etiket).font = KALIN
        ws.cell(row=satir, column=2, value=deger)
        satir += 1
    konumlar = []
    satir += 1
    ws.cell(row=satir, column=1, value="Kaynak dosyalar").font = Font(bold=True, size=12)
    satir += 1
    bas = satir
    for j, b in enumerate(("Kaynak", "Dosya", "Yükleme zamanı", "Yükleyen", "Satır"), start=1):
        ws.cell(row=satir, column=j, value=b).font = KALIN
    for k in c.kaynaklar or [["—", "Kaynak dosya kaydı yok", None, None, None]]:
        satir += 1
        for j, v in enumerate(k, start=1):
            hc = ws.cell(row=satir, column=j, value=v)
            if j == 5 and v is not None:
                hc.number_format = B_ADET
    konumlar.append((bas, satir))
    satir += 2
    ws.cell(row=satir, column=1, value="İçindekiler").font = Font(bold=True, size=12)
    satir += 1
    bas = satir
    ws.cell(row=satir, column=1, value="Sayfa").font = KALIN
    ws.cell(row=satir, column=2, value="İçerik").font = KALIN
    kartlar = set(c.kart_sayfalari)
    for ad in wb.sheetnames:
        if ad == ws.title or ad in kartlar:
            continue
        satir += 1
        _ic_baglanti(ws.cell(row=satir, column=1), ad, ad)
        ws.cell(row=satir, column=2, value=c.aciklamalar.get(ad))
    if kartlar:
        satir += 1
        ws.cell(row=satir, column=1, value=f"{len(kartlar)} ürün kartı")
        ws.cell(row=satir, column=2, value="Ürün başına bir sayfa; listesi ve köprüleri Özet sayfasında")
    konumlar.append((bas, satir))
    satir += 2
    c.imza_satiri = satir
    ws.cell(row=satir, column=1, value="İmzalar").font = Font(bold=True, size=12)
    satir += 1
    bas = satir
    for j, b in enumerate(("Görev", "Ad soyad", "Tarih", "İmza"), start=1):
        h = ws.cell(row=satir, column=j, value=b)
        h.font = KALIN
        h.border = CERCEVE
    for alan, etiket in IMZA_GOREVLERI:
        satir += 1
        ws.row_dimensions[satir].height = 36
        for j, v in enumerate((etiket, getattr(c.imzalar, alan) or None, None, None), start=1):
            h = ws.cell(row=satir, column=j, value=v)
            h.border = CERCEVE
            h.alignment = Alignment(vertical="center")
    konumlar.append((bas, satir))
    for h, g in (("A", 24), ("B", 60), ("C", 20), ("D", 26), ("E", 10)):
        ws.column_dimensions[h].width = g
    c.tablolar[ws.title] = konumlar


def kitabi_bitir(wb, c: Cikti) -> None:
    for ws in wb.worksheets:
        yazdirma_ayarla(ws, c)
    if c.ekler.kapak:
        kapak_yaz(wb["Kapak"], c, wb)
        wb.active = 0


# ---------------------------------------------------------------- ortak ekler
def _elle_tablosu(satirlar: list[dict]) -> Tablo:
    return Tablo([("Zaman", "metin"), ("Kullanıcı", "metin"), ("Nesne", "metin"), ("Ürün / kalem", "metin"), ("Eski", "metin"),
                  ("Yeni", "metin"), ("Neden", "metin")],
                 [[_zaman_tr(r["zaman"]), r["kullanici"], r["baslik"], r.get("urun_kodu"), r.get("eski"), r.get("yeni"), r.get("neden")]
                  for r in satirlar])


def _gunluk_tablolari(satirlar: list[dict], tur_adi) -> list[Tablo]:
    sayac = Counter(tur_adi(r) for r in satirlar)
    ozet = Tablo([("Tür", "metin"), ("Kayıt sayısı", "adet")], [[t, n] for t, n in sorted(sayac.items(), key=lambda x: (-x[1], x[0]))]
                 + [["Toplam", len(satirlar)]], baslik="Tür bazında", vurgulu={len(sayac)})
    son = _elle_tablosu(satirlar[:SON_KAYIT])
    son.baslik = f"Son {min(SON_KAYIT, len(satirlar))} kayıt"
    return [ozet, son]


def _kaydet(wb) -> bytes:
    b = BytesIO()
    wb.save(b)
    return b.getvalue()


def _bos_kitap(c: Cikti) -> Workbook:
    wb = Workbook()
    if c.ekler.kapak:
        wb.active.title = "Kapak"
        c.aciklamalar["Kapak"] = "Belge bilgileri, kaynaklar, içindekiler, imzalar"
    else:
        wb.remove(wb.active)
    return wb


# ---------------------------------------------------------------- Fiyat Çalışması
def _senaryo_kilidi(s: Session, sen: m.Senaryo) -> tuple[str | None, datetime | None]:
    if not sen.kilitli:
        return None, None
    k = s.scalar(select(m.DegisiklikKaydi).where(m.DegisiklikKaydi.tablo == "senaryo", m.DegisiklikKaydi.kayit_id == sen.id,
                                                 m.DegisiklikKaydi.islem == "kilitle").order_by(m.DegisiklikKaydi.id.desc()).limit(1))
    return (k.kullanici, _yerel(k.zaman)) if k else (None, None)


def fiyat_kitabi(s: Session, senaryo_id: int, kodlar: list[str] | None, ekler: Ekler, imzalar: Imzalar, alan: str) -> tuple[Workbook, Cikti]:
    from ..api.disa_aktar import maliyet_kartlari_sayfalari, teklif_kapak_sayfasi
    sen = hs.senaryo_getir(s, senaryo_id)
    t = date.today()
    uyeler = senaryo_servisi.uye_urun_kodlari(s, sen.id)
    secili: set[str] | None = None
    if kodlar is not None:
        secili = {k.strip() for k in kodlar if k and k.strip()}
        if not secili:
            raise DogrulamaHatasi("En az bir ürün seçin.", {"urunler": "boş"})
        yok = sorted(secili - uyeler)
        if yok:
            raise DogrulamaHatasi(f"Seçilen ürünlerden bazıları bu çalışmada yok: {liste_metni(yok)}.", {"urunler": yok[:20]})
    kapatan, kapanis = _senaryo_kilidi(s, sen)
    kapsam = (f"Çalışma: {sen.sezon.ad} — {sen.ad}; "
              + (f"tüm ürünler ({len(uyeler)})" if secili is None or secili == uyeler else f"seçili {len(secili)} ürün (çalışmada {len(uyeler)})"))
    kaynaklar = [["Fiyat çalışması dosyası", sen.kaynak_dosya, _zaman_tr(_yerel(sen.olusturma_zamani)), sen.olusturan, None]] if sen.kaynak_dosya else []
    sezon = "".join(ch if ch.isalnum() else "-" for ch in sen.sezon.ad).strip("-") or "sezon"
    c = Cikti("fiyat", BELGE["fiyat"], bool(sen.kilitli), kapsam, f"{sen.sezon.ad} — {sen.ad}", t, kapatan, kapanis, alan,
              datetime.now().astimezone(), surum(), kaynaklar, imzalar, ekler, f"rapor-fiyat-{sezon}-{t:%m-%d-%Y}")
    wb = _bos_kitap(c)
    sabit = {"kapak", "teklif kapak", "satın alma fiyatları", "parametreler", "gider dağıtım", "elle değişiklikler", "günlük özeti"}

    tk = wb.create_sheet("Teklif Kapak")
    teklif_kapak_sayfasi(tk, s, sen, None, kodlar=secili)
    damga_yaz(tk["L1"], c)
    c.aciklamalar["Teklif Kapak"] = "Ürün başına reçete maliyeti, giderler ve birim maliyet (TL / USD / EUR)"

    oz = wb.create_sheet("Özet")
    once = set(wb.sheetnames)
    maliyet_kartlari_sayfalari(wb, oz, s, sen, t, kodlar=secili, kullanilan=set(sabit))
    damga_yaz(oz["A3"], c)
    c.aciklamalar["Özet"] = "Maliyet kartları özeti; ürün sayfalarına köprü"
    c.kart_sayfalari = [ad for ad in wb.sheetnames if ad not in once]
    for ad in c.kart_sayfalari:
        damga_yaz(wb[ad]["A3"], c, onek=wb[ad]["A3"].value or "")

    # Satın alma fiyatları: senaryodaki tüm malzeme kartları (geçerli fiyat ve ilk bütçe; malzemeler ekranıyla aynı kaynak)
    gecerli = fs.gecerli_kayitlar_kodla(s, sen.id, t)
    ilk = fs.ilk_kayitlar_kodla(s, sen.id)
    satirlar = []
    for kod, mzk in sorted(fs.gecerli_fiyatlar(s, sen.id, t).items()):
        g, i = gecerli.get(kod), ilk.get(kod)
        satirlar.append([kod, mzk.ad, mzk.tip, mzk.birim, mzk.para_birimi, i.fiyat if i else None, g.fiyat if g else None,
                         _tarih_tr(g.gecerlilik_basi) if g else None, g.kaynak if g else None,
                         "Evet" if g and i and g.fiyat != i.fiyat else None])
    tablo_sayfasi(wb, c, "Satın Alma Fiyatları", f"Satın alma fiyatları — {sen.sezon.ad} — {sen.ad}",
                  [Tablo([("Kod", "metin"), ("Malzeme", "metin"), ("Tip", "metin"), ("Birim", "metin"), ("Para birimi", "metin"),
                          ("İlk bütçe fiyatı", "fiyat"), ("Geçerli fiyat", "fiyat"), ("Geçerlilik başı", "metin"), ("Kaynak", "metin"),
                          ("Revize", "metin")], satirlar)],
                  [f"Geçerli fiyat {t:%d.%m.%Y} itibarıyla", "İlk bütçe: çalışmadaki en eski fiyat kaydı", "Fiyatlar malzemenin kendi para birimindedir"],
                  "Malzeme fiyatları: ilk bütçe ve geçerli fiyat")

    tanim = {p.anahtar: p for p in ps.tanimlar(s)}
    degerler = ps.gecerli_degerler(s, sen.id, t)
    tablo_sayfasi(wb, c, "Parametreler", f"Parametreler — {sen.sezon.ad} — {sen.ad}",
                  [Tablo([("Anahtar", "metin"), ("Açıklama", "metin"), ("Birim", "metin"), ("Değer", "fiyat")],
                         [[k, tanim[k].aciklama if k in tanim else None, tanim[k].birim if k in tanim else None, v]
                          for k, v in sorted(degerler.items())])],
                  [f"Geçerli (genel) değerler, {t:%d.%m.%Y} itibarıyla", "Değerler 4 basamakla gösterilir"], "Geçerli parametre değerleri")

    havuz_satirlari, vurgu = [], set()
    for kod, h in sorted(gs.havuzlar(s, sen.id).items()):
        vurgu.add(len(havuz_satirlari))
        havuz_satirlari.append([kod, h.ad, h.baz_tipi, h.toplam_tutar, h.baz_miktar, None, None, None])
        for a in h.anahtarlar:
            havuz_satirlari.append([None, None, None, None, None, a.alt_kalem, a.pay_orani, a.baz_miktar])
    pay_hata = gs.pay_toplami_kontrol(s, sen.id)
    tablo_sayfasi(wb, c, "Gider Dağıtım", f"Gider dağıtımı — {sen.sezon.ad} — {sen.ad}",
                  [Tablo([("Havuz", "metin"), ("Ad", "metin"), ("Baz tipi", "metin"), ("Toplam tutar TL", "tutar"), ("Baz miktarı", "miktar"),
                          ("Alt kalem", "metin"), ("Pay oranı", "oran"), ("Alt kalem baz miktarı", "miktar")], havuz_satirlari, vurgulu=vurgu)],
                  ["Havuz satırı kalın; altındaki satırlar dağıtım anahtarları (paylar)",
                   "Pay toplamı 1'den farklı havuz: " + (", ".join(x["havuz"] for x in pay_hata) if pay_hata else "yok")],
                  "Gider havuzları ve dağıtım payları")

    if ekler.elle_degisiklikler or ekler.gunluk_ozeti:
        tum = gl._suz(gl._tum_satirlar(s, sen.id), gl.Suzgec(senaryo=sen.id))
        if secili is not None:
            tum = [r for r in tum if r["urun_kodu"] is None or r["urun_kodu"] in secili]
        if ekler.elle_degisiklikler:
            elle = [r for r in tum if r["tur"] not in ELLE_DISI_TURLER and r["eski"] is not None]
            tablo_sayfasi(wb, c, "Elle Değişiklikler", "Elle yapılan değişiklikler", [_elle_tablosu(elle)],
                          ["İlk yüklemeden sonra elle değiştirilen değerler (eski değeri olan günlük kayıtları; kayıtlı hesap ve teklif hariç)",
                           f"{len(elle)} kayıt, yeniden eskiye"], "Elle değiştirilen fiyat, parametre, reçete ve kartlar")
        if ekler.gunluk_ozeti:
            sinir = gl._gun_basi(t - timedelta(days=GUNLUK_GUN - 1))
            son = [r for r in tum if r["_z"] >= sinir]
            tablo_sayfasi(wb, c, "Günlük Özeti", f"Değişiklik günlüğü özeti — son {GUNLUK_GUN} gün",
                          _gunluk_tablolari(son, lambda r: GUNLUK_TUR_ADI.get(r["tur"], r["tur"])),
                          [f"{_tarih_tr(t - timedelta(days=GUNLUK_GUN - 1))} – {_tarih_tr(t)}", f"{len(son)} kayıt"],
                          f"Son {GUNLUK_GUN} günün değişiklik sayıları ve son {SON_KAYIT} kayıt")
    kitabi_bitir(wb, c)
    return wb, c


# ---------------------------------------------------------------- Maliyet muhasebesi (SMM)
def _smm_degisiklikleri(s: Session, d: m.SmmDonem) -> list[dict]:
    """Döneme ait değişiklik kayıtları (dönem, mizan ve stok kalemi), yeniden eskiye; günlük satırı biçiminde."""
    kalemler = dict(s.execute(select(m.SmmKalem.id, m.SmmKalem.kod).where(m.SmmKalem.donem_id == d.id)).all())
    q = select(m.DegisiklikKaydi).where(m.DegisiklikKaydi.tablo.in_(("smm_donem", "smm_mizan", "smm_kalem")))
    out = []
    for k in s.scalars(q):
        if k.tablo in ("smm_donem", "smm_mizan") and k.kayit_id != d.id:
            continue
        if k.tablo == "smm_kalem" and k.kayit_id not in kalemler:
            continue
        eski, yeni, neden = gl.fark_metni(k.eski, k.yeni)
        y = k.yeni if isinstance(k.yeni, dict) else {}
        nesne = kalemler.get(k.kayit_id) if k.tablo == "smm_kalem" else (y.get("_hesap") or y.get("kaynak"))
        elle = k.tablo in ("smm_kalem", "smm_mizan") or k.islem in SMM_ELLE_ISLEMLER
        out.append({"zaman": k.zaman, "_z": k.zaman, "_pk": k.id, "kullanici": k.kullanici or "sistem",
                    "baslik": f"{gl._TABLO_ETIKET.get(k.tablo, k.tablo)} {gl._ISLEM_ETIKET.get(k.islem, k.islem)}",
                    "urun_kodu": nesne, "eski": eski, "yeni": yeni, "neden": neden, "elle": elle})
    out.sort(key=lambda r: (r["_z"] or datetime.min, r["_pk"]), reverse=True)
    return out


def smm_kitabi(s: Session, donem_id: int, ekler: Ekler, imzalar: Imzalar, alan: str) -> tuple[Workbook, Cikti]:
    d = ss.donem_getir(s, donem_id)
    ad = ss.donem_adi(d)
    t = date.today()
    vd = sv.veri_durumu(s, d.id)
    kaynaklar = []
    if d.kaynak_dosya:
        kaynaklar.append(["SMM Excel'i (dönem açılışı)", d.kaynak_dosya, _zaman_tr(_yerel(d.olusturma_zamani)), d.olusturan, None])
    for k in vd["kaynaklar"]:
        if k["son"]:
            kaynaklar.append([k["ad"], k["son"].get("dosya"), _zaman_tr(k["son"].get("zaman")), k["son"].get("kullanici"), k["son"].get("satir")])
    kapanis = ss.kilit_zamani(d)
    c = Cikti("smm", BELGE["smm"], bool(d.kilitli), f"Maliyet muhasebesi, {ad} dönemi", ad, t, d.kilitleyen,
              datetime.fromisoformat(kapanis) if kapanis else None, alan, datetime.now().astimezone(), surum(), kaynaklar, imzalar, ekler,
              f"rapor-smm-{d.yil}-{d.ay:02d}-{t:%m-%d-%Y}")
    wb = _bos_kitap(c)
    o = so.smm_ozeti(s, d.id)

    # Stok ve envanter (TABLO): hareketli kalemler; toplam satırı tüm dönemin toplamları
    st = ss.stok_tablosu(s, d.id, yalniz_hareketli=True)
    kol = [("Kod", "metin"), ("Ad", "metin"), ("Birim", "metin"), ("Tür", "metin"), ("Mizan kodu", "metin"),
           ("Dönem başı miktar", "miktar"), ("Dönem başı tutar", "tutar"), ("Alım miktar", "miktar"), ("Alım tutar", "tutar"),
           ("Finansman payı", "tutar"), ("İade miktar", "miktar"), ("İade tutar", "tutar"), ("Üretim miktar", "miktar"),
           ("Satış miktar", "miktar"), ("Şahit miktar", "miktar"), ("Sayım miktar", "miktar"), ("Ortalama fiyat", "fiyat"),
           ("Sarf miktar", "miktar"), ("Sarf tutar", "tutar"), ("Dönem sonu tutar (ortalama)", "tutar"), ("Kontrol", "metin")]
    alanlar = ["kod", "ad", "birim", "tur", "mizan_kodu", "dbs_miktar", "dbs_tutar", "alim_miktar", "alim_tutar", "finansman_payi", "iade_miktar",
               "iade_tutar", "uretim_miktar", "satis_miktar", "sahit_miktar", "sayim_miktar", "ortalama_fiyat", "sarf_miktar", "sarf_tutar", "dss_tutar"]
    satirlar = [[r[a] for a in alanlar] + ["Sayım eldekinden fazla" if r["kontrol"] else None] for r in st["kayitlar"]]
    tp = st["toplamlar"]
    satirlar.append(["Dönem toplamı (tüm kalemler)", None, None, None, None, None, tp["dbs_tutar"], None, tp["alim_tutar"], tp["finansman_payi"], None,
                     tp["iade_tutar"], None, None, None, None, None, None, tp["sarf_tutar"], tp["dss_tutar"], None])
    tablo_sayfasi(wb, c, "Stok ve Envanter", f"Stok ve envanter tablosu — {ad}", [Tablo(kol, satirlar, vurgulu={len(satirlar) - 1})],
                  [f"{len(st['kayitlar'])} hareketli kalem (dönem başı, alım, iade ya da sayımı olan)",
                   "Dönem sonu tutar burada dönem ortalama fiyatıyladır; değerlemede kullanılan tutar DSS sayfasındadır",
                   f"Sayımı eldekinden fazla kalem: {st['kontrol_sayisi']}"], "Kalem bazında dönem başı, alım, iade, üretim, satış, sayım, sarf")

    # Üretim maliyeti: aşama başına bir sayfa
    dagitim = None
    for asama in (20, 40, 50):
        um = uretim_maliyeti(s, d.id, asama)
        dagitim = um["dagitim"]
        oz = next(x for x in um["ozetler"] if x["asama"] == asama)
        kayit = [[x["kod"], x["ad"], x["birim"], x["uretim_miktar"], x["malzeme"], x["stok_payi"], x["iscilik"], x["gug"], x["fire"],
                  x["birim_maliyet"], x["toplam"], "Evet" if x["alim_kurali"] else None, ", ".join(x["elle_alanlar"]) or None]
                 for x in um["kayitlar"]]
        kayit.append(["Toplam", None, None, None, oz["malzeme"], None, oz["iscilik"], oz["gug"], oz["fire"], None, oz["toplam"], None, None])
        tablo_sayfasi(wb, c, f"Üretim {asama}", f"Üretim maliyeti — {asama} · {oz['ad']} — {ad}",
                      [Tablo([("Kod", "metin"), ("Ürün", "metin"), ("Birim", "metin"), ("Üretim miktarı", "miktar"), ("Malzeme", "fiyat"),
                              ("Stok payı", "fiyat"), ("İşçilik", "fiyat"), ("GÜG", "fiyat"), ("Fire", "fiyat"), ("Birim maliyet", "fiyat"),
                              ("Toplam TL", "tutar"), ("Alım kuralı", "metin"), ("Elle alanlar", "metin")], kayit, vurgulu={len(kayit) - 1})],
                      [f"{oz['urun_sayisi']} ürün, {oz['uretilen_urun']} üretilen", "Malzeme / işçilik / GÜG / fire birim başınadır",
                       "Toplam satırı: miktar × birim değerlerin toplamı (aşama özeti)"],
                      f"{asama} · {oz['ad']}: ürün başına birim maliyet")

    # DSS: kalem başına dönem sonu stok değerlemesi
    dss = so._dss(_Baglam(s, d))
    kalemler = {k.kod: k for k in s.scalars(select(m.SmmKalem).where(m.SmmKalem.donem_id == d.id).order_by(m.SmmKalem.kod))}
    satirlar, grup_top = [], {}
    for kod, k in kalemler.items():
        x = dss.get(kod)
        if x is None or x["grup"] is None or (not k.sayim_miktar and not x["tutar"]):
            continue
        satirlar.append([kod, k.ad, k.birim, x["grup"], k.sayim_miktar, x["fiyat"], x["tutar"]])
        g = grup_top.setdefault(x["grup"], [0, Decimal(0)])
        g[0] += 1
        g[1] += x["tutar"]
    toplam_dss = sum((g[1] for g in grup_top.values()), Decimal(0))
    grup_satir = [[gr, SMM_GRUP_ADI.get(gr), n, tut] for gr, (n, tut) in sorted(grup_top.items())] + [["Toplam", None, sum(g[0] for g in grup_top.values()), toplam_dss]]
    tablo_sayfasi(wb, c, "DSS", f"Dönem sonu stok değerlemesi (DSS) — {ad}",
                  [Tablo([("Hesap", "metin"), ("Hesap adı", "metin"), ("Kalem", "adet"), ("Tutar TL", "tutar")], grup_satir, baslik="Hesap grubu toplamları",
                         vurgulu={len(grup_satir) - 1}),
                   Tablo([("Kod", "metin"), ("Ad", "metin"), ("Birim", "metin"), ("Hesap", "metin"), ("Sayım miktarı", "miktar"), ("Birim fiyat", "fiyat"),
                          ("Tutar TL", "tutar")], satirlar, baslik="Kalemler")],
                  ["Birim fiyat: envanter (aşama) fiyatı, yoksa dönem ortalama fiyatı", "Tutar = birim fiyat × sayım, kuruşa yukarı yuvarlanır"],
                  "Kalem bazında dönem sonu stok değeri ve hesap grubu toplamları")

    # SMM tablosu
    satirlar, vurgu = [], set()
    for b in o["tablo"]:
        vurgu.add(len(satirlar))
        satirlar.append([b["hesap"], b["ad"], None, None])
        for x in b["satirlar"]:
            satirlar.append([None, x["ad"], x["isaret"], x["tutar"]])
        vurgu.add(len(satirlar))
        satirlar.append([None, "= " + b["sonuc_ad"], None, b["sonuc"]])
    ana = [["İlk madde ve malzeme gideri (710)", o["ilk_madde"]], ["Üretim maliyeti", o["uretim_maliyeti"]], ["Üretilen mamul maliyeti", o["uretilen"]],
           ["Satılan mamul maliyeti (620)", o["smm"]], ["Dönem sonu stok (sayım, DSS)", o["donem_sonu_stok"]]]
    tablo_sayfasi(wb, c, "SMM Tablosu", f"Satılan mamul maliyeti tablosu — {ad}",
                  [Tablo([("Kalem", "metin"), ("Tutar TL", "tutar")], ana, baslik="Ana tutarlar"),
                   Tablo([("Hesap", "metin"), ("Kalem", "metin"), ("İşaret", "metin"), ("Tutar TL", "tutar")], satirlar, baslik="Tablo", vurgulu=vurgu)],
                  ["Dönemsellik ilkesi; 720 / 730 gider mizanı bakiyeleri"], "SMM tablosu (150 → 72x → 151 → 152 → 620)")

    # Mizanlar
    gider, stok = mz.liste(s, d.id, "gider"), mz.liste(s, d.id, "stok")
    tablolar = []
    for adi, mzn in (("Gider mizanı", gider), ("Stok mizanı", stok)):
        sat = [[x["hesap"], x["ad"], x["bakiye"], "Evet" if x["elle"] else None] for x in mzn["kayitlar"]] + [["Toplam", None, mzn["toplam"], None]]
        tablolar.append((adi, Tablo([("Hesap", "metin"), ("Hesap adı", "metin"), ("Bakiye TL", "tutar"), ("Elle", "metin")], sat, vurgulu={len(sat) - 1})))
    hv = [[h["ad"], h["tutar"], h["excel"], "Evet" if h["degisti"] else None] for h in dagitim["havuzlar"]] + [["Dağıtılan toplam", dagitim["dagitilan"], None, None]]
    tablo_sayfasi(wb, c, "Gider Mizanı", f"Gider mizanı — {ad}",
                  [tablolar[0][1], Tablo([("Havuz", "metin"), ("Tutar TL", "tutar"), ("Excel'deki tutar", "tutar"), ("Değişti", "metin")], hv,
                                         baslik="Aşamalara dağıtılan gider havuzları", vurgulu={len(hv) - 1})],
                  ["Bakiye: borç bakiyesi artı, alacak bakiyesi eksi", "Elle: ekrandan girilen / değiştirilen satır"],
                  "7xx gider hesapları ve aşamalara dağıtılan havuzlar")
    tablo_sayfasi(wb, c, "Stok Mizanı", f"Stok mizanı — {ad}", [tablolar[1][1]],
                  [f"Mizan tarihi: {o.get('mizan_tarihi') or '—'}", "Elle: ekrandan girilen / değiştirilen satır"], "15x stok hesapları")

    # Fiş taslağı
    fis = [[x["hesap"], x["ad"], f"{ad} {x['aciklama']}", _n(x["borc"]) or None, _n(x["alacak"]) or None] for x in o["fis"]]
    fis.append([None, None, "Toplam", o["fis_borc"], o["fis_alacak"]])
    tablo_sayfasi(wb, c, "Fiş Taslağı", f"SMM fişi taslağı — {ad}",
                  [Tablo([("Hesap kodu", "metin"), ("Hesap adı", "metin"), ("Açıklama", "metin"), ("Borç", "tutar"), ("Alacak", "tutar")], fis,
                         vurgulu={len(fis) - 1})],
                  ["Excel STOK MİZAN kuralları: 710/150, 151/711, 151/721, 151/731, 152/151, 620/152"], "Yevmiye fişi taslağı (borç / alacak)")

    if ekler.mutabakat:
        mk = o["mizan_kiyas"]
        stok_sat = [[x["hesap"], x["ad"], x["mizan"], x["sayim"], x["fark"]] for x in mk]
        stok_sat.append(["Toplam", None, sum((_n(x["mizan"]) for x in mk), Decimal(0)), sum((_n(x["sayim"]) for x in mk), Decimal(0)),
                         sum((_n(x["fark"]) for x in mk), Decimal(0))])
        m720, m730 = _n(dagitim["mizan_720"]) or Decimal(0), _n(dagitim["mizan_730"]) or Decimal(0)
        gider_sat = [["720 Direkt işçilik (mizan)", m720], ["730 Genel üretim gideri (mizan)", m730], ["720 + 730 mizan toplamı", m720 + m730],
                     ["Aşamalara dağıtılan (havuz toplamı)", dagitim["dagitilan"]], ["Fark (dağıtılmayan)", dagitim["dagitilmayan"]]]
        yans = []
        for h, karsi in (("721", "720"), ("731", "730")):
            y = _n(o["yansitilan"].get(h))
            if y is not None:
                k_ = m720 if karsi == "720" else m730
                yans.append([f"{karsi} / {h}", k_, y, k_ + y])
        fis_fark = _n(o["fis_borc"]) - _n(o["fis_alacak"])
        dk = o["dss_kiyas"]
        tablolar = [Tablo([("Hesap", "metin"), ("Hesap adı", "metin"), ("Stok mizanı TL", "tutar"), ("Sayım değeri (DSS) TL", "tutar"), ("Fark TL", "tutar")],
                          stok_sat, baslik="Stok mizanı ile sayım değeri", vurgulu={len(stok_sat) - 1}),
                    Tablo([("Kalem", "metin"), ("Tutar TL", "tutar")], gider_sat, baslik="Gider mizanı (720 / 730) ile dağıtılan tutar", vurgulu={4})]
        if yans:
            tablolar.append(Tablo([("Hesaplar", "metin"), ("Gider (mizan)", "tutar"), ("Yansıtma (mizan)", "tutar"), ("Fark (toplam)", "tutar")], yans,
                                  baslik="Gider ve yansıtma hesapları (mizanda varsa)"))
        tablolar.append(Tablo([("Kalem", "metin"), ("Tutar TL", "tutar")],
                              [["Fiş borç toplamı", o["fis_borc"]], ["Fiş alacak toplamı", o["fis_alacak"]], ["Fark", fis_fark]],
                              baslik="Fiş dengesi", vurgulu={2}))
        if dk["karsilastirilan"]:
            tablolar.append(Tablo([("Kalem", "metin"), ("Değer", "tutar")],
                                  [["Karşılaştırılan kalem", dk["karsilastirilan"]], ["Eşit", dk["esit"]], ["Farklı", dk["farkli"]],
                                   ["Excel DSS toplamı", dk["excel_toplam"]], ["Uygulama DSS toplamı", dk["bizim_toplam"]]],
                                  baslik="Excel DSS ile karşılaştırma (dönem Excel'den açıldıysa)"))
        tablo_sayfasi(wb, c, "Mutabakat", f"Mutabakat — {ad}", tablolar,
                      ["Fark = mizan − sayım; gider farkı = mizan − dağıtılan", "Sıfırdan farklı her fark açıklanmalıdır"],
                      "Stok mizanı ↔ sayım, gider mizanı ↔ dağıtılan, fiş dengesi")

    if ekler.elle_degisiklikler or ekler.gunluk_ozeti:
        tum = _smm_degisiklikleri(s, d)
        if ekler.elle_degisiklikler:
            elle = [r for r in tum if r["elle"]]
            tablo_sayfasi(wb, c, "Elle Değişiklikler", f"Elle yapılan değişiklikler — {ad}", [_elle_tablosu(elle)],
                          ["Stok kalemi düzeltmeleri, mizan satırları, finansman / 720-730 tutarları, aşama elle değerleri, dağıtım ve süreler",
                           f"{len(elle)} kayıt, yeniden eskiye"], "Dönemde elle değiştirilen kalem, mizan ve tutarlar")
        if ekler.gunluk_ozeti:
            tablo_sayfasi(wb, c, "Günlük Özeti", f"Değişiklik günlüğü özeti — {ad}", _gunluk_tablolari(tum, lambda r: r["baslik"]),
                          [f"Dönem içi (bu döneme ait) {len(tum)} kayıt"], f"Dönemin değişiklik sayıları ve son {SON_KAYIT} kayıt")
    kitabi_bitir(wb, c)
    return wb, c


# ---------------------------------------------------------------- dış arayüz
def uret(wb: Workbook, c: Cikti, tur: str) -> tuple[bytes, str, str]:
    """(içerik, medya türü, dosya adı)."""
    if tur == "excel":
        return _kaydet(wb), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", c.dosya_koku + ".xlsx"
    if tur == "pdf":
        from .onay_pdf import pdf_uret
        return pdf_uret(wb, c), "application/pdf", c.dosya_koku + ".pdf"
    raise DogrulamaHatasi("Çıktı türü Excel ya da PDF olmalı.", {"tur": tur})


def fiyat_ciktisi(s: Session, senaryo_id: int, tur: str, kodlar: list[str] | None = None, ekler: Ekler | None = None,
                  imzalar: Imzalar | None = None, alan: str = "sistem") -> tuple[bytes, str, str]:
    wb, c = fiyat_kitabi(s, senaryo_id, kodlar, ekler or Ekler(), imzalar or Imzalar(), alan)
    return uret(wb, c, tur)


def smm_ciktisi(s: Session, donem_id: int, tur: str, ekler: Ekler | None = None, imzalar: Imzalar | None = None,
                alan: str = "sistem") -> tuple[bytes, str, str]:
    wb, c = smm_kitabi(s, donem_id, ekler or Ekler(), imzalar or Imzalar(), alan)
    return uret(wb, c, tur)
