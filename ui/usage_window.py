"""Data usage telemetry and analytics window.

Adheres to Apple Design Principles:
- Prominent metric summary cards displaying Today, Past 7 Days, Past 30 Days, and All-Time totals.
- Clean, responsive data table with formatted byte values and per-interface filtering.
- One-click CSV export with UTF-8 BOM encoding and formula injection defense.
"""

from __future__ import annotations

import datetime
import logging
from pathlib import Path
from platform.theme_listener import WindowsThemeDetector

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.constants import APP_NAME
from core.formatter import SpeedFormatter
from storage.settings_store import AppSettings
from storage.usage_database import UsageDatabase

logger = logging.getLogger("FreeNetMeter.UsageWindow")


class UsageDialog(QDialog):
    """Analytics dashboard presenting historical and aggregate network data usage."""

    def __init__(
        self,
        usage_database: UsageDatabase,
        settings: AppSettings,
        formatter: SpeedFormatter,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize usage window.

        Args:
            usage_database: UsageDatabase instance for querying metrics.
            settings: Current AppSettings instance.
            formatter: SpeedFormatter instance for formatting byte values.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._db = usage_database
        self._settings = settings
        self._formatter = formatter

        self.setWindowTitle(f"{APP_NAME} - Network Data Usage")
        self.resize(720, 560)
        self.setMinimumSize(600, 450)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self._init_ui()
        self._apply_dialog_theme()
        self.refresh_data()

    def _init_ui(self) -> None:
        """Build metrics cards, table view, filter toolbar, and export controls."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(14)

        # 1. Top Section: Metric Summary Cards
        main_layout.addLayout(self._create_summary_cards())

        # 2. Filter Bar
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(10)

        filter_bar.addWidget(QLabel("Interface Filter:"))
        self._cmb_filter_iface = QComboBox()
        self._cmb_filter_iface.addItem("All Interfaces", "all")
        self._cmb_filter_iface.currentIndexChanged.connect(self._populate_table)
        filter_bar.addWidget(self._cmb_filter_iface, 1)

        self._btn_refresh = QPushButton("Refresh")
        self._btn_refresh.clicked.connect(self.refresh_data)
        filter_bar.addWidget(self._btn_refresh)

        self._btn_export_csv = QPushButton("Export to CSV...")
        self._btn_export_csv.clicked.connect(self._handle_export_csv)
        filter_bar.addWidget(self._btn_export_csv)

        main_layout.addLayout(filter_bar)

        # 3. Main Data Table
        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(
            ["Date", "Interface", "Downloaded", "Uploaded", "Total Usage"]
        )
        header = self._table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        main_layout.addWidget(self._table, 1)

    def _create_summary_cards(self) -> QHBoxLayout:
        """Create 4 Apple-inspired metric summary cards for quick telemetry glance."""
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(10)

        self._card_today_val, card_today = self._create_card("Today")
        self._card_week_val, card_week = self._create_card("Past 7 Days")
        self._card_month_val, card_month = self._create_card("Past 30 Days")
        self._card_all_val, card_all = self._create_card("All-Time Total")

        cards_layout.addWidget(card_today)
        cards_layout.addWidget(card_week)
        cards_layout.addWidget(card_month)
        cards_layout.addWidget(card_all)

        return cards_layout

    def _create_card(self, title: str) -> tuple[QLabel, QWidget]:
        """Construct a single rounded metric card."""
        card = QWidget()
        card.setObjectName("MetricCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        lbl_title = QLabel(title)
        lbl_title.setObjectName("CardTitle")
        lbl_val = QLabel("0 B")
        lbl_val.setObjectName("CardValue")

        layout.addWidget(lbl_title)
        layout.addWidget(lbl_val)
        return lbl_val, card

    def _apply_dialog_theme(self) -> None:
        """Apply sleek macOS/Windows 11 translucent card aesthetic."""
        effective_theme = WindowsThemeDetector.resolve_theme(self._settings.theme_mode)
        is_dark = effective_theme == "dark"

        if is_dark:
            self.setStyleSheet("""
                QDialog {
                    background-color: #1a1b1f;
                    color: #f5f5f7;
                    font-family: 'Segoe UI', -apple-system, sans-serif;
                }
                QWidget#MetricCard {
                    background-color: #24262d;
                    border: 1px solid #363945;
                    border-radius: 8px;
                }
                QLabel#CardTitle {
                    color: #8e94a5;
                    font-size: 11px;
                    font-weight: 600;
                    text-transform: uppercase;
                }
                QLabel#CardValue {
                    color: #00e676;
                    font-size: 16px;
                    font-weight: 700;
                }
                QTableWidget {
                    background-color: #202228;
                    alternate-background-color: #262830;
                    border: 1px solid #363945;
                    border-radius: 6px;
                    color: #f0f0f0;
                    gridline-color: #2e313c;
                }
                QHeaderView::section {
                    background-color: #292b34;
                    color: #a0a6b8;
                    font-weight: bold;
                    padding: 6px;
                    border: none;
                    border-bottom: 1px solid #363945;
                }
                QComboBox, QPushButton {
                    background-color: #282a32;
                    border: 1px solid #3d4250;
                    border-radius: 5px;
                    padding: 6px 12px;
                    color: #ffffff;
                }
                QPushButton:hover {
                    background-color: #007aff;
                }
                """)
        else:
            self.setStyleSheet("""
                QDialog {
                    background-color: #f6f7f9;
                    color: #1d1d1f;
                    font-family: 'Segoe UI', -apple-system, sans-serif;
                }
                QWidget#MetricCard {
                    background-color: #ffffff;
                    border: 1px solid #dcdfe6;
                    border-radius: 8px;
                }
                QLabel#CardTitle {
                    color: #6e7381;
                    font-size: 11px;
                    font-weight: 600;
                    text-transform: uppercase;
                }
                QLabel#CardValue {
                    color: #007aff;
                    font-size: 16px;
                    font-weight: 700;
                }
                QTableWidget {
                    background-color: #ffffff;
                    alternate-background-color: #f9fafb;
                    border: 1px solid #dcdfe6;
                    border-radius: 6px;
                    color: #1a1a1a;
                    gridline-color: #ebeef5;
                }
                QHeaderView::section {
                    background-color: #f0f2f6;
                    color: #4b5162;
                    font-weight: bold;
                    padding: 6px;
                    border: none;
                    border-bottom: 1px solid #dcdfe6;
                }
                QComboBox, QPushButton {
                    background-color: #ffffff;
                    border: 1px solid #ccd1dc;
                    border-radius: 5px;
                    padding: 6px 12px;
                    color: #1a1a1a;
                }
                QPushButton:hover {
                    background-color: #007aff;
                    color: white;
                }
                """)

    def refresh_data(self) -> None:
        """Query SQLite database and update card statistics and table records."""
        today_str = datetime.datetime.now().astimezone().strftime("%Y-%m-%d")

        # 1. Update summary cards
        summary = self._db.get_summary(today_str)
        self._card_today_val.setText(self._formatter.format_bytes_total(summary.today_total))
        self._card_week_val.setText(self._formatter.format_bytes_total(summary.week_total))
        self._card_month_val.setText(self._formatter.format_bytes_total(summary.month_total))
        self._card_all_val.setText(self._formatter.format_bytes_total(summary.all_time_total))

        # 2. Populate interface filter combo box
        breakdown = self._db.get_interface_breakdown()
        current_iface = self._cmb_filter_iface.currentData()

        self._cmb_filter_iface.blockSignals(True)
        self._cmb_filter_iface.clear()
        self._cmb_filter_iface.addItem("All Interfaces", "all")
        for iface_name, _, _, _ in breakdown:
            self._cmb_filter_iface.addItem(iface_name, iface_name)

        # Restore previous filter selection
        idx = self._cmb_filter_iface.findData(current_iface)
        self._cmb_filter_iface.setCurrentIndex(max(0, idx))
        self._cmb_filter_iface.blockSignals(False)

        # 3. Populate Table Rows
        self._populate_table()

    def _populate_table(self) -> None:
        """Query individual historical records and fill the table widget."""
        selected_iface = self._cmb_filter_iface.currentData()
        entries = self._db.get_history(interface_name=selected_iface)

        self._table.setRowCount(len(entries))
        for row_idx, entry in enumerate(entries):
            # Date
            item_date = QTableWidgetItem(entry.date_str)
            item_date.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row_idx, 0, item_date)

            # Interface
            item_iface = QTableWidgetItem(entry.interface_name)
            self._table.setItem(row_idx, 1, item_iface)

            # Downloaded
            item_down = QTableWidgetItem(self._formatter.format_bytes_total(entry.bytes_recv))
            item_down.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(row_idx, 2, item_down)

            # Uploaded
            item_up = QTableWidgetItem(self._formatter.format_bytes_total(entry.bytes_sent))
            item_up.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(row_idx, 3, item_up)

            # Total
            item_total = QTableWidgetItem(self._formatter.format_bytes_total(entry.total_bytes))
            item_total.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item_total.setFont(
                QFont(self.font().family(), self.font().pointSize(), QFont.Weight.Bold)
            )
            self._table.setItem(row_idx, 4, item_total)

    def _handle_export_csv(self) -> None:
        """Prompt user for destination and export safe CSV with UTF-8 BOM."""
        default_filename = f"FreeNetMeter_Usage_{datetime.date.today().isoformat()}.csv"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Data Usage to CSV",
            str(Path.home() / default_filename),
            "CSV Files (*.csv);;All Files (*)",
        )

        if not file_path:
            return

        try:
            exported_rows = self._db.export_csv(Path(file_path), self._formatter)
            QMessageBox.information(
                self,
                "Export Complete",
                f"Successfully exported {exported_rows} usage records to:\n{file_path}\n\n"
                "The file is encoded with UTF-8 BOM for Microsoft Excel compatibility "
                "and protected against spreadsheet formula injection.",
            )
        except Exception as exc:
            logger.error("CSV Export failed: %s", exc)
            QMessageBox.critical(
                self,
                "Export Error",
                f"Failed to export CSV file:\n{exc}",
            )
