"""Excel yükleme güvenliği (Fiyat Çalışması yüklemeleri + ortak şablon / sorunlu satır uçları).

Veriler bellekte üretilen uydurma kitaplardır; gerçek şirket Excel'i okunmaz.
"""
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook, load_workbook

from backend.servisler import kimlik_servisi as ks
from backend.servisler.excel_ortak import SABLONLAR, sablon_kimligi_yaz
from tests.backend.test_api import _senaryo, istemci  # noqa: F401

API = "/api/v1"
H = {"X-Kullanici": "esma"}


def _bytes(wb) -> bytes:
    b = BytesIO()
    wb.save(b)
    return b.getvalue()


def _kimlikli(wb, kimlik: str) -> Workbook:
    sablon_kimligi_yaz(wb, kimlik)
    return wb


# ---------------------------------------------------------------- ortak: şablon indirme, sorunlu satırlar

def test_sablon_indirme_16_kimlik_200_bilinmeyen_404(istemci):
    assert len(SABLONLAR) == 16
    for kimlik in SABLONLAR:
        r = istemci.get(f"{API}/sablonlar/{kimlik}.xlsx")
        assert r.status_code == 200, (kimlik, r.text)
        assert r.headers["content-type"].startswith("application/vnd.openxmlformats")
        wb = load_workbook(BytesIO(r.content))
        assert wb["_sablon"]["A1"].value == kimlik            # gizli kimlik sayfası
        assert wb["_sablon"].sheet_state == "hidden"
        assert wb.sheetnames[0] != "_sablon"                  # ilk sayfa doldurulacak sayfa
    r = istemci.get(f"{API}/sablonlar/olmayan.xlsx")
    assert r.status_code == 404 and r.json()["kod"] == "sablon_yok"


def test_sorunlu_satirlar_xlsx(istemci):
    govde = {"baslik": "Fiyat listesi sorunlu satırlar",
             "satirlar": [{"satir": 5, "kod": "M-1", "alan": "Bütçe Birim Fiyatları", "deger": "abc", "neden": "sayıya çevrilemedi"},
                          {"neden": "başlık yok"}]}
    r = istemci.post(f"{API}/sablonlar/sorunlu-satirlar.xlsx", json=govde)
    assert r.status_code == 200, r.text
    ws = load_workbook(BytesIO(r.content)).active
    assert ws["A1"].value == "Fiyat listesi sorunlu satırlar"
    assert [c.value for c in ws[3]] == ["Satır", "Kod", "Alan", "Değer", "Neden"]
    assert [c.value for c in ws[4]] == [5, "M-1", "Bütçe Birim Fiyatları", "abc", "sayıya çevrilemedi"]
    assert ws["E5"].value == "başlık yok"


def test_sorunlu_satirlar_her_rol_kullanabilir_ve_sablon_giris_ister():
    assert ks.yazabilir_mi("izleyici", "POST", "/api/v1/sablonlar/sorunlu-satirlar.xlsx")
    assert ks.yazabilir_mi("satin_alma", "POST", "/api/v1/sablonlar/sorunlu-satirlar.xlsx")


def test_sablon_giris_zorunluysa_401(oturum):
    from backend.depo.veritabani import oturum_ver
    from backend.uygulama import uygulama_olustur
    app = uygulama_olustur(giris_zorunlu=True)
    app.dependency_overrides[oturum_ver] = lambda: oturum
    assert TestClient(app).get(f"{API}/sablonlar/uretim_adetleri.xlsx").status_code == 401


# ---------------------------------------------------------------- yardımcılar (uydurma veri)
import sys  # noqa: E402
from datetime import date  # noqa: E402
from decimal import Decimal as D_  # noqa: E402
from pathlib import Path  # noqa: E402

from sqlalchemy import select  # noqa: E402

from backend.depo import modeller as m  # noqa: E402
from backend.servisler import fiyat_servisi  # noqa: E402

URUN = {"ad": "Test Turşu 370 ml", "ambalaj_hacmi": "370", "hat": "Hat 1", "taze_tursu_sinifi": "Sınıf A", "suzme_kg": "0.2"}


def _kitap(basliklar, satirlar, ad="Sayfa1", kimlik=None, ust=None) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = ad
    if ust:
        ws.append(ust)
    ws.append(basliklar)
    for r in satirlar:
        ws.append(r)
    if kimlik:
        sablon_kimligi_yaz(wb, kimlik)
    return _bytes(wb)


