"""Veri Aktar: üretim adetleri, satın alma BF (malzeme kartı + fiyat) ve gider dağıtımı ayrı ayrı içe aktarılır.
Dosya ya tam çalışma kitabıdır (ilgili sayfa adıyla) ya da tek sayfalık xlsx'tir (ilk sayfa, aynı sütun düzeni).
Okuma fiyat_motoru.excel_okuyucu ile yapılır; her tip önce doğrular, sonra yazar (hata -> hiçbir şey yazılmaz)."""
from datetime import date
from decimal import Decimal
from pathlib import Path
import openpyxl
from sqlalchemy import select
from sqlalchemy.orm import Session
from fiyat_motoru import excel_okuyucu as eo
from fiyat_motoru.para import SIFIR
from ..depo import modeller as m
from . import fiyat_servisi, gider_servisi, hesap_servisi, kapasite_servisi
from .hatalar import DogrulamaHatasi
from .import_servisi import HAVUZ_ESLEME, MALZEME_KART_ALANLARI, _ondalik, revize_fiyatlarini_oku, revize_ile_fiyat_ekle

SAYFA_URETIM = eo.URETIM_ADETLERI_SAYFA
SAYFA_SATIN_ALMA = "S.ALMA BF"
SAYFA_GIDER = "Gider Dağıtım"
OKUMA_HATALARI = (KeyError, ValueError, TypeError, ArithmeticError, StopIteration, IndexError)


def _kitap_ac(dosya_yolu: Path, sayfa_adi: str):
    """Değer kitabını bellekte açar. Sayfa adı varsa o sayfa; yoksa ve dosya tek sayfalıysa o sayfa beklenen ada çevrilir
    (yüklenen dosyaya dokunulmaz). Aksi halde 422."""
    try:
        wb = openpyxl.load_workbook(dosya_yolu, data_only=True)
    except OKUMA_HATALARI as e:
        raise DogrulamaHatasi(f"dosya okunamadı: {e!r}")
    if sayfa_adi in wb.sheetnames:
        return wb
    if len(wb.sheetnames) == 1:
        wb.worksheets[0].title = sayfa_adi
        return wb
    raise DogrulamaHatasi(f"{sayfa_adi} sayfası bulunamadı; tek sayfalık dosyada ilk sayfa kullanılır", {"sayfa": sayfa_adi})


_TR = str.maketrans("İIışğüöçŞĞÜÖÇ", "iiisguocsguoc")


def _norm(v) -> str:
    """Türkçe harf duyarsız karşılaştırma metni."""
    return str(v or "").translate(_TR).lower().strip()


def _duzen_hatasi(sayfa: str):
    return DogrulamaHatasi(f"{sayfa} sayfası beklenen düzen değil", {"sayfa": sayfa})


def _satin_alma_baslik_kontrol(ws) -> None:
    """S.ALMA BF birinci satır: Malzeme | Açıklama | Malzeme Tipi | Stok Birimi | Para Birimi | Bütçe Birim Fiyatları."""
    b = [_norm(c.value) for c in next(ws.iter_rows(min_row=1, max_row=1, max_col=6), ())]
    b += [""] * (6 - len(b))
    if not (b[0].startswith("malzeme") and b[1].startswith("aciklama") and b[4].startswith("para") and "fiyat" in b[5]):
        raise _duzen_hatasi(SAYFA_SATIN_ALMA)


GIDER_ETIKETLERI = (("D3", "gider toplam"), ("D12", "gider toplam"), ("D17", "gider toplam"), ("D26", "gider toplam"),
                    ("D63", "gider toplam"), ("D66", "gider toplam"), ("A69", "ambalaj"))


def _gider_duzen_kontrol(ws) -> None:
    """Gider Dağıtım: toplam başlıkları ve ambalaj başlığı bilinen hücrelerde olmalı."""
    if any(not _norm(ws[adres].value).startswith(etiket) for adres, etiket in GIDER_ETIKETLERI):
        raise _duzen_hatasi(SAYFA_GIDER)


