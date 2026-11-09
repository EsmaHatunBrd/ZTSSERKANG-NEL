"""Faz 5c: senaryo kopyalama / güncelleme / silme, senaryo üyeliği (aktif reçete), ?tum=1, boş reçete GET, önbellek anahtarı."""
from datetime import date
from decimal import Decimal as D_
import pytest
from sqlalchemy import func, select
from backend.depo import modeller as m
from backend.depo.veritabani import Base, motor_olustur, oturum_fabrikasi
from backend.servisler import hesap_servisi as hs, senaryo_servisi as ss
from backend.servisler.hatalar import CatismaHatasi, DogrulamaHatasi
from backend.tohum import parametreleri_tohumla
from backend.uygulama import uygulama_olustur
from tests.backend.test_api import _kur, _senaryo, istemci  # noqa: F401
from tests.backend.test_faz5_gunluk import KAP
from tests.backend.test_gider_servisi import tohumla as gider_tohumla

A = "/api/v1"
HATA = {"hata", "mesaj", "alanlar", "kod"}
KART = {"ambalaj_hacmi": "720", "hat": "Niko", "taze_tursu_sinifi": "Turşu/Turşu", "suzme_kg": "0.3"}
HEDEF = {"vardiya_uretim_adedi": "65000", "dolum_personel": "13", "etiketleme_adedi": "35000", "etiket_personel": "7", "mal_kabul_miktar_kg": "0.19"}
HEPSI = {"receteler": True, "fiyatlar": True, "parametreler": True, "gider": True, "uretim": True, "fire_kurallari": True}
HICBIRI = {k: False for k in HEPSI}


def _govde(ad="Kopya", secimler=None, **ek):
    return {"sezon_ad": "2027-2028", "ad": ad, "tur": "fiyat_calismasi", "aciklama": "yeni sezon", "neden": "sezon açılışı",
            "kopyala": HEPSI if secimler is None else secimler, **ek}


def _zengin_kaynak(c, oturum):
    """_kur üstüne: elle değerli 2. reçete sürümü, eski+gelecek fiyat, ürün kapsamlı parametre, metin, taban×çarpan havuz, kapasite, 2 fire kuralı, kayıtlı hesap+teklif."""
    sid = _senaryo(c); _kur(c, sid, oturum)
    uid = c.get(f"{A}/urunler/TEST").json()["id"]
    assert c.post(f"{A}/urunler/TEST/recete?senaryo={sid}", json=[
        {"malzeme_kodu": "KAV", "ad": "Kavanoz", "miktar": "1", "birim": "AD", "fire_override": "0.02", "brut_miktar_elle": "1.1", "seviye": 1},
        {"malzeme_kodu": "ARA", "ad": "Ara mamul", "miktar": "0.5", "birim": "KG", "dugum_tipi": "ara_mamul", "birim_fiyat_elle": "12.5", "seviye": 2},
    ]).status_code == 201   # v2 aktif; v1 pasif (kopyalanmamalı)
    assert c.post(f"{A}/malzemeler/KAV/fiyatlar?senaryo={sid}", json={"onay": True, "fiyat": "4", "gecerlilik_basi": "2026-05-01", "neden": "eski"}).status_code == 201
    assert c.post(f"{A}/malzemeler/KAV/fiyatlar?senaryo={sid}", json={"onay": True, "fiyat": "9", "gecerlilik_basi": "2099-01-01", "neden": "gelecek"}).status_code == 201
    assert c.post(f"{A}/parametreler/kur.USD/degerler?senaryo={sid}", json={"deger": "51", "gecerlilik_basi": "2026-06-01", "neden": "ürüne özel",
                                                                             "kapsam_tipi": "urun", "kapsam_id": uid}).status_code == 201
    assert c.post(f"{A}/metin-parametreler?senaryo={sid}", json={"anahtar": "satis_fiyati_notu", "deger": "not 1", "gecerlilik_basi": "2026-06-01", "neden": "n"}).status_code == 201
    assert c.put(f"{A}/gider-havuzlari/pazarlama?senaryo={sid}", json={"ad": "Pazarlama", "neden": "bütçe", "taban_tutar": "1000", "baz_tipi": "adet",
                                                                        "carpanlar": [{"ad": "SGK", "deger": "1.35"}, {"ad": "zam", "deger": "1.3"}]}).status_code == 200
    assert c.put(f"{A}/uretim-kapasitesi/TEST?senaryo={sid}", json={**KAP, "neden": "kapasite", "urun_ad": "Test"}).status_code == 200
    for oran, tarih in (("0.05", "2026-06-01"), ("0.07", "2026-07-01")):   # aynı kapsam: yalnız geçerli olan (0.07) kopyalanır
        assert c.post(f"{A}/fire-kurallari?senaryo={sid}", json={"kapsam_tipi": "malzeme", "kapsam_deger": "KAV", "oran": oran, "gecerlilik_basi": tarih, "neden": "f"}).status_code == 201
    assert c.post(f"{A}/fire-kurallari?senaryo={sid}", json={"kapsam_tipi": "tip", "kapsam_deger": "0008-Ambalaj Malzeme", "oran": "0.01", "gecerlilik_basi": "2026-06-01", "neden": "f"}).status_code == 201
    h = c.post(f"{A}/urunler/TEST/hesaplar", json={"senaryo_id": sid, "tarih": "2026-10-21"}).json()["id"]
    assert c.post(f"{A}/hesaplar/{h}/teklifler", json={"kar_orani": "0.2"}).status_code == 201
    return sid, uid


