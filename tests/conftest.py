import os
from pathlib import Path
import pytest

PROJE_KOKU = Path(__file__).resolve().parent.parent
VARSAYILAN_EXCEL = PROJE_KOKU / "Fiyat Çalışma - 2026-2027 - Berrak.xlsx"


@pytest.fixture(scope="session")
def excel_yolu() -> Path:
    yol = Path(os.environ.get("EXCEL_YOLU", VARSAYILAN_EXCEL))
    if not yol.exists():
        pytest.skip(f"Excel bulunamadı: {yol}")
    return yol
