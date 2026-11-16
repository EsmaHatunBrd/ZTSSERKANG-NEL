"""Şablonları uygulamanın kendi okuyucularıyla süreç içinde doğrular (sunucu açılmaz, gerçek veritabanına dokunulmaz).

Her şablon için üç deneme:
  bos   : sablonlar/ altındaki dosya olduğu gibi (doldurulacak sayfa boş) -> anlaşılır hata ya da boş önizleme beklenir
  tek   : yalnız 'Örnek' sayfası tek sayfalık dosya olarak -> hatasız okunmalı, satır sayısı örnekle aynı olmalı
  dolu  : şablon kitabı, doldurulacak sayfaya örnek yazılmış ('kullanıcı doldurdu'; Örnek/Açıklama sayfaları da dosyada)
          -> hatasız okunmalı, satır sayısı doğru olmalı; uygula / yükle de çalıştırılır
Veritabanı bellek içi SQLite'tır (sqlite://). Ara dosyalar sablonlar/_dogrulama/ altına yazılır ve iş bitince silinir.
Sonuç: sablonlar/11-16-2026-dogrulama-sonucu.txt

Kullanım (proje kökünden):  .venv\\Scripts\\python.exe sablonlar\\11-16-2026-dogrula.py
"""
import os
import shutil
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

os.environ["VERITABANI_URL"] = "sqlite://"   # güvenlik: varsayılan veri/fiyat.db'ye hiçbir koşulda bağlanılmasın
BURASI = Path(__file__).resolve().parent
KOK = BURASI.parent
sys.path.insert(0, str(KOK))
sys.path.insert(0, str(BURASI))

import openpyxl  # noqa: E402
from backend.depo import modeller as m  # noqa: E402
from backend.depo.veritabani import Base, motor_olustur, oturum_fabrikasi  # noqa: E402
from backend import tohum  # noqa: E402
from backend.servisler import (aktarim_servisi as ak, hesap_servisi as hs, import_servisi as imp, liste_servisi as ls,  # noqa: E402
                               recete_aktarim_servisi as ra, satis_okuyucu, satis_servisi as ss, smm_recete_servisi as sr,
                               smm_veri_servisi as sv, stok_devri_servisi as sd)
from backend.servisler.hatalar import ServisHatasi  # noqa: E402
import uret  # noqa: E402

ARA = BURASI / "_dogrulama"
NEDEN = "şablon doğrulama"


def _bayt(yol: Path) -> bytes:
    return yol.read_bytes()


# ---------------------------------------------------------------- şablon başına okuyucu çağrısı -> (okunan satır sayısı, bilgi)
def v01(s, c, yol, uygula):
    on = ak.satin_alma_onizle(s, c["sid"], yol)
    n = len(on["_malzemeler"]) + len(on["hatali"])
    bilgi = f"yeni malzeme {len(on['yeni_malzeme'])}, fiyat yeni {len(on['fiyat_yeni'])}, revize {on['revize_sayisi']}, hatalı {len(on['hatali'])}"
    if uygula:
        u = ak.satin_alma_uygula(s, c["sid"], yol, date(2026, 6, 1), NEDEN)
        bilgi += f" · uygula: kart {u['malzeme_eklenen']}, fiyat {u['fiyat_yazilan']}, revize {u['revize_yazilan']}"
    return n, bilgi


def v02(s, c, yol, uygula):
    on = imp.fiyat_listesi_onizle(s, c["sid"], yol, date(2026, 7, 1))
    n = len(on["yeni"]) + len(on["degisen"]) + on["ayni"] + len(on["hatali"])
    bilgi = f"değişen {len(on['degisen'])}, aynı {on['ayni']}, yeni (yazılmaz) {len(on['yeni'])}, revize {len(on['revize'])}, hatalı {len(on['hatali'])}"
    if uygula:
        u = imp.fiyat_listesi_uygula(s, c["sid"], yol, date(2026, 7, 1), NEDEN)
        bilgi += f" · uygula: {u['yazilan']} fiyat"
    return n, bilgi


def v03(s, c, yol, uygula):
    on = ak.uretim_onizle(s, c["sid"], yol)
    n = len(on["yeni"]) + len({d["urun_kodu"] for d in on["degisen"]}) + on["ayni"]
    bilgi = f"yeni {len(on['yeni'])}, değişen alan {len(on['degisen'])}, aynı {on['ayni']}"
    if uygula:
        u = ak.uretim_uygula(s, c["sid"], yol, NEDEN)
        bilgi += f" · uygula: eklenen {u['eklenen']}, güncellenen {u['guncellenen']}"
    return n, bilgi


