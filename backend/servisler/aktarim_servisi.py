"""Veri Aktar: üretim adetleri, satın alma BF (malzeme kartı + fiyat) ve gider dağıtımı ayrı ayrı içe aktarılır.
Dosya ya tam çalışma kitabıdır (ilgili sayfa adıyla) ya da tek sayfalık xlsx'tir (ilk sayfa, aynı sütun düzeni).
Okuma fiyat_motoru.excel_okuyucu ile yapılır; her tip önce doğrular, sonra yazar (hata -> hiçbir şey yazılmaz)."""
from datetime import date
from decimal import Decimal
from pathlib import Path
import openpyxl
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from fiyat_motoru import excel_okuyucu as eo
from fiyat_motoru.para import SIFIR
from ..depo import modeller as m
from . import fiyat_servisi, gider_servisi, hesap_servisi, kapasite_servisi
from .hatalar import DogrulamaHatasi, liste_metni
from .import_servisi import HAVUZ_ESLEME, MALZEME_KART_ALANLARI, _ondalik, revize_fiyatlarini_oku, revize_ile_fiyat_ekle

SAYFA_URETIM = eo.URETIM_ADETLERI_SAYFA
SAYFA_SATIN_ALMA = "S.ALMA BF"
SAYFA_GIDER = "Gider Dağıtım"
OKUMA_HATALARI = (KeyError, ValueError, TypeError, ArithmeticError, StopIteration, IndexError)


SAYFA_ESANLAMLARI = {SAYFA_URETIM: ("Uretim Adetleri", "Üretim Adet"), SAYFA_SATIN_ALMA: ("SALMA BF", "Satın Alma", "Satın Alma Fiyat Listesi"),
                     SAYFA_GIDER: ("Gider Dagitim", "Gider Dağıtımı")}
SABLON_KIMLIGI = {SAYFA_URETIM: "uretim_adetleri", SAYFA_SATIN_ALMA: ("satin_alma_fiyat_listesi", "malzeme_fiyat_listesi"),
                  SAYFA_GIDER: "gider_dagitim"}


def _kitap_ac(dosya_yolu: Path, sayfa_adi: str):
    """Değer kitabını bellekte açar. Başka ekranın şablonuysa 422 `yanlis_sablon`. Sayfa adı esnek bulunur (büyük/küçük, Türkçe harf,
    boşluk); yoksa ve dosyada tek veri sayfası varsa o sayfa beklenen ada çevrilir (yüklenen dosyaya dokunulmaz). Aksi halde 422."""
    from .excel_ortak import sablon_denetle
    from .import_servisi import kitap_ac
    from .yukleme_guvenligi import sayfa_sec
    wb = kitap_ac(dosya_yolu, data_only=True)
    sablon_denetle(wb, SABLON_KIMLIGI[sayfa_adi])
    sayfa_sec(wb, sayfa_adi, SAYFA_ESANLAMLARI.get(sayfa_adi, ()))
    return wb


def _yedek_on(s: Session, alan: str, senaryo_id: int, veri: dict, ozet: str, kaynak_dosya: str | None, kullanici: str):
    from .yukleme_guvenligi import yedekle
    return yedekle(s, alan, senaryo_id, {"senaryo_id": senaryo_id, **veri}, ozet, kaynak_dosya, kullanici)


_TR = str.maketrans("İIışğüöçŞĞÜÖÇ", "iiisguocsguoc")


def _norm(v) -> str:
    """Türkçe harf duyarsız karşılaştırma metni."""
    return str(v or "").translate(_TR).lower().strip()


def _duzen_hatasi(sayfa: str):
    return DogrulamaHatasi(f"{sayfa} sayfası beklenen düzende değil.", {"sayfa": sayfa})


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
        raise DogrulamaHatasi(f"Dosya beklenen sütun düzeninde değil: {e}")


def _neden_kontrol(neden: str) -> str:
    if not (neden or "").strip():
        raise DogrulamaHatasi("Neden girin.")
    return neden.strip()


def _str(v) -> str | None:
    return None if v is None else str(v)


# ---------------------------------------------------------------- 1. Üretim adetleri

