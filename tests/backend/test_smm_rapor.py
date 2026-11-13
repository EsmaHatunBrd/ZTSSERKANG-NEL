"""SMM raporları: bütçe / fiili birim maliyet kıyası, aylar arası SMM karşılaştırması, ürün birim maliyet kartı.
Veri uydurma ve küçüktür: test_smm_asama'daki SMM Excel'i (bellekte) + test_api'deki bütçe kurulumu. Gerçek dosya okunmaz."""
from decimal import Decimal as D_
from tests.backend.test_api import _kur, _senaryo, istemci  # noqa: F401  (fixture)
from tests.backend.test_smm_asama import _excel

A = "/api/v1"


def _donem(c, ad="09-2026 SMM.xlsx"):
    r = c.post(f"{A}/smm/donemler/yukle", files={"dosya": (ad, _excel())})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _butce_urunu(c, sid, kod):
    """Bütçe tarafına SMM koduyla ürün: 1 kavanoz (5,9 TL, fire %2), test_api._kur'daki TEST ürünüyle aynı üretim hedefi."""
    assert c.put(f"{A}/urunler/{kod}", json={"ad": f"Bütçe {kod}", "ambalaj_hacmi": "370", "hat": "Niko", "taze_tursu_sinifi": "Turşu/Turşu",
                                            "suzme_kg": "0.18"}).status_code == 200
    assert c.put(f"{A}/urunler/{kod}/uretim-hedefi?senaryo={sid}", json={
        "vardiya_uretim_adedi": "65000", "dolum_personel": "13", "etiketleme_adedi": "35000", "etiket_personel": "7",
        "mal_kabul_miktar_kg": "0.19"}).status_code == 200
    assert c.post(f"{A}/urunler/{kod}/recete?senaryo={sid}", json=[
        {"malzeme_kodu": "KAV", "ad": "Kavanoz", "miktar": "1", "birim": "AD", "fire_override": "0.02"}]).status_code == 201


def _kiyas(c, did, sid):
    r = c.get(f"{A}/smm/donemler/{did}/butce-kiyas", params={"senaryo": sid, "tarih": "2026-10-21"})
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------- T1
def test_butce_kiyas_eslesen_ve_eslesmeyenler(istemci, oturum):  # noqa: F811
    did = _donem(istemci)
    sid = _senaryo(istemci)
    _kur(istemci, sid, oturum)   # bütçede yalnız TEST: SMM'de karşılığı yok
    v = _kiyas(istemci, did, sid)
    assert v["ozet"] == {"eslesen": 0, "karsilastirilan": 0, "uretimsiz": 0, "yalniz_butce": 1, "yalniz_fiili": 1,
                         "ortalama_fark_yuzde": None, "fiili_yuksek": 0}
    assert v["kayitlar"] == [] and v["senaryo"]["id"] == sid and v["donem"]["id"] == did
    yb = v["yalniz_butce"][0]
    assert yb["kod"] == "TEST" and yb["eslesme"] == "yok" and yb["stok_kartinda"] is False and D_(yb["butce_maliyet_tl"]) > 0
    # fiili tarafta yalnız üretilmiş 50 ürünü listelenir (03-2 üretilmedi)
    yf = v["yalniz_fiili"]
    assert [x["kod"] for x in yf] == ["03-1"] and D_(yf[0]["fiili_birim_maliyet_tl"]) == D_("26.6847") and D_(yf[0]["uretim_miktar"]) == 100

    _butce_urunu(istemci, sid, "03-1")   # üretilmiş
    _butce_urunu(istemci, sid, "03-2")   # reçetesi var, bu dönem üretilmedi
    v = _kiyas(istemci, did, sid)
    assert v["ozet"]["eslesen"] == 2 and v["ozet"]["karsilastirilan"] == 1 and v["ozet"]["uretimsiz"] == 1
    assert v["ozet"]["yalniz_butce"] == 1 and v["ozet"]["yalniz_fiili"] == 0 and v["yalniz_fiili"] == []
    k = {x["kod"]: x for x in v["kayitlar"]}
    x = k["03-1"]
    # bütçe tarafı Fiyat Çalışması hesabıyla aynı: üretim maliyeti = malzeme + üretim gideri (finansman, pazarlama, yönetim hariç)
    h = istemci.post(f"{A}/urunler/03-1/hesapla", json={"senaryo_id": sid, "tarih": "2026-10-21"}).json()
    malzeme = sum((D_(s["tutar"]) for s in h["satirlar"] if s["grup"] == "malzeme"), D_(0))
    assert abs(malzeme - D_("5.9") * D_("1.25") / D_("0.98")) < D_("1e-9")
    butce = D_(x["butce_maliyet_tl"])
    assert butce > malzeme and D_(x["butce_finansman_dahil_tl"]) == D_(h["toplamlar"]["maliyet_tl"]) and D_(x["butce_finansman_dahil_tl"]) > butce
    bd = x["butce_dokum"]
    assert abs(D_(bd["malzeme"]) + D_(bd["iscilik"]) + D_(bd["gug"]) + D_(bd["fire"]) - butce) < D_("1e-12")
    assert abs(D_(bd["malzeme"]) - D_("5.9") * D_("1.25")) < D_("1e-12") and D_(bd["fire"]) > 0   # firesiz malzeme; fire ayrı
    assert abs(malzeme + D_(bd["uretim_gideri"]) - butce) < D_("1e-12")
    # fiili taraf aşama hesabıyla aynı (test_smm_asama: 23,47 + 3 + 0,2147 = 26,6847)
    assert x["asama"] == 50 and x["eslesme"] == "kod" and x["uretildi"] is True and D_(x["uretim_miktar"]) == 100
    assert D_(x["fiili_birim_maliyet_tl"]) == D_("26.6847")
    fd = x["fiili_dokum"]
    assert (D_(fd["malzeme"]), D_(fd["iscilik"]), D_(fd["gug"]), D_(fd["fire"])) == (D_("23.47"), 3, 0, D_("0.2147"))
    assert D_(x["fark_tl"]) == D_("26.6847") - butce and abs(D_(x["fark_yuzde"]) - (D_("26.6847") - butce) / butce) < D_("1e-20")
    assert D_(v["ozet"]["ortalama_fark_yuzde"]) == D_(x["fark_yuzde"]) and v["ozet"]["fiili_yuksek"] == 1
    # üretilmeyen ürün: fiili birim maliyet var (alım kuralı 50) ama fark verilmez, ortalamaya girmez
    y = k["03-2"]
    assert y["uretildi"] is False and y["fark_tl"] is None and y["fark_yuzde"] is None and y["alim_kurali"] is True
    assert D_(y["fiili_birim_maliyet_tl"]) == 50 and y["butce_maliyet_tl"] is not None
    assert v["kayitlar"][-1]["kod"] == "03-2"   # farkı olmayan sonda


