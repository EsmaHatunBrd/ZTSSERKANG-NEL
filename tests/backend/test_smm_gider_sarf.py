"""SMM gider dağıtım tablosu (720 / 730 -> aşamalar) ve en büyük sarf farkları. Uydurma küçük SMM Excel'i (test_smm_asama, bellekte):
havuzlar 20: 1000, 40 işçilik: 400, 40 GÜG: 1000, 50: 300; gider mizanı 720: 1000, 730: 5000. Gerçek dosya okunmaz."""
from decimal import Decimal as D_
from tests.backend.test_api import istemci  # noqa: F401  (fixture)
from tests.backend.test_smm_asama import _yukle

A = "/api/v1"


def _gider(c, did, **p):
    r = c.get(f"{A}/smm/donemler/{did}/gider-dagitimi", params=p)
    assert r.status_code == 200, r.text
    return r.json()


def test_gider_dagitimi_toplamlar_mizan_ve_asama_hesabiyla_ayni(istemci):  # noqa: F811
    did = _yukle(istemci)
    v = _gider(istemci, did)
    t = v["toplam"]
    # 720 + 730 = 6000; dağıtılan 2700 (aşama ekranındaki "dağıtılan" ile aynı) -> dağıtılmayan 3300 (%55)
    assert D_(t["mizan_tutari"]) == 6000 and D_(t["dagitilan"]) == 2700 and D_(t["dagitilmayan"]) == 3300
    assert D_(t["dagitilan"]) + D_(t["dagitilmayan"]) == D_(t["mizan_tutari"]) and D_(t["dagitilmayan_yuzde"]) == D_("0.55")
    u = istemci.get(f"{A}/smm/donemler/{did}/uretim", params={"asama": 50}).json()
    assert D_(u["dagitim"]["dagitilmayan"]) == D_(t["dagitilmayan"])
    # aşama toplamları = aşama hesabının özetleri (işçilik, GÜG)
    oz = {o["asama"]: o for o in u["ozetler"]}
    a = {x["asama"]: x for x in v["asamalar"]}
    for k in (20, 40, 50):
        assert D_(a[k]["iscilik"]) == D_(oz[k]["iscilik"]) and D_(a[k]["gug"]) == D_(oz[k]["gug"])
        assert D_(a[k]["toplam"]) == D_(a[k]["iscilik"]) + D_(a[k]["gug"])
    assert (D_(a[20]["toplam"]), D_(a[40]["iscilik"]), D_(a[40]["gug"]), D_(a[50]["toplam"])) == (1000, 400, 1000, 300)
    assert a[20]["birlesik"] and a[50]["birlesik"] and not a[40]["birlesik"]
    assert sum(D_(x["pay_yuzde"]) for x in v["asamalar"]) == 1 and D_(a[40]["pay_yuzde"]) == D_(1400) / 2700
    assert a[20]["anahtar"] == "Üretim miktarı" and a[40]["anahtar"] == "İşçilik: Üretim × etiket adam-sn · GÜG: Üretim × dolum sn"
    assert D_(a[20]["uretim_miktar"]) == 500 and D_(a[20]["birim_basina_ortalama"]) == 2 and a[50]["urun_sayisi"] == 1   # 03-2 üretilmedi
    assert D_(a[40]["havuz"]) == 1400
    # 720 / 730: yalnız 40 ayrılabilir; 20 + 50 birleşik 1300 -> hesap bazında dağıtılmayan verilmez
    k = {x["hesap"]: x for x in v["kaynaklar"]}
    assert D_(k["720"]["mizan_tutari"]) == 1000 and D_(k["720"]["dagitilan"]) == 400 and k["720"]["dagitilmayan"] is None
    assert D_(k["730"]["mizan_tutari"]) == 5000 and D_(k["730"]["dagitilan"]) == 1000 and k["730"]["dagitilmayan_yuzde"] is None
    assert D_(v["ayrilmamis"]) == 1300 and D_(v["havuz_toplami"]) == 2700
    assert any("havuzlara aktarılmamış" in n and "3.300 TL" in n for n in v["notlar"])
    assert any("bölünmediği" in n for n in v["notlar"])
    # en çok gider alan ürünler: toplam TL'ye göre
    assert [(x["kod"], x["asama"], D_(x["toplam"])) for x in v["urunler_ilk20"]] == [("02-1", 40, 1400), ("01-1", 20, 1000), ("03-1", 50, 300)]
    assert v["urun_sayisi"] == 3 and len(_gider(istemci, did, ilk=2)["urunler_ilk20"]) == 2


def test_gider_dagitimi_birlesik_havuz_yoksa_hesap_bazinda_kesin(istemci):  # noqa: F811
    did = _yukle(istemci)
    assert istemci.put(f"{A}/smm/donemler/{did}/dagitim", json={"havuzlar": {"20_uretim": "0", "50_uretim": "0"}}).status_code == 200
    v = _gider(istemci, did)
    k = {x["hesap"]: x for x in v["kaynaklar"]}
    for h, mizan, dagitilan in (("720", 1000, 400), ("730", 5000, 1000)):
        assert D_(k[h]["dagitilan"]) + D_(k[h]["dagitilmayan"]) == D_(k[h]["mizan_tutari"]) == mizan
        assert D_(k[h]["dagitilan"]) == dagitilan
    assert D_(k["720"]["dagitilmayan_yuzde"]) == D_("0.6") and D_(v["ayrilmamis"]) == 0
    assert D_(v["toplam"]["dagitilmayan"]) == D_(k["720"]["dagitilmayan"]) + D_(k["730"]["dagitilmayan"])


