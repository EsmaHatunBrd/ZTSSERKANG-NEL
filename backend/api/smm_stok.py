"""SMM stok/envanter kalemlerinin elle düzenlenmesi (ayrı router: paylaşımlı şema dosyasına dokunmaz)."""
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from ..servisler import smm_stok_servisi as sts
from .bagimliliklar import OturumDep, kullanici_ver
from .semalar import HATA_404_409_422, HATA_404_422

router = APIRouter(tags=["smm"])


class SmmKalemGuncelleGiris(BaseModel):
    """Yalnız gönderilen alanlar değişir; sayısal alanlar metin ya da sayı olabilir (Decimal'e çevrilir), negatif olamaz."""
    model_config = ConfigDict(extra="forbid")
    neden: str = Field(min_length=1, max_length=300)
    ad: str | None = None
    birim: str | None = None
    tur: str | None = None
    mizan_kodu: str | None = None
    dbs_miktar: Decimal | None = None
    dbs_tutar: Decimal | None = None
    alim_miktar: Decimal | None = None
    alim_tutar: Decimal | None = None
    iade_miktar: Decimal | None = None
    iade_tutar: Decimal | None = None
    uretim_miktar: Decimal | None = None
    sayim_miktar: Decimal | None = None
    sahit_miktar: Decimal | None = None


class SmmKalemEkleGiris(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kod: str = Field(min_length=1, max_length=40)
    ad: str | None = None
    birim: str | None = None
    tur: str | None = None
    mizan_kodu: str | None = None
    neden: str = Field(min_length=1, max_length=300)
    dbs_miktar: Decimal | None = None
    dbs_tutar: Decimal | None = None
    alim_miktar: Decimal | None = None
    alim_tutar: Decimal | None = None
    iade_miktar: Decimal | None = None
    iade_tutar: Decimal | None = None
    uretim_miktar: Decimal | None = None
    sayim_miktar: Decimal | None = None
    sahit_miktar: Decimal | None = None


class SmmElleKayit(BaseModel):
    alanlar: list[str]
    zaman: str | None
    kullanici: str | None
    kayit: int


class SmmElleDegisenler(BaseModel):
    kayitlar: dict[str, SmmElleKayit]


@router.get("/smm/donemler/{donem_id}/stok/elle", response_model=SmmElleDegisenler, responses=HATA_404_422)
def elle_degisenler(s: OturumDep, donem_id: int):
    """Dönemde ekranda değiştirilmiş ya da eklenmiş kalemler (kod → alanlar, son zaman, kullanıcı)."""
    return sts.elle_degisenler(s, donem_id)


@router.patch("/smm/donemler/{donem_id}/stok/{kod}", response_model=dict, responses=HATA_404_422)
def kalem_guncelle(s: OturumDep, donem_id: int, kod: str, g: SmmKalemGuncelleGiris, k: str = Depends(kullanici_ver)):
    """Kalemin dönem başı / alım / iade / üretim / sayım / şahit ve kart alanlarını değiştirir; neden zorunlu, günlüğe düşer."""
    alanlar = {a: v for a, v in g.model_dump(exclude={"neden"}, exclude_unset=True).items()}
    return sts.kalem_guncelle(s, donem_id, kod, alanlar, g.neden, k)


@router.post("/smm/donemler/{donem_id}/stok", response_model=dict, status_code=201, responses=HATA_404_409_422)
def kalem_ekle(s: OturumDep, donem_id: int, g: SmmKalemEkleGiris, k: str = Depends(kullanici_ver)):
    """Excel'de olmayan yeni stok kalemi açar; kod dönemde varsa 409."""
    v = g.model_dump(exclude_unset=True)
    return sts.kalem_ekle(s, donem_id, v.pop("kod"), v.pop("ad", None), v.pop("birim", None), v.pop("tur", None), v.pop("mizan_kodu", None),
                          v.pop("neden"), k, **v)
