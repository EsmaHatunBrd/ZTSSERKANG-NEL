# scripts/excel_parite_raporu.py
r"""Motor sonuçlarını Excel'deki değerlerle sayfa sayfa karşılaştırır, farkları raporlar.
Kullanım: .\.venv\Scripts\python scripts/excel_parite_raporu.py ["Fiyat Çalışma - 2026-2027 - Berrak.xlsx"]"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fiyat_motoru.parite import karsilastir


def main():
    yol = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("Fiyat Çalışma - 2026-2027 - Berrak.xlsx")
    farklar, uyarilar = karsilastir(yol)
    sayfalar = sorted({f["sayfa"] for f in farklar})
    rapor = Path("docs") / f"parite-raporu-{date.today():%m-%d-%Y}.md"
    with rapor.open("w", encoding="utf-8") as f:
        f.write(f"# Excel parite raporu - {date.today():%d.%m.%Y}\n\nKaynak: `{yol.name}`\n\n")
        f.write(f"Farklı sayfa sayısı: **{len(sayfalar)}**, toplam fark: **{len(farklar)}**\n\n")
        f.write("| Sayfa | Alan | Excel | Motor | Fark |\n|---|---|---|---|---|\n")
        for d in farklar:
            f.write(f"| {d['sayfa']} | {d['alan']} | {d['excel']} | {d['motor']} | {d['fark']} |\n")
        f.write("\n## Uyarılar (fiyatsız malzeme vb.)\n\n")
        for ad, u in uyarilar.items():
            if u:
                f.write(f"- **{ad}**: " + "; ".join(u) + "\n")
    print(f"farklı sayfa: {len(sayfalar)} / toplam fark: {len(farklar)} -> {rapor}")
    for s in sayfalar:
        print("  ", s, [d["alan"] for d in farklar if d["sayfa"] == s][:8])


if __name__ == "__main__":
    main()
