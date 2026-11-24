"""Bandwidth Stopwatch and Session Telemetry Tracker.

Allows users to benchmark and measure network consumption over an arbitrary
session window (e.g. during a gaming match, video conference, or download):
- Elapsed session duration timer (HH:MM:SS)
- Total download and upload bandwidth accumulated in session
- Average throughput (download & upload)
- Peak throughput (download & upload)
- Start, Pause, and Reset controls

Follows Apple Design Principles with bold typographic rhythm, clean metrics
cards, and smooth state transitions.
"""

from __future__ import annotations

import time
from platform.theme_listener import WindowsThemeDetector
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.formatter import SpeedFormatter
from storage.settings_store import AppSettings

if TYPE_CHECKING:
    from core.speed_calculator import SpeedSample


class StopwatchDialog(QDialog):
    """Interactive session bandwidth stopwatch dialog."""

    def __init__(
        self,
        settings: AppSettings,
        formatter: SpeedFormatter,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize session stopwatch dialog.

        Args:
            settings: Active AppSettings instance.
            formatter: SpeedFormatter for formatting units.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._settings = settings
        self._formatter = formatter

        self.setWindowTitle("FreeNetMeter - Session Stopwatch")
        self.setFixedSize(440, 360)

        # Stopwatch state
        self._is_running: bool = False
        self._start_time: float = 0.0
        self._elapsed_offset: float = 0.0

        self._session_bytes_down: int = 0
        self._session_bytes_up: int = 0
        self._peak_speed_down: float = 0.0
        self._peak_speed_up: float = 0.0

        # UI Refresh Timer for the clock
        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(200)
        self._clock_timer.timeout.connect(self._update_clock_display)

        self._init_ui()
        self._apply_theme()

    def _init_ui(self) -> None:
        """Construct dialog widgets and cards."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(14)

        # Big Timer Display Card
        timer_card = QGroupBox()
        timer_layout = QVBoxLayout(timer_card)
        timer_layout.setContentsMargins(10, 10, 10, 10)
        timer_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._lbl_timer = QLabel("00:00:00")
        self._lbl_timer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_timer.setStyleSheet("font-size: 32px; font-weight: bold; letter-spacing: 2px;")
        timer_layout.addWidget(self._lbl_timer)
        main_layout.addWidget(timer_card)

        # Metrics 2x2 Grid
        metrics_grp = QGroupBox("Session Bandwidth Metrics")
        grid = QGridLayout(metrics_grp)
        grid.setSpacing(12)

        # 1. Total Downloaded
        self._lbl_val_total_down = QLabel("0.0 B")
        self._lbl_val_total_down.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #00e676;"
        )
        grid.addWidget(QLabel("Downloaded:"), 0, 0)
        grid.addWidget(self._lbl_val_total_down, 0, 1)

        # 2. Total Uploaded
        self._lbl_val_total_up = QLabel("0.0 B")
        self._lbl_val_total_up.setStyleSheet("font-size: 14px; font-weight: bold; color: #29b6f6;")
        grid.addWidget(QLabel("Uploaded:"), 0, 2)
        grid.addWidget(self._lbl_val_total_up, 0, 3)

        # 3. Avg / Peak Download
        self._lbl_val_down_rates = QLabel("Avg: 0.0 B/s | Peak: 0.0 B/s")
        grid.addWidget(QLabel("Download Rates:"), 1, 0)
        grid.addWidget(self._lbl_val_down_rates, 1, 1, 1, 3)

        # 4. Avg / Peak Upload
        self._lbl_val_up_rates = QLabel("Avg: 0.0 B/s | Peak: 0.0 B/s")
        grid.addWidget(QLabel("Upload Rates:"), 2, 0)
        grid.addWidget(self._lbl_val_up_rates, 2, 1, 1, 3)

        main_layout.addWidget(metrics_grp)

        # Control Buttons
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(10)

        self._btn_toggle = QPushButton("Start Stopwatch")
        self._btn_toggle.setStyleSheet("font-weight: bold;")
        self._btn_toggle.clicked.connect(self._toggle_stopwatch)
        ctrl_layout.addWidget(self._btn_toggle)

        self._btn_reset = QPushButton("Reset")
        self._btn_reset.clicked.connect(self._reset_stopwatch)
        ctrl_layout.addWidget(self._btn_reset)

        ctrl_layout.addStretch(1)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(self.accept)
        ctrl_layout.addWidget(btn_box)

        main_layout.addLayout(ctrl_layout)

    def _apply_theme(self) -> None:
        """Apply sleek dark/light theme."""
        effective_theme = WindowsThemeDetector.resolve_theme(self._settings.theme_mode)
        is_dark = effective_theme == "dark"

        if is_dark:
            self.setStyleSheet("""
                QDialog {
                    background-color: #1e1f24;
                    color: #f0f0f0;
                    font-family: 'Segoe UI', -apple-system, sans-serif;
                }
                QGroupBox {
                    background-color: #262830;
                    border: 1px solid #383c48;
                    border-radius: 8px;
                    padding: 10px;
                }
                QLabel { color: #dcdcdc; }
                QPushButton {
                    background-color: #2d3039;
                    color: #ffffff;
                    border: 1px solid #454958;
                    border-radius: 6px;
                    padding: 6px 14px;
                }
                QPushButton:hover {
                    background-color: #007aff;
                    border-color: #007aff;
                }
            """)
        else:
            self.setStyleSheet("""
                QDialog {
                    background-color: #f6f8fb;
                    color: #1a1a1a;
                    font-family: 'Segoe UI', -apple-system, sans-serif;
                }
                QGroupBox {
                    background-color: #ffffff;
                    border: 1px solid #d8dce6;
                    border-radius: 8px;
                    padding: 10px;
                }
                QLabel { color: #222222; }
                QPushButton {
                    background-color: #e8ecf4;
                    color: #1a1a1a;
                    border: 1px solid #ccd1dc;
                    border-radius: 6px;
                    padding: 6px 14px;
                }
                QPushButton:hover {
                    background-color: #007aff;
                    color: white;
                    border-color: #007aff;
                }
            """)

    def _toggle_stopwatch(self) -> None:
        """Start or pause the stopwatch."""
        if not self._is_running:
            self._is_running = True
            self._start_time = time.monotonic()
            self._clock_timer.start()
            self._btn_toggle.setText("Pause Stopwatch")
        else:
            self._is_running = False
            self._elapsed_offset += time.monotonic() - self._start_time
            self._clock_timer.stop()
            self._btn_toggle.setText("Resume Stopwatch")

    def _reset_stopwatch(self) -> None:
        """Reset all counters and stopwatch duration to zero."""
        self._is_running = False
        self._clock_timer.stop()
        self._start_time = 0.0
        self._elapsed_offset = 0.0
        self._session_bytes_down = 0
        self._session_bytes_up = 0
        self._peak_speed_down = 0.0
        self._peak_speed_up = 0.0

        self._lbl_timer.setText("00:00:00")
        self._lbl_val_total_down.setText("0.0 B")
        self._lbl_val_total_up.setText("0.0 B")
        self._lbl_val_down_rates.setText("Avg: 0.0 B/s | Peak: 0.0 B/s")
        self._lbl_val_up_rates.setText("Avg: 0.0 B/s | Peak: 0.0 B/s")
        self._btn_toggle.setText("Start Stopwatch")

    def _get_elapsed_seconds(self) -> float:
        """Return total elapsed active seconds."""
        if self._is_running:
            return self._elapsed_offset + (time.monotonic() - self._start_time)
        return self._elapsed_offset

    def _update_clock_display(self) -> None:
        """Format and update HH:MM:SS timer."""
        secs = int(self._get_elapsed_seconds())
        hrs = secs // 3600
        mins = (secs % 3600) // 60
        rem_secs = secs % 60
        self._lbl_timer.setText(f"{hrs:02d}:{mins:02d}:{rem_secs:02d}")

    def on_speed_sample(self, sample: SpeedSample) -> None:
        """Accumulate live speed metrics when stopwatch is running.

        Args:
            sample: Calculated SpeedSample from worker thread.
        """
        if not self._is_running:
            return

        self._session_bytes_down += sample.total_delta_recv
        self._session_bytes_up += sample.total_delta_sent

        if sample.total_download_speed > self._peak_speed_down:
            self._peak_speed_down = sample.total_download_speed

        if sample.total_upload_speed > self._peak_speed_up:
            self._peak_speed_up = sample.total_upload_speed

        # Update labels
        self._lbl_val_total_down.setText(
            self._formatter.format_bytes_total(self._session_bytes_down)
        )
        self._lbl_val_total_up.setText(self._formatter.format_bytes_total(self._session_bytes_up))

        elapsed = max(1.0, self._get_elapsed_seconds())
        avg_down = self._session_bytes_down / elapsed
        avg_up = self._session_bytes_up / elapsed

        fmt_avg_d = self._formatter.format_speed(avg_down).full_str
        fmt_peak_d = self._formatter.format_speed(self._peak_speed_down).full_str
        self._lbl_val_down_rates.setText(f"Avg: {fmt_avg_d} | Peak: {fmt_peak_d}")

        fmt_avg_u = self._formatter.format_speed(avg_up).full_str
        fmt_peak_u = self._formatter.format_speed(self._peak_speed_up).full_str
        self._lbl_val_up_rates.setText(f"Avg: {fmt_avg_u} | Peak: {fmt_peak_u}")