def _oku(islev, *a):
    try:
        return islev(*a)
    except DogrulamaHatasi:
        raise
    except OKUMA_HATALARI as e:
        raise DogrulamaHatasi(f"dosya beklenen sütun düzeninde değil: {e}")


def _neden_kontrol(neden: str) -> str:
    if not (neden or "").strip():
        raise DogrulamaHatasi("neden zorunlu")
    return neden.strip()


def _str(v) -> str | None:
    return None if v is None else str(v)


# ---------------------------------------------------------------- 1. Üretim adetleri

def uretim_onizle(s: Session, senaryo_id: int, dosya_yolu: Path) -> dict:
    hesap_servisi.senaryo_getir(s, senaryo_id)
    wb = _kitap_ac(dosya_yolu, SAYFA_URETIM)
    satirlar = _oku(eo.uretim_adetlerini_oku, wb)
    if not satirlar:
        raise DogrulamaHatasi("Üretim Adetleri sayfasında satır yok")
    mevcut = {k.urun_kodu: k for k in s.scalars(select(m.UretimKapasitesi).where(m.UretimKapasitesi.senaryo_id == senaryo_id))}
    out = {"yeni": [], "degisen": [], "ayni": 0, "uyarilar": [], "_yazilacak": []}
    gorulen: set[str] = set()
    for r in satirlar:
        kod = r["urun_kodu"]
        if kod in gorulen:
            out["uyarilar"].append(f"Üretim Adetleri: ürün kodu {kod} birden fazla satırda; ilk satır korundu")
            continue
        gorulen.add(kod)
        alanlar = {a: r[a] for a in kapasite_servisi.SAYISAL_ALANLAR}
        k = mevcut.get(kod)
        if k is None:
            out["yeni"].append({"urun_kodu": kod, "urun_ad": r["urun_ad"], "alanlar": {a: str(v) for a, v in alanlar.items()}})
            out["_yazilacak"].append(r)
            continue
        farklar = [{"urun_kodu": kod, "alan": a, "eski": str(getattr(k, a)), "yeni": str(v)} for a, v in alanlar.items() if getattr(k, a) != v]
        if r["urun_ad"] and r["urun_ad"] != k.urun_ad:
            farklar.append({"urun_kodu": kod, "alan": "urun_ad", "eski": _str(k.urun_ad), "yeni": r["urun_ad"]})
        if farklar:
            out["degisen"] += farklar
            out["_yazilacak"].append(r)
        else:
            out["ayni"] += 1
    return out


def uretim_uygula(s: Session, senaryo_id: int, dosya_yolu: Path, neden: str, kullanici: str = "sistem") -> dict:
    neden = _neden_kontrol(neden)
    on = uretim_onizle(s, senaryo_id, dosya_yolu)
    yeni_kodlar = {y["urun_kodu"] for y in on["yeni"]}
    for r in on["_yazilacak"]:
        kapasite_servisi.kaydet(s, senaryo_id, r["urun_kodu"], {a: r[a] for a in kapasite_servisi.SAYISAL_ALANLAR}, neden,
                                r["urun_ad"] or None, kullanici)
    guncellenen = len(on["_yazilacak"]) - len(yeni_kodlar)
    return {"eklenen": len(yeni_kodlar), "guncellenen": guncellenen, "uyarilar": on["uyarilar"]}


# ---------------------------------------------------------------- 2. Satın alma BF