def uretim_alanlari():
    from .excel_ortak import Alan
    return [Alan("urun_kodu", ("Ürün Kodu", "Urun Kodu", "Stok Kodu", "Malzeme Kodu", "Mamul Kodu", "Kod")),
            Alan("urun_ad", ("Ürün Adı", "Stok Adı", "Malzeme Adı", "Malzeme Açıklaması", "Mamul Adı", "Ad"), zorunlu=False),
            Alan("net_kapasite", ("Net Süredeki Vardiyalık Kapasite", "Net Süredeki Kapasite", "Net Kapasite", "Net Vardiyalık Kapasite"), zorunlu=False),
            Alan("net_sure", ("Net Süre", "Net Çalışma Süresi"), zorunlu=False),
            Alan("toplam_kapasite", ("Toplam Süredeki Kapasite", "Toplam Süredeki Vardiyalık Kapasite", "Toplam Kapasite"), zorunlu=False),
            Alan("toplam_sure", ("Toplam Süre", "Toplam Vardiya Süresi"), zorunlu=False),
            Alan("hedef_uretim", ("Hedef Vardiyalık Üretim", "Hedef Vardiya Üretimi", "Hedef Üretim", "Vardiyalık Hedef", "Hedef")),
            Alan("ortalama_isci", ("Ortalama İşçi Sayısı", "Ortalama İşçi", "İşçi Sayısı", "İşçi"), zorunlu=False)]


# Excel'in klasik düzeni (A kod, B ad, C-F kapasite/süre, G hedef, H işçi): başlığı tanınmayan sayısal sütunlar bu sıradan okunur.
_URETIM_KLASIK = {"urun_ad": 1, "net_kapasite": 2, "net_sure": 3, "toplam_kapasite": 4, "toplam_sure": 5, "ortalama_isci": 7}
_BOS_SAYI = ("-", "–", "—")


def _uretim_sayisi(v, alan: str):
    """(Decimal, hata). Boş ve '-' → 0 (Excel'deki boş kapasite); metin sayı çevrilir; çevrilemeyen ('#DIV/0!', 'abc') hata."""
    from .excel_ortak import sayi_cevir
    if v is None or (isinstance(v, str) and (not v.strip() or v.strip() in _BOS_SAYI)):
        return SIFIR, None
    if isinstance(v, bool):
        return None, f"{alan}: sayı değil"
    d, hata = sayi_cevir(v, alan)
    if hata:
        return None, hata
    return (d if d is not None else SIFIR), None


def uretim_oku(wb) -> dict:
    """Üretim Adetleri sayfası (başlıklar adla, esnek). Başlığın hemen altındaki birim satırı ('(adet)', '(saat)') atlanır.
    Dönüş: {"satirlar": [...], "sorunlu": [...], "okunan": n}. Sayısı okunamayan satır sorunludur, yazılmaz."""
    from .excel_ortak import baslik_satirini_bul
    from .yukleme_guvenligi import sorunlu as sorunlu_satir
    hepsi = list(wb[SAYFA_URETIM].iter_rows(values_only=True))
    e = baslik_satirini_bul(iter(hepsi), uretim_alanlari(), ne="üretim adetleri dosyası")
    if e.sutun.get("urun_kodu") == 0 and e.sutun.get("hedef_uretim") == 6:
        for a, i in _URETIM_KLASIK.items():
            e.sutun.setdefault(a, i)
    sayisal = kapasite_servisi.SAYISAL_ALANLAR
    hucre = lambda r, a: (r[e.sutun[a]] if a in e.sutun and e.sutun[a] < len(r) else None)
    satirlar, sorunlu, okunan = [], [], 0
    for no, r in enumerate(hepsi[e.satir:], start=e.satir + 1):
        r = list(r or ())
        sayilar = [hucre(r, a) for a in sayisal]
        if no == e.satir + 1 and all(v is None or (isinstance(v, str) and (v.strip().startswith("(") or not v.strip())) for v in sayilar):
            continue   # birim satırı
        kod = hucre(r, "urun_kodu")
        if kod is None or not str(kod).strip():
            continue
        kod = str(kod).strip()
        okunan += 1
        satir = {"satir": no, "urun_kodu": kod, "urun_ad": str(hucre(r, "urun_ad") or "").strip()}
        hatali = False
        for a in sayisal:
            d, hata = _uretim_sayisi(hucre(r, a), a)
            if hata:
                sorunlu.append(sorunlu_satir(no, kod, a, hucre(r, a), hata)); hatali = True
            satir[a] = d
        if not hatali:
            satirlar.append(satir)
    return {"satirlar": satirlar, "sorunlu": sorunlu, "okunan": okunan}


