"""Giriş/çıkış, oturumdaki kullanıcı, şifre değiştirme ve (yalnız Genel Direktör) kullanıcı yönetimi."""
from typing import Literal
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field
from ..servisler import kimlik_servisi as ks
from ..servisler.hatalar import KimlikHatasi
from .bagimliliklar import CEREZ, GirisKullanicisiDep, OturumDep
from .semalar import HATA_404_409_422

acik_router = APIRouter(tags=["kimlik"])   # kimlik_denetle'siz: giriş ekranı bunlarla çalışır
router = APIRouter(tags=["kimlik"])        # kimlik_denetle'li (uygulama.py)

CEREZ_OMRU_SN = 10 * 365 * 24 * 3600   # oturum çıkış yapılana kadar açık kalır; çerez tarayıcı kapansa da silinmez

Rol = Literal["genel_direktor", "muhasebe", "satin_alma", "izleyici"]


class KullaniciCikis(BaseModel):
    id: int
    kullanici_adi: str
    ad: str
    rol: Rol
    rol_ad: str
    aktif: bool
    sifre_degismeli: bool
    son_giris: str | None = None


class BenCikis(BaseModel):
    """giris_zorunlu=false (eski kurulum / testler): kullanici null, arayüz giriş ekranı göstermez."""
    giris_zorunlu: bool
    kullanici: KullaniciCikis | None


class GirisGiris(BaseModel):
    kullanici_adi: str = Field(min_length=1, max_length=64)
    sifre: str = Field(min_length=1, max_length=200)


class SifreDegistirGiris(BaseModel):
    eski_sifre: str = Field(min_length=1, max_length=200)
    yeni_sifre: str = Field(min_length=1, max_length=200)


class KullaniciEkleGiris(BaseModel):
    kullanici_adi: str = Field(min_length=1, max_length=64)
    ad: str = Field(min_length=1, max_length=120)
    rol: Rol
    gecici_sifre: str = Field(min_length=1, max_length=200)


class KullaniciGuncelleGiris(BaseModel):
    ad: str | None = Field(default=None, max_length=120)
    rol: Rol | None = None
    aktif: bool | None = None


class SifreSifirlaGiris(BaseModel):
    gecici_sifre: str = Field(min_length=1, max_length=200)


class KullaniciListesi(BaseModel):
    kayitlar: list[KullaniciCikis]
    toplam: int
    roller: dict[str, str]


def _giris_zorunlu(request: Request) -> bool:
    return bool(getattr(request.app.state, "giris_zorunlu", False))


@acik_router.get("/kimlik/ben", response_model=BenCikis)
def ben(s: OturumDep, request: Request):
    """Giriş zorunlu değilse {giris_zorunlu: false}. Zorunluysa oturumdaki kullanıcı; oturum yoksa 401."""
    if not _giris_zorunlu(request):
        return {"giris_zorunlu": False, "kullanici": None}
    return {"giris_zorunlu": True, "kullanici": ks.kullanici_dict(ks.oturumdaki_kullanici(s, request.cookies.get(CEREZ)))}


@acik_router.post("/kimlik/giris", response_model=BenCikis, responses=HATA_404_409_422)
def giris(s: OturumDep, g: GirisGiris, request: Request, yanit: Response):
    try:
        k, belirtec = ks.giris(s, g.kullanici_adi, g.sifre)
    except KimlikHatasi:
        s.commit()   # hatalı deneme sayacı / kilit yazılsın (hata yanıtında oturum geri alınır)
        raise
    yanit.set_cookie(CEREZ, belirtec, max_age=CEREZ_OMRU_SN, httponly=True, samesite="lax", path="/")
    return {"giris_zorunlu": _giris_zorunlu(request), "kullanici": ks.kullanici_dict(k)}


@acik_router.post("/kimlik/cikis", status_code=204, response_class=Response)
def cikis(s: OturumDep, request: Request):
    ks.cikis(s, request.cookies.get(CEREZ))
    yanit = Response(status_code=204)
    yanit.delete_cookie(CEREZ, path="/")
    return yanit


@acik_router.post("/kimlik/sifre", response_model=KullaniciCikis, responses=HATA_404_409_422)
def sifre_degistir(s: OturumDep, g: SifreDegistirGiris, request: Request):
    """Kendi şifresi (geçici şifreyle ilk girişte de bu kullanılır). Diğer cihazlardaki oturumlar kapanır."""
    belirtec = request.cookies.get(CEREZ)
    k = ks.oturumdaki_kullanici(s, belirtec)
    ks.sifre_degistir(s, k, g.eski_sifre, g.yeni_sifre, belirtec)
    return ks.kullanici_dict(k)


def _yonetici(k) -> None:
    if k is not None:   # giriş kapalıyken (testler) denetim yok
        ks.yonetici_denetle(k)


def _ad(k) -> str:
    return k.kullanici_adi if k is not None else "sistem"


@router.get("/kullanicilar", response_model=KullaniciListesi, responses=HATA_404_409_422)
def listele(s: OturumDep, k: GirisKullanicisiDep):
    _yonetici(k)
    kayitlar = [ks.kullanici_dict(x) for x in ks.listele(s)]
    return {"kayitlar": kayitlar, "toplam": len(kayitlar), "roller": ks.ROLLER}


@router.post("/kullanicilar", status_code=201, response_model=KullaniciCikis, responses=HATA_404_409_422)
def ekle(s: OturumDep, g: KullaniciEkleGiris, k: GirisKullanicisiDep):
    _yonetici(k)
    return ks.kullanici_dict(ks.kullanici_olustur(s, g.kullanici_adi, g.ad, g.rol, g.gecici_sifre, _ad(k)))


@router.patch("/kullanicilar/{kullanici_id}", response_model=KullaniciCikis, responses=HATA_404_409_422)
def guncelle(s: OturumDep, kullanici_id: int, g: KullaniciGuncelleGiris, k: GirisKullanicisiDep):
    _yonetici(k)
    return ks.kullanici_dict(ks.guncelle(s, kullanici_id, _ad(k), g.ad, g.rol, g.aktif))


@router.post("/kullanicilar/{kullanici_id}/sifre-sifirla", response_model=KullaniciCikis, responses=HATA_404_409_422)
def sifre_sifirla(s: OturumDep, kullanici_id: int, g: SifreSifirlaGiris, k: GirisKullanicisiDep):
    _yonetici(k)
    return ks.kullanici_dict(ks.sifre_sifirla(s, kullanici_id, g.gecici_sifre, _ad(k)))
