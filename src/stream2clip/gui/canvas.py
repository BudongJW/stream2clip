"""Interactive canvas for the editor: draws the rendered document and live previews."""

from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QImage, QKeyEvent, QMouseEvent, QPainter, QPainterPath, QPaintEvent, QPen, QPolygonF, QWheelEvent
from PySide6.QtWidgets import QWidget

from ..color import DEFAULT_COLOR, parse_color, to_hex
from ..editor import Arrow, ColorKey, Document, Highlighter, Mosaic, Pen, Rectangle, Transparent, shape_bounds, translate_shape
from ..geometry import Region
from . import theme
from .qt import pil_to_qimage

__all__ = ["TOOLS", "ToolState", "EditorCanvas"]

#: (id, label, shortcut, hint)
TOOLS: list[tuple[str, str, str, str]] = [
    ("select", "선택", "V", "클릭해서 선택 · 드래그로 이동 · Delete로 삭제"),
    ("pen", "펜", "P", "드래그해서 자유롭게 그리기"),
    ("highlighter", "형광펜", "H", "드래그해서 반투명하게 강조"),
    ("rect", "네모", "R", "드래그해서 사각형 그리기"),
    ("arrow", "화살표", "A", "시작점에서 끝점으로 드래그"),
    ("text", "글자", "T", "클릭한 위치에 글자 넣기 (크기 = 굵기 × 3 + 12)"),
    ("mosaic", "모자이크", "M", "드래그한 영역을 모자이크 (블록 = 굵기 × 2)"),
    ("transparent", "투명", "E", "드래그 = 영역 지우기 · 클릭 = 그 색을 투명하게"),
    ("crop", "자르기", "C", "남길 영역을 드래그 · 다시 드래그하면 변경"),
]


@dataclass
class ToolState:
    tool: str = "pen"
    color: str = DEFAULT_COLOR
    width: int = 6
    picking: bool = False

    @property
    def text_size(self) -> float:
        return 12 + self.width * 3


def _qcolor(color: str, alpha: float = 1.0) -> QColor:
    r, g, b, a = parse_color(color)
    return QColor(r, g, b, round(a * alpha))


