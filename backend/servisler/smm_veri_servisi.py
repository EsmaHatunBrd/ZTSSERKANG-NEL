"""Maliyet muhasebesi: aylık veri girişi (kaynak bazında yükleme ve elle düzeltme) ve dönem kapanışı (kilit, fiş Excel'i).

Kaynaklar bugünkü SMM Excel'inin sayfa biçimlerini ve şablonları (sablonlar/11-16-2026-10..16) okur; Canias rapor örnekleri gelince
TANIMLAR'daki eş anlamlılara eklenir. Dosya, ilgili sayfayı içeren bir SMM Excel'i de olabilir, tek sayfalık bir rapor da: sayfa adı
esnek aranır (büyük/küçük, Türkçe harf, boşluk), yoksa tek veri sayfası okunur; başlık ilk 30 satırda adla (eş anlamlılarla) aranır,
bulunamayan sütun SMM Excel düzenindeki yerinden okunur (uyarıyla). Bkz. smm_excel_okuyucu.

Yükleme güvenliği: önce önizleme (`kaynak_onizle`: yeni / değişen / aynı / silinecek, sorunlu satırlar); okunabilen satır yoksa red
(mevcut veri DEĞİŞMEZ); mevcut verinin yarısından azı gelirse `onay` olmadan yazılmaz (409 `satir_kaybi_onayi`). Sayıya çevrilemeyen
hücre 0 sayılmaz: satır sorunlu listelenir ve yazılmaz. Yazmadan önce o kaynağın dönemdeki verisi yedeklenir; `son_yuklemeyi_geri_al`
bir önceki hâli birebir geri yazar. Bir kaynak yüklenince o kaynağın alanları dönemin tüm kalemlerinde sıfırlanıp dosyadakilerle yazılır."""
import io
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from openpyxl import Workbook
from openpyxl.styles import Font
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..depo import modeller as m
from . import smm_excel_okuyucu as eo
from . import yukleme_yedegi as yy
from .donusum import decimal_str
from .excel_ortak import baslik_anahtari, satir_kaybi_denetle, sayi_cevir
from .hatalar import CatismaHatasi, DogrulamaHatasi
from .smm_mizan_servisi import elle_sayisi, elle_uyarisi
from .smm_servisi import MAKS_BAYT, SIFIR, _d, _metin, donem_adi, donem_cikis, donem_getir, kilit_denetle

# kaynak -> ad, şablon kimliği, sıfırlanacak kalem alanları
KAYNAKLAR = {
    "alim": {"ad": "Alım ve satış", "sablon": "smm_alim_satis", "alanlar": ("alim_miktar", "alim_tutar", "satis_miktar")},
    "iade": {"ad": "Alım iadeleri", "sablon": "smm_iadeler", "alanlar": ("iade_miktar", "iade_tutar")},
    "uretim": {"ad": "Üretim miktarları", "sablon": "smm_uretim", "alanlar": ("uretim_miktar",)},
    "sayim": {"ad": "Sayım (dönem sonu stok)", "sablon": "smm_sayim", "alanlar": ("sayim_miktar",)},
    "sahit": {"ad": "Şahit numune", "sablon": "smm_sahit_numune", "alanlar": ("sahit_miktar",)},
    "gider_mizan": {"ad": "Gider mizanı (720 / 730)", "sablon": "smm_gider_mizani", "alanlar": ()},
    "stok_mizan": {"ad": "Stok mizanı (150 / 151 / 152)", "sablon": "smm_stok_mizani", "alanlar": ()},
}
ZORUNLU = ("alim", "uretim", "sayim", "gider_mizan")   # bunlar olmadan SMM hesabı anlamsız
MIZANLAR = ("gider_mizan", "stok_mizan")

# ---------------------------------------------------------------- dosya tanımları (Canias raporu gelince: eş anlamlıyı buraya ekleyin)
S = eo.Sutun
_AD = ("Malzeme Açıklaması", "Açıklama", "Malzeme Adı", "Stok Adı", "Stok Kartı Adı", "StokKartıAdı", "StokAdı", "Ürün Adı", "Ad")
_BIRIM = ("Birim", "Birimi", "Stok Birimi", "Ölçü Birimi", "Ölçü Br")
_MIZAN = [S("hesap", ("Hesap Kodu", "Hesap No", "Hesap Numarası", "Hesap"), konum=0),
          S("ad", ("Hesap Adı", "Hesap Açıklaması", "Açıklama"), zorunlu=False, konum=1),
          S("bakiye", ("Bakiye", "Bakiye (TL)", "Bakiye TL", "Net Bakiye", "Bakiye Tutarı"), konum=6)]
