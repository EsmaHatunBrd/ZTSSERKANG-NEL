"""Stokta kalan (geçen yıldan devreden) ürün ve ortalama maliyet.

Kural (Esma onaylı):
- güncel stok maliyeti = stok birim maliyeti x (1 + enflasyon); enflasyon üründe elle girilmişse o, yoksa çalışmanın `enflasyon`
  parametresi (hesapta kullanılan, hesap tarihinde geçerli değer).
- bu yıl üretim adedi = elle girilmişse o; yoksa geçen yıl satış adedi - stok adedi (en az 0); ikisi de yoksa bilinmiyor (null).
- ortalama maliyet = (stok adedi x güncel stok maliyeti + üretim adedi x bu yılın maliyeti) / (stok adedi + üretim adedi).
  Bu yılın maliyeti = finansman dahil maliyet TL (Genel Bakış "Maliyet TL").
- Kayıt yok ya da adet 0: hiçbir şey değişmez (ortalama null, stok_etkisi false).
- `satis_ortalama_maliyetten` = 1 ise stok etkisi olan üründe satış fiyatı ortalama maliyetten hesaplanır (hesap_servisi.hesapla).
Kayıt çalışmaya (senaryo) bağlıdır; çalışma kopyalanırken taşınmaz. Yuvarlama yapılmaz (Decimal tam değer; gösterim arayüzde)."""
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from fiyat_motoru.para import SIFIR
from ..depo import modeller as m
from .donusum import decimal_str
from .hatalar import DogrulamaHatasi

TABLO = "stok_devri"
PARAMETRE = "satis_ortalama_maliyetten"   # 0/1; girilmezse 0
EN_COK_ENFLASYON = Decimal("5")
ALANLAR = ("adet", "birim_maliyet", "enflasyon", "uretim_adedi")
CIKIS_ALANLARI = ("urun_kodu", "adet", "birim_maliyet", "enflasyon", "uretim_adedi", "enflasyon_kullanilan", "uretim_adedi_kullanilan",
                  "uretim_adedi_kaynagi", "guncel_stok_maliyeti", "bu_yil_maliyet", "ortalama_maliyet", "stok_payi", "stok_etkisi", "aciklama")
ACIKLAMA_ADET_YOK = "stok adedi 0: stokta kalan yok, maliyet değişmez"
ACIKLAMA_URETIM_YOK = "bu yıl üretim adedi bilinmiyor: elle girilmedi ve geçen yıl satış adedi yok; ortalama hesaplanamadı"


def _ondalik(ad: str, v) -> Decimal | None:
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        raise DogrulamaHatasi(f"{ad} sayı olmalı", {ad: str(v)})
    try:
        d = Decimal(str(v).strip().replace(",", ".")) if isinstance(v, str) else Decimal(str(v))
    except ArithmeticError:
        raise DogrulamaHatasi(f"{ad} sayı olmalı", {ad: str(v)})
    if not d.is_finite():
        raise DogrulamaHatasi(f"{ad} sonlu bir sayı olmalı", {ad: str(v)})
    return d


def dogrula(adet, birim_maliyet, enflasyon=None, uretim_adedi=None) -> dict[str, Decimal | None]:
    """Girdi -> saklanacak değerler. adet >= 0 (boş = 0); adet > 0 iken birim maliyet > 0; -1 < enflasyon <= 5; üretim adedi >= 0. Aksi 422."""
    adet = _ondalik("adet", adet) or SIFIR
    birim_maliyet = _ondalik("birim_maliyet", birim_maliyet)
    enflasyon = _ondalik("enflasyon", enflasyon)
    uretim_adedi = _ondalik("uretim_adedi", uretim_adedi)
    if adet < 0:
        raise DogrulamaHatasi("stok adedi 0 ya da daha büyük olmalı", {"adet": str(adet)})
    if birim_maliyet is not None and birim_maliyet < 0:
        raise DogrulamaHatasi("stok birim maliyeti negatif olamaz", {"birim_maliyet": str(birim_maliyet)})
    if adet > 0 and (birim_maliyet is None or birim_maliyet <= 0):
        raise DogrulamaHatasi("stok adedi varken birim maliyet 0'dan büyük olmalı", {"birim_maliyet": None if birim_maliyet is None else str(birim_maliyet)})
    if enflasyon is not None and not (Decimal(-1) < enflasyon <= EN_COK_ENFLASYON):
        raise DogrulamaHatasi("enflasyon oran olarak -%100 ile +%500 arasında olmalı (0,40 = %40)", {"enflasyon": str(enflasyon)})
    if uretim_adedi is not None and uretim_adedi < 0:
        raise DogrulamaHatasi("üretim adedi 0 ya da daha büyük olmalı", {"uretim_adedi": str(uretim_adedi)})
    return {"adet": adet, "birim_maliyet": birim_maliyet, "enflasyon": enflasyon, "uretim_adedi": uretim_adedi}