def uretim_onizle(s: Session, senaryo_id: int, dosya_yolu: Path) -> dict:
    from .yukleme_guvenligi import ozet
    hesap_servisi.senaryo_getir(s, senaryo_id)
    wb = _kitap_ac(dosya_yolu, SAYFA_URETIM)
    okunan = uretim_oku(wb)
    satirlar = okunan["satirlar"]
    if not okunan["okunan"]:
        raise DogrulamaHatasi("Üretim Adetleri sayfasında satır yok; mevcut veri değiştirilmedi.", kod="bos_dosya")
    mevcut = {k.urun_kodu: k for k in s.scalars(select(m.UretimKapasitesi).where(m.UretimKapasitesi.senaryo_id == senaryo_id))}
    out = {"yeni": [], "degisen": [], "ayni": 0, "uyarilar": [], "_yazilacak": []}
    gorulen: set[str] = set()
    tekrar = 0
    for r in satirlar:
        kod = r["urun_kodu"]
        if kod in gorulen:
            out["uyarilar"].append(f"Üretim Adetleri: ürün kodu {kod} birden fazla satırda; ilk satır korundu")
            tekrar += 1
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
    degisen_urun = len({d["urun_kodu"] for d in out["degisen"]})
    out["ozet"] = ozet(okunan=okunan["okunan"], yeni=len(out["yeni"]), degisen=degisen_urun, ayni=out["ayni"],
                       atlanan=tekrar + len(okunan["sorunlu"]), sorunlu_satirlar=okunan["sorunlu"], uyarilar=out["uyarilar"])
    return out


def uretim_uygula(s: Session, senaryo_id: int, dosya_yolu: Path, neden: str, kullanici: str = "sistem", onay: bool = False,
                  kaynak_dosya: str | None = None) -> dict:
    """Upsert: dosyada olmayan ürünlerin kapasitesi silinmez (satır kaybı yok). Yazmadan önce değişecek kayıtların yedeği alınır."""
    from .yukleme_guvenligi import kapasite_icerik
    neden = _neden_kontrol(neden)
    on = uretim_onizle(s, senaryo_id, dosya_yolu)
    yeni_kodlar = {y["urun_kodu"] for y in on["yeni"]}
    if on["_yazilacak"]:
        mevcut = {k.urun_kodu: k for k in s.scalars(select(m.UretimKapasitesi).where(m.UretimKapasitesi.senaryo_id == senaryo_id))}
        _yedek_on(s, "uretim_adetleri", senaryo_id,
                  {"eski": {r["urun_kodu"]: kapasite_icerik(mevcut[r["urun_kodu"]]) for r in on["_yazilacak"] if r["urun_kodu"] in mevcut},
                   "yeni_kodlar": sorted(yeni_kodlar)},
                  f"{len(yeni_kodlar)} yeni, {len(on['_yazilacak']) - len(yeni_kodlar)} değişen ürün", kaynak_dosya, kullanici)
    for r in on["_yazilacak"]:
        kapasite_servisi.kaydet(s, senaryo_id, r["urun_kodu"], {a: r[a] for a in kapasite_servisi.SAYISAL_ALANLAR}, neden,
                                r["urun_ad"] or None, kullanici)
    guncellenen = len(on["_yazilacak"]) - len(yeni_kodlar)
    return {"eklenen": len(yeni_kodlar), "guncellenen": guncellenen, "uyarilar": on["uyarilar"]}


# ---------------------------------------------------------------- 2. Satın alma BF

