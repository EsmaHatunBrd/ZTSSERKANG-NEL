"""Faz 5b G2: S.ALMA BF I sütunu (revize fiyat). F = ilk bütçe, I = sonradan güncelleme; ikisi aynı gün ayrı kayıt, geçerli olan I.
Fixture sentetik (şirket verisi yok); tam kitap testi yalnız proje Excel'i varsa koşar."""
from datetime import date
from decimal import Decimal as D_
from io import BytesIO
import pytest
from openpyxl import Workbook
from sqlalchemy import select
from backend.api.semalar import ImportOzeti
from backend.depo import modeller as m
from backend.servisler import fiyat_servisi as fs, import_servisi as ims
from tests.backend.test_api import _senaryo, istemci  # noqa: F401

A = "/api/v1/aktarim"
H = {"X-Kullanici": "esma"}
BASLIK = ["Malzeme", "Açıklama", "Malzeme Tipi", "Stok Birimi", "Para Birimi", "Bütçe Birim Fiyatları", "Departman", None, "Bütçe Birim Fiyatları"]


def _satin(satirlar, tam=False) -> bytes:
    wb = Workbook(); ws = wb.active
    if tam:
        ws.title = "Diğer"; ws = wb.create_sheet("S.ALMA BF")
    ws.append(BASLIK)
    for r in satirlar:
        ws.append(r)
    b = BytesIO(); wb.save(b)
    return b.getvalue()


# kod, ad, tip, birim, para, F, Z/S, (boş), I
KAV = ["KAV-1", "Kavanoz", "0008-Ambalaj Malzeme", "AD", "TL", 5.9, "S", None, 6.4]      # revize
TUZ = ["TUZ-1", "Tuz", "0001-Hammadde", "KG", "TL", 2.5, "S", None, None]                # I boş -> revize yok
KPK = ["KPK-1", "Kapak", "0008-Ambalaj Malzeme", "AD", "USD", 0.12, "Z", None, 0.12]      # I = F -> revize yok


def _post(c, yol, icerik, sid, **alan):
    return c.post(f"{A}/{yol}", files={"dosya": ("d.xlsx", icerik)}, data={"senaryo": str(sid), **alan}, headers=H)


def _kayitlar(oturum, sid, kod):
    return fs.gecmis(oturum, sid, kod)


def _senaryo_kur(oturum):
    sz = m.Sezon(ad="S", baslangic=date(2026, 6, 1), bitis=date(2027, 5, 31)); oturum.add(sz); oturum.flush()
    sen = m.Senaryo(sezon_id=sz.id, tur="fiyat_calismasi", ad="A"); oturum.add(sen); oturum.flush()
    return sen


# ---------------------------------------------------------------- fiyat_servisi: aynı gün iki kayıt

def test_ayni_gun_iki_kayitta_son_eklenen_gecerli(oturum):
    sen = _senaryo_kur(oturum)
    fs.malzeme_ekle_veya_guncelle(oturum, "A1", "A", None, "AD", "TL", "S")
    fs.fiyat_ekle(oturum, sen.id, "A1", D_("5"), date(2026, 6, 1), "ilk", kaynak="import")
    fs.fiyat_ekle(oturum, sen.id, "A1", D_("6"), date(2026, 6, 1), "revize", kaynak="import-revize")
    assert fs.gecerli_fiyatlar(oturum, sen.id, date(2026, 6, 1))["A1"].fiyat == D_("6")
    assert fs.gecerli_kayitlar_kodla(oturum, sen.id, date(2026, 9, 1))["A1"].kaynak == "import-revize"
    assert [k.fiyat for k in fs.gecmis(oturum, sen.id, "A1")] == [D_("6"), D_("5")]   # en yeni üstte


def test_ilk_kayitlar_senaryodaki_en_eski(oturum):
    sen = _senaryo_kur(oturum)
    fs.malzeme_ekle_veya_guncelle(oturum, "A1", "A", None, "AD", "TL", "S")
    fs.malzeme_ekle_veya_guncelle(oturum, "B1", "B", None, "AD", "TL", "S")
    fs.fiyat_ekle(oturum, sen.id, "A1", D_("7"), date(2026, 9, 1), "zam")          # sonra eklenen ama tarihçe ortası
    fs.fiyat_ekle(oturum, sen.id, "A1", D_("5"), date(2026, 6, 1), "ilk")
    fs.fiyat_ekle(oturum, sen.id, "A1", D_("6"), date(2026, 6, 1), "revize")
    ilk = fs.ilk_kayitlar_kodla(oturum, sen.id)
    assert ilk["A1"].fiyat == D_("5") and "B1" not in ilk