def v04(s, c, yol, uygula):
    on = ak.gider_onizle(s, c["sid"], yol)
    n = (len(on["havuz"]), on["ambalaj"]["yeni_adet"])
    bilgi = f"havuz {len(on['havuz'])} (değişen {sum(h['degisti'] for h in on['havuz'])}), ambalaj sınıfı {on['ambalaj']['yeni_adet']}"
    if uygula:
        u = ak.gider_uygula(s, c["sid"], yol, NEDEN)
        bilgi += f" · uygula: havuz {u['havuz']}, ambalaj {u['ambalaj']}"
    return n, bilgi


def v05(s, c, yol, uygula):
    on = ra.recete_onizle(s, c["sid"], yol)
    n = sum(x["satir_sayisi"] for x in on["sayfalar"])
    bilgi = "; ".join(f"sayfa {x['sayfa']} {x['kod']} {x['durum']}: {x['satir_sayisi']} satır, elle fiyat {x['elle_fiyat']}, elle brüt {x['elle_brut']}"
                      for x in on["sayfalar"])
    if on["hatali"]:
        bilgi += f" · hatalı sayfalar: {on['hatali']}"
    c["elle"] = [(x["elle_fiyat"], x["elle_brut"]) for x in on["sayfalar"]]
    if uygula:
        u = ra.recete_uygula(s, c["sid"], yol, [x["sayfa"] for x in on["sayfalar"]], NEDEN)
        bilgi += f" · uygula: {u['uygulanan']}, yeni ürün {u['yeni_urun']}"
    return n, bilgi


def v06(s, c, yol, uygula):
    on = sd.aktarim_onizle(s, c["sen"], yol)
    n = len(on["satirlar"]) + len(on["hatalar"])
    bilgi = f"yeni {on['yeni']}, değişen {on['degisen']}, aynı {on['ayni']}, hatalar {on['hatalar']}"
    if uygula:
        u = sd.aktarim_uygula(s, c["sen"], yol, NEDEN)
        bilgi += f" · uygula: {u}"
    return n, bilgi


def v07(s, c, yol, uygula):
    satirlar = satis_okuyucu.oku(_bayt(yol), yol.name)
    eklenen, hatalar = ss.toplu_yukle(s, satirlar, "dogrulama", yol.name)
    if hatalar:
        raise ServisHatasi("satır hataları", {"hatalar": hatalar})
    return len(satirlar), f"eklenen {eklenen}"


def v08(s, c, yol, uygula):
    satirlar = ls.dosya_oku(_bayt(yol), yol.name)
    yazilan, hatalar = ls.toplu_yukle(s, satirlar, "dogrulama", yol.name, c["sid"])
    if hatalar:
        raise ServisHatasi("satır hataları", {"hatalar": hatalar})
    return len(satirlar), f"yazılan {yazilan}"


def v09(s, c, yol, uygula):
    on = sr.onizle(s, _bayt(yol))
    bilgi = f"{on['urun_sayisi']} ürün, {on['satir_sayisi']} satır, aşama {on['asama']}, alternatifli {on['alternatifli_urun']}"
    if uygula:
        u = sr.yukle(s, _bayt(yol), yol.name, "dogrulama")
        bilgi += f" · yükle: {u['urun_sayisi']} ürün"
    return (on["urun_sayisi"], on["satir_sayisi"]), bilgi


def _smm(kaynak):
    def f(s, c, yol, uygula):
        v = sv.kaynak_yukle(s, c["donem"], kaynak, _bayt(yol), yol.name, "dogrulama")
        d = s.get(m.SmmDonem, c["donem"])
        okunan = d.veri_kaynaklari[kaynak]["satir"]
        k = next(x for x in v["kaynaklar"] if x["kaynak"] == kaynak)
        return okunan, f"okunan {okunan}, ekranda dolu {k['dolu']}"
    return f


DOGRULAYICI = {"01": (v01, 6), "02": (v02, 4), "03": (v03, 3), "04": (v04, (11, 5)), "05": (v05, 7), "06": (v06, 2), "07": (v07, 4),
               "08": (v08, 4), "09": (v09, (3, 10)), "10": (_smm("alim"), 3), "11": (_smm("iade"), 2), "12": (_smm("uretim"), 3),
               "13": (_smm("sayim"), 5), "14": (_smm("sahit"), 2), "15": (_smm("gider_mizan"), 5), "16": (_smm("stok_mizan"), 5)}


