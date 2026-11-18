"""Analizler 3. dalga: marjı koruyan fiyat (hedef fiyat = maliyet x (1 + marj), gereken zam, liste fiyatı, yıllık ek gelir)."""
from decimal import ROUND_HALF_UP, Decimal as D_
from backend.depo import modeller as m
from backend.servisler import hesap_servisi as hs
from tests.backend.test_analiz_2 import _kurulum, _satis
from tests.backend.test_api import _senaryo, istemci  # noqa: F401  (fixture)

A = "/api/v1"


BERRAK = ("TEST", "T2")


def _hazirla(istemci, oturum) -> int:
    """TEST: 100 TL x 1000 (marj yüksek, zam gerekmez); T2: 1 TL x 100 ve T4: 15 TL x 5000 (maliyetin altında, zam gerekir);
    T3: satış yok (geçen yıl fiyatı yok). TEST ve T2 Berrak markalı (liste fiyatı yalnız onlarda)."""
    sid = _senaryo(istemci); _kurulum(istemci, sid, oturum)
    oturum.query(m.Urun).filter(m.Urun.kod.in_(BERRAK)).update({"marka": "Berrak"}, synchronize_session=False); oturum.commit()
    _satis(oturum, sid, "TEST", "100", "TL", "1000")
    _satis(oturum, sid, "T2", "1", "TL", "100")
    _satis(oturum, sid, "T4", "15", "TL", "5000")
    return sid


def test_hedef_fiyat_hesaplari(istemci, oturum):
    sid = _hazirla(istemci, oturum)
    r = istemci.get(f"{A}/analiz/hedef-fiyat?senaryo={sid}&marj=0.15")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["marj"] == "0.15" and d["adet_kaynagi"] == "satis_gecmisi"
    assert (D_(d["bolen_yurtici"]), D_(d["bolen_yurtdisi"]), d["yuvarlama"]) == (D_("0.63"), D_("0.90"), "0.01")
    assert "bolen" not in d
    k = {x["kod"]: x for x in d["kayitlar"]}
    marj = D_("0.15")
    gecen = {"TEST": (D_(100), D_(1000)), "T2": (D_(1), D_(100)), "T4": (D_(15), D_(5000))}
    for kod, (gy, adet) in gecen.items():
        c = hs.hesapla(oturum, kod, sid).sonuc
        maliyet = c.finansman_dahil_maliyet_tl
        hedef = maliyet * (1 + marj)
        x = k[kod]
        assert x["hata"] is None
        assert D_(x["maliyet"]) == maliyet and D_(x["hesap_fiyati"]) == c.satis_fiyati_tl
        assert D_(x["hedef_fiyat"]) == hedef and "liste_fiyati" not in x
        if kod in BERRAK:   # Berrak: iki pazar, adıma (0,01) en yakın
            assert x["marka"] == "Berrak"
            assert D_(x["liste_fiyati_yurtici"]) == (hedef / D_("0.63")).quantize(D_("0.01"), ROUND_HALF_UP)
            assert D_(x["liste_fiyati_yurtdisi"]) == (hedef / D_("0.90")).quantize(D_("0.01"), ROUND_HALF_UP)
        else:               # Berrak değil: liste fiyatı yok
            assert x["liste_fiyati_yurtici"] is None and x["liste_fiyati_yurtdisi"] is None
        assert D_(x["gecen_yil_fiyat"]) == gy and D_(x["adet"]) == adet
        assert D_(x["mevcut_marj"]) == gy / maliyet - 1 and D_(x["gereken_zam"]) == hedef / gy - 1
        assert D_(x["yillik_ek_gelir"]) == (hedef - gy) * adet
    assert D_(k["TEST"]["gereken_zam"]) < 0 and D_(k["TEST"]["yillik_ek_gelir"]) < 0   # zam gerekmez: ek gelir negatif
    assert D_(k["T2"]["gereken_zam"]) > 0 and D_(k["T4"]["gereken_zam"]) > 0
    # bölge kârlılık haritasıyla aynı
    harita = {x["kod"]: x for x in istemci.get(f"{A}/analiz/karlilik?senaryo={sid}").json()["kayitlar"]}
    assert all(k[kod]["bolge"] == harita[kod]["bolge"] for kod in k)
    # geçen yıl fiyatı yok: kıyas alanları null, hedef ve liste fiyatı yine hesaplanır
    t3 = k["T3"]
    assert t3["gecen_yil_fiyat"] is None and t3["mevcut_marj"] is None and t3["gereken_zam"] is None and t3["yillik_ek_gelir"] is None
    assert t3["adet"] is None and t3["bolge"] is None and D_(t3["hedef_fiyat"]) == D_(t3["maliyet"]) * (1 + marj)
    # özet
    o = d["ozet"]
    assert o["urun_sayisi"] == 4 and o["zam_gereken"] == 2 and o["fiyatsiz"] == 1 and o["hatali"] == 0
    assert D_(o["yillik_ek_gelir"]) == D_(k["T2"]["yillik_ek_gelir"]) + D_(k["T4"]["yillik_ek_gelir"])   # yalnız pozitifler
    fark = sum((D_(k[kod]["hedef_fiyat"]) - gy) * adet for kod, (gy, adet) in gecen.items())
    ciro = sum(gy * adet for gy, adet in gecen.values())
    assert D_(o["ort_zam"]) == fark / ciro