# ---------------------------------------------------------------- okuma

def kayitlar(s: Session, senaryo_id: int) -> dict[int, m.StokDevri]:
    """Çalışmanın tüm kayıtları tek sorguyla: {urun_id: kayıt}."""
    return {k.urun_id: k for k in s.scalars(select(m.StokDevri).where(m.StokDevri.senaryo_id == senaryo_id))}


def getir(s: Session, urun_id: int, senaryo_id: int) -> m.StokDevri | None:
    return s.scalar(select(m.StokDevri).where(m.StokDevri.urun_id == urun_id, m.StokDevri.senaryo_id == senaryo_id))


def liste(s: Session, senaryo_id: int) -> list[tuple[m.Urun, m.StokDevri]]:
    q = (select(m.Urun, m.StokDevri).join(m.StokDevri, m.StokDevri.urun_id == m.Urun.id)
         .where(m.StokDevri.senaryo_id == senaryo_id).order_by(m.Urun.kod))
    return [(u, k) for u, k in s.execute(q).all()]


def satis_adetleri(s: Session, sen: m.Senaryo, urun_idleri: set[int]) -> dict[int, Decimal]:
    """Geçen yıl satış adedi (analiz_servisi.yillik_adetler ile aynı kaynak): {urun_id: adet}; satışı olmayan ürün yok."""
    if not urun_idleri:
        return {}
    from . import analiz_servisi   # yerel: analiz_servisi hesap_servisi'ni, o da bu modülü içe aktarır
    urunler = list(s.scalars(select(m.Urun).where(m.Urun.id.in_(urun_idleri))))
    kodla = analiz_servisi.yillik_adetler(s, sen, urunler)
    return {u.id: kodla[u.kod] for u in urunler if u.kod in kodla}


# ---------------------------------------------------------------- hesap (saf)

def bos_ozet(urun_kodu: str) -> dict:
    """Kayıt yok: tüm alanlar null, stok_etkisi false."""
    return {**{a: None for a in CIKIS_ALANLARI}, "urun_kodu": urun_kodu, "stok_etkisi": False}


def ozet(urun_kodu: str, kayit: m.StokDevri | None, bu_yil_maliyet: Decimal | None, param_enflasyon: Decimal | None,
         satis_adedi: Decimal | None, hata: str | None = None) -> dict | None:
    """Saf hesap (sorgu yok). Kayıt yoksa None. Decimal değerli sözlük (StokDevriCikis alanları). `hata`: bu yılın maliyeti
    hesaplanamadıysa nedeni (ortalama null, açıklamada görünür)."""
    if kayit is None:
        return None
    d = bos_ozet(urun_kodu)
    d.update({a: getattr(kayit, a) for a in ALANLAR})
    adet = kayit.adet or SIFIR
    if adet <= 0:
        d["aciklama"] = ACIKLAMA_ADET_YOK
        return d
    enf = kayit.enflasyon if kayit.enflasyon is not None else param_enflasyon
    d["enflasyon_kullanilan"] = enf
    if enf is not None and kayit.birim_maliyet is not None:
        d["guncel_stok_maliyeti"] = kayit.birim_maliyet * (1 + enf)
    if kayit.uretim_adedi is not None:
        d["uretim_adedi_kullanilan"], d["uretim_adedi_kaynagi"] = kayit.uretim_adedi, "elle"
    elif satis_adedi is not None:
        d["uretim_adedi_kullanilan"], d["uretim_adedi_kaynagi"] = max(satis_adedi - adet, SIFIR), "satis_gecmisi"
    d["bu_yil_maliyet"] = bu_yil_maliyet
    uretim = d["uretim_adedi_kullanilan"]
    if uretim is not None:
        d["stok_payi"] = adet / (adet + uretim)
    if hata is not None or bu_yil_maliyet is None:
        d["aciklama"] = f"bu yılın maliyeti hesaplanamadı: {hata}" if hata else "bu yılın maliyeti hesaplanamadı"
    elif d["guncel_stok_maliyeti"] is None:
        d["aciklama"] = "enflasyon bilinmiyor: elle girilmedi ve çalışmada enflasyon parametresi yok"
    elif uretim is None:
        d["aciklama"] = ACIKLAMA_URETIM_YOK
    else:
        d["ortalama_maliyet"] = (adet * d["guncel_stok_maliyeti"] + uretim * bu_yil_maliyet) / (adet + uretim)
        d["stok_etkisi"] = True
    return d


