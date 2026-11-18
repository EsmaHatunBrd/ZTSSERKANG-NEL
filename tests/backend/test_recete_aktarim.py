"""Dosyadan reçete aktarımı (Veri Aktar → Ürün reçetesi): önizle (fark) → neden → uygula (yeni versiyon). Gerçek kitaptan yalnız
001, 001 (2), 035 ve S.ALMA BF sayfaları değer olarak küçük bir dosyaya alınır; şirket verisi test çıktısına yazılmaz (yalnız sayılar)."""
from io import BytesIO
import openpyxl
import pytest
from sqlalchemy import select
from backend.depo import modeller as m
from backend.servisler import recete_servisi as rs
from tests.backend.test_api import _senaryo, istemci  # noqa: F401

A = "/api/v1/aktarim/recete"
H = {"X-Kullanici": "esma"}
SAYFALAR = ("001", "001 (2)", "035", "S.ALMA BF")


@pytest.fixture(scope="module")
def kucuk_kitap(excel_yolu, tmp_path_factory) -> bytes:
    wb = openpyxl.load_workbook(excel_yolu, data_only=True)
    for ad in list(wb.sheetnames):
        if ad not in SAYFALAR:
            del wb[ad]
    yol = tmp_path_factory.mktemp("recete") / "kucuk.xlsx"
    wb.save(yol)
    return yol.read_bytes()


def _post(c, yol, icerik, sid, **alan):
    return c.post(f"{A}/{yol}", files={"dosya": ("r.xlsx", icerik)}, data={"senaryo": str(sid), **alan}, headers=H)


def _tek_sayfa(icerik: bytes, ad: str) -> bytes:
    wb = openpyxl.load_workbook(BytesIO(icerik))
    for x in list(wb.sheetnames):
        if x != ad:
            del wb[x]
    wb.active.title = "Sayfa1"   # kopyalanan tek sayfa: ad '001' değil
    b = BytesIO(); wb.save(b)
    return b.getvalue()


def test_onizle_yeni_urunler_varyant_secili_degil_hicbir_sey_yazmaz(istemci, oturum, kucuk_kitap):
    c = istemci; sid = _senaryo(c)
    r = _post(c, "onizle", kucuk_kitap, sid)
    assert r.status_code == 200, r.text
    g = {x["sayfa"]: x for x in r.json()["sayfalar"]}
    assert set(g) == {"001", "001 (2)", "035"} and r.json()["hatali"] == []
    assert g["001"]["durum"] == "yeni_urun" and g["001"]["secili"] is True and g["001"]["satir_sayisi"] > 0
    assert g["001 (2)"]["kod"] == g["001"]["kod"] and g["001 (2)"]["secili"] is False
    assert any("(2)" in u for u in g["001 (2)"]["uyarilar"])
    assert g["001 (2)"]["elle_fiyat"] > g["001"]["elle_fiyat"]   # varyantta ürün satırına elle 49,5 vb.
    assert oturum.scalars(select(m.Recete)).all() == [] and oturum.scalars(select(m.Urun)).all() == []


def test_uygula_yeni_urun_kart_hedef_recete_ve_gunluk_sonra_ayni(istemci, oturum, kucuk_kitap):
    c = istemci; sid = _senaryo(c)
    r = _post(c, "uygula", kucuk_kitap, sid, neden="dosyadan ilk reçete", sayfalar=["001", "035"])
    assert r.status_code == 200, r.text
    assert r.json()["yeni_urun"] == 2 and [x["versiyon"] for x in r.json()["uygulanan"]] == [1, 1]
    kod = r.json()["uygulanan"][0]["kod"]
    u = oturum.scalar(select(m.Urun).where(m.Urun.kod == kod))
    rec = rs.aktif_recete_veya_none(oturum, u.id, sid)
    assert rec.kaynak == "dosya" and any(x.seviye is not None for x in rec.satirlar)
    assert oturum.scalar(select(m.UretimHedefi).where(m.UretimHedefi.urun_id == u.id, m.UretimHedefi.senaryo_id == sid)) is not None
    k = oturum.scalar(select(m.DegisiklikKaydi).where(m.DegisiklikKaydi.tablo == "recete", m.DegisiklikKaydi.islem == "dosyadan_aktar"))
    assert k.yeni["_neden"] == "dosyadan ilk reçete" and k.kullanici == "esma"
    # Aynı dosya tekrar: 001 ve 035 'ayni' (seçili değil). Üretim bilgisi sayfadan açıldı: hesap 'hedef yok' demez
    # (bu test senaryosunda parametre değeri olmadığından 'parametre eksik' der).
    g = {x["sayfa"]: x for x in _post(c, "onizle", kucuk_kitap, sid).json()["sayfalar"]}
    assert (g["001"]["durum"], g["001"]["secili"], g["035"]["durum"]) == ("ayni", False, "ayni")
    h = c.post(f"/api/v1/urunler/{kod}/hesapla", json={"senaryo_id": sid})
    assert h.status_code == 422 and h.json()["kod"] == "parametre_eksik"


