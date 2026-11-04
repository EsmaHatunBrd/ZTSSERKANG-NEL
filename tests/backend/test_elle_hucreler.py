"""Elle hücreler: gider satırlarında formül yerine elle yazılan I/K/M/P ve reçete satırında elle Z/S + para birimi.
Önizleme (override), tek Kaydet, üretim hedefi çıktısı, değişiklik kaydı, reçete sürümü ve senaryo kopyası."""
from decimal import Decimal as D_
from backend.depo import modeller as m
from tests.backend.test_faz4c_kaydet import _kaydet, istemci, sid  # noqa: F401 (pytest fikstürleri)

API = "/api/v1"


def _satir(hesap: dict, kod: str) -> dict:
    return next(x for x in hesap["satirlar"] if x["kod"] == kod)


def _hesapla(c, sid, override=None):
    r = c.post(f"{API}/urunler/TEST/hesapla", json={"senaryo_id": sid, "tarih": "2026-10-21", "override": override})
    assert r.status_code == 200, r.text
    return r.json()


def test_onizleme_elle_gider_hucresi_kaydetmeden_hesaba_girer(istemci, sid):
    once = _hesapla(istemci, sid)
    assert _satir(once, "dolum_iscilik")["elle_alanlar"] == []
    h = _hesapla(istemci, sid, {"gider_elle": {"dolum_iscilik": {"tutar": "20"}, "elektrik": {"birim_fiyat": "0"}}})
    assert D_(_satir(h, "dolum_iscilik")["tutar"]) == 20 and _satir(h, "dolum_iscilik")["elle_alanlar"] == ["tutar"]
    assert D_(_satir(h, "elektrik")["tutar"]) == 0 and _satir(h, "elektrik")["elle_alanlar"] == ["birim_fiyat"]
    assert _satir(_hesapla(istemci, sid), "dolum_iscilik")["elle_alanlar"] == []   # kalıcı değil


def test_kaydet_elle_gider_yazar_degisiklik_kaydi_acar_ve_formule_donulur(istemci, oturum, sid):
    r = _kaydet(istemci, sid, gider_elle={"diger_gug": {"tutar": "10"}})
    assert r.status_code == 200, r.text
    assert r.json()["yazilan"]["hedef"] == 1
    assert D_(_satir(r.json()["hesap"], "diger_gug")["tutar"]) == 10
    hedef = istemci.get(f"{API}/urunler/TEST", params={"senaryo": sid}).json()["uretim_hedefi"]
    assert hedef["gider_elle"] == {"diger_gug": {"tutar": "10"}}
    kayit = oturum.query(m.DegisiklikKaydi).filter_by(tablo="uretim_hedefi", kullanici="esma").one()
    assert kayit.eski["gider_elle"] is None and kayit.yeni["gider_elle"] == {"diger_gug": {"tutar": "10"}}
    assert _satir(_hesapla(istemci, sid), "diger_gug")["elle_alanlar"] == ["tutar"]   # artık kayıtlı
    # Başka alan kaydı elle hücrelere dokunmaz; gider_elle={} hepsini formüle döndürür
    assert _kaydet(istemci, sid, hesabi_kaydet=False, parametreler=[{"anahtar": "kur.USD", "deger": "51"}]).status_code == 200
    assert _satir(_hesapla(istemci, sid), "diger_gug")["elle_alanlar"] == ["tutar"]
    assert _kaydet(istemci, sid, gider_elle={}).status_code == 200
    assert _satir(_hesapla(istemci, sid), "diger_gug")["elle_alanlar"] == []


def test_bilinmeyen_kalem_ve_negatif_deger_reddedilir(istemci, sid):
    assert _kaydet(istemci, sid, gider_elle={"yok_boyle": {"tutar": "1"}}).status_code == 422
    assert _kaydet(istemci, sid, gider_elle={"elektrik": {"tutar": "-1"}}).status_code == 422
    assert _kaydet(istemci, sid, gider_elle={"elektrik": {"oran": "1"}}).status_code == 422


def test_recete_elle_zs_ve_para_birimi_kaydedilir_ve_hesapta_gorunur(istemci, sid):
    satir = {"malzeme_kodu": "KAV", "ad": "Kavanoz", "miktar": "1", "birim": "AD", "birim_fiyat_elle": "2", "zs_elle": "S", "para_birimi_elle": "usd"}
    assert _kaydet(istemci, sid, recete=[satir], hesabi_kaydet=False).status_code == 200
    rc = istemci.get(f"{API}/urunler/TEST/recete", params={"senaryo": sid}).json()["satirlar"][0]
    assert (rc["zs_elle"], rc["para_birimi_elle"]) == ("S", "USD")
    h = _satir(_hesapla(istemci, sid), "KAV")
    assert (h["zs"], h["zs_elle"], h["doviz"], h["doviz_elle"]) == ("S", True, "USD", True)


def test_senaryo_kopyasi_elle_hucreleri_tasir(istemci, oturum, sid):
    from tests.backend.test_faz5c_senaryo import _govde
    satir = {"malzeme_kodu": "KAV", "ad": "Kavanoz", "miktar": "1", "birim": "AD", "zs_elle": "Z"}
    assert _kaydet(istemci, sid, gider_elle={"amortisman": {"miktar": "0"}}, recete=[satir], hesabi_kaydet=False).status_code == 200
    r = istemci.post(f"{API}/senaryolar/{sid}/kopyala", json=_govde())
    assert r.status_code == 201, r.text
    yeni = r.json()["id"]
    assert oturum.query(m.UretimHedefi).filter_by(senaryo_id=yeni).one().gider_elle == {"amortisman": {"miktar": "0"}}
    rc = oturum.query(m.Recete).filter_by(senaryo_id=yeni, aktif=True).one()
    assert rc.satirlar[0].zs_elle == "Z"