def hesap_ozeti(s: Session, sen: m.Senaryo, urun: m.Urun, bu_yil_maliyet: Decimal, param_enflasyon: Decimal, baglam=None) -> dict | None:
    """hesap_servisi.hesapla'nın çağırdığı yol: kayıtlar ve satış adetleri `baglam` (HesapBaglami) ile çalışma başına bir kez çekilir."""
    al = baglam.al if baglam is not None else (lambda _a, uret: uret())
    tum = al(("stok_devri", sen.id), lambda: kayitlar(s, sen.id))
    kayit = tum.get(urun.id)
    if kayit is None:
        return None
    satis = None
    if kayit.uretim_adedi is None and (kayit.adet or SIFIR) > 0:
        gerekli = {uid for uid, k in tum.items() if k.uretim_adedi is None and (k.adet or SIFIR) > 0}
        satis = al(("stok_devri_satis", sen.id), lambda: satis_adetleri(s, sen, gerekli)).get(urun.id)
    return ozet(urun.kod, kayit, bu_yil_maliyet, param_enflasyon, satis)


def etki(s: Session, sen: m.Senaryo, urun: m.Urun, cikti=None, tarih=None) -> dict:
    """Ürünün stokta kalan özeti (Decimal değerli, StokDevriCikis alanları). `cikti` (HesapCiktisi) verilmezse bu yılın maliyeti için
    hesap yapılır (hesap_servisi.hesapla); hesap hata verirse ortalama null ve açıklamada neden. Kayıt yoksa bos_ozet."""
    from . import hesap_servisi as hs   # yerel: hesap_servisi bu modülü içe aktarır
    from .hatalar import ServisHatasi
    kayit = getir(s, urun.id, sen.id)
    if kayit is None:
        return bos_ozet(urun.kod)
    if cikti is None:
        try:
            cikti = hs.hesapla(s, urun.kod, sen.id, tarih)
        except (ServisHatasi, KeyError, ValueError, ArithmeticError) as e:
            satis = None
            if kayit.uretim_adedi is None:
                satis = satis_adetleri(s, sen, {urun.id}).get(urun.id)
            enf = None
            try:
                from . import parametre_servisi as ps
                from datetime import date
                enf = ps.gecerli_degerler(s, sen.id, tarih or date.today(), urun.id).get("enflasyon")
            except ServisHatasi:
                pass
            return ozet(urun.kod, kayit, None, enf, satis, str(getattr(e, "mesaj", None) or e))
    if cikti.stok_devri is not None:
        return cikti.stok_devri
    return ozet(urun.kod, kayit, cikti.sonuc.finansman_dahil_maliyet_tl, cikti.parametreler.enflasyon, None)


# ---------------------------------------------------------------- yazma

def _gunluk(s: Session, kayit_id: int, islem: str, eski: dict | None, yeni: dict | None, neden: str, kullanici: str) -> None:
    s.add(m.DegisiklikKaydi(tablo=TABLO, kayit_id=kayit_id, islem=islem, eski=eski, yeni={**(yeni or {}), "_neden": neden}, kullanici=kullanici))


def _neden(neden: str | None) -> str:
    if not (neden or "").strip():
        raise DogrulamaHatasi("neden zorunlu", {"neden": None})
    return neden.strip()[:300]


