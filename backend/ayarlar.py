"""Ortam değişkenlerinden ayarlar. Varsayılanlar tek kullanıcılı yerel kurulum içindir."""
import os
from dataclasses import dataclass
from pathlib import Path

PROJE_KOKU = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Ayarlar:
    veritabani_url: str = os.environ.get("VERITABANI_URL", f"sqlite:///{PROJE_KOKU / 'veri' / 'fiyat.db'}")
    excel_yolu: Path = Path(os.environ.get("EXCEL_YOLU", PROJE_KOKU / "Fiyat Çalışma - 2026-2027 - Berrak.xlsx"))


AYARLAR = Ayarlar()
