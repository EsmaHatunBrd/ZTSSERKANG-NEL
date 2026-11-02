"""Faz 5: Veri Aktar - üretim adetleri, satın alma BF, gider dağıtım (önizle/uygula; tam kitap ve tek sayfalık dosya)."""
from decimal import Decimal as D_
from io import BytesIO
from openpyxl import Workbook
from sqlalchemy import select
from backend.depo import modeller as m
from tests.backend.test_api import _senaryo, istemci  # noqa: F401

A = "/api/v1/aktarim"
H = {"X-Kullanici": "esma"}
GIDER_SAYILARI = {"D4": 1000, "F4": 500, "A6": 800, "D13": 300, "F13": 200, "D18": 400, "F18": 250, "A20": 100, "D27": 150, "F27": 600,
                  "D38": 900, "D49": 700, "D60": 600, "D64": 2000, "D67": 1000}


def _bytes(wb) -> bytes:
    b = BytesIO(); wb.save(b)
    return b.getvalue()


def _iki_sayfa_yanlis() -> bytes:
    wb = Workbook(); wb.active.title = "A"; wb.create_sheet("B")
    return _bytes(wb)


def _uretim(satirlar, tam=False, baslik7="HEDEF VARDİYALIK ÜRETİM") -> bytes:
    wb = Workbook(); ws = wb.active
    if tam:
        ws.title = "Diğer"; ws = wb.create_sheet("Üretim Adetleri")
    ws.append(["Başlık"])
    ws.append(["ÜRÜN KODU", "ÜRÜN ADI", "NK", "NS", "TK", "TS", baslik7, "İŞÇİ"])
    ws.append(["alt"])
    for r in satirlar:
        ws.append(r)
    return _bytes(wb)


U1 = ["T-1", "Ürün 1", 100, 7, 120, 8, 90, 10]
U2 = ["T-2", "Ürün 2", 200, 7, 220, 8, 190, 12]


def _satin(satirlar, tam=False) -> bytes:
    wb = Workbook(); ws = wb.active
    if tam:
        ws.title = "Diğer"; ws = wb.create_sheet("S.ALMA BF")
    ws.append(["Malzeme", "Açıklama", "Malzeme Tipi", "Stok Birimi", "Para Birimi", "Bütçe Birim Fiyatları", "Departman"])
    for r in satirlar:
        ws.append(r)
    return _bytes(wb)


M1 = ["MLZ-1", "Kavanoz", "0008-Ambalaj Malzeme", "AD", "TL", 5.9, "S"]
M2 = ["MLZ-2", "Tuz", "0001-Hammadde", "KG", "USD", 2.5, "Z"]


def _gider_ws(ws, f=1, amb=(("Küçük", 100, 1000, 1),), mal_kabul=2):
    for a, v in GIDER_SAYILARI.items():
        ws[a] = v
    ws["D4"] = 1000 * f
    for a in ("D3", "D12", "D17", "D26", "D63", "D66"):
        ws[a] = "Gider Toplamı"
    ws["A69"] = "Ambalaj Cinsi"
    for r, ad in zip((7, 8)[:mal_kabul], ("Sınıf A", "Sınıf B")):
        ws[f"C{r}"], ws[f"G{r}"], ws[f"E{r}"] = ad, D_("0.5") if mal_kabul == 2 else 1, 100
    for r, ad in zip((21, 22), ("Sınıf A", "Sınıf B")):
        ws[f"C{r}"], ws[f"G{r}"], ws[f"E{r}"] = ad, D_("0.5"), 100
    for ilk in (30, 41, 52):
        ws[f"A{ilk}"], ws[f"G{ilk}"], ws[f"E{ilk}"] = "Hat 1", 1, 3600
    for i, (ad, h, u, k) in enumerate(amb):
        ws[f"A{70 + i}"], ws[f"B{70 + i}"], ws[f"C{70 + i}"], ws[f"D{70 + i}"] = ad, h, u, k


