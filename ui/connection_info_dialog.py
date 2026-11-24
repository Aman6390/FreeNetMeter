"""Network Connection Information Dialog.

Displays comprehensive diagnostic details for all network adapters:
- Operational status (UP / DOWN)
- Link speed and duplex
- IPv4 address and subnet mask
- IPv6 addresses
- Physical MAC hardware address
- Copy-to-clipboard functionality

Adheres to Apple Design principles:
- Sleek card-based grouping with fluid typography.
- Status badges with subtle glow.
- Responsive dark/light theme support.
"""

from __future__ import annotations

import socket
from platform.theme_listener import WindowsThemeDetector

import psutil
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from storage.settings_store import AppSettings


class ConnectionInfoDialog(QDialog):
    """Modal dialog presenting comprehensive network adapter diagnostic parameters."""

    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        """Initialize connection info dialog.

        Args:
            settings: Active AppSettings instance.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._settings = settings
        self.setWindowTitle("FreeNetMeter - Connection Information")
        self.setMinimumSize(480, 450)
        self.resize(520, 520)

        self._init_ui()
        self._apply_theme()
        self._populate_adapters()

    def _init_ui(self) -> None:
        """Construct dialog layout and components."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(14)

        # Header Title with subtle description
        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)
        lbl_title = QLabel("Network Connection Details")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        lbl_sub = QLabel("Active IP configurations and physical hardware parameters")
        lbl_sub.setStyleSheet("font-size: 11px; opacity: 0.8; color: #888888;")
        header_layout.addWidget(lbl_title)
        header_layout.addWidget(lbl_sub)
        main_layout.addLayout(header_layout)

        # Scrollable area for adapter cards
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        self._container = QWidget()
        self._card_layout = QVBoxLayout(self._container)
        self._card_layout.setContentsMargins(0, 0, 0, 0)
        self._card_layout.setSpacing(12)
        self._scroll.setWidget(self._container)
        main_layout.addWidget(self._scroll)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self._btn_refresh = QPushButton("Refresh")
        self._btn_refresh.clicked.connect(self._populate_adapters)
        btn_layout.addWidget(self._btn_refresh)

        self._btn_copy = QPushButton("Copy to Clipboard")
        self._btn_copy.clicked.connect(self._copy_to_clipboard)
        btn_layout.addWidget(self._btn_copy)

        btn_layout.addStretch(1)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(self.accept)
        btn_layout.addWidget(btn_box)

        main_layout.addLayout(btn_layout)

    def _apply_theme(self) -> None:
        """Apply modern dark/light styling."""
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
                    margin-top: 6px;
                    padding: 12px;
                    font-weight: bold;
                }
                QLabel {
                    color: #e0e0e0;
                }
                QPushButton {
                    background-color: #2d3039;
                    color: #ffffff;
                    border: 1px solid #454958;
                    border-radius: 6px;
                    padding: 6px 14px;
                    font-weight: 500;
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
                    margin-top: 6px;
                    padding: 12px;
                    font-weight: bold;
                }
                QLabel {
                    color: #222222;
                }
                QPushButton {
                    background-color: #e8ecf4;
                    color: #1a1a1a;
                    border: 1px solid #ccd1dc;
                    border-radius: 6px;
                    padding: 6px 14px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #007aff;
                    color: white;
                    border-color: #007aff;
                }
            """)

    def _populate_adapters(self) -> None:
        """Scan system interfaces and populate card layouts."""
        # Clear existing cards
        while self._card_layout.count():
            item = self._card_layout.takeAt(0)
            if item is not None:
                w = item.widget()
                if w is not None:
                    w.deleteLater()

        try:
            all_addrs = psutil.net_if_addrs()
            all_stats = psutil.net_if_stats()
        except Exception:
            all_addrs = {}
            all_stats = {}

        if not all_addrs:
            lbl_empty = QLabel("No active network interfaces detected.")
            lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._card_layout.addWidget(lbl_empty)
            return

        # Sort with UP adapters first, then alphabetically
        sorted_names = sorted(
            all_addrs.keys(),
            key=lambda n: (not (all_stats.get(n) and all_stats[n].isup), n.lower()),
        )

        for name in sorted_names:
            addrs = all_addrs[name]
            stats = all_stats.get(name)
            is_up = bool(stats and stats.isup)
            speed_mbps = stats.speed if stats else 0

            grp = QGroupBox(name)
            form = QFormLayout(grp)
            form.setSpacing(6)

            # Status row
            status_color = "#00e676" if is_up else "#888888"
            status_text = "CONNECTED (UP)" if is_up else "DISCONNECTED (DOWN)"
            lbl_status = QLabel(
                f"<span style='color: {status_color}; font-weight: bold;'>● {status_text}</span>"
            )
            form.addRow("Status:", lbl_status)

            if speed_mbps > 0:
                lbl_speed = QLabel(f"{speed_mbps} Mbps")
                form.addRow("Link Speed:", lbl_speed)

            # Addresses
            mac = None
            ipv4_list: list[tuple[str, str | None]] = []
            ipv6_list: list[str] = []

            for addr in addrs:
                # AF_LINK is MAC
                if addr.family == psutil.AF_LINK or (
                    hasattr(addr.family, "name") and addr.family.name == "AF_LINK"
                ):
                    mac = addr.address
                elif addr.family == socket.AF_INET:
                    ipv4_list.append((addr.address, addr.netmask))
                elif addr.family == socket.AF_INET6:
                    # Filter temporary link-local or show first
                    ipv6_list.append(addr.address)

            if mac:
                lbl_mac = QLabel(mac)
                lbl_mac.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                form.addRow("MAC Address:", lbl_mac)

            for ip, netmask in ipv4_list:
                mask_str = f" / {netmask}" if netmask else ""
                lbl_ip = QLabel(f"{ip}{mask_str}")
                lbl_ip.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                form.addRow("IPv4 Address:", lbl_ip)

            for ip6 in ipv6_list[:2]:  # Show top 2 IPv6
                lbl_ip6 = QLabel(ip6)
                lbl_ip6.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                form.addRow("IPv6 Address:", lbl_ip6)

            self._card_layout.addWidget(grp)

        self._card_layout.addStretch(1)

    def _copy_to_clipboard(self) -> None:
        """Export all adapter details as structured text to system clipboard."""
        lines: list[str] = ["=== FreeNetMeter Network Adapter Diagnostics ==="]
        try:
            all_addrs = psutil.net_if_addrs()
            all_stats = psutil.net_if_stats()
            for name, addrs in all_addrs.items():
                stats = all_stats.get(name)
                is_up = bool(stats and stats.isup)
                speed = stats.speed if stats else 0
                lines.append(f"\nAdapter: {name}")
                lines.append(f"  Status: {'UP' if is_up else 'DOWN'} (Speed: {speed} Mbps)")
                for a in addrs:
                    fam_name = getattr(a.family, "name", str(a.family))
                    lines.append(f"  {fam_name}: {a.address} (Netmask: {a.netmask})")
        except Exception as exc:
            lines.append(f"Error querying network: {exc}")

        text = "\n".join(lines)
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)
        self._btn_copy.setText("Copied!")
