import re
from datetime import date
from io import BytesIO
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from decimal import Decimal, DecimalException
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from sqlalchemy import select
from ..depo import modeller as m
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.hyperlink import Hyperlink
from ..servisler import aile as aile_servisi, analiz_servisi as an, hesap_servisi as hs
from ..servisler.hatalar import ServisHatasi
from .bagimliliklar import OturumDep, SenaryoDep
from .semalar import HATA_404_422, KarlilikBolgesi
from .urunler import _hesap_yaniti, dashboard_satirlari

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
router = APIRouter(tags=["disa-aktar"])

KOLONLAR = [("kod", "Kod"), ("ad", "Ürün"), ("ambalaj_hacmi", "Ambalaj Hacmi"), ("hat", "Hat"), ("recete_maliyeti", "Reçete Maliyeti"), ("gug", "GÜG"),
            ("faaliyet", "Faaliyet"), ("finans", "Finans"), ("gider_yuzdesi", "Gider %"), ("maliyet_tl", "Maliyet TL"), ("ortalama_maliyet_tl", "Ortalama Maliyet TL"),
            ("maliyet_tl_firesiz", "Maliyet TL (firesiz)"),
            ("maliyet_usd", "Maliyet USD"), ("maliyet_eur", "Maliyet EUR"), ("satis_tl", "Satış TL"), ("uretim_adedi", "Üretim Adedi"), ("uyari_sayisi", "Uyarı Sayısı"), ("hata", "Hata")]
SAYISAL = {"ambalaj_hacmi", "recete_maliyeti", "gug", "faaliyet", "finans", "gider_yuzdesi", "maliyet_tl", "maliyet_usd", "maliyet_eur", "satis_tl", "uretim_adedi",
           "maliyet_tl_firesiz", "ortalama_maliyet_tl"}


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
    teklif_kapak_sayfasi(ws, s, sen, tarih, tum)
    tampon = BytesIO()
    wb.save(tampon)
    tampon.seek(0)
    return StreamingResponse(tampon, media_type=XLSX,
                             headers={"Content-Disposition": f'attachment; filename="teklif-kapak-{sen.id}.xlsx"'})


def teklif_kapak_sayfasi(ws, s, sen, tarih: date | None = None, tum: bool = False, kodlar: set[str] | None = None) -> int:
    """'Teklif Kapak' düzenini verilen sayfaya yazar (onay çıktısı da kullanır). kodlar: yalnız bu ürünler (None: hepsi). Döner: ürün satırı sayısı."""
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
    satirlar = sorted((r for r in dashboard_satirlari(s, sen.id, tarih, tum=tum) if kodlar is None or r["kod"] in kodlar),
                      key=lambda r: (r["hat"] or "", r["kod"]))
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
    return len(satirlar)


# ---------------------------------------------------------------- Analiz sonuçları (hedef fiyat, kârlılık, kur riski)
BOLGE_ETIKETI = {"yuksek_adet_dusuk_marj": "Fiyatı gözden geçir", "yuksek_adet_yuksek_marj": "Yıldız",
                 "dusuk_adet_yuksek_marj": "Büyütülebilir", "dusuk_adet_dusuk_marj": "Sorgula"}
FIYAT_KAYNAGI = {"satis_gecmisi": "Geçen yıl satış", "hesap": "Çalışma hesabı"}
ADET_NOTU = "Yıllık adet: geçen yılın satış adedi"
BICIM = {"yuzde": "0.0%", "tl": "#,##0.00", "adet": "#,##0"}
GENISLIK = {"metin": 14, "urun": 45, "hata": 40, "yuzde": 12, "tl": 16, "adet": 12}
XLSX_YANIT = {200: {"content": {XLSX: {"schema": {"type": "string", "format": "binary"}}}, "description": "Excel dosyası (.xlsx)"}, **HATA_404_422}


def _d(x) -> float | None:
    """Servis çıktısındaki decimal metni (ya da sayıyı) Excel'e yazılacak sayıya çevirir; boşsa None (boş hücre)."""
    return None if x is None or x == "" else float(Decimal(str(x)))


def _tr_sayi(x, basamak: int = 2) -> str:
    """Parametre satırı için Türkçe sayı: 1.234,5 (sondaki ondalık sıfırlar atılır)."""
    if x is None:
        return "-"
    q = Decimal(str(x)).quantize(Decimal(1).scaleb(-basamak))
    tam, _, ond = f"{q:,.{basamak}f}".partition(".")
    ond = ond.rstrip("0")
    return tam.replace(",", ".") + ("," + ond if ond else "")