def _satin_alma_oku(dosya_yolu: Path):
    """(malzemeler, hatali kodlar, revize fiyatlar, okuyucu çıktısı). Başlıklar adla bulunur (esnek). Fiyatı (F ya da revize) sayı
    olmayan/negatif satırlar hatalıdır (sorunlu), malzemelere girmez. Revize boş ya da F'ye eşitse revize yoktur. Aynı kod: son satır."""
    from fiyat_motoru.modeller import Malzeme as MotorMalzeme
    from .import_servisi import salma_oku
    wb = _kitap_ac(dosya_yolu, SAYFA_SATIN_ALMA)
    okunan = salma_oku(wb[SAYFA_SATIN_ALMA], tam=True, ne="satın alma fiyat listesi (S.ALMA BF)")
    hatali = list(dict.fromkeys(x["kod"] for x in okunan["sorunlu"]))
    malzemeler, revize = {}, {}
    for x in okunan["satirlar"]:
        malzemeler[x["kod"]] = MotorMalzeme(kod=x["kod"], ad=x["ad"], tip=x["tip"], birim=x["birim"], para_birimi=x["para"],
                                            fiyat=x["fiyat"] if x["fiyat"] is not None else SIFIR, zs=x["zs"])
        if x["revize"] is not None:
            revize[x["kod"]] = x["revize"]
        else:
            revize.pop(x["kod"], None)
    for kod in hatali:
        malzemeler.pop(kod, None); revize.pop(kod, None)
    return malzemeler, hatali, revize, okunan


def satin_alma_onizle(s: Session, senaryo_id: int, dosya_yolu: Path, gecerlilik_basi: date | None = None) -> dict:
    """fiyat_yeni/fiyat_degisen geçerli olacak fiyatla (revize varsa I, yoksa F) kıyaslar; `revize` listesi bilgi amaçlıdır (tekrar yüklemede de görünür)."""
    from .import_servisi import _yuzde, buyuk_degisim, fiyat_esikleri
    from .yukleme_guvenligi import ozet
    hesap_servisi.senaryo_getir(s, senaryo_id)
    malzemeler, hatali, revize, okunan = _satin_alma_oku(dosya_yolu)
    if not okunan["okunan"]:
        raise DogrulamaHatasi("Dosyada okunabilen malzeme satırı yok; mevcut veri değiştirilmedi.", kod="bos_dosya")
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
    esikler = fiyat_esikleri(s, senaryo_id, gecerlilik_basi or date.today())
    uyarilar = []
    for f in out["fiyat_degisen"]:
        oran = buyuk_degisim(Decimal(f["eski"]), Decimal(f["yeni"]), f["para"], esikler) if f["para"] == f["eski_para"] or not f["eski_para"] else None
        if oran is not None:
            uyarilar.append(f"{f['kod']}: fiyat {_yuzde(oran)} değişiyor ({f['eski']} → {f['yeni']} {f['para'] or 'TL'}).")
    gorulen: dict[str, int] = {}
    for x in okunan["satirlar"]:
        if x["kod"] in gorulen:
            uyarilar.append(f"{x['kod']} dosyada birden çok satırda (satır {gorulen[x['kod']]} ve {x['satir']}); son satır geçerli.")
        gorulen[x["kod"]] = x["satir"]
    degisen = len({x["kod"] for x in out["kart_farki"]} | {x["kod"] for x in out["fiyat_degisen"]} | {x["kod"] for x in out["fiyat_yeni"]}
                  - {x["kod"] for x in out["yeni_malzeme"]})
    out["ozet"] = ozet(okunan=okunan["okunan"], yeni=len(out["yeni_malzeme"]), degisen=degisen, ayni=out["ayni"],
                       atlanan=len(okunan["sorunlu"]), sorunlu_satirlar=okunan["sorunlu"], uyarilar=uyarilar)
    out["_malzemeler"] = malzemeler
    out["_revize"] = revize
    return out


