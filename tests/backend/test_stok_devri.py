"""Stokta kalan (geçen yıldan devreden) ürün ve ortalama maliyet: kural, API, günlük, kilit, kopya, Excel aktarımı ve satış fiyatına etkisi."""
from decimal import Decimal as D_
from io import BytesIO
from openpyxl import Workbook, load_workbook
from backend.depo import modeller as m
from backend.servisler import hesap_servisi as hs, stok_devri_servisi as sd
from tests.backend.test_analiz_2 import _kurulum, _satis
from tests.backend.test_api import _senaryo, istemci  # noqa: F401  (fixture)

A = "/api/v1"


def _put(c, sid, kod="TEST", **govde):
    return c.put(f"{A}/urunler/{kod}/stok-devri?senaryo={sid}", json={"neden": "sayım", **govde})


def _param(c, sid, anahtar, deger):
    r = c.post(f"{A}/parametreler/{anahtar}/degerler?senaryo={sid}", json={"deger": deger, "gecerlilik_basi": "2026-06-01", "neden": "test"})
    assert r.status_code == 201, r.text


def _hazirla(c, oturum) -> int:
    sid = _senaryo(c); _kurulum(c, sid, oturum)   # enflasyon 0,25; satış kâr 0,20
    return sid


def _maliyet(oturum, sid, kod="TEST") -> D_:
    return hs.hesapla(oturum, kod, sid).sonuc.finansman_dahil_maliyet_tl


# ---------------------------------------------------------------- saf kural

def test_elle_kontrol_ornegi():
    """2.000 adet x 30 TL, enflasyon %40, üretim 8.000, bu yılın maliyeti 50 TL -> güncel stok 42 TL, ortalama 48,40 TL."""
    k = m.StokDevri(adet=D_(2000), birim_maliyet=D_(30), enflasyon=D_("0.40"), uretim_adedi=D_(8000))
    d = sd.ozet("X", k, D_(50), D_("0.25"), None)
    assert d["guncel_stok_maliyeti"] == D_(42) and d["ortalama_maliyet"] == D_("48.40")
    assert d["stok_payi"] == D_("0.2") and d["enflasyon_kullanilan"] == D_("0.40") and d["uretim_adedi_kaynagi"] == "elle"
    assert d["stok_etkisi"] is True and d["aciklama"] is None and d["bu_yil_maliyet"] == D_(50)


def test_dogrulama():
    import pytest
    from backend.servisler.hatalar import DogrulamaHatasi
    for a in [dict(adet=-1, birim_maliyet=1), dict(adet=5, birim_maliyet=None), dict(adet=5, birim_maliyet=0), dict(adet=5, birim_maliyet=1, enflasyon=-1),
              dict(adet=5, birim_maliyet=1, enflasyon=6), dict(adet=5, birim_maliyet=1, uretim_adedi=-2)]:
        with pytest.raises(DogrulamaHatasi):
            sd.dogrula(**a)
    assert sd.dogrula(0, None)["adet"] == 0   # adet 0 iken birim maliyet gerekmez
    assert sd.dogrula(5, 1, D_(5), 0)["enflasyon"] == D_(5)


# ---------------------------------------------------------------- API

def test_kayit_yoksa_etkisiz(istemci, oturum):
    sid = _hazirla(istemci, oturum)
    r = istemci.get(f"{A}/urunler/TEST/stok-devri?senaryo={sid}")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["urun_kodu"] == "TEST" and d["stok_etkisi"] is False
    assert all(d[a] is None for a in sd.CIKIS_ALANLARI if a not in ("urun_kodu", "stok_etkisi"))
    h = istemci.post(f"{A}/urunler/TEST/hesapla", json={"senaryo_id": sid}).json()
    assert h["stok_devri"] is None and h["satis_ortalamadan"] is False
    satir = {x["kod"]: x for x in istemci.get(f"{A}/urunler?senaryo={sid}").json()["kayitlar"]}["TEST"]
    assert satir["ortalama_maliyet_tl"] is None and satir["stok_etkisi"] is False
    assert istemci.get(f"{A}/stok-devri?senaryo={sid}").json() == {"kayitlar": []}


