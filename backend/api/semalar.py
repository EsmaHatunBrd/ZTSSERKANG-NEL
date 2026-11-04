"""Pydantic istek ve yanıt şemaları. İsteklerde Decimal alanlar JSON'da string olarak gelir; yanıt modellerinde tutarlar `decimal_str` çıktısı olduğundan `str` tipindedir."""
from datetime import date
from decimal import Decimal
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SenaryoGiris(BaseModel):
    sezon_ad: str
    tur: Literal["fiyat_calismasi", "gerceklesen"]
    ad: str
    aciklama: str | None = None


class SenaryoCikis(BaseModel):
    id: int
    sezon_ad: str
    tur: Literal["fiyat_calismasi", "gerceklesen"]
    ad: str
    kilitli: bool = False
    aciklama: str | None = None
    urun_sayisi: int = 0   # senaryo üyesi (aktif reçetesi olan, aktif) ürün sayısı


class SenaryoKopyaSecimleri(BaseModel):
    """Altı seçim de açıkça gönderilir (varsayılan yok): neyin kopyalanacağı istemcide belirlenir."""
    receteler: bool
    fiyatlar: bool
    parametreler: bool
    gider: bool
    uretim: bool
    fire_kurallari: bool


class SenaryoKopyaGiris(BaseModel):
    sezon_ad: str
    ad: str = Field(min_length=1, max_length=100)
    tur: Literal["fiyat_calismasi", "gerceklesen"]
    aciklama: str | None = None
    neden: str = Field(min_length=1, max_length=300)
    kopyala: SenaryoKopyaSecimleri


class SenaryoGuncelleGiris(BaseModel):
    sezon_ad: str | None = None
    ad: str | None = Field(default=None, min_length=1, max_length=100)
    aciklama: str | None = None
    neden: str = Field(min_length=1, max_length=300)


class SenaryoKopyaSayilari(BaseModel):
    recete: int = 0
    fiyat: int = 0
    parametre: int = 0
    metin: int = 0
    havuz: int = 0
    ambalaj: int = 0
    hedef: int = 0
    kapasite: int = 0
    fire: int = 0


class SenaryoKopyaCikis(SenaryoCikis):
    kopyalanan: SenaryoKopyaSayilari


class ParametreDegerGiris(BaseModel):
    deger: Decimal
    gecerlilik_basi: date
    neden: str = Field(min_length=1)
    kapsam_tipi: Literal["genel", "urun"] = "genel"
    kapsam_id: int | None = None


class MalzemeGiris(BaseModel):
    kod: str
    ad: str
    tip: str | None = None
    birim: str | None = None
    para_birimi: str | None = None
    zs: str | None = None


class FiyatGiris(BaseModel):
    fiyat: Decimal = Field(ge=0)
    gecerlilik_basi: date
    neden: str = Field(min_length=1)
    para_birimi: str | None = None


class AnahtarGiris(BaseModel):
    """Alt kalem: `pay_orani` (0-1) **ya da** `tutar` (TL; sunucu pay = tutar / havuz toplamı) — en az biri zorunlu; ikisi de gelirse `pay_orani` kazanır."""
    alt_kalem: str
    pay_orani: Decimal | None = Field(default=None, ge=0, le=1)
    tutar: Decimal | None = Field(default=None, ge=0)
    baz_miktar: Decimal

    @model_validator(mode="after")
    def _pay_veya_tutar(self):
        if self.pay_orani is None and self.tutar is None:
            raise ValueError("pay_orani ya da tutar verilmeli")
        return self


class CarpanGiris(BaseModel):
    ad: str = ""
    deger: Decimal = Field(gt=0)


class HavuzGiris(BaseModel):
    """`taban_tutar` verilirse toplam = taban × Π çarpan (sunucu hesaplar); verilmezse `toplam_tutar` zorunludur."""
    ad: str
    neden: str = Field(min_length=1)
    toplam_tutar: Decimal | None = Field(default=None, ge=0)
    taban_tutar: Decimal | None = Field(default=None, ge=0)
    carpanlar: list[CarpanGiris] | None = None
    baz_tipi: Literal["saniye", "kg", "adet"]
    baz_miktar: Decimal | None = None
    anahtarlar: list[AnahtarGiris] = []

    @model_validator(mode="after")
    def _toplam_veya_taban(self):
        if self.toplam_tutar is None and self.taban_tutar is None:
            raise ValueError("toplam_tutar ya da taban_tutar verilmeli")
        if self.toplam_tutar is not None and self.taban_tutar is not None:
            raise ValueError("taban_tutar varken toplam_tutar gönderilmez (toplam sunucuda hesaplanır)")
        if self.carpanlar and self.taban_tutar is None:
            raise ValueError("carpanlar yalnız taban_tutar ile birlikte verilir")
        return self


class AmbalajGiris(BaseModel):
    ad: str
    hacim: Decimal
    uretim_adedi: Decimal = Field(ge=0)
    katsayi: Decimal = Field(gt=0)


class AmbalajKaydiGiris(BaseModel):
    """PUT /ambalaj-siniflari gövdesi: `{"siniflar": [...], "neden": "..."}`; çıplak liste de kabul edilir (neden: "(belirtilmedi)")."""
    siniflar: list[AmbalajGiris]
    neden: str = Field(min_length=1)


class UrunGiris(BaseModel):
    ad: str
    ambalaj_hacmi: Decimal
    hat: str
    taze_tursu_sinifi: str
    suzme_kg: Decimal
    pazar: Literal["Yurtiçi", "Yurtdışı"] = "Yurtiçi"


