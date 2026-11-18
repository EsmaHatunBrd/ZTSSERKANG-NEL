"""Maliyet muhasebesi, 2. adım: üretim aşamalarının maliyet zinciri (Excel '20 KOD', '40 KOD', '50 KOD' sayfalarının mantığı) ve
reçeteye göre sarf ile sayımla bulunan sarfın karşılaştırması.

Aşamalar: 20 sebze kabul (hammaddeden yarı mamul) -> 40 üretim hattı (dolum; yarı mamul) -> 50 etiketleme (mamul).
Ürün başına birim maliyet (Excel ile aynı kurallar):
    çarpan            = reçete miktarı / ana miktar
    malzeme           = Σ çarpan × (HM fiyatı + YM fiyatı)
        20: HM fiyatı = malzemenin dönem ortalama fiyatı (stok tablosu; Excel TABLO!O)
        40/50: HM fiyatı = envanter birim fiyatı (Excel ENVANTER!S, aşağıda); sıfırsa YM fiyatı = bir alt aşamanın birim maliyeti
    stok payı         = dönem sonu stok × (havuz / aşamanın toplam dönem sonu stoku) / dönem sonu stok   (havuz şu an 0)
    işçilik (+GÜG)    = havuz × (ürünün payı) / üretim miktarı
        20: pay = üretim miktarı;  40 işçilik: üretim × 51!S (etiket adam/sn), 40 GÜG: üretim × 51!P (dolum sn), arama 51!C ile;
        50: pay = üretim × 51!P (dolum sn), arama 51!B ile
    fire              = Σ çarpan × fire oranı × (HM fiyatı + YM fiyatı)
    birim maliyet     = (malzeme + stok payı + işçilik); 40/50'de bu, ürünün kendi alım fiyatından (TABLO!L) düşükse alım fiyatı + işçilik
                        + stok payı alınır; sonra (40'ta GÜG payları) + fire eklenir.
Envanter birim fiyatı (ENVANTER!S): (dönem başı tutar + alım tutarı + finansman payı + üretim × 20 birim maliyeti) /
    (dönem başı + alım + üretim miktarı); miktarların toplamı 0 ise 20 birim maliyeti.
Tutarlar Decimal; hesap kayıt değiştirmez (dağıtım havuzları dışında)."""
from collections import defaultdict
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..depo import modeller as m
from .donusum import decimal_str
from .hatalar import BulunamadiHatasi, DogrulamaHatasi, liste_metni
from .smm_servisi import HAVUZ_HUCRELERI, SIFIR, _d, _tr, _yakin, donem_cikis, donem_getir, kilit_denetle, stok_hesabi

ASAMA_ADLARI = {20: "Sebze kabul", 40: "Üretim hattı", 50: "Etiketleme"}
HAVUZ_ADLARI = {
    "20_stok": "20 · Dönem sonu stok işçilik payı",
    "20_uretim": "20 · Üretim işçilik + GÜG",
    "40_stok_iscilik": "40 · Dönem sonu stok işçilik payı",
    "40_iscilik": "40 · Üretim işçilik",
    "40_stok_gug": "40 · Dönem sonu stok GÜG payı",
    "40_gug": "40 · Üretim GÜG",
    "50_stok": "50 · Dönem sonu stok payı",
    "50_uretim": "50 · Üretim işçilik + GÜG",
}
HAVUZLAR = tuple(k for h in HAVUZ_HUCRELERI.values() for k in h)
# Ürüne elle girilebilen aşama değerleri (birim başına TL)
ELLE_ALANLARI = ("malzeme", "iscilik", "gug", "fire", "birim_maliyet")
# Dağıtım anahtarları: hangi havuz neyle dağıtılır. 'uretim' = üretim miktarı; diğerleri üretim × 51 sayfasındaki süre (sn).
ANAHTAR_SECENEKLERI = ("uretim", "dolum_sn", "dolum_adam_sn", "etiket_sn", "etiket_adam_sn")
VARSAYILAN_ANAHTARLAR = {"20": "uretim", "40_iscilik": "etiket_adam_sn", "40_gug": "dolum_sn", "50": "dolum_sn"}   # Excel'deki kurallar
ANAHTAR_ADLARI = {"20": "20 · İşçilik + GÜG", "40_iscilik": "40 · İşçilik", "40_gug": "40 · GÜG", "50": "50 · İşçilik + GÜG"}


def dagitim_anahtarlari(d: m.SmmDonem) -> dict[str, str]:
    kayit = (d.dagitim or {}).get("anahtarlar") or {}
    return {k: kayit.get(k) if kayit.get(k) in ANAHTAR_SECENEKLERI else v for k, v in VARSAYILAN_ANAHTARLAR.items()}


