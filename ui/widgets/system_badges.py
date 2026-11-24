"""System telemetry badges bar rendered across the window header.

Displays live host badges:
- Hostname
- CPU Model
- System RAM
- Operating System
- System Uptime
- Free/Pro Status Badge
"""

from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from core.system_telemetry import SystemTelemetryProvider


class SystemBadgesBar(QWidget):
    """Header bar containing live hardware and OS telemetry badges."""

    def __init__(
        self,
        on_toggle_theme: Optional[Callable[[], None]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._provider = SystemTelemetryProvider()
        self._on_toggle_theme = on_toggle_theme

        self._init_ui()
        self.refresh_telemetry()

        # Update uptime every 60 seconds
        self._timer = QTimer(self)
        self._timer.setInterval(60000)
        self._timer.timeout.connect(self.refresh_telemetry)
        self._timer.start()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(10)

        # Telemetry Badges Container
        self._lbl_host = self._create_badge_label("💻", "Host: --")
        self._lbl_cpu = self._create_badge_label("⚙️", "CPU: --")
        self._lbl_ram = self._create_badge_label("🧠", "RAM: --")
        self._lbl_os = self._create_badge_label("🪟", "OS: --")
        self._lbl_uptime = self._create_badge_label("⏱️", "Up --")

        layout.addWidget(self._lbl_host)
        layout.addWidget(self._lbl_cpu)
        layout.addWidget(self._lbl_ram)
        layout.addWidget(self._lbl_os)
        layout.addWidget(self._lbl_uptime)

        layout.addStretch(1)

        # "✓ Free & Unlocked" badge celebrating 0 ads / no paywall
        self._lbl_pro = QLabel("👑 100% Free Forever")
        self._lbl_pro.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #007AFF, stop:1 #5856D6);
                color: #FFFFFF;
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: bold;
            }
        """)
        layout.addWidget(self._lbl_pro)

        if self._on_toggle_theme:
            self._btn_theme = QPushButton("☀️")
            self._btn_theme.setToolTip("Toggle Dark/Light Mode")
            self._btn_theme.setCursor(Qt.CursorShape.PointingHandCursor)
            self._btn_theme.setStyleSheet("""
                QPushButton {
                    background-color: #262934;
                    color: #E2E8F0;
                    border: 1px solid #3B4254;
                    border-radius: 6px;
                    padding: 4px 8px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #373D4E;
                }
            """)
            self._btn_theme.clicked.connect(self._on_toggle_theme)
            layout.addWidget(self._btn_theme)

    def _create_badge_label(self, icon: str, default_text: str) -> QLabel:
        lbl = QLabel(f"{icon} {default_text}")
        lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Medium))
        lbl.setStyleSheet("""
            QLabel {
                background-color: #1A1D24;
                color: #CBD5E1;
                border: 1px solid #2E3342;
                border-radius: 6px;
                padding: 4px 10px;
            }
        """)
        return lbl

    def refresh_telemetry(self) -> None:
        """Fetch latest telemetry and update badge strings."""
        info = self._provider.get_snapshot()

        # Truncate long CPU strings gracefully
        cpu_display = info.cpu_name
        if len(cpu_display) > 24:
            cpu_display = cpu_display[:22] + "..."

        self._lbl_host.setText(f"💻 {info.hostname}")
        self._lbl_cpu.setText(f"⚙️ {cpu_display}")
        self._lbl_ram.setText(f"🧠 {info.ram_display}")
        self._lbl_os.setText(f"🪟 {info.os_display}")
        self._lbl_uptime.setText(f"⏱️ {info.uptime_display}")
