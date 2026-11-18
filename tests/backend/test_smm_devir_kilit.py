"""SMM: ay devri (önceki ayın kapanışı = bu ayın açılışı) ve ay kilidi kuralları.

Devir durumu / yenileme (elle açılış korunur), kilit açmanın Genel Direktör'e ait olması, kapanış ön kontrolü (409 kapanis_eksik / zorla)
ve zincir (sonraki dönem uyarısı, sonraki dönem kilitliyken 409). Veriler uydurma küçük çalışma kitaplarıdır."""
from decimal import Decimal as D_
import pytest
from fastapi.testclient import TestClient
from backend.depo import modeller as m
from backend.depo.veritabani import oturum_ver
from backend.servisler import kimlik_servisi as ks
from backend.tohum import parametreleri_tohumla
from backend.uygulama import uygulama_olustur
from tests.backend.test_api import istemci  # noqa: F401  (fixture)
from tests.backend.test_smm_asama import _excel
from tests.backend.test_smm_veri import _ekim

A = "/api/v1"
H = {"X-Kullanici": "esma"}


def _eylul_id(c) -> int:
    return next(d["id"] for d in c.get(f"{A}/smm/donemler").json()["kayitlar"] if d["ay"] == 9)


def _durum(c, did) -> dict:
    r = c.get(f"{A}/smm/donemler/{did}/devir-durumu")
    assert r.status_code == 200, r.text
    return r.json()


def _kilit(c, did, kilitli, **ek):
    return c.put(f"{A}/smm/donemler/{did}/kilit", json={"kilitli": kilitli, **ek}, headers=H)


def _eylul_sayimi_degistir(c, miktar="30"):
    r = c.patch(f"{A}/smm/donemler/{_eylul_id(c)}/stok/HM-1", json={"sayim_miktar": miktar, "neden": "sayım düzeltildi"}, headers=H)
    assert r.status_code == 200, r.text


def test_yeni_donem_onceki_kapali_degilse_uyarir_kapaliysa_uyarmaz(istemci):  # noqa: F811
    assert istemci.post(f"{A}/smm/donemler/yukle", files={"dosya": ("09-2026 SMM.xlsx", _excel())}).status_code == 200
    r = istemci.post(f"{A}/smm/donemler", json={"yil": 2026, "ay": 10})
    assert r.status_code == 201 and r.json()["devir"]["uyari"] == "Eylül 2026 kapatılmadı; devir sonradan değişebilir"
    assert _kilit(istemci, r.json()["id"], True, zorla=True).status_code == 200
    r = istemci.post(f"{A}/smm/donemler", json={"yil": 2026, "ay": 11})
    assert r.status_code == 201 and r.json()["devir"]["onceki"] == "Ekim 2026" and r.json()["devir"]["uyari"] is None


def test_devir_durumu_uyumlu_sonra_uyumsuz(istemci):  # noqa: F811
    did = _ekim(istemci)
    d = _durum(istemci, did)
    assert d["onceki"] == {"id": _eylul_id(istemci), "ad": "Eylül 2026", "kilitli": False}
    assert d["uyumlu"] is True and d["fark_kalem"] == 0 and D_(d["fark_tutar"]) == 0 and d["ornek"] == []
    assert D_(d["acilis_tutar"]) == 480 and D_(d["kapanis_tutar"]) == 480
    v = istemci.get(f"{A}/smm/donemler/{did}/veri").json()
    assert D_(v["devir"].pop("fark_tutar")) == 0
    assert v["devir"] == {"uyumlu": True, "fark_kalem": 0, "onceki_ad": "Eylül 2026", "onceki_kilitli": False}

    # Eylül sayımı 40 → 30 KG (ortalama 12 TL): kapanış 360 TL olur, Ekim açılışı hâlâ 40 KG / 480 TL
    _eylul_sayimi_degistir(istemci)
    d = _durum(istemci, did)
    assert d["uyumlu"] is False and d["fark_kalem"] == 1 and D_(d["fark_tutar"]) == 120 and d["elle_kalem"] == 0
    o = d["ornek"][0]
    assert o["kod"] == "HM-1" and o["ad"] == "Biber" and o["elle"] is False
    assert (D_(o["acilis_miktar"]), D_(o["kapanis_miktar"]), D_(o["acilis_tutar"]), D_(o["kapanis_tutar"])) == (40, 30, 480, 360)
    v = istemci.get(f"{A}/smm/donemler/{did}/veri").json()["devir"]
    assert v["uyumlu"] is False and v["fark_kalem"] == 1 and D_(v["fark_tutar"]) == 120

    # devirle gelmeyen (Excel'den yüklenen) dönemde devir kaynağı yok
    e = _durum(istemci, _eylul_id(istemci))
    assert e["onceki"] is None and e["uyumlu"] is True
    assert istemci.get(f"{A}/smm/donemler/{_eylul_id(istemci)}/veri").json()["devir"] is None
    assert istemci.get(f"{A}/smm/donemler/999/devir-durumu").status_code == 404


