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
    onay: bool = Field(default=False, description="Fiyat eşikten fazla değişiyorsa (422 kod=fiyat_sapma) kullanıcı onayıyla yeniden gönderilir")


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
    # Marka ("Berrak" ise liste fiyatı uygulanır). Gönderilmezse: yeni üründe addan türetilir, var olanda değişmez; null/"" bilerek boş.
    marka: str | None = Field(default=None, max_length=64)


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
    ortalama_maliyet_tl: str | None = None     # stokta kalan varsa (stok + bu yıl üretim) ağırlıklı ortalama maliyet; yoksa null
    stok_etkisi: bool = False                  # ortalama maliyet hesaplandı (stok adedi > 0 ve üretim adedi biliniyor)


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
    marka: str | None = None   # "Berrak" ise liste fiyatı uygulanır; null: marka yok/bilinmiyor
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


class StokDevriCikis(BaseModel):
    """Ürünün stokta kalan (geçen yıldan devreden) bilgisi ve ortalama maliyet. İlk dört alan elle girilenler (kayıt yoksa null);
    `_kullanilan` alanlar hesapta kullanılan değerler. Oranlar 0,40 = %40; tutarlar TL."""
    urun_kodu: str
    adet: str | None
    birim_maliyet: str | None
    enflasyon: str | None                 # elle; null ise çalışmanın enflasyon parametresi kullanılır
    uretim_adedi: str | None              # elle; null ise geçen yıl satış adedi - stok (en az 0)
    enflasyon_kullanilan: str | None
    uretim_adedi_kullanilan: str | None
    uretim_adedi_kaynagi: Literal["elle", "satis_gecmisi"] | None
    guncel_stok_maliyeti: str | None      # birim_maliyet x (1 + enflasyon_kullanilan)
    bu_yil_maliyet: str | None            # finansman dahil maliyet TL (Genel Bakış "Maliyet TL")
    ortalama_maliyet: str | None          # (stok x güncel + üretim x bu yıl) / (stok + üretim)
    stok_payi: str | None                 # stok adedi / (stok + üretim)
    stok_etkisi: bool                     # ortalama hesaplandı
    aciklama: str | None                  # ortalama neden yok (null: sorun yok ya da kayıt yok)


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
    stok_devri: StokDevriCikis | None = None   # stokta kalan kaydı yoksa null
    satis_ortalamadan: bool = False   # satış fiyatları ortalama maliyetten hesaplandı (`satis_ortalama_maliyetten` = 1 ve stok etkisi var)


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


# ---------------------------------------------------------------- Liste fiyatı çalışması (Berrak)
ListePazari = Literal["yurtici", "yurtdisi"]


class ListeFiyatiGiris(BaseModel):
    urun_kodu: str = Field(min_length=1, max_length=32)
    yil: int = Field(ge=2000, le=2100)
    pazar: ListePazari = "yurtici"
    liste_fiyati: Decimal = Field(gt=0)
    birim_maliyet: Decimal | None = Field(default=None, gt=0)
    bolen: Decimal | None = Field(default=None, gt=0, le=1)   # boşsa kaydedildiği andaki geçerli bölen yazılır


class ListeFiyatiCikis(BaseModel):
    urun_kodu: str
    yil: int
    pazar: ListePazari
    liste_fiyati: str
    birim_maliyet: str | None
    bolen: str | None   # kaydedildiği andaki bölen; eski kayıtlarda null
    ornek: bool


class ListeGecmisSatiri(BaseModel):
    yil: int
    pazar: ListePazari
    liste_fiyati: str
    birim_maliyet: str | None
    bolen: str | None
    ornek: bool


class ListeCalismaSatiri(BaseModel):
    kod: str
    ad: str
    hat: str | None
    hata: str | None
    maliyet_tl: str | None
    satis_tl: str | None
    yeni_liste_ham: str | None   # satış ÷ bölen, yuvarlamasız
    yeni_liste: str | None       # yuvarlanmış (en yakın adım katı); artışlar bununla
    onceki_yil: int | None
    onceki_liste: str | None
    liste_artis: str | None
    maliyet_artis: str | None
    fark: str | None
    gecmis: list[ListeGecmisSatiri]


class ListeCalismaOzeti(BaseModel):
    liste_artis_ort: str | None
    maliyet_artis_ort: str | None
    fark: str | None
    karsilastirilan: int
    urun_sayisi: int
    gerisinde: int


class ListeYilSatiri(BaseModel):
    yil: int
    liste_artis_ort: str | None
    maliyet_artis_ort: str | None
    urun_sayisi: int


class ListeBolenleri(BaseModel):
    yurtici: str
    yurtdisi: str


class ListeCalismasi(BaseModel):
    """Yalnız Berrak markalı ürünler; `pazar` için hesaplanır."""
    yil: int
    pazar: ListePazari
    bolen: str                  # uygulanan bölen (deneme ?bolen= ya da kayıtlı ya da varsayılan)
    bolenler: ListeBolenleri    # iki pazarın kayıtlı (yoksa varsayılan) bölenleri; denemeden etkilenmez
    bolen_kayitli: bool         # uygulanan bölen bu pazar için senaryoda kayıtlı parametre mi
    varsayilan_bolen: str       # bu pazarın varsayılanı (yurtiçi 0.63, yurtdışı 0.90)
    yuvarlama: str              # uygulanan adım, TL (yuvarlama_secenekleri'nden biri)
    yuvarlama_kayitli: bool
    varsayilan_yuvarlama: str
    yuvarlama_secenekleri: list[str]
    berrak_disi: int            # çalışmada olup Berrak olmayan (listeye girmeyen) ürün sayısı
    ornek_var: bool
    ozet: ListeCalismaOzeti
    yillar: list[ListeYilSatiri]
    kayitlar: list[ListeCalismaSatiri]


