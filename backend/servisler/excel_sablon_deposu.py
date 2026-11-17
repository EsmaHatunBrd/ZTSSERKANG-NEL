"""Müşavir Excel'i şablonları: yükleme sırasında kullanıcının kendi Excel'inin kopyası saklanır (veritabanında, yedeklere girer).

    kaydet(s, "fiyat_kitabi", str(senaryo_id), dosya_adi, icerik, kullanici)   # yükleme başarıyla yazıldıktan sonra
    son(s, "fiyat_kitabi", str(senaryo_id))  -> m.ExcelSablonu | None
    ozet(sablon) -> {"dosya_adi", "zaman", "olusturan", "boyut"} | None    # arayüzde "Şablon: <ad>, <tarih>"
Kapsam başına yalnız en son kopya tutulur.
"""
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..depo import modeller as m

TURLER = ("fiyat_kitabi", "smm_donem")


def kaydet(s: Session, tur: str, kapsam: str, dosya_adi: str, icerik: bytes, kullanici: str = "sistem") -> m.ExcelSablonu:
    assert tur in TURLER, tur
    s.execute(delete(m.ExcelSablonu).where(m.ExcelSablonu.tur == tur, m.ExcelSablonu.kapsam == kapsam))
    y = m.ExcelSablonu(tur=tur, kapsam=kapsam, dosya_adi=(dosya_adi or "sablon.xlsx")[:200], boyut=len(icerik), icerik=icerik,
                       olusturan=kullanici)
    s.add(y)
    s.flush()
    return y


def son(s: Session, tur: str, kapsam: str) -> m.ExcelSablonu | None:
    return s.scalars(select(m.ExcelSablonu).where(m.ExcelSablonu.tur == tur, m.ExcelSablonu.kapsam == kapsam)
                     .order_by(m.ExcelSablonu.id.desc()).limit(1)).first()


def sil(s: Session, tur: str, kapsam: str) -> None:
    s.execute(delete(m.ExcelSablonu).where(m.ExcelSablonu.tur == tur, m.ExcelSablonu.kapsam == kapsam))


def ozet(y: m.ExcelSablonu | None) -> dict | None:
    if y is None:
        return None
    return {"dosya_adi": y.dosya_adi, "zaman": y.olusturma_zamani.isoformat() if y.olusturma_zamani else None,
            "olusturan": y.olusturan, "boyut": y.boyut}
