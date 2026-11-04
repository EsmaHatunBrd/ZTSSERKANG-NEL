"""F2/F3: Reçete satırının TL tutarı ve malzeme toplamı. Excel 001!P6:P99 ve P100."""
from dataclasses import replace
from decimal import Decimal
from .fire import brut_miktar
from .modeller import Malzeme, MaliyetSatiri, Parametreler, ReceteSatiri
from .para import BIR, SIFIR

DOVIZLER = ("USD", "EUR", "GBP", "CHF")


def malzeme_tutari(satir: ReceteSatiri, malzeme: Malzeme | None, p: Parametreler) -> tuple[MaliyetSatiri, str | None]:
    elle_miktar = satir.brut_miktar_elle is not None
    elle_fiyat = satir.birim_fiyat_elle is not None
    if satir.zs_elle or satir.para_birimi_elle:
        # Excel N/O sütunu elle yazılmış: bu satır için kartın Z/S'si ve para birimi yerine. Kart yoksa ve fiyat elle
        # girilmişse satır kendi Z/S + para birimiyle hesaplanır (Excel: M elle × kur).
        if malzeme is None and elle_fiyat:
            malzeme = Malzeme(kod=satir.malzeme_kodu, ad=satir.ad, tip=None, birim=satir.birim, para_birimi=None, fiyat=SIFIR, zs=None)
        if malzeme is not None:
            malzeme = replace(malzeme, zs=satir.zs_elle or malzeme.zs, para_birimi=satir.para_birimi_elle or malzeme.para_birimi)
    brut = satir.brut_miktar_elle if elle_miktar else brut_miktar(satir.miktar, satir.fire_orani)
    fiyat = satir.birim_fiyat_elle if elle_fiyat else (malzeme.fiyat if malzeme is not None else SIFIR)
    uyari = None
    katsayi: Decimal | None = BIR          # None: tutar 0 alınır
    if malzeme is None:
        if not elle_fiyat:
            katsayi = SIFIR
            if satir.dugum_tipi != "ara_mamul" and not satir.alt_satiri_var:
                uyari = f"{satir.malzeme_kodu} ({satir.ad}): fiyat listesinde yok, 0 TL alındı"
    elif malzeme.zs == "S":
        pb = malzeme.para_birimi
        if pb in DOVIZLER:
            kur = p.kurlar.get(pb)
            if kur is None or kur == SIFIR:
                katsayi = SIFIR
                uyari = f"{satir.malzeme_kodu} ({satir.ad}): {pb} kuru tanımsız, 0 TL alındı"
            else:
                katsayi = kur
        elif pb == "TL":
            katsayi = BIR + p.enflasyon
        elif not elle_fiyat:
            katsayi = SIFIR
            uyari = f"{satir.malzeme_kodu} ({satir.ad}): para birimi tanımsız ({pb}), 0 TL alındı"
    elif not elle_fiyat:
        uyarilar = []
        if malzeme.zs not in ("S", "Z", None):
            uyarilar.append(f"{satir.malzeme_kodu} ({satir.ad}): Z/S bayrağı tanımsız ({malzeme.zs})")
        if malzeme.para_birimi in DOVIZLER:
            uyarilar.append(f"{satir.malzeme_kodu} ({satir.ad}): Ziraat kaynaklı ama döviz fiyatlı ({malzeme.para_birimi}): "
                            "kur uygulanmaz, kontrol edin")
        uyari = "; ".join(uyarilar) or None
    if uyari is None and not elle_fiyat and malzeme is not None and malzeme.fiyat == SIFIR and satir.dugum_tipi != "ara_mamul"             and not satir.alt_satiri_var:
        uyari = f"{satir.malzeme_kodu} ({satir.ad}): birim fiyatı 0"
    tutar = katsayi * fiyat * brut
    tutar_firesiz = katsayi * fiyat * satir.miktar
    return MaliyetSatiri(kalem=satir.ad, grup="malzeme", miktar=satir.miktar, brut_miktar=brut,
                         birim_fiyat=fiyat, tutar=tutar, kod=satir.malzeme_kodu, tutar_firesiz=tutar_firesiz,
                         miktar_kaynagi="elle" if elle_miktar else "fire",
                         fiyat_kaynagi="elle" if elle_fiyat else "liste"), uyari


def malzeme_toplami(satirlar: list[MaliyetSatiri]) -> Decimal:
    return sum((s.tutar for s in satirlar), SIFIR)
