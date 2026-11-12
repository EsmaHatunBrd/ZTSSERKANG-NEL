"""Değişiklik Günlüğü: tüm denetim kaynaklarını tek, zamana göre tersten akışta birleştirir.

Kaynaklar: DegisiklikKaydi, ParametreDegeri, MalzemeFiyati, FireKurali, MetinParametre, Recete sürümleri, MaliyetHesabi, Teklif.
Yöntem: her kaynak tek (birkaç) sorguyla çekilir, ad/kod eşlemeleri toplu sorgudur (satır başına sorgu yok),
süzgeç + sıralama + sayfalama bellek içinde yapılır. Birkaç on bin satıra kadar yeterlidir; daha büyük veri için
kaynak başına SQL süzgeci/keyset sayfalama gerekir (bilinen sınır).
Salt okunur: hiçbir şey yazmaz."""
import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from io import BytesIO
from typing import Any
from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from ..depo import modeller as m
from .donusum import zaman_iso
from .hatalar import BulunamadiHatasi, DogrulamaHatasi

TURLER = ("parametre", "fiyat", "fire", "metin", "recete", "hesap", "teklif", "urun", "hedef", "havuz", "ambalaj", "kapasite", "satis", "diger")

_TABLO_TUR = {"urun": "urun", "uretim_hedefi": "hedef", "gider_havuzu": "havuz", "ambalaj_sinifi": "ambalaj", "uretim_kapasitesi": "kapasite",
              "satis_gecmisi": "satis", "recete": "recete", "teklif": "teklif"}
_TABLO_ETIKET = {"urun": "Ürün kartı", "uretim_hedefi": "Üretim hedefi", "gider_havuzu": "Gider havuzu", "ambalaj_sinifi": "Ambalaj sınıfları",
                 "uretim_kapasitesi": "Üretim kapasitesi", "satis_gecmisi": "Satış geçmişi", "malzeme": "Malzeme kartı", "recete": "Reçete",
                 "senaryo": "Senaryo", "teklif": "Teklif turu", "liste_fiyati": "Liste fiyatı", "smm_donem": "SMM dönemi",
                 "smm_recete": "SMM reçeteleri", "stok_devri": "Stokta kalan"}
_ISLEM_ETIKET = {"guncelle": "güncellendi", "olustur": "oluşturuldu", "ekle": "eklendi", "sil": "silindi", "pasiflestir": "pasifleştirildi",
                 "aile_degistir": "ailesi değişti", "kod_degistir": "kodu değişti", "toplu_yukle": "toplu yüklendi", "etkinlestir": "sürümü etkinleştirildi",
                 "kilitle": "kilitlendi", "kilit_ac": "kilidi açıldı", "kopyala": "kopyalanarak oluşturuldu",
                 "ornek_uret": "örnek verisi üretildi", "ornek_sil": "örnek verisi silindi",
                 "dagitim": "dağıtım havuzları değişti", "alternatif": "reçete alternatifi değişti",
                 "recete_kaynagi": "reçete kaynağı değişti", "satir_ekle": "reçete satırı eklendi",
                 "satir_guncelle": "reçete satırı değişti", "satir_sil": "reçete satırı silindi",
                 "alternatif_kopyala": "reçete alternatifi kopyalandı", "canias_don": "Canias reçetesine döndürüldü",
                 "asama": "aşaması değişti", "asama_elle": "aşama değeri elle girildi", "sure_ekle": "üretim süresi eklendi",
                 "sure_guncelle": "üretim süresi değişti", "sure_sil": "üretim süresi silindi",
                 "veri_yukle": "veri yüklendi", "kalem_guncelle": "stok kalemi düzeltildi", "ayar_guncelle": "finansman / gider tutarı değişti"}


@dataclass
class Suzgec:
    senaryo: int | None = None
    bas: date | None = None
    son: date | None = None
    kullanici: str | None = None
    tur: list[str] = field(default_factory=list)
    urun_kodu: str | None = None
    q: str | None = None


def _kisa(v: Any, sinir: int = 160) -> str:
    metin = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str)
    return metin if len(metin) <= sinir else metin[: sinir - 1] + "…"


def _tr_bicim(d: Decimal, basamak: int) -> str:
    """Decimal -> '1.234.567,89' (binlik nokta, ondalık virgül)."""
    return f"{d:,.{basamak}f}".replace(",", "\0").replace(".", ",").replace("\0", ".")