class UretimHedefiGiris(BaseModel):
    vardiya_uretim_adedi: Decimal
    dolum_personel: Decimal
    etiketleme_adedi: Decimal
    etiket_personel: Decimal
    mal_kabul_miktar_kg: Decimal
    mal_kabul_fire: Decimal = Decimal(0)
    pazarlama_yonetim_uygula: bool = True


class UretimHedefiNedenliGiris(UretimHedefiGiris):
    """PUT /urunler/{kod}/uretim-hedefi: Veri Girişi'nden doğrudan yazım; neden verilirse değişiklik kaydına girer."""
    neden: str | None = None


class ReceteSatirGiris(BaseModel):
    malzeme_kodu: str
    ad: str = ""
    miktar: Decimal = Field(ge=0)
    birim: str | None = None
    fire_override: Decimal | None = Field(default=None, ge=0, lt=1)
    dugum_tipi: Literal["yaprak", "ara_mamul"] = "yaprak"
    brut_miktar_elle: Decimal | None = Field(default=None, ge=0)
    birim_fiyat_elle: Decimal | None = Field(default=None, ge=0)
    seviye: int | None = Field(default=None, ge=0)   # Excel A sütunu (0-3); yalnız gösterim
    zs_elle: Literal["Z", "S"] | None = None          # elle Z/S (Excel N); boşsa malzeme kartınınki
    para_birimi_elle: str | None = Field(default=None, max_length=8)   # elle para birimi (Excel O); boşsa kartınki


class GiderElleGiris(BaseModel):
    """Bir gider satırının elle yazılmış hücreleri (Excel I/K/M/P); boş (null) olan formülle hesaplanır."""
    model_config = ConfigDict(extra="forbid")
    miktar: Decimal | None = Field(default=None, ge=0)
    brut_miktar: Decimal | None = Field(default=None, ge=0)
    birim_fiyat: Decimal | None = Field(default=None, ge=0)
    tutar: Decimal | None = Field(default=None, ge=0)


class UretimOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")
    vardiya_uretim_adedi: Decimal | None = Field(default=None, gt=0)
    dolum_personel: Decimal | None = Field(default=None, ge=0)
    etiketleme_adedi: Decimal | None = Field(default=None, ge=0)
    etiket_personel: Decimal | None = Field(default=None, ge=0)
    mal_kabul_miktar_kg: Decimal | None = Field(default=None, ge=0)
    mal_kabul_fire: Decimal | None = Field(default=None, ge=0, lt=1)
    pazarlama_yonetim_uygula: bool | None = None


class SatirOverride(BaseModel):
    """Tek reçete satırı için geçici (kaydedilmeyen) değişiklik. `*_kaldir` true ise satırdaki elle değer geçici olarak yok sayılır."""
    model_config = ConfigDict(extra="forbid")
    miktar: Decimal | None = Field(default=None, ge=0)
    brut_miktar_elle: Decimal | None = Field(default=None, ge=0)
    birim_fiyat_elle: Decimal | None = Field(default=None, ge=0)
    elle_brut_kaldir: bool = False
    elle_fiyat_kaldir: bool = False


class UrunOverride(BaseModel):
    """Ürün kartı alanlarının geçici değişikliği (hepsi isteğe bağlı)."""
    model_config = ConfigDict(extra="forbid")
    hat: str | None = None
    taze_tursu_sinifi: str | None = None
    ambalaj_hacmi: Decimal | None = Field(default=None, gt=0)
    suzme_kg: Decimal | None = Field(default=None, ge=0)
    pazar: Literal["Yurtiçi", "Yurtdışı"] | None = None


class OverrideGiris(BaseModel):
    model_config = ConfigDict(extra="forbid")
    parametreler: dict[str, Decimal] = {}          # anahtar deseni servis tarafında doğrulanır
    fire: dict[int, Decimal] = {}                  # sira >= 1, 0 <= oran < 1; üst sınır (satır sayısı) serviste
    uretim: UretimOverride | None = None
    satirlar: dict[int, SatirOverride] = {}        # sira >= 1; üst sınır serviste
    urun: UrunOverride | None = None
    gider_oranlari: dict[str, Decimal] = {}        # dolum_iscilik_sn | ... | mal_kabul_iscilik_kg.<sınıf> | elektrik_sn.<hat>; desen serviste
    # Elle gider hücreleri (kalem -> hücreler). Verilirse kayıtlı elle hücrelerin TAMAMI yerine geçer ({} = hepsi formülle).
    gider_elle: dict[str, GiderElleGiris] | None = None

    @field_validator("satirlar")
    @classmethod
    def _satirlar(cls, v: dict[int, SatirOverride]) -> dict[int, SatirOverride]:
        for sira in v:
            if sira < 1:
                raise ValueError(f"satirlar sira >= 1 olmalı: {sira}")
        return v

    @field_validator("gider_oranlari")
    @classmethod
    def _gider_sonlu(cls, v: dict[str, Decimal]) -> dict[str, Decimal]:
        for k, x in v.items():
            if not (x.is_finite() and x >= 0):
                raise ValueError(f"gider oranı sonlu ve >= 0 olmalı: {k}")
        return v

    @field_validator("parametreler")
    @classmethod
    def _sonlu(cls, v: dict[str, Decimal]) -> dict[str, Decimal]:
        for k, x in v.items():
            if not x.is_finite():
                raise ValueError(f"parametre değeri sonlu olmalı: {k}")
        return v

    @field_validator("fire")
    @classmethod
    def _fire(cls, v: dict[int, Decimal]) -> dict[int, Decimal]:
        for sira, oran in v.items():
            if sira < 1:
                raise ValueError(f"fire sira >= 1 olmalı: {sira}")
            if not (oran.is_finite() and 0 <= oran < 1):
                raise ValueError(f"fire oranı 0 <= oran < 1 olmalı: {sira}")
        return v