def test_enflasyon_elle_ve_parametre(istemci, oturum):
    sid = _hazirla(istemci, oturum)
    bu_yil = _maliyet(oturum, sid)
    r = _put(istemci, sid, adet="2000", birim_maliyet="3", uretim_adedi="8000")   # enflasyon parametreden (0,25)
    assert r.status_code == 200, r.text
    d = r.json()
    assert (d["adet"], d["birim_maliyet"], d["enflasyon"], d["uretim_adedi"]) == ("2000", "3", None, "8000")
    assert D_(d["enflasyon_kullanilan"]) == D_("0.25") and D_(d["guncel_stok_maliyeti"]) == D_("3.75")
    assert D_(d["bu_yil_maliyet"]) == bu_yil and d["uretim_adedi_kaynagi"] == "elle" and d["stok_etkisi"] is True
    assert D_(d["ortalama_maliyet"]) == (2000 * D_("3.75") + 8000 * bu_yil) / 10000
    d = _put(istemci, sid, adet="2000", birim_maliyet="3", enflasyon="0.4", uretim_adedi="8000").json()   # elle enflasyon
    assert D_(d["enflasyon"]) == D_("0.4") and D_(d["enflasyon_kullanilan"]) == D_("0.4") and D_(d["guncel_stok_maliyeti"]) == D_("4.2")
    assert D_(d["ortalama_maliyet"]) == (2000 * D_("4.2") + 8000 * bu_yil) / 10000 and D_(d["stok_payi"]) == D_("0.2")
    # GET aynı sonucu verir; liste ad ile döner
    assert istemci.get(f"{A}/urunler/TEST/stok-devri?senaryo={sid}").json() == d
    lst = istemci.get(f"{A}/stok-devri?senaryo={sid}").json()["kayitlar"]
    assert len(lst) == 1 and lst[0]["ad"] == "Ürün TEST" and lst[0]["ortalama_maliyet"] == d["ortalama_maliyet"]


def test_uretim_adedi_satis_gecmisinden(istemci, oturum):
    sid = _hazirla(istemci, oturum)
    _satis(oturum, sid, "TEST", "10", "TL", "1000")
    _satis(oturum, sid, "TEST", "1", "USD", "200")   # tüm para birimleri toplanır: 1200 adet
    bu_yil = _maliyet(oturum, sid)
    d = _put(istemci, sid, adet="300", birim_maliyet="2", enflasyon="0").json()
    assert d["uretim_adedi"] is None and d["uretim_adedi_kaynagi"] == "satis_gecmisi" and D_(d["uretim_adedi_kullanilan"]) == 900
    assert D_(d["ortalama_maliyet"]) == (300 * D_(2) + 900 * bu_yil) / 1200 and D_(d["stok_payi"]) == D_("0.25")
    # stok > geçen yıl satışı: üretim 0'a kırpılır, ortalama = güncel stok maliyeti
    d = _put(istemci, sid, adet="1500", birim_maliyet="2", enflasyon="0.1").json()
    assert D_(d["uretim_adedi_kullanilan"]) == 0 and D_(d["ortalama_maliyet"]) == D_("2.2") and D_(d["stok_payi"]) == 1


def test_uretim_adedi_bilinmiyorsa_ortalama_yok(istemci, oturum):
    sid = _hazirla(istemci, oturum)
    d = _put(istemci, sid, kod="T2", adet="100", birim_maliyet="2").json()   # T2'nin satışı yok, elle üretim yok
    assert d["ortalama_maliyet"] is None and d["stok_etkisi"] is False and d["uretim_adedi_kaynagi"] is None
    assert d["aciklama"] == sd.ACIKLAMA_URETIM_YOK and d["guncel_stok_maliyeti"] is not None
    satir = {x["kod"]: x for x in istemci.get(f"{A}/urunler?senaryo={sid}").json()["kayitlar"]}["T2"]
    assert satir["ortalama_maliyet_tl"] is None and satir["stok_etkisi"] is False


