"""Excel yüklemeleri için ortak yardımcılar: esnek başlık eşleme, sayı çevirme, şablon kimliği, satır kaybı denetimi.

Kural: bir yükleme hiçbir zaman sessizce veri silmez. 0 satır okunursa red; mevcut veriden belirgin biçimde az satır
gelirse kullanıcı onayı (`onay=True`) olmadan yazılmaz. Başlıklar büyük/küçük harf, Türkçe harf, boşluk ve noktalama
farkına duyarsız; bilinen eş anlamlılar tanınır.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from openpyxl.workbook.workbook import Workbook

from .hatalar import CatismaHatasi, DogrulamaHatasi
from .satis_okuyucu import BelirsizSayi, _sayi

# --- Başlık eşleme -------------------------------------------------------------------------------------------------

_TR = str.maketrans({"İ": "i", "I": "i", "ı": "i", "ü": "u", "Ü": "u", "ö": "o", "Ö": "o", "ç": "c", "Ç": "c",
                     "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g", "â": "a", "Â": "a", "î": "i", "û": "u"})


def baslik_anahtari(b) -> str:
    """`Malzeme Kodu`, `MALZEME KODU`, `malzeme_kodu`, ` Malzeme  Kodu.` → `malzemekodu`. Türkçe İ/ı dahil."""
    metin = str(b or "").translate(_TR).lower()
    return "".join(c for c in metin if c.isalnum())


@dataclass
class Alan:
    """Okuyucunun beklediği bir sütun. `adlar[0]` kullanıcıya gösterilen ad; diğerleri eş anlamlılar."""
    ad: str
    adlar: tuple[str, ...]
    zorunlu: bool = True

    @property
    def gorunen(self) -> str:
        return self.adlar[0]


@dataclass
class Eslesme:
    satir: int                      # başlık satırı (1 tabanlı)
    sutun: dict[str, int]           # alan adı → sütun sırası (0 tabanlı)
    eksik_zorunlu: list[str] = field(default_factory=list)   # görünen adlar
    eksik_istege_bagli: list[str] = field(default_factory=list)


def sutunlari_eslestir(baslik_hucreleri, alanlar: list[Alan], satir: int = 1) -> Eslesme:
    anahtarlar = [baslik_anahtari(h) for h in baslik_hucreleri]
    sutun, eksik_z, eksik_i = {}, [], []
    for a in alanlar:
        adaylar = {baslik_anahtari(x) for x in a.adlar}
        bulunan = next((i for i, k in enumerate(anahtarlar) if k and k in adaylar), None)
        if bulunan is None:
            (eksik_z if a.zorunlu else eksik_i).append(a.gorunen)
        else:
            sutun[a.ad] = bulunan
    return Eslesme(satir, sutun, eksik_z, eksik_i)


def baslik_satirini_bul(satirlar, alanlar: list[Alan], ilk_n: int = 30, ne: str = "dosya") -> Eslesme:
    """İlk `ilk_n` satırda en çok zorunlu alanı eşleyen satırı başlık sayar. Zorunlu alan eksikse anlaşılır hata verir.
    `satirlar`: hücre değerleri dizilerinin yinelenebiliri (ör. `ws.iter_rows(values_only=True)`)."""
    en_iyi: Eslesme | None = None
    for i, hucreler in enumerate(satirlar, start=1):
        if i > ilk_n:
            break
        e = sutunlari_eslestir(list(hucreler or ()), alanlar, i)
        if en_iyi is None or len(e.sutun) > len(en_iyi.sutun):
            en_iyi = e
        if not e.eksik_zorunlu:
            return e
    if en_iyi is None or not en_iyi.sutun:
        beklenen = ", ".join(a.gorunen for a in alanlar if a.zorunlu)
        raise DogrulamaHatasi(f"Bu {ne} beklenen biçimde değil: başlık satırı bulunamadı. Beklenen sütunlar: {beklenen}.",
                              alanlar={"eksik_sutunlar": [a.gorunen for a in alanlar if a.zorunlu]}, kod="baslik_yok")
    raise DogrulamaHatasi(f"Bu {ne} beklenen biçimde değil: şu sütunlar bulunamadı: {', '.join(en_iyi.eksik_zorunlu)} "
                          f"(başlık satırı {en_iyi.satir} sayıldı).",
                          alanlar={"eksik_sutunlar": en_iyi.eksik_zorunlu, "baslik_satiri": en_iyi.satir}, kod="eksik_sutun")


# --- Sayı ----------------------------------------------------------------------------------------------------------

def sayi_cevir(v, alan: str = "değer") -> tuple[Decimal | None, str | None]:
    """Hücreyi Decimal'e çevirir. Boş hücre → (None, None). Metin sayılar ('1.234,56', '%17', '17 TL') çevrilir.
    Çevrilemeyen hücre 0 SAYILMAZ: (None, hata metni) döner; çağıran satırı 'sorunlu' listeler."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return None, None
    if isinstance(v, str):
        temiz = v.strip().replace(" ", "").replace("%", "")
        for ek in ("TL", "TRY", "USD", "EUR", "₺", "$", "€"):
            temiz = temiz.replace(ek, "")
        v = temiz.strip()
    try:
        d = _sayi(v)
    except BelirsizSayi:
        return None, f"{alan}: '{v}' belirsiz sayı (binlik ayırıcıyı kaldırın ya da ondalık için virgül kullanın)"
    if d is None:
        return None, f"{alan}: '{v}' sayıya çevrilemedi"
    return d, None


