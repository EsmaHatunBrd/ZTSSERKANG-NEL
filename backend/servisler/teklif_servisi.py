# backend/servisler/teklif_servisi.py
"""Teklif turları: kayıtlı hesabın snapshot'ı üzerinden kâr oranıyla fiyat. Tur sayısı sınırsız."""
from decimal import Decimal
from sqlalchemy import func, select
from sqlalchemy.engine import Row
from sqlalchemy.orm import Session
from ..depo import modeller as m
from .donusum import decimal_str
from .hatalar import BulunamadiHatasi, CatismaHatasi, DogrulamaHatasi

DURUMLAR = ("taslak", "gonderildi", "kabul", "red")
KABUL_SILINEMEZ = "Kabul edilmiş teklif silinemez; önce durumunu değiştirin."


def tur_ekle(s: Session, hesap_id: int, kar_orani: Decimal, musteri: str | None = None, notu: str | None = None, kullanici: str = "sistem") -> m.Teklif:
    h = s.get(m.MaliyetHesabi, hesap_id)
    if h is None:
        raise BulunamadiHatasi("Kayıtlı hesap bulunamadı.", {"hesap_id": hesap_id})
    kar = Decimal(kar_orani); carpan = 1 + kar
    sn = h.sonuc_snapshot
    doviz = sn.get("doviz_maliyet", {})
    son = max(s.scalar(select(func.max(m.Teklif.tur_no)).where(m.Teklif.maliyet_hesabi_id == hesap_id)) or 0, _silinen_son_tur(s, hesap_id))
    t = m.Teklif(maliyet_hesabi_id=hesap_id, tur_no=son + 1, kar_orani=kar,
                 fiyat_tl=Decimal(sn["finansman_dahil_maliyet_tl"]) * carpan,
                 fiyat_usd=Decimal(doviz["USD"]) * carpan if "USD" in doviz else None,
                 fiyat_eur=Decimal(doviz["EUR"]) * carpan if "EUR" in doviz else None,
                 musteri=musteri, durum="taslak", notu=notu, olusturan=kullanici)
    s.add(t); s.flush()
    return t


def turlar(s: Session, hesap_id: int) -> list[m.Teklif]:
    return list(s.scalars(select(m.Teklif).where(m.Teklif.maliyet_hesabi_id == hesap_id).order_by(m.Teklif.tur_no)))


def senaryo_teklifleri(s: Session, senaryo_id: int, durum: str | None = None, musteri: str | None = None,
                       urun: str | None = None) -> list[Row]:
    """Senaryodaki tüm teklif turları (en yeni önce): tek birleşik sorgu Teklif -> MaliyetHesabi -> Urun.
    durum: tam eşleşme; musteri: büyük/küçük harf duyarsız içerir (ILIKE); urun: ürün kodu ya da adında içerir. Satır: (Teklif, MaliyetHesabi, Urun)."""
    q = (select(m.Teklif, m.MaliyetHesabi, m.Urun)
         .join(m.MaliyetHesabi, m.MaliyetHesabi.id == m.Teklif.maliyet_hesabi_id)
         .join(m.Urun, m.Urun.id == m.MaliyetHesabi.urun_id)
         .where(m.MaliyetHesabi.senaryo_id == senaryo_id))
    if durum is not None:
        q = q.where(m.Teklif.durum == durum)
    if musteri:
        kacis = musteri.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        q = q.where(m.Teklif.musteri.ilike(f"%{kacis}%", escape="\\"))
    if urun:
        kacis = urun.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        q = q.where(m.Urun.kod.ilike(f"%{kacis}%", escape="\\") | m.Urun.ad.ilike(f"%{kacis}%", escape="\\"))
    return list(s.execute(q.order_by(m.Teklif.id.desc())).all())


def son_turlar(s: Session, hesap_idleri: list[int]) -> dict[int, m.Teklif]:
    """Hesap başına en yüksek tur_no'lu teklif (tek sorgu); teklifi olmayan hesap sözlükte yer almaz."""
    if not hesap_idleri:
        return {}
    q = select(m.Teklif).where(m.Teklif.maliyet_hesabi_id.in_(hesap_idleri)).order_by(m.Teklif.tur_no)
    return {t.maliyet_hesabi_id: t for t in s.scalars(q)}   # tur_no artan: son atama en yüksek turu bırakır


def _silinen_son_tur(s: Session, hesap_id: int) -> int:
    """Silinmiş turların en büyük numarası: silinen tur numarası yeniden verilmez (sıra izi korunur)."""
    q = select(m.DegisiklikKaydi.eski).where(m.DegisiklikKaydi.tablo == "teklif", m.DegisiklikKaydi.islem == "sil")
    return max((e.get("tur_no") or 0 for e in s.scalars(q) if isinstance(e, dict) and e.get("hesap_id") == hesap_id), default=0)


def sil(s: Session, teklif_id: int, kullanici: str = "sistem", neden: str | None = None) -> None:
    """Teklif turu kalıcı silinir; içeriği (ürün, tur, kâr, fiyat, müşteri, durum) Değişiklik Günlüğünde saklanır.
    Diğer turların numarası değişmez. Kabul edilmiş teklif silinmez (409); önce durumu değiştirilmelidir."""
    t = s.get(m.Teklif, teklif_id)
    if t is None:
        raise BulunamadiHatasi("Teklif turu bulunamadı.", {"teklif_id": teklif_id})
    if t.durum == "kabul":
        raise CatismaHatasi(KABUL_SILINEMEZ)
    h = s.get(m.MaliyetHesabi, t.maliyet_hesabi_id)
    u = s.get(m.Urun, h.urun_id) if h else None
    s.add(m.DegisiklikKaydi(tablo="teklif", kayit_id=t.id, islem="sil", yeni={"_neden": neden} if neden else None, kullanici=kullanici,
                            eski=decimal_str({"urun_kodu": u.kod if u else None, "senaryo_id": h.senaryo_id if h else None,
                                              "hesap_id": t.maliyet_hesabi_id, "tur_no": t.tur_no, "kar_orani": t.kar_orani,
                                              "fiyat_tl": t.fiyat_tl, "musteri": t.musteri, "durum": t.durum})))
    s.delete(t)
    s.flush()


def durum_guncelle(s: Session, teklif_id: int, durum: str) -> m.Teklif:
    if durum not in DURUMLAR:
        raise DogrulamaHatasi("Teklif durumu taslak, gönderildi, kabul ya da red olmalı.", {"durum": durum, "izinli": list(DURUMLAR)})
    t = s.get(m.Teklif, teklif_id)
    if t is None:
        raise BulunamadiHatasi("Teklif turu bulunamadı.", {"teklif_id": teklif_id})
    t.durum = durum; s.flush()
    return t
