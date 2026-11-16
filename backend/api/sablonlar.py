"""Yükleme şablonları ve sorunlu satır raporu (tüm yükleme ekranlarının ortak uçları).

- GET  /sablonlar/{kimlik}.xlsx          : sablonlar/ altındaki hazır şablon (kimlik excel_ortak.SABLONLAR'dan). Giriş gerekli, rol kısıtı yok.
- POST /sablonlar/sorunlu-satirlar.xlsx  : önizlemedeki sorunlu satırların tümü Excel olarak (veri yazmaz; her rol kullanabilir).
"""
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from ..servisler.excel_ortak import SABLONLAR
from ..servisler.hatalar import BulunamadiHatasi
from .semalar import HATA_404, SorunluSatirlarGirdi

router = APIRouter(prefix="/sablonlar", tags=["sablonlar"])

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
SABLON_DIZINI = Path(__file__).resolve().parents[2] / "sablonlar"
# Kimlik → dosya numarası (sablonlar/11-16-2026-NN-*.xlsx); SABLONLAR sözlüğünün sırası şablon numarasıdır.
SABLON_NO = {kimlik: f"{i:02d}" for i, kimlik in enumerate(SABLONLAR, start=1)}
_DOSYA_YANITI = {200: {"content": {XLSX: {"schema": {"type": "string", "format": "binary"}}}, "description": "Excel dosyası (.xlsx)"}}


def sablon_dosyasi(kimlik: str) -> Path:
    no = SABLON_NO.get(kimlik)
    if no is None:
        raise BulunamadiHatasi("Böyle bir şablon yok.", {"kimlik": kimlik}, kod="sablon_yok")
    adaylar = sorted(SABLON_DIZINI.glob(f"11-16-2026-{no}-*.xlsx"))
    if not adaylar:
        raise BulunamadiHatasi("Şablon dosyası sunucuda bulunamadı.", {"kimlik": kimlik}, kod="sablon_yok")
    return adaylar[0]


# Sabit yol, {kimlik}.xlsx kalıbından ÖNCE tanımlanır (POST olduğu için çakışmaz ama okunurluk için).
@router.post("/sorunlu-satirlar.xlsx", response_model=None, responses=_DOSYA_YANITI)
def sorunlu_satirlar(g: SorunluSatirlarGirdi):
    wb = Workbook()
    ws = wb.active
    ws.title = "Sorunlu satırlar"
    ws["A1"] = g.baslik
    ws["A1"].font = Font(bold=True, size=12)
    basliklar = ("Satır", "Kod", "Alan", "Değer", "Neden")
    for i, b in enumerate(basliklar, start=1):
        c = ws.cell(row=3, column=i, value=b)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1E5631")
    for r, x in enumerate(g.satirlar, start=4):
        for i, v in enumerate((x.satir, x.kod, x.alan, x.deger, x.neden), start=1):
            ws.cell(row=r, column=i, value=v)
    for harf, w in zip("ABCDE", (8, 16, 22, 24, 70)):
        ws.column_dimensions[harf].width = w
    ws.freeze_panes = "A4"
    tampon = BytesIO()
    wb.save(tampon)
    tampon.seek(0)
    return StreamingResponse(tampon, media_type=XLSX, headers={"Content-Disposition": 'attachment; filename="sorunlu-satirlar.xlsx"'})


@router.get("/{kimlik}.xlsx", response_model=None, responses={**_DOSYA_YANITI, **HATA_404})
def sablon_indir(kimlik: str):
    yol = sablon_dosyasi(kimlik)
    return FileResponse(yol, media_type=XLSX, filename=yol.name)
