"""Ürün maliyeti orkestrasyonu: UrunGirdisi -> MaliyetSonucu. Excel 001 sayfasının P sütunu sırasıyla."""
from dataclasses import replace
from decimal import Decimal
from .finansman import doviz_maliyet, tum_finansman
from .fiyat import satis_fiyati, suzme_kg_fiyati, teklifler, yuzdeleri_doldur
from .malzeme import malzeme_toplami, malzeme_tutari
from .modeller import GiderOranlari, Malzeme, MaliyetSatiri, MaliyetSonucu, Parametreler, UrunGirdisi
from .para import SIFIR
from .uretim_gideri import diger_giderler, direkt_iscilik, genel_uretim


def _toplam(satirlar: list[MaliyetSatiri]) -> Decimal:
    return sum((s.tutar for s in satirlar), SIFIR)


def urun_maliyeti(girdi: UrunGirdisi, malzemeler: dict[str, Malzeme], oranlar: GiderOranlari, p: Parametreler,
                 firesiz_hesapla: bool = True) -> MaliyetSonucu:
    uyarilar: list[str] = []
    malz_satirlari = []
    for rs in girdi.recete:
        s, u = malzeme_tutari(rs, malzemeler.get(rs.malzeme_kodu), p)
        malz_satirlari.append(s)
        if u:
            uyarilar.append(u)
    if girdi.uretim.pazar == "Yurtdışı":
        uyarilar.append("Yurtdışı yüzde kuralı Excel'de doğrulanmadı (ihracat sayfası yok)")
    di, u1 = direkt_iscilik(girdi.uretim, oranlar, p)
    gug, u2 = genel_uretim(girdi.uretim, oranlar, p)
    diger, u3 = diger_giderler(girdi.uretim, oranlar)
    uyarilar += u1 + u2 + u3

    malzeme_top = malzeme_toplami(malz_satirlari)
    di_top, gug_top, diger_top = _toplam(di), _toplam(gug), _toplam(diger)
    uretim_top = di_top + gug_top
    birim = malzeme_top + uretim_top
    giydirilmis = birim + diger_top
    fin = tum_finansman(giydirilmis, p)
    for pb in sorted(set(p.faiz_oranlari) ^ set(p.stok_sureleri_ay)):
        uyarilar.append(f"{pb} faiz/stok süresi eşleşmiyor, atlandı")
    if "TL" not in fin:
        uyarilar.append("TL finansman parametresi yok, finansman 0 alındı")
    if "USD" not in p.kurlar or p.kurlar["USD"] <= 0:
        uyarilar.append("USD kuru yok, USD maliyet/teklif 0 alındı")
    if p.vardiya_saati <= 0:
        uyarilar.append("vardiya saati 0")
    maliyet_tl = giydirilmis + fin.get("TL", SIFIR)
    doviz = doviz_maliyet(giydirilmis, fin, p)
    satis_tl = satis_fiyati(maliyet_tl, p.satis_kar_orani)
    satis_doviz = {pb: satis_fiyati(m, p.satis_kar_orani) for pb, m in doviz.items()}
    usd = doviz.get("USD", SIFIR)

    fin_satiri = MaliyetSatiri(kalem="Finansman Giderleri (TL)", grup="finansman", miktar=Decimal(1), brut_miktar=Decimal(1),
                               birim_fiyat=fin.get("TL", SIFIR), tutar=fin.get("TL", SIFIR),
                               kod="finansman_tl")
    for g in di + gug + diger + [fin_satiri]:
        g.tutar_firesiz = g.tutar
        g.miktar_kaynagi = g.fiyat_kaynagi = "-"
    satirlar = malz_satirlari + di + gug + diger + [fin_satiri]
    yuzdeleri_doldur(satirlar, girdi.uretim.pazar, maliyet_tl, satis_tl, p.kurlar.get("USD", SIFIR),
                     usd, satis_doviz.get("USD", SIFIR))

    uyarilar = list(dict.fromkeys(uyarilar))     # sırayı koru, birebir tekrarları at

    sonuc = MaliyetSonucu(
        urun_kodu=girdi.kod, satirlar=satirlar,
        malzeme_toplami=malzeme_top, direkt_iscilik_toplami=di_top, gug_toplami=gug_top,
        uretim_gideri_toplami=uretim_top, toplam_birim_maliyet=birim,
        pazarlama_gideri=diger[0].tutar, yonetim_gideri=diger[1].tutar, diger_giderler_toplami=diger_top,
        giydirilmis_maliyet=giydirilmis, finansman=fin, finansman_dahil_maliyet_tl=maliyet_tl,
        doviz_maliyet=doviz, satis_fiyati_tl=satis_tl, satis_fiyati_doviz=satis_doviz,
        suzme_kg_fiyati_tl=suzme_kg_fiyati(satis_tl, girdi.uretim.suzme_kg),
        teklifler_usd=teklifler(usd, p.teklif_kar_oranlari), uyarilar=uyarilar,
    )
    if firesiz_hesapla:
        girdi_firesiz = replace(
            girdi,
            recete=tuple(replace(r, fire_orani=SIFIR, brut_miktar_elle=None) for r in girdi.recete),
            uretim=replace(girdi.uretim, mal_kabul_fire=SIFIR))
        sonuc.firesiz = urun_maliyeti(girdi_firesiz, malzemeler, oranlar, p, firesiz_hesapla=False)
    return sonuc
