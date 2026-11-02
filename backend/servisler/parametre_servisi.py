"""Append-only parametre değerleri. Geçerli değer = gecerlilik_basi <= tarih olan en yeni kayıt; ürün override geneli ezer."""
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from fiyat_motoru.modeller import Parametreler
from ..depo import modeller as m
from .hatalar import PARAMETRE_EKSIK, DogrulamaHatasi

ZORUNLU = ("enflasyon", "satis_kar", "vardiya_saati")


def _parametre(s: Session, anahtar: str) -> m.Parametre:
    p = s.scalar(select(m.Parametre).where(m.Parametre.anahtar == anahtar))
    if p is None:
        raise DogrulamaHatasi(f"bilinmeyen parametre: {anahtar}", {"anahtar": anahtar})
    return p


def tanimlar(s: Session) -> list[m.Parametre]:
    return list(s.scalars(select(m.Parametre).order_by(m.Parametre.id)))


def deger_ekle(s: Session, senaryo_id: int, anahtar: str, deger: Decimal, gecerlilik_basi: date, neden: str,
               kapsam_tipi: str = "genel", kapsam_id: int | None = None, olusturan: str = "sistem") -> m.ParametreDegeri:
    if kapsam_tipi not in ("genel", "urun") or (kapsam_tipi == "urun" and kapsam_id is None):
        raise DogrulamaHatasi("kapsam geçersiz", {"kapsam_tipi": kapsam_tipi})
    kayit = m.ParametreDegeri(parametre_id=_parametre(s, anahtar).id, senaryo_id=senaryo_id, kapsam_tipi=kapsam_tipi,
                              kapsam_id=kapsam_id, deger=Decimal(deger), gecerlilik_basi=gecerlilik_basi, neden=neden, olusturan=olusturan)
    s.add(kayit); s.flush()
    return kayit


def gecmis(s: Session, senaryo_id: int, anahtar: str) -> list[m.ParametreDegeri]:
    q = (select(m.ParametreDegeri).join(m.Parametre).where(m.Parametre.anahtar == anahtar, m.ParametreDegeri.senaryo_id == senaryo_id)
         .order_by(m.ParametreDegeri.gecerlilik_basi.desc(), m.ParametreDegeri.id.desc()))
    return list(s.scalars(q))


ParametreSatirlari = list[tuple[str, str, int | None, Decimal]]   # (anahtar, kapsam_tipi, kapsam_id, deger) — geçerlilik sırasına göre (en yeni önce)


def parametre_satirlari(s: Session, senaryo_id: int, tarih: date) -> ParametreSatirlari:
    """Senaryoda tarihte geçerli olabilecek tüm parametre kayıtları, tek sorgu. toplu_hesapla bunu bir kez çeker; ürün başına
    `degerleri_coz` ile çözülür (eskiden 67 ürün × aynı sorgu)."""
    q = (select(m.ParametreDegeri, m.Parametre.anahtar).join(m.Parametre)
         .where(m.ParametreDegeri.senaryo_id == senaryo_id, m.ParametreDegeri.gecerlilik_basi <= tarih)
         .order_by(m.ParametreDegeri.gecerlilik_basi.desc(), m.ParametreDegeri.id.desc()))
    return [(anahtar, kayit.kapsam_tipi, kayit.kapsam_id, kayit.deger) for kayit, anahtar in s.execute(q)]


def degerleri_coz(satirlar: ParametreSatirlari, urun_id: int | None = None) -> dict[str, Decimal]:
    """Genel kapsam + (verilmişse) ürün kapsamı; her anahtar için en yeni kayıt; ürün kapsamı geneli ezer."""
    genel: dict[str, Decimal] = {}
    urun: dict[str, Decimal] = {}
    for anahtar, kapsam_tipi, kapsam_id, deger in satirlar:
        if kapsam_tipi == "urun":
            if urun_id is not None and kapsam_id == urun_id:
                urun.setdefault(anahtar, deger)
        else:
            genel.setdefault(anahtar, deger)
    return {**genel, **urun}


def gecerli_degerler(s: Session, senaryo_id: int, tarih: date, urun_id: int | None = None) -> dict[str, Decimal]:
    return degerleri_coz(parametre_satirlari(s, senaryo_id, tarih), urun_id)


def _grup(d: dict[str, Decimal], onek: str) -> dict[str, Decimal]:
    return {k[len(onek):]: v for k, v in d.items() if k.startswith(onek)}


def gecerli_parametreler(s: Session, senaryo_id: int, tarih: date, urun_id: int | None = None,
                         satirlar: ParametreSatirlari | None = None) -> Parametreler:
    """`satirlar` verilmişse (toplu hesap önbelleği) sorgu yinelenmez."""
    d = degerleri_coz(satirlar, urun_id) if satirlar is not None else gecerli_degerler(s, senaryo_id, tarih, urun_id)
    eksik = [z for z in ZORUNLU if z not in d]
    if eksik:
        raise DogrulamaHatasi("zorunlu parametre eksik", {"eksik": eksik}, kod=PARAMETRE_EKSIK)
    teklif = _grup(d, "teklif_kar.")
    return Parametreler(
        enflasyon=d["enflasyon"], kurlar=_grup(d, "kur."), faiz_oranlari=_grup(d, "faiz."), stok_sureleri_ay=_grup(d, "stok_ay."),
        satis_kar_orani=d["satis_kar"], teklif_kar_oranlari=tuple(teklif[k] for k in sorted(teklif, key=int)),
        vardiya_saati=d["vardiya_saati"])


METIN_ANAHTARLARI = ("satis_fiyati_notu",)


def metin_deger_ekle(s: Session, senaryo_id: int, anahtar: str, deger: str, gecerlilik_basi: date, neden: str, olusturan: str = "sistem") -> m.MetinParametre:
    if anahtar not in METIN_ANAHTARLARI:
        raise DogrulamaHatasi(f"bilinmeyen metin parametresi: {anahtar}", {"anahtar": anahtar})
    if not (neden or "").strip():
        raise DogrulamaHatasi("neden zorunlu")
    k = m.MetinParametre(senaryo_id=senaryo_id, anahtar=anahtar, deger=deger, gecerlilik_basi=gecerlilik_basi, neden=neden, olusturan=olusturan)
    s.add(k); s.flush()
    return k


def _metin_sirali(s: Session, senaryo_id: int):
    return (select(m.MetinParametre).where(m.MetinParametre.senaryo_id == senaryo_id)
            .order_by(m.MetinParametre.gecerlilik_basi.desc(), m.MetinParametre.id.desc()))


def metin_gecmis(s: Session, senaryo_id: int, anahtar: str | None = None) -> list[m.MetinParametre]:
    q = _metin_sirali(s, senaryo_id)
    if anahtar is not None:
        q = q.where(m.MetinParametre.anahtar == anahtar)
    return list(s.scalars(q))


def metin_gecerli(s: Session, senaryo_id: int, tarih: date) -> list[m.MetinParametre]:
    """Her anahtar için tarihte geçerli (gecerlilik_basi <= tarih, en yeni) kayıt; anahtar sırasına göre."""
    gorulen: dict[str, m.MetinParametre] = {}
    for k in s.scalars(_metin_sirali(s, senaryo_id).where(m.MetinParametre.gecerlilik_basi <= tarih)):
        gorulen.setdefault(k.anahtar, k)
    return [gorulen[a] for a in sorted(gorulen)]
