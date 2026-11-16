"""Onay çıktısının PDF'i: onay_ciktisi_servisi'nin kurduğu çalışma kitabı sayfa sayfa PDF'e çizilir (içerik Excel ile aynıdır).

Yöntem: fpdf2 (saf Python). Her Excel sayfası yeni bir PDF sayfasında başlar; sütun genişlikleri Excel'deki oranlarla korunur, sığmayan
geniş sayfalar yatay (A4) çizilir ve yazı küçültülür (en az 5 punto). Sayfa taşarsa tablonun başlık satırı yeni sayfada tekrarlanır.
Sayılar Excel'deki sayı biçimiyle Türkçe yazılır (1.234,56). Her sayfada üstte logo + belge adı + durum, altta "Sayfa n / N";
TASLAK çıktıda her sayfaya filigran. Son sayfada imza bloğu.

Yazı tipi: Türkçe karakterler için TrueType gerekir. Sırayla PDF_YAZI_TIPI / PDF_YAZI_TIPI_KALIN ortam değişkenleri, Windows Arial,
Linux DejaVu Sans / Liberation Sans denenir."""
from __future__ import annotations

import os
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from fpdf import FPDF
from openpyxl.utils import get_column_letter

from .hatalar import DogrulamaHatasi

LOGO = Path(__file__).resolve().parents[2] / "frontend" / "public" / "zeytursan-logo.png"
DIKEY_GENISLIK, YATAY_GENISLIK = 190.0, 277.0   # A4, 10 mm kenar boşluğu
BIRIM_MM = 1.38          # 8 puntoda bir Excel genişlik birimi ≈ 1,38 mm
EN_BUYUK_PUNTO, EN_KUCUK_PUNTO = 8.0, 5.0
UST, ALT = 20.0, 14.0    # üst bilgi ve alt bilgi için ayrılan pay (mm)
GRI = (231, 230, 230)


def _satir_y(punto: float) -> float:
    """Bir metin satırının yüksekliği (mm)."""
    return punto * 0.38 + 0.5


