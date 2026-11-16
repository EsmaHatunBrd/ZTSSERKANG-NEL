"""Test senaryosunun KURU KOŞUSU: senaryodaki yükleme ve sayı içeren adımları API üzerinden (süreç içi TestClient, giriş zorunlu)
geçici bir veritabanında gerçekten uygular ve beklenen sayıları yazdırır. Senaryodaki 'beklenen sonuç' sayıları bu koşudan alınmıştır.

Geçici veritabanı: veri/11-16-2026-kuru-kosu.db (koşu sonunda silinir; gerçek veri/fiyat.db'ye dokunulmaz).
Çıktı: test-dongusu/11-16-2026-kuru-kosu-sonuclari.json (adım -> değerler) ve ekrana özet.

Kullanım (proje kökünden; önce test-dongusu\\uret.py):  .venv\\Scripts\\python.exe test-dongusu\\kuru_kosu.py [--sakla]
--sakla: geçici veritabanını silme (ekran görüntüsü için 8048'de açmak üzere).
"""
import json
import os
import re
import subprocess
import sys
import traceback
from decimal import Decimal
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
DB = KOK / "veri" / "11-16-2026-kuru-kosu.db"
assert DB.name != "fiyat.db"
os.environ["VERITABANI_URL"] = f"sqlite:///{DB.as_posix()}"
os.environ["ONBELLEK_ISITMA"] = "0"
os.environ["GIRIS_ZORUNLU"] = "1"
sys.path.insert(0, str(KOK))
EXCEL = KOK / "test-dongusu" / "excel"
ON = "11-16-2026-"
SONUC: dict[str, dict] = {}
HATALAR: list[str] = []


def temizle():
    for ek in ("", "-wal", "-shm"):
        Path(str(DB) + ek).unlink(missing_ok=True)
    for y in (KOK / "veri" / "yedek").glob(f"*{DB.name}*"):
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
    print(f"[{adim}] " + json.dumps(degerler, ensure_ascii=False, default=str)[:1500])


def bekle(r, kod: int, adim: str):
    if r.status_code != kod:
        HATALAR.append(f"{adim}: HTTP {r.status_code} (beklenen {kod}) {r.text[:400]}")
        print(f"!!! {adim}: HTTP {r.status_code} {r.text[:400]}")
    return r


def tl(x) -> str:
    return None if x is None else str(Decimal(str(x)).quantize(Decimal("0.01")))


# ------------------------------------------------------------------ 0. hazırlık
def istemci() -> TestClient:
    return TestClient(APP, base_url="http://testserver")


gd = istemci()
bekle(gd.get("/api/v1/kimlik/ben"), 401, "0 ilk istek (veritabanı oluşur)")
cikti = subprocess.run([sys.executable, str(KOK / "scripts" / "11-04-2026-ilk-genel-direktor.py"), "--db", str(DB)],
                       capture_output=True, text=True, encoding="utf-8")
gecici = re.search(r"geçici şifre\s*:\s*(\S+)", cikti.stdout)
kaydet("0.2 ilk genel direktör", cikti=cikti.stdout.splitlines()[:2], hata=cikti.stderr[-300:] or None)
SIFRE = "TestSifre2026!"
bekle(gd.post("/api/v1/kimlik/giris", json={"kullanici_adi": "direktor", "sifre": gecici.group(1)}), 200, "0.3 giriş")
r = gd.post("/api/v1/senaryolar", json={})
kaydet("0.3 şifre değişmeden yazma", http=r.status_code, kod=r.json().get("kod"))
bekle(gd.post("/api/v1/kimlik/sifre", json={"eski_sifre": gecici.group(1), "yeni_sifre": SIFRE}), 200, "0.3 şifre")
KUL = {}
for kad, ad, rol in (("muhasebe1", "Test Muhasebe", "muhasebe"), ("satinalma1", "Test Satın Alma", "satin_alma"),
                     ("izleyici1", "Test İzleyici", "izleyici")):
    bekle(gd.post("/api/v1/kullanicilar", json={"kullanici_adi": kad, "ad": ad, "rol": rol, "gecici_sifre": "Gecici2026!"}), 201, "0.4 kullanıcı")
    c = istemci()
    bekle(c.post("/api/v1/kimlik/giris", json={"kullanici_adi": kad, "sifre": "Gecici2026!"}), 200, "0.4 giriş " + kad)
    bekle(c.post("/api/v1/kimlik/sifre", json={"eski_sifre": "Gecici2026!", "yeni_sifre": SIFRE}), 200, "0.4 şifre " + kad)
    KUL[rol] = c
kaydet("0.4 kullanıcılar", kullanici=[(k["kullanici_adi"], k["rol"]) for k in gd.get("/api/v1/kullanicilar").json()["kayitlar"]])
mu = KUL["muhasebe"]


# ------------------------------------------------------------------ yardımcılar
def genel_bakis(sen: int, c=None) -> dict:
    j = bekle((c or mu).get(f"/api/v1/urunler?senaryo={sen}&boyut=100&yenile=true"), 200, "genel bakış").json()
    return {k["kod"]: k for k in j["kayitlar"]}


def ozet_urunler(gb: dict) -> dict:
    return {k: {"maliyet_tl": tl(v["maliyet_tl"]), "satis_tl": tl(v.get("satis_tl"))} for k, v in gb.items()}


def hesap(kod: str, sen: int) -> dict:
    return bekle(mu.post(f"/api/v1/urunler/{kod}/hesapla", json={"senaryo_id": sen}), 200, f"hesapla {kod}").json()


def kontrol(sen: int) -> dict:
    j = bekle(mu.get(f"/api/v1/tutarlilik?senaryo={sen}&yenile=true"), 200, "tutarlılık").json()
    return {"ozet": j["ozet"], "kontroller": {k["kod"]: (k["durum"], k["sayi"], [o["etiket"] for o in k["ogeler"]][:6]) for k in j["kontroller"]}}