def override_sozlugu_yap(override: "OverrideGiris | None") -> dict | None:
    """Servis katmanına düz sözlük: verilmeyen (None) üretim alanları düşer (HesaplaGiris ve TopluKaydetGiris ortak)."""
    if override is None:
        return None
    d = override.model_dump(exclude_none=True)
    for k in ("satirlar", "gider_oranlari"):   # yeni alanlar boşsa snapshot'a girmez (eski biçim korunur)
        if not d.get(k):
            d.pop(k, None)
    for o in (d.get("satirlar") or {}).values():   # kapalı bayraklar gürültü: yalnız true olanlar taşınır
        for bayrak in ("elle_brut_kaldir", "elle_fiyat_kaldir"):
            if not o.get(bayrak):
                o.pop(bayrak, None)
    return d


class HesaplaGiris(BaseModel):
    senaryo_id: int
    tarih: date | None = None
    override: OverrideGiris | None = None

    def override_sozlugu(self) -> dict | None:
        return override_sozlugu_yap(self.override)


class ParametreYazGiris(BaseModel):
    anahtar: str = Field(min_length=1)
    deger: Decimal
    kapsam: Literal["urun", "genel"] = "genel"


class HavuzTutarGiris(BaseModel):
    """Yalnız toplam tutar değişir; ad/baz/dağıtım anahtarları mevcut havuzdan aynen korunur."""
    kod: str = Field(min_length=1)
    toplam_tutar: Decimal = Field(ge=0)


class TopluKaydetGiris(BaseModel):
    """POST /urunler/{kod}/kaydet: tek işlemde (hepsi ya da hiçbiri) ürün kartı, üretim hedefi, reçete sürümü, parametreler ve gider havuzu."""
    senaryo_id: int
    tarih: date | None = None
    neden: str = Field(min_length=1)
    urun: UrunGiris | None = None
    uretim_hedefi: UretimHedefiGiris | None = None
    recete: list[ReceteSatirGiris] | None = None
    parametreler: list[ParametreYazGiris] | None = None
    gider_havuzlari: list[HavuzTutarGiris] | None = None
    # Elle gider hücreleri (kalem -> hücreler). Alan gönderilirse kayıtlıların TAMAMI bununla değişir (null/{} = hepsi formülle).
    gider_elle: dict[str, GiderElleGiris] | None = None
    hesabi_kaydet: bool = True
    override: OverrideGiris | None = None   # kalıcı olmayan what-if değerleri: yalnız kaydedilen hesabın girdi_snapshot.override'ına girer

    @model_validator(mode="after")
    def _override_hesapsiz_olmaz(self) -> "TopluKaydetGiris":
        if self.override is not None and not self.hesabi_kaydet:
            raise ValueError("override yalnız hesabi_kaydet=true iken verilebilir (hesap kaydedilmiyorsa override'ın yazılacağı yer yok)")
        return self

    def override_sozlugu(self) -> dict | None:
        return override_sozlugu_yap(self.override)


class TeklifGiris(BaseModel):
    kar_orani: Decimal = Field(gt=-1)
    musteri: str | None = None
    notu: str | None = None


class DurumGiris(BaseModel):
    durum: str


class FireKuraliGiris(BaseModel):
    kapsam_tipi: Literal["tip", "grup", "malzeme"]
    kapsam_deger: str
    oran: Decimal = Field(ge=0, lt=1)
    gecerlilik_basi: date
    neden: str = Field(min_length=1)


class GrupGiris(BaseModel):
    ad: str
    malzeme_kodlari: list[str]


class KurallaraBirakGiris(BaseModel):
    siralar: list[int] | None = None
    elle_degerleri_kaldir: bool = False

    @field_validator("siralar")
    @classmethod
    def _sira(cls, v):
        if v is not None and any(x < 1 for x in v):
            raise ValueError("sira >= 1 olmalı")
        return v


class KodDegistirGiris(BaseModel):
    yeni_kod: str = Field(min_length=1, max_length=32)


# --------------------------------------------------------------------------------------------------------------------
# Yanıt modelleri. Yalnız mevcut sözlük biçimlerini bildirir; tutarlar `str` (Decimal metin), tarihler ISO `str`.
# --------------------------------------------------------------------------------------------------------------------

class HataGovdesi(BaseModel):
    hata: str
    mesaj: str
    alanlar: dict[str, Any] = {}
    kod: str | None = None   # kararlı ayrıntı kodu: "hedef_yok", "parametre_eksik"; yoksa null


HATA_404 = {404: {"model": HataGovdesi}}
HATA_404_422 = {404: {"model": HataGovdesi}, 422: {"model": HataGovdesi}}
HATA_404_409_422 = {404: {"model": HataGovdesi}, 409: {"model": HataGovdesi}, 422: {"model": HataGovdesi}}


