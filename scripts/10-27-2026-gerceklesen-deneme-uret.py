"""Deneme 'gerçekleşen' Excel'i üretir: asıl fiyat çalışması kitabının kopyası, yalnız elle girilen hücreler olası gerçek değerlerle.

Gerçek gerçekleşen dosyası muhasebeden gelene kadar Faz 6 (Bütçe vs Gerçekleşen) bununla denenir. Asıl dosyaya dokunulmaz:
Excel (COM) asıl kitabı salt okunur açar, değişiklikleri yazar, yeniden hesaplar ve yeni adla kaydeder. Böylece hücre değerleri
openpyxl tahmini değil Excel'in kendi hesabıdır (parite testi bu değerlerle koşar).

Değişen hücreler (rastgele ama tohumlu, her çalıştırmada aynı):
- S.ALMA BF: F (bütçe fiyatı) ve I (revize) aynı yeni fiyata (revize yok). S bayraklı TL %3-25 artış, Z (Ziraat) %-10..+20, döviz %-5..+8.
- Ürün sayfaları: Enflasyon 0 (gerçekleşende enflasyon yok), USD/EUR kuru fiili kura, vardiya üretim adedi %-15..+10,
  reçete satırlarının ~%15'inde net miktar %-5..+8, fire oranı olan satırların ~%20'sinde fire +1 puan, elle fiyatlar %0..+20.
  Yalnız K sütunu '=I/(1-J)' formülü olan satırlarda miktar/fire değişir (elle brüt satırlar elle kalır).
- Gider Dağıtım: havuz toplamlarının tabanı %-8..+12 (çarpanlar aynı), A6 düz sayı aynı oranla.

Kullanım (iki adım):
  1) .venv/Scripts/python scripts/10-27-2026-gerceklesen-deneme-uret.py [kaynak.xlsx] [degisiklik.json]   -> değişiklik listesi
  2) PowerShell: scripts/10-27-2026-excel-hucre-yaz.ps1 -Kaynak ... -Hedef ... -Degisiklik ...           -> Excel yazar, hesaplar, kaydeder
"""
import json
import random
import re
import sys
import tempfile
from pathlib import Path
import openpyxl

KOK = Path(__file__).resolve().parent.parent
KAYNAK = KOK / "Fiyat Çalışma - 2026-2027 - Berrak.xlsx"
HEDEF = KOK / "10-27-2026-gerceklesen-deneme-2026-2027.xlsx"
PS = Path(__file__).with_name("10-27-2026-excel-hucre-yaz.ps1")
URUN_SAYFA = re.compile(r"^\d{3}( \(2\))?$")
FIILI_KUR = {"USD": 52.85, "EUR": 61.4}
GIDER_HUCRELERI = ("D4", "D13", "D18", "A20", "D27", "D38", "D49", "D60", "D64", "D67")
_TABAN = re.compile(r"^=\+?(\(?[\d.+]+\)?)(\*.*)$")


