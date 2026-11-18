"""Maliyet Muhasebesi (SMM) yüklemeleri için ortak okuma: esnek sayfa adı, esnek başlık, başka kaynağın dosyasını tanıma,
standart önizleme özeti ve yükleme yedeği için satır kopyası.

Başlık bulma sırası (her kaynak `Tanim` ile tarif edilir):
1. Ad ile: `excel_ortak.baslik_satirini_bul` (büyük/küçük harf, Türkçe harf, boşluk ve noktalama farkı önemsiz; eş anlamlılar `Sutun.adlar`).
   Aynı başlık iki kez geçerse (ör. SMM Excel'inde A ve T sütunu 'Tür') kaynağın bilinen sütun yeri (`konum`) tercih edilir.
2. Başka kaynağın dosyası mı: bu kaynak adla bulunamadı ama başka bir SMM kaynağının bütün zorunlu sütunları adla bulunuyorsa
   anlaşılır red (`kod="yanlis_kaynak"`).
3. SMM Excel düzeni: kod sütunu bilinen yerindeyse (ör. alımda B) ve ad ile bulunamayan sütunların bilinen yeri varsa oradan okunur;
   önizlemede uyarı olarak söylenir (bugünkü SMM Excel'inde başlık metinleri farklı olabilir: 'TOPLAM', 'Miktar').
4. Hiçbiri olmazsa eksik sütunları adıyla söyleyen 422 (`eksik_sutun` / `baslik_yok`).

Canias raporu gelince: yalnız ilgili `Sutun.adlar` listesine eş anlamlı eklemek yeter (smm_veri_servisi.TANIMLAR,
smm_recete_servisi.TANIM)."""
from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.utils.exceptions import InvalidFileException

from .excel_ortak import Alan, KIMLIK_SAYFASI, baslik_anahtari, baslik_satirini_bul, sablon_denetle
from .hatalar import DogrulamaHatasi

YARDIMCI_SAYFALAR = {baslik_anahtari(x) for x in (KIMLIK_SAYFASI, "Örnek", "Açıklama")}   # şablonun okunmayan sayfaları
SORUNLU_SINIRI = 5000   # yanıtta en çok bu kadar sorunlu satır (arayüz ilk 50'yi gösterir, tümü Excel'e iner)


@dataclass
class Sutun:
    ad: str                         # iç ad (ör. "giris")
    adlar: tuple[str, ...]          # adlar[0] kullanıcıya gösterilen; diğerleri eş anlamlı
    zorunlu: bool = True
    konum: int | None = None        # SMM Excel düzenindeki yeri (0 tabanlı); yoksa yalnız adla bulunur

    @property
    def gorunen(self) -> str:
        return self.adlar[0]


@dataclass
class Tanim:
    kimlik: str                     # kaynak kodu (alim, iade, ...)
    ad: str                         # "Alım ve satış"
    sablon: str                     # excel_ortak.SABLONLAR kimliği
    sayfalar: tuple[str, ...]       # aranan sayfa adları (ilk: kullanıcıya söylenen)
    sutunlar: list[Sutun]
    kod: str = "kod"                # kod sütununun iç adı
    yedek_konum: bool = True        # 3. adım (SMM Excel düzeni) açık mı

    @property
    def alanlar(self) -> list[Alan]:
        return [Alan(s.ad, s.adlar, s.zorunlu) for s in self.sutunlar]

    def sutun(self, ad: str) -> Sutun:
        return next(s for s in self.sutunlar if s.ad == ad)


@dataclass
class Okunan:
    sayfa: str
    baslik_satiri: int                          # 1 tabanlı
    sutun: dict[str, int]                       # iç ad -> 0 tabanlı sütun
    satirlar: list[tuple[int, tuple]]           # (Excel satır no, hücreler) — başlığın altındaki boş olmayan satırlar
    uyarilar: list[str] = field(default_factory=list)

    def hucre(self, r: tuple, ad: str):
        i = self.sutun.get(ad)
        return r[i] if i is not None and i < len(r) else None


@dataclass
class Ozet:
    """Standart önizleme özeti (semalar.YuklemeOzeti)."""
    okunan: int = 0
    yeni: int = 0
    degisen: int = 0
    ayni: int = 0
    silinecek: int = 0
    atlanan: int = 0
    sorunlu: list[dict] = field(default_factory=list)
    uyarilar: list[str] = field(default_factory=list)

    def sorun(self, satir: int | None, kod, alan: str | None, deger, neden: str) -> None:
        if len(self.sorunlu) < SORUNLU_SINIRI:
            self.sorunlu.append({"satir": satir, "kod": None if kod is None else str(kod)[:60], "alan": alan,
                                 "deger": None if deger is None else str(deger)[:120], "neden": neden})

    def sozluk(self) -> dict:
        return {"okunan": self.okunan, "yeni": self.yeni, "degisen": self.degisen, "ayni": self.ayni, "silinecek": self.silinecek,
                "atlanan": self.atlanan, "sorunlu": self.sorunlu, "uyarilar": self.uyarilar}


