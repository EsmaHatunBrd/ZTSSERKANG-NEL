from datetime import date
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..depo import modeller as m
from ..servisler import aile as aile_servisi, fiyat_servisi, karsilastirma_servisi as ks, onbellek, hesap_servisi as hs, recete_servisi as rs, teklif_servisi as ts
from ..servisler.donusum import decimal_str, zaman_iso
from ..servisler.hatalar import BulunamadiHatasi, ServisHatasi
from fiyat_motoru.para import SIFIR
from .bagimliliklar import OturumDep, SenaryoDep, kullanici_ver
from .semalar import AileDegisCikis, AileGiris, DegisiklikListesi, HATA_404_409_422, HATA_404_422, HesapKaydiYaniti, HesapKayitCikis, HesapListesi, HesapYaniti, HesaplaGiris, KodDegistirCikis, KodDegistirGiris, KurallaraBirakCikis, KurallaraBirakGiris, PasifCikis, ReceteCikis, ReceteDetayCikis, ReceteEkleCikis, ReceteSatirGiris, ReceteVersiyonListesi, TopluKaydetCikis, TopluKaydetGiris, UretimHedefiCikis, UretimHedefiGiris, UretimHedefiNedenliGiris, UrunCikis, UrunGiris, UrunListesi, UyariListesi

router = APIRouter(tags=["urunler"])

SAYISAL = ("recete_maliyeti", "gug", "faaliyet", "finans", "gider_yuzdesi", "maliyet_tl", "maliyet_usd", "maliyet_eur", "satis_tl", "uretim_adedi",
           "maliyet_tl_firesiz", "maliyet_usd_firesiz", "gecen_yil_tl", "enflasyon_fark_yuzde", "hedef_adet_maliyet_tl", "ortalama_maliyet_tl")


def _hesapla_satirlar(s: Session, senaryo: int, tarih: date | None = None, gecici: bool | None = None, tum: bool = False) -> tuple[list[dict], list[dict]]:
    """(satırlar, uyarılar): tek toplu hesaptan; uyarılar gecici süzgecinden etkilenmez (hesap_servisi.uyarilar ile aynı biçim).
    Canlı hesaplanan dashboard satırları (snapshot değil). Hatalı ürün: sayısal alanlar None, hata mesajı dolu.
    gecici: True yalnız geçici kodlu (SAYFA-*) ürünler, False yalnız ERP kodlular, None hepsi.
    tum: False yalnız senaryo üyesi (aktif reçeteli) ürünler; True tüm aktif ürünler (reçetesizler 'reçete yok' hata satırı)."""
    urunler = {u.kod: u for u in hs.urunler(s, aktif=False)}
    sen = hs.senaryo_getir(s, senaryo)
    gecen = ks.gecen_yil_toplu(s, sen)   # tek sorgu: {urun_id: özet}
    hedefler = {k.urun_kodu: k.hedef_uretim for k in s.scalars(select(m.UretimKapasitesi).where(m.UretimKapasitesi.senaryo_id == senaryo))}
    out, uyarilar = [], []
    for kod, c in hs.toplu_hesapla(s, senaryo, tarih, tum):
        u = urunler[kod]
        if not isinstance(c, Exception):
            uyarilar += [{"urun_kodu": kod, "uyari": x} for x in c.sonuc.uyarilar]
        if gecici is not None and u.gecici_kod != gecici:
            continue
        satir = {"id": u.id, "kod": kod, "ad": u.ad, "ambalaj_hacmi": str(u.ambalaj_hacmi), "ambalaj_etiket": aile_servisi.ambalaj_etiket(u.ad), "hat": u.hat, "gecici_kod": u.gecici_kod}
        if isinstance(c, Exception):
            satir.update({a: None for a in SAYISAL})
            satir.update(uyari_sayisi=None, hata=str(getattr(c, "mesaj", None) or c), enflasyon_durumu=None, stok_etkisi=False)
        else:
            r = c.sonuc
            finans = r.finansman.get("TL", SIFIR)
            pay = r.uretim_gideri_toplami + r.diger_giderler_toplami + finans
            satir.update(decimal_str({"recete_maliyeti": r.malzeme_toplami, "gug": r.uretim_gideri_toplami, "faaliyet": r.diger_giderler_toplami, "finans": finans,
                                      "gider_yuzdesi": (pay / r.finansman_dahil_maliyet_tl) if r.finansman_dahil_maliyet_tl else None,
                                      "maliyet_tl": r.finansman_dahil_maliyet_tl, "maliyet_usd": r.doviz_maliyet.get("USD"), "maliyet_eur": r.doviz_maliyet.get("EUR"),
                                      "satis_tl": r.satis_fiyati_tl, "uretim_adedi": c.girdi.uretim.vardiya_uretim_adedi,
                                      "maliyet_tl_firesiz": r.firesiz.finansman_dahil_maliyet_tl if r.firesiz else None,
                                      "maliyet_usd_firesiz": r.firesiz.doviz_maliyet.get("USD") if r.firesiz else None}))
            stok = c.stok_devri or {}
            satir.update(ortalama_maliyet_tl=decimal_str(stok.get("ortalama_maliyet")), stok_etkisi=bool(stok.get("stok_etkisi")))
            satir.update(uyari_sayisi=len(r.uyarilar), hata=None, **_karsilastirma_alanlari(s, u, sen, tarih, c, gecen.get(u.id), hedefler.get(kod)))
        out.append(satir)
    return out, uyarilar


