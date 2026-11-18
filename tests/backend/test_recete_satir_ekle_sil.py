"""D3: ürün ekranında reçeteye satır ekle/sil (taslak hesap + atomik Kaydet) ve reçete kaydında zorunlu neden (günlük)."""
from decimal import Decimal as D_
import pytest
from backend.depo import modeller as m
from tests.backend.test_faz4c_kaydet import API, _kaydet, istemci, sid  # noqa: F401 (fikstürler)

KAP = {"kod": "KAP", "ad": "Kapak", "tip": "0008-Ambalaj Malzeme", "birim": "AD", "para_birimi": "TL", "zs": "S"}


def _kapak(c, sid_):
    assert c.post(f"{API}/malzemeler", json=KAP).status_code == 201
    assert c.post(f"{API}/malzemeler/KAP/fiyatlar?senaryo={sid_}",
                  json={"onay": True, "fiyat": "2", "gecerlilik_basi": "2026-06-01", "neden": "bütçe"}).status_code == 201


def _iki_satir(c, sid_):
    """TEST reçetesi: 1 KAV (fire 0.02), 2 KAP (fire 0.1)."""
    _kapak(c, sid_)
    r = c.post(f"{API}/urunler/TEST/recete?senaryo={sid_}", json={"neden": "kapak eklendi", "satirlar": [
        {"malzeme_kodu": "KAV", "ad": "Kavanoz", "miktar": "1", "birim": "AD", "fire_override": "0.02"},
        {"malzeme_kodu": "KAP", "ad": "Kapak", "miktar": "1", "birim": "AD", "fire_override": "0.1"}]})
    assert r.status_code == 201, r.text


def _hesapla(c, sid_, **override):
    r = c.post(f"{API}/urunler/TEST/hesapla", json={"senaryo_id": sid_, "tarih": "2026-10-21", "override": override or None})
    return r


def _malzeme(g):
    return [s for s in g["satirlar"] if s["grup"] == "malzeme"]


# ---------------------------------------------------------------- taslak hesap (override)
def test_taslakta_silinen_satir_hesaptan_duser_siralar_korunur(istemci, sid):
    _iki_satir(istemci, sid)
    taban = _hesapla(istemci, sid).json()
    r = _hesapla(istemci, sid, silinen_satirlar=[1])
    assert r.status_code == 200, r.text
    g = r.json()
    assert [(s["kod"], s["sira"]) for s in _malzeme(g)] == [("KAP", 2)]   # özgün sıra (2) korunur
    kav = _malzeme(taban)[0]
    assert abs(D_(g["toplamlar"]["malzeme"]) - (D_(taban["toplamlar"]["malzeme"]) - D_(kav["tutar"]))) < D_("1e-20")


def test_taslakta_eklenen_satir_sona_girer_fire_kuraldan_ya_da_satirdan(istemci, sid):
    _kapak(istemci, sid)
    r = _hesapla(istemci, sid, eklenen_satirlar=[{"malzeme_kodu": "KAP", "ad": "Kapak", "miktar": "2", "birim": "AD", "fire_override": "0.2"}])
    assert r.status_code == 200, r.text
    m_ = _malzeme(r.json())
    assert [(s["kod"], s["sira"], s["fire_kaynagi"]) for s in m_] == [("KAV", 1, "satir"), ("KAP", 2, "satir")]
    # brüt = 2 / (1 - 0,2) = 2,5 ; tutar = 2,5 x 2 x (1 + enflasyon 0,25)
    assert D_(m_[1]["brut_miktar"]) == D_("2.5")
    assert abs(D_(m_[1]["tutar"]) - D_("2.5") * 2 * D_("1.25")) < D_("1e-9")
    # fire verilmezse kural (yoksa 0) uygulanır
    r2 = _hesapla(istemci, sid, eklenen_satirlar=[{"malzeme_kodu": "KAP", "ad": "Kapak", "miktar": "1"}])
    assert _malzeme(r2.json())[1]["fire_kaynagi"] in ("yok", "tip:0008-Ambalaj Malzeme", "malzeme")