# ---------------------------------------------------------------- Veri Aktar -> satın alma

def test_onizleme_i_sutununu_revize_olarak_okur(istemci, oturum):
    c = istemci; sid = _senaryo(c)
    for tam in (False, True):
        g = _post(c, "satin-alma/onizle", _satin([KAV, TUZ, KPK], tam=tam), sid, gecerlilik_basi="2026-06-01").json()
        assert g["revize"] == [{"kod": "KAV-1", "ilk": "5.9", "revize": "6.4"}]
        assert g["revize_sayisi"] == 1
        # fiyat_yeni geçerli olacak fiyatı (revize) gösterir
        assert {x["kod"]: x["yeni"] for x in g["fiyat_yeni"]} == {"KAV-1": "6.4", "TUZ-1": "2.5", "KPK-1": "0.12"}


def test_uygula_iki_kayit_yazar_gecerli_revize(istemci, oturum):
    c = istemci; sid = _senaryo(c)
    r = _post(c, "satin-alma/uygula", _satin([KAV, TUZ, KPK]), sid, gecerlilik_basi="2026-06-01", neden="bütçe")
    assert r.status_code == 200, r.text
    assert r.json()["fiyat_yazilan"] == 3 and r.json()["revize_yazilan"] == 1
    kav = _kayitlar(oturum, sid, "KAV-1")
    assert [(k.fiyat, k.kaynak) for k in kav] == [(D_("6.4"), "import-revize"), (D_("5.9"), "import")]
    assert all(k.gecerlilik_basi == date(2026, 6, 1) and k.olusturan == "esma" for k in kav)
    assert "İlk bütçe (S.ALMA BF F)" in kav[1].neden and "Revize (S.ALMA BF I)" in kav[0].neden and "bütçe" in kav[0].neden
    assert len(_kayitlar(oturum, sid, "TUZ-1")) == 1 and _kayitlar(oturum, sid, "TUZ-1")[0].neden == "bütçe"
    assert len(_kayitlar(oturum, sid, "KPK-1")) == 1
    g = fs.gecerli_fiyatlar(oturum, sid, date(2026, 6, 1))
    assert g["KAV-1"].fiyat == D_("6.4")


def test_tekrar_yukleme_cift_kayit_uretmez(istemci, oturum):
    c = istemci; sid = _senaryo(c)
    _post(c, "satin-alma/uygula", _satin([KAV, TUZ, KPK]), sid, gecerlilik_basi="2026-06-01", neden="bütçe")
    g = _post(c, "satin-alma/onizle", _satin([KAV, TUZ, KPK]), sid, gecerlilik_basi="2026-06-01").json()
    assert (g["fiyat_yeni"], g["fiyat_degisen"], g["ayni"]) == ([], [], 3)
    assert g["revize"] == [{"kod": "KAV-1", "ilk": "5.9", "revize": "6.4"}]   # bilgi amaçlı; yazılmaz
    r = _post(c, "satin-alma/uygula", _satin([KAV, TUZ, KPK]), sid, gecerlilik_basi="2026-06-01", neden="bütçe").json()
    assert r["fiyat_yazilan"] == 0 and r["revize_yazilan"] == 0
    assert len(oturum.scalars(select(m.MalzemeFiyati).where(m.MalzemeFiyati.senaryo_id == sid)).all()) == 4


def test_mevcut_ilk_fiyat_varsa_yalniz_revize_yazilir(istemci, oturum):
    """Eski (yalnız F okunan) yüklemeden sonra aynı dosya I ile gelirse F yeniden yazılmaz, yalnız revize eklenir."""
    c = istemci; sid = _senaryo(c)
    KAV_ESKI = KAV[:8] + [None]
    _post(c, "satin-alma/uygula", _satin([KAV_ESKI]), sid, gecerlilik_basi="2026-06-01", neden="bütçe")
    g = _post(c, "satin-alma/onizle", _satin([KAV]), sid, gecerlilik_basi="2026-06-01").json()
    assert g["fiyat_degisen"] == [{"kod": "KAV-1", "eski": "5.9", "yeni": "6.4", "para": "TL", "eski_para": "TL"}]
    r = _post(c, "satin-alma/uygula", _satin([KAV]), sid, gecerlilik_basi="2026-06-01", neden="revize geldi").json()
    assert r["fiyat_yazilan"] == 1 and r["revize_yazilan"] == 1
    kav = _kayitlar(oturum, sid, "KAV-1")
    assert [(k.fiyat, k.kaynak) for k in kav] == [(D_("6.4"), "import-revize"), (D_("5.9"), "import")]


