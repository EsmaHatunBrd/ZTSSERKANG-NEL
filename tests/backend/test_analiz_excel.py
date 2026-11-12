"""Analiz sonuçlarının Excel'e indirilmesi: marjı koruyan fiyat, kârlılık haritası, kur riski."""
from datetime import date
from decimal import Decimal as D_
from io import BytesIO
from openpyxl import load_workbook
from backend.depo import modeller as m
from tests.backend.test_analiz_2 import _kurulum, _satis
from tests.backend.test_analiz_3 import _hazirla
from tests.backend.test_api import _senaryo, istemci  # noqa: F401  (fixture)

A = "/api/v1"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _ac(r, dosya: str):
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith(XLSX)
    assert r.headers["content-disposition"] == f'attachment; filename="{dosya}"'
    wb = load_workbook(BytesIO(r.content))
    assert wb.sheetnames[1] == "Özet"
    return wb


def _veri(ws) -> dict[str, dict]:
    """4. satır başlıklarıyla 5. satırdan itibaren veri; koda göre."""
    basliklar = [c.value for c in ws[4]]
    return {row[0]: dict(zip(basliklar, row)) for row in ws.iter_rows(min_row=5, values_only=True)}


def _ozet(wb) -> dict:
    return {row[0]: row[1] for row in wb["Özet"].iter_rows(min_row=4, values_only=True) if row[0]}


def _yakin(a, b):
    assert a is not None and abs(D_(str(a)) - D_(str(b))) < D_("0.0000001"), (a, b)


def test_hedef_fiyat_excel(istemci, oturum):
    sid = _hazirla(istemci, oturum)
    sen_ad = oturum.get(m.Senaryo, sid).ad
    d = istemci.get(f"{A}/analiz/hedef-fiyat?senaryo={sid}&marj=0.15").json()
    k = {x["kod"]: x for x in d["kayitlar"]}
    wb = _ac(istemci.get(f"{A}/disa-aktar/hedef-fiyat.xlsx?senaryo={sid}&marj=0.15"), "marji-koruyan-fiyat.xlsx")
    ws = wb.worksheets[0]
    assert ws["A1"].value == f"Marjı Koruyan Fiyat — {sen_ad} — {date.today():%d.%m.%Y}" and ws["A1"].font.bold
    assert ws["A2"].value.startswith("Hedef marj: %15 · Liste böleni yurtiçi: 0,63 · Liste böleni yurtdışı: 0,9 · "
                                     "Yuvarlama: en yakın 0,01 TL · KDV hariç · Liste fiyatı yalnız Berrak ürünlerinde · "
                                     "Yıllık adet: geçen yılın satış adedi")
    assert [c.value for c in ws[4]] == ["Kod", "Ürün", "Aile", "Bölge", "Maliyet TL", "Geçen Yıl Fiyatı TL", "Mevcut Marj", "Hedef Fiyat TL",
                                        "Gereken Zam", "Liste Fiyatı Yurtiçi TL", "Liste Fiyatı Yurtdışı TL", "Yıllık Adet", "Yıllık Ek Gelir TL",
                                        "Hata"]
    assert ws["A4"].font.bold and ws.freeze_panes == "A5" and ws.auto_filter.ref == "A4:N8"
    assert ws.column_dimensions["B"].width == 45
    v = _veri(ws)
    assert list(v) == [x["kod"] for x in d["kayitlar"]]   # servis sırası korunur
    t4 = v["T4"]
    _yakin(t4["Maliyet TL"], k["T4"]["maliyet"]); _yakin(t4["Hedef Fiyat TL"], k["T4"]["hedef_fiyat"])
    _yakin(t4["Gereken Zam"], k["T4"]["gereken_zam"]); _yakin(t4["Yıllık Ek Gelir TL"], k["T4"]["yillik_ek_gelir"])
    assert t4["Geçen Yıl Fiyatı TL"] == 15 and t4["Yıllık Adet"] == 5000 and t4["Hata"] is None
    assert t4["Liste Fiyatı Yurtiçi TL"] is None and t4["Liste Fiyatı Yurtdışı TL"] is None   # T4 Berrak değil
    t2 = v["T2"]   # Berrak: iki liste fiyatı
    _yakin(t2["Liste Fiyatı Yurtiçi TL"], k["T2"]["liste_fiyati_yurtici"]); _yakin(t2["Liste Fiyatı Yurtdışı TL"], k["T2"]["liste_fiyati_yurtdisi"])
    satir = list(v).index("T4") + 5
    assert ws[f"E{satir}"].number_format == "#,##0.00" and ws[f"G{satir}"].number_format == "0.0%" and ws[f"L{satir}"].number_format == "#,##0"
    assert ws[f"J{satir}"].number_format == "#,##0.00" and ws[f"K{satir}"].number_format == "#,##0.00"
    t3 = v["T3"]   # geçen yıl fiyatı yok: boş hücreler, bölge boş
    assert t3["Geçen Yıl Fiyatı TL"] is None and t3["Gereken Zam"] is None and t3["Bölge"] is None and t3["Yıllık Adet"] is None
    from backend.api.disa_aktar import BOLGE_ETIKETI
    assert v["TEST"]["Bölge"] == BOLGE_ETIKETI[k["TEST"]["bolge"]]
    o = _ozet(wb)
    assert o["Ürün sayısı"] == 4 and o["Zam gereken ürün"] == 2 and o["Geçen yıl fiyatı olmayan"] == 1 and o["Hatalı"] == 0
    _yakin(o["Ortalama gereken zam (ciro ağırlıklı) %"], d["ozet"]["ort_zam"]); _yakin(o["Yıllık ek gelir TL"], d["ozet"]["yillik_ek_gelir"])


