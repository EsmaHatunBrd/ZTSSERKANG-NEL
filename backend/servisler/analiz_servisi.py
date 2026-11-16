"""Analizler (1. dalga): ya olursa (kur / ambalaj / hammadde / üretim adedi varsayımıyla kaydetmeden yeniden hesap), malzeme zam etkisi,
hedef marjın altındaki ürünler ve fiyat girişi sapma eşikleri. Hesaplar mevcut motorla yapılır; hiçbir şey kaydedilmez.
Oranlar 0,10 = %10."""
from dataclasses import replace
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from fiyat_motoru.para import SIFIR
from ..depo import modeller as m
from . import fiyat_servisi, hesap_servisi as hs, parametre_servisi as ps, senaryo_servisi
from .donusum import decimal_str
from .hatalar import BulunamadiHatasi, DogrulamaHatasi, ServisHatasi

AMBALAJ_TIPI = "0008-Ambalaj Malzeme"
HAMMADDE_TIPI = "0001-Hammadde"
# Senaryo parametreleri (girilmezse varsayılan): hedef kâr oranı eşiği, fiyat girişinde sorulacak değişim eşikleri.
MARJ_ESIGI, VARSAYILAN_MARJ_ESIGI = "marj_esigi", Decimal("0.10")
FIYAT_ESIK_TL, VARSAYILAN_FIYAT_ESIK_TL = "fiyat_uyari_esigi.TL", Decimal("0.15")
FIYAT_ESIK_DOVIZ, VARSAYILAN_FIYAT_ESIK_DOVIZ = "fiyat_uyari_esigi.doviz", Decimal("0.10")
FIYAT_SAPMA = "fiyat_sapma"   # hata kodu: fiyat eşikten fazla değişiyor, onay gerekli
EN_COK_ORAN = Decimal("5")    # varsayım oranı en çok %500


def _deger(s: Session, senaryo_id: int, anahtar: str, varsayilan: Decimal, tarih: date | None = None) -> Decimal:
    return ps.gecerli_degerler(s, senaryo_id, tarih or date.today()).get(anahtar, varsayilan)


def marj_esigi(s: Session, senaryo_id: int) -> Decimal:
    return _deger(s, senaryo_id, MARJ_ESIGI, VARSAYILAN_MARJ_ESIGI)


def _oran_dogrula(ad: str, v) -> Decimal:
    v = Decimal(str(v or 0))
    if not (Decimal(-1) < v <= EN_COK_ORAN):
        raise DogrulamaHatasi(f"{ad} -%100 ile +%500 arasında olmalı", {ad: str(v)})
    return v


def _varsayimli_hesap(s: Session, sen: m.Senaryo, kodlar: list[str], fiyat_carpani, kur_orani: Decimal, adet_orani: Decimal,
                      tarih: date, kur_anahtarlari: set[str] | None = None) -> dict[str, object]:
    """Her ürün için (önce, sonra) HesapCiktisi ya da hata. `fiyat_carpani(malzeme) -> Decimal` malzeme fiyatını, `kur_orani` döviz
    kurlarını, `adet_orani` vardiya üretim adedini değiştirir. `kur_anahtarlari` (ör. {"kur.USD"}) verilirse yalnız o kurlar değişir;
    None: hepsi. İki bağlam: önceki hesap ile varsayımlı hesap aynı fiyat haritasını paylaşmaz."""
    once_b, sonra_b = hs.HesapBaglami(), hs.HesapBaglami()
    malzemeler = fiyat_servisi.gecerli_fiyatlar(s, sen.id, tarih)
    degisik = {k: (replace(mz, fiyat=mz.fiyat * c) if (c := fiyat_carpani(mz)) != 1 else mz) for k, mz in malzemeler.items()}
    once_b.al(("malzemeler", sen.id, tarih), lambda: malzemeler)
    sonra_b.al(("malzemeler", sen.id, tarih), lambda: degisik)
    kurlar = {k: v for k, v in ps.gecerli_degerler(s, sen.id, tarih).items() if k.startswith("kur.") and (kur_anahtarlari is None or k in kur_anahtarlari)}
    param_ov = {k: v * (1 + kur_orani) for k, v in kurlar.items()} if kur_orani else {}
    out = {}
    for kod in kodlar:
        try:
            once = hs.hesapla(s, kod, sen.id, tarih, baglam=once_b)
            ov: dict = {}
            if param_ov:
                ov["parametreler"] = param_ov
            if adet_orani:
                ov["uretim"] = {"vardiya_uretim_adedi": once.girdi.uretim.vardiya_uretim_adedi * (1 + adet_orani)}
            sonra = hs.hesapla(s, kod, sen.id, tarih, override=ov or None, baglam=sonra_b)
            out[kod] = (once, sonra)
        except (ServisHatasi, KeyError, ValueError, ArithmeticError) as e:
            out[kod] = e
    return out