def _bol(a: Decimal, b: Decimal) -> Decimal:
    return a / b if b else SIFIR


def _havuz(d: m.SmmDonem) -> dict[str, Decimal]:
    kaynak = d.dagitim or {}
    return {k: _d(kaynak.get(k)) for k in HAVUZLAR}


class _Baglam:
    """Dönemin tüm aşama hesabı; bir kez kurulur (alt aşamanın birim maliyeti üst aşamada kullanılır)."""

    def __init__(self, s: Session, d: m.SmmDonem):
        self.d = d
        self.havuz = _havuz(d)
        self.kalem = {k.kod: k for k in s.scalars(select(m.SmmKalem).where(m.SmmKalem.donem_id == d.id))}
        self.alim_toplam = sum((k.alim_tutar for k in self.kalem.values()), SIFIR)
        self.env_alim_toplam = sum((k.alim_tutar for k in self.kalem.values() if k.envanterde), SIFIR)
        self.stok = {kod: stok_hesabi(k, d.finansman, self.alim_toplam) for kod, k in self.kalem.items()}
        # 51 sayfası: ilk eşleşme (Excel DÜŞEYARA gibi)
        self.sure_mamul: dict[str, m.SmmIscilik] = {}
        self.sure_yari: dict[str, m.SmmIscilik] = {}
        for x in s.scalars(select(m.SmmIscilik).where(m.SmmIscilik.donem_id == d.id).order_by(m.SmmIscilik.id)):
            if x.mamul_kod:
                self.sure_mamul.setdefault(x.mamul_kod, x)
            if x.yari_mamul_kod:
                self.sure_yari.setdefault(x.yari_mamul_kod, x)
        self.gruplar: dict[int, dict[str, list[m.SmmReceteSatiri]]] = {20: {}, 40: {}, 50: {}}
        if (d.recete_kaynagi or "excel") == "ana":   # kalıcı Canias reçeteleri (seçili alternatif)
            from .smm_recete_servisi import hesap_gruplari
            self.gruplar.update(hesap_gruplari(s))
        else:
            for r in s.scalars(select(m.SmmReceteSatiri).where(m.SmmReceteSatiri.donem_id == d.id).order_by(m.SmmReceteSatiri.id)):
                self.gruplar.setdefault(r.asama, {}).setdefault(r.ana_kod, []).append(r)
        self.sonuc: dict[int, dict[str, dict]] = {}
        self.env_fiyat: dict[str, Decimal] = {}
        self._paylar: dict[int, dict[str, dict]] = {}
        self._hesaplaniyor: set[tuple[int, str]] = set()
        self._hesapla()

    # --------------------------------------------------------------- fiyat kaynakları
    def uretim(self, kod: str) -> Decimal:
        k = self.kalem.get(kod)
        return k.uretim_miktar if k else SIFIR

    def sayim(self, kod: str) -> Decimal:
        k = self.kalem.get(kod)
        return k.sayim_miktar if k else SIFIR

    def ortalama(self, kod: str) -> Decimal:
        h = self.stok.get(kod)
        return h["ortalama_fiyat"] if h else SIFIR

    def alim_fiyati(self, kod: str) -> Decimal:
        """Finansman dahil alım birim fiyatı (Excel TABLO!L)."""
        k, h = self.kalem.get(kod), self.stok.get(kod)
        return _bol(k.alim_tutar + h["finansman_payi"], k.alim_miktar) if k else SIFIR

    def birim(self, asama: int, kod: str) -> Decimal:
        x = self.sonuc.get(asama, {}).get(kod)
        return x["birim_maliyet"] if x else SIFIR

    def envanter_fiyati(self, kod: str) -> Decimal:
        """ENVANTER!S. Üretim birim fiyatı (P) kartın baktığı aşama sayfasından (20/40/50) gelir; aşama hesabı gerekirse önce yapılır."""
        if kod in self.env_fiyat:
            return self.env_fiyat[kod]
        k = self.kalem.get(kod)
        if k is None or not k.envanterde:
            return SIFIR
        fin = _bol(k.alim_tutar, self.env_alim_toplam) * self.d.finansman if self.d.finansman else SIFIR
        asama = k.uretim_asamasi or 20
        p = self.urun_birimi(asama, kod)
        miktar = k.uretim_miktar + k.alim_miktar + k.dbs_miktar
        f = p if miktar == 0 else (k.alim_tutar + fin + p * k.uretim_miktar + k.dbs_tutar) / miktar
        if (asama, kod) not in self._hesaplaniyor:   # döngü içindeki geçici değer saklanmaz
            self.env_fiyat[kod] = f
        return f

    @staticmethod
    def carpan(x: m.SmmReceteSatiri) -> Decimal:
        """Reçete çarpanı (Excel I = miktar / ana miktar); Excel'de elle yazılmışsa o."""
        ozel = x.ozel or {}
        return _d(ozel["carpan"]) if "carpan" in ozel else _bol(x.miktar, x.ana_miktar)

    def satir_fiyati(self, asama: int, x: m.SmmReceteSatiri) -> tuple[Decimal, Decimal, str]:
        """(HM fiyatı, YM fiyatı, kaynak) — Excel K ve M sütunları. Excel'de elle/standart dışı yazılmış hücre varsa o değer kullanılır.
        20: YM = malzeme kendisi bir 20 ürünüyse onun birim maliyeti; değilse HM = dönem ortalama fiyatı.
        40/50: HM = envanter birim fiyatı (50'de bazı satırlarda / bölen); sıfırsa YM = bir alt aşamanın birim maliyeti."""
        ozel, mal = x.ozel or {}, x.malzeme_kod
        if "kod_bosluklu" in ozel and not ozel.keys() & {"hm", "ym"}:
            return SIFIR, SIFIR, "kod_bosluklu"   # Excel kartı bulamıyor (kodda boşluk): fiyat 0
        if asama == 20:
            ym = _d(ozel["ym"]) if "ym" in ozel else self.urun_birimi(20, mal)
            if "hm" in ozel:
                hm = _d(ozel["hm"])
            else:
                hm = self.ortalama(mal) if ym == 0 else SIFIR
            kaynak = "excel_elle" if ozel.keys() & {"hm", "ym"} else ("asama_20" if ym else "ortalama")
            return hm, ym, kaynak
        if "hm" in ozel:
            hm = _d(ozel["hm"])
        else:
            hm = self.envanter_fiyati(mal)
            if "hm_bolen" in ozel:
                hm = _bol(hm, _d(ozel["hm_bolen"]))
        alt = 20 if asama == 40 else 40
        if "ym" in ozel:
            ym = _d(ozel["ym"])
        else:
            ym = self.birim(alt, mal) if hm == 0 else SIFIR
        if ozel.keys() & {"hm", "ym"}:
            kaynak = "excel_elle"
        elif hm:
            kaynak = "envanter_bolen" if "hm_bolen" in ozel else "envanter"
        else:
            kaynak = f"asama_{alt}" if ym else "yok"
        return hm, ym, kaynak

    # --------------------------------------------------------------- hesap
    def _hesapla(self) -> None:
        for asama in (20, 40, 50):   # paylar fiyattan bağımsız: önce hepsi (envanter fiyatı üst aşamaya da bakabilir)
            self._dagitim_hazirla(asama)
            self.sonuc[asama] = {}
        for asama in (20, 40, 50):
            for a in self.gruplar.get(asama, {}):
                self.urun_birimi(asama, a)

    def _dagitim_hazirla(self, asama: int) -> None:
        """Aşamanın fiyattan bağımsız payları: dönem sonu stok payı, işçilik ve GÜG (birim başına)."""
        gruplar = self.gruplar.get(asama, {})
        h = self.havuz
        elle = (self.d.asama_elle or {}).get(str(asama), {})
        stok_top = sum((self.sayim(a) for a in gruplar), SIFIR)

        def sure(kod: str, alan: str) -> tuple[Decimal, bool]:
            kaynak = self.sure_yari if asama == 40 else self.sure_mamul
            x = kaynak.get(kod)
            return (getattr(x, alan) if x else SIFIR), x is not None

        # İşçilik/GÜG dağıtım anahtarı (ekrandan seçilebilir; varsayılan Excel'deki gibi): üretim miktarı ya da üretim × süre (sn).
        # Excel'de ürün satırına elle yazılan süre önceliklidir.
        anahtar = dagitim_anahtarlari(self.d)

        def pay(a: str, r: Decimal, alan: str) -> tuple[Decimal, bool]:
            if alan == "uretim":
                return r, True
            sn, var = sure(a, alan)
            return r * sn, var

        isc_pay: dict[str, Decimal] = {}
        gug_pay: dict[str, Decimal] = {}
        sure_yok: set[str] = set()
        for a in gruplar:
            r = self.uretim(a)
            e = elle.get(a, {})
            if asama == 20:
                isc_pay[a], var = pay(a, r, anahtar["20"])
            elif asama == 40:
                isc_pay[a], var = pay(a, r, anahtar["40_iscilik"])
                gug_pay[a] = r * _d(e["gug_sn"]) if "gug_sn" in e else pay(a, r, anahtar["40_gug"])[0]
            else:
                isc_pay[a], var = (_d(e["sure"]), True) if "sure" in e else pay(a, r, anahtar["50"])
            if r and not var:
                sure_yok.add(a)
        isc_top = sum(isc_pay.values(), SIFIR)
        gug_top = sum(gug_pay.values(), SIFIR)
        stok_havuz = {20: h["20_stok"], 40: h["40_stok_iscilik"], 50: h["50_stok"]}[asama]
        uretim_havuz = {20: h["20_uretim"], 40: h["40_iscilik"], 50: h["50_uretim"]}[asama]
        paylar = {}
        for a in gruplar:
            r, o = self.uretim(a), self.sayim(a)
            gug = SIFIR
            if asama == 40:
                gug = _bol(_bol(o, stok_top) * h["40_stok_gug"], o) + _bol(_bol(gug_pay[a], gug_top) * h["40_gug"], r)
            paylar[a] = {"stok_payi": _bol(_bol(o, stok_top) * stok_havuz, o), "iscilik": _bol(_bol(isc_pay[a], isc_top) * uretim_havuz, r),
                         "gug": gug, "sure_yok": a in sure_yok}
        self._paylar[asama] = paylar

    def urun_birimi(self, asama: int, kod: str) -> Decimal:
        """Aşama ürününün birim maliyeti (gerekirse önce hesaplar). 20'de bir ürün başka 20 ürününü girdi olarak kullanabilir:
        hesap özyinelemeli; döngü olursa (Excel'de döngüsel başvuru) döngüdeki girdi 0 sayılır."""
        sonuc = self.sonuc.setdefault(asama, {})
        if kod in sonuc:
            return sonuc[kod]["birim_maliyet"]
        satirlar = self.gruplar.get(asama, {}).get(kod)
        if not satirlar or (asama, kod) in self._hesaplaniyor:
            return SIFIR
        self._hesaplaniyor.add((asama, kod))
        try:
            r = self.uretim(kod)
            malzeme = fire = SIFIR
            for x in satirlar:
                carpan = self.carpan(x)
                hm, ym, _ = self.satir_fiyati(asama, x)
                malzeme += carpan * (hm + ym)
                fire += carpan * x.fire_orani * (hm + ym)
            p = dict(self._paylar[asama][kod])
            # Ekrandan elle girilen değerler (dönem ve ürün başına) hesaplananın yerine geçer; birim maliyet elle ise doğrudan o.
            e = {k_: _d(v) for k_, v in (self.d.asama_elle or {}).get(str(asama), {}).get(kod, {}).items() if k_ in ELLE_ALANLARI}
            malzeme = e.get("malzeme", malzeme)
            fire = e.get("fire", fire)
            p["iscilik"] = e.get("iscilik", p["iscilik"])
            p["gug"] = e.get("gug", p["gug"])
            hesap = malzeme + p["stok_payi"] + p["iscilik"]
            alim = self.alim_fiyati(kod) if asama != 20 else SIFIR
            alim_kurali = hesap < alim
            temel = alim + p["iscilik"] + p["stok_payi"] if alim_kurali else hesap
            birim = e.get("birim_maliyet", temel + p["gug"] + fire)
            ilk = satirlar[0]
            k = self.kalem.get(kod)
            sonuc[kod] = {"kod": kod, "ad": ilk.ana_ad or (k.ad if k else None), "birim": ilk.ana_birim, "uretim_miktar": r,
                          "malzeme": malzeme, "stok_payi": p["stok_payi"], "iscilik": p["iscilik"], "gug": p["gug"], "fire": fire,
                          "alim_fiyati": alim, "alim_kurali": alim_kurali and "birim_maliyet" not in e, "birim_maliyet": birim,
                          "toplam": birim * r, "satir_sayisi": len(satirlar), "sure_yok": p["sure_yok"], "elle_alanlar": sorted(e)}
            return birim
        finally:
            self._hesaplaniyor.discard((asama, kod))


