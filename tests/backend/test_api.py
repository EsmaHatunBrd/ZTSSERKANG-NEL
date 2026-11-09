from datetime import date
from decimal import Decimal as D_
import pytest
from fastapi.testclient import TestClient
from backend.uygulama import uygulama_olustur
from backend.depo import modeller as m
from backend.depo.veritabani import oturum_ver
from backend.tohum import parametreleri_tohumla
from tests.backend.test_gider_servisi import tohumla as gider_tohumla


@pytest.fixture
def istemci(oturum):
    app = uygulama_olustur()
    app.dependency_overrides[oturum_ver] = lambda: oturum
    parametreleri_tohumla(oturum)
    return TestClient(app)


def _senaryo(c):
    r = c.post("/api/v1/senaryolar", json={"sezon_ad": "2026-2027", "tur": "fiyat_calismasi", "ad": "A"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _kur(c, sid, oturum):
    for a, v in [("enflasyon", "0.25"), ("kur.USD", "50"), ("kur.EUR", "60"), ("faiz.TL", "0.4"), ("stok_ay.TL", "6"), ("faiz.USD", "0.06"),
                 ("stok_ay.USD", "6"), ("faiz.EUR", "0.06"), ("stok_ay.EUR", "6"), ("satis_kar", "0.2"), ("teklif_kar.1", "0.2"), ("vardiya_saati", "7.5")]:
        assert c.post(f"/api/v1/parametreler/{a}/degerler?senaryo={sid}", json={"deger": v, "gecerlilik_basi": "2026-06-01", "neden": "tohum"}).status_code == 201
    gider_tohumla(oturum, sid)
    c.post("/api/v1/malzemeler", json={"kod": "KAV", "ad": "Kavanoz", "tip": "0008-Ambalaj Malzeme", "birim": "AD", "para_birimi": "TL", "zs": "S"})
    assert c.post("/api/v1/malzemeler/KAV/fiyatlar?senaryo=%d" % sid, json={"onay": True, "fiyat": "5.9", "gecerlilik_basi": "2026-06-01", "neden": "bütçe"}).status_code == 201
    assert c.put("/api/v1/urunler/TEST", json={"ad": "Test", "ambalaj_hacmi": "370", "hat": "Niko", "taze_tursu_sinifi": "Turşu/Turşu", "suzme_kg": "0.18"}).status_code == 200
    assert c.put(f"/api/v1/urunler/TEST/uretim-hedefi?senaryo={sid}", json={"vardiya_uretim_adedi": "65000", "dolum_personel": "13", "etiketleme_adedi": "35000",
                 "etiket_personel": "7", "mal_kabul_miktar_kg": "0.19"}).status_code == 200
    assert c.post(f"/api/v1/urunler/TEST/recete?senaryo={sid}", json=[{"malzeme_kodu": "KAV", "ad": "Kavanoz", "miktar": "1", "birim": "AD", "fire_override": "0.02"}]).status_code == 201


def test_hesapla_akisi(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    r = istemci.post("/api/v1/urunler/TEST/hesapla", json={"senaryo_id": sid, "tarih": "2026-10-21"})
    assert r.status_code == 200, r.text
    g = r.json()
    assert g["satirlar"][0]["fire_kaynagi"] == "satir" and isinstance(g["toplamlar"]["maliyet_tl"], str)
    assert abs(D_(g["satirlar"][0]["tutar"]) - D_("5.9") * D_("1.25") / D_("0.98")) < D_("1e-9")
    r2 = istemci.post("/api/v1/urunler/TEST/hesaplar", json={"senaryo_id": sid, "tarih": "2026-10-21"}, headers={"X-Kullanici": "esma"})
    assert r2.status_code == 201 and r2.json()["olusturan"] == "esma"
    hid = r2.json()["id"]
    assert istemci.post(f"/api/v1/hesaplar/{hid}/teklifler", json={"kar_orani": "0.2"}).status_code == 201
    assert len(istemci.get(f"/api/v1/hesaplar/{hid}/teklifler").json()["kayitlar"]) == 1


def test_dashboard_ve_disa_aktar(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    r = istemci.get(f"/api/v1/urunler?senaryo={sid}")
    assert r.status_code == 200 and r.json()["toplam"] == 1 and r.json()["kayitlar"][0]["hata"] is None
    x = istemci.get(f"/api/v1/disa-aktar/urunler.xlsx?senaryo={sid}")
    assert x.status_code == 200 and x.headers["content-type"].startswith("application/vnd.openxmlformats")


def test_hata_govdesi(istemci):
    r = istemci.get("/api/v1/hesaplar/999")
    assert r.status_code == 404 and set(r.json()) == {"hata", "mesaj", "alanlar", "kod"}
    sid = _senaryo(istemci)   # G4: senaryo artık her uçta önce doğrulanır; geçerli senaryoyla bilinmeyen parametre 422
    r = istemci.post(f"/api/v1/parametreler/yok.boyle/degerler?senaryo={sid}", json={"deger": "1", "gecerlilik_basi": "2026-06-01", "neden": "x"})
    assert r.status_code == 422


def test_parametre_gecmisi(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    istemci.post(f"/api/v1/parametreler/kur.USD/degerler?senaryo={sid}", json={"deger": "55", "gecerlilik_basi": "2026-09-01", "neden": "zam"})
    g = istemci.get(f"/api/v1/parametreler/kur.USD/gecmis?senaryo={sid}").json()["kayitlar"]
    assert [x["deger"] for x in g] == ["55", "50"]
    assert istemci.get(f"/api/v1/parametreler?senaryo={sid}&tarih=2026-08-01").json()["kur.USD"] == "50"


def test_bilinmeyen_senaryo_404(istemci):
    r = istemci.get("/api/v1/urunler?senaryo=999")
    assert r.status_code == 404 and set(r.json()) == {"hata", "mesaj", "alanlar", "kod"}


def test_dashboard_hata_satiri(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    assert istemci.put("/api/v1/urunler/BOS", json={"ad": "Bos", "ambalaj_hacmi": "720", "hat": "Niko", "taze_tursu_sinifi": "Turşu/Turşu", "suzme_kg": "0.3"}).status_code == 200
    assert [x["kod"] for x in istemci.get(f"/api/v1/urunler?senaryo={sid}").json()["kayitlar"]] == ["TEST"]   # Faz 5c: reçetesiz ürün üye değil
    satirlar = {x["kod"]: x for x in istemci.get(f"/api/v1/urunler?senaryo={sid}&tum=1").json()["kayitlar"]}   # tum=1: eski davranış
    assert satirlar["TEST"]["hata"] is None
    bos = satirlar["BOS"]
    assert bos["hata"] and bos["maliyet_tl"] is None and bos["recete_maliyeti"] is None and bos["uyari_sayisi"] is None


def test_recete_getir(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    r = istemci.get(f"/api/v1/urunler/TEST/recete?senaryo={sid}&tarih=2026-10-21")
    assert r.status_code == 200
    satir = r.json()["satirlar"][0]
    assert satir["malzeme_kodu"] == "KAV" and satir["fire_kaynagi"] == "satir" and satir["fire_orani"] == "0.02"


def test_fiyat_listesi_import(istemci, oturum, tmp_path):
    from openpyxl import Workbook
    sid = _senaryo(istemci)
    istemci.post("/api/v1/malzemeler", json={"kod": "A1", "ad": "A", "tip": "t", "birim": "KG", "para_birimi": "TL", "zs": "S"})
    assert istemci.post(f"/api/v1/malzemeler/A1/fiyatlar?senaryo={sid}", json={"onay": True, "fiyat": "5", "gecerlilik_basi": "2026-06-01", "neden": "x"}).status_code == 201
    wb = Workbook(); ws = wb.active
    ws.append(["kod", "ad", "c", "d", "e", "fiyat"]); ws.append(["A1", "A", None, None, None, 6])
    yol = tmp_path / "fiyat.xlsx"; wb.save(yol)
    with open(yol, "rb") as f:
        r = istemci.post("/api/v1/import/fiyat-listesi", data={"senaryo": str(sid), "gecerlilik_basi": "2026-10-21"}, files={"dosya": ("fiyat.xlsx", f)})
    assert r.status_code == 200, r.text
    assert len(r.json()["degisen"]) == 1 and r.json()["degisen"][0]["kod"] == "A1"
    r = istemci.post("/api/v1/import/fiyat-listesi", data={"senaryo": str(sid)}, files={"dosya": ("x.txt", b"merhaba")})
    assert r.status_code == 422 and r.json()["hata"] == "dogrulama"


def test_uretim_hedefi_getir(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    r = istemci.get(f"/api/v1/urunler/TEST/uretim-hedefi?senaryo={sid}")
    assert r.status_code == 200 and r.json()["vardiya_uretim_adedi"] == "65000"
    assert istemci.get(f"/api/v1/urunler/TEST?senaryo={sid}").json()["uretim_hedefi"]["dolum_personel"] == "13"
    assert istemci.get("/api/v1/urunler/TEST/uretim-hedefi?senaryo=999").status_code == 404


# ---------------------------------------------------------------- Final düzeltme dalgası (G1-G11)
A = "/api/v1"
HATA_ANAHTARLARI = {"hata", "mesaj", "alanlar", "kod"}


def test_override_tipli_dogrulama(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    url = f"{A}/urunler/TEST/hesapla"
    for ov in ({"fire": {"0": "0.05"}}, {"fire": {"1": "1"}}, {"fire": {"1": "-0.1"}}, {"uretim": {"yok_alan": 1}}, {"uretim": {"vardiya_uretim_adedi": "0"}},
               {"uretim": {"mal_kabul_fire": "1"}}, {"bilinmeyen": 1}, {"parametreler": {"kur.USD": "abc"}}, {"parametreler": {"kur.USD": "NaN"}}):
        r = istemci.post(url, json={"senaryo_id": sid, "override": ov})
        assert r.status_code == 422 and set(r.json()) == HATA_ANAHTARLARI, (ov, r.text)
    r = istemci.post(url, json={"senaryo_id": sid, "override": {"fire": {"5": "0.05"}}})
    assert r.status_code == 422 and r.json()["hata"] == "dogrulama"                      # sira > satır sayısı (servis)
    r = istemci.post(url, json={"senaryo_id": sid, "override": {"parametreler": {"teklif_kar.0": "0.1"}}})
    assert r.status_code == 422


def test_gecerli_override_kaydedilir(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    ov = {"parametreler": {"stok_ay.TL": "2"}, "fire": {"1": "0.05"}, "uretim": {"dolum_personel": "20"}}
    r = istemci.post(f"{A}/urunler/TEST/hesapla", json={"senaryo_id": sid, "tarih": "2026-10-21", "override": ov})
    assert r.status_code == 200, r.text
    assert r.json()["satirlar"][0]["fire_orani"] == "0.05" and r.json()["kullanilan_parametreler"]["stok_ay.TL"] == "2"
    r = istemci.post(f"{A}/urunler/TEST/hesaplar", json={"senaryo_id": sid, "tarih": "2026-10-21", "override": ov})
    assert r.status_code == 201
    g = istemci.get(f"{A}/hesaplar/{r.json()['id']}").json()
    assert g["girdi_snapshot"]["override"] == {"parametreler": {"stok_ay.TL": "2"}, "fire": {"1": "0.05"}, "uretim": {"dolum_personel": "20"}}
    assert set(g["girdi_snapshot"]) >= {"malzemeler", "recete", "override"}


def test_kurallara_birak_api(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    r = istemci.post(f"{A}/urunler/TEST/recete/kurallara-birak?senaryo={sid}", json={"siralar": None})
    assert r.status_code == 201 and r.json()["versiyon"] == 2 and r.json()["satir_sayisi"] == 1
    sat = istemci.get(f"{A}/urunler/TEST/recete?senaryo={sid}&tarih=2026-10-21").json()["satirlar"][0]
    assert sat["fire_override"] is None and sat["fire_kaynagi"].startswith(("tip:", "yok"))
    assert istemci.post(f"{A}/urunler/TEST/recete/kurallara-birak?senaryo={sid}", json={"siralar": [0]}).status_code == 422
    assert istemci.post(f"{A}/urunler/TEST/recete/kurallara-birak?senaryo={sid}", json={"siralar": [7]}).status_code == 422
    assert istemci.post(f"{A}/urunler/TEST/recete/kurallara-birak?senaryo=999", json={"siralar": None}).status_code == 404


def test_senaryo_dogrulamasi_tekduze(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    r = istemci.post(f"{A}/malzemeler/KAV/fiyatlar?senaryo=999", json={"onay": True, "fiyat": "1", "gecerlilik_basi": "2026-06-01", "neden": "x"})
    assert r.status_code == 404 and set(r.json()) == HATA_ANAHTARLARI and r.json()["hata"] == "bulunamadi"
    for yol in ("/malzemeler", "/malzemeler/KAV/fiyatlar", "/parametreler", "/parametreler/kur.USD/gecmis", "/gider-havuzlari", "/ambalaj-siniflari",
                "/fire-kurallari", "/urunler", "/urunler/TEST", "/urunler/TEST/recete", "/urunler/TEST/recete/versiyonlar", "/urunler/TEST/hesaplar",
                "/urunler/TEST/uretim-hedefi", "/uyarilar", "/disa-aktar/urunler.xlsx"):
        r = istemci.get(f"{A}{yol}?senaryo=999")
        assert r.status_code == 404 and set(r.json()) == HATA_ANAHTARLARI, (yol, r.status_code)
    assert istemci.post(f"{A}/parametreler/kur.USD/degerler?senaryo=999", json={"deger": "1", "gecerlilik_basi": "2026-06-01", "neden": "x"}).status_code == 404
    assert istemci.post(f"{A}/fire-kurallari?senaryo=999", json={"kapsam_tipi": "tip", "kapsam_deger": "x", "oran": "0.1", "gecerlilik_basi": "2026-06-01", "neden": "x"}).status_code == 404
    assert istemci.put(f"{A}/ambalaj-siniflari?senaryo=999", json=[{"ad": "a", "hacim": "1", "uretim_adedi": "1", "katsayi": "1"}]).status_code == 404
    assert istemci.get(f"{A}/urunler").status_code == 422   # senaryo zorunlu


def test_cakisma_409_ve_beklenmeyen_500(istemci, oturum, monkeypatch):
    assert istemci.post(f"{A}/malzeme-gruplari", json={"ad": "G1", "malzeme_kodlari": ["A"]}).status_code == 201
    r = istemci.post(f"{A}/malzeme-gruplari", json={"ad": "G1", "malzeme_kodlari": ["B"]})
    assert r.status_code == 409 and r.json() == {"hata": "cakisma", "mesaj": "kayıt çakışması (benzersiz alan veya ilişki)", "alanlar": {}, "kod": None}
    oturum.rollback()
    sid = _senaryo(istemci)
    from backend.servisler import hesap_servisi as hs

    def patla(*a, **k):
        raise RuntimeError("gizli ayrıntı")
    monkeypatch.setattr(hs, "urunler", patla)
    r = TestClient(istemci.app, raise_server_exceptions=False).get(f"{A}/urunler?senaryo={sid}")
    assert r.status_code == 500 and r.json() == {"hata": "sunucu", "mesaj": "beklenmeyen hata", "alanlar": {}, "kod": None} and "gizli" not in r.text


def test_pasiflestirme_api(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    r = istemci.patch(f"{A}/malzemeler/KAV/pasif", headers={"X-Kullanici": "esma"})
    assert r.status_code == 200 and r.json() == {"kod": "KAV", "aktif": False}
    r = istemci.patch(f"{A}/urunler/TEST/pasif")
    assert r.status_code == 200 and r.json() == {"kod": "TEST", "aktif": False}
    assert istemci.get(f"{A}/urunler/TEST").json()["aktif"] is False
    assert istemci.patch(f"{A}/urunler/YOK/pasif").status_code == 404 and istemci.patch(f"{A}/malzemeler/YOK/pasif").status_code == 404
    k = istemci.get(f"{A}/degisiklikler?tablo=malzeme").json()["kayitlar"]
    assert [x["islem"] for x in k] == ["pasiflestir"] and k[0]["kullanici"] == "esma" and k[0]["zaman"].endswith("+00:00")


def _xlsx_alakasiz(tmp_path):
    from openpyxl import Workbook
    wb = Workbook(); wb.active.append(["a", "b"]); yol = tmp_path / "alakasiz.xlsx"; wb.save(yol)
    return yol


def test_yukleme_saglamligi(istemci, oturum, tmp_path, monkeypatch):
    yol = _xlsx_alakasiz(tmp_path)
    with open(yol, "rb") as f:
        r = istemci.post(f"{A}/import/excel-tam", data={"sezon_ad": "2026-2027", "senaryo_ad": "X"}, files={"dosya": ("a.xlsx", f)})
    assert r.status_code == 422 and r.json()["hata"] == "dogrulama" and "beklenen yapıda değil" in r.json()["mesaj"]
    from backend.api import import_ as imp_api
    monkeypatch.setattr(imp_api, "MAKS_DOSYA_BAYT", 100)
    with open(yol, "rb") as f:
        r = istemci.post(f"{A}/import/excel-tam", data={"sezon_ad": "2026-2027", "senaryo_ad": "X"}, files={"dosya": ("a.xlsx", f)})
    assert r.status_code == 422 and "25 MB" in r.json()["mesaj"]


def test_fiyat_listesi_onizle_uygula_api(istemci, oturum, tmp_path):
    from openpyxl import Workbook
    sid = _senaryo(istemci)
    istemci.post(f"{A}/malzemeler", json={"kod": "A1", "ad": "A", "tip": "t", "birim": "KG", "para_birimi": "TL", "zs": "S"})
    istemci.post(f"{A}/malzemeler/A1/fiyatlar?senaryo={sid}", json={"onay": True, "fiyat": "5", "gecerlilik_basi": "2026-06-01", "neden": "x"})
    istemci.post(f"{A}/malzemeler/A1/fiyatlar?senaryo={sid}", json={"onay": True, "fiyat": "6", "gecerlilik_basi": "2026-09-01", "neden": "x"})
    wb = Workbook(); ws = wb.active
    ws.append(["kod", "ad", "c", "d", "e", "fiyat"]); ws.append(["A1", "A", None, None, None, 6])
    yol = tmp_path / "f.xlsx"; wb.save(yol)

    def gonder(tarih, uygula):
        with open(yol, "rb") as f:
            veri = {"senaryo": str(sid), "gecerlilik_basi": tarih, **({"neden": "liste"} if uygula else {})}
            return istemci.post(f"{A}/import/fiyat-listesi" + ("/uygula" if uygula else ""), data=veri, files={"dosya": ("f.xlsx", f)})
    assert gonder("2026-10-01", False).json()["ayni"] == 1
    assert gonder("2026-08-01", False).json()["degisen"][0]["kod"] == "A1"
    assert gonder("2026-10-01", True).json() == {"yazilan": 0, "kodlar": []}
    assert gonder("2026-08-01", True).json() == {"yazilan": 1, "kodlar": ["A1"]}


def test_urun_kod_degistir_ve_gecici_filtre(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    h = istemci.post(f"{A}/urunler/TEST/hesaplar", json={"senaryo_id": sid, "tarih": "2026-10-21"}).json()["id"]
    r = istemci.patch(f"{A}/urunler/TEST/kod", json={"yeni_kod": "03.009.001"}, headers={"X-Kullanici": "esma"})
    assert r.status_code == 200 and r.json()["kod"] == "03.009.001" and r.json()["gecici_kod"] is False
    assert istemci.get(f"{A}/urunler/TEST").status_code == 404 and istemci.get(f"{A}/urunler/03.009.001").status_code == 200
    assert istemci.get(f"{A}/hesaplar/{h}").json()["gorunum"]["urun_kodu"] == "03.009.001"
    assert istemci.put(f"{A}/urunler/DIGER", json={"ad": "D", "ambalaj_hacmi": "1", "hat": "Niko", "taze_tursu_sinifi": "Turşu/Turşu", "suzme_kg": "1"}).status_code == 200
    assert istemci.patch(f"{A}/urunler/DIGER/kod", json={"yeni_kod": "03.009.001"}).status_code == 422
    assert istemci.patch(f"{A}/urunler/DIGER/kod", json={"yeni_kod": ""}).status_code == 422
    # geçici kodlu ürün ve filtre
    from backend.depo import modeller as m
    oturum.add(m.Urun(kod="SAYFA-X", ad="X", ambalaj_hacmi=1, hat="Niko", taze_tursu_sinifi="Turşu/Turşu", suzme_kg=1, gecici_kod=True)); oturum.flush()
    assert istemci.get(f"{A}/urunler?senaryo={sid}").json()["toplam"] == 1   # Faz 5c: DIGER ve SAYFA-X reçetesiz -> üye değil; tum=1 eski davranış
    tum = istemci.get(f"{A}/urunler?senaryo={sid}&tum=1").json()
    assert tum["toplam"] == 3 and {x["kod"]: x["gecici_kod"] for x in tum["kayitlar"]}["SAYFA-X"] is True
    g = istemci.get(f"{A}/urunler?senaryo={sid}&gecici=true&tum=1").json()
    assert g["toplam"] == 1 and g["kayitlar"][0]["kod"] == "SAYFA-X"
    assert {x["kod"] for x in istemci.get(f"{A}/urunler?senaryo={sid}&gecici=false&tum=1").json()["kayitlar"]} == {"03.009.001", "DIGER"}


def test_sema_sinirlari(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    for yol in ("/urunler", "/malzemeler"):
        assert istemci.get(f"{A}{yol}?senaryo={sid}&sayfa=0").status_code == 422
        assert istemci.get(f"{A}{yol}?senaryo={sid}&boyut=0").status_code == 422
        assert istemci.get(f"{A}{yol}?senaryo={sid}&boyut=501").status_code == 422
    fg = {"gecerlilik_basi": "2026-06-01", "neden": "x"}
    assert istemci.post(f"{A}/malzemeler/KAV/fiyatlar?senaryo={sid}", json={"onay": True, "fiyat": "-1", **fg}).status_code == 422
    fk = {"kapsam_tipi": "tip", "kapsam_deger": "x", "gecerlilik_basi": "2026-06-01", "neden": "x"}
    for oran in ("1", "-0.1"):
        assert istemci.post(f"{A}/fire-kurallari?senaryo={sid}", json={**fk, "oran": oran}).status_code == 422
    assert istemci.post(f"{A}/fire-kurallari?senaryo={sid}", json={**fk, "oran": "0.1", "neden": ""}).status_code == 422
    assert istemci.post(f"{A}/fire-kurallari?senaryo={sid}", json={**fk, "oran": "0.1"}).status_code == 201
    hid = istemci.post(f"{A}/urunler/TEST/hesaplar", json={"senaryo_id": sid, "tarih": "2026-10-21"}).json()["id"]
    assert istemci.post(f"{A}/hesaplar/{hid}/teklifler", json={"kar_orani": "-1"}).status_code == 422
    assert istemci.post(f"{A}/urunler/TEST/recete?senaryo={sid}", json=[{"malzeme_kodu": "KAV", "miktar": "-1"}]).status_code == 422
    assert istemci.post(f"{A}/urunler/TEST/recete?senaryo={sid}", json=[{"malzeme_kodu": "KAV", "miktar": "1", "fire_override": "1"}]).status_code == 422
    amb = {"ad": "a", "hacim": "1", "uretim_adedi": "1", "katsayi": "1"}
    assert istemci.put(f"{A}/ambalaj-siniflari?senaryo={sid}", json=[{**amb, "katsayi": "0"}]).status_code == 422
    assert istemci.put(f"{A}/ambalaj-siniflari?senaryo={sid}", json=[{**amb, "uretim_adedi": "-1"}]).status_code == 422
    r = istemci.put(f"{A}/ambalaj-siniflari?senaryo={sid}", json=[])
    assert r.status_code == 422 and r.json()["hata"] == "dogrulama"
    hv = {"ad": "x", "toplam_tutar": "1", "baz_tipi": "saniye", "baz_miktar": "5", "anahtarlar": []}
    assert istemci.put(f"{A}/gider-havuzlari/elektrik?senaryo={sid}", json={**hv, "toplam_tutar": "-1"}).status_code == 422
    assert istemci.put(f"{A}/gider-havuzlari/elektrik?senaryo={sid}", json={**hv, "baz_tipi": "litre"}).status_code == 422
    assert istemci.put(f"{A}/gider-havuzlari/elektrik?senaryo={sid}", json={**hv, "baz_miktar": None}).status_code == 422
    assert istemci.put(f"{A}/gider-havuzlari/elektrik?senaryo={sid}", json={**hv, "anahtarlar": [{"alt_kalem": "a", "pay_orani": "1.5", "baz_miktar": "1"}]}).status_code == 422


def test_toplu_hesapta_veritabani_hatasi_yayilir(istemci, oturum, monkeypatch):
    sid = _senaryo(istemci)
    from sqlalchemy.exc import OperationalError
    from backend.depo import modeller as m
    from backend.servisler import hesap_servisi as hs

    def patla(*a, **k):
        raise OperationalError("x", {}, Exception("db"))
    monkeypatch.setattr(hs, "hesapla", patla)
    oturum.add(m.Urun(kod="U", ad="U", ambalaj_hacmi=1, hat="Niko", taze_tursu_sinifi="T", suzme_kg=1)); oturum.flush()
    r = TestClient(istemci.app, raise_server_exceptions=False).get(f"{A}/urunler?senaryo={sid}&tum=1")   # Faz 5c: U reçetesiz, tum=1 ile hesaba girer
    assert r.status_code == 500


def test_okuma_uclari(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    h1 = istemci.post(f"{A}/urunler/TEST/hesaplar", json={"senaryo_id": sid, "tarih": "2026-10-21"}, headers={"X-Kullanici": "esma"}).json()["id"]
    h2 = istemci.post(f"{A}/urunler/TEST/hesaplar", json={"senaryo_id": sid, "tarih": "2026-10-22"}).json()["id"]
    liste = istemci.get(f"{A}/urunler/TEST/hesaplar?senaryo={sid}").json()["kayitlar"]
    assert [x["id"] for x in liste] == [h2, h1] and set(liste[0]) == {"id", "hesap_tarihi", "olusturan", "maliyet_tl", "satis_tl", "son_tur_no", "son_kar_orani", "son_musteri", "son_durum"} and liste[1]["olusturan"] == "esma"
    d = istemci.get(f"{A}/hesaplar/{h1}").json()
    canli = istemci.post(f"{A}/urunler/TEST/hesapla", json={"senaryo_id": sid, "tarih": "2026-10-21"}).json()
    assert d["gorunum"] == canli       # tek çizici: kayıtlı görünüm, canlı hesap yanıtıyla aynı biçim ve değer
    assert liste[1]["maliyet_tl"] == canli["toplamlar"]["maliyet_tl"] and liste[1]["satis_tl"] == canli["fiyatlar"]["satis_tl"]
    t = istemci.get(f"{A}/parametreler/tanimlar").json()["kayitlar"]
    assert {"anahtar": "enflasyon", "aciklama": "Enflasyon öngörüsü (yalnız fiyat çalışması)", "birim": "oran"} in t
    assert istemci.post(f"{A}/malzeme-gruplari", json={"ad": "G", "malzeme_kodlari": ["KAV"]}).status_code == 201
    assert istemci.get(f"{A}/malzeme-gruplari").json()["kayitlar"] == [{"id": 1, "ad": "G", "malzeme_kodlari": ["KAV"]}]
    istemci.post(f"{A}/urunler/TEST/recete/kurallara-birak?senaryo={sid}", json={"siralar": None})
    v = istemci.get(f"{A}/urunler/TEST/recete/versiyonlar?senaryo={sid}").json()["kayitlar"]
    assert [(x["versiyon"], x["aktif"]) for x in v] == [(2, True), (1, False)] and set(v[0]) == {"id", "versiyon", "kaynak", "aktif", "olusturma_zamani"}
    assert v[0]["olusturma_zamani"].endswith("+00:00")
    rc = istemci.get(f"{A}/receteler/{v[1]['id']}").json()
    assert rc["versiyon"] == 1 and rc["satirlar"][0]["malzeme_kodu"] == "KAV" and rc["satirlar"][0]["fire_override"] == "0.02"
    assert istemci.get(f"{A}/receteler/999").status_code == 404
    istemci.patch(f"{A}/urunler/TEST/pasif")
    assert istemci.get(f"{A}/degisiklikler?tablo=urun&kayit_id=1").json()["kayitlar"][0]["islem"] == "pasiflestir"
    assert istemci.get(f"{A}/degisiklikler?tablo=yoktur").json() == {"kayitlar": [], "toplam": 0}


def test_uyarilar_ve_kartsiz_fiyatsiz(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    assert istemci.post(f"{A}/urunler/TEST/recete?senaryo={sid}", json=[
        {"malzeme_kodu": "KAV", "miktar": "1", "fire_override": "0.02"}, {"malzeme_kodu": "KARTYOK", "miktar": "1"},
        {"malzeme_kodu": "ARAMAMUL", "miktar": "1", "dugum_tipi": "ara_mamul"}]).status_code == 201
    u = istemci.get(f"{A}/uyarilar?senaryo={sid}&tarih=2026-10-21").json()
    assert u["toplam"] == len(u["kayitlar"]) >= 1 and set(u["kayitlar"][0]) == {"urun_kodu", "uyari"}
    assert all(x["urun_kodu"] == "TEST" for x in u["kayitlar"]) and any("KARTYOK" in x["uyari"] for x in u["kayitlar"])
    assert not any("ARAMAMUL" in x["uyari"] for x in u["kayitlar"])
    f = istemci.get(f"{A}/malzemeler?senaryo={sid}&fiyatsiz=true").json()
    assert {"kod": "KARTYOK", "ad": None, "kart_yok": True} in f["kayitlar"] and f["toplam"] == len(f["kayitlar"])
    assert all(x["kod"] != "ARAMAMUL" for x in f["kayitlar"]) and all(x["kod"] != "KAV" for x in f["kayitlar"])
    assert all(x["kod"] != "KARTYOK" for x in istemci.get(f"{A}/malzemeler?senaryo={sid}").json()["kayitlar"])


def test_cors_ve_kullanici_cozumleme(istemci, oturum):
    r = istemci.options(f"{A}/senaryolar", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "x-kullanici"})
    assert r.status_code == 200 and r.headers["access-control-allow-origin"] == "http://localhost:5173"
    r = istemci.options(f"{A}/senaryolar", headers={"Origin": "http://baska.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in r.headers
    r = istemci.post(f"{A}/senaryolar", json={"sezon_ad": "2026-2027", "tur": "fiyat_calismasi", "ad": "A"}, headers={"X-Kullanici": "E%C5%9Fma%20Akbulut"})
    assert r.status_code == 201
    from backend.depo import modeller as m
    assert oturum.query(m.Senaryo).one().olusturan == "Eşma Akbulut"


# ---------------------------------------------------------------- G11
def _para_taramasi(x, yol="$"):
    """JSON'da float yok; tamsayı yalnız kimlik/sayaç alanlarında."""
    izinli_int = {"id", "toplam", "sira", "senaryo_id", "urun_id", "uyari_sayisi", "versiyon", "satir_sayisi", "recete_id", "kayit_id", "maliyet_hesabi_id", "tur_no", "enflasyon_altinda_toplam"}
    if isinstance(x, float):
        raise AssertionError(f"float: {yol}")
    if isinstance(x, dict):
        for k, v in x.items():
            if isinstance(v, int) and not isinstance(v, bool):
                assert k in izinli_int, f"tamsayı tutar? {yol}.{k}={v}"
            _para_taramasi(v, f"{yol}.{k}")
    elif isinstance(x, list):
        for i, v in enumerate(x):
            assert not (isinstance(v, int) and not isinstance(v, bool)), f"tamsayı: {yol}[{i}]"
            _para_taramasi(v, f"{yol}[{i}]")


def test_json_para_alanlari_string_ve_sozlesme_anahtarlari(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    canli = istemci.post(f"{A}/urunler/TEST/hesapla", json={"senaryo_id": sid, "tarih": "2026-10-21"}).json()
    hid = istemci.post(f"{A}/urunler/TEST/hesaplar", json={"senaryo_id": sid, "tarih": "2026-10-21"}).json()["id"]
    kayitli = istemci.get(f"{A}/hesaplar/{hid}").json()
    dash = istemci.get(f"{A}/urunler?senaryo={sid}&tarih=2026-10-21").json()
    for govde in (canli, kayitli, kayitli["gorunum"], dash, istemci.get(f"{A}/urunler/TEST/recete?senaryo={sid}").json()):
        _para_taramasi(govde)
    # tasarım belgesi §4 örneği
    for g in (canli, kayitli["gorunum"]):
        assert {"kalem", "grup", "miktar", "brut_miktar", "birim_fiyat", "tutar", "maliyet_yuzdesi", "fiyat_yuzdesi", "fire_orani", "fire_kaynagi"} <= set(g["satirlar"][0])
        # Faz 4b: eski sözleşme anahtarları korunur, yalnız yeni alanlar eklenir (geriye uyumlu)
        assert {"malzeme", "direkt_iscilik", "gug", "uretim_gideri", "diger", "giydirilmis", "finansman_tl", "maliyet_tl", "maliyet_usd", "maliyet_eur"} <= set(g["toplamlar"])
        assert set(g["toplamlar"]) == {"malzeme", "direkt_iscilik", "gug", "uretim_gideri", "diger", "giydirilmis", "finansman_tl", "maliyet_tl", "maliyet_usd", "maliyet_eur",
                                       "maliyet_gbp", "maliyet_zar", "finansman"}
        assert {"satis_tl", "satis_usd", "satis_eur", "suzme_kg_tl", "teklifler_usd"} <= set(g["fiyatlar"])
        assert set(g["fiyatlar"]) == {"satis_tl", "satis_usd", "satis_eur", "suzme_kg_tl", "teklifler_usd", "satis_gbp", "satis_zar", "teklif_kar_oranlari", "satis_kar_orani"}
        assert {"urun_kodu", "senaryo_id", "hesap_tarihi", "satirlar", "toplamlar", "fiyatlar", "toplamlar_firesiz", "fiyatlar_firesiz",
                "kullanilan_parametreler", "uyarilar"} <= set(g)
        assert set(g) - {"urun_kodu", "senaryo_id", "hesap_tarihi", "satirlar", "toplamlar", "fiyatlar", "toplamlar_firesiz", "fiyatlar_firesiz",
                         "kullanilan_parametreler", "uyarilar"} == {"uretim", "parametreler", "notlar"}
    assert canli["satirlar"][0]["fire_kaynagi"] == "satir" and canli["satirlar"][0]["fire_orani"] == "0.02"


def _gercek_oturumlu_istemci(tmp_path, monkeypatch):
    from backend.depo import veritabani as vt
    engine = vt.motor_olustur(f"sqlite:///{tmp_path / 'gercek.db'}"); vt.Base.metadata.create_all(engine)
    fabrika = vt.oturum_fabrikasi(engine)
    monkeypatch.setattr(vt, "_ENGINE", engine); monkeypatch.setattr(vt, "_SESSION", fabrika)
    return TestClient(uygulama_olustur()), fabrika


def test_gercek_oturum_commit_ve_rollback(tmp_path, monkeypatch):
    from backend.depo import modeller as m
    c, fabrika = _gercek_oturumlu_istemci(tmp_path, monkeypatch)
    # 422: servis Sezon/Senaryo/Parametre yazdıktan sonra hata verir -> hiçbir satır kalmamalı
    yol = _xlsx_alakasiz(tmp_path)
    with open(yol, "rb") as f:
        r = c.post(f"{A}/import/excel-tam", data={"sezon_ad": "2026-2027", "senaryo_ad": "X"}, files={"dosya": ("a.xlsx", f)})
    assert r.status_code == 422
    with fabrika() as s2:
        assert (s2.query(m.Sezon).count(), s2.query(m.Senaryo).count(), s2.query(m.Parametre).count()) == (0, 0, 0)
    # 201: ikinci bir oturumdan görünür
    r = c.post(f"{A}/senaryolar", json={"sezon_ad": "2026-2027", "tur": "fiyat_calismasi", "ad": "A"})
    assert r.status_code == 201
    with fabrika() as s3:
        assert s3.query(m.Senaryo).one().id == r.json()["id"] and s3.query(m.Sezon).count() == 1
    # 409: benzersizlik ihlali; oturum geri alınır ve sonraki istek çalışır
    assert c.post(f"{A}/malzeme-gruplari", json={"ad": "G", "malzeme_kodlari": ["A"]}).status_code == 201
    assert c.post(f"{A}/malzeme-gruplari", json={"ad": "G", "malzeme_kodlari": ["B"]}).status_code == 409
    assert c.get(f"{A}/senaryolar").json()["toplam"] == 1


# ---- Faz 4 Görev 9: ön yüz için API boşlukları ----

def test_hesap_satiri_sira_ve_doviz(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    istemci.post(f"{A}/malzemeler", json={"kod": "KAP", "ad": "Kapak", "tip": "0008-Ambalaj Malzeme", "birim": "AD", "para_birimi": "USD", "zs": "S"})
    istemci.post(f"{A}/malzemeler/KAP/fiyatlar?senaryo={sid}", json={"onay": True, "fiyat": "0.1", "gecerlilik_basi": "2026-06-01", "neden": "bütçe"})
    assert istemci.post(f"{A}/urunler/TEST/recete?senaryo={sid}", json=[{"malzeme_kodu": "KAV", "ad": "Kavanoz", "miktar": "1"},
                                                                       {"malzeme_kodu": "KAP", "ad": "Kapak", "miktar": "1"}]).status_code == 201
    g = istemci.post(f"{A}/urunler/TEST/hesapla", json={"senaryo_id": sid, "tarih": "2026-10-21"}).json()
    mal = [x for x in g["satirlar"] if x["grup"] == "malzeme"]
    assert [(x["sira"], x["doviz"]) for x in mal] == [(1, "TL"), (2, "USD")]
    assert all(x["sira"] is None and x["doviz"] is None for x in g["satirlar"] if x["grup"] != "malzeme")
    hid = istemci.post(f"{A}/urunler/TEST/hesaplar", json={"senaryo_id": sid, "tarih": "2026-10-21"}).json()["id"]
    k = istemci.get(f"{A}/hesaplar/{hid}").json()["gorunum"]["satirlar"]
    assert [(x["sira"], x["doviz"]) for x in k if x["grup"] == "malzeme"] == [(1, "TL"), (2, "USD")]
    h = oturum.get(m.MaliyetHesabi, hid)   # eski snapshot: malzemeler anahtarı yok -> doviz null
    h.girdi_snapshot = {a: v for a, v in h.girdi_snapshot.items() if a != "malzemeler"}
    oturum.flush()
    k = istemci.get(f"{A}/hesaplar/{hid}").json()["gorunum"]["satirlar"]
    assert all(x["doviz"] is None for x in k) and [x["sira"] for x in k if x["grup"] == "malzeme"] == [1, 2]


def test_malzeme_satiri_gecerlilik_ve_kaynak_ile_urun_id(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    istemci.post(f"{A}/malzemeler", json={"kod": "FIYATSIZ", "ad": "x"})
    k = {x["kod"]: x for x in istemci.get(f"{A}/malzemeler?senaryo={sid}&tarih=2026-10-21").json()["kayitlar"]}
    assert k["KAV"]["gecerlilik_basi"] == "2026-06-01" and k["KAV"]["kaynak"] == "elle"
    assert k["FIYATSIZ"]["gecerlilik_basi"] is None and k["FIYATSIZ"]["kaynak"] is None
    uid = istemci.get(f"{A}/urunler/TEST").json()["id"]
    assert istemci.get(f"{A}/urunler?senaryo={sid}").json()["kayitlar"][0]["id"] == uid


def test_havuz_ve_ambalaj_neden(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    hv = {"ad": "x", "toplam_tutar": "1", "baz_tipi": "saniye", "baz_miktar": "5", "anahtarlar": []}
    assert istemci.put(f"{A}/gider-havuzlari/elektrik?senaryo={sid}", json=hv).status_code == 422
    assert istemci.put(f"{A}/gider-havuzlari/elektrik?senaryo={sid}", json={**hv, "neden": ""}).status_code == 422
    assert istemci.put(f"{A}/gider-havuzlari/elektrik?senaryo={sid}", json={**hv, "neden": "zam geldi"}).status_code == 200
    log = oturum.query(m.DegisiklikKaydi).filter_by(tablo="gider_havuzu").order_by(m.DegisiklikKaydi.id.desc()).first()
    assert log.yeni["_neden"] == "zam geldi" and log.yeni["toplam_tutar"] == "1"
    amb = {"ad": "a", "hacim": "1", "uretim_adedi": "1", "katsayi": "1"}
    assert istemci.put(f"{A}/ambalaj-siniflari?senaryo={sid}", json={"siniflar": [amb]}).status_code == 422   # sarmalayıcıda neden zorunlu
    assert istemci.put(f"{A}/ambalaj-siniflari?senaryo={sid}", json={"siniflar": [amb], "neden": "yeni sınıf"}).status_code == 200
    log = oturum.query(m.DegisiklikKaydi).filter_by(tablo="ambalaj_sinifi").order_by(m.DegisiklikKaydi.id.desc()).first()
    assert log.yeni["_neden"] == "yeni sınıf" and log.yeni["siniflar"] == [["a", "1", "1", "1"]]
    assert istemci.put(f"{A}/ambalaj-siniflari?senaryo={sid}", json=[{**amb, "uretim_adedi": "2"}]).status_code == 200   # çıplak liste
    log = oturum.query(m.DegisiklikKaydi).filter_by(tablo="ambalaj_sinifi").order_by(m.DegisiklikKaydi.id.desc()).first()
    assert log.yeni["_neden"] == "(belirtilmedi)"


def test_senaryo_teklifleri_ve_son_tur(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    sid2 = _senaryo(istemci)
    h1 = istemci.post(f"{A}/urunler/TEST/hesaplar", json={"senaryo_id": sid, "tarih": "2026-10-21"}).json()["id"]
    h2 = istemci.post(f"{A}/urunler/TEST/hesaplar", json={"senaryo_id": sid, "tarih": "2026-10-22"}).json()["id"]
    assert istemci.get(f"{A}/urunler/TEST/hesaplar?senaryo={sid}").json()["kayitlar"][0]["son_tur_no"] is None
    t1 = istemci.post(f"{A}/hesaplar/{h1}/teklifler", json={"kar_orani": "0.2", "musteri": "Migros A.Ş."}).json()
    istemci.post(f"{A}/hesaplar/{h1}/teklifler", json={"kar_orani": "0.3", "musteri": "BIM"})
    istemci.post(f"{A}/hesaplar/{h2}/teklifler", json={"kar_orani": "0.1", "musteri": "migros b"})
    istemci.patch(f"{A}/teklifler/{t1['id']}/durum", json={"durum": "kabul"})
    r = istemci.get(f"{A}/teklifler?senaryo={sid}").json()
    assert r["toplam"] == 3 and [(x["hesap_id"], x["tur_no"]) for x in r["kayitlar"]] == [(h2, 1), (h1, 2), (h1, 1)]   # en yeni önce
    x = r["kayitlar"][0]
    assert x["urun_kodu"] == "TEST" and x["urun_ad"] == "Test" and x["hesap_tarihi"] == "2026-10-22" and isinstance(x["fiyat_tl"], str) and x["olusturma_zamani"]
    assert set(x) == {"teklif_id", "hesap_id", "urun_kodu", "urun_ad", "hesap_tarihi", "tur_no", "kar_orani", "fiyat_tl", "fiyat_usd", "fiyat_eur",
                      "musteri", "durum", "olusturan", "olusturma_zamani"}
    assert [y["teklif_id"] for y in istemci.get(f"{A}/teklifler?senaryo={sid}&durum=kabul").json()["kayitlar"]] == [t1["id"]]
    assert istemci.get(f"{A}/teklifler?senaryo={sid}&musteri=MIGROS").json()["toplam"] == 2
    assert istemci.get(f"{A}/teklifler?senaryo={sid}&musteri=%25").json()["toplam"] == 0   # joker kaçışlı
    s1 = istemci.get(f"{A}/teklifler?senaryo={sid}&boyut=2&sayfa=2").json()
    assert s1["toplam"] == 3 and len(s1["kayitlar"]) == 1
    assert istemci.get(f"{A}/teklifler?senaryo={sid2}").json() == {"kayitlar": [], "toplam": 0}
    assert istemci.get(f"{A}/teklifler?senaryo=999").status_code == 404
    assert istemci.get(f"{A}/teklifler?senaryo={sid}&boyut=0").status_code == 422
    o = {x["id"]: x for x in istemci.get(f"{A}/urunler/TEST/hesaplar?senaryo={sid}").json()["kayitlar"]}
    assert (o[h1]["son_tur_no"], o[h1]["son_kar_orani"], o[h1]["son_musteri"], o[h1]["son_durum"]) == (2, "0.3", "BIM", "taslak")
    assert o[h2]["son_tur_no"] == 1 and o[h2]["son_musteri"] == "migros b"
    # silme: 204, liste ve son tur özeti güncellenir; olmayan teklif 404
    t3 = istemci.get(f"{A}/teklifler?senaryo={sid}").json()["kayitlar"][1]["teklif_id"]   # h1 tur 2
    assert istemci.delete(f"{A}/teklifler/{t3}").status_code == 204
    assert istemci.get(f"{A}/teklifler?senaryo={sid}").json()["toplam"] == 2
    o = {x["id"]: x for x in istemci.get(f"{A}/urunler/TEST/hesaplar?senaryo={sid}").json()["kayitlar"]}
    assert o[h1]["son_tur_no"] == 1
    assert istemci.delete(f"{A}/teklifler/{t3}").status_code == 404


def test_malzeme_aramasi_sayfalamadan_once_ve_turkce_harf(istemci, oturum):
    """arama kod ya da adda geçen metni sunucuda süzer; sonuç sayfalamadan önce süzüldüğü için 2. sayfadaki malzeme de 1. sayfada gelir.
    'I' -> 'ı' ve 'İ' -> 'i' Türkçe kuralıyla eşleşir."""
    sid = _senaryo(istemci)
    for i in range(3):
        assert istemci.post(f"{A}/malzemeler", json={"kod": f"AR-{i}", "ad": f"Ara Malzeme {i}", "tip": "x", "birim": "AD",
                                                       "para_birimi": "TL", "zs": "S"}).status_code == 201
    istemci.post(f"{A}/malzemeler", json={"kod": "ISIK", "ad": "IŞIK KAPAĞI İnce", "tip": "x", "birim": "AD", "para_birimi": "TL", "zs": "S"})
    assert [x["kod"] for x in istemci.get(f"{A}/malzemeler?senaryo={sid}&boyut=1&sayfa=1&arama=AR-2").json()["kayitlar"]] == ["AR-2"]
    r = istemci.get(f"{A}/malzemeler?senaryo={sid}&arama=ışık").json()
    assert [x["kod"] for x in r["kayitlar"]] == ["ISIK"] and r["toplam"] == 1
    assert [x["kod"] for x in istemci.get(f"{A}/malzemeler?senaryo={sid}&arama=ince").json()["kayitlar"]] == ["ISIK"]
    assert istemci.get(f"{A}/malzemeler?senaryo={sid}&arama=yok-boyle").json()["toplam"] == 0