def adim(ad):
    def sar(fn):
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            HATALAR.append(f"{ad}: {type(e).__name__}: {e}")
            traceback.print_exc()
        return fn
    return sar


S = {}


# ------------------------------------------------------------------ 1. kurulum
@adim("1")
def _():
    r = bekle(mu.post("/api/v1/import/excel-tam", files=dosya("fiyat-calismasi-butce"),
                      data={"sezon_ad": "2026-2027", "senaryo_ad": "Test Bütçe 2026-2027", "tur": "fiyat_calismasi"}), 200, "1.2 tam kitap")
    o = r.json()
    S["butce"] = o["senaryo_id"]
    kaydet("1.2 tam kitap içe aktarma", **{k: o[k] for k in ("senaryo_id", "malzeme", "fiyat", "havuz", "ambalaj", "urun", "recete", "parametre",
                                                             "atlanan", "uyarilar", "urun_parametre_farklari", "kapasite", "revize", "satis_notu")})
    gb = genel_bakis(S["butce"])
    kaydet("1.3 genel bakış", urun_sayisi=len(gb), urunler=ozet_urunler(gb), anahtarlar=sorted(next(iter(gb.values())).keys()))
    h = hesap("03.99.001", S["butce"])
    kaydet("1.3 hesap anahtarları", anahtarlar=sorted(h.keys()), sonuc=sorted((h.get("sonuc") or {}).keys())[:60])
    for kod in gb:
        hh = hesap(kod, S["butce"])
        x = hh["toplamlar"]
        kaydet(f"1.3 hesap {kod}", **({a: tl(v) for a, v in x.items() if isinstance(v, (str, int, float))}), uyarilar=hh.get("uyarilar"),
               satir=len(hh.get("satirlar", [])))
    kaydet("1.4 veri kontrolü", **kontrol(S["butce"]))
    m = bekle(mu.get(f"/api/v1/malzemeler?senaryo={S['butce']}&boyut=200"), 200, "malzemeler").json()
    kaydet("1.4 malzemeler", toplam=m.get("toplam"), anahtar=sorted(m.keys()))
    hv = bekle(mu.get(f"/api/v1/gider-havuzlari?senaryo={S['butce']}"), 200, "havuzlar").json()
    kaydet("1.5 gider havuzları", havuz=[(x["kod"], tl(x["toplam_tutar"]), x.get("taban_tutar"), [c["deger"] for c in (x.get("carpanlar") or [])])
                                        for x in (hv["kayitlar"] if isinstance(hv, dict) else hv)])
    p = bekle(mu.get(f"/api/v1/parametreler?senaryo={S['butce']}"), 200, "parametreler").json()
    kaydet("1.5 parametreler", ornek=json.dumps(p, ensure_ascii=False)[:800])