def _karsilastirma_alanlari(s: Session, u, sen, tarih: date | None, c, gecen: dict | None, hedef) -> dict:
    """Dashboard satırının geçen yıl / enflasyon eşiği / hedef adet alanları (hepsi null olabilir). Hata satırı kırmaz."""
    d = {"gecen_yil_tl": None, "enflasyon_durumu": None, "enflasyon_fark_yuzde": None, "hedef_adet_maliyet_tl": None}
    tl = ((ks.enflasyon_esigi_hesapla(gecen, c) or {}).get("TL"))   # saf hesap: ek sorgu yok (toplu `gecen` yetkilidir)
    if gecen and "TL" in gecen["para_birimleri"]:
        d["gecen_yil_tl"] = gecen["para_birimleri"]["TL"]["fiyat"]
    if tl:
        d["enflasyon_durumu"], d["enflasyon_fark_yuzde"] = tl["durum"], tl["fark_yuzde"]
    if hedef is not None:
        try:
            etki = ks.uretim_adedi_etkisi(s, u, sen, tarih, hesap=c, hedef=hedef)
            d["hedef_adet_maliyet_tl"] = etki["maliyet_tl_hedef"] if etki else None
        except (ServisHatasi, KeyError, ValueError, ArithmeticError):   # ArithmeticError: Decimal InvalidOperation vb.
            pass   # hedef adetle hesap yapılamadı: alan null, satır kırılmaz
    return d


def dashboard_satirlari(s: Session, senaryo: int, tarih: date | None = None, gecici: bool | None = None, tum: bool = False) -> list[dict]:
    """Canlı (önbelleksiz) dashboard satırları; bkz. _hesapla_satirlar."""
    return _hesapla_satirlar(s, senaryo, tarih, gecici, tum)[0]


# Gider satırı kodu -> birim (uretim_gideri.py'deki satırların miktar birimi); finansman_tl birimsizdir.
GIDER_BIRIMI = {"mal_kabul_iscilik": "KG", "mal_kabul_gug": "KG", "dolum_iscilik": "SN", "etiket_iscilik": "SN", "endirekt_iscilik": "SN",
                "elektrik": "SN", "dogalgaz": "SN", "amortisman": "SN", "diger_gug": "SN", "pazarlama": "ADET", "yonetim": "ADET"}
URETIM_CIKIS_ALANLARI = ("pazar", "hat", "taze_tursu_sinifi", "ambalaj_hacmi", "suzme_kg", "vardiya_uretim_adedi", "dolum_personel", "etiketleme_adedi",
                         "etiket_personel", "mal_kabul_miktar_kg", "mal_kabul_fire", "pazarlama_yonetim_uygula")


