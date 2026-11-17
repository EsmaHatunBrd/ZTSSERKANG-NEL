"""Müşavir Excel'i (SMM): kendi SMM Excel'i şablon, rakamlar uygulamadan.

Gidiş-dönüş: uydurma Ekim SMM Excel'i (test-dongusu/uret.py çıktısı; buna bellekte birkaç formül eklenir) yüklenir, şablon saklanır →
Kasım Excel'siz açılır, aylık kaynaklar uydurma dosyalarla yüklenir, bir mizan satırı elle değişir, bir kalem elle eklenir → Kasım'ın
müşavir Excel'i üretilir (şablon Ekim'in) → dosya uygulamanın KENDİ SMM dönem okuyucusuyla yeni bir döneme okunur → kalemler, mizanlar,
DSS ve SMM tablosu Kasım'la birebir. Gerçek şirket dosyası okunmaz."""
import json
from decimal import Decimal as D_
from io import BytesIO
from pathlib import Path
from urllib.parse import unquote

from openpyxl import load_workbook

from backend.depo import modeller as m
from backend.servisler import smm_asama_servisi as sa
from tests.backend.test_api import istemci  # noqa: F401  (fixture)
from tests.backend.test_smm_veri import _rapor

A = "/api/v1"
H = {"X-Kullanici": "esma"}
EXCEL = Path(__file__).resolve().parents[2] / "test-dongusu" / "excel"
ON = "11-16-2026-sezon-smm-"
KASIM = {"alim": "alim-satis", "iade": "iadeler", "uretim": "uretim", "sayim": "sayim", "sahit": "sahit-numune",
         "gider_mizan": "gider-mizan", "stok_mizan": "stok-mizan"}
YENI = "99.99.900"


def _dosya(ad: str) -> bytes:
    return (EXCEL / f"{ON}{ad}.xlsx").read_bytes()


def _formullu_ekim() -> bytes:
    """Ekim SMM Excel'ine gerçek dosyadaki gibi formüller eklenir: üst satır toplamı, satır formülü (DSS!E, TABLO!U), aşama sayfasında
    standart HM fiyatı formülü (40 KOD K) ve bir satırda elle yazılmış fiyat."""
    wb = load_workbook(BytesIO(_dosya("ekim-2026")))
    wb["HM-YM ALIŞ SATIŞ"]["G1"] = "=SUM(G3:G400)"
    ws = wb["DSS"]
    for r in range(3, ws.max_row + 1):
        if ws.cell(r, 1).value:
            ws.cell(r, 5).value = f"=C{r}*1"
    ws = wb["TABLO"]
    for r in range(3, ws.max_row + 1):
        if ws.cell(r, 2).value:
            ws.cell(r, 21).value = f"=D{r}*O{r}"
    ws = wb["40 KOD"]
    ilk = None
    for r in range(3, ws.max_row + 1):
        if ws.cell(r, 5).value:
            ws.cell(r, 11).value = f"=IFERROR(VLOOKUP(E{r},ENVANTER!$A:$S,19,0),0)"
            ilk = ilk or r
    ws.cell(ilk, 11).value = 0   # Ekim'de elle yazılmış fiyat (Kasım'ın kalıcı reçetesinde yok: standart formül geri gelmeli)
    b = BytesIO()
    wb.save(b)
    return b.getvalue()


def _yukle_ok(r):
    assert r.status_code in (200, 201), r.text
    return r.json()


def _formuller(wb) -> dict[tuple[str, str], str]:
    return {(ws.title, c.coordinate): c.value for ws in wb.worksheets for row in ws.iter_rows() for c in row
            if isinstance(c.value, str) and c.value.startswith("=")}


