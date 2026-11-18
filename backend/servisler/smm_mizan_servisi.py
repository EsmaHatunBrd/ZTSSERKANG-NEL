"""SMM mizan satırlarının elle girişi: gider mizanı (720 / 730 ve diğer 7xx) ve stok mizanı (150 / 151 / 152) satırları ekranda
listelenir, eklenir, düzeltilir, silinir.

Veri modeli değişmez (yeni tablo/kolon yok): satırlar Excel yüklemesinin yazdığı yerde, `SmmDonem.excel_ozet` içinde durur:
    gider -> excel_ozet["gider_mizan"] = {hesap: bakiye}   (hesap adı elle verilirse excel_ozet["gider_mizan_ad"][hesap])
    stok  -> excel_ozet["stok_mizan"]  = [{hesap, ad, bakiye}]
Mizanda tek tutar tutulur: bakiye (borç bakiyesi artı, alacak bakiyesi eksi). Elle girilen/değişen satırların hesap kodları
excel_ozet["mizan_elle"][tur] listesinde işaretlenir. 720 / 730 değişince aşama hesabının okuduğu `SmmDonem.gider_mizan` da eşitlenir.
SMM özeti, SMM tablosu ve fiş istek anında hesaplandığı için değişiklik hemen yansır.

Excel yeniden yüklenince o mizan baştan yazılır, elle satırlar ve işaretleri silinir (bkz. smm_veri_servisi.kaynak_yukle); `veri_durumu`
yüklemeden önce "N elle satır var" uyarısını döner. Her değişiklik `DegisiklikKaydi(tablo="smm_mizan", kayit_id=dönem)` ile tutulur
(neden zorunlu; silinen satırın eski değeri kayıtta kalır)."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from ..depo import modeller as m
from .donusum import decimal_str
from .hatalar import BulunamadiHatasi, CatismaHatasi, DogrulamaHatasi
from .smm_servisi import SIFIR, _d, donem_adi, donem_cikis, donem_getir, kilit_denetle

TABLO = "smm_mizan"
TURLER = {"gider": "gider_mizan", "stok": "stok_mizan"}   # uçtaki tür -> veri kaynağı / excel_ozet anahtarı
TUR_ADI = {"gider": "Gider mizanı (720 / 730)", "stok": "Stok mizanı (150 / 151 / 152)"}
ASAMA_HESAPLARI = ("720", "730")   # SmmDonem.gider_mizan'da da tutulan hesaplar
# Tekdüzen Hesap Planı adları (elle ad verilmemiş gider satırlarında gösterilir)
GIDER_ADI = {"710": "Direkt İlk Madde ve Malzeme Giderleri", "711": "Direkt İlk Madde ve Malzeme Yansıtma",
             "720": "Direkt İşçilik Giderleri", "721": "Direkt İşçilik Giderleri Yansıtma",
             "730": "Genel Üretim Giderleri", "731": "Genel Üretim Giderleri Yansıtma"}


def _tur(tur: str) -> str:
    if tur not in TURLER:
        raise DogrulamaHatasi("Mizan türü gider ya da stok olmalı.", {"tur": tur})
    return tur


def _neden(neden: str | None) -> str:
    if not (neden or "").strip():
        raise DogrulamaHatasi("Neden girin.")
    return neden.strip()


def _tutar(v) -> Decimal:
    try:
        d = Decimal(str(v).replace(",", ".").strip())
    except (InvalidOperation, ValueError):
        raise DogrulamaHatasi("Bakiye bir sayı olmalı.", {"bakiye": str(v)})
    if not d.is_finite():
        raise DogrulamaHatasi("Bakiye bir sayı olmalı.", {"bakiye": str(v)})
    return d


def _hesap(tur: str, hesap: str | None) -> str:
    h = (hesap or "").strip()
    if not h:
        raise DogrulamaHatasi("Hesap kodu girin.")
    if tur == "gider" and not (len(h) == 3 and h.isdigit() and h[0] == "7"):
        raise DogrulamaHatasi("Gider mizanında hesap kodu 7 ile başlayan 3 haneli ana hesap olmalı (ör. 720, 730).", {"hesap": h})
    if tur == "stok" and not (h[:2] == "15" and h[:3].isdigit()):
        raise DogrulamaHatasi("Stok mizanında hesap kodu 15 ile başlamalı (ör. 150, 151.04.002).", {"hesap": h})
    return h


def _bakiye_denetle(tur: str, hesap: str, bakiye: Decimal) -> None:
    if tur == "gider" and hesap in ASAMA_HESAPLARI and bakiye < 0:
        raise DogrulamaHatasi(f"{hesap} gider tutarı eksi olamaz.", {"bakiye": str(bakiye)})


def satirlar(d: m.SmmDonem, tur: str, isaretsiz: bool = False) -> list[dict]:
    """Mizan satırları: {hesap, ad, bakiye (Decimal), elle}. Gider hesap koduna göre sıralı, stok kayıt sırasıyla."""
    ozet = d.excel_ozet or {}
    elle = set() if isaretsiz else set((ozet.get("mizan_elle") or {}).get(tur) or [])
    if tur == "gider":
        adlar = ozet.get("gider_mizan_ad") or {}
        gm = ozet.get("gider_mizan") or d.gider_mizan or {}
        return [{"hesap": h, "ad": adlar.get(h) or GIDER_ADI.get(h), "bakiye": _d(v), "elle": h in elle} for h, v in sorted(gm.items())]
    return [{"hesap": x["hesap"], "ad": x.get("ad"), "bakiye": _d(x.get("bakiye")), "elle": x["hesap"] in elle}
            for x in ozet.get("stok_mizan") or []]


def elle_hesaplar(d: m.SmmDonem, tur: str) -> list[str]:
    """Elle girilmiş/değiştirilmiş ve hâlâ mizanda duran hesap kodları."""
    isaretli = ((d.excel_ozet or {}).get("mizan_elle") or {}).get(tur) or []
    mevcut = {x["hesap"] for x in satirlar(d, tur, isaretsiz=True)}
    return [h for h in isaretli if h in mevcut]


def elle_sayisi(d: m.SmmDonem, kaynak: str) -> int:
    """Veri kaynağı (gider_mizan / stok_mizan) için elle satır sayısı; mizan olmayan kaynakta 0."""
    tur = next((t for t, k in TURLER.items() if k == kaynak), None)
    return len(elle_hesaplar(d, tur)) if tur else 0


def elle_uyarisi(n: int) -> str | None:
    return f"{n} elle satır var, yükleme bunları siler" if n else None


def _cikis(d: m.SmmDonem, tur: str) -> dict:
    kayitlar = satirlar(d, tur)
    n = len(elle_hesaplar(d, tur))
    return decimal_str({"donem": donem_cikis(d), "tur": tur, "ad": TUR_ADI[tur], "kayitlar": kayitlar,
                        "toplam": sum((x["bakiye"] for x in kayitlar), SIFIR), "elle": n, "elle_uyari": elle_uyarisi(n)})


def liste(s: Session, donem_id: int, tur: str) -> dict:
    return _cikis(donem_getir(s, donem_id), _tur(tur))


def _yaz(d: m.SmmDonem, tur: str, yeni: list[dict], elle: list[str]) -> None:
    """Satırları excel_ozet'e geri yazar (yeni nesnelerle: JSON kolonu değişikliği görsün) ve 720 / 730'u dönemle eşitler."""
    ozet = dict(d.excel_ozet or {})
    mevcut = {x["hesap"] for x in yeni}
    isaret = dict(ozet.get("mizan_elle") or {})
    isaret[tur] = sorted({h for h in elle if h in mevcut})
    ozet["mizan_elle"] = isaret
    if tur == "gider":
        ozet["gider_mizan"] = {x["hesap"]: str(x["bakiye"]) for x in yeni}
        ozet["gider_mizan_ad"] = {x["hesap"]: x["ad"] for x in yeni if x["ad"] and x["ad"] != GIDER_ADI.get(x["hesap"])}
        d.gider_mizan = {h: ozet["gider_mizan"][h] for h in ASAMA_HESAPLARI if h in ozet["gider_mizan"]}
    else:
        ozet["stok_mizan"] = [{"hesap": x["hesap"], "ad": x["ad"], "bakiye": str(x["bakiye"])} for x in yeni]
    d.excel_ozet = ozet


def _kayit(s: Session, d: m.SmmDonem, tur: str, hesap: str, islem: str, eski: dict | None, yeni: dict, neden: str, kullanici: str) -> None:
    s.add(m.DegisiklikKaydi(tablo=TABLO, kayit_id=d.id, islem=islem, eski=eski, kullanici=kullanici,
                            yeni={**yeni, "_neden": neden, "_mizan": TUR_ADI[tur], "_hesap": hesap, "_donem": donem_adi(d)}))
    s.flush()


def _hazirla(s: Session, donem_id: int, tur: str, neden: str | None) -> tuple[m.SmmDonem, str, str, list[dict], list[str]]:
    tur, neden = _tur(tur), _neden(neden)
    d = donem_getir(s, donem_id)
    kilit_denetle(d)   # kapanmış (kilitli) dönem değiştirilemez
    return d, tur, neden, satirlar(d, tur), elle_hesaplar(d, tur)


def _bul(kayitlar: list[dict], tur: str, hesap: str) -> dict:
    x = next((x for x in kayitlar if x["hesap"] == (hesap or "").strip()), None)
    if x is None:
        raise BulunamadiHatasi(f"Mizanda {hesap} hesabı bulunamadı.", {"tur": tur, "hesap": hesap})
    return x


def satir_ekle(s: Session, donem_id: int, tur: str, hesap: str, ad: str | None, bakiye, neden: str | None,
               kullanici: str = "sistem") -> dict:
    """Yeni mizan satırı; hesap kodu o mizanda varsa 409."""
    d, tur, neden, kayitlar, elle = _hazirla(s, donem_id, tur, neden)
    hesap = _hesap(tur, hesap)
    if any(x["hesap"] == hesap for x in kayitlar):
        raise CatismaHatasi(f"{hesap} hesap kodu mizanda zaten var.", {"hesap": hesap})
    tutar = _tutar(bakiye)
    _bakiye_denetle(tur, hesap, tutar)
    ad = (ad or "").strip() or (GIDER_ADI.get(hesap) if tur == "gider" else None)
    _yaz(d, tur, kayitlar + [{"hesap": hesap, "ad": ad, "bakiye": tutar}], elle + [hesap])
    _kayit(s, d, tur, hesap, "ekle", None, {"hesap": hesap, "ad": ad, "bakiye": str(tutar)}, neden, kullanici)
    return _cikis(d, tur)


def satir_guncelle(s: Session, donem_id: int, tur: str, hesap: str, alanlar: dict, neden: str | None, kullanici: str = "sistem") -> dict:
    """Satırın adını ve/veya bakiyesini değiştirir (yalnız verilen alanlar); değişen yoksa kayıt açmaz. Hesap kodu değişmez (sil + ekle)."""
    d, tur, neden, kayitlar, elle = _hazirla(s, donem_id, tur, neden)
    x = _bul(kayitlar, tur, hesap)
    eski, yeni = {}, {}
    if alanlar.get("bakiye") is not None:
        tutar = _tutar(alanlar["bakiye"])
        _bakiye_denetle(tur, x["hesap"], tutar)
        if tutar != x["bakiye"]:
            eski["bakiye"], yeni["bakiye"] = str(x["bakiye"]), str(tutar)
            x["bakiye"] = tutar
    if "ad" in alanlar:
        ad = (alanlar["ad"] or "").strip() or (GIDER_ADI.get(x["hesap"]) if tur == "gider" else None)
        if ad != x["ad"]:
            eski["ad"], yeni["ad"] = x["ad"], ad
            x["ad"] = ad
    if yeni:
        _yaz(d, tur, kayitlar, elle + [x["hesap"]])
        _kayit(s, d, tur, x["hesap"], "guncelle", eski, yeni, neden, kullanici)
    return {**_cikis(d, tur), "degisti": sorted(yeni)}


def satir_sil(s: Session, donem_id: int, tur: str, hesap: str, neden: str | None, kullanici: str = "sistem") -> dict:
    """Satırı mizandan çıkarır; eski değeri değişiklik kaydında kalır (geri eklenebilir)."""
    d, tur, neden, kayitlar, elle = _hazirla(s, donem_id, tur, neden)
    x = _bul(kayitlar, tur, hesap)
    _yaz(d, tur, [y for y in kayitlar if y is not x], elle)
    _kayit(s, d, tur, x["hesap"], "sil", {"hesap": x["hesap"], "ad": x["ad"], "bakiye": str(x["bakiye"])}, {}, neden, kullanici)
    return _cikis(d, tur)