class DashboardSatiri(BaseModel):
    id: int
    kod: str
    ad: str
    ambalaj_hacmi: str
    ambalaj_etiket: str | None = None
    hat: str
    gecici_kod: bool
    recete_maliyeti: str | None
    gug: str | None
    faaliyet: str | None
    finans: str | None
    gider_yuzdesi: str | None
    maliyet_tl: str | None
    maliyet_usd: str | None
    maliyet_eur: str | None
    satis_tl: str | None
    uretim_adedi: str | None
    maliyet_tl_firesiz: str | None
    maliyet_usd_firesiz: str | None
    uyari_sayisi: int | None
    hata: str | None
    gecen_yil_tl: str | None = None            # geçen yıl TL adet ağırlıklı ortalama satış fiyatı (satış geçmişi yoksa null)
    enflasyon_durumu: str | None = None        # "altinda" | "ustunde" | null (TL yeni fiyat / (geçen yıl x (1+enflasyon)) < 1 ise altinda)
    enflasyon_fark_yuzde: str | None = None    # (oran - 1) x 100
    hedef_adet_maliyet_tl: str | None = None   # Üretim Adetleri hedefiyle yeniden hesaplanan TL maliyet (kapasite kaydı yoksa null)


class UrunListesi(BaseModel):
    kayitlar: list[DashboardSatiri]
    toplam: int
    enflasyon_altinda_toplam: int = 0   # tüm (önbellekli) satırlarda enflasyon_durumu == "altinda" sayısı; sayfadan bağımsız


class UyariSatiri(BaseModel):
    urun_kodu: str
    uyari: str


class UyariListesi(BaseModel):
    kayitlar: list[UyariSatiri]
    toplam: int


class UretimHedefiCikis(BaseModel):
    id: int
    vardiya_uretim_adedi: str
    dolum_personel: str
    etiketleme_adedi: str
    etiket_personel: str
    mal_kabul_miktar_kg: str
    mal_kabul_fire: str
    pazarlama_yonetim_uygula: bool
    gider_elle: dict[str, dict[str, str]] | None = None   # elle gider hücreleri: kalem -> {miktar|brut_miktar|birim_fiyat|tutar: değer}


class UrunCikis(BaseModel):
    """`uretim_hedefi` yalnız GET /urunler/{kod}?senaryo=... yanıtında bulunur (uçlar `response_model_exclude_unset` kullanır)."""
    id: int
    kod: str
    ad: str
    ambalaj_hacmi: str
    hat: str
    taze_tursu_sinifi: str
    suzme_kg: str
    pazar: str
    aktif: bool
    gecici_kod: bool
    uretim_hedefi: UretimHedefiCikis | None = None
    senaryoda: bool | None = None   # yalnız ?senaryo= ile: ürünün o senaryoda aktif reçetesi var mı (senaryo üyeliği)
    aile: str | None = None
    aile_ad: str | None = None   # görünen ad (ı/i korunur); gruplama/URL için `aile` anahtarı kullanılır
    ambalaj_etiket: str | None = None   # addan türetilen boyut metni ("5 lt"); ambalaj_hacmi'nden bağımsız, yalnız gösterim


class PasifCikis(BaseModel):
    kod: str
    aktif: bool


class ReceteSatiriCikis(BaseModel):
    sira: int
    malzeme_kodu: str
    ad: str
    miktar: str
    birim: str | None
    dugum_tipi: Literal["yaprak", "ara_mamul"]
    fire_override: str | None
    brut_miktar_elle: str | None
    birim_fiyat_elle: str | None
    seviye: int | None = None
    zs_elle: str | None = None
    para_birimi_elle: str | None = None


class ReceteSatiriFireli(ReceteSatiriCikis):
    fire_orani: str
    fire_kaynagi: str


class ReceteCikis(BaseModel):
    """Reçetesiz üründe boş yapı döner: id null, versiyon 0, kaynak null, satirlar [] (404 değil)."""
    id: int | None
    versiyon: int
    kaynak: str | None
    satirlar: list[ReceteSatiriFireli]


class ReceteDetayCikis(BaseModel):
    id: int
    urun_id: int
    senaryo_id: int
    versiyon: int
    kaynak: str
    aktif: bool
    satirlar: list[ReceteSatiriCikis]


class ReceteEkleCikis(BaseModel):
    id: int
    versiyon: int
    satir_sayisi: int


class KurallaraBirakCikis(BaseModel):
    id: int
    versiyon: int
    satir_sayisi: int


class ReceteVersiyonu(BaseModel):
    id: int
    versiyon: int
    kaynak: str
    aktif: bool
    olusturma_zamani: str | None


class ReceteVersiyonListesi(BaseModel):
    kayitlar: list[ReceteVersiyonu]
    toplam: int


class HesapSatiri(BaseModel):
    kalem: str
    grup: str
    kod: str | None = None   # eski snapshot satırlarında anahtar bulunmayabilir
    sira: int | None = None    # reçetedeki 1 tabanlı satır sırası (yalnız malzeme satırları; maliyet satırlarında null)
    doviz: str | None = None   # malzemenin para birimi (malzeme satırları; eski snapshot'larda ve maliyet satırlarında null)
    miktar: str | None
    brut_miktar: str | None
    birim_fiyat: str | None
    tutar: str
    tutar_firesiz: str | None
    maliyet_yuzdesi: str | None
    fiyat_yuzdesi: str | None
    fire_orani: str | None
    fire_kaynagi: str | None
    miktar_kaynagi: str | None
    fiyat_kaynagi: str | None
    brut_miktar_elle: str | None
    birim_fiyat_elle: str | None
    birim: str | None = None         # malzeme: reçete satırı birimi; gider: SN/KG/ADET (kod eşlemesi); eski snapshot'ta null
    zs: str | None = None            # geçerli Z/S (yalnız malzeme satırları): elle yazılmışsa o, yoksa malzeme kartındaki
    zs_elle: bool | None = None      # Z/S reçete satırına elle yazılmış (Excel N)
    doviz_elle: bool | None = None   # para birimi reçete satırına elle yazılmış (Excel O)
    elle_alanlar: list[str] | None = None   # gider satırı: formül yerine elle yazılmış hücreler (miktar | brut_miktar | birim_fiyat | tutar)
    dugum_tipi: str | None = None    # yaprak | ara_mamul (yalnız reçete satırları)
    seviye: int | None = None        # reçete satırı seviyesi (yalnız malzeme satırları; eski snapshot'ta null)


