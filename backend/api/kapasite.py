from fastapi import APIRouter, Depends, Query
from ..servisler import ambalaj_servisi, kapasite_servisi as ks
from ..servisler.donusum import decimal_str
from .bagimliliklar import OturumDep, SenaryoDep, kullanici_ver
from .semalar import HATA_404_409_422, HATA_404_422, AmbalajOzeti, KapasiteCikis, KapasiteGiris, KapasiteListesi

router = APIRouter(tags=["kapasite"])


def _kapasite(k) -> dict:
    return {"urun_kodu": k.urun_kodu, "urun_ad": k.urun_ad, **decimal_str({a: getattr(k, a) for a in ks.SAYISAL_ALANLAR})}


@router.get("/uretim-kapasitesi", response_model=KapasiteListesi, responses=HATA_404_422)
def listele(s: OturumDep, sen: SenaryoDep, sayfa: int = Query(1, ge=1), boyut: int = Query(50, ge=1, le=500)):
    kayitlar, toplam = ks.listele(s, sen.id, sayfa, boyut)
    return {"kayitlar": [_kapasite(k) for k in kayitlar], "toplam": toplam}


@router.put("/uretim-kapasitesi/{urun_kodu}", response_model=KapasiteCikis, responses=HATA_404_409_422)
def kaydet(s: OturumDep, urun_kodu: str, g: KapasiteGiris, sen: SenaryoDep, k: str = Depends(kullanici_ver)):
    alanlar = g.model_dump(include=set(ks.SAYISAL_ALANLAR))
    return _kapasite(ks.kaydet(s, sen.id, urun_kodu, alanlar, g.neden, g.urun_ad, k))


@router.get("/ambalaj-ozeti", response_model=AmbalajOzeti, responses=HATA_404_422)
def ambalaj_ozeti(s: OturumDep, sen: SenaryoDep):
    return decimal_str(ambalaj_servisi.ozet(s, sen.id))
