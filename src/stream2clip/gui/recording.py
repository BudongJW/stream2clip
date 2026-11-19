"""Recording UI: region border overlay, floating REC bar and the controller (F9)."""

from __future__ import annotations

import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QPainter, QPaintEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from ..ffmpeg import ExportOptions, extension_for
from ..geometry import Region
from ..i18n import tr
from ..record import Recorder, Recording
from . import theme
from .qt import app_icon, virtual_geometry

__all__ = ["RecordSettings", "RecordController", "RecordingFrame", "RecordingBar"]

START_DELAY_MS = 200


def default_video_dir() -> Path:
    for base in (Path.home() / "Videos", Path.home() / "Movies", Path.home()):
        if base.is_dir():
            return base / "stream2clip"
    return Path.cwd()


@dataclass
class RecordSettings:
    format: str = "gif"
    fps: float = 15.0
    width: int | None = None
    transparent: bool = False
    key_color: str = "#00FF00"
    similarity: float = 0.12
    cursor: bool = True
    save_dir: Path = field(default_factory=default_video_dir)

    def export_options(self) -> ExportOptions:
        transparent = self.transparent and self.format != "mp4"
        return ExportOptions(
            format=self.format,
            fps=self.fps,
            width=self.width,
            transparent=transparent,
            key_color=self.key_color,
            similarity=self.similarity,
            blend=0.0 if self.format == "gif" else 0.04 if transparent else 0.0,
        )


class _Strip(QWidget):
    def __init__(self, color: str) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.color = color

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(self.color))
        p.end()


class RecordingFrame:
    """Border made of four opaque strips placed just *outside* the recorded area.

    Using strips instead of one translucent window means nothing ever covers the
    captured pixels, even on X11 without a compositor (where translucent windows
    are painted black) or with capture APIs that include layered windows.
    """

    GAP = 1
    THICKNESS = 3
    MARGIN = GAP + THICKNESS

    def __init__(self, rect: QRect, color: str = theme.LIVE_PINK) -> None:
        g, t = self.GAP, self.THICKNESS
        outer = rect.adjusted(-g - t, -g - t, g + t, g + t)
        geometries = [
            QRect(outer.left(), outer.top(), outer.width(), t),  # top
            QRect(outer.left(), outer.bottom() - t + 1, outer.width(), t),  # bottom
            QRect(outer.left(), outer.top() + t, t, outer.height() - 2 * t),  # left
            QRect(outer.right() - t + 1, outer.top() + t, t, outer.height() - 2 * t),  # right
        ]
        self.strips = [_Strip(color) for _ in geometries]
        for strip, geo in zip(self.strips, geometries):
            strip.setGeometry(geo)

    def show(self) -> None:
        for strip in self.strips:
            strip.show()

    def close(self) -> None:
        for strip in self.strips:
            strip.close()

    def deleteLater(self) -> None:  # noqa: N802 - mirrors QObject API used by the controller
        for strip in self.strips:
            strip.deleteLater()


class RecordingBar(QWidget):
    stopRequested = Signal()
    cancelRequested = Signal()

    def __init__(self, description: str) -> None:
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setWindowIcon(app_icon())
        self.setObjectName("Card")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 6, 8, 6)
        row.setSpacing(8)
        self.dot = QLabel("●")
        self.dot.setStyleSheet(f"color:{theme.LIVE_PINK}; font-size:14px;")
        self.timer_label = QLabel("REC 00:00")
        self.timer_label.setStyleSheet("font-weight:800; font-family:'JetBrains Mono','Consolas',monospace;")
        info = QLabel(description, objectName="Muted")
        stop = QPushButton(tr("정지 (F9)"), objectName="Primary")
        stop.clicked.connect(self.stopRequested)
        cancel = QPushButton(tr("취소"))
        cancel.clicked.connect(self.cancelRequested)
        for widget in (self.dot, self.timer_label, info, stop, cancel):
            row.addWidget(widget)
        self.adjustSize()

    def set_elapsed(self, seconds: float) -> None:
        m, s = divmod(int(seconds), 60)
        self.timer_label.setText(f"REC {m:02d}:{s:02d}")
        self.dot.setVisible(int(seconds * 2) % 2 == 0)

    def place_near(self, rect: QRect) -> None:
        screen = QGuiApplication.screenAt(rect.center()) or QGuiApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else virtual_geometry()
        x = min(max(avail.left(), rect.right() - self.width()), avail.right() - self.width())
        y = rect.bottom() + RecordingFrame.MARGIN + 8
        if y + self.height() > avail.bottom():
            y = rect.top() - RecordingFrame.MARGIN - 8 - self.height()
        if y < avail.top():
            y = rect.bottom() - self.height() - 8  # inside, bottom-right corner
        self.move(QPoint(x, y))