def _satin_alma_oku(dosya_yolu: Path):
    """(malzemeler, hatali kodlar, revize fiyatlar). Fiyatı (F ya da I) sayı olmayan/negatif satırlar hatalıdır; okuyucuya verilmeden
    hücre boşaltılır ve atlanır. I sütunu (revize) boş ya da F'ye eşitse revize yoktur."""
    wb = _kitap_ac(dosya_yolu, SAYFA_SATIN_ALMA)
    ws = wb[SAYFA_SATIN_ALMA]
    _satin_alma_baslik_kontrol(ws)
    revize, hatali = revize_fiyatlarini_oku(ws)
    for satir in ws.iter_rows(min_row=2, max_col=6):
        kod = satir[0].value
        if not kod or not str(kod).strip():
            continue
        f = satir[5].value if len(satir) > 5 else None
        if f is None or f == "":
            continue
        try:
            _ondalik(f)   # F ve I aynı kural: sayı (ya da sayı metni), negatif değil
        except ValueError:
            hatali.append(str(kod).strip())
            satir[5].value = None
    malzemeler = _oku(eo.malzemeleri_oku, wb)
    hatali = sorted(set(hatali), key=hatali.index)
    for kod in hatali:
        malzemeler.pop(kod, None); revize.pop(kod, None)
    return malzemeler, hatali, revize


def satin_alma_onizle(s: Session, senaryo_id: int, dosya_yolu: Path, gecerlilik_basi: date | None = None) -> dict:
    """fiyat_yeni/fiyat_degisen geçerli olacak fiyatla (revize varsa I, yoksa F) kıyaslar; `revize` listesi bilgi amaçlıdır (tekrar yüklemede de görünür)."""
    hesap_servisi.senaryo_getir(s, senaryo_id)
    malzemeler, hatali, revize = _satin_alma_oku(dosya_yolu)
    kartlar = {mz.kod: mz for mz in s.scalars(select(m.Malzeme))}
    gecerli = fiyat_servisi.gecerli_fiyatlar(s, senaryo_id, gecerlilik_basi or date.today())
    out = {"yeni_malzeme": [], "kart_farki": [], "fiyat_yeni": [], "fiyat_degisen": [], "ayni": 0, "hatali": hatali,
           "revize": [{"kod": kod, "ilk": str(malzemeler[kod].fiyat) if malzemeler[kod].fiyat and malzemeler[kod].fiyat != SIFIR else None,
                       "revize": str(r)} for kod, r in revize.items() if kod in malzemeler],
           "revize_sayisi": 0}
    out["revize_sayisi"] = len(out["revize"])
    for kod, mz in malzemeler.items():
        kart = kartlar.get(kod)
        degisti = False
        if kart is None:
            out["yeni_malzeme"].append({"kod": kod, "ad": mz.ad, "tip": mz.tip, "birim": mz.birim, "para_birimi": mz.para_birimi, "zs": mz.zs})
            degisti = True
        else:
            alanlar = [a for a in MALZEME_KART_ALANLARI if getattr(kart, a) != getattr(mz, a)]
            if alanlar:
                out["kart_farki"].append({"kod": kod, "alanlar": alanlar}); degisti = True
        etkin = revize.get(kod, mz.fiyat)
        if etkin and etkin != SIFIR:
            mevcut = gecerli.get(kod) if kart is not None else None
            para = mz.para_birimi or (kart.para_birimi if kart is not None else None)
            if mevcut is None or mevcut.fiyat == SIFIR:
                out["fiyat_yeni"].append({"kod": kod, "yeni": str(etkin), "para": para}); degisti = True
            elif mevcut.fiyat != etkin or (para and mevcut.para_birimi != para):
                out["fiyat_degisen"].append({"kod": kod, "eski": str(mevcut.fiyat), "yeni": str(etkin), "para": para,
                                             "eski_para": mevcut.para_birimi}); degisti = True
        if not degisti:
            out["ayni"] += 1
    out["_malzemeler"] = malzemeler
    out["_revize"] = revize
    return out