def _kalemler(oturum, did) -> dict[str, dict]:
    alanlar = ("ad", "birim", "tur", "mizan_kodu", "dbs_miktar", "dbs_tutar", "alim_miktar", "alim_tutar", "iade_miktar", "iade_tutar",
               "uretim_miktar", "sayim_miktar", "satis_miktar", "sahit_miktar", "envanterde", "uretim_asamasi")
    out = {}
    for k in oturum.query(m.SmmKalem).filter_by(donem_id=did):
        out[k.kod] = {a: (getattr(k, a) or D_(0)) if a in ("satis_miktar", "sahit_miktar") else getattr(k, a) for a in alanlar}
    return out


def _hazirla(istemci, oturum):  # noqa: F811
    """Ekim (Excel) + Canias reçeteleri + Kasım (aylık kaynaklar, elle düzeltme, elle kalem). Dönüş: (Ekim id, Kasım id, Ekim şablonu)."""
    ekim_bayt = _formullu_ekim()
    e = _yukle_ok(istemci.post(f"{A}/smm/donemler/yukle", files={"dosya": ("10-2026 SMM.xlsx", ekim_bayt)}, headers=H))
    _yukle_ok(istemci.post(f"{A}/smm/receteler/yukle", files={"dosya": ("Reçete.xlsx", _dosya("receteler-canias"))}, headers=H))
    k = _yukle_ok(istemci.post(f"{A}/smm/donemler", json={"yil": 2026, "ay": 11}, headers=H))
    for kaynak, ad in KASIM.items():
        _yukle_ok(istemci.post(f"{A}/smm/donemler/{k['id']}/veri/{kaynak}", files={"dosya": (f"kasim-{ad}.xlsx", _dosya(f"kasim-2026-{ad}"))},
                               headers=H))
    gm = _yukle_ok(istemci.get(f"{A}/smm/donemler/{k['id']}/mizan/gider"))
    eski = next(D_(x["bakiye"]) for x in gm["kayitlar"] if x["hesap"] == "720")
    _yukle_ok(istemci.patch(f"{A}/smm/donemler/{k['id']}/mizan/gider/720", json={"bakiye": str(eski + D_("1234.56")), "neden": "kesinleşti"},
                            headers=H))
    _yukle_ok(istemci.post(f"{A}/smm/donemler/{k['id']}/stok", json={
        "kod": YENI, "ad": "Test yeni koli", "birim": "AD", "tur": "0008-Ambalaj Malzeme", "mizan_kodu": "150.02", "alim_miktar": "10",
        "alim_tutar": "55.5", "sayim_miktar": "4", "neden": "kart eksikti"}, headers=H))
    return e["id"], k["id"], ekim_bayt


