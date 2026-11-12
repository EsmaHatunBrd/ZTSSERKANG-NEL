"""Tek sayfa yönetim özeti (analiz önerisi 15): seçili çalışmanın bütün başlıkları tek yanıtta; süreç içi önbellekli (yazma isteği boşaltır)."""
from datetime import date
from fastapi import APIRouter, Query, Response
from ..servisler import onbellek, yonetim_ozeti_servisi as yo
from .bagimliliklar import OturumDep, SenaryoDep
from .semalar import HATA_404_422, YonetimOzetiCikis

router = APIRouter(tags=["yonetim"])


@router.get("/yonetim/ozet", response_model=YonetimOzetiCikis, responses=HATA_404_422)
def yonetim_ozeti(s: OturumDep, sen: SenaryoDep, yanit: Response, tarih: date | None = None, yenile: bool = Query(False)):
    """Ürün/marj/maliyet yapısı/hedef altı/kur riski/teklif/veri kontrolü/en pahalı/stok etkisi/uyarılar. X-Onbellek: hesap | isabet."""
    anahtar = (sen.id, (tarih or date.today()).isoformat(), "yonetim_ozeti")
    if yenile:
        onbellek.hesap_say()
    deger = None if yenile else onbellek.al(anahtar)
    yanit.headers["X-Onbellek"] = "hesap" if deger is None else "isabet"
    if deger is None:
        nesil = onbellek.nesil()
        deger = yo.ozet(s, sen.id, tarih)
        onbellek.koy(anahtar, deger, nesil)
    return deger
