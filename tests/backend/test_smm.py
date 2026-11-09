"""Maliyet muhasebesi (SMM): Excel yükleme, dönem, stok/envanter hesabı ve Excel'le karşılaştırma. Uydurma küçük bir SMM Excel'i kullanılır."""
from decimal import Decimal as D_
from io import BytesIO
from openpyxl import Workbook
from backend.depo import modeller as m
from backend.servisler import smm_servisi as ss
from tests.backend.test_api import istemci  # noqa: F401  (fixture)

A = "/api/v1"


def _excel(sarf_bos: bool = False, tekrar: bool = False) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)

    def sayfa(ad, satirlar, ust=None):
        ws = wb.create_sheet(ad)
        ws.append(ust or [])
        ws.append(["başlık"])
        for s in satirlar:
            ws.append(s)

    sayfa("ENVANTER", [["HM-1", "Biber", "KG", "0001-Hammadde", "150.01.001"], ["AMB-1", "Kavanoz", "AD", "0008-Ambalaj Malzeme", "150.03.031"],
                       ["YM-1", "Biber salamura", "KG", "0002-Üretim Yarı Mamul", "151.04.002"]])
    sayfa("DBS", [["HM-1", "Biber", 100, 1000], ["AMB-1", "Kavanoz", 50, 250]])
    # HM-YM ALIŞ SATIŞ: B kod, C ad, F birim, G giren miktar, K giriş maliyeti
    sayfa("HM-YM ALIŞ SATIŞ", [[None, "HM-1", "Biber", 9, 9, "KG", 100, 1400, 0, 0, 1400], [None, "AMB-1", "Kavanoz", 9, 9, "AD", 150, 900, 0, 0, 900]])
    sayfa("İADELER", [["HM-1", "Biber", None, None, "KG", None, None, 10, 120]])
    sayfa("ÜRETİM", [["YM-1", "Biber salamura"] + [0] * 8 + [500, 0, 0, 0, 500]])
    sayfa("DSS", [["HM-1", "Biber", 40], ["AMB-1", "Kavanoz", 20]])
    sayfa("40 KOD", [["02-1", "Biber 370", 1, "AD", "HM-1", "Biber", 0.2, "KG"] + [None] * 23 + [0.05]])
    sayfa("51", [[None, None, "02-1", "Biber 370", None, None, None, "Adet", 0.2, 50000, None, 12, 6, None, 7.5, 0.54, 6.48, 0.54, 3.24]])
    # TABLO: Excel'in kendi değerleri (B kod, D DBS miktar, H alım tutarı, O ort. fiyat, U DSS tutarı, V sarf, W sarf maliyeti)
    t = [[None, "HM-1", None, 100, 1000, None, 100, 1400, None, None, None, None, None, None, 12, None, None, None, None, 40, 480,
          None if sarf_bos else 150, None if sarf_bos else 1800],
         [None, "AMB-1", None, 50, 250, None, 150, 900, None, None, None, None, None, None, 5.75, None, None, None, None, 20, 115, 180, 1035]]
    if tekrar:
        t.append([None, "AMB-1", None, 0, 0, None, 0, 0, None, None, None, None, None, None, 0, None, None, None, None, 0, 0, 0, 0])
    sayfa("TABLO", t, ust=[None] * 9 + [0])
    b = BytesIO()
    wb.save(b)
    return b.getvalue()


