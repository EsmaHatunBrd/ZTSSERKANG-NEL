@echo off
rem Fiyat Calismasi - tek tikla ac. Sunucu 8000 portunda calisir, arayuz ayni adresten gelir.
rem Kapatmak icin acilan "Fiyat Calismasi Sunucusu" penceresini kapatin.
cd /d "%~dp0"

netstat -ano | findstr /R /C:":8000 .*LISTENING" >nul
if %errorlevel%==0 (
  echo Sunucu zaten calisiyor, tarayici aciliyor...
  goto ac
)

if not exist ".venv\Scripts\python.exe" (
  echo HATA: .venv bulunamadi. Once kurulum\11-12-2026-kur.ps1 calistirilmali.
  pause
  exit /b 1
)
if not exist "frontend\dist\index.html" (
  echo Arayuz derleniyor, ilk seferde bir dakika surebilir...
  pushd frontend
  call npm run build
  popd
)

echo Sunucu baslatiliyor...
start "Fiyat Calismasi Sunucusu" /min cmd /c ".venv\Scripts\python.exe -m uvicorn backend.uygulama:app --host 127.0.0.1 --port 8000"

rem Sunucunun acilmasini bekle (en cok 30 sn)
set /a deneme=0
:bekle
timeout /t 1 /nobreak >nul
netstat -ano | findstr /R /C:":8000 .*LISTENING" >nul
if %errorlevel%==0 goto ac
set /a deneme+=1
if %deneme% lss 30 goto bekle
echo HATA: sunucu 30 saniyede acilmadi. "Fiyat Calismasi Sunucusu" penceresindeki mesaja bakin.
pause
exit /b 1

:ac
start "" "http://localhost:8000"
exit /b 0