def test_butce_kiyas_404_ve_422(istemci, oturum):  # noqa: F811
    did = _donem(istemci)
    sid = _senaryo(istemci)
    assert istemci.get(f"{A}/smm/donemler/999/butce-kiyas", params={"senaryo": sid}).status_code == 404
    assert istemci.get(f"{A}/smm/donemler/{did}/butce-kiyas", params={"senaryo": 999}).status_code == 404
    r = istemci.get(f"{A}/smm/donemler/{did}/butce-kiyas")   # senaryo zorunlu
    assert r.status_code == 422 and set(r.json()) == {"hata", "mesaj", "alanlar", "kod"}
    # boş senaryo: hata değil, boş kıyas
    v = _kiyas(istemci, did, sid)
    assert v["kayitlar"] == [] and v["yalniz_butce"] == [] and [x["kod"] for x in v["yalniz_fiili"]] == ["03-1"]


# ---------------------------------------------------------------- T2
def _satir(v, anahtar):
    return next(x for x in v["satirlar"] if x["anahtar"] == anahtar)


def test_karsilastirma_tek_donem(istemci):  # noqa: F811
    assert istemci.get(f"{A}/smm/karsilastirma").json() == {"donemler": [], "satirlar": []}   # hiç dönem yok
    did = _donem(istemci)
    v = istemci.get(f"{A}/smm/karsilastirma").json()
    o = istemci.get(f"{A}/smm/donemler/{did}/ozet").json()
    assert [d["id"] for d in v["donemler"]] == [did]
    assert [x["anahtar"] for x in v["satirlar"]] == ["ilk_madde", "iscilik", "gug", "uretim_maliyeti", "yari_mamul_donem_basi",
                                                     "yari_mamul_donem_sonu", "uretilen", "mamul_donem_basi", "mamul_donem_sonu", "smm"]
    for x in v["satirlar"]:
        assert len(x["hucreler"]) == 1 and x["hucreler"][0]["degisim_tl"] is None and x["hucreler"][0]["degisim_yuzde"] is None
        assert x["son_fark_tl"] is None and x["son_fark_yuzde"] is None
    # değerler ve satır adları SMM özetindekilerle aynı
    for anahtar, alan in (("ilk_madde", "ilk_madde"), ("uretim_maliyeti", "uretim_maliyeti"), ("uretilen", "uretilen"), ("smm", "smm")):
        assert _satir(v, anahtar)["hucreler"][0]["tutar"] == o[alan]
    assert D_(_satir(v, "iscilik")["hucreler"][0]["tutar"]) == 1000 and D_(_satir(v, "gug")["hucreler"][0]["tutar"]) == 5000
    assert _satir(v, "smm")["ad"] == "620 · Satılan mamul maliyeti" and _satir(v, "smm")["vurgulu"] is True
    assert _satir(v, "iscilik")["ad"].startswith("720") and _satir(v, "yari_mamul_donem_sonu")["ad"].startswith("151 Yarı mamuller · Dönem sonu")
    b151 = next(b for b in o["tablo"] if b["hesap"] == "151")
    ds = next(s for s in b151["satirlar"] if s["ad"].startswith("Dönem sonu"))
    assert _satir(v, "yari_mamul_donem_sonu")["hucreler"][0]["tutar"] == ds["tutar"]


