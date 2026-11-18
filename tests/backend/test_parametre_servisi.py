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


# ---------------------------------------------------------------- Değer sınırları (D1)
@pytest.mark.parametrize("anahtar, deger", [
    ("kur.USD", "0"), ("kur.USD", "-1"),                        # kur > 0
    ("enflasyon", "250"), ("enflasyon", "25"), ("enflasyon", "3.01"), ("enflasyon", "-1"),   # oran: en çok 3 (= %300)
    ("satis_kar", "-0.01"), ("satis_kar", "25"), ("teklif_kar.1", "4"), ("faiz.TL", "45"),
    ("vardiya_saati", "0"), ("vardiya_saati", "24.5"),
])
def test_sinir_disi_deger_422_ve_sade_mesaj(oturum, senaryo, anahtar, deger):
    with pytest.raises(DogrulamaHatasi) as e:
        ps.deger_ekle(oturum, senaryo.id, anahtar, Decimal(deger), date(2026, 6, 1), "deneme")
    assert e.value.alanlar == {} and anahtar not in e.value.mesaj   # teknik ad ve ek yok


@pytest.mark.parametrize("anahtar, deger", [
    ("kur.USD", "0.0001"), ("enflasyon", "3"), ("enflasyon", "-0.05"), ("satis_kar", "0"), ("satis_kar", "1.5"),
    ("teklif_kar.1", "0.2"), ("faiz.TL", "0.45"), ("vardiya_saati", "24"), ("vardiya_saati", "7.5"), ("stok_ay.TL", "6"),
])
def test_sinir_icindeki_deger_kaydedilir(oturum, senaryo, anahtar, deger):
    assert ps.deger_ekle(oturum, senaryo.id, anahtar, Decimal(deger), date(2026, 6, 1), "deneme").deger == Decimal(deger)


def test_sinir_mesaji_okunur_ad(oturum, senaryo):
    oturum.add(m.Parametre(anahtar="marj_esigi", aciklama="Hedef kâr oranı eşiği: altındaki ürünler uyarılır (girilmezse %10)", birim="oran"))
    oturum.flush()
    with pytest.raises(DogrulamaHatasi) as e:
        ps.deger_ekle(oturum, senaryo.id, "marj_esigi", Decimal(10), date(2026, 6, 1), "deneme")
    assert e.value.mesaj == "Hedef kâr oranı eşiği %0 ile %300 arasında olmalı."


def test_bolen_yuzde_sayilmaz():
    assert not ps.yuzde_mi("liste_bolen_yurtici", "oran") and ps.yuzde_mi("satis_kar", None) and ps.yuzde_mi("faiz.TL", "oran")
    assert not ps.yuzde_mi("kur.USD", "TL") and not ps.yuzde_mi("vardiya_saati", "saat")


def test_olagan_disi_degerler_genel_ve_urun(oturum, senaryo):
    _tohum(oturum, senaryo)
    t = date(2026, 7, 1)
    ps.deger_ekle(oturum, senaryo.id, "enflasyon", Decimal("2.5"), t, "yanlış yazım")             # %250: kaydedilir ama olağan dışı
    ps.deger_ekle(oturum, senaryo.id, "satis_kar", Decimal("1.2"), t, "ürün", kapsam_tipi="urun", kapsam_id=7)
    # Sınır gelmeden önce kaydedilmiş eski bir değer (doğrudan tablo): kur 0
    oturum.add(m.ParametreDegeri(parametre_id=oturum.query(m.Parametre).filter_by(anahtar="kur.EUR").one().id, senaryo_id=senaryo.id,
                                 kapsam_tipi="genel", deger=Decimal(0), gecerlilik_basi=t, neden="eski"))
    oturum.flush()
    x = {(r["anahtar"], r["kapsam_id"]): r["neden"] for r in ps.olagan_disi_degerler(oturum, senaryo.id, date(2026, 8, 1))}
    assert x == {("enflasyon", None): "%100'ün üstünde", ("kur.EUR", None): "kur 0 ya da eksi", ("satis_kar", 7): "%100'ün üstünde"}
    assert ps.olagan_disi_degerler(oturum, senaryo.id, date(2026, 6, 15)) == []   # o tarihte geçerli değerler olağan