def _sayi(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _yuvarla(x: float) -> float:
    return round(x, 2) if abs(x) >= 10 else round(x, 4)


def _etiket(ws, metin: str, tam: bool = False) -> int | None:
    for r in range(1, ws.max_row + 1):
        v = ws[f"D{r}"].value
        if isinstance(v, str) and ((v.strip() == metin) if tam else v.strip().startswith(metin)):
            return r
    return None


def degisiklikler(kaynak: Path) -> list[dict]:
    rnd = random.Random(20261027)
    wb = openpyxl.load_workbook(kaynak)
    out: list[dict] = []
    yaz = lambda sayfa, hucre, deger: out.append({"s": sayfa, "h": hucre, "v": deger})

    ws = wb["S.ALMA BF"]
    for r in range(2, ws.max_row + 1):
        kod, f, zs, i = ws[f"A{r}"].value, ws[f"F{r}"].value, ws[f"G{r}"].value, ws[f"I{r}"].value
        if not kod or not _sayi(f) or f <= 0:
            continue
        taban = i if _sayi(i) and i > 0 else f   # revize varsa gerçekleşen revizeden sapar
        pb = str(ws[f"E{r}"].value or "TL").strip().upper()
        if pb != "TL":
            k = rnd.uniform(0.95, 1.08)
        elif str(zs or "").strip().upper() == "Z":
            k = rnd.uniform(0.90, 1.20)
        else:
            k = rnd.uniform(1.03, 1.25)
        yeni = _yuvarla(taban * k)
        yaz("S.ALMA BF", f"F{r}", yeni)
        if i is not None:
            yaz("S.ALMA BF", f"I{r}", yeni)

    for ad in wb.sheetnames:
        if not URUN_SAYFA.match(ad):
            continue
        w = wb[ad]
        r_enf, r_kur, r_vardiya = _etiket(w, "Enflasyon", tam=True), _etiket(w, "Döviz Kurları"), _etiket(w, "Vardiya Üretim Adedi")
        r_son = _etiket(w, "HAMMADE - YARDIMCI MALZEME MALİYETİ TOPLAMI")
        if None in (r_enf, r_kur, r_vardiya, r_son):
            continue
        if _sayi(w[f"F{r_enf}"].value):
            yaz(ad, f"F{r_enf}", 0)
        for j in range(6):
            pb = w[f"E{r_kur + j}"].value
            if pb in FIILI_KUR and _sayi(w[f"F{r_kur + j}"].value):
                yaz(ad, f"F{r_kur + j}", FIILI_KUR[pb])
        v = w[f"E{r_vardiya}"].value
        if _sayi(v) and v > 0:
            yaz(ad, f"E{r_vardiya}", round(v * rnd.uniform(0.85, 1.10)))
        for r in range(6, r_son):
            if not w[f"D{r}"].value:
                continue
            k_formul = str(w[f"K{r}"].value or "").replace(" ", "").replace("+", "")
            i, j, m = w[f"I{r}"].value, w[f"J{r}"].value, w[f"M{r}"].value
            if k_formul == f"=I{r}/(1-J{r})":
                if _sayi(i) and i > 0 and rnd.random() < 0.15:
                    yaz(ad, f"I{r}", round(i * rnd.uniform(0.95, 1.08), 8))
                if _sayi(j) and 0 < j < 0.5 and rnd.random() < 0.20:
                    yaz(ad, f"J{r}", round(j + 0.01, 4))
            if _sayi(m) and m > 0:   # elle yazılmış fiyat
                yaz(ad, f"M{r}", _yuvarla(m * rnd.uniform(1.0, 1.2)))

    g = wb["Gider Dağıtım"]
    for h in GIDER_HUCRELERI:
        f = str(g[h].value or "").replace(" ", "")
        e = _TABAN.match(f)
        if not e:
            continue
        k = rnd.uniform(0.92, 1.12)
        sayilar = re.findall(r"\d+(?:\.\d+)?", e.group(1))
        taban = "(" + "+".join(str(round(float(x) * k, 2)) for x in sayilar) + ")" if len(sayilar) > 1 else str(round(float(sayilar[0]) * k, 2))
        yaz("Gider Dağıtım", h, f"={taban}{e.group(2)}")
    if _sayi(g["A6"].value):
        yaz("Gider Dağıtım", "A6", round(g["A6"].value * rnd.uniform(0.92, 1.12), 2))
    return out


def main() -> None:
    kaynak = Path(sys.argv[1]) if len(sys.argv) > 1 else KAYNAK
    cikti = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(tempfile.gettempdir()) / "gerceklesen-degisiklik.json"
    d = degisiklikler(kaynak)
    cikti.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    print(f"{len(d)} hücre değişikliği yazıldı: {cikti}")
    print(f"Sonra: {PS.name} -Kaynak '{kaynak}' -Hedef '{HEDEF}' -Degisiklik '{cikti}'")


if __name__ == "__main__":
    main()