def test_gider_dagitimi_elle_deger_notu_ve_mizansiz_donem(istemci, oturum):  # noqa: F811
    did = _yukle(istemci)
    # 03-1 işçiliği elle 5 TL: 50'ye dağılan 500, havuz 300 -> fark notu, neden elle giriş
    r = istemci.put(f"{A}/smm/donemler/{did}/uretim/50/03-1/elle", json={"alanlar": {"iscilik": "5"}})
    assert r.status_code == 200, r.text
    v = _gider(istemci, did)
    assert D_({x["asama"]: x for x in v["asamalar"]}[50]["toplam"]) == 500
    assert any(n.startswith("50 aşaması: havuz 300 TL, ürünlere dağılan 500 TL") and "elle" in n for n in v["notlar"])
    # gider mizanı yoksa: mizan / dağıtılmayan null, not başta
    from backend.depo import modeller as m
    oturum.get(m.SmmDonem, did).gider_mizan = None
    oturum.commit()
    v = _gider(istemci, did)
    assert v["toplam"]["mizan_tutari"] is None and v["toplam"]["dagitilmayan"] is None
    assert all(x["mizan_tutari"] is None and x["dagitilmayan"] is None for x in v["kaynaklar"])
    assert v["notlar"][0].startswith("Gider mizanı (720 / 730) girilmemiş")


def test_sarf_farki_ozeti_siralama_yon_birim_uyumsuz(istemci):  # noqa: F811
    did = _yukle(istemci)
    tum = istemci.get(f"{A}/smm/donemler/{did}/sarf-farki").json()
    r = istemci.get(f"{A}/smm/donemler/{did}/sarf-farki/ozet")
    assert r.status_code == 200, r.text
    v = r.json()
    kod = [x["kod"] for x in v["kalemler"]]
    # birim uyumsuz ETK-1 sıralamaya girmez, ayrı sayılır; farkı 0 olan da girmez
    assert "ETK-1" not in kod and v["ozet"]["birim_uyumsuz_sayisi"] == 1
    beklenen = sorted((x for x in tum["kayitlar"] if not x["birim_uyumsuz"] and D_(x["fark_tutar"]) != 0),
                      key=lambda x: (-abs(D_(x["fark_tutar"])), x["kod"]))
    assert kod == [x["kod"] for x in beklenen] and v["kalem_sayisi"] == len(beklenen)
    tutarlar = [abs(D_(x["fark_tutar"])) for x in v["kalemler"]]
    assert tutarlar == sorted(tutarlar, reverse=True)
    # 01-1: 480 fazla × 8,6 = 4128 en üstte; HM-1: −115 × 12 = −1380 eksik
    x = v["kalemler"][0]
    assert x["kod"] == "01-1" and x["yon"] == "fazla" and D_(x["fark_tutar"]) == D_("4128") and D_(x["fark_miktar"]) == 480
    assert D_(x["beklenen_sarf"]) == 20 and D_(x["gercek_sarf"]) == 500 and D_(x["fark_yuzde"]) == 24 and D_(x["birim_fiyat"]) == D_("8.6")
    hm = next(x for x in v["kalemler"] if x["kod"] == "HM-1")
    assert hm["yon"] == "eksik" and D_(hm["fark_tutar"]) == -1380
    assert all((x["yon"] == "fazla") == (D_(x["fark_tutar"]) > 0) for x in v["kalemler"])
    # özet = sarf farkı ekranının toplamları; net = fazla + eksik
    o = v["ozet"]
    assert D_(o["fazla_tutar"]) == D_(tum["toplamlar"]["fazla"]) and D_(o["eksik_tutar"]) == D_(tum["toplamlar"]["eksik"])
    assert D_(o["toplam_fark_tutari"]) == D_(o["fazla_tutar"]) + D_(o["eksik_tutar"]) and D_(o["eksik_tutar"]) < 0
    assert o["fazla_sayisi"] + o["eksik_sayisi"] == v["kalem_sayisi"]
    # ilk N
    v2 = istemci.get(f"{A}/smm/donemler/{did}/sarf-farki/ozet", params={"ilk": 1}).json()
    assert [x["kod"] for x in v2["kalemler"]] == ["01-1"] and v2["kalem_sayisi"] == v["kalem_sayisi"]
    assert istemci.get(f"{A}/smm/donemler/{did}/sarf-farki/ozet", params={"ilk": 0}).status_code == 422


def test_404(istemci):  # noqa: F811
    assert istemci.get(f"{A}/smm/donemler/9999/gider-dagitimi").status_code == 404
    assert istemci.get(f"{A}/smm/donemler/9999/sarf-farki/ozet").status_code == 404
