"""Small vector icon set drawn with QPainter (theme aware, no assets needed)."""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)


def _pt(size: float, x: float, y: float) -> QPointF:
    return QPointF(x * size, y * size)


def _draw_undo(p: QPainter, size: float, mirrored: bool = False) -> None:
    p.save()
    if mirrored:
        p.translate(size, 0)
        p.scale(-1, 1)
    path = QPainterPath(_pt(size, 0.31, 0.72))
    path.cubicTo(_pt(size, 0.12, 0.45), _pt(size, 0.35, 0.20), _pt(size, 0.67, 0.28))
    path.cubicTo(_pt(size, 0.82, 0.32), _pt(size, 0.87, 0.47), _pt(size, 0.85, 0.61))
    p.drawPath(path)
    p.drawLine(_pt(size, 0.31, 0.72), _pt(size, 0.31, 0.53))
    p.drawLine(_pt(size, 0.31, 0.72), _pt(size, 0.50, 0.72))
    p.restore()


def _draw_moon(p: QPainter, size: float, color: QColor) -> None:
    outer = QPainterPath()
    outer.addEllipse(QRectF(size * 0.22, size * 0.18, size * 0.56, size * 0.56))
    inner = QPainterPath()
    inner.addEllipse(QRectF(size * 0.36, size * 0.10, size * 0.56, size * 0.56))
    crescent = outer.subtracted(inner)
    p.save()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    p.drawPath(crescent)
    p.restore()


