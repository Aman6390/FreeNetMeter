# FreeNetMeter Windows Uninstaller
# Removes FreeNetMeter shortcuts and installed files.

$ErrorActionPreference = "SilentlyContinue"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "     FreeNetMeter Uninstallation          " -ForegroundColor White
Write-Host "==========================================" -ForegroundColor Cyan

# 1. Stop running processes
$running = Get-Process -Name "FreeNetMeter" -ErrorAction SilentlyContinue
if ($running) {
    Write-Host "Stopping running FreeNetMeter instance..." -ForegroundColor Yellow
    $running | Stop-Process -Force
    Start-Sleep -Seconds 1
}

Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*main.py*" } |
    ForEach-Object {
        Write-Host "Stopping running python FreeNetMeter process (PID $($_.ProcessId))..." -ForegroundColor Yellow
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }

# 2. Remove Shortcuts
$DesktopDir = [Environment]::GetFolderPath("Desktop")
$StartMenuDir = [Environment]::GetFolderPath("Programs")

$DesktopShortcut = Join-Path $DesktopDir "FreeNetMeter.lnk"
if (Test-Path $DesktopShortcut) {
    Remove-Item $DesktopShortcut -Force
    Write-Host "Removed Desktop shortcut." -ForegroundColor Gray
}

$StartShortcut = Join-Path $StartMenuDir "FreeNetMeter.lnk"
if (Test-Path $StartShortcut) {
    Remove-Item $StartShortcut -Force
    Write-Host "Removed Start Menu shortcut." -ForegroundColor Gray
}

# 3. Remove Program Files
$InstallDir = Join-Path $env:LOCALAPPDATA "Programs\FreeNetMeter"
if (Test-Path $InstallDir) {
    Remove-Item $InstallDir -Recurse -Force
    Write-Host "Removed program files from $InstallDir." -ForegroundColor Gray
}

Write-Host ""
Write-Host "FreeNetMeter has been cleanly uninstalled from your computer." -ForegroundColor Green
Write-Host "Note: Your settings and usage history database in %APPDATA%\FreeNetMeter have been preserved." -ForegroundColor Yellow
Write-Host "If you wish to remove them as well, delete: $env:APPDATA\FreeNetMeter" -ForegroundColor Gray
Write-Host ""