def test_gidis_donus_kasim_sablonu_ekimden(istemci, oturum):  # noqa: F811
    eid, kid, ekim_bayt = _hazirla(istemci, oturum)
    assert oturum.get(m.SmmDonem, kid).recete_kaynagi == "ana"

    # durum: Kasım'ın kendi şablonu yok, Ekim'inki kullanılır; dönem kapatılmadı
    du = _yukle_ok(istemci.get(f"{A}/smm/donemler/{kid}/musavir-excel/durum"))
    assert du["sablon"]["dosya_adi"] == "10-2026 SMM.xlsx" and du["kaynak_donem"] == "Ekim 2026" and du["kaynak_donem_id"] == eid
    assert du["kendi"] is False and du["taslak"] is True
    assert _yukle_ok(istemci.get(f"{A}/smm/donemler/{eid}/musavir-excel/durum"))["kendi"] is True

    r = istemci.get(f"{A}/smm/donemler/{kid}/musavir-excel.xlsx")
    assert r.status_code == 200 and "spreadsheetml" in r.headers["content-type"]
    ad = unquote(r.headers["content-disposition"].split("''")[1])
    assert ad.startswith("11-2026 SMM - uygulama ") and ad.endswith(".xlsx")
    uyarilar = json.loads(unquote(r.headers["x-musavir-uyarilar"]))
    assert any("Şablon: Ekim 2026" in u for u in uyarilar)
    assert any("ENVANTER: şablondaki satırlar yetmedi" in u for u in uyarilar)   # elle eklenen kalem şablonun altına
    assert any("kalıcı Canias reçeteleri" in u for u in uyarilar)

    # biçim: sayfa adları / sırası aynı, şablondaki her formül aynen duruyor; dosya özellikleri; Excel açınca yeniden hesaplar
    sab, cik = load_workbook(BytesIO(ekim_bayt)), load_workbook(BytesIO(r.content))
    assert cik.sheetnames == sab.sheetnames
    fs, fc = _formuller(sab), _formuller(cik)
    assert all(fc.get(k) == v for k, v in fs.items()), [k for k, v in fs.items() if fc.get(k) != v][:5]
    assert cik.calculation.fullCalcOnLoad is True
    assert "TASLAK" in cik.properties.description and "Kasım 2026" in cik.properties.description
    for ws_s in sab.worksheets:   # birleştirilmiş hücreler ve sütun genişlikleri değişmez
        ws_c = cik[ws_s.title]
        assert set(map(str, ws_c.merged_cells.ranges)) == set(map(str, ws_s.merged_cells.ranges))
        assert {k: v.width for k, v in ws_s.column_dimensions.items()} == {k: v.width for k, v in ws_c.column_dimensions.items()}

    # Ekim'den iz yok: fiş numaraları, Ekim'e özgü iade / şahit / satış satırları, alt hesaplar, eski mizan tarihi
    def kodlar(sayfa, sut=1):
        ws = cik[sayfa]
        return [ws.cell(r_, sut).value for r_ in range(3, ws.max_row + 1) if ws.cell(r_, sut).value is not None]
    ekim_iade = [sab["İADELER"].cell(r_, 1).value for r_ in range(3, sab["İADELER"].max_row + 1)]
    assert ekim_iade and not set(ekim_iade) & set(kodlar("İADELER"))
    assert "03.99.004" not in kodlar("ŞAHİT") and "03.99.004" in [sab["ŞAHİT"].cell(r_, 1).value for r_ in range(3, sab["ŞAHİT"].max_row + 1)]
    alim = cik["HM-YM ALIŞ SATIŞ"]
    assert not any(str(alim.cell(r_, 1).value or "").startswith(("ALS-", "STS-")) for r_ in range(3, alim.max_row + 1))
    assert "Satış" not in kodlar("HM-YM ALIŞ SATIŞ", 20)   # Ekim'de HM satışı vardı, Kasım'da yok
    assert not any("." in str(h) for h in kodlar("GİDER MİZAN")[1:])   # 720.01 gibi alt hesaplar yok (uygulama ana hesapları tutar)
    assert cik["STOK MİZAN"]["J2"].value == "30.11.2026"
    assert "Kasım 2026" in cik["ENVANTER"]["A1"].value and "Ekim" not in cik["ENVANTER"]["A1"].value
    # 40 KOD: Ekim'deki elle fiyat, Kasım reçetesinde elle değer olmadığı için standart formüle döndü
    k40 = cik["40 KOD"]
    assert all(str(k40.cell(r_, 11).value).startswith("=IFERROR(VLOOKUP(E") for r_ in range(3, k40.max_row + 1) if k40.cell(r_, 5).value)
    # 40 KOD satırları kalıcı reçeteden: elle 0 yazılmış satırın ürünü artık formülle
    assert all(isinstance(cik["DSS"].cell(r_, 5).value, str) for r_ in range(3, cik["DSS"].max_row + 1) if cik["DSS"].cell(r_, 1).value
               and r_ <= sab["DSS"].max_row)

    # gidiş-dönüş: üretilen dosyayı uygulamanın kendi okuyucusuyla yeni döneme (Aralık) oku
    a = _yukle_ok(istemci.post(f"{A}/smm/donemler/yukle", files={"dosya": (ad, r.content)}, data={"yil": 2026, "ay": 12}, headers=H))
    aid = a["id"]
    kk, ka = _kalemler(oturum, kid), _kalemler(oturum, aid)
    assert set(ka) == set(kk) and YENI in ka
    farkli = {kod: {f: (kk[kod][f], ka[kod][f]) for f in kk[kod] if kk[kod][f] != ka[kod][f]} for kod in kk if kk[kod] != ka[kod]}
    assert not farkli, list(farkli.items())[:5]
    dk, da = oturum.get(m.SmmDonem, kid), oturum.get(m.SmmDonem, aid)
    assert {h: D_(v) for h, v in dk.excel_ozet["gider_mizan"].items()} == {h: D_(v) for h, v in da.excel_ozet["gider_mizan"].items()}
    assert [(x["hesap"], D_(x["bakiye"])) for x in dk.excel_ozet["stok_mizan"]] == [(x["hesap"], D_(x["bakiye"])) for x in da.excel_ozet["stok_mizan"]]
    assert {h: D_(v) for h, v in dk.gider_mizan.items()} == {h: D_(v) for h, v in da.gider_mizan.items()}
    assert sa._havuz(dk) == sa._havuz(da) and dk.finansman == da.finansman
    sure = lambda did: sorted((x.mamul_kod, x.yari_mamul_kod, x.vardiya_uretim, x.dolum_sn, x.dolum_adam_sn, x.etiket_sn, x.etiket_adam_sn)  # noqa: E731
                              for x in oturum.query(m.SmmIscilik).filter_by(donem_id=did))
    assert sure(kid) == sure(aid)
    # aşama birim maliyetleri (Kasım: kalıcı reçete; Aralık: dosyadaki 20/40/50 KOD) ve SMM özeti birebir
    for asama in (20, 40, 50):
        uk = {x["kod"]: D_(x["birim_maliyet"]) for x in _yukle_ok(istemci.get(f"{A}/smm/donemler/{kid}/uretim?asama={asama}"))["kayitlar"]}
        ua = {x["kod"]: D_(x["birim_maliyet"]) for x in _yukle_ok(istemci.get(f"{A}/smm/donemler/{aid}/uretim?asama={asama}"))["kayitlar"]}
        assert uk and uk == ua, asama
    ok, oa = (_yukle_ok(istemci.get(f"{A}/smm/donemler/{x}/ozet")) for x in (kid, aid))
    for alan in ("smm", "uretim_maliyeti", "uretilen", "ilk_madde", "donem_sonu_stok", "fis_borc", "fis_alacak", "mizan_kiyas"):
        assert ok[alan] == oa[alan], alan
    assert ok["tablo"] == oa["tablo"]
    # DSS!E bu şablonda formül: üzerine yazılmadı (Excel kendi hesaplar); kıyas formül olmayan şablonda (aşağıdaki test)
    assert oa["dss_kiyas"]["karsilastirilan"] == 0
    # Excel'in kendi TABLO değerleri de (formül olmayan sütunlar) uygulamanın hesabıyla aynı
    assert a["excel_kontrol"]["farkli"] == 0 and a["excel_kontrol"]["esit"] > 0


