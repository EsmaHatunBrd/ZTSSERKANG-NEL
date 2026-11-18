@echo off
chcp 65001 >nul
rem Fiyat Calismasi - tek bilgisayar (pilot) kurulumu. Cift tiklayin; yonetici yetkisi gerekmez.
rem Yaptiklari: Python 3.12 (yoksa kurar) -> .venv -> paketlerden bagimliliklar (internet gerekmez) -> ayarlar -> sunucuyu baslatir
rem -> ilk Genel Direktor hesabini acar (gecici sifre ekranda) -> masaustune kisayol koyar -> tarayiciyi acar.
rem Tekrar calistirmak zararsizdir: var olan veri, ayar ve kullanicilara dokunmaz.
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title Fiyat Calismasi - Kurulum

echo.
echo ================================================
echo   Fiyat Calismasi - kurulum
echo ================================================
echo Klasor: %CD%
echo.

rem ---------- 1. Python 3.12 ----------
set "PY="
for /f "delims=" %%i in ('py -3.12 -c "import sys;print(sys.executable)" 2^>nul') do set "PY=%%i"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY if exist "%ProgramFiles%\Python312\python.exe" set "PY=%ProgramFiles%\Python312\python.exe"
if defined PY goto python_hazir

echo [1/6] Python 3.12 bulunamadi; kuruluyor (bir-iki dakika surer)...
where winget >nul 2>nul
if %errorlevel%==0 (
  winget install --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements >nul 2>nul
)
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if defined PY goto python_hazir

set "KURULUM_EXE="
for %%f in ("kurulum\paketler\python-3.12*-amd64.exe") do set "KURULUM_EXE=%%~ff"
if not defined KURULUM_EXE (
  echo HATA: Python kurulamadi ve paket icinde Python kurulum dosyasi yok.
  echo python.org/downloads adresinden Python 3.12 indirip kurun, sonra bu dosyayi yeniden calistirin.
  pause
  exit /b 1
)
"%KURULUM_EXE%" /quiet InstallAllUsers=0 PrependPath=0 Include_launcher=0 Include_test=0
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY (
  echo HATA: Python 3.12 kurulumu tamamlanamadi. python.org/downloads adresinden elle kurup yeniden deneyin.
  pause
  exit /b 1
)

:python_hazir
echo [1/6] Python: %PY%

rem ---------- 2. Sanal ortam ----------
if not exist ".venv\Scripts\python.exe" (
  echo [2/6] Python ortami olusturuluyor...
  "%PY%" -m venv .venv
  if errorlevel 1 ( echo HATA: sanal ortam olusturulamadi. & pause & exit /b 1 )
) else (
  echo [2/6] Python ortami zaten var.
)

rem ---------- 3. Bagimliliklar (once paketlerden, olmazsa internetten) ----------
echo [3/6] Bagimliliklar kuruluyor...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --no-index --find-links kurulum\paketler -r kurulum\paketler\gereksinimler.txt >kurulum\kurulum-pip.log 2>&1
if errorlevel 1 (
  echo     Paketlerden kurulamadi, internetten deneniyor...
  ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r kurulum\paketler\gereksinimler.txt >>kurulum\kurulum-pip.log 2>&1
  if errorlevel 1 ( echo HATA: bagimliliklar kurulamadi. Ayrintilar: kurulum\kurulum-pip.log & pause & exit /b 1 )
)

rem ---------- 4. Klasorler ve ayarlar (yalniz bu bilgisayar, giris zorunlu) ----------
echo [4/6] Ayarlar hazirlaniyor...
powershell -NoProfile -ExecutionPolicy Bypass -File kurulum\11-12-2026-kur.ps1 -BagimlilikAtla -DerlemeAtla -OzetYok
if errorlevel 1 ( echo HATA: kurulum adimlari tamamlanamadi. & pause & exit /b 1 )
powershell -NoProfile -ExecutionPolicy Bypass -Command "$f='kurulum\ayarlar.env'; $t=Get-Content -LiteralPath $f -Encoding UTF8; $t=$t -replace '^HOST=.*$','HOST=127.0.0.1' -replace '^GIRIS_ZORUNLU=.*$','GIRIS_ZORUNLU=1'; Set-Content -LiteralPath $f -Value $t -Encoding UTF8"

rem ---------- 5. Sunucu ve ilk Genel Direktor ----------
echo [5/6] Uygulama baslatiliyor...
powershell -NoProfile -ExecutionPolicy Bypass -File kurulum\11-12-2026-baslat.ps1 >nul
if errorlevel 1 (
  echo HATA: uygulama baslatilamadi. Ayrintilar icin: powershell -ExecutionPolicy Bypass -File kurulum\11-12-2026-baslat.ps1
  pause
  exit /b 1
)
echo.
echo ------------------------------------------------
".venv\Scripts\python.exe" scripts\11-04-2026-ilk-genel-direktor.py
echo ------------------------------------------------
echo Yukaridaki kullanici adini ve gecici sifreyi not edin (ilk kurulumdaysa).
echo Ilk giriste kendi sifrenizi belirleyeceksiniz.
echo.

rem ---------- 6. Masaustu kisayolu ----------
echo [6/6] Masaustune "Fiyat Calismasi" kisayolu ekleniyor...
if defined KISAYOL_YOK goto kisayol_atla
powershell -NoProfile -ExecutionPolicy Bypass -Command "$w=New-Object -ComObject WScript.Shell; $d=[Environment]::GetFolderPath('Desktop'); $k=$w.CreateShortcut((Join-Path $d 'Fiyat Calismasi.lnk')); $k.TargetPath=(Join-Path '%CD%' '11-18-2026-2-uygulamayi-ac.bat'); $k.WorkingDirectory='%CD%'; $k.IconLocation='%SystemRoot%\System32\shell32.dll,13'; $k.Save()"
:kisayol_atla

echo.
echo Kurulum tamam. Tarayici aciliyor: http://127.0.0.1:8000
if not defined TARAYICI_YOK start "" "http://127.0.0.1:8000"
echo Bundan sonra masaustundeki "Fiyat Calismasi" kisayoluyla acabilirsiniz.
pause
exit /b 0
