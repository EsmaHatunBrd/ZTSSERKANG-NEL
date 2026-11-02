from dataclasses import replace
from decimal import Decimal as D_
from fiyat_motoru.hesapla import urun_maliyeti
from fiyat_motoru.malzeme import malzeme_tutari
from fiyat_motoru.modeller import ReceteSatiri
from fiyat_motoru.para import yakin, SIFIR
from tests.test_hesapla import GIRDI, MALZ, O, P
from tests.test_malzeme import P as PM, malz, satir


def test_satir_fireli_ve_firesiz_tutar():
    s, _ = malzeme_tutari(satir(1, "0.02"), malz("5.9", "TL", "S"), PM)       # 001!P13
    assert yakin(s.tutar, D_("7.525510204081633")) and yakin(s.tutar_firesiz, D_("7.375"))
    assert s.miktar_kaynagi == "fire" and s.fiyat_kaynagi == "liste"


def test_elle_brut_fire_hesaplanmaz():
    r = ReceteSatiri("k", "a", D_(1), D_("0.02"), "AD", brut_miktar_elle=D_("1.1"))
    s, _ = malzeme_tutari(r, malz("5.9", "TL", "S"), PM)
    assert yakin(s.tutar, D_("5.9") * D_("1.25") * D_("1.1")) and s.brut_miktar == D_("1.1") and s.miktar_kaynagi == "elle"
    assert yakin(s.tutar_firesiz, D_("7.375"))


def test_elle_fiyat_listeyi_ezer_katsayi_ayni():
    r = ReceteSatiri("k", "a", D_(1), SIFIR, "AD", birim_fiyat_elle=D_("6"))
    s, u = malzeme_tutari(r, malz("5.9", "TL", "S"), PM)
    assert yakin(s.tutar, D_("7.5")) and s.fiyat_kaynagi == "elle" and u is None
    s2, u2 = malzeme_tutari(r, None, PM)             # kartı olmayan malzeme + elle fiyat: Z/S bilinmiyor -> katsayı yok, uyarı yok
    assert yakin(s2.tutar, D_("6")) and u2 is None


def test_urun_firesiz_zinciri():
    r = urun_maliyeti(GIRDI, MALZ, O, P)
    f = r.firesiz
    assert f is not None and f.firesiz is None
    assert yakin(f.malzeme_toplami, D_("22.67374835")) and f.malzeme_toplami < r.malzeme_toplami
    assert f.direkt_iscilik_toplami == r.direkt_iscilik_toplami          # mal kabul firesi zaten 0'dı
    assert yakin(f.finansman_dahil_maliyet_tl, (f.toplam_birim_maliyet + f.diger_giderler_toplami) * D_("1.2"))
    assert all(s.tutar_firesiz == s.tutar for s in r.satirlar if s.grup != "malzeme")
    assert sum(s.tutar_firesiz for s in r.satirlar if s.grup == "malzeme") == f.malzeme_toplami


def test_mal_kabul_firesi_firesizde_sifir():
    g = replace(GIRDI, uretim=replace(GIRDI.uretim, mal_kabul_fire=D_("0.1")))
    r = urun_maliyeti(g, MALZ, O, P)
    assert r.firesiz.satir("mal_kabul_iscilik").brut_miktar == GIRDI.uretim.mal_kabul_miktar_kg
    assert r.satir("mal_kabul_iscilik").brut_miktar > r.firesiz.satir("mal_kabul_iscilik").brut_miktar
