from datetime import date
from decimal import Decimal
import pytest
from backend.depo import modeller as m
from backend.servisler import fiyat_servisi as fs
from fiyat_motoru.para import SIFIR


@pytest.fixture
def senaryo(oturum):
    sz = m.Sezon(ad="S", baslangic=date(2026, 6, 1), bitis=date(2027, 5, 31)); oturum.add(sz); oturum.flush()
    sen = m.Senaryo(sezon_id=sz.id, tur="fiyat_calismasi", ad="A"); oturum.add(sen); oturum.flush()
    return sen


def test_fiyat_gecmisi_ve_gecerli(oturum, senaryo):
    fs.malzeme_ekle_veya_guncelle(oturum, "KAV", "Kavanoz 370", "0008-Ambalaj Malzeme", "AD", "TL", "S")
    fs.fiyat_ekle(oturum, senaryo.id, "KAV", Decimal("5.9"), date(2026, 6, 1), "bütçe", kaynak="import")
    fs.fiyat_ekle(oturum, senaryo.id, "KAV", Decimal("6.4"), date(2026, 9, 1), "zam")
    assert fs.gecerli_fiyatlar(oturum, senaryo.id, date(2026, 8, 1))["KAV"].fiyat == Decimal("5.9")
    g = fs.gecerli_fiyatlar(oturum, senaryo.id, date(2026, 10, 1))["KAV"]
    assert g.fiyat == Decimal("6.4") and g.zs == "S" and g.para_birimi == "TL" and g.ad == "Kavanoz 370"
    assert [x.fiyat for x in fs.gecmis(oturum, senaryo.id, "KAV")] == [Decimal("6.4"), Decimal("5.9")]


def test_fiyatsiz_malzeme_listede_sifir_ve_raporda(oturum, senaryo):
    fs.malzeme_ekle_veya_guncelle(oturum, "ARA", "Ara mamul", "0001-Hammadde", "KG", None, None)
    f = fs.gecerli_fiyatlar(oturum, senaryo.id, date(2026, 8, 1))
    assert f["ARA"].fiyat == SIFIR and fs.fiyatsizlar(oturum, senaryo.id, date(2026, 8, 1)) == ["ARA"]


def test_malzeme_guncelleme_degisiklik_kaydi(oturum, senaryo):
    fs.malzeme_ekle_veya_guncelle(oturum, "KAV", "Kavanoz", None, "AD", "TL", "S")
    fs.malzeme_ekle_veya_guncelle(oturum, "KAV", "Kavanoz 370 Boğumlu", None, "AD", "TL", "S")
    kayit = oturum.query(m.DegisiklikKaydi).filter_by(tablo="malzeme").one()
    assert kayit.eski["ad"] == "Kavanoz" and kayit.yeni["ad"] == "Kavanoz 370 Boğumlu"


def test_recete_kartsiz_kodlar(oturum, senaryo):
    from backend.servisler import hesap_servisi as hs, recete_servisi as rs
    fs.malzeme_ekle_veya_guncelle(oturum, "VAR", "Var", None, "AD", "TL", "S")
    u = hs.urun_kaydet(oturum, "U", "U", Decimal(1), "Niko", "Turşu/Turşu", Decimal(1))
    rs.yeni_versiyon(oturum, u.id, senaryo.id, [{"malzeme_kodu": "VAR", "miktar": 1}, {"malzeme_kodu": "KARTYOK", "miktar": 1},
                                              {"malzeme_kodu": "ARA1", "miktar": 1, "dugum_tipi": "ara_mamul"}], "elle")
    assert fs.recete_kartsiz_kodlar(oturum, senaryo.id) == ["KARTYOK"]
