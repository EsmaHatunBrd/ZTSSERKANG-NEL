"""Faz 5 T5: GET /disa-aktar/teklif-kapak.xlsx (Excel 'Teklif Kapak' düzeni)."""
from decimal import Decimal as D_
from io import BytesIO
from openpyxl import load_workbook
from backend.depo import modeller as m
from backend.servisler import hesap_servisi as hs
from tests.backend.test_api import _kur, _senaryo, istemci  # noqa: F401

A = "/api/v1"
TARIH = "2026-10-21"
BASLIK_1 = {"A": "Grup", "B": "S.\nNO", "C": "ÜRÜN KODU", "D": "ÜRÜN ADI", "E": "REÇETE MALİYETİ", "G": "GÜG", "H": "FAALİYET\nGİDERİ", "I": "FİNANS\nGİDERİ",
            "J": "GÜG+\nFAAL+\nFİN", "K": "GİDER\nMALİYET\n%", "L": "BİRİM MALİYET", "Q": "BİRİM MALİYET"}
BASLIK_2 = {"E": "Maliyet", "F": "Maliyet\n%", "L": "TL", "M": "USD", "N": "EURO", "O": "Üretim\nAdedi", "P": "Üretim\nAdedi", "Q": "TL", "R": "USD", "S": "EURO",
            "T": "Üretim\nAdedi"}


def _ikinci_urun(c, sid, kod="TEST2", recete=True):
    assert c.put(f"{A}/urunler/{kod}", json={"ad": "İkinci", "ambalaj_hacmi": "370", "hat": "Niko", "taze_tursu_sinifi": "Turşu/Turşu", "suzme_kg": "0.18"}).status_code == 200
    assert c.put(f"{A}/urunler/{kod}/uretim-hedefi?senaryo={sid}", json={"vardiya_uretim_adedi": "40000", "dolum_personel": "13", "etiketleme_adedi": "35000",
                 "etiket_personel": "7", "mal_kabul_miktar_kg": "0.19"}).status_code == 200
    if recete:
        assert c.post(f"{A}/urunler/{kod}/recete?senaryo={sid}", json=[{"malzeme_kodu": "KAV", "ad": "Kavanoz", "miktar": "2", "birim": "AD"}]).status_code == 201


def _kapasite(oturum, sid, kod, hedef):
    oturum.add(m.UretimKapasitesi(senaryo_id=sid, urun_kodu=kod, urun_ad=kod, net_kapasite=D_("1000"), net_sure=D_("1"), toplam_kapasite=D_("900"),
                                  toplam_sure=D_("1"), hedef_uretim=D_(hedef), ortalama_isci=D_("10")))
    oturum.flush()


def _ac(r):
    assert r.status_code == 200, r.text
    return load_workbook(BytesIO(r.content)).active


def _satir(ws, kod):
    return next(i for i in range(4, ws.max_row + 1) if ws[f"C{i}"].value == kod)