# ---------------------------------------------------------------- deneme dosyaları
def tek_sayfa(t) -> Path:
    """Şablon dosyasından yalnız 'Örnek' sayfası (değerlerle) tek sayfalık dosya."""
    wb = openpyxl.load_workbook(t.dosya)
    for ad in list(wb.sheetnames):
        if ad != "Örnek":
            del wb[ad]
    yol = ARA / f"{t.no}-tek.xlsx"
    wb.save(yol)
    return yol


def dolu(t) -> Path:
    yol = ARA / f"{t.no}-dolu.xlsx"
    uret.kitap(t, dolu=True).save(yol)
    return yol


def calistir(f, s, c, yol, uygula):
    try:
        n, bilgi = f(s, c, yol, uygula)
        s.flush()
        return True, n, bilgi
    except ServisHatasi as e:
        return False, None, f"HATA: {e.mesaj}" + (f" {e.alanlar}" if e.alanlar else "")
    except Exception as e:   # beklenmeyen istisna: okuyucu kırıldı
        return False, None, f"İSTİSNA: {type(e).__name__}: {e}"


def main() -> int:
    ARA.mkdir(exist_ok=True)
    engine = motor_olustur("sqlite://")
    Base.metadata.create_all(engine)
    s = oturum_fabrikasi(engine)()
    tohum.parametreleri_tohumla(s)
    sz = imp.sezon_getir_veya_olustur(s, "2026-2027")
    sen = m.Senaryo(sezon_id=sz.id, tur="fiyat_calismasi", ad="Şablon doğrulama", olusturan="dogrulama")
    s.add(sen); s.flush()
    c = {"sid": sen.id, "sen": sen}
    satirlar = []
    basarisiz = 0
    try:
        for t in uret.SABLONLAR:
            f, beklenen = DOGRULAYICI[t.no]
            if t.no == "06":   # stok / satış / liste için ürünler: 99.03.001 reçete aktarımından geldi; diğer iki ürün kartı elle açılır
                for kod, ad, hacim in ((uret.URUN2[0], uret.URUN2[1], 720), (uret.URUN3[0], uret.URUN3[1], 370)):
                    hs.urun_kaydet(s, kod, ad, Decimal(hacim), "Kavanoz Hattı", "Turşu/Turşu", Decimal("0.3"))
                s.flush()
            if t.no == "10":
                d = m.SmmDonem(yil=2026, ay=11, olusturan="dogrulama"); s.add(d); s.flush()
                c["donem"] = d.id
            sonuc = {}
            for ad, yol, uygula in (("bos", t.dosya, False), ("tek", tek_sayfa(t), False), ("dolu", dolu(t), True)):
                sonuc[ad] = calistir(f, s, c, yol, uygula)
                if ad == "tek" and t.no == "05":
                    sonuc["tek_elle"] = c.get("elle")
            ok_tek = sonuc["tek"][0] and sonuc["tek"][1] == beklenen
            ok_dolu = sonuc["dolu"][0] and sonuc["dolu"][1] == beklenen
            durum = "GEÇTİ" if ok_tek and ok_dolu else "KALDI"
            if t.no == "05" and ok_dolu and c.get("elle") != [(1, 0)]:
                durum = "KALDI"   # dolu kitapta beklenen: 1 elle fiyat (örnekteki kapak), 0 elle brüt
            basarisiz += durum == "KALDI"
            satirlar.append(f"[{durum}] {t.no} {t.baslik}  (dosya: {t.dosya.name}, beklenen satır: {beklenen})")
            for ad in ("bos", "tek", "dolu"):
                ok, n, bilgi = sonuc[ad]
                satirlar.append(f"    {ad:5} {'tamam' if ok else 'hata '} okunan={n}  {bilgi}")
            satirlar.append("")
    finally:
        s.close()
        shutil.rmtree(ARA, ignore_errors=True)
    satirlar.append(f"Sonuç: {len(uret.SABLONLAR) - basarisiz}/{len(uret.SABLONLAR)} şablon geçti.")
    metin = "\n".join(satirlar)
    (BURASI / "11-16-2026-dogrulama-sonucu.txt").write_text(
        "Şablon doğrulaması (uygulama okuyucularıyla, süreç içinde, bellek içi veritabanı) · 16.11.2026\n"
        "bos = şablon olduğu gibi (boş) · tek = yalnız Örnek sayfası · dolu = doldurulacak sayfaya örnek yazılmış kitap (uygula dahil)\n\n"
        + metin + "\n", encoding="utf-8")
    print(metin)
    return 1 if basarisiz else 0


if __name__ == "__main__":
    sys.exit(main())