def test_karsilastirma_iki_donem_degisim(istemci):  # noqa: F811
    eylul = _donem(istemci)
    ekim = _donem(istemci, "10-2026 SMM.xlsx")
    assert istemci.put(f"{A}/smm/donemler/{ekim}/ayarlar", json={"gider_720": "1500"}).status_code == 200
    for sorgu in ({}, {"donemler": f"{ekim},{eylul}"}, {"donemler": f" {eylul}, {ekim},{eylul} "}):   # sıra her zaman en eski başta
        v = istemci.get(f"{A}/smm/karsilastirma", params=sorgu).json()
        assert [d["id"] for d in v["donemler"]] == [eylul, ekim] and [d["ay"] for d in v["donemler"]] == [9, 10]
        isc = _satir(v, "iscilik")
        assert [h["donem_id"] for h in isc["hucreler"]] == [eylul, ekim]
        assert D_(isc["hucreler"][0]["tutar"]) == 1000 and isc["hucreler"][0]["degisim_tl"] is None
        assert D_(isc["hucreler"][1]["tutar"]) == 1500 and D_(isc["hucreler"][1]["degisim_tl"]) == 500
        assert D_(isc["hucreler"][1]["degisim_yuzde"]) == D_("0.5")
        assert D_(isc["son_fark_tl"]) == 500 and D_(isc["son_fark_yuzde"]) == D_("0.5")
        gug = _satir(v, "gug")
        assert D_(gug["son_fark_tl"]) == 0 and D_(gug["son_fark_yuzde"]) == 0
        smm = _satir(v, "smm")
        assert D_(smm["son_fark_tl"]) == 500 and D_(smm["hucreler"][1]["tutar"]) == D_(smm["hucreler"][0]["tutar"]) + 500
    tek = istemci.get(f"{A}/smm/karsilastirma", params={"donemler": str(ekim)}).json()
    assert [d["id"] for d in tek["donemler"]] == [ekim] and _satir(tek, "smm")["son_fark_tl"] is None
    assert istemci.get(f"{A}/smm/karsilastirma", params={"donemler": f"{eylul},999"}).status_code == 404
    assert istemci.get(f"{A}/smm/karsilastirma", params={"donemler": "1,abc"}).status_code == 422
    assert istemci.get(f"{A}/smm/karsilastirma", params={"donemler": ",".join(str(i) for i in range(1, 14))}).status_code == 422


