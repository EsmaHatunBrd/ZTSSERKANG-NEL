from decimal import Decimal
from fiyat_motoru.para import D, SIFIR, BIR, yakin


def test_D_float_metin_uzerinden_cevirir():
    assert D(0.1) == Decimal("0.1")          # Decimal(0.1) olsaydı 0.1000000000000000055... olurdu


def test_D_none_sifir():
    assert D(None) == SIFIR


def test_D_decimal_aynen():
    assert D(Decimal("2.5")) == Decimal("2.5")


def test_yakin_tolerans():
    assert yakin(Decimal("1.0000001"), Decimal("1.0000002"))
    assert not yakin(Decimal("1.0"), Decimal("1.001"))
    assert BIR == Decimal(1)
