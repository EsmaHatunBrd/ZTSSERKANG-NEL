# 18.11.2026 kopyası: veritabanı ve sonuç test-dongusu/deneme altında (veri/ kullanılmaz). Asıl betik: test-dongusu/kuru_kosu_sezon.py
"""Sezon senaryosunun KURU KOŞUSU (docs/test-dongusu/11-16-2026-sezon-senaryosu.md).

Senaryodaki yükleme ve sayı adımlarını API üzerinden (süreç içi TestClient, giriş zorunlu, rollerle) geçici bir veritabanında gerçekten
uygular; senaryodaki 'API ✓' sayılarını üretir ve üreticinin bağımsız hesabıyla (test-dongusu/11-16-2026-beklenen-sapmalar.json)
karşılaştırır. Özellikle Bütçe vs Gerçekleşen sapma ayrıştırması ürün ürün ve şirket toplamında kodla doğrulanır.

Geçici veritabanı: veri/11-16-2026-sezon-kuru-kosu.db (koşu sonunda silinir; veri/fiyat.db ve veri/test-dongusu.db'ye dokunulmaz).
Çıktı: test-dongusu/11-16-2026-sezon-kuru-kosu-sonuclari.json (adım -> değerler, kontroller, hatalar) ve ekrana özet.

Kullanım (proje kökünden; önce test-dongusu\\uret.py):  .venv\\Scripts\\python.exe test-dongusu\\kuru_kosu_sezon.py [--sakla]
"""
import io
import json
import os
import re
import subprocess
import sys
import traceback
from decimal import Decimal
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent.parent
DB = KOK / "test-dongusu" / "deneme" / "11-18-2026-sezon-kuru-kosu.db"
assert DB.name not in ("fiyat.db", "test-dongusu.db")
os.environ["VERITABANI_URL"] = f"sqlite:///{DB.as_posix()}"
os.environ["ONBELLEK_ISITMA"] = "0"
os.environ["GIRIS_ZORUNLU"] = "1"
sys.path.insert(0, str(KOK))
EXCEL = KOK / "test-dongusu" / "excel"
ON = "11-16-2026-sezon-"
BEK = json.loads((KOK / "test-dongusu" / "11-16-2026-beklenen-sapmalar.json").read_text(encoding="utf-8"))
SONUC: dict[str, dict] = {}
KONTROLLER: list[dict] = []
HATALAR: list[str] = []
S: dict = {}
D = Decimal


def temizle():
    for ek in ("", "-wal", "-shm"):
        Path(str(DB) + ek).unlink(missing_ok=True)
    for y in (DB.parent / "yedek").glob(f"*{DB.stem}*"):
        y.unlink()


temizle()
from fastapi.testclient import TestClient  # noqa: E402
from backend.uygulama import uygulama_olustur  # noqa: E402

APP = uygulama_olustur(giris_zorunlu=True)


def dosya(ad: str):
    yol = EXCEL / f"{ON}{ad}.xlsx"
    return {"dosya": (yol.name, yol.read_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}


def kaydet(adim: str, **degerler):
    SONUC.setdefault(adim, {}).update(degerler)
    print(f"[{adim}] " + json.dumps(degerler, ensure_ascii=False, default=str)[:1200])


def bekle(r, kod: int, adim: str):
    if r.status_code != kod:
        HATALAR.append(f"{adim}: HTTP {r.status_code} (beklenen {kod}) {r.text[:400]}")
        print(f"!!! {adim}: HTTP {r.status_code} {r.text[:400]}")
    return r


def kontrol(ad: str, api, beklenen, tol="0.000005") -> bool:
    """api ile beklenen sayıyı karşılaştırır (|fark| <= tol); sonucu KONTROLLER'e yazar."""
    try:
        a, b = D(str(api)), D(str(beklenen))
        gecti = abs(a - b) <= D(tol)
        k = {"ad": ad, "api": str(a), "beklenen": str(b), "fark": str(a - b), "gecti": gecti}
    except Exception as e:  # noqa: BLE001
        gecti = False
        k = {"ad": ad, "api": str(api), "beklenen": str(beklenen), "hata": repr(e), "gecti": False}
    KONTROLLER.append(k)
    if not gecti:
        print(f"XXX KONTROL TUTMADI: {k}")
    return gecti


def esit(ad: str, api, beklenen) -> bool:
    gecti = api == beklenen
    KONTROLLER.append({"ad": ad, "api": api, "beklenen": beklenen, "gecti": gecti})
    if not gecti:
        print(f"XXX KONTROL TUTMADI: {ad}: {api!r} != {beklenen!r}")
    return gecti


def tl(x, n=2) -> str | None:
    return None if x is None else str(D(str(x)).quantize(D(1).scaleb(-n)))


def adim(ad):
    def sar(fn):
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            HATALAR.append(f"{ad}: {type(e).__name__}: {e}")
            traceback.print_exc()
        return fn
    return sar


def istemci() -> TestClient:
    return TestClient(APP, base_url="http://testserver")


# ------------------------------------------------------------------ 0. hazırlık: kullanıcılar ve roller
gd = istemci()
bekle(gd.get("/api/v1/kimlik/ben"), 401, "0 ilk istek (veritabanı oluşur)")
cikti = subprocess.run([sys.executable, str(KOK / "scripts" / "11-04-2026-ilk-genel-direktor.py"), "--db", str(DB)],
                       capture_output=True, text=True, encoding="utf-8")
gecici = re.search(r"geçici şifre\s*:\s*(\S+)", cikti.stdout)
SIFRE = "TestSifre2026!"
bekle(gd.post("/api/v1/kimlik/giris", json={"kullanici_adi": "direktor", "sifre": gecici.group(1)}), 200, "0.2 giriş")
bekle(gd.post("/api/v1/kimlik/sifre", json={"eski_sifre": gecici.group(1), "yeni_sifre": SIFRE}), 200, "0.2 şifre")
KUL = {"genel_direktor": gd}
for kad, ad, rol in (("muhasebe1", "Test Muhasebe", "muhasebe"), ("satinalma1", "Test Satın Alma", "satin_alma"),
                     ("izleyici1", "Test İzleyici", "izleyici")):
    bekle(gd.post("/api/v1/kullanicilar", json={"kullanici_adi": kad, "ad": ad, "rol": rol, "gecici_sifre": "Gecici2026!"}), 201, "0.3 kullanıcı")
    c = istemci()
    bekle(c.post("/api/v1/kimlik/giris", json={"kullanici_adi": kad, "sifre": "Gecici2026!"}), 200, "0.3 giriş " + kad)
    bekle(c.post("/api/v1/kimlik/sifre", json={"eski_sifre": "Gecici2026!", "yeni_sifre": SIFRE}), 200, "0.3 şifre " + kad)
    KUL[rol] = c
kaydet("0.3 kullanıcılar", kullanici=[(k["kullanici_adi"], k["rol"]) for k in gd.get("/api/v1/kullanicilar").json()["kayitlar"]])
mu, sa, iz = KUL["muhasebe"], KUL["satin_alma"], KUL["izleyici"]


# ------------------------------------------------------------------ yardımcılar
def genel_bakis(sen: int, c=None) -> dict:
    j = bekle((c or mu).get(f"/api/v1/urunler?senaryo={sen}&boyut=100&yenile=true"), 200, "genel bakış").json()
    return {k["kod"]: k for k in j["kayitlar"]}


def maliyetler(sen: int) -> dict[str, str]:
    return {k: v["maliyet_tl"] for k, v in genel_bakis(sen).items()}


def tutarlilik(sen: int) -> dict:
    j = bekle(mu.get(f"/api/v1/tutarlilik?senaryo={sen}&yenile=true"), 200, "tutarlılık").json()
    return {"ozet": j["ozet"], "kontroller": {k["kod"]: (k["durum"], k["sayi"], [o["etiket"] for o in k["ogeler"]][:6]) for k in j["kontroller"]}}


def al(yol: str, c=None):
    return bekle((c or mu).get(yol), 200, yol).json()


def kur_riski(sen: int, oran: str = "0.10") -> dict:
    return al(f"/api/v1/analiz/kur-riski?senaryo={sen}&oran={oran}")


def yonetim(sen: int, c=None) -> dict:
    return al(f"/api/v1/yonetim/ozet?senaryo={sen}&yenile=true", c)


def karlilik_toplam(sen: int) -> tuple[D, list]:
    j = al(f"/api/v1/analiz/karlilik?senaryo={sen}")
    return sum((D(k["yillik_kar"]) for k in j["kayitlar"] if k["yillik_kar"] is not None), D(0)), j


def xlsx_metni(icerik: bytes) -> str:
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(icerik), read_only=True)
    parca = []
    for ws in wb.worksheets[:3]:
        for satir in ws.iter_rows(max_row=4, values_only=True):
            parca += [str(x) for x in satir if x is not None]
    return " | ".join(parca)[:600]


