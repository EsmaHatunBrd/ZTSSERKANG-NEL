"""SMM stok/envanter kalemlerinin elle düzenlenmesi: Excel'den gelen değerler ekranda değiştirilebilir, yeni kalem açılabilir.

Her değişiklik `DegisiklikKaydi(tablo="smm_kalem")` ile tutulur (eski/yeni alanlar, neden, kullanıcı); dönem başı, alım, iade, üretim,
sayım ve şahit alanları değişince sarf farkı, DSS değerlemesi ve SMM özeti hesaplanırken yeni değerler kullanılır (hepsi istek anında
hesaplanır). Excel'le karşılaştırma ekranlarda sürer: elle değişen kalem "elle" rozetiyle işaretlenir ki parite kontrolünde bilinçli sapma
görünsün. Şema dosyaları paylaşımlı olduğu için bu modül yalnız kendi ucunu (api/smm_stok.py) besler."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..depo import modeller as m
from .donusum import decimal_str
from .hatalar import BulunamadiHatasi, CatismaHatasi, DogrulamaHatasi, alan_adi, liste_metni
from .smm_servisi import _alim_toplami, donem_adi, donem_getir, kilit_denetle, stok_hesabi

METIN_ALANLAR = ("ad", "birim", "tur", "mizan_kodu")
SAYISAL_ALANLAR = ("dbs_miktar", "dbs_tutar", "alim_miktar", "alim_tutar", "iade_miktar", "iade_tutar", "uretim_miktar", "sayim_miktar",
                   "sahit_miktar")
DUZENLENEBILIR = METIN_ALANLAR + SAYISAL_ALANLAR
TABLO = "smm_kalem"


def _neden(neden: str | None) -> str:
    if not (neden or "").strip():
        raise DogrulamaHatasi("Neden girin.")
    return neden.strip()


def _sayi(alan: str, v) -> Decimal:
    try:
        d = Decimal(str(v).replace(",", ".").strip())
    except (InvalidOperation, ValueError):
        raise DogrulamaHatasi(f"{alan_adi(alan)} bir sayı olmalı.", {alan: str(v)})
    if d < 0:
        raise DogrulamaHatasi(f"{alan_adi(alan)} eksi olamaz.", {alan: str(v)})
    return d


def kalem_getir(s: Session, donem_id: int, kod: str) -> m.SmmKalem:
    k = s.scalar(select(m.SmmKalem).where(m.SmmKalem.donem_id == donem_id, m.SmmKalem.kod == kod))
    if k is None:
        raise BulunamadiHatasi(f"Bu dönemde {kod} stok kalemi bulunamadı.", {"donem_id": donem_id, "kod": kod})
    return k


def satir(s: Session, d: m.SmmDonem, k: m.SmmKalem) -> dict:
    """Stok tablosundaki satırla aynı biçim (ss.stok_tablosu) + `sahit_miktar`."""
    h = stok_hesabi(k, d.finansman, _alim_toplami(s, d.id))
    return decimal_str({"kod": k.kod, "ad": k.ad, "birim": k.birim, "tur": k.tur, "mizan_kodu": k.mizan_kodu,
                        "dbs_miktar": k.dbs_miktar, "dbs_tutar": k.dbs_tutar, "alim_miktar": k.alim_miktar, "alim_tutar": k.alim_tutar,
                        "iade_miktar": k.iade_miktar, "iade_tutar": k.iade_tutar, "uretim_miktar": k.uretim_miktar,
                        "sayim_miktar": k.sayim_miktar, "sahit_miktar": k.sahit_miktar, **h})


def kalem_guncelle(s: Session, donem_id: int, kod: str, alanlar: dict, neden: str | None, kullanici: str = "sistem") -> dict:
    """Verilen alanları yazar; değişen yoksa kayıt açmaz. Dönüş: güncel satır + `degisti` (alan adları)."""
    neden = _neden(neden)
    d = donem_getir(s, donem_id)
    kilit_denetle(d)   # kapanmış (kilitli) dönem değiştirilemez
    k = kalem_getir(s, donem_id, kod)
    bilinmeyen = sorted(set(alanlar) - set(DUZENLENEBILIR))
    if bilinmeyen:
        raise DogrulamaHatasi(f"Düzenlenemeyen alan: {liste_metni(bilinmeyen)}.", {"alanlar": bilinmeyen})
    eski, yeni = {}, {}
    for alan, v in alanlar.items():
        if v is None and alan in SAYISAL_ALANLAR and alan != "sahit_miktar":
            continue   # sayısal alan boş gönderilirse dokunulmaz (şahit null olabilir)
        deger = _sayi(alan, v) if alan in SAYISAL_ALANLAR and v is not None else (str(v).strip() or None if v is not None else None)
        mevcut = getattr(k, alan)
        if (mevcut if mevcut is not None else None) == deger:
            continue
        eski[alan] = str(mevcut) if mevcut is not None else None
        yeni[alan] = str(deger) if deger is not None else None
        setattr(k, alan, deger)
    if yeni:
        s.add(m.DegisiklikKaydi(tablo=TABLO, kayit_id=k.id, islem="guncelle", eski=eski,
                                yeni={**yeni, "_neden": neden, "_kod": k.kod, "_donem": donem_adi(d)}, kullanici=kullanici))
        s.flush()
    return {**satir(s, d, k), "degisti": sorted(yeni)}


def kalem_ekle(s: Session, donem_id: int, kod: str, ad: str | None, birim: str | None, tur: str | None, mizan_kodu: str | None,
               neden: str | None, kullanici: str = "sistem", **sayisal) -> dict:
    """Excel'de olmayan stok kalemi açar (miktar/tutarlar verilmezse 0). Kod dönemde varsa 409."""
    neden = _neden(neden)
    d = donem_getir(s, donem_id)
    kilit_denetle(d)   # kapanmış (kilitli) dönem değiştirilemez
    kod = (kod or "").strip()
    if not kod:
        raise DogrulamaHatasi("Kod girin.")
    if s.scalar(select(m.SmmKalem).where(m.SmmKalem.donem_id == donem_id, m.SmmKalem.kod == kod)) is not None:
        raise CatismaHatasi(f"{kod} kodu bu dönemde zaten var.", {"kod": kod})
    degerler = {a: _sayi(a, sayisal[a]) for a in SAYISAL_ALANLAR if sayisal.get(a) is not None}
    k = m.SmmKalem(donem_id=d.id, kod=kod, ad=(ad or "").strip() or None, birim=(birim or "").strip() or None, tur=(tur or "").strip() or None,
                   mizan_kodu=(mizan_kodu or "").strip() or None, envanterde=True, **degerler)
    s.add(k); s.flush()
    s.add(m.DegisiklikKaydi(tablo=TABLO, kayit_id=k.id, islem="ekle", eski=None,
                            yeni={"kod": kod, "ad": k.ad, "tur": k.tur, **{a: str(v) for a, v in degerler.items()}, "_neden": neden,
                                  "_kod": kod, "_donem": donem_adi(d)}, kullanici=kullanici))
    s.flush()
    return {**satir(s, d, k), "degisti": ["ekle"]}


