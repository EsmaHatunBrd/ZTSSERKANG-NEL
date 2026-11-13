"""Maliyet muhasebesi raporları: bütçe / fiili birim maliyet kıyası, aylar arası SMM karşılaştırması ve ürün birim maliyet kartı.

Bu modül YENİ HESAP KURALI İÇERMEZ; var olan sonuçları yeniden sunar:
    fiili  = aşama hesabı (smm_asama_servisi._Baglam): ürünün kendi aşamasındaki birim maliyet ve dökümü
    bütçe  = Fiyat Çalışması hesabı (hesap_servisi.toplu_hesapla): MaliyetSonucu alanları
    SMM    = smm_ozet_servisi.smm_ozeti çıktısındaki tablo satırları

Bütçe tarafında karşılaştırılan tutar `toplam_birim_maliyet` (Excel P116 = malzeme + direkt işçilik + genel üretim gideri): SMM aşama
birim maliyeti de yalnız üretim maliyetidir (malzeme + işçilik + GÜG + fire); pazarlama, yönetim ve satış finansmanı içermez. Finansman
dahil maliyet (P130) bilgi için ayrıca döner. Bütçe dökümü, motorun firesiz bloğundan: malzeme / işçilik / GÜG firesiz değerler, fire =
fireli − firesiz üretim maliyeti (dört kalemin toplamı bütçe üretim maliyetine eşittir).
Tutarlar Decimal; çıktıda metin. Hiçbir kayıt değiştirilmez."""
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..depo import modeller as m
from . import hesap_servisi as hs
from . import smm_ozet_servisi as so
from .donusum import decimal_str
from .hatalar import BulunamadiHatasi, DogrulamaHatasi
from .smm_asama_servisi import ASAMA_ADLARI, _Baglam, recete_satirlari
from .smm_donem_servisi import onceki_donem
from .smm_servisi import SIFIR, _d, donem_cikis, donem_getir

ASAMALAR = (50, 40, 20)   # son aşamadan geriye
MAKS_DONEM = 12
VARSAYILAN_DONEM = 6


def _bol(a: Decimal, b: Decimal) -> Decimal | None:
    return a / b if b else None


def urun_asamasi(b: _Baglam, kod: str) -> int | None:
    """Ürünün birim maliyetinin okunacağı aşama: stok kartındaki `uretim_asamasi` (o aşamada reçetesi varsa); yoksa reçetesinin
    bulunduğu en ileri aşama (50 > 40 > 20). Hiçbir aşamada yoksa None."""
    k = b.kalem.get(kod)
    if k is not None and k.uretim_asamasi and kod in b.sonuc.get(k.uretim_asamasi, {}):
        return k.uretim_asamasi
    return next((a for a in ASAMALAR if kod in b.sonuc.get(a, {})), None)


def _fiili_dokum(x: dict) -> dict:
    return {"malzeme": x["malzeme"], "iscilik": x["iscilik"], "gug": x["gug"], "fire": x["fire"], "stok_payi": x["stok_payi"]}


def _butce_dokum(r) -> dict:
    f = r.firesiz
    if f is None:
        return {"malzeme": r.malzeme_toplami, "iscilik": r.direkt_iscilik_toplami, "gug": r.gug_toplami, "fire": None,
                "uretim_gideri": r.uretim_gideri_toplami, "pazarlama_yonetim": r.diger_giderler_toplami, "finansman": r.finansman.get("TL", SIFIR)}
    return {"malzeme": f.malzeme_toplami, "iscilik": f.direkt_iscilik_toplami, "gug": f.gug_toplami,
            "fire": r.toplam_birim_maliyet - f.toplam_birim_maliyet, "uretim_gideri": r.uretim_gideri_toplami,
            "pazarlama_yonetim": r.diger_giderler_toplami, "finansman": r.finansman.get("TL", SIFIR)}


