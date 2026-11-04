import hmac
from typing import Annotated
from urllib.parse import unquote
from fastapi import Depends, Header, Query, Request
from sqlalchemy.orm import Session
from ..depo import modeller as m
from ..depo.veritabani import oturum_ver  # yeniden dışa aktarım; testler bunu override eder
from ..servisler import hesap_servisi as hs, isitici, kimlik_servisi as ks
from ..servisler.hatalar import YetkiHatasi

# scope="function": oturum_ver'in commit'i, yanıt gönderilmeden önce (router fonksiyonu biter bitmez) çalışır.
OturumDep = Annotated[Session, Depends(oturum_ver, scope="function")]

__all__ = ["oturum_ver", "OturumDep", "kullanici_ver", "senaryo_ver", "SenaryoDep", "kimlik_denetle", "GirisKullanicisiDep", "CEREZ"]

CEREZ = "fc_oturum"   # oturum belirtecinin çerez adı (httpOnly)


def kimlik_denetle(request: Request, s: OturumDep) -> m.Kullanici | None:
    """Tüm /api/v1 uçlarının ortak bağımlılığı. Giriş zorunluysa (uygulama ayarı) çerezdeki oturumu doğrular, rolün bu isteğe
    izni olup olmadığına bakar ve kullanıcıyı request.state'e koyar. Giriş kapalıysa (testler, eski kurulum) None döner.
    Arka plan ısıtıcısı iç anahtarla yalnız GET yapabilir."""
    if not getattr(request.app.state, "giris_zorunlu", False):
        return None
    if request.method == "GET" and hmac.compare_digest(request.headers.get("X-Ic-Anahtar", ""), isitici.IC_ANAHTAR):
        return None
    k = ks.oturumdaki_kullanici(s, request.cookies.get(CEREZ))
    if k.sifre_degismeli and request.method != "GET":
        raise YetkiHatasi("önce kendi şifrenizi belirleyin", kod="sifre_degismeli")
    if not ks.yazabilir_mi(k.rol, request.method, request.url.path):
        raise YetkiHatasi(f"{ks.ROLLER.get(k.rol, k.rol)} rolünün bu işleme izni yok")
    request.state.kullanici = k
    return k


GirisKullanicisiDep = Annotated[m.Kullanici | None, Depends(kimlik_denetle)]


def kullanici_ver(request: Request, x_kullanici: str | None = Header(default=None)) -> str:
    """Değişikliği yapanın adı: giriş zorunluysa oturumdaki kullanıcı adı (taklit edilemez); değilse X-Kullanici başlığı
    (yüzde-kodlu gelebilir; HTTP başlıkları ASCII)."""
    k = getattr(request.state, "kullanici", None)
    if k is not None:
        return k.kullanici_adi
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