def urun_bekleneni(kod: str) -> dict:
    return BEK["urunler"][kod]


# ------------------------------------------------------------------ 1. Sezon başı: öngörü
@adim("1")
def _():
    r = bekle(mu.post("/api/v1/import/excel-tam", files=dosya("fiyat-calismasi-butce"),
                      data={"sezon_ad": "2026-2027", "senaryo_ad": "Test Bütçe 2026-2027", "tur": "fiyat_calismasi"}), 200, "1.1 bütçe kitabı").json()
    S["butce"] = r["senaryo_id"]
    kaydet("1.1 bütçe kitabı içe aktarma", **{k: r[k] for k in ("senaryo_id", "malzeme", "fiyat", "havuz", "ambalaj", "urun", "recete", "parametre",
                                                               "atlanan", "uyarilar", "urun_parametre_farklari", "kapasite", "revize", "satis_notu")})
    p = al(f"/api/v1/parametreler?senaryo={S['butce']}")
    kaydet("1.2 parametreler", **{k: p.get(k) for k in ("enflasyon", "satis_kar", "kur.USD", "kur.EUR", "kur.GBP", "kur.CHF", "faiz.TL", "stok_ay.TL",
                                                         "teklif_kar.1", "teklif_kar.2", "teklif_kar.3", "vardiya_saati")})
    t = tutarlilik(S["butce"])
    kaydet("1.3 veri kontrolü (önce)", **t)
    S["vk_once"] = t
    gb = genel_bakis(S["butce"])
    kaydet("1.3 genel bakış (fiyatsız iki malzemeyle)", maliyet={k: tl(v["maliyet_tl"]) for k, v in gb.items()})
    # Satın alma eksik fiyatları tamamlar: önce Veri Aktar › Satın alma fiyat listesi (aktarım), olmazsa tek tek fiyat girişi
    on = sa.post("/api/v1/aktarim/satin-alma/onizle", files=dosya("satin-alma-eksik-fiyatlar"), data={"senaryo": S["butce"]})
    kaydet("1.4 satın alma aktarım önizleme (satinalma1)", http=on.status_code,
           yanit={k: on.json().get(k) for k in ("yeni_malzeme", "fiyat_yeni", "fiyat_degisen", "ayni", "hatali")} if on.status_code == 200 else on.json())
    uy = sa.post("/api/v1/aktarim/satin-alma/uygula", files=dosya("satin-alma-eksik-fiyatlar"),
                 data={"senaryo": S["butce"], "gecerlilik_basi": "2026-09-01", "neden": "Sezon başı: eksik satın alma fiyatları"})
    kaydet("1.4 satın alma aktarım uygula (satinalma1)", http=uy.status_code, yanit=uy.json())
    S["aktarim_satinalma_http"] = uy.status_code
    if uy.status_code != 200:
        for kod, f in (("99.11.010", "68.00"), ("99.20.015", "0.35")):
            r = bekle(sa.post(f"/api/v1/malzemeler/{kod}/fiyatlar?senaryo={S['butce']}",
                              json={"fiyat": f, "gecerlilik_basi": "2026-09-01", "neden": "Sezon başı: eksik satın alma fiyatı"}), 201, f"1.4 tek fiyat {kod}")
            kaydet(f"1.4 tek fiyat girişi {kod} (satinalma1)", http=r.status_code)
    t = tutarlilik(S["butce"])
    kaydet("1.5 veri kontrolü (sonra)", **t)
    gb = genel_bakis(S["butce"])
    kaydet("1.6 genel bakış", maliyet={k: tl(v["maliyet_tl"]) for k, v in gb.items()}, satis={k: tl(v["satis_tl"]) for k, v in gb.items()})
    for kod, v in gb.items():
        kontrol(f"1.6 bütçe birim maliyet {kod}", v["maliyet_tl"], urun_bekleneni(kod)["butce"]["maliyet_tl"])
    h = bekle(mu.post("/api/v1/urunler/03.99.001/hesapla", json={"senaryo_id": S["butce"]}), 200, "hesapla").json()
    kaydet("1.6 ürün maliyeti 03.99.001", toplamlar={a: tl(v, 4) for a, v in h["toplamlar"].items() if isinstance(v, (str, int, float))})
    r = bekle(mu.post("/api/v1/satis-gecmisi/yukle", files={"dosya": (f"{ON}satis-gecmisi.xlsx", (EXCEL / f"{ON}satis-gecmisi.xlsx").read_bytes())}),
              200, "satış").json()
    kaydet("1.7 satış geçmişi", **r)
    y = yonetim(S["butce"])
    kaydet("1.8 yönetim özeti (bütçe)", marj=y["marj"], maliyet_yapisi={k: (tl(v["toplam_tl"]), tl(v["pay_yuzde"])) for k, v in y["maliyet_yapisi"]["kalemler"].items()},
           kur=dict(doviz_payi_yuzde=tl(y["kur_riski"]["doviz_payi_yuzde"], 3), yillik_etki=tl(y["kur_riski"]["yillik_etki_tl"]),
                    yillik_maliyet=tl(y["kur_riski"]["yillik_maliyet_tl"])), veri_kontrolu=y["veri_kontrolu"], hedef_alti=y["hedef_alti"]["toplam"])
    kontrol("1.8 bütçe yıllık maliyet (kur riski kartı)", y["kur_riski"]["yillik_maliyet_tl"], BEK["toplam"]["butce_yillik_maliyet_tl"], "0.01")
    k = kur_riski(S["butce"])
    kaydet("1.8 kur riski %10 (bütçe)", ozet={a: tl(v, 4) for a, v in k["ozet"].items()},
           para_birimleri=[(x["para_birimi"], tl(x["yillik_etki"])) for x in k["para_birimleri"]])
    toplam, j = karlilik_toplam(S["butce"])
    S["kar_butce"] = toplam
    kaydet("1.9 kârlılık haritası (bütçe)", ozet=j["ozet"], esik_adet=j["esik_adet"], yillik_kar_toplam=tl(toplam),
           kayitlar=[(x["kod"], x["bolge"], tl(D(x["marj"]) * 100), tl(x["yillik_kar"])) for x in j["kayitlar"]])
    kontrol("1.9 yıllık kâr toplamı (bütçe, geçen yıl fiyatıyla)", toplam, BEK["sok"]["karlilik_yillik_kar_butce_tl"], "0.05")
    j = al(f"/api/v1/analiz/onemli-malzemeler?senaryo={S['butce']}")
    kaydet("1.10 önemli malzemeler", toplam=tl(j["toplam_tutar_tl"]), esik_icindeki=j["esik_icindeki_sayi"],
           ilk=[(x["kod"], x["ad"], x["pay_yuzde"], x["kumulatif_yuzde"], tl(x["yillik_tutar_tl"])) for x in j["satirlar"][:10]])
    r = bekle(mu.post(f"/api/v1/liste-fiyatlari/yukle?senaryo={S['butce']}",
                      files={"dosya": (f"{ON}liste-fiyatlari-gecmis.xlsx", (EXCEL / f"{ON}liste-fiyatlari-gecmis.xlsx").read_bytes())}), 200, "liste").json()
    j = al(f"/api/v1/liste-calismasi?senaryo={S['butce']}&pazar=yurtici")
    kaydet("1.11 liste çalışması", yukleme=r, ozet=j.get("ozet"),
           kayitlar=[(k_.get("kod"), k_.get("yeni_liste"), k_.get("onceki_liste"), tl(D(k_["liste_artis"]) * 100) if k_.get("liste_artis") else None,
                      tl(D(k_["maliyet_artis"]) * 100) if k_.get("maliyet_artis") else None) for k_ in j.get("kayitlar", [])])
    # Sabitle: önce çalışma kopyası (Güncel), sonra bütçeyi kilitle
    r = bekle(mu.post(f"/api/v1/senaryolar/{S['butce']}/kopyala", json={
        "sezon_ad": "2026-2027", "ad": "Test Güncel 2026-2027", "tur": "fiyat_calismasi", "neden": "Sezon içi çalışma kopyası",
        "kopyala": {"receteler": True, "fiyatlar": True, "parametreler": True, "gider": True, "uretim": True, "fire_kurallari": True}}), 201, "kopyala").json()
    S["guncel"] = r["senaryo"]["id"] if "senaryo" in r else r.get("id")
    kaydet("1.12 kopya (Test Güncel)", yanit=r)
    r = bekle(mu.post(f"/api/v1/senaryolar/{S['butce']}/kilitle", json={"neden": "Bütçe sabitlendi (Eylül öngörüsü)"}), 200, "kilitle")
    yaz = mu.post(f"/api/v1/malzemeler/99.20.001/fiyatlar?senaryo={S['butce']}", json={"fiyat": "7", "gecerlilik_basi": "2026-11-01", "neden": "x"})
    kaydet("1.12 bütçe kilitli", http=r.status_code, kilitliye_yazma=yaz.status_code, mesaj=yaz.json().get("mesaj"))
    gg = maliyetler(S["guncel"])
    for kod, v in gg.items():
        kontrol(f"1.12 güncel = bütçe {kod}", v, urun_bekleneni(kod)["butce"]["maliyet_tl"])