# ------------------------------------------------------------------ 2. günlük işler
@adim("2")
def _():
    sen = S["butce"]
    kaydet("2.1 düzenleme kilidi", muhasebe=mu.post("/api/v1/duzenleme-kilidi/ac", json={"senaryo_id": sen, "sayfa": "urunler"}).status_code,
           izleyici=KUL["izleyici"].post("/api/v1/duzenleme-kilidi/ac", json={"senaryo_id": sen, "sayfa": "urunler"}).status_code)
    # 2.4 fiyat listesi
    once = {k: v["maliyet_tl"] for k, v in genel_bakis(sen).items()}
    r = bekle(mu.post("/api/v1/import/fiyat-listesi", files=dosya("fiyat-listesi-revize"), data={"senaryo": sen, "gecerlilik_basi": "2026-11-15"}),
              200, "2.4 önizle").json()
    kaydet("2.2 fiyat listesi önizleme", degisen=len(r["degisen"]), yeni=len(r["yeni"]), ayni=r["ayni"], hatali=r["hatali"], revize=len(r["revize"]),
           degisen_liste=[(d["kod"], d["eski"], d["yeni"]) for d in r["degisen"]])
    r = bekle(mu.post("/api/v1/import/fiyat-listesi/uygula", files=dosya("fiyat-listesi-revize"),
                      data={"senaryo": sen, "gecerlilik_basi": "2026-11-15", "neden": "Test: Kasım revize fiyat listesi"}), 200, "2.4 uygula").json()
    sonra = {k: v["maliyet_tl"] for k, v in genel_bakis(sen).items()}
    kaydet("2.2 fiyat listesi uygula", **r, maliyet=[(k, tl(once[k]), tl(sonra[k])) for k in once])
    once = genel_bakis(sen)["03.99.001"]["maliyet_tl"]
    # 2.3 tek fiyat: küçük değişiklik
    r = bekle(mu.post(f"/api/v1/malzemeler/99.10.001/fiyatlar?senaryo={sen}",
                      json={"fiyat": "21.5", "gecerlilik_basi": "2026-11-16", "neden": "Test: hıyar alım fiyatı"}), 201, "2.2 fiyat")
    kaydet("2.3 tek fiyat 99.10.001 20,72->21,50", http=r.status_code, maliyet_once=tl(once), maliyet_sonra=tl(genel_bakis(sen)["03.99.001"]["maliyet_tl"]))
    # 2.3 büyük değişiklik
    r = mu.post(f"/api/v1/malzemeler/99.20.004/fiyatlar?senaryo={sen}",
                json={"fiyat": "3.6", "gecerlilik_basi": "2026-11-16", "neden": "Test: kapak 82 mm zammı"})
    kaydet("2.4 büyük değişiklik onaysız", http=r.status_code, yanit=r.json())
    r = mu.post(f"/api/v1/malzemeler/99.20.004/fiyatlar?senaryo={sen}",
                json={"fiyat": "3.6", "gecerlilik_basi": "2026-11-16", "neden": "Test: kapak 82 mm zammı", "onay": True})
    kaydet("2.4 büyük değişiklik onaylı", http=r.status_code)
    # 2.5 satın alma aktarımı (fiyatsızlar + yeni kart)
    r = bekle(mu.post("/api/v1/aktarim/satin-alma/onizle", files=dosya("satin-alma-yeni-malzeme"), data={"senaryo": sen}), 200, "2.5 önizle").json()
    kaydet("2.5 satın alma önizleme", yeni_malzeme=[x["kod"] for x in r["yeni_malzeme"]], fiyat_yeni=[x["kod"] for x in r["fiyat_yeni"]],
           fiyat_degisen=r["fiyat_degisen"], ayni=r["ayni"], hatali=r["hatali"])
    r = bekle(mu.post("/api/v1/aktarim/satin-alma/uygula", files=dosya("satin-alma-yeni-malzeme"),
                      data={"senaryo": sen, "gecerlilik_basi": "2026-11-15", "neden": "Test: eksik fiyatlar"}), 200, "2.5 uygula").json()
    kaydet("2.5 satın alma uygula", **r)
    k = kontrol(sen)
    kaydet("2.5 veri kontrolü sonrası", fiyatsiz=k["kontroller"]["fiyatsiz"], ozet=k["ozet"])
    # 2.6 reçete değişikliği (ürün ekranı): 03.99.001 hıyar 0,22 -> 0,23 + elle fiyat + kaydet
    rec = bekle(mu.get(f"/api/v1/urunler/03.99.001/recete?senaryo={sen}"), 200, "reçete").json()
    kaydet("2.6 reçete anahtarları", anahtar=sorted(rec.keys()), satir_anahtar=sorted(rec["satirlar"][0].keys()) if rec.get("satirlar") else None,
           satir=len(rec.get("satirlar", [])))
    alanlar = ("malzeme_kodu", "ad", "miktar", "birim", "fire_override", "dugum_tipi", "brut_miktar_elle", "birim_fiyat_elle", "seviye", "zs_elle",
               "para_birimi_elle")
    satirlar = [{a: x.get(a) for a in alanlar} for x in rec["satirlar"]]
    for x in satirlar:
        if x["malzeme_kodu"] == "99.10.001":
            x["miktar"] = "0.23"
    once = genel_bakis(sen)["03.99.001"]["maliyet_tl"]
    r = bekle(mu.post("/api/v1/urunler/03.99.001/kaydet", json={"senaryo_id": sen, "neden": "Test: hıyar miktarı 0,22 -> 0,23", "recete": satirlar}),
              200, "2.6 kaydet").json()
    kaydet("2.6 reçete kaydet", hesap_id=r["hesap_id"], yazilan=r["yazilan"], maliyet_once=tl(once),
           maliyet_sonra=tl(genel_bakis(sen)["03.99.001"]["maliyet_tl"]))
    S["hesap_001_a"] = r["hesap_id"]
    # 2.7 elle fiyat ve formüle dönüş (kapak 63 mm)
    for x in satirlar:
        if x["malzeme_kodu"] == "99.20.003":
            x["birim_fiyat_elle"] = "2.50"
    r = bekle(mu.post("/api/v1/urunler/03.99.001/kaydet", json={"senaryo_id": sen, "neden": "Test: kapak elle fiyat", "recete": satirlar}), 200, "2.7").json()
    elle = genel_bakis(sen)["03.99.001"]["maliyet_tl"]
    for x in satirlar:
        if x["malzeme_kodu"] == "99.20.003":
            x["birim_fiyat_elle"] = None
    r2 = bekle(mu.post("/api/v1/urunler/03.99.001/kaydet", json={"senaryo_id": sen, "neden": "Test: kapak listeye dön", "recete": satirlar}), 200, "2.7b").json()
    kaydet("2.7 elle hücre", elle_maliyet=tl(elle), listeye_donunce=tl(genel_bakis(sen)["03.99.001"]["maliyet_tl"]), hesap_id=r["hesap_id"],
           hesap_id_2=r2["hesap_id"])
    S["hesap_001_b"] = r2["hesap_id"]
    # 2.8 gider satırı elle -> formüle dön (03.99.004 elektrik)
    once_k = kontrol(sen)["kontroller"]["elle_hucre"]
    once = genel_bakis(sen)["03.99.004"]["maliyet_tl"]
    r = bekle(mu.post("/api/v1/urunler/03.99.004/kaydet", json={"senaryo_id": sen, "neden": "Test: elektrik formüle dön", "gider_elle": {}}), 200, "2.8").json()
    kaydet("2.8 gider elle formüle dön", elle_hucre_once=once_k, elle_hucre_sonra=kontrol(sen)["kontroller"]["elle_hucre"],
           maliyet_once=tl(once), maliyet_sonra=tl(genel_bakis(sen)["03.99.004"]["maliyet_tl"]))
    # 2.9 geçmiş hesaplar ve kıyas
    hs_ = bekle(mu.get(f"/api/v1/urunler/03.99.001/hesaplar?senaryo={sen}"), 200, "hesaplar").json()
    liste = hs_["kayitlar"] if isinstance(hs_, dict) else hs_
    kaydet("2.9 geçmiş hesaplar", sayi=len(liste), ornek=liste[:1])
    r = bekle(mu.get(f"/api/v1/arsiv/kiyas?hesap_a={S['hesap_001_a']}&hesap_b={S['hesap_001_b']}"), 200, "2.9 kıyas")
    kaydet("2.9 kıyas", yanit=json.dumps(r.json(), ensure_ascii=False)[:1200])