def _icerik(urun: m.Urun, sen_id: int, degerler: dict) -> dict:
    """Günlükte ürün ve çalışma içerikte saklanır (silinen kayıtta da bulunabilsin)."""
    return {"urun_kodu": urun.kod, "senaryo_id": sen_id, **decimal_str(degerler)}


def kaydet(s: Session, sen: m.Senaryo, urun: m.Urun, adet, birim_maliyet, enflasyon=None, uretim_adedi=None, neden: str | None = None,
           kullanici: str = "sistem") -> m.StokDevri:
    """Ekle ya da güncelle (çalışma + ürün başına tek kayıt). Kilitli çalışmada 409. Değişmeyen kayıt günlüğe yazılmaz."""
    from .hesap_servisi import kilit_denetle
    kilit_denetle(sen)
    neden = _neden(neden)
    yeni = dogrula(adet, birim_maliyet, enflasyon, uretim_adedi)
    k = getir(s, urun.id, sen.id)
    if k is None:
        k = m.StokDevri(urun_id=urun.id, senaryo_id=sen.id, olusturan=kullanici, **yeni)
        s.add(k); s.flush()
        _gunluk(s, k.id, "ekle", None, _icerik(urun, sen.id, yeni), neden, kullanici)
        s.flush()
        return k
    eski = {a: getattr(k, a) for a in ALANLAR}
    if eski != yeni:
        for a, v in yeni.items():
            setattr(k, a, v)
        _gunluk(s, k.id, "guncelle", _icerik(urun, sen.id, eski), _icerik(urun, sen.id, yeni), neden, kullanici)
        s.flush()
    return k


def sil(s: Session, sen: m.Senaryo, urun: m.Urun, neden: str | None, kullanici: str = "sistem") -> bool:
    """Kaydı siler (eski değerler günlükte kalır; aynı değerlerle yeniden girilebilir). Kayıt yoksa False. Kilitli çalışmada 409."""
    from .hesap_servisi import kilit_denetle
    kilit_denetle(sen)
    neden = _neden(neden)
    k = getir(s, urun.id, sen.id)
    if k is None:
        return False
    _gunluk(s, k.id, "sil", _icerik(urun, sen.id, {a: getattr(k, a) for a in ALANLAR}), None, neden, kullanici)
    s.delete(k); s.flush()
    return True


# ---------------------------------------------------------------- toplu aktarım (Excel)
SUTUNLAR = ("urun_kodu", "stok_adet", "stok_birim_maliyet", "enflasyon", "uretim_adedi")
ZORUNLU_SUTUNLAR = ("urun_kodu", "stok_adet", "stok_birim_maliyet")
ESANLAMLAR = {"urun_kodu": ("Ürün Kodu", "Stok Kodu", "Malzeme Kodu", "Mamul Kodu", "Kod"),
              "stok_adet": ("Stok Adedi", "Stok Adet", "Stok Miktarı", "Stokta Kalan", "Stokta Kalan Adet", "Adet", "Miktar"),
              "stok_birim_maliyet": ("Stok Birim Maliyeti", "Stok Birim Maliyet", "Birim Maliyet", "Birim Maliyeti", "Maliyet"),
              "enflasyon": ("Enflasyon Oranı", "Enflasyon (%)"),
              "uretim_adedi": ("Üretim Adedi", "Üretilecek Adet", "Bu Yıl Üretim Adedi", "Üretim")}
_SUTUN_ALANI = {"stok_adet": "adet", "stok_birim_maliyet": "birim_maliyet", "enflasyon": "enflasyon", "uretim_adedi": "uretim_adedi"}
_TR = str.maketrans("İIışğüöçŞĞÜÖÇ", "iiisguocsguoc")
SABLON_ACIKLAMA = [
    "Başlıklar (ilk sayfa, ilk satır): urun_kodu, stok_adet, stok_birim_maliyet, enflasyon, uretim_adedi. enflasyon ve uretim_adedi boş bırakılabilir.",
    "stok_adet: geçen yıldan stokta kalan adet. stok_birim_maliyet: o stokun birim maliyeti, TL (stok_adet > 0 ise zorunlu, 0'dan büyük).",
    "enflasyon: oran (0,40 = %40; %40 yazımı da olur). Boşsa çalışmanın enflasyon parametresi kullanılır.",
    "uretim_adedi: bu yıl üretilecek adet. Boşsa geçen yıl satış adedi - stok adedi (en az 0) kullanılır.",
    "Sayı biçimi: 1234.56 ya da 1234,56. Aynı ürün dosyada bir kez geçmeli. Herhangi bir satır hatalıysa hiçbir satır yazılmaz.",
    "Kayıtlar seçili çalışmaya yazılır; yeni çalışma kopyalanırken taşınmaz.",
]