def _say(oturum, tablo, sid):
    return oturum.scalar(select(func.count()).select_from(tablo).where(tablo.senaryo_id == sid))


# ------------------------------------------------------------------ kopyalama
def test_kopya_tam_sayilar_ve_icerik(istemci, oturum):
    c = istemci
    sid, uid = _zengin_kaynak(c, oturum)
    assert c.post(f"{A}/senaryolar/{sid}/kilitle", json={"neden": "kapandı"}).status_code == 200   # kilitli kaynaktan kopya salt okunur: serbest
    r = c.post(f"{A}/senaryolar/{sid}/kopyala", json=_govde(), headers={"X-Kullanici": "esma"})
    assert r.status_code == 201, r.text
    g = r.json()
    yeni = g["id"]
    assert yeni != sid and g["sezon_ad"] == "2027-2028" and g["ad"] == "Kopya" and g["tur"] == "fiyat_calismasi" and g["aciklama"] == "yeni sezon"
    assert g["kilitli"] is False and g["urun_sayisi"] == 1
    assert g["kopyalanan"] == {"recete": 1, "fiyat": 1, "parametre": 13, "metin": 1, "havuz": 11, "ambalaj": 2, "hedef": 1, "kapasite": 1, "fire": 2}

    # reçete: yalnız aktif sürüm, versiyon 1, kaynak kopya, satırlar aynen (elle değerler, seviye, düğüm tipi dahil)
    rec = c.get(f"{A}/urunler/TEST/recete?senaryo={yeni}").json()
    assert rec["versiyon"] == 1 and rec["kaynak"] == "kopya" and len(rec["satirlar"]) == 2
    s1, s2 = rec["satirlar"]
    assert (s1["malzeme_kodu"], s1["miktar"], s1["fire_override"], s1["brut_miktar_elle"], s1["seviye"]) == ("KAV", "1", "0.02", "1.1", 1)
    assert (s2["malzeme_kodu"], s2["dugum_tipi"], s2["birim_fiyat_elle"], s2["seviye"]) == ("ARA", "ara_mamul", "12.5", 2)
    assert len(c.get(f"{A}/urunler/TEST/recete/versiyonlar?senaryo={yeni}").json()["kayitlar"]) == 1
    # fiyat: bugün geçerli tek kayıt (5.9, 2026-06-01); eski (4) ve gelecek (9) kopyalanmaz
    fy = c.get(f"{A}/malzemeler/KAV/fiyatlar?senaryo={yeni}").json()["kayitlar"]
    assert len(fy) == 1 and (fy[0]["fiyat"], fy[0]["gecerlilik_basi"], fy[0]["kaynak"], fy[0]["neden"]) == ("5.9", "2026-06-01", "kopya", "Kopya: A")
    # parametre: genel + ürün kapsamlı; metin
    pk = c.get(f"{A}/parametreler/kur.USD/gecmis?senaryo={yeni}").json()["kayitlar"]
    assert {(x["deger"], x["kapsam_tipi"], x["kapsam_id"], x["neden"]) for x in pk} == {("50", "genel", None, "Kopya: A"), ("51", "urun", uid, "Kopya: A")}
    mt = c.get(f"{A}/metin-parametreler?senaryo={yeni}").json()["kayitlar"]
    assert len(mt) == 1 and mt[0]["deger"] == "not 1" and mt[0]["neden"] == "Kopya: A"
    # gider: taban/çarpan/anahtar; ambalaj
    hv = {h["kod"]: h for h in c.get(f"{A}/gider-havuzlari?senaryo={yeni}").json()["kayitlar"]}
    assert hv["pazarlama"]["taban_tutar"] == "1000" and [x["deger"] for x in hv["pazarlama"]["carpanlar"]] == ["1.35", "1.3"] and D_(hv["pazarlama"]["toplam_tutar"]) == D_("1755")
    kaynak_mk = {h["kod"]: h for h in c.get(f"{A}/gider-havuzlari?senaryo={sid}").json()["kayitlar"]}["mal_kabul_iscilik"]
    assert hv["mal_kabul_iscilik"]["anahtarlar"] == kaynak_mk["anahtarlar"] and len(hv["mal_kabul_iscilik"]["anahtarlar"]) == 3
    amb = c.get(f"{A}/ambalaj-siniflari?senaryo={yeni}").json()["kayitlar"]
    assert [(a["ad"], a["hacim"], a["katsayi"]) for a in amb] == [("370 ml kavanoz", "370", "0.5"), ("720 ml kavanoz", "720", "0.75")]
    # üretim: hedef ve kapasite
    assert c.get(f"{A}/urunler/TEST/uretim-hedefi?senaryo={yeni}").json()["vardiya_uretim_adedi"] == "65000"
    kp = c.get(f"{A}/uretim-kapasitesi?senaryo={yeni}").json()["kayitlar"]
    assert len(kp) == 1 and kp[0]["urun_kodu"] == "TEST" and kp[0]["hedef_uretim"] == "150"
    # fire: aynı kapsamda yalnız geçerli olan
    fk = c.get(f"{A}/fire-kurallari?senaryo={yeni}").json()["kayitlar"]
    assert {(x["kapsam_tipi"], x["kapsam_deger"], x["oran"], x["gecerlilik_basi"], x["neden"]) for x in fk} == {
        ("malzeme", "KAV", "0.07", "2026-07-01", "Kopya: A"), ("tip", "0008-Ambalaj Malzeme", "0.01", "2026-06-01", "Kopya: A")}
    # kopyalanmayanlar: kayıtlı hesap, teklif, kilit, kaynak dosya
    assert c.get(f"{A}/urunler/TEST/hesaplar?senaryo={yeni}").json()["toplam"] == 0 and _say(oturum, m.MaliyetHesabi, yeni) == 0
    sen = oturum.get(m.Senaryo, yeni)
    assert sen.kilitli is False and sen.kaynak_dosya is None and sen.olusturan == "esma"
    # kopya aynı maliyeti verir (bugün geçerli girdiler birebir)
    a, b = (c.post(f"{A}/urunler/TEST/hesapla", json={"senaryo_id": x}).json() for x in (sid, yeni))
    assert a["toplamlar"]["maliyet_tl"] == b["toplamlar"]["maliyet_tl"] and a["notlar"] == b["notlar"] == ["not 1"]
    # günlük: tek senaryo kaydı
    k = c.get(f"{A}/degisiklikler?tablo=senaryo&kayit_id={yeni}").json()["kayitlar"]
    assert len(k) == 1 and k[0]["islem"] == "kopyala" and k[0]["kullanici"] == "esma"
    assert k[0]["yeni"]["kaynak_senaryo_id"] == sid and k[0]["yeni"]["_neden"] == "sezon açılışı" and k[0]["yeni"]["recete"] == 1
    gl = c.get(f"{A}/gunluk?senaryo={yeni}").json()["kayitlar"]
    assert any("kopyalanarak" in x["baslik"] for x in gl) and all(x["senaryo_id"] in (None, yeni) for x in gl)
    # listede ürün sayısı
    liste = {x["id"]: x for x in c.get(f"{A}/senaryolar").json()["kayitlar"]}
    assert liste[sid]["urun_sayisi"] == 1 and liste[yeni]["urun_sayisi"] == 1 and liste[yeni]["aciklama"] == "yeni sezon"