def _yolla(c, yol, icerik, ad="d.xlsx", **alan):
    return c.post(f"{API}/{yol}", files={"dosya": (ad, icerik)}, data={k: str(v) for k, v in alan.items()}, headers=H)


def _malzeme(c, oturum, sid, kod, fiyat, kaynak="import", para="TL"):
    c.post(f"{API}/malzemeler", json={"kod": kod, "ad": kod, "tip": "t", "birim": "KG", "para_birimi": para, "zs": "S"}, headers=H)
    fiyat_servisi.fiyat_ekle(oturum, sid, kod, D_(fiyat), date(2026, 6, 1), "tohum", kaynak=kaynak)
    oturum.flush()


def _gecerli(oturum, sid, kod):
    return fiyat_servisi.gecerli_fiyatlar(oturum, sid, date(2026, 12, 1))[kod].fiyat


def _urun(c, kod, ad="Test Turşu 370 ml"):
    assert c.put(f"{API}/urunler/{kod}", json={**URUN, "ad": ad}, headers=H).status_code == 200


# ---------------------------------------------------------------- fiyat listesi (Malzeme Fiyatları › Fiyat listesi yükle)
FL = "import/fiyat-listesi"


@pytest.mark.parametrize("basliklar", [
    ["MALZEME", "AÇIKLAMA", "TİP", "BİRİM", "PARA BİRİMİ", "BÜTÇE BİRİM FİYATLARI"],
    ["  Malzeme  Kodu ", "Fiyat"],
    ["Stok Kodu", "x", "Birim Fiyat"],
    ["malzeme (sınıf) kodu", "bütçe birim fiyatı"],
])
def test_fiyat_listesi_baslik_varyasyonlari(istemci, oturum, basliklar):
    sid = _senaryo(istemci)
    _malzeme(istemci, oturum, sid, "M-1", "5")
    satir = ["M-1"] + [None] * (len(basliklar) - 2) + [6]
    r = _yolla(istemci, FL, _kitap(basliklar, [satir]), senaryo=sid, gecerlilik_basi="2026-10-01")
    assert r.status_code == 200, r.text
    assert r.json()["degisen"] == [{"kod": "M-1", "eski": "5", "yeni": "6"}]
    assert r.json()["ozet"]["okunan"] == 1 and r.json()["ozet"]["degisen"] == 1


def test_fiyat_listesi_yanlis_sablon_eksik_sutun_bos_dosya(istemci, oturum):
    sid = _senaryo(istemci)
    _malzeme(istemci, oturum, sid, "M-1", "5")
    r = _yolla(istemci, FL, _kitap(["Malzeme", "Fiyat"], [["M-1", 6]], kimlik="uretim_adetleri"), senaryo=sid)
    assert r.status_code == 422 and r.json()["kod"] == "yanlis_sablon" and "üretim adetleri şablonu" in r.json()["mesaj"]
    r = _yolla(istemci, FL, _kitap(["Malzeme", "Açıklama"], [["M-1", "x"]]), senaryo=sid)
    assert r.status_code == 422 and r.json()["kod"] == "eksik_sutun" and "Bütçe Birim Fiyatları" in r.json()["mesaj"]
    r = _yolla(istemci, FL + "/uygula", _kitap(["Malzeme", "Fiyat"], []), senaryo=sid, gecerlilik_basi="2026-10-01", neden="x")
    assert r.status_code == 422 and r.json()["kod"] == "bos_dosya"
    assert _gecerli(oturum, sid, "M-1") == D_(5)   # veri değişmedi
    r = _yolla(istemci, FL, b"a;b\n1;2", ad="liste.csv", senaryo=sid)
    assert r.status_code == 422 and r.json()["kod"] == "desteklenmeyen_dosya"