def _tr_yuzde(x) -> str:
    return "-" if x is None else "%" + _tr_sayi(Decimal(str(x)) * 100, 1)


def _hucre(ws, satir: int, sutun: int, deger, tur: str):
    """tur: metin | urun | hata (olduğu gibi) ya da yuzde | tl | adet (Decimal metninden float + sayı biçimi)."""
    if tur in BICIM:
        c = ws.cell(row=satir, column=sutun, value=_d(deger))
        c.number_format = BICIM[tur]
    else:
        c = ws.cell(row=satir, column=sutun, value=None if deger == "" else deger)
    return c


def _analiz_excel(analiz: str, sen, parametreler: str, kolonlar: list[tuple[str, str, str]], satirlar: list[dict],
                  ozet: list[tuple[str, object, str]], ek_tablo: tuple[list[tuple[str, str, str]], list[dict]] | None = None) -> BytesIO:
    """Ortak analiz Excel düzeni. 1. satır başlık, 2. satır parametreler, 4. satır sütun başlıkları, veri 5. satırdan.
    kolonlar: (alan, başlık, tür). İkinci sayfa "Özet": (etiket, değer, tür) satırları; ek_tablo (kolonlar, satırlar) altına tablo olarak."""
    kalin = Font(bold=True)
    wb = Workbook()
    ws = wb.active
    ws.title = analiz[:31]
    ws["A1"] = f"{analiz} — {sen.ad} — {date.today():%d.%m.%Y}"
    ws["A1"].font = Font(bold=True, size=12)
    ws["A2"] = parametreler
    for j, (_, baslik, tur) in enumerate(kolonlar, start=1):
        h = ws.cell(row=4, column=j, value=baslik)
        h.font = kalin
        h.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[get_column_letter(j)].width = GENISLIK[tur]
    for i, r in enumerate(satirlar, start=5):
        for j, (alan, _, tur) in enumerate(kolonlar, start=1):
            _hucre(ws, i, j, r.get(alan), tur)
    ws.freeze_panes = "A5"
    ws.auto_filter.ref = f"A4:{get_column_letter(len(kolonlar))}{len(satirlar) + 4}"

    oz = wb.create_sheet("Özet")
    oz["A1"] = f"{analiz} — Özet — {sen.ad}"
    oz["A1"].font = Font(bold=True, size=12)
    oz["A2"] = parametreler
    for h, g in (("A", 42), ("B", 18), ("C", 12)):
        oz.column_dimensions[h].width = g
    i = 4
    for etiket, deger, tur in ozet:
        oz.cell(row=i, column=1, value=etiket)
        _hucre(oz, i, 2, deger, tur)
        i += 1
    if ek_tablo:
        ek_kolonlar, ek_satirlar = ek_tablo
        i += 1
        for j, (_, baslik, _) in enumerate(ek_kolonlar, start=1):
            oz.cell(row=i, column=j, value=baslik).font = kalin
        for r in ek_satirlar:
            i += 1
            for j, (alan, _, tur) in enumerate(ek_kolonlar, start=1):
                _hucre(oz, i, j, r.get(alan), tur)
    tampon = BytesIO()
    wb.save(tampon)
    tampon.seek(0)
    return tampon


def _excel_yaniti(tampon: BytesIO, dosya: str) -> StreamingResponse:
    return StreamingResponse(tampon, media_type=XLSX, headers={"Content-Disposition": f'attachment; filename="{dosya}"'})


def _bolge_notu(bolge: str | None) -> str:
    return f" · Bölge: {BOLGE_ETIKETI[bolge]}" if bolge else ""


HF_KOLONLAR = [("kod", "Kod", "metin"), ("ad", "Ürün", "urun"), ("aile", "Aile", "metin"), ("bolge_etiketi", "Bölge", "metin"),
               ("maliyet", "Maliyet TL", "tl"), ("gecen_yil_fiyat", "Geçen Yıl Fiyatı TL", "tl"), ("mevcut_marj", "Mevcut Marj", "yuzde"),
               ("hedef_fiyat", "Hedef Fiyat TL", "tl"), ("gereken_zam", "Gereken Zam", "yuzde"),
               ("liste_fiyati_yurtici", "Liste Fiyatı Yurtiçi TL", "tl"), ("liste_fiyati_yurtdisi", "Liste Fiyatı Yurtdışı TL", "tl"),
               ("adet", "Yıllık Adet", "adet"), ("yillik_ek_gelir", "Yıllık Ek Gelir TL", "tl"), ("hata", "Hata", "hata")]