def test_adet_sifir_etkisiz(istemci, oturum):
    sid = _hazirla(istemci, oturum)
    d = _put(istemci, sid, adet="0").json()
    assert d["adet"] == "0" and d["stok_etkisi"] is False and d["ortalama_maliyet"] is None and d["aciklama"] == sd.ACIKLAMA_ADET_YOK


def test_dogrulama_422_ve_neden_zorunlu(istemci, oturum):
    sid = _hazirla(istemci, oturum)
    assert _put(istemci, sid, adet="5").status_code == 422                               # birim maliyet yok
    assert _put(istemci, sid, adet="5", birim_maliyet="1", enflasyon="40").status_code == 422   # %40 yerine 40
    assert _put(istemci, sid, adet="-1", birim_maliyet="1").status_code == 422
    assert istemci.put(f"{A}/urunler/TEST/stok-devri?senaryo={sid}", json={"adet": "5", "birim_maliyet": "1"}).status_code == 422   # neden yok
    assert _put(istemci, sid, kod="YOK", adet="5", birim_maliyet="1").status_code == 404
    assert istemci.delete(f"{A}/urunler/TEST/stok-devri?senaryo={sid}").status_code == 422   # neden yok


def test_gunluk_ve_silme(istemci, oturum):
    sid = _hazirla(istemci, oturum)
    assert _put(istemci, sid, adet="10", birim_maliyet="2").status_code == 200
    assert _put(istemci, sid, adet="10", birim_maliyet="2").status_code == 200   # değişmedi: günlük yok
    assert _put(istemci, sid, adet="12", birim_maliyet="2", uretim_adedi="5").status_code == 200
    assert istemci.delete(f"{A}/urunler/TEST/stok-devri?senaryo={sid}&neden=yanlış giriş").status_code == 204
    assert istemci.delete(f"{A}/urunler/TEST/stok-devri?senaryo={sid}&neden=tekrar").status_code == 204   # yoksa da 204
    k = istemci.get(f"{A}/degisiklikler?tablo=stok_devri").json()["kayitlar"]
    assert [x["islem"] for x in k] == ["sil", "guncelle", "ekle"]
    sil, gun, ekle = k
    assert ekle["yeni"]["adet"] == "10" and ekle["yeni"]["urun_kodu"] == "TEST" and ekle["yeni"]["_neden"] == "sayım" and ekle["kullanici"]
    assert gun["eski"]["adet"] == "10" and gun["yeni"]["adet"] == "12" and gun["yeni"]["uretim_adedi"] == "5"
    assert sil["eski"]["adet"] == "12" and sil["yeni"]["_neden"] == "yanlış giriş"
    assert oturum.query(m.StokDevri).count() == 0
    # değişiklik günlüğü ekranında ürün ve çalışmaya bağlanır
    g = istemci.get(f"{A}/gunluk?senaryo={sid}&urun_kodu=TEST")
    assert g.status_code == 200, g.text
    stok = [x for x in g.json()["kayitlar"] if x["baslik"].startswith("Stokta kalan")]
    assert len(stok) == 3 and all(x["senaryo_id"] == sid for x in stok) and {x["neden"] for x in stok} == {"sayım", "yanlış giriş"}