def _satirlar(s: Session, sen: m.Senaryo, sonuclar: dict, esik: Decimal) -> tuple[list[dict], dict]:
    urunler = {u.kod: u for u in s.scalars(select(m.Urun).where(m.Urun.kod.in_(list(sonuclar))))}
    satirlar, farklar = [], []
    for kod, c in sonuclar.items():
        u = urunler[kod]
        if isinstance(c, Exception):
            satirlar.append({"kod": kod, "ad": u.ad, "hat": u.hat, "hata": str(getattr(c, "mesaj", None) or c), "maliyet_once": None, "maliyet_sonra": None,
                             "fark_tl": None, "fark_yuzde": None, "satis_once": None, "satis_sonra": None, "kar_orani": None, "mevcut_fiyatla_kar": None,
                             "esik_alti": False})
            continue
        once, sonra = c
        mo, ms = once.sonuc.finansman_dahil_maliyet_tl, sonra.sonuc.finansman_dahil_maliyet_tl
        satis = once.sonuc.satis_fiyati_tl
        kar_mevcut = (satis / ms - 1) if ms else None    # satış fiyatı değişmezse kalan kâr oranı
        fy = (ms / mo - 1) if mo else None
        if fy is not None:
            farklar.append(fy)
        satirlar.append({"kod": kod, "ad": u.ad, "hat": u.hat, "hata": None, "maliyet_once": mo, "maliyet_sonra": ms, "fark_tl": ms - mo,
                         "fark_yuzde": fy, "satis_once": satis, "satis_sonra": sonra.sonuc.satis_fiyati_tl,
                         "kar_orani": once.parametreler.satis_kar_orani, "mevcut_fiyatla_kar": kar_mevcut,
                         "esik_alti": kar_mevcut is not None and kar_mevcut < esik})
    satirlar.sort(key=lambda r: (r["fark_yuzde"] is None, -(r["fark_yuzde"] or SIFIR)))
    ozet = {"urun_sayisi": len(satirlar), "etkilenen": sum(1 for f in farklar if f != 0),
            "ort_fark_yuzde": sum(farklar, SIFIR) / len(farklar) if farklar else None,
            "en_yuksek_fark_yuzde": max(farklar) if farklar else None, "esik_alti": sum(1 for r in satirlar if r["esik_alti"]),
            "hatali": sum(1 for r in satirlar if r["hata"])}
    return satirlar, ozet


def ya_olursa(s: Session, senaryo_id: int, kur: Decimal = SIFIR, ambalaj: Decimal = SIFIR, hammadde: Decimal = SIFIR, adet: Decimal = SIFIR,
              tarih: date | None = None) -> dict:
    """Varsayımlar oran (0,10 = %10): kur tüm döviz kurlarına, ambalaj/hammadde o tipteki malzeme fiyatlarına, adet vardiya üretim adedine."""
    sen = hs.senaryo_getir(s, senaryo_id)
    kur, ambalaj, hammadde, adet = (_oran_dogrula(a, v) for a, v in (("kur", kur), ("ambalaj", ambalaj), ("hammadde", hammadde), ("adet", adet)))
    carpan = {AMBALAJ_TIPI: 1 + ambalaj, HAMMADDE_TIPI: 1 + hammadde}
    t = tarih or date.today()
    kodlar = sorted(senaryo_servisi.uye_urun_kodlari(s, sen.id))
    sonuclar = _varsayimli_hesap(s, sen, kodlar, lambda mz: carpan.get(mz.tip, Decimal(1)), kur, adet, t)
    esik = marj_esigi(s, sen.id)
    satirlar, ozet = _satirlar(s, sen, sonuclar, esik)
    return decimal_str({"varsayimlar": {"kur": kur, "ambalaj": ambalaj, "hammadde": hammadde, "adet": adet}, "marj_esigi": esik,
                        "ozet": ozet, "kayitlar": satirlar})


def malzeme_kullanimi(s: Session, senaryo_id: int, kod: str) -> list[str]:
    """Malzemenin aktif reçetesinde geçtiği senaryo üyesi ürün kodları."""
    q = (select(m.Urun.kod).join(m.Recete, m.Recete.urun_id == m.Urun.id).join(m.ReceteSatiri, m.ReceteSatiri.recete_id == m.Recete.id)
         .where(m.Recete.senaryo_id == senaryo_id, m.Recete.aktif == True, m.Urun.aktif == True, m.ReceteSatiri.malzeme_kodu == kod))   # noqa: E712
    return sorted(set(s.scalars(q)))


