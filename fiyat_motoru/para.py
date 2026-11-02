"""Para ve oran değerleri için Decimal yardımcıları."""
from decimal import Decimal

SIFIR = Decimal(0)
BIR = Decimal(1)
TOLERANS = Decimal("0.000001")


def D(x) -> Decimal:
    """Her türlü sayıyı Decimal'e çevirir. float, str üzerinden geçer ki 0.1 -> 0.1 kalsın."""
    if x is None or x == "":
        return SIFIR
    if isinstance(x, Decimal):
        return x
    if isinstance(x, bool):
        raise TypeError("bool para değeri olamaz")
    return Decimal(str(x))


def yakin(a: Decimal, b: Decimal, tol: Decimal = TOLERANS) -> bool:
    return abs(D(a) - D(b)) < tol