def test_kilitli_senaryoda_yazma_reddi(istemci, oturum):
    sid = _hazirla(istemci, oturum)
    assert _put(istemci, sid, adet="10", birim_maliyet="2").status_code == 200
    sen = oturum.get(m.Senaryo, sid); sen.kilitli = True; oturum.commit()
    assert _put(istemci, sid, adet="11", birim_maliyet="2").status_code == 409
    assert istemci.delete(f"{A}/urunler/TEST/stok-devri?senaryo={sid}&neden=x").status_code == 409
    r = istemci.post(f"{A}/aktarim/stok-devri/uygula", data={"senaryo": str(sid), "neden": "x"}, files=_dosya([["TEST", 1, 1]]))
    assert r.status_code == 409
    assert istemci.get(f"{A}/urunler/TEST/stok-devri?senaryo={sid}").json()["adet"] == "10"   # okuma serbest


def test_kopyada_tasinmaz_ve_senaryo_silinince_gider(istemci, oturum):
    sid = _hazirla(istemci, oturum)
    assert _put(istemci, sid, adet="10", birim_maliyet="2").status_code == 200
    r = istemci.post(f"{A}/senaryolar/{sid}/kopyala", json={"sezon_ad": "2026-2027", "ad": "B", "tur": "fiyat_calismasi", "neden": "yeni yıl",
                                                           "kopyala": {k: True for k in ("receteler", "fiyatlar", "parametreler", "gider", "uretim", "fire_kurallari")}})
    assert r.status_code == 201, r.text
    yeni = r.json()["id"]
    assert istemci.get(f"{A}/stok-devri?senaryo={yeni}").json() == {"kayitlar": []}
    assert istemci.get(f"{A}/urunler/TEST/stok-devri?senaryo={yeni}").json()["adet"] is None
    assert istemci.delete(f"{A}/senaryolar/{sid}").status_code == 204
    assert oturum.query(m.StokDevri).count() == 0


# ---------------------------------------------------------------- satış fiyatı ve analizler

def test_satis_ortalama_maliyetten(istemci, oturum):
    sid = _hazirla(istemci, oturum)
    _satis(oturum, sid, "TEST", "100", "TL", "1000")
    bu_yil = _maliyet(oturum, sid)
    once = hs.hesapla(oturum, "TEST", sid).sonuc
    d = _put(istemci, sid, adet="2000", birim_maliyet="3", enflasyon="0.4", uretim_adedi="8000").json()
    ort = D_(d["ortalama_maliyet"])
    assert ort != bu_yil
    # 0 (varsayılan): satış fiyatı değişmez, ortalama yalnız bilgi; analiz bu yılın maliyetini kullanır
    h = istemci.post(f"{A}/urunler/TEST/hesapla", json={"senaryo_id": sid}).json()
    assert h["satis_ortalamadan"] is False and D_(h["fiyatlar"]["satis_tl"]) == once.satis_fiyati_tl and h["stok_devri"]["ortalama_maliyet"] == d["ortalama_maliyet"]
    hf = {x["kod"]: x for x in istemci.get(f"{A}/analiz/hedef-fiyat?senaryo={sid}&marj=0.15").json()["kayitlar"]}
    assert hf["TEST"]["maliyet_kaynagi"] == "bu_yil" and D_(hf["TEST"]["maliyet"]) == bu_yil
    satir = {x["kod"]: x for x in istemci.get(f"{A}/urunler?senaryo={sid}").json()["kayitlar"]}["TEST"]
    assert D_(satir["ortalama_maliyet_tl"]) == ort and satir["stok_etkisi"] is True and D_(satir["satis_tl"]) == once.satis_fiyati_tl
    # 1: satış fiyatı ortalama maliyet x (1 + kâr); bu yılın maliyeti ayrı görünür; döviz satışı aynı oranla
    _param(istemci, sid, "satis_ortalama_maliyetten", "1")
    c = hs.hesapla(oturum, "TEST", sid)
    assert c.satis_ortalamadan and c.sonuc.finansman_dahil_maliyet_tl == bu_yil
    assert c.sonuc.satis_fiyati_tl == ort * D_("1.2") and c.sonuc.suzme_kg_fiyati_tl == ort * D_("1.2") / D_("0.18")
    assert c.sonuc.satis_fiyati_doviz["USD"] == once.doviz_maliyet["USD"] * (ort / bu_yil) * D_("1.2")
    assert c.sonuc.teklifler_usd == once.teklifler_usd and c.sonuc.firesiz.satis_fiyati_tl == once.firesiz.satis_fiyati_tl
    h = istemci.post(f"{A}/urunler/TEST/hesapla", json={"senaryo_id": sid}).json()
    assert h["satis_ortalamadan"] is True and D_(h["fiyatlar"]["satis_tl"]) == ort * D_("1.2") and D_(h["toplamlar"]["maliyet_tl"]) == bu_yil
    hf = {x["kod"]: x for x in istemci.get(f"{A}/analiz/hedef-fiyat?senaryo={sid}&marj=0.15").json()["kayitlar"]}
    assert hf["TEST"]["maliyet_kaynagi"] == "ortalama" and D_(hf["TEST"]["maliyet"]) == ort and D_(hf["TEST"]["hedef_fiyat"]) == ort * D_("1.15")
    assert hf["T2"]["maliyet_kaynagi"] == "bu_yil"   # stok kaydı olmayan ürün etkilenmez
    kh = {x["kod"]: x for x in istemci.get(f"{A}/analiz/karlilik?senaryo={sid}").json()["kayitlar"]}
    assert kh["TEST"]["maliyet_kaynagi"] == "ortalama" and D_(kh["TEST"]["maliyet"]) == ort and D_(kh["TEST"]["marj"]) == D_(100) / ort - 1
    satir = {x["kod"]: x for x in istemci.get(f"{A}/urunler?senaryo={sid}").json()["kayitlar"]}["TEST"]
    assert D_(satir["satis_tl"]) == ort * D_("1.2") and D_(satir["maliyet_tl"]) == bu_yil
    # kaydedilen hesap stok özetini taşır
    hid = istemci.post(f"{A}/urunler/TEST/hesaplar", json={"senaryo_id": sid}).json()["id"]
    g = istemci.get(f"{A}/hesaplar/{hid}").json()["gorunum"]
    assert g["satis_ortalamadan"] is True and g["stok_devri"]["ortalama_maliyet"] == d["ortalama_maliyet"]