class HesapToplamlari(BaseModel):
    malzeme: str
    direkt_iscilik: str
    gug: str
    uretim_gideri: str
    diger: str
    giydirilmis: str
    finansman_tl: str | None
    maliyet_tl: str
    maliyet_usd: str | None
    maliyet_eur: str | None
    maliyet_gbp: str | None = None
    maliyet_zar: str | None = None
    finansman: dict[str, str] | None = None   # para birimi -> finansman (faiz) tutarı; TL/USD/EUR/GBP/ZAR


class HesapFiyatlari(BaseModel):
    satis_tl: str
    satis_usd: str | None
    satis_eur: str | None
    suzme_kg_tl: str
    teklifler_usd: list[str]
    satis_gbp: str | None = None
    satis_zar: str | None = None
    teklif_kar_oranlari: list[str] | None = None
    satis_kar_orani: str | None = None


class UretimBilgisiCikis(BaseModel):
    pazar: str
    hat: str
    taze_tursu_sinifi: str
    ambalaj_hacmi: str
    suzme_kg: str
    vardiya_uretim_adedi: str
    vardiya_saati: str | None
    dolum_personel: str
    etiketleme_adedi: str
    etiket_personel: str
    mal_kabul_miktar_kg: str
    mal_kabul_fire: str
    pazarlama_yonetim_uygula: bool


class ParametreOzetiCikis(BaseModel):
    enflasyon: str
    maliyet_sapma: str | None
    kurlar: dict[str, str]
    faiz: dict[str, str]
    stok_ay: dict[str, str]
    satis_kar: str
    teklif_kar: list[str]


class HesapYaniti(BaseModel):
    urun_kodu: str
    senaryo_id: int
    hesap_tarihi: str
    satirlar: list[HesapSatiri]
    toplamlar: HesapToplamlari
    fiyatlar: HesapFiyatlari
    toplamlar_firesiz: HesapToplamlari | None
    fiyatlar_firesiz: HesapFiyatlari | None
    kullanilan_parametreler: dict[str, str]
    uyarilar: list[str]
    uretim: UretimBilgisiCikis | None = None            # eski snapshot'larda null
    parametreler: ParametreOzetiCikis | None = None     # eski snapshot'larda null
    notlar: list[str] | None = None   # yanıt her zaman liste döner; alan eski istemciler için isteğe bağlı bildirilir


class TopluYazilan(BaseModel):
    urun: int
    hedef: int
    recete: int      # yazılan reçete satırı sayısı (0: reçete gönderilmedi)
    parametre: int
    havuz: int


class TopluKaydetCikis(BaseModel):
    hesap: HesapYaniti | None
    hesap_id: int | None
    yazilan: TopluYazilan
    uyarilar: list[str]


class HesapKaydiYaniti(BaseModel):
    id: int
    olusturan: str
    hesap_tarihi: str


class HesapOzeti(BaseModel):
    id: int
    hesap_tarihi: str
    olusturan: str
    maliyet_tl: str | None
    satis_tl: str | None
    son_tur_no: int | None = None
    son_kar_orani: str | None = None
    son_musteri: str | None = None
    son_durum: str | None = None


class HesapListesi(BaseModel):
    kayitlar: list[HesapOzeti]
    toplam: int


class HesapKayitCikis(BaseModel):
    id: int
    urun_id: int
    senaryo_id: int
    hesap_tarihi: str
    olusturan: str
    girdi_snapshot: dict[str, Any]
    sonuc_snapshot: dict[str, Any]
    uyarilar: list[str]
    gorunum: HesapYaniti


class DegisiklikKaydi(BaseModel):
    id: int
    tablo: str
    kayit_id: int
    islem: str
    eski: Any = None
    yeni: Any = None
    kullanici: str
    zaman: str | None


class DegisiklikListesi(BaseModel):
    kayitlar: list[DegisiklikKaydi]
    toplam: int


class SenaryoListesi(BaseModel):
    kayitlar: list[SenaryoCikis]
    toplam: int


class TeklifCikis(BaseModel):
    id: int
    maliyet_hesabi_id: int
    tur_no: int
    kar_orani: str
    fiyat_tl: str
    fiyat_usd: str | None
    fiyat_eur: str | None
    musteri: str | None
    durum: str
    notu: str | None
    olusturan: str


class TeklifListesi(BaseModel):
    kayitlar: list[TeklifCikis]
    toplam: int


class SenaryoTeklifSatiri(BaseModel):
    teklif_id: int
    hesap_id: int
    urun_kodu: str
    urun_ad: str
    hesap_tarihi: str
    tur_no: int
    kar_orani: str
    fiyat_tl: str
    fiyat_usd: str | None
    fiyat_eur: str | None
    musteri: str | None
    durum: str
    olusturan: str
    olusturma_zamani: str | None