class ListeYuklemeOzeti(BaseModel):
    yazilan: int
    hatalar: list[SatisYuklemeHatasi]


class ListeOrnekOzeti(BaseModel):
    yazilan: int


# ---------------------------------------------------------------- Analizler (ya olursa, zam etkisi)
class AnalizSatiri(BaseModel):
    kod: str
    ad: str
    hat: str | None
    hata: str | None
    maliyet_once: str | None
    maliyet_sonra: str | None
    fark_tl: str | None
    fark_yuzde: str | None
    satis_once: str | None
    satis_sonra: str | None
    kar_orani: str | None
    mevcut_fiyatla_kar: str | None
    esik_alti: bool


class AnalizOzeti(BaseModel):
    urun_sayisi: int
    etkilenen: int
    ort_fark_yuzde: str | None
    en_yuksek_fark_yuzde: str | None
    esik_alti: int
    hatali: int


class YaOlursaVarsayimlari(BaseModel):
    kur: str
    ambalaj: str
    hammadde: str
    adet: str


class YaOlursaCikis(BaseModel):
    varsayimlar: YaOlursaVarsayimlari
    marj_esigi: str
    ozet: AnalizOzeti
    kayitlar: list[AnalizSatiri]


class ZamMalzemesi(BaseModel):
    kod: str
    ad: str
    tip: str | None
    birim: str | None
    fiyat: str | None
    para_birimi: str | None
    yeni_fiyat: str | None


class ZamEtkisiCikis(BaseModel):
    malzeme: ZamMalzemesi
    oran: str
    marj_esigi: str
    ozet: AnalizOzeti
    kayitlar: list[AnalizSatiri]


# ---------------------------------------------------------------- Maliyet muhasebesi (SMM)
class SmmExcelKontrol(BaseModel):
    karsilastirilan: int
    esit: int
    farkli: int
    farkli_ornek: list[str]
    excelde_sarf_bos: int
    excelde_sarf_bos_ornek: list[str]
    excelde_sarf_bos_tutar: str
    excelde_tekrar: list[str] = []


class SmmDonemCikis(BaseModel):
    id: int
    yil: int
    ay: int
    ad: str
    kaynak_dosya: str | None
    finansman: str
    kalem_sayisi: int | None
    excel_kontrol: SmmExcelKontrol | None
    olusturan: str
    recete_kaynagi: str = "excel"
    devir_donem_id: int | None = None
    kilitli: bool = False
    kilitleyen: str | None = None
    kilit_zamani: str | None = None   # kapatıldığı an (UTC ISO 8601); dönem açıksa null


class SmmKaynakSon(BaseModel):
    dosya: str | None = None
    zaman: str | None = None
    kullanici: str | None = None
    satir: int | None = None
    excel: bool = False


class SmmVeriKaynagi(BaseModel):
    kaynak: str
    ad: str
    zorunlu: bool
    yuklendi: bool
    dolu: int
    son: SmmKaynakSon | None
    elle: int = 0                  # mizan kaynaklarında elle girilmiş/değiştirilmiş satır sayısı
    elle_uyari: str | None = None  # "N elle satır var, yükleme bunları siler"


class SmmDonemBasi(BaseModel):
    kaynak: str
    dolu: int
    tutar: str
    hazir: bool


class SmmVeriAyarlari(BaseModel):
    finansman: str
    gider_720: str
    gider_730: str


class SmmGrupsuzKalemler(BaseModel):
    """Türü / mizan kodu boş olduğu için stok hesabı (150/151/152) bulunamayan, SMM tablosuna girmeyen hareketli kalemler."""
    kalem: int
    alim_tutar: str
    dbs_tutar: str
    ornek: list[str]


class SmmVeriDurumu(BaseModel):
    donem: "SmmDonemCikis"
    donem_basi: SmmDonemBasi
    kaynaklar: list[SmmVeriKaynagi]
    eksik: list[str]
    ayarlar: SmmVeriAyarlari
    turler: list[str]
    grupsuz: SmmGrupsuzKalemler | None = None
    devir: "SmmVeriDevir | None" = None


class SmmVeriDevir(BaseModel):
    """Açılış stoku devralınan dönemin şu anki kapanışıyla uyumlu mu (kısa özet; ayrıntı GET …/devir-durumu)."""
    uyumlu: bool
    fark_kalem: int
    fark_tutar: str = "0"   # açılış toplamı − kapanış toplamı (TL)
    onceki_ad: str
    onceki_kilitli: bool


class SmmDevirOnceki(BaseModel):
    id: int
    ad: str
    kilitli: bool


class SmmDevirFarki(BaseModel):
    kod: str
    ad: str | None = None
    acilis_miktar: str
    kapanis_miktar: str
    acilis_tutar: str
    kapanis_tutar: str
    elle: bool = False   # açılış değeri ekrandan elle girilmiş / düzeltilmiş


class SmmDevirDurumu(BaseModel):
    """`onceki` null: dönemin açılışı devirle gelmemiş (Excel'den yüklenmiş ya da ilk dönem); o durumda uyumlu=true."""
    onceki: SmmDevirOnceki | None
    uyumlu: bool
    fark_kalem: int
    fark_tutar: str
    acilis_tutar: str | None = None
    kapanis_tutar: str | None = None
    elle_kalem: int = 0
    ornek: list[SmmDevirFarki]   # TL farkı en büyük ilk 20 kalem


