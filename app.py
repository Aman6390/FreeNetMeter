"""Application controller and subsystem coordinator for FreeNetMeter.

Coordinates:
- Rotating file logging in %APPDATA%/FreeNetMeter/logs.
- Loading and persisting settings.
- Initializing sampling worker thread and database flusher.
- Managing desktop speed widget, system tray, and dialog windows.
- Handling graceful shutdown on exit, Windows logoff, and system shutdown.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from platform.autostart import WindowsAutostartManager
from platform.single_instance import SingleInstanceGuard

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QApplication

from core.constants import (
    APP_NAME,
    LOG_BACKUP_COUNT,
    LOG_FILE_PATH,
    LOG_MAX_BYTES,
    LOGS_DIR,
)
from core.counter_source import PsutilCounterSource
from core.formatter import SpeedFormatter
from core.interface_filter import InterfaceFilter
from core.speed_calculator import SpeedCalculator, SpeedSample
from core.usage_accumulator import UsageAccumulator
from storage.settings_store import AppSettings, SettingsStore
from storage.usage_database import UsageDatabase
from ui.about_dialog import AboutDialog
from ui.connection_info_dialog import ConnectionInfoDialog
from ui.dashboard_window import MasterDashboardWindow
from ui.help_dialog import HelpDialog
from ui.settings_window import SettingsDialog
from ui.stopwatch_dialog import StopwatchDialog
from ui.tray import SystemTrayManager
from ui.widget import DesktopSpeedWidget
from ui.worker import SamplingWorker

logger = logging.getLogger("FreeNetMeter.App")


class FreeNetMeterApp(QObject):
    """Main application orchestrator coordinating logic, storage, and UI."""

    def __init__(
        self,
        qapp: QApplication,
        single_instance_guard: SingleInstanceGuard | None = None,
    ) -> None:
        """Initialize FreeNetMeter application.

        Args:
            qapp: The running QApplication instance.
            single_instance_guard: SingleInstanceGuard for IPC activation.
        """
        super().__init__()
        self._qapp = qapp
        self._guard = single_instance_guard

        # Configure rotating file logging
        self._setup_logging()
        logger.info("Initializing %s subsystems...", APP_NAME)

        # 1. Storage
        self._settings_store = SettingsStore()
        self._settings = self._settings_store.load()
        self._database = UsageDatabase()

        # Run retention cleanup if configured
        if self._settings.retention_days > 0:
            deleted = self._database.cleanup_old_records(self._settings.retention_days)
            if deleted > 0:
                logger.info("Cleaned up %d expired data usage records.", deleted)

        # 2. Pure Core Logic
        self._counter_source = PsutilCounterSource()
        self._speed_calculator = SpeedCalculator(
            rolling_window_size=self._settings.rolling_window_size
        )
        self._usage_accumulator = UsageAccumulator()
        self._interface_filter = InterfaceFilter(excluded_keywords=self._settings.excluded_keywords)
        self._formatter = self._create_formatter()

        # 3. Platform Integrations
        self._autostart_manager = WindowsAutostartManager()

        # 4. Dialog References
        self._stopwatch_dialog: StopwatchDialog | None = None
        self._dashboard_window: MasterDashboardWindow | None = None

        # 5. User Interface Components
        self._widget = DesktopSpeedWidget(
            settings=self._settings,
            formatter=self._formatter,
            on_open_settings=self.open_settings_dialog,
            on_open_usage=lambda: self.open_usage_dialog(initial_tab=0),
            on_exit_app=self.shutdown,
            on_save_settings=self.save_settings,
            on_refresh_connection=self.refresh_connection,
            on_pause_toggle=self.toggle_pause,
            on_open_connection_info=self.open_connection_info_dialog,
            on_open_stopwatch=self.open_stopwatch_dialog,
            on_open_help=self.open_help_dialog,
            on_open_about=self.open_about_dialog,
            on_restore_defaults=self.restore_default_settings,
            on_update_sample_interval=self.update_sample_interval,
            on_open_adapters_settings=lambda: self.open_settings_dialog(initial_tab=0),
            on_open_speed_test=lambda: self.open_usage_dialog(initial_tab=3),
        )

        self._tray = SystemTrayManager(
            widget=self._widget,
            formatter=self._formatter,
            on_open_settings=self.open_settings_dialog,
            on_open_usage=self.open_usage_dialog,
            on_exit_app=self.shutdown,
            on_open_connection_info=self.open_connection_info_dialog,
            on_open_stopwatch=self.open_stopwatch_dialog,
            on_open_about=self.open_about_dialog,
        )

        # 6. Background Worker Thread
        self._worker = SamplingWorker(
            counter_source=self._counter_source,
            speed_calculator=self._speed_calculator,
            usage_accumulator=self._usage_accumulator,
            usage_database=self._database,
            interface_filter=self._interface_filter,
            sample_interval=self._settings.sample_interval_seconds,
            flush_interval=self._settings.flush_interval_seconds,
        )
        self._worker.speed_updated.connect(self._handle_speed_update)
        self._worker.update_selected_interfaces(self._settings.selected_interfaces)
        self._worker.set_auto_select_nic(self._settings.auto_select_nic)

        # 6. Listen for activation requests from secondary launches
        if self._guard:
            self._guard.activation_requested.connect(self._handle_activate_requested)

        # Connect application aboutToQuit signal to ensure clean shutdown
        self._qapp.aboutToQuit.connect(self.shutdown)

    def _setup_logging(self) -> None:
        """Initialize rotating log handler in %APPDATA%/FreeNetMeter/logs."""
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

        handler = RotatingFileHandler(
            str(LOG_FILE_PATH),
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)

        root_logger = logging.getLogger("FreeNetMeter")
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(handler)

    def _create_formatter(self) -> SpeedFormatter:
        """Instantiate SpeedFormatter from current settings."""
        return SpeedFormatter(
            unit_system=self._settings.unit_system,
            unit_type=self._settings.unit_type,
            fixed_unit=self._settings.fixed_unit,
            precision=self._settings.decimal_precision,
            arrow_style=self._settings.arrow_style,
        )

    def start(self) -> None:
        """Start worker thread and display widget."""
        self._worker.start()
        # Always display and elevate the floating speed widget on application launch
        self._widget._restore_and_clamp_position()
        self._widget.show()
        self._widget.raise_()
        self._widget.activateWindow()
        self._settings.widget_visible = True
        logger.info("%s started successfully.", APP_NAME)

    def _handle_speed_update(self, sample: SpeedSample) -> None:
        """Route calculated speeds from worker thread to widget, tray icon, and stopwatch."""
        self._widget.update_speed(sample)
        self._tray.update_tooltip(sample)
        if self._stopwatch_dialog is not None and self._stopwatch_dialog.isVisible():
            self._stopwatch_dialog.on_speed_sample(sample)
        if self._dashboard_window is not None and self._dashboard_window.isVisible():
            self._dashboard_window.update_live_speeds(sample)

    def _handle_activate_requested(self) -> None:
        """Handle secondary launch: restore widget and bring window to front."""
        logger.info("Activation requested: bringing widget to front.")
        self._widget._restore_and_clamp_position()
        self._widget.show()
        self._widget.raise_()
        self._widget.activateWindow()

    def open_settings_dialog(self, initial_tab: int = 0) -> None:
        """Open the interactive settings configuration dialog."""
        dialog = SettingsDialog(
            current_settings=self._settings,
            counter_source=self._counter_source,
            interface_filter=self._interface_filter,
            autostart_manager=self._autostart_manager,
            on_apply_live=self.apply_live_settings,
            on_save=self.save_settings,
            initial_tab=initial_tab,
            parent=self._widget,
        )
        dialog.exec()

    def open_usage_dialog(self, initial_tab: int = 3) -> None:
        """Open the flagship Master Dashboard and Control Center."""
        # Trigger an immediate database flush so the usage dialog reflects the very latest traffic
        self._worker.trigger_immediate_flush()
        if self._dashboard_window is None:
            self._dashboard_window = MasterDashboardWindow(
                usage_database=self._database,
                settings=self._settings,
                formatter=self._formatter,
                on_save_settings=self.save_settings,
                on_refresh_connection=self.refresh_connection,
                parent=None,
            )
        self._dashboard_window._sidebar.select_index(initial_tab)
        self._dashboard_window.show()
        self._dashboard_window.raise_()
        self._dashboard_window.activateWindow()

    def open_connection_info_dialog(self) -> None:
        """Open comprehensive network adapter diagnostic dialog."""
        dialog = ConnectionInfoDialog(settings=self._settings, parent=self._widget)
        dialog.exec()

    def open_stopwatch_dialog(self) -> None:
        """Open or raise the session bandwidth stopwatch window."""
        if self._stopwatch_dialog is None:
            self._stopwatch_dialog = StopwatchDialog(
                settings=self._settings,
                formatter=self._formatter,
                parent=None,
            )
        self._stopwatch_dialog.show()
        self._stopwatch_dialog.raise_()
        self._stopwatch_dialog.activateWindow()

    def open_about_dialog(self) -> None:
        """Open the application about and licensing dialog."""
        dialog = AboutDialog(settings=self._settings, parent=self._widget)
        dialog.exec()

    def open_help_dialog(self) -> None:
        """Open the user manual and shortcuts guide."""
        dialog = HelpDialog(settings=self._settings, parent=self._widget)
        dialog.exec()

    def refresh_connection(self) -> None:
        """Trigger immediate network adapter re-scan and counter re-baselining."""
        logger.info("Manual connection refresh requested by user.")
        self._worker.refresh_connection()

    def toggle_pause(self, paused: bool) -> None:
        """Pause or resume throughput sampling."""
        logger.info("Sampling pause toggled: %s", paused)
        self._worker.set_paused(paused)

    def update_sample_interval(self, interval: float) -> None:
        """Update counter sampling rate."""
        self._worker.update_sample_interval(interval)

    def restore_default_settings(self) -> None:
        """Reset all user preferences to default setup."""
        logger.info("Restoring factory default settings.")
        defaults = AppSettings()
        self._widget.snap_to_position("top-right")
        defaults.widget_x = self._widget.x()
        defaults.widget_y = self._widget.y()
        self.save_settings(defaults)

    def apply_live_settings(self, new_settings: AppSettings) -> None:
        """Update widget and tray visually in real-time as user adjusts sliders/combos."""
        self._settings = new_settings
        self._formatter = self._create_formatter()

        # Update widget presentation live
        self._widget.apply_settings(self._settings, self._formatter)
        self._tray.set_formatter(self._formatter)

        # Update worker filtering parameters
        self._interface_filter.set_excluded_keywords(self._settings.excluded_keywords)
        self._worker.update_selected_interfaces(self._settings.selected_interfaces)
        self._worker.set_auto_select_nic(self._settings.auto_select_nic)
        self._worker.update_rolling_window(self._settings.rolling_window_size)
        self._worker.update_sample_interval(self._settings.sample_interval_seconds)

    def save_settings(self, updated_settings: AppSettings) -> None:
        """Persist settings to disk and synchronize all components."""
        self.apply_live_settings(updated_settings)
        try:
            self._settings_store.save(self._settings)
            logger.info("Settings saved successfully.")
        except Exception as exc:
            logger.error("Failed to persist settings: %s", exc)

    def shutdown(self) -> None:
        """Cleanly terminate worker threads, flush usage, close database, and release locks."""
        if getattr(self, "_is_shutting_down", False):
            return
        self._is_shutting_down = True

        logger.info("Commencing clean application shutdown...")

        # 1. Stop background worker thread safely
        if self._worker.isRunning():
            self._worker.requestInterruption()
            self._worker.wait(2000)

        # 2. Save current widget coordinates (clamped to screen boundaries) and visibility
        clamped = self._widget._clamp_pos_to_screens(self._widget.pos())
        self._settings.widget_x = clamped.x()
        self._settings.widget_y = clamped.y()
        self._settings.widget_visible = self._widget.isVisible()
        try:
            self._settings_store.save(self._settings)
        except Exception as exc:
            logger.error("Error saving settings on exit: %s", exc)

        # 3. Cleanly remove system tray icon to avoid Windows ghost icons
        self._tray.shutdown()

        # 4. Release single-instance lock
        if self._guard:
            self._guard.release()

        logger.info("Shutdown complete.")
        self._qapp.quit()
