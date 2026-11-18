"""Direktör ekran denemesi için test verisini hazırlar (sezon senaryosu 0-3. bölümler, API üzerinden).

Çalışan bir test sunucusuna (varsayılan http://127.0.0.1:8048) bağlanır; sunucu UYDURMA test veritabanıyla açılmış olmalıdır:
    VERITABANI_URL=sqlite:///.../test-dongusu/deneme/11-18-2026-direktor-deneme.db GIRIS_ZORUNLU=1 uvicorn backend.uygulama:app --port 8048
Kullanım:
    .venv/Scripts/python scripts/11-18-2026-direktor-deneme-hazirla.py --db test-dongusu/deneme/11-18-2026-direktor-deneme.db
Gerçek veritabanına (veri/fiyat.db) karşı çalışmayı reddeder. Tüm kullanıcıların şifresi: Deneme2026!
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

import httpx

KOK = Path(__file__).resolve().parent.parent
EXCEL = KOK / "test-dongusu" / "excel"
ON = "11-16-2026-sezon-"
SIFRE = "Deneme2026!"


def dosya(ad: str, alan: str = "dosya"):
    yol = EXCEL / f"{ON}{ad}.xlsx"
    return {alan: (yol.name, yol.read_bytes())}


def bekle(r: httpx.Response, kod: int, adim: str) -> httpx.Response:
    if r.status_code != kod:
        raise SystemExit(f"{adim}: beklenen {kod}, gelen {r.status_code}: {r.text[:400]}")
    print(f"ok  {adim}")
    return r


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("--db", required=True)
    a.add_argument("--adres", default="http://127.0.0.1:8048")
    g = a.parse_args()
    db = Path(g.db).resolve()
    if db.name in ("fiyat.db", "test-dongusu.db") or "veri" in db.parts:
        raise SystemExit("Bu betik yalnız test-dongusu/deneme altındaki uydurma veritabanıyla çalışır.")

    def istemci() -> httpx.Client:
        return httpx.Client(base_url=g.adres, timeout=120)

    gd = istemci()
    gd.get("/api/v1/kimlik/ben")  # veritabanı oluşsun
    cikti = subprocess.run([sys.executable, str(KOK / "scripts" / "11-04-2026-ilk-genel-direktor.py"), "--db", str(db)],
                           capture_output=True, text=True, encoding="utf-8")
    gecici = re.search(r"geçici şifre\s*:\s*(\S+)", cikti.stdout)
    if not gecici:
        raise SystemExit("direktör hesabı açılamadı: " + cikti.stdout + cikti.stderr)
    bekle(gd.post("/api/v1/kimlik/giris", json={"kullanici_adi": "direktor", "sifre": gecici.group(1)}), 200, "0.2 direktör giriş")
    bekle(gd.post("/api/v1/kimlik/sifre", json={"eski_sifre": gecici.group(1), "yeni_sifre": SIFRE}), 200, "0.2 direktör şifre")
    kul = {}
    for kad, ad, rol in (("muhasebe1", "Muhasebe Bir", "muhasebe"), ("satinalma1", "Satın Alma Bir", "satin_alma"),
                         ("izleyici1", "İzleyici Bir", "izleyici")):
        bekle(gd.post("/api/v1/kullanicilar", json={"kullanici_adi": kad, "ad": ad, "rol": rol, "gecici_sifre": "Gecici2026!"}), 201, "0.3 " + kad)
        c = istemci()
        bekle(c.post("/api/v1/kimlik/giris", json={"kullanici_adi": kad, "sifre": "Gecici2026!"}), 200, "0.3 giriş " + kad)
        bekle(c.post("/api/v1/kimlik/sifre", json={"eski_sifre": "Gecici2026!", "yeni_sifre": SIFRE}), 200, "0.3 şifre " + kad)
        kul[rol] = c
    mu, sa = kul["muhasebe"], kul["satin_alma"]

    # 1. Sezon başı
    r = bekle(mu.post("/api/v1/import/excel-tam", files=dosya("fiyat-calismasi-butce"),
                      data={"sezon_ad": "2026-2027", "senaryo_ad": "Test Bütçe 2026-2027", "tur": "fiyat_calismasi"}), 200, "1.1 bütçe kitabı").json()
    butce = r["senaryo_id"]
    bekle(sa.post("/api/v1/aktarim/satin-alma/uygula", files=dosya("satin-alma-eksik-fiyatlar"),
                  data={"senaryo": butce, "gecerlilik_basi": "2026-09-01", "neden": "Sezon başı: eksik satın alma fiyatları"}), 200, "1.4 eksik fiyatlar")
    bekle(mu.post("/api/v1/satis-gecmisi/yukle", files=dosya("satis-gecmisi")), 200, "1.6 satış geçmişi")
    bekle(mu.post(f"/api/v1/liste-fiyatlari/yukle?senaryo={butce}", files=dosya("liste-fiyatlari-gecmis")), 200, "1.10 liste fiyatları")
    kop = {"receteler": True, "fiyatlar": True, "parametreler": True, "gider": True, "uretim": True, "fire_kurallari": True, "sablon": True}
    r = mu.post(f"/api/v1/senaryolar/{butce}/kopyala", json={"sezon_ad": "2026-2027", "ad": "Test Güncel 2026-2027", "tur": "fiyat_calismasi",
                                                           "neden": "Sezon içi çalışma kopyası", "kopyala": kop})
    if r.status_code == 422:  # şablon bayrağı yoksa onsuz dene
        kop.pop("sablon")
        r = mu.post(f"/api/v1/senaryolar/{butce}/kopyala", json={"sezon_ad": "2026-2027", "ad": "Test Güncel 2026-2027", "tur": "fiyat_calismasi",
                                                               "neden": "Sezon içi çalışma kopyası", "kopyala": kop})
    j = bekle(r, 201, "1.11 kopya").json()
    guncel = j["senaryo"]["id"] if "senaryo" in j else j.get("id")
    bekle(mu.post(f"/api/v1/senaryolar/{butce}/kilitle", json={"neden": "Bütçe sabitlendi (Eylül öngörüsü)"}), 200, "1.11 bütçe kilidi")

    # 2. Teklifler
    h1 = bekle(mu.post("/api/v1/urunler/03.99.001/hesaplar", json={"senaryo_id": guncel}), 201, "2.1 hesap").json()["id"]
    t = {}
    for ad, musteri, kar, notu in (("m1", "Test Market A.Ş.", "0.20", "1. tur"), ("m2", "Test Market A.Ş.", "0.17", "2. tur"),
                                   ("t1", "Test Toptan Ltd.", "0.20", "1. tur")):
        t[ad] = bekle(mu.post(f"/api/v1/hesaplar/{h1}/teklifler", json={"kar_orani": kar, "musteri": musteri, "notu": notu}), 201, "2.2 teklif " + ad).json()["id"]
    for tid, durum in ((t["m1"], "gonderildi"), (t["m1"], "red"), (t["m2"], "gonderildi"), (t["m2"], "kabul"), (t["t1"], "gonderildi")):
        bekle(mu.patch(f"/api/v1/teklifler/{tid}/durum", json={"durum": durum}), 200, f"2.3 durum {durum}")

    # 3. Kasım şoku
    bekle(sa.post("/api/v1/duzenleme-kilidi/ac", json={"senaryo_id": guncel, "sayfa": "fiyatlar"}), 201, "3.2 düzenleme kilidi")
    bekle(sa.post("/api/v1/import/fiyat-listesi/uygula", files=dosya("fiyat-listesi-kasim-revize"),
                  data={"senaryo": guncel, "gecerlilik_basi": "2026-11-01", "neden": "Kasım revize fiyat listesi: kavanoz 370 ml +%15"}), 200, "3.2 revize liste")
    bekle(mu.post(f"/api/v1/parametreler/kur.USD/degerler?senaryo={guncel}",
                  json={"deger": "45.36", "gecerlilik_basi": "2026-11-01", "neden": "Kasım: USD +%8 (42,00 -> 45,36)"}), 201, "3.5 USD kuru")
    bekle(mu.post("/api/v1/urunler/03.99.001/hesaplar", json={"senaryo_id": guncel}), 201, "3.8 ikinci hesap")
    print(f"Hazır: bütçe #{butce} (kilitli), güncel #{guncel}. Kullanıcılar: direktor, muhasebe1, satinalma1, izleyici1 · şifre {SIFRE}")


if __name__ == "__main__":
    main()
