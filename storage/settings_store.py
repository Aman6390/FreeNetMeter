"""Settings storage and configuration management.

Provides:
1. `AppSettings`: dataclass representing user preferences with complete validation and clamping.
2. `SettingsStore`: atomic write persistence to JSON, automatic corrupt-file backup (.bad),
   and forward-compatible schema migrations.

Correctness Rule 12:
Atomic writes are performed by writing to a temporary file in the same directory,
flushing buffers, and replacing the target file with os.replace. If the file is missing
or corrupt, it is backed up as settings.json.bad, defaults are loaded, and the application
continues running safely.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from core.constants import (
    DEFAULT_ARROW_STYLE,
    DEFAULT_BACKGROUND_OPACITY,
    DEFAULT_COLOR_DOWNLOAD,
    DEFAULT_COLOR_UPLOAD,
    DEFAULT_DATA_RETENTION_DAYS,
    DEFAULT_DECIMAL_PRECISION,
    DEFAULT_EXCLUDED_INTERFACE_KEYWORDS,
    DEFAULT_FIXED_UNIT,
    DEFAULT_FONT_FAMILY,
    DEFAULT_FONT_SIZE,
    DEFAULT_LOCKED_POSITION,
    DEFAULT_ROLLING_WINDOW_SIZE,
    DEFAULT_START_WITH_WINDOWS,
    DEFAULT_THEME_MODE,
    DEFAULT_UNIT_SYSTEM,
    DEFAULT_UNIT_TYPE,
    SAMPLE_INTERVAL_SECONDS,
    SETTINGS_BAD_BACKUP_PATH,
    SETTINGS_FILE_PATH,
    SETTINGS_SCHEMA_VERSION,
    USAGE_FLUSH_INTERVAL_SECONDS,
)

logger = logging.getLogger("FreeNetMeter.Settings")


@dataclass
class AppSettings:
    """User preferences and window state.

    All attributes are validated and bounded to ensure invalid inputs from
    external edits never crash or destabilize the application.
    """

    # Schema management
    schema_version: int = SETTINGS_SCHEMA_VERSION

    # Widget geometry & window state
    widget_x: int | None = None
    widget_y: int | None = None
    locked_position: bool = DEFAULT_LOCKED_POSITION
    widget_visible: bool = True
    always_on_top: bool = True
    keep_in_taskbar: bool = False

    # Interface filtering
    auto_select_nic: bool = True
    selected_interfaces: list[str] = field(default_factory=list)
    excluded_keywords: list[str] = field(
        default_factory=lambda: list(DEFAULT_EXCLUDED_INTERFACE_KEYWORDS)
    )

    # Unit scaling & formatting
    unit_system: str = DEFAULT_UNIT_SYSTEM  # 'decimal' or 'binary'
    unit_type: str = DEFAULT_UNIT_TYPE  # 'bytes' or 'bits'
    fixed_unit: str = DEFAULT_FIXED_UNIT  # 'auto' or specific unit
    decimal_precision: int = DEFAULT_DECIMAL_PRECISION  # 0, 1, or 2
    arrow_style: str = DEFAULT_ARROW_STYLE  # 'triangle', 'arrow', 'letters', 'none'

    # Appearance & Theming
    theme_mode: str = DEFAULT_THEME_MODE  # 'system', 'dark', 'light'
    font_family: str = DEFAULT_FONT_FAMILY
    font_size: int = DEFAULT_FONT_SIZE
    color_download: str = DEFAULT_COLOR_DOWNLOAD
    color_upload: str = DEFAULT_COLOR_UPLOAD
    background_opacity: int = DEFAULT_BACKGROUND_OPACITY  # 20 to 100

    # System Integration & Performance
    start_with_windows: bool = DEFAULT_START_WITH_WINDOWS
    retention_days: int = DEFAULT_DATA_RETENTION_DAYS  # 0 means retain forever
    rolling_window_size: int = DEFAULT_ROLLING_WINDOW_SIZE  # 1 to 10
    sample_interval_seconds: float = SAMPLE_INTERVAL_SECONDS  # 0.5 to 10.0 s
    flush_interval_seconds: float = USAGE_FLUSH_INTERVAL_SECONDS

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppSettings:
        """Construct and sanitize an AppSettings instance from a dictionary.

        Clamps all numeric and enumerated settings to safe operating boundaries.
        """
        # Validate schema version
        raw_schema = data.get("schema_version", SETTINGS_SCHEMA_VERSION)
        schema_ver = int(raw_schema) if isinstance(raw_schema, int) else SETTINGS_SCHEMA_VERSION

        # Position coordinates
        wx = data.get("widget_x")
        wy = data.get("widget_y")
        widget_x = int(wx) if isinstance(wx, (int, float)) else None
        widget_y = int(wy) if isinstance(wy, (int, float)) else None

        locked = bool(data.get("locked_position", DEFAULT_LOCKED_POSITION))
        visible = bool(data.get("widget_visible", True))
        always_on_top = bool(data.get("always_on_top", True))
        keep_in_taskbar = bool(data.get("keep_in_taskbar", False))
        auto_select_nic = bool(data.get("auto_select_nic", True))

        # Selected and excluded interfaces
        raw_sel = data.get("selected_interfaces", [])
        selected_interfaces = [str(i) for i in raw_sel] if isinstance(raw_sel, list) else []

        raw_ex = data.get("excluded_keywords", list(DEFAULT_EXCLUDED_INTERFACE_KEYWORDS))
        excluded_keywords = [str(k) for k in raw_ex] if isinstance(raw_ex, list) else []

        # Unit system
        unit_sys = str(data.get("unit_system", DEFAULT_UNIT_SYSTEM)).lower()
        if unit_sys not in ("decimal", "binary"):
            unit_sys = DEFAULT_UNIT_SYSTEM

        # Unit type
        unit_type = str(data.get("unit_type", DEFAULT_UNIT_TYPE)).lower()
        if unit_type not in ("bytes", "bits"):
            unit_type = DEFAULT_UNIT_TYPE

        # Fixed unit
        fixed_unit = str(data.get("fixed_unit", DEFAULT_FIXED_UNIT)).strip()

        # Decimal precision: 0, 1, or 2
        raw_prec = data.get("decimal_precision", DEFAULT_DECIMAL_PRECISION)
        try:
            decimal_precision = max(0, min(2, int(raw_prec)))
        except (ValueError, TypeError):
            decimal_precision = DEFAULT_DECIMAL_PRECISION

        # Arrow style
        raw_arrow = str(data.get("arrow_style", DEFAULT_ARROW_STYLE)).lower()
        if raw_arrow not in ("triangle", "arrow", "letters", "none"):
            raw_arrow = DEFAULT_ARROW_STYLE

        # Theme mode
        raw_theme = str(data.get("theme_mode", DEFAULT_THEME_MODE)).lower()
        if raw_theme not in ("system", "dark", "light"):
            raw_theme = DEFAULT_THEME_MODE

        # Font family and size
        font_family = (
            str(data.get("font_family", DEFAULT_FONT_FAMILY)).strip() or DEFAULT_FONT_FAMILY
        )
        raw_fsize = data.get("font_size", DEFAULT_FONT_SIZE)
        try:
            font_size = max(6, min(48, int(raw_fsize)))
        except (ValueError, TypeError):
            font_size = DEFAULT_FONT_SIZE

        # Text colors
        c_down = str(data.get("color_download", DEFAULT_COLOR_DOWNLOAD)).strip()
        c_up = str(data.get("color_upload", DEFAULT_COLOR_UPLOAD)).strip()
        color_download = (
            c_down
            if c_down.startswith("#") and len(c_down) in (4, 7, 9)
            else DEFAULT_COLOR_DOWNLOAD
        )
        color_upload = (
            c_up if c_up.startswith("#") and len(c_up) in (4, 7, 9) else DEFAULT_COLOR_UPLOAD
        )

        # Opacity: 20% to 100%
        raw_op = data.get("background_opacity", DEFAULT_BACKGROUND_OPACITY)
        try:
            background_opacity = max(20, min(100, int(raw_op)))
        except (ValueError, TypeError):
            background_opacity = DEFAULT_BACKGROUND_OPACITY

        # System and runtime
        start_win = bool(data.get("start_with_windows", DEFAULT_START_WITH_WINDOWS))

        raw_ret = data.get("retention_days", DEFAULT_DATA_RETENTION_DAYS)
        try:
            retention_days = max(0, int(raw_ret))
        except (ValueError, TypeError):
            retention_days = DEFAULT_DATA_RETENTION_DAYS

        raw_rwin = data.get("rolling_window_size", DEFAULT_ROLLING_WINDOW_SIZE)
        try:
            rolling_window_size = max(1, min(10, int(raw_rwin)))
        except (ValueError, TypeError):
            rolling_window_size = DEFAULT_ROLLING_WINDOW_SIZE

        raw_flush = data.get("flush_interval_seconds", USAGE_FLUSH_INTERVAL_SECONDS)
        try:
            flush_interval = max(5.0, min(300.0, float(raw_flush)))
        except (ValueError, TypeError):
            flush_interval = USAGE_FLUSH_INTERVAL_SECONDS

        raw_sample = data.get("sample_interval_seconds", SAMPLE_INTERVAL_SECONDS)
        try:
            sample_interval = max(0.5, min(10.0, float(raw_sample)))
        except (ValueError, TypeError):
            sample_interval = SAMPLE_INTERVAL_SECONDS

        return cls(
            schema_version=schema_ver,
            widget_x=widget_x,
            widget_y=widget_y,
            locked_position=locked,
            widget_visible=visible,
            always_on_top=always_on_top,
            keep_in_taskbar=keep_in_taskbar,
            auto_select_nic=auto_select_nic,
            selected_interfaces=selected_interfaces,
            excluded_keywords=excluded_keywords,
            unit_system=unit_sys,
            unit_type=unit_type,
            fixed_unit=fixed_unit,
            decimal_precision=decimal_precision,
            arrow_style=raw_arrow,
            theme_mode=raw_theme,
            font_family=font_family,
            font_size=font_size,
            color_download=color_download,
            color_upload=color_upload,
            background_opacity=background_opacity,
            start_with_windows=start_win,
            retention_days=retention_days,
            rolling_window_size=rolling_window_size,
            sample_interval_seconds=sample_interval,
            flush_interval_seconds=flush_interval,
        )


class SettingsStore:
    """Manages reading, atomic writing, and validation of AppSettings."""

    def __init__(
        self,
        file_path: Path | None = None,
        bad_backup_path: Path | None = None,
    ) -> None:
        """Initialize settings store with file paths."""
        self.file_path = file_path or SETTINGS_FILE_PATH
        self.bad_backup_path = bad_backup_path or SETTINGS_BAD_BACKUP_PATH

    def load(self) -> AppSettings:
        """Load settings from JSON file.

        If missing: returns default settings.
        If corrupt: moves corrupt file to settings.json.bad, logs warning, and returns defaults.
        Performs forward-compatible schema migrations when necessary.

        Returns:
            Validated AppSettings instance.
        """
        if not self.file_path.exists():
            logger.info("Settings file does not exist. Using defaults: %s", self.file_path)
            return AppSettings()

        try:
            with open(self.file_path, "r", encoding="utf-8-sig") as f:
                raw_data = json.load(f)

            if not isinstance(raw_data, dict):
                raise ValueError("Settings root is not a JSON object")

            # Perform schema migrations if older schema version detected
            migrated_data = self._migrate_schema(raw_data)
            return AppSettings.from_dict(migrated_data)

        except Exception as exc:
            logger.warning(
                "Settings file corrupted or unreadable (%s). Backing up to %s: %s",
                self.file_path,
                self.bad_backup_path,
                exc,
            )
            # Create backup of bad file for user diagnostics
            try:
                self.bad_backup_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(self.file_path, self.bad_backup_path)
            except Exception as backup_exc:
                logger.error("Failed to backup bad settings file: %s", backup_exc)

            # Fall back to safe defaults
            return AppSettings()

    def save(self, settings: AppSettings) -> None:
        """Atomically persist AppSettings to disk.

        Correctness Rule 12:
        Writes to a temporary file in the same directory, flushes and syncs to disk,
        and atomically renames the temporary file over the target using os.replace.

        Args:
            settings: The AppSettings instance to persist.
        """
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.file_path.with_suffix(".tmp")

        data = asdict(settings)
        data["schema_version"] = SETTINGS_SCHEMA_VERSION

        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())

            # Atomic replace on Windows
            os.replace(tmp_path, self.file_path)
            logger.debug("Settings successfully saved atomically to %s", self.file_path)

        except Exception as exc:
            logger.error("Failed to atomically save settings to %s: %s", self.file_path, exc)
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
            raise

    def _migrate_schema(self, data: dict[str, Any]) -> dict[str, Any]:
        """Apply schema migrations incrementally for older settings versions.

        Args:
            data: Raw dictionary loaded from JSON.

        Returns:
            Migrated dictionary compatible with current SETTINGS_SCHEMA_VERSION.
        """
        _version = data.get("schema_version", 1)
        # In v1: nothing to migrate. Future versions can check _version.
        data["schema_version"] = SETTINGS_SCHEMA_VERSION
        return data
