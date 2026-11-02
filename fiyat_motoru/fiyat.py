"""F11/F12/F13: Satış fiyatı, teklif turları, kalem yüzdeleri, süzme kg fiyatı. Excel 001!P137:P147, R/S sütunları."""
from decimal import Decimal
from .modeller import MaliyetSatiri
from .para import BIR, SIFIR


def satis_fiyati(maliyet: Decimal, kar_orani: Decimal) -> Decimal:
    return maliyet * (BIR + kar_orani)


def teklifler(doviz_maliyet: Decimal, kar_oranlari) -> list[Decimal]:
    return [doviz_maliyet * (BIR + k) for k in kar_oranlari]


def suzme_kg_fiyati(satis_tl: Decimal, suzme_kg: Decimal) -> Decimal:
    return SIFIR if suzme_kg == SIFIR else satis_tl / suzme_kg


def _bol(a: Decimal, b: Decimal) -> Decimal:
    return SIFIR if b == SIFIR else a / b


def yuzdeleri_doldur(satirlar: list[MaliyetSatiri], pazar: str, maliyet_tl: Decimal, satis_tl: Decimal,
                     kur_usd: Decimal, maliyet_usd: Decimal, satis_usd: Decimal) -> None:
    for s in satirlar:
        if pazar == "Yurtdışı":
            usd = _bol(s.tutar, kur_usd)
            s.maliyet_yuzdesi = _bol(usd, maliyet_usd)
            s.fiyat_yuzdesi = _bol(usd, satis_usd)
        else:
            s.maliyet_yuzdesi = _bol(s.tutar, maliyet_tl)
            s.fiyat_yuzdesi = _bol(s.tutar, satis_tl)
