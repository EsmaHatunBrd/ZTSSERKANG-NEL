"""Analizler 2. dalga: kur riski (döviz payı, birim/yıllık etki) ve kârlılık haritası (adet x marj bölgeleri)."""
from datetime import timedelta
from decimal import Decimal as D_
from backend.depo import modeller as m
from backend.servisler import hesap_servisi as hs, karsilastirma_servisi as ks, satis_servisi
from tests.backend.test_api import _kur, _senaryo, istemci  # noqa: F401  (fixture)

A = "/api/v1"
URETIM = {"vardiya_uretim_adedi": "65000", "dolum_personel": "13", "etiketleme_adedi": "35000", "etiket_personel": "7", "mal_kabul_miktar_kg": "0.19"}


def _urun(c, sid, kod, recete):
    assert c.put(f"{A}/urunler/{kod}", json={"ad": f"Ürün {kod}", "ambalaj_hacmi": "370", "hat": "Niko", "taze_tursu_sinifi": "Turşu/Turşu",
                                             "suzme_kg": "0.18"}).status_code == 200
    assert c.put(f"{A}/urunler/{kod}/uretim-hedefi?senaryo={sid}", json=URETIM).status_code == 200
    assert c.post(f"{A}/urunler/{kod}/recete?senaryo={sid}", json=recete).status_code == 201


def _kurulum(c, sid, oturum):
    """TEST: kavanoz (TL) + etiket (USD). T2, T3, T4: yalnız kavanoz (dövizsiz)."""
    _kur(c, sid, oturum)
    c.post(f"{A}/malzemeler", json={"kod": "ETK", "ad": "Etiket", "tip": "0008-Ambalaj Malzeme", "birim": "AD", "para_birimi": "USD", "zs": "S"})
    assert c.post(f"{A}/malzemeler/ETK/fiyatlar?senaryo={sid}", json={"onay": True, "fiyat": "0.05", "para_birimi": "USD", "gecerlilik_basi": "2026-06-01",
                                                                     "neden": "bütçe"}).status_code == 201
    kav = {"malzeme_kodu": "KAV", "ad": "Kavanoz", "miktar": "1", "birim": "AD", "fire_override": "0.02"}
    _urun(c, sid, "TEST", [kav, {"malzeme_kodu": "ETK", "ad": "Etiket", "miktar": "1", "birim": "AD", "fire_override": "0"}])
    for kod in ("T2", "T3", "T4"):
        _urun(c, sid, kod, [kav])


def _satis(oturum, sid, kod, fiyat, pb, adet):
    bas, _ = ks.pencere(oturum.get(m.Senaryo, sid))
    satis_servisi.ekle(oturum, kod, "Müşteri A", bas + timedelta(days=30), D_(fiyat), pb, D_(adet))
    oturum.commit()


def test_kur_riski(istemci, oturum):
    sid = _senaryo(istemci); _kurulum(istemci, sid, oturum)
    _satis(oturum, sid, "TEST", "100", "TL", "1000")
    _satis(oturum, sid, "T2", "1", "TL", "100")
    r = istemci.get(f"{A}/analiz/kur-riski?senaryo={sid}")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["oran"] == "0.10" and d["kurlar"] == {"EUR": "60", "USD": "50"} and d["adet_kaynagi"] == "satis_gecmisi"
    k = {x["kod"]: x for x in d["kayitlar"]}
    assert d["kayitlar"][0]["kod"] == "TEST"   # en büyük yıllık etki başta
    t = k["TEST"]
    # birim etki: kurlar %10 artmış bağımsız hesapla aynı
    once = hs.hesapla(oturum, "TEST", sid).sonuc.finansman_dahil_maliyet_tl
    sonra = hs.hesapla(oturum, "TEST", sid, override={"parametreler": {"kur.USD": D_("55"), "kur.EUR": D_("66")}}).sonuc.finansman_dahil_maliyet_tl
    assert D_(t["birim_etki"]) == sonra - once and D_(t["birim_etki"]) > 0 and D_(t["maliyet"]) == once and D_(t["yeni_maliyet"]) == sonra
    pay = D_(t["doviz_payi"])
    assert 0 < pay < 1 and abs(pay - (sonra - once) / once / D_("0.1")) < D_("1e-20")
    assert abs(D_(t["usd_payi"]) - pay) < D_("1e-20") and D_(t["eur_payi"]) == 0   # tek döviz kalemi USD
    assert D_(t["yillik_adet"]) == 1000 and D_(t["yillik_etki"]) == D_(t["birim_etki"]) * 1000
    # dövizsiz ürün: pay 0; satışı olmayan: adet ve yıllık etki null, listede kalır
    assert D_(k["T2"]["doviz_payi"]) == 0 and D_(k["T2"]["yillik_etki"]) == 0
    assert k["T3"]["yillik_adet"] is None and k["T3"]["yillik_etki"] is None and k["T3"]["birim_etki"] is not None
    o = d["ozet"]
    assert o["urun_sayisi"] == 4 and o["adetsiz_urun"] == 2 and o["hatali"] == 0
    assert D_(o["yillik_etki"]) == D_(t["yillik_etki"])
    assert D_(o["yillik_maliyet"]) == once * 1000 + D_(k["T2"]["maliyet"]) * 100
    assert abs(D_(o["doviz_payi_ort"]) - D_(o["yillik_etki"]) / D_("0.1") / D_(o["yillik_maliyet"])) < D_("1e-20")
    pb = {x["para_birimi"]: x for x in d["para_birimleri"]}
    assert D_(pb["USD"]["pay"]) == 1 and D_(pb["EUR"]["yillik_etki"]) == 0
    # doğrusal: oran %20'de döviz payı aynı, birim etki iki katı
    d2 = {x["kod"]: x for x in istemci.get(f"{A}/analiz/kur-riski?senaryo={sid}&oran=0.2").json()["kayitlar"]}
    assert abs(D_(d2["TEST"]["doviz_payi"]) - pay) < D_("1e-9") and abs(D_(d2["TEST"]["birim_etki"]) - 2 * D_(t["birim_etki"])) < D_("1e-9")
    # doğrulama
    assert istemci.get(f"{A}/analiz/kur-riski?senaryo={sid}&oran=-1").status_code == 422
    assert istemci.get(f"{A}/analiz/kur-riski?senaryo={sid}&oran=6").status_code == 422
    assert istemci.get(f"{A}/analiz/kur-riski?senaryo=99999").status_code == 404