class SmmDevirYenileGiris(BaseModel):
    neden: str = Field(min_length=1, max_length=300)
    elle_ez: bool = False   # true: elle girilmiş açılış değerleri de önceki kapanışla ezilir


class SmmDevirYenileCikis(BaseModel):
    donem: "SmmDonemCikis"
    guncellenen: int
    eklenen: int
    elle_kalem: int        # önceki kapanıştan farklı, elle girilmiş açılış sayısı
    elle_korundu: bool     # true: bunlara dokunulmadı (elle_ez=false)
    durum: SmmDevirDurumu


class SmmKilitCikis(SmmDonemCikis):
    uyari: str | None = None   # kilit açılınca: sonraki dönemin açılışı bu dönemden devralındıysa


class SmmAyarGiris(BaseModel):
    finansman: Decimal | None = None
    gider_720: Decimal | None = None
    gider_730: Decimal | None = None


class SmmKilitGiris(BaseModel):
    kilitli: bool
    zorla: bool = False   # kapatırken eksikler (409 kapanis_eksik) görüldükten sonra "yine de kapat"


class SmmYeniDonemGiris(BaseModel):
    yil: int
    ay: int


class SmmDevir(BaseModel):
    onceki: str | None
    kalem: int
    tutar: str
    uyari: str | None = None   # önceki dönem kapatılmadıysa: devir sonradan değişebilir


class SmmYeniDonemCikis(SmmDonemCikis):
    devir: SmmDevir


class SmmReceteKaynagiGiris(BaseModel):
    kaynak: Literal["excel", "ana"]


class SmmAnaReceteOnizleme(BaseModel):
    satir_sayisi: int
    urun_sayisi: int
    asama: dict[str, int]
    alternatifli_urun: int
    mevcut_urun: int
    eklenecek_urun: int
    kalkacak_urun: int
    degisecek_urun: int
    korunan: list["SmmKorunanRecete"] = []
    ornek: list[dict[str, str | None]]


class SmmKorunanRecete(BaseModel):
    ana_kod: str
    ana_ad: str | None
    caniasta_var: bool
    canias_farkli: bool


class SmmReceteYuklemeBilgi(BaseModel):
    kaynak_dosya: str | None
    satir_sayisi: int
    urun_sayisi: int
    olusturan: str
    zaman: str | None


class SmmReceteUrunu(BaseModel):
    ana_kod: str
    ana_ad: str | None
    asama: int
    alternatifler: list[str]
    secili_alternatif: str
    satir_sayisi: int
    elle: bool = False


class SmmReceteListesi(BaseModel):
    son_yukleme: SmmReceteYuklemeBilgi | None
    asama_sayilari: dict[str, int]
    alternatifli_urun: int
    elle_urun: int = 0
    kayitlar: list[SmmReceteUrunu]


class SmmReceteKalemi2(BaseModel):
    id: int
    satir_no: int
    kalem_tipi: int | None
    malzeme_kod: str
    malzeme_ad: str | None
    miktar: str
    birim: str | None
    fire_orani: str


class SmmReceteAlternatifi(BaseModel):
    alternatif: str
    satirlar: list[SmmReceteKalemi2]


class SmmReceteDetayi(BaseModel):
    ana_kod: str
    ana_ad: str | None
    asama: int
    kod_asamasi: int = 20
    secili_alternatif: str
    elle: bool = False
    elle_degistiren: str | None = None
    canias_var: bool = False
    alternatifler: list[SmmReceteAlternatifi]


class SmmReceteSatirGiris(BaseModel):
    """Reçeteye satır. `fire_orani` oran (0,05 = %5)."""
    alternatif: str = "00"
    malzeme_kod: str = Field(min_length=1, max_length=40)
    malzeme_ad: str | None = Field(None, max_length=200)
    miktar: Decimal
    birim: str = Field(min_length=1, max_length=16)
    fire_orani: Decimal = Decimal(0)


class SmmYeniReceteGiris(SmmReceteSatirGiris):
    ana_kod: str = Field(min_length=1, max_length=40)
    ana_ad: str | None = Field(None, max_length=200)


class SmmReceteSatirGuncelle(BaseModel):
    malzeme_kod: str | None = Field(None, max_length=40)
    malzeme_ad: str | None = Field(None, max_length=200)
    miktar: Decimal | None = None
    birim: str | None = Field(None, max_length=16)
    fire_orani: Decimal | None = None


class SmmAlternatifKopyaGiris(BaseModel):
    kaynak: str
    yeni: str


class SmmMalzemeAdayi(BaseModel):
    kod: str
    ad: str | None
    birim: str | None


class SmmAlternatifGiris(BaseModel):
    alternatif: str


class SmmReceteFarki(BaseModel):
    asama: int
    ana_kod: str
    ana_ad: str | None
    durum: str
    ayrinti: dict[str, list[str]] | None


class SmmReceteKiyas(BaseModel):
    donem: int
    sayilar: dict[str, dict[str, int]]
    farklar: list[SmmReceteFarki]


class SmmDonemListesi(BaseModel):
    kayitlar: list[SmmDonemCikis]


class SmmStokSatiri(BaseModel):
    kod: str
    ad: str | None
    birim: str | None
    tur: str | None
    mizan_kodu: str | None
    dbs_miktar: str
    dbs_tutar: str
    alim_miktar: str
    alim_tutar: str
    iade_miktar: str
    iade_tutar: str
    uretim_miktar: str
    sayim_miktar: str
    satis_miktar: str = "0"
    sahit_miktar: str = "0"
    finansman_payi: str
    toplam_miktar: str
    toplam_tutar: str
    ortalama_fiyat: str
    kalan_miktar: str
    kalan_tutar: str
    dss_tutar: str
    sarf_miktar: str
    sarf_tutar: str
    uretime_giden: str
    kontrol: bool


