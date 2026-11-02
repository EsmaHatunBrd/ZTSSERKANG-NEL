"""Faz 6 — Bütçe vs Gerçekleşen. Gerçek bütçe kitabı (A) ve deneme gerçekleşen kitabı (B, scripts/10-27-2026-gerceklesen-deneme-uret.py:
aynı düzen, olası gerçek değerler, Excel'in kendi hesabıyla kaydedilmiş) aynı sezona yüklenir.
- B senaryosunun hesabı deneme kitabının P hücreleriyle birebir (gerçekleşende enflasyon 0: Excel'de de 0); bütçe paritesindeki
  bilinen Excel istisnaları (elle yazılmış gider hücreleri) deneme kitabında da aynıdır, onlar atlanır.
- Sapma ayrıştırmasının toplamı toplam farka eşit (zincirleme ikame, 1e-9).
- Uçlar: liste/önbellek, ürün detayı, karşı senaryo, Excel çıktısı, hatalar."""
import os
from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path
import openpyxl
import pytest
from fastapi.testclient import TestClient
from backend.depo import modeller as m
from backend.depo.veritabani import Base, motor_olustur, oturum_fabrikasi, oturum_ver
from backend.servisler import hesap_servisi as hs, import_servisi as ims, kiyas_servisi as ks
from backend.uygulama import uygulama_olustur
from fiyat_motoru import excel_okuyucu as eo
from fiyat_motoru.para import TOLERANS
from tests.backend.test_uctan_uca_excel import ALANLAR
from tests.test_excel_paritesi import BILINEN_ISTISNALAR

TARIH = date(2026, 10, 27)
DENEME = Path(os.environ.get("GERCEKLESEN_YOLU", Path(__file__).resolve().parents[2] / "10-27-2026-gerceklesen-deneme-2026-2027.xlsx"))


@pytest.fixture(scope="module")
def ortam(excel_yolu):
    if not DENEME.exists():
        pytest.skip(f"deneme gerçekleşen kitabı yok: {DENEME}")
    engine = motor_olustur("sqlite://"); Base.metadata.create_all(engine)
    s = oturum_fabrikasi(engine)()
    a = ims.excel_tam_yukle(s, excel_yolu, "2026-2027", "Bütçe")
    b = ims.excel_tam_yukle(s, DENEME, "2026-2027", "Gerçekleşen", tur="gerceklesen", kartlari_guncelle=False)
    s.commit()
    yield s, a["senaryo_id"], b["senaryo_id"]
    s.close()


@pytest.fixture(scope="module")
def istemci(ortam):
    s, _, _ = ortam
    app = uygulama_olustur()
    app.dependency_overrides[oturum_ver] = lambda: s
    return TestClient(app)


def test_gerceklesen_hesabi_deneme_kitabiyla_ayni(ortam):
    s, _, sb = ortam
    wb_f, wb_v = eo.excel_ac(DENEME)
    farklar, n = [], 0
    for ad in eo.urun_sayfalarini_listele(wb_v):
        if "(2)" in ad:
            continue
        girdi, p, bek = eo.urun_oku(wb_f[ad], wb_v[ad])
        assert p.enflasyon == 0
        c = hs.hesapla(s, girdi.kod or f"SAYFA-{ad}", sb, TARIH)
        n += 1
        farklar += [(ad, alan, bek[alan], al(c.sonuc)) for alan, al in ALANLAR.items()
                   if (ad, alan) not in BILINEN_ISTISNALAR and abs(bek[alan] - al(c.sonuc)) >= TOLERANS]
    assert n == 67
    assert farklar == [], "\n".join(f"{a} {b}: excel={c} servis={d}" for a, b, c, d in farklar[:20])


def test_ayristirma_toplami_toplam_farka_esit_tum_urunler(ortam):
    s, sa, sb = ortam
    for kod in sorted(ks.liste(s, sa, sb, TARIH)["satirlar"], key=lambda x: x["kod"])[:67]:
        d = ks.urun(s, kod["kod"], sa, sb, TARIH)
        assert [x["kaynak"] for x in d["ayristirma"]] == ["fiyat", "recete", "uretim", "gider", "kur", "enflasyon", "diger"]
        assert abs(sum((x["fark"] for x in d["ayristirma"]), Decimal(0)) - d["toplam_fark"]) < Decimal("1e-9"), kod["kod"]
        assert d["toplam_fark"] == d["alanlar"]["maliyet_tl"]["fark"]


def test_ayristirma_gerceklesende_enflasyon_etkisi_negatif(ortam):
    """Bütçede TL satın alma fiyatlarına %25 enflasyon var, gerçekleşende yok: TL malzemeli üründe enflasyon adımı maliyeti düşürür."""
    s, sa, sb = ortam
    etkiler = [next(x["fark"] for x in ks.urun(s, r["kod"], sa, sb, TARIH)["ayristirma"] if x["kaynak"] == "enflasyon")
               for r in ks.liste(s, sa, sb, TARIH)["satirlar"][:10]]
    assert all(e <= 0 for e in etkiler) and any(e < 0 for e in etkiler)