def test_sablon_yok_404_yalniz_sakla_ve_silme(istemci, oturum):  # noqa: F811
    did = _yukle_ok(istemci.post(f"{A}/smm/donemler", json={"yil": 2026, "ay": 1}, headers=H))["id"]
    du = _yukle_ok(istemci.get(f"{A}/smm/donemler/{did}/musavir-excel/durum"))
    assert du["sablon"] is None and du["kaynak_donem"] is None
    r = istemci.get(f"{A}/smm/donemler/{did}/musavir-excel.xlsx")
    assert r.status_code == 404 and r.json()["kod"] == "sablon_yok" and "SMM Excel'inden yükle" in r.json()["mesaj"]
    assert istemci.get(f"{A}/smm/donemler/9999/musavir-excel/durum").status_code == 404

    # SMM Excel'i olmayan dosya reddedilir (önizlemede de, saklamada da)
    yanlis = _rapor(["StokKartıKodu", "Ad", "Miktar"], [["HM-1", "Biber", 30]], "DSS")
    r = istemci.post(f"{A}/smm/donemler/{did}/musavir-excel/sablon/onizle", files={"dosya": ("sayim.xlsx", yanlis)})
    assert r.status_code == 422 and r.json()["kod"] == "smm_excel_degil"
    assert istemci.post(f"{A}/smm/donemler/{did}/musavir-excel/sablon", files={"dosya": ("x.xlsx", b"bozuk")}).status_code == 422
    # yalnız sakla: dönem verisine dokunmaz
    kalem_once = oturum.query(m.SmmKalem).filter_by(donem_id=did).count()
    on = _yukle_ok(istemci.post(f"{A}/smm/donemler/{did}/musavir-excel/sablon/onizle", files={"dosya": ("01-2026 SMM.xlsx", _dosya("ekim-2026"))}))
    assert "ENVANTER" in on["sayfalar"] and on["donem"] == "Ocak 2026" and on["mevcut"] is None
    du = _yukle_ok(istemci.post(f"{A}/smm/donemler/{did}/musavir-excel/sablon", files={"dosya": ("01-2026 SMM.xlsx", _dosya("ekim-2026"))},
                                headers=H))
    assert du["kendi"] is True and du["sablon"]["dosya_adi"] == "01-2026 SMM.xlsx" and du["sablon"]["olusturan"] == "esma"
    assert oturum.query(m.SmmKalem).filter_by(donem_id=did).count() == kalem_once
    r = istemci.get(f"{A}/smm/donemler/{did}/musavir-excel.xlsx")
    assert r.status_code == 200 and "01-2026 SMM - uygulama" in unquote(r.headers["content-disposition"])
    # dönem silinince şablonu da silinir
    assert istemci.delete(f"{A}/smm/donemler/{did}").status_code == 204
    assert oturum.query(m.ExcelSablonu).filter_by(tur="smm_donem").count() == 0


