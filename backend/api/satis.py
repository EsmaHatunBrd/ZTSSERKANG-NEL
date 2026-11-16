from datetime import date
from io import BytesIO
from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from ..servisler import satis_okuyucu, satis_servisi as ss
from ..servisler.hatalar import DogrulamaHatasi
from .bagimliliklar import OturumDep, kullanici_ver
from .import_ import geri_al_uclari
from .semalar import HATA_404_422, SatisCikis, SatisGiris, SatisListesi, SatisOnizleme, SatisYuklemeOzeti

ACIKLAMA = [
    "Başlıklar: urun_kodu, musteri, tarih, fiyat, para_birimi, adet (ilk sayfada, ilk satır).",
    "Tarih: YYYY-AA-GG veya GG.AA.YYYY. Para birimi: TL, USD, EUR, GBP, CHF, RUB, ZAR.",
    "Sayı biçimi: 1234.56 (nokta ondalık), 1.234,56 veya 1234,56 (Türkçe) ya da Excel sayı hücresi.",
    "Reddedilir: 2.000 (nokta + tam 3 hane, virgülsüz; belirsiz) ve 1,234.56 (virgül noktadan önce).",
    "En fazla 20000 satır; herhangi bir satır hatalıysa hiçbir satır eklenmez.",
]

router = APIRouter(tags=["satis-gecmisi"])

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
# Uydurma örnek satır: gerçek ürün/müşteri verisi şablona girmez.
ORNEK_SATIR = ["ORNEK-001", "Örnek Müşteri A.Ş.", "2025-06-30", 12.5, "TL", 1000]


@router.get("/satis-gecmisi", response_model=SatisListesi, responses=HATA_404_422)
def listele(s: OturumDep, urun_kodu: str | None = None, musteri: str | None = None, bas: date | None = None, son: date | None = None,
            sayfa: int = Query(1, ge=1), boyut: int = Query(50, ge=1, le=500)):
    kayitlar, toplam = ss.listele(s, urun_kodu, musteri, bas, son, sayfa, boyut)
    return {"kayitlar": kayitlar, "toplam": toplam}


@router.post("/satis-gecmisi", response_model=SatisCikis, status_code=201, responses=HATA_404_422)
def ekle(s: OturumDep, g: SatisGiris, k: str = Depends(kullanici_ver)):
    return ss.ekle(s, g.urun_kodu, g.musteri, g.tarih, g.fiyat, g.para_birimi, g.adet, k)


@router.post("/satis-gecmisi/onizle", response_model=SatisOnizleme, responses=HATA_404_422)
def onizle(s: OturumDep, dosya: UploadFile = File(...)):
    """Hiçbir şey yazmaz: eklenecek, sistemde zaten kayıtlı (atlanacak) ve hatalı satırlar."""
    icerik = dosya.file.read(satis_okuyucu.MAKS_BAYT + 1)
    return ss.onizle(s, satis_okuyucu.oku(icerik, dosya.filename or ""))


@router.post("/satis-gecmisi/yukle", response_model=SatisYuklemeOzeti, responses=HATA_404_422)
def yukle(s: OturumDep, dosya: UploadFile = File(...), k: str = Depends(kullanici_ver),
          kayitlilari_da_ekle: bool = Query(False, description="Sistemde aynısı olan satırları da ekle (varsayılan: atlanır, ikilenmez)"),
          onay: bool = Query(False, description="Satır kaybı onayı (bu yükleme kayıt silmez; diğer yüklemelerle aynı imza)")):
    """CSV/xlsx yükler. Tek işlem: herhangi bir satır hatalıysa 422 döner (`alanlar.hatalar` = [{satir_no, mesaj}]) ve hiçbir satır yazılmaz.
    Sistemde zaten kayıtlı satırlar (ürün, müşteri, tarih, fiyat, adet) atlanır."""
    icerik = dosya.file.read(satis_okuyucu.MAKS_BAYT + 1)
    eklenen, hatalar, atlanan = ss.toplu_yukle_ayrintili(s, satis_okuyucu.oku(icerik, dosya.filename or ""), k, dosya.filename or "",
                                                         kayitlilari_da_ekle)
    if hatalar:
        raise DogrulamaHatasi("dosyada hatalı satırlar var; hiçbir satır eklenmedi", {"hatalar": hatalar})
    return {"eklenen": eklenen, "hatalar": [], "atlanan_kayitli": atlanan}


geri_al_uclari(router, "/satis-gecmisi", "satis_gecmisi", senaryolu=False, etiket="Satış geçmişi")


@router.get("/satis-gecmisi/sablon.xlsx", response_model=None,
            responses={200: {"content": {XLSX: {"schema": {"type": "string", "format": "binary"}}}, "description": "Yükleme şablonu (.xlsx)"}})
def sablon():
    wb = Workbook()
    ws = wb.active
    ws.title = "Satış Geçmişi"
    ws.append(list(satis_okuyucu.BASLIKLAR))
    ws.append(ORNEK_SATIR)
    nt = wb.create_sheet("Açıklama")
    for satir in ACIKLAMA:
        nt.append([satir])
    tampon = BytesIO()
    wb.save(tampon)
    tampon.seek(0)
    return StreamingResponse(tampon, media_type=XLSX, headers={"Content-Disposition": 'attachment; filename="satis-gecmisi-sablon.xlsx"'})


@router.delete("/satis-gecmisi/{id}", status_code=204, responses=HATA_404_422)
def sil(s: OturumDep, id: int, k: str = Depends(kullanici_ver)):
    ss.sil(s, id, k)
    return Response(status_code=204)
