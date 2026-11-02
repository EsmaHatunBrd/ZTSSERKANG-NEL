"""Faz 4c B1/B3: genişletilmiş override (satır, ürün, gider oranı) == kalıcı yazımla hesaplanan sonuç."""
from datetime import date
from decimal import Decimal as D_
import pytest
from backend.depo import modeller as m
from backend.servisler import gider_servisi as gs, hesap_servisi as hs, recete_servisi as rs
from backend.servisler.donusum import decimal_str
from backend.servisler.hatalar import DogrulamaHatasi
from tests.backend.test_hesap_servisi import ortam  # noqa: F401  (fikstür)

TARIH = date(2026, 10, 21)


def _esit(a, b, yol="sonuc"):
    if isinstance(a, dict):
        assert isinstance(b, dict) and a.keys() == b.keys(), yol
        for k in a:
            _esit(a[k], b[k], f"{yol}.{k}")
    elif isinstance(a, list):
        assert isinstance(b, list) and len(a) == len(b), yol
        for i, (x, y) in enumerate(zip(a, b)):
            _esit(x, y, f"{yol}[{i}]")
    elif isinstance(a, str) and isinstance(b, str):
        try:
            x, y = D_(a), D_(b)
        except Exception:
            assert a == b, yol
            return
        assert abs(x - y) <= D_("1e-9"), f"{yol}: {a} != {b}"
    else:
        assert a == b, yol


def _satirlar(oturum, u, sen):
    r = rs.aktif_recete(oturum, u.id, sen.id)
    return [{"malzeme_kodu": x.malzeme_kodu, "ad": x.ad, "miktar": x.miktar, "birim": x.birim, "dugum_tipi": x.dugum_tipi,
             "fire_override": x.fire_override, "brut_miktar_elle": x.brut_miktar_elle, "birim_fiyat_elle": x.birim_fiyat_elle} for x in r.satirlar]


def _recete_degistir(oturum, u, sen, sira, **alanlar):
    sat = _satirlar(oturum, u, sen)
    sat[sira - 1].update(alanlar)
    rs.yeni_versiyon(oturum, u.id, sen.id, sat, "elle")


def _hesap(oturum, sen, override=None):
    return hs.hesapla(oturum, "TEST", sen.id, TARIH, override=override)


@pytest.mark.parametrize("ov, alanlar, sira", [
    ({"birim_fiyat_elle": D_("7.5")}, {"birim_fiyat_elle": D_("7.5")}, 1),
    ({"brut_miktar_elle": D_("0.25")}, {"brut_miktar_elle": D_("0.25")}, 3),
    ({"miktar": D_("0.3")}, {"miktar": D_("0.3")}, 3),
    ({"miktar": D_("2")}, {"miktar": D_("2")}, 1),   # fire_override'lı satırda brüt yeniden hesaplanır
])
def test_satir_override_kalici_yazima_esit(oturum, ortam, ov, alanlar, sira):
    sen, u = ortam
    c1 = _hesap(oturum, sen, {"satirlar": {sira: ov}})
    _recete_degistir(oturum, u, sen, sira, **alanlar)
    c2 = _hesap(oturum, sen)
    _esit(decimal_str(c1.sonuc), decimal_str(c2.sonuc))
    assert c1.fire_kaynaklari == c2.fire_kaynaklari


def test_override_kaydetmez(oturum, ortam):
    sen, u = ortam
    once = _satirlar(oturum, u, sen)
    _hesap(oturum, sen, {"satirlar": {1: {"birim_fiyat_elle": D_("9")}}, "gider_oranlari": {"dolum_iscilik_sn": D_("1")}})
    assert _satirlar(oturum, u, sen) == once
    assert oturum.query(m.Recete).count() == 1


def test_elle_kaldir_kalici_yazima_esit(oturum, ortam):
    sen, u = ortam
    _recete_degistir(oturum, u, sen, 3, brut_miktar_elle=D_("0.25"), birim_fiyat_elle=D_("70"))
    c1 = _hesap(oturum, sen, {"satirlar": {3: {"elle_brut_kaldir": True, "elle_fiyat_kaldir": True}}})
    assert c1.girdi.recete[2].brut_miktar_elle is None and c1.girdi.recete[2].birim_fiyat_elle is None
    _recete_degistir(oturum, u, sen, 3, brut_miktar_elle=None, birim_fiyat_elle=None)
    c2 = _hesap(oturum, sen)
    _esit(decimal_str(c1.sonuc), decimal_str(c2.sonuc))
    assert c1.fire_kaynaklari == c2.fire_kaynaklari


def test_elle_kaldir_ve_fire_birlikte(oturum, ortam):
    sen, u = ortam
    _recete_degistir(oturum, u, sen, 3, brut_miktar_elle=D_("0.25"))
    c = _hesap(oturum, sen, {"satirlar": {3: {"elle_brut_kaldir": True}}, "fire": {3: D_("0.05")}})
    assert c.girdi.recete[2].fire_orani == D_("0.05") and c.fire_kaynaklari[2] == "satir"