def _toplamlar(sonuc: dict) -> dict:
    return {"malzeme": sonuc["malzeme_toplami"], "direkt_iscilik": sonuc["direkt_iscilik_toplami"], "gug": sonuc["gug_toplami"],
            "uretim_gideri": sonuc["uretim_gideri_toplami"], "diger": sonuc["diger_giderler_toplami"], "giydirilmis": sonuc["giydirilmis_maliyet"],
            "finansman_tl": sonuc["finansman"].get("TL"), "maliyet_tl": sonuc["finansman_dahil_maliyet_tl"],
            "maliyet_usd": sonuc["doviz_maliyet"].get("USD"), "maliyet_eur": sonuc["doviz_maliyet"].get("EUR"),
            "maliyet_gbp": sonuc["doviz_maliyet"].get("GBP"), "maliyet_zar": sonuc["doviz_maliyet"].get("ZAR"),
            "finansman": dict(sonuc["finansman"])}


def _fiyatlar(sonuc: dict, parametreler: dict | None = None) -> dict:
    d = {"satis_tl": sonuc["satis_fiyati_tl"], "satis_usd": sonuc["satis_fiyati_doviz"].get("USD"), "satis_eur": sonuc["satis_fiyati_doviz"].get("EUR"),
         "satis_gbp": sonuc["satis_fiyati_doviz"].get("GBP"), "satis_zar": sonuc["satis_fiyati_doviz"].get("ZAR"),
         "suzme_kg_tl": sonuc["suzme_kg_fiyati_tl"], "teklifler_usd": sonuc["teklifler_usd"], "teklif_kar_oranlari": None, "satis_kar_orani": None}
    if parametreler is not None:
        d["teklif_kar_oranlari"] = list(parametreler.get("teklif_kar_oranlari", []))
        d["satis_kar_orani"] = parametreler.get("satis_kar_orani")
    return d


def _uretim_ozeti(uretim: dict | None, parametreler: dict | None) -> dict | None:
    if not uretim or any(a not in uretim for a in URETIM_CIKIS_ALANLARI):
        return None
    return {**{a: uretim[a] for a in URETIM_CIKIS_ALANLARI}, "vardiya_saati": (parametreler or {}).get("vardiya_saati")}


def _parametre_ozeti(parametreler: dict | None, kullanilan: dict) -> dict | None:
    if not parametreler:
        return None
    return {"enflasyon": parametreler["enflasyon"], "maliyet_sapma": kullanilan.get("maliyet_sapma"), "kurlar": dict(parametreler["kurlar"]),
            "faiz": dict(parametreler["faiz_oranlari"]), "stok_ay": dict(parametreler["stok_sureleri_ay"]), "satis_kar": parametreler["satis_kar_orani"],
            "teklif_kar": list(parametreler["teklif_kar_oranlari"])}


