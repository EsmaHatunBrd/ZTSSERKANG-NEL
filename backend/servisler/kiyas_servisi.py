"""Faz 6 — Bütçe vs Gerçekleşen: iki senaryonun (A = fiyat çalışması, B = gerçekleşen) ürün bazında kıyası.

Kıyas = aynı motorun iki senaryo girdileriyle hesabı; fark B - A, fark % = (B - A) / A x 100 (A 0 ise yok).
Sapma ayrıştırması sıralıdır (zincirleme ikame): A girdilerinden başlanır, her adımda bir blok B'ninkiyle değiştirilip yeniden
hesaplanır; adımın etkisi = önceki adıma göre fark. Son adım B'nin kendisidir, bu yüzden etkilerin toplamı toplam farka tam eşittir
(etkileşim terimleri sıradaki bloğa düşer). Sıra: malzeme fiyatları -> reçete (miktar, fire, elle değerler) -> üretim bilgileri ->
gider oranları -> kurlar -> enflasyon -> diğer parametreler (faiz, stok süresi, kâr oranları, vardiya saati)."""
from dataclasses import replace
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from fiyat_motoru.hesapla import urun_maliyeti
from fiyat_motoru.modeller import MaliyetSonucu
from fiyat_motoru.para import SIFIR
from ..depo import modeller as m
from . import fiyat_servisi, hesap_servisi as hs
from .hatalar import DogrulamaHatasi, ServisHatasi

YUZ = Decimal(100)
VARSAYILAN_ESIK = Decimal(5)   # ±%5
HESAP_HATALARI = (ServisHatasi, ArithmeticError, KeyError, ValueError)

# Liste sütunları: ad -> sonuçtan değer (Teklif Kapak/dashboard ile aynı bloklar).
ALANLAR = {
    "recete_maliyeti": lambda r: r.malzeme_toplami,
    "gug": lambda r: r.uretim_gideri_toplami,
    "faaliyet": lambda r: r.diger_giderler_toplami,
    "finans": lambda r: r.finansman.get("TL", SIFIR),
    "maliyet_tl": lambda r: r.finansman_dahil_maliyet_tl,
    "maliyet_usd": lambda r: r.doviz_maliyet.get("USD"),
    "satis_tl": lambda r: r.satis_fiyati_tl,
    "satis_usd": lambda r: r.satis_fiyati_doviz.get("USD"),
}
SAPMA_ALANI = "maliyet_tl"

AYRISTIRMA_ETIKETLERI = {
    "fiyat": "Malzeme fiyatları", "recete": "Reçete (miktar, fire, elle fiyat)", "uretim": "Üretim bilgileri", "gider": "Gider oranları",
    "kur": "Döviz kurları", "enflasyon": "Enflasyon", "diger": "Diğer parametreler (faiz, stok, kâr)",
}
URETIM_ETIKETLERI = {
    "vardiya_uretim_adedi": "Vardiya üretim adedi", "dolum_personel": "Dolum personeli", "etiketleme_adedi": "Etiketleme adedi",
    "etiket_personel": "Etiket personeli", "hat": "Hat", "taze_tursu_sinifi": "Taze / Turşu", "ambalaj_hacmi": "Ambalaj",
    "suzme_kg": "Süzme kg", "mal_kabul_miktar_kg": "Mal kabul kg", "mal_kabul_fire": "Mal kabul fire", "pazar": "Pazar",
    "pazarlama_yonetim_uygula": "Pazarlama/yönetim payı",
}


def yuzde(a: Decimal | None, b: Decimal | None) -> Decimal | None:
    if a is None or b is None or a == 0:
        return None
    return (b - a) / abs(a) * YUZ


def _deger(a: Decimal | None, b: Decimal | None) -> dict:
    return {"a": a, "b": b, "fark": (b - a) if a is not None and b is not None else None, "fark_yuzde": yuzde(a, b)}


def karsi_senaryo(s: Session, sen: m.Senaryo) -> m.Senaryo | None:
    """Aynı sezonun öbür türdeki (fiyat çalışması <-> gerçekleşen) en son senaryosu; yoksa None."""
    diger = "fiyat_calismasi" if sen.tur == "gerceklesen" else "gerceklesen"
    return s.scalar(select(m.Senaryo).where(m.Senaryo.sezon_id == sen.sezon_id, m.Senaryo.tur == diger).order_by(m.Senaryo.id.desc()).limit(1))


def _senaryolar(s: Session, a: int, b: int) -> tuple[m.Senaryo, m.Senaryo]:
    if a == b:
        raise DogrulamaHatasi("kıyas için iki farklı senaryo seçin", {"a": a, "b": b})
    return hs.senaryo_getir(s, a), hs.senaryo_getir(s, b)


def _hata_metni(e: Exception) -> str:
    return str(getattr(e, "mesaj", None) or e.__class__.__name__)