class SmmStokToplamlari(BaseModel):
    dbs_tutar: str
    alim_tutar: str
    finansman_payi: str
    iade_tutar: str
    dss_tutar: str
    sarf_tutar: str
    uretime_giden: str


class SmmTurOzeti(BaseModel):
    tur: str
    kalem: int
    dbs_tutar: str
    alim_tutar: str
    dss_tutar: str
    sarf_tutar: str


class SmmStokTablosu(BaseModel):
    donem: SmmDonemCikis
    toplamlar: SmmStokToplamlari
    kontrol_sayisi: int
    turler: list[SmmTurOzeti]
    kayitlar: list[SmmStokSatiri]


class SmmHavuz(BaseModel):
    anahtar: str
    ad: str
    tutar: str
    excel: str
    degisti: bool


class SmmDagitim(BaseModel):
    havuzlar: list[SmmHavuz]
    dagitilan: str
    mizan_720: str
    mizan_730: str
    dagitilmayan: str | None
    anahtarlar: list["SmmDagitimAnahtari"] = []


class SmmDagitimAnahtari(BaseModel):
    anahtar: str
    ad: str
    alan: str
    excel_varsayilani: str


class SmmDagitimGiris(BaseModel):
    """Değiştirilecek havuzlar (anahtar -> TL) ve dağıtım anahtarları (havuz -> uretim / dolum_sn / etiket_adam_sn …). Verilmeyenler kalır."""
    havuzlar: dict[str, Decimal] = {}
    anahtarlar: dict[str, str] = {}


class SmmUrunElleGiris(BaseModel):
    """Birim başına TL; null = formüle dön."""
    alanlar: dict[str, Decimal | None]


class SmmAsamaGiris(BaseModel):
    asama: int


class SmmSure(BaseModel):
    id: int
    kod: str
    mamul_kod: str | None
    yari_mamul_kod: str | None
    ad: str | None
    vardiya_uretim: str
    dolum_isci: str
    etiket_isci: str
    dolum_sn: str
    dolum_adam_sn: str
    etiket_sn: str
    etiket_adam_sn: str


class SmmSureListesi(BaseModel):
    donem: "SmmDonemCikis"
    kayitlar: list[SmmSure]


class SmmSureGiris(BaseModel):
    mamul_kod: str | None = Field(None, max_length=40)
    yari_mamul_kod: str | None = Field(None, max_length=40)
    ad: str | None = Field(None, max_length=200)
    vardiya_uretim: Decimal | None = None
    dolum_isci: Decimal | None = None
    etiket_isci: Decimal | None = None
    dolum_sn: Decimal | None = None
    dolum_adam_sn: Decimal | None = None
    etiket_sn: Decimal | None = None
    etiket_adam_sn: Decimal | None = None


class SmmAsamaKarsilastirma(BaseModel):
    karsilastirilan: int
    esit: int
    farkli: int
    farkli_ornek: list[str]


class SmmAsamaOzeti(BaseModel):
    asama: int
    ad: str
    urun_sayisi: int
    uretilen_urun: int
    sure_yok: int
    alim_kurali: int
    kod_bosluklu: int
    excel_elle: int
    malzeme: str
    iscilik: str
    gug: str
    fire: str
    toplam: str
    excel: SmmAsamaKarsilastirma


class SmmAsamaUrunu(BaseModel):
    kod: str
    ad: str | None
    birim: str | None
    uretim_miktar: str
    malzeme: str
    stok_payi: str
    iscilik: str
    gug: str
    fire: str
    alim_fiyati: str
    alim_kurali: bool
    birim_maliyet: str
    toplam: str
    satir_sayisi: int
    sure_yok: bool
    elle_alanlar: list[str] = []
    excel_birim: str | None
    excel_farkli: bool


class SmmUretimMaliyeti(BaseModel):
    donem: SmmDonemCikis
    asama: int
    ozetler: list[SmmAsamaOzeti]
    dagitim: SmmDagitim
    kayitlar: list[SmmAsamaUrunu]


class SmmReceteKalemi(BaseModel):
    malzeme_kod: str
    malzeme_ad: str | None
    miktar: str
    birim: str | None
    carpan: str
    fiyat: str
    fiyat_kaynagi: str
    tutar: str
    fire_orani: str
    fire_tutari: str


class SmmUrunRecetesi(BaseModel):
    urun: SmmAsamaUrunu
    asama: int
    satirlar: list[SmmReceteKalemi]


class SmmSarfSatiri(BaseModel):
    kod: str
    ad: str | None
    birim: str | None
    tur: str
    ortalama_fiyat: str
    recete_sarf: str
    stok_sarf: str
    fark: str
    fark_tutar: str
    fark_orani: str | None
    urun_sayisi: int
    kartsiz: bool
    uretim_girisi: str
    satis_miktar: str
    sahit_miktar: str
    birim_uyumsuz: bool
    recete_birimleri: list[str]


class SmmSarfToplamlari(BaseModel):
    recete_tutar: str = "0"
    stok_tutar: str = "0"
    fazla: str = "0"
    eksik: str = "0"


class SmmTabloSatiri(BaseModel):
    ad: str
    isaret: str
    tutar: str


class SmmTabloBlogu(BaseModel):
    hesap: str
    ad: str
    kalem: int
    satirlar: list[SmmTabloSatiri]
    sonuc_ad: str
    sonuc: str