TANIMLAR: dict[str, eo.Tanim] = {
    "alim": eo.Tanim("alim", "Alım ve satış", "smm_alim_satis", ("HM-YM ALIŞ SATIŞ", "ALIŞ SATIŞ", "HM-YM ALIS SATIS"), [
        S("kod", ("Malzeme(Sınıf)Kodu", "Malzeme Sınıf Kodu", "Malzeme Kodu", "Stok Kodu", "Stok Kartı Kodu"), konum=1),
        S("ad", _AD, zorunlu=False, konum=2),
        S("birim", _BIRIM, zorunlu=False, konum=5),
        S("giris", ("Giriş Miktarı", "Giren Miktar", "Giriş Miktar", "Alış Miktarı", "Alım Miktarı"), konum=6),
        S("tutar", ("Tutar (TL)", "Tutar TL", "TL Tutar", "Tutar", "Giriş Maliyeti", "Giriş Tutarı", "Alış Tutarı", "Alım Tutarı"), konum=10),
        S("cikis", ("Çıkış Miktarı", "Çıkan Miktar", "Çıkış Miktar", "Satış Miktarı"), zorunlu=False, konum=11),
        S("tur", ("Hareket Türü", "Hareket Tipi", "İşlem Türü", "Fiş Türü", "Hareket", "Tür"), konum=19)]),
    "iade": eo.Tanim("iade", "Alım iadeleri", "smm_iadeler", ("İADELER", "İADE", "ALIM İADELERİ"), [
        S("kod", ("Malzeme (Sınıf) Kodu", "Malzeme Kodu", "Stok Kodu", "Stok Kartı Kodu"), konum=0),
        S("ad", _AD, zorunlu=False, konum=1),
        S("birim", _BIRIM, zorunlu=False, konum=4),
        S("miktar", ("İade Miktarı", "İade Miktar", "İade Edilen Miktar"), konum=7),
        S("tutar", ("İade Tutarı", "İade Tutar", "İade Tutarı (TL)"), konum=8)]),
    "uretim": eo.Tanim("uretim", "Üretim miktarları", "smm_uretim", ("ÜRETİM", "ÜRETİM MİKTARLARI"), [
        S("kod", ("MalzemeKodu", "Malzeme Kodu", "Mamul Kodu", "Ürün Kodu", "Stok Kodu"), konum=0),
        S("ad", _AD, zorunlu=False, konum=1),
        S("miktar", ("Üretim Miktarı", "Üretilen Miktar", "Üretim Miktar", "Yıl İçi Toplam", "Toplam Üretim"), konum=14)]),
    "sayim": eo.Tanim("sayim", "Sayım (dönem sonu stok)", "smm_sayim", ("DSS", "SAYIM", "DÖNEM SONU SAYIM"), [
        S("kod", ("StokKartıKodu", "Stok Kartı Kodu", "Stok Kodu", "Malzeme Kodu"), konum=0),
        S("ad", _AD, zorunlu=False, konum=1),
        S("miktar", ("Sayım Miktarı", "Sayılan Miktar", "Sayım Miktar", "Fiili Miktar", "Sayım"), konum=2)]),
    "sahit": eo.Tanim("sahit", "Şahit numune", "smm_sahit_numune", ("ŞAHİT", "ŞAHİT NUMUNE"), [
        S("kod", ("StokKodu", "Stok Kodu", "Stok Kartı Kodu", "Malzeme Kodu"), konum=0),
        S("ad", _AD, zorunlu=False, konum=1),
        S("miktar", ("Toplam Miktar", "Şahit Miktarı", "Şahit Numune Miktarı", "Numune Miktarı"), konum=9)]),
    "gider_mizan": eo.Tanim("gider_mizan", "Gider mizanı (720 / 730)", "smm_gider_mizani", ("GİDER MİZAN", "GİDER MİZANI"), _MIZAN,
                            kod="hesap"),
    "stok_mizan": eo.Tanim("stok_mizan", "Stok mizanı (150 / 151 / 152)", "smm_stok_mizani", ("STOK MİZAN", "STOK MİZANI"), _MIZAN,
                           kod="hesap"),
}
# Aynı düzendeki iki mizanı başlıktan ayırmak mümkün değil (içerikten ayrılır: 7xx / 15x); "başka kaynağın dosyası" denetiminde birbirine bakmazlar.
_DIGER = {k: [t for kk, t in TANIMLAR.items() if kk != k and not (k in MIZANLAR and kk in MIZANLAR)] for k in TANIMLAR}
# Kalem kaynaklarında satırın sayı alanları: (iç ad, kalem alanı)
_SAYILAR = {"alim": (("giris", "alim_miktar"), ("tutar", "alim_tutar"), ("cikis", "satis_miktar")), "iade": (("miktar", "iade_miktar"), ("tutar", "iade_tutar")),
            "uretim": (("miktar", "uretim_miktar"),), "sayim": (("miktar", "sayim_miktar"),), "sahit": (("miktar", "sahit_miktar"),)}


def _gecerli_kaynak(kaynak: str) -> dict:
    if kaynak not in KAYNAKLAR:
        raise DogrulamaHatasi(f"Bilinmeyen veri kaynağı: {kaynak}.", {"kaynak": kaynak, "gecerli": list(KAYNAKLAR)})
    return KAYNAKLAR[kaynak]


def _kalemler(s: Session, d: m.SmmDonem) -> dict[str, m.SmmKalem]:
    return {k.kod: k for k in s.scalars(select(m.SmmKalem).where(m.SmmKalem.donem_id == d.id))}