def satin_alma_uygula(s: Session, senaryo_id: int, dosya_yolu: Path, gecerlilik_basi: date, neden: str, kartlari_guncelle: bool = False,
                      kullanici: str = "sistem") -> dict:
    neden = _neden_kontrol(neden)
    on = satin_alma_onizle(s, senaryo_id, dosya_yolu, gecerlilik_basi)
    if on["hatali"]:
        raise DogrulamaHatasi("fiyatı geçersiz satırlar var; düzeltip yeniden yükleyin", {"hatali": ", ".join(on["hatali"])})
    malzemeler = on["_malzemeler"]
    kod_listesi = [y["kod"] for y in on["yeni_malzeme"]]
    if kartlari_guncelle:
        kod_listesi += [f["kod"] for f in on["kart_farki"]]
    for kod in kod_listesi:
        mz = malzemeler[kod]
        fiyat_servisi.malzeme_ekle_veya_guncelle(s, kod, mz.ad, mz.tip, mz.birim, mz.para_birimi, mz.zs, kullanici)
    yazilan = []
    revize_yazilan = 0
    revize = on["_revize"]
    yeni_kodlar = {y["kod"] for y in on["yeni_malzeme"]}   # kartı yeni açılan kodun senaryoda fiyat kaydı olamaz
    for f in on["fiyat_yeni"] + on["fiyat_degisen"]:
        kod = f["kod"]
        revize_yazilan += revize_ile_fiyat_ekle(s, senaryo_id, kod, malzemeler[kod].fiyat, revize.get(kod), gecerlilik_basi, neden, kullanici,
                                                para_birimi=f["para"], yeni_kayit=kod in yeni_kodlar)
        yazilan.append(kod)
    return {"malzeme_eklenen": len(on["yeni_malzeme"]), "kart_guncellenen": len(on["kart_farki"]) if kartlari_guncelle else 0,
            "fiyat_yazilan": len(yazilan), "kodlar": yazilan, "ayni": on["ayni"], "revize_yazilan": revize_yazilan}


# ---------------------------------------------------------------- 3. Gider dağıtım

def _gider_formulleri(dosya_yolu: Path, sayfa_adi: str) -> dict:
    """Gider sayfasının formül görünümünden taban × çarpan kalıpları (excel_okuyucu.havuz_formulleri_oku). Salt okunur açılır (hızlı);
    sayfa seçimi _kitap_ac ile aynı. Okunamazsa boş: toplamlar eskisi gibi doğrudan yazılır."""
    try:
        wb = openpyxl.load_workbook(dosya_yolu, data_only=False, read_only=True)
    except OKUMA_HATALARI:
        return {}
    try:
        ws = wb[sayfa_adi] if sayfa_adi in wb.sheetnames else (wb.worksheets[0] if len(wb.sheetnames) == 1 else None)
        return eo.havuz_formulleri_oku(ws) if ws is not None else {}
    except OKUMA_HATALARI:
        return {}
    finally:
        wb.close()


def _yeni_havuzlar(h, formuller: dict | None = None) -> dict[str, dict]:
    out = {}
    for kod, ad, toplam_alani, baz_tipi, baz_alani, pay_alani in HAVUZ_ESLEME:
        paylar = [(k, p, b) for k, (p, b) in getattr(h, pay_alani).items()] if pay_alani else []
        toplam, taban, carpanlar = gider_servisi.excel_taban_carpan(getattr(h, toplam_alani), (formuller or {}).get(toplam_alani))
        out[kod] = {"ad": ad, "toplam": toplam, "taban": taban, "carpanlar": carpanlar, "baz_tipi": baz_tipi,
                    "baz": getattr(h, baz_alani) if baz_alani else None, "anahtarlar": paylar}
    return out