@router.get("/disa-aktar/hedef-fiyat.xlsx", response_model=None, responses=XLSX_YANIT)
def hedef_fiyat_xlsx(s: OturumDep, sen: SenaryoDep,
                     marj: Decimal | None = Query(None, description="Hedef marj (0.15 = %15); boşsa marj eşiği"),
                     bolge: KarlilikBolgesi | None = Query(None, description="Yalnız bu kârlılık bölgesi"),
                     yalniz_zam: bool = Query(False, description="Yalnız gereken zamı > 0 olanlar")):
    """Marjı koruyan fiyat analizini Excel olarak indirir (bölge / yalnız zam gerekenler süzmesiyle). Özet sayfası süzmeden bağımsızdır."""
    d = an.hedef_fiyat(s, sen.id, marj)
    satirlar = [{**r, "bolge_etiketi": BOLGE_ETIKETI.get(r["bolge"])} for r in d["kayitlar"]
                if (bolge is None or r["bolge"] == bolge) and (not yalniz_zam or (r["gereken_zam"] is not None and Decimal(r["gereken_zam"]) > 0))]
    o = d["ozet"]
    parametre = (f"Hedef marj: {_tr_yuzde(d['marj'])} · Liste böleni yurtiçi: {_tr_sayi(d['bolen_yurtici'], 4)} · "
                 f"Liste böleni yurtdışı: {_tr_sayi(d['bolen_yurtdisi'], 4)} · Yuvarlama: en yakın {_tr_sayi(d['yuvarlama'])} TL · KDV hariç · "
                 f"Liste fiyatı yalnız Berrak ürünlerinde · {ADET_NOTU}") + _bolge_notu(bolge)
    if yalniz_zam:
        parametre += " · Yalnız zam gerekenler"
    ozet = [("Ürün sayısı", o["urun_sayisi"], "adet"), ("Zam gereken ürün", o["zam_gereken"], "adet"),
            ("Geçen yıl fiyatı olmayan", o["fiyatsiz"], "adet"), ("Hatalı", o["hatali"], "adet"),
            ("Ortalama gereken zam (ciro ağırlıklı) %", o["ort_zam"], "yuzde"), ("Yıllık ek gelir TL", o["yillik_ek_gelir"], "tl")]
    return _excel_yaniti(_analiz_excel("Marjı Koruyan Fiyat", sen, parametre, HF_KOLONLAR, satirlar, ozet), "marji-koruyan-fiyat.xlsx")


KH_KOLONLAR = [("kod", "Kod", "metin"), ("ad", "Ürün", "urun"), ("aile", "Aile", "metin"), ("bolge_etiketi", "Bölge", "metin"),
               ("adet", "Yıllık Adet", "adet"), ("maliyet", "Maliyet TL", "tl"), ("satis_fiyati", "Satış Fiyatı TL", "tl"),
               ("fiyat_kaynagi_etiketi", "Fiyat Kaynağı", "metin"), ("marj", "Marj", "yuzde"), ("yillik_kar", "Yıllık Kâr TL", "tl"), ("hata", "Hata", "hata")]


@router.get("/disa-aktar/karlilik.xlsx", response_model=None, responses=XLSX_YANIT)
def karlilik_xlsx(s: OturumDep, sen: SenaryoDep, bolge: KarlilikBolgesi | None = Query(None, description="Yalnız bu kârlılık bölgesi")):
    """Kârlılık haritasını Excel olarak indirir. Özet sayfası süzmeden bağımsızdır."""
    d = an.karlilik(s, sen.id)
    satirlar = [{**r, "bolge_etiketi": BOLGE_ETIKETI.get(r["bolge"]), "fiyat_kaynagi_etiketi": FIYAT_KAYNAGI.get(r["fiyat_kaynagi"])}
                for r in d["kayitlar"] if bolge is None or r["bolge"] == bolge]
    o = d["ozet"]
    parametre = f"Marj eşiği: {_tr_yuzde(d['esik_marj'])} · Adet eşiği (medyan): {_tr_sayi(d['esik_adet'], 0)} · {ADET_NOTU}" + _bolge_notu(bolge)
    ozet = [("Ürün sayısı", len(d["kayitlar"]), "adet")] + [(BOLGE_ETIKETI[b], o[b], "adet") for b in an.KARLILIK_BOLGELERI]
    ozet += [("Yıllık adedi olmayan", o["adetsiz"], "adet"), ("Hatalı", o["hatali"], "adet"),
             ("Marj eşiği %", d["esik_marj"], "yuzde"), ("Adet eşiği (medyan)", d["esik_adet"], "adet")]
    return _excel_yaniti(_analiz_excel("Kârlılık Haritası", sen, parametre, KH_KOLONLAR, satirlar, ozet), "karlilik-haritasi.xlsx")