def test_fiyat_listesi_metin_sayi_ve_bozuk_sayi(istemci, oturum):
    sid = _senaryo(istemci)
    for k in ("M-1", "M-2"):
        _malzeme(istemci, oturum, sid, k, "5")
    icerik = _kitap(["Malzeme", "Fiyat"], [["M-1", "6,50"], ["M-2", "abc"]])
    g = _yolla(istemci, FL, icerik, senaryo=sid, gecerlilik_basi="2026-10-01").json()
    assert g["degisen"] == [{"kod": "M-1", "eski": "5", "yeni": "6.50"}] and g["hatali"] == ["M-2"]
    s = g["ozet"]["sorunlu"][0]
    assert s["satir"] == 3 and s["kod"] == "M-2" and s["deger"] == "abc"
    r = _yolla(istemci, FL + "/uygula", icerik, senaryo=sid, gecerlilik_basi="2026-10-01", neden="zam")
    assert r.status_code == 200 and r.json()["kodlar"] == ["M-1"]
    assert _gecerli(oturum, sid, "M-1") == D_("6.5") and _gecerli(oturum, sid, "M-2") == D_(5)   # bozuk satır 0 yazılmadı


def test_fiyat_listesi_elle_fiyat_korunur_buyuk_degisim_uyarisi(istemci, oturum):
    sid = _senaryo(istemci)
    _malzeme(istemci, oturum, sid, "M-1", "5", kaynak="elle")
    _malzeme(istemci, oturum, sid, "M-2", "10")
    icerik = _kitap(["Malzeme", "Fiyat"], [["M-1", 6], ["M-2", 20]])
    g = _yolla(istemci, FL, icerik, senaryo=sid, gecerlilik_basi="2026-10-01").json()
    assert [x["kod"] for x in g["elle"]] == ["M-1"] and [x["kod"] for x in g["degisen"]] == ["M-2"]
    assert sorted(x["kod"] for x in g["buyuk_degisim"]) == ["M-1", "M-2"]
    assert any("M-2" in u and "%100" in u for u in g["ozet"]["uyarilar"])
    r = _yolla(istemci, FL + "/uygula", icerik, senaryo=sid, gecerlilik_basi="2026-10-01", neden="x").json()
    assert r["kodlar"] == ["M-2"] and r["korunan_elle"] == 1 and _gecerli(oturum, sid, "M-1") == D_(5)
    r = _yolla(istemci, FL + "/uygula", icerik, senaryo=sid, gecerlilik_basi="2026-10-01", neden="x", elle_ustune_yaz="true").json()
    assert r["kodlar"] == ["M-1"] and _gecerli(oturum, sid, "M-1") == D_(6)


def test_fiyat_listesi_geri_al_birebir_ikinci_404(istemci, oturum):
    sid = _senaryo(istemci)
    _malzeme(istemci, oturum, sid, "M-1", "5")
    once = {k.id for k in oturum.scalars(select(m.MalzemeFiyati))}
    assert istemci.get(f"{API}/{FL}/son-yukleme?senaryo={sid}").json() == {"son": None}
    icerik = _kitap(["Malzeme", "Fiyat", "x", "y", "z", "q", "w", "e", "Revize"], [["M-1", 6, None, None, None, None, None, None, 7]])
    r = _yolla(istemci, FL + "/uygula", icerik, ad="liste.xlsx", senaryo=sid, gecerlilik_basi="2026-10-01", neden="x")
    assert r.status_code == 200, r.text
    assert _gecerli(oturum, sid, "M-1") == D_(7)
    son = istemci.get(f"{API}/{FL}/son-yukleme?senaryo={sid}").json()["son"]
    assert son["olusturan"] == "esma" and son["kaynak_dosya"] == "liste.xlsx"
    r = istemci.post(f"{API}/{FL}/son-yuklemeyi-geri-al?senaryo={sid}", headers=H)
    assert r.status_code == 200, r.text
    assert {k.id for k in oturum.scalars(select(m.MalzemeFiyati))} == once and _gecerli(oturum, sid, "M-1") == D_(5)
    assert oturum.scalar(select(m.DegisiklikKaydi).where(m.DegisiklikKaydi.islem == "geri_al", m.DegisiklikKaydi.tablo == "yukleme_yedegi"))
    r = istemci.post(f"{API}/{FL}/son-yuklemeyi-geri-al?senaryo={sid}", headers=H)
    assert r.status_code == 404 and r.json()["kod"] == "yedek_yok"