def _excel_karsilastir(d: m.SmmDonem, asama: int, sonuc: dict[str, dict]) -> dict:
    excel = (d.excel_asama or {}).get(str(asama)) or {}
    esit = farkli = 0
    ornek = []
    for kod, x in sonuc.items():
        if kod not in excel:
            continue
        e = _d(excel[kod])
        x["excel_birim"] = e
        if _yakin(x["birim_maliyet"], e):
            esit += 1
        else:
            farkli += 1
            if len(ornek) < 20:
                ornek.append(kod)
    return {"karsilastirilan": esit + farkli, "esit": esit, "farkli": farkli, "farkli_ornek": ornek}


def _dagitim_cikis(d: m.SmmDonem) -> dict:
    h, ilk = _havuz(d), d.dagitim_excel or {}
    dagitilan = sum(h.values(), SIFIR)
    mizan = d.gider_mizan or {}
    mizan_top = sum((_d(v) for v in mizan.values()), SIFIR)
    return {"havuzlar": [{"anahtar": k, "ad": HAVUZ_ADLARI[k], "tutar": h[k], "excel": _d(ilk.get(k)), "degisti": h[k] != _d(ilk.get(k))}
                         for k in HAVUZLAR],
            "dagitilan": dagitilan, "mizan_720": _d(mizan.get("720")), "mizan_730": _d(mizan.get("730")),
            "dagitilmayan": mizan_top - dagitilan if mizan else None,
            "anahtarlar": [{"anahtar": k, "ad": ANAHTAR_ADLARI[k], "alan": v, "excel_varsayilani": VARSAYILAN_ANAHTARLAR[k]}
                           for k, v in dagitim_anahtarlari(d).items()]}


