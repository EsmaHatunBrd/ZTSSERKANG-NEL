"""SMM 2. adım: 20 -> 40 -> 50 aşama maliyet zinciri, dağıtım havuzları ve reçete sarfı ile sayım sarfının farkı.
Uydurma küçük bir SMM Excel'i; beklenen değerler elle hesaplandı (aşağıdaki açıklamalar)."""
from decimal import Decimal as D_
from io import BytesIO
from openpyxl import Workbook
from backend.depo import modeller as m
from tests.backend.test_api import istemci  # noqa: F401  (fixture)

A = "/api/v1"


def _satir(ana, ad, mal, miktar, birim, fire_i, fire=0, birim_i=None, birim_degeri=None, ana_miktar=1):
    r = [ana, ad, ana_miktar, "AD", mal, mal, miktar, birim] + [None] * (fire_i - 8) + [fire]
    if birim_i is not None and birim_degeri is not None:
        r[birim_i] = birim_degeri
    return r


def _excel() -> bytes:
    wb = Workbook()
    wb.remove(wb.active)

    def sayfa(ad, satirlar, ust=None, bas_bos=True):
        ws = wb.create_sheet(ad)
        if bas_bos:
            ws.append(ust or [])
            ws.append(["başlık"])
        for s in satirlar:
            ws.append(s)

    def ust(**h):
        r = [None] * 30
        for i, v in h.items():
            r[int(i[1:])] = v
        return r

    sayfa("ENVANTER", [["HM-1", "Biber", "KG", "0001-Hammadde", "150.01.001"], ["AMB-1", "Kavanoz", "AD", "0008-Ambalaj Malzeme", "150.03.031"],
                       ["ETK-1", "Etiket", "AD", "0008-Ambalaj Malzeme", "150.03.032"], ["01-1", "Biber salamura", "KG", "0002-Üretim Yarı Mamul", "151.04.002"]])
    sayfa("DBS", [["HM-1", "Biber", 100, 1000], ["AMB-1", "Kavanoz", 50, 250]])
    sayfa("HM-YM ALIŞ SATIŞ", [[None, "HM-1", "Biber", 9, 9, "KG", 100, 1400, 0, 0, 1400], [None, "AMB-1", "Kavanoz", 9, 9, "AD", 150, 900, 0, 0, 900],
                               [None, "ETK-1", "Etiket", 9, 9, "AD", 10, 20, 0, 0, 20], [None, "03-2", "Hazır kavanoz", 9, 9, "AD", 10, 500, 0, 0, 500]])
    sayfa("ÜRETİM", [["01-1", "Biber salamura"] + [0] * 12 + [500], ["02-1", "Biber 370"] + [0] * 12 + [100], ["03-1", "Biber 370 etiketli"] + [0] * 12 + [100]])
    sayfa("DSS", [["HM-1", "Biber", 40]])
    # 20: 01-1 = 0,5 KG biber (fire %10). Excel birim maliyeti doğru yazıldı (8,6).
    sayfa("20 KOD", [_satir("01-1", "Biber salamura", "HM-1", 0.5, "KG", 23, 0.1, 20, 8.6)], ust=ust(c15=0, c18=1000))
    # 40: 02-1 = 0,2 KG 01-1 + 1 kavanoz. Excel birim maliyeti doğru (21,47).
    sayfa("40 KOD", [_satir("02-1", "Biber 370", "01-1", 0.2, "KG", 31, 0, 22, 21.47), _satir("02-1", "Biber 370", "AMB-1", 1, "AD", 31)],
          ust=ust(c15=0, c20=400, c25=0, c28=1000))
    # 50: 03-1 = 1 adet 02-1 (fire %1) + 1 etiket; Excel birim maliyeti bilerek yanlış (99). 03-2 alımla geliyor (alım kuralı).
    sayfa("50 KOD", [_satir("03-1", "Biber 370 etiketli", "02-1", 1, "AD", 25, 0.01, 22, 99), _satir("03-1", "Biber 370 etiketli", "ETK-1", 1, "AD", 25),
                     _satir("03-2", "Hazır kavanoz", "ETK-1", 1, "MT", 25)], ust=ust(c15=0, c20=300))   # MT: kartta AD -> birim uyumsuz
    # 51: 02-1 (C sütunu) dolum 0,5 sn, etiket adam/sn 2; 03-1 (B sütunu) dolum 1 sn
    sayfa("51", [[None, None, "02-1", "Biber 370", None, None, None, "Adet", 0.2, 50000, None, 12, 6, None, 7.5, 0.5, 6, 0.5, 2],
                 [None, "03-1", None, "Biber 370 etiketli", None, None, None, "Adet", 0.2, 50000, None, 12, 6, None, 7.5, 1, 6, 1, 3]])
    sayfa("GİDER MİZAN", [["Hesap Kodu"], ["720", "İşçilik", 0, 0, 0, 0, 1000], ["730", "GÜG", 0, 0, 0, 0, 5000]], bas_bos=False)
    sayfa("TABLO", [], ust=[None] * 9 + [0])
    b = BytesIO()
    wb.save(b)
    return b.getvalue()


