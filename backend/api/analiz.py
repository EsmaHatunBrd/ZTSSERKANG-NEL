"""Analizler: ya olursa (kur / ambalaj / hammadde / üretim adedi) ve malzeme zam etkisi. Kaydetmez; yalnız okur ve hesaplar."""
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Query
from ..servisler import analiz_servisi as an
from .bagimliliklar import OturumDep, SenaryoDep
from .semalar import HATA_404_422, HedefFiyatCikis, KarlilikCikis, KurRiskiCikis, OnemliMalzemelerCikis, YaOlursaCikis, ZamEtkisiCikis

router = APIRouter(tags=["analiz"])


@router.get("/analiz/ya-olursa", response_model=YaOlursaCikis, responses=HATA_404_422)
def ya_olursa(s: OturumDep, sen: SenaryoDep, kur: Decimal = Query(Decimal(0), description="Döviz kurlarındaki değişim (0.1 = %10)"),
              ambalaj: Decimal = Query(Decimal(0)), hammadde: Decimal = Query(Decimal(0)), adet: Decimal = Query(Decimal(0))):
    return an.ya_olursa(s, sen.id, kur, ambalaj, hammadde, adet)


@router.get("/analiz/zam-etkisi", response_model=ZamEtkisiCikis, responses=HATA_404_422)
def zam_etkisi(s: OturumDep, sen: SenaryoDep, malzeme: str = Query(..., min_length=1), oran: Decimal = Query(...)):
    return an.zam_etkisi(s, sen.id, malzeme, oran)


@router.get("/analiz/kur-riski", response_model=KurRiskiCikis, responses=HATA_404_422)
def kur_riski(s: OturumDep, sen: SenaryoDep, oran: Decimal = Query(Decimal("0.10"), description="Kurlardaki artış (0.1 = %10)")):
    """Kurlar `oran` kadar artarsa ürün başına ve yıllık maliyet etkisi; döviz / USD / EUR payı."""
    return an.kur_riski(s, sen.id, oran)


@router.get("/analiz/karlilik", response_model=KarlilikCikis, responses=HATA_404_422)
def karlilik(s: OturumDep, sen: SenaryoDep):
    """Kârlılık haritası: yıllık adet x marj, dört bölge (eşikler: marj_esigi ve adet medyanı)."""
    return an.karlilik(s, sen.id)


@router.get("/analiz/hedef-fiyat", response_model=HedefFiyatCikis, responses=HATA_404_422)
def hedef_fiyat(s: OturumDep, sen: SenaryoDep,
                marj: Decimal | None = Query(None, description="Hedef marj (0.15 = %15); boşsa marj eşiği")):
    """Marjı koruyan fiyat: hedef fiyat = maliyet x (1 + marj), geçen yıl fiyatına göre gereken zam, liste fiyatı ve yıllık ek gelir."""
    return an.hedef_fiyat(s, sen.id, marj)


@router.get("/analiz/onemli-malzemeler", response_model=OnemliMalzemelerCikis, responses=HATA_404_422)
def onemli_malzemeler(s: OturumDep, sen: SenaryoDep, tarih: date | None = None,
                      esik: Decimal = Query(an.VARSAYILAN_ONEM_ESIGI, description="Kümülatif pay eşiği (0.8 = %80)")):
    """Önemli malzemeler (80/20): yıllık üretim adediyle ağırlıklı malzeme tutarları, pay ve kümülatif pay. Yalnız okur."""
    return an.onemli_malzemeler(s, sen.id, esik, tarih)