def uretim_maliyeti(s: Session, donem_id: int, asama: int = 50, arama: str | None = None, yalniz_farkli: bool = False) -> dict:
    """Dönemin aşama maliyetleri: aşama özetleri (hepsi), dağıtım havuzları ve seçilen aşamanın ürünleri."""
    if asama not in ASAMA_ADLARI:
        raise DogrulamaHatasi("Aşama 20, 40 ya da 50 olmalı.", {"asama": asama})
    d = donem_getir(s, donem_id)
    b = _Baglam(s, d)
    ozetler = []
    for a in (20, 40, 50):
        sonuc = b.sonuc[a]
        ex = _excel_karsilastir(d, a, sonuc)
        top = defaultdict(lambda: SIFIR)
        for x in sonuc.values():
            r = x["uretim_miktar"]
            for alan in ("malzeme", "iscilik", "gug", "fire"):
                top[alan] += x[alan] * r
            top["toplam"] += x["toplam"]
        ozetler.append({"asama": a, "ad": ASAMA_ADLARI[a], "urun_sayisi": len(sonuc),
                        "uretilen_urun": sum(1 for x in sonuc.values() if x["uretim_miktar"]),
                        "sure_yok": sum(1 for x in sonuc.values() if x["sure_yok"]),
                        "alim_kurali": sum(1 for x in sonuc.values() if x["alim_kurali"] and x["uretim_miktar"]),
                        "kod_bosluklu": sum(1 for ss_ in b.gruplar.get(a, {}).values() for x in ss_ if "kod_bosluklu" in (x.ozel or {})),
                        "excel_elle": sum(1 for ss_ in b.gruplar.get(a, {}).values() for x in ss_
                                          if (x.ozel or {}).keys() & {"hm", "ym", "carpan", "hm_bolen"})
                        + len((d.asama_elle or {}).get(str(a), {})),
                        **{k: top[k] for k in ("malzeme", "iscilik", "gug", "fire", "toplam")}, "excel": ex})
    q = _tr((arama or "").strip())
    kayitlar = []
    for x in sorted(b.sonuc[asama].values(), key=lambda x: (-x["toplam"], x["kod"])):
        if q and q not in _tr(x["kod"]) and q not in _tr(x["ad"]):
            continue
        fark = "excel_birim" in x and not _yakin(x["birim_maliyet"], x["excel_birim"])
        if yalniz_farkli and not fark:
            continue
        kayitlar.append({**x, "excel_birim": x.get("excel_birim"), "excel_farkli": fark})
    return decimal_str({"donem": donem_cikis(d, len(b.kalem)), "asama": asama, "ozetler": ozetler, "dagitim": _dagitim_cikis(d),
                        "kayitlar": kayitlar})


