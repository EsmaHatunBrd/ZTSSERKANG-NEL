import os
import tempfile
import zipfile
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from openpyxl.utils.exceptions import InvalidFileException
from ..servisler import hesap_servisi as hs, import_servisi as imp, musavir_excel_servisi as mx, yukleme_guvenligi as yg
from ..servisler.donusum import decimal_str
from ..servisler.hatalar import DogrulamaHatasi
from .bagimliliklar import OturumDep, kullanici_ver

from .semalar import (FiyatKitabiSablonKaydi, FiyatKitabiSablonOnizleme, FiyatListesiOnizleme, FiyatListesiUygulama, GeriAlSonucu,
                      HATA_404_409_422, HATA_404_422, ImportOzeti, SonYuklemeYaniti)

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
                    raise DogrulamaHatasi("Dosya 25 MB'den büyük.")
                f.write(parca)
        try:
            yield Path(f.name)
        except (zipfile.BadZipFile, InvalidFileException):
            raise DogrulamaHatasi(imp.DESTEKLENMEYEN_DOSYA, kod="desteklenmeyen_dosya")
    finally:
        os.unlink(f.name)


@router.post("/import/excel-tam", response_model=ImportOzeti, responses=HATA_404_409_422)
def excel_tam(s: OturumDep, dosya: UploadFile = File(...), sezon_ad: str | None = Form(None), senaryo_ad: str | None = Form(None),
              tur: Literal["fiyat_calismasi", "gerceklesen"] = Form("fiyat_calismasi"), kartlari_guncelle: bool = Form(True),
              senaryo_id: int | None = Form(None), k: str = Depends(kullanici_ver)):
    """senaryo_id verilirse 'mevcut senaryoyu tamamla' modu: sezon_ad/senaryo_ad/tur yok sayılır, yeni Sezon/Senaryo açılmaz."""
    if senaryo_id is None and not ((sezon_ad or "").strip() and (senaryo_ad or "").strip()):
        raise DogrulamaHatasi("Sezon ve çalışma adını girin ya da var olan bir çalışmayı seçin.")
    if senaryo_id is not None:   # tamamla modu mevcut senaryoya yazar: kilitliyse 409
        hs.kilit_denetle(hs.senaryo_getir(s, senaryo_id))
    with _gecici(dosya) as yol:
        ozet = imp.excel_tam_yukle(s, yol, sezon_ad or "", senaryo_ad or "", tur, k, kartlari_guncelle, senaryo_id,
                                   kaynak_dosya=hs.dosya_adi_temizle(dosya.filename))
        # Müşavir Excel'i için kitabın kendisi şablon olarak saklanır (aktarım başarıyla yazıldıktan sonra; aynı işlemde).
        mx.sablon_sakla(s, ozet["senaryo_id"], hs.dosya_adi_temizle(dosya.filename), yol.read_bytes(), k)
        ozet["musavir_sablonu_saklandi"] = True
        return decimal_str(ozet)


@router.post("/import/excel-tam/musavir-sablonu/onizle", response_model=FiyatKitabiSablonOnizleme, responses=HATA_404_422,
             summary="Müşavir şablonu: yalnız saklamadan önce kitap mı denetle")
def musavir_sablonu_onizle(s: OturumDep, dosya: UploadFile = File(...), senaryo: int = Form(...)):
    """Aktarım yapılmaz. Dosya Fiyat Çalışması kitabı değilse 422 (eksik_sayfa / yanlis_sablon / desteklenmeyen_dosya)."""
    sen = hs.senaryo_getir(s, senaryo)
    with _gecici(dosya) as yol:
        on = mx.sablon_onizle(yol)
    return {"dosya_adi": hs.dosya_adi_temizle(dosya.filename) or "fiyat-calismasi.xlsx", **on, "mevcut": mx.sablon_ozeti(s, sen.id)}


@router.post("/import/excel-tam/musavir-sablonu", response_model=FiyatKitabiSablonKaydi, responses=HATA_404_422,
             summary="Müşavir şablonu olarak yalnız sakla (aktarım yapmadan)")
def musavir_sablonu_sakla(s: OturumDep, dosya: UploadFile = File(...), senaryo: int = Form(...), k: str = Depends(kullanici_ver)):
    """Kitabı zaten yüklemiş kullanıcılar için: dosya yalnız şablon olarak saklanır (senaryo verisine dokunulmaz; kilitli çalışmada da
    olur). Önce önizlemeyle aynı denetim yapılır. Çalışma başına yalnız son şablon tutulur."""
    sen = hs.senaryo_getir(s, senaryo)
    with _gecici(dosya) as yol:
        mx.sablon_onizle(yol)
        oz = mx.sablon_sakla(s, sen.id, hs.dosya_adi_temizle(dosya.filename), yol.read_bytes(), k)
    return {"sablon": oz}


