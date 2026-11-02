from datetime import date
from decimal import Decimal
import pytest
from backend.depo import modeller as m
from backend.servisler import parametre_servisi as ps
from backend.servisler.hatalar import DogrulamaHatasi


@pytest.fixture
def senaryo(oturum):
    sz = m.Sezon(ad="S", baslangic=date(2026, 6, 1), bitis=date(2027, 5, 31)); oturum.add(sz); oturum.flush()
    sen = m.Senaryo(sezon_id=sz.id, tur="fiyat_calismasi", ad="A"); oturum.add(sen); oturum.flush()
    for a in ["enflasyon", "kur.USD", "kur.EUR", "faiz.TL", "stok_ay.TL", "faiz.USD", "stok_ay.USD", "satis_kar", "teklif_kar.1", "teklif_kar.2", "vardiya_saati"]:
        oturum.add(m.Parametre(anahtar=a))
    oturum.flush()
    return sen


def _tohum(oturum, sen):
    t = date(2026, 6, 1)
    for a, v in [("enflasyon", "0.25"), ("kur.USD", "50"), ("kur.EUR", "60"), ("faiz.TL", "0.4"), ("stok_ay.TL", "6"),
                 ("faiz.USD", "0.06"), ("stok_ay.USD", "6"), ("satis_kar", "0.2"), ("teklif_kar.1", "0.2"), ("teklif_kar.2", "0.17"), ("vardiya_saati", "7.5")]:
        ps.deger_ekle(oturum, sen.id, a, Decimal(v), t, "tohum")


def test_gecerli_parametreler_motor_tipi(oturum, senaryo):
    _tohum(oturum, senaryo)
    p = ps.gecerli_parametreler(oturum, senaryo.id, date(2026, 10, 21))
    assert p.enflasyon == Decimal("0.25") and p.kurlar == {"USD": Decimal(50), "EUR": Decimal(60)}
    assert p.faiz_oranlari["TL"] == Decimal("0.4") and p.stok_sureleri_ay["USD"] == Decimal(6)
    assert p.teklif_kar_oranlari == (Decimal("0.2"), Decimal("0.17")) and p.vardiya_saati == Decimal("7.5")


def test_yeni_deger_eskiyi_silmez_gecmiste_kalir(oturum, senaryo):
    _tohum(oturum, senaryo)
    ps.deger_ekle(oturum, senaryo.id, "kur.USD", Decimal(55), date(2026, 9, 1), "kur güncellendi")
    assert ps.gecerli_degerler(oturum, senaryo.id, date(2026, 8, 1))["kur.USD"] == Decimal(50)
    assert ps.gecerli_degerler(oturum, senaryo.id, date(2026, 10, 1))["kur.USD"] == Decimal(55)
    g = ps.gecmis(oturum, senaryo.id, "kur.USD")
    assert [x.deger for x in g] == [Decimal(55), Decimal(50)] and g[0].neden == "kur güncellendi"


def test_ayni_gun_iki_kayit_sonuncusu_gecerli(oturum, senaryo):
    _tohum(oturum, senaryo)
    ps.deger_ekle(oturum, senaryo.id, "stok_ay.TL", Decimal(2), date(2026, 6, 1), "düzeltme")
    assert ps.gecerli_degerler(oturum, senaryo.id, date(2026, 6, 1))["stok_ay.TL"] == Decimal(2)


def test_urun_override_geneli_ezer(oturum, senaryo):
    _tohum(oturum, senaryo)
    ps.deger_ekle(oturum, senaryo.id, "stok_ay.TL", Decimal(2), date(2026, 6, 1), "bu ürün hızlı döner", kapsam_tipi="urun", kapsam_id=7)
    assert ps.gecerli_parametreler(oturum, senaryo.id, date(2026, 7, 1), urun_id=7).stok_sureleri_ay["TL"] == Decimal(2)
    assert ps.gecerli_parametreler(oturum, senaryo.id, date(2026, 7, 1), urun_id=8).stok_sureleri_ay["TL"] == Decimal(6)


def test_eksik_zorunlu_parametre_hata(oturum, senaryo):
    with pytest.raises(DogrulamaHatasi):
        ps.gecerli_parametreler(oturum, senaryo.id, date(2026, 7, 1))


def test_bilinmeyen_anahtar_hata(oturum, senaryo):
    with pytest.raises(DogrulamaHatasi):
        ps.deger_ekle(oturum, senaryo.id, "yok.boyle", Decimal(1), date(2026, 6, 1), "")
