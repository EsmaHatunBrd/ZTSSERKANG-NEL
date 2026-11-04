from decimal import Decimal
from fiyat_motoru.uretim_gideri import direkt_iscilik, genel_uretim, diger_giderler, adet_basina_saniye
from fiyat_motoru.modeller import GiderOranlari, UretimBilgisi, Parametreler
from fiyat_motoru.para import yakin, SIFIR

D_ = Decimal
P = Parametreler(enflasyon=D_("0.25"), kurlar={}, faiz_oranlari={}, stok_sureleri_ay={}, satis_kar_orani=D_("0.2"),
                 teklif_kar_oranlari=(), vardiya_saati=D_("7.5"))
O = GiderOranlari(dolum_iscilik_sn=D_("0.19458743011022273"), etiket_iscilik_sn=D_("0.13994644943943274"),
                  endirekt_iscilik_sn=D_("1.2931365767672984"), diger_gug_sn=D_("0.7767400107693577"),
                  mal_kabul_iscilik_kg={"turşu/turşu": D_("0.9161488975071086")},
                  mal_kabul_gug_kg={"turşu/turşu": D_("0.6")},
                  elektrik_sn={"niko": D_("0.6475834151847173")}, dogalgaz_sn={"niko": D_("1.26114269088296")},
                  amortisman_sn={"niko": D_("2.574422923334381")},
                  pazarlama_adet={D_(370): D_("0.5048087845717276")}, yonetim_adet={D_(370): D_("0.7872650748141269")})
U = UretimBilgisi(pazar="Yurtiçi", vardiya_uretim_adedi=D_(65000), dolum_personel=D_(13), etiketleme_adedi=D_(35000),
                  etiket_personel=D_(7), hat="Niko", taze_tursu_sinifi="Turşu/Turşu", ambalaj_hacmi=D_(370),
                  suzme_kg=D_("0.18"), mal_kabul_miktar_kg=D_("0.19013459"), mal_kabul_fire=SIFIR, pazarlama_yonetim_uygula=True)


def test_adet_basina_saniye():
    assert yakin(adet_basina_saniye(U, P), D_("0.4153846153846154"))  # 27000/65000


def test_direkt_iscilik_001():
    satirlar, uyarilar = direkt_iscilik(U, O, P)
    t = {s.kalem: s.tutar for s in satirlar}
    assert yakin(t["Mal Kabul ve Fermantasyon Giderleri"], D_("0.1741915950064661"))  # P104
    assert yakin(t["Dolum Doğrudan İşçilik Giderleri"], D_("1.0507721225952027"))     # P105
    assert yakin(t["Etiketleme İşçilik Giderleri"], D_("0.7557108269729369"))         # P106
    assert yakin(sum(s.tutar for s in satirlar), D_("1.9806745445746057")) and uyarilar == []


def test_etiketleme_adedi_sifir_ise_sifir():
    u = UretimBilgisi(**{**U.__dict__, "etiketleme_adedi": SIFIR})
    satirlar, _ = direkt_iscilik(u, O, P)
    assert {s.kalem: s.tutar for s in satirlar}["Etiketleme İşçilik Giderleri"] == SIFIR


def test_genel_uretim_001():
    satirlar, uyarilar = genel_uretim(U, O, P)
    t = {s.kalem: s.tutar for s in satirlar}
    assert yakin(t["Endirekt İşçilik Giderleri"], D_("0.5371490395802625"))                      # P108
    assert yakin(t["Mal Kabul ve Fermantasyon Genel Üretim Giderleri"], D_("0.11408075399999999"))  # P109
    assert yakin(t["Elektrik Giderleri"], D_("0.2689961878459595"))                               # P110
    assert yakin(t["Doğalgaz Giderleri"], D_("0.5238592715975372"))                               # P111
    assert yakin(t["Amortisman Giderleri"], D_("1.069375675846589"))                              # P112
    assert yakin(t["Diğer Genel Üretim Giderleri"], D_("0.3226458506272717"))                     # P113
    assert yakin(sum(s.tutar for s in satirlar), D_("2.83610677949762")) and uyarilar == []


def test_hat_bulunamazsa_sifir_ve_uyari():
    u = UretimBilgisi(**{**U.__dict__, "hat": "Yok"})
    satirlar, uyarilar = genel_uretim(u, O, P)
    assert {s.kalem: s.tutar for s in satirlar}["Elektrik Giderleri"] == SIFIR and any("hat" in w.lower() for w in uyarilar)


def test_diger_giderler_001():
    satirlar, _ = diger_giderler(U, O)
    t = {s.kalem: s.tutar for s in satirlar}
    assert yakin(t["Pazarlama Satış Giderleri"], D_("0.5048087845717276"))
    assert yakin(t["Genel Yönetim Giderleri"], D_("0.7872650748141269"))


def test_diger_giderler_kapali():
    u = UretimBilgisi(**{**U.__dict__, "pazarlama_yonetim_uygula": False})
    satirlar, _ = diger_giderler(u, O)
    assert all(s.tutar == SIFIR for s in satirlar)


def test_vardiya_adedi_sifir_uyarir():
    u = UretimBilgisi(**{**U.__dict__, "vardiya_uretim_adedi": SIFIR})
    for f in (direkt_iscilik, genel_uretim):
        satirlar, uyarilar = f(u, O, P)
        assert "vardiya üretim adedi 0, saniye bazlı giderler 0 alındı" in uyarilar
        assert uyarilar.count("vardiya üretim adedi 0, saniye bazlı giderler 0 alındı") == 1


def test_elle_hucre_formulun_yerine_gecer_ve_excel_gibi_akar():
    """Excel I/K/M/P: elle miktar brüte ve tutara akar (K = I x personel), elle fiyat tutara akar, elle tutar her şeyi ezer."""
    from fiyat_motoru.modeller import GiderElle
    elle = {"dolum_iscilik": GiderElle(miktar=D_(1)), "endirekt_iscilik": GiderElle(birim_fiyat=SIFIR),
            "etiket_iscilik": GiderElle(brut_miktar=SIFIR), "diger_gug": GiderElle(tutar=D_(10))}
    di, _ = direkt_iscilik(U, O, P, elle)
    gug, _ = genel_uretim(U, O, P, elle)
    t = {s.kod: s for s in di + gug}
    assert t["dolum_iscilik"].brut_miktar == D_(13) and yakin(t["dolum_iscilik"].tutar, 13 * O.dolum_iscilik_sn)
    assert t["dolum_iscilik"].elle_alanlar == ("miktar",)
    assert t["endirekt_iscilik"].tutar == SIFIR and t["endirekt_iscilik"].elle_alanlar == ("birim_fiyat",)
    assert t["etiket_iscilik"].tutar == SIFIR
    assert t["diger_gug"].tutar == D_(10) and t["diger_gug"].elle_alanlar == ("tutar",)
    assert t["elektrik"].elle_alanlar == ()   # elle hücresi olmayan satır formülle


def test_elle_tutar_pazarlama_satirinda_da_gecerli():
    from fiyat_motoru.modeller import GiderElle
    satirlar, _ = diger_giderler(U, O, {"yonetim": GiderElle(tutar=SIFIR)})
    t = {s.kod: s.tutar for s in satirlar}
    assert t["yonetim"] == SIFIR and yakin(t["pazarlama"], D_("0.5048087845717276"))
