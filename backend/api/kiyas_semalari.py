"""Faz 6 Bütçe vs Gerçekleşen yanıt şemaları (semalar.py'den ayrı). Tutarlar ondalık metin; fark_yuzde yüzde (5 = %5)."""
from typing import Literal
from pydantic import BaseModel

BgKiyasDurumu = Literal["iki", "yalniz_a", "yalniz_b", "hata"]


class BgKiyasSenaryo(BaseModel):
    id: int
    ad: str
    tur: str
    sezon: str


class BgKiyasDegeri(BaseModel):
    a: str | None
    b: str | None
    fark: str | None
    fark_yuzde: str | None


class BgKiyasAlanlari(BaseModel):
    recete_maliyeti: BgKiyasDegeri
    gug: BgKiyasDegeri
    faaliyet: BgKiyasDegeri
    finans: BgKiyasDegeri
    maliyet_tl: BgKiyasDegeri
    maliyet_usd: BgKiyasDegeri
    satis_tl: BgKiyasDegeri
    satis_usd: BgKiyasDegeri


class BgKiyasSatiri(BaseModel):
    kod: str
    ad: str
    hat: str
    ambalaj_hacmi: str
    gecici_kod: bool
    durum: BgKiyasDurumu
    hata: str | None
    alanlar: BgKiyasAlanlari | None
    sapma_yuzde: str | None   # maliyet TL fark %
    sapan: bool


class BgKiyasOzeti(BaseModel):
    karsilastirilan: int
    sapan: int
    yalniz_a: int
    yalniz_b: int
    hatali: int
    ortalama_sapma_yuzde: str | None


class BgKiyasListesi(BaseModel):
    a: BgKiyasSenaryo
    b: BgKiyasSenaryo
    esik: str
    tarih: str
    satirlar: list[BgKiyasSatiri]
    ozet: BgKiyasOzeti


class BgKiyasReceteDegerleri(BaseModel):
    miktar: str
    fire: str
    brut_miktar: str
    birim_fiyat: str
    tutar: str


class BgKiyasReceteSatiri(BaseModel):
    kod: str
    kalem: str
    durum: Literal["iki", "yalniz_a", "yalniz_b"]
    a: BgKiyasReceteDegerleri | None
    b: BgKiyasReceteDegerleri | None
    fark_tutar: str
    degisen: list[str]


class BgKiyasGiderSatiri(BgKiyasDegeri):
    kod: str
    kalem: str
    grup: str


class BgKiyasUretimSatiri(BaseModel):
    alan: str
    etiket: str
    a: str
    b: str
    degisti: bool


class BgKiyasParametreSatiri(BaseModel):
    anahtar: str
    a: str | None
    b: str | None
    degisti: bool


class BgKiyasAyristirma(BaseModel):
    kaynak: Literal["fiyat", "recete", "uretim", "gider", "kur", "enflasyon", "diger"]
    etiket: str
    fark: str


class BgKiyasUrunCikis(BaseModel):
    kod: str
    ad: str
    a: BgKiyasSenaryo
    b: BgKiyasSenaryo
    tarih: str
    alanlar: BgKiyasAlanlari
    recete: list[BgKiyasReceteSatiri]
    giderler: list[BgKiyasGiderSatiri]
    uretim: list[BgKiyasUretimSatiri]
    parametreler: list[BgKiyasParametreSatiri]
    ayristirma: list[BgKiyasAyristirma]
    toplam_fark: str | None


class BgKarsiSenaryoCikis(BaseModel):
    """Seçili senaryonun aynı sezondaki karşılığı (fiyat çalışması <-> gerçekleşen); yoksa null."""
    karsi: BgKiyasSenaryo | None