# ------------------------------------------------------------------ 2. Teklif dönemi (Güncel)
@adim("2")
def _():
    sen = S["guncel"]
    r = bekle(mu.post("/api/v1/urunler/03.99.001/hesaplar", json={"senaryo_id": sen}), 201, "hesap kaydet").json()
    S["hesap_once"] = r["id"]
    kaydet("2.1 hesap kaydı (şok öncesi)", **r)
    t = {}
    for ad, musteri, kar, notu in (("m1", "Test Market A.Ş.", "0.20", "1. tur"), ("m2", "Test Market A.Ş.", "0.17", "2. tur"),
                                   ("t1", "Test Toptan Ltd.", "0.20", "1. tur")):
        x = bekle(mu.post(f"/api/v1/hesaplar/{S['hesap_once']}/teklifler", json={"kar_orani": kar, "musteri": musteri, "notu": notu}), 201, "teklif").json()
        t[ad] = x
    S["teklif"] = {k: v["id"] for k, v in t.items()}
    kaydet("2.2 teklifler", **{k: {a: v.get(a) for a in ("id", "tur_no", "musteri", "kar_orani", "fiyat_tl", "fiyat_usd", "durum")} for k, v in t.items()})
    m = D(urun_bekleneni("03.99.001")["butce"]["maliyet_tl"])
    kontrol("2.2 teklif Market tur 1 (%20) TL", t["m1"]["fiyat_tl"], m * D("1.20"), "0.0001")
    kontrol("2.2 teklif Market tur 2 (%17) TL", t["m2"]["fiyat_tl"], m * D("1.17"), "0.0001")
    for tid, durum in ((t["m1"]["id"], "gonderildi"), (t["m1"]["id"], "red"), (t["m2"]["id"], "gonderildi"), (t["m2"]["id"], "kabul"),
                       (t["t1"]["id"], "gonderildi")):
        bekle(mu.patch(f"/api/v1/teklifler/{tid}/durum", json={"durum": durum}), 200, f"durum {durum}")
    kaydet("2.3 süzgeçler", **{str(d): al(f"/api/v1/teklifler?senaryo={sen}" + (f"&durum={d}" if d else "")).get("toplam")
                                for d in (None, "kabul", "red", "gonderildi", "taslak")})
    r = mu.post("/api/v1/onay-ciktisi/fiyat", json={"senaryo_id": sen, "tur": "excel"})
    kaydet("2.4 rapor (Güncel, kilitsiz) Excel", http=r.status_code, bayt=len(r.content), basliklar=xlsx_metni(r.content) if r.status_code == 200 else r.text[:300])
    esit("2.4 kilitsiz çalışmada rapor TASLAK", "TASLAK" in xlsx_metni(r.content), True)