def _gider(tam=False, **kw) -> bytes:
    wb = Workbook(); ws = wb.active
    ws.title = "Gider Dağıtım"
    if tam:
        wb.create_sheet("Diğer")
    _gider_ws(ws, **kw)
    return _bytes(wb)


def _post(c, yol, icerik, sid, **alan):
    return c.post(f"{A}/{yol}", files={"dosya": ("d.xlsx", icerik)}, data={"senaryo": str(sid), **alan}, headers=H)


def _kap(oturum, sid):
    return {k.urun_kodu: k for k in oturum.scalars(select(m.UretimKapasitesi).where(m.UretimKapasitesi.senaryo_id == sid))}


def _kayitlar(oturum, tablo):
    return oturum.scalars(select(m.DegisiklikKaydi).where(m.DegisiklikKaydi.tablo == tablo).order_by(m.DegisiklikKaydi.id)).all()


# ---------------- üretim adetleri

def test_uretim_onizle_uygula_tek_sayfa_ve_tam_kitap(istemci, oturum):
    c = istemci; sid = _senaryo(c)
    for tam in (False, True):
        r = _post(c, "uretim-adetleri/onizle", _uretim([U1, U2], tam=tam), sid)
        assert r.status_code == 200, r.text
        g = r.json()
        assert [y["urun_kodu"] for y in g["yeni"]] == ["T-1", "T-2"] and g["degisen"] == [] and g["ayni"] == 0
        assert g["yeni"][0]["alanlar"]["hedef_uretim"] == "90" and g["yeni"][0]["urun_ad"] == "Ürün 1"
    assert _kap(oturum, sid) == {}   # önizleme yazmaz
    r = _post(c, "uretim-adetleri/uygula", _uretim([U1, U2]), sid, neden="ilk yükleme")
    assert r.status_code == 200, r.text
    assert r.json() == {"eklenen": 2, "guncellenen": 0, "uyarilar": []}
    k = _kap(oturum, sid)
    assert k["T-1"].hedef_uretim == D_(90) and k["T-1"].olusturan == "esma"
    kayit = _kayitlar(oturum, "uretim_kapasitesi")
    assert len(kayit) == 2 and kayit[0].yeni["_neden"] == "ilk yükleme"
    assert _post(c, "uretim-adetleri/uygula", _uretim([U1], tam=True), sid, neden="tam kitap").status_code == 200


def test_uretim_degisen_ayni_ve_tekrar(istemci, oturum):
    c = istemci; sid = _senaryo(c)
    assert _post(c, "uretim-adetleri/uygula", _uretim([U1, U2]), sid, neden="n").status_code == 200
    g = _post(c, "uretim-adetleri/onizle", _uretim([U1, U2]), sid).json()
    assert (g["yeni"], g["degisen"], g["ayni"]) == ([], [], 2)
    r = _post(c, "uretim-adetleri/uygula", _uretim([U1, U2]), sid, neden="n").json()
    assert (r["eklenen"], r["guncellenen"]) == (0, 0)
    assert len(_kayitlar(oturum, "uretim_kapasitesi")) == 2
    U1b = ["T-1", "Ürün 1", 100, 7, 120, 8, 95, 10]
    g = _post(c, "uretim-adetleri/onizle", _uretim([U1b, U2, U2]), sid).json()
    assert g["degisen"] == [{"urun_kodu": "T-1", "alan": "hedef_uretim", "eski": "90", "yeni": "95"}]
    assert g["ayni"] == 1 and len(g["uyarilar"]) == 1 and "T-2" in g["uyarilar"][0]
    r = _post(c, "uretim-adetleri/uygula", _uretim([U1b, U2]), sid, neden="revizyon")
    assert r.json() == {"eklenen": 0, "guncellenen": 1, "uyarilar": []}
    assert _kap(oturum, sid)["T-1"].hedef_uretim == D_(95)
    son = _kayitlar(oturum, "uretim_kapasitesi")[-1]
    assert son.islem == "guncelle" and son.eski["hedef_uretim"] == "90" and son.yeni["_neden"] == "revizyon"