def _yukle(istemci):
    r = istemci.post(f"{A}/smm/donemler/yukle", files={"dosya": ("09-2026 SMM.xlsx", _excel())})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _urun(veri, kod):
    return next(x for x in veri["kayitlar"] if x["kod"] == kod)


def test_asama_zinciri_excel_kurallariyla(istemci):  # noqa: F811
    did = _yukle(istemci)
    # 20: malzeme 0,5 × 12 = 6; işçilik 1000 / 500 = 2; fire 0,5 × 0,1 × 12 = 0,6 -> 8,6
    v = istemci.get(f"{A}/smm/donemler/{did}/uretim", params={"asama": 20}).json()
    x = _urun(v, "01-1")
    assert D_(x["malzeme"]) == 6 and D_(x["iscilik"]) == 2 and D_(x["fire"]) == D_("0.6") and D_(x["birim_maliyet"]) == D_("8.6")
    assert D_(x["toplam"]) == D_("4300") and x["excel_farkli"] is False
    # 40: 01-1 envanterde -> envanter fiyatı (500 × 8,6) / 500 = 8,6; kavanoz 1150 / 200 = 5,75 -> malzeme 1,72 + 5,75 = 7,47
    #     işçilik 400 × (100 × 2 / 200) / 100 = 4; GÜG 1000 × (100 × 0,5 / 50) / 100 = 10 -> 21,47
    v = istemci.get(f"{A}/smm/donemler/{did}/uretim", params={"asama": 40}).json()
    x = _urun(v, "02-1")
    assert D_(x["malzeme"]) == D_("7.47") and D_(x["iscilik"]) == 4 and D_(x["gug"]) == 10 and D_(x["birim_maliyet"]) == D_("21.47")
    # 50: 02-1 envanterde yok -> 40 birim maliyeti 21,47; etiket 20 / 10 = 2 -> malzeme 23,47; işçilik 300 / 100 = 3; fire 0,01 × 21,47
    v = istemci.get(f"{A}/smm/donemler/{did}/uretim", params={"asama": 50}).json()
    x = _urun(v, "03-1")
    assert D_(x["malzeme"]) == D_("23.47") and D_(x["iscilik"]) == 3 and D_(x["fire"]) == D_("0.2147")
    assert D_(x["birim_maliyet"]) == D_("26.6847") and x["excel_farkli"] is True and D_(x["excel_birim"]) == 99
    # 03-2: hesap (2) alım fiyatından (500 / 10 = 50) düşük -> alım fiyatı esas alınır
    y = _urun(v, "03-2")
    assert y["alim_kurali"] is True and D_(y["birim_maliyet"]) == 50
    oz = {o["asama"]: o for o in v["ozetler"]}
    assert oz[20]["excel"]["esit"] == 1 and oz[40]["excel"]["esit"] == 1 and oz[50]["excel"]["farkli"] == 1
    assert D_(oz[50]["toplam"]) == D_("2668.47")
    # dağıtım: 1000 + 400 + 1000 + 300 = 2700; mizan 720 + 730 = 6000 -> dağıtılmayan 3300
    dg = v["dagitim"]
    assert D_(dg["dagitilan"]) == 2700 and D_(dg["dagitilmayan"]) == 3300
    # yalnız Excel'den farklı olanlar
    v = istemci.get(f"{A}/smm/donemler/{did}/uretim", params={"asama": 50, "yalniz_farkli": True}).json()
    assert [x["kod"] for x in v["kayitlar"]] == ["03-1"]