def test_geri_al_kilitli_senaryoda_409(istemci, oturum):
    sid = _senaryo(istemci)
    _malzeme(istemci, oturum, sid, "M-1", "5")
    _yolla(istemci, FL + "/uygula", _kitap(["Malzeme", "Fiyat"], [["M-1", 6]]), senaryo=sid, gecerlilik_basi="2026-10-01", neden="x")
    oturum.get(m.Senaryo, sid).kilitli = True
    oturum.flush()
    assert istemci.post(f"{API}/{FL}/son-yuklemeyi-geri-al?senaryo={sid}", headers=H).status_code == 409


# ---------------------------------------------------------------- satın alma (Veri Aktar)
SA = "aktarim/satin-alma"


def test_satin_alma_esnek_baslik_ve_geri_al(istemci, oturum):
    sid = _senaryo(istemci)
    icerik = _kitap(["STOK KODU", "MALZEME ADI", "BİRİM", "DÖVİZ", "BİRİM FİYAT", "Z/S"], [["Y-1", "Yeni Tuz", "KG", "tl", "4,20", "s"]])
    g = _yolla(istemci, SA + "/onizle", icerik, senaryo=sid).json()
    assert g["yeni_malzeme"] == [{"kod": "Y-1", "ad": "Yeni Tuz", "tip": None, "birim": "KG", "para_birimi": "TL", "zs": "S"}]
    assert g["fiyat_yeni"] == [{"kod": "Y-1", "yeni": "4.20", "para": "TL"}]
    r = _yolla(istemci, SA + "/uygula", icerik, senaryo=sid, gecerlilik_basi="2026-06-01", neden="ilk")
    assert r.status_code == 200 and r.json()["malzeme_eklenen"] == 1
    assert istemci.post(f"{API}/{SA}/son-yuklemeyi-geri-al?senaryo={sid}", headers=H).status_code == 200
    assert oturum.scalar(select(m.Malzeme).where(m.Malzeme.kod == "Y-1")) is None   # açılan kart kaldırıldı
    assert oturum.scalar(select(m.MalzemeFiyati)) is None


def test_satin_alma_rolu_uygulayabilir_403_duzeldi():
    for yol in ("/api/v1/aktarim/satin-alma/uygula", "/api/v1/aktarim/satin-alma/son-yuklemeyi-geri-al",
                "/api/v1/import/fiyat-listesi/uygula", "/api/v1/import/fiyat-listesi/son-yuklemeyi-geri-al"):
        assert ks.yazabilir_mi("satin_alma", "POST", yol), yol
    assert not ks.yazabilir_mi("satin_alma", "POST", "/api/v1/aktarim/gider-dagitim/uygula")


def test_satin_alma_rolu_api_ile(oturum):
    from backend.depo.veritabani import oturum_ver
    from backend.tohum import parametreleri_tohumla
    from backend.uygulama import uygulama_olustur
    app = uygulama_olustur(giris_zorunlu=True)
    app.dependency_overrides[oturum_ver] = lambda: oturum
    parametreleri_tohumla(oturum)
    ks.kullanici_olustur(oturum, "alim", "Alım", "satin_alma", "gecici-sifre", sifre_degismeli=False)
    sz = m.Sezon(ad="2026-2027", baslangic=date(2026, 6, 1), bitis=date(2027, 5, 31)); oturum.add(sz); oturum.flush()
    sen = m.Senaryo(sezon_id=sz.id, tur="fiyat_calismasi", ad="A"); oturum.add(sen); oturum.flush()
    c = TestClient(app)
    assert c.post(f"{API}/kimlik/giris", json={"kullanici_adi": "alim", "sifre": "gecici-sifre"}).status_code == 200
    icerik = _kitap(["Malzeme", "Açıklama", "Para Birimi", "Fiyat"], [["Y-1", "Tuz", "TL", 4]])
    r = c.post(f"{API}/{SA}/uygula", files={"dosya": ("d.xlsx", icerik)},
               data={"senaryo": str(sen.id), "gecerlilik_basi": "2026-06-01", "neden": "x"})
    assert r.status_code == 200, r.text


# ---------------------------------------------------------------- üretim adetleri
UA = "aktarim/uretim-adetleri"