KUR_KOLONLAR = [("kod", "Kod", "metin"), ("ad", "Ürün", "urun"), ("hat", "Hat", "metin"), ("maliyet", "Maliyet TL", "tl"),
                ("doviz_payi", "Döviz Payı", "yuzde"), ("usd_payi", "USD Payı", "yuzde"), ("eur_payi", "EUR Payı", "yuzde"),
                ("birim_etki", "Birim Etki TL", "tl"), ("yeni_maliyet", "Yeni Maliyet TL", "tl"), ("yillik_adet", "Yıllık Adet", "adet"),
                ("yillik_etki", "Yıllık Etki TL", "tl"), ("hata", "Hata", "hata")]
KUR_PB_KOLONLAR = [("para_birimi", "Para Birimi", "metin"), ("yillik_etki", "Yıllık Etki TL", "tl"), ("pay", "Pay", "yuzde")]


@router.get("/disa-aktar/kur-riski.xlsx", response_model=None, responses=XLSX_YANIT)
def kur_riski_xlsx(s: OturumDep, sen: SenaryoDep, oran: Decimal = Query(Decimal("0.10"), description="Kurlardaki artış (0.1 = %10)")):
    """Kur riski analizini Excel olarak indirir; Özet sayfasında para birimi kırılımı."""
    d = an.kur_riski(s, sen.id, oran)
    o = d["ozet"]
    kurlar = "; ".join(f"{pb} {_tr_sayi(v, 4)}" for pb, v in d["kurlar"].items()) or "-"
    parametre = f"Kur artışı: {_tr_yuzde(d['oran'])} · Kurlar: {kurlar} · {ADET_NOTU}"
    ozet = [("Ürün sayısı", o["urun_sayisi"], "adet"), ("Ortalama döviz payı %", o["doviz_payi_ort"], "yuzde"),
            ("Yıllık maliyet TL", o["yillik_maliyet"], "tl"), ("Yıllık etki TL", o["yillik_etki"], "tl"),
            ("Yıllık adedi olmayan", o["adetsiz_urun"], "adet"), ("Hatalı", o["hatali"], "adet")]
    tampon = _analiz_excel("Kur Riski", sen, parametre, KUR_KOLONLAR, d["kayitlar"], ozet, (KUR_PB_KOLONLAR, d["para_birimleri"]))
    return _excel_yaniti(tampon, "kur-riski.xlsx")


# ---------------------------------------------------------------- Toplu maliyet kartları (ürün başına sayfa)
B_TUTAR, B_FIYAT, B_ORAN, B_ADET = "#,##0.00", "#,##0.0000", "0.00%", "#,##0"
KART_SUTUNLARI = [("Satır", 8), ("Kod", 16), ("Cinsi", 46), ("Miktar", 13), ("Fire %", 9), ("Brüt", 13), ("Birim", 8), ("Birim fiyat", 14), ("Döviz", 8),
                  ("Tutar (firesiz)", 16), ("Tutar (fireli)", 16)]
GIDER_SUTUNLARI = {1: "Grup", 3: "Gider kalemi", 4: "Miktar", 6: "Brüt", 7: "Birim", 8: "Birim fiyat", 10: "Tutar (firesiz)", 11: "Tutar (fireli)"}
GIDER_GRUBU = {"direkt_iscilik": "Direkt işçilik", "gug": "GÜG", "diger": "Diğer giderler", "finansman": "Finansman"}
KART_OZET_SUTUNLARI = [("Kod", 16), ("Ürün", 46), ("Hat", 12), ("Ambalaj", 12), ("Malzeme toplamı", 16), ("Üretim gideri", 15), ("Faaliyet gideri", 15),
                       ("Finansman", 13), ("Birim maliyet TL", 17), ("Satış TL", 14), ("Satış USD", 12), ("Satış EUR", 12), ("Uyarı sayısı", 12),
                       ("Sayfa", 18), ("Durum", 50)]
