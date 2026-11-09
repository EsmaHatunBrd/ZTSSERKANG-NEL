"""Satış geçmişi dosyası okuyucu: CSV (`;` veya `,`; UTF-8/UTF-8-BOM/cp1254) ve xlsx.

Çıktı satırları `{satir_no, urun_kodu, musteri, tarih, fiyat, para_birimi, adet, hatalar}` biçimindedir;
ayrıştırılamayan hücre `None` olur ve `hatalar` listesine Türkçe mesaj eklenir (satır atlanmaz, sessizce düşmez).
Sayı biçimi: virgül varsa `1.234,56`, yoksa `1234.56` (tek nokta ondalık, birden çok nokta binlik).
"""
import csv
import io
import re
import zipfile
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from .hatalar import DogrulamaHatasi

BASLIKLAR = ("urun_kodu", "musteri", "tarih", "fiyat", "para_birimi", "adet")
MAKS_BAYT = 10 * 1024 * 1024
MAKS_SATIR = 20000
_TR = str.maketrans({"İ": "i", "I": "i", "ı": "i", "ü": "u", "Ü": "u", "ö": "o", "Ö": "o", "ç": "c", "Ç": "c", "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g"})


def _baslik_anahtari(b) -> str:
    """Büyük/küçük ve Türkçe harf duyarsız; `Ürün Kodu`, `urun_kodu`, `URUNKODU` aynı anahtar."""
    metin = str(b or "").translate(_TR).lower()
    return "".join(c for c in metin if c.isalnum())




def _tarih(v) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    metin = str(v or "").strip()
    for bicim in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(metin, bicim).date()
        except ValueError:
            continue
    return None


class BelirsizSayi(ValueError):
    """Binlik/ondalık ayırıcısı belirsiz sayı metni."""


_BINLIK = re.compile(r"^[+-]?\d{1,3}(\.\d{3})+$")   # Türkçe binlik gruplama: 1.234 / 12.345.678
_ONDALIK_NOKTA_UC = re.compile(r"^[+-]?\d+\.\d{3}$")


