from datetime import date
from fastapi import APIRouter, Query
from ..servisler import aile as aile_servisi, hesap_servisi as hs, karsilastirma_servisi as ks
from ..servisler.hatalar import BulunamadiHatasi, ServisHatasi
from .bagimliliklar import OturumDep, SenaryoDep
from .semalar import AileCikis, AileKarsilastirmaCikis, HATA_404_422, UrunKarsilastirmaCikis

router = APIRouter(tags=["karsilastirma"])
HESAP_HATALARI = (ServisHatasi, ArithmeticError, KeyError, ValueError)


@router.get("/karsilastirma/aileler", response_model=list[AileCikis], responses=HATA_404_422)
def aileler(s: OturumDep, sen: SenaryoDep, tum: bool = Query(False)):
    """Senaryo üyesi ürünlerin aileleri (ambalaj hacmine göre sıralı üyeler); tum=1 tüm aktif ürünler. `tek_uyeli: true` tek ürünlü aile."""
    return ks.aileler(s, None if tum else sen.id)


@router.get("/karsilastirma/aile/{aile:path}", response_model=AileKarsilastirmaCikis, responses=HATA_404_422)
def aile_trendi(s: OturumDep, aile: str, sen: SenaryoDep, tarih: date | None = None, tum: bool = Query(False)):
    us = ks.aile_urunleri(s, aile, None if tum else sen.id)
    if not us:
        raise BulunamadiHatasi(f"{aile} ailesi bulunamadı.", {"aile": aile})
    return {"aile": aile, "aile_ad": aile_servisi.aile_gorunen_ad(aile, us), "satirlar": ks.ambalaj_kg_trendi(s, aile, sen, tarih, tum)}


@router.get("/karsilastirma/urun/{kod}", response_model=UrunKarsilastirmaCikis, responses=HATA_404_422)
def urun_karsilastirma(s: OturumDep, kod: str, sen: SenaryoDep, tarih: date | None = None, musteri: str | None = None):
    """Geçen yıl satışı, enflasyon eşiği ve hedef adet etkisi. Bütçe hesabı yapılamazsa (örn. üretim hedefi yok) `gecen_yil` yine döner,
    diğer ikisi null olur ve `hesap_hatasi` mesaj taşır."""
    u = hs.urun_getir(s, kod)
    gecen = ks.gecen_yil(s, u, sen, musteri)
    d = {"gecen_yil": gecen, "enflasyon_esigi": None, "uretim_adedi_etkisi": None, "hesap_hatasi": None}
    hatalar: list[str] = []

    def bolum(ad: str, fonk):
        """Her bölüm bağımsız: biri patlarsa diğerleri dolu kalır, hata `hesap_hatasi`na eklenir (500 yok)."""
        try:
            return fonk()
        except HESAP_HATALARI as e:
            hatalar.append(f"{ad}: {getattr(e, 'mesaj', None) or e.__class__.__name__}")
            return None
    hesap = bolum("bütçe hesabı", lambda: hs.hesapla(s, u.kod, sen.id, tarih))
    if hesap is not None:
        d["enflasyon_esigi"] = bolum("enflasyon eşiği", lambda: ks.enflasyon_esigi_hesapla(gecen, hesap))
        d["uretim_adedi_etkisi"] = bolum("üretim adedi etkisi", lambda: ks.uretim_adedi_etkisi(s, u, sen, tarih, hesap=hesap))
    d["hesap_hatasi"] = "; ".join(hatalar) or None
    return d
