"""Veri Aktar: üretim adetleri, satın alma BF ve gider dağıtımı ayrı ayrı önizle/uygula. Dosya tam kitap ya da tek sayfalık xlsx olabilir.
Her yazan uçta `onay` (satır kaybı onayı) ve son yüklemeyi geri alma uçları (`.../son-yukleme`, `.../son-yuklemeyi-geri-al`) vardır."""
from datetime import date
from fastapi import APIRouter, Depends, File, Form, UploadFile
from ..servisler import aktarim_servisi as ak, hesap_servisi as hs, recete_aktarim_servisi as ra
from ..servisler.donusum import decimal_str
from .bagimliliklar import OturumDep, kullanici_ver
from .import_ import _gecici, geri_al_uclari
from .semalar import (AktarimOnizleGider, AktarimOnizleRecete, AktarimOnizleSatinAlma, AktarimOnizleUretim, AktarimUygulaGider,
                      AktarimUygulaRecete, AktarimUygulaSatinAlma, AktarimUygulaUretim, HATA_404_409_422, HATA_404_422)

router = APIRouter(prefix="/aktarim", tags=["aktarim"])
ONAY = Form(False, description="Satır kaybı onayı: dosya mevcut kayıtların yarısından azını içeriyorsa 409 sonrası true ile yeniden gönderin")


def _kaynak_yaz(sen, dosya: UploadFile) -> None:
    """Arşivde görünsün diye senaryonun son kaynak dosya adı (yalnız ad, yol değil)."""
    sen.kaynak_dosya = hs.dosya_adi_temizle(dosya.filename)


def _temiz(d: dict) -> dict:
    return decimal_str({k: v for k, v in d.items() if not k.startswith("_")})


@router.post("/uretim-adetleri/onizle", response_model=AktarimOnizleUretim, responses=HATA_404_422)
def uretim_onizle(s: OturumDep, dosya: UploadFile = File(...), senaryo: int = Form(...)):
    sen = hs.senaryo_getir(s, senaryo)
    with _gecici(dosya) as yol:
        return _temiz(ak.uretim_onizle(s, sen.id, yol))


@router.post("/uretim-adetleri/uygula", response_model=AktarimUygulaUretim, responses=HATA_404_409_422)
def uretim_uygula(s: OturumDep, dosya: UploadFile = File(...), senaryo: int = Form(...), neden: str = Form(...), onay: bool = ONAY,
                  kul: str = Depends(kullanici_ver)):
    sen = hs.senaryo_getir(s, senaryo)
    hs.kilit_denetle(sen)
    with _gecici(dosya) as yol:
        sonuc = ak.uretim_uygula(s, sen.id, yol, neden, kul, onay, hs.dosya_adi_temizle(dosya.filename))
    _kaynak_yaz(sen, dosya)
    return sonuc


@router.post("/satin-alma/onizle", response_model=AktarimOnizleSatinAlma, responses=HATA_404_422)
def satin_alma_onizle(s: OturumDep, dosya: UploadFile = File(...), senaryo: int = Form(...), gecerlilik_basi: date | None = Form(None)):
    sen = hs.senaryo_getir(s, senaryo)
    with _gecici(dosya) as yol:
        return _temiz(ak.satin_alma_onizle(s, sen.id, yol, gecerlilik_basi))


@router.post("/satin-alma/uygula", response_model=AktarimUygulaSatinAlma, responses=HATA_404_409_422)
def satin_alma_uygula(s: OturumDep, dosya: UploadFile = File(...), senaryo: int = Form(...), gecerlilik_basi: date = Form(...),
                      neden: str = Form(...), kartlari_guncelle: bool = Form(False), onay: bool = ONAY, kul: str = Depends(kullanici_ver)):
    sen = hs.senaryo_getir(s, senaryo)
    hs.kilit_denetle(sen)
    with _gecici(dosya) as yol:
        sonuc = ak.satin_alma_uygula(s, sen.id, yol, gecerlilik_basi, neden, kartlari_guncelle, kul, onay, hs.dosya_adi_temizle(dosya.filename))
    _kaynak_yaz(sen, dosya)
    return sonuc


@router.post("/gider-dagitim/onizle", response_model=AktarimOnizleGider, responses=HATA_404_422)
def gider_onizle(s: OturumDep, dosya: UploadFile = File(...), senaryo: int = Form(...)):
    sen = hs.senaryo_getir(s, senaryo)
    with _gecici(dosya) as yol:
        return _temiz(ak.gider_onizle(s, sen.id, yol))


@router.post("/gider-dagitim/uygula", response_model=AktarimUygulaGider, responses=HATA_404_409_422)
def gider_uygula(s: OturumDep, dosya: UploadFile = File(...), senaryo: int = Form(...), neden: str = Form(...), onay: bool = ONAY,
                 kul: str = Depends(kullanici_ver)):
    sen = hs.senaryo_getir(s, senaryo)
    hs.kilit_denetle(sen)
    with _gecici(dosya) as yol:
        sonuc = ak.gider_uygula(s, sen.id, yol, neden, kul, onay, hs.dosya_adi_temizle(dosya.filename))
    _kaynak_yaz(sen, dosya)
    return sonuc


@router.post("/recete/onizle", response_model=AktarimOnizleRecete, responses=HATA_404_422)
def recete_onizle(s: OturumDep, dosya: UploadFile = File(...), senaryo: int = Form(...)):
    """Excel ürün sayfası düzenindeki dosyadan reçeteler: seçili çalışmanın aktif reçetesiyle fark. Hiçbir şey yazılmaz."""
    sen = hs.senaryo_getir(s, senaryo)
    with _gecici(dosya) as yol:
        return _temiz(ra.recete_onizle(s, sen.id, yol))


@router.post("/recete/uygula", response_model=AktarimUygulaRecete, responses=HATA_404_409_422)
def recete_uygula(s: OturumDep, dosya: UploadFile = File(...), senaryo: int = Form(...), neden: str = Form(...),
                  sayfalar: list[str] = Form(...), onay: bool = ONAY, kul: str = Depends(kullanici_ver)):
    """Seçilen sayfalar için yeni reçete versiyonu (eski versiyon geçmişte kalır). Kilitli çalışmaya yazılmaz."""
    sen = hs.senaryo_getir(s, senaryo)
    hs.kilit_denetle(sen)
    with _gecici(dosya) as yol:
        sonuc = ra.recete_uygula(s, sen.id, yol, sayfalar, neden, kul, onay, hs.dosya_adi_temizle(dosya.filename))
    _kaynak_yaz(sen, dosya)
    return sonuc


for _onek, _alan, _etiket in (("/uretim-adetleri", "uretim_adetleri", "Üretim adetleri"), ("/satin-alma", "satin_alma", "Satın alma fiyat listesi"),
                              ("/gider-dagitim", "gider_dagitim", "Gider dağıtım"), ("/recete", "recete", "Ürün reçetesi")):
    geri_al_uclari(router, _onek, _alan, etiket=_etiket)