def _kaydet_kaynak(d: m.SmmDonem, kaynak: str, dosya: str | None, satir: int, kullanici: str) -> None:
    v = dict(d.veri_kaynaklari or {})
    v[kaynak] = {"dosya": (dosya or "")[-200:] or None, "zaman": datetime.now().isoformat(timespec="seconds"), "kullanici": kullanici,
                 "satir": satir, "excel": False}
    d.veri_kaynaklari = v


# ---------------------------------------------------------------- dosyayı okuma (yazmaz)
def _oku(icerik: bytes, kaynak: str) -> tuple[eo.Okunan, eo.Ozet]:
    t = TANIMLAR[kaynak]
    wb = eo.calisma_kitabi(icerik, MAKS_BAYT)
    try:
        o = eo.oku(wb, t, _DIGER[kaynak])
    finally:
        wb.close()
    ozet = eo.Ozet(okunan=len(o.satirlar), uyarilar=list(o.uyarilar))
    if baslik_anahtari(o.sayfa) not in {baslik_anahtari(a) for a in t.sayfalar}:
        ozet.uyarilar.insert(0, f"'{t.sayfalar[0]}' adlı sayfa yok; '{o.sayfa}' sayfası okundu.")
    return o, ozet


def _kalem_dosyasi(icerik: bytes, kaynak: str) -> tuple[dict[str, dict[str, Decimal]], dict[str, dict], eo.Ozet]:
    """Kalem kaynağı: kod -> {kalem alanı: toplam}; kod -> {ad, birim}; özet (okunan, atlanan, sorunlu, uyarılar)."""
    o, ozet = _oku(icerik, kaynak)
    toplam: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(lambda: SIFIR))
    adlar: dict[str, dict] = {}
    t = TANIMLAR[kaynak]
    for satir_no, r in o.satirlar:
        kod = eo.kod_metni(o.hucre(r, "kod"))
        degerler, hatali = {}, False
        for ic, alan in _SAYILAR[kaynak]:
            if ic not in o.sutun:
                continue
            ham = o.hucre(r, ic)
            v, hata = sayi_cevir(ham, t.sutun(ic).gorunen)
            if hata:
                ozet.sorun(satir_no, kod, t.sutun(ic).gorunen, ham, hata + "; satır yazılmadı")
                hatali = True
            elif v is not None:
                degerler[alan] = v
        if not kod:
            if degerler or hatali:
                ozet.atlanan += 1
                ozet.sorun(satir_no, None, t.sutun("kod").gorunen, None, "kod boş (toplam / ara satır olabilir); satır atlandı")
            else:
                ozet.okunan -= 1   # kodu da sayısı da olmayan satır (açıklama, boş görünen satır): sayılmaz
            continue
        if hatali:
            ozet.atlanan += 1
            continue
        dolu = bool(degerler)
        if kaynak == "alim":   # G ve K her satırda alıma; L yalnız hareket türü 'Satış' ('SATIŞ', 'Satis' de) olan satırda satışa
            satis = baslik_anahtari(o.hucre(r, "tur")) == "satis"
            degerler = {"alim_miktar": degerler.get("alim_miktar", SIFIR), "alim_tutar": degerler.get("alim_tutar", SIFIR),
                        **({"satis_miktar": degerler.get("satis_miktar", SIFIR)} if satis else {})}
        if not dolu:
            ozet.atlanan += 1
            ozet.sorun(satir_no, kod, t.sutun(_SAYILAR[kaynak][0][0]).gorunen, None, "miktar boş; satır atlandı")
            continue
        x = toplam[kod]
        for alan, v in degerler.items():
            x[alan] += v
        ad = _metin(o.hucre(r, "ad")) if "ad" in o.sutun else None
        birim = _metin(o.hucre(r, "birim")) if "birim" in o.sutun else None
        a = adlar.setdefault(kod, {})
        if ad and not a.get("ad"):
            a["ad"] = ad
        if birim and not a.get("birim"):
            a["birim"] = birim
    return {k: dict(v) for k, v in toplam.items()}, adlar, ozet


def _mizan_dosyasi(icerik: bytes, kaynak: str) -> tuple[list[dict], eo.Ozet]:
    """Mizan: [{hesap, ad, bakiye}] (gider: 3 haneli ana hesaplar, ilk geçen; stok: 15 ile başlayanlar)."""
    o, ozet = _oku(icerik, kaynak)
    t = TANIMLAR[kaynak]
    out, gorulen = [], set()
    okunan = 0
    for satir_no, r in o.satirlar:
        h = eo.kod_metni(o.hucre(r, "hesap"))
        if kaynak == "gider_mizan":
            uygun = bool(h) and len(h) == 3 and h.isdigit()
        else:
            uygun = bool(h) and h[:2] == "15"
        if not uygun:
            continue   # başka hesaplar ve alt hesaplar okunmaz (sayılmaz)
        okunan += 1
        ham = o.hucre(r, "bakiye")
        v, hata = sayi_cevir(ham, t.sutun("bakiye").gorunen)
        if hata or v is None:
            ozet.atlanan += 1
            ozet.sorun(satir_no, h, t.sutun("bakiye").gorunen, ham, (hata or "bakiye boş") + "; satır yazılmadı")
            continue
        if kaynak == "gider_mizan" and h in gorulen:
            continue   # aynı hesap iki kez: ilk satır geçerli (önceki davranış)
        gorulen.add(h)
        out.append({"hesap": h, "ad": _metin(o.hucre(r, "ad")) if "ad" in o.sutun else None, "bakiye": v})
    ozet.okunan = okunan
    return out, ozet