def test_kopya_secimli(istemci, oturum):
    c = istemci
    sid, _ = _zengin_kaynak(c, oturum)
    r = c.post(f"{A}/senaryolar/{sid}/kopyala", json=_govde("Yalnız reçete", {**HICBIRI, "receteler": True}))
    assert r.status_code == 201, r.text
    g = r.json()
    assert g["kopyalanan"] == {"recete": 1, "fiyat": 0, "parametre": 0, "metin": 0, "havuz": 0, "ambalaj": 0, "hedef": 0, "kapasite": 0, "fire": 0}
    assert g["urun_sayisi"] == 1
    for tablo in (m.MalzemeFiyati, m.ParametreDegeri, m.MetinParametre, m.GiderHavuzu, m.AmbalajSinifi, m.UretimHedefi, m.UretimKapasitesi, m.FireKurali):
        assert _say(oturum, tablo, g["id"]) == 0, tablo.__tablename__
    # dashboard üyeyi gösterir ama hesap girdisi eksik -> hata satırı (üretim hedefi yok)
    d = c.get(f"{A}/urunler?senaryo={g['id']}").json()
    assert d["toplam"] == 1 and d["kayitlar"][0]["kod"] == "TEST" and d["kayitlar"][0]["hata"]
    # seçimler açıkça gönderilir (eksik anahtar 422); hepsi False -> boş senaryo
    assert c.post(f"{A}/senaryolar/{sid}/kopyala", json=_govde("Eksik", {"receteler": True})).status_code == 422
    assert c.post(f"{A}/senaryolar/{sid}/kopyala", json={k: v for k, v in _govde("Eksik").items() if k != "kopyala"}).status_code == 422
    r2 = c.post(f"{A}/senaryolar/{sid}/kopyala", json=_govde("Boş", HICBIRI))
    assert r2.status_code == 201 and sum(r2.json()["kopyalanan"].values()) == 0 and r2.json()["urun_sayisi"] == 0
    assert c.get(f"{A}/urunler?senaryo={r2.json()['id']}").json()["toplam"] == 0
    r3 = c.post(f"{A}/senaryolar/{sid}/kopyala", json=_govde("Gider", {**HICBIRI, "gider": True, "uretim": True}))
    assert r3.json()["kopyalanan"]["havuz"] == 11 and r3.json()["kopyalanan"]["hedef"] == 1 and r3.json()["kopyalanan"]["recete"] == 0


def _dosya_uygulamasi(tmp_path):
    """Üretim yolu: dosya DB + istek başına oturum (commit/rollback `oturum_ver` ile aynı). Paylaşılan test oturumu rollback yapmadığından
    'tek işlem' garantisi ancak böyle doğrulanır."""
    from fastapi.testclient import TestClient
    e = motor_olustur(f"sqlite:///{tmp_path / 'fiyat.db'}"); Base.metadata.create_all(e)
    fab = oturum_fabrikasi(e)

    def oturum_ver_dosya():
        s = fab()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()
    with fab() as s:
        parametreleri_tohumla(s); s.commit()
    return TestClient(uygulama_olustur(oturum_ver_dosya), raise_server_exceptions=False), fab, e