def _baslik(v) -> str:
    return str(v or "").translate(_TR).lower().strip().replace(" ", "_")


def _hucre_sayi(v, oran: bool = False) -> Decimal | None:
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if isinstance(v, str):
        metin = v.strip().replace(" ", "")
        yuzde = "%" in metin
        if yuzde and not oran:
            raise DogrulamaHatasi("yüzde işareti yalnız enflasyonda kullanılabilir")
        metin = metin.strip("%")
        if "," in metin and "." in metin:   # 1.234,56
            metin = metin.replace(".", "").replace(",", ".")
        d = _ondalik("deger", metin)
        return d / 100 if yuzde and d is not None else d
    return _ondalik("deger", v)


def aktarim_oku(dosya_yolu) -> tuple[dict[str, str | None], list[dict], list[dict]]:
    """xlsx ilk sayfası -> (sütun eşlemesi, satırlar, hatalar). Satır: {satir_no, urun_kodu, adet, birim_maliyet, enflasyon, uretim_adedi}.
    Boş satırlar atlanır; hatalı satırlar atlanmaz, `hatalar`a {satir_no, mesaj} olarak yazılır."""
    from .excel_ortak import Alan, baslik_satirini_bul, sablon_denetle
    from .import_servisi import kitap_ac
    from .yukleme_guvenligi import sayfa_sec
    wb = kitap_ac(dosya_yolu, data_only=True)
    sablon_denetle(wb, "stokta_kalan")
    ws = sayfa_sec(wb, "Stokta Kalan", ("Stok Devri", "Stokta Kalanlar"), ilk_sayfaya_dus=True, kanonik_ad=False)
    satirlar_ham = [list(r) for r in ws.iter_rows(values_only=True)]
    if not satirlar_ham:
        raise DogrulamaHatasi("dosya boş; mevcut veri değiştirilmedi", kod="bos_dosya")
    alanlar = [Alan(a, (a,) + ESANLAMLAR.get(a, ()), zorunlu=a in ZORUNLU_SUTUNLAR) for a in SUTUNLAR]
    e = baslik_satirini_bul(iter(satirlar_ham), alanlar, ne="stokta kalan dosyası")
    baslik = satirlar_ham[e.satir - 1]
    sutunlar = {a: (None if a not in e.sutun else str(baslik[e.sutun[a]])) for a in SUTUNLAR}
    yer = dict(e.sutun)
    satirlar, hatalar = [], []
    for no, satir in enumerate(satirlar_ham[e.satir:], start=e.satir + 1):
        hucre = lambda a: (satir[yer[a]] if a in yer and yer[a] < len(satir) else None)
        if all(v is None or (isinstance(v, str) and not v.strip()) for v in satir):
            continue
        kod = str(hucre("urun_kodu") or "").strip()
        if not kod:
            hatalar.append({"satir_no": no, "mesaj": "urun_kodu boş"}); continue
        r = {"satir_no": no, "urun_kodu": kod}
        try:
            for sutun, alan in _SUTUN_ALANI.items():
                try:
                    r[alan] = _hucre_sayi(hucre(sutun), oran=(alan == "enflasyon"))
                except DogrulamaHatasi:
                    raise DogrulamaHatasi(f"{sutun} sayı değil: {hucre(sutun)!s}"[:200])
            r.update(dogrula(r["adet"], r["birim_maliyet"], r["enflasyon"], r["uretim_adedi"]))
        except DogrulamaHatasi as e:
            hatalar.append({"satir_no": no, "mesaj": f"{kod}: {e.mesaj}"}); continue
        satirlar.append(r)
    return sutunlar, satirlar, hatalar


