"""Maliyet muhasebesi raporları: bütçe / fiili birim maliyet kıyası, aylar arası SMM karşılaştırması, ürün birim maliyet kartı.
Hepsi salt okunur; var olan aşama ve SMM hesabının sonuçlarını yeniden sunar."""
from datetime import date
from fastapi import APIRouter, Query
from ..servisler import smm_gider_sarf_servisi as gs
from ..servisler import smm_rapor_servisi as sr
from .bagimliliklar import OturumDep
from .semalar import HATA_404_422, SmmButceKiyas, SmmGiderDagitimi, SmmKarsilastirma, SmmMaliyetKarti, SmmSarfOzeti

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


@router.get("/smm/donemler/{donem_id}/gider-dagitimi", response_model=SmmGiderDagitimi, responses=HATA_404_422)
def gider_dagitimi(s: OturumDep, donem_id: int, ilk: int = Query(20, ge=1, le=200)):
    """720 / 730 gider mizanı tutarı, aşamalara dağıtılan ve dağıtılmayan; aşama başına işçilik / GÜG ve en çok gider alan ürünler.
    Aşama hesabının sonuçlarından; yeni kural yok. 20 ve 50 havuzları birleşik (işçilik + GÜG) olduğundan 720 / 730'a bölünmez."""
    return gs.gider_dagitimi(s, donem_id, ilk)


@router.get("/smm/donemler/{donem_id}/sarf-farki/ozet", response_model=SmmSarfOzeti, responses=HATA_404_422)
def sarf_farki_ozeti(s: OturumDep, donem_id: int, ilk: int = Query(20, ge=1, le=200)):
    """Tutara göre en büyük ilk N sarf farkı (birim uyumsuzlar hariç, ayrı sayılır) ve fazla / eksik özeti."""
    return gs.sarf_farki_ozeti(s, donem_id, ilk)