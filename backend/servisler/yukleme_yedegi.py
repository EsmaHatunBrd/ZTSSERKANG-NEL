"""Son yüklemeyi geri al: her Excel yüklemesi yazmadan önce etkilediği verinin JSON kopyasını burada saklar.

Kullanım (alana özel servis içinde, aynı oturum/işlem):
    yedek_kaydet(s, "satin_alma_fiyat", str(senaryo_id), {"satirlar": [...]}, ozet="312 fiyat", kaynak_dosya=ad, kullanici=k)
    ... yükleme yazılır ...
Geri alırken:
    y = son_yedek(s, "satin_alma_fiyat", str(senaryo_id))   # yoksa None
    ... y.veri ile eski durum geri yazılır ...
    geri_alindi_isaretle(s, y)
Alan başına yalnız son YEDEK_SAYISI kayıt tutulur. Geri alınmış yedek ikinci kez kullanılmaz.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..depo import modeller as m
from .hatalar import BulunamadiHatasi

YEDEK_SAYISI = 5


def yedek_kaydet(s: Session, alan: str, kapsam: str, veri: dict, ozet: str = "", kaynak_dosya: str | None = None,
                 kullanici: str = "sistem") -> m.YuklemeYedegi:
    y = m.YuklemeYedegi(alan=alan, kapsam=kapsam, veri=veri, ozet=ozet[:300], kaynak_dosya=(kaynak_dosya or None) and kaynak_dosya[:200],
                        olusturan=kullanici)
    s.add(y)
    s.flush()
    eskiler = s.scalars(select(m.YuklemeYedegi).where(m.YuklemeYedegi.alan == alan, m.YuklemeYedegi.kapsam == kapsam)
                        .order_by(m.YuklemeYedegi.id.desc()).offset(YEDEK_SAYISI)).all()
    for e in eskiler:
        s.delete(e)
    return y


def son_yedek(s: Session, alan: str, kapsam: str) -> m.YuklemeYedegi | None:
    return s.scalars(select(m.YuklemeYedegi).where(m.YuklemeYedegi.alan == alan, m.YuklemeYedegi.kapsam == kapsam,
                                                   m.YuklemeYedegi.geri_alindi.is_(False))
                     .order_by(m.YuklemeYedegi.id.desc()).limit(1)).first()


def son_yedek_zorunlu(s: Session, alan: str, kapsam: str) -> m.YuklemeYedegi:
    y = son_yedek(s, alan, kapsam)
    if y is None:
        raise BulunamadiHatasi("Geri alınacak bir yükleme yok.", kod="yedek_yok")
    return y


def geri_alindi_isaretle(s: Session, y: m.YuklemeYedegi) -> None:
    y.geri_alindi = True
    s.flush()


def yedek_ozeti(y: m.YuklemeYedegi | None) -> dict | None:
    """Arayüz için: "Son yükleme: 16.11.2026 14:20, Esma, 312 fiyat — Geri al"."""
    if y is None:
        return None
    return {"id": y.id, "zaman": y.olusturma_zamani.isoformat() if y.olusturma_zamani else None, "olusturan": y.olusturan,
            "ozet": y.ozet, "kaynak_dosya": y.kaynak_dosya}