def _tutar_tr(v: Any) -> str:
    """Tutar: 2 ondalık ROUND_HALF_UP ('1755.1755' -> '1.755,18'). Sayı değilse olduğu gibi."""
    try:
        return _tr_bicim(Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), 2)
    except (InvalidOperation, ValueError, TypeError):
        return str(v)


def _carpan_tr(v: Any) -> str:
    """Çarpan: en az 2 ondalık, fazlası varsa korunur ('1.3' -> '1,30', '1.355' -> '1,355')."""
    try:
        d = Decimal(str(v)).normalize()
    except (InvalidOperation, ValueError, TypeError):
        return str(v)
    us = d.as_tuple().exponent
    return _tr_bicim(d, max(2, -us) if isinstance(us, int) else 2)


def _carpan_metni(c: Any) -> str:
    if not isinstance(c, dict):
        return str(c)
    deger = _carpan_tr(c.get("deger", "?"))
    return f"{deger} ({c['ad']})" if c.get("ad") else deger


def _havuz_gosterim(d: Any) -> Any:
    """Gider havuzu kaydı: taban/çarpanlar JSON'u yerine 'toplam_tutar: 1.000,10 × 1,35 (SGK) × 1,30 (zam) = 1.755,18' okunur metni.
    Toplam yoksa kayıt olduğu gibi kalır."""
    if not isinstance(d, dict) or d.get("toplam_tutar") is None:
        return d
    d = dict(d)
    taban, carpanlar, toplam = d.pop("taban_tutar", None), d.pop("carpanlar", None), d["toplam_tutar"]
    if taban is not None and carpanlar:
        d["toplam_tutar"] = " × ".join([_tutar_tr(taban), *map(_carpan_metni, carpanlar)]) + f" = {_tutar_tr(toplam)}"
    else:
        d["toplam_tutar"] = _tutar_tr(toplam)
    return d


HAVUZ_ALAN_SINIRI = 240   # taban × çarpanlar = toplam metni 60 karakteri kolayca aşar; kesilirse toplam kaybolur


def fark_metni(eski: Any, yeni: Any, alan_siniri: int = 60) -> tuple[str | None, str | None, str | None]:
    """DegisiklikKaydi.eski/yeni -> (eski_metin, yeni_metin, neden). Sözlüklerde yalnız değişen alanlar gösterilir (alan başına
    `alan_siniri` karakter); `_neden` ayrılır."""
    neden = None
    if isinstance(yeni, dict):
        neden = yeni.get("_neden")
        yeni = {k: v for k, v in yeni.items() if k != "_neden"}
        if set(yeni) == {"siniflar"}:
            yeni = yeni["siniflar"]
    if isinstance(eski, dict) and isinstance(yeni, dict):
        anahtarlar = [k for k in yeni if eski.get(k) != yeni[k]] or list(yeni)
        return ("; ".join(f"{k}: {_kisa(eski.get(k), alan_siniri)}" for k in anahtarlar), "; ".join(f"{k}: {_kisa(yeni[k], alan_siniri)}" for k in anahtarlar), neden)
    gos = lambda v: None if v is None else (_kisa(", ".join(f"{k}: {x}" for k, x in v.items())) if isinstance(v, dict) else _kisa(v))
    return gos(eski), gos(yeni), neden


def _gun_basi(d: date) -> datetime:
    """Kullanıcının (sunucunun) yerel takvim gününün başlangıcı, saklanan damgalarla aynı eksende (naif UTC).
    Önceden UTC gece yarısı alınıyordu; Türkiye'de 00:00-03:00 arası kayıtlar bir önceki güne düşüyordu."""
    return datetime.combine(d, time.min).astimezone().astimezone(timezone.utc).replace(tzinfo=None)


def _naif_utc(z: datetime | None) -> datetime:
    if z is None:
        return datetime.min
    return z.astimezone(timezone.utc).replace(tzinfo=None) if z.tzinfo else z


def _satir(kaynak: str, pk: int, zaman: datetime | None, kullanici: str | None, tur: str, baslik: str, **ek) -> dict:
    return {"id": f"{kaynak}:{pk}", "zaman": zaman_iso(zaman), "_z": _naif_utc(zaman), "_pk": pk, "kullanici": kullanici or "sistem", "tur": tur, "baslik": baslik,
            "urun_kodu": ek.get("urun_kodu"), "senaryo_id": ek.get("senaryo_id"), "eski": ek.get("eski"), "yeni": ek.get("yeni"), "neden": ek.get("neden"),
            "geri_alinabilir": False, "geri_al": None}


