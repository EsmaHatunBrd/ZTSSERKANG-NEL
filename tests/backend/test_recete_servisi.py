from datetime import date
from decimal import Decimal as D_
import pytest
from backend.depo import modeller as m
from backend.servisler import recete_servisi as rs
from fiyat_motoru.para import SIFIR


@pytest.fixture
def ortam(oturum):
    sz = m.Sezon(ad="S", baslangic=date(2026, 6, 1), bitis=date(2027, 5, 31)); oturum.add(sz); oturum.flush()
    sen = m.Senaryo(sezon_id=sz.id, tur="fiyat_calismasi", ad="A"); oturum.add(sen); oturum.flush()
    u = m.Urun(kod="U1", ad="Ürün", ambalaj_hacmi=D_(370), hat="Niko", taze_tursu_sinifi="Turşu/Turşu", suzme_kg=D_("0.18")); oturum.add(u); oturum.flush()
    return sen, u


SATIRLAR = [
    {"malzeme_kodu": "KAV", "ad": "Kavanoz", "miktar": D_(1), "birim": "AD"},
    {"malzeme_kodu": "ETK", "ad": "Etiket", "miktar": D_(1), "birim": "AD", "fire_override": D_("0.05")},
    {"malzeme_kodu": "TAZ", "ad": "Taze", "miktar": D_("0.19"), "birim": "KG"},
    {"malzeme_kodu": "ARA", "ad": "Ara mamul", "miktar": D_(1), "birim": "KG", "dugum_tipi": "ara_mamul"},
]
TIPLER = {"KAV": "0008-Ambalaj Malzeme", "ETK": "0008-Ambalaj Malzeme", "TAZ": "0001-Hammadde", "ARA": None}


def test_versiyonlama(oturum, ortam):
    sen, u = ortam
    r1 = rs.yeni_versiyon(oturum, u.id, sen.id, SATIRLAR, "import", "sistem")
    r2 = rs.yeni_versiyon(oturum, u.id, sen.id, SATIRLAR[:2], "elle", "esma")
    assert (r1.versiyon, r1.aktif, r2.versiyon, r2.aktif) == (1, False, 2, True)
    assert rs.aktif_recete(oturum, u.id, sen.id).id == r2.id and len(r2.satirlar) == 2


def test_fire_onceligi(oturum, ortam):
    sen, u = ortam
    r = rs.yeni_versiyon(oturum, u.id, sen.id, SATIRLAR, "import", "sistem")
    t = date(2026, 6, 1)
    rs.fire_kurali_ekle(oturum, sen.id, "tip", "0008-Ambalaj Malzeme", D_("0.02"), t, "varsayılan")
    rs.fire_kurali_ekle(oturum, sen.id, "tip", "0001-Hammadde", D_("0.05"), t, "varsayılan")
    rs.fire_kurali_ekle(oturum, sen.id, "malzeme", "TAZ", D_("0.03"), t, "bu taze az fire verir")
    rs.grup_olustur(oturum, "Hassas kavanozlar", ["KAV"])
    rs.fire_kurali_ekle(oturum, sen.id, "grup", "Hassas kavanozlar", D_("0.04"), t, "kırılgan")
    satirlar, kaynaklar = rs.fire_uygulanmis(oturum, r, sen.id, date(2026, 10, 1), TIPLER)
    assert [s.fire_orani for s in satirlar] == [D_("0.04"), D_("0.05"), D_("0.03"), SIFIR]
    assert kaynaklar == ["grup:Hassas kavanozlar", "satir", "malzeme", "yok"]


def test_fire_kurali_gecmisi(oturum, ortam):
    sen, u = ortam
    r = rs.yeni_versiyon(oturum, u.id, sen.id, SATIRLAR[:1], "import", "sistem")
    rs.fire_kurali_ekle(oturum, sen.id, "tip", "0008-Ambalaj Malzeme", D_("0.02"), date(2026, 6, 1), "v1")
    rs.fire_kurali_ekle(oturum, sen.id, "tip", "0008-Ambalaj Malzeme", D_("0.03"), date(2026, 9, 1), "v2")
    assert rs.fire_uygulanmis(oturum, r, sen.id, date(2026, 8, 1), TIPLER)[0][0].fire_orani == D_("0.02")
    assert rs.fire_uygulanmis(oturum, r, sen.id, date(2026, 10, 1), TIPLER)[0][0].fire_orani == D_("0.03")


def test_grup_kurali_malzeme_kuralini_ezer(oturum, ortam):
    sen, u = ortam
    r = rs.yeni_versiyon(oturum, u.id, sen.id, SATIRLAR[:1], "import", "sistem")   # KAV
    t = date(2026, 6, 1)
    rs.fire_kurali_ekle(oturum, sen.id, "malzeme", "KAV", D_("0.03"), t, "malzeme kuralı")
    rs.grup_olustur(oturum, "Hassas", ["KAV"])
    rs.fire_kurali_ekle(oturum, sen.id, "grup", "Hassas", D_("0.04"), t, "grup kuralı")
    satirlar, kaynaklar = rs.fire_uygulanmis(oturum, r, sen.id, date(2026, 10, 1), TIPLER)
    assert satirlar[0].fire_orani == D_("0.04") and kaynaklar == ["grup:Hassas"]


