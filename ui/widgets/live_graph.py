"""Live speed & latency graph canvas for real-time test visualization.

Plots dual waveforms:
1. Speed curve (Mbps) with smooth gradient-filled underlay.
2. Latency curve (ms) overlay with distinct glowing stroke.
"""

from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
)
from PyQt6.QtWidgets import QWidget

from core.speed_test_engine import SpeedTestSamplePoint


class LiveSpeedLatencyGraph(QWidget):
    """Vector canvas rendering dynamic speed and ping curves during execution."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(320, 180)
        self._samples: List[SpeedTestSamplePoint] = []
        self._max_speed: float = 50.0
        self._max_latency: float = 100.0

    def add_sample(self, sample: SpeedTestSamplePoint) -> None:
        """Add new live telemetry point and trigger redraw."""
        self._samples.append(sample)
        if sample.speed_mbps > self._max_speed:
            self._max_speed = max(50.0, sample.speed_mbps * 1.15)
        if sample.latency_ms > self._max_latency:
            self._max_latency = max(100.0, sample.latency_ms * 1.15)
        self.update()

    def clear(self) -> None:
        """Clear all historical curve samples."""
        self._samples.clear()
        self._max_speed = 50.0
        self._max_latency = 100.0
        self.update()

    def paintEvent(self, event: QPaintEvent | None) -> None:
        """Render background grid, curves, and empty state placeholder."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = self.rect().adjusted(2, 2, -2, -2)
        w = rect.width()
        h = rect.height()

        # 1. Dark Card Background with subtle border
        painter.setBrush(QColor(22, 24, 30))
        painter.setPen(QPen(QColor(42, 46, 58), 1.0))
        painter.drawRoundedRect(rect, 8.0, 8.0)

        # 2. Empty State
        if not self._samples:
            painter.setPen(QColor("#64748B"))
            painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Normal))
            painter.drawText(
                rect,
                Qt.AlignmentFlag.AlignCenter,
                "Live speed and latency appear here during a test",
            )
            painter.end()
            return

        # 3. Grid Lines
        grid_pen = QPen(QColor(38, 42, 54), 1.0, Qt.PenStyle.DashLine)
        painter.setPen(grid_pen)
        for i in range(1, 4):
            y = rect.top() + (h / 4.0) * i
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))

        padding_x = 12.0
        padding_y = 12.0
        plot_w = w - padding_x * 2.0
        plot_h = h - padding_y * 2.0

        max_t = max(1.0, self._samples[-1].elapsed_s)

        # 4. Draw Speed Curve & Filled Area
        speed_path = QPainterPath()
        speed_points: List[QPointF] = []

        for s in self._samples:
            x = rect.left() + padding_x + (s.elapsed_s / max_t) * plot_w
            # Higher speed = lower y coordinate
            y = (
                rect.bottom()
                - padding_y
                - (min(s.speed_mbps, self._max_speed) / self._max_speed) * plot_h
            )
            speed_points.append(QPointF(x, y))

        if speed_points:
            speed_path.moveTo(speed_points[0])
            for pt in speed_points[1:]:
                speed_path.lineTo(pt)

            # Create closed underlay area for gradient fill
            fill_path = QPainterPath(speed_path)
            fill_path.lineTo(speed_points[-1].x(), rect.bottom() - padding_y)
            fill_path.lineTo(speed_points[0].x(), rect.bottom() - padding_y)
            fill_path.closeSubpath()

            grad = QLinearGradient(0, rect.top(), 0, rect.bottom())
            grad.setColorAt(0.0, QColor(0, 122, 255, 90))
            grad.setColorAt(1.0, QColor(0, 122, 255, 5))
            painter.fillPath(fill_path, grad)

            # Stroke speed curve
            painter.setPen(QPen(QColor("#007AFF"), 2.0))
            painter.drawPath(speed_path)

        # 5. Draw Latency Curve (Orange/Amber)
        lat_path = QPainterPath()
        lat_points: List[QPointF] = []
        for s in self._samples:
            if s.latency_ms <= 0.0:
                continue
            x = rect.left() + padding_x + (s.elapsed_s / max_t) * plot_w
            y = (
                rect.bottom()
                - padding_y
                - (min(s.latency_ms, self._max_latency) / self._max_latency) * plot_h
            )
            lat_points.append(QPointF(x, y))

        if lat_points:
            lat_path.moveTo(lat_points[0])
            for pt in lat_points[1:]:
                lat_path.lineTo(pt)
            painter.setPen(QPen(QColor("#FF9500"), 1.8, Qt.PenStyle.SolidLine))
            painter.drawPath(lat_path)

        # 6. Axis Legend Indicator in Top Left
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.setPen(QColor("#007AFF"))
        painter.drawText(
            QRectF(rect.left() + 10, rect.top() + 6, 120, 18),
            Qt.AlignmentFlag.AlignLeft,
            f"Speed: {self._samples[-1].speed_mbps:.1f} Mbps",
        )
        painter.setPen(QColor("#FF9500"))
        painter.drawText(
            QRectF(rect.left() + 140, rect.top() + 6, 120, 18),
            Qt.AlignmentFlag.AlignLeft,
            f"Ping: {self._samples[-1].latency_ms:.1f} ms",
        )

        painter.end()