def _yazi_tipleri() -> tuple[str, str]:
    win = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    adaylar = [(os.environ.get("PDF_YAZI_TIPI"), os.environ.get("PDF_YAZI_TIPI_KALIN")),
               (str(win / "arial.ttf"), str(win / "arialbd.ttf")),
               ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
               ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf")]
    for normal, kalin in adaylar:
        if normal and Path(normal).is_file():
            return normal, kalin if kalin and Path(kalin).is_file() else normal
    raise DogrulamaHatasi("PDF için Türkçe karakter destekli yazı tipi bulunamadı (PDF_YAZI_TIPI ayarlayın)")


# ---------------------------------------------------------------- sayı ve metin biçimi
def _tr(d: Decimal, basamak: int, binlik: bool = True) -> str:
    q = d.quantize(Decimal(1).scaleb(-basamak), rounding=ROUND_HALF_UP)
    metin = f"{q:,.{basamak}f}" if binlik else f"{q:.{basamak}f}"
    return metin.replace(",", "X").replace(".", ",").replace("X", ".")


def bicimle(deger, bicim: str | None) -> str:
    """Hücre değerini Excel sayı biçimine göre Türkçe metne çevirir."""
    if deger is None:
        return ""
    if isinstance(deger, datetime):
        return f"{deger:%d.%m.%Y %H:%M}"
    if isinstance(deger, date):
        return f"{deger:%d.%m.%Y}"
    if isinstance(deger, bool) or not isinstance(deger, (int, float, Decimal)):
        return str(deger)
    d = Decimal(repr(deger)) if isinstance(deger, float) else Decimal(deger)
    b = bicim or "General"
    ondalik = len(b.split(".", 1)[1].rstrip("%")) if "." in b else 0
    if "%" in b:
        return "%" + _tr(d * 100, ondalik)
    if b == "General":
        if d == d.to_integral_value():
            return str(int(d))
        return _tr(d, 4).rstrip("0").rstrip(",")
    return _tr(d, ondalik, binlik="," in b)


def _renk(font) -> tuple[int, int, int] | None:
    rgb = getattr(getattr(font, "color", None), "rgb", None)
    if isinstance(rgb, str) and len(rgb) >= 6 and rgb[-6:].upper() not in ("000000",):
        try:
            return tuple(int(rgb[-6:][i:i + 2], 16) for i in (0, 2, 4))
        except ValueError:
            return None
    return None


def _dolgu(cell) -> tuple[int, int, int] | None:
    f = cell.fill
    if f is not None and f.fill_type == "solid":
        rgb = getattr(f.fgColor, "rgb", None)
        if isinstance(rgb, str) and len(rgb) >= 6:
            try:
                return tuple(int(rgb[-6:][i:i + 2], 16) for i in (0, 2, 4))
            except ValueError:
                return None
    return None


# ---------------------------------------------------------------- PDF
class _Pdf(FPDF):
    def __init__(self, c):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.c = c
        normal, kalin = _yazi_tipleri()
        self.add_font("Govde", "", normal)
        self.add_font("Govde", "B", kalin)
        self.set_auto_page_break(False)
        self.set_margins(10, UST, 10)
        self.set_title(c.belge)
        self.set_author("Zeytursan")
        self.set_creator(f"Fiyat Çalışması uygulaması ({c.surum})")

    def header(self):
        if not self.c.kesin:   # filigran
            with self.local_context(fill_opacity=0.10):
                self.set_font("Govde", "B", 96)
                self.set_text_color(200, 0, 0)
                cx, cy = self.w / 2, self.h / 2
                with self.rotation(35, cx, cy):
                    g = self.get_string_width("TASLAK")
                    self.text(cx - g / 2, cy + 12, "TASLAK")
        if LOGO.is_file():
            self.image(str(LOGO), x=10, y=6, h=9)
        self.set_font("Govde", "B", 9)
        self.set_text_color(0, 0, 0)
        self.set_xy(10, 7)
        self.cell(self.w - 20, 4, self.c.belge, align="R")
        self.set_xy(10, 11.5)
        self.set_font("Govde", "B" if not self.c.kesin else "", 8)
        self.set_text_color(*((192, 0, 0) if not self.c.kesin else (30, 107, 52)))
        self.cell(self.w - 20, 4, self.c.damga, align="R")
        self.set_text_color(0, 0, 0)
        self.set_draw_color(160, 160, 160)
        self.line(10, 16.5, self.w - 10, 16.5)
        self.set_y(UST)

    def footer(self):
        self.set_y(-10)
        self.set_font("Govde", "", 7)
        self.set_text_color(90, 90, 90)
        self.cell(0, 4, f"{self.c.kapsam}", align="L")
        self.set_x(10)
        self.cell(0, 4, f"Sayfa {self.page_no()} / {{nb}}", align="R")
        self.set_text_color(0, 0, 0)


class _SayfaCizici:
    """Bir Excel sayfasını PDF'e çizer."""

    def __init__(self, pdf: _Pdf, ws, tablolar: list[tuple[int, int]] | None, son_satir: int | None = None):
        self.pdf, self.ws = pdf, ws
        self.tablolar = tablolar
        dolu_sutun = 0
        self.son_satir = 0
        for row in ws.iter_rows():
            for cell in row:
                if cell.value not in (None, ""):
                    dolu_sutun = max(dolu_sutun, cell.column)
                    self.son_satir = max(self.son_satir, cell.row)
        if son_satir is not None:
            self.son_satir = min(self.son_satir, son_satir - 1)
        self.sutun = max(dolu_sutun, 1)
        birimler = []
        for j in range(1, self.sutun + 1):
            cd = ws.column_dimensions.get(get_column_letter(j))
            birimler.append(cd.width if cd is not None and cd.width else 9.0)
        toplam = sum(birimler)
        self.yatay = DIKEY_GENISLIK / toplam < 1.05   # dikeyde yaklaşık 6 puntonun altına düşecekse yatay sayfa
        alan = YATAY_GENISLIK if self.yatay else DIKEY_GENISLIK
        birim_mm = min(alan / toplam, BIRIM_MM)
        self.punto = max(EN_KUCUK_PUNTO, min(EN_BUYUK_PUNTO, EN_BUYUK_PUNTO * birim_mm / BIRIM_MM))
        self.satir_y = _satir_y(self.punto)
        self.genislik = [b * birim_mm for b in birimler]
        self.x = [10.0]
        for g in self.genislik[:-1]:
            self.x.append(self.x[-1] + g)
        self.birlesik: dict[tuple[int, int], int] = {}
        self.kapali: set[tuple[int, int]] = set()
        for r in ws.merged_cells.ranges:
            self.birlesik[(r.min_row, r.min_col)] = r.max_col
            for rr in range(r.min_row, r.max_row + 1):
                for cc in range(r.min_col, r.max_col + 1):
                    if (rr, cc) != (r.min_row, r.min_col):
                        self.kapali.add((rr, cc))
        fp = ws.freeze_panes
        self.tekrar_ust = 0
        if not tablolar and fp and fp != "A1":
            self.tekrar_ust = int("".join(ch for ch in fp if ch.isdigit())) - 1

    # -- bir satırın hücreleri: (x, genişlik, metin, hizalama N/R/C/L, kalın, renk, dolgu, punto)
    def _hucreler(self, r: int) -> list[tuple]:
        ws = self.ws
        out = []
        degerler = {j: ws.cell(row=r, column=j) for j in range(1, self.sutun + 1)}
        j = 1
        while j <= self.sutun:
            cell = degerler[j]
            if (r, j) in self.kapali or cell.value in (None, ""):
                if cell.value in (None, "") and _dolgu(cell) and (r, j) not in self.kapali:
                    out.append((self.x[j - 1], self.genislik[j - 1], "", "L", False, None, _dolgu(cell), self.punto))
                j += 1
                continue
            son = self.birlesik.get((r, j), j)
            sayi = isinstance(cell.value, (int, float, Decimal)) and not isinstance(cell.value, bool)
            sarma = bool(cell.alignment is not None and cell.alignment.wrap_text)
            metin_ = str(cell.value)
            sigmiyor = False
            if sarma and "\n" not in metin_:
                self.pdf.set_font("Govde", "B" if cell.font is not None and cell.font.b else "", self.punto)
                sigmiyor = self.pdf.get_string_width(metin_) > self.genislik[j - 1] - 2
            if not sayi and (not sarma or sigmiyor):   # Excel gibi: metin boş komşu hücrelere taşar (sarmalı ama sığmayan tek satır da)
                while son < self.sutun and degerler[son + 1].value in (None, "") and (r, son + 1) not in self.kapali \
                        and not _dolgu(degerler[son + 1]):
                    son += 1
            g = sum(self.genislik[j - 1:son])
            f = cell.font
            punto = self.punto
            if f is not None and f.b and f.sz and f.sz >= 12:   # başlık (köprü stili de 12 puntodur ama kalın değildir)
                punto = min(self.punto + (f.sz - 11) * 0.8 + 1.5, 14)
            yatay = cell.alignment.horizontal if cell.alignment is not None else None
            # N: sayı (sağa yaslı, sığmazsa küçültülür); R/C/L: metin hizası (sığmazsa sarılır)
            hiza = "N" if sayi and yatay != "left" else ("R" if yatay == "right" else ("C" if yatay == "center" else "L"))
            out.append((self.x[j - 1], g, bicimle(cell.value, cell.number_format), hiza, bool(f is not None and f.b), _renk(f), _dolgu(cell), punto))
            j = son + 1
        return out

    def _yukseklik(self, hucreler: list[tuple]) -> float:
        pdf = self.pdf
        h = self.satir_y
        for x, g, metin, hiza, kalin, _, _, punto in hucreler:
            if not metin:
                continue
            satir_y = _satir_y(punto)
            if "\n" not in metin:
                if hiza == "N":
                    h = max(h, satir_y)
                    continue
                pdf.set_font("Govde", "B" if kalin else "", punto)
                if pdf.get_string_width(metin) <= g - 2:   # tek satıra sığıyor: pahalı satır ölçümü gerekmez
                    h = max(h, satir_y)
                    continue
            pdf.set_font("Govde", "B" if kalin else "", punto)
            satirlar = pdf.multi_cell(max(g - 1, 2), satir_y, metin, dry_run=True, output="LINES")
            h = max(h, satir_y * len(satirlar))
        return h + 0.5

    def _ciz(self, r: int, cizgi: bool) -> None:
        pdf = self.pdf
        hucreler = self._hucreler(r)
        if not hucreler:
            pdf.set_y(pdf.get_y() + self.satir_y * 0.7)
            return
        h = self._yukseklik(hucreler)
        if pdf.get_y() + h > pdf.h - ALT:
            self._yeni_sayfa(r)
        y = pdf.get_y()
        for x, g, metin, hiza, kalin, renk, dolgu, punto in hucreler:
            if dolgu:
                pdf.set_fill_color(*dolgu)
                pdf.rect(x, y, g, h, style="F")
            if not metin:
                continue
            pdf.set_font("Govde", "B" if kalin else "", punto)
            pdf.set_text_color(*(renk or (0, 0, 0)))
            satir_y = _satir_y(punto)
            if hiza == "N" and "\n" not in metin:
                p = punto
                while pdf.get_string_width(metin) > g - 1 and p > 4:   # sığmayan sayı: küçült
                    p -= 0.5
                    pdf.set_font("Govde", "B" if kalin else "", p)
                pdf.set_xy(x, y + 0.3)
                pdf.cell(g - 0.5, satir_y, metin, align="R")
            elif "\n" not in metin and pdf.get_string_width(metin) <= g - 2:   # tek satır: hızlı yol
                pdf.set_xy(x + 0.5, y + 0.3)
                pdf.cell(g - 1, satir_y, metin, align="R" if hiza == "N" else hiza)
            else:
                pdf.set_xy(x + 0.5, y + 0.3)
                pdf.multi_cell(max(g - 1, 2), satir_y, metin, align=hiza if hiza in ("L", "C", "R") else "L")
        pdf.set_text_color(0, 0, 0)
        if cizgi:
            pdf.set_draw_color(205, 205, 205)
            pdf.line(10, y + h, 10 + sum(self.genislik), y + h)
        pdf.set_y(y + h)

    def _tablo(self, r: int) -> tuple[int, int] | None:
        for bas, son in self.tablolar or ():
            if bas <= r <= son:
                return bas, son
        return None

    def _yeni_sayfa(self, r: int) -> None:
        self.pdf.add_page(orientation="L" if self.yatay else "P")
        t = self._tablo(r)
        if t and r > t[0]:
            self._ciz(t[0], True)
        elif self.tekrar_ust and r > self.tekrar_ust:
            for rr in range(1, self.tekrar_ust + 1):
                self._ciz(rr, False)

    def ciz(self) -> None:
        self.pdf.add_page(orientation="L" if self.yatay else "P")
        for r in range(1, self.son_satir + 1):
            self._ciz(r, self._tablo(r) is not None)


def _imza_blogu(pdf: _Pdf, c) -> None:
    gerek = 12 + 3 * 16 + 10
    if pdf.get_y() + gerek > pdf.h - ALT:
        pdf.add_page(orientation="P")
    else:
        pdf.set_y(pdf.get_y() + 6)
    sol = 10
    genislik = pdf.w - 20
    pdf.set_font("Govde", "B", 11)
    pdf.set_x(sol)
    pdf.cell(genislik, 7, "İmzalar", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Govde", "", 7.5)
    pdf.set_x(sol)
    pdf.multi_cell(genislik, 4, f"Bu belgedeki değerler {c.hesap_tarihi:%d.%m.%Y} tarihinde uygulamadan alınmıştır. Durum: {c.damga}.",
                   new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    g = [genislik * x for x in (0.22, 0.34, 0.18, 0.26)]
    pdf.set_font("Govde", "B", 8.5)
    pdf.set_fill_color(*GRI)
    pdf.set_x(sol)
    for w, b in zip(g, ("Görev", "Ad soyad", "Tarih", "İmza")):
        pdf.cell(w, 7, b, border=1, fill=True)
    pdf.ln(7)
    pdf.set_font("Govde", "", 9)
    from .onay_ciktisi_servisi import IMZA_GOREVLERI
    for alan, etiket in IMZA_GOREVLERI:
        pdf.set_x(sol)
        for w, v in zip(g, (etiket, getattr(c.imzalar, alan) or "", "", "")):
            pdf.cell(w, 16, v, border=1)
        pdf.ln(16)


def pdf_uret(wb, c) -> bytes:
    """Çalışma kitabının her sayfasını sırayla PDF'e çizer; Kapak'ın imza tablosu yerine son sayfaya imza bloğu konur."""
    pdf = _Pdf(c)
    for ws in wb.worksheets:
        son = c.imza_satiri if ws.title == "Kapak" else None
        tablolar = c.tablolar.get(ws.title)
        if ws.title == "Kapak" and tablolar and son:
            tablolar = [t for t in tablolar if t[0] < son]
        _SayfaCizici(pdf, ws, tablolar, son).ciz()
    _imza_blogu(pdf, c)
    return bytes(pdf.output())