def test_elle_brut_ile_fire_422(oturum, ortam):
    sen, _ = ortam
    with pytest.raises(DogrulamaHatasi):
        _hesap(oturum, sen, {"satirlar": {3: {"brut_miktar_elle": D_("0.25")}}, "fire": {3: D_("0.05")}})


def test_satir_override_gecersiz(oturum, ortam):
    sen, _ = ortam
    with pytest.raises(DogrulamaHatasi):
        _hesap(oturum, sen, {"satirlar": {9: {"miktar": D_(1)}}})
    with pytest.raises(DogrulamaHatasi):
        _hesap(oturum, sen, {"satirlar": {1: {"birim_fiyat_elle": D_(1), "elle_fiyat_kaldir": True}}})
    with pytest.raises(DogrulamaHatasi):
        _hesap(oturum, sen, {"satirlar": {1: {"brut_miktar_elle": D_(1), "elle_brut_kaldir": True}}})


def test_gider_orani_havuz_yazimina_esit(oturum, ortam):
    sen, u = ortam
    h = gs.havuzlar(oturum, sen.id)["dolum_iscilik"]
    r = D_("0.3")
    c1 = _hesap(oturum, sen, {"gider_oranlari": {"dolum_iscilik_sn": r}})
    assert c1.oranlar.dolum_iscilik_sn == r
    gs.havuz_kaydet(oturum, sen.id, "dolum_iscilik", h.ad, r * h.baz_miktar, h.baz_tipi, h.baz_miktar, [])
    c2 = _hesap(oturum, sen)
    _esit(decimal_str(c1.sonuc), decimal_str(c2.sonuc))


def test_gider_orani_sozluklu_anahtarlar(oturum, ortam):
    sen, _ = ortam
    c = _hesap(oturum, sen, {"gider_oranlari": {"mal_kabul_iscilik_kg.Turşu/Turşu": D_("2"), "elektrik_sn.Niko": D_("1"), "endirekt_iscilik_sn": D_("0.5"),
                                                "etiket_iscilik_sn": D_("0.1"), "diger_gug_sn": D_("0.2"), "mal_kabul_gug_kg.turşu/turşu": D_("3")}})
    assert c.oranlar.mal_kabul_iscilik_kg["turşu/turşu"] == D_(2) and c.oranlar.elektrik_sn["niko"] == D_(1)
    assert c.oranlar.mal_kabul_gug_kg["turşu/turşu"] == D_(3) and c.oranlar.diger_gug_sn == D_("0.2")
    # asıl havuz oranları değişmedi
    assert gs.oranlar(oturum, sen.id).elektrik_sn["niko"] != D_(1)


@pytest.mark.parametrize("anahtar", ["bilinmeyen", "dolum_iscilik_kg", "elektrik_sn", "elektrik_sn.", "dogalgaz_sn.Niko", "mal_kabul_gug_kg"])
def test_gider_orani_bilinmeyen_anahtar_422(oturum, ortam, anahtar):
    sen, _ = ortam
    with pytest.raises(DogrulamaHatasi):
        _hesap(oturum, sen, {"gider_oranlari": {anahtar: D_(1)}})


def test_urun_override_urun_kaydina_esit(oturum, ortam):
    sen, u = ortam
    ov = {"hat": "Niko", "taze_tursu_sinifi": "Taze/Taze", "ambalaj_hacmi": D_(720), "suzme_kg": D_("0.5"), "pazar": "Yurtdışı"}
    c1 = _hesap(oturum, sen, {"urun": ov})
    assert c1.girdi.uretim.ambalaj_hacmi == D_(720) and c1.girdi.uretim.pazar == "Yurtdışı"
    assert u.ambalaj_hacmi == D_(370) and u.pazar == "Yurtiçi"
    hs.urun_kaydet(oturum, "TEST", u.ad, D_(720), "Niko", "Taze/Taze", D_("0.5"), "Yurtdışı")
    c2 = _hesap(oturum, sen)
    _esit(decimal_str(c1.sonuc), decimal_str(c2.sonuc))


def test_snapshot_override_yeni_alanlari_tasir(oturum, ortam):
    sen, _ = ortam
    ov = {"satirlar": {1: {"birim_fiyat_elle": D_("7.5")}}, "gider_oranlari": {"dolum_iscilik_sn": D_("0.3")}, "urun": {"suzme_kg": D_("0.5")}}
    c = _hesap(oturum, sen, ov)
    assert c.override["satirlar"][1]["birim_fiyat_elle"] == D_("7.5")
    h = hs.kaydet(oturum, c, "TEST", sen.id, TARIH)
    sn = h.girdi_snapshot["override"]
    assert sn["satirlar"]["1"]["birim_fiyat_elle"] == "7.5" and sn["gider_oranlari"]["dolum_iscilik_sn"] == "0.3" and sn["urun"]["suzme_kg"] == "0.5"