def test_kur_riski_adet_yoksa_duz_ortalama(istemci, oturum):
    sid = _senaryo(istemci); _kurulum(istemci, sid, oturum)
    d = istemci.get(f"{A}/analiz/kur-riski?senaryo={sid}").json()
    paylar = [D_(x["doviz_payi"]) for x in d["kayitlar"]]
    assert d["ozet"]["adetsiz_urun"] == 4 and D_(d["ozet"]["yillik_etki"]) == 0
    assert abs(D_(d["ozet"]["doviz_payi_ort"]) - sum(paylar) / 4) < D_("1e-20")
    assert all(x["pay"] is None for x in d["para_birimleri"])


def test_karlilik_haritasi(istemci, oturum):
    sid = _senaryo(istemci); _kurulum(istemci, sid, oturum)
    _satis(oturum, sid, "TEST", "100", "TL", "1000")   # yüksek fiyat
    _satis(oturum, sid, "T2", "1", "TL", "100")        # maliyetin altında
    _satis(oturum, sid, "T4", "1", "USD", "5000")      # 1 USD x 50 = 50 TL
    r = istemci.get(f"{A}/analiz/karlilik?senaryo={sid}")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["esik_marj"] == "0.10" and D_(d["esik_adet"]) == 1000   # medyan(100, 1000, 5000)
    k = {x["kod"]: x for x in d["kayitlar"]}
    t = k["TEST"]
    assert t["fiyat_kaynagi"] == "satis_gecmisi" and D_(t["satis_fiyati"]) == 100   # satış geçmişi hesaplanan fiyata tercih edilir
    assert D_(t["marj"]) == D_(100) / D_(t["maliyet"]) - 1 and D_(t["yillik_kar"]) == (100 - D_(t["maliyet"])) * 1000
    assert t["bolge"] == "yuksek_adet_yuksek_marj" and t["aile"]
    assert D_(k["T4"]["satis_fiyati"]) == 50 and k["T4"]["bolge"] == "yuksek_adet_yuksek_marj"
    assert k["T2"]["bolge"] == "dusuk_adet_dusuk_marj" and D_(k["T2"]["marj"]) < 0
    # satışı olmayan: hesaplanan satış fiyatı, adet/bölge/yıllık kâr null
    t3 = k["T3"]
    assert t3["fiyat_kaynagi"] == "hesap" and t3["adet"] is None and t3["bolge"] is None and t3["yillik_kar"] is None
    assert D_(t3["satis_fiyati"]) == hs.hesapla(oturum, "T3", sid).sonuc.satis_fiyati_tl
    assert [x["kod"] for x in d["kayitlar"]] == ["T4", "TEST", "T2", "T3"]   # yıllık kâr büyükten küçüğe, null sonda
    assert d["ozet"] == {"yuksek_adet_yuksek_marj": 2, "yuksek_adet_dusuk_marj": 0, "dusuk_adet_yuksek_marj": 0, "dusuk_adet_dusuk_marj": 1,
                         "adetsiz": 1, "hatali": 0}
    # marj eşiği parametresi bölgeyi değiştirir
    assert istemci.post(f"{A}/parametreler/marj_esigi/degerler?senaryo={sid}", json={"deger": "100", "gecerlilik_basi": "2026-06-01",
                                                                                     "neden": "eşik"}).status_code == 201
    k2 = {x["kod"]: x for x in istemci.get(f"{A}/analiz/karlilik?senaryo={sid}").json()["kayitlar"]}
    assert k2["TEST"]["bolge"] == "yuksek_adet_dusuk_marj"
    assert istemci.get(f"{A}/analiz/karlilik?senaryo=99999").status_code == 404