BIRIM_MALIYET_ETIKETI = "Finansman dahil maliyet TL"
# (etiket, görünüm alanı, sayı biçimi, vurgulu): ürün ekranındaki Toplamlar kartıyla aynı satırlar ve sıra.
KART_TOPLAMLARI = [("Hammadde-yardımcı malzeme toplamı", "malzeme", B_TUTAR, False), ("Direkt işçilik", "direkt_iscilik", B_TUTAR, False),
                   ("GÜG", "gug", B_TUTAR, False), ("Gider toplamı", "uretim_gideri", B_TUTAR, False),
                   ("Toplam birim maliyet", "_toplam_birim", B_TUTAR, True), ("Diğer giderler", "diger", B_TUTAR, False),
                   ("Giydirilmiş maliyet", "giydirilmis", B_TUTAR, False), ("Finansman (TL)", "finansman_tl", B_TUTAR, False),
                   (BIRIM_MALIYET_ETIKETI, "maliyet_tl", B_TUTAR, True),
                   ("Finansman dahil maliyet USD", "maliyet_usd", B_FIYAT, False), ("Finansman dahil maliyet EUR", "maliyet_eur", B_FIYAT, False),
                   ("Finansman dahil maliyet GBP", "maliyet_gbp", B_FIYAT, False), ("Finansman dahil maliyet ZAR", "maliyet_zar", B_FIYAT, False)]
KART_SATISLARI = [("Satış fiyatı TL", "satis_tl", B_TUTAR), ("Satış fiyatı USD", "satis_usd", B_FIYAT), ("Satış fiyatı EUR", "satis_eur", B_FIYAT),
                  ("Satış fiyatı GBP", "satis_gbp", B_FIYAT), ("Satış fiyatı ZAR", "satis_zar", B_FIYAT),
                  ("Süzme kg birim fiyatı TL", "suzme_kg_tl", B_TUTAR)]
ISTEGE_BAGLI = {"maliyet_gbp", "maliyet_zar", "satis_gbp", "satis_zar"}   # yalnız değeri olan üründe yazılır (ürün ekranıyla aynı)
_SAYFA_ADI_YASAK = re.compile(r"[\[\]:*?/\\]")
_DOSYA_ADI_YASAK = re.compile(r"[^A-Za-z0-9-]+")
KALIN = Font(bold=True)


def sayfa_adi(kod: str, kullanilan: set[str]) -> str:
    """Excel sayfa adı kuralları: en çok 31 karakter, [ ] : * ? / \\ yok, baş/sonda kesme işareti yok, boş olmaz, büyük/küçük harf
    ayırmadan benzersiz. Çakışmada sonuna " (2)", " (3)" eklenir. `kullanilan` (casefold) güncellenir."""
    taban = _SAYFA_ADI_YASAK.sub("-", kod or "").strip().strip("'").strip()[:31] or "Ürün"
    ad, n = taban, 1
    while ad.casefold() in kullanilan:
        n += 1
        ek = f" ({n})"
        ad = taban[:31 - len(ek)] + ek
    kullanilan.add(ad.casefold())
    return ad


def _ic_baglanti(hucre, sayfa: str, metin: str):
    """Çalışma kitabı içindeki sayfaya köprü."""
    hucre.hyperlink = Hyperlink(ref=hucre.coordinate, location="'" + sayfa.replace("'", "''") + "'!A1", display=metin)
    hucre.value = metin
    hucre.style = "Hyperlink"


def _sayi(ws, satir: int, sutun: int, deger, bicim: str):
    """Decimal metnini SAYI hücresi olarak yazar (boşsa boş hücre)."""
    c = ws.cell(row=satir, column=sutun, value=_d(deger))
    c.number_format = bicim
    return c


def _baslik_satiri(ws, satir: int, basliklar: dict[int, str]):
    for j, b in basliklar.items():
        h = ws.cell(row=satir, column=j, value=b)
        h.font = KALIN
        h.alignment = Alignment(wrap_text=True, vertical="center", horizontal="left" if j <= 3 or j in (7, 9) else "right")


def _oran_notu(o) -> str:
    return "" if o is None else f" ({_tr_yuzde(o)})"


