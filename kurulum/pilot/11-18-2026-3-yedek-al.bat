@echo off
chcp 65001 >nul
rem Fiyat Calismasi - veritabaninin tarihli yedegini alir (veri\yedek klasorune). Uygulama acikken de calisir.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File kurulum\11-12-2026-yedekle.ps1
pause