def liste(s: Session, a: int, b: int, tarih: date | None = None, esik: Decimal = VARSAYILAN_ESIK) -> dict:
    """Ürün başına A | B | fark | fark % (ALANLAR). İki senaryodan birinde olmayan ürün `yalniz_a` / `yalniz_b`; hesabı yapılamayan `hata`.
    `sapan`: maliyet TL farkı eşiği (±esik %) aşıyor."""
    sa, sb = _senaryolar(s, a, b)
    tarih = tarih or date.today()
    ca = dict(hs.toplu_hesapla(s, sa.id, tarih))
    cb = dict(hs.toplu_hesapla(s, sb.id, tarih))
    urunler = {u.kod: u for u in s.scalars(select(m.Urun).where(m.Urun.kod.in_(set(ca) | set(cb))))}
    satirlar = []
    for kod in sorted(urunler):
        u = urunler[kod]
        x, y = ca.get(kod), cb.get(kod)
        satir = {"kod": kod, "ad": u.ad, "hat": u.hat, "ambalaj_hacmi": u.ambalaj_hacmi, "gecici_kod": u.gecici_kod,
                 "durum": "iki", "hata": None, "alanlar": None, "sapma_yuzde": None, "sapan": False}
        if x is None or y is None:
            satir["durum"] = "yalniz_a" if y is None else "yalniz_b"
        elif isinstance(x, Exception) or isinstance(y, Exception):
            satir["durum"] = "hata"
            satir["hata"] = "; ".join(f"{t}: {_hata_metni(e)}" for t, e in (("A", x), ("B", y)) if isinstance(e, Exception))
        else:
            alanlar = {ad: _deger(f(x.sonuc), f(y.sonuc)) for ad, f in ALANLAR.items()}
            satir["alanlar"] = alanlar
            satir["sapma_yuzde"] = alanlar[SAPMA_ALANI]["fark_yuzde"]
            satir["sapan"] = satir["sapma_yuzde"] is not None and abs(satir["sapma_yuzde"]) > esik
        satirlar.append(satir)
    iki = [x for x in satirlar if x["durum"] == "iki"]
    sapmalar = [x["sapma_yuzde"] for x in iki if x["sapma_yuzde"] is not None]
    ozet = {"karsilastirilan": len(iki), "sapan": sum(1 for x in iki if x["sapan"]),
            "yalniz_a": sum(1 for x in satirlar if x["durum"] == "yalniz_a"), "yalniz_b": sum(1 for x in satirlar if x["durum"] == "yalniz_b"),
            "hatali": sum(1 for x in satirlar if x["durum"] == "hata"),
            "ortalama_sapma_yuzde": (sum(sapmalar, SIFIR) / len(sapmalar)) if sapmalar else None}
    return {"a": sa, "b": sb, "esik": esik, "tarih": tarih, "satirlar": satirlar, "ozet": ozet}


def _recete_eslestir(ca: hs.HesapCiktisi, cb: hs.HesapCiktisi) -> list[dict]:
    """Malzeme satırlarını koda göre eşler (aynı kod birden çoksa sırayla). A sırası korunur; yalnız B'de olanlar sona eklenir."""
    def satirlar(c: hs.HesapCiktisi) -> list[dict]:
        malz = [x for x in c.sonuc.satirlar if x.grup == "malzeme"]
        return [{"kod": x.kod, "kalem": x.kalem, "miktar": r.miktar, "fire": r.fire_orani, "brut_miktar": x.brut_miktar,
                 "birim_fiyat": x.birim_fiyat, "tutar": x.tutar} for x, r in zip(malz, c.girdi.recete)]
    kalan: dict[str, list[dict]] = {}
    for y in satirlar(cb):
        kalan.setdefault(y["kod"], []).append(y)
    out = []
    for x in satirlar(ca):
        aday = kalan.get(x["kod"])
        y = aday.pop(0) if aday else None
        out.append(_recete_satiri(x, y))
    out += [_recete_satiri(None, y) for liste_ in kalan.values() for y in liste_]
    return out


RECETE_ALANLARI = ("miktar", "fire", "brut_miktar", "birim_fiyat", "tutar")


def _recete_satiri(x: dict | None, y: dict | None) -> dict:
    ref = x or y
    deg = [a for a in RECETE_ALANLARI if x is not None and y is not None and x[a] != y[a]]
    return {"kod": ref["kod"], "kalem": ref["kalem"], "durum": "iki" if x and y else ("yalniz_a" if x else "yalniz_b"),
            "a": {a: x[a] for a in RECETE_ALANLARI} if x else None, "b": {a: y[a] for a in RECETE_ALANLARI} if y else None,
            "fark_tutar": (y["tutar"] if y else SIFIR) - (x["tutar"] if x else SIFIR), "degisen": deg}