def _kart_sayfasi(ws, u, c, g: dict, sen, t: date, not_: str):
    """Tek ürünün maliyet kartı. g: ürün ekranının görünümü (`urunler._hesap_yaniti`); c: aynı hesabın çıktısı (firesiz satır tutarları için).
    Satır 1-3 başlık bloğu, 4 reçete sütun başlıkları (dondurulmuş), sonra reçete, gider kalemleri, toplamlar, satış ve teklif fiyatları."""
    ws["A1"] = u.ad
    ws["A1"].font = Font(bold=True, size=13)
    _ic_baglanti(ws["K1"], "Özet", "Özet'e dön")
    ws["A2"] = f"Kod: {u.kod} · Çalışma: {sen.sezon.ad} — {sen.ad} · Hesap tarihi: {t:%d.%m.%Y}"
    ws["A3"] = not_
    ws["A3"].font = Font(italic=True)
    for j, (_, genislik) in enumerate(KART_SUTUNLARI, start=1):
        ws.column_dimensions[get_column_letter(j)].width = genislik
    _baslik_satiri(ws, 4, {j: b for j, (b, _) in enumerate(KART_SUTUNLARI, start=1)})
    ws.freeze_panes = "A5"
    firesiz = c.sonuc.firesiz.satirlar if c.sonuc.firesiz is not None else None
    i = 4
    giderler = []
    for sira, r in enumerate(g["satirlar"]):
        tutar_firesiz = firesiz[sira].tutar if firesiz is not None and sira < len(firesiz) else r.get("tutar_firesiz")
        if r["grup"] != "malzeme":
            giderler.append((r, tutar_firesiz))
            continue
        i += 1
        ws.cell(row=i, column=1, value=r["sira"])
        ws.cell(row=i, column=2, value=r["kod"] or None)
        ws.cell(row=i, column=3, value=r["kalem"])
        _sayi(ws, i, 4, r["miktar"], B_FIYAT)
        _sayi(ws, i, 5, r["fire_orani"], B_ORAN)
        _sayi(ws, i, 6, r["brut_miktar"], B_FIYAT)
        ws.cell(row=i, column=7, value=r["birim"])
        _sayi(ws, i, 8, r["birim_fiyat"], B_FIYAT)
        ws.cell(row=i, column=9, value=r["doviz"])
        _sayi(ws, i, 10, tutar_firesiz, B_TUTAR)
        _sayi(ws, i, 11, r["tutar"], B_TUTAR)
    tp, tf = g["toplamlar"], g["toplamlar_firesiz"] or {}
    i += 1
    ws.cell(row=i, column=3, value="Malzeme toplamı").font = KALIN
    _sayi(ws, i, 10, tf.get("malzeme"), B_TUTAR).font = KALIN
    _sayi(ws, i, 11, tp["malzeme"], B_TUTAR).font = KALIN

    i += 2
    ws.cell(row=i, column=1, value="Gider kalemleri").font = Font(bold=True, size=12)
    i += 1
    _baslik_satiri(ws, i, GIDER_SUTUNLARI)
    for r, tutar_firesiz in giderler:
        i += 1
        ws.cell(row=i, column=1, value=GIDER_GRUBU.get(r["grup"], r["grup"]))
        ws.cell(row=i, column=3, value=r["kalem"])
        _sayi(ws, i, 4, r["miktar"], B_FIYAT)
        _sayi(ws, i, 6, r["brut_miktar"], B_FIYAT)
        ws.cell(row=i, column=7, value=r["birim"])
        _sayi(ws, i, 8, r["birim_fiyat"], B_FIYAT)
        _sayi(ws, i, 10, tutar_firesiz, B_TUTAR)
        _sayi(ws, i, 11, r["tutar"], B_TUTAR)

    def toplam_birim(x: dict):
        return None if not x else Decimal(x["malzeme"]) + Decimal(x["uretim_gideri"])

    i += 2
    ws.cell(row=i, column=1, value="Toplamlar").font = Font(bold=True, size=12)
    _baslik_satiri(ws, i, {10: "Firesiz", 11: "Fireli"})
    for etiket, alan, bicim, vurgulu in KART_TOPLAMLARI:
        fireli, firesiz_d = (toplam_birim(tp), toplam_birim(tf)) if alan == "_toplam_birim" else (tp.get(alan), tf.get(alan))
        if alan in ISTEGE_BAGLI and fireli is None and firesiz_d is None:
            continue
        i += 1
        e = ws.cell(row=i, column=3, value=etiket)
        a, b = _sayi(ws, i, 10, firesiz_d, bicim), _sayi(ws, i, 11, fireli, bicim)
        if vurgulu:
            e.font = a.font = b.font = KALIN

    fy, ff = g["fiyatlar"], g["fiyatlar_firesiz"] or {}
    i += 2
    ws.cell(row=i, column=1, value="Satış fiyatı ve teklif fiyatları").font = Font(bold=True, size=12)
    _baslik_satiri(ws, i, {10: "Firesiz", 11: "Fireli"})
    for etiket, alan, bicim in KART_SATISLARI:
        if alan in ISTEGE_BAGLI and fy.get(alan) is None and ff.get(alan) is None:
            continue
        i += 1
        ws.cell(row=i, column=3, value=etiket + (_oran_notu(fy.get("satis_kar_orani")) if alan.startswith("satis_") else ""))
        _sayi(ws, i, 10, ff.get(alan), bicim)
        _sayi(ws, i, 11, fy.get(alan), bicim)
    oranlar = fy.get("teklif_kar_oranlari") or []
    tek, tek_f = fy.get("teklifler_usd") or [], ff.get("teklifler_usd") or []
    for n in range(max(len(tek), len(tek_f))):
        i += 1
        ws.cell(row=i, column=3, value=f"{n + 1}. teklif USD/adet" + _oran_notu(oranlar[n] if n < len(oranlar) else None))
        _sayi(ws, i, 10, tek_f[n] if n < len(tek_f) else None, B_FIYAT)
        _sayi(ws, i, 11, tek[n] if n < len(tek) else None, B_FIYAT)
    for n, uyari in enumerate(g["uyarilar"]):
        if n == 0:
            i += 2
            ws.cell(row=i, column=1, value="Uyarılar").font = Font(bold=True, size=12)
        i += 1
        ws.cell(row=i, column=1, value=uyari)