def test_uretim_adetleri_kucuk_harf_noktasiz_i_ve_esanlam(istemci, oturum):
    sid = _senaryo(istemci)
    for basliklar in (["Ürün kodu", "Ürün adı", "Hedef vardiyalık üretim", "İşçi sayısı"],
                      ["URUN KODU", "URUN ADI", "HEDEF VARDIYALIK URETIM", "ISCI SAYISI"],
                      ["  stok kodu ", "ad", "hedef üretim"]):
        r = _yolla(istemci, UA + "/onizle", _kitap(basliklar, [["U-1", "Ürün", "1.200,5", 12][:len(basliklar)]]), senaryo=sid)
        assert r.status_code == 200, (basliklar, r.text)
        assert r.json()["yeni"][0]["alanlar"]["hedef_uretim"] == "1200.5"


def test_uretim_adetleri_bozuk_sayi_sorunlu_yazilmaz_ve_geri_al(istemci, oturum):
    sid = _senaryo(istemci)
    b = ["Ürün Kodu", "Ürün Adı", "Hedef Vardiyalık Üretim"]
    assert _yolla(istemci, UA + "/uygula", _kitap(b, [["U-1", "A", 90]]), senaryo=sid, neden="ilk").status_code == 200
    icerik = _kitap(b, [["U-1", "A", 95], ["U-2", "B", "#DIV/0!"]])
    g = _yolla(istemci, UA + "/onizle", icerik, senaryo=sid).json()
    assert g["ozet"]["sorunlu"][0]["kod"] == "U-2" and g["ozet"]["okunan"] == 2 and g["ozet"]["degisen"] == 1
    assert _yolla(istemci, UA + "/uygula", icerik, senaryo=sid, neden="rev").status_code == 200
    kap = {k.urun_kodu: k for k in oturum.scalars(select(m.UretimKapasitesi).where(m.UretimKapasitesi.senaryo_id == sid))}
    assert set(kap) == {"U-1"} and kap["U-1"].hedef_uretim == D_(95)   # U-2 yazılmadı (0 da yazılmadı)
    assert istemci.post(f"{API}/{UA}/son-yuklemeyi-geri-al?senaryo={sid}", headers=H).status_code == 200
    oturum.expire_all()
    assert oturum.scalar(select(m.UretimKapasitesi.hedef_uretim).where(m.UretimKapasitesi.urun_kodu == "U-1")) == D_(90)
    assert istemci.post(f"{API}/{UA}/son-yuklemeyi-geri-al?senaryo={sid}", headers=H).status_code == 200   # ilk yükleme
    assert oturum.scalar(select(m.UretimKapasitesi)) is None
    assert istemci.post(f"{API}/{UA}/son-yuklemeyi-geri-al?senaryo={sid}", headers=H).status_code == 404


def test_uretim_adetleri_bos_ve_yanlis_sablon(istemci, oturum):
    sid = _senaryo(istemci)
    b = ["Ürün Kodu", "Hedef Vardiyalık Üretim"]
    r = _yolla(istemci, UA + "/uygula", _kitap(b, []), senaryo=sid, neden="x")
    assert r.status_code == 422 and r.json()["kod"] == "bos_dosya"
    r = _yolla(istemci, UA + "/onizle", _kitap(b, [["U", 1]], kimlik="gider_dagitim"), senaryo=sid)
    assert r.json()["kod"] == "yanlis_sablon"


# ---------------------------------------------------------------- gider dağıtım: ambalaj tablosu değişir → satır kaybı onayı
from tests.backend.test_faz5_aktarim import _gider  # noqa: E402

GD = "aktarim/gider-dagitim"
DORT = (("A", 100, 1000, 1), ("B", 200, 1000, 1), ("C", 300, 1000, 1), ("D", 400, 1000, 1))


def test_gider_satir_kaybi_409_onayla_ve_geri_al(istemci, oturum):
    sid = _senaryo(istemci)
    assert _yolla(istemci, GD + "/uygula", _gider(amb=DORT), senaryo=sid, neden="ilk").status_code == 200
    tek = _gider(f=2, amb=(("A", 100, 1000, 1),))
    g = _yolla(istemci, GD + "/onizle", tek, senaryo=sid).json()
    assert g["ozet"]["silinecek"] == 3
    r = _yolla(istemci, GD + "/uygula", tek, senaryo=sid, neden="x")
    assert r.status_code == 409 and r.json()["kod"] == "satir_kaybi_onayi" and r.json()["alanlar"]["silinecek"] == 3
    assert len(list(oturum.scalars(select(m.AmbalajSinifi)))) == 4   # onaysız hiçbir şey yazılmadı
    assert _yolla(istemci, GD + "/uygula", tek, senaryo=sid, neden="x", onay="true").status_code == 200
    assert len(list(oturum.scalars(select(m.AmbalajSinifi)))) == 1
    assert istemci.post(f"{API}/{GD}/son-yuklemeyi-geri-al?senaryo={sid}", headers=H).status_code == 200
    assert sorted(a.ad for a in oturum.scalars(select(m.AmbalajSinifi))) == ["A", "B", "C", "D"]
    h = oturum.scalar(select(m.GiderHavuzu).where(m.GiderHavuzu.kod == "dolum_iscilik"))
    assert h.toplam_tutar == D_(1000)


