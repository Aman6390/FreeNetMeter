@echo off
setlocal
cd /d "%~dp0"
echo ==========================================
echo     FreeNetMeter Uninstallation
echo ==========================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Uninstall-FreeNetMeter.ps1"
echo.
pause
