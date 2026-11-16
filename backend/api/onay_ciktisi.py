"""Onay çıktısı uçları: Fiyat Çalışması ve maliyet muhasebesi (SMM) için yeminli mali müşavire verilecek değerli Excel ya da PDF.
POST'tur (gövde büyük olabilir) ama veri yazmaz: her rol (izleyici dahil) ve kilitli çalışma / dönem indirebilir (kimlik_servisi
_SALT_OKUNUR_POST); dashboard önbelleği de boşaltılmaz (uygulama.onbellegi_temizlemeli_mi)."""
from urllib.parse import quote
from fastapi import APIRouter, Depends, Response
from ..servisler import onay_ciktisi_servisi as oc
from .bagimliliklar import OturumDep, kullanici_ver
from .semalar import HATA_404_422, OnayCiktisiFiyatGiris, OnayCiktisiSmmGiris

router = APIRouter(tags=["onay-ciktisi"])
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DOSYA_YANITI = {200: {"content": {XLSX: {"schema": {"type": "string", "format": "binary"}},
                                  "application/pdf": {"schema": {"type": "string", "format": "binary"}}},
                      "description": "Excel (.xlsx) ya da PDF dosyası"}, **HATA_404_422}


def _yanit(icerik: bytes, tur: str, ad: str) -> Response:
    return Response(icerik, media_type=tur, headers={"Content-Disposition": f"attachment; filename=\"{ad}\"; filename*=UTF-8''{quote(ad)}"})


def _ekler(g) -> oc.Ekler:
    return oc.Ekler(**g.ekler.model_dump())


def _imzalar(g) -> oc.Imzalar:
    return oc.Imzalar(**{k: (v or "").strip() or None for k, v in g.imzalar.model_dump().items()})


@router.post("/onay-ciktisi/fiyat", response_class=Response, responses=DOSYA_YANITI)
def fiyat(s: OturumDep, g: OnayCiktisiFiyatGiris, k: str = Depends(kullanici_ver)):
    """Fiyat Çalışması onay çıktısı. Excel: Kapak · Teklif Kapak · Özet + ürün başına kart · Satın Alma Fiyatları · Parametreler ·
    Gider Dağıtım · (ekler). PDF: aynı içerik. Çalışma kilitliyse KESİN, değilse TASLAK. Bilinmeyen çalışma 404; çalışmada olmayan ürün 422."""
    return _yanit(*oc.fiyat_ciktisi(s, g.senaryo_id, g.tur, g.urunler, _ekler(g), _imzalar(g), k))


@router.post("/onay-ciktisi/smm", response_class=Response, responses=DOSYA_YANITI)
def smm(s: OturumDep, g: OnayCiktisiSmmGiris, k: str = Depends(kullanici_ver)):
    """Maliyet muhasebesi onay çıktısı. Excel: Kapak · Stok ve Envanter · Üretim 20/40/50 · DSS · SMM Tablosu · Gider Mizanı ·
    Stok Mizanı · Fiş Taslağı · (Mutabakat · ekler). PDF: aynı içerik. Dönem kilitliyse KESİN, değilse TASLAK. Bilinmeyen dönem 404."""
    return _yanit(*oc.smm_ciktisi(s, g.donem_id, g.tur, _ekler(g), _imzalar(g), k))