def _onceki_ile_eski(kayitlar: list, grup, deger) -> dict[int, Any]:
    """Aynı (grup) içinde id sırasına göre bir önceki kaydın değeri; ilk kayıt için yok (None, ve `ilk` işaretli)."""
    onceki: dict[tuple, Any] = {}
    out: dict[int, Any] = {}
    for k in sorted(kayitlar, key=lambda x: x.id):
        g = grup(k)
        out[k.id] = onceki.get(g)
        onceki[g] = k
    return out


def _bugun() -> str:
    return date.today().isoformat()


def _degisiklik_satirlari(s: Session, senaryo: int | None, urunler: dict[int, m.Urun]) -> list[dict]:
    kayitlar = list(s.scalars(select(m.DegisiklikKaydi)))
    if not kayitlar:
        return []
    hedef = {h.id: (h.urun_id, h.senaryo_id) for h in s.execute(select(m.UretimHedefi.id, m.UretimHedefi.urun_id, m.UretimHedefi.senaryo_id)).all()}
    havuz = dict(s.execute(select(m.GiderHavuzu.id, m.GiderHavuzu.senaryo_id)).all())
    kap = {k.id: (k.urun_kodu, k.senaryo_id) for k in s.execute(select(m.UretimKapasitesi.id, m.UretimKapasitesi.urun_kodu, m.UretimKapasitesi.senaryo_id)).all()}
    satis = dict(s.execute(select(m.SatisGecmisi.id, m.SatisGecmisi.urun_id)).all())
    recete = {r.id: (r.urun_id, r.senaryo_id) for r in s.execute(select(m.Recete.id, m.Recete.urun_id, m.Recete.senaryo_id)).all()}
    malzeme = dict(s.execute(select(m.Malzeme.id, m.Malzeme.kod)).all())
    out = []
    for k in kayitlar:
        urun_kodu, sen_id = None, None
        t = k.tablo
        if t == "urun":
            urun_kodu = urunler[k.kayit_id].kod if k.kayit_id in urunler else None
        elif t == "uretim_hedefi" and k.kayit_id in hedef:
            uid, sen_id = hedef[k.kayit_id]
            urun_kodu = urunler[uid].kod if uid in urunler else None
        elif t == "gider_havuzu":
            sen_id = havuz.get(k.kayit_id)
        elif t == "ambalaj_sinifi":
            sen_id = k.kayit_id
        elif t == "uretim_kapasitesi":
            urun_kodu, sen_id = kap.get(k.kayit_id, (None, None))
            if urun_kodu is None and isinstance(k.yeni, dict):
                urun_kodu = k.yeni.get("urun_kodu")
        elif t == "satis_gecmisi":
            if k.kayit_id in satis and satis[k.kayit_id] in urunler:
                urun_kodu = urunler[satis[k.kayit_id]].kod
            else:   # silinmiş kayıt: ürün kodu içerikte saklıdır
                veri = k.yeni if isinstance(k.yeni, dict) else k.eski
                urun_kodu = veri.get("urun_kodu") if isinstance(veri, dict) else None
        elif t == "recete" and k.kayit_id in recete:
            uid, sen_id = recete[k.kayit_id]
            urun_kodu = urunler[uid].kod if uid in urunler else None
        elif t == "malzeme":
            urun_kodu = None
        elif t == "senaryo":
            sen_id = k.kayit_id
        elif t == "liste_fiyati":
            veri = k.yeni if isinstance(k.yeni, dict) else k.eski
            urun_kodu = veri.get("urun_kodu") if isinstance(veri, dict) else None
        elif t == "stok_devri":   # ürün ve çalışma içerikte saklıdır (silinen kayıtta da)
            veri = k.yeni if isinstance(k.yeni, dict) and "urun_kodu" in k.yeni else k.eski
            if isinstance(veri, dict):
                urun_kodu, sen_id = veri.get("urun_kodu"), veri.get("senaryo_id")
        elif t == "teklif" and isinstance(k.eski, dict):   # silinmiş tur: ürün ve senaryo içerikte saklıdır
            urun_kodu, sen_id = k.eski.get("urun_kodu"), k.eski.get("senaryo_id")
        if senaryo is not None and sen_id is not None and sen_id != senaryo:
            continue   # senaryoya bağlı kayıt başka senaryoya aitse çıkar; senaryosuz (ürün/malzeme/satış) kayıtlar her senaryoda görünür
        if t == "gider_havuzu":
            eski, yeni, neden = fark_metni(_havuz_gosterim(k.eski), _havuz_gosterim(k.yeni), HAVUZ_ALAN_SINIRI)
        else:
            eski, yeni, neden = fark_metni(k.eski, k.yeni)
        baslik = f"{_TABLO_ETIKET.get(t, t)} {_ISLEM_ETIKET.get(k.islem, k.islem)}"
        if t == "malzeme" and malzeme.get(k.kayit_id):
            baslik += f" ({malzeme[k.kayit_id]})"
        out.append(_satir("degisiklik", k.id, k.zaman, k.kullanici, _TABLO_TUR.get(t, "diger"), baslik, urun_kodu=urun_kodu, senaryo_id=sen_id,
                          eski=eski, yeni=yeni, neden=neden))
    return out


