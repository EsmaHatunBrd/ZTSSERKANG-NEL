from fastapi import APIRouter, Depends
from ..depo import modeller as m
from ..servisler import gider_servisi as gs
from ..servisler.donusum import decimal_str
from .bagimliliklar import OturumDep, SenaryoDep, kullanici_ver
from .semalar import AmbalajGiris, AmbalajKaydiGiris, AmbalajListesi, GiderHavuzlariCikis, HATA_404_409_422, HATA_404_422, HavuzGiris, HavuzKaydetCikis

router = APIRouter(tags=["gider"])


def _havuz(h: m.GiderHavuzu) -> dict:
    return {"kod": h.kod, "ad": h.ad, "toplam_tutar": str(h.toplam_tutar), "baz_tipi": h.baz_tipi,
            "baz_miktar": None if h.baz_miktar is None else str(h.baz_miktar),
            "taban_tutar": None if h.taban_tutar is None else str(h.taban_tutar),
            "carpanlar": [{"ad": c.get("ad", ""), "deger": str(c.get("deger", ""))} for c in (h.carpanlar or [])],
            "anahtarlar": [{"alt_kalem": a.alt_kalem, "pay_orani": str(a.pay_orani), "baz_miktar": str(a.baz_miktar)} for a in h.anahtarlar]}


def _ambalajlar(s, senaryo_id: int) -> dict:
    k = [{"ad": a.ad, "hacim": str(a.hacim), "uretim_adedi": str(a.uretim_adedi), "katsayi": str(a.katsayi)} for a in gs.ambalajlar(s, senaryo_id)]
    return {"kayitlar": k, "toplam": len(k)}


@router.get("/gider-havuzlari", response_model=GiderHavuzlariCikis, responses=HATA_404_422)
def havuzlar(s: OturumDep, sen: SenaryoDep):
    k = [_havuz(h) for h in gs.havuzlar(s, sen.id).values()]
    return {"kayitlar": k, "toplam": len(k), "pay_kontrol": decimal_str(gs.pay_toplami_kontrol(s, sen.id))}


@router.put("/gider-havuzlari/{kod}", response_model=HavuzKaydetCikis, responses=HATA_404_409_422)
def havuz_kaydet(s: OturumDep, kod: str, g: HavuzGiris, sen: SenaryoDep, k: str = Depends(kullanici_ver)):
    h = gs.havuz_kaydet(s, sen.id, kod, g.ad, g.toplam_tutar, g.baz_tipi, g.baz_miktar,
                        [(a.alt_kalem, a.pay_orani, a.baz_miktar, a.tutar) for a in g.anahtarlar], k, g.neden,
                        taban_tutar=g.taban_tutar, carpanlar=None if g.carpanlar is None else [(c.ad, c.deger) for c in g.carpanlar])
    return {**_havuz(h), "pay_kontrol": decimal_str(gs.pay_toplami_kontrol(s, sen.id))}


@router.get("/ambalaj-siniflari", response_model=AmbalajListesi, responses=HATA_404_422)
def ambalaj_listele(s: OturumDep, sen: SenaryoDep):
    return _ambalajlar(s, sen.id)


@router.put("/ambalaj-siniflari", response_model=AmbalajListesi, responses=HATA_404_409_422)
def ambalaj_kaydet(s: OturumDep, g: AmbalajKaydiGiris | list[AmbalajGiris], sen: SenaryoDep, k: str = Depends(kullanici_ver)):
    siniflar, neden = (g.siniflar, g.neden) if isinstance(g, AmbalajKaydiGiris) else (g, "(belirtilmedi)")   # çıplak liste geriye uyumluluk için
    gs.ambalaj_kaydet(s, sen.id, [(a.ad, a.hacim, a.uretim_adedi, a.katsayi) for a in siniflar], k, neden)
    return _ambalajlar(s, sen.id)