# ------------------------------------------------------------------ 3. Sezon içi şok (Güncel)
@adim("3")
def _():
    sen = S["guncel"]
    once = maliyetler(sen)
    z = al(f"/api/v1/analiz/zam-etkisi?senaryo={sen}&malzeme=99.20.001&oran=0.15")
    kaydet("3.1 zam etkisi kavanoz %15 (öngörü)", malzeme=z["malzeme"], ozet=z["ozet"],
           kayitlar=[(x["kod"], tl(x["maliyet_once"]), tl(x["maliyet_sonra"]), tl(x["fark_tl"], 4), tl(D(x["mevcut_fiyatla_kar"]) * 100)) for x in z["kayitlar"]])
    for x in z["kayitlar"]:
        kontrol(f"3.1 zam etkisi {x['kod']}", x["fark_tl"], urun_bekleneni(x["kod"])["guncel_sok_sonrasi"]["kavanoz_zammi_tl"])
    kl = sa.post("/api/v1/duzenleme-kilidi/ac", json={"senaryo_id": sen, "sayfa": "fiyatlar"})
    kaydet("3.2 düzenleme kilidi (satinalma1)", http=kl.status_code)
    on = sa.post("/api/v1/import/fiyat-listesi", files=dosya("fiyat-listesi-kasim-revize"), data={"senaryo": sen, "gecerlilik_basi": "2026-11-01"})
    kaydet("3.2 fiyat listesi önizleme (satinalma1)", http=on.status_code,
           **({"degisen": on.json()["degisen"], "yeni": on.json()["yeni"], "ayni": on.json()["ayni"], "revize": on.json()["revize"],
               "hatali": on.json()["hatali"]} if on.status_code == 200 else {"yanit": on.text[:300]}))
    uy = sa.post("/api/v1/import/fiyat-listesi/uygula", files=dosya("fiyat-listesi-kasim-revize"),
                 data={"senaryo": sen, "gecerlilik_basi": "2026-11-01", "neden": "Kasım revize fiyat listesi: kavanoz 370 ml +%15"})
    kaydet("3.2 fiyat listesi uygula (satinalma1)", http=uy.status_code, yanit=uy.json())
    sonra = maliyetler(sen)
    kaydet("3.3 genel bakış kavanoz sonrası", maliyet=[(k, tl(once[k]), tl(sonra[k]), tl(D(sonra[k]) - D(once[k]), 4)) for k in once])
    for k in once:
        kontrol(f"3.3 kavanoz zammı gerçekleşti {k}", D(sonra[k]) - D(once[k]), urun_bekleneni(k)["guncel_sok_sonrasi"]["kavanoz_zammi_tl"])
    k8 = kur_riski(sen, "0.08")
    y8 = al(f"/api/v1/analiz/ya-olursa?senaryo={sen}&kur=0.08")
    kaydet("3.4 ya olursa kur +%8 (tüm dövizler)", ozet=y8["ozet"], kayitlar=[(x["kod"], tl(x["fark_tl"], 4)) for x in y8["kayitlar"]])
    for x in y8["kayitlar"]:
        kontrol(f"3.4 ya olursa kur +8 {x['kod']}", x["fark_tl"], urun_bekleneni(x["kod"])["guncel_sok_sonrasi"]["tum_kurlar_yuzde8_tl"])
    usd = next(x for x in k8["para_birimleri"] if x["para_birimi"] == "USD")
    kaydet("3.4 kur riski %8", ozet={a: tl(v, 4) for a, v in k8["ozet"].items()}, para_birimleri=[(x["para_birimi"], tl(x["yillik_etki"])) for x in k8["para_birimleri"]])
    kontrol("3.4 kur riski %8 USD yıllık etki", usd["yillik_etki"], BEK["sok"]["usd_yillik_tl"], "0.01")
    once = sonra
    r = bekle(mu.post(f"/api/v1/parametreler/kur.USD/degerler?senaryo={sen}",
                      json={"deger": "45.36", "gecerlilik_basi": "2026-11-01", "neden": "Kasım: USD +%8 (42,00 -> 45,36)"}), 201, "kur").json()
    sonra = maliyetler(sen)
    kaydet("3.5 USD kuru güncellendi", yanit=r, maliyet=[(k, tl(once[k]), tl(sonra[k]), tl(D(sonra[k]) - D(once[k]), 4)) for k in once])
    for k in once:
        kontrol(f"3.5 USD +%8 etkisi {k}", D(sonra[k]) - D(once[k]), urun_bekleneni(k)["guncel_sok_sonrasi"]["usd_artisi_tl"])
        kontrol(f"3.5 güncel birim maliyet {k}", sonra[k], urun_bekleneni(k)["guncel_sok_sonrasi"]["maliyet_tl"])
    y = yonetim(sen)
    kaydet("3.6 yönetim özeti (güncel)", marj=y["marj"], yillik_maliyet=tl(y["kur_riski"]["yillik_maliyet_tl"]),
           acik_teklifler={a: y["teklifler"][a] for a in ("toplam", "durumlar", "acik_sayi", "acik_toplam_tl", "en_eski_acik")})
    kontrol("3.6 güncel yıllık maliyet", y["kur_riski"]["yillik_maliyet_tl"], BEK["toplam"]["guncel_yillik_maliyet_tl"], "0.01")
    kontrol("3.6 şokun yıllık etkisi", D(y["kur_riski"]["yillik_maliyet_tl"]) - D(BEK["toplam"]["butce_yillik_maliyet_tl"]),
            BEK["sok"]["toplam_yillik_tl"], "0.01")
    toplam, j = karlilik_toplam(sen)
    kaydet("3.7 kârlılık haritası (güncel)", ozet=j["ozet"], yillik_kar_toplam=tl(toplam), dusus=tl(S["kar_butce"] - toplam),
           kayitlar=[(x["kod"], x["bolge"], tl(D(x["marj"]) * 100), tl(x["yillik_kar"])) for x in j["kayitlar"]])
    kontrol("3.7 yıllık kâr toplamı (güncel)", toplam, BEK["sok"]["karlilik_yillik_kar_guncel_tl"], "0.05")
    h = al(f"/api/v1/analiz/hedef-fiyat?senaryo={sen}&marj=0.20")
    kaydet("3.8 marjı koruyan fiyat %20", ozet=h["ozet"],
           kayitlar=[(x["kod"], tl(x["maliyet"]), tl(x["gecen_yil_fiyat"]), tl(x["hedef_fiyat"]), tl(D(x["gereken_zam"]) * 100) if x["gereken_zam"] else None,
                      x["liste_fiyati_yurtici"], tl(x["yillik_ek_gelir"])) for x in h["kayitlar"]])
    r = bekle(mu.post("/api/v1/urunler/03.99.001/hesaplar", json={"senaryo_id": sen}), 201, "hesap kaydet 2").json()
    S["hesap_sonra"] = r["id"]
    k = al(f"/api/v1/arsiv/kiyas?hesap_a={S['hesap_once']}&hesap_b={S['hesap_sonra']}")
    kaydet("3.9 geçmiş hesaplar kıyas 03.99.001", yanit=json.dumps(k, ensure_ascii=False)[:1500])
    f = al(f"/api/v1/analiz/fiyat-egilimi?senaryo={sen}")
    kaydet("3.10 fiyat eğilimi", ozet={a: f.get(a) for a in ("ay", "tarih", "pencere_basi", "enflasyon_yuzde")},
           ilk=[(x["kod"], x["ilk_fiyat"], x["son_fiyat"], x["degisim_yuzde"], x["yillik_yuzde"], x["enflasyonu_asiyor"], x["kayit_sayisi"])
                for x in f["satirlar"][:4]])
    yeni = D(sonra["03.99.001"])
    kaydet("3.11 açık teklif eskidi mi", teklif_toptan_tl=tl(D(urun_bekleneni("03.99.001")["butce"]["maliyet_tl"]) * D("1.2"), 4),
           bugunku_maliyetle_ayni_kar_tl=tl(yeni * D("1.2"), 4), teklifte_kalan_kar=tl((D(urun_bekleneni("03.99.001")["butce"]["maliyet_tl"]) * D("1.2") / yeni - 1) * 100, 2))


