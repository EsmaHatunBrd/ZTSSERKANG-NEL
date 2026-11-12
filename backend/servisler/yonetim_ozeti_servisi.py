"""Tek sayfa yönetim özeti (analiz önerisi 15): seçili çalışmanın bütün başlıklarını tek yanıtta toplar. Yeni hesap kuralı yoktur;
mevcut servislerin sonuçları özetlenir, hiçbir şey kaydedilmez.

Kaynaklar ve kurallar:
- Ürünler, marj, maliyet yapısı, en pahalı, stok etkisi, uyarılar: `hesap_servisi.toplu_hesapla` (bu modülde bir kez). Satır alanları
  Genel Bakış (`GET /urunler`) ile aynı formüllerdir: malzeme = malzeme_toplami, uretim = uretim_gideri_toplami (direkt işçilik + GÜG),
  faaliyet = diger_giderler_toplami (pazarlama + yönetim), finansman = finansman["TL"]; toplamları finansman dahil maliyet TL'dir.
- Marj: ürün kâr oranı = satış TL / maliyet TL - 1 (hesaplanan ürünler). Basit ortalama ve geçen yıl satış adediyle ağırlıklı ortalama
  (Σ(satış - maliyet) x adet / Σ maliyet x adet; adedi bilinen ürün yoksa null). Hedef: genel `satis_kar` parametresi; eşik: `marj_esigi`.
- Hedef altı: `analiz_servisi.hedef_alti` (ilk 10 + toplam). Kur riski: `analiz_servisi.kur_riski(oran=0,10)` özeti ve en riskli 5 ürün.
- Teklifler: `teklif_servisi.senaryo_teklifleri`; açık = taslak + gönderildi; en eski 5 açık teklif (olusturma sırası).
- Veri kontrolü: `tutarlilik_servisi.kontroller` (süreç içi önbellekte varsa oradan; yoksa hesaplanır ve önbelleğe konur).
- Stok etkisi: stok devri kaydı yoksa null. toplam_etki_tl = Σ stok adedi x (güncel stok maliyeti - bu yılın maliyeti) (ortalama maliyet
  hesaplanan ürünlerde): stoktan gelen birimlerin bu yılın maliyetine göre farkı; negatif olabilir."""
from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from fiyat_motoru.para import SIFIR
from ..depo import modeller as m
from . import analiz_servisi, hesap_servisi as hs, onbellek, parametre_servisi as ps, stok_devri_servisi, teklif_servisi, tutarlilik_servisi
from .donusum import decimal_str, zaman_iso

KUR_ORANI = Decimal("0.10")
ACIK_DURUMLAR = ("taslak", "gonderildi")
ILK_N = 10
ILK_5 = 5


def _kontroller(s: Session, senaryo_id: int, t: date) -> dict:
    """Veri Kontrolü ucuyla aynı önbellek anahtarı: uç daha önce hesapladıysa yeniden hesaplanmaz."""
    anahtar = (senaryo_id, t.isoformat(), "tutarlilik")
    d = onbellek.al(anahtar)
    if d is None:
        nesil = onbellek.nesil()
        d = tutarlilik_servisi.kontroller(s, senaryo_id, t)
        onbellek.koy(anahtar, d, nesil)
    return d


def _urun_satirlari(s: Session, sen: m.Senaryo, t: date) -> tuple[list[dict], list[dict]]:
    """(hesaplanan satırlar, hatalı satırlar). Hesaplanan: kod, ad, malzeme, uretim, faaliyet, finansman, maliyet, satis, kar_orani, stok."""
    urunler = {u.kod: u for u in s.scalars(select(m.Urun))}
    hesaplanan, hatali = [], []
    for kod, c in hs.toplu_hesapla(s, sen.id, t):
        u = urunler[kod]
        if isinstance(c, Exception):
            hatali.append({"kod": kod, "ad": u.ad, "mesaj": str(getattr(c, "mesaj", None) or c)})
            continue
        r = c.sonuc
        maliyet = r.finansman_dahil_maliyet_tl
        hesaplanan.append({"kod": kod, "ad": u.ad, "urun_id": u.id, "malzeme": r.malzeme_toplami, "uretim": r.uretim_gideri_toplami,
                           "faaliyet": r.diger_giderler_toplami, "finansman": r.finansman.get("TL", SIFIR), "maliyet": maliyet,
                           "satis": r.satis_fiyati_tl, "kar_orani": (r.satis_fiyati_tl / maliyet - 1) if maliyet else None,
                           "stok": c.stok_devri})
    return hesaplanan, hatali