def test_satir_override_ozgun_siraya_uygulanir_silme_ile_birlikte(istemci, sid):
    _iki_satir(istemci, sid)
    r = _hesapla(istemci, sid, silinen_satirlar=[1], satirlar={"2": {"miktar": "3"}},
                 eklenen_satirlar=[{"malzeme_kodu": "KAV", "ad": "Kavanoz", "miktar": "1"}])
    assert r.status_code == 200, r.text
    m_ = _malzeme(r.json())
    assert [(s["kod"], s["sira"]) for s in m_] == [("KAP", 2), ("KAV", 3)]
    assert D_(m_[0]["miktar"]) == D_(3)


@pytest.mark.parametrize("override, kod", [
    ({"silinen_satirlar": [5]}, 422),
    ({"silinen_satirlar": [0]}, 422),
    ({"silinen_satirlar": [1]}, 422),   # tek satırlı reçetede son satır silinemez
])
def test_gecersiz_yapi_422(istemci, sid, override, kod):
    assert _hesapla(istemci, sid, **override).status_code == kod


def test_bos_yapi_alanlari_snapshot_bicimini_degistirmez(istemci, oturum, sid):
    r = istemci.post(f"{API}/urunler/TEST/hesaplar", json={"senaryo_id": sid, "tarih": "2026-10-21",
                                                          "override": {"parametreler": {"kur.USD": "51"}}})
    assert r.status_code == 201, r.text
    ov = oturum.get(m.MaliyetHesabi, r.json()["id"]).girdi_snapshot["override"]
    assert "silinen_satirlar" not in ov and "eklenen_satirlar" not in ov


# ---------------------------------------------------------------- Kaydet (atomik): tam liste yeni sürüm + hesap
def test_kaydet_satir_ekle_sil_yeni_surum_ve_hesap_canli_ile_ayni(istemci, oturum, sid):
    _iki_satir(istemci, sid)
    canli = _hesapla(istemci, sid, silinen_satirlar=[2], eklenen_satirlar=[{"malzeme_kodu": "KAP", "ad": "Kapak", "miktar": "2", "birim": "AD"}]).json()
    r = _kaydet(istemci, sid, recete=[{"malzeme_kodu": "KAV", "ad": "Kavanoz", "miktar": "1", "birim": "AD", "fire_override": "0.02"},
                                      {"malzeme_kodu": "KAP", "ad": "Kapak", "miktar": "2", "birim": "AD"}])
    assert r.status_code == 200, r.text
    g = r.json()
    assert g["yazilan"]["recete"] == 2 and g["hesap_id"] is not None
    assert g["hesap"]["toplamlar"]["maliyet_tl"] == canli["toplamlar"]["maliyet_tl"]
    u = oturum.query(m.Urun).filter_by(kod="TEST").one()
    aktif = oturum.query(m.Recete).filter_by(urun_id=u.id, aktif=True).one()
    assert aktif.kaynak == "ekran" and aktif.neden == "ekrandan düzeltme"
    assert [(x.sira, x.malzeme_kodu, x.miktar) for x in aktif.satirlar] == [(1, "KAV", D_(1)), (2, "KAP", D_(2))]


# ---------------------------------------------------------------- reçete nedeni
def test_recete_ekle_nedenli_govde_ve_gunluk(istemci, oturum, sid):
    r = istemci.post(f"{API}/urunler/TEST/recete?senaryo={sid}", headers={"X-Kullanici": "esma"},
                     json={"neden": "  Ekim revizyonu ", "satirlar": [{"malzeme_kodu": "KAV", "ad": "Kavanoz", "miktar": "2", "birim": "AD"}]})
    assert r.status_code == 201, r.text
    rc = oturum.get(m.Recete, r.json()["id"])
    assert rc.neden == "Ekim revizyonu" and rc.kaynak == "elle"
    gunluk = istemci.get(f"{API}/gunluk", params={"senaryo": sid, "tur": "recete"}).json()["kayitlar"]
    satir = next(x for x in gunluk if x["id"] == f"recete:{rc.id}")
    assert satir["neden"] == "Ekim revizyonu" and satir["kullanici"] == "esma"