def _gorunum(urun_kodu: str, senaryo_id: int, tarih: date, sonuc: dict, recete: list[dict], fire_kaynaklari: list, kullanilan: dict,
             para_birimleri: dict[str, str | None] | None = None, zs_haritasi: dict[str, str | None] | None = None,
             uretim: dict | None = None, parametreler: dict | None = None, notlar: list[str] | None = None,
             seviyeler: list[int | None] | None = None, stok_devri: dict | None = None, satis_ortalamadan: bool = False) -> dict:
    """Tek çizici: canlı hesap ve kayıtlı hesap aynı sözlük biçimlerinden (decimal_str çıktısı) bu yanıtı üretir.
    Firesiz bloklar `sonuc["firesiz"]`dan gelir; firesiz alanı olmayan eski snapshot'larda None döner.
    uretim/parametreler/notlar/zs/birim eski snapshot'larda bulunmayabilir (None / boş)."""
    def elle(i: int, alan: str):
        return recete[i].get(alan) if i < len(recete) else None
    malzeme_satiri = lambda s_: s_.get("grup") == "malzeme"

    def birim(i: int, s_: dict):
        if malzeme_satiri(s_):
            return elle(i, "birim")
        return GIDER_BIRIMI.get(s_.get("kod"))
    def doviz(i: int, s_: dict):
        if not malzeme_satiri(s_):
            return None
        return elle(i, "para_birimi_elle") or (para_birimleri.get(s_.get("kod")) if para_birimleri is not None else None)

    def zs(i: int, s_: dict):
        if not malzeme_satiri(s_):
            return None
        return elle(i, "zs_elle") or (zs_haritasi.get(s_.get("kod")) if zs_haritasi is not None else None)
    satirlar = [dict(s_, sira=(i + 1) if malzeme_satiri(s_) else None, doviz=doviz(i, s_),
                     fire_orani=recete[i]["fire_orani"] if i < len(recete) else None,
                     fire_kaynagi=fire_kaynaklari[i] if i < len(fire_kaynaklari) else None,
                     tutar_firesiz=s_.get("tutar_firesiz"), miktar_kaynagi=s_.get("miktar_kaynagi"), fiyat_kaynagi=s_.get("fiyat_kaynagi"),
                     brut_miktar_elle=elle(i, "brut_miktar_elle"), birim_fiyat_elle=elle(i, "birim_fiyat_elle"),
                     birim=birim(i, s_), zs=zs(i, s_),
                     zs_elle=bool(malzeme_satiri(s_) and elle(i, "zs_elle")), doviz_elle=bool(malzeme_satiri(s_) and elle(i, "para_birimi_elle")),
                     elle_alanlar=list(s_.get("elle_alanlar") or []),
                     dugum_tipi=elle(i, "dugum_tipi") if malzeme_satiri(s_) else None,
                     seviye=seviyeler[i] if seviyeler is not None and malzeme_satiri(s_) and i < len(seviyeler) else None)
               for i, s_ in enumerate(sonuc["satirlar"])]
    firesiz = sonuc.get("firesiz")
    return {"urun_kodu": urun_kodu, "senaryo_id": senaryo_id, "hesap_tarihi": tarih.isoformat(), "satirlar": satirlar,
            "toplamlar": _toplamlar(sonuc), "fiyatlar": _fiyatlar(sonuc, parametreler),
            "toplamlar_firesiz": _toplamlar(firesiz) if firesiz else None, "fiyatlar_firesiz": _fiyatlar(firesiz, parametreler) if firesiz else None,
            "kullanilan_parametreler": kullanilan, "uyarilar": sonuc["uyarilar"],
            "uretim": _uretim_ozeti(uretim, parametreler), "parametreler": _parametre_ozeti(parametreler, kullanilan), "notlar": list(notlar or []),
            "stok_devri": stok_devri or None, "satis_ortalamadan": bool(satis_ortalamadan)}


def _hesap_yaniti(c, urun_kodu, senaryo_id, tarih):
    pb = {k: mz.para_birimi for k, mz in (c.malzemeler or {}).items()}
    zs = {k: mz.zs for k, mz in (c.malzemeler or {}).items()}
    return _gorunum(urun_kodu, senaryo_id, tarih, decimal_str(c.sonuc), decimal_str(list(c.girdi.recete)), c.fire_kaynaklari, decimal_str(c.kullanilan_parametreler), pb,
                    zs, decimal_str(c.girdi.uretim), decimal_str(c.parametreler), c.notlar, c.seviyeler, decimal_str(c.stok_devri), c.satis_ortalamadan)


def _hedef_dict(h) -> dict:
    return {"id": h.id, **decimal_str({a: getattr(h, a) for a in hs.URETIM_ALANLARI}), "gider_elle": h.gider_elle}


def _urun_dict(u) -> dict:
    return {"id": u.id, "kod": u.kod, "ad": u.ad, "ambalaj_hacmi": str(u.ambalaj_hacmi), "hat": u.hat, "taze_tursu_sinifi": u.taze_tursu_sinifi,
            "suzme_kg": str(u.suzme_kg), "pazar": u.pazar, "aktif": u.aktif, "gecici_kod": u.gecici_kod, "marka": u.marka or None,
            "aile": u.aile, "aile_ad": aile_servisi.aile_gorunen_ad(u.aile, [u]) if u.aile else None, "ambalaj_etiket": aile_servisi.ambalaj_etiket(u.ad)}