# ------------------------------------------------------------------ 2b. diğer Veri Aktar sekmeleri
@adim("2b")
def _():
    sen = S["butce"]
    r = bekle(mu.post("/api/v1/aktarim/uretim-adetleri/onizle", files=dosya("uretim-adetleri"), data={"senaryo": sen}), 200, "üretim önizle").json()
    kaydet("2.10 üretim adetleri önizleme", yeni=[x["urun_kodu"] for x in r["yeni"]], degisen=r["degisen"], ayni=r["ayni"], uyarilar=r["uyarilar"])
    r = bekle(mu.post("/api/v1/aktarim/uretim-adetleri/uygula", files=dosya("uretim-adetleri"), data={"senaryo": sen, "neden": "Test: hedef adetler"}),
              200, "üretim uygula").json()
    kaydet("2.10 üretim adetleri uygula", **r, eslesmeyen=kontrol(sen)["kontroller"]["uretim_adetleri"])
    once = {k: v["maliyet_tl"] for k, v in genel_bakis(sen).items()}
    r = bekle(mu.post("/api/v1/aktarim/gider-dagitim/onizle", files=dosya("gider-dagitim"), data={"senaryo": sen}), 200, "gider önizle").json()
    kaydet("2.11 gider önizleme", degisen=[(h["kod"], h["eski_toplam"], h["yeni_toplam"], h["yeni_carpanlar"]) for h in r["havuz"] if h["degisti"]],
           ambalaj=r["ambalaj"])
    r = bekle(mu.post("/api/v1/aktarim/gider-dagitim/uygula", files=dosya("gider-dagitim"), data={"senaryo": sen, "neden": "Test: elektrik zammı"}),
              200, "gider uygula").json()
    sonra = {k: v["maliyet_tl"] for k, v in genel_bakis(sen).items()}
    kaydet("2.11 gider uygula", **r, maliyet=[(k, tl(once[k]), tl(sonra[k])) for k in once])
    r = bekle(mu.post("/api/v1/aktarim/recete/onizle", files=dosya("urun-recetesi-004"), data={"senaryo": sen}), 200, "reçete önizle").json()
    kaydet("2.12 reçete önizleme", sayfalar=r["sayfalar"], hatali=r["hatali"])
    once = genel_bakis(sen)["03.99.004"]["maliyet_tl"]
    r = bekle(mu.post("/api/v1/aktarim/recete/uygula", files=dosya("urun-recetesi-004"),
                      data={"senaryo": sen, "neden": "Test: sos reçetesi revizyonu", "sayfalar": ["004"]}), 200, "reçete uygula").json()
    kaydet("2.12 reçete uygula", **r, maliyet_once=tl(once), maliyet_sonra=tl(genel_bakis(sen)["03.99.004"]["maliyet_tl"]))
    r = bekle(mu.post("/api/v1/satis-gecmisi/yukle", files={"dosya": (f"{ON}satis-gecmisi.xlsx", (EXCEL / f"{ON}satis-gecmisi.xlsx").read_bytes())}),
              200, "satış yükle").json()
    kaydet("2.13 satış geçmişi", **r, toplam=mu.get("/api/v1/satis-gecmisi?boyut=1").json()["toplam"])
    r = bekle(mu.post("/api/v1/aktarim/stok-devri/onizle", files=dosya("stokta-kalan"), data={"senaryo": sen}), 200, "stok önizle").json()
    kaydet("2.14 stok devri önizleme", yeni=r["yeni"], degisen=r["degisen"], hatalar=r["hatalar"])
    r = bekle(mu.post("/api/v1/aktarim/stok-devri/uygula", files=dosya("stokta-kalan"), data={"senaryo": sen, "neden": "Test: geçen yıldan stok"}),
              200, "stok uygula").json()
    kaydet("2.14 stok devri uygula", **r)
    for kod in ("03.99.001", "03.99.003"):
        kaydet(f"2.14 stok kartı {kod}", **bekle(mu.get(f"/api/v1/urunler/{kod}/stok-devri?senaryo={sen}"), 200, "stok kartı").json())


# ------------------------------------------------------------------ 3. teklif
@adim("3")
def _():
    sen = S["butce"]
    r = bekle(mu.post(f"/api/v1/hesaplar/{S['hesap_001_b']}/teklifler", json={"kar_orani": "0.20", "musteri": "Test Market A.Ş.", "notu": "1. tur"}),
              201, "teklif").json()
    kaydet("3.1 teklif 1", **{k: r.get(k) for k in ("id", "tur", "durum", "kar_orani", "fiyat_tl", "fiyat_usd")}, anahtar=sorted(r.keys()))
    t1 = r["id"]
    r = bekle(mu.post(f"/api/v1/hesaplar/{S['hesap_001_b']}/teklifler", json={"kar_orani": "0.17", "musteri": "Test Market A.Ş.", "notu": "2. tur"}),
              201, "teklif 2").json()
    t2 = r["id"]
    kaydet("3.1 teklif 2", **{k: r.get(k) for k in ("id", "tur", "durum", "kar_orani")}, tum=r)
    kaydet("3.2 durum", gonderildi=mu.patch(f"/api/v1/teklifler/{t1}/durum", json={"durum": "gonderildi"}).json(),
           red=mu.patch(f"/api/v1/teklifler/{t1}/durum", json={"durum": "red"}).status_code,
           kabul=mu.patch(f"/api/v1/teklifler/{t2}/durum", json={"durum": "kabul"}).status_code)
    for d in (None, "kabul", "red", "taslak"):
        j = mu.get(f"/api/v1/teklifler?senaryo={sen}" + (f"&durum={d}" if d else "")).json()
        kaydet(f"3.3 teklifler süzgeç {d}", toplam=j.get("toplam"))
    r = mu.get(f"/api/v1/disa-aktar/teklif-kapak.xlsx?senaryo={sen}")
    kaydet("3.4 teklif kapak", http=r.status_code, bayt=len(r.content), tur=r.headers.get("content-type"))
    kaydet("3.5 kayıtlı hesap", http=mu.get(f"/api/v1/hesaplar/{S['hesap_001_b']}").status_code)