def elle_degisenler(s: Session, donem_id: int) -> dict:
    """Dönemde elle değiştirilen/eklenen kalemler: kod → {alanlar, son zaman, kullanıcı, kayıt sayısı}."""
    donem_getir(s, donem_id)
    idler = {k.id: k.kod for k in s.scalars(select(m.SmmKalem).where(m.SmmKalem.donem_id == donem_id))}
    out: dict[str, dict] = {}
    if not idler:
        return {"kayitlar": out}
    q = (select(m.DegisiklikKaydi).where(m.DegisiklikKaydi.tablo == TABLO, m.DegisiklikKaydi.kayit_id.in_(idler))
         .order_by(m.DegisiklikKaydi.zaman.asc(), m.DegisiklikKaydi.id.asc()))
    for d in s.scalars(q):
        kod = idler[d.kayit_id]
        o = out.setdefault(kod, {"alanlar": [], "zaman": None, "kullanici": None, "kayit": 0})
        alanlar = [a for a in (d.yeni or {}) if not a.startswith("_")] if d.islem == "guncelle" else ["ekle"]
        o["alanlar"] = sorted(set(o["alanlar"]) | set(alanlar))
        o["zaman"] = d.zaman.isoformat() if d.zaman else None
        o["kullanici"] = d.kullanici
        o["kayit"] += 1
    return {"kayitlar": out}