# ------------------------------------------------------------------ 4. Her ay kapanış (SMM)
@adim("4")
def _():
    r = bekle(mu.post("/api/v1/smm/donemler/yukle", files=dosya("smm-ekim-2026"), data={"yil": 2026, "ay": 10}), 200, "smm yükle").json()
    E = S["ekim"] = r["id"]
    kaydet("4.1 Ekim yükleme", **{k: r[k] for k in ("ad", "kalem_sayisi", "finansman", "excel_kontrol", "recete_kaynagi")})
    v = al(f"/api/v1/smm/donemler/{E}/veri")
    kaydet("4.2 kontrol listesi", kaynaklar=[(k["kaynak"], k["yuklendi"], k["dolu"]) for k in v["kaynaklar"]], eksik=v["eksik"], donem_basi=v["donem_basi"],
           ayarlar=v["ayarlar"])
    st = al(f"/api/v1/smm/donemler/{E}/stok")
    kaydet("4.3 stok ve envanter", toplamlar=st["toplamlar"], kontrol_sayisi=st["kontrol_sayisi"], turler=[(t["tur"], t["kalem"]) for t in st["turler"]],
           ornek={k["kod"]: {a: k[a] for a in ("ortalama_fiyat", "sarf_miktar", "sarf_tutar", "sayim_miktar")} for k in st["kayitlar"]
                  if k["kod"] in ("99.10.001", "99.20.001")})
    kontrol("4.3 kavanoz Ekim ortalama fiyat", next(k["ortalama_fiyat"] for k in st["kayitlar"] if k["kod"] == "99.20.001"),
            BEK["smm"]["kavanoz_ortalama_fiyat"]["ekim"], "0.0001")
    for a in (20, 40, 50):
        j = al(f"/api/v1/smm/donemler/{E}/uretim?asama={a}")
        kaydet(f"4.4 üretim {a}", kayitlar=[(x["kod"], tl(x["uretim_miktar"]), tl(x["malzeme"], 4), tl(x["iscilik"], 4), tl(x["gug"], 4), tl(x["fire"], 4),
                                             tl(x["birim_maliyet"], 4)) for x in j["kayitlar"]],
               **({"dagitim": {k_: j["dagitim"][k_] for k_ in ("dagitilan", "mizan_720", "mizan_730", "dagitilmayan")}} if a == 50 else {}))
        if a == 50:
            S["ekim_birim"] = {x["kod"]: x["birim_maliyet"] for x in j["kayitlar"]}
            kontrol("4.4 Ekim dağıtılan", j["dagitim"]["dagitilan"], BEK["smm"]["dagitilan"], "0.01")
            kontrol("4.4 Ekim dağıtılmayan", j["dagitim"]["dagitilmayan"], BEK["smm"]["dagitilmayan"], "0.01")
    g = mu.get(f"/api/v1/smm/donemler/{E}/gider-dagitimi")
    kaydet("4.5 gider dağıtımı bölümü", http=g.status_code, yanit=json.dumps({k_: v_ for k_, v_ in g.json().items() if k_ not in ("donem", "urunler_ilk20")},
                                                                             ensure_ascii=False)[:1500])
    sf = al(f"/api/v1/smm/donemler/{E}/sarf-farki")
    kaydet("4.6 sarf farkı", toplamlar=sf["toplamlar"], ilk=[(x["kod"], tl(x["recete_sarf"]), tl(x["stok_sarf"]), tl(x["fark"]), tl(x["fark_tutar"]))
                                                             for x in sf["kayitlar"][:5]])
    so = mu.get(f"/api/v1/smm/donemler/{E}/sarf-farki/ozet")
    kaydet("4.6 en büyük farklar", http=so.status_code, yanit=json.dumps({k_: v_ for k_, v_ in so.json().items() if k_ != "donem"}, ensure_ascii=False)[:1200])
    ilk = sf["kayitlar"][0]
    esit("4.6 sarf farkı en büyük kalem", ilk["kod"], "99.10.001")
    kontrol("4.6 hıyar sarf farkı tutarı", abs(D(ilk["fark_tutar"])), BEK["smm"]["sayim_farki"]["tutar_tl"], "1.00")
    o = al(f"/api/v1/smm/donemler/{E}/ozet")
    kaydet("4.7 SMM özeti Ekim", smm=tl(o["smm"]), uretim=tl(o["uretim_maliyeti"]), uretilen=tl(o["uretilen"]), ilk_madde=tl(o["ilk_madde"]),
           donem_sonu_stok=o["donem_sonu_stok"], mizan_kiyas=o["mizan_kiyas"], fis=[(f["hesap"], tl(f["borc"]), tl(f["alacak"])) for f in o["fis"]],
           fis_borc=tl(o["fis_borc"]), fis_alacak=tl(o["fis_alacak"]))
    S["stok_mizani_ayari_ekim"] = {m_["hesap"]: m_["sayim"] for m_ in o["mizan_kiyas"]}
    b = al(f"/api/v1/smm/donemler/{E}/butce-kiyas?senaryo={S['butce']}")
    kaydet("4.8 bütçe kıyası Ekim", ozet=b["ozet"], kayitlar=[(x["kod"], tl(x["butce_maliyet_tl"], 4), tl(x["fiili_birim_maliyet_tl"], 4), tl(x["fark_tl"], 4),
                                                              tl(D(x["fark_yuzde"]) * 100) if x["fark_yuzde"] else None, x["fiili_dokum"], x["butce_dokum"])
                                                             for x in b["kayitlar"]])
    for x in b["kayitlar"]:
        kontrol(f"4.8 bütçe kıyası bütçe tarafı {x['kod']}", x["butce_maliyet_tl"], BEK["smm"]["kasim_fiyat_etkisi"][x["kod"]]["butce_toplam_birim_maliyet_tl"])
    S["ekim_fark"] = {x["kod"]: x["fark_tl"] for x in b["kayitlar"]}
    j = al(f"/api/v1/smm/donemler/{E}/urun/03.99.001/maliyet-karti")
    kaydet("4.9 ürün maliyet kartı 03.99.001", birim=tl(j["birim_maliyet"], 4), asamalar=[(a["asama"], a["kod"], tl(a["malzeme"], 4), tl(a["iscilik"], 4),
                                                                                         tl(a["gug"], 4), tl(a["fire"], 4), tl(a["birim_maliyet"], 4)) for a in j["asamalar"]])
    r = mu.put(f"/api/v1/smm/donemler/{E}/kilit", json={"kilitli": True})
    kaydet("4.10 Ekim kapat", http=r.status_code, yanit=r.json() if r.status_code != 200 else {"kilitli": r.json()["kilitli"]})
    kaydet("4.10 kilitliye yazma", http=mu.patch(f"/api/v1/smm/donemler/{E}/stok/99.20.001", json={"neden": "x", "sayim_miktar": "1"}).status_code)
    r = mu.post("/api/v1/onay-ciktisi/smm", json={"donem_id": E, "tur": "excel"})
    kaydet("4.10 SMM raporu (kilitli Ekim)", http=r.status_code, bayt=len(r.content))
    esit("4.10 kilitli dönemde SMM raporu KESİN", "KESİN" in xlsx_metni(r.content), True)
    kaydet("4.11 Ekim kilidi aç (Muhasebe)", http=mu.put(f"/api/v1/smm/donemler/{E}/kilit", json={"kilitli": False}).status_code)
    r = bekle(mu.post("/api/v1/smm/receteler/onizle", files=dosya("smm-receteler-canias")), 200, "reçete önizle").json()
    kaydet("4.12 Canias önizleme", **{k_: r[k_] for k_ in ("satir_sayisi", "urun_sayisi", "asama", "alternatifli_urun", "eklenecek_urun")})
    bekle(mu.post("/api/v1/smm/receteler/yukle", files=dosya("smm-receteler-canias")), 200, "reçete yükle")
    r = bekle(mu.post("/api/v1/smm/donemler", json={"yil": 2026, "ay": 11}), 201, "yeni dönem").json()
    K = S["kasim"] = r["id"]
    kaydet("4.13 Kasım yeni dönem", ad=r["ad"], kalem=r["kalem_sayisi"], devir=r["devir"], recete_kaynagi=r["recete_kaynagi"])
    for kaynak, ad in (("alim", "alim-satis"), ("iade", "iadeler"), ("uretim", "uretim"), ("sayim", "sayim"), ("sahit", "sahit-numune"),
                       ("gider_mizan", "gider-mizan"), ("stok_mizan", "stok-mizan")):
        r = bekle(mu.post(f"/api/v1/smm/donemler/{K}/veri/{kaynak}", files=dosya(f"smm-kasim-2026-{ad}")), 200, f"kasım {kaynak}").json()
        kaydet(f"4.14 Kasım {kaynak}", dolu=next(x["dolu"] for x in r["kaynaklar"] if x["kaynak"] == kaynak), eksik=r["eksik"])
    st = al(f"/api/v1/smm/donemler/{K}/stok")
    kontrol("4.15 kavanoz Kasım ortalama fiyat", next(k_["ortalama_fiyat"] for k_ in st["kayitlar"] if k_["kod"] == "99.20.001"),
            BEK["smm"]["kavanoz_ortalama_fiyat"]["kasim"], "0.0001")
    j = al(f"/api/v1/smm/donemler/{K}/uretim?asama=50")
    S["kasim_birim"] = {x["kod"]: x["birim_maliyet"] for x in j["kayitlar"]}
    kaydet("4.15 Kasım üretim 50", dagitim={k_: j["dagitim"][k_] for k_ in ("dagitilan", "mizan_720", "mizan_730", "dagitilmayan")},
           birim=[(x["kod"], tl(x["birim_maliyet"], 4), tl(D(x["birim_maliyet"]) - D(S["ekim_birim"][x["kod"]]), 4),
                   BEK["smm"]["kasim_fiyat_etkisi"][x["kod"]]["fiyat_etkisi_tl"]) for x in j["kayitlar"]])
    for x in j["kayitlar"]:
        kontrol(f"4.15 Kasım-Ekim birim maliyet farkı = fiyat etkisi {x['kod']}", D(x["birim_maliyet"]) - D(S["ekim_birim"][x["kod"]]),
                BEK["smm"]["kasim_fiyat_etkisi"][x["kod"]]["fiyat_etkisi_tl"], "0.01")
    o = al(f"/api/v1/smm/donemler/{K}/ozet")
    kaydet("4.16 SMM özeti Kasım", smm=tl(o["smm"]), uretim=tl(o["uretim_maliyeti"]), ilk_madde=tl(o["ilk_madde"]), donem_sonu_stok=o["donem_sonu_stok"],
           mizan_kiyas=o["mizan_kiyas"])
    S["stok_mizani_ayari_kasim"] = {m_["hesap"]: m_["sayim"] for m_ in o["mizan_kiyas"]}
    kaydet("4.16 Kasım devir durumu", **al(f"/api/v1/smm/donemler/{K}/devir-durumu"))
    b = al(f"/api/v1/smm/donemler/{K}/butce-kiyas?senaryo={S['butce']}")
    kaydet("4.17 bütçe kıyası Kasım", ozet=b["ozet"], kayitlar=[(x["kod"], tl(x["butce_maliyet_tl"], 4), tl(x["fiili_birim_maliyet_tl"], 4), tl(x["fark_tl"], 4),
                                                               tl(D(x["fark_yuzde"]) * 100) if x["fark_yuzde"] else None,
                                                               tl(D(x["fark_tl"]) - D(S["ekim_fark"][x["kod"]]), 4)) for x in b["kayitlar"]])
    a = al("/api/v1/smm/karsilastirma")
    kaydet("4.18 aylar arası", satirlar=[(x["anahtar"], x["ad"], [tl(h["tutar"]) for h in x["hucreler"]], tl(x["son_fark_tl"]),
                                          tl(D(x["son_fark_yuzde"]) * 100) if x["son_fark_yuzde"] else None) for x in a["satirlar"]])
    r = mu.put(f"/api/v1/smm/donemler/{K}/kilit", json={"kilitli": True})
    kaydet("4.19 Kasım kapat", http=r.status_code, yanit=r.json() if r.status_code != 200 else "kilitli")
    r = gd.put(f"/api/v1/smm/donemler/{E}/kilit", json={"kilitli": False})
    kaydet("4.19 Ekim kilidi aç (GD, Kasım kilitli)", http=r.status_code, yanit=r.json())
    kaydet("4.19 Kasım kilidi aç (GD)", http=gd.put(f"/api/v1/smm/donemler/{K}/kilit", json={"kilitli": False}).status_code)
    r = gd.put(f"/api/v1/smm/donemler/{E}/kilit", json={"kilitli": False})
    kaydet("4.19 Ekim kilidi aç (GD)", http=r.status_code, uyari=r.json().get("uyari"))
    for d in (E, K):   # sonraki bölümler için yeniden kapat (önce Ekim)
        bekle(mu.put(f"/api/v1/smm/donemler/{d}/kilit", json={"kilitli": True}), 200, "yeniden kapat")