# ------------------------------------------------------------------ 4. analiz
@adim("4")
def _():
    sen = S["butce"]
    def al(yol):
        return bekle(mu.get(yol), 200, yol).json()
    j = al(f"/api/v1/analiz/ya-olursa?senaryo={sen}&kur=0.10&ambalaj=0&hammadde=0&adet=0")
    kaydet("4.1 ya olursa kur +10", ozet=json.dumps({k: v for k, v in j.items() if k != "kayitlar"}, ensure_ascii=False)[:800],
           ilk=json.dumps((j.get("kayitlar") or [None])[0], ensure_ascii=False)[:500])
    j = al(f"/api/v1/analiz/zam-etkisi?senaryo={sen}&malzeme=99.20.001&oran=0.10")
    kaydet("4.2 zam etkisi kavanoz 370 %10", ozet=json.dumps({k: v for k, v in j.items() if k != "kayitlar"}, ensure_ascii=False)[:800],
           kayit=json.dumps(j.get("kayitlar"), ensure_ascii=False)[:900])
    j = al(f"/api/v1/analiz/kur-riski?senaryo={sen}&oran=0.10")
    kaydet("4.3 kur riski", ozet=json.dumps({k: v for k, v in j.items() if k != "kayitlar"}, ensure_ascii=False)[:900])
    j = al(f"/api/v1/analiz/karlilik?senaryo={sen}")
    kaydet("4.4 kârlılık", ozet=json.dumps({k: v for k, v in j.items() if k != "kayitlar"}, ensure_ascii=False)[:900],
           kayitlar=[(k.get("kod"), k.get("bolge"), k.get("marj"), k.get("adet"), k.get("fiyat_kaynagi")) for k in j.get("kayitlar", [])])
    j = al(f"/api/v1/analiz/hedef-fiyat?senaryo={sen}&marj=0.25")
    kaydet("4.5 hedef fiyat", ozet=json.dumps({k: v for k, v in j.items() if k != "kayitlar"}, ensure_ascii=False)[:900],
           kayitlar=[(k.get("kod"), k.get("gecen_yil_fiyat"), k.get("hedef_fiyat"), k.get("gereken_zam")) for k in j.get("kayitlar", [])])
    j = al(f"/api/v1/analiz/fiyat-egilimi?senaryo={sen}")
    kaydet("4.6 fiyat eğilimi", ozet=json.dumps({k: v for k, v in j.items() if k != "kayitlar"}, ensure_ascii=False)[:900],
           kayitlar=[(k.get("kod"), k.get("yillik_yuzde"), k.get("enflasyonu_asiyor")) for k in j.get("satirlar", [])][:15])
    j = al(f"/api/v1/analiz/onemli-malzemeler?senaryo={sen}")
    kaydet("4.7 önemli malzemeler", ozet=json.dumps({k: v for k, v in j.items() if k != "kayitlar"}, ensure_ascii=False)[:900],
           kayitlar=[(k.get("kod"), k.get("pay_yuzde"), k.get("kumulatif_yuzde"), k.get("esik_icinde")) for k in j.get("satirlar", [])][:12])
    r = bekle(mu.post(f"/api/v1/liste-fiyatlari/yukle?senaryo={sen}", files={"dosya": (f"{ON}liste-fiyatlari-gecmis.xlsx",
                                                                                       (EXCEL / f"{ON}liste-fiyatlari-gecmis.xlsx").read_bytes())}),
              200, "liste yükle").json()
    kaydet("4.8 liste yükle", **r)
    j = al(f"/api/v1/liste-calismasi?senaryo={sen}&pazar=yurtici")
    kaydet("4.8 liste çalışması", ozet=json.dumps({k: v for k, v in j.items() if k not in ("kayitlar", "seri")}, ensure_ascii=False)[:900],
           kayitlar=[(k.get("kod"), k.get("yeni_liste"), k.get("onceki_liste"), k.get("liste_artis"), k.get("maliyet_artis")) for k in j.get("kayitlar", [])])
    r = mu.get(f"/api/v1/disa-aktar/onemli-malzemeler?senaryo={sen}")
    kaydet("4.7 önemli malzemeler excel", http=r.status_code, bayt=len(r.content))


# ------------------------------------------------------------------ 5. kıyas
@adim("5")
def _():
    r = bekle(mu.post("/api/v1/import/excel-tam", files=dosya("fiyat-calismasi-gerceklesen"),
                      data={"sezon_ad": "2026-2027", "senaryo_ad": "Test Gerçekleşen 2026-2027", "tur": "gerceklesen", "kartlari_guncelle": "false"}),
              200, "gerçekleşen").json()
    S["gercek"] = r["senaryo_id"]
    kaydet("5.1 gerçekleşen içe aktarma", **{k: r[k] for k in ("senaryo_id", "malzeme", "fiyat", "urun", "kart_farklari", "uyarilar", "atlanan")})
    j = bekle(mu.get(f"/api/v1/kiyas?a={S['butce']}&b={S['gercek']}"), 200, "kıyas").json()
    kaydet("5.2 bütçe vs gerçekleşen", ozet=json.dumps({k: v for k, v in j.items() if k != "kayitlar"}, ensure_ascii=False)[:1200],
           satirlar=[(x["kod"], x["durum"], {a: (tl(v["a"]), tl(v["b"]), tl(v.get("fark_yuzde"))) for a, v in x["alanlar"].items() if a in ("maliyet_tl", "recete_maliyeti")})
                     for x in j.get("satirlar", [])])
    j = bekle(mu.get(f"/api/v1/kiyas/urun/03.99.001?a={S['butce']}&b={S['gercek']}"), 200, "kıyas ürün").json()
    kaydet("5.3 sapmanın kaynağı 03.99.001", yanit=json.dumps(j, ensure_ascii=False)[:1500])