def test_ikinci_revize_turunda_f_yeniden_yazilmaz(istemci, oturum):
    """DB'de F=5.9 + I=6.4 varken dosya I=7.0 ile gelirse yalnız yeni revize eklenir; sahte 'İlk bütçe' satırı oluşmaz."""
    c = istemci; sid = _senaryo(c)
    _post(c, "satin-alma/uygula", _satin([KAV]), sid, gecerlilik_basi="2026-06-01", neden="bütçe")
    KAV2 = KAV[:8] + [7.0]
    r = _post(c, "satin-alma/uygula", _satin([KAV2]), sid, gecerlilik_basi="2026-09-01", neden="ikinci revize").json()
    assert r["fiyat_yazilan"] == 1 and r["revize_yazilan"] == 1
    kav = _kayitlar(oturum, sid, "KAV-1")
    assert [(k.fiyat, k.kaynak) for k in kav] == [(D_("7"), "import-revize"), (D_("6.4"), "import-revize"), (D_("5.9"), "import")]


def test_i_basligi_fiyat_degilse_yok_sayilir(istemci, oturum):
    c = istemci; sid = _senaryo(c)
    wb = Workbook(); ws = wb.active
    ws.append(BASLIK[:8] + ["Not"])
    ws.append(KAV)
    b = BytesIO(); wb.save(b)
    g = _post(c, "satin-alma/onizle", b.getvalue(), sid, gecerlilik_basi="2026-06-01").json()
    assert g["revize"] == [] and g["fiyat_yeni"] == [{"kod": "KAV-1", "yeni": "5.9", "para": "TL"}]


def test_f_sayi_metni_kabul_edilir(istemci, oturum):
    c = istemci; sid = _senaryo(c)
    g = _post(c, "satin-alma/onizle", _satin([["TUZ-1", "Tuz", "0001-Hammadde", "KG", "TL", "2.5", "S", None, None]]), sid, gecerlilik_basi="2026-06-01").json()
    assert g["hatali"] == [] and g["fiyat_yeni"] == [{"kod": "TUZ-1", "yeni": "2.5", "para": "TL"}]


def test_revize_hatali_ise_satir_hatali(istemci, oturum):
    c = istemci; sid = _senaryo(c)
    bozuk = KAV[:8] + ["abc"]
    g = _post(c, "satin-alma/onizle", _satin([bozuk, TUZ]), sid, gecerlilik_basi="2026-06-01").json()
    assert g["hatali"] == ["KAV-1"] and [x["kod"] for x in g["yeni_malzeme"]] == ["TUZ-1"]


# ---------------------------------------------------------------- malzeme listesi API

def test_malzeme_listesi_ilk_fiyat_ve_revize_suzgeci(istemci, oturum):
    c = istemci; sid = _senaryo(c)
    _post(c, "satin-alma/uygula", _satin([KAV, TUZ, KPK]), sid, gecerlilik_basi="2026-06-01", neden="bütçe")
    k = {x["kod"]: x for x in c.get(f"/api/v1/malzemeler?senaryo={sid}").json()["kayitlar"]}
    assert k["KAV-1"]["ilk_fiyat"] == "5.9" and k["KAV-1"]["fiyat"] == "6.4" and k["KAV-1"]["revize"] is True
    assert k["KAV-1"]["kaynak"] == "import-revize"
    assert k["TUZ-1"]["ilk_fiyat"] == "2.5" and k["TUZ-1"]["revize"] is False
    assert k["KPK-1"]["revize"] is False
    r = c.get(f"/api/v1/malzemeler?senaryo={sid}&revize=1").json()
    assert [x["kod"] for x in r["kayitlar"]] == ["KAV-1"] and r["toplam"] == 1
    # elle zam da "revize" sayılır (geçerli ≠ ilk)
    c.post(f"/api/v1/malzemeler/TUZ-1/fiyatlar?senaryo={sid}", json={"fiyat": "3", "gecerlilik_basi": "2026-09-01", "neden": "zam"}, headers=H)
    r = c.get(f"/api/v1/malzemeler?senaryo={sid}&revize=true").json()
    assert sorted(x["kod"] for x in r["kayitlar"]) == ["KAV-1", "TUZ-1"]
    # fiyat kaydı olmayan kartta ilk_fiyat null
    c.post("/api/v1/malzemeler", json={"kod": "YENI", "ad": "Yeni", "birim": "AD", "para_birimi": "TL", "zs": "S"}, headers=H)
    k = {x["kod"]: x for x in c.get(f"/api/v1/malzemeler?senaryo={sid}").json()["kayitlar"]}
    assert k["YENI"]["ilk_fiyat"] is None and k["YENI"]["revize"] is False


# ---------------------------------------------------------------- fiyat listesi (Malzeme Fiyatları -> Fiyat listesi yükle)

