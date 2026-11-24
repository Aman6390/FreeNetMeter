"""Settings configuration dialog for FreeNetMeter.

Implements Apple-inspired UI design principles:
- Clear typographic hierarchy and consistent 8pt spacing grid.
- Live preview: adjustments to colors, fonts, arrows, units, and opacity reflect instantly on the desktop widget.
- Clean category grouping: Adapters, Display, Appearance, and System.
"""

from __future__ import annotations

import logging
from platform.autostart import WindowsAutostartManager
from platform.theme_listener import WindowsThemeDetector
from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFontComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.constants import APP_NAME
from core.counter_source import CounterSource
from core.interface_filter import InterfaceFilter
from storage.settings_store import AppSettings

logger = logging.getLogger("FreeNetMeter.SettingsWindow")


class SettingsDialog(QDialog):
    """Configuration dialog providing interactive customization with live updates."""

    def __init__(
        self,
        current_settings: AppSettings,
        counter_source: CounterSource,
        interface_filter: InterfaceFilter,
        autostart_manager: WindowsAutostartManager,
        on_apply_live: Callable[[AppSettings], None],
        on_save: Callable[[AppSettings], None],
        initial_tab: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize settings dialog.

        Args:
            current_settings: Current AppSettings instance.
            counter_source: CounterSource to list available network adapters.
            interface_filter: Filter to determine physical vs virtual adapters.
            autostart_manager: WindowsAutostartManager for registry integration.
            on_apply_live: Callback to trigger instant visual update on the widget.
            on_save: Callback to persist settings to disk.
            initial_tab: Index of initial tab to display (0: Adapters, 1: Display, etc.).
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._settings = AppSettings.from_dict(current_settings.__dict__)
        self._source = counter_source
        self._filter = interface_filter
        self._autostart = autostart_manager
        self._on_apply_live = on_apply_live
        self._on_save = on_save

        self.setWindowTitle(f"{APP_NAME} - Settings")
        self.setFixedSize(520, 560)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self._init_ui()
        if 0 <= initial_tab < self._tabs.count():
            self._tabs.setCurrentIndex(initial_tab)
        self._apply_dialog_theme()

    def _init_ui(self) -> None:
        """Construct dialog tabs and action buttons."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._create_adapters_tab(), "Adapters")
        self._tabs.addTab(self._create_display_tab(), "Display & Units")
        self._tabs.addTab(self._create_appearance_tab(), "Appearance")
        self._tabs.addTab(self._create_system_tab(), "System & Storage")

        main_layout.addWidget(self._tabs)

        # Bottom standard buttons: OK (Save), Cancel
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._handle_accept)
        btn_box.rejected.connect(self.reject)
        main_layout.addWidget(btn_box)

    def _apply_dialog_theme(self) -> None:
        """Apply sleek modern styling consistent with macOS / Windows 11 design guidelines."""
        effective_theme = WindowsThemeDetector.resolve_theme(self._settings.theme_mode)
        is_dark = effective_theme == "dark"

        if is_dark:
            self.setStyleSheet("""
                QDialog {
                    background-color: #1e1f24;
                    color: #f0f0f0;
                    font-family: 'Segoe UI', -apple-system, sans-serif;
                }
                QTabWidget::pane {
                    border: 1px solid #333640;
                    background: #25272e;
                    border-radius: 8px;
                }
                QTabBar::tab {
                    background: #1e1f24;
                    color: #a0a4b0;
                    padding: 8px 16px;
                    border-top-left-radius: 6px;
                    border-top-right-radius: 6px;
                }
                QTabBar::tab:selected {
                    background: #25272e;
                    color: #ffffff;
                    font-weight: bold;
                }
                QGroupBox {
                    border: 1px solid #383c48;
                    border-radius: 6px;
                    margin-top: 12px;
                    padding-top: 14px;
                    font-weight: bold;
                    color: #007aff;
                }
                QLabel {
                    color: #e0e0e0;
                }
                QLineEdit, QComboBox, QSpinBox, QFontComboBox, QListWidget {
                    background-color: #18191d;
                    border: 1px solid #3d4252;
                    border-radius: 4px;
                    padding: 4px 8px;
                    color: #ffffff;
                }
                QPushButton {
                    background-color: #007aff;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    padding: 6px 14px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #0066d6;
                }
                """)
        else:
            self.setStyleSheet("""
                QDialog {
                    background-color: #f5f6f8;
                    color: #202020;
                    font-family: 'Segoe UI', -apple-system, sans-serif;
                }
                QTabWidget::pane {
                    border: 1px solid #d0d4dc;
                    background: #ffffff;
                    border-radius: 8px;
                }
                QTabBar::tab {
                    background: #e6e8ee;
                    color: #555a65;
                    padding: 8px 16px;
                    border-top-left-radius: 6px;
                    border-top-right-radius: 6px;
                }
                QTabBar::tab:selected {
                    background: #ffffff;
                    color: #000000;
                    font-weight: bold;
                }
                QGroupBox {
                    border: 1px solid #d8dce6;
                    border-radius: 6px;
                    margin-top: 12px;
                    padding-top: 14px;
                    font-weight: bold;
                    color: #0066d6;
                }
                QLineEdit, QComboBox, QSpinBox, QFontComboBox, QListWidget {
                    background-color: #ffffff;
                    border: 1px solid #ccd1dc;
                    border-radius: 4px;
                    padding: 4px 8px;
                    color: #1a1a1a;
                }
                QPushButton {
                    background-color: #007aff;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    padding: 6px 14px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #0066d6;
                }
                """)

    # 1. Adapters Tab
    def _create_adapters_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)

        lbl_info = QLabel("Select network adapters to monitor (uncheck to ignore):")
        layout.addWidget(lbl_info)

        self._list_adapters = QListWidget()
        self._populate_adapters_list()
        layout.addWidget(self._list_adapters)

        # Exclusion list keyword configuration
        grp_exclude = QGroupBox("Excluded Adapter Keywords")
        grp_layout = QVBoxLayout(grp_exclude)
        lbl_ex = QLabel("Comma-separated keywords to filter virtual adapters:")
        self._txt_exclude = QLineEdit(", ".join(self._settings.excluded_keywords))
        grp_layout.addWidget(lbl_ex)
        grp_layout.addWidget(self._txt_exclude)
        layout.addWidget(grp_exclude)

        return widget

    def _populate_adapters_list(self) -> None:
        """Scan system interfaces and populate checklist."""
        self._list_adapters.clear()
        try:
            snapshot = self._source.read_counters()
            statuses = self._source.read_interface_statuses()
            available = sorted(snapshot.counters.keys())
        except Exception:
            available = []
            statuses = {}

        saved_selected = set(self._settings.selected_interfaces)

        # If user has no saved selection, default to physical adapters that are up
        if not saved_selected:
            default_selected = set(self._filter.get_default_selected(available, statuses))
        else:
            default_selected = saved_selected

        for name in available:
            stat = statuses.get(name)
            status_text = " (UP)" if (stat and stat.is_up) else " (DOWN)"
            item = QListWidgetItem(f"{name}{status_text}")
            item.setData(Qt.ItemDataRole.UserRole, name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            check_state = (
                Qt.CheckState.Checked if name in default_selected else Qt.CheckState.Unchecked
            )
            item.setCheckState(check_state)
            self._list_adapters.addItem(item)

    # 2. Display & Units Tab
    def _create_display_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)

        form = QFormLayout()
        form.setSpacing(12)

        # Unit system: Decimal SI vs Binary IEC
        self._cmb_unit_system = QComboBox()
        self._cmb_unit_system.addItem("Decimal SI (1 KB = 1000 B)", "decimal")
        self._cmb_unit_system.addItem("Binary IEC (1 KiB = 1024 B)", "binary")
        idx_sys = 0 if self._settings.unit_system == "decimal" else 1
        self._cmb_unit_system.setCurrentIndex(idx_sys)
        self._cmb_unit_system.currentIndexChanged.connect(self._trigger_live_update)
        form.addRow("Unit Standard:", self._cmb_unit_system)

        # Value type: Bytes vs Bits
        self._cmb_unit_type = QComboBox()
        self._cmb_unit_type.addItem("Bytes per second (B/s, KB/s, MB/s)", "bytes")
        self._cmb_unit_type.addItem("Bits per second (bps, Kbps, Mbps)", "bits")
        idx_type = 0 if self._settings.unit_type == "bytes" else 1
        self._cmb_unit_type.setCurrentIndex(idx_type)
        self._cmb_unit_type.currentIndexChanged.connect(self._trigger_live_update)
        form.addRow("Measurement:", self._cmb_unit_type)

        # Fixed unit override
        self._cmb_fixed_unit = QComboBox()
        self._cmb_fixed_unit.addItems(
            ["Auto", "B/s", "KB/s", "MB/s", "GB/s", "bps", "Kbps", "Mbps", "Gbps"]
        )
        curr_fixed = self._settings.fixed_unit.capitalize()
        fixed_idx = self._cmb_fixed_unit.findText(curr_fixed, Qt.MatchFlag.MatchFixedString)
        self._cmb_fixed_unit.setCurrentIndex(fixed_idx if fixed_idx >= 0 else 0)
        self._cmb_fixed_unit.currentIndexChanged.connect(self._trigger_live_update)
        form.addRow("Fixed Unit Scale:", self._cmb_fixed_unit)

        # Decimal precision
        self._spn_precision = QSpinBox()
        self._spn_precision.setRange(0, 2)
        self._spn_precision.setValue(self._settings.decimal_precision)
        self._spn_precision.valueChanged.connect(self._trigger_live_update)
        form.addRow("Decimal Precision:", self._spn_precision)

        # Arrow style
        self._cmb_arrow_style = QComboBox()
        self._cmb_arrow_style.addItem("Triangles (▼ / ▲)", "triangle")
        self._cmb_arrow_style.addItem("Arrows (↓ / ↑)", "arrow")
        self._cmb_arrow_style.addItem("Letters (D: / U:)", "letters")
        self._cmb_arrow_style.addItem("None", "none")
        arrow_map = {"triangle": 0, "arrow": 1, "letters": 2, "none": 3}
        self._cmb_arrow_style.setCurrentIndex(arrow_map.get(self._settings.arrow_style, 0))
        self._cmb_arrow_style.currentIndexChanged.connect(self._trigger_live_update)
        form.addRow("Direction Style:", self._cmb_arrow_style)

        # Speed Refresh Interval
        self._cmb_refresh_rate = QComboBox()
        self._cmb_refresh_rate.addItem("1.0 s (Default - 1 second)", 1.0)
        self._cmb_refresh_rate.addItem("0.5 s (High Frequency)", 0.5)
        self._cmb_refresh_rate.addItem("2.0 s", 2.0)
        self._cmb_refresh_rate.addItem("3.0 s", 3.0)
        self._cmb_refresh_rate.addItem("5.0 s", 5.0)
        rate_idx = self._cmb_refresh_rate.findData(self._settings.sample_interval_seconds)
        self._cmb_refresh_rate.setCurrentIndex(rate_idx if rate_idx >= 0 else 0)
        self._cmb_refresh_rate.currentIndexChanged.connect(self._trigger_live_update)
        form.addRow("Refresh Interval:", self._cmb_refresh_rate)

        layout.addLayout(form)
        layout.addStretch()
        return widget

    # 3. Appearance Tab
    def _create_appearance_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)

        form = QFormLayout()
        form.setSpacing(12)

        # Theme mode
        self._cmb_theme = QComboBox()
        self._cmb_theme.addItem("Follow Windows Setting", "system")
        self._cmb_theme.addItem("Dark Mode", "dark")
        self._cmb_theme.addItem("Light Mode", "light")
        theme_map = {"system": 0, "dark": 1, "light": 2}
        self._cmb_theme.setCurrentIndex(theme_map.get(self._settings.theme_mode, 0))
        self._cmb_theme.currentIndexChanged.connect(self._handle_theme_change)
        form.addRow("Theme:", self._cmb_theme)

        # Font Family
        self._cmb_font = QFontComboBox()
        self._cmb_font.setCurrentFont(QFont(self._settings.font_family))
        self._cmb_font.currentFontChanged.connect(self._trigger_live_update)
        form.addRow("Font Family:", self._cmb_font)

        # Font Size
        self._spn_font_size = QSpinBox()
        self._spn_font_size.setRange(8, 24)
        self._spn_font_size.setValue(self._settings.font_size)
        self._spn_font_size.valueChanged.connect(self._trigger_live_update)
        form.addRow("Font Size (pt):", self._spn_font_size)

        # Download Color Picker
        self._btn_color_down = QPushButton("Pick Color")
        self._btn_color_down.setStyleSheet(
            f"background-color: {self._settings.color_download}; color: black; font-weight: bold;"
        )
        self._btn_color_down.clicked.connect(self._pick_download_color)
        form.addRow("Download Color:", self._btn_color_down)

        # Upload Color Picker
        self._btn_color_up = QPushButton("Pick Color")
        self._btn_color_up.setStyleSheet(
            f"background-color: {self._settings.color_upload}; color: black; font-weight: bold;"
        )
        self._btn_color_up.clicked.connect(self._pick_upload_color)
        form.addRow("Upload Color:", self._btn_color_up)

        # Opacity Slider
        op_layout = QHBoxLayout()
        self._sld_opacity = QSlider(Qt.Orientation.Horizontal)
        self._sld_opacity.setRange(20, 100)
        self._sld_opacity.setValue(self._settings.background_opacity)
        self._lbl_opacity_val = QLabel(f"{self._settings.background_opacity}%")
        self._sld_opacity.valueChanged.connect(self._handle_opacity_slider)
        op_layout.addWidget(self._sld_opacity)
        op_layout.addWidget(self._lbl_opacity_val)
        form.addRow("Background Opacity:", op_layout)

        layout.addLayout(form)
        layout.addStretch()
        return widget

    def _handle_opacity_slider(self, value: int) -> None:
        self._lbl_opacity_val.setText(f"{value}%")
        self._trigger_live_update()

    def _pick_download_color(self) -> None:
        initial = QColor(self._settings.color_download)
        color = QColorDialog.getColor(initial, self, "Select Download Color")
        if color.isValid():
            self._settings.color_download = color.name()
            self._btn_color_down.setStyleSheet(
                f"background-color: {color.name()}; color: black; font-weight: bold;"
            )
            self._trigger_live_update()

    def _pick_upload_color(self) -> None:
        initial = QColor(self._settings.color_upload)
        color = QColorDialog.getColor(initial, self, "Select Upload Color")
        if color.isValid():
            self._settings.color_upload = color.name()
            self._btn_color_up.setStyleSheet(
                f"background-color: {color.name()}; color: black; font-weight: bold;"
            )
            self._trigger_live_update()

    def _handle_theme_change(self) -> None:
        self._trigger_live_update()
        self._apply_dialog_theme()

    # 4. System & Storage Tab
    def _create_system_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)

        form = QFormLayout()
        form.setSpacing(12)

        # Start with Windows
        self._chk_autostart = QCheckBox("Start FreeNetMeter with Windows (HKCU Run)")
        self._chk_autostart.setChecked(self._settings.start_with_windows)
        form.addRow("Autostart:", self._chk_autostart)

        # Data Retention
        self._spn_retention = QSpinBox()
        self._spn_retention.setRange(0, 3650)
        self._spn_retention.setSpecialValueText("Keep forever (0)")
        self._spn_retention.setValue(self._settings.retention_days)
        form.addRow("Data Retention (days):", self._spn_retention)

        # Rolling Window Smoothing
        self._spn_smoothing = QSpinBox()
        self._spn_smoothing.setRange(1, 10)
        self._spn_smoothing.setValue(self._settings.rolling_window_size)
        self._spn_smoothing.setSuffix(" samples")
        self._spn_smoothing.valueChanged.connect(self._trigger_live_update)
        form.addRow("Speed Smoothing:", self._spn_smoothing)

        layout.addLayout(form)
        layout.addStretch()
        return widget

    def _gather_settings_from_ui(self) -> AppSettings:
        """Read all inputs from UI controls into an AppSettings instance."""
        # Read selected adapters
        selected: list[str] = []
        for i in range(self._list_adapters.count()):
            item = self._list_adapters.item(i)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                name = item.data(Qt.ItemDataRole.UserRole)
                if name:
                    selected.append(str(name))

        # Excluded keywords
        kw_text = self._txt_exclude.text()
        keywords = [k.strip() for k in kw_text.split(",") if k.strip()]

        unit_sys = self._cmb_unit_system.currentData()
        unit_type = self._cmb_unit_type.currentData()
        fixed_u = self._cmb_fixed_unit.currentText().lower()
        prec = self._spn_precision.value()
        arrow = self._cmb_arrow_style.currentData()

        theme_mode = self._cmb_theme.currentData()
        font_family = self._cmb_font.currentFont().family()
        font_size = self._spn_font_size.value()
        opacity = self._sld_opacity.value()

        autostart = self._chk_autostart.isChecked()
        retention = self._spn_retention.value()
        smoothing = self._spn_smoothing.value()
        refresh_interval = float(self._cmb_refresh_rate.currentData() or 1.0)

        return AppSettings(
            schema_version=self._settings.schema_version,
            widget_x=self._settings.widget_x,
            widget_y=self._settings.widget_y,
            locked_position=self._settings.locked_position,
            widget_visible=self._settings.widget_visible,
            selected_interfaces=selected,
            excluded_keywords=keywords,
            unit_system=unit_sys,
            unit_type=unit_type,
            fixed_unit=fixed_u,
            decimal_precision=prec,
            arrow_style=arrow,
            theme_mode=theme_mode,
            font_family=font_family,
            font_size=font_size,
            color_download=self._settings.color_download,
            color_upload=self._settings.color_upload,
            background_opacity=opacity,
            start_with_windows=autostart,
            retention_days=retention,
            rolling_window_size=smoothing,
            sample_interval_seconds=refresh_interval,
            flush_interval_seconds=self._settings.flush_interval_seconds,
        )

    def _trigger_live_update(self) -> None:
        """Emit live updates to widget while dialog is open."""
        updated = self._gather_settings_from_ui()
        self._on_apply_live(updated)

    def _handle_accept(self) -> None:
        """Save settings and apply Windows integration changes."""
        updated = self._gather_settings_from_ui()

        # Update Windows autostart registry if changed
        if updated.start_with_windows != self._autostart.is_enabled():
            self._autostart.set_enabled(updated.start_with_windows)

        # Persist to JSON
        self._on_save(updated)
        self.accept()
