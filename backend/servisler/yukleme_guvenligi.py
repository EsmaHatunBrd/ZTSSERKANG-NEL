"""Fiyat Çalışması yüklemelerinin ortak güvenlik parçaları: standart önizleme özeti, esnek sayfa seçimi, son yüklemeyi geri alma.

Yedek alanları (YuklemeYedegi.alan) ve kapsamları:
  fiyat_listesi, satin_alma, uretim_adetleri, gider_dagitim, recete, stok_devri  → kapsam = senaryo id
  satis_gecmisi, liste_fiyatlari                                                  → kapsam = "genel" (senaryodan bağımsız veriler)
Her yazan yükleme, yazmadan önce etkilenen verinin kopyasını (`yedek_kaydet`) bırakır; geri alma bu kopyayı birebir geri yazar ve
DegisiklikKaydi'na (tablo="yukleme_yedegi", islem="geri_al") düşer.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..depo import modeller as m
from .excel_ortak import KIMLIK_SAYFASI, baslik_anahtari
from .hatalar import DogrulamaHatasi
from .yukleme_yedegi import geri_alindi_isaretle, son_yedek, son_yedek_zorunlu, yedek_kaydet, yedek_ozeti

GENEL = "genel"
SORUNLU_DEGER_UZUNLUGU = 200


# ---------------------------------------------------------------- standart özet
def sorunlu(satir: int | None, kod, alan: str | None, deger, neden: str) -> dict:
    d = None if deger is None or (isinstance(deger, str) and not deger.strip()) else str(deger)[:SORUNLU_DEGER_UZUNLUGU]
    return {"satir": satir, "kod": None if kod in (None, "") else str(kod), "alan": alan, "deger": d, "neden": neden}


def ozet(okunan: int = 0, yeni: int = 0, degisen: int = 0, ayni: int = 0, silinecek: int = 0, atlanan: int = 0,
         sorunlu_satirlar: list[dict] | None = None, uyarilar: list[str] | None = None) -> dict:
    return {"okunan": okunan, "yeni": yeni, "degisen": degisen, "ayni": ayni, "silinecek": silinecek, "atlanan": atlanan,
            "sorunlu": list(sorunlu_satirlar or []), "uyarilar": list(uyarilar or [])}


# ---------------------------------------------------------------- esnek sayfa seçimi
_YARDIMCI_SAYFALAR = {"ornek", "aciklama"}


def veri_sayfalari(wb) -> list:
    """Gizli şablon kimliği ve şablonun 'Örnek' / 'Açıklama' sayfaları dışındaki sayfalar. Dosyada yalnız yardımcı sayfa kaldıysa
    (ör. yalnız 'Örnek' sayfası kaydedilmiş dosya) o sayfalar veri sayfası sayılır."""
    gercek = [ws for ws in wb.worksheets if ws.title != KIMLIK_SAYFASI]
    veri = [ws for ws in gercek if baslik_anahtari(ws.title) not in _YARDIMCI_SAYFALAR]
    return veri or gercek


def sayfa_bul(wb, beklenen: str, esanlamlar: tuple[str, ...] = ()):
    """Adı (büyük/küçük, Türkçe harf, boşluk ve noktalama farkı önemsiz) beklenen ya da eş anlamlı olan sayfa; yoksa None."""
    adaylar = {baslik_anahtari(beklenen), *(baslik_anahtari(x) for x in esanlamlar)}
    return next((ws for ws in wb.worksheets if baslik_anahtari(ws.title) in adaylar), None)


def sayfa_sec(wb, beklenen: str, esanlamlar: tuple[str, ...] = (), ilk_sayfaya_dus: bool = False, kanonik_ad: bool = True):
    """Beklenen sayfa (esnek ad); yoksa dosyada tek veri sayfası varsa o (ya da `ilk_sayfaya_dus` ise ilk veri sayfası).
    `kanonik_ad`: bulunan sayfa bellekte beklenen ada çevrilir (okuyucular sayfayı adıyla arar; dosyaya dokunulmaz)."""
    ws = sayfa_bul(wb, beklenen, esanlamlar)
    if ws is None:
        veri = veri_sayfalari(wb)
        if len(veri) == 1 or (ilk_sayfaya_dus and veri):
            ws = veri[0]
        else:
            adlar = ", ".join(w.title for w in veri[:10])
            raise DogrulamaHatasi(f"{beklenen} sayfası bulunamadı (dosyadaki sayfalar: {adlar}). Sayfayı '{beklenen}' diye adlandırın "
                                  "ya da yalnız bu sayfayı içeren tek sayfalık dosya yükleyin.",
                                  {"sayfa": beklenen, "dosyadaki_sayfalar": [w.title for w in veri[:20]]}, kod="sayfa_yok")
    if kanonik_ad and ws.title != beklenen and beklenen not in wb.sheetnames:
        ws.title = beklenen
    return ws


# ---------------------------------------------------------------- yedek + geri al
def yedekle(s: Session, alan: str, kapsam, veri: dict, ozet_metni: str, kaynak_dosya: str | None, kullanici: str) -> m.YuklemeYedegi:
    return yedek_kaydet(s, alan, str(kapsam), veri, ozet=ozet_metni, kaynak_dosya=kaynak_dosya, kullanici=kullanici)


def yedek_guncelle(y: m.YuklemeYedegi, **ek) -> None:
    """Yazma sırasında oluşan kimlikleri (eklenen kayıtlar) yedeğe ekler. JSON alanı yeniden atanır (değişiklik algılansın)."""
    y.veri = {**(y.veri or {}), **ek}


def son_yukleme(s: Session, alan: str, kapsam) -> dict:
    return {"son": yedek_ozeti(son_yedek(s, alan, str(kapsam)))}


def geri_al(s: Session, alan: str, kapsam, kullanici: str) -> dict:
    y = son_yedek_zorunlu(s, alan, str(kapsam))
    GERI_ALICILAR[alan](s, y.veri or {}, kullanici)
    geri_alindi_isaretle(s, y)
    s.add(m.DegisiklikKaydi(tablo="yukleme_yedegi", kayit_id=y.id, islem="geri_al", eski=None, kullanici=kullanici,
                            yeni={"alan": alan, "kapsam": str(kapsam), "ozet": y.ozet, "kaynak_dosya": y.kaynak_dosya}))
    s.flush()
    return {"geri_alinan": yedek_ozeti(y), "mesaj": f"Son yükleme geri alındı ({y.ozet})."}


def _d(v) -> Decimal | None:
    return None if v is None else Decimal(str(v))


def _s(v) -> str | None:
    return None if v is None else str(v)


# --- fiyatlar (fiyat listesi, satın alma): eklenen fiyat kayıtları silinir, açılan kartlar kaldırılır, güncellenen kartlar geri yazılır
def malzeme_karti(mz: m.Malzeme) -> dict:
    return {"ad": mz.ad, "tip": mz.tip, "birim": mz.birim, "para_birimi": mz.para_birimi, "zs": mz.zs}


def _fiyatlari_geri_al(s: Session, veri: dict, kullanici: str) -> None:
    for fid in veri.get("fiyat_idleri", []):
        k = s.get(m.MalzemeFiyati, fid)
        if k is None:
            continue
        s.add(m.DegisiklikKaydi(tablo="malzeme_fiyati", kayit_id=k.id, islem="geri_al_sil", yeni=None, kullanici=kullanici,
                                eski={"malzeme_id": k.malzeme_id, "senaryo_id": k.senaryo_id, "fiyat": str(k.fiyat), "para_birimi": k.para_birimi,
                                      "gecerlilik_basi": k.gecerlilik_basi.isoformat(), "kaynak": k.kaynak}))
        s.delete(k)
    s.flush()
    for kod, kart in (veri.get("kart_eski") or {}).items():
        mz = s.scalar(select(m.Malzeme).where(m.Malzeme.kod == kod))
        if mz is None:
            continue
        simdi = malzeme_karti(mz)
        if simdi != kart:
            for a, v in kart.items():
                setattr(mz, a, v)
            s.add(m.DegisiklikKaydi(tablo="malzeme", kayit_id=mz.id, islem="geri_al", eski=simdi, yeni=kart, kullanici=kullanici))
    for kod in veri.get("yeni_malzemeler", []):
        mz = s.scalar(select(m.Malzeme).where(m.Malzeme.kod == kod))
        if mz is None:
            continue
        fiyat_var = s.scalar(select(func.count()).select_from(m.MalzemeFiyati).where(m.MalzemeFiyati.malzeme_id == mz.id))
        recetede = s.scalar(select(func.count()).select_from(m.ReceteSatiri).where(m.ReceteSatiri.malzeme_kodu == kod))
        if fiyat_var or recetede:   # yükleme sonrası başka yerde kullanılmış: silinmez, pasifleştirilir
            if mz.aktif:
                mz.aktif = False
                s.add(m.DegisiklikKaydi(tablo="malzeme", kayit_id=mz.id, islem="geri_al_pasif", eski={"aktif": True}, yeni={"aktif": False},
                                        kullanici=kullanici))
            continue
        s.add(m.DegisiklikKaydi(tablo="malzeme", kayit_id=mz.id, islem="geri_al_sil", eski={"kod": kod, **malzeme_karti(mz)}, yeni=None,
                                kullanici=kullanici))
        s.delete(mz)
    s.flush()


# --- üretim adetleri
KAPASITE_ALANLARI = ("urun_ad", "net_kapasite", "net_sure", "toplam_kapasite", "toplam_sure", "hedef_uretim", "ortalama_isci")


def kapasite_icerik(k: m.UretimKapasitesi) -> dict:
    return {a: (getattr(k, a) if a == "urun_ad" else str(getattr(k, a))) for a in KAPASITE_ALANLARI}


def _kapasite_geri_al(s: Session, veri: dict, kullanici: str) -> None:
    sid = veri["senaryo_id"]
    for kod, eski in (veri.get("eski") or {}).items():
        k = s.scalar(select(m.UretimKapasitesi).where(m.UretimKapasitesi.senaryo_id == sid, m.UretimKapasitesi.urun_kodu == kod))
        if k is None:
            k = m.UretimKapasitesi(senaryo_id=sid, urun_kodu=kod, olusturan=kullanici, **{a: (v if a == "urun_ad" else Decimal(v)) for a, v in eski.items()})
            s.add(k); s.flush()
            simdi = None
        else:
            simdi = kapasite_icerik(k)
            for a, v in eski.items():
                setattr(k, a, v if a == "urun_ad" else Decimal(v))
        s.add(m.DegisiklikKaydi(tablo="uretim_kapasitesi", kayit_id=k.id, islem="geri_al", eski=simdi, yeni=eski, kullanici=kullanici))
    for kod in veri.get("yeni_kodlar", []):
        k = s.scalar(select(m.UretimKapasitesi).where(m.UretimKapasitesi.senaryo_id == sid, m.UretimKapasitesi.urun_kodu == kod))
        if k is not None:
            s.add(m.DegisiklikKaydi(tablo="uretim_kapasitesi", kayit_id=k.id, islem="geri_al_sil", eski=kapasite_icerik(k), yeni=None,
                                    kullanici=kullanici))
            s.delete(k)
    s.flush()


# --- gider dağıtım
def havuz_icerik(h: m.GiderHavuzu) -> dict:
    return {"ad": h.ad, "toplam_tutar": str(h.toplam_tutar), "baz_tipi": h.baz_tipi, "baz_miktar": _s(h.baz_miktar),
            "taban_tutar": _s(h.taban_tutar), "carpanlar": h.carpanlar or None,
            "anahtarlar": [[a.alt_kalem, str(a.pay_orani), str(a.baz_miktar)] for a in h.anahtarlar]}


def ambalaj_icerik(liste: list[m.AmbalajSinifi]) -> list[list]:
    return [[a.ad, str(a.hacim), str(a.uretim_adedi), str(a.katsayi)] for a in liste]


def _gider_geri_al(s: Session, veri: dict, kullanici: str) -> None:
    sid = veri["senaryo_id"]
    for kod, eski in (veri.get("havuzlar") or {}).items():
        h = s.scalar(select(m.GiderHavuzu).where(m.GiderHavuzu.senaryo_id == sid, m.GiderHavuzu.kod == kod))
        simdi = havuz_icerik(h) if h is not None else None
        if eski is None:
            if h is not None:
                s.delete(h)
                s.add(m.DegisiklikKaydi(tablo="gider_havuzu", kayit_id=h.id, islem="geri_al_sil", eski=simdi, yeni=None, kullanici=kullanici))
            continue
        if h is None:
            h = m.GiderHavuzu(senaryo_id=sid, kod=kod, ad=eski["ad"], toplam_tutar=Decimal(eski["toplam_tutar"]), baz_tipi=eski["baz_tipi"],
                              olusturan=kullanici)
            s.add(h)
        h.ad, h.toplam_tutar, h.baz_tipi = eski["ad"], Decimal(eski["toplam_tutar"]), eski["baz_tipi"]
        h.baz_miktar, h.taban_tutar, h.carpanlar = _d(eski["baz_miktar"]), _d(eski["taban_tutar"]), eski["carpanlar"]
        h.anahtarlar = [m.DagitimAnahtari(alt_kalem=a, pay_orani=Decimal(p), baz_miktar=Decimal(b)) for a, p, b in eski["anahtarlar"]]
        s.flush()
        s.add(m.DegisiklikKaydi(tablo="gider_havuzu", kayit_id=h.id, islem="geri_al", eski=simdi, yeni=eski, kullanici=kullanici))
    if "ambalaj" in veri:
        mevcut = list(s.scalars(select(m.AmbalajSinifi).where(m.AmbalajSinifi.senaryo_id == sid).order_by(m.AmbalajSinifi.id)))
        simdi = ambalaj_icerik(mevcut)
        if simdi != veri["ambalaj"]:
            for a in mevcut:
                s.delete(a)
            s.add_all([m.AmbalajSinifi(senaryo_id=sid, ad=ad, hacim=Decimal(hc), uretim_adedi=Decimal(u), katsayi=Decimal(k), olusturan=kullanici)
                       for ad, hc, u, k in veri["ambalaj"]])
            s.add(m.DegisiklikKaydi(tablo="ambalaj_sinifi", kayit_id=sid, islem="geri_al", eski=simdi, yeni=veri["ambalaj"], kullanici=kullanici))
    s.flush()


# --- reçete: yükleme yeni versiyon açar; geri alınca yeni versiyon silinir, önceki aktif versiyon yeniden aktif olur
def _recete_geri_al(s: Session, veri: dict, kullanici: str) -> None:
    sid = veri["senaryo_id"]
    for x in veri.get("urunler", []):
        yeni = s.get(m.Recete, x["yeni_recete_id"])
        if yeni is not None:
            s.add(m.DegisiklikKaydi(tablo="recete", kayit_id=yeni.id, islem="geri_al_sil", yeni=None, kullanici=kullanici,
                                    eski={"urun_id": yeni.urun_id, "versiyon": yeni.versiyon, "satir": len(yeni.satirlar)}))
            s.delete(yeni)
            s.flush()
        if x.get("onceki_aktif_id"):
            onceki = s.get(m.Recete, x["onceki_aktif_id"])
            if onceki is not None:
                for r in s.scalars(select(m.Recete).where(m.Recete.urun_id == onceki.urun_id, m.Recete.senaryo_id == sid, m.Recete.aktif == True)):  # noqa: E712
                    r.aktif = False
                onceki.aktif = True
        if x.get("yeni_urun"):
            u = s.get(m.Urun, x["urun_id"])
            if u is None:
                continue
            for h in s.scalars(select(m.UretimHedefi).where(m.UretimHedefi.urun_id == u.id, m.UretimHedefi.senaryo_id == sid)):
                s.delete(h)
            s.flush()
            baglar = sum(s.scalar(select(func.count()).select_from(t).where(t.urun_id == u.id)) or 0
                         for t in (m.Recete, m.UretimHedefi, m.SatisGecmisi, m.ListeFiyati, m.StokDevri, m.MaliyetHesabi))
            if baglar:
                u.aktif = False
                s.add(m.DegisiklikKaydi(tablo="urun", kayit_id=u.id, islem="geri_al_pasif", eski={"aktif": True}, yeni={"aktif": False},
                                        kullanici=kullanici))
            else:
                s.add(m.DegisiklikKaydi(tablo="urun", kayit_id=u.id, islem="geri_al_sil", eski={"kod": u.kod, "ad": u.ad}, yeni=None,
                                        kullanici=kullanici))
                s.delete(u)
    s.flush()


# --- stokta kalan
STOK_ALANLARI = ("adet", "birim_maliyet", "enflasyon", "uretim_adedi")


def stok_icerik(k: m.StokDevri) -> dict:
    return {a: _s(getattr(k, a)) for a in STOK_ALANLARI}


def _stok_geri_al(s: Session, veri: dict, kullanici: str) -> None:
    sid = veri["senaryo_id"]
    for urun_id, eski in (veri.get("eski") or {}).items():
        urun_id = int(urun_id)
        k = s.scalar(select(m.StokDevri).where(m.StokDevri.urun_id == urun_id, m.StokDevri.senaryo_id == sid))
        simdi = stok_icerik(k) if k is not None else None
        if eski is None:
            if k is not None:
                s.delete(k)
                s.add(m.DegisiklikKaydi(tablo="stok_devri", kayit_id=k.id, islem="geri_al_sil", eski=simdi, yeni=None, kullanici=kullanici))
            continue
        if k is None:
            k = m.StokDevri(urun_id=urun_id, senaryo_id=sid, olusturan=kullanici, adet=Decimal(eski["adet"]))
            s.add(k)
        for a in STOK_ALANLARI:
            setattr(k, a, _d(eski[a]))
        s.flush()
        s.add(m.DegisiklikKaydi(tablo="stok_devri", kayit_id=k.id, islem="geri_al", eski=simdi, yeni=eski, kullanici=kullanici))
    s.flush()


# --- satış geçmişi: yükleme ekler; geri alınca eklenen satırlar silinir
def _satis_geri_al(s: Session, veri: dict, kullanici: str) -> None:
    n = 0
    for sid_ in veri.get("eklenen_idler", []):
        k = s.get(m.SatisGecmisi, sid_)
        if k is not None:
            s.delete(k); n += 1
    s.add(m.DegisiklikKaydi(tablo="satis_gecmisi", kayit_id=0, islem="geri_al", eski={"silinen": n}, yeni=None, kullanici=kullanici))
    s.flush()


# --- liste fiyatları (upsert): eski değerler geri yazılır, yeni açılan satırlar silinir
LISTE_ALANLARI = ("liste_fiyati", "birim_maliyet", "bolen", "ornek")


def liste_icerik(k: m.ListeFiyati) -> dict:
    return {"liste_fiyati": str(k.liste_fiyati), "birim_maliyet": _s(k.birim_maliyet), "bolen": _s(k.bolen), "ornek": bool(k.ornek)}


def _liste_geri_al(s: Session, veri: dict, kullanici: str) -> None:
    for x in veri.get("satirlar", []):
        k = s.scalar(select(m.ListeFiyati).where(m.ListeFiyati.urun_id == x["urun_id"], m.ListeFiyati.yil == x["yil"],
                                                 m.ListeFiyati.pazar == x["pazar"]))
        simdi = liste_icerik(k) if k is not None else None
        eski = x["eski"]
        if eski is None:
            if k is not None:
                s.delete(k)
                s.add(m.DegisiklikKaydi(tablo="liste_fiyati", kayit_id=k.id, islem="geri_al_sil", eski=simdi, yeni=None, kullanici=kullanici))
            continue
        if k is None:
            k = m.ListeFiyati(urun_id=x["urun_id"], yil=x["yil"], pazar=x["pazar"], liste_fiyati=Decimal(eski["liste_fiyati"]), olusturan=kullanici)
            s.add(k)
        k.liste_fiyati, k.birim_maliyet, k.bolen, k.ornek = Decimal(eski["liste_fiyati"]), _d(eski["birim_maliyet"]), _d(eski["bolen"]), eski["ornek"]
        s.flush()
        s.add(m.DegisiklikKaydi(tablo="liste_fiyati", kayit_id=k.id, islem="geri_al", eski=simdi, yeni=eski, kullanici=kullanici))
    s.flush()


# --- tüm çalışma kitabı, tamamla modu: yalnız eksikleri EKLER (var olan kayda dokunmaz); geri alınca eklenen kayıtlar silinir.
# Sıra silme sırasıdır (bağımlı kayıtlar önce). Ürün / malzeme kartı başka yerde kullanılıyorsa silinmez, pasifleştirilir.
TAMAMLA_TABLOLARI = (m.Recete, m.UretimHedefi, m.UretimKapasitesi, m.ParametreDegeri, m.MetinParametre, m.FireKurali, m.MalzemeFiyati,
                     m.GiderHavuzu, m.AmbalajSinifi, m.Urun, m.Malzeme)


def _tamamla_geri_al(s: Session, veri: dict, kullanici: str) -> None:
    eklenen = veri.get("eklenen") or {}
    sayilar = {}
    for t in TAMAMLA_TABLOLARI:
        idler = eklenen.get(t.__tablename__, [])
        n = 0
        for i in idler:
            k = s.get(t, i)
            if k is None:
                continue
            if t is m.Urun:
                bag = sum(s.scalar(select(func.count()).select_from(x).where(x.urun_id == k.id)) or 0
                          for x in (m.Recete, m.UretimHedefi, m.SatisGecmisi, m.ListeFiyati, m.StokDevri, m.MaliyetHesabi))
                if bag:
                    k.aktif = False
                    continue
            if t is m.Malzeme:
                bag = (s.scalar(select(func.count()).select_from(m.MalzemeFiyati).where(m.MalzemeFiyati.malzeme_id == k.id)) or 0) + \
                      (s.scalar(select(func.count()).select_from(m.ReceteSatiri).where(m.ReceteSatiri.malzeme_kodu == k.kod)) or 0)
                if bag:
                    k.aktif = False
                    continue
            s.delete(k); n += 1
        s.flush()
        if idler:
            sayilar[t.__tablename__] = n
    # Tamamla, reçetesi olmayan ürünlere reçete açar; o ürünlerin senaryoda önceki aktif reçetesi yoktu (eklenen versiyon silinince boş kalır).
    s.add(m.DegisiklikKaydi(tablo="senaryo", kayit_id=veri["senaryo_id"], islem="geri_al_tamamla", eski={"silinen": sayilar}, yeni=None,
                            kullanici=kullanici))
    s.flush()


GERI_ALICILAR = {
    "excel_tam": _tamamla_geri_al,
    "fiyat_listesi": _fiyatlari_geri_al,
    "satin_alma": _fiyatlari_geri_al,
    "uretim_adetleri": _kapasite_geri_al,
    "gider_dagitim": _gider_geri_al,
    "recete": _recete_geri_al,
    "stok_devri": _stok_geri_al,
    "satis_gecmisi": _satis_geri_al,
    "liste_fiyatlari": _liste_geri_al,
}