def test_devir_yenile_elle_degeri_korur_elle_ez_ile_ezer(istemci, oturum):  # noqa: F811
    did = _ekim(istemci)
    eylul = _eylul_id(istemci)
    # Ekim'de AMB-1 açılışı elle girilir (önceki kapanışta 0); Eylül'de sayım değişir ve yeni bir kalem açılır
    r = istemci.patch(f"{A}/smm/donemler/{did}/stok/AMB-1", json={"dbs_miktar": "5", "dbs_tutar": "99", "neden": "elle açılış"}, headers=H)
    assert r.status_code == 200, r.text
    _eylul_sayimi_degistir(istemci)
    r = istemci.post(f"{A}/smm/donemler/{eylul}/stok", json={"kod": "YENI-9", "ad": "Yeni kart", "tur": "0001-Hammadde", "neden": "kart"},
                     headers=H)
    assert r.status_code == 201, r.text
    d = _durum(istemci, did)
    assert d["fark_kalem"] == 2 and d["elle_kalem"] == 1 and {x["kod"]: x["elle"] for x in d["ornek"]} == {"HM-1": False, "AMB-1": True}

    # neden zorunlu
    assert istemci.post(f"{A}/smm/donemler/{did}/devir-yenile", json={"neden": ""}, headers=H).status_code == 422
    assert istemci.post(f"{A}/smm/donemler/{did}/devir-yenile", json={}, headers=H).status_code == 422
    # devir kaynağı olmayan dönem
    r = istemci.post(f"{A}/smm/donemler/{eylul}/devir-yenile", json={"neden": "x"}, headers=H)
    assert r.status_code == 422 and "devralınmamış" in r.json()["mesaj"]

    r = istemci.post(f"{A}/smm/donemler/{did}/devir-yenile", json={"neden": "Eylül sayımı düzeltildi"}, headers=H)
    assert r.status_code == 200, r.text
    y = r.json()
    assert (y["guncellenen"], y["eklenen"], y["elle_kalem"], y["elle_korundu"]) == (1, 1, 1, True)
    assert y["durum"]["fark_kalem"] == 1 and y["durum"]["ornek"][0]["kod"] == "AMB-1" and y["durum"]["ornek"][0]["elle"] is True
    stok = {x["kod"]: x for x in istemci.get(f"{A}/smm/donemler/{did}/stok", params={"yalniz_hareketli": False}).json()["kayitlar"]}
    assert (D_(stok["HM-1"]["dbs_miktar"]), D_(stok["HM-1"]["dbs_tutar"])) == (30, 360)
    assert (D_(stok["AMB-1"]["dbs_miktar"]), D_(stok["AMB-1"]["dbs_tutar"])) == (5, 99)   # elle değer korundu
    assert "YENI-9" in stok and stok["YENI-9"]["tur"] == "0001-Hammadde"
    kayit = oturum.query(m.DegisiklikKaydi).filter_by(tablo="smm_donem", islem="devir_yenile").one()
    assert kayit.kullanici == "esma" and kayit.yeni["neden"] == "Eylül sayımı düzeltildi" and kayit.yeni["elle_ez"] is False
    assert list(kayit.eski["kalemler"]) == ["HM-1"] and [D_(x) for x in kayit.eski["kalemler"]["HM-1"]] == [40, 480]

    # elle_ez: elle değer de önceki kapanışla (0) ezilir; devir uyumlu olur ve kalem artık elle sayılmaz
    r = istemci.post(f"{A}/smm/donemler/{did}/devir-yenile", json={"neden": "tam devir", "elle_ez": True}, headers=H)
    assert r.status_code == 200, r.text
    y = r.json()
    assert (y["guncellenen"], y["eklenen"], y["elle_kalem"], y["elle_korundu"]) == (1, 0, 1, False)
    assert y["durum"]["uyumlu"] is True and y["durum"]["fark_kalem"] == 0
    r = istemci.post(f"{A}/smm/donemler/{did}/devir-yenile", json={"neden": "değişiklik yok"}, headers=H)
    assert (r.json()["guncellenen"], r.json()["eklenen"], r.json()["elle_kalem"]) == (0, 0, 0)

    # kilitli dönemde yenilenmez
    assert _kilit(istemci, did, True, zorla=True).status_code == 200
    r = istemci.post(f"{A}/smm/donemler/{did}/devir-yenile", json={"neden": "x"}, headers=H)
    assert r.status_code == 409 and r.json()["kod"] == "donem_kilitli"