def _mevcut_kalem_degerleri(kalemler: dict[str, m.SmmKalem], kaynak: str) -> dict[str, dict[str, Decimal]]:
    alanlar = KAYNAKLAR[kaynak]["alanlar"]
    return {kod: {a: getattr(x, a) or SIFIR for a in alanlar} for kod, x in kalemler.items() if any(getattr(x, a) for a in alanlar)}


def _mevcut_mizan(d: m.SmmDonem, kaynak: str) -> dict[str, Decimal]:
    from .smm_mizan_servisi import satirlar as mizan_satirlari
    return {x["hesap"]: x["bakiye"] for x in mizan_satirlari(d, "gider" if kaynak == "gider_mizan" else "stok", isaretsiz=True)}


def _karsilastir(ozet: eo.Ozet, mevcut: dict[str, dict], yeni: dict[str, dict]) -> None:
    for kod, v in yeni.items():
        e = mevcut.get(kod)
        if e is None:
            ozet.yeni += 1
        elif all(_d(e.get(a)) == _d(v.get(a)) for a in set(e) | set(v)):
            ozet.ayni += 1
        else:
            ozet.degisen += 1
    ozet.silinecek = len(set(mevcut) - set(yeni))


def _hazirla(s: Session, d: m.SmmDonem, kaynak: str, icerik: bytes) -> dict:
    """Dosyayı okur, mevcut veriyle karşılaştırır. Yazmaz. Dönüş: özet + yazmak için gereken ara veriler."""
    if kaynak in MIZANLAR:
        satirlar, ozet = _mizan_dosyasi(icerik, kaynak)
        mevcut = _mevcut_mizan(d, kaynak)
        _karsilastir(ozet, {h: {"b": v} for h, v in mevcut.items()}, {x["hesap"]: {"b": x["bakiye"]} for x in satirlar})
        if kaynak == "gider_mizan" and satirlar and not ({"720", "730"} & {x["hesap"] for x in satirlar}):
            raise DogrulamaHatasi("Gider mizanında 720 / 730 hesapları bulunamadı.", {"hesaplar": [x["hesap"] for x in satirlar][:20]}, kod="mizan_hesap_yok")
        elle = elle_sayisi(d, kaynak)
        if elle:
            ozet.uyarilar.append(f"{elle} elle girilmiş / düzeltilmiş mizan satırı var; yükleme bunları siler (eski değerler günlükte kalır).")
        return {"ozet": ozet, "mizan": satirlar, "mevcut_sayi": len(mevcut), "yeni_sayi": len(satirlar), "elle": elle}
    toplam, adlar, ozet = _kalem_dosyasi(icerik, kaynak)
    kalemler = _kalemler(s, d)
    mevcut = _mevcut_kalem_degerleri(kalemler, kaynak)
    _karsilastir(ozet, mevcut, toplam)
    yeni_kalem = sorted(set(toplam) - set(kalemler))
    if yeni_kalem:
        ozet.uyarilar.append(f"{len(yeni_kalem)} kalem dönemde yok, yeni kart açılacak (türü / mizan kodu boş; SMM tablosuna girmesi için "
                             f"Stok ve Envanter'de türünü girin). Örnek: {', '.join(yeni_kalem[:5])}.")
        birimsiz = [k for k in yeni_kalem if not (adlar.get(k) or {}).get("birim")]
        if birimsiz and kaynak in ("alim", "iade"):
            ozet.uyarilar.append(f"{len(birimsiz)} yeni kalemin birimi boş. Örnek: {', '.join(birimsiz[:5])}.")
    if ozet.silinecek:
        ad = KAYNAKLAR[kaynak]["ad"].lower()
        ozet.uyarilar.append(f"{ozet.silinecek} kalemin {ad} değeri dosyada yok; yüklenirse sıfırlanır.")
    return {"ozet": ozet, "toplam": toplam, "adlar": adlar, "kalemler": kalemler, "mevcut_sayi": len(mevcut), "yeni_sayi": len(toplam),
            "yeni_kalem": len(yeni_kalem)}


def kaynak_onizle(s: Session, donem_id: int, kaynak: str, icerik: bytes) -> dict:
    """Yüklemeden önce: kaç kalem yeni / değişen / aynı / sıfırlanacak, sorunlu satırlar ve uyarılar. Hiçbir şey yazılmaz."""
    k = _gecerli_kaynak(kaynak)
    d = donem_getir(s, donem_id)
    kilit_denetle(d)
    h = _hazirla(s, d, kaynak, icerik)
    if not h["yeni_sayi"]:
        h["ozet"].uyarilar.insert(0, "Dosyada okunabilen satır yok; bu dosya yüklenemez (mevcut veri değişmez).")
    elif h["mevcut_sayi"] and h["yeni_sayi"] < h["mevcut_sayi"] / 2:
        h["ozet"].uyarilar.insert(0, f"Dosyada {h['yeni_sayi']} kayıt var, mevcut veride {h['mevcut_sayi']}; yüklemek için ayrıca onay istenecek.")
    return decimal_str({**h["ozet"].sozluk(), "kaynak": kaynak, "ad": k["ad"], "donem": donem_cikis(d), "mevcut": h["mevcut_sayi"],
                        "dosyadaki": h["yeni_sayi"], "elle_silinecek": h.get("elle", 0), "yeni_kalem": h.get("yeni_kalem", 0)})


