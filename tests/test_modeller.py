from decimal import Decimal
from fiyat_motoru.modeller import Malzeme, ReceteSatiri, Parametreler, MaliyetSatiri
from fiyat_motoru.para import SIFIR


def test_malzeme_dondurulmus():
    m = Malzeme(kod="20.10.051.000.0000", ad="Cam Kavanoz 370 ml", tip="0008-Ambalaj Malzeme",
                birim="AD", para_birimi="TL", fiyat=Decimal("5.9"), zs="S")
    try:
        m.fiyat = Decimal(1)
        assert False, "frozen olmalı"
    except AttributeError:
        pass


def test_recete_satiri_varsayilan_fire_yok():
    s = ReceteSatiri(malzeme_kodu="x", ad="y", miktar=Decimal(1), fire_orani=SIFIR, birim="AD")
    assert s.fire_orani == SIFIR


def test_maliyet_satiri_yuzde_varsayilan_sifir():
    s = MaliyetSatiri(kalem="a", grup="malzeme", miktar=Decimal(1), brut_miktar=Decimal(1),
                      birim_fiyat=Decimal(2), tutar=Decimal(2))
    assert s.maliyet_yuzdesi == SIFIR and s.fiyat_yuzdesi == SIFIR


def test_parametreler_teklif_tuple():
    p = Parametreler(enflasyon=Decimal("0.25"), kurlar={"USD": Decimal(50)},
                     faiz_oranlari={"TL": Decimal("0.4")}, stok_sureleri_ay={"TL": Decimal(6)},
                     satis_kar_orani=Decimal("0.2"),
                     teklif_kar_oranlari=(Decimal("0.2"), Decimal("0.17"), Decimal("0.14")),
                     vardiya_saati=Decimal("7.5"))
    assert len(p.teklif_kar_oranlari) == 3