def recete_satirlari(b: _Baglam, asama: int, kod: str) -> list[dict]:
    """Kurulmuş bağlamdan bir aşama ürününün reçete satırları (Decimal değerli): çarpan, fiyat, kaynak, malzeme ve fire tutarı."""
    satirlar = []
    for r in b.gruplar[asama][kod]:
        carpan = b.carpan(r)
        hm, ym, kaynak = b.satir_fiyati(asama, r)
        fiyat = hm + ym
        satirlar.append({"malzeme_kod": r.malzeme_kod, "malzeme_ad": r.malzeme_ad, "miktar": r.miktar, "birim": r.birim, "carpan": carpan,
                         "fiyat": fiyat, "fiyat_kaynagi": kaynak, "tutar": carpan * fiyat, "fire_orani": r.fire_orani,
                         "fire_tutari": carpan * r.fire_orani * fiyat})
    return satirlar


def urun_recetesi(s: Session, donem_id: int, asama: int, kod: str) -> dict:
    """Bir aşama ürününün reçete satırları: çarpan, fiyat kaynağı, malzeme ve fire tutarı (birim başına)."""
    d = donem_getir(s, donem_id)
    b = _Baglam(s, d)
    x = b.sonuc.get(asama, {}).get(kod)
    if x is None:
        raise BulunamadiHatasi(f"{asama} aşamasında {kod} kodlu ürün bulunamadı.", {"asama": asama, "kod": kod})
    satirlar = recete_satirlari(b, asama, kod)
    ex = (d.excel_asama or {}).get(str(asama), {}).get(kod)
    return decimal_str({"urun": {**x, "excel_birim": _d(ex) if ex is not None else None,
                                 "excel_farkli": ex is not None and not _yakin(x["birim_maliyet"], _d(ex))},
                        "asama": asama, "satirlar": satirlar})