def test_uretim_hatalar(istemci, oturum):
    c = istemci; sid = _senaryo(c)
    r = _post(c, "uretim-adetleri/onizle", _iki_sayfa_yanlis(), sid)
    assert r.status_code == 422 and "Üretim Adetleri sayfası bulunamadı" in r.json()["mesaj"]
    assert _post(c, "uretim-adetleri/onizle", _uretim([U1], baslik7="BAŞKA"), sid).status_code == 422
    assert _post(c, "uretim-adetleri/uygula", _uretim([U1], baslik7="BAŞKA"), sid, neden="x").status_code == 422
    assert _post(c, "uretim-adetleri/uygula", _uretim([U1]), sid, neden="  ").status_code == 422
    assert _post(c, "uretim-adetleri/onizle", _uretim([U1]), 9999).status_code == 404
    assert _kap(oturum, sid) == {}


# ---------------- satın alma BF

def _fiyatlar(oturum, sid):
    return oturum.scalars(select(m.MalzemeFiyati).where(m.MalzemeFiyati.senaryo_id == sid)).all()


def test_satin_alma_onizle_uygula_ve_tekrar(istemci, oturum):
    c = istemci; sid = _senaryo(c)
    for tam in (False, True):
        g = _post(c, "satin-alma/onizle", _satin([M1, M2], tam=tam), sid, gecerlilik_basi="2026-06-01").json()
        assert [x["kod"] for x in g["yeni_malzeme"]] == ["MLZ-1", "MLZ-2"] and g["hatali"] == []
        assert g["fiyat_yeni"][1] == {"kod": "MLZ-2", "yeni": "2.5", "para": "USD"}
    assert oturum.scalars(select(m.Malzeme)).all() == []
    r = _post(c, "satin-alma/uygula", _satin([M1, M2]), sid, gecerlilik_basi="2026-06-01", neden="bütçe")
    assert r.status_code == 200, r.text
    assert r.json()["malzeme_eklenen"] == 2 and r.json()["fiyat_yazilan"] == 2
    f = _fiyatlar(oturum, sid)
    assert {x.fiyat for x in f} == {D_("5.9"), D_("2.5")} and all(x.kaynak == "import" and x.neden == "bütçe" and x.olusturan == "esma" for x in f)
    g = _post(c, "satin-alma/onizle", _satin([M1, M2]), sid, gecerlilik_basi="2026-06-01").json()
    assert (g["yeni_malzeme"], g["fiyat_yeni"], g["fiyat_degisen"], g["kart_farki"], g["ayni"]) == ([], [], [], [], 2)
    r = _post(c, "satin-alma/uygula", _satin([M1, M2]), sid, gecerlilik_basi="2026-06-01", neden="bütçe").json()
    assert r["fiyat_yazilan"] == 0 and len(_fiyatlar(oturum, sid)) == 2


def test_satin_alma_fiyat_degisen_ve_kart_farki(istemci, oturum):
    c = istemci; sid = _senaryo(c)
    _post(c, "satin-alma/uygula", _satin([M1, M2]), sid, gecerlilik_basi="2026-06-01", neden="ilk")
    M1b = ["MLZ-1", "Kavanoz 370", "0008-Ambalaj Malzeme", "AD", "TL", 6.5, "S"]
    g = _post(c, "satin-alma/onizle", _satin([M1b, M2]), sid, gecerlilik_basi="2026-09-01").json()
    assert g["fiyat_degisen"] == [{"kod": "MLZ-1", "eski": "5.9", "yeni": "6.5", "para": "TL", "eski_para": "TL"}]
    assert g["kart_farki"] == [{"kod": "MLZ-1", "alanlar": ["ad"]}] and g["ayni"] == 1
    r = _post(c, "satin-alma/uygula", _satin([M1b, M2]), sid, gecerlilik_basi="2026-09-01", neden="zam").json()
    assert (r["fiyat_yazilan"], r["kart_guncellenen"]) == (1, 0)
    assert oturum.scalar(select(m.Malzeme.ad).where(m.Malzeme.kod == "MLZ-1")) == "Kavanoz"
    assert len(_fiyatlar(oturum, sid)) == 3   # append-only: eski kayıt duruyor
    r = _post(c, "satin-alma/uygula", _satin([M1b, M2]), sid, gecerlilik_basi="2026-09-01", neden="kart", kartlari_guncelle="true").json()
    assert r["kart_guncellenen"] == 1 and r["fiyat_yazilan"] == 0
    assert oturum.scalar(select(m.Malzeme.ad).where(m.Malzeme.kod == "MLZ-1")) == "Kavanoz 370"
    assert _kayitlar(oturum, "malzeme")


