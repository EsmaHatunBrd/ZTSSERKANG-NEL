"""Liste fiyatı kuralları (bağımlılıksız; parametre_servisi ve hesap_servisi de kullanır):
- Liste fiyatı YALNIZ Berrak markalı ürünlere uygulanır (`Urun.marka` "Berrak", büyük/küçük harf duyarsız).
- Liste fiyatı = satış fiyatı ÷ pazarın böleni (yurtiçi vars. 0,63, yurtdışı vars. 0,90), KDV hariç; sonra seçilen adıma EN YAKINA
  yuvarlanır (ROUND_HALF_UP, adımın katı; vars. 0,01 TL).
- Bölenler ve adım senaryo parametresi (tarihli): `liste_bolen_yurtici`, `liste_bolen_yurtdisi`, `liste_yuvarlama`."""
from decimal import ROUND_HALF_UP, Decimal
from .hatalar import DogrulamaHatasi

PAZARLAR = ("yurtici", "yurtdisi")
BOLEN_ANAHTARLARI = {"yurtici": "liste_bolen_yurtici", "yurtdisi": "liste_bolen_yurtdisi"}
VARSAYILAN_BOLENLER = {"yurtici": Decimal("0.63"), "yurtdisi": Decimal("0.90")}
ESKI_BOLEN_ANAHTARI = "liste_bolen"   # eski tek bölen; açılışta liste_bolen_yurtici'ye taşınır (tohum.liste_bolen_gocu)
YUVARLAMA_ANAHTARI = "liste_yuvarlama"
VARSAYILAN_YUVARLAMA = Decimal("0.01")
YUVARLAMA_SECENEKLERI = ("0.01", "0.05", "0.10", "0.25", "0.50", "1", "5")
BERRAK = "Berrak"


def pazar_dogrula(pazar: str | None) -> str:
    p = (pazar or "yurtici").strip()
    if p not in PAZARLAR:
        raise DogrulamaHatasi("Pazar Yurtiçi ya da Yurtdışı olmalı.", {"pazar": pazar})
    return p


def bolen_dogrula(b) -> Decimal:
    try:
        b = Decimal(str(b))
    except ArithmeticError:
        raise DogrulamaHatasi("Bölen bir sayı olmalı (ör. 0,63).", {"bolen": str(b)}) from None
    if not b.is_finite() or not (Decimal(0) < b <= Decimal(1)):
        raise DogrulamaHatasi(f"Bölen 0'dan büyük ve en fazla 1 olmalı (ör. 0,63); girilen değer {str(b).replace('.', ',')}.", {"bolen": str(b)})
    return b


def yuvarlama_dogrula(adim) -> Decimal:
    """Adım izinli kümeden olmalı; dönüş kümedeki kanonik yazımla (0.1 -> 0.10)."""
    try:
        a = Decimal(str(adim))
    except ArithmeticError:
        a = None
    for sec in YUVARLAMA_SECENEKLERI:
        if a is not None and a.is_finite() and a == Decimal(sec):
            return Decimal(sec)
    raise DogrulamaHatasi("Yuvarlama adımı şunlardan biri olmalı: " + ", ".join(s.replace(".", ",") for s in YUVARLAMA_SECENEKLERI) + ".",
                          {"yuvarlama": str(adim)})


def yuvarla(x: Decimal | None, adim: Decimal) -> Decimal | None:
    """En yakın adım katına (yarım yukarı): adım 0,05 -> 12,37 = 12,35; 12,375 = 12,40. Sonuç adımın basamak sayısıyla."""
    if x is None:
        return None
    return ((x / adim).quantize(Decimal(1), rounding=ROUND_HALF_UP) * adim).quantize(adim)


def liste_fiyati(satis: Decimal | None, bolen: Decimal, adim: Decimal) -> tuple[Decimal | None, Decimal | None]:
    """(ham, yuvarlanmış): ham = satış ÷ bölen."""
    if satis is None:
        return None, None
    ham = Decimal(satis) / bolen
    return ham, yuvarla(ham, adim)


def _kucuk(metin: str) -> str:
    return metin.replace("İ", "i").replace("I", "ı").casefold()


def berrak_mi(marka: str | None) -> bool:
    return bool(marka) and _kucuk(marka.strip()) == _kucuk(BERRAK)


def marka_turet(ad: str | None) -> str | None:
    """Ürün adında "berrak" geçiyorsa "Berrak"; değilse None (marka bilinmiyor)."""
    return BERRAK if ad and _kucuk(BERRAK) in _kucuk(ad) else None


def marka_normalle(marka: str | None) -> str:
    """Kullanıcının yazdığı marka: boşluklar kırpılır; boş metin "" (bilerek boş bırakıldı; açılış göçü dokunmaz).
    Berrak'ın yazımı kanonikleşir ("BERRAK" -> "Berrak")."""
    m = (marka or "").strip()
    if len(m) > 64:
        raise DogrulamaHatasi("Marka en fazla 64 karakter olabilir.", {"marka": m[:64]})
    return BERRAK if berrak_mi(m) else m