# ------------------------------------------------------------------ 6. yönetim ve roller
@adim("6")
def _():
    sen = S["butce"]
    j = bekle(mu.get(f"/api/v1/yonetim/ozet?senaryo={sen}&yenile=true"), 200, "yönetim").json()
    kaydet("6.1 yönetim özeti", yanit=json.dumps(j, ensure_ascii=False)[:2500])
    r = mu.get(f"/api/v1/disa-aktar/maliyet-kartlari?senaryo={sen}")
    import io
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(r.content), read_only=True)
    kaydet("6.2 maliyet kartları", http=r.status_code, sayfalar=wb.sheetnames)
    j = mu.get(f"/api/v1/gunluk?senaryo={sen}&boyut=200").json()
    kaydet("6.3 değişiklik günlüğü", toplam=j.get("toplam"), anahtar=sorted(j.keys()),
           ilk=j.get("kayitlar", [None])[0])
    iz, sa = KUL["izleyici"], KUL["satin_alma"]
    kaydet("6.4 roller",
           izleyici_fiyat=iz.post(f"/api/v1/malzemeler/99.11.007/fiyatlar?senaryo={sen}",
                                  json={"fiyat": "74", "gecerlilik_basi": "2026-11-16", "neden": "rol testi"}).json(),
           satin_alma_fiyat=sa.post(f"/api/v1/malzemeler/99.11.007/fiyatlar?senaryo={sen}",
                                    json={"fiyat": "74", "gecerlilik_basi": "2026-11-16", "neden": "Test: satın alma fiyat girişi"}).status_code,
           satin_alma_recete=sa.post("/api/v1/urunler/03.99.002/kaydet", json={"senaryo_id": sen, "neden": "rol testi", "gider_elle": {}}).json(),
           satin_alma_kilit_ac=sa.post("/api/v1/duzenleme-kilidi/ac", json={"senaryo_id": sen, "sayfa": "urunler"}).status_code,
           izleyici_kullanicilar=iz.get("/api/v1/kullanicilar").status_code,
           muhasebe_kullanici_ekle=mu.post("/api/v1/kullanicilar", json={"kullanici_adi": "x123", "ad": "x", "rol": "izleyici",
                                                                         "gecici_sifre": "Gecici2026!"}).status_code)
    r = bekle(mu.post(f"/api/v1/senaryolar/{S['gercek']}/kilitle", json={"neden": "Test: gerçekleşen kesinleşti"}), 200, "kilitle")
    kaydet("6.5 çalışma kilitle", http=r.status_code,
           kilitliye_yazma=mu.post(f"/api/v1/malzemeler/99.11.007/fiyatlar?senaryo={S['gercek']}",
                                   json={"fiyat": "75", "gecerlilik_basi": "2026-11-16", "neden": "x"}).json())


