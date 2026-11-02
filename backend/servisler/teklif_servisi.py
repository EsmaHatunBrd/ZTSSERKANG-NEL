# backend/servisler/teklif_servisi.py
"""Teklif turları: kayıtlı hesabın snapshot'ı üzerinden kâr oranıyla fiyat. Tur sayısı sınırsız."""
from decimal import Decimal
from sqlalchemy import func, select
from sqlalchemy.engine import Row
from sqlalchemy.orm import Session
from ..depo import modeller as m
from .hatalar import BulunamadiHatasi, DogrulamaHatasi

DURUMLAR = ("taslak", "gonderildi", "kabul", "red")


def tur_ekle(s: Session, hesap_id: int, kar_orani: Decimal, musteri: str | None = None, notu: str | None = None, kullanici: str = "sistem") -> m.Teklif:
    h = s.get(m.MaliyetHesabi, hesap_id)
    if h is None:
        raise BulunamadiHatasi("hesap yok", {"hesap_id": hesap_id})
    kar = Decimal(kar_orani); carpan = 1 + kar
    sn = h.sonuc_snapshot
    doviz = sn.get("doviz_maliyet", {})
    son = s.scalar(select(func.max(m.Teklif.tur_no)).where(m.Teklif.maliyet_hesabi_id == hesap_id)) or 0
    t = m.Teklif(maliyet_hesabi_id=hesap_id, tur_no=son + 1, kar_orani=kar,
                 fiyat_tl=Decimal(sn["finansman_dahil_maliyet_tl"]) * carpan,
                 fiyat_usd=Decimal(doviz["USD"]) * carpan if "USD" in doviz else None,
                 fiyat_eur=Decimal(doviz["EUR"]) * carpan if "EUR" in doviz else None,
                 musteri=musteri, durum="taslak", notu=notu, olusturan=kullanici)
    s.add(t); s.flush()
    return t


def turlar(s: Session, hesap_id: int) -> list[m.Teklif]:
    return list(s.scalars(select(m.Teklif).where(m.Teklif.maliyet_hesabi_id == hesap_id).order_by(m.Teklif.tur_no)))


def senaryo_teklifleri(s: Session, senaryo_id: int, durum: str | None = None, musteri: str | None = None) -> list[Row]:
    """Senaryodaki tüm teklif turları (en yeni önce): tek birleşik sorgu Teklif -> MaliyetHesabi -> Urun.
    durum: tam eşleşme; musteri: büyük/küçük harf duyarsız içerir (ILIKE). Satır: (Teklif, MaliyetHesabi, Urun)."""
    q = (select(m.Teklif, m.MaliyetHesabi, m.Urun)
         .join(m.MaliyetHesabi, m.MaliyetHesabi.id == m.Teklif.maliyet_hesabi_id)
         .join(m.Urun, m.Urun.id == m.MaliyetHesabi.urun_id)
         .where(m.MaliyetHesabi.senaryo_id == senaryo_id))
    if durum is not None:
        q = q.where(m.Teklif.durum == durum)
    if musteri:
        kacis = musteri.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        q = q.where(m.Teklif.musteri.ilike(f"%{kacis}%", escape="\\"))
    return list(s.execute(q.order_by(m.Teklif.id.desc())).all())


def son_turlar(s: Session, hesap_idleri: list[int]) -> dict[int, m.Teklif]:
    """Hesap başına en yüksek tur_no'lu teklif (tek sorgu); teklifi olmayan hesap sözlükte yer almaz."""
    if not hesap_idleri:
        return {}
    q = select(m.Teklif).where(m.Teklif.maliyet_hesabi_id.in_(hesap_idleri)).order_by(m.Teklif.tur_no)
    return {t.maliyet_hesabi_id: t for t in s.scalars(q)}   # tur_no artan: son atama en yüksek turu bırakır


def durum_guncelle(s: Session, teklif_id: int, durum: str) -> m.Teklif:
    if durum not in DURUMLAR:
        raise DogrulamaHatasi("durum geçersiz", {"durum": durum, "izinli": list(DURUMLAR)})
    t = s.get(m.Teklif, teklif_id)
    if t is None:
        raise BulunamadiHatasi("teklif yok", {"teklif_id": teklif_id})
    t.durum = durum; s.flush()
    return t