# ---------------------------------------------------------------- dosya ve sayfa
def calisma_kitabi(icerik: bytes, maks_bayt: int, data_only: bool = True):
    if len(icerik) > maks_bayt:
        raise DogrulamaHatasi(f"Dosya {maks_bayt // (1024 * 1024)} MB'den büyük.")
    try:
        return load_workbook(io.BytesIO(icerik), read_only=True, data_only=data_only)
    except (zipfile.BadZipFile, InvalidFileException, KeyError, OSError):
        raise DogrulamaHatasi("Dosya geçerli bir .xlsx değil (Excel'de .xlsx olarak kaydedip yeniden deneyin).", kod="gecersiz_dosya")


def veri_sayfalari(wb) -> list[str]:
    """Şablonun 'Örnek' / 'Açıklama' / gizli kimlik sayfaları dışındakiler; yalnız bunlar varsa (ör. Örnek sayfası tek başına
    kaydedilmiş) kimlik sayfası dışındaki hepsi."""
    veri = [a for a in wb.sheetnames if baslik_anahtari(a) not in YARDIMCI_SAYFALAR]
    return veri or [a for a in wb.sheetnames if a != KIMLIK_SAYFASI]


def adli_sayfa(wb, adlar: tuple[str, ...]) -> str | None:
    """Sayfa adını esnek arar: 'HM-YM ALIŞ SATIŞ' = 'hm-ym alış satış' = 'HMYM ALIS SATIS'."""
    anahtarlar = {baslik_anahtari(a) for a in adlar}
    return next((a for a in wb.sheetnames if baslik_anahtari(a) in anahtarlar), None)


def _ilk_satirlar(ws, n: int = 30) -> list[tuple]:
    return [tuple(r) for r in ws.iter_rows(max_row=n, values_only=True)]


def _adla_eslesir(satirlar: list[tuple], t: Tanim) -> bool:
    try:
        baslik_satirini_bul(satirlar, t.alanlar, ne=t.ad)
        return True
    except DogrulamaHatasi:
        return False


def sayfa_sec(wb, t: Tanim, digerleri: list[Tanim]) -> str:
    """Adlı sayfa; yoksa tek veri sayfası; birden çoksa başlığı bu kaynağa uyan tek sayfa. Başka kaynağın sayfası tek başına gelmişse red."""
    adli = adli_sayfa(wb, t.sayfalar)
    if adli:
        return adli
    veri = veri_sayfalari(wb)
    if len(veri) == 1:
        tek = veri[0]
        baska = next((o for o in digerleri if baslik_anahtari(tek) in {baslik_anahtari(a) for a in o.sayfalar}), None)
        if baska is not None and not _adla_eslesir(_ilk_satirlar(wb[tek]), t):
            raise DogrulamaHatasi(f"Bu dosyada '{tek}' sayfası var ({baska.ad}); burası {t.ad} yüklemesi. Doğru dosyayı seçtiğinizden emin olun.",
                                  {"gelen_kaynak": baska.kimlik, "beklenen_kaynak": t.kimlik, "sayfalar": wb.sheetnames}, kod="yanlis_kaynak")
        return tek
    uyan = [a for a in veri if _adla_eslesir(_ilk_satirlar(wb[a]), t)]
    if len(uyan) == 1:
        return uyan[0]
    raise DogrulamaHatasi(f"Beklenen sayfa bulunamadı: '{t.sayfalar[0]}' ({t.ad}). Dosyadaki sayfalar: {', '.join(veri) or '(yok)'}.",
                          {"beklenen_sayfa": t.sayfalar[0], "sayfalar": veri}, kod="sayfa_yok")


# ---------------------------------------------------------------- başlık
def _yerlestir(hucreler: tuple, t: Tanim, yalniz: set[str] | None = None) -> dict[str, int]:
    """Adla eşleşen sütunlar; bir başlık birden çok sütunda geçerse bilinen yer (konum) tercih edilir, aynı sütun iki alana verilmez."""
    anahtarlar = [baslik_anahtari(h) for h in hucreler]
    kullanilan: set[int] = set()
    sonuc: dict[str, int] = {}
    # konumu adayları arasında olanlar önce yerleşsin
    for s in sorted(t.sutunlar, key=lambda s: 0 if s.konum is not None else 1):
        if yalniz is not None and s.ad not in yalniz:
            continue
        adaylar = {baslik_anahtari(a) for a in s.adlar}
        bulunan = [i for i, k in enumerate(anahtarlar) if k and k in adaylar and i not in kullanilan]
        if not bulunan:
            continue
        i = s.konum if s.konum in bulunan else bulunan[0]
        sonuc[s.ad] = i
        kullanilan.add(i)
    return sonuc


