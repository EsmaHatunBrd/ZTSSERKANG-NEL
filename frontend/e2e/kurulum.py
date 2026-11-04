"""E2E kurulumu: veri/e2e.db'yi silip gerçek Excel çalışma kitabını içe aktarır, sonra uvicorn'u başlatır.

Kullanım (proje kökünden): .venv/Scripts/python frontend/e2e/kurulum.py
Playwright webServer bunu çalıştırır; sunucu 8010 portunda dinler (geliştirme backend'i 8000 ile çakışmaz).
"""
import os
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parents[2]
DB = KOK / "veri" / "e2e.db"
EXCEL = KOK / "Fiyat Çalışma - 2026-2027 - Berrak.xlsx"

os.environ["VERITABANI_URL"] = f"sqlite:///{DB.as_posix()}"
sys.path.insert(0, str(KOK))

DB.parent.mkdir(parents=True, exist_ok=True)
for ek in ("", "-wal", "-shm"):
    Path(str(DB) + ek).unlink(missing_ok=True)

from backend.depo.veritabani import Base, motor_olustur, oturum_fabrikasi  # noqa: E402
from backend.servisler import import_servisi, kimlik_servisi  # noqa: E402

# Giriş zorunlu: testler bu Genel Direktör hesabıyla oturum açar (e2e/giris-kurulumu.ts). Şifre yalnız boş e2e.db içindir.
E2E_KULLANICI, E2E_SIFRE = "e2e.yonetici", "e2e-sifre-1"

motor = motor_olustur()
Base.metadata.create_all(motor)
with oturum_fabrikasi(motor)() as s:
    ozet = import_servisi.excel_tam_yukle(s, EXCEL, "2026-2027", "E2E", "fiyat_calismasi")
    kimlik_servisi.kullanici_olustur(s, E2E_KULLANICI, "E2E Yönetici", "genel_direktor", E2E_SIFRE, olusturan="e2e", sifre_degismeli=False)
    s.commit()
print("E2E import tamam:", {k: v for k, v in ozet.items() if isinstance(v, (int, str))}, flush=True)
motor.dispose()

import uvicorn  # noqa: E402

uvicorn.run("backend.uygulama:app", host="127.0.0.1", port=8010, log_level="warning")