def _yedek_alan(kaynak: str) -> str:
    return f"smm_mizan:{'gider' if kaynak == 'gider_mizan' else 'stok'}" if kaynak in MIZANLAR else f"smm_kaynak:{kaynak}"


def _yedek_verisi(d: m.SmmDonem, kaynak: str, kalemler: dict[str, m.SmmKalem] | None) -> dict:
    vk = (d.veri_kaynaklari or {}).get(kaynak)
    if kaynak in MIZANLAR:
        ozet = d.excel_ozet or {}
        parca = {a: ozet[a] for a in ("gider_mizan", "gider_mizan_ad", "stok_mizan") if a in ozet}
        return {"tur": "mizan", "kaynak": kaynak, "excel_ozet": parca, "mizan_elle": ozet.get("mizan_elle"), "gider_mizan": d.gider_mizan,
                "veri_kaynagi": vk, "veri_kaynagi_var": kaynak in (d.veri_kaynaklari or {})}
    alanlar = KAYNAKLAR[kaynak]["alanlar"]
    return {"tur": "kalem", "kaynak": kaynak, "veri_kaynagi": vk, "veri_kaynagi_var": kaynak in (d.veri_kaynaklari or {}),
            "kalemler": {kod: {**{a: (None if getattr(x, a) is None else str(getattr(x, a))) for a in alanlar}, "ad": x.ad, "birim": x.birim}
                         for kod, x in (kalemler or {}).items()}}


def kaynak_yukle(s: Session, donem_id: int, kaynak: str, icerik: bytes, dosya_adi: str, kullanici: str = "sistem", onay: bool = False) -> dict:
    """Kaynağı yazar. Okunabilen satır yoksa 422 `bos_dosya` (veri değişmez); mevcut verinin yarısından azı gelirse onaysız 409."""
    k = _gecerli_kaynak(kaynak)
    d = donem_getir(s, donem_id)
    kilit_denetle(d)
    h = _hazirla(s, d, kaynak, icerik)
    ozet: eo.Ozet = h["ozet"]
    ne = "hesap" if kaynak in MIZANLAR else "kalem"
    satir_kaybi_denetle(h["mevcut_sayi"], h["yeni_sayi"], onay, ne)
    yy.yedek_kaydet(s, _yedek_alan(kaynak), str(d.id), _yedek_verisi(d, kaynak, h.get("kalemler")),
                    ozet=f"{k['ad']}: {h['yeni_sayi']} {ne}" + (f", {len(ozet.sorunlu)} sorunlu satır" if ozet.sorunlu else ""),
                    kaynak_dosya=dosya_adi, kullanici=kullanici)
    okunan = h["yeni_sayi"]
    elle_silinen = h.get("elle", 0)
    if kaynak in MIZANLAR:
        ozet_d = dict(d.excel_ozet or {})
        isaret = dict(ozet_d.get("mizan_elle") or {})
        isaret.pop("gider" if kaynak == "gider_mizan" else "stok", None)
        ozet_d["mizan_elle"] = isaret
        if kaynak == "gider_mizan":
            hesaplar = {x["hesap"]: str(x["bakiye"]) for x in h["mizan"]}
            ozet_d["gider_mizan"] = hesaplar
            ozet_d.pop("gider_mizan_ad", None)
            d.gider_mizan = {x: hesaplar[x] for x in ("720", "730") if x in hesaplar}
        else:
            ozet_d["stok_mizan"] = [{"hesap": x["hesap"], "ad": x["ad"], "bakiye": str(x["bakiye"])} for x in h["mizan"]]
        d.excel_ozet = ozet_d
    else:
        kalemler = h["kalemler"]
        for x in kalemler.values():
            for a in k["alanlar"]:
                setattr(x, a, SIFIR)
        for kod, alanlar in h["toplam"].items():
            x = kalemler.get(kod)
            if x is None:
                x = m.SmmKalem(donem_id=d.id, kod=kod, envanterde=False, olusturan=kullanici, **{a: SIFIR for a in (
                    "dbs_miktar", "dbs_tutar", "alim_miktar", "alim_tutar", "iade_miktar", "iade_tutar", "uretim_miktar", "sayim_miktar")})
                s.add(x)
                kalemler[kod] = x
            for a, v in (h["adlar"].get(kod) or {}).items():
                if v and not getattr(x, a, None):
                    setattr(x, a, v)
            for a, v in alanlar.items():
                setattr(x, a, v)
    _kaydet_kaynak(d, kaynak, dosya_adi, okunan, kullanici)
    s.add(m.DegisiklikKaydi(tablo="smm_donem", kayit_id=d.id, islem="veri_yukle", eski=None, kullanici=kullanici,
                            yeni={"donem": donem_adi(d), "kaynak": k["ad"], "dosya": dosya_adi, "satir": okunan,
                                  **({"elle_silinen": elle_silinen} if elle_silinen else {}),
                                  **({"sorunlu": len(ozet.sorunlu)} if ozet.sorunlu else {}),
                                  **({"onayli_kayip": h["mevcut_sayi"] - h["yeni_sayi"]} if onay and h["yeni_sayi"] < h["mevcut_sayi"] else {})}))
    s.flush()
    return {**veri_durumu(s, donem_id), "yukleme": decimal_str({**ozet.sozluk(), "kaynak": kaynak, "ad": k["ad"]})}


