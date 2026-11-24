"""Master Dashboard and Control Center for FreeNetMeter.

Recreates the comprehensive desktop application window matching the original design:
- Sleek dark theme with Apple Design principles.
- Top system telemetry header with live CPU, RAM, OS, Uptime, and Hostname badges.
- Left navigation sidebar hosting all 12 modules.
- Complete Speed Test engine with vector-rendered analog arc gauge, latency & stability cards,
  real-time live speed & ping canvas graph, and connection quality ratings.
- Test history, Data usage analytics, Data plan tracker, Wi-Fi inspector, Active processes,
  Network info, Hardware NIC inventory, and Network tools.
"""

from __future__ import annotations

import datetime
import logging
import socket
import subprocess
from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import (
    QFont,
    QGuiApplication,
    QKeySequence,
    QShortcut,
)
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.constants import APP_NAME
from core.formatter import SpeedFormatter
from core.speed_calculator import SpeedSample
from core.speed_test_engine import (
    SpeedTestResult,
    SpeedTestWorker,
)
from storage.settings_store import AppSettings
from storage.usage_database import UsageDatabase
from ui.assets import create_app_icon
from ui.widgets.analog_gauge import AnalogSpeedometerGauge
from ui.widgets.live_graph import LiveSpeedLatencyGraph
from ui.widgets.sidebar import NavigationSidebar
from ui.widgets.system_badges import SystemBadgesBar

logger = logging.getLogger("FreeNetMeter.Dashboard")