def test_urun_recetesi_fiyat_kaynaklari(istemci):  # noqa: F811
    did = _yukle(istemci)
    r = istemci.get(f"{A}/smm/donemler/{did}/uretim/50/03-1").json()
    k = {s["malzeme_kod"]: s for s in r["satirlar"]}
    assert k["02-1"]["fiyat_kaynagi"] == "asama_40" and D_(k["02-1"]["fiyat"]) == D_("21.47")
    assert k["ETK-1"]["fiyat_kaynagi"] == "envanter" and D_(k["ETK-1"]["tutar"]) == 2
    assert istemci.get(f"{A}/smm/donemler/{did}/uretim/50/YOK").status_code == 404
    assert istemci.get(f"{A}/smm/donemler/{did}/uretim", params={"asama": 30}).status_code == 422


def test_dagitim_degisir_ve_gunluge_yazilir(istemci):  # noqa: F811
    did = _yukle(istemci)
    r = istemci.put(f"{A}/smm/donemler/{did}/dagitim", json={"havuzlar": {"50_uretim": "600"}})
    assert r.status_code == 200, r.text
    h = {x["anahtar"]: x for x in r.json()["havuzlar"]}
    assert D_(h["50_uretim"]["tutar"]) == 600 and D_(h["50_uretim"]["excel"]) == 300 and h["50_uretim"]["degisti"] is True
    v = istemci.get(f"{A}/smm/donemler/{did}/uretim", params={"asama": 50}).json()
    assert D_(_urun(v, "03-1")["iscilik"]) == 6
    assert istemci.put(f"{A}/smm/donemler/{did}/dagitim", json={"havuzlar": {"yok": "1"}}).status_code == 422
    assert istemci.put(f"{A}/smm/donemler/{did}/dagitim", json={"havuzlar": {"50_uretim": "-1"}}).status_code == 422
    assert "dağıtım havuzları değişti" in istemci.get(f"{A}/gunluk").text


def test_sarf_farki(istemci):  # noqa: F811
    did = _yukle(istemci)
    v = istemci.get(f"{A}/smm/donemler/{did}/sarf-farki").json()
    x = next(k for k in v["kayitlar"] if k["kod"] == "HM-1")
    # reçete: 500 × 0,5 × 1,1 = 275; sayım sarfı: 200 − 40 = 160; fark −115 × 12 = −1380
    assert D_(x["recete_sarf"]) == 275 and D_(x["stok_sarf"]) == 160 and D_(x["fark_tutar"]) == -1380
    # yarı mamul 01-1: 40'ta 100 × 0,2 = 20 kullanıldı; elde olan üretim girişi 500 (sayım yok) -> sayıma göre sarf 500
    ym = next(k for k in v["kayitlar"] if k["kod"] == "01-1")
    assert D_(ym["uretim_girisi"]) == 500 and D_(ym["stok_sarf"]) == 500 and D_(ym["recete_sarf"]) == 20
    # etiket: kartta AD, bir reçetede MT -> birim uyumsuz, toplamlara girmez, listenin sonunda
    etk = next(k for k in v["kayitlar"] if k["kod"] == "ETK-1")
    assert etk["birim_uyumsuz"] is True and etk["recete_birimleri"] == ["AD", "MT"] and v["birim_uyumsuz_sayisi"] == 1
    assert v["kayitlar"][-1]["kod"] == "ETK-1"
    assert v["kayitlar"][0]["kod"] == "01-1"   # en büyük TL farkı üstte (480 × 8,6)
    v = istemci.get(f"{A}/smm/donemler/{did}/sarf-farki", params={"esik": 2000}).json()
    assert all(abs(D_(k["fark_tutar"])) >= 2000 for k in v["kayitlar"])


def test_eski_donemde_dagitim_bos(oturum):
    """2. adımdan önce yüklenmiş dönemde havuzlar yok: hesap 0 havuzla çalışır, hata vermez."""
    from backend.servisler import smm_asama_servisi as sa, smm_servisi as ss
    d = ss.yukle(oturum, _excel(), "09-2026 SMM.xlsx")
    oturum.get(m.SmmDonem, d["id"]).dagitim = None
    v = sa.uretim_maliyeti(oturum, d["id"], 20)
    assert D_(v["kayitlar"][0]["iscilik"]) == 0 and D_(v["dagitim"]["dagitilan"]) == 0


