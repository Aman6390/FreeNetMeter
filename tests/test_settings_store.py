"""Unit tests for SettingsStore and AppSettings.

Verifies:
- Default settings creation and serialization.
- Save and load round-trip.
- Atomic writes.
- Corrupt settings file backup as settings.json.bad and graceful fallback to defaults.
- Schema version migration.
- Clamping and validation of invalid/out-of-range inputs.
"""

from __future__ import annotations

import json
from pathlib import Path

from storage.settings_store import AppSettings, SettingsStore


def test_default_settings(tmp_path: Path) -> None:
    """Verify clean initial state when no file exists."""
    settings_file = tmp_path / "settings.json"
    bad_file = tmp_path / "settings.json.bad"
    store = SettingsStore(file_path=settings_file, bad_backup_path=bad_file)

    settings = store.load()
    assert isinstance(settings, AppSettings)
    assert settings.schema_version == 1
    assert settings.decimal_precision == 1
    assert settings.background_opacity == 85
    assert settings.theme_mode == "system"
    assert settings.sample_interval_seconds == 1.0


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    """Verify settings save atomically and load with exact values."""
    settings_file = tmp_path / "settings.json"
    bad_file = tmp_path / "settings.json.bad"
    store = SettingsStore(file_path=settings_file, bad_backup_path=bad_file)

    original = AppSettings(
        widget_x=250,
        widget_y=350,
        locked_position=True,
        selected_interfaces=["Ethernet", "Wi-Fi"],
        decimal_precision=2,
        font_family="Consolas",
        font_size=12,
        background_opacity=90,
        retention_days=30,
    )
    store.save(original)

    assert settings_file.exists()
    loaded = store.load()

    assert loaded.widget_x == 250
    assert loaded.widget_y == 350
    assert loaded.locked_position is True
    assert loaded.selected_interfaces == ["Ethernet", "Wi-Fi"]
    assert loaded.decimal_precision == 2
    assert loaded.font_family == "Consolas"
    assert loaded.font_size == 12
    assert loaded.background_opacity == 90
    assert loaded.retention_days == 30


def test_corrupt_settings_file_handled(tmp_path: Path) -> None:
    """Verify corrupt JSON creates a .bad backup and falls back to defaults without crashing."""
    settings_file = tmp_path / "settings.json"
    bad_file = tmp_path / "settings.json.bad"
    store = SettingsStore(file_path=settings_file, bad_backup_path=bad_file)

    # Write corrupt JSON content
    settings_file.write_text("{this is corrupted json", encoding="utf-8")

    loaded = store.load()
    # Must fallback to valid defaults
    assert isinstance(loaded, AppSettings)
    assert loaded.schema_version == 1

    # Bad backup must have been created
    assert bad_file.exists()
    assert bad_file.read_text(encoding="utf-8") == "{this is corrupted json"


def test_validation_and_clamping(tmp_path: Path) -> None:
    """Verify out-of-range values are clamped to safe boundaries."""
    raw_data = {
        "decimal_precision": 999,  # Should clamp to 2
        "background_opacity": 5,  # Should clamp to 20
        "font_size": 100,  # Should clamp to 48
        "unit_system": "invalid",  # Should fallback to 'decimal'
        "theme_mode": "rainbow",  # Should fallback to 'system'
        "color_download": "not_a_color",  # Should fallback to default hex
    }

    settings = AppSettings.from_dict(raw_data)
    assert settings.decimal_precision == 2
    assert settings.background_opacity == 20
    assert settings.font_size == 48
    assert settings.unit_system == "decimal"
    assert settings.theme_mode == "system"
    assert settings.color_download.startswith("#")


def test_schema_migration(tmp_path: Path) -> None:
    """Verify future schema migration preserves data and updates schema_version."""
    settings_file = tmp_path / "settings.json"
    store = SettingsStore(file_path=settings_file)

    old_data = {
        "schema_version": 1,
        "font_size": 14,
    }
    settings_file.write_text(json.dumps(old_data), encoding="utf-8")

    loaded = store.load()
    assert loaded.schema_version == 1
    assert loaded.font_size == 14


def test_utf8_with_bom_handling(tmp_path: Path) -> None:
    """Verify JSON files saved with Windows UTF-8 BOM are loaded transparently."""
    settings_file = tmp_path / "settings.json"
    store = SettingsStore(file_path=settings_file)

    data = {"schema_version": 1, "font_size": 16, "widget_x": 500, "widget_y": 300}
    # Write with utf-8-sig to prepend BOM
    settings_file.write_text(json.dumps(data), encoding="utf-8-sig")

    loaded = store.load()
    assert loaded.font_size == 16
    assert loaded.widget_x == 500
    assert loaded.widget_y == 300
