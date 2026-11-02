from fastapi import APIRouter, Depends
from ..depo import modeller as m
from ..servisler import recete_servisi as rs
from .bagimliliklar import OturumDep, SenaryoDep, kullanici_ver
from .semalar import FireKuraliCikis, FireKuraliGiris, FireKuraliListesi, GrupGiris, GrupListesi, HATA_404_409_422, HATA_404_422, MalzemeGrubuCikis

router = APIRouter(tags=["fire"])


def _kural(x: m.FireKurali) -> dict:
    return {"id": x.id, "kapsam_tipi": x.kapsam_tipi, "kapsam_deger": x.kapsam_deger, "oran": str(x.oran), "oncelik": x.oncelik,
            "gecerlilik_basi": x.gecerlilik_basi.isoformat(), "neden": x.neden, "olusturan": x.olusturan}


def _grup(x: m.MalzemeGrubu) -> dict:
    return {"id": x.id, "ad": x.ad, "malzeme_kodlari": [u.malzeme_kodu for u in x.uyeler]}


@router.get("/fire-kurallari", response_model=FireKuraliListesi, responses=HATA_404_422)
def listele(s: OturumDep, sen: SenaryoDep):
    k = [_kural(x) for x in rs.fire_kurallari(s, sen.id)]
    return {"kayitlar": k, "toplam": len(k)}


@router.post("/fire-kurallari", status_code=201, response_model=FireKuraliCikis, responses=HATA_404_409_422)
def ekle(s: OturumDep, g: FireKuraliGiris, sen: SenaryoDep, k: str = Depends(kullanici_ver)):
    return _kural(rs.fire_kurali_ekle(s, sen.id, g.kapsam_tipi, g.kapsam_deger, g.oran, g.gecerlilik_basi, g.neden, olusturan=k))


@router.get("/malzeme-gruplari", response_model=GrupListesi, responses=HATA_404_422)
def gruplar(s: OturumDep):
    k = [_grup(x) for x in rs.gruplar_listele(s)]
    return {"kayitlar": k, "toplam": len(k)}


@router.post("/malzeme-gruplari", status_code=201, response_model=MalzemeGrubuCikis, responses=HATA_404_409_422)
def grup(s: OturumDep, g: GrupGiris):
    return _grup(rs.grup_olustur(s, g.ad, g.malzeme_kodlari))