def _formullu_excel() -> bytes:
    """50 KOD'da Excel'deki gibi formüllü satırlar: standart, elle sabit fiyat, '/800' bölen, sonu boşluklu kod; ENVANTER P aşama sayfası."""
    wb = Workbook()
    wb.remove(wb.active)

    def sayfa(ad, satirlar, ust=None):
        ws = wb.create_sheet(ad)
        ws.append(ust or [])
        ws.append(["başlık"])
        for s in satirlar:
            ws.append(s)

    env = []
    for n, (kod, asama_sayfasi) in enumerate([("ETK-1", "20 KOD"), ("02-1", "40 KOD"), ("03-1", "50 KOD")], 3):
        env.append([kod, kod, "AD", "0008-Ambalaj Malzeme", "150"] + [None] * 10 + [f"=IFERROR(VLOOKUP(A{n},'{asama_sayfasi}'!A:U,21,FALSE),0)"])
    sayfa("ENVANTER", env)
    sayfa("DBS", [])
    sayfa("HM-YM ALIŞ SATIŞ", [])
    sayfa("DSS", [])
    sayfa("TABLO", [], ust=[None] * 9 + [0])

    def satir(n, mal, k=None, m_=None):
        k = k if k is not None else f"=IFERROR(VLOOKUP(E{n},ENVANTER!A:S,19,FALSE),0)"
        m_ = m_ if m_ is not None else f"=IFERROR(IF(K{n}=0,VLOOKUP(E{n},'40 KOD'!A:W,23,FALSE),0),0)"
        return ["03-1", "Ürün", 1, "AD", mal, mal, 1, "AD", f"=+G{n}/C{n}", None, k, None, m_] + [None] * 12 + [0]

    sayfa("50 KOD", [satir(3, "ETK-1"), satir(4, "02-1"), satir(5, "ETK-1"), satir(6, "AMB-9", k=0, m_=0),
                     satir(7, "KOLI", k="=IFERROR(VLOOKUP(E7,ENVANTER!A:S,19,FALSE),0)/800"), satir(8, "ETK-1 ")])
    b = BytesIO()
    wb.save(b)
    return b.getvalue()


def test_excel_okuyucu_elle_ve_standart_disi_hucreleri_bulur():
    from backend.servisler import smm_servisi as ss
    v = ss.excel_oku(_formullu_excel())
    ozel = {(r["malzeme_kod"], i): r["ozel"] for i, r in enumerate(v["receteler"])}
    assert ozel[("ETK-1", 0)] is None and ozel[("02-1", 1)] is None
    assert ozel[("AMB-9", 3)] == {"hm": "0", "ym": "0"}            # elle 0 yazılmış fiyat
    assert ozel[("KOLI", 4)] == {"hm_bolen": "800"}                 # standart formül / 800
    assert ozel[("ETK-1", 5)] == {"kod_bosluklu": "1"}              # 'ETK-1 ': Excel kartı bulamaz
    asm = {k: x["uretim_asamasi"] for k, x in v["kalemler"].items()}
    assert asm["ETK-1"] == 20 and asm["02-1"] == 40 and asm["03-1"] == 50