def maliyet_kartlari_kitabi(s, sen, t: date) -> BytesIO:
    """Tüm senaryo üyesi ürünlerin maliyet kartları tek kitapta: "Özet" + hesaplanan ürün başına bir sayfa. Tek toplu hesap
    (`toplu_hesapla`); ürün sayfası ürün ekranının görünümünden (`_hesap_yaniti`) yazılır: yeni hesap kuralı yok, formül yok."""
    wb = Workbook()
    oz = wb.active
    oz.title = "Özet"
    maliyet_kartlari_sayfalari(wb, oz, s, sen, t)
    tampon = BytesIO()
    wb.save(tampon)
    tampon.seek(0)
    return tampon


def maliyet_kartlari_sayfalari(wb, oz, s, sen, t: date, kodlar: set[str] | None = None, kullanilan: set[str] | None = None) -> list:
    """Özet sayfasını (`oz`, adı "Özet" olmalı: kartlardaki geri dönüş köprüsü) ve hesaplanan her ürünün kart sayfasını `wb`'ye yazar
    (onay çıktısı da kullanır). kodlar: yalnız bu ürünler (None: senaryo üyelerinin hepsi). kullanilan: başka sayfa adlarıyla çakışmayı
    önlemek için dolu verilebilir (casefold). Döner: (kod, hesap ya da hata) listesi."""
    hesaplar = [(kod, c) for kod, c in hs.toplu_hesapla(s, sen.id, t) if kodlar is None or kod in kodlar]
    urunler = {u.kod: u for u in hs.urunler(s, aktif=False)}
    not_ = f"Değerler {t:%d.%m.%Y} itibarıyla uygulamadan alınmıştır (formül yoktur)."
    oz["A1"] = f"Maliyet kartları — {sen.sezon.ad} — {sen.ad}"
    oz["A1"].font = Font(bold=True, size=13)
    oz["A2"] = not_
    oz["A2"].font = Font(italic=True)
    for j, (b, genislik) in enumerate(KART_OZET_SUTUNLARI, start=1):
        h = oz.cell(row=4, column=j, value=b)
        h.font = KALIN
        h.alignment = Alignment(wrap_text=True, vertical="center")
        oz.column_dimensions[get_column_letter(j)].width = genislik
    oz.freeze_panes = "A5"
    kullanilan = {"özet"} if kullanilan is None else kullanilan | {"özet"}
    for i, (kod, c) in enumerate(hesaplar, start=5):
        u = urunler[kod]
        oz.cell(row=i, column=1, value=kod)
        oz.cell(row=i, column=2, value=u.ad)
        oz.cell(row=i, column=3, value=u.hat)
        oz.cell(row=i, column=4, value=aile_servisi.ambalaj_etiket(u.ad) or str(u.ambalaj_hacmi))
        if isinstance(c, Exception):
            oz.cell(row=i, column=15, value=f"hesaplanamadı: {getattr(c, 'mesaj', None) or c}")
            continue
        g = _hesap_yaniti(c, kod, sen.id, t)
        tp, fy = g["toplamlar"], g["fiyatlar"]
        for j, deger in enumerate((tp["malzeme"], tp["uretim_gideri"], tp["diger"], tp["finansman_tl"], tp["maliyet_tl"], fy["satis_tl"]), start=5):
            _sayi(oz, i, j, deger, B_TUTAR)
        _sayi(oz, i, 11, fy["satis_usd"], B_FIYAT)
        _sayi(oz, i, 12, fy["satis_eur"], B_FIYAT)
        oz.cell(row=i, column=13, value=len(g["uyarilar"])).number_format = B_ADET
        ad = sayfa_adi(kod, kullanilan)
        _ic_baglanti(oz.cell(row=i, column=14), ad, ad)
        _kart_sayfasi(wb.create_sheet(ad), u, c, g, sen, t, not_)
    oz.auto_filter.ref = f"A4:{get_column_letter(len(KART_OZET_SUTUNLARI))}{max(len(hesaplar), 1) + 4}"
    return hesaplar


