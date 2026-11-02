"""F1: Fire oranından brüt miktar. Excel: K = I / (1 - J). Fire çarpma ile değil bölme ile eklenir."""
from decimal import Decimal
from .para import BIR, SIFIR


def brut_miktar(miktar: Decimal, fire_orani: Decimal) -> Decimal:
    if fire_orani < SIFIR or fire_orani >= BIR:
        raise ValueError(f"fire oranı [0, 1) aralığında olmalı: {fire_orani}")
    if fire_orani == SIFIR:
        return miktar
    return miktar / (BIR - fire_orani)