# ---------------------------------------------------------------- son yüklemeyi geri al
def son_yukleme(s: Session, donem_id: int, kaynak: str) -> dict:
    _gecerli_kaynak(kaynak)
    donem_getir(s, donem_id)
    return {"son": yy.yedek_ozeti(yy.son_yedek(s, _yedek_alan(kaynak), str(donem_id)))}


def son_yuklemeyi_geri_al(s: Session, donem_id: int, kaynak: str, kullanici: str = "sistem") -> dict:
    """Kaynağın son yüklemesinden önceki hâlini birebir geri yazar. Kapanmış dönemde 409; geri alınacak yükleme yoksa 404."""
    k = _gecerli_kaynak(kaynak)
    d = donem_getir(s, donem_id)
    kilit_denetle(d)
    y = yy.son_yedek_zorunlu(s, _yedek_alan(kaynak), str(d.id))
    v = y.veri
    if v["tur"] == "mizan":
        ozet_d = dict(d.excel_ozet or {})
        for a in ("gider_mizan", "gider_mizan_ad", "stok_mizan"):
            ozet_d.pop(a, None)
        ozet_d.update(v["excel_ozet"])
        if v.get("mizan_elle") is None:
            ozet_d.pop("mizan_elle", None)
        else:
            ozet_d["mizan_elle"] = v["mizan_elle"]
        d.excel_ozet = ozet_d
        d.gider_mizan = v.get("gider_mizan")
    else:
        alanlar = k["alanlar"]
        eski = v["kalemler"]
        kalemler = _kalemler(s, d)
        silinen = []
        for kod, x in kalemler.items():
            e = eski.get(kod)
            if e is None:   # bu yüklemeyle açılmış kart: başka kaynaktan değeri yoksa silinir
                for a in alanlar:
                    setattr(x, a, SIFIR)
                if not any(getattr(x, a) for a in ("dbs_miktar", "dbs_tutar", "alim_miktar", "alim_tutar", "iade_miktar", "iade_tutar",
                                                    "uretim_miktar", "sayim_miktar", "satis_miktar", "sahit_miktar")):
                    s.delete(x)
                    silinen.append(kod)
                continue
            for a in alanlar:
                setattr(x, a, None if e.get(a) is None else Decimal(e[a]))
            x.ad, x.birim = e.get("ad"), e.get("birim")
    vk = dict(d.veri_kaynaklari or {})
    if v.get("veri_kaynagi_var"):
        vk[kaynak] = v.get("veri_kaynagi")
    else:
        vk.pop(kaynak, None)
    d.veri_kaynaklari = vk
    yy.geri_alindi_isaretle(s, y)
    yedekleri_kapat(s, [_yedek_alan(kaynak)], str(d.id))
    s.add(m.DegisiklikKaydi(tablo="smm_donem", kayit_id=d.id, islem="yukleme_geri_al", eski=None, kullanici=kullanici,
                            yeni={"donem": donem_adi(d), "kaynak": k["ad"], "geri_alinan": y.ozet, "dosya": y.kaynak_dosya}))
    s.flush()
    return {"geri_alinan": yy.yedek_ozeti(y), "mesaj": f"{k['ad']} son yüklemeden önceki hâline döndü."}


def yedekleri_kapat(s: Session, alanlar: list[str], kapsam: str) -> None:
    """Yedekleri geri alınamaz işaretler. Geri al tek adımdır (yalnız son yükleme): geri almadan sonra aynı alanın eski yedekleri de
    kapanır (ikinci geri al 404); dönem baştan yazılınca aylık kaynak yedekleri eskir."""
    for y in s.scalars(select(m.YuklemeYedegi).where(m.YuklemeYedegi.alan.in_(alanlar), m.YuklemeYedegi.kapsam == kapsam,
                                                     m.YuklemeYedegi.geri_alindi.is_(False))):
        y.geri_alindi = True
    s.flush()


def donem_yedeklerini_kapat(s: Session, donem_id: int) -> None:
    """Dönem baştan yazılınca (SMM Excel'i üzerine yazma / geri alma) aylık kaynak yedekleri eskir: geri alınamaz olarak işaretlenir."""
    yedekleri_kapat(s, [_yedek_alan(k) for k in KAYNAKLAR], str(donem_id))


