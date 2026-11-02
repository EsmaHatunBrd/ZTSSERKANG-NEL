import os
import tempfile
import zipfile
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, Depends, File, Form, UploadFile
from openpyxl.utils.exceptions import InvalidFileException
from ..servisler import hesap_servisi as hs, import_servisi as imp
from ..servisler.donusum import decimal_str
from ..servisler.hatalar import DogrulamaHatasi
from .bagimliliklar import OturumDep, kullanici_ver

from .semalar import FiyatListesiOnizleme, FiyatListesiUygulama, HATA_404_409_422, HATA_404_422, ImportOzeti

router = APIRouter(tags=["import"])

MAKS_DOSYA_BAYT = 25 * 1024 * 1024
PARCA_BAYT = 1024 * 1024


@contextmanager
def _gecici(dosya: UploadFile):
    """Yüklenen dosyayı parça parça geçici .xlsx'e yazar (25 MB sınırı); bozuk/yanlış biçim 422; dosya her durumda silinir."""
    f = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    try:
        with f:
            toplam = 0
            while parca := dosya.file.read(PARCA_BAYT):
                toplam += len(parca)
                if toplam > MAKS_DOSYA_BAYT:
                    raise DogrulamaHatasi("dosya 25 MB'den büyük")
                f.write(parca)
        try:
            yield Path(f.name)
        except (zipfile.BadZipFile, InvalidFileException):
            raise DogrulamaHatasi("dosya geçerli bir .xlsx değil")
    finally:
        os.unlink(f.name)


@router.post("/import/excel-tam", response_model=ImportOzeti, responses=HATA_404_409_422)
def excel_tam(s: OturumDep, dosya: UploadFile = File(...), sezon_ad: str | None = Form(None), senaryo_ad: str | None = Form(None),
              tur: Literal["fiyat_calismasi", "gerceklesen"] = Form("fiyat_calismasi"), kartlari_guncelle: bool = Form(True),
              senaryo_id: int | None = Form(None), k: str = Depends(kullanici_ver)):
    """senaryo_id verilirse 'mevcut senaryoyu tamamla' modu: sezon_ad/senaryo_ad/tur yok sayılır, yeni Sezon/Senaryo açılmaz."""
    if senaryo_id is None and not ((sezon_ad or "").strip() and (senaryo_ad or "").strip()):
        raise DogrulamaHatasi("sezon_ad ve senaryo_ad zorunlu (veya senaryo_id verin)")
    if senaryo_id is not None:   # tamamla modu mevcut senaryoya yazar: kilitliyse 409
        hs.kilit_denetle(hs.senaryo_getir(s, senaryo_id))
    with _gecici(dosya) as yol:
        return decimal_str(imp.excel_tam_yukle(s, yol, sezon_ad or "", senaryo_ad or "", tur, k, kartlari_guncelle, senaryo_id,
                                               kaynak_dosya=hs.dosya_adi_temizle(dosya.filename)))


@router.post("/import/fiyat-listesi", response_model=FiyatListesiOnizleme, responses=HATA_404_422)
def fiyat_onizle(s: OturumDep, dosya: UploadFile = File(...), senaryo: int = Form(...), gecerlilik_basi: date | None = Form(None)):
    sen = hs.senaryo_getir(s, senaryo)
    with _gecici(dosya) as yol:
        return decimal_str({k: v for k, v in imp.fiyat_listesi_onizle(s, sen.id, yol, gecerlilik_basi).items() if not k.startswith("_")})


@router.post("/import/fiyat-listesi/uygula", response_model=FiyatListesiUygulama, responses=HATA_404_409_422)
def fiyat_uygula(s: OturumDep, dosya: UploadFile = File(...), senaryo: int = Form(...), gecerlilik_basi: date = Form(...), neden: str = Form(...),
                 k: str = Depends(kullanici_ver)):
    sen = hs.senaryo_getir(s, senaryo)
    hs.kilit_denetle(sen)
    with _gecici(dosya) as yol:
        return imp.fiyat_listesi_uygula(s, sen.id, yol, gecerlilik_basi, neden, k)