def _gider_satirlari(ra: MaliyetSonucu, rb: MaliyetSonucu) -> list[dict]:
    gb = {x.kod: x for x in rb.satirlar if x.grup != "malzeme"}
    out = []
    for x in (x for x in ra.satirlar if x.grup != "malzeme"):
        y = gb.get(x.kod)
        out.append({"kod": x.kod, "kalem": x.kalem, "grup": x.grup, **_deger(x.tutar, y.tutar if y else None)})
    return out


def _uretim_satirlari(ca: hs.HesapCiktisi, cb: hs.HesapCiktisi) -> list[dict]:
    ua, ub = ca.girdi.uretim, cb.girdi.uretim
    metin = lambda v: ("Evet" if v else "Hayır") if isinstance(v, bool) else str(v)
    return [{"alan": a, "etiket": e, "a": metin(getattr(ua, a)), "b": metin(getattr(ub, a)), "degisti": getattr(ua, a) != getattr(ub, a)}
            for a, e in URETIM_ETIKETLERI.items()]


def _parametre_satirlari(ca: hs.HesapCiktisi, cb: hs.HesapCiktisi) -> list[dict]:
    pa, pb = ca.kullanilan_parametreler, cb.kullanilan_parametreler
    return [{"anahtar": k, "a": pa.get(k), "b": pb.get(k), "degisti": pa.get(k) != pb.get(k)} for k in sorted(set(pa) | set(pb))]


def ayristir(ca: hs.HesapCiktisi, cb: hs.HesapCiktisi, malz_a: dict, malz_b: dict) -> list[dict]:
    """Zincirleme ikame (modül belgesi). Her adım {kaynak, etiket, fark}: finansman dahil maliyet TL üzerindeki etki."""
    ga, gb, oa, ob, pa, pb = ca.girdi, cb.girdi, ca.oranlar, cb.oranlar, ca.parametreler, cb.parametreler
    adimlar = [
        ("fiyat", ga, malz_b, oa, pa),
        ("recete", replace(ga, recete=gb.recete), malz_b, oa, pa),
        ("uretim", gb, malz_b, oa, pa),
        ("gider", gb, malz_b, ob, pa),
        ("kur", gb, malz_b, ob, replace(pa, kurlar=pb.kurlar)),
        ("enflasyon", gb, malz_b, ob, replace(pa, kurlar=pb.kurlar, enflasyon=pb.enflasyon)),
        ("diger", gb, malz_b, ob, pb),
    ]
    onceki = urun_maliyeti(ga, malz_a, oa, pa, firesiz_hesapla=False).finansman_dahil_maliyet_tl
    out = []
    for kaynak, g, mz, o, p in adimlar:
        simdi = urun_maliyeti(g, mz, o, p, firesiz_hesapla=False).finansman_dahil_maliyet_tl
        out.append({"kaynak": kaynak, "etiket": AYRISTIRMA_ETIKETLERI[kaynak], "fark": simdi - onceki})
        onceki = simdi
    return out


def urun(s: Session, kod: str, a: int, b: int, tarih: date | None = None) -> dict:
    """Tek ürün: toplamlar (ALANLAR), reçete eşlemesi, gider kalemleri, üretim bilgileri, parametreler ve sapma ayrıştırması.
    İki senaryodan birinde hesap yapılamazsa 422 (mesajda hangi taraf)."""
    sa, sb = _senaryolar(s, a, b)
    u = hs.urun_getir(s, kod)
    tarih = tarih or date.today()
    ba, bb = hs.HesapBaglami(), hs.HesapBaglami()
    cikti = {}
    for taraf, sen, bag in (("A", sa, ba), ("B", sb, bb)):
        try:
            cikti[taraf] = hs.hesapla(s, kod, sen.id, tarih, baglam=bag)
        except HESAP_HATALARI as e:
            raise DogrulamaHatasi(f"{taraf} ({sen.ad}) hesaplanamadı: {_hata_metni(e)}", {"taraf": taraf, "senaryo_id": sen.id}) from e
    ca, cb = cikti["A"], cikti["B"]
    malz_a = ba.al(("malzemeler", sa.id, tarih), lambda: fiyat_servisi.gecerli_fiyatlar(s, sa.id, tarih))
    malz_b = bb.al(("malzemeler", sb.id, tarih), lambda: fiyat_servisi.gecerli_fiyatlar(s, sb.id, tarih))
    toplam = _deger(ca.sonuc.finansman_dahil_maliyet_tl, cb.sonuc.finansman_dahil_maliyet_tl)
    return {"kod": u.kod, "ad": u.ad, "a": sa, "b": sb, "tarih": tarih,
            "alanlar": {ad: _deger(f(ca.sonuc), f(cb.sonuc)) for ad, f in ALANLAR.items()},
            "recete": _recete_eslestir(ca, cb), "giderler": _gider_satirlari(ca.sonuc, cb.sonuc),
            "uretim": _uretim_satirlari(ca, cb), "parametreler": _parametre_satirlari(ca, cb),
            "ayristirma": ayristir(ca, cb, malz_a, malz_b), "toplam_fark": toplam["fark"]}
