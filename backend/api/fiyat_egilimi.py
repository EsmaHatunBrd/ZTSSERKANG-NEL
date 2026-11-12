"""Fiyat eğilimi (analiz önerisi 9): malzeme fiyatlarının son `ay` aydaki değişimi, yıllıklandırılmış artış ve enflasyon eşiği. Kaydetmez."""
from datetime import date
from fastapi import APIRouter, Query
from ..servisler import fiyat_egilimi_servisi as fe
from .bagimliliklar import OturumDep, SenaryoDep
from .semalar import HATA_404_422, FiyatEgilimiCikis

router = APIRouter(tags=["analiz"])


@router.get("/analiz/fiyat-egilimi", response_model=FiyatEgilimiCikis, responses=HATA_404_422)
def fiyat_egilimi(s: OturumDep, sen: SenaryoDep, ay: int = Query(12, ge=1, le=120, description="Pencere uzunluğu (ay)"),
                  yalniz_asan: bool = Query(False, description="1: yalnız enflasyonu aşan malzemeler"),
                  tarih: date | None = Query(None, description="Pencere sonu; boşsa bugün")):
    """Her malzeme için pencere başı/sonu fiyatı, değişim %, yıllık %, eşik (TL: enflasyon parametresi; döviz: 0) ve aşıp aşmadığı.
    Sıralama: aşanlar önce, sonra yıllık % azalan."""
    return fe.egilim(s, sen.id, ay, tarih, yalniz_asan)