class SmmDssKiyas(BaseModel):
    karsilastirilan: int
    esit: int
    farkli: int
    farkli_ornek: list[str]
    excel_toplam: str
    bizim_toplam: str


class SmmMizanKiyas(BaseModel):
    hesap: str
    ad: str
    mizan: str
    sayim: str
    fark: str


class SmmFisSatiri(BaseModel):
    hesap: str
    ad: str
    aciklama: str
    borc: str
    alacak: str


class SmmOzeti(BaseModel):
    donem: SmmDonemCikis
    smm: str
    uretim_maliyeti: str
    uretilen: str
    ilk_madde: str
    donem_sonu_stok: str
    satilan_hm_ym: str
    tablo: list[SmmTabloBlogu]
    dss_kiyas: SmmDssKiyas
    mizan_kiyas: list[SmmMizanKiyas]
    mizan_tarihi: str | None
    yansitilan: dict[str, str | None]
    fis: list[SmmFisSatiri]
    fis_borc: str
    fis_alacak: str


class SmmSarfFarki(BaseModel):
    donem: SmmDonemCikis
    toplamlar: SmmSarfToplamlari
    birim_uyumsuz_sayisi: int
    turler: list[str]
    kayitlar: list[SmmSarfSatiri]


# ---------------------------------------------------------------- Analizler: kur riski, kârlılık haritası
class KurRiskiOzeti(BaseModel):
    urun_sayisi: int
    doviz_payi_ort: str | None
    yillik_maliyet: str
    yillik_etki: str
    adetsiz_urun: int
    hatali: int


class KurRiskiParaBirimi(BaseModel):
    para_birimi: str
    yillik_etki: str
    pay: str | None


class KurRiskiSatiri(BaseModel):
    kod: str
    ad: str
    hat: str | None
    maliyet: str | None
    doviz_payi: str | None
    usd_payi: str | None
    eur_payi: str | None
    birim_etki: str | None
    yeni_maliyet: str | None
    yillik_adet: str | None
    yillik_etki: str | None
    hata: str | None


class KurRiskiCikis(BaseModel):
    oran: str
    kurlar: dict[str, str]
    adet_kaynagi: str   # yıllık adedin kaynağı: "satis_gecmisi" (geçen yıl satış adedi)
    ozet: KurRiskiOzeti
    para_birimleri: list[KurRiskiParaBirimi]
    kayitlar: list[KurRiskiSatiri]


class KarlilikOzeti(BaseModel):
    yuksek_adet_yuksek_marj: int
    yuksek_adet_dusuk_marj: int
    dusuk_adet_yuksek_marj: int
    dusuk_adet_dusuk_marj: int
    adetsiz: int
    hatali: int


KarlilikBolgesi = Literal["yuksek_adet_yuksek_marj", "yuksek_adet_dusuk_marj", "dusuk_adet_yuksek_marj", "dusuk_adet_dusuk_marj"]


class KarlilikSatiri(BaseModel):
    kod: str
    ad: str
    aile: str | None
    adet: str | None
    maliyet: str | None
    satis_fiyati: str | None
    marj: str | None
    fiyat_kaynagi: Literal["satis_gecmisi", "hesap"] | None
    yillik_kar: str | None
    bolge: KarlilikBolgesi | None
    hata: str | None
    maliyet_kaynagi: Literal["bu_yil", "ortalama"] | None = None   # ortalama: `satis_ortalama_maliyetten` = 1 ve stokta kalan var


class KarlilikCikis(BaseModel):
    esik_marj: str
    esik_adet: str | None
    adet_kaynagi: str   # yıllık adedin kaynağı: "satis_gecmisi" (geçen yıl satış adedi)
    ozet: KarlilikOzeti
    kayitlar: list[KarlilikSatiri]


class HedefFiyatOzeti(BaseModel):
    urun_sayisi: int
    zam_gereken: int      # gereken_zam > 0
    fiyatsiz: int         # hatasız ama geçen yıl fiyatı yok
    hatali: int
    yillik_ek_gelir: str  # yalnız pozitif yıllık ek gelirlerin toplamı
    ort_zam: str | None   # ciro ağırlıklı: Σ(hedef - geçen) x adet / Σ geçen x adet


class HedefFiyatSatiri(BaseModel):
    kod: str
    ad: str
    marka: str | None
    aile: str | None
    adet: str | None
    maliyet: str | None
    hesap_fiyati: str | None      # çalışmanın hesapladığı satış fiyatı
    gecen_yil_fiyat: str | None   # geçen yıl adet ağırlıklı TL satış fiyatı
    mevcut_marj: str | None
    hedef_fiyat: str | None       # maliyet x (1 + marj)
    gereken_zam: str | None       # hedef / geçen - 1
    liste_fiyati_yurtici: str | None    # hedef / yurtiçi bölen, adıma yuvarlanmış; Berrak değilse null
    liste_fiyati_yurtdisi: str | None   # hedef / yurtdışı bölen, adıma yuvarlanmış; Berrak değilse null
    yillik_ek_gelir: str | None   # (hedef - geçen) x adet; negatif olabilir
    bolge: KarlilikBolgesi | None
    hata: str | None
    maliyet_kaynagi: Literal["bu_yil", "ortalama"] | None = None   # ortalama: `satis_ortalama_maliyetten` = 1 ve stokta kalan var


class HedefFiyatCikis(BaseModel):
    marj: str
    bolen_yurtici: str
    bolen_yurtdisi: str
    yuvarlama: str   # liste fiyatı yuvarlama adımı, TL
    adet_kaynagi: str   # yıllık adedin kaynağı: "satis_gecmisi" (geçen yıl satış adedi)
    ozet: HedefFiyatOzeti
    kayitlar: list[HedefFiyatSatiri]