def _kur_dosya(c, sid, fab):
    """_kur'un dosya DB sürümü: gider tohumu kendi oturumunda commit edilir (açık yazma işlemi API isteklerini kilitlemesin)."""
    for a, v in [("enflasyon", "0.25"), ("kur.USD", "50"), ("kur.EUR", "60"), ("faiz.TL", "0.4"), ("stok_ay.TL", "6"), ("faiz.USD", "0.06"),
                 ("stok_ay.USD", "6"), ("faiz.EUR", "0.06"), ("stok_ay.EUR", "6"), ("satis_kar", "0.2"), ("teklif_kar.1", "0.2"), ("vardiya_saati", "7.5")]:
        assert c.post(f"{A}/parametreler/{a}/degerler?senaryo={sid}", json={"deger": v, "gecerlilik_basi": "2026-06-01", "neden": "tohum"}).status_code == 201
    with fab() as s:
        gider_tohumla(s, sid); s.commit()
    assert c.post(f"{A}/malzemeler", json={"kod": "KAV", "ad": "Kavanoz", "tip": "0008-Ambalaj Malzeme", "birim": "AD", "para_birimi": "TL", "zs": "S"}).status_code == 201
    assert c.post(f"{A}/malzemeler/KAV/fiyatlar?senaryo={sid}", json={"onay": True, "fiyat": "5.9", "gecerlilik_basi": "2026-06-01", "neden": "bütçe"}).status_code == 201
    assert c.put(f"{A}/urunler/TEST", json={"ad": "Test", "ambalaj_hacmi": "370", "hat": "Niko", "taze_tursu_sinifi": "Turşu/Turşu", "suzme_kg": "0.18"}).status_code == 200
    assert c.put(f"{A}/urunler/TEST/uretim-hedefi?senaryo={sid}", json=HEDEF).status_code == 200
    assert c.post(f"{A}/urunler/TEST/recete?senaryo={sid}", json=[{"malzeme_kodu": "KAV", "ad": "Kavanoz", "miktar": "1", "birim": "AD", "fire_override": "0.02"}]).status_code == 201


def test_kopya_hata_geri_alir(tmp_path, monkeypatch):
    c, fab, e = _dosya_uygulamasi(tmp_path)
    try:
        sid = _senaryo(c)
        _kur_dosya(c, sid, fab)
        once = {x["id"] for x in c.get(f"{A}/senaryolar").json()["kayitlar"]}
        with fab() as s:
            recete_once, sezon_once = s.scalar(select(func.count()).select_from(m.Recete)), s.scalar(select(func.count()).select_from(m.Sezon))

        def patla(*a, **k):
            raise RuntimeError("havuz kopyası patladı")
        monkeypatch.setattr(ss, "_havuzlari_kopyala", patla)
        r = c.post(f"{A}/senaryolar/{sid}/kopyala", json=_govde("Yarım"))
        assert r.status_code == 500 and set(r.json()) == HATA and "patladı" not in r.text
        # tek işlem (istek geri alındı): senaryo, yeni sezon ve önceki adımlarda yazılan reçete/fiyat/parametre kalmaz
        assert {x["id"] for x in c.get(f"{A}/senaryolar").json()["kayitlar"]} == once
        with fab() as s:
            assert s.scalar(select(func.count()).select_from(m.Recete)) == recete_once
            assert s.scalar(select(func.count()).select_from(m.Sezon)) == sezon_once and s.scalar(select(m.Sezon.id).where(m.Sezon.ad == "2027-2028")) is None
            assert s.scalar(select(func.count()).select_from(m.Senaryo).where(m.Senaryo.ad == "Yarım")) == 0
        monkeypatch.undo()
        r = c.post(f"{A}/senaryolar/{sid}/kopyala", json=_govde("Tam"))
        assert r.status_code == 201 and r.json()["kopyalanan"]["havuz"] == 11
        with fab() as s:   # başarılı kopya kalıcı (yeni oturumdan görünür)
            assert s.scalar(select(func.count()).select_from(m.Senaryo).where(m.Senaryo.ad == "Tam")) == 1
            assert s.scalar(select(func.count()).select_from(m.GiderHavuzu).where(m.GiderHavuzu.senaryo_id == r.json()["id"])) == 11
        # aynı sezona kopya da olur (sezon yeniden açılmaz)
        r2 = c.post(f"{A}/senaryolar/{sid}/kopyala", json={**_govde("Aynı sezon", HICBIRI), "sezon_ad": "2026-2027"})
        assert r2.status_code == 201 and r2.json()["sezon_ad"] == "2026-2027"
        with fab() as s:
            assert s.scalar(select(func.count()).select_from(m.Sezon).where(m.Sezon.ad == "2026-2027")) == 1
    finally:
        e.dispose()