def test_liste_ozet_ve_esik(ortam):
    s, sa, sb = ortam
    d = ks.liste(s, sa, sb, TARIH, esik=Decimal(5))
    assert d["ozet"]["karsilastirilan"] == 67 and d["ozet"]["yalniz_a"] == d["ozet"]["yalniz_b"] == d["ozet"]["hatali"] == 0
    for x in d["satirlar"]:
        f = x["alanlar"]["maliyet_tl"]
        assert f["fark"] == f["b"] - f["a"] and x["sapma_yuzde"] == (f["b"] - f["a"]) / abs(f["a"]) * 100
        assert x["sapan"] == (abs(x["sapma_yuzde"]) > 5)
    assert d["ozet"]["sapan"] == sum(x["sapan"] for x in d["satirlar"]) > 0
    assert ks.liste(s, sa, sb, TARIH, esik=Decimal(1000))["ozet"]["sapan"] == 0


def test_recete_eslemesi_degisen_alanlar(ortam):
    s, sa, sb = ortam
    satirlar = [r for x in ks.liste(s, sa, sb, TARIH)["satirlar"][:20] for r in ks.urun(s, x["kod"], sa, sb, TARIH)["recete"]]
    assert all(r["durum"] == "iki" for r in satirlar)   # deneme kitabı satır eklemez/çıkarmaz
    assert any("birim_fiyat" in r["degisen"] for r in satirlar)
    assert all(r["fark_tutar"] == r["b"]["tutar"] - r["a"]["tutar"] for r in satirlar)


def test_yalniz_bir_tarafta_olan_urun(ortam):
    """B'de reçetesi pasif olan ürün listede 'yalniz_a' görünür, detay 422 (hangi taraf hesaplanamadı)."""
    s, sa, sb = ortam
    kod = ks.liste(s, sa, sb, TARIH)["satirlar"][0]["kod"]
    u = hs.urun_getir(s, kod)
    r = s.query(m.Recete).filter_by(urun_id=u.id, senaryo_id=sb, aktif=True).one()
    r.aktif = False; s.flush()
    try:
        x = next(x for x in ks.liste(s, sa, sb, TARIH)["satirlar"] if x["kod"] == kod)
        assert x["durum"] == "yalniz_a" and x["alanlar"] is None and not x["sapan"]
        with pytest.raises(Exception) as e:
            ks.urun(s, kod, sa, sb, TARIH)
        assert "B (" in str(getattr(e.value, "mesaj", e.value))
    finally:
        r.aktif = True; s.flush()


def test_karsi_senaryo(ortam):
    s, sa, sb = ortam
    assert ks.karsi_senaryo(s, hs.senaryo_getir(s, sa)).id == sb
    assert ks.karsi_senaryo(s, hs.senaryo_getir(s, sb)).id == sa


def test_api_liste_onbellek_detay_karsi_xlsx(istemci, ortam):
    _, sa, sb = ortam
    q = f"a={sa}&b={sb}&tarih={TARIH}"
    r = istemci.get(f"/api/v1/kiyas?{q}")
    assert r.status_code == 200, r.text
    assert r.headers["X-Onbellek"] == "hesap" and istemci.get(f"/api/v1/kiyas?{q}").headers["X-Onbellek"] == "isabet"
    j = r.json()
    assert (j["a"]["tur"], j["b"]["tur"], j["esik"]) == ("fiyat_calismasi", "gerceklesen", "5")
    assert len(j["satirlar"]) == 67 and set(j["satirlar"][0]["alanlar"]) == set(ks.ALANLAR)
    kod = j["satirlar"][0]["kod"]
    d = istemci.get(f"/api/v1/kiyas/urun/{kod}?{q}")
    assert d.status_code == 200, d.text
    assert len(d.json()["ayristirma"]) == 7 and d.json()["recete"] and d.json()["giderler"] and d.json()["uretim"]
    assert istemci.get(f"/api/v1/kiyas/karsi?senaryo={sa}").json()["karsi"]["id"] == sb
    x = istemci.get(f"/api/v1/disa-aktar/butce-gerceklesen.xlsx?{q}&yalniz_sapan=true")
    assert x.status_code == 200
    ws = openpyxl.load_workbook(BytesIO(x.content)).active
    assert ws["A2"].value == "Kod" and ws.max_row - 2 == j["ozet"]["sapan"]


def test_api_hatalar(istemci, ortam):
    _, sa, sb = ortam
    r = istemci.get(f"/api/v1/kiyas?a={sa}&b={sa}")
    assert r.status_code == 422 and "iki farklı" in r.json()["mesaj"]
    assert istemci.get(f"/api/v1/kiyas?a={sa}&b=9999").status_code == 404
    assert istemci.get(f"/api/v1/kiyas/urun/YOK?a={sa}&b={sb}").status_code == 404
    assert istemci.get(f"/api/v1/kiyas?a={sa}&b={sb}&esik=-1").status_code == 422