@pytest.mark.parametrize("govde", [
    {"satirlar": [{"malzeme_kodu": "KAV", "miktar": "1"}]},                      # neden yok
    {"neden": "   ", "satirlar": [{"malzeme_kodu": "KAV", "miktar": "1"}]},      # boş neden
    {"neden": "x", "satirlar": []},                                                # satır yok
])
def test_recete_ekle_nedensiz_nesne_govde_422(istemci, sid, govde):
    assert istemci.post(f"{API}/urunler/TEST/recete?senaryo={sid}", json=govde).status_code == 422


def test_recete_ekle_eski_liste_bicimi_calisir_neden_bos(istemci, oturum, sid):
    r = istemci.post(f"{API}/urunler/TEST/recete?senaryo={sid}", json=[{"malzeme_kodu": "KAV", "ad": "Kavanoz", "miktar": "3"}])
    assert r.status_code == 201 and oturum.get(m.Recete, r.json()["id"]).neden is None


# ---------------------------------------------------------------- D3b: kartı olmayan malzeme ekrandan reçeteye eklenemez
YOK_MESAJI = "Etiket 370 kodlu malzeme yok; önce Veri Girişi › Yeni malzeme ile açın."


def test_kartsiz_malzeme_canli_hesapta_422(istemci, sid):
    r = _hesapla(istemci, sid, eklenen_satirlar=[{"malzeme_kodu": "Etiket 370", "ad": "Etiket", "miktar": "1"}])
    assert r.status_code == 422 and r.json()["mesaj"] == YOK_MESAJI and r.json()["kod"] == "malzeme_yok"
    assert r.json()["alanlar"] == {"malzeme_kodu": ["Etiket 370"]}
    # ara mamul satırı denetlenmez (fiyatsız olması bilinçli)
    assert _hesapla(istemci, sid, eklenen_satirlar=[{"malzeme_kodu": "ARA-1", "miktar": "1", "dugum_tipi": "ara_mamul"}]).status_code == 200


def test_kartsiz_malzeme_kaydet_ve_recete_ekle_422_hicbir_sey_yazilmaz(istemci, oturum, sid):
    u = oturum.query(m.Urun).filter_by(kod="TEST").one()
    once = oturum.query(m.Recete).filter_by(urun_id=u.id).count()
    r = _kaydet(istemci, sid, recete=[{"malzeme_kodu": "KAV", "ad": "Kavanoz", "miktar": "1"}, {"malzeme_kodu": "Etiket 370", "miktar": "1"}])
    assert r.status_code == 422 and r.json()["mesaj"] == YOK_MESAJI
    r = istemci.post(f"{API}/urunler/TEST/recete?senaryo={sid}", json={"neden": "etiket", "satirlar": [
        {"malzeme_kodu": "KAV", "miktar": "1"}, {"malzeme_kodu": "Etiket 370", "miktar": "1"}, {"malzeme_kodu": "X9", "miktar": "1"}]})
    assert r.status_code == 422 and r.json()["mesaj"] == "Etiket 370, X9 kodlu malzemeler yok; önce Veri Girişi › Yeni malzeme ile açın."
    oturum.expire_all()
    assert oturum.query(m.Recete).filter_by(urun_id=u.id).count() == once


def test_aktif_recetedeki_kartsiz_eski_satir_kaydetmeyi_engellemez(istemci, oturum, sid):
    # Excel/Canias aktarımından gelen kartsız satır (eski liste biçimi = aktarım gibi) zaten reçetede: ekrandan yeniden kaydetmek serbest
    assert istemci.post(f"{API}/urunler/TEST/recete?senaryo={sid}", json=[{"malzeme_kodu": "KAV", "miktar": "1"},
                                                                          {"malzeme_kodu": "ESKI-KARTSIZ", "miktar": "1"}]).status_code == 201
    r = _kaydet(istemci, sid, recete=[{"malzeme_kodu": "KAV", "miktar": "2"}, {"malzeme_kodu": "ESKI-KARTSIZ", "miktar": "1"}])
    assert r.status_code == 200, r.text