# ---------------------------------------------------------------- T1: bütçe / fiili birim maliyet kıyası
def butce_kiyas(s: Session, donem_id: int, senaryo_id: int, tarih: date | None = None) -> dict:
    """Fiyat Çalışması senaryosundaki ürünlerin bütçe üretim maliyeti ile dönemin fiili (SMM) birim maliyeti; eşleme ürün koduyla.
    fark = fiili − bütçe; oran = fark / bütçe. Fark yalnız dönemde üretilmiş ve bütçesi hesaplanabilmiş üründe verilir
    (üretim yoksa aşama hesabı işçilik payı dağıtmaz: birim maliyet karşılaştırılamaz)."""
    d = donem_getir(s, donem_id)
    sen = hs.senaryo_getir(s, senaryo_id)
    b = _Baglam(s, d)
    adlar = {u.kod: u.ad for u in hs.urunler(s, aktif=False)}
    kayitlar, yalniz_butce = [], []
    butce_kodlari: set[str] = set()
    for kod, c in hs.toplu_hesapla(s, senaryo_id, tarih):
        butce_kodlari.add(kod)
        hata = isinstance(c, Exception)
        asama = urun_asamasi(b, kod)
        if asama is None:
            yalniz_butce.append({"kod": kod, "ad": adlar.get(kod), "butce_maliyet_tl": None if hata else c.sonuc.toplam_birim_maliyet,
                                 "stok_kartinda": kod in b.kalem, "eslesme": "yok"})
            continue
        x = b.sonuc[asama][kod]
        r = None if hata else c.sonuc
        butce = r.toplam_birim_maliyet if r else None
        uretildi = x["uretim_miktar"] > 0
        fark = x["birim_maliyet"] - butce if (butce is not None and uretildi) else None
        kayitlar.append({
            "kod": kod, "ad": adlar.get(kod) or x["ad"], "asama": asama, "birim": x["birim"], "uretim_miktar": x["uretim_miktar"],
            "uretildi": uretildi, "butce_maliyet_tl": butce, "butce_finansman_dahil_tl": r.finansman_dahil_maliyet_tl if r else None,
            "fiili_birim_maliyet_tl": x["birim_maliyet"], "fark_tl": fark, "fark_yuzde": _bol(fark, butce) if fark is not None else None,
            "fiili_dokum": _fiili_dokum(x), "butce_dokum": _butce_dokum(r) if r else None, "alim_kurali": x["alim_kurali"],
            "butce_hatasi": str(getattr(c, "mesaj", None) or c) if hata else None, "eslesme": "kod"})
    # Fiili tarafta olup senaryoda olmayanlar: dönemde üretilmiş son aşama (50, mamul) ürünleri
    yalniz_fiili = [{"kod": kod, "ad": x["ad"], "asama": 50, "uretim_miktar": x["uretim_miktar"], "fiili_birim_maliyet_tl": x["birim_maliyet"],
                     "eslesme": "yok"}
                    for kod, x in b.sonuc.get(50, {}).items() if kod not in butce_kodlari and x["uretim_miktar"] > 0]
    kayitlar.sort(key=lambda x: (x["fark_yuzde"] is None, -(abs(x["fark_yuzde"]) if x["fark_yuzde"] is not None else SIFIR), x["kod"]))
    yalniz_butce.sort(key=lambda x: x["kod"])
    yalniz_fiili.sort(key=lambda x: (-x["uretim_miktar"] * x["fiili_birim_maliyet_tl"], x["kod"]))
    farklar = [x["fark_yuzde"] for x in kayitlar if x["fark_yuzde"] is not None]
    return decimal_str({
        "donem": donem_cikis(d, len(b.kalem)), "senaryo": {"id": sen.id, "ad": sen.ad},
        "ozet": {"eslesen": len(kayitlar), "karsilastirilan": len(farklar), "uretimsiz": sum(1 for x in kayitlar if not x["uretildi"]),
                 "yalniz_butce": len(yalniz_butce), "yalniz_fiili": len(yalniz_fiili),
                 "ortalama_fark_yuzde": sum(farklar, SIFIR) / len(farklar) if farklar else None,
                 "fiili_yuksek": sum(1 for f in farklar if f > 0)},
        "kayitlar": kayitlar, "yalniz_butce": yalniz_butce, "yalniz_fiili": yalniz_fiili})


