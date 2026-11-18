"""Full-screen overlay to pick a region (영역 캡쳐 / 녹화 영역) or a color (스포이드).

The desktop is frozen into a screenshot first, so the captured image is exactly
what the user saw while dragging.
"""

from __future__ import annotations

from PIL import Image
from PySide6.QtCore import QPoint, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QKeyEvent, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from ..capture import CaptureBackend
from ..color import to_hex
from ..frames import to_image
from ..geometry import Region
from . import theme
from .qt import pil_to_qimage, virtual_geometry

__all__ = ["ScreenSelector", "grab_virtual_screen"]


def grab_virtual_screen(backend: CaptureBackend | None = None) -> tuple[Image.Image, Region]:
    from ..capture.mss_backend import MssBackend

    owned = backend is None
    backend = backend or MssBackend()
    try:
        phys = backend.virtual_screen()
        return to_image(backend.grab(phys)), phys
    finally:
        if owned:
            backend.close()


class ScreenSelector(QWidget):
    #: (physical Region, cropped PIL image, logical QRect in global coordinates)
    regionSelected = Signal(object, object, QRect)
    colorPicked = Signal(str)
    cancelled = Signal()

    def __init__(self, mode: str = "region", *, screenshot: Image.Image | None = None, physical: Region | None = None, hint: str | None = None) -> None:
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        if mode not in ("region", "color"):
            raise ValueError(mode)
        self.mode = mode
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        if screenshot is None or physical is None:
            screenshot, physical = grab_virtual_screen()
        self._image = screenshot.convert("RGBA")
        self._physical = physical
        self._qimage = pil_to_qimage(self._image)
        self._logical = virtual_geometry()
        self.setGeometry(self._logical)
        self._sx = self._image.width / max(1, self._logical.width())
        self._sy = self._image.height / max(1, self._logical.height())
        self._start: QPoint | None = None
        self._current = QPoint(-1, -1)
        self._hint = hint or (
            "드래그해서 영역 선택  ·  Enter 전체 화면  ·  Esc 취소" if mode == "region" else "투명하게 만들 색을 클릭  ·  Esc 취소"
        )

    # ------------------------------------------------------------------ geometry
    def _selection(self) -> QRect | None:
        if self._start is None:
            return None
        return QRect(self._start, self._current).normalized()

    def _to_physical(self, rect: QRect) -> Region:
        local = Region.from_points(rect.left() * self._sx, rect.top() * self._sy, (rect.right() + 1) * self._sx, (rect.bottom() + 1) * self._sy)
        local = local.clamp(self._image.width, self._image.height) or Region(0, 0, 1, 1)
        return local

    def _pixel_hex(self, pos: QPoint) -> str:
        x = min(self._image.width - 1, max(0, int(pos.x() * self._sx)))
        y = min(self._image.height - 1, max(0, int(pos.y() * self._sy)))
        return to_hex(self._image.getpixel((x, y)))

    def _emit_region(self, rect: QRect) -> None:
        local = self._to_physical(rect)
        crop = self._image.crop(local.as_box())
        absolute = local.translate(self._physical.x, self._physical.y)
        self.hide()  # get off the screen before anyone starts grabbing it
        self.regionSelected.emit(absolute, crop, rect.translated(self._logical.topLeft()))
        self.close()

    # ------------------------------------------------------------------ events
    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.raise_()
        self.activateWindow()
        self.setFocus()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            self.close()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.mode == "region":
            self._emit_region(QRect(0, 0, self.width(), self.height()))

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.RightButton:
            self.cancelled.emit()
            self.close()
            return
        pos = event.position().toPoint()
        if self.mode == "color":
            self.colorPicked.emit(self._pixel_hex(pos))
            self.close()
            return
        self._start = pos
        self._current = pos
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._current = event.position().toPoint()
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self.mode != "region" or self._start is None:
            return
        self._current = event.position().toPoint()
        rect = self._selection()
        self._start = None
        if rect is None or rect.width() < 4 or rect.height() < 4:
            self.update()
            return
        self._emit_region(rect)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.drawImage(self.rect(), self._qimage)
        dim = QColor(10, 8, 18, 150)
        sel = self._selection()
        if sel is None:
            p.fillRect(self.rect(), dim)
        else:
            full = self.rect()
            p.fillRect(QRect(full.left(), full.top(), full.width(), sel.top() - full.top()), dim)
            p.fillRect(QRect(full.left(), sel.bottom() + 1, full.width(), full.bottom() - sel.bottom()), dim)
            p.fillRect(QRect(full.left(), sel.top(), sel.left() - full.left(), sel.height()), dim)
            p.fillRect(QRect(sel.right() + 1, sel.top(), full.right() - sel.right(), sel.height()), dim)
            p.setPen(QPen(QColor(theme.LIVE_PINK), 2))
            p.drawRect(sel.adjusted(-1, -1, 0, 0))
            phys = self._to_physical(sel)
            self._label(p, f"{phys.width} × {phys.height}", QPoint(sel.left(), max(0, sel.top() - 30)))

        if self.mode == "color" and self.rect().contains(self._current):
            self._magnifier(p, self._current)
        elif sel is None and self.rect().contains(self._current):
            p.setPen(QPen(QColor(255, 255, 255, 90), 1, Qt.PenStyle.DashLine))
            p.drawLine(0, self._current.y(), self.width(), self._current.y())
            p.drawLine(self._current.x(), 0, self._current.x(), self.height())

        screen = QGuiApplication.screenAt(self.mapToGlobal(self._current)) or QGuiApplication.primaryScreen()
        top = screen.geometry().translated(-self._logical.topLeft()) if screen else self.rect()
        self._label(p, self._hint, QPoint(top.center().x(), top.top() + 28), center=True)
        p.end()

    def _label(self, p: QPainter, text: str, at: QPoint, *, center: bool = False) -> None:
        font = QFont(self.font())
        font.setPointSize(10)
        font.setBold(True)
        p.setFont(font)
        metrics = p.fontMetrics()
        w, h = metrics.horizontalAdvance(text) + 20, metrics.height() + 10
        x = at.x() - w // 2 if center else at.x()
        box = QRectF(x, at.y(), w, h)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.INK))
        p.drawRoundedRect(box, 8, 8)
        p.setPen(QColor(theme.PAPER))
        p.drawText(box, Qt.AlignmentFlag.AlignCenter, text)

    def _magnifier(self, p: QPainter, pos: QPoint) -> None:
        zoom, cells = 10, 11
        size = zoom * cells
        sx, sy = int(pos.x() * self._sx), int(pos.y() * self._sy)
        half = cells // 2
        patch = self._image.crop((sx - half, sy - half, sx + half + 1, sy + half + 1)).resize((size, size), Image.Resampling.NEAREST)
        x = pos.x() + 20 if pos.x() + 20 + size < self.width() else pos.x() - 20 - size
        y = pos.y() + 20 if pos.y() + 20 + size + 34 < self.height() else pos.y() - 20 - size - 34
        p.drawImage(QRect(x, y, size, size), pil_to_qimage(patch))
        p.setPen(QPen(QColor(theme.LIVE_PINK), 2))
        p.drawRect(QRect(x, y, size, size))
        p.drawRect(QRect(x + half * zoom, y + half * zoom, zoom, zoom))
        hex_color = self._pixel_hex(pos)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(hex_color))
        p.drawRoundedRect(QRectF(x, y + size + 6, 24, 24), 6, 6)
        self._label(p, hex_color, QPoint(x + 30, y + size + 4))