def test_kopya_pasif_urun_tasinmaz(istemci, oturum):
    c = istemci
    sid = _senaryo(c); _kur(c, sid, oturum)
    assert c.put(f"{A}/urunler/PASIF", json={"ad": "Pasif", **KART}).status_code == 200
    assert c.put(f"{A}/urunler/PASIF/uretim-hedefi?senaryo={sid}", json=HEDEF).status_code == 200
    assert c.post(f"{A}/urunler/PASIF/recete?senaryo={sid}", json=[{"malzeme_kodu": "KAV", "ad": "Kavanoz", "miktar": "1", "birim": "AD"}]).status_code == 201
    assert c.put(f"{A}/uretim-kapasitesi/PASIF?senaryo={sid}", json={**KAP, "neden": "k", "urun_ad": "Pasif"}).status_code == 200
    assert c.put(f"{A}/uretim-kapasitesi/KARTSIZ?senaryo={sid}", json={**KAP, "neden": "k", "urun_ad": "Yalnız sayfa satırı"}).status_code == 200
    assert c.patch(f"{A}/urunler/PASIF/pasif").status_code == 200
    g = c.post(f"{A}/senaryolar/{sid}/kopyala", json=_govde()).json()
    assert (g["kopyalanan"]["recete"], g["kopyalanan"]["hedef"], g["kopyalanan"]["kapasite"], g["urun_sayisi"]) == (1, 1, 1, 1)   # PASIF yok; KARTSIZ satırı kalır
    assert [k["urun_kodu"] for k in c.get(f"{A}/uretim-kapasitesi?senaryo={g['id']}").json()["kayitlar"]] == ["KARTSIZ"]
    assert c.get(f"{A}/urunler/PASIF/recete?senaryo={g['id']}").json()["versiyon"] == 0


def test_kopya_dogrulama(istemci, oturum):
    c = istemci
    sid = _senaryo(c)
    assert c.post(f"{A}/senaryolar/999/kopyala", json=_govde()).status_code == 404
    r = c.post(f"{A}/senaryolar/{sid}/kopyala", json={**_govde(), "neden": ""})
    assert r.status_code == 422 and r.json()["hata"] == "dogrulama"
    assert c.post(f"{A}/senaryolar/{sid}/kopyala", json={**_govde(), "sezon_ad": "2027"}).status_code == 422
    assert c.post(f"{A}/senaryolar/{sid}/kopyala", json={**_govde(), "tur": "baska"}).status_code == 422
    with pytest.raises(DogrulamaHatasi):
        ss.kopyala(oturum, sid, "2027-2028", "X", "fiyat_calismasi", None, {"bilinmeyen": True}, "n")
    assert c.get(f"{A}/senaryolar").json()["toplam"] == 1


# ------------------------------------------------------------------ güncelleme
def test_patch_senaryo(istemci, oturum):
    c = istemci
    sid = _senaryo(c)
    r = c.patch(f"{A}/senaryolar/{sid}", json={"ad": "Berrak 2", "aciklama": "revize", "neden": "ad düzeltme"}, headers={"X-Kullanici": "esma"})
    assert r.status_code == 200, r.text
    assert r.json()["ad"] == "Berrak 2" and r.json()["aciklama"] == "revize" and r.json()["sezon_ad"] == "2026-2027" and r.json()["urun_sayisi"] == 0
    r = c.patch(f"{A}/senaryolar/{sid}", json={"sezon_ad": "2027-2028", "neden": "sezon"})   # yalnız gönderilen alan değişir
    assert r.status_code == 200 and r.json()["sezon_ad"] == "2027-2028" and r.json()["ad"] == "Berrak 2" and r.json()["aciklama"] == "revize"
    k = c.get(f"{A}/degisiklikler?tablo=senaryo&kayit_id={sid}").json()["kayitlar"]
    assert [x["islem"] for x in k] == ["guncelle", "guncelle"]
    assert k[1]["eski"] == {"ad": "A", "aciklama": None} and k[1]["yeni"] == {"ad": "Berrak 2", "aciklama": "revize", "_neden": "ad düzeltme"} and k[1]["kullanici"] == "esma"
    assert k[0]["eski"] == {"sezon_ad": "2026-2027"} and k[0]["yeni"]["sezon_ad"] == "2027-2028"
    # açıklama null ile temizlenir; değişiklik yoksa kayıt açılmaz
    r = c.patch(f"{A}/senaryolar/{sid}", json={"aciklama": None, "neden": "temizle"})
    assert r.status_code == 200 and r.json()["aciklama"] is None and oturum.get(m.Senaryo, sid).aciklama is None
    assert c.patch(f"{A}/senaryolar/{sid}", json={"ad": "Berrak 2", "neden": "aynı"}).status_code == 200
    assert c.get(f"{A}/degisiklikler?tablo=senaryo&kayit_id={sid}").json()["toplam"] == 3
    assert c.post(f"{A}/senaryolar", json={"sezon_ad": "2026-2027", "tur": "fiyat_calismasi", "ad": "   "}).status_code == 422   # boş ad
    # doğrulama
    assert c.patch(f"{A}/senaryolar/{sid}", json={"ad": "X"}).status_code == 422          # neden zorunlu
    assert c.patch(f"{A}/senaryolar/{sid}", json={"ad": "  ", "neden": "n"}).status_code == 422
    assert c.patch(f"{A}/senaryolar/{sid}", json={"sezon_ad": "kötü", "neden": "n"}).status_code == 422
    assert c.patch(f"{A}/senaryolar/999", json={"ad": "X", "neden": "n"}).status_code == 404
    # kilitli -> 409
    assert c.post(f"{A}/senaryolar/{sid}/kilitle", json={"neden": "kapandı"}).status_code == 200
    r = c.patch(f"{A}/senaryolar/{sid}", json={"ad": "Y", "neden": "n"})
    assert r.status_code == 409 and set(r.json()) == HATA and r.json()["hata"] == "kilitli"
    assert oturum.get(m.Senaryo, sid).ad == "Berrak 2"


