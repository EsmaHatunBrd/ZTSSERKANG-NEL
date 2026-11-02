from decimal import Decimal
from fiyat_motoru.finansman import finansman_gideri, tum_finansman, doviz_maliyet
from fiyat_motoru.modeller import Parametreler
from fiyat_motoru.para import yakin

D_ = Decimal
P = Parametreler(enflasyon=D_("0.25"), kurlar={"USD": D_(50), "EUR": D_(60), "GBP": D_(68)},
                 faiz_oranlari={"TL": D_("0.4"), "USD": D_("0.06"), "EUR": D_("0.06"), "GBP": D_("0.06")},
                 stok_sureleri_ay={"TL": D_(6), "USD": D_(6), "EUR": D_(6), "GBP": D_(6)},
                 satis_kar_orani=D_("0.2"), teklif_kar_oranlari=(), vardiya_saati=D_("7.5"))
GIY = D_("31.775657799710626")   # 001!P122


def test_basit_faiz():
    assert yakin(finansman_gideri(GIY, D_("0.4"), D_(6)), D_("6.355131559942126"))   # P124
    assert yakin(finansman_gideri(GIY, D_("0.06"), D_(6)), D_("0.9532697339913188"))  # P125


def test_tum_finansman():
    f = tum_finansman(GIY, P)
    assert set(f) == {"TL", "USD", "EUR", "GBP"} and yakin(f["TL"], D_("6.355131559942126"))


def test_doviz_maliyet():
    f = tum_finansman(GIY, P)
    d = doviz_maliyet(GIY, f, P)
    assert yakin(d["USD"], D_("0.6545785506740388"))   # P131
    assert yakin(d["EUR"], D_("0.5454821255616991"))   # P132
    assert yakin(d["GBP"], D_("0.48130775784855795"))  # P133
    assert "TL" not in d


def test_faiz_stok_uyusmazligi_atlanir():
    p = Parametreler(enflasyon=D_("0.25"), kurlar={"USD": D_(50)},
                     faiz_oranlari={"TL": D_("0.4"), "USD": D_("0.06"), "EUR": D_("0.06")},
                     stok_sureleri_ay={"TL": D_(6), "GBP": D_(6)},
                     satis_kar_orani=D_("0.2"), teklif_kar_oranlari=(), vardiya_saati=D_("7.5"))
    assert set(tum_finansman(GIY, p)) == {"TL"}


def test_sifir_veya_negatif_kur_atlanir():
    p = Parametreler(enflasyon=D_("0.25"), kurlar={"USD": D_(0), "EUR": D_(-1), "GBP": D_(68)},
                     faiz_oranlari=P.faiz_oranlari, stok_sureleri_ay=P.stok_sureleri_ay,
                     satis_kar_orani=D_("0.2"), teklif_kar_oranlari=(), vardiya_saati=D_("7.5"))
    d = doviz_maliyet(GIY, tum_finansman(GIY, p), p)
    assert set(d) == {"GBP"}
