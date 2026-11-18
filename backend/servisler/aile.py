"""Ürün ailesi: aynı ürünün farklı ambalajlarını (370 ml / 720 ml / 2,5 kg ...) tek adla toplar."""
import re
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..depo import modeller as m
from .hatalar import BulunamadiHatasi, DogrulamaHatasi

def _casefold_tr(ad: str) -> str:
    """Eşleştirme anahtarı için katlama: İ, I ve ı hepsi 'i' olur ('ZEYTIN', 'Zeytin', 'zeytın' aynı aileye düşer)."""
    return ad.replace("İ", "i").replace("I", "i").replace("ı", "i").casefold()


# Hacim/ağırlık: 370 ml, 2,5 kg, 5lt, 1062 ml ...
_HACIM = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:ml|cl|lt|l|kg|gr|g)\b")
_ORAN = re.compile(r"\b\d+\s*/\s*\d+\b")          # 3/1, 5/1
_KOD = re.compile(r"\b[a-zçğıöşü]\d{1,2}\b")      # A9
# Ambalaj ve marka/seri sözcükleri (casefold sonrası)
_SOZCUKLER = {_casefold_tr(w) for w in ("pet", "cam", "teneke", "torba", "kavanoz", "şişe", "kutu", "folyo", "fıçı", "boğumlu", "berrak", "tr")}
MAKS_UZUNLUK = 120
_ETIKET = re.compile(r"(\d+(?:[,.]\d+)?)\s*(ml|lt|l|kg|gr|g)\b", re.IGNORECASE)
_BINLI = {"lt", "l", "kg"}   # ml/gr/g x1, lt/l/kg x1000


def _etiket_bul(ad: str) -> tuple[str, str] | None:
    e = _ETIKET.search(ad or "")
    return (e.group(1), e.group(2).lower()) if e else None


def ambalaj_etiket(ad: str) -> str | None:
    """Ürün adındaki boyut ifadesi, normalize: "5lt" -> "5 lt", "370 ML" -> "370 ml", "2,5 kg" -> "2,5 kg"; yoksa None.
    Yalnız gösterim içindir; `Urun.ambalaj_hacmi` (Excel 'Ambalaj' hücresi) değişmez."""
    b = _etiket_bul(ad)
    return f"{b[0]} {b[1]}" if b else None


def ambalaj_ml(ad: str, hacim) -> Decimal:
    """Sıralama için ml/g eşdeğeri. Etiket varsa ondan (lt/l/kg x1000); yoksa hacim >= 50 ise hacim, < 50 ise hacim x1000."""
    b = _etiket_bul(ad)
    if b:
        return Decimal(b[0].replace(",", ".")) * (1000 if b[1] in _BINLI else 1)
    h = Decimal(str(hacim))
    return h if h >= 50 else h * 1000


def _kucuk_tr(ad: str) -> str:
    """Gösterim için Türkçe küçük harf: İ -> i, I -> ı (katlama yok)."""
    return ad.replace("İ", "i").replace("I", "ı").lower()


def aile_ad_turet(ad: str) -> str:
    """Aile görünen adı: `aile_turet` ile aynı temizlik, ama ı/i korunur (KARIŞIK -> karışık). Sonuç boşsa adın kendisi."""
    ham = _kucuk_tr((ad or "").strip())
    t = _ORAN.sub(" ", _HACIM.sub(" ", ham))
    t = _KOD.sub(" ", t)
    kalan = [k for k in t.split() if _casefold_tr(k) not in _SOZCUKLER]
    sonuc = " ".join(kalan).strip()
    return (sonuc or " ".join(ham.split()))[:MAKS_UZUNLUK]


_BIRIMLER = {"ml", "cl", "lt", "l", "kg", "gr", "g"}


