"""Renders high-fidelity visual snapshots of the Master Dashboard window for visual inspection."""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtWidgets import QApplication, QFrame, QLabel

from core.formatter import SpeedFormatter
from core.speed_test_engine import SpeedTestSamplePoint
from storage.settings_store import SettingsStore
from storage.usage_database import UsageDatabase
from ui.dashboard_window import MasterDashboardWindow


def set_card(card: QFrame, text: str) -> None:
    lbl = card.findChild(QLabel, "val")
    if lbl:
        lbl.setText(text)


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)

    settings = SettingsStore()
    db = UsageDatabase(Path("test_preview_usage.db"))
    formatter = SpeedFormatter()

    dash = MasterDashboardWindow(db, settings.load(), formatter, lambda s: None)
    dash.resize(1060, 680)
    dash.show()

    # 1. Capture Main Dashboard Overview (Tab 0)
    dash._sidebar.select_index(0)
    app.processEvents()

    out_dir = Path(r"C:\Users\Dell\.gemini\antigravity\brain\47f5e522-787b-48c2-8c5f-76c661dee67b")
    pix_overview = dash.grab()
    pix_overview.save(str(out_dir / "dashboard_preview_overview.png"))
    print("Saved overview snapshot.")

    # 2. Switch to Speed Test Tab (Tab 3) and inject sample speed test state
    dash._sidebar.select_index(3)
    dash._gauge.set_speed(542.8)
    dash._gauge.set_status("Testing Download Throughput...", "#007AFF")

    # Populate live graph with realistic progression
    for i in range(25):
        t = i * 0.4
        spd = 100.0 + (442.8 * (1 - 2.718 ** (-t / 2.0))) + ((i % 3) * 15.0)
        lat = 18.0 + (i % 4) * 2.5
        dash._live_graph.add_sample(
            SpeedTestSamplePoint(elapsed_s=t, speed_mbps=spd, latency_ms=lat, stage="download")
        )

    # Populate latency & stability cards
    set_card(dash._card_idle, "18.4")
    set_card(dash._card_loaded_down, "24.1")
    set_card(dash._card_loaded_up, "21.8")
    set_card(dash._card_loss, "0.0%")
    set_card(dash._card_bufferbloat, "A+")

    # Populate metric cards
    set_card(dash._card_down, "542.8")
    set_card(dash._card_up, "128.5")
    set_card(dash._card_ping, "18 ms")
    set_card(dash._card_jitter, "2.1 ms")

    # Populate connection quality ratings
    dash._lbl_qual_stream.setText("4K Ultra HD Seamless")
    dash._lbl_qual_gaming.setText("Competitive / Low Latency")
    dash._lbl_qual_video.setText("HD Multi-party Conference")

    app.processEvents()

    pix_speedtest = dash.grab()
    pix_speedtest.save(str(out_dir / "dashboard_preview_speedtest.png"))
    print("Saved speedtest snapshot.")

    # Clean up test DB
    try:
        Path("test_preview_usage.db").unlink(missing_ok=True)
    except Exception:
        pass


if __name__ == "__main__":
    main()