def test_satin_alma_hatali_satir_422_hicbir_sey_yazilmaz(istemci, oturum):
    c = istemci; sid = _senaryo(c)
    kotu = ["MLZ-3", "Bozuk", "x", "KG", "TL", "abc", "Z"]
    g = _post(c, "satin-alma/onizle", _satin([M1, kotu]), sid, gecerlilik_basi="2026-06-01").json()
    assert g["hatali"] == ["MLZ-3"] and [x["kod"] for x in g["yeni_malzeme"]] == ["MLZ-1"]
    r = _post(c, "satin-alma/uygula", _satin([M1, kotu]), sid, gecerlilik_basi="2026-06-01", neden="x")
    assert r.status_code == 422 and "MLZ-3" in r.json()["alanlar"]["hatali"]
    assert oturum.scalars(select(m.Malzeme)).all() == [] and _fiyatlar(oturum, sid) == []
    assert _post(c, "satin-alma/uygula", _satin([M1]), sid, neden="x").status_code == 422   # gecerlilik_basi zorunlu
    r = _post(c, "satin-alma/onizle", _iki_sayfa_yanlis(), sid)
    assert r.status_code == 422 and "S.ALMA BF sayfası bulunamadı" in r.json()["mesaj"]


# ---------------- gider dağıtım

def test_gider_onizle_uygula_ve_tekrar(istemci, oturum):
    c = istemci; sid = _senaryo(c)
    for tam in (False, True):
        r = _post(c, "gider-dagitim/onizle", _gider(tam=tam), sid)
        assert r.status_code == 200, r.text
        g = r.json()
        assert len(g["havuz"]) == 11
        assert g["ambalaj"] == {"eski_adet": 0, "yeni_adet": 1, "degisen": [{"ad": "Küçük", "alan": "sinif", "eski": None, "yeni": "eklendi"}]}
        assert g["havuz"][0]["kod"] == "dolum_iscilik" and g["havuz"][0]["eski_toplam"] is None and g["havuz"][0]["yeni_toplam"] == "1000"
    assert oturum.scalars(select(m.GiderHavuzu)).all() == []
    r = _post(c, "gider-dagitim/uygula", _gider(), sid, neden="ilk")
    assert r.status_code == 200, r.text
    assert r.json()["havuz"] == 11 and r.json()["ambalaj"] == 1
    assert len(oturum.scalars(select(m.GiderHavuzu)).all()) == 11
    g = _post(c, "gider-dagitim/onizle", _gider(), sid).json()
    assert not any(h["degisti"] for h in g["havuz"]) and g["ambalaj"]["degisen"] == []
    r = _post(c, "gider-dagitim/uygula", _gider(), sid, neden="tekrar").json()
    assert (r["havuz"], r["ambalaj"], r["havuz_kodlari"]) == (0, 0, [])
    yeni = dict(f=2, amb=(("Küçük", 100, 2000, 1),))
    g = _post(c, "gider-dagitim/onizle", _gider(**yeni), sid).json()
    d = g["havuz"][0]
    assert (d["eski_toplam"], d["yeni_toplam"], d["degisti"], d["anahtar_farki"]) == ("1000", "2000", True, False)
    assert g["ambalaj"]["degisen"] == [{"ad": "Küçük", "alan": "uretim_adedi", "eski": "1000", "yeni": "2000"}]
    r = _post(c, "gider-dagitim/uygula", _gider(**yeni), sid, neden="revizyon").json()
    assert r["havuz"] == 1 and r["havuz_kodlari"] == ["dolum_iscilik"] and r["ambalaj"] == 1
    assert any(k.yeni.get("_neden") == "revizyon" for k in _kayitlar(oturum, "gider_havuzu"))
    assert _kayitlar(oturum, "ambalaj_sinifi")