def dagitim_guncelle(s: Session, donem_id: int, havuzlar: dict[str, Decimal], kullanici: str = "sistem",
                     anahtarlar: dict[str, str] | None = None) -> dict:
    """Dağıtılacak işçilik/GÜG havuzlarını ve dağıtım anahtarlarını değiştirir (yalnız verilenler). Excel'deki ilk değerler korunur."""
    d = donem_getir(s, donem_id)
    bilinmeyen = sorted(set(havuzlar) - set(HAVUZLAR))
    if bilinmeyen:
        raise DogrulamaHatasi(f"Bilinmeyen havuz: {liste_metni(bilinmeyen)}.", {"havuzlar": bilinmeyen})
    eksi = sorted(k for k, v in havuzlar.items() if v < 0)
    if eksi:
        raise DogrulamaHatasi(f"Havuz tutarı eksi olamaz: {liste_metni(HAVUZ_ADLARI.get(x, x) for x in eksi)}.", {"havuzlar": eksi})
    anahtarlar = anahtarlar or {}
    gecersiz = sorted(k for k, v in anahtarlar.items() if k not in VARSAYILAN_ANAHTARLAR or v not in ANAHTAR_SECENEKLERI)
    if gecersiz:
        raise DogrulamaHatasi(f"Geçersiz dağıtım anahtarı: {liste_metni(gecersiz)}; seçenekler: {liste_metni(ANAHTAR_SECENEKLERI)}.", {"anahtarlar": gecersiz, "secenekler": list(ANAHTAR_SECENEKLERI)})
    kilit_denetle(d)
    eski = dict(d.dagitim or {})
    yeni = {**eski, **decimal_str(dict(havuzlar))}
    if anahtarlar:
        yeni["anahtarlar"] = {**(eski.get("anahtarlar") or {}), **anahtarlar}
    if yeni != eski:
        d.dagitim = yeni
        s.add(m.DegisiklikKaydi(tablo="smm_donem", kayit_id=d.id, islem="dagitim", eski=eski, yeni=yeni, kullanici=kullanici))
        s.flush()
    return decimal_str(_dagitim_cikis(d))


def urun_elle_guncelle(s: Session, donem_id: int, asama: int, kod: str, alanlar: dict[str, Decimal | None],
                       kullanici: str = "sistem") -> dict:
    """Ürünün aşama değerlerini (malzeme, işçilik, GÜG, fire, birim maliyet; birim başına TL) elle girer. None = formüle dön."""
    d = donem_getir(s, donem_id)
    if asama not in ASAMA_ADLARI:
        raise DogrulamaHatasi("Aşama 20, 40 ya da 50 olmalı.", {"asama": asama})
    bilinmeyen = sorted(set(alanlar) - set(ELLE_ALANLARI))
    if bilinmeyen:
        raise DogrulamaHatasi(f"Bilinmeyen alan: {liste_metni(bilinmeyen)}.", {"alanlar": bilinmeyen, "gecerli": list(ELLE_ALANLARI)})
    eksi = sorted(k for k, v in alanlar.items() if v is not None and v < 0)
    if eksi:
        raise DogrulamaHatasi(f"Değer eksi olamaz: {liste_metni(eksi)}.", {"alanlar": eksi})
    kilit_denetle(d)
    if kod not in _Baglam(s, d).gruplar.get(asama, {}):
        raise BulunamadiHatasi(f"{asama} aşamasında {kod} kodlu ürün bulunamadı.", {"asama": asama, "kod": kod})
    tum = {a: {k: dict(v) for k, v in x.items()} for a, x in (d.asama_elle or {}).items()}
    e = tum.setdefault(str(asama), {}).setdefault(kod, {})
    eski = {k: e.get(k) for k in alanlar}
    for k, v in alanlar.items():
        if v is None:
            e.pop(k, None)
        else:
            e[k] = str(v)
    if not e:
        tum[str(asama)].pop(kod, None)
    yeni = {k: e.get(k) for k in alanlar}
    if eski != yeni:
        d.asama_elle = tum
        s.add(m.DegisiklikKaydi(tablo="smm_donem", kayit_id=d.id, islem="asama_elle", eski={"asama": asama, "kod": kod, **eski},
                                yeni={"asama": asama, "kod": kod, **yeni}, kullanici=kullanici))
        s.flush()
    return urun_recetesi(s, donem_id, asama, kod)