def test_gider_metin_sayi_cevrilir_bozuk_sorunlu(istemci, oturum):
    from openpyxl import load_workbook
    sid = _senaryo(istemci)
    wb = load_workbook(BytesIO(_gider()))
    wb.active["D4"] = "1.500,00"
    wb.active["D13"] = "yok"
    g = _yolla(istemci, GD + "/onizle", _bytes(wb), senaryo=sid).json()
    assert [x["alan"] for x in g["ozet"]["sorunlu"]] == ["D13"]
    assert next(h for h in g["havuz"] if h["kod"] == "dolum_iscilik")["yeni_toplam"] == "1500.00"
    r = _yolla(istemci, GD + "/uygula", _bytes(wb), senaryo=sid, neden="x")
    assert r.status_code == 422 and r.json()["kod"] == "sorunlu_hucre"


# ---------------------------------------------------------------- ürün reçetesi
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "sablonlar"))
import uret  # noqa: E402

RA = "aktarim/recete"


def test_recete_bos_fiyat_elle_sayilmaz_ve_geri_al(istemci, oturum):
    sid = _senaryo(istemci)
    wb = uret.kitap(uret.RECETE, dolu=True)
    for ad in ("S.ALMA BF", "Örnek", "Açıklama", "_sablon"):
        del wb[ad]            # yalnız ürün sayfası: eskiden boş M hücreleri 'elle fiyat 0' sayılıyordu
    icerik = _bytes(wb)
    g = _yolla(istemci, RA + "/onizle", icerik, senaryo=sid).json()
    s = g["sayfalar"][0]
    assert s["elle_fiyat"] == 1 and s["durum"] == "yeni_urun"   # yalnız M'si dolu kapak satırı
    r = _yolla(istemci, RA + "/uygula", icerik, senaryo=sid, neden="x", sayfalar="001")
    assert r.status_code == 200, r.text
    sat = oturum.scalars(select(m.ReceteSatiri)).all()
    assert sum(1 for x in sat if x.birim_fiyat_elle is not None) == 1
    assert istemci.post(f"{API}/{RA}/son-yuklemeyi-geri-al?senaryo={sid}", headers=H).status_code == 200
    assert oturum.scalar(select(m.Recete)) is None and oturum.scalar(select(m.Urun).where(m.Urun.kod == uret.URUN1[0])) is None


def test_recete_yanlis_sablon(istemci, oturum):
    sid = _senaryo(istemci)
    r = _yolla(istemci, RA + "/onizle", _kitap(["a"], [["b"]], kimlik="satis_gecmisi"), senaryo=sid)
    assert r.status_code == 422 and r.json()["kod"] == "yanlis_sablon"


# ---------------------------------------------------------------- stokta kalan
SD = "aktarim/stok-devri"


def test_stok_devri_esnek_baslik_ve_geri_al(istemci, oturum):
    sid = _senaryo(istemci)
    _urun(istemci, "S-1")
    icerik = _kitap(["Ürün Kodu", "Stok Adedi", "Birim Maliyet"], [["S-1", "1.200,5", "10,5"]], ust=["Stokta kalan listesi"])
    g = _yolla(istemci, SD + "/onizle", icerik, senaryo=sid).json()
    assert g["yeni"] == 1 and g["satirlar"][0]["adet"] == "1200.5" and g["ozet"]["yeni"] == 1
    assert _yolla(istemci, SD + "/uygula", icerik, senaryo=sid, neden="x").status_code == 200
    assert oturum.scalar(select(m.StokDevri)) is not None
    assert istemci.post(f"{API}/{SD}/son-yuklemeyi-geri-al?senaryo={sid}", headers=H).status_code == 200
    assert oturum.scalar(select(m.StokDevri)) is None
    r = _yolla(istemci, SD + "/onizle", _kitap(["Ürün Kodu", "Stok Adedi"], [["S-1", 1]]), senaryo=sid)
    assert r.status_code == 422 and "stok_birim_maliyet" in r.json()["mesaj"]