# ------------------------------------------------------------------ silme
def test_delete_senaryo_204_ve_tum_satirlar_gider(istemci, oturum):
    c = istemci
    sid, _ = _zengin_kaynak(c, oturum)
    kopya = c.post(f"{A}/senaryolar/{sid}/kopyala", json=_govde()).json()["id"]
    assert c.put(f"{A}/gider-havuzlari/yonetim?senaryo={kopya}", json={"ad": "Yönetim", "neden": "revize", "toplam_tutar": "1", "baz_tipi": "adet"}).status_code == 200
    tablolar = (m.Recete, m.MalzemeFiyati, m.ParametreDegeri, m.MetinParametre, m.GiderHavuzu, m.AmbalajSinifi, m.UretimHedefi, m.UretimKapasitesi, m.FireKurali)
    assert all(_say(oturum, t, kopya) > 0 for t in tablolar)
    havuz_idleri = list(oturum.scalars(select(m.GiderHavuzu.id).where(m.GiderHavuzu.senaryo_id == kopya)))
    assert oturum.scalar(select(func.count()).select_from(m.DagitimAnahtari).where(m.DagitimAnahtari.gider_havuzu_id.in_(havuz_idleri))) > 0
    assert c.get(f"{A}/gunluk?senaryo={kopya}").json()["toplam"] >= 2   # kopya + havuz güncelleme

    r = c.delete(f"{A}/senaryolar/{kopya}", headers={"X-Kullanici": "esma"})
    assert r.status_code == 204 and r.content == b""
    assert kopya not in {x["id"] for x in c.get(f"{A}/senaryolar").json()["kayitlar"]}
    # kim/ne zaman: tek 'sil' kaydı kalır, genel günlükte görünür; kaynak senaryo süzgecinde görünmez
    k = c.get(f"{A}/degisiklikler?tablo=senaryo&kayit_id={kopya}").json()["kayitlar"]
    assert len(k) == 1 and k[0]["islem"] == "sil" and k[0]["kullanici"] == "esma" and k[0]["eski"] is None
    assert k[0]["yeni"]["ad"] == "Kopya" and k[0]["yeni"]["sezon_ad"] == "2027-2028" and k[0]["yeni"]["ayrinti"]["recete"] == 1 and k[0]["yeni"]["silinen_satir"] > 10
    gl = c.get(f"{A}/gunluk").json()["kayitlar"]
    satir = next(x for x in gl if x["baslik"] == "Senaryo silindi")
    assert satir["senaryo_id"] == kopya and satir["kullanici"] == "esma" and satir["yeni"].startswith("ad: Kopya, sezon_ad: 2027-2028")
    assert not any(x["senaryo_id"] == kopya for x in c.get(f"{A}/gunluk?senaryo={sid}").json()["kayitlar"])
    assert c.get(f"{A}/gunluk/ozet").status_code == 200
    assert c.get(f"{A}/urunler?senaryo={kopya}").status_code == 404
    for t in tablolar:
        assert _say(oturum, t, kopya) == 0, t.__tablename__
    assert oturum.scalar(select(func.count()).select_from(m.DagitimAnahtari).where(m.DagitimAnahtari.gider_havuzu_id.in_(havuz_idleri))) == 0
    assert oturum.scalar(select(func.count()).select_from(m.ReceteSatiri).join(m.Recete, m.Recete.id == m.ReceteSatiri.recete_id)) == \
        oturum.scalar(select(func.count()).select_from(m.ReceteSatiri))   # öksüz reçete satırı kalmadı
    assert [x.islem for x in oturum.scalars(select(m.DegisiklikKaydi).where(m.DegisiklikKaydi.tablo == "senaryo", m.DegisiklikKaydi.kayit_id == kopya))] == ["sil"]
    assert oturum.scalar(select(func.count()).select_from(m.DegisiklikKaydi).where(m.DegisiklikKaydi.tablo == "gider_havuzu", m.DegisiklikKaydi.kayit_id.in_(havuz_idleri))) == 0
    # kaynak senaryo ve ürün kartları/malzemeler dokunulmadı
    assert _say(oturum, m.Recete, sid) == 2 and c.get(f"{A}/urunler/TEST").status_code == 200 and c.get(f"{A}/malzemeler?senaryo={sid}").json()["toplam"] >= 1
    assert c.get(f"{A}/urunler?senaryo={sid}").json()["toplam"] == 1
    # son senaryo da silinebilir (boş uygulama durumu)
    bos = _senaryo(c)
    assert c.delete(f"{A}/senaryolar/{sid}").status_code == 409   # kayıtlı hesabı var
    assert c.delete(f"{A}/senaryolar/{bos}").status_code == 204
    assert c.delete(f"{A}/senaryolar/{bos}").status_code == 404


def test_delete_409_hesap_var_ve_kilitli(istemci, oturum):
    c = istemci
    sid = _senaryo(c); _kur(c, sid, oturum)
    assert c.post(f"{A}/urunler/TEST/hesaplar", json={"senaryo_id": sid, "tarih": "2026-10-21"}).status_code == 201
    r = c.delete(f"{A}/senaryolar/{sid}")
    assert r.status_code == 409 and set(r.json()) == HATA and r.json()["hata"] == "catisma" and "kayıtlı hesap" in r.json()["mesaj"]
    assert r.json()["alanlar"]["hesap_sayisi"] == 1
    bos = _senaryo(c)
    assert c.post(f"{A}/senaryolar/{bos}/kilitle", json={"neden": "kapandı"}).status_code == 200
    r = c.delete(f"{A}/senaryolar/{bos}")
    assert r.status_code == 409 and r.json()["hata"] == "catisma" and "kilit" in r.json()["mesaj"]
    assert {x["id"] for x in c.get(f"{A}/senaryolar").json()["kayitlar"]} == {sid, bos}
    with pytest.raises(CatismaHatasi):
        ss.sil(oturum, sid)