def _harf(i: int) -> str:
    return get_column_letter(i + 1)


def baslik_bul(satirlar: list[tuple], t: Tanim, digerleri: list[Tanim]) -> tuple[int, dict[str, int], list[str]]:
    """(başlık satırı 1 tabanlı, sütunlar, uyarılar). Bkz. modül açıklaması (1-4)."""
    try:
        e = baslik_satirini_bul(satirlar, t.alanlar, ne=f"{t.ad} dosyası")
        return e.satir, _yerlestir(satirlar[e.satir - 1], t), []
    except DogrulamaHatasi as hata:
        ilk_hata = hata
    # 2) başka kaynağın dosyası mı
    for o in digerleri:
        if _adla_eslesir(satirlar, o):
            raise DogrulamaHatasi(f"Bu dosya {o.ad} dosyası gibi görünüyor; burası {t.ad} yüklemesi. Doğru dosyayı seçtiğinizden emin olun.",
                                  {"gelen_kaynak": o.kimlik, "beklenen_kaynak": t.kimlik}, kod="yanlis_kaynak")
    # 3) SMM Excel düzeni: kod sütunu bilinen yerinde
    kod = t.sutun(t.kod)
    if t.yedek_konum and kod.konum is not None:
        kod_anahtarlari = {baslik_anahtari(a) for a in kod.adlar}
        for n, r in enumerate(satirlar[:8], start=1):
            if len(r) > kod.konum and baslik_anahtari(r[kod.konum]) in kod_anahtarlari:
                sutun = _yerlestir(r, t)
                eksik = [s for s in t.sutunlar if s.ad not in sutun and s.zorunlu and s.konum is None]
                if eksik:
                    break
                uyarilar = []
                for s in t.sutunlar:
                    if s.ad in sutun or s.konum is None or s.konum in sutun.values():
                        continue
                    baslik = r[s.konum] if len(r) > s.konum else None
                    if baslik is None or not str(baslik).strip():
                        continue   # o yerde başlık yok: sütun dosyada yok sayılır (zorunluysa aşağıda hata)
                    sutun[s.ad] = s.konum
                    if s.zorunlu:
                        uyarilar.append(f"'{s.gorunen}' sütunu başlık adıyla bulunamadı; SMM Excel düzenine göre {_harf(s.konum)} sütunundan okundu"
                                        f" (başlık: '{baslik}'). Değerleri kontrol edin.")
                if all(s.ad in sutun for s in t.sutunlar if s.zorunlu):
                    return n, sutun, uyarilar
                break
    raise ilk_hata


def oku(wb, t: Tanim, digerleri: list[Tanim]) -> Okunan:
    """Şablon kimliği, sayfa, başlık; başlığın altındaki boş olmayan satırlar."""
    sablon_denetle(wb, t.sablon)
    ad = sayfa_sec(wb, t, digerleri)
    ws = wb[ad]
    tum = [tuple(r) for r in ws.iter_rows(values_only=True)]
    satir, sutun, uyarilar = baslik_bul(tum[:30], t, digerleri)
    veriler = [(satir + 1 + i, r) for i, r in enumerate(tum[satir:]) if any(x not in (None, "") for x in r)]
    return Okunan(ad, satir, sutun, veriler, uyarilar)


def kod_metni(v) -> str | None:
    """Hücreden kod: baş/son boşluk atılır; 720.0 gibi tam sayı float '720' olur."""
    if v is None:
        return None
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    s = str(v).strip()
    return s or None


# ---------------------------------------------------------------- yedek için satır kopyası
def satir_json(obj, haric: tuple[str, ...] = ("id",)) -> dict:
    out = {}
    for c in obj.__table__.columns:
        if c.key in haric:
            continue
        v = getattr(obj, c.key)
        if isinstance(v, Decimal):
            v = str(v)
        elif isinstance(v, (datetime, date)):
            v = v.isoformat()
        out[c.key] = v
    return out


def satirdan(model, veri: dict):
    """satir_json'un tersi: sütun türüne göre Decimal / tarih geri çevrilir."""
    from sqlalchemy import Date, DateTime
    from ..depo.veritabani import ParaTipi
    alanlar = {}
    for c in model.__table__.columns:
        if c.key not in veri:
            continue
        v = veri[c.key]
        if v is not None:
            if isinstance(c.type, ParaTipi):
                v = Decimal(v)
            elif isinstance(c.type, DateTime):
                v = datetime.fromisoformat(v)
            elif isinstance(c.type, Date):
                v = date.fromisoformat(v)
        alanlar[c.key] = v
    return model(**alanlar)
