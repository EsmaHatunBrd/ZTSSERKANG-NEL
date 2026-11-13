"""Maliyet muhasebesi raporları: bütçe / fiili birim maliyet kıyası, aylar arası SMM karşılaştırması, ürün birim maliyet kartı.
Hepsi salt okunur; var olan aşama ve SMM hesabının sonuçlarını yeniden sunar."""
from datetime import date
from fastapi import APIRouter, Query
from ..servisler import smm_rapor_servisi as sr
from .bagimliliklar import OturumDep
from .semalar import HATA_404_422, SmmButceKiyas, SmmKarsilastirma, SmmMaliyetKarti

router = APIRouter(tags=["smm"])


@router.get("/smm/donemler/{donem_id}/butce-kiyas", response_model=SmmButceKiyas, responses=HATA_404_422)
def butce_kiyas(s: OturumDep, donem_id: int, senaryo: int = Query(...), tarih: date | None = None):
    """Fiyat Çalışması senaryosunun bütçe üretim maliyeti (finansman, pazarlama, yönetim hariç) ile dönemin fiili SMM birim maliyeti;
    eşleme ürün koduyla. Eşleşmeyenler `yalniz_butce` ve `yalniz_fiili` listelerinde."""
    return sr.butce_kiyas(s, donem_id, senaryo, tarih)


@router.get("/smm/karsilastirma", response_model=SmmKarsilastirma, responses=HATA_404_422)
def karsilastirma(s: OturumDep, donemler: str | None = Query(None, max_length=200, description="virgülle dönem id'leri; boşsa son 6 dönem")):
    """Dönemlerin SMM tablosu ana satırları (en eski başta) ve bir önceki döneme göre değişim."""
    return sr.karsilastirma(s, donemler)


@router.get("/smm/donemler/{donem_id}/urun/{kod}/maliyet-karti", response_model=SmmMaliyetKarti, responses=HATA_404_422)
def maliyet_karti(s: OturumDep, donem_id: int, kod: str):
    """Ürünün aşama aşama birim maliyeti, reçete satırları ve bir önceki dönemle farkı."""
    return sr.maliyet_karti(s, donem_id, kod)