def test_yukle_stok_hesabi_ve_excel_karsilastirma(oturum):
    d = ss.yukle(oturum, _excel(tekrar=True), "09-2026 SMM v1.xlsx", kullanici="esma")
    assert (d["yil"], d["ay"], d["ad"], d["kalem_sayisi"]) == (2026, 9, "Eylül 2026", 3)
    k = d["excel_kontrol"]
    assert (k["karsilastirilan"], k["esit"], k["farkli"], k["excelde_sarf_bos"], k["excelde_tekrar"]) == (2, 2, 0, 0, ["AMB-1"])
    assert oturum.query(m.SmmReceteSatiri).one().fire_orani == D_("0.05")
    assert oturum.query(m.SmmIscilik).one().etiket_isci == D_("6")
    t = ss.stok_tablosu(oturum, d["id"])
    hm = next(x for x in t["kayitlar"] if x["kod"] == "HM-1")
    # (1000 + 1400) / (100 + 100) = 12; kalan 200 - 10 iade = 190; sarf 190 - 40 = 150; sarf maliyeti 1800; üretime giden 1800 + 120
    assert (hm["ortalama_fiyat"], hm["kalan_miktar"], hm["sarf_miktar"], D_(hm["sarf_tutar"]), D_(hm["uretime_giden"])) == ("12", "190", "150", 1800, 1920)
    assert D_(hm["dss_tutar"]) == 480 and hm["kontrol"] is False and hm["tur"] == "0001-Hammadde"
    assert D_(t["toplamlar"]["dss_tutar"]) == 480 + 115 and D_(t["toplamlar"]["sarf_tutar"]) == 1800 + 1035
    assert [x["tur"] for x in t["turler"]] == ["0001-Hammadde", "0002-Üretim Yarı Mamul", "0008-Ambalaj Malzeme"]
    assert [x["kod"] for x in ss.stok_tablosu(oturum, d["id"], tur="0008-Ambalaj Malzeme")["kayitlar"]] == ["AMB-1"]
    # yalnız yıllık üretimi olan (stok hareketi olmayan) kalem varsayılan listede yok; tüm kalemlerde var
    assert [x["kod"] for x in ss.stok_tablosu(oturum, d["id"], arama="bİber")["kayitlar"]] == ["HM-1"]
    tum = ss.stok_tablosu(oturum, d["id"], arama="bİber", yalniz_hareketli=False)
    assert [x["kod"] for x in tum["kayitlar"]] == ["HM-1", "YM-1"]
    ym = tum["kayitlar"][1]
    assert ym["uretim_miktar"] == "500"


def test_excelde_sarf_bos_ve_finansman_dagitimi(oturum):
    d = ss.yukle(oturum, _excel(sarf_bos=True), "SMM.xlsx", yil=2026, ay=10)
    assert d["excel_kontrol"]["excelde_sarf_bos"] == 1 and d["excel_kontrol"]["excelde_sarf_bos_ornek"] == ["HM-1"]
    dn = oturum.get(m.SmmDonem, d["id"])
    dn.finansman = D_("230")   # alım tutarı oranında: HM %60,87 / AMB %39,13
    t = ss.stok_tablosu(oturum, d["id"])
    pay = {x["kod"]: D_(x["finansman_payi"]) for x in t["kayitlar"]}
    assert abs(pay["HM-1"] - D_("140")) < D_("0.0001") and abs(pay["AMB-1"] - D_("90")) < D_("0.0001")


def test_api_yukle_cakisma_ve_sil(istemci, oturum):
    dosya = {"dosya": ("09-2026 SMM.xlsx", _excel())}
    r = istemci.post(f"{A}/smm/donemler/yukle", files=dosya)
    assert r.status_code == 200, r.text
    did = r.json()["id"]
    assert istemci.post(f"{A}/smm/donemler/yukle", files={"dosya": ("09-2026 SMM.xlsx", _excel())}).status_code == 409
    r2 = istemci.post(f"{A}/smm/donemler/yukle", files={"dosya": ("09-2026 SMM.xlsx", _excel())}, data={"uzerine_yaz": "true"})
    assert r2.status_code == 200 and r2.json()["id"] == did
    assert oturum.query(m.SmmKalem).count() == 3   # üzerine yazınca çoğalmaz
    assert istemci.post(f"{A}/smm/donemler/yukle", files={"dosya": ("smm.xlsx", _excel())}).status_code == 422   # dönem yok
    assert istemci.post(f"{A}/smm/donemler/yukle", files={"dosya": ("09-2026.xlsx", b"bozuk")}).status_code == 422
    assert [x["ad"] for x in istemci.get(f"{A}/smm/donemler").json()["kayitlar"]] == ["Eylül 2026"]
    stok = istemci.get(f"{A}/smm/donemler/{did}/stok?yalniz_hareketli=false").json()
    assert len(stok["kayitlar"]) == 3 and stok["donem"]["ad"] == "Eylül 2026"
    assert istemci.delete(f"{A}/smm/donemler/{did}").status_code == 204
    assert oturum.query(m.SmmKalem).count() == 0 and istemci.get(f"{A}/smm/donemler/{did}/stok").status_code == 404
    assert oturum.query(m.DegisiklikKaydi).filter_by(tablo="smm_donem").count() == 3   # 2 yükleme + 1 silme
