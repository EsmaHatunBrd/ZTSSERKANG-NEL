"""Faz 2b API: firesiz paralel sonuç, elle brüt miktar / birim fiyat alanları, dashboard ve dışa aktarma sütunu."""
from decimal import Decimal as D_
from io import BytesIO
import pytest
from openpyxl import load_workbook
from tests.backend.test_api import A, _kur, _senaryo, istemci  # noqa: F401  (istemci fixture)

BODY = {"tarih": "2026-10-21"}


def _recete(c, sid, satirlar):
    r = c.post(f"{A}/urunler/TEST/recete?senaryo={sid}", json=satirlar)
    assert r.status_code == 201, r.text


def _hesapla(c, sid, **ek):
    r = c.post(f"{A}/urunler/TEST/hesapla", json={"senaryo_id": sid, **BODY, **ek})
    assert r.status_code == 200, r.text
    return r.json()


def test_hesapla_iki_toplam_ve_satir_alanlari(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    g = _hesapla(istemci, sid)
    assert set(g["toplamlar_firesiz"]) == set(g["toplamlar"]) and set(g["fiyatlar_firesiz"]) == set(g["fiyatlar"])
    assert D_(g["toplamlar_firesiz"]["malzeme"]) < D_(g["toplamlar"]["malzeme"])          # %2 fire
    assert D_(g["toplamlar_firesiz"]["malzeme"]) == D_("5.9") * D_("1.25")
    assert D_(g["fiyatlar_firesiz"]["satis_tl"]) < D_(g["fiyatlar"]["satis_tl"])
    s0 = g["satirlar"][0]
    assert D_(s0["tutar_firesiz"]) == D_("5.9") * D_("1.25") and s0["miktar_kaynagi"] == "fire" and s0["fiyat_kaynagi"] == "liste"
    assert s0["brut_miktar_elle"] is None and s0["birim_fiyat_elle"] is None
    assert g["satirlar"][-1]["miktar_kaynagi"] == "-" and g["satirlar"][-1]["fiyat_kaynagi"] == "-"      # gider satırı


def test_elle_brut_ve_fiyat_satiri(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    _recete(istemci, sid, [{"malzeme_kodu": "KAV", "ad": "Kavanoz", "miktar": "1", "birim": "AD", "brut_miktar_elle": "1.5", "birim_fiyat_elle": "10"}])
    g = _hesapla(istemci, sid)
    s0 = g["satirlar"][0]
    assert s0["miktar_kaynagi"] == "elle" and s0["fiyat_kaynagi"] == "elle" and s0["fire_kaynagi"] == "elle"
    assert D_(s0["brut_miktar"]) == D_("1.5") and D_(s0["birim_fiyat"]) == 10
    assert D_(s0["tutar"]) == D_("1.25") * 10 * D_("1.5") and D_(s0["tutar_firesiz"]) == D_("1.25") * 10
    assert s0["brut_miktar_elle"] == "1.5" and s0["birim_fiyat_elle"] == "10"
    r = istemci.get(f"{A}/urunler/TEST/recete?senaryo={sid}").json()["satirlar"][0]
    assert r["brut_miktar_elle"] == "1.5" and r["birim_fiyat_elle"] == "10"
    rr = istemci.get(f"{A}/receteler/{istemci.get(f'{A}/urunler/TEST/recete?senaryo={sid}').json()['id']}").json()["satirlar"][0]
    assert rr["brut_miktar_elle"] == "1.5"
    # elle brütlü satıra fire override -> 422
    r = istemci.post(f"{A}/urunler/TEST/hesapla", json={"senaryo_id": sid, **BODY, "override": {"fire": {"1": "0.1"}}})
    assert r.status_code == 422 and "elle brüt" in r.json()["mesaj"]


def test_kayitli_hesap_gorunumu_firesiz_bloklari(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    canli = _hesapla(istemci, sid)
    hid = istemci.post(f"{A}/urunler/TEST/hesaplar", json={"senaryo_id": sid, **BODY}).json()["id"]
    gorunum = istemci.get(f"{A}/hesaplar/{hid}").json()["gorunum"]
    assert gorunum["toplamlar_firesiz"] == canli["toplamlar_firesiz"] and gorunum["fiyatlar_firesiz"] == canli["fiyatlar_firesiz"]
    assert gorunum["satirlar"][0]["tutar_firesiz"] == canli["satirlar"][0]["tutar_firesiz"]
    # firesiz alanı olmayan eski snapshot: bloklar None, görünüm bozulmaz
    from backend.depo import modeller as m
    h = oturum.get(m.MaliyetHesabi, hid)
    eski = {k: v for k, v in h.sonuc_snapshot.items() if k != "firesiz"}
    h.sonuc_snapshot = eski
    oturum.flush()
    g2 = istemci.get(f"{A}/hesaplar/{hid}").json()["gorunum"]
    assert g2["toplamlar_firesiz"] is None and g2["fiyatlar_firesiz"] is None


def test_dashboard_firesiz_sutunlari_ve_export(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    satir = istemci.get(f"{A}/urunler?senaryo={sid}").json()["kayitlar"][0]
    g = _hesapla(istemci, sid)
    assert satir["maliyet_tl_firesiz"] == g["toplamlar_firesiz"]["maliyet_tl"] and satir["maliyet_usd_firesiz"] == g["toplamlar_firesiz"]["maliyet_usd"]
    assert D_(satir["maliyet_tl_firesiz"]) < D_(satir["maliyet_tl"])
    x = istemci.get(f"{A}/disa-aktar/urunler.xlsx?senaryo={sid}")
    ws = load_workbook(BytesIO(x.content)).active
    baslik = [c.value for c in ws[1]]
    assert "Maliyet TL" in baslik and "Maliyet TL (firesiz)" in baslik
    assert ws.cell(2, baslik.index("Maliyet TL (firesiz)") + 1).value == pytest.approx(float(satir["maliyet_tl_firesiz"]))


def test_sema_sinirlari_elle_alanlar(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    for alan in ("brut_miktar_elle", "birim_fiyat_elle"):
        r = istemci.post(f"{A}/urunler/TEST/recete?senaryo={sid}", json=[{"malzeme_kodu": "KAV", "miktar": "1", alan: "-1"}])
        assert r.status_code == 422, (alan, r.text)
        r = istemci.post(f"{A}/urunler/TEST/recete?senaryo={sid}", json=[{"malzeme_kodu": "KAV", "miktar": "1", alan: "0"}])
        assert r.status_code == 201, (alan, r.text)
        r = istemci.post(f"{A}/urunler/TEST/recete?senaryo={sid}", json=[{"malzeme_kodu": "KAV", "miktar": "1", alan: None}])
        assert r.status_code == 201, (alan, r.text)


def test_kurallara_birak_elle_degerleri_kaldir(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    _recete(istemci, sid, [{"malzeme_kodu": "KAV", "ad": "Kavanoz", "miktar": "1", "birim": "AD", "brut_miktar_elle": "1.5"}])
    u = f"{A}/urunler/TEST/recete/kurallara-birak?senaryo={sid}"
    assert istemci.post(u, json={"siralar": None}).status_code == 201
    assert istemci.get(f"{A}/urunler/TEST/recete?senaryo={sid}").json()["satirlar"][0]["brut_miktar_elle"] == "1.5"   # varsayılan: korunur
    assert istemci.post(u, json={"siralar": [1], "elle_degerleri_kaldir": True}).status_code == 201
    assert istemci.get(f"{A}/urunler/TEST/recete?senaryo={sid}").json()["satirlar"][0]["brut_miktar_elle"] is None