def _parametre_satirlari(s: Session, senaryo: int | None, kilitli: dict[int, bool], gerceklesen: set[int]) -> list[dict]:
    q = select(m.ParametreDegeri, m.Parametre.anahtar).join(m.Parametre, m.Parametre.id == m.ParametreDegeri.parametre_id)
    if senaryo is not None:
        q = q.where(m.ParametreDegeri.senaryo_id == senaryo)
    sat = list(s.execute(q).all())
    son_id = {}
    for d, _ in sat:
        g = (d.senaryo_id, d.parametre_id, d.kapsam_tipi, d.kapsam_id)
        son_id[g] = max(son_id.get(g, 0), d.id)
    onceki = _onceki_ile_eski([d for d, _ in sat], lambda d: (d.senaryo_id, d.parametre_id, d.kapsam_tipi, d.kapsam_id), None)
    out = []
    for d, anahtar in sat:
        e = onceki[d.id]
        kapsam = "" if d.kapsam_tipi == "genel" else f" (ürün #{d.kapsam_id})"
        r = _satir("parametre", d.id, d.olusturma_zamani, d.olusturan, "parametre", f"Parametre: {anahtar}{kapsam}", senaryo_id=d.senaryo_id,
                   eski=None if e is None else str(e.deger), yeni=str(d.deger), neden=d.neden)
        r["anahtar"] = anahtar
        g = (d.senaryo_id, d.parametre_id, d.kapsam_tipi, d.kapsam_id)
        if e is not None and son_id[g] == d.id and not kilitli.get(d.senaryo_id) and not (anahtar == "enflasyon" and d.senaryo_id in gerceklesen):
            r["geri_alinabilir"] = True
            r["geri_al"] = {"yol": f"/api/v1/parametreler/{anahtar}/degerler?senaryo={d.senaryo_id}",
                            "govde": {"deger": str(e.deger), "gecerlilik_basi": _bugun(), "neden": f"Geri alındı (günlük #{d.id})",
                                      "kapsam_tipi": d.kapsam_tipi, "kapsam_id": d.kapsam_id}}
        out.append(r)
    return out


def _fiyat_satirlari(s: Session, senaryo: int | None, kilitli: dict[int, bool]) -> list[dict]:
    q = select(m.MalzemeFiyati, m.Malzeme.kod).join(m.Malzeme, m.Malzeme.id == m.MalzemeFiyati.malzeme_id)
    if senaryo is not None:
        q = q.where(m.MalzemeFiyati.senaryo_id == senaryo)
    sat = list(s.execute(q).all())
    grup = lambda f: (f.senaryo_id, f.malzeme_id)
    onceki = _onceki_ile_eski([f for f, _ in sat], grup, None)
    son_id: dict[tuple, int] = {}
    for f, _ in sat:
        son_id[grup(f)] = max(son_id.get(grup(f), 0), f.id)
    out = []
    for f, kod in sat:
        e = onceki[f.id]
        r = _satir("fiyat", f.id, f.olusturma_zamani, f.olusturan, "fiyat", f"Malzeme fiyatı: {kod}", senaryo_id=f.senaryo_id,
                   eski=None if e is None else str(e.fiyat), yeni=str(f.fiyat), neden=f.neden)
        r["kod"] = kod
        if e is not None and son_id[grup(f)] == f.id and not kilitli.get(f.senaryo_id):
            r["geri_alinabilir"] = True
            r["geri_al"] = {"yol": f"/api/v1/malzemeler/{kod}/fiyatlar?senaryo={f.senaryo_id}",
                            "govde": {"fiyat": str(e.fiyat), "gecerlilik_basi": _bugun(), "neden": f"Geri alındı (günlük #{f.id})", "para_birimi": e.para_birimi}}
        out.append(r)
    return out


