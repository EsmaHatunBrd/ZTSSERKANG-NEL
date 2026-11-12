"""Liste fiyatı çalışması (yalnız Berrak; yurtiçi/yurtdışı pazar): liste = satış fiyatı ÷ pazar böleni, adıma yuvarlanmış; geçmiş liste fiyatları elle ya da Excel'den; örnek veri üret/sil."""
from decimal import Decimal
from typing import Literal
from io import BytesIO
from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from ..servisler import hesap_servisi as hs, liste_servisi as ls, satis_okuyucu
from ..servisler.hatalar import DogrulamaHatasi
from . import urunler as urunler_api
from .bagimliliklar import OturumDep, SenaryoDep, kullanici_ver
from .semalar import HATA_404_422, ListeCalismasi, ListeFiyatiCikis, ListeFiyatiGiris, ListeOrnekOzeti, ListeYuklemeOzeti

router = APIRouter(tags=["liste-fiyatlari"])
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
Pazar = Literal["yurtici", "yurtdisi"]
ACIKLAMA = [
    "Başlıklar: urun_kodu, yil, liste_fiyati, birim_maliyet, pazar (ilk sayfada, ilk satır). birim_maliyet ve pazar boş bırakılabilir.",
    "Liste fiyatı yalnız Berrak markalı ürünlere girilir.",
    "liste_fiyati: o yılın liste fiyatı, TL, KDV hariç. birim_maliyet: o yılın birim maliyeti (TL); maliyet artışıyla kıyas için.",
    "pazar: Yurtiçi ya da Yurtdışı; boşsa Yurtiçi. Her ürünün iki pazar için ayrı liste fiyatı olabilir.",
    "Sayı biçimi: 1234.56 ya da 1234,56. Aynı ürün, yıl ve pazar tekrar yüklenirse eski değerin yerine geçer.",
    "Herhangi bir satır hatalıysa hiçbir satır yazılmaz.",
]


def _dashboard(s, sen, yanit: Response) -> list[dict]:
    return urunler_api._onbellekli(s, sen.id, None, None, False, yanit)


def _senaryo_id(s, senaryo: int | None) -> int | None:
    return hs.senaryo_getir(s, senaryo).id if senaryo is not None else None


@router.get("/liste-calismasi", response_model=ListeCalismasi, responses=HATA_404_422)
def calisma(s: OturumDep, sen: SenaryoDep, yanit: Response, pazar: Pazar = Query("yurtici", description="yurtici | yurtdisi"),
            bolen: Decimal | None = Query(None, description="Kaydetmeden denemek için bölen (seçili pazar)"),
            yuvarlama: Decimal | None = Query(None, description="Kaydetmeden denemek için yuvarlama adımı (TL)")):
    """Yalnız Berrak markalı ürünler. yeni_liste = satış ÷ pazar böleni, adıma en yakına yuvarlanmış (KDV hariç); yeni_liste_ham yuvarlamasız."""
    return ls.calisma(s, sen, _dashboard(s, sen, yanit), pazar, bolen, yuvarlama)


@router.put("/liste-fiyatlari", response_model=ListeFiyatiCikis, responses=HATA_404_422)
def kaydet(s: OturumDep, g: ListeFiyatiGiris, k: str = Depends(kullanici_ver),
           senaryo: int | None = Query(None, description="Bölen girilmezse bu senaryonun bugünkü geçerli böleni yazılır (yoksa varsayılan)")):
    return ls.kaydet(s, g.urun_kodu, g.yil, g.liste_fiyati, g.birim_maliyet, k, g.pazar, g.bolen, _senaryo_id(s, senaryo))


@router.delete("/liste-fiyatlari/{urun_kodu}/{yil}", status_code=204, response_class=Response, responses=HATA_404_422)
def sil(s: OturumDep, urun_kodu: str, yil: int, pazar: Pazar = Query("yurtici"), k: str = Depends(kullanici_ver)):
    ls.sil(s, urun_kodu, yil, k, pazar)
    return Response(status_code=204)


@router.post("/liste-fiyatlari/yukle", response_model=ListeYuklemeOzeti, responses=HATA_404_422)
def yukle(s: OturumDep, dosya: UploadFile = File(...), k: str = Depends(kullanici_ver),
          senaryo: int | None = Query(None, description="Satırlara bu senaryonun bugünkü geçerli bölenleri yazılır (yoksa varsayılan)")):
    """CSV/xlsx. Tek işlem: herhangi bir satır hatalıysa 422 (`alanlar.hatalar` = [{satir_no, mesaj}]) ve hiçbir satır yazılmaz."""
    icerik = dosya.file.read(satis_okuyucu.MAKS_BAYT + 1)
    yazilan, hatalar = ls.toplu_yukle(s, ls.dosya_oku(icerik, dosya.filename or ""), k, dosya.filename or "", _senaryo_id(s, senaryo))
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
    ws.append(["ORNEK-001", 2025, 54.9, 31.25, "Yurtiçi"])   # uydurma örnek satırlar
    ws.append(["ORNEK-001", 2025, 38.45, 31.25, "Yurtdışı"])
    nt = wb.create_sheet("Açıklama")
    for satir in ACIKLAMA:
        nt.append([satir])
    tampon = BytesIO()
    wb.save(tampon)
    tampon.seek(0)
    return StreamingResponse(tampon, media_type=XLSX, headers={"Content-Disposition": 'attachment; filename="liste-fiyatlari-sablon.xlsx"'})


@router.post("/liste-calismasi/ornek", response_model=ListeOrnekOzeti, responses=HATA_404_422)
def ornek_uret(s: OturumDep, sen: SenaryoDep, yanit: Response, k: str = Depends(kullanici_ver)):
    """Berrak ürünleri için iki pazarın (yurtiçi, yurtdışı) son 3 yılına tahmini liste fiyatı yazar."""
    return {"yazilan": ls.ornek_uret(s, sen, _dashboard(s, sen, yanit), k)}


@router.delete("/liste-calismasi/ornek", response_model=ListeOrnekOzeti, responses=HATA_404_422)
def ornek_sil(s: OturumDep, k: str = Depends(kullanici_ver)):
    return {"yazilan": ls.ornek_sil(s, k)}
