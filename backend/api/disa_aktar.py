from datetime import date
from io import BytesIO
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from decimal import Decimal, DecimalException
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from sqlalchemy import select
from ..depo import modeller as m
from ..servisler import hesap_servisi as hs
from ..servisler.hatalar import ServisHatasi
from .bagimliliklar import OturumDep, SenaryoDep
from .semalar import HATA_404_422
from .urunler import dashboard_satirlari

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
router = APIRouter(tags=["disa-aktar"])

KOLONLAR = [("kod", "Kod"), ("ad", "Ürün"), ("ambalaj_hacmi", "Ambalaj Hacmi"), ("hat", "Hat"), ("recete_maliyeti", "Reçete Maliyeti"), ("gug", "GÜG"),
            ("faaliyet", "Faaliyet"), ("finans", "Finans"), ("gider_yuzdesi", "Gider %"), ("maliyet_tl", "Maliyet TL"), ("maliyet_tl_firesiz", "Maliyet TL (firesiz)"),
            ("maliyet_usd", "Maliyet USD"), ("maliyet_eur", "Maliyet EUR"), ("satis_tl", "Satış TL"), ("uretim_adedi", "Üretim Adedi"), ("uyari_sayisi", "Uyarı Sayısı"), ("hata", "Hata")]
SAYISAL = {"ambalaj_hacmi", "recete_maliyeti", "gug", "faaliyet", "finans", "gider_yuzdesi", "maliyet_tl", "maliyet_usd", "maliyet_eur", "satis_tl", "uretim_adedi",
           "maliyet_tl_firesiz"}


@router.get("/disa-aktar/urunler.xlsx", response_model=None,
            responses={200: {"content": {XLSX: {"schema": {"type": "string", "format": "binary"}}}, "description": "Excel dosyası (.xlsx)"}, **HATA_404_422})