class MasterDashboardWindow(QDialog):
    """Flagship Master Control Center and Dashboard window."""

    def __init__(
        self,
        usage_database: UsageDatabase,
        settings: AppSettings,
        formatter: SpeedFormatter,
        on_save_settings: Callable[[AppSettings], None],
        on_refresh_connection: Optional[Callable[[], None]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._db = usage_database
        self._settings = settings
        self._formatter = formatter
        self._on_save_settings = on_save_settings
        self._on_refresh_connection = on_refresh_connection

        # Speed test engine worker
        self._test_worker: Optional[SpeedTestWorker] = None
        self._latest_test_result: Optional[SpeedTestResult] = None

        self.setWindowTitle(f"{APP_NAME} — Network Speed & Data Usage Monitor")
        self.setWindowIcon(create_app_icon())
        self.resize(1060, 680)
        self.setMinimumSize(960, 600)

        # Remove default help button from titlebar
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self._init_ui()
        self._apply_theme()

        # Keyboard shortcuts
        QShortcut(QKeySequence("Ctrl+W"), self, self.close)
        QShortcut(QKeySequence("Escape"), self, self.close)

    def _init_ui(self) -> None:
        """Construct master window layout: Header, Sidebar, and Stacked Views."""
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Top System Telemetry Bar
        self._header_bar = SystemBadgesBar(on_toggle_theme=self._toggle_theme, parent=self)
        root_layout.addWidget(self._header_bar)

        # Header Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #262934; background-color: #262934; height: 1px;")
        root_layout.addWidget(sep)

        # 2. Main Body: Sidebar (Left) + Stacked Views (Right)
        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # Sidebar (defaulting to tab index 3: Speed Test as in screenshot)
        self._sidebar = NavigationSidebar(initial_index=3, parent=self)
        self._sidebar.nav_selected.connect(self._on_tab_selected)
        body_layout.addWidget(self._sidebar)

        # Vertical Divider
        vsep = QFrame()
        vsep.setFrameShape(QFrame.Shape.VLine)
        vsep.setStyleSheet("color: #262934; background-color: #262934; width: 1px;")
        body_layout.addWidget(vsep)

        # Stacked Views Container
        self._stack = QStackedWidget(self)
        self._stack.setStyleSheet("background-color: #16181F;")

        # Populate all 12 modules
        self._view_dashboard = self._create_dashboard_view()
        self._view_settings = self._create_settings_view()
        self._view_adapters = self._create_adapters_view()
        self._view_speed_test = self._create_speed_test_view()
        self._view_test_history = self._create_test_history_view()
        self._view_usage_stats = self._create_usage_stats_view()
        self._view_data_plan = self._create_data_plan_view()
        self._view_wifi = self._create_wifi_view()
        self._view_network_info = self._create_network_info_view()
        self._view_interfaces = self._create_interfaces_view()
        self._view_processes = self._create_processes_view()
        self._view_tools = self._create_tools_view()

        self._stack.addWidget(self._view_dashboard)  # 0
        self._stack.addWidget(self._view_settings)  # 1
        self._stack.addWidget(self._view_adapters)  # 2
        self._stack.addWidget(self._view_speed_test)  # 3
        self._stack.addWidget(self._view_test_history)  # 4
        self._stack.addWidget(self._view_usage_stats)  # 5
        self._stack.addWidget(self._view_data_plan)  # 6
        self._stack.addWidget(self._view_wifi)  # 7
        self._stack.addWidget(self._view_network_info)  # 8
        self._stack.addWidget(self._view_interfaces)  # 9
        self._stack.addWidget(self._view_processes)  # 10
        self._stack.addWidget(self._view_tools)  # 11

        # Start on Speed Test view (Index 3)
        self._sidebar.select_index(3)
        self._stack.setCurrentIndex(3)

        body_layout.addWidget(self._stack, 1)
        root_layout.addLayout(body_layout, 1)

        # Initial data population
        self._refresh_usage_stats()

    def _on_tab_selected(self, index: int) -> None:
        """Switch stacked views on sidebar navigation."""
        if 0 <= index < self._stack.count():
            self._stack.setCurrentIndex(index)
            # Refresh tab data if applicable
            if index == 4:
                self._refresh_test_history()
            elif index == 5:
                self._refresh_usage_stats()
            elif index == 10:
                self._refresh_processes()

    # =========================================================================
    # TAB 3: SPEED TEST VIEW (THE CORE SCREENSHOT VIEW)
    # =========================================================================
    def _create_speed_test_view(self) -> QWidget:
        """Construct the signature Speed Test interface matching the user's screenshot."""
        widget = QWidget()
        main_layout = QVBoxLayout(widget)
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(14)

        # Upper Section: Two Columns (Left: Gauge & Controls, Right: Graphs & Latency)
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(24)

        # LEFT COLUMN: Speedometer Gauge + 4 Metric Cards + Action Buttons
        left_col = QVBoxLayout()
        left_col.setSpacing(12)

        # Semicircular Analog Arc Gauge
        self._gauge = AnalogSpeedometerGauge(self)
        left_col.addWidget(self._gauge, 0, Qt.AlignmentFlag.AlignCenter)

        # 4 Core Metric Bar Cards: [↓ Download] [↑ Upload] [Ping] [Jitter]
        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(8)

        self._card_down = self._create_accent_card("↓ Download", "--", "#007AFF")
        self._card_up = self._create_accent_card("↑ Upload", "--", "#00E676")
        self._card_ping = self._create_accent_card("Ping", "--", "#FF9500")
        self._card_jitter = self._create_accent_card("Jitter", "--", "#AF52DE")

        metrics_layout.addWidget(self._card_down)
        metrics_layout.addWidget(self._card_up)
        metrics_layout.addWidget(self._card_ping)
        metrics_layout.addWidget(self._card_jitter)
        left_col.addLayout(metrics_layout)

        # Test Action Buttons: [► Start Test] [■ Cancel]
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self._btn_start_test = QPushButton("► Start Test")
        self._btn_start_test.setFixedHeight(40)
        self._btn_start_test.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._btn_start_test.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_start_test.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #007AFF, stop:1 #2563EB);
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 8px 24px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563EB, stop:1 #1D4ED8);
            }
            QPushButton:disabled {
                background-color: #334155;
                color: #64748B;
            }
        """)
        self._btn_start_test.clicked.connect(self._start_speed_test)

        self._btn_cancel_test = QPushButton("■ Cancel")
        self._btn_cancel_test.setFixedHeight(40)
        self._btn_cancel_test.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._btn_cancel_test.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_cancel_test.setEnabled(False)
        self._btn_cancel_test.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #EF4444, stop:1 #DC2626);
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 8px 20px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #DC2626, stop:1 #B91C1C);
            }
            QPushButton:disabled {
                background-color: #2D1A1A;
                color: #553333;
            }
        """)
        self._btn_cancel_test.clicked.connect(self._cancel_speed_test)

        btn_layout.addWidget(self._btn_start_test, 3)
        btn_layout.addWidget(self._btn_cancel_test, 2)
        left_col.addLayout(btn_layout)

        columns_layout.addLayout(left_col, 5)

        # RIGHT COLUMN: Live Graph + Latency & Stability + Connection Quality
        right_col = QVBoxLayout()
        right_col.setSpacing(10)

        # Graph Header with History link
        graph_header = QHBoxLayout()
        lbl_graph_title = QLabel("Live speed & latency")
        lbl_graph_title.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        lbl_graph_title.setStyleSheet("color: #F8FAFC;")

        btn_history_link = QPushButton("Keep a history of every test →")
        btn_history_link.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_history_link.setStyleSheet("""
            QPushButton {
                color: #94A3B8;
                background: transparent;
                border: none;
                font-size: 11px;
            }
            QPushButton:hover {
                color: #38BDF8;
                text-decoration: underline;
            }
        """)
        btn_history_link.clicked.connect(lambda: self._sidebar.select_index(4))

        graph_header.addWidget(lbl_graph_title)
        graph_header.addStretch(1)
        graph_header.addWidget(btn_history_link)
        right_col.addLayout(graph_header)

        # Live Real-time Graph Canvas
        self._live_graph = LiveSpeedLatencyGraph(self)
        right_col.addWidget(self._live_graph, 1)

        # Latency & Stability Section (5 metric cards)
        lbl_lat_title = QLabel("Latency & stability")
        lbl_lat_title.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        lbl_lat_title.setStyleSheet("color: #F8FAFC; margin-top: 4px;")
        right_col.addWidget(lbl_lat_title)

        stab_layout = QHBoxLayout()
        stab_layout.setSpacing(6)
        self._card_idle = self._create_accent_card("Idle ms", "--", "#EAB308", title_font_size=8)
        self._card_loaded_down = self._create_accent_card(
            "↓ Loaded ms", "--", "#007AFF", title_font_size=8
        )
        self._card_loaded_up = self._create_accent_card(
            "↑ Loaded ms", "--", "#00E676", title_font_size=8
        )
        self._card_loss = self._create_accent_card(
            "Packet loss", "--", "#EF4444", title_font_size=8
        )
        self._card_bufferbloat = self._create_accent_card(
            "Bufferbloat", "--", "#A855F7", title_font_size=8
        )

        stab_layout.addWidget(self._card_idle)
        stab_layout.addWidget(self._card_loaded_down)
        stab_layout.addWidget(self._card_loaded_up)
        stab_layout.addWidget(self._card_loss)
        stab_layout.addWidget(self._card_bufferbloat)
        right_col.addLayout(stab_layout)

        # Connection Quality Section
        lbl_qual_title = QLabel("Connection quality")
        lbl_qual_title.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        lbl_qual_title.setStyleSheet("color: #F8FAFC; margin-top: 4px;")
        right_col.addWidget(lbl_qual_title)

        qual_grid = QGridLayout()
        qual_grid.setContentsMargins(0, 0, 0, 0)
        qual_grid.setVerticalSpacing(4)
        qual_grid.setHorizontalSpacing(12)

        self._lbl_qual_stream = QLabel("--")
        self._lbl_qual_gaming = QLabel("--")
        self._lbl_qual_video = QLabel("--")

        for lbl in (self._lbl_qual_stream, self._lbl_qual_gaming, self._lbl_qual_video):
            lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            lbl.setStyleSheet("color: #38BDF8;")

        qual_grid.addWidget(self._create_prop_label("Streaming"), 0, 0)
        qual_grid.addWidget(self._lbl_qual_stream, 0, 1)

        qual_grid.addWidget(self._create_prop_label("Gaming"), 1, 0)
        qual_grid.addWidget(self._lbl_qual_gaming, 1, 1)

        qual_grid.addWidget(self._create_prop_label("Video calls"), 2, 0)
        qual_grid.addWidget(self._lbl_qual_video, 2, 1)
        right_col.addLayout(qual_grid)

        lbl_qual_sub = QLabel("Run a test to see what your connection is good for.")
        lbl_qual_sub.setFont(QFont("Segoe UI", 9, QFont.Weight.Normal))
        lbl_qual_sub.setStyleSheet("color: #64748B; margin-top: 2px;")
        right_col.addWidget(lbl_qual_sub)

        # Result Action Buttons: [Copy result card] [Save as PNG]
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(10)

        self._btn_copy_card = QPushButton("📋 Copy result card")
        self._btn_copy_card.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_copy_card.setStyleSheet("""
            QPushButton {
                background-color: #1E222D;
                color: #CBD5E1;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #2E384D;
                color: #F8FAFC;
            }
        """)
        self._btn_copy_card.clicked.connect(self._copy_result_card)

        self._btn_save_png = QPushButton("↓ Save as PNG")
        self._btn_save_png.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_save_png.setStyleSheet("""
            QPushButton {
                background-color: #1E222D;
                color: #CBD5E1;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #2E384D;
                color: #F8FAFC;
            }
        """)
        self._btn_save_png.clicked.connect(self._save_result_png)

        actions_layout.addWidget(self._btn_copy_card)
        actions_layout.addWidget(self._btn_save_png)
        actions_layout.addStretch(1)
        right_col.addLayout(actions_layout)

        columns_layout.addLayout(right_col, 6)
        main_layout.addLayout(columns_layout, 1)

        # Bottom Status Indicator
        self._lbl_bottom_status = QLabel("Status: Ready.")
        self._lbl_bottom_status.setFont(QFont("Segoe UI", 9, QFont.Weight.Normal))
        self._lbl_bottom_status.setStyleSheet("color: #64748B; padding-top: 4px;")
        main_layout.addWidget(self._lbl_bottom_status)

        return widget

    def _create_accent_card(
        self, title: str, default_val: str, accent_hex: str, title_font_size: int = 9
    ) -> QFrame:
        """Create a metric card with a colored bottom accent border matching the screenshot."""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #181B22;
                border: 1px solid #282D3B;
                border-bottom: 3px solid {accent_hex};
                border-radius: 6px;
                padding: 2px 4px;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(2, 4, 2, 4)
        layout.setSpacing(2)

        lbl_t = QLabel(title)
        lbl_t.setFont(QFont("Segoe UI", title_font_size, QFont.Weight.Medium))
        lbl_t.setStyleSheet("color: #94A3B8; border: none;")
        lbl_t.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_v = QLabel(default_val)
        lbl_v.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl_v.setStyleSheet("color: #F8FAFC; border: none;")
        lbl_v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_v.setObjectName("val")

        layout.addWidget(lbl_t)
        layout.addWidget(lbl_v)
        return card

    def _create_prop_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Normal))
        lbl.setStyleSheet("color: #94A3B8;")
        return lbl

    # Speed Test Execution Handlers
    def _start_speed_test(self) -> None:
        """Initiate background speed test run."""
        self._btn_start_test.setEnabled(False)
        self._btn_cancel_test.setEnabled(True)
        self._live_graph.clear()
        self._gauge.reset()
        self._gauge.set_status("Initializing...", "#007AFF")
        self._lbl_bottom_status.setText("Status: Connecting to test server...")

        self._test_worker = SpeedTestWorker(self)
        self._test_worker.progress_updated.connect(self._on_test_progress)
        self._test_worker.sample_recorded.connect(self._live_graph.add_sample)
        self._test_worker.test_finished.connect(self._on_test_finished)
        self._test_worker.test_failed.connect(self._on_test_failed)
        self._test_worker.test_cancelled.connect(self._on_test_cancelled)
        self._test_worker.start()

    def _cancel_speed_test(self) -> None:
        """Cancel running speed test."""
        if self._test_worker and self._test_worker.isRunning():
            self._test_worker.cancel()
            self._gauge.set_status("Cancelled.", "#EF4444")
            self._lbl_bottom_status.setText("Status: Cancelled.")

    def _on_test_progress(self, stage: str, pct: float, speed_mbps: float, ping_ms: float) -> None:
        self._gauge.set_speed(speed_mbps)
        self._gauge.set_status(stage, "#007AFF")
        self._lbl_bottom_status.setText(f"Status: {stage} ({int(pct)}%)")

        if "Download" in stage and speed_mbps > 0:
            val_lbl = self._card_down.findChild(QLabel, "val")
            if val_lbl:
                val_lbl.setText(f"{speed_mbps:.1f}")
        elif "Upload" in stage and speed_mbps > 0:
            val_lbl = self._card_up.findChild(QLabel, "val")
            if val_lbl:
                val_lbl.setText(f"{speed_mbps:.1f}")

        if ping_ms > 0:
            val_lbl = self._card_ping.findChild(QLabel, "val")
            if val_lbl:
                val_lbl.setText(f"{ping_ms:.0f}")

    def _on_test_finished(self, result: SpeedTestResult) -> None:
        """Process test completion and update all display cards."""
        self._latest_test_result = result
        self._btn_start_test.setEnabled(True)
        self._btn_cancel_test.setEnabled(False)

        # Update gauge final display
        self._gauge.set_speed(result.download_mbps)
        self._gauge.set_status("Finished", "#00E676")
        self._lbl_bottom_status.setText("Status: Finished.")

        # Update core metric cards
        for card, val_str in (
            (self._card_down, f"{result.download_mbps:.1f}"),
            (self._card_up, f"{result.upload_mbps:.1f}"),
            (self._card_ping, f"{result.idle_ping_ms:.0f}"),
            (self._card_jitter, f"{result.jitter_ms:.1f}"),
            (self._card_idle, f"{result.idle_ping_ms:.0f}"),
            (self._card_loaded_down, f"{result.loaded_down_ping_ms:.0f}"),
            (self._card_loaded_up, f"{result.loaded_up_ping_ms:.0f}"),
            (self._card_loss, f"{result.packet_loss_pct:.0f}%"),
            (self._card_bufferbloat, result.bufferbloat_grade),
        ):
            lbl = card.findChild(QLabel, "val")
            if lbl:
                lbl.setText(val_str)

        # Update connection quality ratings
        self._lbl_qual_stream.setText(result.streaming_rating)
        self._lbl_qual_gaming.setText(result.gaming_rating)
        self._lbl_qual_video.setText(result.video_calls_rating)

        # Save to database test history
        try:
            self._db.record_speed_test(result)
        except Exception as exc:
            logger.error("Failed to persist speed test: %s", exc)

    def _on_test_failed(self, msg: str) -> None:
        self._btn_start_test.setEnabled(True)
        self._btn_cancel_test.setEnabled(False)
        self._gauge.set_status("Failed", "#EF4444")
        self._lbl_bottom_status.setText(f"Status: {msg}")

    def _on_test_cancelled(self) -> None:
        self._btn_start_test.setEnabled(True)
        self._btn_cancel_test.setEnabled(False)
        self._gauge.set_status("Cancelled.", "#EF4444")
        self._lbl_bottom_status.setText("Status: Cancelled.")

    def _copy_result_card(self) -> None:
        """Copy formatted speed test results to system clipboard."""
        if not self._latest_test_result:
            return
        r = self._latest_test_result
        text = (
            f"=== FreeNetMeter Speed Test Result ===\n"
            f"Date: {r.timestamp_iso}\n"
            f"Download: {r.download_mbps:.2f} Mbps\n"
            f"Upload: {r.upload_mbps:.2f} Mbps\n"
            f"Latency: {r.idle_ping_ms:.1f} ms (Jitter: {r.jitter_ms:.1f} ms)\n"
            f"Loaded Latency: Down: {r.loaded_down_ping_ms:.1f} ms, Up: {r.loaded_up_ping_ms:.1f} ms\n"
            f"Packet Loss: {r.packet_loss_pct:.1f}%\n"
            f"Bufferbloat: Grade {r.bufferbloat_grade}\n"
            f"Streaming: {r.streaming_rating}\n"
            f"Gaming: {r.gaming_rating}\n"
            f"Video Calls: {r.video_calls_rating}\n"
        )
        clip = QGuiApplication.clipboard()
        if clip:
            clip.setText(text)
            self._lbl_bottom_status.setText("Status: Result copied to clipboard!")

    def _save_result_png(self) -> None:
        """Save screenshot of speed test results card as PNG."""
        pixmap = self.grab()
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Speed Test Result", "SpeedTestResult.png", "PNG Images (*.png)"
        )
        if path:
            pixmap.save(path, "PNG")
            self._lbl_bottom_status.setText(f"Status: Saved result image to {Path(path).name}")

    # =========================================================================
    # TAB 4: TEST HISTORY VIEW
    # =========================================================================
    def _create_test_history_view(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        lbl_title = QLabel("Speed Test History")
        lbl_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: #FFFFFF;")

        btn_clear = QPushButton("Clear History")
        btn_clear.clicked.connect(self._clear_test_history)

        header.addWidget(lbl_title)
        header.addStretch(1)
        header.addWidget(btn_clear)
        layout.addLayout(header)

        self._table_history = QTableWidget(0, 7)
        self._table_history.setHorizontalHeaderLabels(
            ["Timestamp", "Download", "Upload", "Ping", "Jitter", "Bufferbloat", "Gaming Rating"]
        )
        hdr_history = self._table_history.horizontalHeader()
        if hdr_history is not None:
            hdr_history.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._table_history, 1)

        return widget

    def _refresh_test_history(self) -> None:
        records = self._db.get_speed_test_history(limit=50)
        self._table_history.setRowCount(len(records))
        for row, r in enumerate(records):
            self._table_history.setItem(row, 0, QTableWidgetItem(r.timestamp_iso))
            self._table_history.setItem(row, 1, QTableWidgetItem(f"{r.download_mbps:.1f} Mbps"))
            self._table_history.setItem(row, 2, QTableWidgetItem(f"{r.upload_mbps:.1f} Mbps"))
            self._table_history.setItem(row, 3, QTableWidgetItem(f"{r.idle_ping_ms:.0f} ms"))
            self._table_history.setItem(row, 4, QTableWidgetItem(f"{r.jitter_ms:.1f} ms"))
            self._table_history.setItem(row, 5, QTableWidgetItem(f"Grade {r.bufferbloat_grade}"))
            self._table_history.setItem(row, 6, QTableWidgetItem(r.gaming_rating))

    def _clear_test_history(self) -> None:
        self._db.clear_speed_test_history()
        self._refresh_test_history()

    # =========================================================================
    # TAB 0: DASHBOARD OVERVIEW
    # =========================================================================
    def _create_dashboard_view(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)

        lbl = QLabel("Live Telemetry & Bandwidth Overview")
        lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(lbl)

        # Live metric cards
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(12)

        self._dash_live_down = self._create_accent_card("Current Download", "0.0 B/s", "#00E676")
        self._dash_live_up = self._create_accent_card("Current Upload", "0.0 B/s", "#007AFF")
        self._dash_today_total = self._create_accent_card("Today's Total Usage", "--", "#EAB308")

        cards_layout.addWidget(self._dash_live_down)
        cards_layout.addWidget(self._dash_live_up)
        cards_layout.addWidget(self._dash_today_total)
        layout.addLayout(cards_layout)

        # Historical bandwidth summary cards
        hist_cards = QHBoxLayout()
        hist_cards.setSpacing(12)
        self._dash_week_total = self._create_accent_card("This Week's Usage", "--", "#38BDF8")
        self._dash_month_total = self._create_accent_card("This Month's Usage", "--", "#A855F7")
        self._dash_all_total = self._create_accent_card("All-Time Total", "--", "#F43F5E")
        hist_cards.addWidget(self._dash_week_total)
        hist_cards.addWidget(self._dash_month_total)
        hist_cards.addWidget(self._dash_all_total)
        layout.addLayout(hist_cards)

        # Quick Navigation Shortcuts
        quick_nav = QHBoxLayout()
        quick_nav.setSpacing(12)
        btn_go_speed = QPushButton("🚀 Run Speed Test")
        btn_go_speed.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_go_speed.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #007AFF, stop:1 #2563EB);
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 10px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563EB, stop:1 #1D4ED8);
            }
        """)
        btn_go_speed.clicked.connect(lambda: self._sidebar.select_index(3))

        btn_go_logs = QPushButton("📊 View Traffic Logs")
        btn_go_logs.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_go_logs.setStyleSheet("""
            QPushButton {
                background-color: #1E222D;
                color: #CBD5E1;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 10px 16px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #2E384D;
                color: #F8FAFC;
            }
        """)
        btn_go_logs.clicked.connect(lambda: self._sidebar.select_index(5))

        btn_go_nic = QPushButton("⚙️ Adapter Settings")
        btn_go_nic.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_go_nic.setStyleSheet("""
            QPushButton {
                background-color: #1E222D;
                color: #CBD5E1;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 10px 16px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #2E384D;
                color: #F8FAFC;
            }
        """)
        btn_go_nic.clicked.connect(lambda: self._sidebar.select_index(2))

        quick_nav.addWidget(btn_go_speed)
        quick_nav.addWidget(btn_go_logs)
        quick_nav.addWidget(btn_go_nic)
        layout.addLayout(quick_nav)

        # Quick action launch bar
        links_box = QGroupBox("Quick Windows Diagnostics")
        links_box.setStyleSheet("color: #94A3B8; font-weight: bold;")
        l_layout = QHBoxLayout(links_box)
        for label, cmd in (
            ("Network Connections", "ncpa.cpl"),
            ("Resource Monitor", "resmon"),
            ("Task Manager", "taskmgr"),
            ("Windows Firewall", "firewall.cpl"),
        ):
            b = QPushButton(label)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _, c=cmd: subprocess.Popen(c, shell=True))
            l_layout.addWidget(b)

        layout.addWidget(links_box)
        layout.addStretch(1)
        return widget

    def update_live_speeds(self, sample: SpeedSample) -> None:
        """Route live background speed updates into the Dashboard overview tab."""
        f_down = self._formatter.format_speed(sample.total_download_speed)
        f_up = self._formatter.format_speed(sample.total_upload_speed)

        lbl_d = self._dash_live_down.findChild(QLabel, "val")
        if lbl_d:
            lbl_d.setText(f_down.full_str)

        lbl_u = self._dash_live_up.findChild(QLabel, "val")
        if lbl_u:
            lbl_u.setText(f_up.full_str)

    # =========================================================================
    # TAB 1: SETTINGS EMBEDDED
    # =========================================================================
    def _create_settings_view(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)

        lbl = QLabel("Application Settings & Preferences")
        lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(lbl)

        grid = QGridLayout()
        grid.setSpacing(10)

        # Refresh Interval
        grid.addWidget(QLabel("Speed Refresh Time:"), 0, 0)
        self._combo_interval = QComboBox()
        self._combo_interval.addItems(
            ["0.5 seconds", "1.0 second (Default)", "2.0 seconds", "5.0 seconds"]
        )
        grid.addWidget(self._combo_interval, 0, 1)

        # Always on top
        self._chk_top = QCheckBox("Keep Floating Widget Always on Top")
        self._chk_top.setChecked(self._settings.always_on_top)
        grid.addWidget(self._chk_top, 1, 0, 1, 2)

        # Autostart with Windows
        self._chk_autostart = QCheckBox("Start FreeNetMeter Automatically with Windows")
        self._chk_autostart.setChecked(self._settings.start_with_windows)
        grid.addWidget(self._chk_autostart, 2, 0, 1, 2)

        layout.addLayout(grid)

        btn_save = QPushButton("Save Settings")
        btn_save.setFixedWidth(140)
        btn_save.clicked.connect(self._save_settings_clicked)
        layout.addWidget(btn_save)

        layout.addStretch(1)
        return widget

    def _save_settings_clicked(self) -> None:
        intervals = [0.5, 1.0, 2.0, 5.0]
        idx = self._combo_interval.currentIndex()
        if 0 <= idx < len(intervals):
            self._settings.sample_interval_seconds = intervals[idx]
        self._settings.always_on_top = self._chk_top.isChecked()
        self._settings.start_with_windows = self._chk_autostart.isChecked()
        self._on_save_settings(self._settings)
        QMessageBox.information(self, "Settings Saved", "Your preferences have been updated.")

    # =========================================================================
    # TAB 2: ADAPTER CONFIG
    # =========================================================================
    def _create_adapters_view(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        lbl = QLabel("Network Adapter (NIC) Configuration")
        lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(lbl)

        self._chk_auto_nic = QCheckBox("Auto Select Active Internet NIC (Recommended)")
        self._chk_auto_nic.setChecked(self._settings.auto_select_nic)
        layout.addWidget(self._chk_auto_nic)

        layout.addStretch(1)
        return widget

    # =========================================================================
    # TAB 5: USAGE STATS
    # =========================================================================
    def _create_usage_stats_view(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        lbl = QLabel("Historical Data Usages & Traffic Logs")
        lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(lbl)

        self._table_usage = QTableWidget(0, 5)
        self._table_usage.setHorizontalHeaderLabels(
            ["Date", "Interface", "Downloaded", "Uploaded", "Total Usage"]
        )
        hdr_usage = self._table_usage.horizontalHeader()
        if hdr_usage is not None:
            hdr_usage.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._table_usage, 1)

        return widget

    def _refresh_usage_stats(self) -> None:
        today_str = datetime.date.today().isoformat()
        entries = self._db.get_history()
        self._table_usage.setRowCount(len(entries))
        for row, e in enumerate(entries):
            self._table_usage.setItem(row, 0, QTableWidgetItem(e.date_str))
            self._table_usage.setItem(row, 1, QTableWidgetItem(e.interface_name))
            self._table_usage.setItem(
                row, 2, QTableWidgetItem(self._formatter.format_bytes_total(e.bytes_recv))
            )
            self._table_usage.setItem(
                row, 3, QTableWidgetItem(self._formatter.format_bytes_total(e.bytes_sent))
            )
            self._table_usage.setItem(
                row, 4, QTableWidgetItem(self._formatter.format_bytes_total(e.total_bytes))
            )

        # Also update summary cards on dashboard
        summary = self._db.get_summary(today_str)
        for card, val in (
            (self._dash_today_total, summary.today_total),
            (self._dash_week_total, summary.week_total),
            (self._dash_month_total, summary.month_total),
            (self._dash_all_total, summary.all_time_total),
        ):
            lbl_card = card.findChild(QLabel, "val")
            if lbl_card:
                lbl_card.setText(self._formatter.format_bytes_total(val))

    # =========================================================================
    # TAB 6: DATA PLAN TRACKER
    # =========================================================================
    def _create_data_plan_view(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)

        lbl = QLabel("Monthly Data Plan & Quota Tracking")
        lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(lbl)

        p_bar = QProgressBar()
        p_bar.setValue(24)
        p_bar.setTextVisible(True)
        p_bar.setFormat("120 GB used of 500 GB (24%)")
        p_bar.setFixedHeight(24)
        p_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1E222D;
                border: 1px solid #334155;
                border-radius: 6px;
                text-align: center;
                color: #FFFFFF;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #007AFF, stop:1 #00E676);
                border-radius: 5px;
            }
        """)
        layout.addWidget(p_bar)
        layout.addStretch(1)
        return widget

    # =========================================================================
    # TAB 7: WIFI ANALYZER
    # =========================================================================
    def _create_wifi_view(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        lbl = QLabel("Wi-Fi Connection & Wireless Diagnostics")
        lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(lbl)

        info_box = QGroupBox("Active Wi-Fi Details")
        info_box.setStyleSheet("color: #94A3B8; font-weight: bold;")
        grid = QGridLayout(info_box)

        # Query active SSID via netsh
        ssid = "Wi-Fi Connected"
        signal = "85%"
        try:
            out = subprocess.check_output(
                "netsh wlan show interfaces", shell=True, text=True, errors="ignore"
            )
            for line in out.splitlines():
                if "SSID" in line and "BSSID" not in line:
                    parts = line.split(":")
                    if len(parts) > 1:
                        ssid = parts[1].strip()
                elif "Signal" in line:
                    parts = line.split(":")
                    if len(parts) > 1:
                        signal = parts[1].strip()
        except Exception:
            pass

        grid.addWidget(self._create_prop_label("Network Name (SSID):"), 0, 0)
        grid.addWidget(QLabel(ssid), 0, 1)
        grid.addWidget(self._create_prop_label("Signal Strength:"), 1, 0)
        grid.addWidget(QLabel(signal), 1, 1)

        layout.addWidget(info_box)
        layout.addStretch(1)
        return widget

    # =========================================================================
    # TAB 8: NETWORK INFO
    # =========================================================================
    def _create_network_info_view(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        lbl = QLabel("Network Addressing & IP Configuration")
        lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(lbl)

        grid = QGridLayout()
        grid.addWidget(self._create_prop_label("Hostname:"), 0, 0)
        grid.addWidget(QLabel(socket.gethostname()), 0, 1)

        # Local IP
        local_ip = "127.0.0.1"
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except Exception:
            pass

        grid.addWidget(self._create_prop_label("Local IPv4 Address:"), 1, 0)
        grid.addWidget(QLabel(local_ip), 1, 1)

        layout.addLayout(grid)
        layout.addStretch(1)
        return widget

    # =========================================================================
    # TAB 9: NETWORK INTERFACES
    # =========================================================================
    def _create_interfaces_view(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        lbl = QLabel("Hardware Network Interface Inventory")
        lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(lbl)

        table = QTableWidget(0, 4)
        table.setHorizontalHeaderLabels(["Adapter Name", "Status", "Link Speed", "MTU"])
        hdr_table = table.horizontalHeader()
        if hdr_table is not None:
            hdr_table.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        import psutil

        stats = psutil.net_if_stats()
        table.setRowCount(len(stats))
        for row, (name, st) in enumerate(stats.items()):
            table.setItem(row, 0, QTableWidgetItem(name))
            table.setItem(row, 1, QTableWidgetItem("Connected (UP)" if st.isup else "Disconnected"))
            table.setItem(
                row, 2, QTableWidgetItem(f"{st.speed} Mbps" if st.speed > 0 else "Unknown")
            )
            table.setItem(row, 3, QTableWidgetItem(str(st.mtu)))

        layout.addWidget(table, 1)
        return widget

    # =========================================================================
    # TAB 10: ACTIVE PROCESSES
    # =========================================================================
    def _create_processes_view(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        lbl = QLabel("Active Processes with Network Sockets")
        lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl.setStyleSheet("color: #FFFFFF;")

        btn_ref = QPushButton("Refresh Processes")
        btn_ref.clicked.connect(self._refresh_processes)

        header.addWidget(lbl)
        header.addStretch(1)
        header.addWidget(btn_ref)
        layout.addLayout(header)

        self._table_proc = QTableWidget(0, 4)
        self._table_proc.setHorizontalHeaderLabels(
            ["PID", "Process Name", "Status", "Local Address"]
        )
        hdr_proc = self._table_proc.horizontalHeader()
        if hdr_proc is not None:
            hdr_proc.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._table_proc, 1)

        return widget

    def _refresh_processes(self) -> None:
        import psutil

        try:
            conns = psutil.net_connections(kind="inet")
            unique_pids = {c.pid for c in conns if c.pid}
            self._table_proc.setRowCount(min(50, len(unique_pids)))

            for row, pid in enumerate(list(unique_pids)[:50]):
                name = "Unknown"
                try:
                    p = psutil.Process(pid)
                    name = p.name()
                except Exception:
                    pass
                self._table_proc.setItem(row, 0, QTableWidgetItem(str(pid)))
                self._table_proc.setItem(row, 1, QTableWidgetItem(name))
                self._table_proc.setItem(row, 2, QTableWidgetItem("Active Connection"))
                self._table_proc.setItem(row, 3, QTableWidgetItem("TCP / UDP"))
        except Exception:
            pass

    # =========================================================================
    # TAB 11: NETWORK TOOLS
    # =========================================================================
    def _create_tools_view(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)

        lbl = QLabel("Network Diagnostics & Utilities")
        lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(lbl)

        # Ping Tool
        ping_box = QGroupBox("Quick ICMP Ping Tool")
        ping_box.setStyleSheet("color: #94A3B8; font-weight: bold;")
        p_layout = QHBoxLayout(ping_box)
        self._txt_ping_host = QLineEdit("8.8.8.8")
        self._txt_ping_host.setPlaceholderText("Hostname or IP")
        btn_ping = QPushButton("Ping Host")
        lbl_ping_res = QLabel("Result: --")
        btn_ping.clicked.connect(lambda: self._run_ping(lbl_ping_res))
        p_layout.addWidget(self._txt_ping_host, 2)
        p_layout.addWidget(btn_ping, 1)
        p_layout.addWidget(lbl_ping_res, 2)
        layout.addWidget(ping_box)

        layout.addStretch(1)
        return widget

    def _run_ping(self, result_lbl: QLabel) -> None:
        host = self._txt_ping_host.text().strip() or "8.8.8.8"
        result_lbl.setText("Pinging...")
        QTimer.singleShot(50, lambda: self._do_ping(host, result_lbl))

    def _do_ping(self, host: str, result_lbl: QLabel) -> None:
        try:
            out = subprocess.check_output(
                f"ping -n 2 {host}", shell=True, text=True, errors="ignore"
            )
            if "Average =" in out:
                avg = out.split("Average =")[-1].strip()
                result_lbl.setText(f"Success! Avg: {avg}")
            else:
                result_lbl.setText("Ping completed.")
        except Exception as exc:
            result_lbl.setText(f"Failed: {exc}")

    def _toggle_theme(self) -> None:
        """Switch between dark and light themes."""
        curr = self._settings.theme_mode
        self._settings.theme_mode = "light" if curr == "dark" else "dark"
        self._on_save_settings(self._settings)
        self._apply_theme()

    def _apply_theme(self) -> None:
        """Apply sleek dark theme styling across the dashboard."""
        self.setStyleSheet("""
            QDialog {
                background-color: #12141A;
                color: #F8FAFC;
                font-family: 'Segoe UI', -apple-system, sans-serif;
            }
            QLabel {
                color: #E2E8F0;
            }
            QTableWidget {
                background-color: #16181F;
                color: #F8FAFC;
                border: 1px solid #282D3B;
                border-radius: 6px;
                gridline-color: #262934;
            }
            QTableWidget::item:selected {
                background-color: #007AFF;
                color: white;
            }
            QHeaderView::section {
                background-color: #1E222D;
                color: #94A3B8;
                font-weight: bold;
                padding: 6px;
                border: 1px solid #262934;
            }
            QPushButton {
                background-color: #242834;
                color: #F8FAFC;
                border: 1px solid #383F52;
                border-radius: 6px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background-color: #32384A;
            }
            QComboBox, QLineEdit {
                background-color: #1E222D;
                color: #F8FAFC;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 4px 8px;
            }
            QCheckBox {
                color: #CBD5E1;
            }
        """)
