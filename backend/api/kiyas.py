"""Faz 6 — Bütçe vs Gerçekleşen uçları: liste (önbellekli), ürün detayı (sapma ayrıştırması), karşı senaryo, Excel çıktısı."""
from datetime import date
from decimal import Decimal
from io import BytesIO
from fastapi import APIRouter, Query, Response
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from ..depo import modeller as m
from ..servisler import hesap_servisi as hs, kiyas_servisi as ks, onbellek
from ..servisler.donusum import decimal_str
from .bagimliliklar import OturumDep
from .kiyas_semalari import BgKarsiSenaryoCikis, BgKiyasListesi, BgKiyasUrunCikis
from .semalar import HATA_404_422

router = APIRouter(tags=["kiyas"])
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _senaryo(sen: m.Senaryo) -> dict:
    return {"id": sen.id, "ad": sen.ad, "tur": sen.tur, "sezon": sen.sezon.ad}


def _liste_json(d: dict) -> dict:
    return {**decimal_str({k: v for k, v in d.items() if k not in ("a", "b")}), "a": _senaryo(d["a"]), "b": _senaryo(d["b"])}


def _liste(s, a: int, b: int, tarih: date | None, esik: Decimal, yenile: bool, yanit: Response | None = None) -> dict:
    """Önbellek anahtarı A senaryosuyla başlar (onbellek.temizle(senaryo_id) A'ya yazılınca düşürür; her yazma zaten hepsini boşaltır)."""
    anahtar = (a, (tarih or date.today()).isoformat(), "kiyas", b, str(esik))
    deger = None if yenile else onbellek.al(anahtar)
    if yanit is not None:
        yanit.headers["X-Onbellek"] = "hesap" if deger is None else "isabet"
    if deger is None:
        nesil = onbellek.nesil()
        deger = _liste_json(ks.liste(s, a, b, tarih, esik))
        onbellek.koy(anahtar, deger, nesil)
    return deger


@router.get("/kiyas", response_model=BgKiyasListesi, responses=HATA_404_422)
def kiyas_listesi(s: OturumDep, yanit: Response, a: int = Query(..., description="bütçe (fiyat çalışması) senaryosu"),
                  b: int = Query(..., description="gerçekleşen senaryo"), tarih: date | None = None,
                  esik: Decimal = Query(ks.VARSAYILAN_ESIK, ge=0, le=1000, description="sapma eşiği, yüzde"), yenile: bool = False):
    """Ürün başına A | B | fark | fark %; `sapan` maliyet TL farkı ±esik %'yi aşan ürün."""
    return _liste(s, a, b, tarih, esik, yenile, yanit)


@router.get("/kiyas/karsi", response_model=BgKarsiSenaryoCikis, responses=HATA_404_422)
def karsi_senaryo(s: OturumDep, senaryo: int = Query(...)):
    k = ks.karsi_senaryo(s, hs.senaryo_getir(s, senaryo))
    return {"karsi": _senaryo(k) if k else None}


@router.get("/kiyas/urun/{kod}", response_model=BgKiyasUrunCikis, responses=HATA_404_422)
def kiyas_urun(s: OturumDep, kod: str, a: int = Query(...), b: int = Query(...), tarih: date | None = None):
    d = ks.urun(s, kod, a, b, tarih)
    return {**decimal_str({k: v for k, v in d.items() if k not in ("a", "b")}), "a": _senaryo(d["a"]), "b": _senaryo(d["b"])}


SUTUNLAR = [("recete_maliyeti", "Reçete maliyeti"), ("gug", "GÜG"), ("faaliyet", "Faaliyet"), ("finans", "Finans"), ("maliyet_tl", "Maliyet TL"),
            ("maliyet_usd", "Maliyet USD"), ("satis_tl", "Satış TL"), ("satis_usd", "Satış USD")]
DURUM_METNI = {"yalniz_a": "yalnız bütçede", "yalniz_b": "yalnız gerçekleşende"}


def _f(x: str | None) -> float | None:
    return None if x is None else float(x)


@router.get("/disa-aktar/butce-gerceklesen.xlsx", response_model=None,
            responses={200: {"content": {XLSX: {"schema": {"type": "string", "format": "binary"}}}, "description": "Excel dosyası (.xlsx)"}, **HATA_404_422})
def kiyas_xlsx(s: OturumDep, a: int = Query(...), b: int = Query(...), tarih: date | None = None,
               esik: Decimal = Query(ks.VARSAYILAN_ESIK, ge=0, le=1000), yalniz_sapan: bool = False):
    d = _liste(s, a, b, tarih, esik, False)
    wb = Workbook()
    ws = wb.active
    ws.title = "Bütçe vs Gerçekleşen"
    ws.append([f"A: {d['a']['ad']} ({d['a']['sezon']})", None, f"B: {d['b']['ad']} ({d['b']['sezon']})", None, f"Eşik ±%{d['esik']}", None, f"Tarih {d['tarih']}"])
    baslik = ["Kod", "Ürün", "Hat"]
    for _, e in SUTUNLAR:
        baslik += [f"{e} A", f"{e} B", f"{e} fark", f"{e} fark %"]
    ws.append(baslik + ["Durum"])
    for h in ws[2]:
        h.font = Font(bold=True)
    sari = PatternFill("solid", fgColor="FFF2CC")
    for r in d["satirlar"]:
        if yalniz_sapan and not r["sapan"]:
            continue
        satir = [r["kod"], r["ad"], r["hat"]]
        for alan, _ in SUTUNLAR:
            v = (r["alanlar"] or {}).get(alan) or {}
            satir += [_f(v.get("a")), _f(v.get("b")), _f(v.get("fark")), _f(v.get("fark_yuzde"))]
        ws.append(satir + [r["hata"] or DURUM_METNI.get(r["durum"]) or ("sapan" if r["sapan"] else "")])
        if r["sapan"]:
            for h in ws[ws.max_row]:
                h.fill = sari
    ws.freeze_panes = "D3"
    tampon = BytesIO()
    wb.save(tampon)
    tampon.seek(0)
    return StreamingResponse(tampon, media_type=XLSX, headers={"Content-Disposition": 'attachment; filename="butce-gerceklesen.xlsx"'})
