from decimal import Decimal
from fiyat_motoru.fiyat import satis_fiyati, teklifler, suzme_kg_fiyati, yuzdeleri_doldur
from fiyat_motoru.modeller import MaliyetSatiri
from fiyat_motoru.para import yakin, SIFIR

D_ = Decimal


def test_satis_fiyati():
    assert yakin(satis_fiyati(D_("38.13078935965275"), D_("0.2")), D_("45.756947231583304"))  # P137


def test_teklifler_usd():
    t = teklifler(D_("0.6545785506740388"), (D_("0.2"), D_("0.17"), D_("0.14")))
    assert [str(round(x, 10)) for x in t] == ["0.7854942608", "0.7658569043", "0.7462195478"]  # P145-147


def test_suzme():
    assert yakin(suzme_kg_fiyati(D_("45.756947231583304"), D_("0.18")), D_("254.20526239768503"))  # P143
    assert suzme_kg_fiyati(D_(10), SIFIR) == SIFIR


def test_yuzdeler_yurtici():
    s = MaliyetSatiri(kalem="k", grup="malzeme", miktar=D_(1), brut_miktar=D_(1), birim_fiyat=D_(1),
                      tutar=D_("7.525510204081633"))   # 001!P13 kavanoz
    yuzdeleri_doldur([s], "Yurtiçi", D_("38.13078935965275"), D_("45.756947231583304"), D_(50), SIFIR, SIFIR)
    assert yakin(s.maliyet_yuzdesi, D_("0.19736046199045082")) and yakin(s.fiyat_yuzdesi, D_("0.164467051658709"))


def test_yuzdeler_yurtdisi():
    s = MaliyetSatiri(kalem="k", grup="malzeme", miktar=D_(1), brut_miktar=D_(1), birim_fiyat=D_(1), tutar=D_(50))
    yuzdeleri_doldur([s], "Yurtdışı", SIFIR, SIFIR, D_(50), D_(2), D_(4))
    assert s.maliyet_yuzdesi == D_("0.5") and s.fiyat_yuzdesi == D_("0.25")