# ---------------------------------------------------------------- Stokta kalan
class StokDevriGiris(BaseModel):
    """PUT /urunler/{kod}/stok-devri gövdesi. Sayılar metin ya da sayı; oranlar 0,40 = %40."""
    adet: Decimal
    birim_maliyet: Decimal | None = None   # adet > 0 iken zorunlu (> 0)
    enflasyon: Decimal | None = None
    uretim_adedi: Decimal | None = None
    neden: str = Field(min_length=1, max_length=300)


class StokDevriSatiri(StokDevriCikis):
    ad: str


class StokDevriListesi(BaseModel):
    kayitlar: list[StokDevriSatiri]


class StokDevriAktarimSatiri(BaseModel):
    satir_no: int                 # Excel satır numarası (başlık 1)
    urun_kodu: str
    ad: str | None
    adet: str | None
    birim_maliyet: str | None
    enflasyon: str | None
    uretim_adedi: str | None
    durum: Literal["yeni", "degisen", "ayni"]
    eski: dict[str, str | None] | None = None   # degisen satırda mevcut değerler


class StokDevriAktarimHatasi(BaseModel):
    satir_no: int
    mesaj: str


class StokDevriOnizle(BaseModel):
    sutunlar: dict[str, str | None]   # beklenen sütun -> dosyada bulunan başlık (yoksa null)
    satirlar: list[StokDevriAktarimSatiri]
    hatalar: list[StokDevriAktarimHatasi]
    yeni: int
    degisen: int
    ayni: int


class StokDevriUygula(BaseModel):
    eklenen: int
    guncellenen: int
    ayni: int


# ---------------------------------------------------------------- Fiyat eğilimi (analiz önerisi 9)
class FiyatEgilimiSatiri(BaseModel):
    """Yüzdeler 2 basamak (ROUND_HALF_UP); degisim/yillik null: ilk fiyat 0 ya da ilk/son kaydın para birimi farklı."""
    kod: str
    ad: str
    tip: str | None
    para_birimi: str
    ilk_fiyat: str
    ilk_tarih: str
    son_fiyat: str
    son_tarih: str
    kayit_sayisi: int
    degisim_yuzde: str | None
    yillik_yuzde: str | None
    esik_yuzde: str                 # TL: enflasyon parametresi x 100; döviz: 0
    enflasyonu_asiyor: bool         # yillik_yuzde > esik_yuzde + 1 puan
    kullanan_urun_sayisi: int       # aktif reçetesinde geçtiği senaryo üyesi ürün sayısı


class FiyatEgilimiCikis(BaseModel):
    senaryo_id: int
    ay: int
    tarih: str                      # pencere sonu (ISO)
    pencere_basi: str               # tarih - ay ay (ISO)
    enflasyon_yuzde: str | None     # senaryonun enflasyon parametresi (%); girilmemişse null
    satirlar: list[FiyatEgilimiSatiri]
    asan_sayisi: int                # süzgeçten bağımsız: enflasyonu aşan malzeme sayısı
    toplam: int                     # satır sayısı (yalniz_asan=1 ile aşanlar)


# ---------------------------------------------------------------- Yönetim özeti (analiz önerisi 15)
class YonetimBaslik(BaseModel):
    senaryo_id: int
    sezon_ad: str
    ad: str
    tur: str
    kilitli: bool
    hesap_tarihi: str
    uretim_zamani: str              # yanıtın üretildiği an (UTC ISO)


class YonetimUrunSayilari(BaseModel):
    toplam: int
    hesaplanan: int
    hatali: int


class YonetimMarj(BaseModel):
    """Oranlar 0,20 = %20. agirlikli_ortalama: geçen yıl satış adediyle ağırlıklı (adedi bilinen ürün yoksa null)."""
    ortalama: str | None
    agirlikli_ortalama: str | None
    adetli_urun: int
    hedef: str | None               # genel `satis_kar` parametresi
    marj_esigi: str
    adet_kaynagi: str


class YonetimMaliyetKalemi(BaseModel):
    toplam_tl: str
    pay_yuzde: str | None
    urun_basina_tl: str | None


class YonetimMaliyetYapisi(BaseModel):
    """Hesaplanan ürünlerin birim maliyet toplamı ve kalem payları (malzeme / uretim / faaliyet / finansman; toplamı %100)."""
    urun_sayisi: int
    toplam_tl: str
    urun_basina_tl: str | None
    kalemler: dict[str, YonetimMaliyetKalemi]


class YonetimHedefAltiSatiri(BaseModel):
    kod: str
    ad: str
    kar_orani: str
    maliyet: str | None
    satis: str | None


class YonetimHedefAlti(BaseModel):
    esik: str
    toplam: int
    kayitlar: list[YonetimHedefAltiSatiri]   # ilk 10, kâr oranı artan


class YonetimKurRiskiSatiri(BaseModel):
    kod: str
    ad: str
    maliyet: str | None
    birim_etki: str | None
    yillik_etki: str | None
    doviz_payi_yuzde: str | None


class YonetimKurRiski(BaseModel):
    oran: str
    kurlar: dict[str, str]
    doviz_payi_yuzde: str | None
    yillik_etki_tl: str
    yillik_maliyet_tl: str
    adetsiz_urun: int
    hatali: int
    en_riskli: list[YonetimKurRiskiSatiri]   # ilk 5 (yıllık etki azalan)


class YonetimAcikTeklif(BaseModel):
    teklif_id: int
    urun_kodu: str
    urun_ad: str
    musteri: str | None
    durum: str
    tur_no: int
    tarih: str | None               # teklifin oluşturulma zamanı (UTC ISO)
    hesap_tarihi: str
    fiyat_tl: str