def test_kurallara_birak(oturum, ortam):
    sen, u = ortam
    ilk = [dict(x, fire_override=D_(0)) for x in SATIRLAR[:3]]
    ilk.append(dict(SATIRLAR[3]))
    r1 = rs.yeni_versiyon(oturum, u.id, sen.id, ilk, "import", "sistem")
    t = date(2026, 6, 1)
    rs.fire_kurali_ekle(oturum, sen.id, "tip", "0008-Ambalaj Malzeme", D_("0.02"), t, "varsayılan")
    assert rs.fire_uygulanmis(oturum, r1, sen.id, t, TIPLER)[1][:3] == ["satir", "satir", "satir"]
    r2 = rs.kurallara_birak(oturum, u.id, sen.id, [1, 2], "esma")
    assert (r2.versiyon, r2.aktif, r2.olusturan) == (2, True, "esma") and r1.aktif is False
    assert [x.fire_override for x in r2.satirlar] == [None, None, D_(0), None]
    assert r2.satirlar[3].dugum_tipi == "ara_mamul" and r2.satirlar[0].malzeme_kodu == "KAV"
    satirlar, kaynaklar = rs.fire_uygulanmis(oturum, r2, sen.id, t, TIPLER)
    assert kaynaklar == ["tip:0008-Ambalaj Malzeme", "tip:0008-Ambalaj Malzeme", "satir", "yok"]
    assert satirlar[0].fire_orani == D_("0.02")
    r3 = rs.kurallara_birak(oturum, u.id, sen.id, None, "esma")
    assert all(x.fire_override is None for x in r3.satirlar) and r3.versiyon == 3


def test_kurallara_birak_gecersiz_sira(oturum, ortam):
    from backend.servisler.hatalar import DogrulamaHatasi
    sen, u = ortam
    rs.yeni_versiyon(oturum, u.id, sen.id, SATIRLAR, "import", "sistem")
    with pytest.raises(DogrulamaHatasi):
        rs.kurallara_birak(oturum, u.id, sen.id, [9], "esma")


def test_dugum_tipi_motora_gecer(oturum, ortam):
    sen, u = ortam
    r = rs.yeni_versiyon(oturum, u.id, sen.id, SATIRLAR, "import", "sistem")
    satirlar, _ = rs.fire_uygulanmis(oturum, r, sen.id, date(2026, 10, 1), TIPLER)
    assert [x.dugum_tipi for x in satirlar] == ["yaprak", "yaprak", "yaprak", "ara_mamul"]


def test_versiyonlar_ve_recete_getir(oturum, ortam):
    sen, u = ortam
    r1 = rs.yeni_versiyon(oturum, u.id, sen.id, SATIRLAR, "import", "sistem")
    r2 = rs.yeni_versiyon(oturum, u.id, sen.id, SATIRLAR[:2], "elle", "esma")
    assert [x.id for x in rs.versiyonlar(oturum, u.id, sen.id)] == [r2.id, r1.id]
    assert len(rs.recete_getir(oturum, r1.id).satirlar) == 4
    from backend.servisler.hatalar import BulunamadiHatasi
    with pytest.raises(BulunamadiHatasi):
        rs.recete_getir(oturum, 999)


def test_gruplar_listele(oturum, ortam):
    rs.grup_olustur(oturum, "B grubu", ["KAV", "ETK"])
    g = rs.gruplar_listele(oturum)
    assert [x.ad for x in g] == ["B grubu"] and [u.malzeme_kodu for u in g[0].uyeler] == ["KAV", "ETK"]


ELLE_SATIRLAR = [
    {"malzeme_kodu": "KAV", "ad": "Kavanoz", "miktar": D_(1), "birim": "AD", "brut_miktar_elle": D_("1.5")},
    {"malzeme_kodu": "ETK", "ad": "Etiket", "miktar": D_(1), "birim": "AD", "fire_override": D_("0.05"), "birim_fiyat_elle": D_("7.25")},
    {"malzeme_kodu": "TAZ", "ad": "Taze", "miktar": D_("0.19"), "birim": "KG"},
]


def test_elle_alanlar_versiyonla_tasinir_ve_kaynak_elle(oturum, ortam):
    sen, u = ortam
    r = rs.yeni_versiyon(oturum, u.id, sen.id, ELLE_SATIRLAR, "elle")
    oturum.expire_all()
    a = rs.aktif_recete(oturum, u.id, sen.id)
    assert [(x.brut_miktar_elle, x.birim_fiyat_elle) for x in a.satirlar] == [(D_("1.5"), None), (None, D_("7.25")), (None, None)]
    satirlar, kaynaklar = rs.fire_uygulanmis(oturum, r, sen.id, date(2026, 6, 1), {})
    assert kaynaklar == ["elle", "satir", "yok"]
    assert satirlar[0].brut_miktar_elle == D_("1.5") and satirlar[1].birim_fiyat_elle == D_("7.25")
    # elle alanlar verilmemişse None (geri uyumlu)
    r2 = rs.yeni_versiyon(oturum, u.id, sen.id, SATIRLAR, "elle")
    assert all(x.brut_miktar_elle is None and x.birim_fiyat_elle is None for x in r2.satirlar)


def test_kurallara_birak_elle_degerleri_korur_ve_istenirse_kaldirir(oturum, ortam):
    sen, u = ortam
    rs.yeni_versiyon(oturum, u.id, sen.id, ELLE_SATIRLAR, "elle")
    r = rs.kurallara_birak(oturum, u.id, sen.id, None)
    assert [x.brut_miktar_elle for x in r.satirlar] == [D_("1.5"), None, None] and r.satirlar[1].birim_fiyat_elle == D_("7.25")
    assert r.satirlar[1].fire_override is None
    r = rs.kurallara_birak(oturum, u.id, sen.id, [2], elle_degerleri_kaldir=True)       # 1. satır seçili değil: elle değer kalır
    assert r.satirlar[0].brut_miktar_elle == D_("1.5")
    r = rs.kurallara_birak(oturum, u.id, sen.id, [1], elle_degerleri_kaldir=True)
    assert r.satirlar[0].brut_miktar_elle is None and r.satirlar[1].birim_fiyat_elle == D_("7.25")