def _marj(s: Session, sen: m.Senaryo, t: date, satirlar: list[dict]) -> dict:
    oranlar = [r["kar_orani"] for r in satirlar if r["kar_orani"] is not None]
    adetler = analiz_servisi.yillik_adetler(s, sen, [s.get(m.Urun, r["urun_id"]) for r in satirlar]) if satirlar else {}
    agirlikli_pay = agirlikli_maliyet = SIFIR
    adetli = 0
    for r in satirlar:
        adet = adetler.get(r["kod"])
        if adet is None or r["kar_orani"] is None:
            continue
        adetli += 1
        agirlikli_pay += (r["satis"] - r["maliyet"]) * adet
        agirlikli_maliyet += r["maliyet"] * adet
    degerler = ps.gecerli_degerler(s, sen.id, t)
    return {"ortalama": sum(oranlar, SIFIR) / len(oranlar) if oranlar else None,
            "agirlikli_ortalama": agirlikli_pay / agirlikli_maliyet if agirlikli_maliyet else None, "adetli_urun": adetli,
            "hedef": degerler.get("satis_kar"), "marj_esigi": analiz_servisi.marj_esigi(s, sen.id), "adet_kaynagi": "satis_gecmisi"}


def _maliyet_yapisi(satirlar: list[dict]) -> dict:
    n = len(satirlar)
    toplam = sum((r["maliyet"] for r in satirlar), SIFIR)
    kalemler = {}
    for ad in ("malzeme", "uretim", "faaliyet", "finansman"):
        t = sum((r[ad] for r in satirlar), SIFIR)
        kalemler[ad] = {"toplam_tl": t, "pay_yuzde": (t / toplam * 100) if toplam else None, "urun_basina_tl": (t / n) if n else None}
    return {"urun_sayisi": n, "toplam_tl": toplam, "urun_basina_tl": (toplam / n) if n else None, "kalemler": kalemler}


def _hedef_alti(s: Session, sen: m.Senaryo, t: date, satirlar: dict[str, dict]) -> dict:
    esik, alti = analiz_servisi.hedef_alti(s, sen.id, t)
    alti.sort(key=lambda x: (x["kar_orani"], x["kod"]))
    kayitlar = [{"kod": x["kod"], "ad": x["ad"], "kar_orani": x["kar_orani"],
                 "maliyet": (satirlar.get(x["kod"]) or {}).get("maliyet"), "satis": (satirlar.get(x["kod"]) or {}).get("satis")} for x in alti[:ILK_N]]
    return {"esik": esik, "toplam": len(alti), "kayitlar": kayitlar}


def _kur_riski(s: Session, sen: m.Senaryo, t: date) -> dict:
    d = analiz_servisi.kur_riski(s, sen.id, KUR_ORANI, t)   # decimal_str çıktısı (metin)
    o = d["ozet"]
    pay = o["doviz_payi_ort"]
    riskli = [r for r in d["kayitlar"] if r["hata"] is None][:ILK_5]
    return {"oran": d["oran"], "kurlar": d["kurlar"], "doviz_payi_yuzde": (Decimal(pay) * 100) if pay is not None else None,
            "yillik_etki_tl": o["yillik_etki"], "yillik_maliyet_tl": o["yillik_maliyet"], "adetsiz_urun": o["adetsiz_urun"], "hatali": o["hatali"],
            "en_riskli": [{"kod": r["kod"], "ad": r["ad"], "maliyet": r["maliyet"], "birim_etki": r["birim_etki"], "yillik_etki": r["yillik_etki"],
                           "doviz_payi_yuzde": (Decimal(r["doviz_payi"]) * 100) if r["doviz_payi"] is not None else None} for r in riskli]}