def test_fiyat_listesi_i_sutunu(oturum, tmp_path):
    sen = _senaryo_kur(oturum)
    fs.malzeme_ekle_veya_guncelle(oturum, "A1", "A", None, "AD", "TL", "S")
    fs.malzeme_ekle_veya_guncelle(oturum, "B1", "B", None, "AD", "TL", "S")
    wb = Workbook(); ws = wb.active
    ws.append(BASLIK)
    ws.append(["A1", "a", None, "AD", "TL", 5, "S", None, 6])     # revize
    ws.append(["B1", "b", None, "AD", "TL", 7, "S", None, None])  # düz
    dosya = tmp_path / "l.xlsx"; wb.save(dosya)
    on = ims.fiyat_listesi_onizle(oturum, sen.id, dosya, date(2026, 6, 1))
    assert {d["kod"]: d["yeni"] for d in on["degisen"]} == {"A1": "6", "B1": "7"}
    assert on["revize"] == [{"kod": "A1", "ilk": "5", "revize": "6"}]
    ims.fiyat_listesi_uygula(oturum, sen.id, dosya, date(2026, 6, 1), "liste", "esma")
    a = fs.gecmis(oturum, sen.id, "A1")
    assert [(k.fiyat, k.kaynak) for k in a] == [(D_("6"), "import-revize"), (D_("5"), "import")]
    assert fs.gecerli_fiyatlar(oturum, sen.id, date(2026, 6, 1))["A1"].fiyat == D_("6")
    assert ims.fiyat_listesi_onizle(oturum, sen.id, dosya, date(2026, 6, 1))["ayni"] == 2


# ---------------------------------------------------------------- tam kitap (proje Excel'i varsa)

@pytest.fixture(scope="module")
def tam_kitap(excel_yolu):
    from backend.depo.veritabani import Base, motor_olustur, oturum_fabrikasi
    engine = motor_olustur("sqlite://"); Base.metadata.create_all(engine)
    s = oturum_fabrikasi(engine)()
    ozet = ims.excel_tam_yukle(s, excel_yolu, "2026-2027", "Revize deneme")
    s.commit()
    yield s, ozet, excel_yolu
    s.close()


def test_tam_kitap_revize_kayitlari(tam_kitap):
    s, ozet, excel_yolu = tam_kitap
    revize = ims.revize_fiyatlarini_oku_dosyadan(excel_yolu)
    assert ozet["revize"] == len(revize) > 0
    assert ImportOzeti.model_validate(ozet).revize == ozet["revize"]   # API özeti sayacı geçirir (G3)
    kayitlar = s.scalars(select(m.MalzemeFiyati).where(m.MalzemeFiyati.senaryo_id == ozet["senaryo_id"], m.MalzemeFiyati.kaynak == "import-revize")).all()
    assert len(kayitlar) == len(revize)
    kod = next(iter(revize))
    g = fs.gecmis(s, ozet["senaryo_id"], kod)
    assert g[0].kaynak == "import-revize" and g[0].fiyat == revize[kod] and len(g) <= 2   # F boşsa tek kayıt
    assert all(x.gecerlilik_basi == g[0].gecerlilik_basi for x in g)
    assert fs.gecerli_fiyatlar(s, ozet["senaryo_id"], date(2026, 10, 21))[kod].fiyat == revize[kod]


def test_tam_kitap_revize_kapali_yalniz_f(excel_yolu):
    from backend.depo.veritabani import Base, motor_olustur, oturum_fabrikasi
    engine = motor_olustur("sqlite://"); Base.metadata.create_all(engine)
    s = oturum_fabrikasi(engine)()
    ozet = ims.excel_tam_yukle(s, excel_yolu, "2026-2027", "Yalnız F", revize_uygula=False)
    assert ozet["revize"] == 0
    assert s.scalar(select(m.MalzemeFiyati.id).where(m.MalzemeFiyati.kaynak == "import-revize")) is None
    s.close()


def test_import_ozeti_semasi_revize_sayaci():
    """G3: ImportOzeti `revize` alanını taşır; eski özetlerde (alan yoksa) 0 varsayılır."""
    alanlar = {"senaryo_id": 1, "malzeme": 0, "fiyat": 0, "havuz": 0, "ambalaj": 0, "urun": 0, "recete": 0, "parametre": 0, "atlanan": [], "uyarilar": [],
               "kart_farklari": [], "yeniden_adlandirilan": [], "urun_parametre_farklari": []}
    assert ImportOzeti.model_validate(alanlar).revize == 0
    assert ImportOzeti.model_validate({**alanlar, "revize": 7}).model_dump()["revize"] == 7
