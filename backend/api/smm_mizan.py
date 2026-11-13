"""SMM mizan satırlarının (gider 720/730, stok 150/151/152) elle girişi (ayrı router; şemaları burada)."""
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from ..servisler import smm_mizan_servisi as sms
from .bagimliliklar import OturumDep, kullanici_ver
from .semalar import HATA_404_409_422, SmmDonemCikis

router = APIRouter(tags=["smm"])
Tur = Literal["gider", "stok"]


class SmmMizanSatiri(BaseModel):
    hesap: str
    ad: str | None
    bakiye: str            # borç bakiyesi artı, alacak bakiyesi eksi (TL)
    elle: bool             # ekranda girildi ya da değiştirildi


class SmmMizan(BaseModel):
    donem: SmmDonemCikis
    tur: Tur
    ad: str
    kayitlar: list[SmmMizanSatiri]
    toplam: str
    elle: int               # elle satır sayısı
    elle_uyari: str | None  # "N elle satır var, yükleme bunları siler"


class SmmMizanGuncel(SmmMizan):
    degisti: list[str]


class SmmMizanEkleGiris(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hesap: str = Field(min_length=1, max_length=40)
    ad: str | None = Field(None, max_length=200)
    bakiye: Decimal
    neden: str = Field(min_length=1, max_length=300)


class SmmMizanGuncelleGiris(BaseModel):
    """Yalnız gönderilen alanlar değişir."""
    model_config = ConfigDict(extra="forbid")
    ad: str | None = Field(None, max_length=200)
    bakiye: Decimal | None = None
    neden: str = Field(min_length=1, max_length=300)


@router.get("/smm/donemler/{donem_id}/mizan/{tur}", response_model=SmmMizan, responses=HATA_404_409_422)
def mizan(s: OturumDep, donem_id: int, tur: Tur):
    """Dönemin gider ya da stok mizanı satırları, toplamı ve elle satır sayısı."""
    return sms.liste(s, donem_id, tur)


@router.post("/smm/donemler/{donem_id}/mizan/{tur}", response_model=SmmMizan, status_code=201, responses=HATA_404_409_422)
def mizan_satir_ekle(s: OturumDep, donem_id: int, tur: Tur, g: SmmMizanEkleGiris, k: str = Depends(kullanici_ver)):
    """Mizana elle satır ekler; hesap kodu varsa 409, dönem kilitliyse 409 (donem_kilitli)."""
    return sms.satir_ekle(s, donem_id, tur, g.hesap, g.ad, g.bakiye, g.neden, k)


@router.patch("/smm/donemler/{donem_id}/mizan/{tur}/{hesap}", response_model=SmmMizanGuncel, responses=HATA_404_409_422)
def mizan_satir_guncelle(s: OturumDep, donem_id: int, tur: Tur, hesap: str, g: SmmMizanGuncelleGiris, k: str = Depends(kullanici_ver)):
    """Satırın adını / bakiyesini değiştirir; neden zorunlu, günlüğe düşer, satır 'elle' işaretlenir."""
    return sms.satir_guncelle(s, donem_id, tur, hesap, g.model_dump(exclude={"neden"}, exclude_unset=True), g.neden, k)


@router.delete("/smm/donemler/{donem_id}/mizan/{tur}/{hesap}", response_model=SmmMizan, responses=HATA_404_409_422)
def mizan_satir_sil(s: OturumDep, donem_id: int, tur: Tur, hesap: str, neden: str = Query(min_length=1, max_length=300),
                    k: str = Depends(kullanici_ver)):
    """Satırı mizandan çıkarır (eski değeri günlükte kalır); neden sorgu parametresidir."""
    return sms.satir_sil(s, donem_id, tur, hesap, neden, k)