def urunler_xlsx(s: OturumDep, sen: SenaryoDep, tarih: date | None = None, tum: bool = Query(False)):
    """Senaryo üyesi ürünler; tum=1 tüm aktif ürünler (reçetesizler hata satırı)."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Ürünler"
    ws.append([b for _, b in KOLONLAR])
    for r in dashboard_satirlari(s, sen.id, tarih, tum=tum):
        ws.append([float(r[a]) if a in SAYISAL and r[a] is not None else r[a] for a, _ in KOLONLAR])
    tampon = BytesIO()
    wb.save(tampon)
    tampon.seek(0)
    return StreamingResponse(tampon, media_type=XLSX,
                             headers={"Content-Disposition": 'attachment; filename="urunler.xlsx"'})


TK_BASLIK_1 = {"A": "Grup", "B": "S.\nNO", "C": "ÜRÜN KODU", "D": "ÜRÜN ADI", "E": "REÇETE MALİYETİ", "G": "GÜG", "H": "FAALİYET\nGİDERİ", "I": "FİNANS\nGİDERİ",
               "J": "GÜG+\nFAAL+\nFİN", "K": "GİDER\nMALİYET\n%", "L": "BİRİM MALİYET", "Q": "BİRİM MALİYET"}
TK_BASLIK_2 = {"E": "Maliyet", "F": "Maliyet\n%", "L": "TL", "M": "USD", "N": "EURO", "O": "Üretim\nAdedi", "P": "Üretim\nAdedi", "Q": "TL", "R": "USD", "S": "EURO",
               "T": "Üretim\nAdedi"}
TK_GENISLIK = {"A": 12, "B": 6, "C": 14, "D": 40, "E": 14, "F": 11, "G": 12, "H": 12, "I": 12, "J": 12, "K": 11, "L": 13, "M": 11, "N": 11, "O": 12, "P": 12,
               "Q": 13, "R": 11, "S": 11, "T": 12, "U": 3, "V": 10}
TK_PARA = "EFGHIJLMNQRS"


def _buyuk(ad: str) -> str:
    return ad.replace("i", "İ").replace("ı", "I").upper()


def _f(x: Decimal | None) -> float | None:
    return None if x is None else float(x)


@router.get("/disa-aktar/teklif-kapak.xlsx", response_model=None,
            responses={200: {"content": {XLSX: {"schema": {"type": "string", "format": "binary"}}}, "description": "Teklif Kapak düzeninde Excel dosyası (.xlsx)"}, **HATA_404_422})
def teklif_kapak_xlsx(s: OturumDep, sen: SenaryoDep, tarih: date | None = None, tum: bool = Query(False)):
    """Excel 'Teklif Kapak' sayfası düzeni. Q-T: Üretim Adetleri `hedef_uretim` ile yeniden hesap (kapasite kaydı yoksa boş). P: kaynağı belirsiz, boş."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Teklif Kapak"
    ws["B1"] = f"{sen.sezon.ad} SEZONU FİYAT ÇALIŞMALARI - {_buyuk(sen.ad)}"
    ws["G1"] = "GİDERLER"
    for h, v in TK_BASLIK_1.items():
        ws[f"{h}2"] = v
    for h, v in TK_BASLIK_2.items():
        ws[f"{h}3"] = v
    ws.merge_cells("L2:O2")
    ws.merge_cells("Q2:T2")
    for satir in (1, 2, 3):
        for h in "ABCDEFGHIJKLMNOPQRSTUV":
            ws[f"{h}{satir}"].font = Font(bold=True)
            ws[f"{h}{satir}"].alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for h, g in TK_GENISLIK.items():
        ws.column_dimensions[h].width = g
    hedefler = {k.urun_kodu: k.hedef_uretim for k in s.scalars(select(m.UretimKapasitesi).where(m.UretimKapasitesi.senaryo_id == sen.id))}
    satirlar = sorted(dashboard_satirlari(s, sen.id, tarih, tum=tum), key=lambda r: (r["hat"] or "", r["kod"]))
    for no, r in enumerate(satirlar, start=1):
        i = no + 3
        ws[f"A{i}"], ws[f"B{i}"], ws[f"C{i}"], ws[f"D{i}"] = r["hat"], no, r["kod"], r["ad"]
        if r["hata"] is not None:
            ws[f"D{i}"] = f"{r['ad']} - HATA: {r['hata']}"
            continue
        v = {a: Decimal(r[a]) if r[a] is not None else None for a in ("recete_maliyeti", "gug", "faaliyet", "finans", "maliyet_tl", "maliyet_usd", "maliyet_eur", "uretim_adedi")}
        gider = v["gug"] + v["faaliyet"] + v["finans"]
        oran = lambda x: (x / v["maliyet_tl"]) if v["maliyet_tl"] else None
        ws[f"E{i}"], ws[f"F{i}"] = _f(v["recete_maliyeti"]), _f(oran(v["recete_maliyeti"]))
        ws[f"G{i}"], ws[f"H{i}"], ws[f"I{i}"], ws[f"J{i}"], ws[f"K{i}"] = _f(v["gug"]), _f(v["faaliyet"]), _f(v["finans"]), _f(gider), _f(oran(gider))
        ws[f"L{i}"], ws[f"M{i}"], ws[f"N{i}"], ws[f"O{i}"] = _f(v["maliyet_tl"]), _f(v["maliyet_usd"]), _f(v["maliyet_eur"]), _f(v["uretim_adedi"])
        hedef = hedefler.get(r["kod"])
        if hedef is None or hedef <= 0:
            continue
        try:
            c = hs.hesapla(s, r["kod"], sen.id, tarih, override={"uretim": {"vardiya_uretim_adedi": hedef}}).sonuc
        except (ServisHatasi, KeyError, ValueError, ArithmeticError, DecimalException):   # tek ürünün hatası dosyayı düşürmez
            continue
        ws[f"Q{i}"], ws[f"R{i}"], ws[f"S{i}"] = _f(c.finansman_dahil_maliyet_tl), _f(c.doviz_maliyet.get("USD")), _f(c.doviz_maliyet.get("EUR"))
        ws[f"T{i}"] = _f(hedef)
        if v["uretim_adedi"]:
            ws[f"V{i}"] = _f(hedef / v["uretim_adedi"])
    for i in range(4, len(satirlar) + 4):
        for h in TK_PARA:
            ws[f"{h}{i}"].number_format = "#,##0.00"
        for h in "FKV":
            ws[f"{h}{i}"].number_format = "0.0%"
        for h in "OT":
            ws[f"{h}{i}"].number_format = "#,##0"
    ws.freeze_panes = "A4"
    tampon = BytesIO()
    wb.save(tampon)
    tampon.seek(0)
    return StreamingResponse(tampon, media_type=XLSX,
                             headers={"Content-Disposition": f'attachment; filename="teklif-kapak-{sen.id}.xlsx"'})
