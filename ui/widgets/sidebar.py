"""Navigation sidebar with modern Apple-style pill highlights and icon layout.

Manages 12 navigation modules:
0. Dashboard
1. Settings
2. Adapter Config
3. Speed Test
4. Test History
5. Usage Stats
6. Data Plan
7. WiFi
8. Network Info
9. Network Interface
10. Active Process
11. Network Tools
"""

from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.constants import APP_NAME

NAV_ITEMS = [
    ("📈", "Dashboard"),
    ("⚙️", "Settings"),
    ("🎛️", "Adapter Config"),
    ("⏱️", "Speed Test"),
    ("🕒", "Test History"),
    ("📊", "Usage Stats"),
    ("🥧", "Data Plan"),
    ("📶", "WiFi"),
    ("🌐", "Network Info"),
    ("🔌", "Network Interface"),
    ("⚡", "Active Process"),
    ("🛠️", "Network Tools"),
]


class NavigationSidebar(QWidget):
    """Vertical navigation sidebar with modern pill highlights."""

    nav_selected = pyqtSignal(int)

    def __init__(
        self,
        initial_index: int = 3,  # Speed Test by default as shown in screenshot
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setFixedWidth(200)
        self._current_index: int = initial_index
        self._buttons: List[QPushButton] = []
        self._btn_group = QButtonGroup(self)
        self._btn_group.setExclusive(True)

        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 14, 8, 14)
        main_layout.setSpacing(4)

        # 1. App Brand Header
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(6, 0, 6, 12)
        header_layout.setSpacing(10)

        # App Logo Icon (Green circle with arrows)
        lbl_logo = QLabel("⇅")
        lbl_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_logo.setFixedSize(32, 32)
        lbl_logo.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #00E676, stop:1 #00B0FF);
                color: #FFFFFF;
                font-size: 18px;
                font-weight: bold;
                border-radius: 16px;
            }
        """)

        lbl_title = QLabel(APP_NAME)
        lbl_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: #FFFFFF;")

        header_layout.addWidget(lbl_logo)
        header_layout.addWidget(lbl_title)
        header_layout.addStretch(1)
        main_layout.addLayout(header_layout)

        # Separator Line
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(
            "color: #2E3342; background-color: #2E3342; height: 1px; margin-bottom: 8px;"
        )
        main_layout.addWidget(sep)

        # 2. Scrollable Navigation List
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(3)

        for i, (icon, title) in enumerate(NAV_ITEMS):
            btn = QPushButton(f"  {icon}   {title}")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
            btn.setStyleSheet("""
                QPushButton {
                    text-align: left;
                    padding: 8px 12px;
                    border: none;
                    border-radius: 8px;
                    color: #94A3B8;
                    background-color: transparent;
                }
                QPushButton:hover {
                    color: #F8FAFC;
                    background-color: #262934;
                }
                QPushButton:checked {
                    color: #FFFFFF;
                    font-weight: bold;
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #007AFF, stop:1 #2563EB);
                }
            """)
            if i == self._current_index:
                btn.setChecked(True)

            btn.clicked.connect(lambda _, idx=i: self._on_btn_clicked(idx))
            self._btn_group.addButton(btn, i)
            self._buttons.append(btn)
            c_layout.addWidget(btn)

        c_layout.addStretch(1)
        scroll.setWidget(container)
        main_layout.addWidget(scroll, 1)

    def _on_btn_clicked(self, index: int) -> None:
        self._current_index = index
        self.nav_selected.emit(index)

    def select_index(self, index: int) -> None:
        """Select a navigation item programmatically."""
        if 0 <= index < len(self._buttons):
            self._buttons[index].setChecked(True)
            self._on_btn_clicked(index)