def aktarim_onizle(s: Session, sen: m.Senaryo, dosya_yolu) -> dict:
    """Hiçbir şey yazmaz. Bilinmeyen ürün ve tekrar eden ürün kodu hata satırıdır."""
    sutunlar, satirlar, hatalar = aktarim_oku(dosya_yolu)
    urunler = {u.kod: u for u in s.scalars(select(m.Urun).where(m.Urun.kod.in_([r["urun_kodu"] for r in satirlar])))} if satirlar else {}
    mevcut = kayitlar(s, sen.id)
    gorulen: dict[str, int] = {}
    out = []
    for r in satirlar:
        kod = r["urun_kodu"]
        if kod in gorulen:
            hatalar.append({"satir_no": r["satir_no"], "mesaj": f"{kod}: ürün kodu dosyada birden fazla (ilk: satır {gorulen[kod]})"}); continue
        gorulen[kod] = r["satir_no"]
        u = urunler.get(kod)
        if u is None:
            hatalar.append({"satir_no": r["satir_no"], "mesaj": f"{kod}: ürün bulunamadı"}); continue
        yeni = {a: r[a] for a in ALANLAR}
        k = mevcut.get(u.id)
        eski = {a: getattr(k, a) for a in ALANLAR} if k is not None else None
        durum = "yeni" if k is None else ("ayni" if eski == yeni else "degisen")
        out.append({"satir_no": r["satir_no"], "urun_kodu": kod, "ad": u.ad, **decimal_str(yeni), "durum": durum,
                    "eski": decimal_str(eski) if durum == "degisen" else None, "_urun": u, "_degerler": yeni})
    hatalar.sort(key=lambda h: h["satir_no"])
    from .yukleme_guvenligi import ozet
    sayac = {d: sum(1 for r in out if r["durum"] == d) for d in ("yeni", "degisen", "ayni")}
    if not out and not hatalar:
        raise DogrulamaHatasi("Dosyada okunabilen stok satırı yok; mevcut veri değiştirilmedi.", kod="bos_dosya")
    oz = ozet(okunan=len(out) + len(hatalar), yeni=sayac["yeni"], degisen=sayac["degisen"], ayni=sayac["ayni"], atlanan=len(hatalar),
              sorunlu_satirlar=[{"satir": h["satir_no"], "kod": h["mesaj"].split(":", 1)[0] if ":" in h["mesaj"] else None, "alan": None,
                                 "deger": None, "neden": h["mesaj"]} for h in hatalar],
              uyarilar=["Hatalı satırlar düzeltilmeden hiçbir satır yazılmaz."] if hatalar else [])
    return {"sutunlar": sutunlar, "satirlar": out, "hatalar": hatalar, **sayac, "ozet": oz}


def aktarim_uygula(s: Session, sen: m.Senaryo, dosya_yolu, neden: str, kullanici: str = "sistem", onay: bool = False,
                   kaynak_dosya: str | None = None) -> dict:
    """Önizlemeyi yeniden yapar; hatalı satır varsa 422 (alanlar.hatalar) ve hiçbir şey yazılmaz. Yeni ve değişen satırlar yazılır
    (upsert: dosyada olmayan kayıt silinmez). Yazmadan önce değişecek kayıtların yedeği alınır."""
    from .hesap_servisi import kilit_denetle
    from .yukleme_guvenligi import stok_icerik, yedekle
    kilit_denetle(sen)
    neden = _neden(neden)
    on = aktarim_onizle(s, sen, dosya_yolu)
    if on["hatalar"]:
        raise DogrulamaHatasi("dosyada hatalı satırlar var; hiçbir satır yazılmadı", {"hatalar": on["hatalar"]})
    yazilacak = [r for r in on["satirlar"] if r["durum"] != "ayni"]
    if yazilacak:
        mevcut = kayitlar(s, sen.id)
        yedekle(s, "stok_devri", sen.id,
                {"senaryo_id": sen.id, "eski": {str(r["_urun"].id): (stok_icerik(mevcut[r["_urun"].id]) if r["_urun"].id in mevcut else None)
                                                for r in yazilacak}},
                f"{on['yeni']} yeni, {on['degisen']} değişen stok", kaynak_dosya, kullanici)
    for r in on["satirlar"]:
        if r["durum"] != "ayni":
            kaydet(s, sen, r["_urun"], neden=neden, kullanici=kullanici, **r["_degerler"])
    return {"eklenen": on["yeni"], "guncellenen": on["degisen"], "ayni": on["ayni"]}