@router.get("/disa-aktar/maliyet-kartlari", response_model=None, responses=XLSX_YANIT)
def maliyet_kartlari_xlsx(s: OturumDep, sen: SenaryoDep, tarih: date | None = None):
    """Tüm ürünlerin maliyet kartları tek Excel dosyasında: ilk sayfa "Özet" (ürün başına satır + sayfa köprüsü), sonra hesaplanan her
    ürün için bir sayfa (reçete, gider kalemleri, toplamlar, satış ve teklif fiyatları). Hesaplanamayan ürün yalnız Özet'te görünür.
    Değerler sayı olarak yazılır; formül yoktur. Yalnız okur (her rol indirebilir)."""
    sezon = _DOSYA_ADI_YASAK.sub("-", sen.sezon.ad).strip("-") or "sezon"
    return _excel_yaniti(maliyet_kartlari_kitabi(s, sen, tarih or date.today()), f"maliyet-kartlari-{sezon}-{date.today():%m-%d-%Y}.xlsx")


# ---------------------------------------------------------------- Önemli malzemeler (80/20)
BICIM.update(fiyat=B_FIYAT, miktar=B_TUTAR, puan="0.00")
GENISLIK.update(fiyat=14, miktar=16, puan=12)
OM_KOLONLAR = [("sira", "Sıra", "adet"), ("kod", "Kod", "metin"), ("ad", "Malzeme", "urun"), ("tip", "Tip", "metin"), ("birim", "Birim", "metin"),
               ("para_birimi", "Para Birimi", "metin"), ("birim_fiyat", "Birim Fiyat", "fiyat"), ("yillik_miktar", "Yıllık Miktar", "miktar"),
               ("yillik_tutar_tl", "Yıllık Tutar TL", "tl"), ("pay_yuzde", "Pay %", "puan"), ("kumulatif_yuzde", "Kümülatif %", "puan"),
               ("esik_etiketi", "Eşik İçinde", "metin"), ("kullanan_urun_sayisi", "Kullanan Ürün", "adet")]


@router.get("/disa-aktar/onemli-malzemeler", response_model=None, responses=XLSX_YANIT)
def onemli_malzemeler_xlsx(s: OturumDep, sen: SenaryoDep, tarih: date | None = None,
                           esik: Decimal = Query(an.VARSAYILAN_ONEM_ESIGI, description="Kümülatif pay eşiği (0.8 = %80)")):
    """Önemli malzemeler (80/20) analizini Excel olarak indirir; sayılar sayı tipindedir (Pay % / Kümülatif % yüzde puanı)."""
    d = an.onemli_malzemeler(s, sen.id, esik, tarih)
    satirlar = [{**r, "esik_etiketi": "Evet" if r["esik_icinde"] else None} for r in d["satirlar"]]
    parametre = (f"Eşik: {_tr_yuzde(d['esik'])} · Yıllık tutar = Σ (yıllık adet × üründeki fireli malzeme tutarı) · {ADET_NOTU} · "
                 f"Birim fiyat malzemenin kendi para birimindedir")
    ozet = [("Malzeme sayısı", len(satirlar), "adet"), (f"Toplam tutarın {_tr_yuzde(d['esik'])} kadarını oluşturan malzeme", d["esik_icindeki_sayi"], "adet"),
            ("Toplam yıllık malzeme tutarı TL", d["toplam_tutar_tl"], "tl"), ("Eşik %", d["esik"], "yuzde"),
            ("Yıllık adedi olmayan ürün (hesaba girmedi)", d["adetsiz_urun"], "adet"), ("Hesaplanamayan ürün (hesaba girmedi)", d["hatali_urun"], "adet")]
    return _excel_yaniti(_analiz_excel("Önemli Malzemeler", sen, parametre, OM_KOLONLAR, satirlar, ozet), "onemli-malzemeler.xlsx")
