from fastapi import APIRouter, Depends, Response
from ..depo import modeller as m
from ..servisler import hesap_servisi as hs, senaryo_servisi as ss
from .bagimliliklar import OturumDep, kullanici_ver
from .semalar import HATA_404_409_422, HATA_404_422, SenaryoCikis, SenaryoGiris, SenaryoGuncelleGiris, SenaryoKopyaCikis, SenaryoKopyaGiris, SenaryoListesi

router = APIRouter(tags=["senaryolar"])


def _cikis(sen: m.Senaryo, urun_sayisi: int) -> dict:
    return SenaryoCikis(id=sen.id, sezon_ad=sen.sezon.ad, tur=sen.tur, ad=sen.ad, kilitli=bool(sen.kilitli), aciklama=sen.aciklama,
                        urun_sayisi=urun_sayisi).model_dump()


def _tek(s, sen: m.Senaryo) -> dict:
    return _cikis(sen, len(ss.uye_urun_kodlari(s, sen.id)))


@router.get("/senaryolar", response_model=SenaryoListesi, responses=HATA_404_422)
def listele(s: OturumDep):
    sayilar = ss.uye_sayilari(s)
    k = [_cikis(x, sayilar.get(x.id, 0)) for x in hs.senaryolar(s)]
    return {"kayitlar": k, "toplam": len(k)}


@router.post("/senaryolar", status_code=201, response_model=SenaryoCikis, responses=HATA_404_409_422)
def olustur(s: OturumDep, g: SenaryoGiris, k: str = Depends(kullanici_ver)):
    return _cikis(hs.senaryo_olustur(s, g.sezon_ad, g.tur, g.ad, g.aciklama, k), 0)


@router.post("/senaryolar/{senaryo_id}/kopyala", status_code=201, response_model=SenaryoKopyaCikis, responses=HATA_404_409_422)
def kopyala(s: OturumDep, senaryo_id: int, g: SenaryoKopyaGiris, k: str = Depends(kullanici_ver)):
    """Kaynak senaryodan seçilen bölümleri yeni senaryoya kopyalar (tek işlem). Kaynak kilitli olabilir (salt okunur)."""
    yeni, sayilar = ss.kopyala(s, senaryo_id, g.sezon_ad, g.ad, g.tur, g.aciklama, g.kopyala.model_dump(), g.neden, k)
    return {**_tek(s, yeni), "kopyalanan": sayilar}


@router.patch("/senaryolar/{senaryo_id}", response_model=SenaryoCikis, responses=HATA_404_409_422)
def guncelle(s: OturumDep, senaryo_id: int, g: SenaryoGuncelleGiris, k: str = Depends(kullanici_ver)):
    """Yalnız gönderilen alanlar (sezon_ad, ad, aciklama) değişir; kilitli senaryoda 409."""
    alanlar = g.model_dump(exclude_unset=True, exclude={"neden"})
    return _tek(s, ss.guncelle(s, senaryo_id, alanlar, g.neden, k))


@router.delete("/senaryolar/{senaryo_id}", status_code=204, response_class=Response, responses=HATA_404_409_422)
def sil(s: OturumDep, senaryo_id: int, k: str = Depends(kullanici_ver)):
    """Yalnız kayıtlı hesabı olmayan ve kilitsiz senaryo silinir; aksi 409 `catisma`. Dosya veritabanında önce otomatik yedek alınır;
    günlüğe kim/ne zaman sildiği düşer."""
    ss.sil(s, senaryo_id, kullanici=k)
    return Response(status_code=204)
