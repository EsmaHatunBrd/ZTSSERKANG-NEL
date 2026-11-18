@echo off
chcp 65001 >nul
rem Fiyat Calismasi - uygulamayi ac. Sunucu arka planda calisir; zaten aciksa yalniz tarayiciyi acar.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Uygulama henuz kurulmamis. Once "11-18-2026-1-kur.bat" dosyasini calistirin.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File kurulum\11-12-2026-baslat.ps1 >nul
if errorlevel 1 (
  echo Uygulama baslatilamadi. Ayrinti icin bu pencereyi kapatmadan asagidaki komutu calistirin:
  echo   powershell -ExecutionPolicy Bypass -File kurulum\11-12-2026-baslat.ps1
  pause
  exit /b 1
)
start "" "http://127.0.0.1:8000"
exit /b 0