# ---------------------------------------------------------------- üretim süreleri (Excel '51'; dönem başına)
SURE_ALANLARI = ("kod", "mamul_kod", "yari_mamul_kod", "ad", "vardiya_uretim", "dolum_isci", "etiket_isci", "dolum_sn", "dolum_adam_sn",
                 "etiket_sn", "etiket_adam_sn")


def _sure_cikis(x: m.SmmIscilik) -> dict:
    return decimal_str({"id": x.id, **{a: getattr(x, a) for a in SURE_ALANLARI}})


def sure_listesi(s: Session, donem_id: int, arama: str | None = None) -> dict:
    d = donem_getir(s, donem_id)
    q = _tr((arama or "").strip())
    kayitlar = [x for x in s.scalars(select(m.SmmIscilik).where(m.SmmIscilik.donem_id == d.id).order_by(m.SmmIscilik.id))
                if not q or q in _tr(x.kod) or q in _tr(x.ad) or q in _tr(x.mamul_kod) or q in _tr(x.yari_mamul_kod)]
    return {"donem": donem_cikis(d), "kayitlar": [_sure_cikis(x) for x in kayitlar]}


def _sure_dogrula(alanlar: dict) -> None:
    eksi = sorted(k for k, v in alanlar.items() if isinstance(v, Decimal) and v < 0)
    if eksi:
        raise DogrulamaHatasi("Süre ve kişi sayıları eksi olamaz.", {"alanlar": eksi})


def sure_ekle(s: Session, donem_id: int, alanlar: dict, kullanici: str = "sistem") -> dict:
    d = donem_getir(s, donem_id)
    kilit_denetle(d)
    alanlar = {k: v for k, v in alanlar.items() if k in SURE_ALANLARI and v is not None}
    if not (alanlar.get("mamul_kod") or alanlar.get("yari_mamul_kod")):
        raise DogrulamaHatasi("Mamul ya da yarı mamul kodu girin.", {"mamul_kod": "zorunlu"})
    _sure_dogrula(alanlar)
    alanlar["kod"] = alanlar.get("mamul_kod") or alanlar.get("yari_mamul_kod")
    x = m.SmmIscilik(donem_id=d.id, olusturan=kullanici, **alanlar)
    s.add(x)
    s.flush()
    s.add(m.DegisiklikKaydi(tablo="smm_donem", kayit_id=d.id, islem="sure_ekle", eski=None, yeni=decimal_str(dict(alanlar)), kullanici=kullanici))
    s.flush()
    return _sure_cikis(x)


def sure_guncelle(s: Session, sure_id: int, alanlar: dict, kullanici: str = "sistem") -> dict:
    x = s.get(m.SmmIscilik, sure_id)
    if x is None:
        raise BulunamadiHatasi("Süre satırı bulunamadı.", {"id": sure_id})
    kilit_denetle(donem_getir(s, x.donem_id))
    alanlar = {k: v for k, v in alanlar.items() if k in SURE_ALANLARI and k != "kod" and v is not None}
    _sure_dogrula(alanlar)
    eski = decimal_str({k: getattr(x, k) for k in alanlar})
    for k, v in alanlar.items():
        setattr(x, k, v)
    x.kod = x.mamul_kod or x.yari_mamul_kod or x.kod
    if not (x.mamul_kod or x.yari_mamul_kod):
        raise DogrulamaHatasi("Mamul ya da yarı mamul kodu girin.", {"mamul_kod": "zorunlu"})
    yeni = decimal_str({k: getattr(x, k) for k in alanlar})
    if eski != yeni:
        s.add(m.DegisiklikKaydi(tablo="smm_donem", kayit_id=x.donem_id, islem="sure_guncelle", eski={"kod": x.kod, **eski},
                                yeni={"kod": x.kod, **yeni}, kullanici=kullanici))
    s.flush()
    return _sure_cikis(x)


def sure_sil(s: Session, sure_id: int, kullanici: str = "sistem") -> None:
    x = s.get(m.SmmIscilik, sure_id)
    if x is None:
        raise BulunamadiHatasi("Süre satırı bulunamadı.", {"id": sure_id})
    kilit_denetle(donem_getir(s, x.donem_id))
    s.add(m.DegisiklikKaydi(tablo="smm_donem", kayit_id=x.donem_id, islem="sure_sil", eski={"kod": x.kod, "ad": x.ad}, yeni=None,
                            kullanici=kullanici))
    s.delete(x)
    s.flush()