def zam_etkisi(s: Session, senaryo_id: int, malzeme_kodu: str, oran: Decimal, tarih: date | None = None) -> dict:
    sen = hs.senaryo_getir(s, senaryo_id)
    mz = s.scalar(select(m.Malzeme).where(m.Malzeme.kod == (malzeme_kodu or "").strip()))
    if mz is None:
        raise BulunamadiHatasi("malzeme bulunamadı", {"malzeme_kodu": malzeme_kodu})
    oran = _oran_dogrula("oran", oran)
    t = tarih or date.today()
    fiyat = fiyat_servisi.gecerli_fiyatlar(s, sen.id, t).get(mz.kod)
    kodlar = malzeme_kullanimi(s, sen.id, mz.kod)
    sonuclar = _varsayimli_hesap(s, sen, kodlar, lambda x: (1 + oran) if x.kod == mz.kod else Decimal(1), SIFIR, SIFIR, t)
    esik = marj_esigi(s, sen.id)
    satirlar, ozet = _satirlar(s, sen, sonuclar, esik)
    return decimal_str({"malzeme": {"kod": mz.kod, "ad": mz.ad, "tip": mz.tip, "birim": mz.birim,
                                    "fiyat": fiyat.fiyat if fiyat else None, "para_birimi": fiyat.para_birimi if fiyat else mz.para_birimi,
                                    "yeni_fiyat": fiyat.fiyat * (1 + oran) if fiyat else None},
                        "oran": oran, "marj_esigi": esik, "ozet": ozet, "kayitlar": satirlar})


def hedef_alti(s: Session, senaryo_id: int, tarih: date | None = None) -> tuple[Decimal, list[dict]]:
    """Kâr oranı (ürüne özel ya da genel `satis_kar`) marj eşiğinin altında kalan senaryo üyesi ürünler. Satış geçmişi gelene kadar
    'marj' çalışmadaki kâr oranıdır."""
    sen = hs.senaryo_getir(s, senaryo_id)
    t = tarih or date.today()
    esik = marj_esigi(s, sen.id)
    satirlar = ps.parametre_satirlari(s, sen.id, t)
    out = []
    for u in s.scalars(select(m.Urun).where(m.Urun.kod.in_(senaryo_servisi.uye_urun_kodlari(s, sen.id))).order_by(m.Urun.kod)):
        kar = ps.degerleri_coz(satirlar, u.id).get("satis_kar")
        if kar is not None and kar < esik:
            out.append({"kod": u.kod, "ad": u.ad, "kar_orani": kar})
    return esik, out


def fiyat_sapmasi(s: Session, senaryo_id: int, kod: str, yeni: Decimal, para_birimi: str | None, tarih: date) -> dict | None:
    """Yeni fiyat geçerli fiyattan eşikten fazla farklıysa ayrıntı; değilse (ya da önceki fiyat yok / 0 / para birimi farklı) None.
    Eşik TL fiyatlarda `fiyat_uyari_esigi.TL`, dövizlilerde `fiyat_uyari_esigi.doviz` (girilmezse %15 / %10)."""
    mz = s.scalar(select(m.Malzeme).where(m.Malzeme.kod == kod))
    if mz is None:
        return None
    eski = fiyat_servisi.gecerli_kayitlar_kodla(s, senaryo_id, tarih).get(kod)
    pb = (para_birimi or (eski.para_birimi if eski else None) or mz.para_birimi or "TL").upper()
    if eski is None or not eski.fiyat or (eski.para_birimi or mz.para_birimi or "TL").upper() != pb:
        return None
    degerler = ps.gecerli_degerler(s, senaryo_id, tarih)
    esik = degerler.get(FIYAT_ESIK_TL, VARSAYILAN_FIYAT_ESIK_TL) if pb == "TL" else degerler.get(FIYAT_ESIK_DOVIZ, VARSAYILAN_FIYAT_ESIK_DOVIZ)
    oran = Decimal(yeni) / eski.fiyat - 1
    if abs(oran) <= esik:
        return None
    return decimal_str({"eski_fiyat": eski.fiyat, "yeni_fiyat": Decimal(yeni), "para_birimi": pb, "oran": oran, "esik": esik})


def eksik_fiyat_etkisi(s: Session, senaryo_id: int, urunler: list[tuple[str, object, set[str]]]) -> list[dict]:
    """Fiyatı 0 ya da hiç olmayan malzemelerden etkilenen ürünler: kaç satır, hangi malzemeler ve (başka bir çalışmada TL fiyatı biliniyorsa)
    en az kaç TL eksik. `urunler`: (ürün kodu, HesapCiktisi, fiyatsız malzeme kodları) — yeniden hesap yapılmaz."""
    son_bilinen: dict[str, Decimal] = {}
    q = (select(m.Malzeme.kod, m.MalzemeFiyati.fiyat, m.MalzemeFiyati.para_birimi).join(m.MalzemeFiyati, m.MalzemeFiyati.malzeme_id == m.Malzeme.id)
         .where(m.MalzemeFiyati.senaryo_id != senaryo_id, m.MalzemeFiyati.fiyat > 0).order_by(m.MalzemeFiyati.gecerlilik_basi))
    for kod, fiyat, pb in s.execute(q):
        if (pb or "TL").upper() == "TL":
            son_bilinen[kod] = fiyat   # tarih sırasıyla: son yazılan en yeni
    out = []
    for kod, c, fiyatsiz in urunler:
        eksik = [r for r in c.sonuc.satirlar if r.grup == "malzeme" and r.kod in fiyatsiz]
        if not eksik:
            continue
        bilinen = [r for r in eksik if r.kod in son_bilinen]
        out.append({"kod": kod, "satir": len(eksik), "malzemeler": sorted({r.kod for r in eksik}),
                    "tahmini_eksik_tl": sum((r.brut_miktar * son_bilinen[r.kod] for r in bilinen), SIFIR) if bilinen else None,
                    "maliyet_tl": c.sonuc.finansman_dahil_maliyet_tl})
    out.sort(key=lambda x: (-x["satir"], x["kod"]))
    return out


