"""Analizler 1. dalga: ya olursa, zam etkisi, hedef marj altı, fiyat girişi sapma onayı."""
from decimal import Decimal as D_
from backend.servisler import analiz_servisi as an
from tests.backend.test_api import _kur, _senaryo, istemci  # noqa: F401  (fixture)

A = "/api/v1"


def _ya(c, sid, **q):
    ek = "".join(f"&{k}={v}" for k, v in q.items())
    r = c.get(f"{A}/analiz/ya-olursa?senaryo={sid}{ek}")
    assert r.status_code == 200, r.text
    return r.json()


def test_ya_olursa_varsayimlar(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    sifir = _ya(istemci, sid)
    r0 = sifir["kayitlar"][0]
    assert r0["kod"] == "TEST" and D_(r0["fark_tl"]) == 0 and sifir["ozet"]["etkilenen"] == 0 and sifir["marj_esigi"] == "0.10"
    # ambalaj %10: kavanoz (ambalaj tipi) pahalanır -> maliyet artar; satış fiyatı aynı kalırsa kâr oranı %20'nin altına iner
    amb = _ya(istemci, sid, ambalaj="0.1")["kayitlar"][0]
    assert D_(amb["maliyet_sonra"]) > D_(amb["maliyet_once"]) and D_(amb["fark_yuzde"]) > 0
    assert D_(amb["mevcut_fiyatla_kar"]) < D_("0.2") and D_(amb["kar_orani"]) == D_("0.2")
    # hammadde %10: reçetede hammadde yok -> değişmez
    assert D_(_ya(istemci, sid, hammadde="0.1")["kayitlar"][0]["fark_tl"]) == 0
    # üretim adedi +%100: saniye bazlı giderler yarıya iner -> maliyet düşer
    assert D_(_ya(istemci, sid, adet="1")["kayitlar"][0]["fark_tl"]) < 0
    # büyük zam: kâr eşiğin altına düşer
    buyuk = _ya(istemci, sid, ambalaj="3")
    assert buyuk["kayitlar"][0]["esik_alti"] is True and buyuk["ozet"]["esik_alti"] == 1
    assert istemci.get(f"{A}/analiz/ya-olursa?senaryo={sid}&kur=-1").status_code == 422
    assert istemci.get(f"{A}/analiz/ya-olursa?senaryo={sid}&kur=6").status_code == 422


def test_zam_etkisi(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    r = istemci.get(f"{A}/analiz/zam-etkisi?senaryo={sid}&malzeme=KAV&oran=0.2")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["malzeme"]["kod"] == "KAV" and D_(d["malzeme"]["yeni_fiyat"]) == D_("5.9") * D_("1.2")
    assert [k["kod"] for k in d["kayitlar"]] == ["TEST"] and D_(d["kayitlar"][0]["fark_tl"]) > 0
    # zam etkisi ile ya olursa aynı fiyat değişiminde aynı sonucu verir (tek ambalaj malzemesi)
    ya = _ya(istemci, sid, ambalaj="0.2")["kayitlar"][0]
    assert abs(D_(ya["maliyet_sonra"]) - D_(d["kayitlar"][0]["maliyet_sonra"])) < D_("0.0001")
    assert istemci.get(f"{A}/analiz/zam-etkisi?senaryo={sid}&malzeme=YOK&oran=0.2").status_code == 404


def test_hedef_alti_ve_parametre_esigi(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    assert an.hedef_alti(oturum, sid) == (D_("0.10"), [])
    u = istemci.get(f"{A}/urunler/TEST").json()
    assert istemci.post(f"{A}/parametreler/satis_kar/degerler?senaryo={sid}", json={"deger": "0.08", "gecerlilik_basi": "2026-06-01", "neden": "kampanya",
                        "kapsam_tipi": "urun", "kapsam_id": u["id"]}).status_code == 201
    esik, alti = an.hedef_alti(oturum, sid)
    assert [x["kod"] for x in alti] == ["TEST"] and alti[0]["kar_orani"] == D_("0.08")
    assert istemci.post(f"{A}/parametreler/marj_esigi/degerler?senaryo={sid}", json={"deger": "0.05", "gecerlilik_basi": "2026-06-01", "neden": "eşik"}).status_code == 201
    assert an.hedef_alti(oturum, sid)[1] == []
    k = {x["kod"]: x for x in istemci.get(f"{A}/tutarlilik?senaryo={sid}").json()["kontroller"]}
    assert k["hedef_alti"]["durum"] == "tamam" and "%5" in k["hedef_alti"]["aciklama"]


def test_fiyat_girisi_sapma_onayi(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    yol = f"{A}/malzemeler/KAV/fiyatlar?senaryo={sid}"
    govde = {"fiyat": "7", "gecerlilik_basi": "2026-07-01", "neden": "zam"}
    r = istemci.post(yol, json=govde)   # 5,9 -> 7 = %18,6 > %15 (TL eşiği)
    assert r.status_code == 422 and r.json()["kod"] == "fiyat_sapma"
    a = r.json()["alanlar"]
    assert (a["eski_fiyat"], a["yeni_fiyat"], a["esik"]) == ("5.9", "7", "0.15") and D_(a["oran"]) > D_("0.18")
    assert istemci.post(yol, json={**govde, "onay": True}).status_code == 201
    assert istemci.post(yol, json={"fiyat": "7.5", "gecerlilik_basi": "2026-07-02", "neden": "küçük"}).status_code == 201   # %7
    # eşik parametreyle değişir
    assert istemci.post(f"{A}/parametreler/fiyat_uyari_esigi.TL/degerler?senaryo={sid}",
                        json={"deger": "0.5", "gecerlilik_basi": "2026-06-01", "neden": "geniş eşik"}).status_code == 201
    assert istemci.post(yol, json={"fiyat": "10", "gecerlilik_basi": "2026-07-03", "neden": "x"}).status_code == 201   # %33 < %50
