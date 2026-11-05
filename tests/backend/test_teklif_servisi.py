# tests/backend/test_teklif_servisi.py
from datetime import date
from decimal import Decimal as D_
import pytest
from backend.servisler import hesap_servisi as hs, teklif_servisi as ts
from backend.servisler.hatalar import DogrulamaHatasi
from fiyat_motoru.para import yakin
from tests.backend.test_hesap_servisi import ortam  # noqa: F401  (fixture)


def test_uc_tur_ve_fazlasi(oturum, ortam):
    sen, _ = ortam
    h = hs.kaydet(oturum, hs.hesapla(oturum, "TEST", sen.id, date(2026, 10, 21)), "TEST", sen.id, date(2026, 10, 21))
    usd = D_(h.sonuc_snapshot["doviz_maliyet"]["USD"]); tl = D_(h.sonuc_snapshot["finansman_dahil_maliyet_tl"])
    t1 = ts.tur_ekle(oturum, h.id, D_("0.2"), musteri="M")
    t2 = ts.tur_ekle(oturum, h.id, D_("0.17"))
    t3 = ts.tur_ekle(oturum, h.id, D_("0.14"))
    t4 = ts.tur_ekle(oturum, h.id, D_("0.12"), notu="4. tur istisna")
    assert [t.tur_no for t in ts.turlar(oturum, h.id)] == [1, 2, 3, 4]
    assert yakin(t1.fiyat_usd, usd * D_("1.2")) and yakin(t3.fiyat_tl, tl * D_("1.14")) and t4.notu == "4. tur istisna"
    assert ts.durum_guncelle(oturum, t2.id, "gonderildi").durum == "gonderildi"
    with pytest.raises(DogrulamaHatasi):
        ts.durum_guncelle(oturum, t2.id, "belirsiz")


def test_senaryo_teklifleri_ve_son_turlar(oturum, ortam):
    sen, _ = ortam
    h = hs.kaydet(oturum, hs.hesapla(oturum, "TEST", sen.id, date(2026, 10, 21)), "TEST", sen.id, date(2026, 10, 21))
    t1 = ts.tur_ekle(oturum, h.id, D_("0.2"), musteri="Migros")
    t2 = ts.tur_ekle(oturum, h.id, D_("0.1"), musteri="BIM")
    ts.durum_guncelle(oturum, t2.id, "red")
    assert [t.id for t, _h, _u in ts.senaryo_teklifleri(oturum, sen.id)] == [t2.id, t1.id]          # en yeni önce
    assert ts.senaryo_teklifleri(oturum, sen.id)[0][2].kod == "TEST"
    assert [t.id for t, _h, _u in ts.senaryo_teklifleri(oturum, sen.id, durum="red")] == [t2.id]
    assert [t.id for t, _h, _u in ts.senaryo_teklifleri(oturum, sen.id, musteri="migr")] == [t1.id]
    assert ts.senaryo_teklifleri(oturum, sen.id + 99) == []
    assert ts.son_turlar(oturum, [h.id])[h.id].id == t2.id and ts.son_turlar(oturum, []) == {}


def test_sil_gunluge_yazar_ve_tur_numarasi_yeniden_verilmez(oturum, ortam):
    from backend.depo import modeller as m
    from backend.servisler import gunluk_servisi as gs
    from backend.servisler.hatalar import BulunamadiHatasi
    sen, _ = ortam
    h = hs.kaydet(oturum, hs.hesapla(oturum, "TEST", sen.id, date(2026, 10, 21)), "TEST", sen.id, date(2026, 10, 21))
    t1 = ts.tur_ekle(oturum, h.id, D_("0.2"), musteri="Migros")
    t2 = ts.tur_ekle(oturum, h.id, D_("0.15"))
    ts.sil(oturum, t2.id, "esma")
    assert [t.tur_no for t in ts.turlar(oturum, h.id)] == [1]
    kayit = oturum.query(m.DegisiklikKaydi).filter_by(tablo="teklif", islem="sil").one()
    assert kayit.kullanici == "esma" and kayit.eski["tur_no"] == 2 and kayit.eski["urun_kodu"] == "TEST" and kayit.eski["senaryo_id"] == sen.id
    # silinen 2. turun numarası tekrar kullanılmaz; ilk turun numarası değişmez
    assert ts.tur_ekle(oturum, h.id, D_("0.1")).tur_no == 3 and t1.tur_no == 1
    satir = next(r for r in gs.liste(oturum, gs.Suzgec(senaryo=sen.id))[0] if r["tur"] == "teklif" and "silindi" in r["baslik"])
    assert satir["urun_kodu"] == "TEST" and satir["baslik"] == "Teklif turu silindi"
    with pytest.raises(BulunamadiHatasi):
        ts.sil(oturum, 999999)