def _anahtar(senaryo: int, tarih: date | None, gecici, tum: bool = False) -> tuple:
    """Önbellek anahtarı; `tum` (üye/tüm ürün) dahil: iki görünüm ayrı girdilerdir."""
    return (senaryo, (tarih or date.today()).isoformat(), gecici, bool(tum))


def _onbellekli(s: Session, senaryo: int, tarih: date | None, gecici: bool | None, yenile: bool, yanit: Response, uyari: bool = False, tum: bool = False):
    """Önbellekten (isabet) ya da hesaplayarak (hesap) satırları/uyarıları verir; her hesap iki anahtarı da doldurur."""
    k_satir, k_uyari = _anahtar(senaryo, tarih, gecici, tum), _anahtar(senaryo, tarih, "uyarilar", tum)
    if yenile:
        onbellek.hesap_say()
    deger = None if yenile else onbellek.al(k_uyari if uyari else k_satir)
    yanit.headers["X-Onbellek"] = "hesap" if deger is None else "isabet"
    if deger is None:
        nesil = onbellek.nesil()   # hesap sürerken yazma olursa (temizle) bu sonuç eski sayılır, önbelleğe konmaz
        satirlar, uyarilar = _hesapla_satirlar(s, senaryo, tarih, gecici, tum)
        onbellek.koy(k_satir, satirlar, nesil); onbellek.koy(k_uyari, uyarilar, nesil)
        deger = uyarilar if uyari else satirlar
    return deger


@router.get("/urunler", response_model=UrunListesi, responses=HATA_404_422)
def listele(s: OturumDep, sen: SenaryoDep, yanit: Response, tarih: date | None = None, gecici: bool | None = None,
            sayfa: int = Query(1, ge=1), boyut: int = Query(50, ge=1, le=500), yenile: bool = Query(False), tum: bool = Query(False)):
    """Varsayılan: yalnız senaryo üyesi (o senaryoda aktif reçetesi olan) ürünler. tum=1: tüm aktif ürünler (reçetesizler hata satırı)."""
    satirlar = _onbellekli(s, sen.id, tarih, gecici, yenile, yanit, tum=tum)
    bas = (sayfa - 1) * boyut
    return {"kayitlar": satirlar[bas:bas + boyut], "toplam": len(satirlar),
            "enflasyon_altinda_toplam": sum(1 for x in satirlar if x.get("enflasyon_durumu") == "altinda")}   # tüm satırlar (sayfa değil)


@router.get("/uyarilar", response_model=UyariListesi, responses=HATA_404_422)
def uyarilar(s: OturumDep, sen: SenaryoDep, yanit: Response, tarih: date | None = None, yenile: bool = Query(False), tum: bool = Query(False)):
    k = _onbellekli(s, sen.id, tarih, None, yenile, yanit, uyari=True, tum=tum)
    return {"kayitlar": k, "toplam": len(k)}


@router.get("/urunler/{kod}", response_model=UrunCikis, responses=HATA_404_422, response_model_exclude_unset=True)
def getir(s: OturumDep, kod: str, senaryo: int | None = None):
    u = hs.urun_getir(s, kod)
    d = _urun_dict(u)
    if senaryo is not None:
        sen = hs.senaryo_getir(s, senaryo)   # bilinmeyen senaryo -> 404 (SenaryoDep ile aynı kural; burada senaryo isteğe bağlı)
        try:
            d["uretim_hedefi"] = _hedef_dict(hs.uretim_hedefi_getir(s, u.id, sen.id))
        except BulunamadiHatasi:
            d["uretim_hedefi"] = None
        d["senaryoda"] = rs.aktif_recete_veya_none(s, u.id, sen.id) is not None   # senaryo üyeliği: aktif reçete
    return d