def _create_pixmap(kind: str, color: str, size: int = 64) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    c = QColor(color)
    width = max(1.8, size * 0.062)
    pen = QPen(
        c,
        width,
        Qt.PenStyle.SolidLine,
        Qt.PenCapStyle.RoundCap,
        Qt.PenJoinStyle.RoundJoin,
    )
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    s = float(size)

    if kind == "new":
        path = QPainterPath(_pt(s, 0.26, 0.13))
        path.lineTo(_pt(s, 0.60, 0.13))
        path.lineTo(_pt(s, 0.77, 0.30))
        path.lineTo(_pt(s, 0.77, 0.88))
        path.lineTo(_pt(s, 0.26, 0.88))
        path.closeSubpath()
        p.drawPath(path)
        p.drawLine(_pt(s, 0.60, 0.13), _pt(s, 0.60, 0.30))
        p.drawLine(_pt(s, 0.60, 0.30), _pt(s, 0.77, 0.30))
        p.drawLine(_pt(s, 0.51, 0.48), _pt(s, 0.51, 0.70))
        p.drawLine(_pt(s, 0.40, 0.59), _pt(s, 0.62, 0.59))

    elif kind == "open":
        path = QPainterPath(_pt(s, 0.12, 0.29))
        path.lineTo(_pt(s, 0.40, 0.29))
        path.lineTo(_pt(s, 0.48, 0.40))
        path.lineTo(_pt(s, 0.88, 0.40))
        path.lineTo(_pt(s, 0.88, 0.79))
        path.lineTo(_pt(s, 0.12, 0.79))
        path.closeSubpath()
        p.drawPath(path)
        p.drawLine(_pt(s, 0.12, 0.47), _pt(s, 0.88, 0.47))

    elif kind == "save":
        p.drawRoundedRect(QRectF(s * 0.18, s * 0.18, s * 0.64, s * 0.64), s * 0.07, s * 0.07)
        p.drawRect(QRectF(s * 0.33, s * 0.18, s * 0.33, s * 0.24))
        p.drawRoundedRect(QRectF(s * 0.30, s * 0.56, s * 0.40, s * 0.26), s * 0.04, s * 0.04)

    elif kind == "undo":
        _draw_undo(p, s, mirrored=False)

    elif kind == "redo":
        _draw_undo(p, s, mirrored=True)

    elif kind == "find":
        p.drawEllipse(QRectF(s * 0.18, s * 0.16, s * 0.42, s * 0.42))
        p.drawLine(_pt(s, 0.57, 0.55), _pt(s, 0.83, 0.82))

    elif kind == "eye":
        path = QPainterPath(_pt(s, 0.10, 0.50))
        path.cubicTo(_pt(s, 0.29, 0.22), _pt(s, 0.71, 0.22), _pt(s, 0.90, 0.50))
        path.cubicTo(_pt(s, 0.71, 0.78), _pt(s, 0.29, 0.78), _pt(s, 0.10, 0.50))
        p.drawPath(path)
        p.save()
        p.setBrush(c)
        p.drawEllipse(QRectF(s * 0.40, s * 0.40, s * 0.20, s * 0.20))
        p.restore()

    elif kind == "outline":
        for y, length in ((0.26, 0.52), (0.50, 0.62), (0.74, 0.44)):
            p.save()
            p.setBrush(c)
            p.drawEllipse(QRectF(s * 0.16, s * (y - 0.035), s * 0.07, s * 0.07))
            p.restore()
            p.drawLine(_pt(s, 0.32, y), _pt(s, 0.32 + length, y))

    elif kind == "moon":
        _draw_moon(p, s, c)

    elif kind == "sun":
        p.drawEllipse(QRectF(s * 0.32, s * 0.32, s * 0.36, s * 0.36))
        for i in range(8):
            p.save()
            p.translate(s * 0.5, s * 0.5)
            p.rotate(i * 45)
            p.drawLine(QPointF(0, -s * 0.28), QPointF(0, -s * 0.38))
            p.restore()

    elif kind == "link":
        p.save()
        p.translate(s * 0.5, s * 0.5)
        p.rotate(-45)
        p.drawRoundedRect(QRectF(-s * 0.34, -s * 0.09, s * 0.34, s * 0.18), s * 0.09, s * 0.09)
        p.drawRoundedRect(QRectF(0.0, -s * 0.09, s * 0.34, s * 0.18), s * 0.09, s * 0.09)
        p.restore()

    elif kind == "book":
        p.drawLine(_pt(s, 0.50, 0.26), _pt(s, 0.50, 0.78))
        path = QPainterPath(_pt(s, 0.50, 0.27))
        path.cubicTo(_pt(s, 0.36, 0.18), _pt(s, 0.20, 0.20), _pt(s, 0.12, 0.27))
        path.lineTo(_pt(s, 0.12, 0.76))
        path.cubicTo(_pt(s, 0.24, 0.70), _pt(s, 0.38, 0.72), _pt(s, 0.50, 0.80))
        path.cubicTo(_pt(s, 0.62, 0.72), _pt(s, 0.76, 0.70), _pt(s, 0.88, 0.76))
        path.lineTo(_pt(s, 0.88, 0.27))
        path.cubicTo(_pt(s, 0.80, 0.20), _pt(s, 0.64, 0.18), _pt(s, 0.50, 0.27))
        p.drawPath(path)

    elif kind == "export":
        p.drawLine(_pt(s, 0.50, 0.66), _pt(s, 0.50, 0.18))
        p.drawLine(_pt(s, 0.34, 0.35), _pt(s, 0.50, 0.18))
        p.drawLine(_pt(s, 0.66, 0.35), _pt(s, 0.50, 0.18))
        path = QPainterPath(_pt(s, 0.20, 0.48))
        path.lineTo(_pt(s, 0.20, 0.84))
        path.lineTo(_pt(s, 0.80, 0.84))
        path.lineTo(_pt(s, 0.80, 0.48))
        p.drawPath(path)

    elif kind == "close":
        p.drawLine(_pt(s, 0.28, 0.28), _pt(s, 0.72, 0.72))
        p.drawLine(_pt(s, 0.72, 0.28), _pt(s, 0.28, 0.72))

    elif kind in ("bold", "italic", "strike", "code"):
        p.save()
        p.setPen(c)
        if kind == "bold":
            font = QFont("Segoe UI")
            font.setPixelSize(int(size * 0.62))
            font.setBold(True)
            p.setFont(font)
            p.drawText(QRectF(0, 0, s, s), Qt.AlignmentFlag.AlignCenter, "B")
        elif kind == "italic":
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(c)
            top = QPainterPath()
            top.addRoundedRect(QRectF(s * 0.29, s * 0.27, s * 0.38, s * 0.065), s * 0.02, s * 0.02)
            bottom = QPainterPath()
            bottom.addRoundedRect(QRectF(s * 0.33, s * 0.665, s * 0.38, s * 0.065), s * 0.02, s * 0.02)
            stem = QPainterPath()
            stem.moveTo(_pt(s, 0.53, 0.31))
            stem.lineTo(_pt(s, 0.62, 0.31))
            stem.lineTo(_pt(s, 0.48, 0.69))
            stem.lineTo(_pt(s, 0.39, 0.69))
            stem.closeSubpath()
            p.drawPath(top)
            p.drawPath(bottom)
            p.drawPath(stem)
        elif kind == "strike":
            font = QFont("Segoe UI")
            font.setPixelSize(int(size * 0.60))
            font.setBold(True)
            p.setFont(font)
            p.drawText(QRectF(0, 0, s, s), Qt.AlignmentFlag.AlignCenter, "S")
            p.setPen(QPen(c, max(2.4, size * 0.075), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(_pt(s, 0.23, 0.54), _pt(s, 0.77, 0.54))
        else:
            p.setPen(
                QPen(
                    c,
                    max(2.6, size * 0.085),
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                    Qt.PenJoinStyle.RoundJoin,
                )
            )
            p.drawLine(_pt(s, 0.43, 0.29), _pt(s, 0.24, 0.50))
            p.drawLine(_pt(s, 0.24, 0.50), _pt(s, 0.43, 0.71))
            p.drawLine(_pt(s, 0.57, 0.29), _pt(s, 0.76, 0.50))
            p.drawLine(_pt(s, 0.76, 0.50), _pt(s, 0.57, 0.71))
        p.restore()

    p.end()
    return pm


@lru_cache(maxsize=128)
def icon(kind: str, color: str, size: int = 64) -> QIcon:
    return QIcon(_create_pixmap(kind, color, size))


def app_icon(size: int = 256) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    rect = QRectF(size * 0.06, size * 0.06, size * 0.88, size * 0.88)
    path = QPainterPath()
    path.addRoundedRect(rect, size * 0.20, size * 0.20)
    gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
    gradient.setColorAt(0.0, QColor("#3b8cff"))
    gradient.setColorAt(1.0, QColor("#0757b8"))
    p.fillPath(path, gradient)

    p.setPen(QColor("#ffffff"))
    font = QFont("Segoe UI")
    font.setPixelSize(int(size * 0.46))
    font.setBold(True)
    p.setFont(font)
    p.drawText(QRectF(0, size * 0.13, size, size * 0.58), Qt.AlignmentFlag.AlignCenter, "M")

    p.setPen(QPen(QColor(255, 255, 255, 230), size * 0.045, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawLine(QPointF(size * 0.28, size * 0.70), QPointF(size * 0.72, size * 0.70))
    p.setPen(QPen(QColor(255, 255, 255, 230), size * 0.035, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawLine(QPointF(size * 0.62, size * 0.79), QPointF(size * 0.68, size * 0.86))
    p.drawLine(QPointF(size * 0.74, size * 0.72), QPointF(size * 0.68, size * 0.86))
    p.end()
    return QIcon(pm)
