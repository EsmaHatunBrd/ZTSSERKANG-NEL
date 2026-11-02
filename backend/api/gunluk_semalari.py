"""Değişiklik Günlüğü ve Arşiv yanıt/istek şemaları (semalar.py'den ayrı: eşzamanlı çalışmada çakışmayı önler)."""
from typing import Any, Literal
from pydantic import BaseModel, Field

GunlukTuru = Literal["parametre", "fiyat", "fire", "metin", "recete", "hesap", "teklif", "urun", "hedef", "havuz", "ambalaj", "kapasite", "satis", "diger"]


class GeriAlIstegi(BaseModel):
    """Geri alma = mevcut ucun (yol) yeni kayıt olarak çağrılması; istemci `govde`yi aynen POST eder."""
    yol: str
    govde: dict[str, Any]


class GunlukSatiri(BaseModel):
    id: str                       # "<kaynak>:<pk>", ör. "parametre:12"
    zaman: str | None
    kullanici: str
    tur: GunlukTuru
    baslik: str
    urun_kodu: str | None = None
    senaryo_id: int | None = None
    eski: str | None = None
    yeni: str | None = None
    neden: str | None = None
    geri_alinabilir: bool
    geri_al: GeriAlIstegi | None = None


class GunlukListesi(BaseModel):
    kayitlar: list[GunlukSatiri]
    toplam: int
    sayfa: int
    boyut: int


class KullaniciAdedi(BaseModel):
    kullanici: str
    adet: int


class TurAdedi(BaseModel):
    tur: GunlukTuru
    adet: int


class GunlukOzeti(BaseModel):
    gun: int
    toplam: int
    kullanici_bazinda: list[KullaniciAdedi]
    tur_bazinda: list[TurAdedi]


class ReceteEtkinlestirGiris(BaseModel):
    neden: str = Field(min_length=1)


class ReceteEtkinlestirCikis(BaseModel):
    id: int
    versiyon: int
    aktif: bool


class KilitGiris(BaseModel):
    neden: str = Field(min_length=1)


class ArsivSenaryo(BaseModel):
    id: int
    tur: Literal["fiyat_calismasi", "gerceklesen"]
    ad: str
    aciklama: str | None
    olusturma_zamani: str | None
    olusturan: str
    kilitli: bool
    kaynak_dosya: str | None
    urun_sayisi: int
    hesap_sayisi: int
    teklif_sayisi: int


class ArsivSezon(BaseModel):
    id: int
    ad: str
    baslangic: str
    bitis: str
    senaryolar: list[ArsivSenaryo]


class ArsivAgaci(BaseModel):
    sezonlar: list[ArsivSezon]


class ArsivKaydi(BaseModel):
    id: int
    urun_kodu: str
    urun_ad: str
    hesap_tarihi: str
    olusturma_zamani: str | None
    olusturan: str
    neden: str | None
    maliyet_tl: str | None
    satis_tl: str | None
    teklif_sayisi: int


class ArsivKayitListesi(BaseModel):
    kayitlar: list[ArsivKaydi]
    toplam: int
    sayfa: int
    boyut: int


class KiyasHesap(BaseModel):
    id: int
    urun_kodu: str
    urun_ad: str
    senaryo_id: int
    hesap_tarihi: str
    olusturma_zamani: str | None
    olusturan: str


class KiyasAlani(BaseModel):
    alan: str
    etiket: str
    a: str | None
    b: str | None
    fark: str | None


class KiyasSatiri(BaseModel):
    malzeme_kodu: str
    ad: str | None
    a_tutar: str | None
    b_tutar: str | None
    fark: str
    durum: Literal["ortak", "sadece_a", "sadece_b"]


class ArsivKiyasi(BaseModel):
    a: KiyasHesap
    b: KiyasHesap
    uyari: str | None
    toplamlar: list[KiyasAlani]
    fiyatlar: list[KiyasAlani]
    satirlar: list[KiyasSatiri]
