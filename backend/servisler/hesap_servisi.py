# backend/servisler/hesap_servisi.py
"""Ürün maliyeti: servislerden girdileri toplar, motoru çağırır, isteğe bağlı snapshot kaydeder."""
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from fiyat_motoru.gider_dagitim import anahtar
from fiyat_motoru.hesapla import urun_maliyeti
from fiyat_motoru.modeller import (GIDER_ELLE_ALANLARI, GIDER_KALEMLERI, GiderElle, GiderOranlari, MaliyetSonucu, Malzeme as MotorMalzeme,
                                   Parametreler, UretimBilgisi, UrunGirdisi)
from fiyat_motoru.para import SIFIR
from ..depo import modeller as m
from . import aile, fiyat_servisi, gider_servisi, parametre_servisi, recete_servisi
from .donusum import decimal_str
from .hatalar import HEDEF_YOK, BulunamadiHatasi, DogrulamaHatasi, KilitliHatasi, ServisHatasi

URUN_OVERRIDE_ALANLARI = ("hat", "taze_tursu_sinifi", "ambalaj_hacmi", "suzme_kg", "pazar")
URETIM_ALANLARI = ("vardiya_uretim_adedi", "dolum_personel", "etiketleme_adedi", "etiket_personel", "mal_kabul_miktar_kg", "mal_kabul_fire", "pazarlama_yonetim_uygula")


@dataclass
class HesapCiktisi:
    girdi: UrunGirdisi
    parametreler: Parametreler
    oranlar: GiderOranlari
    sonuc: MaliyetSonucu
    fire_kaynaklari: list[str]
    kullanilan_parametreler: dict[str, Decimal]
    recete_id: int | None = None
    recete_versiyon: int | None = None
    malzemeler: dict[str, MotorMalzeme] | None = None
    override: dict | None = None
    seviyeler: list[int | None] = field(default_factory=list)   # reçete satırı seviyeleri (satır sırasıyla); yalnız gösterim
    notlar: list[str] = field(default_factory=list)   # metin parametrelerden (satış fiyatı notu); snapshot'a yazılır


def urun_getir(s: Session, kod: str) -> m.Urun:
    u = s.scalar(select(m.Urun).where(m.Urun.kod == kod))
    if u is None:
        raise BulunamadiHatasi(f"ürün yok: {kod}", {"kod": kod})
    return u


def senaryo_getir(s: Session, senaryo_id: int) -> m.Senaryo:
    sen = s.get(m.Senaryo, senaryo_id)
    if sen is None:
        raise BulunamadiHatasi("senaryo yok", {"senaryo_id": senaryo_id})
    return sen


def kilit_denetle(sen: m.Senaryo) -> None:
    """Kilitli senaryoda yazma yok: 409 `senaryo kilitli` (KilitliHatasi)."""
    if sen.kilitli:
        raise KilitliHatasi("senaryo kilitli", {"senaryo_id": sen.id})