# ---------------------------------------------------------------- satış geçmişi: ikilenme yok
def test_satis_gecmisi_esanlam_ikilenme_onizle_geri_al(istemci, oturum):
    _urun(istemci, "S-1")
    b = ["Ürün Kodu", "Müşteri", "Fatura Tarihi", "Birim Fiyat", "Döviz", "Miktar"]
    satir = ["S-1", "Test Market", "15.06.2025", "35,40", "TL", 100]
    icerik = _kitap(b, [satir, satir])
    r = _yolla(istemci, "satis-gecmisi/yukle", icerik)
    assert r.status_code == 200 and r.json()["eklenen"] == 2 and r.json()["atlanan_kayitli"] == 0
    g = _yolla(istemci, "satis-gecmisi/onizle", icerik).json()
    assert g["kayitli"] == 2 and g["eklenecek"] == 0 and "2 satır zaten kayıtlı" in g["ozet"]["uyarilar"][0]
    r = _yolla(istemci, "satis-gecmisi/yukle", icerik)
    assert r.json()["eklenen"] == 0 and r.json()["atlanan_kayitli"] == 2
    assert len(oturum.scalars(select(m.SatisGecmisi)).all()) == 2
    assert istemci.post(f"{API}/satis-gecmisi/son-yuklemeyi-geri-al", headers=H).status_code == 200
    assert oturum.scalar(select(m.SatisGecmisi)) is None
    r = _yolla(istemci, "satis-gecmisi/yukle", _kitap(b, [satir], kimlik="liste_fiyatlari"))
    assert r.status_code == 422 and r.json()["kod"] == "yanlis_sablon"


# ---------------------------------------------------------------- liste fiyatları
def test_liste_fiyatlari_onizle_ve_geri_al(istemci, oturum):
    _urun(istemci, "B-1", ad="Berrak Turşu 370 ml")
    b = ["Ürün Kodu", "Yıl", "Liste Fiyatı"]
    assert _yolla(istemci, "liste-fiyatlari/yukle", _kitap(b, [["B-1", 2025, "49,90"]])).status_code == 200
    icerik = _kitap(b, [["B-1", 2025, "54,90"], ["B-1", 2024, "39,90"]])
    g = _yolla(istemci, "liste-fiyatlari/onizle", icerik).json()
    assert (g["yeni"], g["degisen"], g["ayni"]) == (1, 1, 0)
    assert _yolla(istemci, "liste-fiyatlari/yukle", icerik).status_code == 200
    assert istemci.post(f"{API}/liste-fiyatlari/son-yuklemeyi-geri-al", headers=H).status_code == 200
    k = oturum.scalars(select(m.ListeFiyati)).all()
    assert [(x.yil, x.liste_fiyati) for x in k] == [(2025, D_("49.90"))]


# ---------------------------------------------------------------- tüm çalışma kitabı
def test_tam_kitap_eksik_sayfa_ve_yanlis_sablon(istemci, oturum):
    r = istemci.post(f"{API}/import/excel-tam", files={"dosya": ("d.xlsx", _kitap(["a"], [["b"]], ad="Gider dagitim"))},
                     data={"sezon_ad": "2026-2027", "senaryo_ad": "X"}, headers=H)
    assert r.status_code == 422 and r.json()["kod"] == "eksik_sayfa"
    assert "S.ALMA BF" in r.json()["mesaj"] and "Gider Dağıtım" not in r.json()["alanlar"]["eksik_sayfalar"]
    r = istemci.post(f"{API}/import/excel-tam", files={"dosya": ("d.xlsx", _kitap(["a"], [["b"]], kimlik="uretim_adetleri"))},
                     data={"sezon_ad": "2026-2027", "senaryo_ad": "X"}, headers=H)
    assert r.status_code == 422 and r.json()["kod"] == "yanlis_sablon"