@router.put("/urunler/{kod}", response_model=UrunCikis, responses=HATA_404_409_422, response_model_exclude_unset=True)
def kaydet(s: OturumDep, kod: str, g: UrunGiris, k: str = Depends(kullanici_ver)):
    return _urun_dict(hs.urun_kaydet(s, kod, g.ad, g.ambalaj_hacmi, g.hat, g.taze_tursu_sinifi, g.suzme_kg, g.pazar, k,
                                     **({"marka": g.marka} if "marka" in g.model_fields_set else {})))


@router.patch("/urunler/{kod}/pasif", response_model=PasifCikis, responses=HATA_404_409_422)
def pasiflestir(s: OturumDep, kod: str, k: str = Depends(kullanici_ver)):
    u = hs.urun_pasiflestir(s, kod, k)
    return {"kod": u.kod, "aktif": u.aktif}


@router.patch("/urunler/{kod}/aile", response_model=AileDegisCikis, responses=HATA_404_409_422)
def aile_degistir(s: OturumDep, kod: str, g: AileGiris, k: str = Depends(kullanici_ver)):
    """{aile: "Görünen Ad"} ürün ailesini elle atar (anahtar sunucuda türetilir, ad saklanır); {aile: null} addan yeniden türetir."""
    u = aile_servisi.aile_degistir(s, kod, g.aile, k)
    return {"kod": u.kod, "aile": u.aile, "aile_ad": aile_servisi.aile_gorunen_ad(u.aile, [u])}


@router.patch("/urunler/{kod}/kod", response_model=KodDegistirCikis, responses=HATA_404_409_422, response_model_exclude_unset=True)
def kod_degistir(s: OturumDep, kod: str, g: KodDegistirGiris, k: str = Depends(kullanici_ver)):
    return _urun_dict(hs.urun_kod_degistir(s, kod, g.yeni_kod, k))


@router.put("/urunler/{kod}/uretim-hedefi", response_model=UretimHedefiCikis, responses=HATA_404_409_422)
def uretim_hedefi(s: OturumDep, kod: str, g: UretimHedefiNedenliGiris, sen: SenaryoDep, k: str = Depends(kullanici_ver)):
    u = hs.urun_getir(s, kod)
    return _hedef_dict(hs.uretim_hedefi_kaydet(s, u.id, sen.id, k, g.neden, **g.model_dump(exclude={"neden"})))


@router.get("/urunler/{kod}/uretim-hedefi", response_model=UretimHedefiCikis, responses=HATA_404_422)
def uretim_hedefi_getir(s: OturumDep, kod: str, sen: SenaryoDep):
    return _hedef_dict(hs.uretim_hedefi_getir(s, hs.urun_getir(s, kod).id, sen.id))


@router.get("/urunler/{kod}/recete", response_model=ReceteCikis, responses=HATA_404_422)
def recete_getir(s: OturumDep, kod: str, sen: SenaryoDep, tarih: date | None = None):
    t = tarih or date.today()
    u = hs.urun_getir(s, kod)
    r = rs.aktif_recete_veya_none(s, u.id, sen.id)
    if r is None:   # senaryo üyesi değil: boş reçete yapısı (404 değil); POST .../recete ilk sürümü açar
        return {"id": None, "versiyon": 0, "kaynak": None, "satirlar": []}
    tipler = {k: mz.tip for k, mz in fiyat_servisi.gecerli_fiyatlar(s, sen.id, t).items()}
    satirlar, kaynaklar = rs.fire_uygulanmis(s, r, sen.id, t, tipler)
    return {"id": r.id, "versiyon": r.versiyon, "kaynak": r.kaynak,
            "satirlar": [{"sira": x.sira, "malzeme_kodu": x.malzeme_kodu, "ad": x.ad, "miktar": str(x.miktar), "birim": x.birim, "dugum_tipi": x.dugum_tipi,
                          "fire_override": None if x.fire_override is None else str(x.fire_override),
                          "brut_miktar_elle": None if x.brut_miktar_elle is None else str(x.brut_miktar_elle),
                          "birim_fiyat_elle": None if x.birim_fiyat_elle is None else str(x.birim_fiyat_elle), "seviye": x.seviye,
                          "zs_elle": x.zs_elle, "para_birimi_elle": x.para_birimi_elle,
                          "fire_orani": str(ms.fire_orani), "fire_kaynagi": kaynak} for x, ms, kaynak in zip(r.satirlar, satirlar, kaynaklar)]}


