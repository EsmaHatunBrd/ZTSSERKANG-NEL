"""Malzeme kartı ve append-only bütçe birim fiyatı. Motorun Malzeme dataclass'ını üretir."""
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from fiyat_motoru.modeller import Malzeme as MotorMalzeme
from fiyat_motoru.para import SIFIR
from ..depo import modeller as m
from .hatalar import BulunamadiHatasi

IZLENEN = ("ad", "tip", "birim", "para_birimi", "zs")   # aktif ayrı işlem: malzeme_pasiflestir


def _malzeme(s: Session, kod: str) -> m.Malzeme:
    mz = s.scalar(select(m.Malzeme).where(m.Malzeme.kod == kod))
    if mz is None:
        raise BulunamadiHatasi(f"{kod} kodlu malzeme bulunamadı.", {"kod": kod})
    return mz


def malzeme_ekle_veya_guncelle(s: Session, kod: str, ad: str, tip: str | None, birim: str | None,
                               para_birimi: str | None, zs: str | None, kullanici: str = "sistem") -> m.Malzeme:
    mz = s.scalar(select(m.Malzeme).where(m.Malzeme.kod == kod))
    yeni = {"ad": ad, "tip": tip, "birim": birim, "para_birimi": para_birimi, "zs": zs}
    if mz is None:
        mz = m.Malzeme(kod=kod, **yeni, aktif=True, olusturan=kullanici); s.add(mz); s.flush()
        return mz
    eski = {a: getattr(mz, a) for a in IZLENEN}
    if eski != yeni:
        for a, v in yeni.items():
            setattr(mz, a, v)
        s.add(m.DegisiklikKaydi(tablo="malzeme", kayit_id=mz.id, islem="guncelle", eski=eski, yeni=yeni, kullanici=kullanici))
        s.flush()
    return mz


def malzeme_pasiflestir(s: Session, kod: str, kullanici: str = "sistem") -> m.Malzeme:
    mz = _malzeme(s, kod)
    if mz.aktif:
        mz.aktif = False
        s.add(m.DegisiklikKaydi(tablo="malzeme", kayit_id=mz.id, islem="pasiflestir", eski={"aktif": True}, yeni={"aktif": False}, kullanici=kullanici))
        s.flush()
    return mz


def recete_kartsiz_kodlar(s: Session, senaryo_id: int) -> list[str]:
    """Senaryodaki aktif reçetelerde geçen ama malzeme kartı olmayan kodlar. Ara mamul satırları bilinçli fiyatsızdır, sayılmaz."""
    kodlar = set(s.scalars(select(m.ReceteSatiri.malzeme_kodu).join(m.Recete, m.Recete.id == m.ReceteSatiri.recete_id)
                           .where(m.Recete.senaryo_id == senaryo_id, m.Recete.aktif == True, m.ReceteSatiri.dugum_tipi != "ara_mamul")))
    return sorted(kodlar - set(s.scalars(select(m.Malzeme.kod))))


def fiyat_ekle(s: Session, senaryo_id: int, kod: str, fiyat: Decimal, gecerlilik_basi: date, neden: str,
               kaynak: str = "elle", para_birimi: str | None = None, olusturan: str = "sistem") -> m.MalzemeFiyati:
    mz = _malzeme(s, kod)
    k = m.MalzemeFiyati(malzeme_id=mz.id, senaryo_id=senaryo_id, fiyat=Decimal(fiyat), para_birimi=para_birimi or mz.para_birimi,
                        gecerlilik_basi=gecerlilik_basi, kaynak=kaynak, neden=neden, olusturan=olusturan)
    s.add(k); s.flush()
    return k


def gecmis(s: Session, senaryo_id: int, kod: str) -> list[m.MalzemeFiyati]:
    mz = _malzeme(s, kod)
    q = (select(m.MalzemeFiyati).where(m.MalzemeFiyati.malzeme_id == mz.id, m.MalzemeFiyati.senaryo_id == senaryo_id)
         .order_by(m.MalzemeFiyati.gecerlilik_basi.desc(), m.MalzemeFiyati.id.desc()))
    return list(s.scalars(q))


def _gecerli_kayitlar(s: Session, senaryo_id: int, tarih: date) -> dict[int, m.MalzemeFiyati]:
    q = (select(m.MalzemeFiyati).where(m.MalzemeFiyati.senaryo_id == senaryo_id, m.MalzemeFiyati.gecerlilik_basi <= tarih)
         .order_by(m.MalzemeFiyati.gecerlilik_basi.desc(), m.MalzemeFiyati.id.desc()))
    son: dict[int, m.MalzemeFiyati] = {}
    for k in s.scalars(q):
        son.setdefault(k.malzeme_id, k)
    return son


def gecerli_kayitlar_kodla(s: Session, senaryo_id: int, tarih: date) -> dict[str, m.MalzemeFiyati]:
    """Geçerli fiyat kaydı (gecerlilik_basi, kaynak vb.) malzeme koduna göre; fiyat kaydı olmayan kod sözlükte yer almaz."""
    son = _gecerli_kayitlar(s, senaryo_id, tarih)
    return {kod: son[mid] for mid, kod in s.execute(select(m.Malzeme.id, m.Malzeme.kod)) if mid in son}


def _ilk_kayitlar(s: Session, senaryo_id: int) -> dict[int, m.MalzemeFiyati]:
    """Senaryodaki en eski kayıt (ilk bütçe): en küçük gecerlilik_basi, eşitlikte ilk eklenen. Tek sorgu."""
    q = (select(m.MalzemeFiyati).where(m.MalzemeFiyati.senaryo_id == senaryo_id)
         .order_by(m.MalzemeFiyati.gecerlilik_basi.asc(), m.MalzemeFiyati.id.asc()))
    ilk: dict[int, m.MalzemeFiyati] = {}
    for k in s.scalars(q):
        ilk.setdefault(k.malzeme_id, k)
    return ilk


def ilk_kayitlar_kodla(s: Session, senaryo_id: int) -> dict[str, m.MalzemeFiyati]:
    """İlk bütçe kaydı malzeme koduna göre; fiyat kaydı olmayan kod sözlükte yer almaz."""
    ilk = _ilk_kayitlar(s, senaryo_id)
    return {kod: ilk[mid] for mid, kod in s.execute(select(m.Malzeme.id, m.Malzeme.kod)) if mid in ilk}


def gecerli_fiyatlar(s: Session, senaryo_id: int, tarih: date) -> dict[str, MotorMalzeme]:
    son = _gecerli_kayitlar(s, senaryo_id, tarih)
    out = {}
    for mz in s.scalars(select(m.Malzeme)):
        f = son.get(mz.id)
        out[mz.kod] = MotorMalzeme(kod=mz.kod, ad=mz.ad, tip=mz.tip, birim=mz.birim,
                                   para_birimi=(f.para_birimi if f else mz.para_birimi), fiyat=(f.fiyat if f else SIFIR), zs=mz.zs)
    return out


def fiyatsizlar(s: Session, senaryo_id: int, tarih: date) -> list[str]:
    son = _gecerli_kayitlar(s, senaryo_id, tarih)
    return sorted(mz.kod for mz in s.scalars(select(m.Malzeme).where(m.Malzeme.aktif == True))
                  if mz.id not in son or son[mz.id].fiyat == SIFIR)