def test_delete_dosya_veritabaninda_yedek_alir(tmp_path):
    url = f"sqlite:///{tmp_path / 'fiyat.db'}"
    e = motor_olustur(url); Base.metadata.create_all(e)
    s = oturum_fabrikasi(e)()
    try:
        sen = hs.senaryo_olustur(s, "2026-2027", "fiyat_calismasi", "Berrak / Deneme 2026")
        s.commit()
        sonuc = ss.sil(s, sen.id)
        s.commit()
        yedek = tmp_path / "yedek" / f"{date.today().strftime('%m-%d-%Y')}-silme-oncesi-Berrak-Deneme-2026.db"
        assert yedek.exists() and sonuc["yedek"] == str(yedek)
        import sqlite3
        assert sqlite3.connect(str(yedek)).execute("select count(*) from senaryo").fetchone()[0] == 1   # yedek silme öncesi durumu taşır
        assert s.scalar(select(func.count()).select_from(m.Senaryo)) == 0
        sen2 = hs.senaryo_olustur(s, "2026-2027", "fiyat_calismasi", "Berrak / Deneme 2026"); s.commit()
        assert ss.sil(s, sen2.id)["yedek"].endswith("-silme-oncesi-Berrak-Deneme-2026-2.db")   # aynı gün aynı ad: üzerine yazmaz
    finally:
        s.close(); e.dispose()


def test_bellek_ici_db_yedek_atlanir(istemci, oturum):
    sid = _senaryo(istemci)
    assert ss.sil(oturum, sid)["yedek"] is None


# ------------------------------------------------------------------ üyelik
def test_uyelik_suzgeci_ve_tum(istemci, oturum):
    c = istemci
    sid = _senaryo(c); _kur(c, sid, oturum)
    assert c.put(f"{A}/urunler/BOS", json={"ad": "Bos", **KART}).status_code == 200                    # reçetesiz, hedefsiz
    assert c.put(f"{A}/urunler/HEDEFLI", json={"ad": "Hedefli", **KART}).status_code == 200            # hedefi var, reçetesi yok
    assert c.put(f"{A}/urunler/HEDEFLI/uretim-hedefi?senaryo={sid}", json=HEDEF).status_code == 200
    assert ss.uye_urun_kodlari(oturum, sid) == {"TEST"}
    d = c.get(f"{A}/urunler?senaryo={sid}").json()
    assert [x["kod"] for x in d["kayitlar"]] == ["TEST"] and d["toplam"] == 1
    t = c.get(f"{A}/urunler?senaryo={sid}&tum=1").json()
    assert [x["kod"] for x in t["kayitlar"]] == ["BOS", "HEDEFLI", "TEST"] and t["toplam"] == 3
    satir = {x["kod"]: x for x in t["kayitlar"]}
    assert "reçete yok" in satir["HEDEFLI"]["hata"] and "üretim hedefi yok" in satir["BOS"]["hata"] and satir["TEST"]["hata"] is None
    # uyarılar: üye olmayanlar hesaba girmez (hata satırı zaten uyarı üretmez), tum=1 da aynı sonucu verir
    assert c.get(f"{A}/uyarilar?senaryo={sid}").json() == c.get(f"{A}/uyarilar?senaryo={sid}&tum=1").json()
    # dışa aktarım: üyeler; tum=1 hepsi
    from io import BytesIO
    from openpyxl import load_workbook
    ws = load_workbook(BytesIO(c.get(f"{A}/disa-aktar/urunler.xlsx?senaryo={sid}").content)).active
    assert ws.max_row == 2 and ws["A2"].value == "TEST"
    ws = load_workbook(BytesIO(c.get(f"{A}/disa-aktar/urunler.xlsx?senaryo={sid}&tum=1").content)).active
    assert ws.max_row == 4
    # pasif ürün üye sayılmaz
    assert c.patch(f"{A}/urunler/TEST/pasif").status_code == 200
    assert ss.uye_urun_kodlari(oturum, sid) == set() and ss.uye_urun_kodlari(oturum, sid, aktif=False) == {"TEST"}
    assert c.get(f"{A}/senaryolar").json()["kayitlar"][0]["urun_sayisi"] == 0
    # reçetesiz ürüne hesap: anlamlı doğrulama hatası
    r = c.post(f"{A}/urunler/HEDEFLI/hesapla", json={"senaryo_id": sid})
    assert r.status_code == 422 and r.json()["hata"] == "dogrulama" and "reçete yok" in r.json()["mesaj"] and r.json()["alanlar"]["urun"] == "HEDEFLI"
    assert r.json()["kod"] is None


