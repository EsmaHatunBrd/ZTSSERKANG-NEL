from datetime import date
from fastapi import APIRouter, Depends, Query
from ..servisler import analiz_servisi, fiyat_servisi as fs
from ..servisler.hatalar import DogrulamaHatasi
from ..servisler.donusum import zaman_iso
from .bagimliliklar import OturumDep, SenaryoDep, kullanici_ver
from .semalar import FiyatEkleCikis, FiyatGecmisi, FiyatGiris, HATA_404_409_422, HATA_404_422, MalzemeGiris, MalzemeKartiCikis, MalzemeListesi, PasifCikis

router = APIRouter(tags=["malzemeler"])


def _kucuk(s: str) -> str:
    """Türkçe küçük harf: 'I' -> 'ı', 'İ' -> 'i' (str.lower 'İ'yi noktalı 'i̇' yapar)."""
    return s.replace("I", "ı").replace("İ", "i").lower()


@router.get("/malzemeler", response_model=MalzemeListesi, responses=HATA_404_422, response_model_exclude_unset=True)
def listele(s: OturumDep, sen: SenaryoDep, fiyatsiz: bool = False, tarih: date | None = None, revize: bool = False,
            sayfa: int = Query(1, ge=1), boyut: int = Query(50, ge=1, le=500), arama: str | None = None):
    """revize=1: yalnız geçerli fiyatı ilk bütçeden (senaryodaki en eski kayıt) farklı olanlar. arama: kod ya da adda geçen metin
    (Türkçe büyük/küçük harf duyarsız); sayfalamadan ÖNCE süzülür, aranan malzeme hangi sayfada olursa olsun bulunur."""
    t = tarih or date.today()
    fiyatsizlar = set(fs.fiyatsizlar(s, sen.id, t))
    kayitlar = fs.gecerli_kayitlar_kodla(s, sen.id, t)
    ilk = fs.ilk_kayitlar_kodla(s, sen.id)
    satirlar = [{"kod": mz.kod, "ad": mz.ad, "tip": mz.tip, "birim": mz.birim, "para_birimi": mz.para_birimi, "zs": mz.zs,
                 "fiyat": str(mz.fiyat), "fiyatsiz": kod in fiyatsizlar,
                 "gecerlilik_basi": kayitlar[kod].gecerlilik_basi.isoformat() if kod in kayitlar else None,
                 "kaynak": kayitlar[kod].kaynak if kod in kayitlar else None,
                 "ilk_fiyat": str(ilk[kod].fiyat) if kod in ilk else None,
                 "revize": kod in ilk and kod in kayitlar and kayitlar[kod].fiyat != ilk[kod].fiyat}
                for kod, mz in sorted(fs.gecerli_fiyatlar(s, sen.id, t).items())]
    if revize:
        satirlar = [x for x in satirlar if x["revize"]]
    if fiyatsiz:
        satirlar = [x for x in satirlar if x["fiyatsiz"]]
        satirlar += [{"kod": kod, "ad": None, "kart_yok": True} for kod in fs.recete_kartsiz_kodlar(s, sen.id)]   # reçetede geçen ama kartı olmayan kodlar
    q = _kucuk(arama or "").strip()
    if q:
        satirlar = [x for x in satirlar if q in _kucuk(x["kod"]) or q in _kucuk(x.get("ad") or "")]
    bas = (sayfa - 1) * boyut
    return {"kayitlar": satirlar[bas:bas + boyut], "toplam": len(satirlar)}


@router.post("/malzemeler", status_code=201, response_model=MalzemeKartiCikis, responses=HATA_404_409_422)
def kart(s: OturumDep, g: MalzemeGiris, k: str = Depends(kullanici_ver)):
    mz = fs.malzeme_ekle_veya_guncelle(s, g.kod, g.ad, g.tip, g.birim, g.para_birimi, g.zs, k)
    return {"id": mz.id, "kod": mz.kod, "ad": mz.ad}


@router.patch("/malzemeler/{kod}/pasif", response_model=PasifCikis, responses=HATA_404_409_422)
def pasiflestir(s: OturumDep, kod: str, k: str = Depends(kullanici_ver)):
    mz = fs.malzeme_pasiflestir(s, kod, k)
    return {"kod": mz.kod, "aktif": mz.aktif}


@router.post("/malzemeler/{kod}/fiyatlar", status_code=201, response_model=FiyatEkleCikis, responses=HATA_404_409_422)
def fiyat_ekle(s: OturumDep, kod: str, g: FiyatGiris, sen: SenaryoDep, k: str = Depends(kullanici_ver)):
    if not g.onay and (sapma := analiz_servisi.fiyat_sapmasi(s, sen.id, kod, g.fiyat, g.para_birimi, g.gecerlilik_basi)):
        raise DogrulamaHatasi("fiyat bir önceki fiyattan eşikten fazla farklı; onaylayıp yeniden gönderin", sapma, kod=analiz_servisi.FIYAT_SAPMA)
    f = fs.fiyat_ekle(s, sen.id, kod, g.fiyat, g.gecerlilik_basi, g.neden, "elle", g.para_birimi, k)
    return {"id": f.id, "fiyat": str(f.fiyat), "gecerlilik_basi": f.gecerlilik_basi.isoformat()}


@router.get("/malzemeler/{kod}/fiyatlar", response_model=FiyatGecmisi, responses=HATA_404_422)
def fiyat_gecmisi(s: OturumDep, kod: str, sen: SenaryoDep):
    k = [{"id": x.id, "fiyat": str(x.fiyat), "para_birimi": x.para_birimi, "gecerlilik_basi": x.gecerlilik_basi.isoformat(), "kaynak": x.kaynak,
          "neden": x.neden, "olusturan": x.olusturan, "olusturma_zamani": zaman_iso(x.olusturma_zamani)} for x in fs.gecmis(s, sen.id, kod)]
    return {"kayitlar": k, "toplam": len(k)}