# ---------------------------------------------------------------- Kur riski ve kârlılık haritası
KARLILIK_BOLGELERI = ("yuksek_adet_yuksek_marj", "yuksek_adet_dusuk_marj", "dusuk_adet_yuksek_marj", "dusuk_adet_dusuk_marj")


def _gecen_yil(s: Session, sen: m.Senaryo, urun_idleri: set[int]) -> dict[int, dict]:
    from . import karsilastirma_servisi as ks   # yerel içe aktarma: modül yükleme sırasını etkilemesin
    return ks.gecen_yil_toplu(s, sen, urun_idleri)


def yillik_adetler(s: Session, sen: m.Senaryo, urunler: list[m.Urun], gecen: dict[int, dict] | None = None) -> dict[str, Decimal]:
    """Ürün kodu -> yıllık adet. Kaynak: geçen yıl satış adedi (sezon başlangıcından önceki 12 ayın satış geçmişi, tüm para birimleri
    toplamı). Sistemde yıllık üretim hedefi yok (`Üretim Adetleri.hedef_uretim` vardiyalık); satışı olmayan ürün sözlükte yoktur."""
    if gecen is None:
        gecen = _gecen_yil(s, sen, {u.id for u in urunler})
    out = {}
    for u in urunler:
        g = gecen.get(u.id)
        if g:
            adet = sum((Decimal(p["adet"]) for p in g["para_birimleri"].values()), SIFIR)
            if adet > 0:
                out[u.kod] = adet
    return out


def _maliyet_farki(c) -> Decimal | None:
    """(önce, sonra) çiftinde finansman dahil maliyet farkı; hata ise None."""
    return None if isinstance(c, Exception) else c[1].sonuc.finansman_dahil_maliyet_tl - c[0].sonuc.finansman_dahil_maliyet_tl


def kur_riski(s: Session, senaryo_id: int, oran: Decimal = Decimal("0.10"), tarih: date | None = None) -> dict:
    """Kurlar `oran` kadar artarsa (0,10 = %10) ürün maliyetleri ne kadar artar. Yöntem: `_varsayimli_hesap` ile önce tüm kurlar birlikte,
    sonra her kur tek başına artırılarak yeniden hesap (kaydedilmez). Maliyet döviz kalemlerinde kura doğrusal olduğundan
    birim_etki = maliyet(kur x (1+oran)) - maliyet(bugün), döviz payı = birim_etki / maliyet / oran (USD/EUR payı aynı yolla, tek kurla).
    Yıllık etki = birim_etki x yıllık adet (geçen yıl satış adedi; yoksa null, ürün listeden düşmez)."""
    sen = hs.senaryo_getir(s, senaryo_id)
    oran = _oran_dogrula("oran", oran)
    t = tarih or date.today()
    kurlar = {k: v for k, v in sorted(ps.gecerli_degerler(s, sen.id, t).items()) if k.startswith("kur.")}
    kodlar = sorted(senaryo_servisi.uye_urun_kodlari(s, sen.id))
    birim = lambda mz: Decimal(1)
    birlikte = _varsayimli_hesap(s, sen, kodlar, birim, oran, SIFIR, t)
    tekil = {k[4:]: _varsayimli_hesap(s, sen, kodlar, birim, oran, SIFIR, t, {k}) for k in kurlar}
    urunler = {u.kod: u for u in s.scalars(select(m.Urun).where(m.Urun.kod.in_(kodlar)))}
    adetler = yillik_adetler(s, sen, list(urunler.values()))

    satirlar, pb_etki = [], {pb: SIFIR for pb in tekil}
    for kod in kodlar:
        u, c = urunler[kod], birlikte[kod]
        adet = adetler.get(kod)
        bos = {"kod": kod, "ad": u.ad, "hat": u.hat, "maliyet": None, "doviz_payi": None, "usd_payi": None, "eur_payi": None, "birim_etki": None,
               "yeni_maliyet": None, "yillik_adet": adet, "yillik_etki": None, "hata": None, "_yillik_maliyet": None}
        if isinstance(c, Exception):
            satirlar.append({**bos, "hata": str(getattr(c, "mesaj", None) or c)})
            continue
        maliyet, be = c[0].sonuc.finansman_dahil_maliyet_tl, _maliyet_farki(c)
        pay = lambda x: (x / maliyet / oran) if (x is not None and maliyet and oran) else None
        pb_farklari = {pb: _maliyet_farki(r[kod]) for pb, r in tekil.items()}
        if adet is not None:
            for pb, e in pb_farklari.items():
                if e is not None:
                    pb_etki[pb] += e * adet
        satirlar.append({**bos, "maliyet": maliyet, "doviz_payi": pay(be), "usd_payi": pay(pb_farklari.get("USD")), "eur_payi": pay(pb_farklari.get("EUR")),
                         "birim_etki": be, "yeni_maliyet": c[1].sonuc.finansman_dahil_maliyet_tl,
                         "yillik_etki": be * adet if adet is not None else None, "_yillik_maliyet": maliyet * adet if adet is not None else None})
    satirlar.sort(key=lambda r: (r["yillik_etki"] is None, -(r["yillik_etki"] or SIFIR), r["birim_etki"] is None, -(r["birim_etki"] or SIFIR), r["kod"]))
    adetli = [r for r in satirlar if r["_yillik_maliyet"] is not None]
    yillik_maliyet = sum((r["_yillik_maliyet"] for r in adetli), SIFIR)
    yillik_etki = sum((r["yillik_etki"] for r in adetli), SIFIR)
    if adetli:   # yıllık maliyetle ağırlıklı ortalama = Σ yıllık etki / oran / Σ yıllık maliyet
        ort = yillik_etki / oran / yillik_maliyet if (yillik_maliyet and oran) else None
    else:        # hiçbir üründe adet yok: düz ortalama
        paylar = [r["doviz_payi"] for r in satirlar if r["doviz_payi"] is not None]
        ort = sum(paylar, SIFIR) / len(paylar) if paylar else None
    for r in satirlar:
        del r["_yillik_maliyet"]
    toplam_pb = sum(pb_etki.values(), SIFIR)
    ozet = {"urun_sayisi": len(satirlar), "doviz_payi_ort": ort, "yillik_maliyet": yillik_maliyet, "yillik_etki": yillik_etki,
            "adetsiz_urun": sum(1 for r in satirlar if r["hata"] is None and r["yillik_adet"] is None), "hatali": sum(1 for r in satirlar if r["hata"])}
    para_birimleri = [{"para_birimi": pb, "yillik_etki": e, "pay": (e / toplam_pb) if toplam_pb else None}
                      for pb, e in sorted(pb_etki.items(), key=lambda x: (-x[1], x[0]))]
    return decimal_str({"oran": oran, "kurlar": {k[4:]: v for k, v in kurlar.items()}, "adet_kaynagi": "satis_gecmisi", "ozet": ozet,
                        "para_birimleri": para_birimleri, "kayitlar": satirlar})


