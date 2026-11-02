# tests/test_hesapla.py
from decimal import Decimal
import pytest
from dataclasses import replace
from fiyat_motoru.hesapla import urun_maliyeti
from fiyat_motoru.modeller import Malzeme, ReceteSatiri, UrunGirdisi, UretimBilgisi, Parametreler, GiderOranlari
from fiyat_motoru.para import yakin, SIFIR
from tests.test_uretim_gideri import O, U, P as P_URETIM

D_ = Decimal
P = Parametreler(enflasyon=D_("0.25"), kurlar={"USD": D_(50), "EUR": D_(60)},
                 faiz_oranlari={"TL": D_("0.4"), "USD": D_("0.06"), "EUR": D_("0.06")},
                 stok_sureleri_ay={"TL": D_(6), "USD": D_(6), "EUR": D_(6)},
                 satis_kar_orani=D_("0.2"), teklif_kar_oranlari=(D_("0.2"), D_("0.17"), D_("0.14")), vardiya_saati=D_("7.5"))
MALZ = {
    "KAV": Malzeme("KAV", "Cam Kavanoz 370", "0008-Ambalaj Malzeme", "AD", "TL", D_("5.9"), "S"),
    "ETK": Malzeme("ETK", "Etiket", "0008-Ambalaj Malzeme", "AD", "EUR", D_("0.049"), "S"),
    "TAZ": Malzeme("TAZ", "Sarı Biberiye Taze", "0001-Hammadde", "KG", "TL", D_(65), "Z"),
}
GIRDI = UrunGirdisi(kod="TEST", ad="Test Ürün", uretim=U, recete=(
    ReceteSatiri("KAV", "Cam Kavanoz 370", D_(1), D_("0.02"), "AD"),
    ReceteSatiri("ETK", "Etiket", D_(1), D_("0.02"), "AD"),
    ReceteSatiri("TAZ", "Sarı Biberiye Taze", D_("0.19013459"), SIFIR, "KG"),
    ReceteSatiri("YOK", "Fiyatsız Ara Mamul", D_(1), SIFIR, "KG"),
))


def test_uctan_uca():
    r = urun_maliyeti(GIRDI, MALZ, O, P)
    # malzeme: 7.525510204081633 + 3 + 12.35874835 + 0
    assert yakin(r.malzeme_toplami, D_("22.884258554081633"))
    assert yakin(r.direkt_iscilik_toplami, D_("1.9806745445746057"))
    assert yakin(r.gug_toplami, D_("2.83610677949762"))
    assert yakin(r.uretim_gideri_toplami, D_("4.816781324072226"))
    assert yakin(r.toplam_birim_maliyet, r.malzeme_toplami + r.uretim_gideri_toplami)
    assert yakin(r.diger_giderler_toplami, D_("1.2920738593858545"))
    giy = r.toplam_birim_maliyet + r.diger_giderler_toplami
    assert yakin(r.giydirilmis_maliyet, giy)
    assert yakin(r.finansman["TL"], giy * D_("0.2"))
    assert yakin(r.finansman_dahil_maliyet_tl, giy * D_("1.2"))
    assert yakin(r.doviz_maliyet["USD"], (giy + giy * D_("0.03")) / 50)
    assert yakin(r.satis_fiyati_tl, r.finansman_dahil_maliyet_tl * D_("1.2"))
    assert yakin(r.satis_fiyati_doviz["USD"], r.doviz_maliyet["USD"] * D_("1.2"))
    assert yakin(r.suzme_kg_fiyati_tl, r.satis_fiyati_tl / D_("0.18"))
    assert len(r.teklifler_usd) == 3 and yakin(r.teklifler_usd[1], r.doviz_maliyet["USD"] * D_("1.17"))


def test_yuzdeler_toplami_bir():
    r = urun_maliyeti(GIRDI, MALZ, O, P)
    # R sütunu: tüm kalemler + finansman TL = 1 (Excel R130)
    assert yakin(sum(s.maliyet_yuzdesi for s in r.satirlar), D_(1))


def test_fiyatsiz_malzeme_uyarisi():
    r = urun_maliyeti(GIRDI, MALZ, O, P)
    assert any("YOK" in u for u in r.uyarilar)
    assert [s.grup for s in r.satirlar].count("finansman") == 1


def test_satir_kodu_ile_erisim():
    r = urun_maliyeti(GIRDI, MALZ, O, P)
    assert r.satir("KAV").tutar == r.satirlar[0].tutar
    assert r.satir("dolum_iscilik").grup == "direkt_iscilik"
    assert r.satir("finansman_tl").tutar == r.finansman["TL"]
    with pytest.raises(KeyError):
        r.satir("yok")


def test_tl_finansman_parametresi_yok():
    p = replace(P, faiz_oranlari={"USD": D_("0.06")}, stok_sureleri_ay={"USD": D_(6)})
    r = urun_maliyeti(GIRDI, MALZ, O, p)
    assert any("TL finansman parametresi yok" in u for u in r.uyarilar)
    assert r.finansman_dahil_maliyet_tl == r.giydirilmis_maliyet and r.finansman_dahil_maliyet_tl > 0


def test_usd_kuru_yok():
    p = replace(P, kurlar={"EUR": D_(60)})
    r = urun_maliyeti(GIRDI, MALZ, O, p)
    assert any("USD kuru yok" in u for u in r.uyarilar)
    assert r.teklifler_usd == [SIFIR, SIFIR, SIFIR]


def test_faiz_stok_eslesmiyor_ve_vardiya_saati_uyarilari():
    p = replace(P, stok_sureleri_ay={"TL": D_(6), "USD": D_(6)}, vardiya_saati=SIFIR)
    r = urun_maliyeti(GIRDI, MALZ, O, p)
    assert any("EUR faiz/stok süresi eşleşmiyor, atlandı" in u for u in r.uyarilar)
    assert any("vardiya saati 0" in u for u in r.uyarilar)


def test_yurtdisi_yuzde_kurali_sabitlenir_ve_uyarir():
    # Mevcut davranış: USD bazlı yüzdeler (ihracat sayfası yok, Excel'de doğrulanmadı). Değer bilerek sabitlendi.
    r = urun_maliyeti(replace(GIRDI, uretim=replace(U, pazar="Yurtdışı")), MALZ, O, P)
    assert yakin(sum(s.maliyet_yuzdesi for s in r.satirlar), D_("1.165048543689320388349514563"))
    assert any("Yurtdışı yüzde kuralı Excel'de doğrulanmadı" in u for u in r.uyarilar)
    assert not any("Yurtdışı" in u for u in urun_maliyeti(GIRDI, MALZ, O, P).uyarilar)


def test_gecersiz_pazar_hata_verir():
    with pytest.raises(ValueError):
        replace(U, pazar="yurtici")


def test_uyarilar_tekrarsiz_sirali():
    o = replace(O, mal_kabul_iscilik_kg={}, mal_kabul_gug_kg={})
    r = urun_maliyeti(GIRDI, MALZ, o, P)
    assert len(r.uyarilar) == len(set(r.uyarilar))
    assert sum("taze/turşu sınıfı bulunamadı" in u for u in r.uyarilar) == 1