def _fire_satirlari(s: Session, senaryo: int | None, kilitli: dict[int, bool]) -> list[dict]:
    q = select(m.FireKurali)
    if senaryo is not None:
        q = q.where(m.FireKurali.senaryo_id == senaryo)
    sat = list(s.scalars(q))
    grup = lambda f: (f.senaryo_id, f.kapsam_tipi, f.kapsam_deger)
    onceki = _onceki_ile_eski(sat, grup, None)
    son_id: dict[tuple, int] = {}
    for f in sat:
        son_id[grup(f)] = max(son_id.get(grup(f), 0), f.id)
    out = []
    for f in sat:
        e = onceki[f.id]
        r = _satir("fire", f.id, f.olusturma_zamani, f.olusturan, "fire", f"Fire kuralı: {f.kapsam_tipi} {f.kapsam_deger}", senaryo_id=f.senaryo_id,
                   eski=None if e is None else str(e.oran), yeni=str(f.oran), neden=f.neden)
        if e is not None and son_id[grup(f)] == f.id and not kilitli.get(f.senaryo_id):
            r["geri_alinabilir"] = True
            r["geri_al"] = {"yol": f"/api/v1/fire-kurallari?senaryo={f.senaryo_id}",
                            "govde": {"kapsam_tipi": f.kapsam_tipi, "kapsam_deger": f.kapsam_deger, "oran": str(e.oran), "gecerlilik_basi": _bugun(),
                                      "neden": f"Geri alındı (günlük #{f.id})"}}
        out.append(r)
    return out


def _metin_satirlari(s: Session, senaryo: int | None) -> list[dict]:
    q = select(m.MetinParametre)
    if senaryo is not None:
        q = q.where(m.MetinParametre.senaryo_id == senaryo)
    sat = list(s.scalars(q))
    onceki = _onceki_ile_eski(sat, lambda k: (k.senaryo_id, k.anahtar), None)
    return [_satir("metin", k.id, k.olusturma_zamani, k.olusturan, "metin", f"Metin parametresi: {k.anahtar}", senaryo_id=k.senaryo_id,
                   eski=None if onceki[k.id] is None else _kisa(onceki[k.id].deger), yeni=_kisa(k.deger), neden=k.neden) for k in sat]


def _recete_satirlari(s: Session, senaryo: int | None, urunler: dict[int, m.Urun], kilitli: dict[int, bool]) -> list[dict]:
    q = select(m.Recete)
    if senaryo is not None:
        q = q.where(m.Recete.senaryo_id == senaryo)
    sat = list(s.scalars(q))
    adet = dict(s.execute(select(m.ReceteSatiri.recete_id, func.count()).group_by(m.ReceteSatiri.recete_id)).all())
    grup = lambda r: (r.urun_id, r.senaryo_id)
    onceki = _onceki_ile_eski(sat, grup, None)   # id sırası = sürüm sırası
    out = []
    for r in sat:
        urun_kodu = urunler[r.urun_id].kod if r.urun_id in urunler else None
        e = onceki[r.id]
        satir = _satir("recete", r.id, r.olusturma_zamani, r.olusturan, "recete",
                       f"Reçete sürümü v{r.versiyon} ({r.kaynak or 'bilinmiyor'}, {adet.get(r.id, 0)} satır){'' if r.aktif else ' - pasif'}",
                       urun_kodu=urun_kodu, senaryo_id=r.senaryo_id, eski=None if e is None else f"v{e.versiyon}", yeni=f"v{r.versiyon}")
        if r.aktif and e is not None and urun_kodu and not kilitli.get(r.senaryo_id):
            satir["geri_alinabilir"] = True
            satir["geri_al"] = {"yol": f"/api/v1/urunler/{urun_kodu}/recete/{e.versiyon}/etkinlestir?senaryo={r.senaryo_id}",
                                "govde": {"neden": f"Geri alındı: v{r.versiyon} yerine v{e.versiyon} (günlük #{r.id})"}}
        out.append(satir)
    return out