def _gecen_yil_tl_fiyat(g: dict | None, kurlar: dict[str, Decimal]) -> Decimal | None:
    """Geçen yıl satışlarının adet ağırlıklı TL fiyatı. Dövizli satışlar bugünkü `kur.<pb>` ile TL'ye çevrilir; kuru olmayan para birimi atlanır."""
    if not g:
        return None
    tutar = adet = SIFIR
    for pb, p in g["para_birimleri"].items():
        kur = Decimal(1) if pb.upper() == "TL" else kurlar.get(f"kur.{pb.upper()}")
        if not kur:
            continue
        a = Decimal(p["adet"])
        tutar += Decimal(p["fiyat"]) * kur * a
        adet += a
    return tutar / adet if adet > 0 else None


def _medyan(xs: list[Decimal]) -> Decimal | None:
    if not xs:
        return None
    xs, n = sorted(xs), len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def analiz_maliyeti(c) -> tuple[Decimal, str]:
    """(maliyet, kaynak): `satis_ortalama_maliyetten` = 1 ve stokta kalan etkisi varsa ortalama maliyet ("ortalama"), yoksa bu yılın
    finansman dahil maliyeti ("bu_yil"). Karar hesap_servisi.hesapla'da verilir (HesapCiktisi.satis_ortalamadan)."""
    if c.satis_ortalamadan and c.stok_devri and c.stok_devri.get("ortalama_maliyet") is not None:
        return c.stok_devri["ortalama_maliyet"], "ortalama"
    return c.sonuc.finansman_dahil_maliyet_tl, "bu_yil"


