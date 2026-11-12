"""Stokta kalan (geçen yıldan devreden) ürün: ürün başına kayıt, liste ve Excel ile toplu aktarım. Kural: servisler/stok_devri_servisi.py."""
from io import BytesIO
from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from ..servisler import hesap_servisi as hs, stok_devri_servisi as sd
from ..servisler.donusum import decimal_str
from ..servisler.hatalar import ServisHatasi
from .bagimliliklar import OturumDep, SenaryoDep, kullanici_ver
from .import_ import _gecici
from .semalar import HATA_404_409_422, HATA_404_422, StokDevriCikis, StokDevriGiris, StokDevriListesi, StokDevriOnizle, StokDevriUygula

router = APIRouter(tags=["stok-devri"])
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _cikis(s, sen, urun) -> dict:
    return decimal_str(sd.etki(s, sen, urun))


@router.get("/urunler/{kod}/stok-devri", response_model=StokDevriCikis, responses=HATA_404_422)
def getir(s: OturumDep, kod: str, sen: SenaryoDep):
    """Kayıt yoksa 200: alanlar null, stok_etkisi false. Kayıt varsa bu yılın maliyeti bugünkü canlı hesaptan gelir."""
    return _cikis(s, sen, hs.urun_getir(s, kod))


@router.put("/urunler/{kod}/stok-devri", response_model=StokDevriCikis, responses=HATA_404_409_422)
def kaydet(s: OturumDep, kod: str, g: StokDevriGiris, sen: SenaryoDep, k: str = Depends(kullanici_ver)):
    u = hs.urun_getir(s, kod)
    sd.kaydet(s, sen, u, g.adet, g.birim_maliyet, g.enflasyon, g.uretim_adedi, g.neden, k)
    return _cikis(s, sen, u)


@router.delete("/urunler/{kod}/stok-devri", status_code=204, response_class=Response, responses=HATA_404_409_422)
def sil(s: OturumDep, kod: str, sen: SenaryoDep, neden: str = Query(..., min_length=1, max_length=300), k: str = Depends(kullanici_ver)):
    """Kayıt yoksa da 204 (değişiklik kaydı açılmaz). Silinen değerler değişiklik günlüğünde kalır."""
    sd.sil(s, sen, hs.urun_getir(s, kod), neden, k)
    return Response(status_code=204)


@router.get("/stok-devri", response_model=StokDevriListesi, responses=HATA_404_422)
def listele(s: OturumDep, sen: SenaryoDep):
    """Yalnız kaydı olan ürünler (ürün koduna göre). Bu yılın maliyeti tek hesap bağlamıyla canlı hesaplanır."""
    baglam = hs.HesapBaglami()
    out = []
    for u, _ in sd.liste(s, sen.id):
        try:
            c = hs.hesapla(s, u.kod, sen.id, baglam=baglam)
        except (ServisHatasi, KeyError, ValueError, ArithmeticError):   # hesap hatası satırı düşürmez; sd.etki nedeni açıklamaya yazar
            c = None
        out.append({**decimal_str(sd.etki(s, sen, u, c)), "ad": u.ad})
    return {"kayitlar": out}


@router.get("/aktarim/stok-devri/sablon.xlsx", response_model=None,
            responses={200: {"content": {XLSX: {"schema": {"type": "string", "format": "binary"}}}, "description": "Yükleme şablonu (.xlsx)"}})
def sablon():
    wb = Workbook()
    ws = wb.active
    ws.title = "Stokta Kalan"
    ws.append(list(sd.SUTUNLAR))
    ws.append(["ORNEK-001", 2000, 30, 0.4, 8000])   # uydurma örnek satırlar
    ws.append(["ORNEK-002", 500, 12.5, None, None])
    nt = wb.create_sheet("Açıklama")
    for satir in sd.SABLON_ACIKLAMA:
        nt.append([satir])
    tampon = BytesIO()
    wb.save(tampon)
    tampon.seek(0)
    return StreamingResponse(tampon, media_type=XLSX, headers={"Content-Disposition": 'attachment; filename="stokta-kalan-sablon.xlsx"'})


def _temiz(d: dict) -> dict:
    return {**d, "satirlar": [{k: v for k, v in r.items() if not k.startswith("_")} for r in d["satirlar"]]}


@router.post("/aktarim/stok-devri/onizle", response_model=StokDevriOnizle, responses=HATA_404_422)
def onizle(s: OturumDep, dosya: UploadFile = File(...), senaryo: int = Form(...)):
    """Sütun eşlemesi, yeni/değişen/aynı satırlar ve hatalı satırlar (atlanmaz, listelenir). Hiçbir şey yazılmaz."""
    sen = hs.senaryo_getir(s, senaryo)
    with _gecici(dosya) as yol:
        return _temiz(sd.aktarim_onizle(s, sen, yol))


@router.post("/aktarim/stok-devri/uygula", response_model=StokDevriUygula, responses=HATA_404_409_422)
def uygula(s: OturumDep, dosya: UploadFile = File(...), senaryo: int = Form(...), neden: str = Form(...), kul: str = Depends(kullanici_ver)):
    """Hatalı satır varsa 422 (`alanlar.hatalar` = [{satir_no, mesaj}]) ve hiçbir satır yazılmaz. Kilitli çalışmaya yazılmaz (409)."""
    sen = hs.senaryo_getir(s, senaryo)
    hs.kilit_denetle(sen)
    with _gecici(dosya) as yol:
        return sd.aktarim_uygula(s, sen, yol, neden, kul)
