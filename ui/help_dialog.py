"""How To Use and Shortcuts Help Dialog for FreeNetMeter.

Presents a clear user manual explaining widget gestures, context menu actions,
keyboard shortcuts, unit configurations, and diagnostic capabilities.

Adheres to Apple Design Principles with structured sections, readable typography,
and responsive theme styling.
"""

from __future__ import annotations

from platform.theme_listener import WindowsThemeDetector

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from storage.settings_store import AppSettings


class HelpDialog(QDialog):
    """Modal dialog presenting comprehensive user guidance and keyboard shortcuts."""

    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        """Initialize help dialog.

        Args:
            settings: Active AppSettings instance.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._settings = settings

        self.setWindowTitle("FreeNetMeter - How To Use & Quick Reference")
        self.setMinimumSize(500, 460)
        self.resize(540, 520)

        self._init_ui()
        self._apply_theme()

    def _init_ui(self) -> None:
        """Construct dialog layout."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 16)
        main_layout.setSpacing(14)

        lbl_header = QLabel("FreeNetMeter Guide & Shortcuts")
        lbl_header.setStyleSheet("font-size: 18px; font-weight: bold;")
        main_layout.addWidget(lbl_header)

        # Scrollable content area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 10, 0)
        content_layout.setSpacing(16)

        # 1. Desktop Widget Gestures
        s1 = QLabel(
            "<h3>1. Desktop Speed Widget</h3>"
            "<ul>"
            "<li><b>Drag & Move:</b> Left-click anywhere on the widget and drag it to your preferred position.</li>"
            "<li><b>Lock Position:</b> Right-click the widget and select <i>Lock Position</i> to prevent dragging.</li>"
            "<li><b>Snap Corners:</b> Right-click &rarr; <i>Change UI Position</i> to instantly snap to Top-Right, Top-Left, Bottom-Right, or Center.</li>"
            "<li><b>Screen Clamping:</b> The widget automatically stays inside your visible monitor workspace, even when unplugging external displays.</li>"
            "</ul>"
        )
        s1.setWordWrap(True)
        content_layout.addWidget(s1)

        # 2. Keyboard Shortcuts
        s2 = QLabel(
            "<h3>2. Keyboard Shortcuts</h3>"
            "<ul>"
            "<li><b>Ctrl + H:</b> Hide or show the floating desktop widget.</li>"
            "<li><b>S:</b> Open the Settings window.</li>"
            "<li><b>D:</b> Open the Data Usage Dashboard.</li>"
            "<li><b>Q:</b> Cleanly exit FreeNetMeter.</li>"
            "</ul>"
        )
        s2.setWordWrap(True)
        content_layout.addWidget(s2)

        # 3. System Tray Integration
        s3 = QLabel(
            "<h3>3. System Tray Icon</h3>"
            "<ul>"
            "<li><b>Live Tooltip:</b> Hover over the circular speedometer icon in your Windows taskbar notification area to see live download/upload speeds.</li>"
            "<li><b>Quick Toggle:</b> Left double-click the tray icon to quickly show or hide the floating desktop widget.</li>"
            "<li><b>Full Menu:</b> Right-click the tray icon for quick access to Settings, Data Usage, Connection Info, and Stopwatch.</li>"
            "</ul>"
        )
        s3.setWordWrap(True)
        content_layout.addWidget(s3)

        # 4. Units & Precision
        s4 = QLabel(
            "<h3>4. Units & Formatting</h3>"
            "<ul>"
            "<li><b>Bytes vs. Bits:</b> Toggle between Bytes per second (<code>KB/s</code>, <code>MB/s</code>) and Bits per second (<code>Kbps</code>, <code>Mbps</code>) in Settings.</li>"
            "<li><b>SI vs. Binary:</b> Decimal SI (1 KB = 1000 B) or Binary IEC (1 KiB = 1024 B).</li>"
            "<li><b>Direction Glyphs:</b> Choose between Triangles (<code>▲ / ▼</code>), Arrows (<code>↑ / ↓</code>), Letters (<code>U: / D:</code>), or None.</li>"
            "<li><b>Live Customization:</b> Colors, font family, font size, and background opacity update live without restarting.</li>"
            "</ul>"
        )
        s4.setWordWrap(True)
        content_layout.addWidget(s4)

        # 5. Diagnostic Tools & Features
        s5 = QLabel(
            "<h3>5. Built-In Utilities</h3>"
            "<ul>"
            "<li><b>Connection Info:</b> View active IP address, MAC address, link speed, and subnet mask.</li>"
            "<li><b>Session Stopwatch:</b> Measure total bandwidth and average/peak speeds during gaming, video calls, or downloads.</li>"
            "<li><b>Quick Links:</b> 1-click access to Windows Network Connections (<code>ncpa.cpl</code>), Settings, Resource Monitor, and Task Manager.</li>"
            "<li><b>Safe CSV Export:</b> Export usage history to Excel-ready UTF-8 CSV with formula injection defense.</li>"
            "<li><b>Pause / Resume:</b> Temporarily suspend sampling at any time from the right-click menu.</li>"
            "</ul>"
        )
        s5.setWordWrap(True)
        content_layout.addWidget(s5)

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

        # Close Button
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(self.accept)
        main_layout.addWidget(btn_box)

    def _apply_theme(self) -> None:
        """Apply sleek dark/light theme styling."""
        effective_theme = WindowsThemeDetector.resolve_theme(self._settings.theme_mode)
        is_dark = effective_theme == "dark"

        if is_dark:
            self.setStyleSheet("""
                QDialog {
                    background-color: #1e1f24;
                    color: #f0f0f0;
                    font-family: 'Segoe UI', -apple-system, sans-serif;
                }
                QLabel { color: #d8d8d8; }
                h3 { color: #007aff; }
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
                QLabel { color: #333333; }
                h3 { color: #0066d6; }
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