def _sayi(v) -> Decimal | None:
    """Kabul: `1234.56`, `1.234,56`, `1234,56`, `1.234.567` ve xlsx sayı hücreleri.
    Reddedilir (BelirsizSayi): tek noktadan sonra tam 3 hane ve virgül yok (`2.000`); virgül noktadan önce gelen (`1,234.56`).
    Ayrıştırılamayan metin için None döner."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        metin = str(v)
    else:
        metin = str(v or "").strip().replace(" ", "")
        if "," in metin and "." in metin:
            if metin.index(",") < metin.index("."):
                raise BelirsizSayi(metin)
            tam, _, kesir = metin.partition(",")
            if not _BINLIK.match(tam):   # "1.2.3,5" gibi gruplanmamış noktalar sessizce birleştirilmez
                raise BelirsizSayi(metin)
            metin = tam.replace(".", "") + "." + kesir
        elif "," in metin:
            metin = metin.replace(",", ".")
        elif _ONDALIK_NOKTA_UC.match(metin):
            raise BelirsizSayi(metin)
        elif metin.count(".") > 1:
            if not _BINLIK.match(metin):   # "1.234.56", "1.2.3", "01.02.2025" belirsiz/geçersiz
                raise BelirsizSayi(metin)
            metin = metin.replace(".", "")
    try:
        d = Decimal(metin)
    except InvalidOperation:
        return None
    return d if d.is_finite() else None


def _sayi_alani(ham: dict, alan: str, hatalar: list[str]) -> Decimal | None:
    try:
        d = _sayi(ham.get(alan))
    except BelirsizSayi:
        hatalar.append(f"{alan}: belirsiz sayı biçimi '{str(ham.get(alan)).strip()}' — binlik ayırıcı kullanmayın ya da ondalık için virgül yazın")
        return None
    if d is None:
        hatalar.append(f"{alan} sayı olmalı")
    return d


def _satir(no: int, ham: dict) -> dict:
    hatalar = []
    tarih = _tarih(ham.get("tarih"))
    if tarih is None:
        hatalar.append("tarih geçersiz (YYYY-AA-GG veya GG.AA.YYYY)")
    fiyat, adet = _sayi_alani(ham, "fiyat", hatalar), _sayi_alani(ham, "adet", hatalar)
    return {"satir_no": no, "urun_kodu": str(ham.get("urun_kodu") or "").strip(), "musteri": str(ham.get("musteri") or "").strip(),
            "tarih": tarih, "fiyat": fiyat, "para_birimi": str(ham.get("para_birimi") or "").strip().upper(), "adet": adet, "hatalar": hatalar}


def _satirlara(baslik: list, govde, basliklar: tuple = BASLIKLAR, satir_fn=None, istege_bagli: tuple = ()) -> list[dict]:
    """Başlık satırı + (satir_no, hücreler) üreteci -> çözümlenmiş satırlar. Tamamen boş satırlar atlanır.
    `basliklar`/`satir_fn`: başka bir tablo biçimi (ör. liste fiyatları) aynı okuyucuyla okunur; `istege_bagli` başlıklar eksik olabilir."""
    satir_fn = satir_fn or _satir
    esleme = {_baslik_anahtari(b): b for b in basliklar}
    sutun = {i: esleme[k] for i, b in enumerate(baslik) if (k := _baslik_anahtari(b)) in esleme}
    eksik = [b for b in basliklar if b not in sutun.values() and b not in istege_bagli]
    if eksik:
        raise DogrulamaHatasi("dosyada zorunlu başlık eksik", {"eksik_basliklar": eksik, "beklenen": list(basliklar)})
    sonuc = []
    for no, hucreler in govde:
        if no - 1 > MAKS_SATIR:   # no = dosyadaki satır (başlık 1); bellek şişmesin diye daha fazla ayrıştırılmaz
            raise DogrulamaHatasi(f"en fazla {MAKS_SATIR} satır yüklenebilir", {"en_fazla_satir": MAKS_SATIR})
        ham = {ad: (hucreler[i] if i < len(hucreler) else None) for i, ad in sutun.items()}
        if all(v is None or str(v).strip() == "" for v in ham.values()):
            continue
        sonuc.append(satir_fn(no, ham))
    if not sonuc:
        raise DogrulamaHatasi("dosyada veri satırı yok")
    return sonuc


def _csv_oku(icerik: bytes, **bicim) -> list[dict]:
    try:
        metin = icerik.decode("utf-8-sig")
    except UnicodeDecodeError:
        metin = icerik.decode("cp1254", errors="replace")
    if not metin.strip():
        raise DogrulamaHatasi("dosya boş")
    ilk = metin.splitlines()[0]
    ayirac = ";" if ilk.count(";") >= ilk.count(",") and ";" in ilk else ","
    okuyucu = csv.reader(io.StringIO(metin), delimiter=ayirac)
    baslik = next(okuyucu)
    return _satirlara(baslik, ((i, r) for i, r in enumerate(okuyucu, start=2)), **bicim)


def _xlsx_oku(icerik: bytes, **bicim) -> list[dict]:
    try:
        wb = load_workbook(io.BytesIO(icerik), read_only=True, data_only=True)
    except (zipfile.BadZipFile, InvalidFileException, KeyError):
        raise DogrulamaHatasi("dosya geçerli bir .xlsx değil")
    try:
        satirlar = wb.worksheets[0].iter_rows(values_only=True)
        baslik = next(satirlar, None)
        if baslik is None:
            raise DogrulamaHatasi("dosya boş")
        return _satirlara(list(baslik), ((i, list(r)) for i, r in enumerate(satirlar, start=2)), **bicim)
    finally:
        wb.close()


def oku(icerik: bytes, dosya_adi: str = "", **bicim) -> list[dict]:
    """`bicim`: `_satirlara` seçenekleri (basliklar, satir_fn, istege_bagli); verilmezse satış geçmişi biçimi."""
    if len(icerik) > MAKS_BAYT:
        raise DogrulamaHatasi("dosya 10 MB'den büyük")
    ad = (dosya_adi or "").lower()
    if ad.endswith(".csv") or (not ad.endswith(".xlsx") and not icerik.startswith(b"PK")):
        return _csv_oku(icerik, **bicim)
    return _xlsx_oku(icerik, **bicim)
