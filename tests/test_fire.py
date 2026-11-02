from decimal import Decimal
import pytest
from fiyat_motoru.fire import brut_miktar
from fiyat_motoru.para import yakin


def test_fire_bolme_ile_eklenir():
    # Excel 001!K8: 0.08333333/(1-0.02) = 0.08503401020408163
    assert yakin(brut_miktar(Decimal("0.08333333"), Decimal("0.02")), Decimal("0.08503401020408163"))


def test_fire_sifir_miktar_aynen():
    assert brut_miktar(Decimal("0.19531875"), Decimal(0)) == Decimal("0.19531875")


def test_fire_yuzde_yuz_hata():
    with pytest.raises(ValueError):
        brut_miktar(Decimal(1), Decimal(1))


def test_fire_negatif_hata():
    with pytest.raises(ValueError):
        brut_miktar(Decimal(1), Decimal("-0.1"))