# ------------------------------------------------------------------ 5. Sezon sonu: gerçekleşen
@adim("5")
def _():
    r = bekle(mu.post("/api/v1/import/excel-tam", files=dosya("fiyat-calismasi-gerceklesen"),
                      data={"sezon_ad": "2026-2027", "senaryo_ad": "Test Gerçekleşen 2026-2027", "tur": "gerceklesen", "kartlari_guncelle": "false"}),
              200, "gerçekleşen").json()
    S["gercek"] = r["senaryo_id"]
    kaydet("5.1 gerçekleşen içe aktarma", **{k: r[k] for k in ("senaryo_id", "malzeme", "fiyat", "urun", "recete", "parametre", "kart_farklari",
                                                               "uyarilar", "atlanan")})
    A, B = S["butce"], S["gercek"]
    j = al(f"/api/v1/kiyas?a={A}&b={B}&yenile=true")
    kaydet("5.2 bütçe vs gerçekleşen", ozet=j["ozet"],
           satirlar=[(x["kod"], x["durum"], x["sapan"], tl(x["alanlar"]["maliyet_tl"]["a"], 4), tl(x["alanlar"]["maliyet_tl"]["b"], 4),
                      tl(x["alanlar"]["maliyet_tl"]["fark"], 4), tl(x["sapma_yuzde"], 2)) for x in j["satirlar"]])
    yillik = {k: D(0) for k in ("fiyat", "recete", "uretim", "gider", "kur", "enflasyon", "diger")}
    S["ayristirma"] = {}
    for x in j["satirlar"]:
        kod = x["kod"]
        bek = urun_bekleneni(kod)
        kontrol(f"5.2 bütçe maliyeti {kod}", x["alanlar"]["maliyet_tl"]["a"], bek["butce"]["maliyet_tl"])
        kontrol(f"5.2 gerçekleşen maliyeti {kod}", x["alanlar"]["maliyet_tl"]["b"], bek["gerceklesen"]["maliyet_tl"])
        u = al(f"/api/v1/kiyas/urun/{kod}?a={A}&b={B}")
        ayr = {a_["kaynak"]: a_["fark"] for a_ in u["ayristirma"]}
        S["ayristirma"][kod] = {a_: tl(v, 6) for a_, v in ayr.items()}
        for kaynak, v in ayr.items():
            kontrol(f"5.3 ayrıştırma {kod} {kaynak}", v, bek["ayristirma"][kaynak])
            yillik[kaynak] += D(v) * bek["yillik_adet"]
        kontrol(f"5.3 ayrıştırma toplamı = toplam fark {kod}", sum((D(v) for v in ayr.values()), D(0)), u["toplam_fark"], "0.0000001")
        degisen_uretim = [s_["alan"] for s_ in u["uretim"] if s_["degisti"]]
        degisen_recete = [(s_["kod"], s_["degisen"]) for s_ in u["recete"] if s_["degisen"]]
        degisen_param = [s_["anahtar"] for s_ in u["parametreler"] if s_["degisti"]]
        kaydet(f"5.3 sapmanın kaynağı {kod}", ayristirma=S["ayristirma"][kod], toplam_fark=tl(u["toplam_fark"], 6), uretim_degisen=degisen_uretim,
               recete_degisen=degisen_recete, parametre_degisen=degisen_param)
        esit(f"5.3 reçete (fire) satırı yalnız 03.99.002'de dolu ({kod})", D(ayr["recete"]) != 0, kod == "03.99.002")
        esit(f"5.3 üretim (adet) satırı yalnız 03.99.007'de dolu ({kod})", D(ayr["uretim"]) != 0, kod == "03.99.007")
        esit(f"5.3 gider ve diğer satırı 0 ({kod})", [D(ayr[k]) == 0 for k in ("gider", "diger")], [True, True])
        # iş anlamında dört sapma (kur / fiyat / fire / adet) ile uygulama satırlarının ilişkisi
        is_ = bek["is_anlaminda"]
        kontrol(f"5.3 iş: kur = 'Döviz kurları' satırı {kod}", ayr["kur"], is_["kur"])
        kontrol(f"5.3 iş: adet = 'Üretim bilgileri' satırı {kod}", ayr["uretim"], is_["adet"])
        kontrol(f"5.3 iş: fire x 1,25 = 'Reçete' satırı {kod}", ayr["recete"], D(is_["fire"]) * D("1.25"))
        kontrol(f"5.3 iş: fiyat = fiyat + enflasyon + (reçete - fire) {kod}", D(ayr["fiyat"]) + D(ayr["enflasyon"]) + D(ayr["recete"]) - D(is_["fire"]),
                is_["fiyat"])
    kaydet("5.4 şirket toplamı uygulama satırlarına göre (yıllık, birim fark x geçen yıl adedi)", **{k: tl(v) for k, v in yillik.items()})
    for k, v in yillik.items():
        kontrol(f"5.4 yıllık {k}", v, BEK["toplam"]["kaynaga_gore_yillik_tl"][k], "0.01")
    is_y = {"kur": yillik["kur"], "adet": yillik["uretim"], "fire": yillik["recete"] / D("1.25")}
    is_y["fiyat"] = sum(yillik.values(), D(0)) - is_y["kur"] - is_y["adet"] - is_y["fire"]
    kaydet("5.4 şirket toplamı iş anlamında (yıllık)", **{k: tl(v) for k, v in is_y.items()})
    for k, v in is_y.items():
        kontrol(f"5.4 iş anlamında yıllık {k}", v, BEK["toplam"]["is_anlaminda_yillik_tl"][k], "0.01")
    ya, yb = yonetim(A), yonetim(B)
    kaydet("5.5 yönetim özeti bütçe vs gerçekleşen", butce=dict(marj=ya["marj"]["agirlikli_ortalama"], yillik_maliyet=tl(ya["kur_riski"]["yillik_maliyet_tl"]),
                                                               maliyet_toplam=tl(ya["maliyet_yapisi"]["toplam_tl"], 4), doviz_payi=tl(ya["kur_riski"]["doviz_payi_yuzde"], 3)),
           gerceklesen=dict(marj=yb["marj"]["agirlikli_ortalama"], yillik_maliyet=tl(yb["kur_riski"]["yillik_maliyet_tl"]),
                            maliyet_toplam=tl(yb["maliyet_yapisi"]["toplam_tl"], 4), doviz_payi=tl(yb["kur_riski"]["doviz_payi_yuzde"], 3)),
           fark=tl(D(yb["kur_riski"]["yillik_maliyet_tl"]) - D(ya["kur_riski"]["yillik_maliyet_tl"])))
    kontrol("5.5 gerçekleşen yıllık maliyet", yb["kur_riski"]["yillik_maliyet_tl"], BEK["toplam"]["gerceklesen_yillik_maliyet_tl"], "0.01")
    kontrol("5.5 şirket toplamı yıllık sapma", D(yb["kur_riski"]["yillik_maliyet_tl"]) - D(ya["kur_riski"]["yillik_maliyet_tl"]),
            BEK["toplam"]["yillik_sapma_tl"], "0.01")
    kontrol("5.5 kaynaklar toplamı = şirket sapması", sum(yillik.values(), D(0)), D(yb["kur_riski"]["yillik_maliyet_tl"]) - D(ya["kur_riski"]["yillik_maliyet_tl"]), "0.01")
    toplam, k = karlilik_toplam(B)
    kaydet("5.6 kârlılık haritası (gerçekleşen)", ozet=k["ozet"], yillik_kar_toplam=tl(toplam), butceye_gore=tl(toplam - S["kar_butce"]),
           kayitlar=[(x["kod"], x["bolge"], tl(D(x["marj"]) * 100), tl(x["yillik_kar"])) for x in k["kayitlar"]])
    j = al(f"/api/v1/kiyas?a={S['guncel']}&b={B}&yenile=true")
    kaydet("5.7 güncel vs gerçekleşen (şoktan sonra kalan fark)", ozet=j["ozet"],
           satirlar=[(x["kod"], tl(x["alanlar"]["maliyet_tl"]["fark"], 4)) for x in j["satirlar"]])