class SenaryoTeklifListesi(BaseModel):
    kayitlar: list[SenaryoTeklifSatiri]
    toplam: int


class MalzemeSatiri(BaseModel):
    """Kartlı satırda tüm alanlar, kartsız (`kart_yok`) satırda yalnız kod/ad/kart_yok bulunur (uç `response_model_exclude_unset` kullanır)."""
    kod: str
    ad: str | None
    tip: str | None = None
    birim: str | None = None
    para_birimi: str | None = None
    zs: str | None = None
    fiyat: str | None = None
    fiyatsiz: bool | None = None
    gecerlilik_basi: str | None = None   # geçerli fiyat kaydının başlangıcı (ISO); fiyat kaydı yoksa null
    kaynak: str | None = None            # geçerli fiyat kaydının kaynağı (elle / import / import-revize); fiyat kaydı yoksa null
    ilk_fiyat: str | None = None         # senaryodaki en eski fiyat kaydı (ilk bütçe); fiyat kaydı yoksa null
    revize: bool | None = None           # geçerli fiyat ilk bütçeden farklı mı (S.ALMA BF I ya da sonraki elle/import değişiklik)
    kart_yok: bool | None = None


class MalzemeListesi(BaseModel):
    kayitlar: list[MalzemeSatiri]
    toplam: int


class MalzemeKartiCikis(BaseModel):
    id: int
    kod: str
    ad: str


class FiyatEkleCikis(BaseModel):
    id: int
    fiyat: str
    gecerlilik_basi: str


class FiyatKaydi(BaseModel):
    id: int
    fiyat: str
    para_birimi: str | None
    gecerlilik_basi: str
    kaynak: str
    neden: str
    olusturan: str
    olusturma_zamani: str | None


class FiyatGecmisi(BaseModel):
    kayitlar: list[FiyatKaydi]
    toplam: int


class ParametreTanimi(BaseModel):
    anahtar: str
    aciklama: str | None
    birim: str | None


class ParametreTanimListesi(BaseModel):
    kayitlar: list[ParametreTanimi]
    toplam: int


class ParametreDegerCikis(BaseModel):
    id: int
    deger: str
    gecerlilik_basi: str


class ParametreKaydi(BaseModel):
    id: int
    deger: str
    gecerlilik_basi: str
    neden: str
    kapsam_tipi: str
    kapsam_id: int | None
    olusturan: str
    olusturma_zamani: str | None


class ParametreGecmisi(BaseModel):
    kayitlar: list[ParametreKaydi]
    toplam: int


class GiderAnahtari(BaseModel):
    alt_kalem: str
    pay_orani: str
    baz_miktar: str


class CarpanCikis(BaseModel):
    ad: str
    deger: str


class GiderHavuzuCikis(BaseModel):
    kod: str
    ad: str
    toplam_tutar: str
    baz_tipi: Literal["saniye", "kg", "adet"]
    baz_miktar: str | None
    taban_tutar: str | None = None       # doluysa toplam_tutar = taban_tutar × Π carpanlar
    carpanlar: list[CarpanCikis] = []
    anahtarlar: list[GiderAnahtari]


class PayKontrolSatiri(BaseModel):
    havuz: str
    toplam: str


class GiderHavuzlariCikis(BaseModel):
    kayitlar: list[GiderHavuzuCikis]
    toplam: int
    pay_kontrol: list[PayKontrolSatiri]


class HavuzKaydetCikis(GiderHavuzuCikis):
    pay_kontrol: list[PayKontrolSatiri]


class AmbalajCikis(BaseModel):
    ad: str
    hacim: str
    uretim_adedi: str
    katsayi: str


class AmbalajListesi(BaseModel):
    kayitlar: list[AmbalajCikis]
    toplam: int


class FireKuraliCikis(BaseModel):
    id: int
    kapsam_tipi: Literal["tip", "grup", "malzeme"]
    kapsam_deger: str
    oran: str
    oncelik: int
    gecerlilik_basi: str
    neden: str
    olusturan: str


class FireKuraliListesi(BaseModel):
    kayitlar: list[FireKuraliCikis]
    toplam: int


class MalzemeGrubuCikis(BaseModel):
    id: int
    ad: str
    malzeme_kodlari: list[str]


class GrupListesi(BaseModel):
    kayitlar: list[MalzemeGrubuCikis]
    toplam: int


class KartFarki(BaseModel):
    tur: str
    kod: str
    alanlar: list[str]


class YenidenAdlandirilan(BaseModel):
    eski: str
    yeni: str


class UrunParametreFarki(BaseModel):
    ad: str
    anahtar: str
    deger: str


class ImportOzeti(BaseModel):
    senaryo_id: int
    malzeme: int
    fiyat: int
    havuz: int
    ambalaj: int
    urun: int
    recete: int
    parametre: int
    atlanan: list[str]
    uyarilar: list[str]
    kart_farklari: list[KartFarki]
    yeniden_adlandirilan: list[YenidenAdlandirilan]
    urun_parametre_farklari: list[UrunParametreFarki]
    kapasite: int | None = None   # Üretim Adetleri satır sayısı (sayfa yoksa 0)
    mod: Literal["yeni", "tamamla"] = "yeni"   # tamamla: yalnız mevcut senaryodaki eksikler eklendi (sayımlar = eklenenler)
    satis_notu: int = 0   # satış fiyatı notu eklendiyse 1
    revize: int = 0   # S.ALMA BF I sütunundan (revize fiyat) yazılan ek fiyat kaydı sayısı