class RecordController(QObject):
    """Owns the select -> record -> encode lifecycle. ``toggle()`` is bound to F9."""

    stateChanged = Signal(str)  # idle | selecting | recording | encoding
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, settings: Callable[[], RecordSettings], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self.state = "idle"
        self._recorder: Recorder | None = None
        self._frame: RecordingFrame | None = None
        self._bar: RecordingBar | None = None
        self._selector = None
        self._active: RecordSettings | None = None
        self._cursor_phys: tuple[int, int] | None = None
        self._mapping: tuple[QRect, Region, float, float] | None = None
        self._ticker = QTimer(self)
        self._ticker.setInterval(33)
        self._ticker.timeout.connect(self._tick)
        self.finished.connect(lambda _: self._set_state("idle"))
        self.failed.connect(lambda _: self._set_state("idle"))

    def _set_state(self, state: str) -> None:
        self.state = state
        self.stateChanged.emit(state)

    # ------------------------------------------------------------------ public
    def toggle(self) -> None:
        if self.state == "idle":
            self.begin_selection()
        elif self.state == "recording":
            self.stop()

    def begin_selection(self, *, delay_ms: int = 250) -> None:
        if self.state != "idle":
            return
        self._set_state("selecting")
        QTimer.singleShot(delay_ms, self._open_selector)

    def _open_selector(self) -> None:
        from .selector import ScreenSelector, grab_virtual_screen

        try:
            screenshot, physical = grab_virtual_screen()
        except Exception as exc:
            self.failed.emit(tr("화면을 캡처할 수 없습니다: {0}").format(exc))
            return
        logical = virtual_geometry()
        self._mapping = (logical, physical, screenshot.width / max(1, logical.width()), screenshot.height / max(1, logical.height()))
        self._selector = ScreenSelector("region", screenshot=screenshot, physical=physical, hint=tr("녹화할 영역을 드래그, Enter 전체 화면, Esc 취소"))
        # Give the compositor / X server time to repaint what was under the overlay,
        # otherwise the first frames show the dimmed selection screen.
        self._selector.regionSelected.connect(lambda region, _img, rect: QTimer.singleShot(START_DELAY_MS, lambda: self.start(region, rect)))
        self._selector.cancelled.connect(lambda: self._set_state("idle"))
        self._selector.show()

    def start(self, region: Region, rect: QRect) -> None:
        settings = self._settings()
        self._active = settings
        if settings.cursor:
            cursor = self._cursor_provider()
        else:
            cursor = None
        # Physical pixels per logical pixel, so the drawn cursor is as big as the real one.
        scale = round(self._mapping[2], 2) if self._mapping is not None else 1.0
        try:
            self._recorder = Recorder(region, fps=settings.fps, cursor=cursor, cursor_scale=scale)
            self._recorder.start()
        except Exception as exc:
            self._recorder = None
            self.failed.emit(tr("녹화를 시작할 수 없습니다: {0}").format(exc))
            return
        self._frame = RecordingFrame(rect)
        self._frame.show()
        desc = f"{settings.format.upper()}, {settings.fps:g}fps" + (tr(", 투명") if settings.transparent and settings.format != "mp4" else "")
        self._bar = RecordingBar(desc)
        self._bar.stopRequested.connect(self.stop)
        self._bar.cancelRequested.connect(self.cancel)
        self._bar.place_near(rect)
        self._bar.show()
        self._ticker.start()
        self._set_state("recording")

    def stop(self) -> None:
        if self._recorder is None:
            return
        recorder, self._recorder = self._recorder, None
        self._teardown()
        self._set_state("encoding")
        settings = self._active or self._settings()

        def work() -> None:
            recording: Recording | None = None
            try:
                recording = recorder.stop()
                settings.save_dir.mkdir(parents=True, exist_ok=True)
                name = time.strftime("stream2clip_%Y%m%d_%H%M%S") + extension_for(settings.format)
                out = recording.export(settings.save_dir / name, settings.export_options())
                self.finished.emit(str(out))
            except Exception as exc:  # surfaced in the UI
                self.failed.emit(tr("녹화 저장 실패: {0}").format(exc))
            finally:
                if recording is not None:
                    recording.discard()

        threading.Thread(target=work, name="stream2clip-encode", daemon=True).start()

    def cancel(self) -> None:
        recorder, self._recorder = self._recorder, None
        self._teardown()
        if recorder is not None:
            try:
                recorder.stop().discard()
            except Exception:
                pass
        self._set_state("idle")

    # ------------------------------------------------------------------ internals
    def _teardown(self) -> None:
        self._ticker.stop()
        for widget in (self._frame, self._bar):
            if widget is not None:
                widget.close()
                widget.deleteLater()
        self._frame = self._bar = None

    def _cursor_provider(self) -> Callable[[], "tuple[int, int] | None"]:
        if sys.platform == "win32":
            from ..capture import system_cursor_position

            return system_cursor_position
        return lambda: self._cursor_phys

    def _tick(self) -> None:
        if self._recorder is not None and self._bar is not None:
            self._bar.set_elapsed(self._recorder.elapsed)
            if self._recorder.error is not None:
                err = self._recorder.error
                self.cancel()
                self.failed.emit(tr("녹화 중 오류: {0}").format(err))
                return
        if self._mapping is not None:
            logical, physical, sx, sy = self._mapping
            pos = QCursor.pos()
            self._cursor_phys = (physical.x + round((pos.x() - logical.x()) * sx), physical.y + round((pos.y() - logical.y()) * sy))