def test_hesap_hatalarinda_kararli_kod(istemci, oturum):
    """B1: arayüz mesaj metnine değil koda bakar: hedef yoksa 'hedef_yok', zorunlu parametre yoksa 'parametre_eksik'."""
    from datetime import date
    from backend.servisler import parametre_servisi as ps
    from backend.servisler.hatalar import DogrulamaHatasi
    c = istemci
    sid = _senaryo(c); _kur(c, sid, oturum)
    assert c.put(f"{A}/urunler/BOS", json={"ad": "Bos", **KART}).status_code == 200
    r = c.post(f"{A}/urunler/BOS/hesapla", json={"senaryo_id": sid})
    assert r.status_code == 404 and (r.json()["hata"], r.json()["kod"]) == ("bulunamadi", "hedef_yok")
    bos = c.post(f"{A}/senaryolar", json={"sezon_ad": "2027-2028", "tur": "fiyat_calismasi", "ad": "Boş"}).json()["id"]   # değersiz senaryo
    try:
        ps.gecerli_parametreler(oturum, bos, date(2026, 10, 21)); assert False, "hata bekleniyordu"
    except DogrulamaHatasi as e:
        assert e.kod == "parametre_eksik" and e.alanlar["eksik"]


def test_onbellek_anahtari_tum_ile_ayrisir(istemci, oturum):
    c = istemci
    sid = _senaryo(c); _kur(c, sid, oturum)
    assert c.put(f"{A}/urunler/BOS", json={"ad": "Bos", **KART}).status_code == 200
    u = f"{A}/urunler?senaryo={sid}&tarih=2026-10-21"
    r1 = c.get(u); assert r1.headers["X-Onbellek"] == "hesap" and r1.json()["toplam"] == 1
    r2 = c.get(u + "&tum=1"); assert r2.headers["X-Onbellek"] == "hesap" and r2.json()["toplam"] == 2   # ayrı anahtar: isabet değil
    r3 = c.get(u); assert r3.headers["X-Onbellek"] == "isabet" and r3.json()["toplam"] == 1
    r4 = c.get(u + "&tum=true"); assert r4.headers["X-Onbellek"] == "isabet" and r4.json()["toplam"] == 2
    assert c.get(f"{A}/uyarilar?senaryo={sid}&tarih=2026-10-21").headers["X-Onbellek"] == "isabet"
    assert c.get(f"{A}/uyarilar?senaryo={sid}&tarih=2026-10-21&tum=1").headers["X-Onbellek"] == "isabet"
    assert c.get(u + "&tum=0").headers["X-Onbellek"] == "isabet" and c.get(u + "&tum=0").json()["toplam"] == 1


def test_senaryoda_ve_bos_recete(istemci, oturum):
    c = istemci
    sid = _senaryo(c); _kur(c, sid, oturum)
    assert c.put(f"{A}/urunler/BOS", json={"ad": "Bos", **KART}).status_code == 200
    g = c.get(f"{A}/urunler/BOS?senaryo={sid}").json()
    assert g["senaryoda"] is False and g["uretim_hedefi"] is None and g["kod"] == "BOS"
    assert c.get(f"{A}/urunler/TEST?senaryo={sid}").json()["senaryoda"] is True
    assert "senaryoda" not in c.get(f"{A}/urunler/TEST").json()   # senaryosuz istekte alan yok
    assert c.get(f"{A}/urunler/BOS?senaryo=999").status_code == 404
    # boş reçete: 404 değil
    r = c.get(f"{A}/urunler/BOS/recete?senaryo={sid}")
    assert r.status_code == 200 and r.json() == {"id": None, "versiyon": 0, "kaynak": None, "satirlar": []}
    assert c.get(f"{A}/urunler/BOS/recete/versiyonlar?senaryo={sid}").json()["toplam"] == 0
    assert c.get(f"{A}/urunler/YOK/recete?senaryo={sid}").status_code == 404   # ürün yoksa yine 404
    # ilk sürüm açılınca üye olur
    assert c.post(f"{A}/urunler/BOS/recete?senaryo={sid}", json=[{"malzeme_kodu": "KAV", "ad": "Kavanoz", "miktar": "1", "birim": "AD"}]).status_code == 201
    r = c.get(f"{A}/urunler/BOS/recete?senaryo={sid}").json()
    assert r["versiyon"] == 1 and r["kaynak"] == "elle" and len(r["satirlar"]) == 1
    assert c.get(f"{A}/urunler/BOS?senaryo={sid}").json()["senaryoda"] is True
    assert [x["kod"] for x in c.get(f"{A}/urunler?senaryo={sid}").json()["kayitlar"]] == ["BOS", "TEST"]
    assert c.get(f"{A}/senaryolar").json()["kayitlar"][0]["urun_sayisi"] == 2


def test_bos_senaryo_parametre_tanimlari_global(istemci, oturum):
    """POST /senaryolar: parametre tanımları senaryodan bağımsız (tohum); değer yok -> hesap 'zorunlu parametre eksik' verir, dashboard boş."""
    c = istemci
    sid = _senaryo(c)
    assert oturum.scalar(select(func.count()).select_from(m.Parametre)) > 0 and _say(oturum, m.ParametreDegeri, sid) == 0
    assert c.get(f"{A}/urunler?senaryo={sid}").json() == {"kayitlar": [], "toplam": 0, "enflasyon_altinda_toplam": 0}
    assert c.get(f"{A}/karsilastirma/aileler?senaryo={sid}").json() == []
    assert c.get(f"{A}/senaryolar").json()["kayitlar"][0]["urun_sayisi"] == 0