def test_kapali_donem_taslak_degil(istemci, oturum):  # noqa: F811
    did = _yukle_ok(istemci.post(f"{A}/smm/donemler/yukle", files={"dosya": ("10-2026 SMM.xlsx", _dosya("ekim-2026"))}, headers=H))["id"]
    _yukle_ok(istemci.put(f"{A}/smm/donemler/{did}/kilit", json={"kilitli": True, "zorla": True}, headers=H))
    assert _yukle_ok(istemci.get(f"{A}/smm/donemler/{did}/musavir-excel/durum"))["taslak"] is False
    r = istemci.get(f"{A}/smm/donemler/{did}/musavir-excel.xlsx")
    wb = load_workbook(BytesIO(r.content))
    assert "TASLAK" not in wb.properties.description
    # kendi Excel'iyle üretilen dosya, yüklenen dosyayla aynı veriyi taşır (okuyucu aynı kalemleri okur)
    a = _yukle_ok(istemci.post(f"{A}/smm/donemler/yukle", files={"dosya": ("x.xlsx", r.content)}, data={"yil": 2026, "ay": 12}, headers=H))
    assert _kalemler(oturum, did) == _kalemler(oturum, a["id"])
    # DSS!E sabit: uygulamanın dönem sonu stok değerlemesi yazılır, okununca kalem kalem aynı; SMM tablosu aynı
    ok, oa = (_yukle_ok(istemci.get(f"{A}/smm/donemler/{x}/ozet")) for x in (did, a["id"]))
    assert oa["dss_kiyas"]["karsilastirilan"] > 0 and oa["dss_kiyas"]["farkli"] == 0
    assert ok["tablo"] == oa["tablo"] and ok["smm"] == oa["smm"]