def _teklifler(s: Session, sen: m.Senaryo) -> dict:
    satirlar = teklif_servisi.senaryo_teklifleri(s, sen.id)   # en yeni önce: (Teklif, MaliyetHesabi, Urun)
    sayilar = {d: 0 for d in teklif_servisi.DURUMLAR}
    for t, _, _ in satirlar:
        sayilar[t.durum] = sayilar.get(t.durum, 0) + 1
    acik = [(t, h, u) for t, h, u in satirlar if t.durum in ACIK_DURUMLAR]
    acik.reverse()   # en eski önce
    return {"toplam": len(satirlar), "durumlar": sayilar, "acik_sayi": len(acik),
            "acik_toplam_tl": sum((t.fiyat_tl for t, _, _ in acik), SIFIR),
            "en_eski_acik": [{"teklif_id": t.id, "urun_kodu": u.kod, "urun_ad": u.ad, "musteri": t.musteri, "durum": t.durum, "tur_no": t.tur_no,
                              "tarih": zaman_iso(t.olusturma_zamani), "hesap_tarihi": h.hesap_tarihi, "fiyat_tl": t.fiyat_tl}
                             for t, h, u in acik[:ILK_5]]}


def _veri_kontrolu(kontroller: dict) -> dict:
    o = kontroller["ozet"]
    return {"hata": o.get("hata", 0), "dikkat": o.get("dikkat", 0), "bilgi": o.get("bilgi", 0), "tamam": o.get("tamam", 0),
            "sorunlar": [{"kod": k["kod"], "baslik": k["baslik"], "durum": k["durum"], "sayi": k["sayi"]}
                         for k in kontroller["kontroller"] if k["durum"] in ("hata", "dikkat")]}


def _stok_etkisi(s: Session, sen: m.Senaryo, t: date, satirlar: list[dict]) -> dict | None:
    kayitlar = stok_devri_servisi.kayitlar(s, sen.id)
    if not kayitlar:
        return None
    etkili = [r for r in satirlar if r["stok"] and r["stok"].get("stok_etkisi")]
    toplam = SIFIR
    for r in etkili:
        st = r["stok"]
        toplam += st["adet"] * (st["guncel_stok_maliyeti"] - st["bu_yil_maliyet"])
    param = ps.gecerli_degerler(s, sen.id, t).get(stok_devri_servisi.PARAMETRE, SIFIR)
    return {"kayit_sayisi": len(kayitlar), "etkili_urun": len(etkili), "stok_adedi": sum((k.adet or SIFIR for k in kayitlar.values()), SIFIR),
            "toplam_etki_tl": toplam, "satis_ortalama_maliyetten": param == 1}


def ozet(s: Session, senaryo_id: int, tarih: date | None = None) -> dict:
    sen = hs.senaryo_getir(s, senaryo_id)
    t = tarih or date.today()
    hesaplanan, hatali = _urun_satirlari(s, sen, t)
    kodla = {r["kod"]: r for r in hesaplanan}
    kontroller = _kontroller(s, sen.id, t)
    en_pahali = sorted(hesaplanan, key=lambda r: (-r["maliyet"], r["kod"]))[:ILK_5]
    out = {"baslik": {"senaryo_id": sen.id, "sezon_ad": sen.sezon.ad, "ad": sen.ad, "tur": sen.tur, "kilitli": sen.kilitli, "hesap_tarihi": t,
                      "uretim_zamani": datetime.now(timezone.utc)},
           "urunler": {"toplam": len(hesaplanan) + len(hatali), "hesaplanan": len(hesaplanan), "hatali": len(hatali)},
           "marj": _marj(s, sen, t, hesaplanan),
           "maliyet_yapisi": _maliyet_yapisi(hesaplanan),
           "hedef_alti": _hedef_alti(s, sen, t, kodla),
           "kur_riski": _kur_riski(s, sen, t),
           "teklifler": _teklifler(s, sen),
           "veri_kontrolu": _veri_kontrolu(kontroller),
           "en_pahali": [{"kod": r["kod"], "ad": r["ad"], "maliyet": r["maliyet"], "satis": r["satis"]} for r in en_pahali],
           "stok_etkisi": _stok_etkisi(s, sen, t, hesaplanan),
           "uyarilar": hatali[:ILK_N]}
    return decimal_str(out)
