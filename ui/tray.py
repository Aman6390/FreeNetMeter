"""System tray integration for FreeNetMeter.

Provides real-time tooltip telemetry, quick access context menu, widget visibility
toggle on click, and clean destruction to prevent Windows ghost tray icons.
"""

from __future__ import annotations

import logging
from typing import Callable

from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from core.constants import APP_NAME
from core.formatter import SpeedFormatter
from core.speed_calculator import SpeedSample
from ui.assets import create_app_icon

logger = logging.getLogger("FreeNetMeter.Tray")


class SystemTrayManager:
    """Manages system tray icon, context menu, and tooltip updates."""

    def __init__(
        self,
        widget: QWidget,
        formatter: SpeedFormatter,
        on_open_settings: Callable[[], None],
        on_open_usage: Callable[[], None],
        on_exit_app: Callable[[], None],
        on_open_connection_info: Callable[[], None] | None = None,
        on_open_stopwatch: Callable[[], None] | None = None,
        on_open_about: Callable[[], None] | None = None,
    ) -> None:
        """Initialize system tray manager.

        Args:
            widget: DesktopSpeedWidget instance to show/hide.
            formatter: SpeedFormatter instance for tooltip text.
            on_open_settings: Callback to open settings dialog.
            on_open_usage: Callback to open data usage dialog.
            on_exit_app: Callback to cleanly terminate application.
            on_open_connection_info: Optional callback to open connection info.
            on_open_stopwatch: Optional callback to open stopwatch dialog.
            on_open_about: Optional callback to open about dialog.
        """
        self._widget = widget
        self._formatter = formatter
        self._on_open_settings = on_open_settings
        self._on_open_usage = on_open_usage
        self._on_exit_app = on_exit_app
        self._on_open_connection_info = on_open_connection_info
        self._on_open_stopwatch = on_open_stopwatch
        self._on_open_about = on_open_about

        self._tray_icon: QSystemTrayIcon | None = None
        self._menu: QMenu | None = None
        self._act_toggle_widget: QAction | None = None

        self._init_tray()

    def _init_tray(self) -> None:
        """Set up system tray icon and context menu."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.warning("System tray is not available on this platform.")
            return

        icon = create_app_icon()
        tray = QSystemTrayIcon(icon)
        tray.setToolTip(f"{APP_NAME}\nInitializing...")

        # Construct Context Menu
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #24252a;
                color: #f0f0f0;
                border: 1px solid #3c3f4a;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 24px 6px 12px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #007aff;
                color: white;
            }
            QMenu::separator {
                height: 1px;
                background-color: #3c3f4a;
                margin: 4px 8px;
            }
            """)

        self._act_toggle_widget = menu.addAction("Hide Desktop Widget")
        if self._act_toggle_widget:
            self._act_toggle_widget.triggered.connect(self._toggle_widget_visibility)

        menu.addSeparator()

        act_settings = menu.addAction("Settings...")
        if act_settings:
            act_settings.triggered.connect(self._on_open_settings)

        act_usage = menu.addAction("Data Usage...")
        if act_usage:
            act_usage.triggered.connect(self._on_open_usage)

        if self._on_open_connection_info:
            act_conn = menu.addAction("Connection Info...")
            if act_conn:
                act_conn.triggered.connect(self._on_open_connection_info)

        if self._on_open_stopwatch:
            act_sw = menu.addAction("Session Stopwatch...")
            if act_sw:
                act_sw.triggered.connect(self._on_open_stopwatch)

        if self._on_open_about:
            act_about = menu.addAction("About FreeNetMeter...")
            if act_about:
                act_about.triggered.connect(self._on_open_about)

        menu.addSeparator()

        act_exit = menu.addAction("Exit FreeNetMeter")
        if act_exit:
            act_exit.triggered.connect(self._on_exit_app)

        tray.setContextMenu(menu)
        tray.activated.connect(self._on_tray_activated)

        tray.show()
        self._tray_icon = tray
        self._menu = menu

    def _toggle_widget_visibility(self) -> None:
        """Toggle desktop widget between visible and hidden states."""
        if self._widget.isVisible():
            self._widget.hide()
            if self._act_toggle_widget:
                self._act_toggle_widget.setText("Show Desktop Widget")
        else:
            self._widget.show()
            self._widget.raise_()
            self._widget.activateWindow()
            if self._act_toggle_widget:
                self._act_toggle_widget.setText("Hide Desktop Widget")

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Handle clicks on the tray icon."""
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._toggle_widget_visibility()

    def update_tooltip(self, sample: SpeedSample) -> None:
        """Update system tray tooltip with real-time download and upload speeds.

        Args:
            sample: Latest SpeedSample.
        """
        if not self._tray_icon:
            return

        formatted_down = self._formatter.format_speed(sample.total_download_speed)
        formatted_up = self._formatter.format_speed(sample.total_upload_speed)

        tooltip = (
            f"{APP_NAME}\n" f"Down: {formatted_down.full_str}\n" f"Up:   {formatted_up.full_str}"
        )
        self._tray_icon.setToolTip(tooltip)

        # Sync toggle menu action text
        if self._act_toggle_widget:
            is_visible = self._widget.isVisible()
            self._act_toggle_widget.setText(
                "Hide Desktop Widget" if is_visible else "Show Desktop Widget"
            )

    def set_formatter(self, formatter: SpeedFormatter) -> None:
        """Update formatter instance when settings change."""
        self._formatter = formatter

    def shutdown(self) -> None:
        """Gracefully hide and delete the system tray icon to prevent Windows ghost icons."""
        if self._tray_icon:
            self._tray_icon.hide()
            self._tray_icon.deleteLater()
            self._tray_icon = None
            logger.info("System tray icon removed cleanly.")
