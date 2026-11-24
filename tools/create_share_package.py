"""Automated packaging script for FreeNetMeter distribution.

Creates a complete, portable, standalone distribution package (.zip)
ready to share with other Windows users.
"""

from __future__ import annotations

import os
import shutil
import zipfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT_DIR / "dist" / "FreeNetMeter"
APP_ICO = ROOT_DIR / "app.ico"
ZIP_NAME = "FreeNetMeter-v1.0.0-Windows-x64.zip"
OUTPUT_ZIP = ROOT_DIR / ZIP_NAME
DESKTOP_DIR = Path(os.environ.get("USERPROFILE", "")) / "Desktop"

INSTALL_BAT_CONTENT = r"""@echo off
setlocal
title FreeNetMeter Setup
echo ========================================================
echo           FreeNetMeter Setup for Windows
echo ========================================================
echo.
echo Installing FreeNetMeter to %LOCALAPPDATA%\Programs\FreeNetMeter...

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference = 'Stop'; $src = '%~dp0'; $dst = Join-Path $env:LOCALAPPDATA 'Programs\FreeNetMeter'; if (-not (Test-Path $dst)) { New-Item -ItemType Directory -Path $dst -Force | Out-Null }; Copy-Item -Path \"$src\*\" -Destination $dst -Recurse -Force; $wsh = New-Object -ComObject WScript.Shell; $exe = Join-Path $dst 'FreeNetMeter.exe'; $ico = Join-Path $dst 'app.ico'; $desk = [Environment]::GetFolderPath('Desktop'); $sc1 = $wsh.CreateShortcut((Join-Path $desk 'FreeNetMeter.lnk')); $sc1.TargetPath = $exe; $sc1.WorkingDirectory = $dst; if (Test-Path $ico) { $sc1.IconLocation = \"$ico,0\" }; $sc1.Save(); $progs = [Environment]::GetFolderPath('Programs'); $sc2 = $wsh.CreateShortcut((Join-Path $progs 'FreeNetMeter.lnk')); $sc2.TargetPath = $exe; $sc2.WorkingDirectory = $dst; if (Test-Path $ico) { $sc2.IconLocation = \"$ico,0\" }; $sc2.Save(); Write-Host 'Successfully created Desktop and Start Menu shortcuts!' -ForegroundColor Green"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================================
    echo SUCCESS: FreeNetMeter installed successfully!
    echo Desktop and Start Menu shortcuts have been created.
    echo ========================================================
    echo.
    set /p launch="Would you like to launch FreeNetMeter now? (Y/N): "
    if /i "%launch%"=="Y" (
        start "" "%LOCALAPPDATA%\Programs\FreeNetMeter\FreeNetMeter.exe"
    )
) else (
    echo.
    echo Installation script completed. You can run FreeNetMeter.exe directly from this folder!
)
pause
"""

README_CONTENT = """========================================================================
                      FreeNetMeter for Windows
             Live Desktop Network Speed & Bandwidth Monitor
========================================================================

Thank you for using FreeNetMeter! This software is 100% free, open-source,
offline, privacy-friendly, and has zero ads, zero telemetry, and zero bloat.

------------------------------------------------------------------------
HOW TO USE
------------------------------------------------------------------------

OPTION 1: Portable Mode (No Installation Required)
  Simply double-click "FreeNetMeter.exe" in this folder!
  The floating speed meter widget will appear on your screen immediately.
  You can run it from any folder, USB drive, or desktop.

OPTION 2: Install to Desktop & Start Menu
  Double-click "Install.bat".
  This creates official shortcuts on your Desktop and Start Menu and
  installs the application cleanly into your user profile (no administrator
  rights needed).

------------------------------------------------------------------------
KEY FEATURES & SHORTCUTS
------------------------------------------------------------------------
- Drag & Drop: Click and drag the floating speed meter to place it anywhere.
  Screen boundaries prevent it from ever sliding behind your Windows taskbar.
- Multi-Monitor Support: Automatically stays visible across multiple displays,
  display sleep/wake, and resolution changes.
- Right-Click Context Menu:
  * Speed Refresh Time: Change refresh interval (0.5s, 1s, 2s, 3s, 5s)
  * Data Usages Stat: View daily & monthly download/upload history & charts
  * Stopwatch: Measure live bandwidth transferred during downloads/games
  * Adapters (NIC) Setting: Choose Wi-Fi, Ethernet, or auto-detect
  * Change UI Position: Snap to Top-Right, Top-Left, Bottom-Right, etc.
  * Always on Top & Lock Position: Keep widget visible over all windows
  * Themes & Appearance: Dark mode, Light mode, custom colors & opacity

Keyboard Shortcuts (when widget has focus):
  Ctrl + S : Open Settings
  Ctrl + D : Open Data Usage Dashboard
  Ctrl + H : Hide to System Tray
  Ctrl + Q : Exit Application

------------------------------------------------------------------------
SYSTEM REQUIREMENTS
------------------------------------------------------------------------
- Windows 10 or Windows 11 (64-bit)
- No additional runtime, Python, or framework installation required.
"""


def main() -> None:
    print(f"Creating distribution package from: {DIST_DIR}")
    if not DIST_DIR.exists():
        raise FileNotFoundError(f"Dist directory not found: {DIST_DIR}")

    # Copy app.ico
    if APP_ICO.exists():
        shutil.copy2(APP_ICO, DIST_DIR / "app.ico")
        print("Copied app.ico to dist directory.")

    # Write Install.bat
    install_bat_path = DIST_DIR / "Install.bat"
    install_bat_path.write_text(INSTALL_BAT_CONTENT, encoding="ansi")
    print(f"Created {install_bat_path}")

    # Write README.txt
    readme_path = DIST_DIR / "README.txt"
    readme_path.write_text(README_CONTENT, encoding="utf-8")
    print(f"Created {readme_path}")

    # Create ZIP archive
    print(f"Compressing into {OUTPUT_ZIP}...")
    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(DIST_DIR):
            for file in files:
                file_path = Path(root) / file
                archive_name = Path("FreeNetMeter") / file_path.relative_to(DIST_DIR)
                zf.write(file_path, archive_name)

    size_mb = OUTPUT_ZIP.stat().st_size / (1024 * 1024)
    print(f"Package created successfully: {OUTPUT_ZIP} ({size_mb:.2f} MB)")

    # Also copy to user's Desktop for easy access
    if DESKTOP_DIR.exists():
        desktop_zip = DESKTOP_DIR / ZIP_NAME
        shutil.copy2(OUTPUT_ZIP, desktop_zip)
        print(f"Copied package to Desktop: {desktop_zip}")


if __name__ == "__main__":
    main()