def test_hedef_fiyat_excel_suzme(istemci, oturum):
    sid = _hazirla(istemci, oturum)
    d = istemci.get(f"{A}/analiz/hedef-fiyat?senaryo={sid}&marj=0.15").json()
    zamli = [x["kod"] for x in d["kayitlar"] if x["gereken_zam"] is not None and D_(x["gereken_zam"]) > 0]
    assert sorted(zamli) == ["T2", "T4"]
    ws = _ac(istemci.get(f"{A}/disa-aktar/hedef-fiyat.xlsx?senaryo={sid}&marj=0.15&yalniz_zam=1"), "marji-koruyan-fiyat.xlsx").worksheets[0]
    assert list(_veri(ws)) == zamli and "Yalnız zam gerekenler" in ws["A2"].value
    bolge = d["kayitlar"][0]["bolge"]   # T4
    beklenen = [x["kod"] for x in d["kayitlar"] if x["bolge"] == bolge]
    ws2 = _ac(istemci.get(f"{A}/disa-aktar/hedef-fiyat.xlsx?senaryo={sid}&marj=0.15&bolge={bolge}"), "marji-koruyan-fiyat.xlsx").worksheets[0]
    assert list(_veri(ws2)) == beklenen and len(beklenen) < 4
    # hiç satır kalmasa da dosya iner (başlıklar durur)
    ws3 = _ac(istemci.get(f"{A}/disa-aktar/hedef-fiyat.xlsx?senaryo={sid}&marj=0.15&bolge=dusuk_adet_yuksek_marj&yalniz_zam=1"),
              "marji-koruyan-fiyat.xlsx").worksheets[0]
    assert ws3["A4"].value == "Kod"


def test_hedef_fiyat_excel_dogrulama(istemci, oturum):
    sid = _hazirla(istemci, oturum)
    assert istemci.get(f"{A}/disa-aktar/hedef-fiyat.xlsx?senaryo={sid}&marj=-2").status_code == 422
    assert istemci.get(f"{A}/disa-aktar/hedef-fiyat.xlsx?senaryo={sid}&marj=6").status_code == 422
    assert istemci.get(f"{A}/disa-aktar/hedef-fiyat.xlsx?senaryo={sid}&bolge=yok").status_code == 422
    assert istemci.get(f"{A}/disa-aktar/hedef-fiyat.xlsx?senaryo=99999").status_code == 404