def test_ozel_hucreler_ve_aşama_kurallari_hesapta(oturum):
    """20'de yarı mamul fiyatı kendi aşamasından; envanter fiyatı kartın aşamasından; elle/bölen/boşluklu kod Excel gibi."""
    from backend.servisler import smm_asama_servisi as sa, smm_servisi as ss
    did = ss.yukle(oturum, _excel(), "09-2026 SMM.xlsx")["id"]
    # 20: 01-2 = 1 KG 01-1 (01-1 de bir 20 ürünü) -> YM fiyatı 01-1'in 20 birim maliyeti (8,6); HM (ortalama) kullanılmaz
    oturum.add(m.SmmReceteSatiri(donem_id=did, asama=20, ana_kod="01-2", ana_ad="Karışım", ana_miktar=D_(1), malzeme_kod="01-1",
                                 miktar=D_(1), birim="KG", fire_orani=D_(0)))
    # 02-1 envanterde, üretim birim fiyatını 40 KOD'dan alıyor; dönem başı 10 adet 100 TL -> (100 × 21,47 + 100) / 110
    k = oturum.query(m.SmmKalem).filter_by(donem_id=did, kod="02-1").one()
    k.envanterde, k.uretim_asamasi, k.dbs_miktar, k.dbs_tutar = True, 40, D_(10), D_(100)
    # 03-1'in etiket satırı: standart fiyat / 800
    for x in oturum.query(m.SmmReceteSatiri).filter_by(donem_id=did, asama=50, ana_kod="03-1"):
        if x.malzeme_kod == "ETK-1":
            x.ozel = {"hm_bolen": "800"}
    # 03-2'nin etiket satırı: kodu boşluklu -> Excel bulamaz, 0
    for x in oturum.query(m.SmmReceteSatiri).filter_by(donem_id=did, asama=50, ana_kod="03-2"):
        x.ozel = {"kod_bosluklu": "1"}
    oturum.flush()
    v20 = sa.uretim_maliyeti(oturum, did, 20)
    assert D_(_urun(v20, "01-2")["malzeme"]) == D_("8.6")
    r = sa.urun_recetesi(oturum, did, 50, "03-1")
    s = {x["malzeme_kod"]: x for x in r["satirlar"]}
    env = (D_(100) * D_("21.47") + 100) / 110
    assert abs(D_(s["02-1"]["fiyat"]) - env) < D_("0.0001") and s["02-1"]["fiyat_kaynagi"] == "envanter"
    assert D_(s["ETK-1"]["fiyat"]) == D_("0.0025") and s["ETK-1"]["fiyat_kaynagi"] == "envanter_bolen"
    r2 = sa.urun_recetesi(oturum, did, 50, "03-2")
    assert r2["satirlar"][0]["fiyat_kaynagi"] == "kod_bosluklu" and D_(r2["satirlar"][0]["fiyat"]) == 0
    oz = {o["asama"]: o for o in sa.uretim_maliyeti(oturum, did, 50)["ozetler"]}
    assert oz[50]["kod_bosluklu"] == 1 and oz[50]["excel_elle"] == 1


def test_smm_ozeti_tablo_ve_fis(istemci):  # noqa: F811
    """150: dönem başı 1000 + 250, alım 1400 + 900 + 20, sayım biber 40 × 12 = 480 -> 710 = 3090; + 720 (1000) + 730 (5000) = 9090;
    151 ve 152'de stok yok -> üretilen = SMM = 9090. Fiş borç = alacak."""
    did = _yukle(istemci)
    v = istemci.get(f"{A}/smm/donemler/{did}/ozet").json()
    blok = {b["hesap"]: b for b in v["tablo"]}
    assert D_(blok["150"]["sonuc"]) == 3090 and D_(v["ilk_madde"]) == 3090
    ds = next(x for x in blok["150"]["satirlar"] if x["ad"].startswith("Dönem sonu"))
    assert D_(ds["tutar"]) == 480
    assert D_(v["uretim_maliyeti"]) == 9090 and D_(v["uretilen"]) == 9090 and D_(v["smm"]) == 9090
    assert D_(v["fis_borc"]) == D_(v["fis_alacak"]) > 0
    hesaplar = {(x["hesap"], D_(x["borc"]) > 0) for x in v["fis"]}
    assert ("710", True) in hesaplar and ("150", False) in hesaplar and ("620", True) in hesaplar and ("152", False) in hesaplar
    assert istemci.get(f"{A}/smm/donemler/999/ozet").status_code == 404


def test_urune_elle_deger_ve_zincire_etkisi(istemci):  # noqa: F811
    did = _yukle(istemci)
    # 02-1 malzemesi elle 10 -> birim 10 + işçilik 4 + GÜG 10 = 24; 03-1 bunu YM fiyatı olarak kullanır: 24 + etiket 2 = 26
    r = istemci.put(f"{A}/smm/donemler/{did}/uretim/40/02-1/elle", json={"alanlar": {"malzeme": "10"}})
    assert r.status_code == 200, r.text
    assert r.json()["urun"]["elle_alanlar"] == ["malzeme"] and D_(r.json()["urun"]["birim_maliyet"]) == 24
    v = istemci.get(f"{A}/smm/donemler/{did}/uretim", params={"asama": 50}).json()
    assert D_(_urun(v, "03-1")["malzeme"]) == 26
    # birim maliyet elle: doğrudan o
    r = istemci.put(f"{A}/smm/donemler/{did}/uretim/50/03-1/elle", json={"alanlar": {"birim_maliyet": "30"}})
    assert D_(r.json()["urun"]["birim_maliyet"]) == 30 and D_(r.json()["urun"]["toplam"]) == 3000
    # formüle dön
    istemci.put(f"{A}/smm/donemler/{did}/uretim/40/02-1/elle", json={"alanlar": {"malzeme": None}})
    v = istemci.get(f"{A}/smm/donemler/{did}/uretim", params={"asama": 40}).json()
    assert D_(_urun(v, "02-1")["birim_maliyet"]) == D_("21.47") and _urun(v, "02-1")["elle_alanlar"] == []
    assert istemci.put(f"{A}/smm/donemler/{did}/uretim/40/02-1/elle", json={"alanlar": {"yok": "1"}}).status_code == 422
    assert istemci.put(f"{A}/smm/donemler/{did}/uretim/40/02-1/elle", json={"alanlar": {"fire": "-1"}}).status_code == 422
    assert istemci.put(f"{A}/smm/donemler/{did}/uretim/40/YOK/elle", json={"alanlar": {"fire": "1"}}).status_code == 404
    assert "aşama değeri elle girildi" in istemci.get(f"{A}/gunluk").text