class FiyatYeni(BaseModel):
    kod: str
    yeni: str


class FiyatDegisen(BaseModel):
    kod: str
    eski: str
    yeni: str


class FiyatListesiRevize(BaseModel):
    kod: str
    ilk: str | None
    revize: str


class FiyatListesiOnizleme(BaseModel):
    yeni: list[FiyatYeni]
    degisen: list[FiyatDegisen]
    ayni: int
    hatali: list[str]
    revize: list[FiyatListesiRevize] = []    # I sütunu (revize) F'den farklı olan satırlar; geçerli olacak fiyat I'dır


class FiyatListesiUygulama(BaseModel):
    yazilan: int
    kodlar: list[str]


class KodDegistirCikis(UrunCikis):
    """PATCH /urunler/{kod}/kod: güncellenmiş ürün kartı."""


class MetinParametreGiris(BaseModel):
    anahtar: str
    deger: str = Field(max_length=1000)
    gecerlilik_basi: date
    neden: str = Field(min_length=1)


class MetinParametreCikis(BaseModel):
    id: int
    anahtar: str
    deger: str
    gecerlilik_basi: str
    neden: str | None
    olusturan: str


class MetinParametreListesi(BaseModel):
    kayitlar: list[MetinParametreCikis]
    toplam: int


class KapasiteAlanlari(BaseModel):
    net_kapasite: Decimal = Field(ge=0)
    net_sure: Decimal = Field(ge=0)
    toplam_kapasite: Decimal = Field(ge=0)
    toplam_sure: Decimal = Field(ge=0)
    hedef_uretim: Decimal = Field(ge=0)
    ortalama_isci: Decimal = Field(ge=0)


class KapasiteGiris(KapasiteAlanlari):
    neden: str = Field(min_length=1)
    urun_ad: str | None = None   # yalnız yeni kayıtta / ad düzeltmesinde


class KapasiteCikis(BaseModel):
    urun_kodu: str
    urun_ad: str | None
    net_kapasite: str
    net_sure: str
    toplam_kapasite: str
    toplam_sure: str
    hedef_uretim: str
    ortalama_isci: str


class KapasiteListesi(BaseModel):
    kayitlar: list[KapasiteCikis]
    toplam: int


class AmbalajTuruOzeti(BaseModel):
    tur: str
    urun_sayisi: int
    uretim_adedi: str


class KapakOzeti(BaseModel):
    ad: str
    urun_sayisi: int
    uretim_adedi: str


class AmbalajOzeti(BaseModel):
    turler: list[AmbalajTuruOzeti]
    kapaklar: list[KapakOzeti]


class SatisGiris(BaseModel):
    urun_kodu: str = Field(min_length=1, max_length=32)
    musteri: str = Field(min_length=1, max_length=200)
    tarih: date
    fiyat: Decimal = Field(ge=0)
    para_birimi: Literal["TL", "USD", "EUR", "GBP", "CHF", "RUB", "ZAR"]
    adet: Decimal = Field(gt=0)


class SatisCikis(BaseModel):
    id: int
    urun_kodu: str
    urun_ad: str
    musteri: str
    tarih: str
    fiyat: str
    para_birimi: str
    adet: str
    olusturan: str


class SatisListesi(BaseModel):
    kayitlar: list[SatisCikis]
    toplam: int


class SatisYuklemeHatasi(BaseModel):
    satir_no: int
    mesaj: str


class SatisYuklemeOzeti(BaseModel):
    eklenen: int
    hatalar: list[SatisYuklemeHatasi]


# ---------------------------------------------------------------- Karşılaştırma (Faz 5 T3)
class AileUyeCikis(BaseModel):
    kod: str
    ad: str
    ambalaj_hacmi: str
    ambalaj_etiket: str | None = None


class AileCikis(BaseModel):
    aile: str
    aile_ad: str
    urun_sayisi: int
    tek_uyeli: bool
    urunler: list[AileUyeCikis]


class AileGiris(BaseModel):
    aile: str | None = None   # görünen ad: kullanıcı yazar, sunucu anahtarı türetir (ı/i katlanmış küçük harf); null: addan yeniden türet


class AileDegisCikis(BaseModel):
    kod: str
    aile: str      # gruplama/URL anahtarı
    aile_ad: str   # görünen ad


class GecenYilPb(BaseModel):
    fiyat: str
    adet: str
    musteri_sayisi: int
    kayit_sayisi: int


class GecenYilCikis(BaseModel):
    donem_basi: str
    donem_sonu: str
    kayit_sayisi: int
    musteri_sayisi: int
    para_birimleri: dict[str, GecenYilPb]


class EnflasyonPb(BaseModel):
    gecen_yil: str
    yeni: str
    oran: str
    fark_yuzde: str
    durum: Literal["altinda", "ustunde"]


class UretimEtkisiCikis(BaseModel):
    butce_adedi: str
    hedef_adedi: str
    oran: str | None
    maliyet_tl_butce: str
    maliyet_usd_butce: str | None
    maliyet_eur_butce: str | None
    satis_tl_butce: str
    satis_usd_butce: str | None
    satis_eur_butce: str | None
    maliyet_tl_hedef: str
    maliyet_usd_hedef: str | None
    maliyet_eur_hedef: str | None
    satis_tl_hedef: str
    satis_usd_hedef: str | None
    satis_eur_hedef: str | None