# --- Şablon kimliği ------------------------------------------------------------------------------------------------

KIMLIK_SAYFASI = "_sablon"   # gizli sayfa: A1 kimlik, A2 sürüm

# Kimlik → kullanıcıya gösterilen ad. Yeni şablon eklenirse buraya bir satır eklenir.
SABLONLAR: dict[str, str] = {
    "satin_alma_fiyat_listesi": "satın alma fiyat listesi",
    "malzeme_fiyat_listesi": "malzeme fiyat listesi",
    "uretim_adetleri": "üretim adetleri",
    "gider_dagitim": "gider dağıtım",
    "urun_recetesi": "ürün reçetesi",
    "stokta_kalan": "stokta kalan",
    "satis_gecmisi": "satış geçmişi",
    "liste_fiyatlari": "liste fiyatları",
    "canias_urun_agaci": "Canias ürün ağacı",
    "smm_alim_satis": "SMM alım-satış",
    "smm_iadeler": "SMM iadeler",
    "smm_uretim": "SMM üretim",
    "smm_sayim": "SMM sayım",
    "smm_sahit_numune": "SMM şahit numune",
    "smm_gider_mizani": "SMM gider mizanı",
    "smm_stok_mizani": "SMM stok mizanı",
}


def sablon_kimligi_yaz(wb: Workbook, kimlik: str, surum: int = 1) -> None:
    """Şablon üretirken çağrılır: gizli `_sablon` sayfası en sona eklenir (okuyucuların ilk sayfası değişmez)."""
    assert kimlik in SABLONLAR, kimlik
    ws = wb[KIMLIK_SAYFASI] if KIMLIK_SAYFASI in wb.sheetnames else wb.create_sheet(KIMLIK_SAYFASI)
    ws["A1"], ws["A2"] = kimlik, surum
    ws.sheet_state = "hidden"


def sablon_kimligi_oku(wb: Workbook) -> tuple[str, int] | None:
    if KIMLIK_SAYFASI not in wb.sheetnames:
        return None
    ws = wb[KIMLIK_SAYFASI]
    kimlik, surum = ws["A1"].value, ws["A2"].value
    if not isinstance(kimlik, str) or not kimlik:
        return None
    try:
        return kimlik, int(surum or 1)
    except (TypeError, ValueError):
        return kimlik, 1


def sablon_denetle(wb: Workbook, beklenen: str | tuple[str, ...]) -> None:
    """Dosyada başka bir ekranın şablon kimliği varsa anlaşılır hatayla reddeder. Kimliksiz dosya serbest
    (kullanıcının kendi Excel'i ya da Canias çıktısı olabilir; o durumda başlık denetimi devreye girer)."""
    beklenenler = (beklenen,) if isinstance(beklenen, str) else beklenen
    k = sablon_kimligi_oku(wb)
    if k is None or k[0] in beklenenler:
        return
    gelen = SABLONLAR.get(k[0], k[0])
    burasi = SABLONLAR.get(beklenenler[0], beklenenler[0])
    raise DogrulamaHatasi(f"Bu dosya {gelen} şablonu; burası {burasi} yüklemesi. Doğru dosyayı seçtiğinizden emin olun.",
                          alanlar={"gelen_sablon": k[0], "beklenen_sablon": beklenenler[0]}, kod="yanlis_sablon")


# --- Sessiz silmeye karşı ------------------------------------------------------------------------------------------

SATIR_KAYBI_ESIGI = Decimal("0.5")   # yeni satır sayısı mevcudun yarısından azsa onay istenir


def satir_kaybi_denetle(mevcut: int, yeni: int, onay: bool, ne: str = "satır") -> None:
    """0 satır → her zaman red. Mevcut veri varken yeni dosya belirgin biçimde azsa ve `onay` yoksa 409
    (`kod="satir_kaybi_onayi"`); arayüz "N kalem silinecek, emin misiniz?" sorar ve `onay=true` ile yeniden gönderir."""
    if yeni <= 0:
        raise DogrulamaHatasi(f"Dosyada okunabilen {ne} yok; mevcut veri değiştirilmedi. Doğru sayfayı ve dosyayı seçtiğinizden emin olun.",
                              kod="bos_dosya")
    if onay or mevcut <= 0:
        return
    if Decimal(yeni) < Decimal(mevcut) * SATIR_KAYBI_ESIGI:
        raise CatismaHatasi(f"Yeni dosyada {yeni} {ne} var, mevcut veride {mevcut}. Yüklerseniz {mevcut - yeni} {ne} silinecek. Emin misiniz?",
                            alanlar={"mevcut": mevcut, "yeni": yeni, "silinecek": mevcut - yeni}, kod="satir_kaybi_onayi")