def veri_durumu(s: Session, donem_id: int) -> dict:
    """Dönemin veri kontrol listesi: her kaynak yüklendi mi, kaç kalemde değer var, son kim yükledi; eksik zorunlular."""
    d = donem_getir(s, donem_id)
    kalemler = list(_kalemler(s, d).values())
    vk = d.veri_kaynaklari or {}
    ozet = d.excel_ozet or {}
    kaynaklar = []
    for kod, k in KAYNAKLAR.items():
        if k["alanlar"]:
            dolu = sum(1 for x in kalemler if any(getattr(x, a) for a in k["alanlar"]))
        elif kod == "gider_mizan":
            dolu = len(ozet.get("gider_mizan") or d.gider_mizan or {})
        else:
            dolu = len(ozet.get("stok_mizan") or [])
        son = vk.get(kod)
        elle = elle_sayisi(d, kod)
        kaynaklar.append({"kaynak": kod, "ad": k["ad"], "zorunlu": kod in ZORUNLU, "yuklendi": bool(son) or dolu > 0, "dolu": dolu,
                          "son": son, "elle": elle, "elle_uyari": elle_uyarisi(elle)})
    devir = d.devir_donem_id is not None or (d.kaynak_dosya is not None)
    dbs_dolu = sum(1 for x in kalemler if x.dbs_miktar or x.dbs_tutar)
    gm = d.gider_mizan or {}
    # Stok hesabı (150/151/152) bulunamayan hareketli kalemler SMM tablosuna girmez: tür / mizan kodu boş (ör. alım raporuyla ilk kez gelen kalem)
    from .smm_ozet_servisi import grup
    grupsuz = [x for x in kalemler if grup(x.tur, x.mizan_kodu) is None
               and (x.dbs_tutar or x.alim_tutar or x.iade_tutar or x.sayim_miktar)]
    from .smm_donem_servisi import devir_ozeti
    return decimal_str({
        "devir": devir_ozeti(s, d),   # açılış stoku devralınan dönemin şu anki kapanışıyla uyumlu mu (devir kaynağı yoksa None)
        "donem": donem_cikis(d, len(kalemler)),
        "donem_basi": {"kaynak": "devir" if d.devir_donem_id else ("excel" if d.kaynak_dosya else "yok"), "dolu": dbs_dolu,
                       "tutar": sum((x.dbs_tutar for x in kalemler), SIFIR), "hazir": devir or dbs_dolu > 0},
        "kaynaklar": kaynaklar,
        "eksik": [x["ad"] for x in kaynaklar if x["zorunlu"] and not x["yuklendi"]],
        "ayarlar": {"finansman": d.finansman or SIFIR, "gider_720": _d(gm.get("720")), "gider_730": _d(gm.get("730"))},
        "turler": sorted({x.tur for x in kalemler if x.tur}),
        "grupsuz": {"kalem": len(grupsuz), "alim_tutar": sum((x.alim_tutar or SIFIR for x in grupsuz), SIFIR),
                    "dbs_tutar": sum((x.dbs_tutar or SIFIR for x in grupsuz), SIFIR), "ornek": sorted(x.kod for x in grupsuz)[:10]},
    })


def ayarlar_guncelle(s: Session, donem_id: int, finansman: Decimal | None = None, gider_720: Decimal | None = None,
                     gider_730: Decimal | None = None, kullanici: str = "sistem") -> dict:
    """Finansman (alımlara dağıtılır) ve 720 / 730 gider tutarlarını elle girer."""
    d = donem_getir(s, donem_id)
    kilit_denetle(d)
    for ad, v in (("finansman", finansman), ("gider_720", gider_720), ("gider_730", gider_730)):
        if v is not None and v < 0:
            raise DogrulamaHatasi("Tutar eksi olamaz.", {ad: str(v)})
    eski = {"finansman": str(d.finansman or SIFIR), **{f"gider_{h}": (d.gider_mizan or {}).get(h) for h in ("720", "730")}}
    if finansman is not None:
        d.finansman = finansman
    gm = dict(d.gider_mizan or {})
    ozet = dict(d.excel_ozet or {})
    gmo = dict(ozet.get("gider_mizan") or {})
    isaret = dict(ozet.get("mizan_elle") or {})
    for h, v in (("720", gider_720), ("730", gider_730)):
        if v is not None:
            if h not in gmo or _d(gmo[h]) != v:
                isaret["gider"] = sorted(set(isaret.get("gider") or []) | {h})   # elle girilen tutar mizan satırında işaretlenir
            gm[h] = str(v)
            gmo[h] = str(v)
    ozet["mizan_elle"] = isaret
    d.gider_mizan = gm
    ozet["gider_mizan"] = gmo
    d.excel_ozet = ozet
    yeni = {"finansman": str(d.finansman or SIFIR), **{f"gider_{h}": gm.get(h) for h in ("720", "730")}}
    if eski != yeni:
        s.add(m.DegisiklikKaydi(tablo="smm_donem", kayit_id=d.id, islem="ayar_guncelle", eski=eski, yeni=yeni, kullanici=kullanici))
    s.flush()
    return veri_durumu(s, donem_id)