def test_teklif_kapak_duzeni_ve_degerler(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum); _ikinci_urun(istemci, sid)
    _kapasite(oturum, sid, "TEST", "30000")
    r = istemci.get(f"{A}/disa-aktar/teklif-kapak.xlsx?senaryo={sid}&tarih={TARIH}")
    assert r.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert f"teklif-kapak-{sid}.xlsx" in r.headers["content-disposition"]
    ws = _ac(r)
    assert ws.title == "Teklif Kapak"
    assert ws["B1"].value == "2026-2027 SEZONU FİYAT ÇALIŞMALARI - A" and ws["G1"].value == "GİDERLER"
    for h, v in BASLIK_1.items():
        assert ws[f"{h}2"].value == v, h
    for h, v in BASLIK_2.items():
        assert ws[f"{h}3"].value == v, h
    assert ws.freeze_panes == "A4"
    assert {str(x) for x in ws.merged_cells.ranges} >= {"L2:O2", "Q2:T2"}

    from datetime import date
    satirlar = {x["kod"]: x for x in __import__("backend.api.urunler", fromlist=["x"]).dashboard_satirlari(oturum, sid, date.fromisoformat(TARIH))}
    i = _satir(ws, "TEST")
    d = satirlar["TEST"]
    assert ws[f"D{i}"].value == "Test" and ws[f"A{i}"].value == "Niko"
    assert abs(ws[f"L{i}"].value - float(d["maliyet_tl"])) < 1e-6
    assert abs(ws[f"E{i}"].value - float(d["recete_maliyeti"])) < 1e-6
    g, h_, f = (ws[f"{x}{i}"].value for x in "GHI")
    assert abs(ws[f"J{i}"].value - (g + h_ + f)) < 1e-9
    assert abs(ws[f"K{i}"].value - ws[f"J{i}"].value / ws[f"L{i}"].value) < 1e-9
    assert abs(ws[f"F{i}"].value - ws[f"E{i}"].value / ws[f"L{i}"].value) < 1e-9
    assert abs(ws[f"M{i}"].value - float(d["maliyet_usd"])) < 1e-6 and abs(ws[f"N{i}"].value - float(d["maliyet_eur"])) < 1e-6
    assert ws[f"O{i}"].value == 65000 and ws[f"P{i}"].value is None
    hedefli = hs.hesapla(oturum, "TEST", sid, date.fromisoformat(TARIH), override={"uretim": {"vardiya_uretim_adedi": D_("30000")}}).sonuc
    assert abs(ws[f"Q{i}"].value - float(hedefli.finansman_dahil_maliyet_tl)) < 1e-6
    assert abs(ws[f"R{i}"].value - float(hedefli.doviz_maliyet["USD"])) < 1e-6
    assert ws[f"T{i}"].value == 30000 and abs(ws[f"V{i}"].value - 30000 / 65000) < 1e-9
    assert ws[f"Q{i}"].value > ws[f"L{i}"].value   # daha az adet -> daha yüksek birim maliyet
    assert ws[f"L{i}"].number_format == "#,##0.00" and ws[f"K{i}"].number_format == "0.0%" and ws["D2"].font.bold

    j = _satir(ws, "TEST2")   # kapasitesiz: Q-T ve V boş
    assert all(ws[f"{x}{j}"].value is None for x in "QRSTV") and ws[f"L{j}"].value is not None
    assert (i < j) and ws[f"B{i}"].value == 1 and ws[f"B{j}"].value == 2


def test_teklif_kapak_hatali_urun(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum); _ikinci_urun(istemci, sid, "BOS", recete=False)
    ws = _ac(istemci.get(f"{A}/disa-aktar/teklif-kapak.xlsx?senaryo={sid}&tarih={TARIH}"))
    assert all(ws[f"C{i}"].value != "BOS" for i in range(4, ws.max_row + 1))   # Faz 5c: reçetesiz ürün senaryo üyesi değil; tum=1 eski davranış
    ws = _ac(istemci.get(f"{A}/disa-aktar/teklif-kapak.xlsx?senaryo={sid}&tarih={TARIH}&tum=1"))
    i = _satir(ws, "BOS")
    assert ws[f"D{i}"].value.startswith("İkinci") and "HATA:" in ws[f"D{i}"].value
    assert all(ws[f"{x}{i}"].value is None for x in "EFGHIJKLMNOQ")
    assert ws[f"L{_satir(ws, 'TEST')}"].value is not None


def test_teklif_kapak_bilinmeyen_senaryo(istemci):
    assert istemci.get(f"{A}/disa-aktar/teklif-kapak.xlsx?senaryo=999").status_code == 404


def test_teklif_kapak_hedef_sifir(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    _kapasite(oturum, sid, "TEST", "0")
    ws = _ac(istemci.get(f"{A}/disa-aktar/teklif-kapak.xlsx?senaryo={sid}&tarih={TARIH}"))
    i = _satir(ws, "TEST")
    assert all(ws[f"{x}{i}"].value is None for x in "QRSTV") and ws[f"L{i}"].value is not None


def test_teklif_kapak_hedef_hesabi_patlarsa(istemci, oturum, monkeypatch):
    from decimal import InvalidOperation
    sid = _senaryo(istemci); _kur(istemci, sid, oturum); _ikinci_urun(istemci, sid)
    _kapasite(oturum, sid, "TEST", "30000"); _kapasite(oturum, sid, "TEST2", "20000")
    gercek = hs.hesapla

    def sahte(s, kod, *a, override=None, **k):
        if override and kod == "TEST":
            raise InvalidOperation("test")
        return gercek(s, kod, *a, override=override, **k)
    monkeypatch.setattr(hs, "hesapla", sahte)
    ws = _ac(istemci.get(f"{A}/disa-aktar/teklif-kapak.xlsx?senaryo={sid}&tarih={TARIH}"))
    i, j = _satir(ws, "TEST"), _satir(ws, "TEST2")
    assert ws[f"L{i}"].value is not None and all(ws[f"{x}{i}"].value is None for x in "QRSTV")
    assert ws[f"Q{j}"].value is not None and ws[f"T{j}"].value == 20000