def test_kapanis_on_kontrolu_eksikleri_soyler_zorla_ile_kapatir(istemci, oturum):  # noqa: F811
    did = _ekim(istemci)
    _eylul_sayimi_degistir(istemci)   # devir de uyumsuz olsun
    r = _kilit(istemci, did, True)
    assert r.status_code == 409 and r.json()["kod"] == "kapanis_eksik", r.text
    eksikler = r.json()["alanlar"]["eksikler"]
    assert "Eksik veri: Alım ve satış" in eksikler and "Eksik veri: Gider mizanı (720 / 730)" in eksikler
    assert "Açılış stoku Eylül 2026 kapanışıyla uyuşmuyor (1 kalem, fark 120,00 TL)" in eksikler
    assert istemci.get(f"{A}/smm/donemler/{did}/veri").json()["donem"]["kilitli"] is False

    r = _kilit(istemci, did, True, zorla=True)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["kilitli"] is True and d["kilitleyen"] == "esma" and d["kilit_zamani"] is not None and d["uyari"] is None
    kayit = oturum.query(m.DegisiklikKaydi).filter_by(tablo="smm_donem", islem="kilitle").one()
    assert kayit.yeni["zorla"] is True and len(kayit.yeni["eksikler"]) == len(eksikler)
    liste = {x["id"]: x for x in istemci.get(f"{A}/smm/donemler").json()["kayitlar"]}
    assert liste[did]["kilit_zamani"] == d["kilit_zamani"] and liste[_eylul_id(istemci)]["kilit_zamani"] is None

    # Eylül'de türü boş kalem (03-2) var: ön kontrol onu da söyler
    r = _kilit(istemci, _eylul_id(istemci), True)
    assert r.status_code == 409 and any("türü / mizan kodu boş" in x for x in r.json()["alanlar"]["eksikler"])


def test_kilit_zinciri_sonraki_donem_uyarisi_ve_409(istemci):  # noqa: F811
    did = _ekim(istemci)
    eylul = _eylul_id(istemci)
    assert _kilit(istemci, eylul, True, zorla=True).status_code == 200
    assert _durum(istemci, did)["onceki"]["kilitli"] is True

    # sonraki dönem (Ekim) açık: Eylül kilidi açılır, yanıtta uyarı
    r = _kilit(istemci, eylul, False)
    assert r.status_code == 200 and r.json()["kilitli"] is False and r.json()["kilit_zamani"] is None
    assert r.json()["uyari"] == "Ekim 2026 açılışı bu dönemden devralındı; değişiklik sonrası devri yenileyin"

    # sonraki dönem kilitli: önce o açılmalı
    assert _kilit(istemci, eylul, True, zorla=True).status_code == 200
    assert _kilit(istemci, did, True, zorla=True).status_code == 200
    r = _kilit(istemci, eylul, False)
    assert r.status_code == 409 and r.json()["kod"] == "sonraki_kilitli" and "Önce Ekim 2026 kilidini açın" in r.json()["mesaj"]
    assert r.json()["alanlar"] == {"donem_id": did}
    r = _kilit(istemci, did, False)
    assert r.status_code == 200 and r.json()["uyari"] is None   # Ekim'den devralan dönem yok
    assert _kilit(istemci, eylul, False).status_code == 200


# ---------------------------------------------------------------- rol: kilidi yalnız Genel Direktör açar
@pytest.fixture
def girisli(oturum):
    app = uygulama_olustur(giris_zorunlu=True)

    def _ver():
        try:
            yield oturum
            oturum.commit()
        except Exception:
            oturum.rollback()
            raise
    app.dependency_overrides[oturum_ver] = _ver
    parametreleri_tohumla(oturum)
    for ad, rol in (("genel", "genel_direktor"), ("muhasebeci", "muhasebe"), ("izleyen", "izleyici")):
        ks.kullanici_olustur(oturum, ad, ad.title(), rol, "gecici-sifre", sifre_degismeli=False)
    oturum.commit()
    return app


def _giris(app, kullanici) -> TestClient:
    c = TestClient(app)
    r = c.post(f"{A}/kimlik/giris", json={"kullanici_adi": kullanici, "sifre": "gecici-sifre"})
    assert r.status_code == 200, r.text
    return c


def test_kilidi_yalniz_genel_direktor_acar(girisli):
    muhasebe, genel, izleyen = _giris(girisli, "muhasebeci"), _giris(girisli, "genel"), _giris(girisli, "izleyen")
    did = _ekim(muhasebe)
    # kapatma: yazma yetkisi olan herkes (muhasebe); izleyici yazamaz
    assert izleyen.put(f"{A}/smm/donemler/{did}/kilit", json={"kilitli": True, "zorla": True}).status_code == 403
    r = muhasebe.put(f"{A}/smm/donemler/{did}/kilit", json={"kilitli": True, "zorla": True})
    assert r.status_code == 200 and r.json()["kilitli"] is True and r.json()["kilitleyen"] == "muhasebeci"
    # açma: muhasebe 403, Genel Direktör 200
    r = muhasebe.put(f"{A}/smm/donemler/{did}/kilit", json={"kilitli": False})
    assert r.status_code == 403 and r.json()["mesaj"] == "Dönem kilidini yalnız Genel Direktör açabilir."
    assert r.json()["kod"] == "kilit_acma_yetkisi"
    assert muhasebe.get(f"{A}/smm/donemler/{did}/veri").json()["donem"]["kilitli"] is True
    r = genel.put(f"{A}/smm/donemler/{did}/kilit", json={"kilitli": False})
    assert r.status_code == 200 and r.json()["kilitli"] is False
    # devir yenileme muhasebeye açık (yazma yetkisi)
    assert muhasebe.post(f"{A}/smm/donemler/{did}/devir-yenile", json={"neden": "kontrol"}).status_code == 200
