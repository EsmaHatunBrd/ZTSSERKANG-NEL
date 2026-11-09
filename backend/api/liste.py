"""Liste fiyatı çalışması: liste = satış fiyatı ÷ bölen; geçmiş liste fiyatları elle ya da Excel'den; örnek veri üret/sil."""
from decimal import Decimal
from io import BytesIO
from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from ..servisler import liste_servisi as ls, satis_okuyucu
from ..servisler.hatalar import DogrulamaHatasi
from . import urunler as urunler_api
from .bagimliliklar import OturumDep, SenaryoDep, kullanici_ver
from .semalar import HATA_404_422, ListeCalismasi, ListeFiyatiCikis, ListeFiyatiGiris, ListeOrnekOzeti, ListeYuklemeOzeti

router = APIRouter(tags=["liste-fiyatlari"])
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
ACIKLAMA = [
    "Başlıklar: urun_kodu, yil, liste_fiyati, birim_maliyet (ilk sayfada, ilk satır). birim_maliyet boş bırakılabilir.",
    "liste_fiyati: o yılın liste fiyatı, TL, KDV hariç. birim_maliyet: o yılın birim maliyeti (TL); maliyet artışıyla kıyas için.",
    "Sayı biçimi: 1234.56 ya da 1234,56. Aynı ürün ve yıl tekrar yüklenirse eski değerin yerine geçer.",
    "Herhangi bir satır hatalıysa hiçbir satır yazılmaz.",
]


def _dashboard(s, sen, yanit: Response) -> list[dict]:
    return urunler_api._onbellekli(s, sen.id, None, None, False, yanit)


@router.get("/liste-calismasi", response_model=ListeCalismasi, responses=HATA_404_422)
def calisma(s: OturumDep, sen: SenaryoDep, yanit: Response, bolen: Decimal | None = Query(None, description="Kaydetmeden denemek için bölen")):
    kayitli, var = ls.bolen_gecerli(s, sen.id)
    d = ls.calisma(s, sen, _dashboard(s, sen, yanit), bolen if bolen is not None else kayitli)
    return {**d, "bolen_kayitli": var and bolen is None, "varsayilan_bolen": str(ls.VARSAYILAN_BOLEN)}


@router.put("/liste-fiyatlari", response_model=ListeFiyatiCikis, responses=HATA_404_422)
def kaydet(s: OturumDep, g: ListeFiyatiGiris, k: str = Depends(kullanici_ver)):
    return ls.kaydet(s, g.urun_kodu, g.yil, g.liste_fiyati, g.birim_maliyet, k)


@router.delete("/liste-fiyatlari/{urun_kodu}/{yil}", status_code=204, response_class=Response, responses=HATA_404_422)
def sil(s: OturumDep, urun_kodu: str, yil: int, k: str = Depends(kullanici_ver)):
    ls.sil(s, urun_kodu, yil, k)
    return Response(status_code=204)


@router.post("/liste-fiyatlari/yukle", response_model=ListeYuklemeOzeti, responses=HATA_404_422)
def yukle(s: OturumDep, dosya: UploadFile = File(...), k: str = Depends(kullanici_ver)):
    """CSV/xlsx. Tek işlem: herhangi bir satır hatalıysa 422 (`alanlar.hatalar` = [{satir_no, mesaj}]) ve hiçbir satır yazılmaz."""
    icerik = dosya.file.read(satis_okuyucu.MAKS_BAYT + 1)
    yazilan, hatalar = ls.toplu_yukle(s, ls.dosya_oku(icerik, dosya.filename or ""), k, dosya.filename or "")
    if hatalar:
        raise DogrulamaHatasi("dosyada hatalı satırlar var; hiçbir satır yazılmadı", {"hatalar": hatalar})
    return {"yazilan": yazilan, "hatalar": []}


@router.get("/liste-fiyatlari/sablon.xlsx", response_model=None,
            responses={200: {"content": {XLSX: {"schema": {"type": "string", "format": "binary"}}}, "description": "Yükleme şablonu (.xlsx)"}})
def sablon():
    wb = Workbook()
    ws = wb.active
    ws.title = "Liste Fiyatları"
    ws.append(list(ls.BASLIKLAR))
    ws.append(["ORNEK-001", 2025, 54.9, 31.25])   # uydurma örnek satır
    nt = wb.create_sheet("Açıklama")
    for satir in ACIKLAMA:
        nt.append([satir])
    tampon = BytesIO()
    wb.save(tampon)
    tampon.seek(0)
    return StreamingResponse(tampon, media_type=XLSX, headers={"Content-Disposition": 'attachment; filename="liste-fiyatlari-sablon.xlsx"'})


@router.post("/liste-calismasi/ornek", response_model=ListeOrnekOzeti, responses=HATA_404_422)
def ornek_uret(s: OturumDep, sen: SenaryoDep, yanit: Response, k: str = Depends(kullanici_ver)):
    bolen, _ = ls.bolen_gecerli(s, sen.id)
    return {"yazilan": ls.ornek_uret(s, sen, _dashboard(s, sen, yanit), bolen, k)}


@router.delete("/liste-calismasi/ornek", response_model=ListeOrnekOzeti, responses=HATA_404_422)
def ornek_sil(s: OturumDep, k: str = Depends(kullanici_ver)):
    return {"yazilan": ls.ornek_sil(s, k)}
