"""Değişiklik Günlüğü (birleşik akış), Arşiv (sezon -> senaryo -> kayıtlı hesaplar), senaryo kilidi, reçete sürümü etkinleştirme."""
from datetime import date
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from ..servisler import arsiv_servisi as ar, gunluk_servisi as gs
from .bagimliliklar import OturumDep, SenaryoDep, kullanici_ver
from .disa_aktar import XLSX
from .gunluk_semalari import (ArsivAgaci, ArsivKayitListesi, ArsivKiyasi, GunlukListesi, GunlukOzeti, KilitGiris, ReceteEtkinlestirCikis,
                              ReceteEtkinlestirGiris)
from .semalar import HATA_404_409_422, HATA_404_422, SenaryoCikis

router = APIRouter(tags=["gunluk-arsiv"])


def _suzgec(senaryo: int | None, bas: date | None, son: date | None, kullanici: str | None, tur: list[str] | None, urun_kodu: str | None, q: str | None) -> gs.Suzgec:
    return gs.Suzgec(senaryo=senaryo, bas=bas, son=son, kullanici=kullanici, tur=list(tur or []), urun_kodu=urun_kodu, q=q)


@router.get("/gunluk", response_model=GunlukListesi, responses=HATA_404_422)
def gunluk(s: OturumDep, senaryo: int | None = None, bas: date | None = None, son: date | None = None, kullanici: str | None = None,
           tur: list[str] | None = Query(None), urun_kodu: str | None = None, q: str | None = None,
           sayfa: int = Query(1, ge=1), boyut: int = Query(50, ge=1, le=500)):
    kayitlar, toplam = gs.liste(s, _suzgec(senaryo, bas, son, kullanici, tur, urun_kodu, q), sayfa, boyut)
    return {"kayitlar": kayitlar, "toplam": toplam, "sayfa": sayfa, "boyut": boyut}


@router.get("/gunluk/ozet", response_model=GunlukOzeti, responses=HATA_404_422)
def gunluk_ozeti(s: OturumDep, senaryo: int | None = None, gun: int = Query(7, ge=1, le=366)):
    return gs.ozet(s, senaryo, gun)


@router.get("/disa-aktar/gunluk.xlsx", response_model=None,
            responses={200: {"content": {XLSX: {"schema": {"type": "string", "format": "binary"}}}, "description": "Değişiklik günlüğü (.xlsx)"}, **HATA_404_422})
def gunluk_xlsx(s: OturumDep, senaryo: int | None = None, bas: date | None = None, son: date | None = None, kullanici: str | None = None,
                tur: list[str] | None = Query(None), urun_kodu: str | None = None, q: str | None = None):
    tampon = gs.xlsx(s, _suzgec(senaryo, bas, son, kullanici, tur, urun_kodu, q))
    return StreamingResponse(tampon, media_type=XLSX, headers={"Content-Disposition": 'attachment; filename="degisiklik-gunlugu.xlsx"'})


@router.post("/urunler/{kod}/recete/{versiyon}/etkinlestir", response_model=ReceteEtkinlestirCikis, responses=HATA_404_409_422)
def recete_etkinlestir(s: OturumDep, kod: str, versiyon: int, g: ReceteEtkinlestirGiris, sen: SenaryoDep, k: str = Depends(kullanici_ver)):
    """Eski bir reçete sürümünü yeniden aktif yapar (günlükteki 'geri al'); yeni sürüm açılmaz, DegisiklikKaydi yazılır."""
    r = gs.recete_etkinlestir(s, kod, sen.id, versiyon, g.neden, k)
    return {"id": r.id, "versiyon": r.versiyon, "aktif": r.aktif}


@router.get("/arsiv", response_model=ArsivAgaci, responses=HATA_404_422)
def arsiv(s: OturumDep):
    return {"sezonlar": ar.agac(s)}


@router.get("/arsiv/senaryo/{senaryo_id}/kayitlar", response_model=ArsivKayitListesi, responses=HATA_404_422)
def arsiv_kayitlari(s: OturumDep, senaryo_id: int, urun_kodu: str | None = None, sayfa: int = Query(1, ge=1), boyut: int = Query(50, ge=1, le=500)):
    kayitlar, toplam = ar.kayitlar(s, senaryo_id, sayfa, boyut, urun_kodu)
    return {"kayitlar": kayitlar, "toplam": toplam, "sayfa": sayfa, "boyut": boyut}


@router.get("/arsiv/kiyas", response_model=ArsivKiyasi, responses=HATA_404_422)
def arsiv_kiyasi(s: OturumDep, hesap_a: int, hesap_b: int):
    return ar.kiyas(s, hesap_a, hesap_b)


def _cikis(s, sen) -> dict:
    from ..servisler import senaryo_servisi as ss
    return SenaryoCikis(id=sen.id, sezon_ad=sen.sezon.ad, tur=sen.tur, ad=sen.ad, kilitli=bool(sen.kilitli), aciklama=sen.aciklama,
                        urun_sayisi=len(ss.uye_urun_kodlari(s, sen.id))).model_dump()


@router.post("/senaryolar/{senaryo_id}/kilitle", response_model=SenaryoCikis, responses=HATA_404_409_422)
def kilitle(s: OturumDep, senaryo_id: int, g: KilitGiris, k: str = Depends(kullanici_ver)):
    return _cikis(s, ar.kilitle(s, senaryo_id, g.neden, k))


@router.post("/senaryolar/{senaryo_id}/kilit-ac", response_model=SenaryoCikis, responses=HATA_404_409_422)
def kilit_ac(s: OturumDep, senaryo_id: int, g: KilitGiris, k: str = Depends(kullanici_ver)):
    return _cikis(s, ar.kilit_ac(s, senaryo_id, g.neden, k))