def _baslik_tr(ad: str) -> str:
    """Gösterim için Türkçe baş harf büyük: 'karışık turşu' -> 'Karışık Turşu', 'izmir' -> 'İzmir', 'ılık' -> 'Ilık'.
    Birim sözcükleri (ml, kg ...) ve harfle başlamayan parçalar olduğu gibi kalır."""
    def _kelime(k: str) -> str:
        if not k or not k[0].isalpha() or k in _BIRIMLER:
            return k
        ilk = {"i": "İ", "ı": "I"}.get(k[0], k[0].upper())
        return ilk + k[1:]
    return " ".join(_kelime(k) for k in ad.split(" "))


def aile_turet(ad: str) -> str:
    """Eşleştirme/gruplama anahtarı: görünen adın ı/i katlanmış hali (ZEYTIN, Zeytin, zeytın aynı aileye düşer)."""
    return _casefold_tr(aile_ad_turet(ad))[:MAKS_UZUNLUK]


def aile_anahtari(ad: str) -> str:
    """Elle yazılan görünen addan gruplama anahtarı: fazla boşluk atılır, ı/i katlanmış küçük harf (ambalaj sözcükleri ayıklanmaz;
    kullanıcı ne yazdıysa odur). 'Karışık Turşu' -> 'karişik turşu' = addan türeyen ailelerle aynı anahtar."""
    return _casefold_tr(" ".join((ad or "").split()))[:MAKS_UZUNLUK]


def aile_gorunen_ad(anahtar: str, urunler) -> str:
    """Görünen ad: `urunler` içinde elle yazılmış ilk `aile_ad` varsa o; yoksa anahtarı üreten ilk ürünün adından; o da yoksa anahtarın kendisi.
    Ürün ucu yalnız ürünün kendisiyle çağırır (başka üyenin elle adı orada görünmez); Karşılaştırma grubun tüm üyeleriyle çağırır."""
    for u in urunler:
        if u.aile == anahtar and getattr(u, "aile_ad", None):
            return u.aile_ad
    for u in urunler:
        if aile_turet(u.ad) == anahtar:
            return _baslik_tr(aile_ad_turet(u.ad))
    return anahtar


def aileleri_doldur(s: Session) -> int:
    """Boş `aile` alanlarını addan türetir (idempotent). Dönüş: doldurulan ürün sayısı. Commit çağıranın işidir."""
    n = 0
    for u in s.scalars(select(m.Urun).where(m.Urun.aile.is_(None))):
        u.aile = aile_turet(u.ad); n += 1
    s.flush()
    return n


def aile_degistir(s: Session, kod: str, aile: str | None, kullanici: str = "sistem") -> m.Urun:
    """`aile` görünen addır: kullanıcı yazar, anahtar `aile_anahtari` ile türetilir ve ad `aile_ad`a saklanır.
    aile=None (veya boş): addan yeniden türet, elle ad kalkar. Değişiklik DegisiklikKaydi'na yazılır."""
    u = s.scalar(select(m.Urun).where(m.Urun.kod == kod))
    if u is None:
        raise BulunamadiHatasi(f"{kod} kodlu ürün bulunamadı.", {"kod": kod})
    ad = " ".join((aile or "").split())
    if len(ad) > MAKS_UZUNLUK:
        raise DogrulamaHatasi(f"Aile adı en fazla {MAKS_UZUNLUK} karakter olabilir.", {"aile": aile})
    yeni, yeni_ad = (aile_anahtari(ad), ad) if ad else (aile_turet(u.ad), None)
    if yeni_ad is not None and yeni == u.aile and u.aile_ad is None and yeni_ad in (aile_gorunen_ad(u.aile, [u]), aile_ad_turet(u.ad)):
        return u   # türetilen ad değiştirilmeden kaydedildi: yazım ve günlük kaydı yok
    if (u.aile, u.aile_ad) != (yeni, yeni_ad):
        s.add(m.DegisiklikKaydi(tablo="urun", kayit_id=u.id, islem="aile_degistir", eski={"aile": u.aile, "aile_ad": u.aile_ad},
                                yeni={"aile": yeni, "aile_ad": yeni_ad}, kullanici=kullanici))
        u.aile, u.aile_ad = yeni, yeni_ad
        s.flush()
    return u