# ------------------------------------------------------------------ 6. Yönetime ve müşavire rapor
@adim("6")
def _():
    A, B = S["butce"], S["gercek"]
    r = bekle(mu.post(f"/api/v1/senaryolar/{B}/kilitle", json={"neden": "Sezon sonu gerçekleşen kesinleşti"}), 200, "kilitle B")
    for sen, ad in ((A, "bütçe"), (B, "gerçekleşen")):
        for tur in ("excel", "pdf"):
            r = gd.post("/api/v1/onay-ciktisi/fiyat", json={"senaryo_id": sen, "tur": tur})
            kaydet(f"6.1 rapor {ad} {tur} (direktor)", http=r.status_code, bayt=len(r.content), tur=r.headers.get("content-type"),
                   ad=r.headers.get("content-disposition"))
            if tur == "excel" and r.status_code == 200:
                esit(f"6.1 kilitli {ad} raporu KESİN", "KESİN" in xlsx_metni(r.content), True)
    r = iz.post("/api/v1/onay-ciktisi/fiyat", json={"senaryo_id": A, "tur": "excel"})
    kaydet("6.2 izleyici rapor indirme", http=r.status_code)
    kaydet("6.2 izleyici yazma denemeleri",
           fiyat=iz.post(f"/api/v1/malzemeler/99.11.007/fiyatlar?senaryo={S['guncel']}", json={"fiyat": "74", "gecerlilik_basi": "2026-11-16", "neden": "x"}).status_code,
           kilit=iz.post("/api/v1/duzenleme-kilidi/ac", json={"senaryo_id": S["guncel"], "sayfa": "urunler"}).status_code,
           okuma=iz.get(f"/api/v1/yonetim/ozet?senaryo={A}").status_code)
    oz = al("/api/v1/gunluk/ozet?gun=30")
    kaydet("6.3 değişiklik günlüğü (30 gün)", **oz)
    for kul in ("satinalma1", "direktor", "izleyici1"):
        j = al(f"/api/v1/gunluk?kullanici={kul}&boyut=100")
        kaydet(f"6.3 günlük {kul}", toplam=j.get("toplam"),
               kayitlar=[(x["tur"], x["baslik"][:70], x.get("senaryo_id"), x.get("eski"), x.get("yeni"), (x.get("neden") or "")[:60]) for x in j.get("kayitlar", [])])
    for sen, ad in ((A, "bütçe"), (S["guncel"], "güncel"), (B, "gerçekleşen")):
        j = al(f"/api/v1/gunluk?senaryo={sen}&boyut=200")
        kaydet(f"6.3 günlük {ad}", toplam=j.get("toplam"),
               ozet=sorted({(x["kullanici"], x["tur"], x["baslik"][:60]) for x in j.get("kayitlar", [])})[:25])