# ---------------------------------------------------------------- T3
def test_maliyet_karti_asamalar_ve_recete(istemci):  # noqa: F811
    did = _donem(istemci)
    r = istemci.get(f"{A}/smm/donemler/{did}/urun/03-1/maliyet-karti")
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["kod"] == "03-1" and v["asama"] == 50 and v["birim"] == "AD" and v["onceki"] is None   # önceki dönem yok
    assert D_(v["birim_maliyet"]) == D_("26.6847") and D_(v["uretim_miktar"]) == 100 and D_(v["toplam"]) == D_("2668.47")
    # aşama zinciri: 50 (kendisi) -> 40 (02-1) -> 20 (01-1); değerler aşama hesabıyla aynı
    assert [(a["asama"], a["kod"], a["ust_kod"]) for a in v["asamalar"]] == [(50, "03-1", None), (40, "02-1", "03-1"), (20, "01-1", "02-1")]
    a50, a40, a20 = v["asamalar"]
    assert a50["ad"] == "Etiketleme" and a50["carpan"] is None
    assert (D_(a50["malzeme"]), D_(a50["iscilik"]), D_(a50["gug"]), D_(a50["fire"]), D_(a50["birim_maliyet"])) == (
        D_("23.47"), 3, 0, D_("0.2147"), D_("26.6847"))
    assert (D_(a40["malzeme"]), D_(a40["iscilik"]), D_(a40["gug"]), D_(a40["birim_maliyet"]), D_(a40["carpan"])) == (D_("7.47"), 4, 10, D_("21.47"), 1)
    assert (D_(a20["malzeme"]), D_(a20["iscilik"]), D_(a20["fire"]), D_(a20["birim_maliyet"]), D_(a20["carpan"]), D_(a20["uretim_miktar"])) == (
        6, 2, D_("0.6"), D_("8.6"), D_("0.2"), 500)
    # reçete satırları mevcut ürün reçetesi ucuyla birebir
    assert v["satirlar"] == istemci.get(f"{A}/smm/donemler/{did}/uretim/50/03-1").json()["satirlar"]
    k = {s["malzeme_kod"]: s for s in v["satirlar"]}
    assert k["02-1"]["fiyat_kaynagi"] == "asama_40" and D_(k["02-1"]["fiyat"]) == D_("21.47") and D_(k["ETK-1"]["tutar"]) == 2
    # yarı mamulün kartı: kendi aşaması 40, altında 20
    ym = istemci.get(f"{A}/smm/donemler/{did}/urun/02-1/maliyet-karti").json()
    assert ym["asama"] == 40 and [(a["asama"], a["kod"]) for a in ym["asamalar"]] == [(40, "02-1"), (20, "01-1")]
    assert D_(ym["birim_maliyet"]) == D_("21.47") and len(ym["satirlar"]) == 2


def test_maliyet_karti_onceki_donem_farki_ve_404(istemci):  # noqa: F811
    eylul = _donem(istemci)
    ekim = _donem(istemci, "10-2026 SMM.xlsx")
    # Ekim'de 50 havuzu 300 -> 600: 03-1 işçiliği 3 -> 6, birim maliyet 26,6847 -> 29,6847
    assert istemci.put(f"{A}/smm/donemler/{ekim}/dagitim", json={"havuzlar": {"50_uretim": "600"}}).status_code == 200
    v = istemci.get(f"{A}/smm/donemler/{ekim}/urun/03-1/maliyet-karti").json()
    assert D_(v["birim_maliyet"]) == D_("29.6847")
    o = v["onceki"]
    assert o["donem"]["id"] == eylul and o["asama"] == 50 and D_(o["birim_maliyet"]) == D_("26.6847") and D_(o["uretim_miktar"]) == 100
    assert D_(o["fark_tl"]) == 3 and abs(D_(o["fark_yuzde"]) - D_(3) / D_("26.6847")) < D_("1e-20")
    assert istemci.get(f"{A}/smm/donemler/{eylul}/urun/03-1/maliyet-karti").json()["onceki"] is None
    # Excel'siz devirle açılan dönemde (kalıcı reçete yok) ürünün aşama reçetesi yok: 404; önceki dönemde ürün yoksa onceki null
    r = istemci.post(f"{A}/smm/donemler", json={"yil": 2026, "ay": 11})
    assert r.status_code == 201, r.text
    kasim = r.json()["id"]
    r = istemci.get(f"{A}/smm/donemler/{kasim}/urun/03-1/maliyet-karti")
    assert r.status_code == 404 and set(r.json()) == {"hata", "mesaj", "alanlar", "kod"}
    assert istemci.get(f"{A}/smm/donemler/{ekim}/urun/YOK/maliyet-karti").status_code == 404
    assert istemci.get(f"{A}/smm/donemler/999/urun/03-1/maliyet-karti").status_code == 404
    # hiçbir uç kayıt değiştirmez: günlükte rapor kaynaklı satır yok, aşama sonucu aynı
    assert D_(istemci.get(f"{A}/smm/donemler/{ekim}/uretim/50/03-1").json()["urun"]["birim_maliyet"]) == D_("29.6847")
