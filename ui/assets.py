"""Programmatic icon and visual asset generator for FreeNetMeter.

Generates original, high-resolution vector-rendered icons at runtime using QPainter.
Multi-resolution pixmaps (16x16 up to 256x256) are bundled into a single QIcon
to ensure razor-sharp rendering on Windows 10/11 high-DPI displays (100% to 250% scale).

Originality: 100% created from scratch using geometric primitives and math.
No third-party image assets or proprietary icons are embedded or copied.
"""

from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)


def create_app_pixmap(size: int = 64) -> QPixmap:
    """Generate an original high-fidelity application icon pixmap.

    Features:
    - Dark circular glass badge with subtle inner glow.
    - Vibrant emerald green download indicator (downward arrow).
    - Vibrant sky cyan upload indicator (upward arrow).
    - Circular telemetry gauge arc symbolizing network activity.

    Args:
        size: Width and height in pixels.

    Returns:
        QPixmap with transparent background.
    """
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    scale = size / 64.0  # Normalized coordinate scale

    # 1. Dark circular badge background
    bg_rect = QRectF(2.0 * scale, 2.0 * scale, 60.0 * scale, 60.0 * scale)
    bg_gradient = QLinearGradient(
        bg_rect.topLeft(),
        bg_rect.bottomRight(),
    )
    bg_gradient.setColorAt(0.0, QColor(32, 34, 40))
    bg_gradient.setColorAt(1.0, QColor(18, 20, 24))

    painter.setPen(QPen(QColor(60, 64, 75), 1.5 * scale))
    painter.setBrush(QBrush(bg_gradient))
    painter.drawEllipse(bg_rect)

    # 2. Outer speed arc accent (gauge ring)
    arc_rect = QRectF(6.0 * scale, 6.0 * scale, 52.0 * scale, 52.0 * scale)
    arc_pen = QPen(QColor(0, 230, 118, 180), 2.0 * scale)
    arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(arc_pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawArc(arc_rect, 135 * 16, -180 * 16)  # Left/bottom arc

    arc_pen_up = QPen(QColor(41, 182, 246, 180), 2.0 * scale)
    arc_pen_up.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(arc_pen_up)
    painter.drawArc(arc_rect, -45 * 16, -180 * 16)  # Right/top arc

    # 3. Emerald Download Arrow (Left side, pointing down)
    down_path = QPainterPath()
    # Center arrow shaft
    cx_down = 23.0 * scale
    down_path.moveTo(cx_down, 18.0 * scale)
    down_path.lineTo(cx_down, 38.0 * scale)
    # Arrowhead
    down_path.lineTo(cx_down - 6.0 * scale, 32.0 * scale)
    down_path.moveTo(cx_down, 38.0 * scale)
    down_path.lineTo(cx_down + 6.0 * scale, 32.0 * scale)

    pen_down = QPen(QColor(0, 230, 118), 3.2 * scale)
    pen_down.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen_down.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen_down)
    painter.drawPath(down_path)

    # 4. Cyan Upload Arrow (Right side, pointing up)
    up_path = QPainterPath()
    cx_up = 41.0 * scale
    up_path.moveTo(cx_up, 46.0 * scale)
    up_path.lineTo(cx_up, 26.0 * scale)
    # Arrowhead
    up_path.lineTo(cx_up - 6.0 * scale, 32.0 * scale)
    up_path.moveTo(cx_up, 26.0 * scale)
    up_path.lineTo(cx_up + 6.0 * scale, 32.0 * scale)

    pen_up = QPen(QColor(41, 182, 246), 3.2 * scale)
    pen_up.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen_up.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen_up)
    painter.drawPath(up_path)

    painter.end()
    return pixmap


def create_app_icon() -> QIcon:
    """Generate a multi-resolution QIcon containing standard Windows mipmap sizes.

    Includes 16x16 (tray), 24x24, 32x32 (taskbar), 48x48, 64x64, 128x128, 256x256.

    Returns:
        QIcon containing all rendered resolutions.
    """
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(create_app_pixmap(size))
    return icon