class EditorCanvas(QWidget):
    changed = Signal()
    colorPicked = Signal(str)
    textRequested = Signal(float, float)
    zoomChanged = Signal(float)

    def __init__(self, document: Document, tools: ToolState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.doc = document
        self.tools = tools
        self.zoom = 1.0
        self.selected: int | None = None
        self._press: QPointF | None = None
        self._now: QPointF | None = None
        self._points: list[tuple[float, float]] = []
        self._checker = self._make_checker()
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.refresh()

    # ------------------------------------------------------------------ state
    def refresh(self) -> None:
        self._pil = self.doc.render(apply_crop=False)
        self._image: QImage = pil_to_qimage(self._pil)
        if self.selected is not None and self.selected >= len(self.doc.state.items):
            self.selected = None
        self.updateGeometry()
        self.resize(self.sizeHint())
        self.update()

    def set_zoom(self, zoom: float) -> None:
        self.zoom = max(0.1, min(8.0, zoom))
        self.updateGeometry()
        self.resize(self.sizeHint())
        self.update()
        self.zoomChanged.emit(self.zoom)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(max(1, round(self._image.width() * self.zoom)), max(1, round(self._image.height() * self.zoom)))

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return self.sizeHint()

    def _img(self, pos: QPointF) -> tuple[float, float]:
        return (pos.x() / self.zoom, pos.y() / self.zoom)

    def _w(self, x: float, y: float) -> QPointF:
        return QPointF(x * self.zoom, y * self.zoom)

    def _drag_region(self) -> Region | None:
        if self._press is None or self._now is None:
            return None
        (x0, y0), (x1, y1) = self._img(self._press), self._img(self._now)
        region = Region.from_points(x0, y0, x1, y1).clamp(*self.doc.size)
        return region

    def pixel_color(self, x: float, y: float) -> str:
        xi = min(self._pil.width - 1, max(0, int(x)))
        yi = min(self._pil.height - 1, max(0, int(y)))
        return to_hex(self._pil.getpixel((xi, yi)))

    def delete_selected(self) -> None:
        if self.selected is not None:
            self.doc.remove(self.selected)
            self.selected = None
            self.refresh()
            self.changed.emit()

    # ------------------------------------------------------------------ mouse
    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position()
        x, y = self._img(pos)
        if self.tools.picking:
            self.colorPicked.emit(self.pixel_color(x, y))
            return
        tool = self.tools.tool
        if tool == "text":
            self.textRequested.emit(x, y)
            return
        if tool == "select":
            self.selected = self.doc.hit_test(x, y)
            if self.selected is None:
                self.update()
                return
        self._press = pos
        self._now = pos
        self._points = [(x, y)]
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._press is None:
            return
        self._now = event.position()
        if self.tools.tool in ("pen", "highlighter"):
            x, y = self._img(self._now)
            lx, ly = self._points[-1]
            if math.hypot(x - lx, y - ly) * self.zoom >= 1.5:
                self._points.append((x, y))
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton or self._press is None:
            return
        self._now = event.position()
        shape = None
        t = self.tools
        tool = t.tool
        region = self._drag_region()
        (x0, y0), (x1, y1) = self._img(self._press), self._img(self._now)
        clicked = math.hypot(x1 - x0, y1 - y0) * self.zoom < 3
        committed = False

        if tool == "pen":
            shape = Pen(tuple(self._points), color=t.color, width=t.width)
        elif tool == "highlighter":
            shape = Highlighter(tuple(self._points), color=t.color, width=t.width * 3)
        elif tool == "rect" and region is not None and not clicked:
            shape = Rectangle(region, color=t.color, width=t.width)
        elif tool == "arrow" and not clicked:
            shape = Arrow((x0, y0), (x1, y1), color=t.color, width=t.width)
        elif tool == "mosaic" and region is not None and not clicked:
            shape = Mosaic(region, block=max(4, t.width * 2))
        elif tool == "transparent":
            if clicked:
                shape = ColorKey(self.pixel_color(x0, y0), similarity=0.1)
            elif region is not None:
                shape = Transparent(region)
        elif tool == "crop" and region is not None and not clicked:
            self.doc.set_crop(region)
            committed = True
        elif tool == "select" and self.selected is not None and not clicked:
            self.doc.move(self.selected, x1 - x0, y1 - y0)
            committed = True

        if shape is not None:
            self.doc.add(shape)
            committed = True
        self._press = self._now = None
        self._points = []
        if committed:
            self.refresh()
            self.changed.emit()
        else:
            self.update()

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.set_zoom(self.zoom * factor)
            event.accept()
        else:
            super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_selected()
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------ painting
    @staticmethod
    def _make_checker() -> QBrush:
        tile = QImage(16, 16, QImage.Format.Format_RGB32)
        tile.fill(QColor("#2B2738"))
        p = QPainter(tile)
        p.fillRect(0, 0, 8, 8, QColor("#363147"))
        p.fillRect(8, 8, 8, 8, QColor("#363147"))
        p.end()
        return QBrush(tile)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        p = QPainter(self)
        target = QRectF(0, 0, self._image.width() * self.zoom, self._image.height() * self.zoom)
        p.fillRect(target, self._checker)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, self.zoom < 1)
        p.drawImage(target, self._image)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        crop = self.doc.state.crop
        if crop is not None and not (self._press is not None and self.tools.tool == "crop"):
            self._dim_outside(p, target, QRectF(self._w(crop.x, crop.y), self._w(crop.right, crop.bottom)))

        if self.selected is not None and self.selected < len(self.doc.state.items):
            shape = self.doc.state.items[self.selected]
            if self._press is not None and self._now is not None and self.tools.tool == "select":
                (x0, y0), (x1, y1) = self._img(self._press), self._img(self._now)
                shape = translate_shape(shape, x1 - x0, y1 - y0)
            bounds = shape_bounds(shape, self.doc.font_path)
            if bounds is not None:
                p.setPen(QPen(QColor(theme.LIVE_PINK), 1.5, Qt.PenStyle.DashLine))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRect(QRectF(self._w(bounds.x, bounds.y), self._w(bounds.right, bounds.bottom)))

        if self._press is not None and self._now is not None:
            self._paint_preview(p, target)
        p.end()

    def _dim_outside(self, p: QPainter, full: QRectF, keep: QRectF) -> None:
        path = QPainterPath()
        path.addRect(full)
        inner = QPainterPath()
        inner.addRect(keep)
        p.fillPath(path.subtracted(inner), QColor(10, 8, 18, 160))
        p.setPen(QPen(QColor(theme.HIGHLIGHT), 1.5, Qt.PenStyle.DashLine))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(keep)

    def _paint_preview(self, p: QPainter, full: QRectF) -> None:
        t = self.tools
        tool = t.tool
        a, b = self._press, self._now
        rect = QRectF(a, b).normalized()
        width = max(1.0, t.width * self.zoom)
        if tool in ("pen", "highlighter"):
            pts = [self._w(x, y) for x, y in self._points]
            color = _qcolor(t.color, 0.4 if tool == "highlighter" else 1.0)
            pen = QPen(color, width * (3 if tool == "highlighter" else 1), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            if len(pts) == 1:
                p.drawPoint(pts[0])
            else:
                p.drawPolyline(QPolygonF(pts))
        elif tool == "rect":
            p.setPen(QPen(_qcolor(t.color), width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap, Qt.PenJoinStyle.MiterJoin))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(rect.adjusted(width / 2, width / 2, -width / 2, -width / 2))
        elif tool == "arrow":
            dx, dy = b.x() - a.x(), b.y() - a.y()
            length = math.hypot(dx, dy)
            if length > 1:
                ux, uy = dx / length, dy / length
                head = min(max(t.width * 3.5, 14) * self.zoom, length)
                hw = head * 0.85 / 2
                base = QPointF(b.x() - ux * head, b.y() - uy * head)
                p.setPen(QPen(_qcolor(t.color), width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawLine(a, QPointF(b.x() - ux * head * 0.7, b.y() - uy * head * 0.7))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(_qcolor(t.color))
                p.drawPolygon(QPolygonF([b, QPointF(base.x() - uy * hw, base.y() + ux * hw), QPointF(base.x() + uy * hw, base.y() - ux * hw)]))
        elif tool in ("mosaic", "transparent"):
            fill = QColor(255, 255, 255, 60) if tool == "mosaic" else QColor(0, 0, 0, 120)
            p.setPen(QPen(QColor(theme.PAPER), 1.5, Qt.PenStyle.DashLine))
            p.setBrush(fill)
            p.drawRect(rect)
        elif tool == "crop":
            self._dim_outside(p, full, rect)
            region = self._drag_region()
            if region is not None:
                p.setPen(QColor(theme.HIGHLIGHT))
                p.drawText(QRect(int(rect.left()), int(rect.top()) - 20, 200, 18), Qt.AlignmentFlag.AlignLeft, f"{region.width} × {region.height}")