@router.post("/urunler/{kod}/recete", status_code=201, response_model=ReceteEkleCikis, responses=HATA_404_409_422)
def recete_ekle(s: OturumDep, kod: str, g: list[ReceteSatirGiris], sen: SenaryoDep, k: str = Depends(kullanici_ver)):
    u = hs.urun_getir(s, kod)
    r = rs.yeni_versiyon(s, u.id, sen.id, [x.model_dump() for x in g], "elle", k)
    return {"id": r.id, "versiyon": r.versiyon, "satir_sayisi": len(r.satirlar)}


@router.post("/urunler/{kod}/recete/kurallara-birak", status_code=201, response_model=KurallaraBirakCikis, responses=HATA_404_409_422)
def kurallara_birak(s: OturumDep, kod: str, g: KurallaraBirakGiris, sen: SenaryoDep, k: str = Depends(kullanici_ver)):
    u = hs.urun_getir(s, kod)
    r = rs.kurallara_birak(s, u.id, sen.id, g.siralar, k, g.elle_degerleri_kaldir)
    return {"id": r.id, "versiyon": r.versiyon, "satir_sayisi": len(r.satirlar)}


@router.get("/urunler/{kod}/recete/versiyonlar", response_model=ReceteVersiyonListesi, responses=HATA_404_422)
def recete_versiyonlari(s: OturumDep, kod: str, sen: SenaryoDep):
    u = hs.urun_getir(s, kod)
    k = [{"id": r.id, "versiyon": r.versiyon, "kaynak": r.kaynak, "aktif": r.aktif, "olusturma_zamani": zaman_iso(r.olusturma_zamani)}
         for r in rs.versiyonlar(s, u.id, sen.id)]
    return {"kayitlar": k, "toplam": len(k)}


@router.get("/receteler/{recete_id}", response_model=ReceteDetayCikis, responses=HATA_404_422)
def recete_satirlari(s: OturumDep, recete_id: int):
    r = rs.recete_getir(s, recete_id)
    return {"id": r.id, "urun_id": r.urun_id, "senaryo_id": r.senaryo_id, "versiyon": r.versiyon, "kaynak": r.kaynak, "aktif": r.aktif,
            "satirlar": [{"sira": x.sira, "malzeme_kodu": x.malzeme_kodu, "ad": x.ad, "miktar": str(x.miktar), "birim": x.birim, "dugum_tipi": x.dugum_tipi,
                          "fire_override": None if x.fire_override is None else str(x.fire_override),
                          "brut_miktar_elle": None if x.brut_miktar_elle is None else str(x.brut_miktar_elle),
                          "birim_fiyat_elle": None if x.birim_fiyat_elle is None else str(x.birim_fiyat_elle),
                          "seviye": x.seviye, "zs_elle": x.zs_elle, "para_birimi_elle": x.para_birimi_elle} for x in r.satirlar]}


@router.post("/urunler/{kod}/hesapla", response_model=HesapYaniti, responses=HATA_404_422)
def hesapla(s: OturumDep, kod: str, g: HesaplaGiris):
    t = g.tarih or date.today()
    return _hesap_yaniti(hs.hesapla(s, kod, g.senaryo_id, t, g.override_sozlugu()), kod, g.senaryo_id, t)


@router.post("/urunler/{kod}/hesaplar", status_code=201, response_model=HesapKaydiYaniti, responses=HATA_404_409_422)
def hesap_kaydet(s: OturumDep, kod: str, g: HesaplaGiris, k: str = Depends(kullanici_ver)):
    hs.kilit_denetle(hs.senaryo_getir(s, g.senaryo_id))
    t = g.tarih or date.today()
    h = hs.kaydet(s, hs.hesapla(s, kod, g.senaryo_id, t, g.override_sozlugu()), kod, g.senaryo_id, t, k)
    return {"id": h.id, "olusturan": h.olusturan, "hesap_tarihi": h.hesap_tarihi.isoformat()}