def _tl(x) -> str:
    """1234567.891 -> '1.234.567,89' (uyarı metinleri için)."""
    return f"{_d(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def kapanis_eksikleri(s: Session, donem_id: int) -> list[str]:
    """Dönem kapatılmadan önce giderilmesi beklenenler: yüklenmemiş zorunlu kaynak, türü boş kalem, açılış–önceki kapanış uyumsuzluğu."""
    v = veri_durumu(s, donem_id)
    eksikler = [f"Eksik veri: {ad}" for ad in v["eksik"]]
    if v["grupsuz"]["kalem"]:
        eksikler.append(f"{v['grupsuz']['kalem']} kalemin türü / mizan kodu boş; SMM tablosuna girmiyor")
    dv = v.get("devir")
    if dv and not dv["uyumlu"]:
        eksikler.append(f"Açılış stoku {dv['onceki_ad']} kapanışıyla uyuşmuyor ({dv['fark_kalem']} kalem, fark {_tl(dv['fark_tutar'])} TL)")
    return eksikler


def kilit(s: Session, donem_id: int, kilitli: bool, kullanici: str = "sistem", zorla: bool = False) -> dict:
    """Dönemi kapatır ya da kilidi açar. Kapatırken eksik varsa ve `zorla` değilse 409 `kapanis_eksik`. Kilidi açarken: açılışını bu
    dönemden devralmış dönem kilitliyse 409 `sonraki_kilitli`; kilitli değilse yanıtta `uyari` (devri yenileyin). Rol denetimi API'de."""
    from .smm_donem_servisi import sonraki_donemler
    d = donem_getir(s, donem_id)
    uyari = None
    if bool(d.kilitli) != kilitli:
        kayit = {"donem": donem_adi(d)}
        if kilitli:
            eksikler = kapanis_eksikleri(s, donem_id)
            if eksikler and not zorla:
                raise CatismaHatasi(f"{donem_adi(d)} kapatılmadan önce eksikler var: {'; '.join(eksikler)}.", {"eksikler": eksikler}, kod="kapanis_eksik")
            if eksikler:
                kayit.update(zorla=True, eksikler=eksikler)
        else:
            sonrakiler = sonraki_donemler(s, d)
            kapali = next((x for x in sonrakiler if x.kilitli), None)
            if kapali is not None:
                raise CatismaHatasi(f"Önce {donem_adi(kapali)} kilidini açın; açılışı bu dönemden devralındı.", {"donem_id": kapali.id},
                                    kod="sonraki_kilitli")
            if sonrakiler:
                uyari = f"{donem_adi(sonrakiler[0])} açılışı bu dönemden devralındı; değişiklik sonrası devri yenileyin"
        d.kilitli = kilitli
        d.kilitleyen = kullanici if kilitli else None
        s.add(m.DegisiklikKaydi(tablo="smm_donem", kayit_id=d.id, islem="kilitle" if kilitli else "kilit_ac", eski=None,
                                yeni=kayit, kullanici=kullanici))
        s.flush()
    return {**donem_cikis(d), "uyari": uyari}


def fis_excel(s: Session, donem_id: int) -> tuple[bytes, str]:
    """SMM fişi taslağı ve SMM tablosu (.xlsx): Canias'a aktarım ya da kontrol için."""
    from .smm_ozet_servisi import smm_ozeti
    d = donem_getir(s, donem_id)
    o = smm_ozeti(s, donem_id)
    wb = Workbook()
    ws = wb.active
    ws.title = "SMM Fişi"
    kalin = Font(bold=True)
    ws.append([f"Zeytursan — {donem_adi(d)} SMM fişi taslağı" + ("" if d.kilitli else " (dönem kilitli değil)")])
    ws["A1"].font = kalin
    ws.append(["Hesap Kodu", "Hesap Adı", "Açıklama", "Borç", "Alacak"])
    for c in ws[2]:
        c.font = kalin
    for f in o["fis"]:
        ws.append([f["hesap"], f["ad"], f"{donem_adi(d)} {f['aciklama']}", float(_d(f["borc"])) or None, float(_d(f["alacak"])) or None])
    ws.append(["", "", "Toplam", float(_d(o["fis_borc"])), float(_d(o["fis_alacak"]))])
    for c in ws[ws.max_row]:
        c.font = kalin
    for col, w in zip("ABCDE", (12, 40, 44, 18, 18)):
        ws.column_dimensions[col].width = w
    for row in ws.iter_rows(min_row=3, min_col=4, max_col=5):
        for c in row:
            c.number_format = "#,##0.00"
    t = wb.create_sheet("SMM Tablosu")
    t.append([f"{donem_adi(d)} SMM tablosu"])
    t["A1"].font = kalin
    for b in o["tablo"]:
        t.append([])
        t.append([b["hesap"], b["ad"]])
        t[t.max_row][0].font = kalin
        for x in b["satirlar"]:
            t.append(["", f"{x['isaret']} {x['ad']}", float(_d(x["tutar"]))])
        t.append(["", f"= {b['sonuc_ad']}", float(_d(b["sonuc"]))])
        t[t.max_row][1].font = kalin
    t.column_dimensions["B"].width = 44
    t.column_dimensions["C"].width = 20
    for row in t.iter_rows(min_col=3, max_col=3):
        for c in row:
            c.number_format = "#,##0.00"
    b = io.BytesIO()
    wb.save(b)
    return b.getvalue(), f"{d.yil}-{d.ay:02d} SMM fişi.xlsx"
