"""Liste fiyatı çalışması: liste = satış ÷ bölen (varsayılan 0,63), geçmiş liste fiyatları (elle / Excel), örnek veri, artış kıyası."""
from decimal import Decimal as D_
from io import BytesIO
from openpyxl import Workbook, load_workbook
from backend.depo import modeller as m
from tests.backend.test_api import _kur, _senaryo, istemci  # noqa: F401  (fixture)

A = "/api/v1"


def _calisma(c, sid, **q):
    ek = "".join(f"&{k}={v}" for k, v in q.items())
    r = c.get(f"{A}/liste-calismasi?senaryo={sid}{ek}")
    assert r.status_code == 200, r.text
    return r.json()


def _xlsx(satirlar):
    wb = Workbook(); ws = wb.active
    for s in satirlar:
        ws.append(s)
    b = BytesIO(); wb.save(b)
    return b.getvalue()


def test_varsayilan_bolen_ve_liste_fiyati(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    d = _calisma(istemci, sid)
    assert (d["bolen"], d["bolen_kayitli"], d["varsayilan_bolen"], d["yil"]) == ("0.63", False, "0.63", 2026)
    r = d["kayitlar"][0]
    assert r["kod"] == "TEST" and abs(D_(r["yeni_liste"]) - D_(r["satis_tl"]) / D_("0.63")) < D_("0.000001")
    assert r["onceki_liste"] is None and r["liste_artis"] is None and d["ornek_var"] is False and d["yillar"] == []
    # kaydetmeden deneme: ?bolen=
    d2 = _calisma(istemci, sid, bolen="0.7")
    assert d2["bolen"] == "0.7" and abs(D_(d2["kayitlar"][0]["yeni_liste"]) - D_(r["satis_tl"]) / D_("0.7")) < D_("0.000001")
    assert istemci.get(f"{A}/liste-calismasi?senaryo={sid}&bolen=0").status_code == 422
    # kayıtlı bölen parametresi
    assert istemci.post(f"{A}/parametreler/liste_bolen/degerler?senaryo={sid}",
                        json={"deger": "0.6", "gecerlilik_basi": "2026-01-01", "neden": "yeni liste politikası"}).status_code == 201
    d3 = _calisma(istemci, sid)
    assert d3["bolen"] == "0.6" and d3["bolen_kayitli"] is True


def test_elle_gecmis_artis_ve_maliyet_kiyasi(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    r0 = _calisma(istemci, sid)["kayitlar"][0]
    yeni, maliyet = D_(r0["yeni_liste"]), D_(r0["maliyet_tl"])
    # 2025: liste yeni/1.4, maliyet maliyet/1.5 -> liste %40, maliyet %50 artmış; fark -10 puan
    liste25, mal25 = (yeni / D_("1.4")).quantize(D_("0.0001")), (maliyet / D_("1.5")).quantize(D_("0.0001"))
    assert istemci.put(f"{A}/liste-fiyatlari", json={"urun_kodu": "TEST", "yil": 2025, "liste_fiyati": str(liste25), "birim_maliyet": str(mal25)}).status_code == 200
    assert istemci.put(f"{A}/liste-fiyatlari", json={"urun_kodu": "TEST", "yil": 2024, "liste_fiyati": str(liste25 / 2)}).status_code == 200
    d = _calisma(istemci, sid)
    r = d["kayitlar"][0]
    assert r["onceki_yil"] == 2025 and abs(D_(r["liste_artis"]) - D_("0.4")) < D_("0.001") and abs(D_(r["maliyet_artis"]) - D_("0.5")) < D_("0.001")
    assert abs(D_(r["fark"]) + D_("0.1")) < D_("0.002") and d["ozet"]["gerisinde"] == 1 and d["ozet"]["karsilastirilan"] == 1
    assert [g["yil"] for g in r["gecmis"]] == [2025, 2024]
    # yıllık seri: 2025 (2024'e göre %100 liste; 2024 maliyeti yok) ve 2026
    assert [(y["yil"], y["maliyet_artis_ort"] is None) for y in d["yillar"]] == [(2025, True), (2026, False)]
    assert abs(D_(d["yillar"][0]["liste_artis_ort"]) - 1) < D_("0.001")
    # güncelleme + günlük; silme
    assert istemci.put(f"{A}/liste-fiyatlari", json={"urun_kodu": "TEST", "yil": 2025, "liste_fiyati": "1"}).status_code == 200
    k = oturum.query(m.DegisiklikKaydi).filter_by(tablo="liste_fiyati", islem="guncelle").one()
    assert k.yeni["yil"] == 2025 and k.eski["liste_fiyati"] == str(liste25)
    assert istemci.delete(f"{A}/liste-fiyatlari/TEST/2024").status_code == 204
    assert istemci.delete(f"{A}/liste-fiyatlari/TEST/2024").status_code == 404
    assert istemci.put(f"{A}/liste-fiyatlari", json={"urun_kodu": "YOK", "yil": 2025, "liste_fiyati": "1"}).status_code == 404
    assert istemci.put(f"{A}/liste-fiyatlari", json={"urun_kodu": "TEST", "yil": 2025, "liste_fiyati": "0"}).status_code == 422


def test_excel_yukleme_tek_islem(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    sablon = istemci.get(f"{A}/liste-fiyatlari/sablon.xlsx")
    assert sablon.status_code == 200 and [c.value for c in load_workbook(BytesIO(sablon.content)).active[1]] == ["urun_kodu", "yil", "liste_fiyati", "birim_maliyet"]
    hatali = _xlsx([["Ürün Kodu", "Yıl", "Liste Fiyatı"], ["TEST", 2025, "40,5"], ["YOK", 2025, 10], ["TEST", 2025, 41]])
    r = istemci.post(f"{A}/liste-fiyatlari/yukle", files={"dosya": ("l.xlsx", hatali)})
    assert r.status_code == 422 and [h["satir_no"] for h in r.json()["alanlar"]["hatalar"]] == [3, 4]
    assert oturum.query(m.ListeFiyati).count() == 0
    iyi = _xlsx([["urun_kodu", "yil", "liste_fiyati", "birim_maliyet"], ["TEST", 2025, "40,5", ""], ["TEST", 2024, 30, 18.2]])
    r = istemci.post(f"{A}/liste-fiyatlari/yukle", files={"dosya": ("l.xlsx", iyi)})
    assert r.status_code == 200 and r.json()["yazilan"] == 2
    g = {k.yil: k for k in oturum.query(m.ListeFiyati)}
    assert g[2025].liste_fiyati == D_("40.5") and g[2025].birim_maliyet is None and g[2024].birim_maliyet == D_("18.2")


def test_ornek_veri_uret_sil_gercegi_ezmez(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    assert istemci.put(f"{A}/liste-fiyatlari", json={"urun_kodu": "TEST", "yil": 2024, "liste_fiyati": "7.77"}).status_code == 200
    r = istemci.post(f"{A}/liste-calismasi/ornek?senaryo={sid}")
    assert r.status_code == 200 and r.json()["yazilan"] == 2   # 2025, 2023 (2024 gerçek: atlanır)
    d = _calisma(istemci, sid)
    assert d["ornek_var"] is True and [(g["yil"], g["ornek"]) for g in d["kayitlar"][0]["gecmis"]] == [(2025, True), (2024, False), (2023, True)]
    l = D_(d["kayitlar"][0]["liste_artis"])
    assert D_("0.37") < l < D_("0.47")   # 2025 -> 2026 örnek artışı %42 ± 4 puan
    # tekrar üretmek aynı sonucu verir (sapma koddan türetilir)
    istemci.post(f"{A}/liste-calismasi/ornek?senaryo={sid}")
    assert _calisma(istemci, sid)["kayitlar"][0]["liste_artis"] == d["kayitlar"][0]["liste_artis"]
    # örnek satıra elle yazılınca gerçek olur
    assert istemci.put(f"{A}/liste-fiyatlari", json={"urun_kodu": "TEST", "yil": 2023, "liste_fiyati": "5"}).json()["ornek"] is False
    assert istemci.delete(f"{A}/liste-calismasi/ornek").json()["yazilan"] == 1
    assert sorted(k.yil for k in oturum.query(m.ListeFiyati)) == [2023, 2024]
    assert oturum.query(m.DegisiklikKaydi).filter_by(tablo="liste_fiyati", islem="ornek_sil").count() == 1