class UrunKarsilastirmaCikis(BaseModel):
    gecen_yil: GecenYilCikis | None
    enflasyon_esigi: dict[str, EnflasyonPb] | None
    uretim_adedi_etkisi: UretimEtkisiCikis | None
    hesap_hatasi: str | None = None   # bütçe hesabı yapılamadıysa (örn. üretim hedefi yok) mesaj; enflasyon/uretim alanları null olur


class AileSatiriCikis(BaseModel):
    kod: str
    ad: str
    ambalaj_hacmi: str
    ambalaj_etiket: str | None = None
    ambalaj_ml: str | None = None   # ml/g eşdeğeri (sıralama anahtarı)
    suzme_kg: str
    satis_tl: str | None
    satis_usd: str | None
    suzme_kg_fiyati: str | None
    kg_basi_satis_tl: str | None
    onceki_ile_fark_yuzde: str | None
    hata: str | None


class AileKarsilastirmaCikis(BaseModel):
    aile: str
    aile_ad: str
    satirlar: list[AileSatiriCikis]


# ---- Veri Aktar (/aktarim/...) ----

class AktarimUretimYeni(BaseModel):
    urun_kodu: str
    urun_ad: str
    alanlar: dict[str, str]


class AktarimUretimDegisen(BaseModel):
    urun_kodu: str
    alan: str
    eski: str | None
    yeni: str | None


class AktarimOnizleUretim(BaseModel):
    yeni: list[AktarimUretimYeni]
    degisen: list[AktarimUretimDegisen]
    ayni: int
    uyarilar: list[str]


class AktarimUygulaUretim(BaseModel):
    eklenen: int
    guncellenen: int
    uyarilar: list[str]


class AktarimYeniMalzeme(BaseModel):
    kod: str
    ad: str
    tip: str | None
    birim: str | None
    para_birimi: str | None
    zs: str | None


class AktarimKartFarki(BaseModel):
    kod: str
    alanlar: list[str]


class AktarimFiyatYeni(BaseModel):
    kod: str
    yeni: str
    para: str | None


class AktarimFiyatDegisen(BaseModel):
    kod: str
    eski: str
    yeni: str
    para: str | None
    eski_para: str | None


class RevizeFiyat(BaseModel):
    """S.ALMA BF: F ilk bütçe, I sonradan yapılan güncelleme (geçerli olan). ilk: F boşsa null."""
    kod: str
    ilk: str | None
    revize: str


class AktarimOnizleSatinAlma(BaseModel):
    yeni_malzeme: list[AktarimYeniMalzeme]
    kart_farki: list[AktarimKartFarki]
    fiyat_yeni: list[AktarimFiyatYeni]       # yeni: geçerli olacak fiyat (revize varsa I)
    fiyat_degisen: list[AktarimFiyatDegisen]
    ayni: int
    hatali: list[str]
    revize: list[RevizeFiyat]                # bilgi amaçlı: I sütunu F'den farklı olan satırlar
    revize_sayisi: int


class AktarimUygulaSatinAlma(BaseModel):
    malzeme_eklenen: int
    kart_guncellenen: int
    fiyat_yazilan: int
    kodlar: list[str]
    ayni: int
    revize_yazilan: int                      # fiyat_yazilan içinde ayrıca revize (I) kaydı da yazılan malzeme sayısı


class AktarimHavuz(BaseModel):
    kod: str
    ad: str
    eski_toplam: str | None
    yeni_toplam: str
    eski_baz: str | None
    yeni_baz: str | None
    anahtar_farki: bool
    degisti: bool
    yeni_taban: str | None = None          # Excel formülü taban × çarpan kalıbındaysa taban (B3); değilse null (toplam doğrudan yazılır)
    yeni_carpanlar: list[str] = []         # o formüldeki çarpanlar, sırasıyla


class AktarimAmbalajFarki(BaseModel):
    ad: str
    alan: str
    eski: str | None
    yeni: str | None


class AktarimAmbalaj(BaseModel):
    eski_adet: int
    yeni_adet: int
    degisen: list[AktarimAmbalajFarki]


class AktarimOnizleGider(BaseModel):
    havuz: list[AktarimHavuz]
    ambalaj: AktarimAmbalaj


class AktarimUygulaGider(BaseModel):
    havuz: int
    ambalaj: int
    havuz_kodlari: list[str]


class ReceteFarkSatiri(BaseModel):
    kod: str
    ad: str
    alanlar: list[str] = []   # yalnız değişenlerde: "miktar", "fire", "elle brüt", "elle fiyat"


class ReceteAktarimSayfasi(BaseModel):
    sayfa: str
    kod: str
    ad: str
    durum: Literal["yeni_urun", "yeni_recete", "degisti", "ayni"]
    satir_sayisi: int
    elle_fiyat: int
    elle_brut: int
    eklenen: list[ReceteFarkSatiri]
    cikan: list[ReceteFarkSatiri]
    degisen: list[ReceteFarkSatiri]
    uyarilar: list[str]
    secili: bool   # önerilen seçim: değişen/yeni ve '(2)' varyantı olmayan sayfalar


class ReceteAktarimHatasi(BaseModel):
    sayfa: str
    mesaj: str


class AktarimOnizleRecete(BaseModel):
    sayfalar: list[ReceteAktarimSayfasi]
    hatali: list[ReceteAktarimHatasi]


class ReceteUygulanan(BaseModel):
    sayfa: str
    kod: str
    versiyon: int


class AktarimUygulaRecete(BaseModel):
    uygulanan: list[ReceteUygulanan]
    yeni_urun: int