def _karlilik_satirlari(s: Session, sen: m.Senaryo, t: date) -> tuple[list[dict], Decimal, Decimal | None]:
    """Kârlılık satırları (Decimal, sıralanmamış, bölgeleri dolu), marj eşiği ve adet eşiği (medyan). Satırlarda iç alanlar
    `_gecen_yil_fiyat` (geçen yıl adet ağırlıklı TL fiyat; yoksa None) ve `_hesap_fiyati` (çalışmanın satış fiyatı) da vardır."""
    from . import aile as aile_servisi
    esik_marj = marj_esigi(s, sen.id)
    kurlar = {k: v for k, v in ps.gecerli_degerler(s, sen.id, t).items() if k.startswith("kur.")}
    hesaplar = hs.toplu_hesapla(s, sen.id, t)
    urunler = {u.kod: u for u in s.scalars(select(m.Urun).where(m.Urun.kod.in_([k for k, _ in hesaplar])))}
    gecen = _gecen_yil(s, sen, {u.id for u in urunler.values()})
    adetler = yillik_adetler(s, sen, list(urunler.values()), gecen)
    satirlar = []
    for kod, c in hesaplar:
        u = urunler[kod]
        adet = adetler.get(kod)
        r = {"kod": kod, "ad": u.ad, "aile": u.aile or aile_servisi.aile_turet(u.ad), "adet": adet, "maliyet": None, "satis_fiyati": None,
             "marj": None, "fiyat_kaynagi": None, "yillik_kar": None, "bolge": None, "hata": None, "maliyet_kaynagi": None,
             "_gecen_yil_fiyat": None, "_hesap_fiyati": None}
        if isinstance(c, Exception):
            r["hata"] = str(getattr(c, "mesaj", None) or c)
            satirlar.append(r)
            continue
        maliyet, maliyet_kaynagi = analiz_maliyeti(c)
        gy = _gecen_yil_tl_fiyat(gecen.get(u.id), kurlar)
        satis, kaynak = (gy, "satis_gecmisi") if gy is not None else (c.sonuc.satis_fiyati_tl, "hesap")
        r.update(maliyet=maliyet, maliyet_kaynagi=maliyet_kaynagi, satis_fiyati=satis, fiyat_kaynagi=kaynak, marj=(satis / maliyet - 1) if maliyet else None,
                 yillik_kar=(satis - maliyet) * adet if adet is not None else None, _gecen_yil_fiyat=gy, _hesap_fiyati=c.sonuc.satis_fiyati_tl)
        satirlar.append(r)
    esik_adet = _medyan([r["adet"] for r in satirlar if r["adet"] is not None and r["hata"] is None])
    for r in satirlar:
        if r["hata"] is None and r["adet"] is not None and r["marj"] is not None:
            r["bolge"] = f"{'yuksek' if r['adet'] >= esik_adet else 'dusuk'}_adet_{'yuksek' if r['marj'] >= esik_marj else 'dusuk'}_marj"
    return satirlar, esik_marj, esik_adet


def _ic_alanlari_at(r: dict) -> dict:
    return {k: v for k, v in r.items() if not k.startswith("_")}


def karlilik(s: Session, senaryo_id: int, tarih: date | None = None) -> dict:
    """Kârlılık haritası (adet x marj). Maliyet = finansman dahil maliyet (`satis_ortalama_maliyetten` = 1 ve stokta kalan varsa ortalama
    maliyet; `maliyet_kaynagi`); satış fiyatı = geçen yıl satış geçmişindeki adet ağırlıklı TL fiyat
    (varsa; `fiyat_kaynagi` "satis_gecmisi"), yoksa çalışmanın hesapladığı satış fiyatı ("hesap"). marj = satış / maliyet - 1;
    adet = geçen yıl satış adedi; yıllık kâr = (satış - maliyet) x adet. Bölge: marj >= `marj_esigi` (vars. 0,10) yüksek marj,
    adet >= adet bilinen ürünlerin medyanı yüksek adet; adet ya da marj yoksa bölge null."""
    sen = hs.senaryo_getir(s, senaryo_id)
    satirlar, esik_marj, esik_adet = _karlilik_satirlari(s, sen, tarih or date.today())
    ozet = {b: 0 for b in KARLILIK_BOLGELERI}
    for r in satirlar:
        if r["bolge"]:
            ozet[r["bolge"]] += 1
    ozet["adetsiz"] = sum(1 for r in satirlar if r["hata"] is None and r["adet"] is None)
    ozet["hatali"] = sum(1 for r in satirlar if r["hata"])
    satirlar = [_ic_alanlari_at(r) for r in satirlar]
    satirlar.sort(key=lambda r: (r["yillik_kar"] is None, -(r["yillik_kar"] or SIFIR), r["kod"]))
    return decimal_str({"esik_marj": esik_marj, "esik_adet": esik_adet, "adet_kaynagi": "satis_gecmisi", "ozet": ozet, "kayitlar": satirlar})


