"""Ambalaj özeti (Excel `Ambalaj Özeti` sayfası): reçete malzeme adından ambalaj türü ve kapak; ürün sayısı ve üretim adedi."""
import re
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from fiyat_motoru.para import SIFIR
from ..depo import modeller as m
from . import hesap_servisi, recete_servisi
from .hatalar import BulunamadiHatasi

# (anahtar sözcükler, tür): ilk eşleşen kazanır; "Pet Kavanoz" hem pet hem kavanoz içerdiğinden pet önce gelir. Excel tür adları.
AMBALAJ_TURU = (
    (("pet",), "Pet Kavanoz"),
    (("kavanoz",), "Cam Kavanoz"),
    (("şişe", "sise"), "Cam Şişe"),
    (("teneke",), "Teneke Kutu"),
    (("torba", "folyo"), "Torba/Folyo"),
)
TUR_SIRASI = [t for _, t in AMBALAJ_TURU]
_KELIME = re.compile(r"[\wçğıöşü]+")


def _kucuk(ad: str) -> str:
    return ad.replace("İ", "i").replace("I", "ı").lower()


def kapak_mi(ad: str | None) -> bool:
    return bool(ad) and _kucuk(ad.strip()).startswith("kapak")


def ambalaj_turu(ad: str | None) -> str | None:
    """Malzeme adından ambalaj türü; kapaklar ve eşleşmeyenler None. Sözcük bazlı eşleşir ('Karpet' pet sayılmaz)."""
    if not ad or kapak_mi(ad):
        return None
    sozcukler = set(_KELIME.findall(_kucuk(ad)))
    for anahtarlar, tur in AMBALAJ_TURU:
        if sozcukler & set(anahtarlar):
            return tur
    return None


def ozet(s: Session, senaryo_id: int) -> dict:
    """Aktif ürünlerin aktif reçetesindeki yaprak satırlardan; ürün başına ilk ambalaj ve ilk kapak sayılır.
    Üretim adedi = ürünün üretim hedefindeki vardiya üretim adedi (toplanır)."""
    kartlar = {mz.kod: mz.ad for mz in s.scalars(select(m.Malzeme))}
    turler: dict[str, list[Decimal]] = {}
    kapaklar: dict[str, list[Decimal]] = {}
    for u in hesap_servisi.urunler(s):
        try:
            recete = recete_servisi.aktif_recete(s, u.id, senaryo_id)
            adet = hesap_servisi.uretim_hedefi_getir(s, u.id, senaryo_id).vardiya_uretim_adedi
        except BulunamadiHatasi:
            continue
        tur = kapak = None
        for x in recete.satirlar:
            if x.dugum_tipi != "yaprak":
                continue
            ad = x.ad or kartlar.get(x.malzeme_kodu)
            if kapak is None and kapak_mi(ad):
                kapak = ad.strip()
            elif tur is None:
                tur = ambalaj_turu(ad)
        for sozluk, anahtar in ((turler, tur), (kapaklar, kapak)):
            if anahtar is not None:
                g = sozluk.setdefault(anahtar, [Decimal(0), SIFIR])
                g[0] += 1; g[1] += adet
    return {"turler": [{"tur": t, "urun_sayisi": int(turler[t][0]), "uretim_adedi": turler[t][1]} for t in TUR_SIRASI if t in turler],
            "kapaklar": [{"ad": ad, "urun_sayisi": int(kapaklar[ad][0]), "uretim_adedi": kapaklar[ad][1]} for ad in sorted(kapaklar)]}
