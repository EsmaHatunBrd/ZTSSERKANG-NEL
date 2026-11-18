"""Yönetim özeti (analiz önerisi 15): gerçek kitapla uç 200 + şema + diğer uçlarla tutarlılık; küçük kurulumla teklif ve stok etkisi.
Şirket verisi test çıktısına yazılmaz (yalnız kod ve sayılar)."""
from decimal import Decimal as D_
import pytest
from fastapi.testclient import TestClient
from backend.depo import modeller as m
from backend.depo.veritabani import Base, motor_olustur, oturum_fabrikasi, oturum_ver
from backend.servisler import import_servisi as ims, stok_devri_servisi as sd, yonetim_ozeti_servisi as yo
from backend.uygulama import uygulama_olustur
from tests.backend.test_analiz_2 import _kurulum, _satis
from tests.backend.test_api import _senaryo, istemci  # noqa: F401  (fixture)

A = "/api/v1"
BOLUMLER = {"baslik", "urunler", "marj", "maliyet_yapisi", "hedef_alti", "kur_riski", "teklifler", "veri_kontrolu", "en_pahali", "stok_etkisi", "uyarilar"}


@pytest.fixture(scope="module")
def ortam(excel_yolu):
    engine = motor_olustur("sqlite://"); Base.metadata.create_all(engine)
    s = oturum_fabrikasi(engine)()
    sid = ims.excel_tam_yukle(s, excel_yolu, "2026-2027", "Bütçe")["senaryo_id"]
    s.commit()
    app = uygulama_olustur()
    app.dependency_overrides[oturum_ver] = lambda: s
    yield TestClient(app), s, sid
    s.close()


def test_gercek_kitap_uc_sema_ve_tutarlilik(ortam):
    c, s, sid = ortam
    r = c.get(f"{A}/yonetim/ozet?senaryo={sid}")
    assert r.status_code == 200, r.text
    assert r.headers["X-Onbellek"] == "hesap"
    d = r.json()
    assert set(d) == BOLUMLER
    b = d["baslik"]
    assert b["senaryo_id"] == sid and b["sezon_ad"] == "2026-2027" and b["ad"] == "Bütçe" and b["uretim_zamani"].endswith("+00:00")
    # ürün sayıları Genel Bakış ile aynı
    urunler = c.get(f"{A}/urunler?senaryo={sid}&boyut=500").json()
    assert d["urunler"]["toplam"] == urunler["toplam"] and d["urunler"]["hesaplanan"] + d["urunler"]["hatali"] == d["urunler"]["toplam"]
    assert d["urunler"]["hatali"] == sum(1 for x in urunler["kayitlar"] if x["hata"]) == len(d["uyarilar"]) <= 10
    # maliyet yapısı: toplam = Σ Genel Bakış maliyet TL; kalem payları %100; kalemler Genel Bakış sütunlarıyla aynı
    my = d["maliyet_yapisi"]
    satirlar = [x for x in urunler["kayitlar"] if x["hata"] is None]
    assert my["urun_sayisi"] == len(satirlar) == d["urunler"]["hesaplanan"]
    assert D_(my["toplam_tl"]) == sum(D_(x["maliyet_tl"]) for x in satirlar)
    assert set(my["kalemler"]) == {"malzeme", "uretim", "faaliyet", "finansman"}
    for kalem, sutun in (("malzeme", "recete_maliyeti"), ("uretim", "gug"), ("faaliyet", "faaliyet"), ("finansman", "finans")):
        assert D_(my["kalemler"][kalem]["toplam_tl"]) == sum(D_(x[sutun]) for x in satirlar)
    paylar = sum(D_(k["pay_yuzde"]) for k in my["kalemler"].values())
    assert abs(paylar - 100) < D_("1e-9")
    assert D_(my["urun_basina_tl"]) == D_(my["toplam_tl"]) / len(satirlar)
    # marj: kitapta kâr oranı %20; eşik %10
    mj = d["marj"]
    assert D_(mj["hedef"]) == D_("0.2") and D_(mj["marj_esigi"]) == D_("0.10") and mj["adet_kaynagi"] == "satis_gecmisi"
    assert abs(D_(mj["ortalama"]) - D_("0.2")) < D_("1e-9")
    assert mj["agirlikli_ortalama"] is None and mj["adetli_urun"] == 0   # satış geçmişi yüklü değil
    assert mj["gecen_yil_agirlikli_ortalama"] is None and mj["gecen_yil_urun"] == 0
    assert all(x["fiyat_kaynagi"] == "hesap" for x in d["hedef_alti"]["kayitlar"])
    # hedef altı sayısı Veri Kontrolü ile aynı (kitapta 0)
    kontrol = {k["kod"]: k for k in c.get(f"{A}/tutarlilik?senaryo={sid}").json()["kontroller"]}
    assert d["hedef_alti"]["toplam"] == kontrol["hedef_alti"]["sayi"] == 0 and D_(d["hedef_alti"]["esik"]) == D_("0.10")
    # veri kontrolü özeti = tutarlılık ucu özeti; sorunlar = hata/dikkat olanlar
    oz = c.get(f"{A}/tutarlilik?senaryo={sid}").json()["ozet"]
    vk = d["veri_kontrolu"]
    assert {k: vk[k] for k in ("hata", "dikkat", "bilgi", "tamam")} == oz
    assert [x["kod"] for x in vk["sorunlar"]] == [k["kod"] for k in kontrol.values() if k["durum"] in ("hata", "dikkat")]
    assert all(x["sayi"] == kontrol[x["kod"]]["sayi"] for x in vk["sorunlar"])
    # en pahalı: birim maliyete göre ilk 5, azalan; Genel Bakış ile aynı
    beklenen = sorted(satirlar, key=lambda x: (-D_(x["maliyet_tl"]), x["kod"]))[:5]
    assert [x["kod"] for x in d["en_pahali"]] == [x["kod"] for x in beklenen]
    assert [D_(x["maliyet"]) for x in d["en_pahali"]] == [D_(x["maliyet_tl"]) for x in beklenen]
    # kur riski: analiz ucuyla aynı özet
    kr = c.get(f"{A}/analiz/kur-riski?senaryo={sid}").json()
    assert d["kur_riski"]["kurlar"] == kr["kurlar"] and d["kur_riski"]["oran"] == "0.10"
    assert D_(d["kur_riski"]["yillik_etki_tl"]) == D_(kr["ozet"]["yillik_etki"])
    assert [x["kod"] for x in d["kur_riski"]["en_riskli"]] == [x["kod"] for x in kr["kayitlar"] if x["hata"] is None][:5]
    if kr["ozet"]["doviz_payi_ort"] is not None:
        assert D_(d["kur_riski"]["doviz_payi_yuzde"]) == D_(kr["ozet"]["doviz_payi_ort"]) * 100
    # teklif ve stok kaydı yok
    assert d["teklifler"] == {"toplam": 0, "durumlar": {"taslak": 0, "gonderildi": 0, "kabul": 0, "red": 0}, "acik_sayi": 0, "acik_toplam_tl": "0", "en_eski_acik": []}
    assert d["stok_etkisi"] is None
    # önbellek: ikinci istek isabet, yenile=1 hesap
    assert c.get(f"{A}/yonetim/ozet?senaryo={sid}").headers["X-Onbellek"] == "isabet"
    assert c.get(f"{A}/yonetim/ozet?senaryo={sid}&yenile=1").headers["X-Onbellek"] == "hesap"
    assert c.get(f"{A}/yonetim/ozet?senaryo=9999").status_code == 404


