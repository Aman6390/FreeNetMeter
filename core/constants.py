"""Centralized constants for FreeNetMeter.

All timing intervals, limits, registry paths, default settings, and schema
identifiers are consolidated here to avoid hardcoded magic numbers or paths.
"""

from __future__ import annotations

import os
from pathlib import Path

# Application identity
APP_NAME: str = "FreeNetMeter"
APP_VERSION: str = "1.0.0"
SETTINGS_SCHEMA_VERSION: int = 1
ORGANIZATION_NAME: str = "FreeNetMeter"

# Operating System paths
# Standard application data directory under %APPDATA%\FreeNetMeter
APPDATA_ENV: str = os.environ.get("APPDATA", "")
if APPDATA_ENV:
    APP_DATA_DIR: Path = Path(APPDATA_ENV) / APP_NAME
else:
    # Safe fallback if APPDATA is not defined (e.g. non-Windows test runner)
    APP_DATA_DIR = Path.home() / f".{APP_NAME.lower()}"

LOGS_DIR: Path = APP_DATA_DIR / "logs"
LOG_FILE_PATH: Path = LOGS_DIR / "freenetmeter.log"
SETTINGS_FILE_PATH: Path = APP_DATA_DIR / "settings.json"
SETTINGS_BAD_BACKUP_PATH: Path = APP_DATA_DIR / "settings.json.bad"
USAGE_DB_PATH: Path = APP_DATA_DIR / "usage.db"

# Single-instance IPC identifier
SINGLE_INSTANCE_SERVER_NAME: str = (
    f"FreeNetMeter_SingleInstance_IPC_{os.environ.get('USERNAME', 'default')}"
)

# Windows Registry Keys
REGISTRY_AUTOSTART_KEY: str = r"Software\Microsoft\Windows\CurrentVersion\Run"
REGISTRY_AUTOSTART_VALUE_NAME: str = APP_NAME
REGISTRY_THEMES_KEY: str = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
REGISTRY_THEMES_VALUE_NAME: str = "AppsUseLightTheme"

# Sampling and Timing Limits
SAMPLE_INTERVAL_SECONDS: float = 1.0
MIN_SAMPLE_INTERVAL_SECONDS: float = 0.2
MAX_SAMPLE_GAP_SECONDS: float = 5.0
DEFAULT_ROLLING_WINDOW_SIZE: int = 3
USAGE_FLUSH_INTERVAL_SECONDS: float = 30.0

# Database Limits
SQLITE_BUSY_TIMEOUT_MS: int = 5000

# Logging limits
LOG_MAX_BYTES: int = 5 * 1024 * 1024  # 5 Megabytes
LOG_BACKUP_COUNT: int = 3

# Network interface filtering defaults
DEFAULT_EXCLUDED_INTERFACE_KEYWORDS: tuple[str, ...] = (
    "loopback",
    "lo",
    "vethernet",
    "hyper-v",
    "docker",
    "wsl",
    "vmware",
    "virtualbox",
    "virtual",
    "bluetooth",
    "isatap",
    "teredo",
    "npcap",
)

# Display & Formatting defaults
DEFAULT_UNIT_SYSTEM: str = "decimal"  # 'decimal' (1 KB = 1000 B) or 'binary' (1 KiB = 1024 B)
DEFAULT_UNIT_TYPE: str = "bytes"  # 'bytes' or 'bits'
DEFAULT_FIXED_UNIT: str = (
    "auto"  # 'auto', 'B/s', 'KB/s', 'MB/s', 'GB/s', 'bps', 'Kbps', 'Mbps', etc.
)
DEFAULT_DECIMAL_PRECISION: int = 1  # 0, 1, or 2
DEFAULT_ARROW_STYLE: str = "triangle"  # 'triangle' (▼/▲), 'arrow' (↓/↑), 'letters' (D/U), 'none'

# Theme and visual defaults
DEFAULT_THEME_MODE: str = "system"  # 'system', 'dark', 'light'
DEFAULT_FONT_FAMILY: str = "Segoe UI"
DEFAULT_FONT_SIZE: int = 10
DEFAULT_COLOR_DOWNLOAD: str = "#00E676"  # Vibrant Apple/Material Green
DEFAULT_COLOR_UPLOAD: str = "#29B6F6"  # Vibrant Cyan/Light Blue
DEFAULT_BACKGROUND_OPACITY: int = 85  # 20 to 100 percentage
DEFAULT_LOCKED_POSITION: bool = False
DEFAULT_START_WITH_WINDOWS: bool = False
DEFAULT_DATA_RETENTION_DAYS: int = 0  # 0 means retain forever