class YonetimTeklifler(BaseModel):
    toplam: int
    durumlar: dict[str, int]        # taslak / gonderildi / kabul / red
    acik_sayi: int                  # taslak + gonderildi
    acik_toplam_tl: str
    en_eski_acik: list[YonetimAcikTeklif]


class YonetimKontrolSorunu(BaseModel):
    kod: str
    baslik: str
    durum: str
    sayi: int


class YonetimVeriKontrolu(BaseModel):
    hata: int
    dikkat: int
    bilgi: int
    tamam: int
    sorunlar: list[YonetimKontrolSorunu]   # durumu hata/dikkat olan kontroller


class YonetimPahaliSatiri(BaseModel):
    kod: str
    ad: str
    maliyet: str
    satis: str


class YonetimStokEtkisi(BaseModel):
    """Stok devri kaydı olan çalışmada; toplam_etki_tl = Σ stok adedi x (güncel stok maliyeti - bu yılın maliyeti)."""
    kayit_sayisi: int
    etkili_urun: int
    stok_adedi: str
    toplam_etki_tl: str
    satis_ortalama_maliyetten: bool


class YonetimUyari(BaseModel):
    kod: str
    ad: str
    mesaj: str


class YonetimOzetiCikis(BaseModel):
    baslik: YonetimBaslik
    urunler: YonetimUrunSayilari
    marj: YonetimMarj
    maliyet_yapisi: YonetimMaliyetYapisi
    hedef_alti: YonetimHedefAlti
    kur_riski: YonetimKurRiski
    teklifler: YonetimTeklifler
    veri_kontrolu: YonetimVeriKontrolu
    en_pahali: list[YonetimPahaliSatiri]
    stok_etkisi: YonetimStokEtkisi | None = None   # stok devri kaydı yoksa null (arayüz kartı gizler)
    uyarilar: list[YonetimUyari]                   # hesaplanamayan ürünler, ilk 10


# ---------------------------------------------------------------- Maliyet muhasebesi raporları (bütçe kıyası, aylar arası, maliyet kartı)
class SmmFiiliDokum(BaseModel):
    """Aşama hesabının ürün satırı (birim başına TL). Üst aşamada `malzeme`, alt aşamadan gelen yarı mamulün tam maliyetini içerir."""
    malzeme: str
    iscilik: str
    gug: str
    fire: str
    stok_payi: str


class SmmButceDokum(BaseModel):
    """Fiyat Çalışması hesabından (birim başına TL). malzeme / iscilik / gug firesiz değerler; fire = fireli − firesiz üretim maliyeti
    (firesiz blok yoksa null ve kalemler fire dahil). uretim_gideri = işçilik + GÜG (fire dahil). Son ikisi bütçe üretim maliyetine girmez."""
    malzeme: str
    iscilik: str
    gug: str
    fire: str | None
    uretim_gideri: str
    pazarlama_yonetim: str
    finansman: str


class SmmButceKiyasSatiri(BaseModel):
    kod: str
    ad: str | None
    asama: int
    birim: str | None
    uretim_miktar: str
    uretildi: bool
    butce_maliyet_tl: str | None              # finansman, pazarlama ve yönetim HARİÇ üretim maliyeti; bütçe hesaplanamadıysa null
    butce_finansman_dahil_tl: str | None      # bilgi için: satış fiyatına esas maliyet
    fiili_birim_maliyet_tl: str
    fark_tl: str | None                       # fiili − bütçe; üretim yoksa ya da bütçe yoksa null
    fark_yuzde: str | None                    # oran (0.05 = %5)
    fiili_dokum: SmmFiiliDokum
    butce_dokum: SmmButceDokum | None
    alim_kurali: bool
    butce_hatasi: str | None
    eslesme: Literal["kod"]


class SmmYalnizButce(BaseModel):
    kod: str
    ad: str | None
    butce_maliyet_tl: str | None
    stok_kartinda: bool                       # dönemde stok kartı var ama aşama reçetesi yok
    eslesme: Literal["yok"]


class SmmYalnizFiili(BaseModel):
    kod: str
    ad: str | None
    asama: int
    uretim_miktar: str
    fiili_birim_maliyet_tl: str
    eslesme: Literal["yok"]


class SmmButceKiyasOzeti(BaseModel):
    eslesen: int
    karsilastirilan: int                      # farkı hesaplanabilen (üretilmiş ve bütçesi olan)
    uretimsiz: int
    yalniz_butce: int
    yalniz_fiili: int
    ortalama_fark_yuzde: str | None           # karşılaştırılanların basit ortalaması (oran)
    fiili_yuksek: int


class SmmSenaryoOzeti(BaseModel):
    id: int
    ad: str


class SmmButceKiyas(BaseModel):
    donem: SmmDonemCikis
    senaryo: SmmSenaryoOzeti
    ozet: SmmButceKiyasOzeti
    kayitlar: list[SmmButceKiyasSatiri]
    yalniz_butce: list[SmmYalnizButce]
    yalniz_fiili: list[SmmYalnizFiili]


class SmmKarsilastirmaHucresi(BaseModel):
    donem_id: int
    tutar: str
    degisim_tl: str | None                    # bir önceki (soldaki) döneme göre; ilk dönemde null
    degisim_yuzde: str | None                 # oran; önceki tutar 0 ise null


class SmmKarsilastirmaSatiri(BaseModel):
    anahtar: str
    ad: str
    vurgulu: bool
    hucreler: list[SmmKarsilastirmaHucresi]
    son_fark_tl: str | None                   # son iki dönemin farkı; tek dönemde null
    son_fark_yuzde: str | None