def satin_alma_uygula(s: Session, senaryo_id: int, dosya_yolu: Path, gecerlilik_basi: date, neden: str, kartlari_guncelle: bool = False,
                      kullanici: str = "sistem", onay: bool = False, kaynak_dosya: str | None = None) -> dict:
    """Kart açar / günceller, fiyatları ekler (eski fiyatlar silinmez: satır kaybı yok). Yazmadan önce yedek: geri al eklenen fiyatları
    siler, açılan kartları kaldırır, güncellenen kartları eski haline döndürür."""
    from .yukleme_guvenligi import malzeme_karti, yedek_guncelle
    neden = _neden_kontrol(neden)
    on = satin_alma_onizle(s, senaryo_id, dosya_yolu, gecerlilik_basi)
    if on["hatali"]:
        raise DogrulamaHatasi(f"Fiyatı geçersiz satırlar var ({liste_metni(on['hatali'])}); düzeltip yeniden yükleyin.", {"hatali": ", ".join(on["hatali"])})
    malzemeler = on["_malzemeler"]
    kod_listesi = [y["kod"] for y in on["yeni_malzeme"]]
    if kartlari_guncelle:
        kod_listesi += [f["kod"] for f in on["kart_farki"]]
    y = None
    if kod_listesi or on["fiyat_yeni"] or on["fiyat_degisen"]:
        kartlar = {mz.kod: mz for mz in s.scalars(select(m.Malzeme).where(m.Malzeme.kod.in_(kod_listesi)))} if kod_listesi else {}
        y = _yedek_on(s, "satin_alma", senaryo_id,
                      {"fiyat_idleri": [], "yeni_malzemeler": [x["kod"] for x in on["yeni_malzeme"]],
                       "kart_eski": {k: malzeme_karti(v) for k, v in kartlar.items()}},
                      f"{len(on['yeni_malzeme'])} yeni malzeme, {len(on['fiyat_yeni']) + len(on['fiyat_degisen'])} fiyat", kaynak_dosya, kullanici)
    once = s.scalar(select(func.max(m.MalzemeFiyati.id))) or 0
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
    if y is not None:
        yedek_guncelle(y, fiyat_idleri=list(s.scalars(select(m.MalzemeFiyati.id).where(m.MalzemeFiyati.id > once,
                                                                                       m.MalzemeFiyati.senaryo_id == senaryo_id))))
        s.flush()
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


def _gider_sayi_hucreleri(ws) -> list[str]:
    """Gider Dağıtım'da sayı beklenen hücre adresleri (toplamlar, saniye bazları, pay / baz hücreleri, ambalaj sayıları)."""
    adresler = list(eo.HAVUZ_TOPLAM_HUCRELERI.values()) + ["F4", "F13", "F18", "F27"]
    for ad_sutunu, satirlar in (("C", range(7, 10)), ("C", range(21, 24)), ("A", range(30, 38)), ("A", range(41, 49)), ("A", range(52, 60))):
        adresler += [f"{x}{r}" for r in satirlar if ws[f"{ad_sutunu}{r}"].value for x in ("E", "G")]
    adresler += [f"{x}{r}" for r in range(70, 92) if ws[f"A{r}"].value for x in ("B", "C", "D")]
    return adresler


def _gider_sayilarini_cevir(ws) -> list[dict]:
    """Metin olarak yazılmış sayıları ('1.234,56', '%20') bellekte sayıya çevirir; çevrilemeyenleri sorunlu döner (sessizce 0 sayılmaz)."""
    from .excel_ortak import sayi_cevir
    from .yukleme_guvenligi import sorunlu as sorunlu_satir
    sorunlu = []
    for a in _gider_sayi_hucreleri(ws):
        v = ws[a].value
        if v is None or isinstance(v, (int, float, Decimal)) and not isinstance(v, bool):
            continue
        d, hata = sayi_cevir(v, a) if not isinstance(v, bool) else (None, f"{a}: sayı değil")
        if hata:
            sorunlu.append(sorunlu_satir(int("".join(c for c in a if c.isdigit())), None, a, v, hata))
            ws[a].value = None
        else:
            ws[a].value = d
    return sorunlu


def gider_onizle(s: Session, senaryo_id: int, dosya_yolu: Path) -> dict:
    from .yukleme_guvenligi import ozet
    hesap_servisi.senaryo_getir(s, senaryo_id)
    wb = _kitap_ac(dosya_yolu, SAYFA_GIDER)
    _gider_duzen_kontrol(wb[SAYFA_GIDER])
    sorunlu = _gider_sayilarini_cevir(wb[SAYFA_GIDER])
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
    silinecek = sum(1 for ad in eski_ad if ad not in yeni_ad) if yeni_amb else 0
    uyarilar = []
    if silinecek:
        uyarilar.append(f"Dosyada olmayan {silinecek} ambalaj sınıfı silinecek.")
    if sorunlu:
        uyarilar.append("Sayıya çevrilemeyen hücreler var; düzeltilmeden uygulanamaz.")
    n_havuz_degisen = sum(1 for x in havuz if x["degisti"])
    out = {"havuz": havuz, "ambalaj": {"eski_adet": len(eski_amb), "yeni_adet": len(yeni_amb), "degisen": degisen},
           "_yeni": yeni, "_yeni_ambalaj": yeni_amb, "_sorunlu": sorunlu, "_silinecek": silinecek}
    out["ozet"] = ozet(okunan=len(havuz) + len(yeni_amb), yeni=sum(1 for x in havuz if x["eski_toplam"] is None)
                       + sum(1 for a in yeni_amb if a.ad not in eski_ad),
                       degisen=n_havuz_degisen + len({d["ad"] for d in degisen if d["alan"] != "sinif"}),
                       ayni=len(havuz) - n_havuz_degisen, silinecek=silinecek, sorunlu_satirlar=sorunlu, uyarilar=uyarilar)
    return out