def test_parametre_tanimi_ve_dogrulamasi(istemci, oturum):
    sid = _hazirla(istemci, oturum)
    t = {x["anahtar"]: x for x in istemci.get(f"{A}/parametreler/tanimlar").json()["kayitlar"]}
    assert t["satis_ortalama_maliyetten"]["birim"] == "evet_hayir"
    r = istemci.post(f"{A}/parametreler/satis_ortalama_maliyetten/degerler?senaryo={sid}", json={"deger": "2", "gecerlilik_basi": "2026-06-01", "neden": "x"})
    assert r.status_code == 422


def test_genel_bakis_excel_ortalama_sutunu(istemci, oturum):
    sid = _hazirla(istemci, oturum)
    d = _put(istemci, sid, adet="2000", birim_maliyet="3", uretim_adedi="8000").json()
    r = istemci.get(f"{A}/disa-aktar/urunler.xlsx?senaryo={sid}")
    assert r.status_code == 200
    ws = load_workbook(BytesIO(r.content)).active
    baslik = [c.value for c in ws[1]]
    i = baslik.index("Ortalama Maliyet TL")
    satirlar = {row[0]: row for row in ws.iter_rows(min_row=2, values_only=True)}
    assert abs(D_(str(satirlar["TEST"][i])) - D_(d["ortalama_maliyet"])) < D_("1e-9") and satirlar["T2"][i] is None


# ---------------------------------------------------------------- Excel aktarımı

