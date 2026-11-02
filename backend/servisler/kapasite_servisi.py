"""Üretim kapasitesi (Excel `Üretim Adetleri`): senaryo + ürün kodu başına bir kayıt; değişiklikler DegisiklikKaydi'na yazılır."""
from decimal import Decimal
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from ..depo import modeller as m
from .donusum import decimal_str
from .hatalar import DogrulamaHatasi

SAYISAL_ALANLAR = ("net_kapasite", "net_sure", "toplam_kapasite", "toplam_sure", "hedef_uretim", "ortalama_isci")


def listele(s: Session, senaryo_id: int, sayfa: int = 1, boyut: int = 50) -> tuple[list[m.UretimKapasitesi], int]:
    q = select(m.UretimKapasitesi).where(m.UretimKapasitesi.senaryo_id == senaryo_id)
    toplam = s.scalar(select(func.count()).select_from(q.subquery())) or 0
    return list(s.scalars(q.order_by(m.UretimKapasitesi.id).offset((sayfa - 1) * boyut).limit(boyut))), toplam


def kaydet(s: Session, senaryo_id: int, urun_kodu: str, alanlar: dict[str, Decimal], neden: str, urun_ad: str | None = None,
           kullanici: str = "sistem") -> m.UretimKapasitesi:
    if not (neden or "").strip():
        raise DogrulamaHatasi("neden zorunlu")
    eksik = [a for a in SAYISAL_ALANLAR if a not in alanlar]
    if eksik:
        raise DogrulamaHatasi("kapasite alanı eksik", {"eksik": eksik})
    yeni = {a: alanlar[a] for a in SAYISAL_ALANLAR}
    k = s.scalar(select(m.UretimKapasitesi).where(m.UretimKapasitesi.senaryo_id == senaryo_id, m.UretimKapasitesi.urun_kodu == urun_kodu))
    if k is None:
        k = m.UretimKapasitesi(senaryo_id=senaryo_id, urun_kodu=urun_kodu, urun_ad=urun_ad or urun_kodu, olusturan=kullanici, **yeni)
        s.add(k); s.flush()
        s.add(m.DegisiklikKaydi(tablo="uretim_kapasitesi", kayit_id=k.id, islem="olustur", eski=None,
                                yeni={**decimal_str(yeni), "urun_kodu": urun_kodu, "_neden": neden}, kullanici=kullanici))
        s.flush()
        return k
    eski = {a: getattr(k, a) for a in SAYISAL_ALANLAR}
    ad_degisti = urun_ad is not None and urun_ad != k.urun_ad
    if eski != yeni or ad_degisti:
        eski_k, yeni_k = decimal_str(eski), decimal_str(yeni)
        if ad_degisti:
            eski_k["urun_ad"], yeni_k["urun_ad"] = k.urun_ad, urun_ad
            k.urun_ad = urun_ad
        for a, v in yeni.items():
            setattr(k, a, v)
        s.add(m.DegisiklikKaydi(tablo="uretim_kapasitesi", kayit_id=k.id, islem="guncelle", eski=eski_k, yeni={**yeni_k, "_neden": neden}, kullanici=kullanici))
        s.flush()
    return k


def importla(s: Session, senaryo_id: int, satirlar: list[dict], kullanici: str = "sistem") -> tuple[int, list[str]]:
    """Excel satırlarını yazar; tekrarlayan kodda ilk satır korunur, tekrarlar uyarı olarak döner."""
    gorulen: set[str] = set()
    uyarilar: list[str] = []
    for r in satirlar:
        kod = r["urun_kodu"]
        if kod in gorulen:
            uyarilar.append(f"Üretim Adetleri: ürün kodu {kod} birden fazla satırda; ilk satır korundu")
            continue
        gorulen.add(kod)
        s.add(m.UretimKapasitesi(senaryo_id=senaryo_id, urun_kodu=kod, urun_ad=r["urun_ad"], olusturan=kullanici,
                                 **{a: r[a] for a in SAYISAL_ALANLAR}))
    s.flush()
    return len(gorulen), uyarilar