def sarf_farki(s: Session, donem_id: int, arama: str | None = None, tur: str | None = None, esik: Decimal = SIFIR) -> dict:
    """Malzeme başına reçeteye göre sarf (Σ üretim × çarpan × (1 + fire)) ile sayımla bulunan sarfın (stok tablosu) farkı.
    Pozitif fark: sayıma göre reçetenin söylediğinden fazla malzeme harcanmış (fazla sarf / kayıp)."""
    d = donem_getir(s, donem_id)
    b = _Baglam(s, d)
    recete = defaultdict(lambda: SIFIR)
    kullanan = defaultdict(set)
    recete_birim: dict[str, set[str]] = defaultdict(set)
    for asama, gruplar in b.gruplar.items():
        for ana, satirlar in gruplar.items():
            r = b.uretim(ana)
            for x in satirlar:
                carpan = b.carpan(x)
                recete[x.malzeme_kod] += r * carpan * (1 + x.fire_orani)
                kullanan[x.malzeme_kod].add(ana)
                if x.birim:
                    recete_birim[x.malzeme_kod].add(_birim(x.birim))
    q = _tr((arama or "").strip())
    kayitlar = []
    top = defaultdict(lambda: SIFIR)
    turler = set()
    uyumsuz_sayi = 0
    for kod in sorted(set(recete)):
        k = b.kalem.get(kod)
        h = b.stok.get(kod)
        # Sayıma göre sarf = dönem başı + alım + üretim girişi − iade − sayım. Üretilen yarı mamul başka aşamada kullanılıyorsa
        # elde olan, üretim girişini de içerir (stok tablosunun sarfı, Excel TABLO gibi, üretim girişini saymaz).
        # Satılan HM/YM ve şahit numune sayımda yoktur ama üretime de gitmemiştir: sayıma göre sarftan düşülür.
        uretim_girisi = k.uretim_miktar if k else SIFIR
        satis = (k.satis_miktar or SIFIR) if k else SIFIR
        sahit = (k.sahit_miktar or SIFIR) if k else SIFIR
        stok_sarf = (h["sarf_miktar"] if h else SIFIR) + uretim_girisi - satis - sahit
        # Birim fiyat: dönem ortalaması; alımı/dönem başı olmayan üretilmiş kalemde aşama birim maliyeti.
        ort = (h["ortalama_fiyat"] if h else SIFIR) or b.birim(20, kod) or b.birim(40, kod) or b.birim(50, kod)
        fark = stok_sarf - recete[kod]
        fark_tutar = fark * ort
        t = (k.tur if k else None) or "Diğer"
        turler.add(t)
        # Reçetedeki birim stok kartının biriminden farklıysa miktarlar karşılaştırılamaz (Excel de dönüştürmez): toplamlara girmez.
        kart_birim = _birim(k.birim) if k and k.birim else None
        birim_uyumsuz = bool(kart_birim and recete_birim[kod] and recete_birim[kod] != {kart_birim})
        if birim_uyumsuz:
            uyumsuz_sayi += 1
        else:
            top["recete_tutar"] += recete[kod] * ort
            top["stok_tutar"] += stok_sarf * ort
            top["fazla"] += fark_tutar if fark_tutar > 0 else SIFIR
            top["eksik"] += fark_tutar if fark_tutar < 0 else SIFIR
        if tur and t != tur:
            continue
        if q and q not in _tr(kod) and q not in _tr(k.ad if k else None):
            continue
        if esik and abs(fark_tutar) < esik:
            continue
        kayitlar.append({"kod": kod, "ad": k.ad if k else None, "birim": k.birim if k else None, "tur": t, "ortalama_fiyat": ort,
                         "recete_sarf": recete[kod], "stok_sarf": stok_sarf, "fark": fark, "fark_tutar": fark_tutar,
                         "fark_orani": _bol(fark, recete[kod]) if recete[kod] else None, "urun_sayisi": len(kullanan[kod]),
                         "kartsiz": k is None, "uretim_girisi": uretim_girisi, "satis_miktar": satis, "sahit_miktar": sahit,
                         "birim_uyumsuz": birim_uyumsuz,
                         "recete_birimleri": sorted(recete_birim[kod])})
    # Birimi uyumsuz satırlar en alta: TL farkları anlamsız büyük çıkabilir.
    kayitlar.sort(key=lambda x: (x["birim_uyumsuz"], -abs(x["fark_tutar"]), x["kod"]))
    return decimal_str({"donem": donem_cikis(d, len(b.kalem)), "toplamlar": dict(top), "birim_uyumsuz_sayisi": uyumsuz_sayi,
                        "turler": sorted(turler), "kayitlar": kayitlar})


def _birim(b: str) -> str:
    """Birim karşılaştırması için: büyük harf, boşluksuz, sık eş anlamlılar birleşik (ADET=AD, KILO/KİLO=KG)."""
    x = b.strip().upper().replace("İ", "I")
    return {"ADET": "AD", "ADT": "AD", "KILO": "KG", "KGM": "KG", "LITRE": "LT", "L": "LT"}.get(x, x)