def _dosya(satirlar, basliklar=sd.SUTUNLAR):
    wb = Workbook()
    ws = wb.active
    ws.append(list(basliklar))
    for s in satirlar:
        ws.append(list(s))
    b = BytesIO(); wb.save(b); b.seek(0)
    return {"dosya": ("stok.xlsx", b.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}


def test_sablon(istemci, oturum):
    r = istemci.get(f"{A}/aktarim/stok-devri/sablon.xlsx")
    assert r.status_code == 200
    wb = load_workbook(BytesIO(r.content))
    assert [c.value for c in wb.worksheets[0][1]] == list(sd.SUTUNLAR) and "Açıklama" in wb.sheetnames


def test_onizle_uygula(istemci, oturum):
    sid = _hazirla(istemci, oturum)
    assert _put(istemci, sid, kod="T2", adet="5", birim_maliyet="1").status_code == 200
    assert _put(istemci, sid, kod="T3", adet="7", birim_maliyet="1").status_code == 200
    satirlar = [["TEST", 2000, 30, "%40", 8000], ["T2", 5, "1,5", None, None], ["T3", 7, 1, None, None]]
    # hatalı satırlar listelenir (atlanmaz), uygulanmaz
    hatali = satirlar + [["YOK", 1, 1, None, None], ["T4", 3, None, None, None], ["TEST", 1, 1, None, None], ["T4", "abc", 1, None, None]]
    r = istemci.post(f"{A}/aktarim/stok-devri/onizle", data={"senaryo": str(sid)}, files=_dosya(hatali))
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["sutunlar"] == {a: a for a in sd.SUTUNLAR}
    assert [h["satir_no"] for h in d["hatalar"]] == [5, 6, 7, 8]
    assert "ürün bulunamadı" in d["hatalar"][0]["mesaj"] and "birden fazla" in d["hatalar"][2]["mesaj"]
    r = istemci.post(f"{A}/aktarim/stok-devri/uygula", data={"senaryo": str(sid), "neden": "sayım"}, files=_dosya(hatali))
    assert r.status_code == 422 and len(r.json()["alanlar"]["hatalar"]) == 4
    assert oturum.query(m.StokDevri).count() == 2   # hiçbir şey yazılmadı
    # temiz dosya: önizleme durumları, sonra uygula
    d = istemci.post(f"{A}/aktarim/stok-devri/onizle", data={"senaryo": str(sid)}, files=_dosya(satirlar)).json()
    durum = {x["urun_kodu"]: x for x in d["satirlar"]}
    assert (d["yeni"], d["degisen"], d["ayni"], d["hatalar"]) == (1, 1, 1, [])
    assert durum["TEST"]["durum"] == "yeni" and durum["TEST"]["enflasyon"] == "0.4" and durum["TEST"]["ad"] == "Ürün TEST"
    assert durum["T2"]["durum"] == "degisen" and durum["T2"]["birim_maliyet"] == "1.5" and durum["T2"]["eski"]["birim_maliyet"] == "1"
    assert durum["T3"]["durum"] == "ayni"
    r = istemci.post(f"{A}/aktarim/stok-devri/uygula", data={"senaryo": str(sid), "neden": "sayım"}, files=_dosya(satirlar))
    assert r.status_code == 200, r.text
    assert r.json() == {"eklenen": 1, "guncellenen": 1, "ayni": 1}
    t = istemci.get(f"{A}/urunler/TEST/stok-devri?senaryo={sid}").json()
    assert D_(t["guncel_stok_maliyeti"]) == 42 and t["stok_etkisi"] is True
    assert len(istemci.get(f"{A}/degisiklikler?tablo=stok_devri").json()["kayitlar"]) == 4   # 2 elle + 1 ekle + 1 güncelle
    # neden zorunlu; eksik zorunlu sütun 422
    assert istemci.post(f"{A}/aktarim/stok-devri/uygula", data={"senaryo": str(sid), "neden": " "}, files=_dosya(satirlar)).status_code == 422
    r = istemci.post(f"{A}/aktarim/stok-devri/onizle", data={"senaryo": str(sid)}, files=_dosya([["TEST", 1]], ("urun_kodu", "stok_adet")))
    assert r.status_code == 422 and "stok_birim_maliyet" in r.json()["mesaj"]
