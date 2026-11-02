from datetime import date
from fastapi import APIRouter, Depends
from ..servisler import parametre_servisi as ps
from ..servisler.donusum import decimal_str, zaman_iso
from .bagimliliklar import OturumDep, SenaryoDep, kullanici_ver
from .semalar import HATA_404_409_422, HATA_404_422, ParametreDegerCikis, ParametreDegerGiris, MetinParametreCikis, MetinParametreGiris, MetinParametreListesi, ParametreGecmisi, ParametreTanimListesi

router = APIRouter(tags=["parametreler"])


@router.get("/parametreler", response_model=dict[str, str], responses=HATA_404_422)
def gecerli(s: OturumDep, sen: SenaryoDep, tarih: date | None = None, urun_id: int | None = None):
    return decimal_str(ps.gecerli_degerler(s, sen.id, tarih or date.today(), urun_id))


@router.get("/parametreler/tanimlar", response_model=ParametreTanimListesi, responses=HATA_404_422)
def tanimlar(s: OturumDep):
    k = [{"anahtar": p.anahtar, "aciklama": p.aciklama, "birim": p.birim} for p in ps.tanimlar(s)]
    return {"kayitlar": k, "toplam": len(k)}


@router.post("/parametreler/{anahtar}/degerler", status_code=201, response_model=ParametreDegerCikis, responses=HATA_404_409_422)
def ekle(s: OturumDep, anahtar: str, g: ParametreDegerGiris, sen: SenaryoDep, k: str = Depends(kullanici_ver)):
    d = ps.deger_ekle(s, sen.id, anahtar, g.deger, g.gecerlilik_basi, g.neden, g.kapsam_tipi, g.kapsam_id, k)
    return {"id": d.id, "deger": str(d.deger), "gecerlilik_basi": d.gecerlilik_basi.isoformat()}


@router.get("/parametreler/{anahtar}/gecmis", response_model=ParametreGecmisi, responses=HATA_404_422)
def gecmis(s: OturumDep, anahtar: str, sen: SenaryoDep):
    k = [{"id": x.id, "deger": str(x.deger), "gecerlilik_basi": x.gecerlilik_basi.isoformat(), "neden": x.neden, "kapsam_tipi": x.kapsam_tipi,
          "kapsam_id": x.kapsam_id, "olusturan": x.olusturan, "olusturma_zamani": zaman_iso(x.olusturma_zamani)} for x in ps.gecmis(s, sen.id, anahtar)]
    return {"kayitlar": k, "toplam": len(k)}


def _metin(x) -> dict:
    return {"id": x.id, "anahtar": x.anahtar, "deger": x.deger, "gecerlilik_basi": x.gecerlilik_basi.isoformat(), "neden": x.neden, "olusturan": x.olusturan}


@router.get("/metin-parametreler", response_model=MetinParametreListesi, responses=HATA_404_422)
def metin_listele(s: OturumDep, sen: SenaryoDep, tarih: date | None = None, gecmis: bool = False, anahtar: str | None = None):
    """Varsayılan: tarihte (yoksa bugün) geçerli değerler. gecmis=true: tüm kayıtlar (yeni -> eski)."""
    k = ps.metin_gecmis(s, sen.id, anahtar) if gecmis else ps.metin_gecerli(s, sen.id, tarih or date.today())
    if anahtar is not None and not gecmis:
        k = [x for x in k if x.anahtar == anahtar]
    return {"kayitlar": [_metin(x) for x in k], "toplam": len(k)}


@router.post("/metin-parametreler", status_code=201, response_model=MetinParametreCikis, responses=HATA_404_409_422)
def metin_ekle(s: OturumDep, g: MetinParametreGiris, sen: SenaryoDep, k: str = Depends(kullanici_ver)):
    return _metin(ps.metin_deger_ekle(s, sen.id, g.anahtar, g.deger, g.gecerlilik_basi, g.neden, k))
