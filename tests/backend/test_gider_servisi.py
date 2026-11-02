from datetime import date
from decimal import Decimal as D_
import pytest
from backend.depo import modeller as m
from backend.servisler import gider_servisi as gs
from backend.servisler.hatalar import DogrulamaHatasi
from fiyat_motoru.para import yakin


@pytest.fixture
def senaryo(oturum):
    sz = m.Sezon(ad="S", baslangic=date(2026, 6, 1), bitis=date(2027, 5, 31)); oturum.add(sz); oturum.flush()
    sen = m.Senaryo(sezon_id=sz.id, tur="fiyat_calismasi", ad="A"); oturum.add(sen); oturum.flush()
    return sen


def tohumla(oturum, sid):
    sinif = [("Taze/Taze", D_("0.25"), D_(6000000)), ("Taze/Turşu", D_("0.65"), D_(7000000)), ("Turşu/Turşu", D_("0.1"), D_(3500000))]
    hat = [("Niko", D_("0.376"), D_(8193712))]
    gs.havuz_kaydet(oturum, sid, "dolum_iscilik", "Dolum", D_("86037707.86667047"), "saniye", D_(442154500), [])
    gs.havuz_kaydet(oturum, sid, "mal_kabul_iscilik", "Mal kabul", D_("32065211.4127488"), "kg", None, sinif)
    gs.havuz_kaydet(oturum, sid, "etiket_iscilik", "Etiket", D_("18533808.031511273"), "saniye", D_(132435000), [])
    gs.havuz_kaydet(oturum, sid, "endirekt_iscilik", "Endirekt", D_("42088882.57323751"), "saniye", D_(32547902), [])
    gs.havuz_kaydet(oturum, sid, "mal_kabul_gug", "Mal kabul GÜG", D_(21000000), "kg", None, sinif)
    gs.havuz_kaydet(oturum, sid, "diger_gug", "Diğer GÜG", D_("25281257.75"), "saniye", D_(32547902), [])
    gs.havuz_kaydet(oturum, sid, "elektrik", "Elektrik", D_(14112000), "saniye", None, hat)
    gs.havuz_kaydet(oturum, sid, "dogalgaz", "Doğalgaz", D_(22464000), "saniye", None, [("Niko", D_("0.46"), D_(8193712))])
    gs.havuz_kaydet(oturum, sid, "amortisman", "Amortisman", D_(49056000), "saniye", None, [("Niko", D_("0.43"), D_(8193712))])
    gs.havuz_kaydet(oturum, sid, "yonetim", "Yönetim", D_("26274982.5"), "adet", None, [])
    gs.havuz_kaydet(oturum, sid, "pazarlama", "Pazarlama", D_(16848000), "adet", None, [])
    gs.ambalaj_kaydet(oturum, sid, [("370 ml kavanoz", D_(370), D_(5690071), D_("0.5")), ("720 ml kavanoz", D_(720), D_(11896020), D_("0.75"))])


def test_oranlar_excel_ile_ayni(oturum, senaryo):
    tohumla(oturum, senaryo.id)
    o = gs.oranlar(oturum, senaryo.id)
    assert yakin(o.dolum_iscilik_sn, D_("0.19458743011022273"))
    assert yakin(o.mal_kabul_iscilik_kg["turşu/turşu"], D_("0.9161488975071086"))
    assert yakin(o.elektrik_sn["niko"], D_("0.6475834151847173"))
    payda = D_(5690071) * D_("0.5") + D_(11896020) * D_("0.75")
    assert yakin(o.pazarlama_adet[D_(370)], D_(16848000) / payda * D_("0.5"))


def test_eksik_havuz_hata(oturum, senaryo):
    with pytest.raises(DogrulamaHatasi):
        gs.havuzlari_getir(oturum, senaryo.id)


def test_pay_toplami_kontrol(oturum, senaryo):
    tohumla(oturum, senaryo.id)
    gs.havuz_kaydet(oturum, senaryo.id, "elektrik", "Elektrik", D_(14112000), "saniye", None,
                    [("Niko", D_("0.376"), D_(8193712)), ("Herbort", D_("0.191"), D_(4720549))])
    bozuk = gs.pay_toplami_kontrol(oturum, senaryo.id)
    assert {b["havuz"] for b in bozuk} >= {"elektrik", "dogalgaz", "amortisman"}
    assert next(b for b in bozuk if b["havuz"] == "elektrik")["toplam"] == D_("0.567")


def test_havuz_guncelleme_anahtarlari_yeniler(oturum, senaryo):
    tohumla(oturum, senaryo.id)
    gs.havuz_kaydet(oturum, senaryo.id, "elektrik", "Elektrik", D_(1), "saniye", None, [("Torba", D_(1), D_(10))])
    h = oturum.query(m.GiderHavuzu).filter_by(senaryo_id=senaryo.id, kod="elektrik").one()
    assert [a.alt_kalem for a in h.anahtarlar] == ["Torba"] and oturum.query(m.DegisiklikKaydi).filter_by(tablo="gider_havuzu").count() == 1


def test_havuz_ayni_veriyle_kaydedince_log_yok(oturum, senaryo):
    tohumla(oturum, senaryo.id)
    n = oturum.query(m.DegisiklikKaydi).filter_by(tablo="gider_havuzu").count()
    gs.havuz_kaydet(oturum, senaryo.id, "elektrik", "Elektrik", D_(14112000), "saniye", None, [("Niko", D_("0.376"), D_(8193712))])
    assert oturum.query(m.DegisiklikKaydi).filter_by(tablo="gider_havuzu").count() == n


def test_ambalaj_degisiklik_kaydi(oturum, senaryo):
    gs.ambalaj_kaydet(oturum, senaryo.id, [("A", D_(370), D_(10), D_("0.5"))], "esma")
    k = oturum.query(m.DegisiklikKaydi).filter_by(tablo="ambalaj_sinifi")
    assert k.count() == 1 and k.one().eski == [] and k.one().kullanici == "esma"
    gs.ambalaj_kaydet(oturum, senaryo.id, [("A", D_(370), D_(10), D_("0.5"))], "esma")   # aynı veri -> log yok
    assert k.count() == 1
    gs.ambalaj_kaydet(oturum, senaryo.id, [("A", D_(370), D_(20), D_("0.5"))], "esma")
    assert k.count() == 2 and k.order_by(m.DegisiklikKaydi.id.desc()).first().eski == [["A", "370", "10", "0.5"]]


def test_ambalaj_bos_liste_reddedilir(oturum, senaryo):
    with pytest.raises(DogrulamaHatasi):
        gs.ambalaj_kaydet(oturum, senaryo.id, [])


def test_havuz_dogrulamalari(oturum, senaryo):
    with pytest.raises(DogrulamaHatasi):
        gs.havuz_kaydet(oturum, senaryo.id, "dolum_iscilik", "D", D_(1), "litre", D_(5), [])
    with pytest.raises(DogrulamaHatasi):
        gs.havuz_kaydet(oturum, senaryo.id, "dolum_iscilik", "D", D_(1), "saniye", None, [])
    with pytest.raises(DogrulamaHatasi):
        gs.havuz_kaydet(oturum, senaryo.id, "dolum_iscilik", "D", D_(1), "saniye", D_(0), [])
    gs.havuz_kaydet(oturum, senaryo.id, "dolum_iscilik", "D", D_(1), "saniye", D_(5), [])
    gs.havuz_kaydet(oturum, senaryo.id, "yonetim", "Y", D_(1), "adet", None, [])   # ambalaj bazlı havuz: baz_miktar yok