class SmmKarsilastirma(BaseModel):
    donemler: list[SmmDonemCikis]             # en eski başta
    satirlar: list[SmmKarsilastirmaSatiri]


class SmmKartAsamasi(BaseModel):
    asama: int
    ad: str
    kod: str
    urun_ad: str | None
    birim: str | None
    ust_kod: str | None                       # bu yarı mamulü kullanan üst ürün; ürünün kendi satırında null
    carpan: str | None                        # üst ürünün bir birimi için reçetedeki kullanım
    malzeme: str
    iscilik: str
    gug: str
    fire: str
    stok_payi: str
    birim_maliyet: str
    uretim_miktar: str
    alim_kurali: bool
    elle_alanlar: list[str] = []


class SmmKartOnceki(BaseModel):
    donem: SmmDonemCikis
    asama: int
    birim_maliyet: str
    uretim_miktar: str
    fark_tl: str
    fark_yuzde: str | None


class SmmMaliyetKarti(BaseModel):
    donem: SmmDonemCikis
    kod: str
    ad: str | None
    birim: str | None
    asama: int
    birim_maliyet: str
    uretim_miktar: str
    toplam: str
    alim_kurali: bool
    alim_fiyati: str
    asamalar: list[SmmKartAsamasi]            # ürünün kendi aşaması başta, sonra reçetesindeki alt aşama ürünleri
    satirlar: list[SmmReceteKalemi]
    onceki: SmmKartOnceki | None


class DuzenlemeKilidiAcGiris(BaseModel):
    """Arayüzdeki düzenleme kilidinin açılması: hangi çalışmada, hangi sayfada."""
    senaryo_id: int | None = None
    sayfa: str = Field(min_length=1, max_length=200)


class DuzenlemeKilidiAcCikis(BaseModel):
    kayit_id: int
    sayfa: str
    senaryo_id: int | None
    kullanici: str


# ---------------------------------------------------------------- Önemli malzemeler (80/20) — 13.11.2026
class OnemliMalzemeSatiri(BaseModel):
    """Tutar ve miktarlar ondalık metin. pay_yuzde / kumulatif_yuzde yüzde metni, 2 basamak ("12.34" = %12,34)."""
    sira: int                       # yıllık tutara göre sıra (1 = en büyük)
    kod: str
    ad: str
    tip: str | None
    para_birimi: str | None         # malzeme kartının para birimi
    birim: str | None
    yillik_miktar: str              # Σ (yıllık adet x brüt miktar)
    yillik_tutar_tl: str            # Σ (yıllık adet x üründeki fireli TL tutarı)
    pay_yuzde: str                  # yıllık tutarın toplam içindeki payı (%)
    kumulatif_yuzde: str            # koşan toplam (%)
    esik_icinde: bool               # kümülatifi eşiği geçmeyenler + eşiği aşan ilk satır
    kullanan_urun_sayisi: int       # hesaba giren (yıllık adedi olan) ürünlerden kaçında geçtiği
    birim_fiyat: str | None         # malzeme kartının geçerli fiyatı (kendi para biriminde); kart yoksa null


class OnemliMalzemelerCikis(BaseModel):
    senaryo_id: int
    esik: str                       # 0.8 = %80
    tarih: str                      # hesap tarihi (ISO)
    adet_kaynagi: str               # "satis_gecmisi": yıllık adet = geçen yıl satış adedi
    toplam_tutar_tl: str            # hesaba giren ürünlerin yıllık malzeme tutarı
    adetsiz_urun: int               # yıllık adedi olmadığı için hesaba girmeyen ürün sayısı
    hatali_urun: int                # hesaplanamadığı için hesaba girmeyen ürün sayısı
    satirlar: list[OnemliMalzemeSatiri]
    esik_icindeki_sayi: int


# ---------------------------------------------------------------- Onay çıktısı (yeminli mali müşavir için) — 16.11.2026
class OnayCiktisiEkleri(BaseModel):
    """Çıktıya eklenecek bölümler; hepsi varsayılan açık. `mutabakat` yalnız SMM çıktısında kullanılır."""
    kapak: bool = True
    mutabakat: bool = True
    elle_degisiklikler: bool = True
    gunluk_ozeti: bool = True


class OnayCiktisiImzalari(BaseModel):
    """İmza tablosundaki adlar (isteğe bağlı); boşsa çizgi boş kalır."""
    hazirlayan: str | None = Field(None, max_length=120)
    kontrol_eden: str | None = Field(None, max_length=120)
    onaylayan: str | None = Field(None, max_length=120)


class OnayCiktisiFiyatGiris(BaseModel):
    """Fiyat Çalışması onay çıktısı. urunler: yalnız bu ürün kodları (yoksa çalışmanın tüm ürünleri)."""
    senaryo_id: int
    urunler: list[str] | None = Field(None, min_length=1, max_length=2000)
    tur: Literal["excel", "pdf"]
    ekler: OnayCiktisiEkleri = Field(default_factory=OnayCiktisiEkleri)
    imzalar: OnayCiktisiImzalari = Field(default_factory=OnayCiktisiImzalari)


class OnayCiktisiSmmGiris(BaseModel):
    """Maliyet muhasebesi (SMM) onay çıktısı: bir dönem."""
    donem_id: int
    tur: Literal["excel", "pdf"]
    ekler: OnayCiktisiEkleri = Field(default_factory=OnayCiktisiEkleri)
    imzalar: OnayCiktisiImzalari = Field(default_factory=OnayCiktisiImzalari)