def test_varyant_uygulaninca_fark_ve_yeni_versiyon_eski_gecmiste(istemci, oturum, kucuk_kitap):
    c = istemci; sid = _senaryo(c)
    assert _post(c, "uygula", kucuk_kitap, sid, neden="ilk", sayfalar=["001"]).status_code == 200
    g = {x["sayfa"]: x for x in _post(c, "onizle", kucuk_kitap, sid).json()["sayfalar"]}
    v = g["001 (2)"]
    assert v["durum"] == "degisti" and v["degisen"] and all(x["alanlar"] for x in v["degisen"])
    r = _post(c, "uygula", kucuk_kitap, sid, neden="hazır alım varyantı", sayfalar=["001 (2)"])
    assert r.status_code == 200 and r.json()["uygulanan"][0]["versiyon"] == 2 and r.json()["yeni_urun"] == 0
    u = oturum.scalar(select(m.Urun).where(m.Urun.kod == v["kod"]))
    assert [x.versiyon for x in rs.versiyonlar(oturum, u.id, sid)] == [2, 1]
    assert [x.aktif for x in rs.versiyonlar(oturum, u.id, sid)] == [True, False]


def test_hatalar_kilit_neden_secim_tekrar_kod(istemci, oturum, kucuk_kitap):
    c = istemci; sid = _senaryo(c)
    assert _post(c, "uygula", kucuk_kitap, sid, neden="  ", sayfalar=["001"]).status_code == 422
    assert _post(c, "uygula", kucuk_kitap, sid, neden="x", sayfalar=["999"]).status_code == 422
    r = _post(c, "uygula", kucuk_kitap, sid, neden="x", sayfalar=["001", "001 (2)"])
    assert r.status_code == 422 and "Aynı ürün" in r.json()["mesaj"]
    assert oturum.scalars(select(m.Recete)).all() == []   # tek işlem: hiçbiri yazılmadı
    assert c.post(f"/api/v1/senaryolar/{sid}/kilitle", json={"neden": "kapandı"}, headers=H).status_code == 200
    r = _post(c, "uygula", kucuk_kitap, sid, neden="x", sayfalar=["001"])
    assert r.status_code == 409 and r.json()["hata"] == "kilitli"
    assert _post(c, "onizle", kucuk_kitap, sid).status_code == 200   # önizleme kilitte de çalışır (salt okuma)


def test_tek_sayfalik_kopya_ve_urun_sayfasi_olmayan_dosya(istemci, oturum, kucuk_kitap):
    c = istemci; sid = _senaryo(c)
    r = _post(c, "onizle", _tek_sayfa(kucuk_kitap, "035"), sid)
    assert r.status_code == 200 and [x["sayfa"] for x in r.json()["sayfalar"]] == ["Sayfa1"]
    assert any("S.ALMA BF yok" in u for u in r.json()["sayfalar"][0]["uyarilar"]) or r.json()["sayfalar"][0]["elle_fiyat"] == 0
    r = _post(c, "onizle", _tek_sayfa(kucuk_kitap, "S.ALMA BF"), sid)
    assert r.status_code == 200 and r.json()["sayfalar"] == [] and r.json()["hatali"][0]["sayfa"] == "Sayfa1"
    wb = openpyxl.Workbook(); wb.create_sheet("Diğer"); b = BytesIO(); wb.save(b)
    r = _post(c, "onizle", b.getvalue(), sid)
    assert r.status_code == 422 and "ürün sayfası" in r.json()["mesaj"]
    assert _post(c, "onizle", b"bozuk", sid).status_code == 422


def test_kodsuz_urun_sayfasi_gecici_kodla_eslenir(istemci, oturum, kucuk_kitap):
    """056-067 gibi D6'sı boş ürün sayfaları tam kitap aktarımındaki gibi 'SAYFA-<sayfa>' koduyla eşlenir; sayfa adı ürün sayfası
    biçiminde değilse (kopyalanıp adı değişmiş tek sayfa) okunamayan sayfa olur."""
    wb = openpyxl.load_workbook(BytesIO(kucuk_kitap))
    wb["035"]["D6"] = None
    b = BytesIO(); wb.save(b)
    c = istemci; sid = _senaryo(c)
    g = {x["sayfa"]: x for x in _post(c, "onizle", b.getvalue(), sid).json()["sayfalar"]}
    assert g["035"]["kod"] == "SAYFA-035" and g["035"]["durum"] == "yeni_urun" and any("geçici kod" in u for u in g["035"]["uyarilar"])
    r = _post(c, "uygula", b.getvalue(), sid, neden="geçici", sayfalar=["035"])
    assert r.status_code == 200 and r.json()["uygulanan"][0]["kod"] == "SAYFA-035"
    assert oturum.scalar(select(m.Urun).where(m.Urun.kod == "SAYFA-035")).gecici_kod is True
    r = _post(c, "onizle", _tek_sayfa(b.getvalue(), "035"), sid)
    assert r.json()["sayfalar"] == [] and "ürün kodu yok" in r.json()["hatali"][0]["mesaj"]