# ---------------------------------------------------------------- Marjı koruyan fiyat
def hedef_fiyat(s: Session, senaryo_id: int, marj: Decimal | None = None, tarih: date | None = None) -> dict:
    """Marjı koruyan fiyat: her ürün için hedef fiyat = maliyet x (1 + marj) (marj boşsa `marj_esigi`). Maliyet kârlılıkla aynı
    (`analiz_maliyeti`: ortalama ya da bu yıl; `maliyet_kaynagi`). Geçen yıl fiyatı (satış geçmişi,
    adet ağırlıklı TL) ile kıyas: mevcut marj = geçen / maliyet - 1, gereken zam = hedef / geçen - 1, yıllık ek gelir = (hedef - geçen) x adet
    (negatif olabilir). Liste fiyatları YALNIZ Berrak markalı ürünlerde: yurtiçi = hedef ÷ yurtiçi bölen (vars. 0,63), yurtdışı = hedef ÷
    yurtdışı bölen (vars. 0,90), ikisi de `liste_yuvarlama` adımına en yakına yuvarlanır (KDV hariç); Berrak değilse null.
    Geçen yıl fiyatı yoksa kıyas alanları null, ürün `fiyatsiz` sayılır.
    Sıralama: zam gerekenler yıllık ek gelir azalan (null sonda), sonra gereken zam azalan, sonra kod."""
    from . import liste_servisi   # yerel içe aktarma: döngüsel bağımlılık olmasın
    from .liste_kurallari import berrak_mi, liste_fiyati
    sen = hs.senaryo_getir(s, senaryo_id)
    t = tarih or date.today()
    marj = marj_esigi(s, sen.id) if marj is None else _oran_dogrula("marj", marj)
    bolenler = liste_servisi.bolenler_gecerli(s, sen.id, t)
    adim, _ = liste_servisi.yuvarlama_gecerli(s, sen.id, t)
    kaynak, _, _ = _karlilik_satirlari(s, sen, t)
    markalar = dict(s.execute(select(m.Urun.kod, m.Urun.marka).where(m.Urun.kod.in_([k["kod"] for k in kaynak]))).all()) if kaynak else {}
    satirlar = []
    for k in kaynak:
        marka = markalar.get(k["kod"]) or None
        r = {"kod": k["kod"], "ad": k["ad"], "marka": marka, "aile": k["aile"], "adet": k["adet"], "maliyet": None, "hesap_fiyati": None,
             "gecen_yil_fiyat": None, "mevcut_marj": None, "hedef_fiyat": None, "gereken_zam": None, "liste_fiyati_yurtici": None,
             "liste_fiyati_yurtdisi": None, "yillik_ek_gelir": None, "bolge": k["bolge"], "hata": k["hata"], "maliyet_kaynagi": k["maliyet_kaynagi"]}
        if k["hata"] is None:
            maliyet, gy, adet = k["maliyet"], k["_gecen_yil_fiyat"], k["adet"]
            hedef = maliyet * (1 + marj)
            if berrak_mi(marka):
                r.update(liste_fiyati_yurtici=liste_fiyati(hedef, bolenler["yurtici"], adim)[1],
                         liste_fiyati_yurtdisi=liste_fiyati(hedef, bolenler["yurtdisi"], adim)[1])
            r.update(maliyet=maliyet, hesap_fiyati=k["_hesap_fiyati"], gecen_yil_fiyat=gy, hedef_fiyat=hedef,
                     mevcut_marj=(gy / maliyet - 1) if (gy is not None and maliyet) else None,
                     gereken_zam=(hedef / gy - 1) if gy else None,
                     yillik_ek_gelir=(hedef - gy) * adet if (gy is not None and adet is not None) else None)
        satirlar.append(r)

    def _sira(r):
        zam, ek = r["gereken_zam"], r["yillik_ek_gelir"]
        if zam is not None and zam > 0:
            return (0, ek is None, -(ek or SIFIR), -zam, r["kod"])
        return (1, zam is None, False, -(zam or SIFIR), r["kod"])
    satirlar.sort(key=_sira)

    agirlikli = [r for r in satirlar if r["hata"] is None and r["gecen_yil_fiyat"] is not None and r["adet"] is not None]
    ciro = sum((r["gecen_yil_fiyat"] * r["adet"] for r in agirlikli), SIFIR)
    fark = sum(((r["hedef_fiyat"] - r["gecen_yil_fiyat"]) * r["adet"] for r in agirlikli), SIFIR)
    ozet = {"urun_sayisi": len(satirlar),
            "zam_gereken": sum(1 for r in satirlar if r["gereken_zam"] is not None and r["gereken_zam"] > 0),
            "fiyatsiz": sum(1 for r in satirlar if r["hata"] is None and r["gecen_yil_fiyat"] is None),
            "hatali": sum(1 for r in satirlar if r["hata"]),
            "yillik_ek_gelir": sum((r["yillik_ek_gelir"] for r in satirlar if r["yillik_ek_gelir"] is not None and r["yillik_ek_gelir"] > 0), SIFIR),
            "ort_zam": fark / ciro if ciro else None}
    return decimal_str({"marj": marj, "bolen_yurtici": bolenler["yurtici"], "bolen_yurtdisi": bolenler["yurtdisi"], "yuvarlama": adim,
                        "adet_kaynagi": "satis_gecmisi", "ozet": ozet, "kayitlar": satirlar})


# ---------------------------------------------------------------- Önemli malzemeler (80/20)
VARSAYILAN_ONEM_ESIGI = Decimal("0.8")
_YUZDE_ADIMI = Decimal("0.01")


def _yuzde(pay: Decimal, toplam: Decimal) -> Decimal:
    """pay / toplam x 100, 2 basamak (ROUND_HALF_UP); toplam 0 ise 0."""
    return (pay / toplam * 100).quantize(_YUZDE_ADIMI, rounding=ROUND_HALF_UP) if toplam else SIFIR.quantize(_YUZDE_ADIMI)