def test_hedef_fiyat_siralama(istemci, oturum):
    sid = _hazirla(istemci, oturum)
    d = istemci.get(f"{A}/analiz/hedef-fiyat?senaryo={sid}&marj=0.15").json()
    # zam gerekenler yıllık ek gelir azalan (T4 > T2), sonra gereken zam azalan (TEST negatif), null en sonda (T3)
    assert [x["kod"] for x in d["kayitlar"]] == ["T4", "T2", "TEST", "T3"]


def test_hedef_fiyat_marj_bossa_esik(istemci, oturum):
    sid = _hazirla(istemci, oturum)
    d = istemci.get(f"{A}/analiz/hedef-fiyat?senaryo={sid}").json()
    assert d["marj"] == "0.10"
    m = hs.hesapla(oturum, "T2", sid).sonuc.finansman_dahil_maliyet_tl
    assert D_({x["kod"]: x for x in d["kayitlar"]}["T2"]["hedef_fiyat"]) == m * D_("1.10")
    assert istemci.post(f"{A}/parametreler/marj_esigi/degerler?senaryo={sid}", json={"deger": "0.25", "gecerlilik_basi": "2026-06-01",
                                                                                     "neden": "eşik"}).status_code == 201
    d2 = istemci.get(f"{A}/analiz/hedef-fiyat?senaryo={sid}").json()
    assert d2["marj"] == "0.25" and D_({x["kod"]: x for x in d2["kayitlar"]}["T2"]["hedef_fiyat"]) == m * D_("1.25")


def test_hedef_fiyat_dogrulama(istemci, oturum):
    sid = _hazirla(istemci, oturum)
    assert istemci.get(f"{A}/analiz/hedef-fiyat?senaryo={sid}&marj=-2").status_code == 422
    assert istemci.get(f"{A}/analiz/hedef-fiyat?senaryo={sid}&marj=6").status_code == 422
    assert istemci.get(f"{A}/analiz/hedef-fiyat?senaryo=99999").status_code == 404


def test_karlilik_cikisi_degismedi(istemci, oturum):
    sid = _hazirla(istemci, oturum)
    d = istemci.get(f"{A}/analiz/karlilik?senaryo={sid}").json()
    assert set(d) == {"esik_marj", "esik_adet", "adet_kaynagi", "ozet", "kayitlar"}
    alanlar = {"kod", "ad", "aile", "aile_anahtari", "adet", "maliyet", "satis_fiyati", "marj", "fiyat_kaynagi", "yillik_kar", "bolge", "hata", "maliyet_kaynagi"}
    assert all(set(x) == alanlar for x in d["kayitlar"])   # iç alanlar (_gecen_yil_fiyat, _hesap_fiyati) sızmaz
    k = {x["kod"]: x for x in d["kayitlar"]}
    assert D_(k["T4"]["satis_fiyati"]) == 15 and k["T4"]["fiyat_kaynagi"] == "satis_gecmisi" and k["T3"]["fiyat_kaynagi"] == "hesap"
    assert all(x["maliyet_kaynagi"] == "bu_yil" for x in d["kayitlar"])   # stokta kalan yok: bu yılın maliyeti


def test_hedef_fiyat_liste_parametreleri_ve_yuvarlama(istemci, oturum):
    sid = _hazirla(istemci, oturum)
    for a, v in [("liste_bolen_yurtici", "0.6"), ("liste_bolen_yurtdisi", "0.8"), ("liste_yuvarlama", "0.5")]:
        r = istemci.post(f"{A}/parametreler/{a}/degerler?senaryo={sid}", json={"deger": v, "gecerlilik_basi": "2026-01-01", "neden": "politika"})
        assert r.status_code == 201, r.text
    d = istemci.get(f"{A}/analiz/hedef-fiyat?senaryo={sid}&marj=0.15").json()
    assert (d["bolen_yurtici"], d["bolen_yurtdisi"], d["yuvarlama"]) == ("0.6", "0.8", "0.50")
    k = {r["kod"]: r for r in d["kayitlar"]}
    hedef = D_(k["T2"]["hedef_fiyat"])
    assert D_(k["T2"]["liste_fiyati_yurtici"]) == ((hedef / D_("0.6")) / D_("0.5")).quantize(D_(1), ROUND_HALF_UP) * D_("0.5")
    assert D_(k["T2"]["liste_fiyati_yurtdisi"]) == ((hedef / D_("0.8")) / D_("0.5")).quantize(D_(1), ROUND_HALF_UP) * D_("0.5")
    assert D_(k["T2"]["liste_fiyati_yurtici"]) % D_("0.5") == 0
    assert k["T4"]["marka"] is None and k["T4"]["liste_fiyati_yurtici"] is None
