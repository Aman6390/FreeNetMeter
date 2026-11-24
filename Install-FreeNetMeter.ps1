# FreeNetMeter Windows Installer
# Installs FreeNetMeter into %LOCALAPPDATA%\Programs\FreeNetMeter (No admin rights required)
# Creates Windows Start Menu and Desktop shortcuts with official icon.

[CmdletBinding()]
param(
    [switch]$LaunchAfterInstall
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "      FreeNetMeter Windows Setup          " -ForegroundColor White
Write-Host "==========================================" -ForegroundColor Cyan

# 1. Paths
$SourceDir = Join-Path $PSScriptRoot "dist\FreeNetMeter"
if (-not (Test-Path $SourceDir)) {
    Write-Host "ERROR: Compiled distribution not found at '$SourceDir'." -ForegroundColor Red
    Write-Host "Please build the project first." -ForegroundColor Yellow
    Exit 1
}

$InstallDir = Join-Path $env:LOCALAPPDATA "Programs\FreeNetMeter"
$DesktopDir = [Environment]::GetFolderPath("Desktop")
$StartMenuDir = [Environment]::GetFolderPath("Programs")
$IconPath = Join-Path $PSScriptRoot "app.ico"

# 2. Check for running instance and terminate gracefully
$running = Get-Process -Name "FreeNetMeter" -ErrorAction SilentlyContinue
if ($running) {
    Write-Host "Stopping running FreeNetMeter instance..." -ForegroundColor Yellow
    $running | Stop-Process -Force
    Start-Sleep -Seconds 1
}

# Also stop any running development python instances of FreeNetMeter
Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*main.py*" } |
    ForEach-Object {
        Write-Host "Stopping running python FreeNetMeter process (PID $($_.ProcessId))..." -ForegroundColor Yellow
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }

# 3. Create install directory and copy files
Write-Host "Installing to: $InstallDir" -ForegroundColor Green
if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}

Copy-Item -Path "$SourceDir\*" -Destination $InstallDir -Recurse -Force
if (Test-Path $IconPath) {
    Copy-Item -Path $IconPath -Destination (Join-Path $InstallDir "app.ico") -Force
}

# 4. Create Desktop & Start Menu Shortcuts using WScript.Shell
$ExePath = Join-Path $InstallDir "FreeNetMeter.exe"
$InstalledIcon = Join-Path $InstallDir "app.ico"
$WshShell = New-Object -ComObject WScript.Shell

# Desktop Shortcut
$DesktopShortcutPath = Join-Path $DesktopDir "FreeNetMeter.lnk"
Write-Host "Creating Desktop shortcut: $DesktopShortcutPath" -ForegroundColor Gray
$Shortcut = $WshShell.CreateShortcut($DesktopShortcutPath)
$Shortcut.TargetPath = $ExePath
$Shortcut.WorkingDirectory = $InstallDir
$Shortcut.Description = "FreeNetMeter - Live Network Speed Meter"
if (Test-Path $InstalledIcon) {
    $Shortcut.IconLocation = "$InstalledIcon,0"
}
$Shortcut.Save()

# Start Menu Shortcut
$StartMenuShortcutPath = Join-Path $StartMenuDir "FreeNetMeter.lnk"
Write-Host "Creating Start Menu shortcut: $StartMenuShortcutPath" -ForegroundColor Gray
$StartShortcut = $WshShell.CreateShortcut($StartMenuShortcutPath)
$StartShortcut.TargetPath = $ExePath
$StartShortcut.WorkingDirectory = $InstallDir
$StartShortcut.Description = "FreeNetMeter - Live Network Speed Meter"
if (Test-Path $InstalledIcon) {
    $StartShortcut.IconLocation = "$InstalledIcon,0"
}
$StartShortcut.Save()

Write-Host ""
Write-Host "SUCCESS: FreeNetMeter has been installed successfully!" -ForegroundColor Green
Write-Host "  - Executable: $ExePath"
Write-Host "  - Desktop shortcut created"
Write-Host "  - Start Menu shortcut created"
Write-Host ""

if ($LaunchAfterInstall) {
    Write-Host "Launching FreeNetMeter..." -ForegroundColor Cyan
    Start-Process -FilePath $ExePath -WorkingDirectory $InstallDir
}