# ---------------------------------------------------------------- T2: aylar arası SMM karşılaştırması
def _tablo_satiri(o: dict, hesap: str, bas: str) -> tuple[str, Decimal]:
    blok = next(x for x in o["tablo"] if x["hesap"] == hesap)
    x = next(r for r in blok["satirlar"] if r["ad"].startswith(bas))
    return x["ad"], _d(x["tutar"])


def _sonuc(o: dict, hesap: str) -> tuple[str, Decimal]:
    blok = next(x for x in o["tablo"] if x["hesap"] == hesap)
    return blok["sonuc_ad"], _d(blok["sonuc"])


def _stok(o: dict, hesap: str, bas: str) -> tuple[str, Decimal]:
    blok = next(x for x in o["tablo"] if x["hesap"] == hesap)
    ad, tutar = _tablo_satiri(o, hesap, bas)
    return f"{hesap} {blok['ad']} · {ad}", tutar


# (anahtar, smm_ozeti çıktısından (ad, tutar) okuyan işlev, vurgulu satır mı)
SMM_SATIRLARI = (
    ("ilk_madde", lambda o: _sonuc(o, "150"), False),
    ("iscilik", lambda o: _tablo_satiri(o, "72x", "720"), False),
    ("gug", lambda o: _tablo_satiri(o, "72x", "730"), False),
    ("uretim_maliyeti", lambda o: _sonuc(o, "72x"), True),
    ("yari_mamul_donem_basi", lambda o: _stok(o, "151", "Dönem başı"), False),
    ("yari_mamul_donem_sonu", lambda o: _stok(o, "151", "Dönem sonu"), False),
    ("uretilen", lambda o: _sonuc(o, "151"), True),
    ("mamul_donem_basi", lambda o: _stok(o, "152", "Dönem başı"), False),
    ("mamul_donem_sonu", lambda o: _stok(o, "152", "Dönem sonu"), False),
    ("smm", lambda o: _sonuc(o, "152"), True),
)


def _donem_idleri(s: Session, donemler: str | None) -> list[m.SmmDonem]:
    if not (donemler or "").strip():
        son = list(s.scalars(select(m.SmmDonem).order_by(m.SmmDonem.yil.desc(), m.SmmDonem.ay.desc()).limit(VARSAYILAN_DONEM)))
        return sorted(son, key=lambda d: (d.yil, d.ay))
    idler: list[int] = []
    for p in donemler.split(","):
        p = p.strip()
        if not p:
            continue
        if not p.isdigit():
            raise DogrulamaHatasi("dönem listesi virgülle ayrılmış dönem numaraları olmalı", {"donemler": donemler})
        if int(p) not in idler:
            idler.append(int(p))
    if len(idler) > MAKS_DONEM:
        raise DogrulamaHatasi(f"en çok {MAKS_DONEM} dönem karşılaştırılabilir", {"donemler": len(idler)})
    return sorted((donem_getir(s, i) for i in idler), key=lambda d: (d.yil, d.ay))


def karsilastirma(s: Session, donemler: str | None = None) -> dict:
    """Seçilen dönemlerin (boşsa son 6) SMM tablosu ana satırları, en eski dönem başta; her hücrede bir önceki döneme göre değişim."""
    secili = _donem_idleri(s, donemler)
    ozetler = [so.smm_ozeti(s, d.id) for d in secili]
    satirlar = []
    for anahtar, oku, vurgulu in SMM_SATIRLARI:
        hucreler, ad, onceki = [], None, None
        for d, o in zip(secili, ozetler):
            ad, tutar = oku(o)
            degisim = tutar - onceki if onceki is not None else None
            hucreler.append({"donem_id": d.id, "tutar": tutar, "degisim_tl": degisim,
                             "degisim_yuzde": _bol(degisim, abs(onceki)) if degisim is not None else None})
            onceki = tutar
        son = hucreler[-1] if len(hucreler) > 1 else None
        satirlar.append({"anahtar": anahtar, "ad": ad, "vurgulu": vurgulu, "hucreler": hucreler,
                         "son_fark_tl": son["degisim_tl"] if son else None, "son_fark_yuzde": son["degisim_yuzde"] if son else None})
    return decimal_str({"donemler": [o["donem"] for o in ozetler], "satirlar": satirlar if secili else []})