def test_dagitim_anahtari_degisir(istemci):  # noqa: F811
    did = _yukle(istemci)
    v = istemci.get(f"{A}/smm/donemler/{did}/uretim", params={"asama": 20}).json()
    a = {x["anahtar"]: x for x in v["dagitim"]["anahtarlar"]}
    assert a["40_iscilik"]["alan"] == "etiket_adam_sn" and a["20"]["alan"] == "uretim"
    # 20'yi dolum süresine göre dağıt: 01-1'in 51'de süresi yok -> payı 0, 'süre yok' işaretli
    r = istemci.put(f"{A}/smm/donemler/{did}/dagitim", json={"anahtarlar": {"20": "dolum_sn"}})
    assert r.status_code == 200 and {x["anahtar"]: x["alan"] for x in r.json()["anahtarlar"]}["20"] == "dolum_sn"
    v = istemci.get(f"{A}/smm/donemler/{did}/uretim", params={"asama": 20}).json()
    x = _urun(v, "01-1")
    assert D_(x["iscilik"]) == 0 and x["sure_yok"] is True
    # havuz tutarı değişince anahtar korunur
    istemci.put(f"{A}/smm/donemler/{did}/dagitim", json={"havuzlar": {"20_uretim": "2000"}})
    v = istemci.get(f"{A}/smm/donemler/{did}/uretim", params={"asama": 20}).json()
    assert {x["anahtar"]: x["alan"] for x in v["dagitim"]["anahtarlar"]}["20"] == "dolum_sn"
    assert istemci.put(f"{A}/smm/donemler/{did}/dagitim", json={"anahtarlar": {"20": "saat"}}).status_code == 422


def test_uretim_sureleri_duzenlenir(istemci):  # noqa: F811
    did = _yukle(istemci)
    v = istemci.get(f"{A}/smm/donemler/{did}/sureler").json()
    assert {x["kod"] for x in v["kayitlar"]} == {"02-1", "03-1"}
    s1 = next(x for x in v["kayitlar"] if x["kod"] == "03-1")
    # 03-1'in dolum süresi 1 -> 2: tek ürün olduğu için 50 işçiliği yine 300 / 100 = 3 (pay oranı değişmez); 03-2 eklenip üretimi yok
    r = istemci.put(f"{A}/smm/sureler/{s1['id']}", json={"dolum_sn": "2"})
    assert r.status_code == 200 and D_(r.json()["dolum_sn"]) == 2
    r = istemci.post(f"{A}/smm/donemler/{did}/sureler", json={"mamul_kod": "03-2", "ad": "Hazır kavanoz", "dolum_sn": "1"})
    assert r.status_code == 201 and r.json()["kod"] == "03-2"
    assert istemci.post(f"{A}/smm/donemler/{did}/sureler", json={"ad": "kodsuz"}).status_code == 422
    assert istemci.put(f"{A}/smm/sureler/{s1['id']}", json={"dolum_sn": "-1"}).status_code == 422
    assert istemci.delete(f"{A}/smm/sureler/{r.json()['id']}").status_code == 204
    assert len(istemci.get(f"{A}/smm/donemler/{did}/sureler", params={"arama": "03-1"}).json()["kayitlar"]) == 1
    assert "üretim süresi değişti" in istemci.get(f"{A}/gunluk").text
