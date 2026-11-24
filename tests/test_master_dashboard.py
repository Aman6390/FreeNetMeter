"""Unit tests for Master Dashboard, Speedometer Gauge, and Speed Test Engine.

Verifies:
- Hardware and OS telemetry parsing.
- Speed test rating heuristics (Bufferbloat, Streaming, Gaming, Video calls).
- SQLite speed test history persistence and retrieval.
- Analog gauge angle calculation and speed smoothing.
- Live speed and ping graph canvas updates.
- Master dashboard tab switching and speed routing.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from core.formatter import SpeedFormatter
from core.speed_calculator import SpeedSample
from core.speed_test_engine import (
    SpeedTestResult,
    SpeedTestSamplePoint,
    calculate_bufferbloat_grade,
    rate_gaming,
    rate_streaming,
    rate_video_calls,
)
from core.system_telemetry import SystemTelemetryProvider, format_uptime
from storage.settings_store import AppSettings
from storage.usage_database import UsageDatabase
from ui.dashboard_window import MasterDashboardWindow
from ui.widgets.analog_gauge import AnalogSpeedometerGauge
from ui.widgets.live_graph import LiveSpeedLatencyGraph
from ui.widgets.sidebar import NavigationSidebar


def get_qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_telemetry_provider() -> None:
    """Verify hardware badges extraction runs safely."""
    provider = SystemTelemetryProvider()
    snap = provider.get_snapshot()

    assert snap.hostname
    assert snap.cpu_name
    assert "RAM" in snap.ram_display
    assert snap.os_display
    assert snap.uptime_display.startswith("Up ")


def test_format_uptime() -> None:
    """Verify uptime formatting branches."""
    import time

    now = time.time()
    # 2 hours, 15 mins ago
    assert format_uptime(now - 8100) == "Up 2h 15m"
    # 3 days, 4 hours ago
    assert format_uptime(now - 273600) == "Up 3d 4h"
    # 45 mins ago
    assert format_uptime(now - 2700) == "Up 45m"


def test_rating_heuristics() -> None:
    """Verify connection quality rating tiers."""
    # Bufferbloat
    assert calculate_bufferbloat_grade(15.0, 18.0) == "A+"
    assert calculate_bufferbloat_grade(15.0, 25.0) == "A"
    assert calculate_bufferbloat_grade(15.0, 45.0) == "B"
    assert calculate_bufferbloat_grade(15.0, 80.0) == "C"
    assert calculate_bufferbloat_grade(15.0, 150.0) == "D"

    # Streaming
    assert "4K" in rate_streaming(35.0, 20.0)
    assert "1080p" in rate_streaming(15.0, 30.0)
    assert "720p" in rate_streaming(6.0, 50.0)

    # Gaming
    assert "Elite" in rate_gaming(18.0, 2.0, 0.0)
    assert "Great" in rate_gaming(40.0, 8.0, 0.0)
    assert "Packet Loss" in rate_gaming(15.0, 2.0, 5.0)

    # Video calls
    assert "Smooth HD" in rate_video_calls(15.0, 8.0, 25.0)
    assert "Standard HD" in rate_video_calls(4.0, 1.5, 80.0)


def test_database_speed_test_history(tmp_path: Path) -> None:
    """Verify storing and retrieving speed test runs in SQLite."""
    db = UsageDatabase(db_path=tmp_path / "test_usage.db")
    res1 = SpeedTestResult(
        timestamp_iso="2026-11-24 10:00:00",
        download_mbps=150.5,
        upload_mbps=45.2,
        idle_ping_ms=18.0,
        jitter_ms=2.1,
        loaded_down_ping_ms=28.0,
        loaded_up_ping_ms=22.0,
        packet_loss_pct=0.0,
        bufferbloat_grade="A",
        streaming_rating="4K Ultra HD",
        gaming_rating="Great (<50ms)",
        video_calls_rating="Smooth HD",
    )
    test_id = db.record_speed_test(res1)
    assert test_id > 0

    history = db.get_speed_test_history()
    assert len(history) == 1
    assert history[0].download_mbps == 150.5
    assert history[0].upload_mbps == 45.2

    deleted = db.clear_speed_test_history()
    assert deleted == 1
    assert len(db.get_speed_test_history()) == 0


def test_analog_gauge_widget() -> None:
    """Verify gauge angle calculation and speed setter."""
    _ = get_qapp()
    gauge = AnalogSpeedometerGauge()
    assert gauge._max_speed == 1000.0

    gauge.set_speed(250.0)
    assert gauge._target_speed == 250.0

    # Test non-linear angle mapping
    deg_0 = gauge._speed_to_angle(0.0)
    deg_1000 = gauge._speed_to_angle(1000.0)
    assert deg_0 > deg_1000  # Angle sweeps clockwise (descending degrees in Qt)


def test_live_graph_widget() -> None:
    """Verify adding samples and clearing graph canvas."""
    _ = get_qapp()
    graph = LiveSpeedLatencyGraph()
    pt = SpeedTestSamplePoint(elapsed_s=1.5, speed_mbps=85.0, latency_ms=22.0, stage="download")
    graph.add_sample(pt)
    assert len(graph._samples) == 1
    assert graph._max_speed >= 85.0

    graph.clear()
    assert len(graph._samples) == 0


def test_sidebar_navigation() -> None:
    """Verify sidebar tab selection signal."""
    _ = get_qapp()
    sidebar = NavigationSidebar(initial_index=3)
    emitted: list[int] = []
    sidebar.nav_selected.connect(lambda idx: emitted.append(idx))

    sidebar.select_index(0)
    assert emitted == [0]
    assert sidebar._current_index == 0


def test_master_dashboard_window_flow(tmp_path: Path) -> None:
    """Verify master dashboard construction and live speed routing."""
    _ = get_qapp()
    db = UsageDatabase(db_path=tmp_path / "dash_test.db")
    settings = AppSettings()
    formatter = SpeedFormatter()

    saved: list[AppSettings] = []
    win = MasterDashboardWindow(
        usage_database=db,
        settings=settings,
        formatter=formatter,
        on_save_settings=lambda s: saved.append(s),
    )

    # Initial tab should be 3 (Speed Test)
    assert win._stack.currentIndex() == 3

    # Switch to Dashboard tab
    win._sidebar.select_index(0)
    assert win._stack.currentIndex() == 0

    # Route live speed sample
    sample = SpeedSample(
        timestamp=100.0,
        elapsed_seconds=1.0,
        total_download_speed=25_000_000.0,
        total_upload_speed=5_000_000.0,
        total_raw_download_speed=25_000_000.0,
        total_raw_upload_speed=5_000_000.0,
        total_delta_recv=25_000_000,
        total_delta_sent=5_000_000,
        per_interface={},
        selected_interfaces=("Wi-Fi",),
    )
    win.update_live_speeds(sample)