def test_gider_anahtar_farki_ve_hatalar(istemci, oturum):
    c = istemci; sid = _senaryo(c)
    assert _post(c, "gider-dagitim/uygula", _gider(), sid, neden="ilk").status_code == 200
    wb = Workbook(); ws = wb.active; ws.title = "Gider Dağıtım"
    _gider_ws(ws, mal_kabul=1)   # mal kabul paylarından biri eksik: anahtar farkı
    g = _post(c, "gider-dagitim/onizle", _bytes(wb), sid).json()
    mk = next(h for h in g["havuz"] if h["kod"] == "mal_kabul_iscilik")
    assert mk["degisti"] is True and mk["anahtar_farki"] is True
    ws["D4"] = "abc"   # bozuk hücre: 422, hiçbir şey değişmez
    sayi = len(oturum.scalars(select(m.DegisiklikKaydi)).all())
    assert _post(c, "gider-dagitim/uygula", _bytes(wb), sid, neden="x").status_code == 422
    assert len(oturum.scalars(select(m.DegisiklikKaydi)).all()) == sayi
    ws["D4"] = 1000; ws["F4"] = 0   # baz 0 olan saniye havuzu: yazmadan önce 422
    assert _post(c, "gider-dagitim/uygula", _bytes(wb), sid, neden="x").status_code == 422
    assert oturum.scalar(select(m.GiderHavuzu.baz_miktar).where(m.GiderHavuzu.kod == "dolum_iscilik")) == D_(500)
    assert len(oturum.scalars(select(m.DegisiklikKaydi)).all()) == sayi
    r = _post(c, "gider-dagitim/onizle", _iki_sayfa_yanlis(), sid)
    assert r.status_code == 422 and "Gider Dağıtım sayfası bulunamadı" in r.json()["mesaj"]


# ---------------- yanlış tek sayfalık dosya (düzen doğrulaması)

def _yanlis_sayfa() -> bytes:
    wb = Workbook(); ws = wb.active
    ws.append(["Kod", "Ad", "Tip", "Birim", "Para", "Fiyat", "Z/S"])
    ws.append(["X-1", "Alakasız", "t", "AD", "TL", 3, "Z"])
    return _bytes(wb)


def test_yanlis_tek_sayfa_satin_alma_ve_gider_422_hicbir_sey_yazilmaz(istemci, oturum):
    c = istemci; sid = _senaryo(c)
    for yol, ek in (("satin-alma", {"gecerlilik_basi": "2026-06-01"}), ("gider-dagitim", {})):
        for asama in ("onizle", "uygula"):
            r = _post(c, f"{yol}/{asama}", _yanlis_sayfa(), sid, neden="x", **ek)
            assert r.status_code == 422 and "beklenen düzen değil" in r.json()["mesaj"], (yol, asama, r.text)
    # gider sayfasını satın almaya, satın alma sayfasını gider/üretime yüklemek de reddedilir
    assert _post(c, "satin-alma/onizle", _gider(), sid).status_code == 422
    assert _post(c, "gider-dagitim/onizle", _satin([M1]), sid).status_code == 422
    # tüm toplamları 0 olan (etiketleri doğru) gider sayfası reddedilir
    wb = Workbook(); ws = wb.active
    for a in ("D3", "D12", "D17", "D26", "D63", "D66"):
        ws[a] = "Gider Toplamı"
    ws["A69"] = "Ambalaj Cinsi"
    assert _post(c, "gider-dagitim/uygula", _bytes(wb), sid, neden="x").status_code == 422
    assert oturum.scalars(select(m.Malzeme)).all() == [] and oturum.scalars(select(m.GiderHavuzu)).all() == []
    assert _fiyatlar(oturum, sid) == [] and oturum.scalars(select(m.AmbalajSinifi)).all() == []


