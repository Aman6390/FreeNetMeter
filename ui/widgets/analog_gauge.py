"""Custom high-fidelity Analog Speedometer Arc Gauge.

Adheres to Apple Design Principles:
- Fluid 60 FPS spring animation interpolating smoothly toward current speed.
- Crisp vector-rendered glowing arc, track, and tick marks.
- Prominent tabular typographic readout with unit and status tags.
"""

from __future__ import annotations

import math
from typing import Optional

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPaintEvent,
    QPen,
)
from PyQt6.QtWidgets import QWidget


class AnalogSpeedometerGauge(QWidget):
    """Vector-rendered semi-circular speedometer gauge with glowing sweep."""

    # Scale thresholds for 0 -> 1000 Mbps (1 Gbps)
    TICKS = [
        (0.0, "0"),
        (100.0, "100"),
        (250.0, "250"),
        (500.0, "500"),
        (750.0, "750"),
        (1000.0, "1G"),
    ]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(280, 240)

        self._target_speed: float = 0.0
        self._current_speed: float = 0.0
        self._max_speed: float = 1000.0  # 1 Gbps scale
        self._unit_label: str = "Mbps"
        self._status_text: str = "Ready"
        self._status_color: QColor = QColor("#00E676")  # Green

        # 60 FPS animation timer for fluid needle / arc smoothing
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(16)
        self._anim_timer.timeout.connect(self._animate_step)
        self._anim_timer.start()

    def set_speed(self, speed_mbps: float) -> None:
        """Update target speed."""
        self._target_speed = max(0.0, speed_mbps)

    def set_status(self, text: str, color_hex: str = "#00E676") -> None:
        """Update status line below readout."""
        self._status_text = text
        self._status_color = QColor(color_hex)
        self.update()

    def reset(self) -> None:
        """Reset gauge reading to zero."""
        self._target_speed = 0.0
        self._status_text = "Ready"
        self._status_color = QColor("#94A3B8")
        self.update()

    def _animate_step(self) -> None:
        """Interpolate smoothly toward target speed."""
        diff = self._target_speed - self._current_speed
        if abs(diff) > 0.1:
            # Spring ease factor
            self._current_speed += diff * 0.18
            self.update()
        elif self._current_speed != self._target_speed:
            self._current_speed = self._target_speed
            self.update()

    def _speed_to_angle(self, speed: float) -> float:
        """Convert speed value to arc angle in degrees (220° to -40° span)."""
        # Angles: 0 Mbps starts at 215° (bottom left), 1000 Mbps ends at -35° (bottom right)
        start_angle = 215.0
        total_span = 250.0

        clamped = max(0.0, min(self._max_speed, speed))
        # Non-linear scaling for better sensitivity at lower speeds
        # 0 -> 100 is 20% of arc, 100 -> 250 is 20%, 250 -> 500 is 20%, 500 -> 1000 is 40%
        if clamped <= 100.0:
            fraction = (clamped / 100.0) * 0.20
        elif clamped <= 250.0:
            fraction = 0.20 + ((clamped - 100.0) / 150.0) * 0.20
        elif clamped <= 500.0:
            fraction = 0.40 + ((clamped - 250.0) / 250.0) * 0.20
        else:
            fraction = 0.60 + ((clamped - 500.0) / 500.0) * 0.40

        return start_angle - (fraction * total_span)

    def paintEvent(self, event: QPaintEvent | None) -> None:
        """Render high-fidelity curved arc, tick marks, and digital display."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        width = self.width()
        height = self.height()
        cx = width / 2.0
        cy = height * 0.52
        radius = min(width * 0.38, height * 0.42)

        arc_rect = QRectF(cx - radius, cy - radius, radius * 2.0, radius * 2.0)
        track_thickness = max(8.0, radius * 0.08)

        # 1. Background Arc Track (Dark Navy/Slate)
        bg_pen = QPen(QColor(36, 40, 54, 180), track_thickness)
        bg_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(bg_pen)
        # In Qt, arc angles are in 1/16th of a degree
        start_angle_qt = int(215.0 * 16)
        span_angle_qt = int(-250.0 * 16)
        painter.drawArc(arc_rect, start_angle_qt, span_angle_qt)

        # 2. Active Glowing Speed Arc
        if self._current_speed > 0.1:
            active_angle = self._speed_to_angle(self._current_speed)
            active_span = (active_angle - 215.0) * 16.0

            grad = QLinearGradient(
                arc_rect.left(), arc_rect.top(), arc_rect.right(), arc_rect.bottom()
            )
            grad.setColorAt(0.0, QColor("#007AFF"))
            grad.setColorAt(0.5, QColor("#2979FF"))
            grad.setColorAt(1.0, QColor("#00E676"))

            active_pen = QPen(grad, track_thickness)
            active_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(active_pen)
            painter.drawArc(arc_rect, start_angle_qt, int(active_span))

        # 3. Tick Marks and Labels
        painter.setFont(QFont("Segoe UI", int(max(8.0, radius * 0.08)), QFont.Weight.Bold))
        for val, label in self.TICKS:
            deg = self._speed_to_angle(val)
            rad = math.radians(deg)

            # Tick tick lines
            r_in = radius - track_thickness * 1.4
            r_out = radius - track_thickness * 0.8
            p1 = QPointF(cx + r_in * math.cos(rad), cy - r_in * math.sin(rad))
            p2 = QPointF(cx + r_out * math.cos(rad), cy - r_out * math.sin(rad))

            tick_pen = QPen(QColor(160, 175, 205, 140), 1.5)
            painter.setPen(tick_pen)
            painter.drawLine(p1, p2)

            # Label text positioned outside arc
            r_lbl = radius + track_thickness * 1.5
            tx = cx + r_lbl * math.cos(rad)
            ty = cy - r_lbl * math.sin(rad)

            painter.setPen(QColor("#94A3B8"))
            lbl_rect = QRectF(tx - 24, ty - 10, 48, 20)
            painter.drawText(lbl_rect, Qt.AlignmentFlag.AlignCenter, label)

        # 4. Center Speed Indicator Bar / Needle Pill
        curr_deg = self._speed_to_angle(self._current_speed)
        curr_rad = math.radians(curr_deg)
        needle_len = radius * 0.80
        nx = cx + needle_len * math.cos(curr_rad)
        ny = cy - needle_len * math.sin(curr_rad)

        needle_pen = QPen(QColor("#FFFFFF"), max(3.0, track_thickness * 0.25))
        needle_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(needle_pen)
        painter.drawLine(QPointF(cx, cy), QPointF(nx, ny))

        # Center pivot circle
        painter.setBrush(QColor("#007AFF"))
        painter.setPen(QPen(QColor("#FFFFFF"), 2.0))
        painter.drawEllipse(QPointF(cx, cy), 6.0, 6.0)

        # 5. Center Digital Readout (Speed Number)
        painter.setPen(QColor("#F8FAFC"))
        readout_font = QFont("Segoe UI", int(max(20.0, radius * 0.26)), QFont.Weight.Bold)
        readout_font.setStyleHint(QFont.StyleHint.Monospace)
        painter.setFont(readout_font)

        if self._current_speed < 0.05 and self._target_speed < 0.05:
            display_num = "--"
        else:
            display_num = f"{self._current_speed:.1f}"

        speed_rect = QRectF(cx - 100, cy + 10, 200, 36)
        painter.drawText(speed_rect, Qt.AlignmentFlag.AlignCenter, display_num)

        # 6. Unit Label (e.g. Mbps)
        unit_font = QFont("Segoe UI", int(max(10.0, radius * 0.09)), QFont.Weight.DemiBold)
        painter.setFont(unit_font)
        painter.setPen(QColor("#94A3B8"))
        unit_rect = QRectF(cx - 100, cy + 46, 200, 20)
        painter.drawText(unit_rect, Qt.AlignmentFlag.AlignCenter, self._unit_label)

        # 7. Status Line (e.g. Cancelled. / Testing Download...)
        status_font = QFont("Segoe UI", int(max(9.0, radius * 0.08)), QFont.Weight.Normal)
        painter.setFont(status_font)
        painter.setPen(self._status_color)
        status_rect = QRectF(cx - 100, cy + 68, 200, 20)
        painter.drawText(status_rect, Qt.AlignmentFlag.AlignCenter, self._status_text)

        painter.end()
