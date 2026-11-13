"""Kurulum betiklerinin yedek yardımcısı (yalnız standart kütüphane).

SQLite dosyasını, sunucu çalışırken de tutarlı biçimde kopyalar (sqlite3 backup API; WAL içeriği dahil).
Düz dosya kopyası WAL kipinde eksik/bozuk yedek üretebilir; bu yüzden yedekle.ps1 bunu kullanır.

Kullanım:
  python 11-12-2026-yedek-araci.py yedekle --db <kaynak.db> --hedef <hedef.db>
  python 11-12-2026-yedek-araci.py dogrula --db <dosya.db>
Çıkış kodu: 0 başarılı, 1 hata. Ekrana yalnız dosya yolu ve sayılar yazılır (veri içeriği yazılmaz).
"""
import argparse
import sqlite3
import sys
from pathlib import Path


def dogrula(yol: Path) -> int:
    """Bütünlük denetimi; tablo sayısını döner. Bozuksa hata fırlatır."""
    if not yol.is_file():
        raise SystemExit(f"dosya yok: {yol}")
    bag = sqlite3.connect(str(yol), timeout=30)
    try:
        sonuc = bag.execute("PRAGMA integrity_check").fetchone()[0]
        if sonuc != "ok":
            raise SystemExit(f"veritabanı bütünlük denetiminden geçmedi: {yol}")
        return bag.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
    finally:
        bag.close()


def yedekle(kaynak: Path, hedef: Path) -> None:
    if not kaynak.is_file():
        raise SystemExit(f"kaynak veritabanı yok: {kaynak}")
    if hedef.exists():
        raise SystemExit(f"hedef zaten var, üzerine yazılmaz: {hedef}")
    hedef.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(str(kaynak), timeout=30)
    try:
        dst = sqlite3.connect(str(hedef))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()


def main() -> None:
    a = argparse.ArgumentParser()
    alt = a.add_subparsers(dest="komut", required=True)
    y = alt.add_parser("yedekle")
    y.add_argument("--db", required=True)
    y.add_argument("--hedef", required=True)
    d = alt.add_parser("dogrula")
    d.add_argument("--db", required=True)
    g = a.parse_args()
    for akis in (sys.stdout, sys.stderr):   # Türkçe harf konsol kod sayfasında yoksa betik düşmesin
        akis.reconfigure(errors="replace")
    try:
        if g.komut == "yedekle":
            hedef = Path(g.hedef)
            yedekle(Path(g.db), hedef)
            tablo = dogrula(hedef)
            print(f"yedek alındı: {hedef} ({hedef.stat().st_size} bayt, {tablo} tablo)")
        else:
            tablo = dogrula(Path(g.db))
            print(f"dosya sağlam: {g.db} ({tablo} tablo)")
    except sqlite3.Error as e:
        print(f"veritabanı hatası: {e}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