def onemli_malzemeler(s: Session, senaryo_id: int, esik: Decimal = VARSAYILAN_ONEM_ESIGI, tarih: date | None = None) -> dict:
    """Önemli malzemeler (80/20, Pareto): yıllık malzeme tutarının `esik` kadarını (0,8 = %80) oluşturan malzemeler.
    Yıllık tutar = Σ ürünler (yıllık adet x o malzemenin üründeki fireli TL tutarı); yıllık miktar = Σ (yıllık adet x brüt miktar).
    Yıllık adet `yillik_adetler` (geçen yıl satış adedi; kur riski ve kârlılıkla aynı kaynak). Adedi olmayan ürün hesaba girmez
    (`adetsiz_urun`), hesaplanamayan ürün de girmez (`hatali_urun`). Tutarlar tek toplu hesabın (`toplu_hesapla`) reçete satırlarından
    alınır; yeni hesap kuralı yok: Σ yıllık tutar = Σ (yıllık adet x ürünün malzeme toplamı).
    Ara mamul / alt satırı olan (başlık) satırlar tutar taşımıyorsa atlanır: maliyetleri alt satırlardadır, çift sayılmaz. Böyle bir
    satıra fiyat girilmişse motor onu ürün maliyetine kattığı için burada da sayılır.
    Sıra: yıllık tutar azalan, sonra kod; fiyatsız (tutarı 0) malzemeler sonda, payı 0. `pay_yuzde` / `kumulatif_yuzde` yüzde metni
    ("12.34" = %12,34). `esik_icinde`: kendinden önceki kümülatif pay eşiğin altında olan satırlar, yani kümülatifi eşiği geçmeyenler
    ile eşiği aşan (ya da tam tutturan) ilk satır. `birim_fiyat`: malzeme kartının geçerli fiyatı (kendi para biriminde; kart yoksa null).
    `kullanan_urun_sayisi`: hesaba giren (adedi olan) ürünlerden kaçında geçtiği."""
    sen = hs.senaryo_getir(s, senaryo_id)
    esik = Decimal(str(esik))
    if not (SIFIR < esik <= 1):
        raise DogrulamaHatasi("eşik 0 ile 1 arasında olmalı (0.8 = %80)", {"esik": str(esik)})
    t = tarih or date.today()
    hesaplar = hs.toplu_hesapla(s, sen.id, t)
    urunler = {u.kod: u for u in s.scalars(select(m.Urun).where(m.Urun.kod.in_([k for k, _ in hesaplar])))} if hesaplar else {}
    adetler = yillik_adetler(s, sen, list(urunler.values()))
    toplamlar: dict[tuple[str, str], dict] = {}
    adetsiz = hatali = 0
    for kod, c in hesaplar:
        if isinstance(c, Exception):
            hatali += 1
            continue
        adet = adetler.get(kod)
        if adet is None:
            adetsiz += 1
            continue
        for rs_, ms in zip(c.girdi.recete, c.sonuc.satirlar):   # malzeme satırları reçeteyle aynı sırada, gider satırlarından önce
            if (rs_.dugum_tipi == "ara_mamul" or rs_.alt_satiri_var) and not ms.tutar:
                continue
            kart = (c.malzemeler or {}).get(ms.kod)
            k = toplamlar.setdefault((ms.kod, "" if ms.kod else ms.kalem), {
                "kod": ms.kod, "ad": kart.ad if kart else ms.kalem, "tip": kart.tip if kart else None,
                "para_birimi": (kart.para_birimi if kart else rs_.para_birimi_elle) or None, "birim": (kart.birim if kart else rs_.birim) or None,
                "birim_fiyat": kart.fiyat if kart else None, "yillik_miktar": SIFIR, "yillik_tutar_tl": SIFIR, "_urunler": set()})
            k["yillik_miktar"] += adet * ms.brut_miktar
            k["yillik_tutar_tl"] += adet * ms.tutar
            k["_urunler"].add(kod)
    sirali = sorted(toplamlar.values(), key=lambda r: (-r["yillik_tutar_tl"], r["kod"], r["ad"]))
    toplam = sum((r["yillik_tutar_tl"] for r in sirali), SIFIR)
    sinir = esik * toplam
    kumulatif, satirlar = SIFIR, []
    for i, r in enumerate(sirali, start=1):
        onceki = kumulatif
        kumulatif += r["yillik_tutar_tl"]
        satirlar.append({"sira": i, "kod": r["kod"], "ad": r["ad"], "tip": r["tip"], "para_birimi": r["para_birimi"], "birim": r["birim"],
                         "yillik_miktar": r["yillik_miktar"], "yillik_tutar_tl": r["yillik_tutar_tl"],
                         "pay_yuzde": _yuzde(r["yillik_tutar_tl"], toplam), "kumulatif_yuzde": _yuzde(kumulatif, toplam),
                         "esik_icinde": bool(r["yillik_tutar_tl"] > 0 and onceki < sinir),
                         "kullanan_urun_sayisi": len(r["_urunler"]), "birim_fiyat": r["birim_fiyat"]})
    return decimal_str({"senaryo_id": sen.id, "esik": esik, "tarih": t.isoformat(), "adet_kaynagi": "satis_gecmisi", "toplam_tutar_tl": toplam,
                        "adetsiz_urun": adetsiz, "hatali_urun": hatali, "satirlar": satirlar,
                        "esik_icindeki_sayi": sum(1 for r in satirlar if r["esik_icinde"])})
