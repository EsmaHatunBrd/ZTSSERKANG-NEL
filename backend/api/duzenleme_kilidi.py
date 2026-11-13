"""Fiyat Çalışması düzenleme kilidi: arayüz ekranları kilitli açılır; kullanıcı "Düzenlemeyi aç" dediğinde bu uç olayı
Değişiklik Günlüğü'ne yazar (izlenebilirlik). Sunucu tarafında ek zorlama yoktur: yazma uçlarının yetki ve senaryo kilidi
kuralları aynen geçerlidir. İzleyici rolü yazamadığı için bu uçta da 403 alır (kimlik_denetle)."""
from fastapi import APIRouter, Depends
from ..depo import modeller as m
from ..servisler import hesap_servisi as hs
from .bagimliliklar import OturumDep, kullanici_ver
from .semalar import HATA_404_422, DuzenlemeKilidiAcCikis, DuzenlemeKilidiAcGiris

router = APIRouter(tags=["duzenleme-kilidi"])


@router.post("/duzenleme-kilidi/ac", response_model=DuzenlemeKilidiAcCikis, status_code=201, responses=HATA_404_422)
def kilit_ac(s: OturumDep, g: DuzenlemeKilidiAcGiris, k: str = Depends(kullanici_ver)):
    """Kilidin açıldığını günlüğe yazar. Bilinmeyen senaryo 404; senaryo verilmezse kayıt senaryosuz düşer."""
    if g.senaryo_id is not None:
        hs.senaryo_getir(s, g.senaryo_id)
    kayit = m.DegisiklikKaydi(tablo="duzenleme_kilidi", kayit_id=g.senaryo_id or 0, islem="kilit_ac", eski=None,
                              yeni={"sayfa": g.sayfa, "senaryo_id": g.senaryo_id}, kullanici=k)
    s.add(kayit)
    s.flush()
    return {"kayit_id": kayit.id, "sayfa": g.sayfa, "senaryo_id": g.senaryo_id, "kullanici": k}