def test_teklif_ve_stok_etkisi(istemci, oturum):
    sid = _senaryo(istemci); _kurulum(istemci, sid, oturum)
    _satis(oturum, sid, "TEST", "100", "TL", "1000")
    _satis(oturum, sid, "T2", "1", "TL", "100")
    d = istemci.get(f"{A}/yonetim/ozet?senaryo={sid}").json()
    assert d["urunler"] == {"toplam": 4, "hesaplanan": 4, "hatali": 0} and d["uyarilar"] == []
    assert d["teklifler"]["acik_sayi"] == 0 and d["stok_etkisi"] is None
    # ağırlıklı marj: adedi bilinen 2 ürün (TEST 1000, T2 100); kâr oranı her üründe 0,20 -> ağırlıklı da 0,20
    assert d["marj"]["adetli_urun"] == 2 and abs(D_(d["marj"]["agirlikli_ortalama"]) - D_("0.2")) < D_("1e-9")
    # geçen yılın satış fiyatıyla marj: Kârlılık haritasıyla aynı kaynak ve formül (adetle ağırlıklı, yalnız satış geçmişi olan ürünler)
    kh = {x["kod"]: x for x in istemci.get(f"{A}/analiz/karlilik?senaryo={sid}").json()["kayitlar"]}
    gy = [x for x in kh.values() if x["fiyat_kaynagi"] == "satis_gecmisi" and x["adet"] is not None]
    beklenen = sum((D_(x["satis_fiyati"]) - D_(x["maliyet"])) * D_(x["adet"]) for x in gy) / sum(D_(x["maliyet"]) * D_(x["adet"]) for x in gy)
    assert d["marj"]["gecen_yil_urun"] == len(gy) == 2 and D_(d["marj"]["gecen_yil_agirlikli_ortalama"]) == beklenen
    # marj eşiği altı: Kârlılık haritasının marjıyla (geçen yıl fiyatı; yoksa hesaplanan) eşiğin altında kalanlar, kaynağı satırda
    ha = d["hedef_alti"]
    alti = sorted((x for x in kh.values() if x["marj"] is not None and D_(x["marj"]) < D_(ha["esik"])), key=lambda x: (D_(x["marj"]), x["kod"]))
    assert ha["toplam"] == len(alti) >= 1 and [x["kod"] for x in ha["kayitlar"]] == [x["kod"] for x in alti]
    for x in ha["kayitlar"]:
        assert D_(x["kar_orani"]) == D_(kh[x["kod"]]["marj"]) and D_(x["satis"]) == D_(kh[x["kod"]]["satis_fiyati"])
        assert x["fiyat_kaynagi"] == ("gecen_yil" if kh[x["kod"]]["fiyat_kaynagi"] == "satis_gecmisi" else "hesap")
    assert ha["kayitlar"][0]["kod"] == "T2" and ha["kayitlar"][0]["fiyat_kaynagi"] == "gecen_yil"   # 1 TL'ye satılmış: eksi marj
    # teklif ekle (taslak): açık sayı ve açık toplam artar; en eski açık listede
    hid = istemci.post(f"{A}/urunler/TEST/hesaplar", json={"senaryo_id": sid, "tarih": "2026-10-21"}).json()["id"]
    r = istemci.post(f"{A}/hesaplar/{hid}/teklifler", json={"kar_orani": "0.2", "musteri": "Müşteri A"})
    assert r.status_code == 201
    t1 = r.json()
    assert istemci.post(f"{A}/hesaplar/{hid}/teklifler", json={"kar_orani": "0.3"}).status_code == 201
    t3 = istemci.post(f"{A}/hesaplar/{hid}/teklifler", json={"kar_orani": "0.1"}).json()
    assert istemci.patch(f"{A}/teklifler/{t3['id']}/durum", json={"durum": "kabul"}).status_code == 200
    r = istemci.get(f"{A}/yonetim/ozet?senaryo={sid}")
    assert r.headers["X-Onbellek"] == "hesap"   # yazma isteği önbelleği boşalttı
    tk = r.json()["teklifler"]
    assert tk["toplam"] == 3 and tk["durumlar"] == {"taslak": 2, "gonderildi": 0, "kabul": 1, "red": 0} and tk["acik_sayi"] == 2
    acik = tk["en_eski_acik"]
    assert [x["teklif_id"] for x in acik] == [t1["id"], acik[1]["teklif_id"]] and acik[0]["urun_kodu"] == "TEST" and acik[0]["musteri"] == "Müşteri A"
    assert acik[0]["durum"] == "taslak" and acik[0]["tur_no"] == 1 and acik[0]["hesap_tarihi"] == "2026-10-21" and acik[0]["tarih"].endswith("+00:00")
    assert D_(tk["acik_toplam_tl"]) == sum(D_(x["fiyat_tl"]) for x in acik)
    # stok devri kaydı: etkili ürün, toplam etki = adet x (güncel stok maliyeti - bu yılın maliyeti)
    sen = oturum.get(m.Senaryo, sid); u = oturum.query(m.Urun).filter_by(kod="TEST").one()
    sd.kaydet(oturum, sen, u, "200", "50", None, "800", neden="test"); oturum.commit()
    d = istemci.get(f"{A}/yonetim/ozet?senaryo={sid}&yenile=1").json()
    st = d["stok_etkisi"]
    assert st["kayit_sayisi"] == 1 and st["etkili_urun"] == 1 and D_(st["stok_adedi"]) == 200 and st["satis_ortalama_maliyetten"] is False
    bu_yil = D_(istemci.get(f"{A}/urunler/TEST/stok-devri?senaryo={sid}").json()["bu_yil_maliyet"])
    assert D_(st["toplam_etki_tl"]) == 200 * (D_(50) * D_("1.25") - bu_yil)
    assert istemci.post(f"{A}/parametreler/satis_ortalama_maliyetten/degerler?senaryo={sid}", json={"deger": "1", "gecerlilik_basi": "2026-06-01", "neden": "test"}).status_code == 201
    assert istemci.get(f"{A}/yonetim/ozet?senaryo={sid}").json()["stok_etkisi"]["satis_ortalama_maliyetten"] is True
    # servis doğrudan: senaryo yok -> 404 hatası
    from backend.servisler.hatalar import BulunamadiHatasi
    with pytest.raises(BulunamadiHatasi):
        yo.ozet(oturum, 9999)
