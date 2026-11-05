from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session
from ..depo import modeller as m
from ..servisler import hesap_servisi as hs, teklif_servisi as ts
from ..servisler.donusum import zaman_iso
from .bagimliliklar import OturumDep, SenaryoDep, kullanici_ver
from .semalar import DurumGiris, HATA_404_409_422, HATA_404_422, SenaryoTeklifListesi, TeklifCikis, TeklifGiris, TeklifListesi

router = APIRouter(tags=["teklifler"])


def _s(v):
    return None if v is None else str(v)


def _teklif(t: m.Teklif) -> dict:
    return {"id": t.id, "maliyet_hesabi_id": t.maliyet_hesabi_id, "tur_no": t.tur_no, "kar_orani": str(t.kar_orani), "fiyat_tl": str(t.fiyat_tl),
            "fiyat_usd": _s(t.fiyat_usd), "fiyat_eur": _s(t.fiyat_eur), "musteri": t.musteri, "durum": t.durum, "notu": t.notu, "olusturan": t.olusturan}


def _senaryo_satiri(t: m.Teklif, h: m.MaliyetHesabi, u: m.Urun) -> dict:
    return {"teklif_id": t.id, "hesap_id": h.id, "urun_kodu": u.kod, "urun_ad": u.ad, "hesap_tarihi": h.hesap_tarihi.isoformat(), "tur_no": t.tur_no,
            "kar_orani": str(t.kar_orani), "fiyat_tl": str(t.fiyat_tl), "fiyat_usd": _s(t.fiyat_usd), "fiyat_eur": _s(t.fiyat_eur), "musteri": t.musteri,
            "durum": t.durum, "olusturan": t.olusturan, "olusturma_zamani": zaman_iso(t.olusturma_zamani)}


@router.get("/teklifler", response_model=SenaryoTeklifListesi, responses=HATA_404_422)
def senaryo_teklifleri(s: OturumDep, sen: SenaryoDep, durum: str | None = None, musteri: str | None = None,
                       sayfa: int = Query(1, ge=1), boyut: int = Query(50, ge=1, le=500)):
    satirlar = ts.senaryo_teklifleri(s, sen.id, durum, musteri)
    bas = (sayfa - 1) * boyut
    return {"kayitlar": [_senaryo_satiri(*x) for x in satirlar[bas:bas + boyut]], "toplam": len(satirlar)}


@router.post("/hesaplar/{hesap_id}/teklifler", status_code=201, response_model=TeklifCikis, responses=HATA_404_409_422)
def tur_ekle(s: OturumDep, hesap_id: int, g: TeklifGiris, k: str = Depends(kullanici_ver)):
    hs.kilit_denetle(hs.senaryo_getir(s, hs.getir(s, hesap_id).senaryo_id))
    return _teklif(ts.tur_ekle(s, hesap_id, g.kar_orani, g.musteri, g.notu, k))


@router.get("/hesaplar/{hesap_id}/teklifler", response_model=TeklifListesi, responses=HATA_404_422)
def turlar(s: OturumDep, hesap_id: int):
    k = [_teklif(t) for t in ts.turlar(s, hesap_id)]
    return {"kayitlar": k, "toplam": len(k)}


@router.patch("/teklifler/{teklif_id}/durum", response_model=TeklifCikis, responses=HATA_404_409_422)
def durum(s: OturumDep, teklif_id: int, g: DurumGiris):
    t = s.get(m.Teklif, teklif_id)
    if t is not None:   # yoksa servis 404 verir
        hs.kilit_denetle(hs.senaryo_getir(s, hs.getir(s, t.maliyet_hesabi_id).senaryo_id))
    return _teklif(ts.durum_guncelle(s, teklif_id, g.durum))


@router.delete("/teklifler/{teklif_id}", status_code=204, response_class=Response, responses=HATA_404_409_422)
def sil(s: OturumDep, teklif_id: int, k: str = Depends(kullanici_ver)):
    t = s.get(m.Teklif, teklif_id)
    if t is not None:   # yoksa servis 404 verir
        hs.kilit_denetle(hs.senaryo_getir(s, hs.getir(s, t.maliyet_hesabi_id).senaryo_id))
    ts.sil(s, teklif_id, k)
    return Response(status_code=204)
