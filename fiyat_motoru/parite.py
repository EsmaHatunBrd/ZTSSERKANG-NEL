"""Motor sonuçlarını Excel'in değerleriyle karşılaştıran parite yardımcıları (script ve testler ortak kullanır)."""
from decimal import Decimal
from pathlib import Path

from .excel_okuyucu import excel_ac, havuzlari_oku, malzemeleri_oku, urun_oku, urun_sayfalarini_listele
from .gider_dagitim import anahtar, oranlari_hesapla
from .hesapla import urun_maliyeti
from .para import D, TOLERANS

ALAN_ESLEME = {   # beklenen anahtarı -> MaliyetSonucu'ndan değer alan fonksiyon
    "P100": lambda r: r.malzeme_toplami, "P103": lambda r: r.direkt_iscilik_toplami, "P107": lambda r: r.gug_toplami,
    "P104": lambda r: r.satir("mal_kabul_iscilik").tutar,
    "P105": lambda r: r.satir("dolum_iscilik").tutar,
    "P106": lambda r: r.satir("etiket_iscilik").tutar,
    "P108": lambda r: r.satir("endirekt_iscilik").tutar,
    "P109": lambda r: r.satir("mal_kabul_gug").tutar,
    "P110": lambda r: r.satir("elektrik").tutar, "P111": lambda r: r.satir("dogalgaz").tutar,
    "P112": lambda r: r.satir("amortisman").tutar, "P113": lambda r: r.satir("diger_gug").tutar,
    "P114": lambda r: r.uretim_gideri_toplami, "P116": lambda r: r.toplam_birim_maliyet,
    "P118": lambda r: r.pazarlama_gideri, "P119": lambda r: r.yonetim_gideri, "P120": lambda r: r.diger_giderler_toplami,
    "P122": lambda r: r.giydirilmis_maliyet, "P124": lambda r: r.finansman["TL"], "P125": lambda r: r.finansman["USD"],
    "P130": lambda r: r.finansman_dahil_maliyet_tl, "P131": lambda r: r.doviz_maliyet["USD"], "P132": lambda r: r.doviz_maliyet["EUR"],
    "P133": lambda r: r.doviz_maliyet["GBP"],
    "P137": lambda r: r.satis_fiyati_tl, "P138": lambda r: r.satis_fiyati_doviz["USD"], "P143": lambda r: r.suzme_kg_fiyati_tl,
    "P145": lambda r: r.teklifler_usd[0], "P146": lambda r: r.teklifler_usd[1], "P147": lambda r: r.teklifler_usd[2],
}


def gider_dagitim_farklari(wb_v, oranlar):
    ws = wb_v["Gider Dağıtım"]
    g = lambda a: D(ws[a].value)
    kontrol = [("G4", oranlar.dolum_iscilik_sn), ("G13", oranlar.etiket_iscilik_sn),
               ("G18", oranlar.endirekt_iscilik_sn), ("G27", oranlar.diger_gug_sn)]
    kontrol += [(f"F{r}", oranlar.mal_kabul_iscilik_kg[anahtar(ws[f"C{r}"].value)]) for r in range(7, 10)]
    kontrol += [(f"F{r}", oranlar.mal_kabul_gug_kg[anahtar(ws[f"C{r}"].value)]) for r in range(21, 24)]
    for blok, tablo in [(range(30, 38), oranlar.elektrik_sn), (range(41, 49), oranlar.dogalgaz_sn), (range(52, 60), oranlar.amortisman_sn)]:
        kontrol += [(f"F{r}", tablo[anahtar(ws[f"A{r}"].value)]) for r in blok]
    for r in range(70, 92):
        h = D(ws[f"B{r}"].value)
        kontrol += [(f"F{r}", oranlar.pazarlama_adet[h]), (f"G{r}", oranlar.yonetim_adet[h])]
    return [{"sayfa": "Gider Dağıtım", "alan": a, "excel": g(a), "motor": m, "fark": g(a) - m} for a, m in kontrol if abs(g(a) - m) >= TOLERANS]


def _grup_toplami(r, grup: str, alan: str) -> Decimal:
    return sum((getattr(s, alan) for s in r.satirlar if s.grup == grup), Decimal(0))


ORAN_ESLEME = {   # R (maliyet yüzdesi) ve S (fiyat yüzdesi) sütunları
    "R100": lambda r: _grup_toplami(r, "malzeme", "maliyet_yuzdesi"),
    "R103": lambda r: _grup_toplami(r, "direkt_iscilik", "maliyet_yuzdesi"),
    "R107": lambda r: _grup_toplami(r, "gug", "maliyet_yuzdesi"),
    "R118": lambda r: r.satir("pazarlama").maliyet_yuzdesi,
    "R119": lambda r: r.satir("yonetim").maliyet_yuzdesi,
    "R124": lambda r: _grup_toplami(r, "finansman", "maliyet_yuzdesi"),
    "S100": lambda r: _grup_toplami(r, "malzeme", "fiyat_yuzdesi"),
    "S103": lambda r: _grup_toplami(r, "direkt_iscilik", "fiyat_yuzdesi"),
    "S107": lambda r: _grup_toplami(r, "gug", "fiyat_yuzdesi"),
    "S118": lambda r: r.satir("pazarlama").fiyat_yuzdesi,
    "S119": lambda r: r.satir("yonetim").fiyat_yuzdesi,
    "S124": lambda r: r.satir("finansman_tl").fiyat_yuzdesi,
}


def urun_farklari(ad: str, r, bek: dict[str, Decimal]) -> list[dict]:
    """Bir ürün sayfasının beklenen (Excel) değerlerini motor sonucuyla karşılaştırır (P, R ve S alanları)."""
    farklar = []
    for alan, al in {**ALAN_ESLEME, **ORAN_ESLEME}.items():
        try:
            motor = al(r)
        except (StopIteration, KeyError, IndexError):
            motor = None
        excel = bek.get(alan)
        if motor is None or excel is None or abs(excel - motor) >= TOLERANS:
            farklar.append({"sayfa": ad, "alan": alan, "excel": excel, "motor": motor,
                            "fark": None if motor is None or excel is None else excel - motor})
    return farklar


def karsilastir(yol: Path) -> tuple[list[dict], dict[str, list[str]]]:
    wb_f, wb_v = excel_ac(yol)
    malzemeler = malzemeleri_oku(wb_v)
    oranlar = oranlari_hesapla(havuzlari_oku(wb_v))
    farklar = gider_dagitim_farklari(wb_v, oranlar)
    uyarilar = {}
    for ad in urun_sayfalarini_listele(wb_v):
        try:
            girdi, p, bek = urun_oku(wb_f[ad], wb_v[ad], malzemeler)
            r = urun_maliyeti(girdi, malzemeler, oranlar, p)
        except Exception as e:  # sayfa şablondan sapmış olabilir; raporda görünsün
            farklar.append({"sayfa": ad, "alan": "HATA", "excel": None, "motor": None, "fark": str(e)})
            continue
        uyarilar[ad] = r.uyarilar
        farklar += urun_farklari(ad, r, bek)
    return farklar, uyarilar