@router.get("/urunler/{kod}/hesaplar", response_model=HesapListesi, responses=HATA_404_422)
def hesaplar(s: OturumDep, kod: str, sen: SenaryoDep):
    u = hs.urun_getir(s, kod)
    hesaplar_ = hs.hesaplar_listele(s, u.id, sen.id)
    son = ts.son_turlar(s, [h.id for h in hesaplar_])
    k = [{"id": h.id, "hesap_tarihi": h.hesap_tarihi.isoformat(), "olusturan": h.olusturan,
          "maliyet_tl": h.sonuc_snapshot.get("finansman_dahil_maliyet_tl"), "satis_tl": h.sonuc_snapshot.get("satis_fiyati_tl"),
          "son_tur_no": son[h.id].tur_no if h.id in son else None, "son_kar_orani": str(son[h.id].kar_orani) if h.id in son else None,
          "son_musteri": son[h.id].musteri if h.id in son else None, "son_durum": son[h.id].durum if h.id in son else None}
         for h in hesaplar_]
    return {"kayitlar": k, "toplam": len(k)}


@router.get("/hesaplar/{hesap_id}", response_model=HesapKayitCikis, responses=HATA_404_422)
def hesap_getir(s: OturumDep, hesap_id: int):
    h = hs.getir(s, hesap_id)
    gs_ = h.girdi_snapshot
    gorunum = _gorunum(hs.urun_getir_id(s, h.urun_id).kod, h.senaryo_id, h.hesap_tarihi, h.sonuc_snapshot, gs_["girdi"]["recete"],
                       gs_.get("fire_kaynaklari", []), gs_.get("kullanilan_parametreler", {}),
                       {k: v.get("para_birimi") for k, v in gs_["malzemeler"].items()} if gs_.get("malzemeler") else None,
                       {k: v.get("zs") for k, v in gs_["malzemeler"].items()} if gs_.get("malzemeler") else None,
                       gs_["girdi"].get("uretim"), gs_.get("parametreler"), gs_.get("notlar"), (gs_.get("recete") or {}).get("seviyeler"),
                       gs_.get("stok_devri"), bool(gs_.get("satis_ortalamadan")))
    return {"id": h.id, "urun_id": h.urun_id, "senaryo_id": h.senaryo_id, "hesap_tarihi": h.hesap_tarihi.isoformat(), "olusturan": h.olusturan,
            "girdi_snapshot": h.girdi_snapshot, "sonuc_snapshot": h.sonuc_snapshot, "uyarilar": h.uyarilar, "gorunum": gorunum}


@router.post("/urunler/{kod}/kaydet", response_model=TopluKaydetCikis, responses=HATA_404_409_422)
def toplu_kaydet(s: OturumDep, kod: str, g: TopluKaydetGiris, k: str = Depends(kullanici_ver)):
    """Atomik: tek işlem, tek neden. Herhangi bir adım hata verirse (oturum_ver rollback) hiçbir şey yazılmaz."""
    hs.kilit_denetle(hs.senaryo_getir(s, g.senaryo_id))
    r = hs.toplu_kaydet(s, kod, g, k)
    c = r["hesap_ciktisi"]
    return {"hesap": None if c is None else _hesap_yaniti(c, kod, g.senaryo_id, r["tarih"]), "hesap_id": r["hesap_id"],
            "yazilan": r["yazilan"], "uyarilar": r["uyarilar"]}


@router.get("/degisiklikler", response_model=DegisiklikListesi, responses=HATA_404_422)
def degisiklikler(s: OturumDep, tablo: str, kayit_id: int | None = None):
    k = [{"id": x.id, "tablo": x.tablo, "kayit_id": x.kayit_id, "islem": x.islem, "eski": x.eski, "yeni": x.yeni, "kullanici": x.kullanici,
          "zaman": zaman_iso(x.zaman)} for x in hs.degisiklikler(s, tablo, kayit_id)]
    return {"kayitlar": k, "toplam": len(k)}