def main():
    sakla = "--sakla" in sys.argv
    cikti = KOK / "test-dongusu" / "deneme" / "11-18-2026-sezon-kuru-kosu-sonuclari.json"
    gecen = sum(1 for k in KONTROLLER if k["gecti"])
    cikti.write_text(json.dumps({"senaryolar": {k: v for k, v in S.items() if isinstance(v, int)}, "adimlar": SONUC,
                                 "kontroller": {"toplam": len(KONTROLLER), "gecen": gecen, "tutmayan": [k for k in KONTROLLER if not k["gecti"]],
                                                "liste": KONTROLLER},
                                 "stok_mizani_ayari": {"ekim": S.get("stok_mizani_ayari_ekim"), "kasim": S.get("stok_mizani_ayari_kasim")},
                                 "hatalar": HATALAR}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"\nKONTROL: {gecen} / {len(KONTROLLER)} tuttu")
    for k in KONTROLLER:
        if not k["gecti"]:
            print("  TUTMADI:", k)
    print(f"[stok mizanı ayarı] Ekim {S.get('stok_mizani_ayari_ekim')} · Kasım {S.get('stok_mizani_ayari_kasim')}")
    print(f"HATALAR ({len(HATALAR)}):")
    for h in HATALAR:
        print(" -", h)
    if not sakla:
        from backend.depo import veritabani
        if veritabani._ENGINE is not None:
            veritabani._ENGINE.dispose()
        temizle()
        print("geçici veritabanı silindi")


main()