def _hesap_satirlari(s: Session, senaryo: int | None, urunler: dict[int, m.Urun]) -> list[dict]:
    q = select(m.MaliyetHesabi)
    if senaryo is not None:
        q = q.where(m.MaliyetHesabi.senaryo_id == senaryo)
    out = []
    for h in s.scalars(q):
        sn = h.sonuc_snapshot or {}
        u = urunler.get(h.urun_id)
        yeni = f"maliyet {sn['finansman_dahil_maliyet_tl']} TL" if sn.get("finansman_dahil_maliyet_tl") is not None else None
        out.append(_satir("hesap", h.id, h.olusturma_zamani, h.olusturan, "hesap", f"Hesap kaydedildi ({h.hesap_tarihi.isoformat()})",
                          urun_kodu=u.kod if u else None, senaryo_id=h.senaryo_id, yeni=yeni, neden=(h.girdi_snapshot or {}).get("neden")))
    return out


def _teklif_satirlari(s: Session, senaryo: int | None, urunler: dict[int, m.Urun]) -> list[dict]:
    q = select(m.Teklif, m.MaliyetHesabi.urun_id, m.MaliyetHesabi.senaryo_id).join(m.MaliyetHesabi, m.MaliyetHesabi.id == m.Teklif.maliyet_hesabi_id)
    if senaryo is not None:
        q = q.where(m.MaliyetHesabi.senaryo_id == senaryo)
    out = []
    for t, urun_id, sen_id in s.execute(q).all():
        u = urunler.get(urun_id)
        musteri = f" - {t.musteri}" if t.musteri else ""
        out.append(_satir("teklif", t.id, t.olusturma_zamani, t.olusturan, "teklif", f"Teklif turu {t.tur_no} ({t.durum}){musteri}",
                          urun_kodu=u.kod if u else None, senaryo_id=sen_id, yeni=f"{t.fiyat_tl} TL (kâr {t.kar_orani})", neden=t.notu))
    return out


def _tum_satirlar(s: Session, senaryo: int | None) -> list[dict]:
    urunler = {u.id: u for u in s.scalars(select(m.Urun))}
    sen_durum = {x.id: (x.kilitli, x.tur) for x in s.execute(select(m.Senaryo.id, m.Senaryo.kilitli, m.Senaryo.tur)).all()}
    kilitli = {i: bool(k) for i, (k, _) in sen_durum.items()}
    gerceklesen = {i for i, (_, t) in sen_durum.items() if t == "gerceklesen"}
    return (_degisiklik_satirlari(s, senaryo, urunler) + _parametre_satirlari(s, senaryo, kilitli, gerceklesen) + _fiyat_satirlari(s, senaryo, kilitli)
            + _fire_satirlari(s, senaryo, kilitli) + _metin_satirlari(s, senaryo) + _recete_satirlari(s, senaryo, urunler, kilitli)
            + _hesap_satirlari(s, senaryo, urunler) + _teklif_satirlari(s, senaryo, urunler))


def _suz(satirlar: list[dict], f: Suzgec) -> list[dict]:
    bas = _gun_basi(f.bas) if f.bas else None
    son = _gun_basi(f.son + timedelta(days=1)) if f.son else None
    turler = set(f.tur)
    kul = (f.kullanici or "").strip().casefold()
    kod = (f.urun_kodu or "").strip().casefold()
    q = (f.q or "").strip().casefold()
    out = []
    for r in satirlar:
        if bas and r["_z"] < bas or son and r["_z"] >= son:
            continue
        if turler and r["tur"] not in turler:
            continue
        if kul and (r["kullanici"] or "").casefold() != kul:
            continue
        if kod and kod not in (r["urun_kodu"] or "").casefold():
            continue
        if q and q not in " ".join(str(r.get(a) or "") for a in ("baslik", "kullanici", "urun_kodu", "eski", "yeni", "neden", "anahtar", "kod")).casefold():
            continue
        out.append(r)
    out.sort(key=lambda r: (r["_z"], r["_pk"]), reverse=True)   # aynı saniyedeki kayıtlar: kimlik sırası (yeni önce)
    return out


def _temiz(r: dict) -> dict:
    return {k: v for k, v in r.items() if k not in ("_z", "_pk", "anahtar", "kod")}


def _dogrula(f: Suzgec) -> None:
    kotu = [t for t in f.tur if t not in TURLER]
    if kotu:
        raise DogrulamaHatasi("bilinmeyen tür", {"tur": kotu, "izinli": list(TURLER)})
    if f.bas and f.son and f.bas > f.son:
        raise DogrulamaHatasi("bas, son tarihinden sonra olamaz", {"bas": f.bas.isoformat(), "son": f.son.isoformat()})