# ------------------------------------------------------------------ 7. SMM
@adim("7")
def _():
    r = bekle(mu.post("/api/v1/smm/donemler/yukle", files=dosya("smm-ekim-2026"), data={"yil": 2026, "ay": 10}), 200, "smm yükle").json()
    E = r["id"]
    S["ekim"] = E
    kaydet("7.1 Ekim yükleme", **{k: r[k] for k in ("ad", "kalem_sayisi", "finansman", "excel_kontrol", "recete_kaynagi")})
    v = bekle(mu.get(f"/api/v1/smm/donemler/{E}/veri"), 200, "veri").json()
    kaydet("7.2 kontrol listesi", kaynaklar=[(k["kaynak"], k["yuklendi"], k["dolu"]) for k in v["kaynaklar"]], eksik=v["eksik"], donem_basi=v["donem_basi"],
           ayarlar=v["ayarlar"], grupsuz=v["grupsuz"])
    st = bekle(mu.get(f"/api/v1/smm/donemler/{E}/stok"), 200, "stok").json()
    kaydet("7.3 stok ve envanter", toplamlar=st["toplamlar"], kontrol_sayisi=st["kontrol_sayisi"], satir=len(st["kayitlar"]),
           turler=[(t["tur"], t["kalem"]) for t in st["turler"]],
           ornek={k["kod"]: {a: k[a] for a in ("ortalama_fiyat", "sarf_miktar", "sarf_tutar", "dss_tutar")} for k in st["kayitlar"] if k["kod"] in ("99.10.001", "99.20.001")})
    def ozet(d):
        return bekle(mu.get(f"/api/v1/smm/donemler/{d}/ozet"), 200, "özet").json()
    o = ozet(E)
    kaydet("7.4 SMM özeti (önce)", smm=o["smm"], uretim=o["uretim_maliyeti"], uretilen=o["uretilen"], ilk_madde=o["ilk_madde"],
           donem_sonu_stok=o["donem_sonu_stok"], mizan_kiyas=o["mizan_kiyas"], fis_borc=o["fis_borc"], fis_alacak=o["fis_alacak"])
    # elle kalem düzeltme: kavanoz 370 sayım +500
    k = next(x for x in st["kayitlar"] if x["kod"] == "99.20.001")
    r = bekle(mu.patch(f"/api/v1/smm/donemler/{E}/stok/99.20.001", json={"neden": "Test: sayım tutanağına göre düzeltme",
                                                                          "sayim_miktar": str(Decimal(k["sayim_miktar"]) + 500)}), 200, "elle kalem")
    st2 = mu.get(f"/api/v1/smm/donemler/{E}/stok?arama=99.20.001").json()["kayitlar"][0]
    kaydet("7.5 elle kalem", sayim_once=k["sayim_miktar"], sayim_sonra=st2["sayim_miktar"], sarf_once=k["sarf_miktar"], sarf_sonra=st2["sarf_miktar"],
           elle=mu.get(f"/api/v1/smm/donemler/{E}/stok/elle").json())
    # mizan elle satır: stok mizanına 153 ticari mal
    r = mu.post(f"/api/v1/smm/donemler/{E}/mizan/stok", json={"hesap": "153.01", "ad": "Test Ticari Mal", "bakiye": "12500", "neden": "Test: elle satır"})
    kaydet("7.6 mizan elle satır", http=r.status_code, yanit=json.dumps(r.json(), ensure_ascii=False)[:600])
    # üretim maliyeti
    for a in (20, 40, 50):
        j = bekle(mu.get(f"/api/v1/smm/donemler/{E}/uretim?asama={a}"), 200, "üretim").json()
        kaydet(f"7.7 üretim {a}", kayitlar=[(x["kod"], tl(x["uretim_miktar"]), tl(x["malzeme"]), tl(x["iscilik"]), tl(x["gug"]), tl(x["fire"]),
                                             tl(x["birim_maliyet"]), x["alim_kurali"], x["sure_yok"]) for x in j["kayitlar"]],
                **({"ozetler": [(z["asama"], z["urun_sayisi"], tl(z["toplam"]), z["excel"]) for z in j["ozetler"]],
                    "dagitim": {k_: j["dagitim"][k_] for k_ in ("dagitilan", "mizan_720", "mizan_730", "dagitilmayan")}} if a == 50 else {}))
    j = bekle(mu.put(f"/api/v1/smm/donemler/{E}/uretim/50/03.99.002/elle", json={"alanlar": {"iscilik": "1.25"}}), 200, "elle aşama").json()
    kaydet("7.8 aşama elle", birim=j["urun"]["birim_maliyet"], elle=j["urun"]["elle_alanlar"])
    j = bekle(mu.put(f"/api/v1/smm/donemler/{E}/uretim/50/03.99.002/elle", json={"alanlar": {"iscilik": None}}), 200, "formüle dön").json()
    kaydet("7.8 formüle dön", birim=j["urun"]["birim_maliyet"], elle=j["urun"]["elle_alanlar"])
    j = bekle(mu.get(f"/api/v1/smm/donemler/{E}/sarf-farki"), 200, "sarf").json()
    kaydet("7.9 sarf farkı", toplamlar=j["toplamlar"], birim_uyumsuz=j["birim_uyumsuz_sayisi"],
           ilk=[(x["kod"], tl(x["recete_sarf"]), tl(x["stok_sarf"]), tl(x["fark"]), tl(x["fark_tutar"])) for x in j["kayitlar"][:6]])
    o = ozet(E)
    kaydet("7.10 SMM özeti", smm=o["smm"], uretim=o["uretim_maliyeti"], uretilen=o["uretilen"], ilk_madde=o["ilk_madde"],
           donem_sonu_stok=o["donem_sonu_stok"], mizan_kiyas=o["mizan_kiyas"], fis=[(f["hesap"], f["borc"], f["alacak"]) for f in o["fis"]],
           fis_borc=o["fis_borc"], dss_kiyas=o["dss_kiyas"], tablo=[(b["hesap"], b["sonuc"]) for b in o["tablo"]])
    j = bekle(mu.get(f"/api/v1/smm/donemler/{E}/butce-kiyas?senaryo={S['butce']}"), 200, "bütçe kıyas").json()
    kaydet("7.11 bütçe kıyası", yanit=json.dumps({k_: v_ for k_, v_ in j.items() if k_ != "kayitlar"}, ensure_ascii=False)[:800],
           ilk=json.dumps((j.get("kayitlar") or [None])[0], ensure_ascii=False)[:900],
           kayitlar=[(x.get("kod"), tl(x.get("butce_maliyet_tl")), tl(x.get("fiili_birim_maliyet_tl")), tl(x.get("fark_tl")), tl(Decimal(x["fark_yuzde"]) * 100) if x.get("fark_yuzde") else None) for x in j.get("kayitlar", [])])
    j = bekle(mu.get(f"/api/v1/smm/donemler/{E}/urun/03.99.001/maliyet-karti"), 200, "kart").json()
    kaydet("7.12 ürün maliyet kartı", yanit=json.dumps(j, ensure_ascii=False)[:1500])
    r = mu.get(f"/api/v1/smm/donemler/{E}/fis.xlsx")
    kaydet("7.13 fiş excel", http=r.status_code, bayt=len(r.content))
    r = mu.put(f"/api/v1/smm/donemler/{E}/kilit", json={"kilitli": True})
    kaydet("7.14 Ekim kapat", http=r.status_code, yanit=r.json() if r.status_code != 200 else {"kilitli": r.json()["kilitli"]})
    if r.status_code == 409:
        r = mu.put(f"/api/v1/smm/donemler/{E}/kilit", json={"kilitli": True, "zorla": True})
        kaydet("7.14 Ekim kapat zorla", http=r.status_code)
    kaydet("7.14 kilitliye yazma", http=mu.patch(f"/api/v1/smm/donemler/{E}/stok/99.20.001", json={"neden": "x", "sayim_miktar": "1"}).status_code)
    # Canias reçeteleri
    r = bekle(mu.post("/api/v1/smm/receteler/onizle", files=dosya("smm-receteler-canias")), 200, "reçete önizle").json()
    kaydet("7.15 Canias önizleme", **{k_: r[k_] for k_ in ("satir_sayisi", "urun_sayisi", "asama", "alternatifli_urun", "eklenecek_urun")})
    bekle(mu.post("/api/v1/smm/receteler/yukle", files=dosya("smm-receteler-canias")), 200, "reçete yükle")
    kaydet("7.15 reçeteler", toplam=len(mu.get("/api/v1/smm/receteler").json().get("kayitlar", [])))
    # Kasım
    r = bekle(mu.post("/api/v1/smm/donemler", json={"yil": 2026, "ay": 11}), 201, "yeni dönem").json()
    K = r["id"]
    S["kasim"] = K
    kaydet("7.16 Kasım yeni dönem", ad=r["ad"], kalem=r["kalem_sayisi"], devir=r["devir"], recete_kaynagi=r["recete_kaynagi"])
    v = mu.get(f"/api/v1/smm/donemler/{K}/veri").json()
    kaydet("7.16 Kasım kontrol listesi (boş)", eksik=v["eksik"], devir=v["devir"], donem_basi=v["donem_basi"])
    for kaynak, ad in (("alim", "alim-satis"), ("iade", "iadeler"), ("uretim", "uretim"), ("sayim", "sayim"), ("sahit", "sahit-numune"),
                       ("gider_mizan", "gider-mizan"), ("stok_mizan", "stok-mizan")):
        r = bekle(mu.post(f"/api/v1/smm/donemler/{K}/veri/{kaynak}", files=dosya(f"smm-kasim-2026-{ad}")), 200, f"kasım {kaynak}").json()
        kaydet(f"7.17 Kasım {kaynak}", dolu=next(x["dolu"] for x in r["kaynaklar"] if x["kaynak"] == kaynak), eksik=r["eksik"])
    j = mu.get(f"/api/v1/smm/donemler/{K}/uretim?asama=50").json()
    kaydet("7.18 Kasım dağıtım", dagitim={k_: j["dagitim"][k_] for k_ in ("dagitilan", "mizan_720", "mizan_730", "dagitilmayan")},
           birim=[(x["kod"], tl(x["birim_maliyet"])) for x in j["kayitlar"]])
    j = bekle(mu.put(f"/api/v1/smm/donemler/{K}/dagitim", json={"havuzlar": {"40_gug": "1970000"}, "anahtarlar": {}}),
              200, "dağıtım").json()
    kaydet("7.18 Kasım dağıtım güncel", dagitilan=j["dagitilan"], dagitilmayan=j["dagitilmayan"])
    o = ozet(K)
    kaydet("7.19 Kasım SMM özeti", smm=o["smm"], uretim=o["uretim_maliyeti"], ilk_madde=o["ilk_madde"], donem_sonu_stok=o["donem_sonu_stok"],
           mizan_kiyas=o["mizan_kiyas"], tablo=[(b["hesap"], b["sonuc"]) for b in o["tablo"]])
    kaydet("7.19 Kasım devir durumu", **mu.get(f"/api/v1/smm/donemler/{K}/devir-durumu").json())
    j = mu.get("/api/v1/smm/karsilastirma").json()
    kaydet("7.20 aylar arası", yanit=json.dumps(j, ensure_ascii=False)[:1500])
    # kilit kuralları
    kaydet("7.21 Ekim kilidi aç (Muhasebe)", http=mu.put(f"/api/v1/smm/donemler/{E}/kilit", json={"kilitli": False}).status_code)
    r = mu.put(f"/api/v1/smm/donemler/{K}/kilit", json={"kilitli": True})
    kaydet("7.21 Kasım kapat", http=r.status_code, yanit=r.json() if r.status_code != 200 else "kilitli")
    if r.status_code == 409:
        kaydet("7.21 Kasım kapat zorla", http=mu.put(f"/api/v1/smm/donemler/{K}/kilit", json={"kilitli": True, "zorla": True}).status_code)
    r = gd.put(f"/api/v1/smm/donemler/{E}/kilit", json={"kilitli": False})
    kaydet("7.21 Ekim kilidi aç (GD, Kasım kilitli)", http=r.status_code, yanit=r.json())
    kaydet("7.21 Kasım kilidi aç (GD)", http=gd.put(f"/api/v1/smm/donemler/{K}/kilit", json={"kilitli": False}).status_code)
    r = gd.put(f"/api/v1/smm/donemler/{E}/kilit", json={"kilitli": False})
    kaydet("7.21 Ekim kilidi aç (GD)", http=r.status_code, uyari=r.json().get("uyari"))
    # Ekim'de değişiklik -> Kasım devri uyuşmaz -> devri yenile
    bekle(mu.patch(f"/api/v1/smm/donemler/{E}/stok/99.10.001", json={"neden": "Test: Ekim sayım düzeltmesi",
                                                                      "sayim_miktar": "5000"}), 200, "ekim düzelt")
    d = mu.get(f"/api/v1/smm/donemler/{K}/devir-durumu").json()
    kaydet("7.22 devir uyumsuz", uyumlu=d["uyumlu"], fark_kalem=d["fark_kalem"], fark_tutar=d["fark_tutar"],
           eksikler=mu.put(f"/api/v1/smm/donemler/{K}/kilit", json={"kilitli": True}).json())
    r = bekle(mu.post(f"/api/v1/smm/donemler/{K}/devir-yenile", json={"neden": "Test: Ekim düzeltmesi sonrası", "elle_ez": False}), 200, "devir yenile").json()
    kaydet("7.22 devri yenile", guncellenen=r["guncellenen"], eklenen=r["eklenen"], uyumlu=r["durum"]["uyumlu"])


def main():
    sakla = "--sakla" in sys.argv
    try:
        pass
    finally:
        cikti = KOK / "test-dongusu" / f"{ON}kuru-kosu-sonuclari.json"
        cikti.write_text(json.dumps({"senaryolar": S, "adimlar": SONUC, "hatalar": HATALAR}, ensure_ascii=False, indent=1, default=str),
                         encoding="utf-8")
        print(f"\nHATALAR ({len(HATALAR)}):")
        for h in HATALAR:
            print(" -", h)
        if not sakla:
            from backend.depo import veritabani
            if veritabani._ENGINE is not None:
                veritabani._ENGINE.dispose()
            temizle()
            print("geçici veritabanı silindi")


main()
