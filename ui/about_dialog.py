"""About FreeNetMeter Dialog.

Displays application identity, version, MIT licensing, and architectural transparency:
- 100% Free & Open Source statement
- Privacy First guarantee (zero telemetry, zero external network connections)
- Underlying runtime metrics (Python, PyQt6, Windows 64-bit kernel APIs)

Adheres to Apple Design Principles with clean layout, polished icon badge,
and fluid typography.
"""

from __future__ import annotations

import sys
from platform.theme_listener import WindowsThemeDetector

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from core.constants import APP_NAME, APP_VERSION
from storage.settings_store import AppSettings
from ui.assets import create_app_pixmap


class AboutDialog(QDialog):
    """Modal dialog displaying FreeNetMeter identity and licensing information."""

    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        """Initialize about dialog.

        Args:
            settings: Active AppSettings instance.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._settings = settings

        self.setWindowTitle(f"About {APP_NAME}")
        self.setFixedSize(460, 380)

        self._init_ui()
        self._apply_theme()

    def _init_ui(self) -> None:
        """Construct dialog layout."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 20)
        main_layout.setSpacing(16)

        # Header with high-res icon and titles
        header_layout = QHBoxLayout()
        header_layout.setSpacing(18)

        lbl_icon = QLabel()
        lbl_icon.setPixmap(create_app_pixmap(64))
        header_layout.addWidget(lbl_icon)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(3)
        lbl_name = QLabel(APP_NAME)
        lbl_name.setStyleSheet("font-size: 20px; font-weight: bold;")
        lbl_ver = QLabel(f"Version {APP_VERSION} (64-bit Windows)")
        lbl_ver.setStyleSheet("font-size: 12px; color: #007aff; font-weight: 500;")
        lbl_sub = QLabel("Precision Network Throughput Monitor")
        lbl_sub.setStyleSheet("font-size: 12px; opacity: 0.8;")

        title_layout.addWidget(lbl_name)
        title_layout.addWidget(lbl_ver)
        title_layout.addWidget(lbl_sub)
        header_layout.addLayout(title_layout)
        header_layout.addStretch(1)

        main_layout.addLayout(header_layout)

        # Description and Transparency Details
        details_layout = QVBoxLayout()
        details_layout.setSpacing(10)

        lbl_desc = QLabel(
            "FreeNetMeter is a completely free, open-source desktop network throughput meter "
            "engineered from scratch for Windows 10 and 11. Built with no copied assets, "
            "no telemetry, and no external dependencies."
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("font-size: 12px; line-height: 1.4;")
        details_layout.addWidget(lbl_desc)

        # Architecture Highlights
        arch_text = (
            f"<b>Runtime:</b> Python {sys.version.split()[0]} (64-bit) &bull; PyQt6<br>"
            "<b>Kernel Source:</b> Windows <code>MIB_IF_ROW2</code> (IP Helper API)<br>"
            "<b>Storage:</b> SQLite WAL Persistence & Atomic JSON Settings<br>"
            "<b>License:</b> MIT License (100% Free & Open Source)"
        )
        lbl_arch = QLabel(arch_text)
        lbl_arch.setStyleSheet(
            "font-size: 11px; padding: 10px; border-radius: 6px; background: rgba(127,127,127,0.1);"
        )
        details_layout.addWidget(lbl_arch)

        # Privacy badge
        lbl_priv = QLabel(
            "🛡️ <b>Privacy Guarantee:</b> Zero telemetry. Makes no network connections."
        )
        lbl_priv.setStyleSheet("font-size: 11px; color: #00e676; font-weight: 500;")
        details_layout.addWidget(lbl_priv)

        main_layout.addLayout(details_layout)
        main_layout.addStretch(1)

        # OK Button
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btn_box.accepted.connect(self.accept)
        main_layout.addWidget(btn_box)

    def _apply_theme(self) -> None:
        """Apply modern theme styling."""
        effective_theme = WindowsThemeDetector.resolve_theme(self._settings.theme_mode)
        is_dark = effective_theme == "dark"

        if is_dark:
            self.setStyleSheet("""
                QDialog {
                    background-color: #1e1f24;
                    color: #f0f0f0;
                    font-family: 'Segoe UI', -apple-system, sans-serif;
                }
                QLabel { color: #e0e0e0; }
                QPushButton {
                    background-color: #007aff;
                    color: #ffffff;
                    border: none;
                    border-radius: 6px;
                    padding: 6px 18px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #0066d6;
                }
            """)
        else:
            self.setStyleSheet("""
                QDialog {
                    background-color: #ffffff;
                    color: #1a1a1a;
                    font-family: 'Segoe UI', -apple-system, sans-serif;
                }
                QLabel { color: #222222; }
                QPushButton {
                    background-color: #007aff;
                    color: #ffffff;
                    border: none;
                    border-radius: 6px;
                    padding: 6px 18px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #0066d6;
                }
            """)