# ---------------------------------------------------------------- T3: ürün birim maliyet kartı
def _asama_satiri(x: dict, asama: int, ust_kod: str | None, carpan: Decimal | None) -> dict:
    return {"asama": asama, "ad": ASAMA_ADLARI[asama], "kod": x["kod"], "urun_ad": x["ad"], "birim": x["birim"], "ust_kod": ust_kod,
            "carpan": carpan, "malzeme": x["malzeme"], "iscilik": x["iscilik"], "gug": x["gug"], "fire": x["fire"], "stok_payi": x["stok_payi"],
            "birim_maliyet": x["birim_maliyet"], "uretim_miktar": x["uretim_miktar"], "alim_kurali": x["alim_kurali"],
            "elle_alanlar": x["elle_alanlar"]}


def _zincir(b: _Baglam, asama: int, kod: str) -> list[dict]:
    """Ürünün kendi aşaması ve reçetesinde geçen alt aşama ürünleri (50 -> 40 -> 20; 20'de başka bir 20 ürünü girdi olabilir).
    Alt aşama satırında `carpan` = bir üst ürünün bir birimi için reçetedeki kullanım. Her (aşama, kod) bir kez."""
    cikti = [_asama_satiri(b.sonuc[asama][kod], asama, None, None)]
    gorulen = {(asama, kod)}
    kuyruk = [(asama, kod)]
    while kuyruk:
        a, k = kuyruk.pop(0)
        alt = 20 if a in (20, 40) else 40
        for r in b.gruplar.get(a, {}).get(k, []):
            mal = r.malzeme_kod
            if (alt, mal) in gorulen or mal not in b.sonuc.get(alt, {}):
                continue
            gorulen.add((alt, mal))
            cikti.append(_asama_satiri(b.sonuc[alt][mal], alt, k, b.carpan(r)))
            kuyruk.append((alt, mal))
    return cikti


def maliyet_karti(s: Session, donem_id: int, kod: str) -> dict:
    """Ürünün aşama aşama birim maliyeti (kendi aşaması + reçetesindeki alt aşama ürünleri), kendi aşamasının reçete satırları ve
    bir önceki dönemdeki birim maliyetiyle farkı (önceki dönem ya da o dönemde ürün yoksa null)."""
    d = donem_getir(s, donem_id)
    b = _Baglam(s, d)
    asama = urun_asamasi(b, kod)
    if asama is None:
        raise BulunamadiHatasi("bu dönemde ürünün aşama reçetesi bulunamadı", {"kod": kod, "donem_id": donem_id})
    x = b.sonuc[asama][kod]
    onceki = None
    od = onceki_donem(s, d.yil, d.ay)
    if od is not None:
        ob = _Baglam(s, od)
        oa = urun_asamasi(ob, kod)
        if oa is not None:
            ox = ob.sonuc[oa][kod]
            fark = x["birim_maliyet"] - ox["birim_maliyet"]
            onceki = {"donem": donem_cikis(od), "asama": oa, "birim_maliyet": ox["birim_maliyet"], "uretim_miktar": ox["uretim_miktar"],
                      "fark_tl": fark, "fark_yuzde": _bol(fark, ox["birim_maliyet"])}
    return decimal_str({
        "donem": donem_cikis(d, len(b.kalem)), "kod": kod, "ad": x["ad"], "birim": x["birim"], "asama": asama,
        "birim_maliyet": x["birim_maliyet"], "uretim_miktar": x["uretim_miktar"], "toplam": x["toplam"],
        "alim_kurali": x["alim_kurali"], "alim_fiyati": x["alim_fiyati"],
        "asamalar": sorted(_zincir(b, asama, kod), key=lambda z: -z["asama"]),
        "satirlar": recete_satirlari(b, asama, kod), "onceki": onceki})
