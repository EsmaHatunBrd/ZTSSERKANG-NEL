@echo off
rem Fiyat Calismasi - TEST ORTAMI. Ayri veritabani (veri\test-dongusu.db) ile 8047 portunda acar.
rem Gercek veritabanina (veri\fiyat.db) ve 8000 portundaki sunucuya DOKUNMAZ.
rem Ilk acilista (test veritabani yoksa) Genel Direktor hesabi acilir ve gecici sifre ekrana yazilir.
rem Kapatmak icin "Fiyat Calismasi TEST Sunucusu (8047)" penceresini kapatin.
setlocal
cd /d "%~dp0.."
set "PORT=8047"
set "TESTDB=%CD%\veri\test-dongusu.db"
set "VERITABANI_URL=sqlite:///%TESTDB:\=/%"
set "GIRIS_ZORUNLU=1"

if /i "%VERITABANI_URL:fiyat.db=%" neq "%VERITABANI_URL%" (
  echo HATA: test ortami gercek veritabanini gosteriyor; durduruldu.
  pause
  exit /b 1
)

netstat -ano | findstr /R /C:":%PORT% .*LISTENING" >nul
if %errorlevel%==0 (
  echo Test sunucusu zaten calisiyor, tarayici aciliyor...
  goto ac
)

if not exist ".venv\Scripts\python.exe" (
  echo HATA: .venv bulunamadi. Once kurulum\11-12-2026-kur.ps1 calistirilmali.
  pause
  exit /b 1
)
if not exist "frontend\dist\index.html" (
  echo HATA: frontend\dist yok. Once ana uygulamayi bir kez 11-13-2026-uygulamayi-ac.bat ile acin ^(arayuzu derler^).
  pause
  exit /b 1
)

set "YENI=0"
if not exist "%TESTDB%" set "YENI=1"

echo Test sunucusu baslatiliyor: http://localhost:%PORT%   veritabani: %TESTDB%
start "Fiyat Calismasi TEST Sunucusu (8047)" /min cmd /c ".venv\Scripts\python.exe -m uvicorn backend.uygulama:app --host 127.0.0.1 --port %PORT%"

set /a deneme=0
:bekle
timeout /t 1 /nobreak >nul
netstat -ano | findstr /R /C:":%PORT% .*LISTENING" >nul
if %errorlevel%==0 goto hazir
set /a deneme+=1
if %deneme% lss 30 goto bekle
echo HATA: test sunucusu 30 saniyede acilmadi. "Fiyat Calismasi TEST Sunucusu (8047)" penceresine bakin.
pause
exit /b 1

:hazir
rem Veritabani ilk istekte olusur.
curl -s -o nul "http://127.0.0.1:%PORT%/api/v1/kimlik/ben"
if "%YENI%"=="1" (
  echo.
  echo === Yeni test veritabani: ilk Genel Direktor hesabi aciliyor ===
  ".venv\Scripts\python.exe" "scripts\11-04-2026-ilk-genel-direktor.py" --db "%TESTDB%"
  echo.
  echo Bu kullanici adini ve gecici sifreyi not edin; tarayicida ilk giriste kendi sifrenizi belirleyeceksiniz.
  pause
)

:ac
start "" "http://localhost:%PORT%"
exit /b 0
