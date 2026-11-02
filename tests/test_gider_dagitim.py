import pytest
from dataclasses import replace
from decimal import Decimal
from fiyat_motoru.gider_dagitim import oranlari_hesapla, anahtar
from fiyat_motoru.modeller import GiderHavuzlari, AmbalajSinifi
from fiyat_motoru.para import yakin

D_ = Decimal


def havuz():
    return GiderHavuzlari(
        dolum_iscilik_toplam=D_("86037707.86667047"), dolum_iscilik_saniye=D_(442154500),
        mal_kabul_iscilik_toplam=D_("32065211.4127488"),
        mal_kabul_paylari={"Taze/Taze": (D_("0.25"), D_(6000000)), "Taze/Turşu": (D_("0.65"), D_(7000000)), "Turşu/Turşu": (D_("0.1"), D_(3500000))},
        etiket_iscilik_toplam=D_("18533808.031511273"), etiket_iscilik_saniye=D_(132435000),
        endirekt_iscilik_toplam=D_("42088882.57323751"), endirekt_saniye=D_(32547902),
        mal_kabul_gug_toplam=D_(21000000),
        mal_kabul_gug_paylari={"Taze/Taze": (D_("0.25"), D_(6000000)), "Taze/Turşu": (D_("0.65"), D_(7000000)), "Turşu/Turşu": (D_("0.1"), D_(3500000))},
        diger_gug_toplam=D_("25281257.75"), diger_gug_saniye=D_(32547902),
        elektrik_toplam=D_(14112000), elektrik_hatlar={"Niko": (D_("0.376"), D_(8193712))},
        dogalgaz_toplam=D_(22464000), dogalgaz_hatlar={"Niko": (D_("0.46"), D_(8193712))},
        amortisman_toplam=D_(49056000), amortisman_hatlar={"Niko": (D_("0.43"), D_(8193712))},
        yonetim_toplam=D_("26274982.5"), pazarlama_toplam=D_(16848000),
        ambalajlar=(AmbalajSinifi("370 ml kavanoz", D_(370), D_(5690071), D_("0.5")),
                    AmbalajSinifi("720 ml kavanoz", D_(720), D_(11896020), D_("0.75"))),
    )


def test_saniye_bazli():
    o = oranlari_hesapla(havuz())
    assert yakin(o.dolum_iscilik_sn, D_("0.19458743011022273"))     # G4
    assert yakin(o.etiket_iscilik_sn, D_("0.13994644943943274"))    # G13
    assert yakin(o.endirekt_iscilik_sn, D_("1.2931365767672984"))   # G18
    assert yakin(o.diger_gug_sn, D_("0.7767400107693577"))          # G27


def test_kg_bazli_mal_kabul_anahtar_casefold():
    o = oranlari_hesapla(havuz())
    assert yakin(o.mal_kabul_iscilik_kg[anahtar("Turşu/turşu")], D_("0.9161488975071086"))  # F9
    assert yakin(o.mal_kabul_gug_kg[anahtar("TAZE/TAZE")], D_("0.875"))                    # F21


def test_hat_bazli():
    o = oranlari_hesapla(havuz())
    assert yakin(o.elektrik_sn[anahtar("Niko")], D_("0.6475834151847173"))     # F30
    assert yakin(o.dogalgaz_sn[anahtar("Niko")], D_("1.26114269088296"))       # F41
    assert yakin(o.amortisman_sn[anahtar("Niko")], D_("2.574422923334381"))    # F52


def test_ambalaj_dagitimi():
    # Gerçek Excel'de 22 ambalaj var; iki ambalajla formülün şekli test edilir:
    # paz/adet = 16848000 / (5690071*0.5 + 11896020*0.75) * katsayı
    o = oranlari_hesapla(havuz())
    payda = D_(5690071) * D_("0.5") + D_(11896020) * D_("0.75")
    assert yakin(o.pazarlama_adet[D_(370)], D_(16848000) / payda * D_("0.5"))
    assert yakin(o.yonetim_adet[D_(720)], D_("26274982.5") / payda * D_("0.75"))


def test_tekrarlanan_anahtar_hata_verir():
    h = havuz()
    h2 = replace(h, elektrik_hatlar={"Niko": (D_("0.3"), D_(100)), " NIKO ": (D_("0.2"), D_(100))})
    with pytest.raises(ValueError, match="dağıtım anahtarı tekrarı: niko"):
        oranlari_hesapla(h2)


def test_tekrarlanan_ambalaj_hacmi_hata_verir():
    h = havuz()
    h2 = replace(h, ambalajlar=h.ambalajlar + (AmbalajSinifi("370 ml diğer", D_(370), D_(1), D_(1)),))
    with pytest.raises(ValueError, match="hacim"):
        oranlari_hesapla(h2)