def gider_onizle(s: Session, senaryo_id: int, dosya_yolu: Path) -> dict:
    hesap_servisi.senaryo_getir(s, senaryo_id)
    wb = _kitap_ac(dosya_yolu, SAYFA_GIDER)
    _gider_duzen_kontrol(wb[SAYFA_GIDER])
    h = _oku(eo.havuzlari_oku, wb)
    yeni = _yeni_havuzlar(h, _gider_formulleri(dosya_yolu, SAYFA_GIDER))
    if all(y["toplam"] == SIFIR for y in yeni.values()):
        raise _duzen_hatasi(SAYFA_GIDER)
    mevcut = gider_servisi.havuzlar(s, senaryo_id)
    havuz = []
    for kod, y in yeni.items():
        e = mevcut.get(kod)
        eski_anahtar = {a.alt_kalem: (a.pay_orani, a.baz_miktar) for a in e.anahtarlar} if e is not None else {}
        yeni_anahtar = {a: (p, b) for a, p, b in y["anahtarlar"]}
        anahtar_farki = e is not None and eski_anahtar != yeni_anahtar or (e is None and bool(yeni_anahtar))
        carpan_farki = e is not None and gider_servisi.carpan_degerleri(e) != (y["taban"], tuple(d for _, d in y["carpanlar"] or []))
        degisti = (e is None or e.toplam_tutar != y["toplam"] or e.baz_miktar != y["baz"] or e.baz_tipi != y["baz_tipi"] or anahtar_farki
                   or carpan_farki)
        havuz.append({"kod": kod, "ad": y["ad"], "eski_toplam": _str(e.toplam_tutar) if e else None, "yeni_toplam": str(y["toplam"]),
                      "eski_baz": _str(e.baz_miktar) if e else None, "yeni_baz": _str(y["baz"]), "anahtar_farki": bool(anahtar_farki),
                      "yeni_taban": _str(y["taban"]), "yeni_carpanlar": [str(d) for _, d in y["carpanlar"] or []],
                      "degisti": bool(degisti)})
    eski_amb = gider_servisi.ambalajlar(s, senaryo_id)
    yeni_amb = list(h.ambalajlar)
    eski_ad = {a.ad: a for a in eski_amb}
    yeni_ad = {a.ad: a for a in yeni_amb}
    degisen = []
    for a in yeni_amb:
        e = eski_ad.get(a.ad)
        if e is None:
            degisen.append({"ad": a.ad, "alan": "sinif", "eski": None, "yeni": "eklendi"}); continue
        for alan in ("hacim", "uretim_adedi", "katsayi"):
            if getattr(e, alan) != getattr(a, alan):
                degisen.append({"ad": a.ad, "alan": alan, "eski": str(getattr(e, alan)), "yeni": str(getattr(a, alan))})
    for ad in eski_ad:
        if ad not in yeni_ad and yeni_amb:
            degisen.append({"ad": ad, "alan": "sinif", "eski": "var", "yeni": None})
    return {"havuz": havuz, "ambalaj": {"eski_adet": len(eski_amb), "yeni_adet": len(yeni_amb), "degisen": degisen},
            "_yeni": yeni, "_yeni_ambalaj": yeni_amb}


def gider_uygula(s: Session, senaryo_id: int, dosya_yolu: Path, neden: str, kullanici: str = "sistem") -> dict:
    neden = _neden_kontrol(neden)
    on = gider_onizle(s, senaryo_id, dosya_yolu)
    yeni = on["_yeni"]
    for kod, y in yeni.items():   # yazmadan önce doğrula: kısmi yazım olmasın
        if y["baz_tipi"] in ("saniye", "adet") and not y["anahtarlar"] and kod not in gider_servisi.AMBALAJ_BAZLI and (y["baz"] is None or y["baz"] <= 0):
            raise DogrulamaHatasi(f"{y['ad']}: dağıtım bazı (saniye/adet) 0'dan büyük olmalı", {"kod": kod})
    yazilan = [h["kod"] for h in on["havuz"] if h["degisti"]]
    for kod in yazilan:
        y = yeni[kod]
        gider_servisi.havuz_kaydet(s, senaryo_id, kod, y["ad"], y["toplam"], y["baz_tipi"], y["baz"], y["anahtarlar"], kullanici, neden=neden,
                                   taban_tutar=y["taban"], carpanlar=y["carpanlar"])
    amb = on["ambalaj"]
    amb_yazilan = 0
    if on["_yeni_ambalaj"] and (amb["degisen"] or amb["eski_adet"] != amb["yeni_adet"]):
        gider_servisi.ambalaj_kaydet(s, senaryo_id, [(a.ad, a.hacim, a.uretim_adedi, a.katsayi) for a in on["_yeni_ambalaj"]], kullanici, neden=neden)
        amb_yazilan = len(on["_yeni_ambalaj"])
    return {"havuz": len(yazilan), "ambalaj": amb_yazilan, "havuz_kodlari": yazilan}