@router.post("/import/fiyat-listesi", response_model=FiyatListesiOnizleme, responses=HATA_404_422)
def fiyat_onizle(s: OturumDep, dosya: UploadFile = File(...), senaryo: int = Form(...), gecerlilik_basi: date | None = Form(None),
                 elle_ustune_yaz: bool = Form(False)):
    sen = hs.senaryo_getir(s, senaryo)
    with _gecici(dosya) as yol:
        return decimal_str({k: v for k, v in imp.fiyat_listesi_onizle(s, sen.id, yol, gecerlilik_basi, elle_ustune_yaz).items()
                            if not k.startswith("_")})


@router.post("/import/fiyat-listesi/uygula", response_model=FiyatListesiUygulama, responses=HATA_404_409_422)
def fiyat_uygula(s: OturumDep, dosya: UploadFile = File(...), senaryo: int = Form(...), gecerlilik_basi: date = Form(...), neden: str = Form(...),
                 elle_ustune_yaz: bool = Form(False, description="Elle girilmiş fiyatların da üzerine yaz (varsayılan: korunur)"),
                 onay: bool = Form(False, description="Satır kaybı onayı (bu yükleme kayıt silmez; diğer yüklemelerle aynı imza)"),
                 k: str = Depends(kullanici_ver)):
    sen = hs.senaryo_getir(s, senaryo)
    hs.kilit_denetle(sen)
    with _gecici(dosya) as yol:
        return imp.fiyat_listesi_uygula(s, sen.id, yol, gecerlilik_basi, neden, k, elle_ustune_yaz, hs.dosya_adi_temizle(dosya.filename))


def geri_al_uclari(router: APIRouter, onek: str, alan: str, senaryolu: bool = True, etiket: str = "") -> None:
    """`{onek}/son-yukleme` (GET) ve `{onek}/son-yuklemeyi-geri-al` (POST). senaryolu: kapsam ?senaryo=; değilse 'genel'.
    Geri al: senaryo kilidi kuralı aynen (kilitli → 409); her geri alma DegisiklikKaydi'na yazılır."""
    ad = etiket or alan
    if senaryolu:
        @router.get(f"{onek}/son-yukleme", response_model=SonYuklemeYaniti, responses=HATA_404_422, name=f"{alan}_son_yukleme",
                    summary=f"{ad}: geri alınabilecek son yükleme")
        def _son(s: OturumDep, senaryo: int = Query(...)):
            return yg.son_yukleme(s, alan, hs.senaryo_getir(s, senaryo).id)

        @router.post(f"{onek}/son-yuklemeyi-geri-al", response_model=GeriAlSonucu, responses=HATA_404_409_422, name=f"{alan}_geri_al",
                     summary=f"{ad}: son yüklemeyi geri al")
        def _geri(s: OturumDep, senaryo: int = Query(...), k: str = Depends(kullanici_ver)):
            sen = hs.senaryo_getir(s, senaryo)
            hs.kilit_denetle(sen)
            return yg.geri_al(s, alan, sen.id, k)
        return

    @router.get(f"{onek}/son-yukleme", response_model=SonYuklemeYaniti, responses=HATA_404_422, name=f"{alan}_son_yukleme",
                summary=f"{ad}: geri alınabilecek son yükleme")
    def _son_genel(s: OturumDep):
        return yg.son_yukleme(s, alan, yg.GENEL)

    @router.post(f"{onek}/son-yuklemeyi-geri-al", response_model=GeriAlSonucu, responses=HATA_404_409_422, name=f"{alan}_geri_al",
                 summary=f"{ad}: son yüklemeyi geri al")
    def _geri_genel(s: OturumDep, k: str = Depends(kullanici_ver)):
        return yg.geri_al(s, alan, yg.GENEL, k)


geri_al_uclari(router, "/import/fiyat-listesi", "fiyat_listesi", etiket="Fiyat listesi")
# Tüm çalışma kitabı: yalnız 'tamamla' modu (mevcut senaryoya yazar) yedeklenir; 'yeni' mod ayrı senaryo açar (geri almak = senaryoyu silmek).
geri_al_uclari(router, "/import/excel-tam", "excel_tam", etiket="Tüm çalışma kitabı (tamamla)")