def test_karlilik_excel(istemci, oturum):
    sid = _senaryo(istemci); _kurulum(istemci, sid, oturum)
    _satis(oturum, sid, "TEST", "100", "TL", "1000")
    _satis(oturum, sid, "T2", "1", "TL", "100")
    _satis(oturum, sid, "T4", "1", "USD", "5000")
    d = istemci.get(f"{A}/analiz/karlilik?senaryo={sid}").json()
    k = {x["kod"]: x for x in d["kayitlar"]}
    wb = _ac(istemci.get(f"{A}/disa-aktar/karlilik.xlsx?senaryo={sid}"), "karlilik-haritasi.xlsx")
    ws = wb.worksheets[0]
    assert ws["A1"].value.startswith("Kârlılık Haritası — ") and ws["A2"].value.startswith("Marj eşiği: %10 · Adet eşiği (medyan): 1.000")
    assert [c.value for c in ws[4]] == ["Kod", "Ürün", "Aile", "Bölge", "Yıllık Adet", "Maliyet TL", "Satış Fiyatı TL", "Fiyat Kaynağı", "Marj",
                                        "Yıllık Kâr TL", "Hata"]
    v = _veri(ws)
    assert list(v) == ["T4", "TEST", "T2", "T3"]
    t = v["TEST"]
    assert t["Bölge"] == "Yıldız" and t["Fiyat Kaynağı"] == "Geçen yıl satış" and t["Satış Fiyatı TL"] == 100 and t["Yıllık Adet"] == 1000
    _yakin(t["Marj"], k["TEST"]["marj"]); _yakin(t["Yıllık Kâr TL"], k["TEST"]["yillik_kar"])
    assert v["T2"]["Bölge"] == "Sorgula" and v["T3"]["Fiyat Kaynağı"] == "Çalışma hesabı" and v["T3"]["Bölge"] is None
    o = _ozet(wb)
    assert o["Ürün sayısı"] == 4 and o["Yıldız"] == 2 and o["Sorgula"] == 1 and o["Fiyatı gözden geçir"] == 0 and o["Yıllık adedi olmayan"] == 1
    ws2 = _ac(istemci.get(f"{A}/disa-aktar/karlilik.xlsx?senaryo={sid}&bolge=yuksek_adet_yuksek_marj"), "karlilik-haritasi.xlsx").worksheets[0]
    assert list(_veri(ws2)) == ["T4", "TEST"] and "Bölge: Yıldız" in ws2["A2"].value


def test_kur_riski_excel(istemci, oturum):
    sid = _senaryo(istemci); _kurulum(istemci, sid, oturum)
    _satis(oturum, sid, "TEST", "100", "TL", "1000")
    d = istemci.get(f"{A}/analiz/kur-riski?senaryo={sid}&oran=0.2").json()
    k = {x["kod"]: x for x in d["kayitlar"]}
    wb = _ac(istemci.get(f"{A}/disa-aktar/kur-riski.xlsx?senaryo={sid}&oran=0.2"), "kur-riski.xlsx")
    ws = wb.worksheets[0]
    assert ws["A1"].value.startswith("Kur Riski — ") and ws["A2"].value.startswith("Kur artışı: %20 · Kurlar: ")
    assert [c.value for c in ws[4]] == ["Kod", "Ürün", "Hat", "Maliyet TL", "Döviz Payı", "USD Payı", "EUR Payı", "Birim Etki TL", "Yeni Maliyet TL",
                                        "Yıllık Adet", "Yıllık Etki TL", "Hata"]
    v = _veri(ws)
    assert list(v) == [x["kod"] for x in d["kayitlar"]]
    t = v["TEST"]
    _yakin(t["Döviz Payı"], k["TEST"]["doviz_payi"]); _yakin(t["Birim Etki TL"], k["TEST"]["birim_etki"])
    _yakin(t["Yıllık Etki TL"], k["TEST"]["yillik_etki"]); assert t["Yıllık Adet"] == 1000 and t["Hat"] == "Niko"
    assert v["T2"]["Yıllık Adet"] is None and v["T2"]["Yıllık Etki TL"] is None
    o = _ozet(wb)
    assert o["Ürün sayısı"] == 4 and o["Yıllık adedi olmayan"] == 3
    _yakin(o["Yıllık etki TL"], d["ozet"]["yillik_etki"])
    # para birimi kırılımı tablosu
    satirlar = list(wb["Özet"].iter_rows(min_row=4, values_only=True))
    i = next(n for n, r in enumerate(satirlar) if r[0] == "Para Birimi")
    assert satirlar[i][:3] == ("Para Birimi", "Yıllık Etki TL", "Pay")
    pb = {r[0]: r for r in satirlar[i + 1:]}
    assert set(pb) == {x["para_birimi"] for x in d["para_birimleri"]}
    _yakin(pb["USD"][1], next(x["yillik_etki"] for x in d["para_birimleri"] if x["para_birimi"] == "USD"))


def test_kur_riski_excel_dogrulama(istemci, oturum):
    sid = _senaryo(istemci); _kurulum(istemci, sid, oturum)
    assert istemci.get(f"{A}/disa-aktar/kur-riski.xlsx?senaryo={sid}&oran=-1").status_code == 422
    assert istemci.get(f"{A}/disa-aktar/kur-riski.xlsx?senaryo={sid}&oran=abc").status_code == 422
