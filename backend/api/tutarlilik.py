"""Veri Kontrolü (D7) ucu ve şemaları: seçili çalışmanın veri sorunları tek listede (önbellekli)."""
from datetime import date
from typing import Literal
from fastapi import APIRouter, Query, Response
from pydantic import BaseModel
from ..servisler import onbellek, tutarlilik_servisi as ts
from .bagimliliklar import OturumDep, SenaryoDep
from .semalar import HATA_404_422

router = APIRouter(tags=["tutarlilik"])


class TutarlilikOgesi(BaseModel):
    etiket: str
    aciklama: str
    yol: str


class TutarlilikCozumu(BaseModel):
    etiket: str
    yol: str


class TutarlilikKontrolu(BaseModel):
    kod: str
    baslik: str
    aciklama: str
    durum: Literal["tamam", "dikkat", "hata"]
    sayi: int
    cozum: TutarlilikCozumu
    ogeler: list[TutarlilikOgesi]


class TutarlilikOzeti(BaseModel):
    hata: int
    dikkat: int
    tamam: int


class TutarlilikCikis(BaseModel):
    senaryo_id: int
    kontroller: list[TutarlilikKontrolu]
    ozet: TutarlilikOzeti


@router.get("/tutarlilik", response_model=TutarlilikCikis, responses=HATA_404_422)
def tutarlilik(s: OturumDep, sen: SenaryoDep, yanit: Response, tarih: date | None = None, yenile: bool = Query(False)):
    """Kontroller sabit sırayla (ağır olanlar önce); her birinde durum, sayı, çözüm bağlantısı ve ilgili kayıtlar (en çok 200)."""
    anahtar = (sen.id, (tarih or date.today()).isoformat(), "tutarlilik")
    deger = None if yenile else onbellek.al(anahtar)
    yanit.headers["X-Onbellek"] = "hesap" if deger is None else "isabet"
    if deger is None:
        nesil = onbellek.nesil()
        deger = ts.kontroller(s, sen.id, tarih)
        onbellek.koy(anahtar, deger, nesil)
    return deger
