"""Maliyet muhasebesi (SMM): aylık SMM Excel'inin yüklenmesi ve stok/envanter hesabı (Excel TABLO sayfasının mantığı).

Stok hesabı, malzeme başına:
    toplam miktar   = dönem başı + alım                 toplam tutar = dönem başı tutar + alım tutarı + finansman payı
    ortalama fiyat  = toplam tutar / toplam miktar      (dönem ağırlıklı ortalama; Excel'deki "hareketli maliyet")
    kalan           = toplam − iade                     dönem sonu stok (DSS) = sayım miktarı × ortalama fiyat
    sarf            = kalan miktar − sayım              sarf maliyeti = sarf × ortalama fiyat; üretime giden = sarf maliyeti + iade tutarı
Finansman payı alım tutarı oranında dağıtılır. Tutarlar Decimal."""
import io
import re
from datetime import datetime, timezone
import zipfile
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, object_session
from ..depo import modeller as m
from .donusum import decimal_str
from .hatalar import BulunamadiHatasi, CatismaHatasi, DogrulamaHatasi, KilitliHatasi

SIFIR = Decimal(0)
ZORUNLU_SAYFALAR = ("DBS", "HM-YM ALIŞ SATIŞ", "DSS", "TABLO")
ASAMA_SAYFALARI = {20: ("20 KOD", 23), 40: ("40 KOD", 31), 50: ("50 KOD", 25)}   # sayfa, fire oranı sütun indeksi (0 tabanlı)
# Aşama sayfalarının 1. satırındaki dağıtım havuzları (0 tabanlı sütun): 20 KOD P1/S1, 40 KOD P1/U1/Z1/AC1, 50 KOD P1/U1.
HAVUZ_HUCRELERI = {
    20: {"20_stok": 15, "20_uretim": 18},
    40: {"40_stok_iscilik": 15, "40_iscilik": 20, "40_stok_gug": 25, "40_gug": 28},
    50: {"50_stok": 15, "50_uretim": 20},
}
BIRIM_SUTUNU = {20: 20, 40: 22, 50: 22}   # Excel'in aşama birim maliyeti: 20 KOD U, 40 KOD W, 50 KOD W
MAKS_BAYT = 60 * 1024 * 1024
AY_ADLARI = ("", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık")
_DOSYA_DONEMI = re.compile(r"(?<!\d)(\d{1,2})[-_. ](\d{4})(?!\d)")


def _d(x) -> Decimal:
    if x is None or x == "":
        return SIFIR
    if isinstance(x, Decimal):
        return x
    try:
        return Decimal(str(x))
    except (InvalidOperation, ValueError):
        return SIFIR


def _metin(x) -> str | None:
    s = str(x).strip() if x is not None else ""
    return s or None


def donem_adi(d: m.SmmDonem) -> str:
    return f"{AY_ADLARI[d.ay]} {d.yil}"


def dosyadan_donem(dosya_adi: str) -> tuple[int, int] | None:
    """'09-2026 SMM v1.xlsx' -> (2026, 9)."""
    e = _DOSYA_DONEMI.search(dosya_adi or "")
    if not e:
        return None
    ay, yil = int(e.group(1)), int(e.group(2))
    return (yil, ay) if 1 <= ay <= 12 else None


# ---------------------------------------------------------------- hesap
def stok_hesabi(k: m.SmmKalem, finansman: Decimal, alim_toplam: Decimal) -> dict:
    """Bir kalemin TABLO satırı (bkz. modül açıklaması)."""
    fin = (k.alim_tutar / alim_toplam * finansman) if alim_toplam and finansman else SIFIR
    top_miktar = k.dbs_miktar + k.alim_miktar
    top_tutar = k.dbs_tutar + k.alim_tutar + fin
    ort = top_tutar / top_miktar if top_miktar else SIFIR
    kalan_miktar = top_miktar - k.iade_miktar
    kalan_tutar = top_tutar - k.iade_tutar
    dss_tutar = k.sayim_miktar * ort
    sarf = kalan_miktar - k.sayim_miktar
    sarf_tutar = sarf * ort
    return {"finansman_payi": fin, "toplam_miktar": top_miktar, "toplam_tutar": top_tutar, "ortalama_fiyat": ort,
            "kalan_miktar": kalan_miktar, "kalan_tutar": kalan_tutar, "dss_tutar": dss_tutar, "sarf_miktar": sarf,
            "sarf_tutar": sarf_tutar, "uretime_giden": sarf_tutar + k.iade_tutar,
            # sayım, eldekinden (dönem başı + alım + üretim girişi − iade) fazlaysa: kayıt eksik ya da sayım hatası. Üretilen yarı mamul/mamulde
            # üretim girişi bu tabloda (Excel TABLO gibi) maliyete girmez, aşama maliyetiyle gelir; kontrolde ise miktar olarak sayılır.
            "kontrol": kalan_miktar + k.uretim_miktar - k.sayim_miktar < 0}


def _alim_toplami(s: Session, donem_id: int) -> Decimal:
    return s.scalar(select(func.coalesce(func.sum(m.SmmKalem.alim_tutar), 0)).where(m.SmmKalem.donem_id == donem_id)) or SIFIR


def kilit_denetle(d: m.SmmDonem) -> None:
    """Kapanmış (kilitli) dönemde değişiklik yapılamaz."""
    if d.kilitli:
        raise KilitliHatasi(f"{donem_adi(d)} dönemi kilitli; değişiklik için önce kilidi açın", {"donem_id": d.id}, kod="donem_kilitli")


def donem_getir(s: Session, donem_id: int) -> m.SmmDonem:
    d = s.get(m.SmmDonem, donem_id)
    if d is None:
        raise BulunamadiHatasi("dönem bulunamadı", {"donem_id": donem_id})
    return d


def stok_tablosu(s: Session, donem_id: int, tur: str | None = None, arama: str | None = None, yalniz_hareketli: bool = True,
                 yalniz_kontrol: bool = False) -> dict:
    """Dönemin stok/envanter tablosu: süzülmüş kalemler, tür listesi ve TÜM dönemin toplamları (süzgeçten bağımsız)."""
    d = donem_getir(s, donem_id)
    kalemler = list(s.scalars(select(m.SmmKalem).where(m.SmmKalem.donem_id == d.id).order_by(m.SmmKalem.kod)))
    alim_toplam = sum((k.alim_tutar for k in kalemler), SIFIR)
    toplam = defaultdict(lambda: SIFIR)
    tur_ozet: dict[str, dict] = {}
    satirlar = []
    q = _tr((arama or "").strip())
    for k in kalemler:
        h = stok_hesabi(k, d.finansman, alim_toplam)
        for a in ("dbs_tutar", "alim_tutar", "iade_tutar"):
            toplam[a] += getattr(k, a)
        for a in ("finansman_payi", "dss_tutar", "sarf_tutar", "uretime_giden"):
            toplam[a] += h[a]
        t = k.tur or "Diğer"
        o = tur_ozet.setdefault(t, {"tur": t, "kalem": 0, "dbs_tutar": SIFIR, "alim_tutar": SIFIR, "dss_tutar": SIFIR, "sarf_tutar": SIFIR})
        o["kalem"] += 1; o["dbs_tutar"] += k.dbs_tutar; o["alim_tutar"] += k.alim_tutar; o["dss_tutar"] += h["dss_tutar"]; o["sarf_tutar"] += h["sarf_tutar"]
        # Dönemde stok hareketi (dönem başı, alım, iade, sayım) olmayan kalem varsayılan listede gösterilmez; yıllık üretim tek başına hareket sayılmaz.
        hareketli = any((k.dbs_miktar, k.alim_miktar, k.iade_miktar, k.sayim_miktar))
        if yalniz_hareketli and not hareketli:
            continue
        if tur and t != tur:
            continue
        if yalniz_kontrol and not h["kontrol"]:
            continue
        if q and q not in _tr(k.kod) and q not in _tr(k.ad):
            continue
        satirlar.append({"kod": k.kod, "ad": k.ad, "birim": k.birim, "tur": k.tur, "mizan_kodu": k.mizan_kodu,
                         "dbs_miktar": k.dbs_miktar, "dbs_tutar": k.dbs_tutar, "alim_miktar": k.alim_miktar, "alim_tutar": k.alim_tutar,
                         "iade_miktar": k.iade_miktar, "iade_tutar": k.iade_tutar, "uretim_miktar": k.uretim_miktar,
                         "sayim_miktar": k.sayim_miktar, "satis_miktar": k.satis_miktar or SIFIR, "sahit_miktar": k.sahit_miktar or SIFIR,
                         **h})
    return decimal_str({
        "donem": donem_cikis(d, len(kalemler)),
        "toplamlar": {a: toplam[a] for a in ("dbs_tutar", "alim_tutar", "finansman_payi", "iade_tutar", "dss_tutar", "sarf_tutar", "uretime_giden")},
        "kontrol_sayisi": sum(1 for k in kalemler if stok_hesabi(k, d.finansman, alim_toplam)["kontrol"]),
        "turler": sorted(tur_ozet.values(), key=lambda x: x["tur"]),
        "kayitlar": satirlar,
    })


def kilit_zamani(d: m.SmmDonem) -> str | None:
    """Dönemin kapatıldığı an (son 'kilitle' değişiklik kaydı, UTC ISO 8601); dönem açık ya da kayıt yoksa None."""
    s = object_session(d)
    if not d.kilitli or s is None or d.id is None:
        return None
    z = s.scalar(select(m.DegisiklikKaydi.zaman).where(m.DegisiklikKaydi.tablo == "smm_donem", m.DegisiklikKaydi.kayit_id == d.id,
                                                       m.DegisiklikKaydi.islem == "kilitle").order_by(m.DegisiklikKaydi.id.desc()).limit(1))
    return z.replace(tzinfo=timezone.utc).isoformat(timespec="seconds") if z else None


def donem_cikis(d: m.SmmDonem, kalem_sayisi: int | None = None) -> dict:
    return decimal_str({"id": d.id, "yil": d.yil, "ay": d.ay, "ad": donem_adi(d), "kaynak_dosya": d.kaynak_dosya, "finansman": d.finansman,
                        "kalem_sayisi": kalem_sayisi, "excel_kontrol": d.excel_kontrol, "olusturan": d.olusturan,
                        "recete_kaynagi": d.recete_kaynagi or "excel", "devir_donem_id": d.devir_donem_id,
                        "kilitli": bool(d.kilitli), "kilitleyen": d.kilitleyen, "kilit_zamani": kilit_zamani(d)})


def donemler(s: Session) -> list[dict]:
    sayi = dict(s.execute(select(m.SmmKalem.donem_id, func.count()).group_by(m.SmmKalem.donem_id)).all())
    return [donem_cikis(d, sayi.get(d.id, 0)) for d in s.scalars(select(m.SmmDonem).order_by(m.SmmDonem.yil.desc(), m.SmmDonem.ay.desc()))]


def donem_sil(s: Session, donem_id: int, kullanici: str = "sistem") -> None:
    from .smm_veri_servisi import donem_yedeklerini_kapat, yedekleri_kapat
    d = donem_getir(s, donem_id)
    kilit_denetle(d)
    _temizle(s, d.id)
    from . import excel_sablon_deposu as esd
    esd.sil(s, "smm_donem", str(d.id))   # müşavir Excel'i şablonu dönemle gider (kimlik yeni döneme verilirse eskisi kullanılmasın)
    # dönemin yükleme yedekleri artık geri alınamaz (silinen dönemin kimliği yeni bir döneme verilirse eski yedek ona uygulanmasın)
    yedekleri_kapat(s, [YEDEK_ALANI], str(d.id))
    donem_yedeklerini_kapat(s, d.id)
    s.add(m.DegisiklikKaydi(tablo="smm_donem", kayit_id=d.id, islem="sil", eski={"donem": donem_adi(d), "kaynak_dosya": d.kaynak_dosya},
                            yeni=None, kullanici=kullanici))
    s.delete(d)
    s.flush()


def _temizle(s: Session, donem_id: int) -> None:
    for tablo in (m.SmmKalem, m.SmmReceteSatiri, m.SmmIscilik):
        s.execute(delete(tablo).where(tablo.donem_id == donem_id))


# ---------------------------------------------------------------- Excel'den yükleme
def _sayfa(wb, ad: str, bas: int = 3):
    return wb[ad].iter_rows(min_row=bas, values_only=True)


def _hucre(r, i):
    return r[i] if len(r) > i else None


def _sayfa_bulucu(wb):
    """Beklenen sayfa adı -> dosyadaki ad (büyük/küçük, Türkçe harf, boşluk farkı önemsiz); yoksa None."""
    from .excel_ortak import baslik_anahtari
    harita: dict[str, str] = {}
    for a in wb.sheetnames:
        harita.setdefault(baslik_anahtari(a), a)
    return lambda ad: ad if ad in wb.sheetnames else harita.get(baslik_anahtari(ad))


def _sablon_degil(wb) -> None:
    """Aylık kaynak şablonu (10-16) ya da başka bir şablon dönem Excel'i yerine seçilmişse anlaşılır red."""
    from .excel_ortak import SABLONLAR, sablon_kimligi_oku
    k = sablon_kimligi_oku(wb)
    if k is not None:
        raise DogrulamaHatasi(f"Bu dosya {SABLONLAR.get(k[0], k[0])} şablonu; burası SMM dönem Excel'i yüklemesi. Aylık kaynakları Veri Girişi'nde "
                              f"ilgili satırdan yükleyin.", {"gelen_sablon": k[0]}, kod="yanlis_sablon")


def _sorunlu_tara(satirlar, sayfa: str, kod_i: int, sutunlar: dict[int, str], sorunlu: list[dict], bas: int = 3):
    """Satırları olduğu gibi geçirir; sayı sütununda metin olarak yazılmış hücreleri `sorunlu` listesine ekler. Değer okuma DEĞİŞMEZ
    (SMM Excel'i de bu hücreleri hesapta 0 sayar; uygulamanın hesabı Excel'in kendi TABLO'suyla kıyaslandığı için aynı kalır)."""
    for n, r in enumerate(satirlar):
        for i, alan in sutunlar.items():
            v = _hucre(r, i)
            if isinstance(v, str) and v.strip() and len(sorunlu) < 5000:
                try:
                    Decimal(v.strip())
                    continue
                except (InvalidOperation, ValueError):
                    pass
                sorunlu.append({"satir": bas + n, "kod": _metin(_hucre(r, kod_i)), "alan": f"{sayfa} · {alan}", "deger": v[:120],
                                "neden": "sayı sütununda metin; SMM Excel'i gibi 0 okundu. Hücreyi sayı yapıp yeniden yükleyin."})
        yield r


def excel_oku(icerik: bytes) -> dict:
    """SMM Excel'inin veri sayfalarını okur (formüller değil, Excel'in son hesapladığı değerler). Dönüş: ham kalemler, reçeteler, işçilik,
    finansman ve Excel'in kendi TABLO değerleri (karşılaştırma için)."""
    if len(icerik) > MAKS_BAYT:
        raise DogrulamaHatasi("dosya 60 MB'den büyük")
    try:
        wb = load_workbook(io.BytesIO(icerik), read_only=True, data_only=True)
    except (zipfile.BadZipFile, InvalidFileException, KeyError):
        raise DogrulamaHatasi("dosya geçerli bir .xlsx değil")
    try:
        _sablon_degil(wb)
        bul = _sayfa_bulucu(wb)   # sayfa adı esnek: 'HM-YM ALIŞ SATIŞ' = 'hm-ym alış satış'; '20 KOD' = '20KOD'
        eksik = [a for a in ZORUNLU_SAYFALAR if bul(a) is None]
        if eksik:
            raise DogrulamaHatasi(f"SMM Excel'inde beklenen sayfalar yok: {', '.join(eksik)}. Dosyadaki sayfalar: {', '.join(wb.sheetnames)}.",
                                  {"eksik_sayfalar": eksik, "beklenen": list(ZORUNLU_SAYFALAR), "sayfalar": list(wb.sheetnames)},
                                  kod="eksik_sayfa")
        sorunlu: list[dict] = []
        kalem: dict[str, dict] = {}

        def k(kod) -> dict | None:
            kod = _metin(kod)
            if not kod:
                return None
            return kalem.setdefault(kod, {"kod": kod, "ad": None, "birim": None, "tur": None, "mizan_kodu": None, "dbs_miktar": SIFIR,
                                          "dbs_tutar": SIFIR, "alim_miktar": SIFIR, "alim_tutar": SIFIR, "iade_miktar": SIFIR,
                                          "iade_tutar": SIFIR, "uretim_miktar": SIFIR, "sayim_miktar": SIFIR, "envanterde": False,
                                          "uretim_asamasi": None, "satis_miktar": SIFIR, "sahit_miktar": SIFIR})

        wbf = load_workbook(io.BytesIO(icerik), read_only=True, data_only=False)   # formüller: elle/standart dışı hücreleri bulmak için
        if bul("ENVANTER"):   # kart bilgisi: ad, birim, mizan adı ve kodu; P sütununun baktığı aşama sayfası
            for r, f in zip(_sayfa(wb, bul("ENVANTER")), _sayfa(wbf, bul("ENVANTER"))):
                if (x := k(_hucre(r, 0))):
                    p = str(_hucre(f, 15) or "")
                    asm = next((a for a, (ad, _) in ASAMA_SAYFALARI.items() if f"'{ad}'" in p), None)
                    x.update(ad=_metin(_hucre(r, 1)), birim=_metin(_hucre(r, 2)), tur=_metin(_hucre(r, 3)), mizan_kodu=_metin(_hucre(r, 4)),
                             envanterde=True, uretim_asamasi=x["uretim_asamasi"] or asm)
        for r in _sorunlu_tara(_sayfa(wb, bul("DBS")), bul("DBS"), 0, {2: "miktar", 3: "tutar"}, sorunlu):
            if (x := k(_hucre(r, 0))):
                x["ad"] = x["ad"] or _metin(_hucre(r, 1))
                x["dbs_miktar"] += _d(_hucre(r, 2)); x["dbs_tutar"] += _d(_hucre(r, 3))
        for r in _sorunlu_tara(_sayfa(wb, bul("HM-YM ALIŞ SATIŞ")), bul("HM-YM ALIŞ SATIŞ"), 1, {6: "giriş miktarı", 10: "tutar",
                                                                                               11: "çıkış miktarı"}, sorunlu):
            if (x := k(_hucre(r, 1))):
                x["ad"] = x["ad"] or _metin(_hucre(r, 2)); x["birim"] = x["birim"] or _metin(_hucre(r, 5))
                x["alim_miktar"] += _d(_hucre(r, 6)); x["alim_tutar"] += _d(_hucre(r, 10))
                if _metin(_hucre(r, 19)) == "Satış":   # T 'Satış' ise L (çıkış miktarı) satılan miktar (Excel U sütunu)
                    x["satis_miktar"] += _d(_hucre(r, 11))
        if bul("İADELER"):
            for r in _sorunlu_tara(_sayfa(wb, bul("İADELER")), bul("İADELER"), 0, {7: "iade miktarı", 8: "iade tutarı"}, sorunlu):
                if (x := k(_hucre(r, 0))):
                    x["ad"] = x["ad"] or _metin(_hucre(r, 1))
                    x["iade_miktar"] += _d(_hucre(r, 7)); x["iade_tutar"] += _d(_hucre(r, 8))
        if bul("ÜRETİM"):   # O sütunu: yıl içi toplam üretim
            for r in _sorunlu_tara(_sayfa(wb, bul("ÜRETİM")), bul("ÜRETİM"), 0, {14: "üretim miktarı"}, sorunlu):
                if (x := k(_hucre(r, 0))):
                    x["ad"] = x["ad"] or _metin(_hucre(r, 1))
                    x["uretim_miktar"] += _d(_hucre(r, 14))
        excel_dss: dict[str, Decimal] = {}   # Excel'in sayım tutarı (DSS!E), karşılaştırma için
        for r in _sorunlu_tara(_sayfa(wb, bul("DSS")), bul("DSS"), 0, {2: "sayım miktarı"}, sorunlu):
            if (x := k(_hucre(r, 0))):
                x["ad"] = x["ad"] or _metin(_hucre(r, 1))
                x["sayim_miktar"] += _d(_hucre(r, 2))
                if isinstance(_hucre(r, 4), (int, float)):
                    excel_dss[x["kod"]] = excel_dss.get(x["kod"], SIFIR) + _d(_hucre(r, 4))
        if bul("ŞAHİT"):   # J: şahit numune toplam miktarı (sayımda yok)
            for r in _sorunlu_tara(_sayfa(wb, bul("ŞAHİT")), bul("ŞAHİT"), 0, {9: "toplam miktar"}, sorunlu):
                if (x := k(_hucre(r, 0))) and isinstance(_hucre(r, 9), (int, float)):
                    x["sahit_miktar"] += _d(_hucre(r, 9))
        stok_mizan, mizan_tarihi = [], None
        if bul("STOK MİZAN"):   # A hesap, B ad, G bakiye (yalnız 15x stok hesapları); J2 fiş tarihi
            ws = wb[bul("STOK MİZAN")]
            mizan_tarihi = _metin(next(ws.iter_rows(min_row=2, max_row=2, min_col=10, max_col=10, values_only=True), (None,))[0])
            for r in _sayfa(wb, bul("STOK MİZAN")):
                hesap = _metin(_hucre(r, 0))
                if hesap and hesap[:2] == "15" and isinstance(_hucre(r, 6), (int, float)):
                    stok_mizan.append({"hesap": hesap, "ad": _metin(_hucre(r, 1)), "bakiye": str(_d(_hucre(r, 6)))})

        receteler = []
        dagitim: dict[str, Decimal] = {}
        excel_asama: dict[str, dict[str, Decimal]] = {}
        asama_elle: dict[str, dict[str, dict]] = {}
        try:
            for asama, (ad, fire_i) in ASAMA_SAYFALARI.items():
                ad = bul(ad)
                if ad is None:
                    continue
                bas = next(wb[ad].iter_rows(min_row=1, max_row=1, values_only=True), ())
                for anahtar, i in HAVUZ_HUCRELERI[asama].items():
                    dagitim[anahtar] = _d(_hucre(bas, i))
                birim_i, birimler, onceki = BIRIM_SUTUNU[asama], {}, None
                excel_asama[str(asama)] = birimler
                elle = asama_elle.setdefault(str(asama), {})
                degerler = list(_sayfa(wb, ad))
                formuller = list(_sayfa(wbf, ad))
                standart = _standart_formuller(degerler, formuller)
                for n, r in enumerate(degerler):
                    f = formuller[n] if n < len(formuller) else ()
                    satir_no = n + 3
                    ana, mal = _metin(_hucre(r, 0)), _metin(_hucre(r, 4))
                    # Grubun ilk satırı (Excel'de J=YANLIŞ) ürünün birim maliyetini taşır; arama formülleri ilk eşleşmeyi kullanır.
                    if ana and ana != onceki:
                        if ana not in birimler and isinstance(_hucre(r, birim_i), (int, float)):
                            birimler[ana] = _d(_hucre(r, birim_i))
                        for alan, i in URUN_ELLE_SUTUNLARI.get(asama, {}).items():
                            v = _hucre(f, i)
                            if v is not None and not _formul_mu(v):
                                elle.setdefault(ana, {})[alan] = str(_d(v))
                    onceki = ana
                    if not ana or not mal:
                        continue
                    ozel = _ozel_hucreler(r, f, satir_no, standart)
                    if str(_hucre(r, 4)) != mal:
                        # Kodda baş/son boşluk: Excel'in arama formülleri kartı bulamaz, fiyat 0 olur. Excel'le aynı sonuç için işaretlenir.
                        ozel = {**(ozel or {}), "kod_bosluklu": "1"}
                    receteler.append({"asama": asama, "ana_kod": ana, "ana_ad": _metin(_hucre(r, 1)), "ana_miktar": _d(_hucre(r, 2)) or Decimal(1),
                                      "ana_birim": _metin(_hucre(r, 3)), "malzeme_kod": mal, "malzeme_ad": _metin(_hucre(r, 5)),
                                      "miktar": _d(_hucre(r, 6)), "birim": _metin(_hucre(r, 7)), "fire_orani": _d(_hucre(r, fire_i)),
                                      "ozel": ozel})
        finally:
            wbf.close()
        iscilik = []
        if bul("51"):
            for r in _sayfa(wb, bul("51")):
                kod = _metin(_hucre(r, 1)) or _metin(_hucre(r, 2))
                if not kod:
                    continue
                iscilik.append({"kod": kod, "mamul_kod": _metin(_hucre(r, 1)), "yari_mamul_kod": _metin(_hucre(r, 2)), "ad": _metin(_hucre(r, 3)), "vardiya_uretim": _d(_hucre(r, 9)), "dolum_isci": _d(_hucre(r, 11)),
                                "etiket_isci": _d(_hucre(r, 12)), "dolum_sn": _d(_hucre(r, 15)), "dolum_adam_sn": _d(_hucre(r, 16)),
                                "etiket_sn": _d(_hucre(r, 17)), "etiket_adam_sn": _d(_hucre(r, 18))})
        tablo_bas = next(wb[bul("TABLO")].iter_rows(min_row=1, max_row=1, values_only=True), ())
        finansman = _d(_hucre(tablo_bas, 9))
        # Excel'in kendi TABLO değerleri: kod -> (DBS miktar, alım tutarı, ort. fiyat, DSS tutarı, sarf miktarı, sarf maliyeti); boş hücre None
        # Aynı kod TABLO'da birden çok kez yazılmış olabilir: Excel'in arama formülleri ilk satırı kullanır; tekrarlar ayrıca raporlanır.
        excel_tablo, tekrar = {}, []
        for r in _sayfa(wb, bul("TABLO")):
            kod = _metin(_hucre(r, 1))
            if not kod:
                continue
            if kod in excel_tablo:
                tekrar.append(kod)
                continue
            excel_tablo[kod] = tuple(None if _hucre(r, i) is None else _d(_hucre(r, i)) for i in (3, 7, 14, 20, 21, 22))
        gider_mizan, gider_mizan_tum = {}, {}
        if bul("GİDER MİZAN"):   # 3 haneli hesaplar (710…781): bakiye (G sütunu); 720/730 aşama dağıtımı için ayrıca
            for r in _sayfa(wb, bul("GİDER MİZAN"), 1):
                hesap = _metin(_hucre(r, 0))
                if hesap and len(hesap) == 3 and hesap.isdigit() and hesap not in gider_mizan_tum:
                    gider_mizan_tum[hesap] = str(_d(_hucre(r, 6)))
                if hesap in ("720", "730") and hesap not in gider_mizan:
                    gider_mizan[hesap] = _d(_hucre(r, 6))
        return {"kalemler": kalem, "receteler": receteler, "iscilik": iscilik, "finansman": finansman, "excel_tablo": excel_tablo,
                "excel_tekrar": tekrar, "dagitim": dagitim, "excel_asama": excel_asama, "gider_mizan": gider_mizan, "asama_elle": asama_elle,
                "excel_ozet": {"dss": {kd: str(v) for kd, v in excel_dss.items()}, "stok_mizan": stok_mizan, "gider_mizan": gider_mizan_tum,
                               "mizan_tarihi": mizan_tarihi},
                "sorunlu": sorunlu, "sayfalar": [a for a in wb.sheetnames if a != "_sablon"]}
    finally:
        wb.close()


# Reçete satırında Excel formülü sayfanın standart formülünden sapabilecek sütunlar (0 tabanlı): I çarpan, K HM fiyatı, M YM fiyatı.
OZEL_SUTUNLAR = {"carpan": 8, "hm": 10, "ym": 12}
# Ürün satırında elle yazılabilen dağıtım anahtarları: 40 KOD AA (GÜG dolum saniyesi), 50 KOD T (toplam üretim süresi, sn).
URUN_ELLE_SUTUNLARI = {40: {"gug_sn": 26}, 50: {"sure": 19}}
_SON_BOLEN = re.compile(r"^(.*)/(\d+(?:\.\d+)?)$")


def _formul_mu(v) -> bool:
    return isinstance(v, str) and v.startswith("=")


def _normal(v, satir_no: int) -> str | None:
    """Formülü satırdan bağımsız biçime getirir (A12 -> A{r}, önceki satır A11 -> A{p}); formül değilse None."""
    if not _formul_mu(v):
        return None
    v = re.sub(rf"(?<=[A-Z]){satir_no}(?!\d)", "{r}", v.replace("$", "").replace(" ", ""))
    return re.sub(rf"(?<=[A-Z]){satir_no - 1}(?!\d)", "{p}", v)


def _standart_formuller(degerler: list, formuller: list) -> dict[str, str]:
    """Her özel sütun için reçete satırlarında en sık görülen (normalleştirilmiş) formül = sayfanın standardı."""
    sayac: dict[str, Counter] = {a: Counter() for a in OZEL_SUTUNLAR}
    for n, f in enumerate(formuller):
        r = degerler[n] if n < len(degerler) else ()
        if not _metin(_hucre(r, 4)):
            continue
        for alan, i in OZEL_SUTUNLAR.items():
            nf = _normal(_hucre(f, i), n + 3)
            if nf:
                sayac[alan][nf] += 1
    return {a: c.most_common(1)[0][0] for a, c in sayac.items() if c}


def _ozel_hucreler(r, f, satir_no: int, standart: dict[str, str]) -> dict | None:
    """Satırın standart formülden sapan hücreleri: elle değer ya da başka formül -> Excel'in hesapladığı değer sabitlenir;
    standart formülün sonuna '/N' eklenmişse bölen saklanır (girdi değişince yeniden hesaplanabilsin)."""
    ozel = {}
    for alan, i in OZEL_SUTUNLAR.items():
        std = standart.get(alan)
        if std is None:
            continue
        ham = _hucre(f, i)
        nf = _normal(ham, satir_no)
        if nf == std:
            continue
        if nf and alan == "hm" and (e := _SON_BOLEN.match(nf)) and e.group(1) in (std, f"({std[1:]})", f"={std[1:]}"):
            ozel["hm_bolen"] = e.group(2)
            continue
        if ham is None and alan == "carpan":
            continue
        ozel[alan] = str(_d(_hucre(r, i)))
    return ozel or None


def _tr(x: str | None) -> str:
    """Türkçe harf duyarlı küçük harf (İ->i, I->ı) — aramada 'BİBER' ile 'biber' eşleşsin."""
    return (x or "").replace("İ", "i").replace("I", "ı").lower()


def _yakin(a: Decimal, b: Decimal) -> bool:
    return abs(a - b) <= max(Decimal("0.01"), abs(b) * Decimal("0.000001"))


def excel_karsilastir(kalemler: list[m.SmmKalem], finansman: Decimal, excel_tablo: dict, tekrar: list[str] | None = None) -> dict:
    """Bizim hesabı Excel'in TABLO sayfasıyla kalem kalem karşılaştırır. Excel'de sarf formülü boş bırakılmış kalemler ayrıca sayılır."""
    alim_toplam = sum((k.alim_tutar for k in kalemler), SIFIR)
    esit = farkli = sarf_bos = 0
    farkli_ornek, sarf_bos_ornek = [], []
    sarf_bos_tutar = SIFIR
    for k in kalemler:
        ex = excel_tablo.get(k.kod)
        if ex is None:
            continue
        h = stok_hesabi(k, finansman, alim_toplam)
        bizim = (k.dbs_miktar, k.alim_tutar, h["ortalama_fiyat"], h["dss_tutar"], h["sarf_miktar"], h["sarf_tutar"])
        if ex[4] is None and h["sarf_miktar"] != 0:
            sarf_bos += 1; sarf_bos_tutar += h["sarf_tutar"]
            if len(sarf_bos_ornek) < 20:
                sarf_bos_ornek.append(k.kod)
            continue
        if all(e is None or _yakin(b, e) for b, e in zip(bizim, ex)):
            esit += 1
        else:
            farkli += 1
            if len(farkli_ornek) < 20:
                farkli_ornek.append(k.kod)
    return decimal_str({"karsilastirilan": esit + farkli + sarf_bos, "esit": esit, "farkli": farkli, "farkli_ornek": farkli_ornek,
                        "excelde_sarf_bos": sarf_bos, "excelde_sarf_bos_ornek": sarf_bos_ornek, "excelde_sarf_bos_tutar": sarf_bos_tutar,
                        "excelde_tekrar": sorted(set(tekrar or []))})


def _donem_belirle(dosya_adi: str, yil: int | None, ay: int | None) -> tuple[int, int]:
    if yil is None or ay is None:
        bulunan = dosyadan_donem(dosya_adi)
        if bulunan is None:
            raise DogrulamaHatasi("dönem (yıl ve ay) seçin; dosya adından çıkarılamadı", {"dosya": dosya_adi})
        yil, ay = yil or bulunan[0], ay or bulunan[1]
    if not (2000 <= yil <= 2100 and 1 <= ay <= 12):
        raise DogrulamaHatasi("dönem geçersiz", {"yil": yil, "ay": ay})
    return yil, ay


_KALEM_SAYILARI = ("dbs_miktar", "dbs_tutar", "alim_miktar", "alim_tutar", "iade_miktar", "iade_tutar", "uretim_miktar", "sayim_miktar",
                   "satis_miktar", "sahit_miktar")


def yukle_onizle(s: Session, icerik: bytes, dosya_adi: str, yil: int | None = None, ay: int | None = None) -> dict:
    """SMM Excel'i önizlemesi (yazmaz): dönem, kalem / reçete / süre sayıları; dönem varsa kalem bazında yeni / değişen / aynı / silinecek;
    sayı sütununda metin hücreler (sorunlu) ve uyarılar."""
    yil, ay = _donem_belirle(dosya_adi, yil, ay)
    veri = excel_oku(icerik)
    d = s.scalar(select(m.SmmDonem).where(m.SmmDonem.yil == yil, m.SmmDonem.ay == ay))
    yeni_k = veri["kalemler"]
    mevcut = {k.kod: k for k in s.scalars(select(m.SmmKalem).where(m.SmmKalem.donem_id == d.id))} if d is not None else {}
    yeni = degisen = ayni = 0
    for kod, x in yeni_k.items():
        e = mevcut.get(kod)
        if e is None:
            yeni += 1
        elif all(_d(getattr(e, a)) == _d(x.get(a)) for a in _KALEM_SAYILARI):
            ayni += 1
        else:
            degisen += 1
    silinecek = len(set(mevcut) - set(yeni_k))
    uyarilar = []
    if not yeni_k:
        uyarilar.append("Dosyada okunabilen kalem yok; bu dosya yüklenemez.")
    if d is not None:
        if d.kilitli:
            uyarilar.append(f"{donem_adi(d)} dönemi kapatılmış (kilitli); yüklenemez.")
        uyarilar.append(f"{donem_adi(d)} dönemi zaten var: yüklerseniz dönemin kalemleri, reçeteleri ve süreleri dosyadakilerle baştan "
                        f"yazılır; aylık kaynaklardan yüklenenler ve elle düzeltmeler kaybolur (Geri al ile önceki hâline dönebilirsiniz).")
        if mevcut and len(yeni_k) < len(mevcut) / 2:
            uyarilar.append(f"Dosyada {len(yeni_k)} kalem var, dönemde {len(mevcut)}; yüklemek için ayrıca onay istenecek.")
    if veri["sorunlu"]:
        uyarilar.append(f"{len(veri['sorunlu'])} sayı hücresi metin olarak yazılmış; SMM Excel'i gibi 0 okunur (sorunlu satırlara bakın).")
    if veri["excel_tekrar"]:
        uyarilar.append(f"TABLO sayfasında {len(set(veri['excel_tekrar']))} kod birden çok kez geçiyor; Excel ilk satırı kullanır.")
    return decimal_str({"okunan": len(yeni_k), "yeni": yeni, "degisen": degisen, "ayni": ayni, "silinecek": silinecek, "atlanan": 0,
                        "sorunlu": veri["sorunlu"], "uyarilar": uyarilar, "yil": yil, "ay": ay, "donem_ad": f"{AY_ADLARI[ay]} {yil}",
                        "mevcut_donem_id": d.id if d is not None else None, "kilitli": bool(d is not None and d.kilitli),
                        "kalem": len(yeni_k), "mevcut_kalem": len(mevcut), "recete_satiri": len(veri["receteler"]), "iscilik": len(veri["iscilik"]),
                        "sayfalar": veri["sayfalar"]})


YEDEK_ALANI = "smm_donem_excel"
_DONEM_YEDEK_HARIC = ("id", "yil", "ay", "olusturma_zamani", "olusturan", "kilitli", "kilitleyen")


def _donem_yedegi(s: Session, d: m.SmmDonem | None) -> dict:
    """Üzerine yazmadan önce dönemin tamamı (dönem alanları + kalemler, reçete satırları, süreler); yeni dönem için {"yeni": true}."""
    from .smm_excel_okuyucu import satir_json
    if d is None:
        return {"yeni": True}
    return {"yeni": False, "donem": satir_json(d, _DONEM_YEDEK_HARIC),
            **{ad: [satir_json(x, ("id", "donem_id")) for x in s.scalars(select(tablo).where(tablo.donem_id == d.id).order_by(tablo.id))]
               for ad, tablo in (("kalemler", m.SmmKalem), ("receteler", m.SmmReceteSatiri), ("iscilik", m.SmmIscilik))}}


def yukle(s: Session, icerik: bytes, dosya_adi: str, yil: int | None = None, ay: int | None = None, uzerine_yaz: bool = False,
          kullanici: str = "sistem", onay: bool = False) -> dict:
    """SMM Excel'ini dönem olarak yükler. Dönem verilmezse dosya adından (ör. '09-2026 …') çıkarılır. Dönem varsa `uzerine_yaz` gerekir;
    üzerine yazarken dosyadaki kalem dönemdekinin yarısından azsa `onay` da gerekir (409 `satir_kaybi_onayi`). Kalem yoksa 422 `bos_dosya`.
    Yazmadan önce dönemin önceki hâli yedeklenir (geri al)."""
    from .excel_ortak import satir_kaybi_denetle
    from . import yukleme_yedegi as yy
    yil, ay = _donem_belirle(dosya_adi, yil, ay)
    veri = excel_oku(icerik)
    d = s.scalar(select(m.SmmDonem).where(m.SmmDonem.yil == yil, m.SmmDonem.ay == ay))
    if d is not None and not uzerine_yaz:
        raise CatismaHatasi(f"{AY_ADLARI[ay]} {yil} dönemi zaten yüklü; üzerine yazmak için onaylayın", {"donem_id": d.id})
    if d is not None:
        kilit_denetle(d)
    mevcut_kalem = (s.scalar(select(func.count()).select_from(m.SmmKalem).where(m.SmmKalem.donem_id == d.id)) or 0) if d is not None else 0
    satir_kaybi_denetle(mevcut_kalem, len(veri["kalemler"]), onay, "kalem")
    yedek = _donem_yedegi(s, d)
    yeni = d is None
    if yeni:
        d = m.SmmDonem(yil=yil, ay=ay, olusturan=kullanici)
        s.add(d); s.flush()
    else:
        from .smm_veri_servisi import donem_yedeklerini_kapat
        donem_yedeklerini_kapat(s, d.id)   # aylık kaynak yedekleri eski veriye ait: geri alınamaz olur
        _temizle(s, d.id)
    yy.yedek_kaydet(s, YEDEK_ALANI, str(d.id), yedek, kaynak_dosya=dosya_adi, kullanici=kullanici,
                    ozet=f"SMM Excel'i: {len(veri['kalemler'])} kalem" + (" (yeni dönem)" if yeni else " (üzerine yazıldı)"))
    d.kaynak_dosya, d.finansman = (dosya_adi or "")[-200:] or None, veri["finansman"]
    d.dagitim = d.dagitim_excel = decimal_str(veri["dagitim"])
    d.gider_mizan = decimal_str(veri["gider_mizan"])
    d.excel_asama = decimal_str(veri["excel_asama"])
    d.asama_elle = veri["asama_elle"]
    d.excel_ozet = veri["excel_ozet"]
    zaman = datetime.now().isoformat(timespec="seconds")
    d.veri_kaynaklari = {k: {"dosya": d.kaynak_dosya, "zaman": zaman, "kullanici": kullanici, "satir": None, "excel": True}
                         for k in ("alim", "iade", "uretim", "sayim", "sahit", "gider_mizan", "stok_mizan")}
    kalemler = [m.SmmKalem(donem_id=d.id, **x) for x in veri["kalemler"].values()]
    s.add_all(kalemler)
    s.add_all(m.SmmReceteSatiri(donem_id=d.id, **x) for x in veri["receteler"])
    s.add_all(m.SmmIscilik(donem_id=d.id, **x) for x in veri["iscilik"])
    d.excel_kontrol = excel_karsilastir(kalemler, d.finansman, veri["excel_tablo"], veri["excel_tekrar"])
    s.add(m.DegisiklikKaydi(tablo="smm_donem", kayit_id=d.id, islem="toplu_yukle", eski=None, kullanici=kullanici,
                            yeni={"donem": donem_adi(d), "dosya": d.kaynak_dosya, "kalem": len(kalemler), "recete_satiri": len(veri["receteler"]),
                                  "uzerine_yazildi": not yeni, **({"sorunlu": len(veri["sorunlu"])} if veri["sorunlu"] else {}),
                                  **({"onayli_kayip": mevcut_kalem - len(kalemler)} if onay and len(kalemler) < mevcut_kalem else {})}))
    # Müşavir Excel'i için şablon: yüklenen dosyanın olduğu gibi kopyası (bkz. smm_musavir_excel_servisi)
    from . import excel_sablon_deposu as esd
    esd.kaydet(s, "smm_donem", str(d.id), dosya_adi, icerik, kullanici)
    s.flush()
    return donem_cikis(d, len(kalemler))


def son_yukleme(s: Session, donem_id: int) -> dict:
    from . import yukleme_yedegi as yy
    donem_getir(s, donem_id)
    return {"son": yy.yedek_ozeti(yy.son_yedek(s, YEDEK_ALANI, str(donem_id)))}


def son_yuklemeyi_geri_al(s: Session, donem_id: int, kullanici: str = "sistem") -> dict:
    """Dönem Excel'inin son yüklemesini geri alır: üzerine yazıldıysa dönem önceki hâline döner; yeni dönem açtıysa dönem silinir.
    Kapanmış dönemde 409; açılışını bu dönemden devralmış dönem varsa (yeni dönem silinemez) 409; geri alınacak yükleme yoksa 404."""
    from . import yukleme_yedegi as yy
    from .smm_excel_okuyucu import satirdan
    from .smm_veri_servisi import donem_yedeklerini_kapat, yedekleri_kapat
    d = donem_getir(s, donem_id)
    kilit_denetle(d)
    y = yy.son_yedek_zorunlu(s, YEDEK_ALANI, str(d.id))
    v = y.veri
    ad = donem_adi(d)
    if v.get("yeni"):
        devralan = s.scalar(select(m.SmmDonem).where(m.SmmDonem.devir_donem_id == d.id).limit(1))
        if devralan is not None:
            raise CatismaHatasi(f"{donem_adi(devralan)} açılışını bu dönemden devraldı; önce o dönemi silin", {"donem_id": devralan.id},
                                kod="devralan_donem_var")
        yy.geri_alindi_isaretle(s, y)
        donem_sil(s, d.id, kullanici)   # dönemin bütün yükleme yedeklerini de kapatır
        mesaj = f"{ad} dönemi silindi (Excel'den ilk kez yüklenmişti)."
    else:
        _temizle(s, d.id)
        for a, deger in v["donem"].items():
            setattr(d, a, Decimal(deger) if a == "finansman" and deger is not None else deger)
        for ad_, tablo in (("kalemler", m.SmmKalem), ("receteler", m.SmmReceteSatiri), ("iscilik", m.SmmIscilik)):
            for x in v[ad_]:
                r = satirdan(tablo, x)
                r.donem_id = d.id
                s.add(r)
        yy.geri_alindi_isaretle(s, y)
        yedekleri_kapat(s, [YEDEK_ALANI], str(d.id))
        donem_yedeklerini_kapat(s, d.id)
        mesaj = f"{ad} SMM Excel'i yüklemesinden önceki hâline döndü."
    s.add(m.DegisiklikKaydi(tablo="smm_donem", kayit_id=donem_id, islem="yukleme_geri_al", eski=None, kullanici=kullanici,
                            yeni={"donem": ad, "geri_alinan": y.ozet, "dosya": y.kaynak_dosya, "donem_silindi": bool(v.get("yeni"))}))
    s.flush()
    return {"geri_alinan": yy.yedek_ozeti(y), "mesaj": mesaj}
