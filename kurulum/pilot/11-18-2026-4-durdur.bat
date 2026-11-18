@echo off
chcp 65001 >nul
rem Fiyat Calismasi - arka planda calisan uygulamayi kapatir.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File kurulum\11-12-2026-durdur.ps1
pause
