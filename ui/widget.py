"""Frameless, draggable, always-on-top desktop speed widget.

Adheres to Apple Design Principles:
- Sleek rounded geometry with smooth translucency and subtle borders.
- Crisp tabular typographic rhythm that prevents layout jitter as numbers fluctuate.
- Natural, friction-free drag mechanics with position locking.
- Multi-monitor intelligence: clamps to visible screen areas on startup and handles
  unplugged monitor scenarios automatically.
- Rich right-click context menu offering instant diagnostics, corner snapping,
  session stopwatch, connection details, and quick system links.
"""

from __future__ import annotations

import logging
from platform.quick_links import (
    open_device_manager,
    open_firewall,
    open_network_connections,
    open_network_settings,
    open_resource_monitor,
    open_speed_test,
    open_task_manager,
)
from platform.theme_listener import WindowsThemeDetector
from typing import Callable

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import (
    QAction,
    QColor,
    QContextMenuEvent,
    QCursor,
    QFont,
    QGuiApplication,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QScreen,
)
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QVBoxLayout,
    QWidget,
)

from core.formatter import SpeedFormatter
from core.speed_calculator import SpeedSample
from storage.settings_store import AppSettings

logger = logging.getLogger("FreeNetMeter.Widget")


class DesktopSpeedWidget(QWidget):
    """Floating desktop overlay displaying real-time download and upload throughput."""

    def __init__(
        self,
        settings: AppSettings,
        formatter: SpeedFormatter,
        on_open_settings: Callable[[], None],
        on_open_usage: Callable[[], None],
        on_exit_app: Callable[[], None],
        on_save_settings: Callable[[AppSettings], None],
        on_refresh_connection: Callable[[], None] | None = None,
        on_pause_toggle: Callable[[bool], None] | None = None,
        on_open_connection_info: Callable[[], None] | None = None,
        on_open_stopwatch: Callable[[], None] | None = None,
        on_open_help: Callable[[], None] | None = None,
        on_open_about: Callable[[], None] | None = None,
        on_restore_defaults: Callable[[], None] | None = None,
        on_update_sample_interval: Callable[[float], None] | None = None,
        on_open_adapters_settings: Callable[[], None] | None = None,
        on_open_speed_test: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize desktop speed widget.

        Args:
            settings: Active AppSettings instance.
            formatter: SpeedFormatter instance for text conversions.
            on_open_settings: Callback to display settings window.
            on_open_usage: Callback to display data usage window.
            on_exit_app: Callback to cleanly terminate application.
            on_save_settings: Callback to persist updated settings.
            on_refresh_connection: Optional callback to re-baseline network counters.
            on_pause_toggle: Optional callback to pause/resume monitoring.
            on_open_connection_info: Optional callback to show connection info dialog.
            on_open_stopwatch: Optional callback to show session stopwatch dialog.
            on_open_help: Optional callback to show how to use guide.
            on_open_about: Optional callback to show about dialog.
            on_restore_defaults: Optional callback to reset settings to defaults.
            on_update_sample_interval: Optional callback when refresh rate is changed.
            on_open_adapters_settings: Optional callback to open Settings at Adapters tab.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._settings = settings
        self._formatter = formatter
        self._on_open_settings = on_open_settings
        self._on_open_usage = on_open_usage
        self._on_exit_app = on_exit_app
        self._on_save_settings = on_save_settings

        self._on_refresh_connection = on_refresh_connection
        self._on_pause_toggle = on_pause_toggle
        self._on_open_connection_info = on_open_connection_info
        self._on_open_stopwatch = on_open_stopwatch
        self._on_open_help = on_open_help
        self._on_open_about = on_open_about
        self._on_restore_defaults = on_restore_defaults
        self._on_update_sample_interval = on_update_sample_interval
        self._on_open_adapters_settings = on_open_adapters_settings
        self._on_open_speed_test = on_open_speed_test

        # Dragging state
        self._is_dragging: bool = False
        self._has_moved: bool = False
        self._drag_start_pos: QPoint = QPoint()
        self._drag_offset: QPoint = QPoint()
        self._is_paused: bool = False

        self._update_window_flags()
        self._init_ui()
        self._apply_styling()
        self._restore_and_clamp_position()

        # Connect screen change listeners so widget remains visible across display sleeps, DPI changes, and monitor hotplugs
        app = QGuiApplication.instance()
        if app is not None:
            app.screenAdded.connect(lambda *_: self._restore_and_clamp_position())
            app.screenRemoved.connect(lambda *_: self._restore_and_clamp_position())
            primary = QGuiApplication.primaryScreen()
            if primary is not None:
                primary.geometryChanged.connect(lambda *_: self._restore_and_clamp_position())

    def _update_window_flags(self) -> None:
        """Update window flags dynamically based on user preferences.

        Only updates flags when they actually differ from the current flags to avoid
        unnecessary native Win32 window handle (HWND) destruction, flicker, or hiding.
        """
        flags = Qt.WindowType.FramelessWindowHint
        if self._settings.always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        if not self._settings.keep_in_taskbar:
            flags |= Qt.WindowType.Tool

        if self.windowFlags() != flags:
            was_visible = self.isVisible() or self._settings.widget_visible
            self.setWindowFlags(flags)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
            if was_visible:
                self.show()

    def _init_ui(self) -> None:
        """Construct widget layout and child labels."""
        # Compact, sleek geometry (shorter width and height)
        self.setFixedWidth(122)
        self.setFixedHeight(40)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(7, 3, 7, 3)
        main_layout.setSpacing(1)

        # Row 1: Upload Speed (at top)
        self._row_up = QHBoxLayout()
        self._row_up.setContentsMargins(0, 0, 0, 0)
        self._row_up.setSpacing(3)
        self._lbl_up_arrow = QLabel()
        self._lbl_up_val = QLabel("0.0 B/s")
        self._lbl_up_val.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._row_up.addWidget(self._lbl_up_arrow)
        self._row_up.addWidget(self._lbl_up_val, 1)

        # Row 2: Download Speed (in bottom)
        self._row_down = QHBoxLayout()
        self._row_down.setContentsMargins(0, 0, 0, 0)
        self._row_down.setSpacing(3)
        self._lbl_down_arrow = QLabel()
        self._lbl_down_val = QLabel("0.0 B/s")
        self._lbl_down_val.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._row_down.addWidget(self._lbl_down_arrow)
        self._row_down.addWidget(self._lbl_down_val, 1)

        main_layout.addLayout(self._row_up)
        main_layout.addLayout(self._row_down)

        self._update_arrow_glyphs()

    def _update_arrow_glyphs(self) -> None:
        """Update direction indicator glyphs from formatter, keeping digits tightly aligned."""
        glyphs = self._formatter.get_arrow_glyphs()
        self._lbl_up_arrow.setText(glyphs.upload)
        self._lbl_down_arrow.setText(glyphs.download)

        has_glyph = bool(glyphs.upload or glyphs.download)
        self._lbl_up_arrow.setVisible(has_glyph)
        self._lbl_down_arrow.setVisible(has_glyph)

        if has_glyph:
            # Measure text width using font metrics to set a tight, matching width for both
            fm = self._lbl_up_arrow.fontMetrics()
            w = max(
                fm.horizontalAdvance(glyphs.upload),
                fm.horizontalAdvance(glyphs.download),
                12,
            )
            self._lbl_up_arrow.setFixedWidth(w + 1)
            self._lbl_down_arrow.setFixedWidth(w + 1)
            self._lbl_up_arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._lbl_down_arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def _apply_styling(self) -> None:
        """Apply colors, fonts, and background opacity to the widget."""
        # Resolve font
        font = QFont(self._settings.font_family, self._settings.font_size)
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setBold(True)

        self._lbl_up_arrow.setFont(font)
        self._lbl_up_val.setFont(font)
        self._lbl_down_arrow.setFont(font)
        self._lbl_down_val.setFont(font)

        # Apply text colors
        color_up = self._settings.color_upload
        color_down = self._settings.color_download

        self._lbl_up_arrow.setStyleSheet(f"color: {color_up}; background: transparent;")
        self._lbl_up_val.setStyleSheet(f"color: {color_up}; background: transparent;")
        self._lbl_down_arrow.setStyleSheet(f"color: {color_down}; background: transparent;")
        self._lbl_down_val.setStyleSheet(f"color: {color_down}; background: transparent;")

        self._update_arrow_glyphs()
        self.update()

    def paintEvent(self, event: QPaintEvent | None) -> None:
        """Custom paint event to render rounded translucent glass background."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        effective_theme = WindowsThemeDetector.resolve_theme(self._settings.theme_mode)
        is_dark = effective_theme == "dark"

        # Calculate alpha from opacity percentage (20 to 100)
        alpha = int((self._settings.background_opacity / 100.0) * 255)

        if is_dark:
            bg_color = QColor(24, 25, 29, alpha)
            border_color = QColor(255, 255, 255, min(40, alpha))
        else:
            bg_color = QColor(245, 246, 248, alpha)
            border_color = QColor(0, 0, 0, min(35, alpha))

        # Render rounded rectangle background
        rect = self.rect().adjusted(1, 1, -1, -1)
        painter.setBrush(bg_color)
        painter.setPen(border_color)
        painter.drawRoundedRect(rect, 8.0, 8.0)
        painter.end()

    def _clamp_pos_to_screens(self, pos: QPoint) -> QPoint:
        """Clamp coordinates strictly inside the target monitor's available geometry.

        Guarantees that the widget never slides behind the Windows Taskbar or off-screen,
        supporting smooth dragging across multi-monitor setups.
        """
        screens = QGuiApplication.screens()
        if not screens:
            return pos

        # Target screen selection:
        # 1. Screen containing the mouse cursor (for responsive multi-monitor dragging)
        cursor_pos = QCursor.pos()
        target_screen = QGuiApplication.screenAt(cursor_pos)

        widget_center = QPoint(pos.x() + self.width() // 2, pos.y() + self.height() // 2)
        if target_screen is None:
            # 2. Screen containing widget center
            target_screen = QGuiApplication.screenAt(widget_center)

        if target_screen is None:
            # 3. Fallback: Screen with minimum distance to widget center
            def screen_dist_sq(s: QScreen) -> float:
                c = s.geometry().center()
                dx = float(c.x() - widget_center.x())
                dy = float(c.y() - widget_center.y())
                return dx * dx + dy * dy

            target_screen = min(screens, key=screen_dist_sq)

        geo = target_screen.availableGeometry()
        max_x = geo.x() + geo.width() - self.width()
        max_y = geo.y() + geo.height() - self.height()
        clamped_x = max(geo.x(), min(pos.x(), max_x))
        clamped_y = max(geo.y(), min(pos.y(), max_y))
        return QPoint(clamped_x, clamped_y)

    def _restore_and_clamp_position(self) -> None:
        """Position widget on screen, clamping strictly to visible monitor geometry."""
        screens = QGuiApplication.screens()
        if not screens:
            return

        primary_screen = QGuiApplication.primaryScreen() or screens[0]
        primary_geo = primary_screen.availableGeometry()

        target_x = self._settings.widget_x
        target_y = self._settings.widget_y

        # If no saved position, place in top-right corner of primary display
        if target_x is None or target_y is None:
            target_x = primary_geo.right() - self.width() - 24
            target_y = primary_geo.top() + 40
            clamped = QPoint(target_x, target_y)
        else:
            clamped = self._clamp_pos_to_screens(QPoint(target_x, target_y))

        self.move(clamped)
        self._settings.widget_x = clamped.x()
        self._settings.widget_y = clamped.y()

    def snap_to_position(self, corner: str) -> None:
        """Snap widget to predefined screen anchor points."""
        screens = QGuiApplication.screens()
        if not screens:
            return

        primary_screen = QGuiApplication.primaryScreen() or screens[0]
        geo = primary_screen.availableGeometry()

        if corner == "top-right":
            x = geo.right() - self.width() - 24
            y = geo.top() + 40
        elif corner == "top-left":
            x = geo.left() + 24
            y = geo.top() + 40
        elif corner == "bottom-right":
            x = geo.right() - self.width() - 24
            y = geo.bottom() - self.height() - 48
        elif corner == "bottom-left":
            x = geo.left() + 24
            y = geo.bottom() - self.height() - 48
        elif corner == "center":
            x = geo.center().x() - self.width() // 2
            y = geo.center().y() - self.height() // 2
        else:
            return

        self.move(x, y)
        self._settings.widget_x = x
        self._settings.widget_y = y
        self._on_save_settings(self._settings)

    def take_screenshot(self) -> None:
        """Capture screenshot of the desktop widget and copy to clipboard."""
        pixmap = self.grab()
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setPixmap(pixmap)

    def update_speed(self, sample: SpeedSample) -> None:
        """Update live download and upload speed display.

        Args:
            sample: Calculated SpeedSample containing smoothed speeds.
        """
        if self._is_paused:
            self._lbl_up_val.setText("PAUSED")
            self._lbl_down_val.setText("PAUSED")
            return

        formatted_down = self._formatter.format_speed(sample.total_download_speed)
        formatted_up = self._formatter.format_speed(sample.total_upload_speed)

        self._lbl_down_val.setText(formatted_down.full_str)
        self._lbl_up_val.setText(formatted_up.full_str)

    def apply_settings(self, settings: AppSettings, formatter: SpeedFormatter) -> None:
        """Apply newly updated settings live.

        Args:
            settings: Updated AppSettings.
            formatter: Updated SpeedFormatter.
        """
        self._settings = settings
        self._formatter = formatter
        self._update_window_flags()
        self._update_arrow_glyphs()
        self._apply_styling()

    # Keyboard Shortcuts
    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        """Handle keyboard shortcuts when widget has focus."""
        if event is None:
            return
        key = event.key()
        modifiers = event.modifiers()
        has_ctrl = bool(modifiers & Qt.KeyboardModifier.ControlModifier)

        if key == Qt.Key.Key_S and (has_ctrl or not bool(modifiers)):
            self._on_open_settings()
            event.accept()
        elif key == Qt.Key.Key_D and (has_ctrl or not bool(modifiers)):
            self._on_open_usage()
            event.accept()
        elif key == Qt.Key.Key_Q and has_ctrl:
            self._on_exit_app()
            event.accept()
        elif key == Qt.Key.Key_H and has_ctrl:
            self.hide()
            event.accept()
        else:
            super().keyPressEvent(event)

    # Drag and Drop Mechanics
    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        """Handle mouse press to initiate drag tracking if position is not locked."""
        if (
            event is not None
            and event.button() == Qt.MouseButton.LeftButton
            and not self._settings.locked_position
        ):
            self._is_dragging = True
            self._has_moved = False
            self._drag_start_pos = event.globalPosition().toPoint()
            self._drag_offset = event.globalPosition().toPoint() - self.pos()
            event.accept()
        elif event is not None:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:
        """Handle dragging movement with screen edge clamping."""
        if (
            event is not None
            and self._is_dragging
            and bool(event.buttons() & Qt.MouseButton.LeftButton)
        ):
            current_pos = event.globalPosition().toPoint()
            if not self._has_moved:
                delta = current_pos - self._drag_start_pos
                if abs(delta.x()) < 3 and abs(delta.y()) < 3:
                    event.accept()
                    return
                self._has_moved = True

            new_pos = current_pos - self._drag_offset
            clamped = self._clamp_pos_to_screens(new_pos)
            self.move(clamped)
            event.accept()
        elif event is not None:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        """Handle mouse release to persist new widget coordinates if dragged."""
        if event is not None and event.button() == Qt.MouseButton.LeftButton and self._is_dragging:
            self._is_dragging = False
            if self._has_moved:
                self._has_moved = False
                clamped = self._clamp_pos_to_screens(self.pos())
                self.move(clamped)
                self._settings.widget_x = clamped.x()
                self._settings.widget_y = clamped.y()
                self._on_save_settings(self._settings)
            event.accept()
        elif event is not None:
            super().mouseReleaseEvent(event)

    # Context Menu Actions
    def _set_speed_interval(self, interval: float) -> None:
        """Set speed refresh rate from context menu."""
        self._settings.sample_interval_seconds = interval
        self._on_save_settings(self._settings)
        if self._on_update_sample_interval:
            self._on_update_sample_interval(interval)

    def _toggle_lock(self, checked: bool) -> None:
        """Toggle position lock."""
        self._settings.locked_position = checked
        self._on_save_settings(self._settings)

    def _toggle_always_on_top(self, checked: bool) -> None:
        """Toggle always on top window state."""
        self._settings.always_on_top = checked
        self._update_window_flags()
        self._on_save_settings(self._settings)

    def _toggle_keep_in_taskbar(self, checked: bool) -> None:
        """Toggle presence in Windows taskbar."""
        self._settings.keep_in_taskbar = checked
        self._update_window_flags()
        self._on_save_settings(self._settings)

    def _toggle_auto_nic(self, checked: bool) -> None:
        """Toggle automatic NIC selection."""
        self._settings.auto_select_nic = checked
        self._on_save_settings(self._settings)

    def _toggle_pause(self, checked: bool) -> None:
        """Toggle monitoring pause state."""
        self._is_paused = checked
        if self._on_pause_toggle:
            self._on_pause_toggle(checked)
        if checked:
            self._lbl_up_val.setText("PAUSED")
            self._lbl_down_val.setText("PAUSED")

    def contextMenuEvent(self, event: QContextMenuEvent | None) -> None:
        """Display rich right-click context menu containing all diagnostic and control tools."""
        if event is None:
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #24252a;
                color: #f0f0f0;
                border: 1px solid #3c3f4a;
                border-radius: 8px;
                padding: 4px;
                font-family: 'Segoe UI', -apple-system, sans-serif;
            }
            QMenu::item {
                padding: 6px 24px 6px 14px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #007aff;
                color: white;
            }
            QMenu::separator {
                height: 1px;
                background-color: #383c48;
                margin: 4px 8px;
            }
        """)

        # 1. Hide (Ctrl+H)
        act_hide = menu.addAction("Hide\tCtrl+H")
        if act_hide:
            act_hide.triggered.connect(self.hide)

        # 2. Setting (Ctrl+S)
        act_settings = menu.addAction("Setting\tCtrl+S")
        if act_settings:
            act_settings.triggered.connect(self._on_open_settings)

        # 3. Dashboard (Ctrl+D)
        act_dashboard = menu.addAction("Dashboard\tCtrl+D")
        if act_dashboard:
            act_dashboard.triggered.connect(self._on_open_usage)

        menu.addSeparator()

        # 4. Refresh Connection
        act_refresh = menu.addAction("Refresh Connection")
        if act_refresh and self._on_refresh_connection:
            act_refresh.triggered.connect(self._on_refresh_connection)

        # 5. Speed Refresh Time Submenu
        menu_speed = menu.addMenu("Speed Refresh Time")
        if menu_speed:
            speeds = [
                ("0.5 s (High Frequency)", 0.5),
                ("1.0 s (Default)", 1.0),
                ("2.0 s", 2.0),
                ("3.0 s", 3.0),
                ("5.0 s", 5.0),
            ]
            for label, val in speeds:
                act = menu_speed.addAction(label)
                if act:
                    act.setCheckable(True)
                    act.setChecked(abs(self._settings.sample_interval_seconds - val) < 0.05)
                    act.triggered.connect(lambda _, v=val: self._set_speed_interval(v))

        # 6. Adapters (NIC) Setting
        act_nic_settings = menu.addAction("Adapters (NIC) Setting")
        if act_nic_settings:
            act_nic_settings.triggered.connect(
                self._on_open_adapters_settings or self._on_open_settings
            )

        # 7. Auto Select NIC
        act_auto_nic = QAction("Auto Select NIC", menu)
        act_auto_nic.setCheckable(True)
        act_auto_nic.setChecked(self._settings.auto_select_nic)
        act_auto_nic.toggled.connect(self._toggle_auto_nic)
        menu.addAction(act_auto_nic)

        # 8. Connection Info
        if self._on_open_connection_info:
            act_conn_info = menu.addAction("Connection Info")
            if act_conn_info:
                act_conn_info.triggered.connect(self._on_open_connection_info)

        menu.addSeparator()

        # 9. Always On Top
        act_top = QAction("Always On Top", menu)
        act_top.setCheckable(True)
        act_top.setChecked(self._settings.always_on_top)
        act_top.toggled.connect(self._toggle_always_on_top)
        menu.addAction(act_top)

        # 10. Lock Position
        act_lock = QAction("Lock Position", menu)
        act_lock.setCheckable(True)
        act_lock.setChecked(self._settings.locked_position)
        act_lock.toggled.connect(self._toggle_lock)
        menu.addAction(act_lock)

        # 11. Keep in Taskbar
        act_taskbar = QAction("Keep in Taskbar", menu)
        act_taskbar.setCheckable(True)
        act_taskbar.setChecked(self._settings.keep_in_taskbar)
        act_taskbar.toggled.connect(self._toggle_keep_in_taskbar)
        menu.addAction(act_taskbar)

        # 12. Change UI Position Submenu
        menu_pos = menu.addMenu("Change UI Position")
        if menu_pos:
            act_tr = menu_pos.addAction("Top-Right (Default)")
            if act_tr:
                act_tr.triggered.connect(lambda: self.snap_to_position("top-right"))
            act_tl = menu_pos.addAction("Top-Left")
            if act_tl:
                act_tl.triggered.connect(lambda: self.snap_to_position("top-left"))
            act_br = menu_pos.addAction("Bottom-Right")
            if act_br:
                act_br.triggered.connect(lambda: self.snap_to_position("bottom-right"))
            act_bl = menu_pos.addAction("Bottom-Left")
            if act_bl:
                act_bl.triggered.connect(lambda: self.snap_to_position("bottom-left"))
            act_ctr = menu_pos.addAction("Center Screen")
            if act_ctr:
                act_ctr.triggered.connect(lambda: self.snap_to_position("center"))

        menu.addSeparator()

        # 13. Data Usages Stat
        act_usage = menu.addAction("Data Usages Stat")
        if act_usage:
            act_usage.triggered.connect(self._on_open_usage)

        # 14. Stopwatch
        if self._on_open_stopwatch:
            act_sw = menu.addAction("Stopwatch")
            if act_sw:
                act_sw.triggered.connect(self._on_open_stopwatch)

        # 15. Test Speed
        act_speed_test = menu.addAction("Test Speed")
        if act_speed_test:
            act_speed_test.triggered.connect(
                self._on_open_speed_test or (lambda: open_speed_test())
            )

        # 16. Active Process (Resource Monitor)
        act_active_proc = menu.addAction("Active Process")
        if act_active_proc:
            act_active_proc.triggered.connect(lambda: open_resource_monitor())

        # 17. Quick Links Submenu
        menu_quick = menu.addMenu("Quick Links")
        if menu_quick:
            act_ncpa = menu_quick.addAction("Network Connections (ncpa.cpl)")
            if act_ncpa:
                act_ncpa.triggered.connect(open_network_connections)
            act_net_settings = menu_quick.addAction("Network Settings (ms-settings)")
            if act_net_settings:
                act_net_settings.triggered.connect(open_network_settings)
            act_resmon = menu_quick.addAction("Resource Monitor (resmon)")
            if act_resmon:
                act_resmon.triggered.connect(open_resource_monitor)
            act_taskmgr = menu_quick.addAction("Task Manager (taskmgr)")
            if act_taskmgr:
                act_taskmgr.triggered.connect(open_task_manager)
            act_dev = menu_quick.addAction("Device Manager (devmgmt.msc)")
            if act_dev:
                act_dev.triggered.connect(open_device_manager)
            act_fw = menu_quick.addAction("Windows Firewall (firewall.cpl)")
            if act_fw:
                act_fw.triggered.connect(open_firewall)

        # 18. Network Properties
        act_net_props = menu.addAction("Network Properties")
        if act_net_props:
            act_net_props.triggered.connect(open_network_connections)

        # 19. Take Screenshot
        act_ss = menu.addAction("Take Screenshot")
        if act_ss:
            act_ss.triggered.connect(self.take_screenshot)

        menu.addSeparator()

        # 20. Pause
        act_pause = QAction("Pause", menu)
        act_pause.setCheckable(True)
        act_pause.setChecked(self._is_paused)
        act_pause.toggled.connect(self._toggle_pause)
        menu.addAction(act_pause)

        # 21. Restore Default Setup
        if self._on_restore_defaults:
            act_restore = menu.addAction("Restore Default Setup")
            if act_restore:
                act_restore.triggered.connect(self._on_restore_defaults)

        # 22. How To Use
        if self._on_open_help:
            act_help = menu.addAction("How To Use")
            if act_help:
                act_help.triggered.connect(self._on_open_help)

        # 23. About
        if self._on_open_about:
            act_about = menu.addAction("About")
            if act_about:
                act_about.triggered.connect(self._on_open_about)

        menu.addSeparator()

        # 24. Exit (Ctrl+Q)
        act_exit = menu.addAction("Exit\tCtrl+Q")
        if act_exit:
            act_exit.triggered.connect(self._on_exit_app)

        menu.exec(event.globalPos())