def dosya_adi_temizle(ad: str | None) -> str | None:
    """Yüklenen dosya adı: yalnız son bileşen, en çok 200 karakter; boşsa None."""
    ad = (ad or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    return ad[:200] or None


def senaryo_olustur(s: Session, sezon_ad: str, tur: str, ad: str, aciklama: str | None = None, kullanici: str = "sistem") -> m.Senaryo:
    from . import import_servisi   # import_servisi bu modülü kullanır; döngüyü yerel içe aktarma kırar
    ad = (ad or "").strip()
    if not ad:
        raise DogrulamaHatasi("senaryo adı boş olamaz", {"ad": ad})
    sezon = import_servisi.sezon_getir_veya_olustur(s, sezon_ad)
    sen = m.Senaryo(sezon_id=sezon.id, tur=tur, ad=ad, aciklama=(aciklama or None), olusturan=kullanici)
    s.add(sen); s.flush()
    sen.sezon = sezon
    return sen


def urun_getir_id(s: Session, urun_id: int) -> m.Urun:
    u = s.get(m.Urun, urun_id)
    if u is None:
        raise BulunamadiHatasi("ürün yok", {"urun_id": urun_id})
    return u


_urun = urun_getir
_senaryo = senaryo_getir


def urunler(s: Session, aktif: bool = True) -> list[m.Urun]:
    q = select(m.Urun).order_by(m.Urun.kod)
    if aktif:
        q = q.where(m.Urun.aktif == True)
    return list(s.scalars(q))


def senaryolar(s: Session) -> list[m.Senaryo]:
    return list(s.scalars(select(m.Senaryo).order_by(m.Senaryo.id)))


def uretim_hedefi_getir(s: Session, urun_id: int, senaryo_id: int) -> m.UretimHedefi:
    h = s.scalar(select(m.UretimHedefi).where(m.UretimHedefi.urun_id == urun_id, m.UretimHedefi.senaryo_id == senaryo_id))
    if h is None:
        raise BulunamadiHatasi("üretim hedefi yok", {"urun_id": urun_id, "senaryo_id": senaryo_id}, kod=HEDEF_YOK)
    return h


def urun_kaydet(s: Session, kod: str, ad: str, ambalaj_hacmi: Decimal, hat: str, taze_tursu_sinifi: str, suzme_kg: Decimal,
                pazar: str = "Yurtiçi", kullanici: str = "sistem", neden: str | None = None) -> m.Urun:
    yeni = {"ad": ad, "ambalaj_hacmi": ambalaj_hacmi, "hat": hat, "taze_tursu_sinifi": taze_tursu_sinifi, "suzme_kg": suzme_kg, "pazar": pazar}
    u = s.scalar(select(m.Urun).where(m.Urun.kod == kod))
    if u is None:
        u = m.Urun(kod=kod, **yeni, aile=aile.aile_turet(ad), olusturan=kullanici); s.add(u); s.flush()
        return u
    if u.aile is None:   # eski kayıt (aile kolonu sonradan eklendi): türet; kullanıcı değeri asla ezilmez
        u.aile = aile.aile_turet(u.ad)
    eski = {k: getattr(u, k) for k in yeni}
    if eski != yeni:
        for k, v in yeni.items():
            setattr(u, k, v)
        s.add(m.DegisiklikKaydi(tablo="urun", kayit_id=u.id, islem="guncelle", eski=decimal_str(eski),
                                yeni=decimal_str(yeni) if neden is None else {**decimal_str(yeni), "_neden": neden}, kullanici=kullanici))
        s.flush()
    return u


def urun_pasiflestir(s: Session, kod: str, kullanici: str = "sistem") -> m.Urun:
    u = urun_getir(s, kod)
    if u.aktif:
        u.aktif = False
        s.add(m.DegisiklikKaydi(tablo="urun", kayit_id=u.id, islem="pasiflestir", eski={"aktif": True}, yeni={"aktif": False}, kullanici=kullanici))
        s.flush()
    return u


def urun_kod_degistir(s: Session, eski_kod: str, yeni_kod: str, kullanici: str = "sistem") -> m.Urun:
    """Kimlik (id) değişmez; kayıtlı hesaplar urun_id ile çözülmeye devam eder."""
    u = urun_getir(s, eski_kod)
    yeni_kod = (yeni_kod or "").strip()
    if not yeni_kod:
        raise DogrulamaHatasi("yeni kod boş olamaz")
    if yeni_kod != eski_kod:
        if s.scalar(select(m.Urun.id).where(m.Urun.kod == yeni_kod)) is not None:
            raise DogrulamaHatasi(f"bu ürün kodu zaten var: {yeni_kod}", {"yeni_kod": yeni_kod})
        u.kod = yeni_kod
        u.gecici_kod = False
        s.add(m.DegisiklikKaydi(tablo="urun", kayit_id=u.id, islem="kod_degistir", eski={"kod": eski_kod}, yeni={"kod": yeni_kod}, kullanici=kullanici))
        s.flush()
    return u


def gider_elle_normalle(veri) -> dict | None:
    """Elle gider hücreleri: {kalem: {alan: değer}} -> saklanan biçim (Decimal metni; boş alan/kalem atılır; hiç yoksa None).
    Girdi motor nesnesi (GiderElle) ya da sözlük olabilir. Bilinmeyen kalem/alan ve sonlu olmayan değer 422."""
    out = {}
    for kalem, alanlar in (veri or {}).items():
        if kalem not in GIDER_KALEMLERI:
            raise DogrulamaHatasi(f"bilinmeyen gider kalemi: {kalem}", {"kalem": kalem})
        if isinstance(alanlar, GiderElle):
            alanlar = {a: getattr(alanlar, a) for a in GIDER_ELLE_ALANLARI}
        elif not isinstance(alanlar, dict):
            alanlar = alanlar.model_dump()   # API şeması (GiderElleGiris)
        bilinmeyen = sorted(set(alanlar) - set(GIDER_ELLE_ALANLARI))
        if bilinmeyen:
            raise DogrulamaHatasi("bilinmeyen elle gider alanı", {"kalem": kalem, "alanlar": bilinmeyen})
        d = {}
        for a, v in alanlar.items():
            if v is None or v == "":
                continue
            v = Decimal(str(v))
            if not v.is_finite():
                raise DogrulamaHatasi("elle gider değeri sonlu olmalı", {"kalem": kalem, "alan": a})
            d[a] = str(v)
        if d:
            out[kalem] = d
    return out or None


def gider_elle_motor(saklanan: dict | None) -> dict[str, GiderElle]:
    """Saklanan elle gider hücreleri -> motor girdisi."""
    return {k: GiderElle(**{a: Decimal(v) for a, v in d.items()}) for k, d in (saklanan or {}).items()}


_DEGISMEZ = object()


def uretim_hedefi_kaydet(s: Session, urun_id: int, senaryo_id: int, kullanici: str = "sistem", neden: str | None = None,
                         gider_elle=_DEGISMEZ, **alanlar) -> m.UretimHedefi:
    """gider_elle verilmezse mevcut elle gider hücrelerine dokunulmaz; verilirse (None dahil) tamamı bununla değişir."""
    eksik = [a for a in URETIM_ALANLARI if a not in alanlar]
    if eksik:
        raise DogrulamaHatasi("üretim hedefi alanı eksik", {"eksik": eksik})
    h = s.scalar(select(m.UretimHedefi).where(m.UretimHedefi.urun_id == urun_id, m.UretimHedefi.senaryo_id == senaryo_id))
    elle = None if gider_elle is _DEGISMEZ else gider_elle_normalle(gider_elle)
    if h is None:
        h = m.UretimHedefi(urun_id=urun_id, senaryo_id=senaryo_id, olusturan=kullanici, gider_elle=elle,
                           **{a: alanlar[a] for a in URETIM_ALANLARI}); s.add(h); s.flush()
        return h
    eski = {a: getattr(h, a) for a in URETIM_ALANLARI}
    yeni = {a: alanlar[a] for a in URETIM_ALANLARI}
    if gider_elle is not _DEGISMEZ:
        eski["gider_elle"], yeni["gider_elle"] = h.gider_elle, elle
    if eski != yeni:
        for a, v in yeni.items():
            setattr(h, a, v)
        s.add(m.DegisiklikKaydi(tablo="uretim_hedefi", kayit_id=h.id, islem="guncelle", eski=decimal_str(eski),
                                yeni=decimal_str(yeni) if neden is None else {**decimal_str(yeni), "_neden": neden}, kullanici=kullanici))
        s.flush()
    return h


def _parametre_override(p: Parametreler, degerler: dict[str, Decimal]) -> Parametreler:
    kurlar, faiz, stok = dict(p.kurlar), dict(p.faiz_oranlari), dict(p.stok_sureleri_ay)
    teklif = list(p.teklif_kar_oranlari)
    enf, kar, vs = p.enflasyon, p.satis_kar_orani, p.vardiya_saati
    for k, v in degerler.items():
        v = Decimal(str(v))
        if k == "enflasyon": enf = v
        elif k == "satis_kar": kar = v
        elif k == "vardiya_saati": vs = v
        elif k == "maliyet_sapma": pass   # yalnız gösterim: kullanilan_parametreler'e yazılır, motor kullanmaz
        elif k.startswith("kur."): kurlar[k[4:]] = v
        elif k.startswith("faiz."): faiz[k[5:]] = v
        elif k.startswith("stok_ay."): stok[k[8:]] = v
        elif k.startswith("teklif_kar."):
            try:
                n = int(k[11:])
            except ValueError:
                raise DogrulamaHatasi(f"bilinmeyen override parametresi: {k}")
            if n < 1:
                raise DogrulamaHatasi("teklif_kar sırası >= 1 olmalı", {"anahtar": k})
            i = n - 1
            while len(teklif) <= i: teklif.append(SIFIR)
            teklif[i] = v
        else:
            raise DogrulamaHatasi(f"bilinmeyen override parametresi: {k}")
    return Parametreler(enflasyon=enf, kurlar=kurlar, faiz_oranlari=faiz, stok_sureleri_ay=stok, satis_kar_orani=kar,
                        teklif_kar_oranlari=tuple(teklif), vardiya_saati=vs)


_GIDER_SKALER = ("dolum_iscilik_sn", "etiket_iscilik_sn", "endirekt_iscilik_sn", "diger_gug_sn")
_GIDER_SOZLUK = {"mal_kabul_iscilik_kg": "mal_kabul_iscilik_kg", "mal_kabul_gug_kg": "mal_kabul_gug_kg", "elektrik_sn": "elektrik_sn"}


def _gider_orani_override(o: GiderOranlari, degerler: dict[str, Decimal]) -> GiderOranlari:
    """Birim gider oranlarını geçici değiştirir (havuz toplamı yerine doğrudan oran). Sözlüklü anahtarlar `alan.<sınıf|hat>` (casefold)."""
    if not degerler:
        return o
    skaler: dict[str, Decimal] = {}
    sozlukler: dict[str, dict[str, Decimal]] = {}
    for k, v in degerler.items():
        v = Decimal(str(v))
        if k in _GIDER_SKALER:
            skaler[k] = v
            continue
        alan, nokta, alt = k.partition(".")
        if not nokta or alan not in _GIDER_SOZLUK or not alt.strip():
            raise DogrulamaHatasi(f"bilinmeyen gider oranı anahtarı: {k}", {"anahtar": k})
        d = sozlukler.setdefault(alan, dict(getattr(o, _GIDER_SOZLUK[alan])))
        d[anahtar(alt)] = v
    return replace(o, **skaler, **sozlukler)


class HesapBaglami:
    """Aynı senaryo+tarih için senaryo geneli yüklerin tek seferlik önbelleği: malzeme fiyat haritası (833 malzeme), gider oranları,
    parametre satırları, satış notları. `toplu_hesapla` 67 ürün için bir tane açar; eskiden her ürün bunları yeniden çekiyordu
    (soğuk dashboard süresinin ~%85'i). Tek ürünlük `hesapla` baglam vermezse kendi geçici bağlamını kurar (davranış aynı).
    Paylaşılan nesneler yalnız okunur: override'lar kopya üretir (`_gider_orani_override`, `_parametre_override`)."""

    def __init__(self):
        self._d: dict[tuple, object] = {}

    def al(self, anahtar: tuple, uret):
        if anahtar not in self._d:
            self._d[anahtar] = uret()
        return self._d[anahtar]


def hesapla(s: Session, urun_kodu: str, senaryo_id: int, tarih: date | None = None, override: dict | None = None,
            baglam: HesapBaglami | None = None) -> HesapCiktisi:
    tarih = tarih or date.today()
    override = override or {}
    b = baglam if baglam is not None else HesapBaglami()
    u, sen = _urun(s, urun_kodu), _senaryo(s, senaryo_id)
    hedef = s.scalar(select(m.UretimHedefi).where(m.UretimHedefi.urun_id == u.id, m.UretimHedefi.senaryo_id == senaryo_id))
    if hedef is None:
        raise BulunamadiHatasi("üretim hedefi yok", {"urun": urun_kodu, "senaryo_id": senaryo_id}, kod=HEDEF_YOK)

    param_satirlari = b.al(("parametreler", senaryo_id, tarih), lambda: parametre_servisi.parametre_satirlari(s, senaryo_id, tarih))
    kullanilan = parametre_servisi.degerleri_coz(param_satirlari, u.id)
    p = parametre_servisi.gecerli_parametreler(s, senaryo_id, tarih, u.id, satirlar=param_satirlari)
    ov_param = override.get("parametreler") or {}
    if sen.tur == "gerceklesen" and "enflasyon" in ov_param:
        raise DogrulamaHatasi("gerçekleşen senaryoda enflasyon override edilemez")
    if ov_param:
        p = _parametre_override(p, ov_param); kullanilan.update({k: Decimal(str(v)) for k, v in ov_param.items()})
    if sen.tur == "gerceklesen":   # override'dan SONRA: gerçekleşen senaryoda enflasyon her zaman 0
        p = replace(p, enflasyon=SIFIR); kullanilan["enflasyon"] = SIFIR

    malzemeler = b.al(("malzemeler", senaryo_id, tarih), lambda: fiyat_servisi.gecerli_fiyatlar(s, senaryo_id, tarih))
    tipler = b.al(("tipler", senaryo_id, tarih), lambda: {k: mz.tip for k, mz in malzemeler.items()})
    oranlar = b.al(("oranlar", senaryo_id), lambda: gider_servisi.oranlar(s, senaryo_id))
    recete = recete_servisi.aktif_recete_veya_none(s, u.id, senaryo_id)
    if recete is None:
        raise DogrulamaHatasi("reçete yok: bu üründe bu senaryoda aktif reçete bulunmuyor", {"urun": urun_kodu, "senaryo_id": senaryo_id})
    satir_ov = {int(k): v for k, v in (override.get("satirlar") or {}).items()}
    for sira, o in satir_ov.items():
        if not 1 <= sira <= len(recete.satirlar):
            raise DogrulamaHatasi("satır override sira aralık dışı", {"sira": sira})
        if o.get("brut_miktar_elle") is not None and o.get("elle_brut_kaldir"):
            raise DogrulamaHatasi("brüt miktar hem verilip hem kaldırılamaz", {"sira": sira})
        if o.get("birim_fiyat_elle") is not None and o.get("elle_fiyat_kaldir"):
            raise DogrulamaHatasi("birim fiyat hem verilip hem kaldırılamaz", {"sira": sira})
    brut_kaldir = frozenset(sira for sira, o in satir_ov.items() if o.get("elle_brut_kaldir"))
    satirlar, kaynaklar = recete_servisi.fire_uygulanmis(s, recete, senaryo_id, tarih, tipler, brut_kaldir)
    for sira, o in satir_ov.items():   # fire override'dan ÖNCE: elle brüt kaldırılan satıra fire verilebilir, elle brüt verilen satıra verilemez
        i = sira - 1
        degisim = {}
        if o.get("miktar") is not None:
            degisim["miktar"] = Decimal(str(o["miktar"]))   # brüt: elle brüt yoksa motor miktar/(1-fire) ile yeniden hesaplar
        if o.get("brut_miktar_elle") is not None:
            degisim["brut_miktar_elle"] = Decimal(str(o["brut_miktar_elle"])); kaynaklar[i] = "elle"
        if o.get("birim_fiyat_elle") is not None:
            degisim["birim_fiyat_elle"] = Decimal(str(o["birim_fiyat_elle"]))
        if o.get("elle_fiyat_kaldir"):
            degisim["birim_fiyat_elle"] = None
        if degisim:
            satirlar[i] = replace(satirlar[i], **degisim)
    for sira, oran in (override.get("fire") or {}).items():
        sira = int(sira)
        if not 1 <= sira <= len(satirlar):
            raise DogrulamaHatasi("fire override sira aralık dışı", {"sira": sira})
        i = sira - 1
        if satirlar[i].brut_miktar_elle is not None:
            raise DogrulamaHatasi("satır elle brüt miktarlı; önce elle değeri kaldırın", {"sira": sira})
        satirlar[i] = replace(satirlar[i], fire_orani=Decimal(str(oran))); kaynaklar[i] = "satir"
    oranlar = _gider_orani_override(oranlar, override.get("gider_oranlari") or {})

    ov_uretim = {k: v for k, v in (override.get("uretim") or {}).items() if v is not None}
    bilinmeyen = sorted(set(ov_uretim) - set(URETIM_ALANLARI))
    if bilinmeyen:
        raise DogrulamaHatasi("bilinmeyen üretim override alanı", {"alanlar": bilinmeyen})
    ub = {a: getattr(hedef, a) for a in URETIM_ALANLARI}
    ub.update(ov_uretim)
    ov_urun = {k: v for k, v in (override.get("urun") or {}).items() if v is not None}
    bilinmeyen_urun = sorted(set(ov_urun) - set(URUN_OVERRIDE_ALANLARI))
    if bilinmeyen_urun:
        raise DogrulamaHatasi("bilinmeyen ürün override alanı", {"alanlar": bilinmeyen_urun})
    ua = {a: getattr(u, a) for a in URUN_OVERRIDE_ALANLARI}
    ua.update(ov_urun)
    uretim = UretimBilgisi(pazar=ua["pazar"], hat=ua["hat"], taze_tursu_sinifi=ua["taze_tursu_sinifi"], ambalaj_hacmi=Decimal(str(ua["ambalaj_hacmi"])),
                           suzme_kg=Decimal(str(ua["suzme_kg"])),
                           vardiya_uretim_adedi=Decimal(ub["vardiya_uretim_adedi"]), dolum_personel=Decimal(ub["dolum_personel"]),
                           etiketleme_adedi=Decimal(ub["etiketleme_adedi"]), etiket_personel=Decimal(ub["etiket_personel"]),
                           mal_kabul_miktar_kg=Decimal(ub["mal_kabul_miktar_kg"]), mal_kabul_fire=Decimal(ub["mal_kabul_fire"]),
                           pazarlama_yonetim_uygula=bool(ub["pazarlama_yonetim_uygula"]))
    # Elle gider hücreleri: override'da "gider_elle" varsa kayıtlının TAMAMI yerine geçer (ekrandaki taslak tam haritayı yollar).
    gider_elle = gider_elle_motor(gider_elle_normalle(override["gider_elle"]) if "gider_elle" in override else hedef.gider_elle)
    girdi = UrunGirdisi(kod=u.kod, ad=u.ad, recete=tuple(satirlar), uretim=uretim, gider_elle=gider_elle)
    sonuc = urun_maliyeti(girdi, malzemeler, oranlar, p)
    return HesapCiktisi(girdi=girdi, parametreler=p, oranlar=oranlar, sonuc=sonuc, fire_kaynaklari=kaynaklar, kullanilan_parametreler=kullanilan,
                        recete_id=recete.id, recete_versiyon=recete.versiyon,
                        malzemeler={r.malzeme_kodu: malzemeler[r.malzeme_kodu] for r in recete.satirlar if r.malzeme_kodu in malzemeler},
                        override=override or None, seviyeler=[r.seviye for r in recete.satirlar],
                        notlar=list(b.al(("notlar", senaryo_id, tarih), lambda: [k.deger for k in parametre_servisi.metin_gecerli(s, senaryo_id, tarih)])))


def kaydet(s: Session, cikti: HesapCiktisi, urun_kodu: str, senaryo_id: int, tarih: date, kullanici: str = "sistem", neden: str | None = None) -> m.MaliyetHesabi:
    u = _urun(s, urun_kodu)
    h = m.MaliyetHesabi(urun_id=u.id, senaryo_id=senaryo_id, hesap_tarihi=tarih,
                        girdi_snapshot={"girdi": decimal_str(cikti.girdi), "parametreler": decimal_str(cikti.parametreler),
                                        "oranlar": decimal_str(cikti.oranlar), "fire_kaynaklari": cikti.fire_kaynaklari,
                                        "kullanilan_parametreler": decimal_str(cikti.kullanilan_parametreler),
                                        "malzemeler": decimal_str(cikti.malzemeler or {}),
                                        "recete": {"id": cikti.recete_id, "versiyon": cikti.recete_versiyon, "seviyeler": list(cikti.seviyeler)},
                                        "notlar": list(cikti.notlar), "neden": neden,
                                        "override": decimal_str(cikti.override) if cikti.override else None},
                        sonuc_snapshot=decimal_str(cikti.sonuc), uyarilar=list(cikti.sonuc.uyarilar), olusturan=kullanici)
    s.add(h); s.flush()
    return h


def getir(s: Session, hesap_id: int) -> m.MaliyetHesabi:
    h = s.get(m.MaliyetHesabi, hesap_id)
    if h is None:
        raise BulunamadiHatasi("hesap yok", {"hesap_id": hesap_id})
    return h


def toplu_hesapla(s: Session, senaryo_id: int, tarih: date | None = None, tum: bool = False) -> list[tuple[str, HesapCiktisi | Exception]]:
    """Varsayılan: yalnız senaryo üyesi (o senaryoda aktif reçetesi olan) aktif ürünler. tum=True: tüm aktif ürünler (reçetesizler hata satırı)."""
    from . import senaryo_servisi   # senaryo_servisi bu modülü kullanır; döngüyü yerel içe aktarma kırar
    uyeler = None if tum else senaryo_servisi.uye_urun_kodlari(s, senaryo_id)
    baglam = HesapBaglami()   # senaryo geneli yükler tüm ürünler için bir kez
    out = []
    for u in s.scalars(select(m.Urun).where(m.Urun.aktif == True).order_by(m.Urun.kod)):
        if uyeler is not None and u.kod not in uyeler:
            continue
        try:
            out.append((u.kod, hesapla(s, u.kod, senaryo_id, tarih, baglam=baglam)))
        except (ServisHatasi, KeyError, ValueError) as e:  # bir ürünün hatası toplu hesabı durdurmaz; dashboard satırında gösterilir (DB hataları yayılır)
            out.append((u.kod, e))
    return out


def hesaplar_listele(s: Session, urun_id: int, senaryo_id: int) -> list[m.MaliyetHesabi]:
    return list(s.scalars(select(m.MaliyetHesabi).where(m.MaliyetHesabi.urun_id == urun_id, m.MaliyetHesabi.senaryo_id == senaryo_id)
                          .order_by(m.MaliyetHesabi.id.desc())))


def degisiklikler(s: Session, tablo: str, kayit_id: int | None = None) -> list[m.DegisiklikKaydi]:
    q = select(m.DegisiklikKaydi).where(m.DegisiklikKaydi.tablo == tablo)
    if kayit_id is not None:
        q = q.where(m.DegisiklikKaydi.kayit_id == kayit_id)
    return list(s.scalars(q.order_by(m.DegisiklikKaydi.id.desc())))


def uyarilar(s: Session, senaryo_id: int, tarih: date | None = None, tum: bool = False) -> list[dict]:
    """Senaryo üyesi ürünlerin (tum=True: tüm aktif ürünlerin) hesap uyarıları (ürün başına birden çok olabilir)."""
    out = []
    for kod, c in toplu_hesapla(s, senaryo_id, tarih, tum):
        if not isinstance(c, Exception):
            out += [{"urun_kodu": kod, "uyari": x} for x in c.sonuc.uyarilar]
    return out


def toplu_kaydet(s: Session, kod: str, g, kullanici: str = "sistem") -> dict:
    """Atomik toplu kayıt (g: TopluKaydetGiris). Servis yalnız flush eder; commit/rollback oturum sahibinin (router) işidir:
    herhangi bir adım hata verirse çağıran rollback yapmalıdır. Sıra: ürün kartı, hedef, reçete sürümü, parametreler, havuz tutarları, hesap.
    Dönüş: {"yazilan", "uyarilar", "hesap_id", "hesap_ciktisi", "tarih"}."""
    u, sen = urun_getir(s, kod), senaryo_getir(s, g.senaryo_id)
    t = g.tarih or date.today()
    yazilan = {"urun": 0, "hedef": 0, "recete": 0, "parametre": 0, "havuz": 0}
    uyarilar: list[str] = []

    # girdi doğrulamaları: hiçbir şey yazılmadan önce (rollback'e güvenmeden de temiz hata)
    parametreler = list(g.parametreler or [])
    gorulen_p: set[tuple[str, str]] = set()
    for p in parametreler:
        if (p.anahtar, p.kapsam) in gorulen_p:
            raise DogrulamaHatasi("parametre listesinde tekrar", {"anahtar": p.anahtar, "kapsam": p.kapsam})
        gorulen_p.add((p.anahtar, p.kapsam))
        if sen.tur == "gerceklesen" and p.anahtar == "enflasyon":
            raise DogrulamaHatasi("gerçekleşen senaryoda enflasyon yazılamaz", {"anahtar": p.anahtar})
        if not p.deger.is_finite():
            raise DogrulamaHatasi("parametre değeri sonlu olmalı", {"anahtar": p.anahtar})
    havuzlar_ = list(g.gider_havuzlari or [])
    if len({h.kod for h in havuzlar_}) != len(havuzlar_):
        raise DogrulamaHatasi("gider havuzu listesinde tekrar")

    if g.urun is not None:
        u = urun_kaydet(s, kod, g.urun.ad, g.urun.ambalaj_hacmi, g.urun.hat, g.urun.taze_tursu_sinifi, g.urun.suzme_kg, g.urun.pazar, kullanici, g.neden)
        yazilan["urun"] = 1
    elle_var = "gider_elle" in g.model_fields_set
    if g.uretim_hedefi is not None or elle_var:
        alanlar = (g.uretim_hedefi.model_dump() if g.uretim_hedefi is not None
                   else {a: getattr(uretim_hedefi_getir(s, u.id, sen.id), a) for a in URETIM_ALANLARI})
        uretim_hedefi_kaydet(s, u.id, sen.id, kullanici, g.neden, **({"gider_elle": g.gider_elle} if elle_var else {}), **alanlar)
        yazilan["hedef"] = 1
    if g.recete is not None:
        r = recete_servisi.yeni_versiyon(s, u.id, sen.id, [x.model_dump() for x in g.recete], "ekran", kullanici)
        yazilan["recete"] = len(r.satirlar)
    for p in parametreler:
        if p.kapsam == "genel" and s.scalar(select(m.ParametreDegeri.id).join(m.Parametre).where(
                m.Parametre.anahtar == p.anahtar, m.ParametreDegeri.senaryo_id == sen.id,
                m.ParametreDegeri.kapsam_tipi == "urun", m.ParametreDegeri.kapsam_id == u.id).limit(1)) is not None:
            # Karar 11: ürüne özel değer genel yazımı gölgeler; kaydedilen hesap önizlemeyle aynı olsun diye ürün değeri de güncellenir
            parametre_servisi.deger_ekle(s, sen.id, p.anahtar, p.deger, t, g.neden, kapsam_tipi="urun", kapsam_id=u.id, olusturan=kullanici)
            yazilan["parametre"] += 1
            uyarilar.append(f"{p.anahtar}: bu ürüne özel değer vardı; ürün değeri de güncellendi")
        parametre_servisi.deger_ekle(s, sen.id, p.anahtar, p.deger, t, g.neden, kapsam_tipi=p.kapsam,
                                     kapsam_id=u.id if p.kapsam == "urun" else None, olusturan=kullanici)
        yazilan["parametre"] += 1
    if havuzlar_:
        mevcut = gider_servisi.havuzlar(s, sen.id)
        for hg in havuzlar_:
            if hg.kod not in gider_servisi.HAVUZ_KODLARI:
                raise DogrulamaHatasi(f"bilinmeyen havuz: {hg.kod}", {"kod": hg.kod})
            h = mevcut.get(hg.kod)
            if h is None:
                raise BulunamadiHatasi(f"gider havuzu yok: {hg.kod}", {"kod": hg.kod, "senaryo_id": sen.id})
            if h.toplam_tutar == hg.toplam_tutar:
                continue   # değişmeyen havuz: gereksiz değişiklik kaydı açılmaz
            if h.taban_tutar is not None:   # toplam doğrudan yazılınca taban × çarpan açıklaması artık geçerli değil; sessiz silinmesin
                uyarilar.append(f"gider havuzu {h.kod}: toplam doğrudan girildi, taban × çarpan bilgisi temizlendi")
            gider_servisi.havuz_kaydet(s, sen.id, h.kod, h.ad, hg.toplam_tutar, h.baz_tipi, h.baz_miktar,
                                       [(a.alt_kalem, a.pay_orani, a.baz_miktar) for a in h.anahtarlar], kullanici, g.neden)
            yazilan["havuz"] += 1
        uyarilar += [f"gider havuzu pay toplamı 1 değil: {x['havuz']} ({x['toplam']})" for x in gider_servisi.pay_toplami_kontrol(s, sen.id)]

    cikti, hesap_id = None, None
    if g.hesabi_kaydet:
        cikti = hesapla(s, kod, sen.id, t, g.override_sozlugu())   # kalıcı değerler DB'den gelir; override yalnız istemcinin verdiği kalıcı-olmayan değerler
        hesap_id = kaydet(s, cikti, kod, sen.id, t, kullanici, g.neden).id
        uyarilar += list(cikti.sonuc.uyarilar)
    return {"yazilan": yazilan, "uyarilar": uyarilar, "hesap_id": hesap_id, "hesap_ciktisi": cikti, "tarih": t}
