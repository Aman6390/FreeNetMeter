"""Unit tests for newly added diagnostic dialogs and features.

Tests:
- ConnectionInfoDialog initialization and clipboard export.
- StopwatchDialog timer, metrics accumulation, and reset.
- AboutDialog and HelpDialog rendering.
- QuickLinks functions safety.
- DesktopSpeedWidget corner snapping and pause toggling.
"""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from core.formatter import SpeedFormatter
from core.speed_calculator import SpeedSample
from storage.settings_store import AppSettings
from ui.about_dialog import AboutDialog
from ui.connection_info_dialog import ConnectionInfoDialog
from ui.help_dialog import HelpDialog
from ui.stopwatch_dialog import StopwatchDialog
from ui.widget import DesktopSpeedWidget


def get_qapp() -> QApplication:
    """Ensure singleton QApplication."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_connection_info_dialog() -> None:
    """Verify ConnectionInfoDialog initializes and populates without error."""
    _ = get_qapp()
    settings = AppSettings()
    dialog = ConnectionInfoDialog(settings=settings)
    assert dialog.windowTitle() == "FreeNetMeter - Connection Information"

    # Test clipboard export function
    dialog._copy_to_clipboard()
    assert dialog._btn_copy.text() == "Copied!"


def test_stopwatch_dialog_flow() -> None:
    """Verify StopwatchDialog timer, accumulation, and reset."""
    _ = get_qapp()
    settings = AppSettings()
    formatter = SpeedFormatter()
    dialog = StopwatchDialog(settings=settings, formatter=formatter)

    # Initially stopped
    assert not dialog._is_running
    assert dialog._session_bytes_down == 0

    # Start stopwatch
    dialog._toggle_stopwatch()
    assert dialog._is_running

    # Simulate speed sample
    sample = SpeedSample(
        timestamp=100.0,
        elapsed_seconds=1.0,
        total_download_speed=1_000_000.0,
        total_upload_speed=500_000.0,
        total_raw_download_speed=1_000_000.0,
        total_raw_upload_speed=500_000.0,
        total_delta_recv=1_000_000,
        total_delta_sent=500_000,
        per_interface={},
        selected_interfaces=("Wi-Fi",),
    )
    dialog.on_speed_sample(sample)
    assert dialog._session_bytes_down == 1_000_000
    assert dialog._session_bytes_up == 500_000
    assert dialog._peak_speed_down == 1_000_000.0

    # Pause stopwatch
    dialog._toggle_stopwatch()
    assert not dialog._is_running

    # Reset stopwatch
    dialog._reset_stopwatch()
    assert dialog._session_bytes_down == 0
    assert dialog._peak_speed_down == 0.0


def test_about_and_help_dialogs() -> None:
    """Verify AboutDialog and HelpDialog instantiate cleanly."""
    _ = get_qapp()
    settings = AppSettings()

    about = AboutDialog(settings=settings)
    assert "About FreeNetMeter" in about.windowTitle()

    help_dlg = HelpDialog(settings=settings)
    assert "How To Use" in help_dlg.windowTitle()


def test_widget_snapping_and_pause() -> None:
    """Verify corner snapping and pause toggle on DesktopSpeedWidget."""
    _ = get_qapp()
    settings = AppSettings()
    formatter = SpeedFormatter()

    saved: list[AppSettings] = []
    widget = DesktopSpeedWidget(
        settings=settings,
        formatter=formatter,
        on_open_settings=lambda: None,
        on_open_usage=lambda: None,
        on_exit_app=lambda: None,
        on_save_settings=lambda s: saved.append(s),
    )

    # Test snap
    widget.snap_to_position("top-right")
    assert widget.x() > 0
    assert widget.y() > 0

    # Test pause
    widget._toggle_pause(True)
    assert widget._is_paused
    assert widget._lbl_up_val.text() == "PAUSED"
    assert widget._lbl_down_val.text() == "PAUSED"

    widget._toggle_pause(False)
    assert not widget._is_paused