def gider_uygula(s: Session, senaryo_id: int, dosya_yolu: Path, neden: str, kullanici: str = "sistem", onay: bool = False,
                 kaynak_dosya: str | None = None) -> dict:
    """Değişen havuzları ve (değiştiyse) ambalaj tablosunu yazar. Ambalaj tablosu dosyadakiyle DEĞİŞTİRİLİR: dosyada mevcut sınıfların
    yarısından azı varsa onaysız 409 `satir_kaybi_onayi`. Sayıya çevrilemeyen hücre varsa 422 (hiçbir şey yazılmaz). Yazmadan önce yedek."""
    from .excel_ortak import satir_kaybi_denetle
    from .yukleme_guvenligi import ambalaj_icerik, havuz_icerik
    neden = _neden_kontrol(neden)
    on = gider_onizle(s, senaryo_id, dosya_yolu)
    if on["_sorunlu"]:
        raise DogrulamaHatasi("Gider Dağıtım sayfasında sayıya çevrilemeyen hücreler var; hiçbir şey yazılmadı.",
                              {"hucreler": ", ".join(x["alan"] for x in on["_sorunlu"])}, kod="sorunlu_hucre")
    amb = on["ambalaj"]
    if on["_yeni_ambalaj"] and (amb["degisen"] or amb["eski_adet"] != amb["yeni_adet"]):
        satir_kaybi_denetle(amb["eski_adet"], amb["yeni_adet"], onay, "ambalaj sınıfı")
    yeni = on["_yeni"]
    for kod, y in yeni.items():   # yazmadan önce doğrula: kısmi yazım olmasın
        if y["baz_tipi"] in ("saniye", "adet") and not y["anahtarlar"] and kod not in gider_servisi.AMBALAJ_BAZLI and (y["baz"] is None or y["baz"] <= 0):
            raise DogrulamaHatasi(f"{y['ad']}: dağıtım bazı (saniye/adet) 0'dan büyük olmalı.", {"kod": kod})
    yazilan = [h["kod"] for h in on["havuz"] if h["degisti"]]
    amb_degisecek = bool(on["_yeni_ambalaj"] and (amb["degisen"] or amb["eski_adet"] != amb["yeni_adet"]))
    if yazilan or amb_degisecek:
        mevcut = gider_servisi.havuzlar(s, senaryo_id)
        veri = {"havuzlar": {kod: (havuz_icerik(mevcut[kod]) if kod in mevcut else None) for kod in yazilan}}
        if amb_degisecek:
            veri["ambalaj"] = ambalaj_icerik(gider_servisi.ambalajlar(s, senaryo_id))
        _yedek_on(s, "gider_dagitim", senaryo_id, veri, f"{len(yazilan)} havuz" + (", ambalaj tablosu" if amb_degisecek else ""),
                  kaynak_dosya, kullanici)
    for kod in yazilan:
        y = yeni[kod]
        gider_servisi.havuz_kaydet(s, senaryo_id, kod, y["ad"], y["toplam"], y["baz_tipi"], y["baz"], y["anahtarlar"], kullanici, neden=neden,
                                   taban_tutar=y["taban"], carpanlar=y["carpanlar"])
    amb_yazilan = 0
    if amb_degisecek:
        gider_servisi.ambalaj_kaydet(s, senaryo_id, [(a.ad, a.hacim, a.uretim_adedi, a.katsayi) for a in on["_yeni_ambalaj"]], kullanici, neden=neden)
        amb_yazilan = len(on["_yeni_ambalaj"])
    return {"havuz": len(yazilan), "ambalaj": amb_yazilan, "havuz_kodlari": yazilan}
