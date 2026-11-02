from typing import Annotated
from urllib.parse import unquote
from fastapi import Depends, Header, Query, Request
from sqlalchemy.orm import Session
from ..depo import modeller as m
from ..depo.veritabani import oturum_ver  # yeniden dışa aktarım; testler bunu override eder
from ..servisler import hesap_servisi as hs

# scope="function": oturum_ver'in commit'i, yanıt gönderilmeden önce (router fonksiyonu biter bitmez) çalışır.
OturumDep = Annotated[Session, Depends(oturum_ver, scope="function")]

__all__ = ["oturum_ver", "OturumDep", "kullanici_ver", "senaryo_ver", "SenaryoDep"]


def kullanici_ver(x_kullanici: str | None = Header(default=None)) -> str:
    """X-Kullanici başlığı yüzde-kodlu gelebilir (HTTP başlıkları ASCII); çözülerek kullanılır."""
    return unquote(x_kullanici) if x_kullanici else "sistem"


YAZMA_YONTEMLERI = ("POST", "PUT", "PATCH", "DELETE")


def senaryo_ver(s: OturumDep, request: Request, senaryo: int = Query(...)) -> m.Senaryo:
    """Her `?senaryo=` alan uçta aynı doğrulama: bilinmeyen senaryo -> 404 (BulunamadiHatasi).
    Kilitli senaryoda yazan istek (POST/PUT/PATCH/DELETE) 409 `senaryo kilitli`; salt okunur `.../hesapla` POST'u hariç."""
    sen = hs.senaryo_getir(s, senaryo)
    if request.method in YAZMA_YONTEMLERI and not request.url.path.rstrip("/").endswith("/hesapla"):
        hs.kilit_denetle(sen)
    return sen


SenaryoDep = Annotated[m.Senaryo, Depends(senaryo_ver)]
