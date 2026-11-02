from decimal import Decimal
from fiyat_motoru.malzeme import malzeme_tutari, malzeme_toplami
from fiyat_motoru.modeller import Malzeme, ReceteSatiri, Parametreler
from fiyat_motoru.para import yakin, SIFIR

P = Parametreler(enflasyon=Decimal("0.25"),
                 kurlar={"USD": Decimal(50), "EUR": Decimal(60), "GBP": Decimal(68), "CHF": Decimal(50) / Decimal("0.79")},
                 faiz_oranlari={"TL": Decimal("0.4")}, stok_sureleri_ay={"TL": Decimal(6)},
                 satis_kar_orani=Decimal("0.2"), teklif_kar_oranlari=(Decimal("0.2"),), vardiya_saati=Decimal("7.5"))


def satir(miktar, fire=SIFIR):
    return ReceteSatiri(malzeme_kodu="k", ad="a", miktar=Decimal(miktar), fire_orani=Decimal(fire), birim="AD")


def malz(fiyat, para, zs):
    return Malzeme(kod="k", ad="a", tip=None, birim="AD", para_birimi=para, fiyat=Decimal(fiyat), zs=zs)


def test_s_tl_enflasyon_uygulanir():
    # 001!P13: kavanoz 5.9 TL, fire 0.02 -> (5.9+5.9*0.25)*1.0204081632653061 = 7.525510204081633
    s, uyari = malzeme_tutari(satir(1, "0.02"), malz("5.9", "TL", "S"), P)
    assert yakin(s.tutar, Decimal("7.525510204081633")) and uyari is None


def test_s_eur_kur_enflasyon_yok():
    # 001!P10: etiket 0.049 EUR * 60 * 1.0204081632653061 = 3.0
    s, _ = malzeme_tutari(satir(1, "0.02"), malz("0.049", "EUR", "S"), P)
    assert yakin(s.tutar, Decimal("3"))


def test_s_usd():
    # 001!P9: shrink 1.95 USD * 50 * (0.00125/0.98) = 0.12436224489795919
    s, _ = malzeme_tutari(satir("0.00125", "0.02"), malz("1.95", "USD", "S"), P)
    assert yakin(s.tutar, Decimal("0.12436224489795919"))


def test_z_fiyat_aynen():
    # 001!P17: taze biberiye 65 TL, Z -> 0.19013459*65 = 12.35874835
    s, _ = malzeme_tutari(satir("0.19013459"), malz("65", "TL", "Z"), P)
    assert yakin(s.tutar, Decimal("12.35874835"))


def test_malzeme_bulunamadi_sifir_ve_uyari():
    s, uyari = malzeme_tutari(satir(1), None, P)
    assert s.tutar == SIFIR and "fiyat" in uyari.lower()


def test_s_bilinmeyen_para_sifir_ve_uyari():
    s, uyari = malzeme_tutari(satir(1), malz("10", "RUB", "S"), P)
    assert s.tutar == SIFIR and uyari is not None


def test_toplam():
    s1, _ = malzeme_tutari(satir(1, "0.02"), malz("5.9", "TL", "S"), P)
    s2, _ = malzeme_tutari(satir(1, "0.02"), malz("0.049", "EUR", "S"), P)
    assert yakin(malzeme_toplami([s1, s2]), Decimal("10.525510204081633"))


def test_s_doviz_kuru_yoksa_sifir_ve_uyari():
    s, uyari = malzeme_tutari(satir(1), malz("10", "CHF", "S"),
                              Parametreler(enflasyon=P.enflasyon, kurlar={"USD": Decimal(50)},
                                           faiz_oranlari=P.faiz_oranlari, stok_sureleri_ay=P.stok_sureleri_ay,
                                           satis_kar_orani=P.satis_kar_orani, teklif_kar_oranlari=P.teklif_kar_oranlari,
                                           vardiya_saati=P.vardiya_saati))
    assert s.tutar == SIFIR and "kur" in uyari.lower()


def test_kucuk_harf_ve_bosluk_normallesir():
    m = Malzeme(kod=" k ", ad="a", tip=" t ", birim=" ad ", para_birimi=" tl ", fiyat=Decimal("5.9"), zs="s")
    assert (m.kod, m.zs, m.para_birimi, m.tip, m.birim) == ("k", "S", "TL", "t", "ad")
    s, uyari = malzeme_tutari(satir(1, "0.02"), m, P)
    assert yakin(s.tutar, Decimal("7.525510204081633")) and uyari is None


def test_zs_tanimsiz_uyari():
    s, uyari = malzeme_tutari(satir(1), malz("10", "TL", "X"), P)
    assert s.tutar == Decimal(10) and "Z/S" in uyari and "tanımsız" in uyari


def test_z_dovizli_kur_uygulanmaz_ama_uyarir():
    # Excel paritesi: Ziraat (Z) malzemede brüt * fiyat, kur yok; muhasebe (23.10.2026): Z'ye enflasyon/kur uygulanmaz, yine de uyar
    s, uyari = malzeme_tutari(satir(2), malz("10", "USD", "Z"), P)
    assert s.tutar == Decimal(20)
    assert "Ziraat kaynaklı ama döviz fiyatlı (USD)" in uyari and "kur uygulanmaz" in uyari


def test_ara_mamul_fiyatsiz_uyarmaz_ama_yaprak_uyarir():
    ara = ReceteSatiri(malzeme_kodu="k", ad="a", miktar=Decimal(1), fire_orani=SIFIR, birim="AD", dugum_tipi="ara_mamul")
    s, uyari = malzeme_tutari(ara, None, P)
    assert s.tutar == SIFIR and uyari is None
    s, uyari = malzeme_tutari(ara, malz("0", "TL", "S"), P)
    assert s.tutar == SIFIR and uyari is None
    assert malzeme_tutari(satir(1), None, P)[1] is not None


def test_alt_satiri_olan_fiyatsiz_uyarmaz_elle_fiyat_yine_uygulanir():
    """Uyarı sadeleştirme: altında daha derin satırlar olan (maliyeti alt satırlardan gelen) satır fiyat listesinde yoksa
    uyarı vermez; yaprak satır uyarmaya devam eder. Elle fiyat yazılırsa yine kullanılır (001 (2) gibi hazır alım)."""
    ust = ReceteSatiri(malzeme_kodu="02.x", ad="ara", miktar=Decimal(1), fire_orani=SIFIR, birim="AD", alt_satiri_var=True)
    s, uyari = malzeme_tutari(ust, None, P)
    assert s.tutar == SIFIR and uyari is None
    s, uyari = malzeme_tutari(ust, malz("0", "TL", "S"), P)
    assert uyari is None   # listede 0 fiyatlı da olsa 'birim fiyatı 0' denmez
    elle = ReceteSatiri(malzeme_kodu="02.x", ad="ara", miktar=Decimal(2), fire_orani=SIFIR, birim="AD", alt_satiri_var=True,
                        birim_fiyat_elle=Decimal("49.5"))
    s, uyari = malzeme_tutari(elle, None, P)
    assert s.tutar == Decimal("99.0") and uyari is None
    yaprak = ReceteSatiri(malzeme_kodu="16.x", ad="turşu", miktar=Decimal(1), fire_orani=SIFIR, birim="KG")
    _, uyari = malzeme_tutari(yaprak, None, P)
    assert uyari == "16.x (turşu): fiyat listesinde yok, 0 TL alındı"