def senaryo_denetle(s: Session, senaryo: int | None) -> None:
    if senaryo is not None and s.get(m.Senaryo, senaryo) is None:
        raise BulunamadiHatasi("senaryo yok", {"senaryo_id": senaryo})


def liste(s: Session, f: Suzgec, sayfa: int = 1, boyut: int = 50) -> tuple[list[dict], int]:
    _dogrula(f)
    senaryo_denetle(s, f.senaryo)
    uygun = _suz(_tum_satirlar(s, f.senaryo), f)
    bas = (sayfa - 1) * boyut
    return [_temiz(r) for r in uygun[bas:bas + boyut]], len(uygun)


def ozet(s: Session, senaryo: int | None, gun: int = 7) -> dict:
    senaryo_denetle(s, senaryo)
    f = Suzgec(senaryo=senaryo, bas=date.today() - timedelta(days=gun - 1))
    uygun = _suz(_tum_satirlar(s, senaryo), f)
    kul = Counter(r["kullanici"] for r in uygun)
    tur = Counter(r["tur"] for r in uygun)
    return {"gun": gun, "toplam": len(uygun),
            "kullanici_bazinda": [{"kullanici": k, "adet": n} for k, n in sorted(kul.items(), key=lambda x: (-x[1], x[0]))],
            "tur_bazinda": [{"tur": k, "adet": n} for k, n in sorted(tur.items(), key=lambda x: (-x[1], x[0]))]}


XLSX_BASLIK = ["Zaman", "Kullanıcı", "Tür", "Başlık", "Ürün kodu", "Senaryo", "Eski", "Yeni", "Neden"]


def xlsx(s: Session, f: Suzgec) -> BytesIO:
    _dogrula(f)
    senaryo_denetle(s, f.senaryo)
    wb = Workbook()
    ws = wb.active
    ws.title = "Değişiklik Günlüğü"
    ws.append(XLSX_BASLIK)
    for r in _suz(_tum_satirlar(s, f.senaryo), f):
        ws.append([r["zaman"], r["kullanici"], r["tur"], r["baslik"], r["urun_kodu"], r["senaryo_id"], r["eski"], r["yeni"], r["neden"]])
    for sutun, genislik in zip("ABCDEFGHI", (26, 14, 12, 44, 16, 10, 30, 30, 36)):
        ws.column_dimensions[sutun].width = genislik
    ws.freeze_panes = "A2"
    tampon = BytesIO()
    wb.save(tampon)
    tampon.seek(0)
    return tampon


# ---------------------------------------------------------------- reçete sürümü etkinleştirme (geri al ucu)
def recete_etkinlestir(s: Session, urun_kodu: str, senaryo_id: int, versiyon: int, neden: str, kullanici: str = "sistem") -> m.Recete:
    """Seçilen eski sürümü aktif yapar (satırlar silinmez, sürüm numarası artmaz); DegisiklikKaydi yazar."""
    if not (neden or "").strip():
        raise DogrulamaHatasi("neden zorunlu")
    u = s.scalar(select(m.Urun).where(m.Urun.kod == urun_kodu))
    if u is None:
        raise BulunamadiHatasi(f"ürün yok: {urun_kodu}", {"kod": urun_kodu})
    r = s.scalar(select(m.Recete).where(m.Recete.urun_id == u.id, m.Recete.senaryo_id == senaryo_id, m.Recete.versiyon == versiyon))
    if r is None:
        raise BulunamadiHatasi("reçete sürümü yok", {"versiyon": versiyon})
    if not r.aktif:
        eski = s.scalar(select(m.Recete).where(m.Recete.urun_id == u.id, m.Recete.senaryo_id == senaryo_id, m.Recete.aktif == True))
        for x in s.scalars(select(m.Recete).where(m.Recete.urun_id == u.id, m.Recete.senaryo_id == senaryo_id, m.Recete.aktif == True)):
            x.aktif = False
        r.aktif = True
        s.add(m.DegisiklikKaydi(tablo="recete", kayit_id=r.id, islem="etkinlestir", kullanici=kullanici,
                                eski={"aktif_versiyon": eski.versiyon if eski else None}, yeni={"aktif_versiyon": versiyon, "_neden": neden}))
        s.flush()
    return r