# ---------------- B3: Excel'deki taban × çarpan formülü okunur

def test_taban_carpan_coz_kaliplari():
    from fiyat_motoru.excel_okuyucu import taban_carpan_coz
    assert taban_carpan_coz("=49024334.9667638*1.35*1.3") == (D_("49024334.9667638"), (D_("1.35"), D_("1.3")))
    assert taban_carpan_coz("=(10875000+3571433)*1.4*1.25") == (D_("14446433"), (D_("1.4"), D_("1.25")))
    assert taban_carpan_coz("=(11977200)*1.25*1.35*1.3") == (D_("11977200"), (D_("1.25"), D_("1.35"), D_("1.3")))
    assert taban_carpan_coz("=+ 35040000 * 1.4") == (D_("35040000"), (D_("1.4"),))
    for kalip_disi in (32065211.41, None, "=8400000", "=+D18+D24", "=+F4/3600", "=A1*1.3", "=100-5*2"):
        assert taban_carpan_coz(kalip_disi) is None


def test_excel_taban_carpan_eslesme_kurali():
    from backend.servisler.gider_servisi import excel_taban_carpan
    assert excel_taban_carpan(D_("1000"), None) == (D_("1000"), None, None)
    t, taban, c = excel_taban_carpan(D_("1300"), (D_("800"), (D_("1.25"), D_("1.3"))))
    assert (t, taban, c) == (D_("1300.000"), D_("800"), [("Excel çarpanı 1", D_("1.25")), ("Excel çarpanı 2", D_("1.3"))])
    assert excel_taban_carpan(D_("1300.5"), (D_("800"), (D_("1.25"), D_("1.3")))) == (D_("1300.5"), None, None)   # kuruşu tutmuyor
    assert excel_taban_carpan(D_("0"), (D_("800"), (D_("0"),))) == (D_("0"), None, None)                         # 0 çarpan


def test_gider_yeniden_yukleme_taban_ve_carpanlari_yazar(istemci, oturum, monkeypatch):
    """Excel'de D4 '=800*1.25*1' gibi formülse havuz taban + çarpanlarla yazılır; aynı dosya tekrar yüklenince değişiklik yok;
    önceden toplamla (çarpansız) yazılmış havuz, aynı toplam olsa da çarpanları almak için 'değişti' sayılır."""
    from backend.servisler import aktarim_servisi
    c = istemci; sid = _senaryo(c)
    assert _post(c, "gider-dagitim/uygula", _gider(), sid, neden="ilk").status_code == 200   # D4 = 1000, formülsüz
    monkeypatch.setattr(aktarim_servisi, "_gider_formulleri", lambda *_: {"dolum_iscilik_toplam": (D_("800"), (D_("1.25"), D_("1")))})
    g = _post(c, "gider-dagitim/onizle", _gider(), sid).json()
    d = g["havuz"][0]
    assert (d["kod"], d["degisti"], d["yeni_taban"], d["yeni_carpanlar"]) == ("dolum_iscilik", True, "800", ["1.25", "1"])
    assert [h["kod"] for h in g["havuz"] if h["degisti"]] == ["dolum_iscilik"]
    r = _post(c, "gider-dagitim/uygula", _gider(), sid, neden="çarpanlar").json()
    assert r["havuz_kodlari"] == ["dolum_iscilik"]
    h = oturum.scalar(select(m.GiderHavuzu).where(m.GiderHavuzu.senaryo_id == sid, m.GiderHavuzu.kod == "dolum_iscilik"))
    oturum.refresh(h)
    assert (h.taban_tutar, h.toplam_tutar) == (D_("800"), D_("1000"))
    assert h.carpanlar == [{"ad": "Excel çarpanı 1", "deger": "1.25"}, {"ad": "Excel çarpanı 2", "deger": "1"}]
    g = _post(c, "gider-dagitim/onizle", _gider(), sid).json()
    assert not any(x["degisti"] for x in g["havuz"])   # aynı dosya: değişiklik yok
