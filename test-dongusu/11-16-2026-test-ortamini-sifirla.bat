@echo off
rem Fiyat Calismasi - TEST ORTAMINI SIFIRLA: yalniz veri\test-dongusu.db, -wal ve -shm dosyalarini siler (onay ister).
rem Gercek veritabanina (veri\fiyat.db) ve yedek klasorune dokunmaz. Test sunucusu (8047) aciksa calismaz.
setlocal
cd /d "%~dp0.."
set "PORT=8047"
set "TESTDB=%CD%\veri\test-dongusu.db"

netstat -ano | findstr /R /C:":%PORT% .*LISTENING" >nul
if %errorlevel%==0 (
  echo Test sunucusu ^(8047^) calisiyor. Once "Fiyat Calismasi TEST Sunucusu (8047)" penceresini kapatin.
  pause
  exit /b 2
)
if not exist "%TESTDB%" if not exist "%TESTDB%-wal" if not exist "%TESTDB%-shm" (
  echo Silinecek test veritabani yok: %TESTDB%
  pause
  exit /b 0
)

echo Silinecek dosyalar:
if exist "%TESTDB%" echo   %TESTDB%
if exist "%TESTDB%-wal" echo   %TESTDB%-wal
if exist "%TESTDB%-shm" echo   %TESTDB%-shm
echo Test ortamindaki tum kullanicilar, calismalar ve donemler silinir. Gercek veritabani (fiyat.db) etkilenmez.
set "CEVAP="
set /p "CEVAP=Devam etmek icin EVET yazin: "
if /i not "%CEVAP%"=="EVET" (
  echo Vazgecildi; hicbir sey silinmedi.
  pause
  exit /b 4
)
del /q "%TESTDB%" "%TESTDB%-wal" "%TESTDB%-shm" 2>nul
echo Test veritabani silindi. Yeniden baslamak icin 11-16-2026-test-ortamini-ac.bat calistirin.
pause
exit /b 0
