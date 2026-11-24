@echo off
setlocal
cd /d "%~dp0"
echo ==========================================
echo       FreeNetMeter Windows Setup
echo ==========================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-FreeNetMeter.ps1"
echo.
pause
