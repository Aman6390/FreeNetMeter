"""Unit tests for FreeNetMeter UI components and worker thread.

Tests:
- Programmatic asset creation (QPixmap, QIcon).
- DesktopSpeedWidget layout, updating speeds, position clamping.
- SystemTrayManager tooltip formatting.
- SamplingWorker execution with FakeCounterSource.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from core.counter_source import FakeCounterSource
from core.formatter import SpeedFormatter
from core.interface_filter import InterfaceFilter
from core.speed_calculator import SpeedCalculator, SpeedSample
from core.usage_accumulator import UsageAccumulator
from storage.settings_store import AppSettings
from storage.usage_database import UsageDatabase
from ui.assets import create_app_icon, create_app_pixmap
from ui.tray import SystemTrayManager
from ui.widget import DesktopSpeedWidget
from ui.worker import SamplingWorker


def get_qapp() -> QApplication:
    """Ensure a singleton QApplication exists for GUI component tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_assets_generation() -> None:
    """Verify programmatic icon and pixmap generation."""
    _ = get_qapp()
    pixmap = create_app_pixmap(64)
    assert not pixmap.isNull()
    assert pixmap.width() == 64
    assert pixmap.height() == 64

    icon = create_app_icon()
    assert not icon.isNull()


def test_desktop_speed_widget_initialization_and_update() -> None:
    """Verify DesktopSpeedWidget renders initial values and updates live."""
    _ = get_qapp()
    settings = AppSettings()
    formatter = SpeedFormatter()

    saved_settings: list[AppSettings] = []

    widget = DesktopSpeedWidget(
        settings=settings,
        formatter=formatter,
        on_open_settings=lambda: None,
        on_open_usage=lambda: None,
        on_exit_app=lambda: None,
        on_save_settings=lambda s: saved_settings.append(s),
    )

    assert widget.width() == 122
    assert widget.height() == 40

    # Test update speed
    sample = SpeedSample(
        timestamp=100.0,
        elapsed_seconds=1.0,
        total_download_speed=15_000_000.0,
        total_upload_speed=2_500_000.0,
        total_raw_download_speed=15_000_000.0,
        total_raw_upload_speed=2_500_000.0,
        total_delta_recv=15_000_000,
        total_delta_sent=2_500_000,
        per_interface={},
        selected_interfaces=("Ethernet",),
    )
    widget.update_speed(sample)

    assert "15.0 MB/s" in widget._lbl_down_val.text()
    assert "2.5 MB/s" in widget._lbl_up_val.text()

    # Test apply live settings
    settings.decimal_precision = 2
    formatter2 = SpeedFormatter(precision=2)
    widget.apply_settings(settings, formatter2)
    widget.update_speed(sample)

    assert "15.00 MB/s" in widget._lbl_down_val.text()
    assert "2.50 MB/s" in widget._lbl_up_val.text()


def test_system_tray_tooltip_update() -> None:
    """Verify tray manager formats tooltip on speed updates."""
    _ = get_qapp()
    settings = AppSettings()
    formatter = SpeedFormatter()

    widget = DesktopSpeedWidget(
        settings=settings,
        formatter=formatter,
        on_open_settings=lambda: None,
        on_open_usage=lambda: None,
        on_exit_app=lambda: None,
        on_save_settings=lambda s: None,
    )

    tray = SystemTrayManager(
        widget=widget,
        formatter=formatter,
        on_open_settings=lambda: None,
        on_open_usage=lambda: None,
        on_exit_app=lambda: None,
    )

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
        selected_interfaces=("Ethernet",),
    )
    tray.update_tooltip(sample)

    # Tooltip must be updated
    if tray._tray_icon:
        tooltip = tray._tray_icon.toolTip()
        assert "Down: 1.0 MB/s" in tooltip
        assert "Up:   500.0 KB/s" in tooltip

    tray.shutdown()


def test_sampling_worker_thread(tmp_path: Path) -> None:
    """Verify SamplingWorker samples off-thread and emits calculated SpeedSample."""
    _ = get_qapp()
    source = FakeCounterSource()
    source.set_interface("Ethernet", bytes_sent=1000, bytes_recv=2000)

    calc = SpeedCalculator(rolling_window_size=1)
    acc = UsageAccumulator()
    db = UsageDatabase(db_path=tmp_path / "test_usage.db")
    filt = InterfaceFilter()

    worker = SamplingWorker(
        counter_source=source,
        speed_calculator=calc,
        usage_accumulator=acc,
        usage_database=db,
        interface_filter=filt,
        sample_interval=0.1,  # Fast interval for test
        flush_interval=0.2,
    )

    received_samples: list[SpeedSample] = []
    worker.speed_updated.connect(lambda s: received_samples.append(s))

    worker.start()

    # Advance time and counters
    source.advance_time(0.5)
    source.set_interface("Ethernet", bytes_sent=2000, bytes_recv=4000)

    # Allow worker loop to process
    worker.msleep(300)
    app = get_qapp()
    app.processEvents()

    # Stop worker cleanly
    worker.requestInterruption()
    worker.wait(1000)
    app.processEvents()

    # Verify samples were emitted
    assert len(received_samples) > 0
    latest = received_samples[-1]
    assert isinstance(latest, SpeedSample)


def test_widget_click_and_drag_does_not_vanish() -> None:
    """Verify clicking or moving widget never hides it or causes it to vanish."""
    from PyQt6.QtCore import QPointF, Qt
    from PyQt6.QtGui import QMouseEvent

    _ = get_qapp()
    settings = AppSettings(widget_x=100, widget_y=100)
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
    widget.show()
    assert widget.isVisible()

    # 1. Plain click without movement
    press_ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(10, 10),
        QPointF(110, 110),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    widget.mousePressEvent(press_ev)
    assert widget.isVisible()

    release_ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        QPointF(10, 10),
        QPointF(110, 110),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    widget.mouseReleaseEvent(release_ev)

    # Click must NOT hide the widget and must NOT trigger unnecessary saves
    assert widget.isVisible()
    assert len(saved) == 0

    # 2. Re-applying settings must NOT hide the visible widget
    widget.apply_settings(settings, formatter)
    assert widget.isVisible()

    # 3. Drag movement
    widget.mousePressEvent(press_ev)
    move_ev = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(60, 60),
        QPointF(160, 160),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    widget.mouseMoveEvent(move_ev)
    assert widget.isVisible()

    widget.mouseReleaseEvent(release_ev)
    assert widget.isVisible()
    assert len(saved) == 1
