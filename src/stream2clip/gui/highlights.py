"""Highlights window: 방송 → 클립.

Pick a VOD and its chat replay (or paste the stream's address), find the highlights, fine-tune each span by dragging
it on the timeline, look at a still preview with the chosen layout and export the
checked ones. All the work is done by the core (``pipeline.find_highlights`` /
``pipeline.make_clips``); this module only draws and collects settings.
"""

from __future__ import annotations

import threading
from dataclasses import replace
from pathlib import Path

import numpy as np
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QCloseEvent, QColor, QFont, QIcon, QMouseEvent, QPainter, QPaintEvent, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..ffmpeg import ExportOptions
from ..geometry import Region
from ..highlights import Highlight, HighlightConfig, HighlightResult
from ..i18n import tr
from ..layouts import AVATAR_LAYOUTS, LAYOUTS, VerticalLayout
from . import theme
from .qt import app_icon, mascot, pil_to_qimage
from .settings import load_section, save_section

__all__ = ["HighlightsWindow", "TimelineWidget", "default_clip_dir", "mood_for"]

_LAYOUT_LABELS = {"blur": tr("blur: 블러 배경"), "center": tr("center: 가운데 채우기"), "fit": tr("fit: 전체 보이기"), "stack": tr("stack: 아바타 위 / 게임 아래"), "pip": tr("pip: 게임 화면에 아바타 삽입"), "none": tr("원본 화면 그대로")}
_STAGES = {
    "chat": tr("채팅 읽는 중"), "audio": tr("음량 분석 중 (영상 길이에 따라 수십 초)"), "laughter": tr("웃음소리 찾는 중"),
    "singing": tr("노래 구간 찾는 중"), "detect": tr("하이라이트 찾는 중"), "avatar": tr("아바타 찾는 중"),
    "fetch-info": tr("방송 정보 받는 중"), "fetch-chat": tr("채팅 다시보기 받는 중 (긴 방송은 몇 분 걸립니다)"),
}
_SUBTITLE_STYLES = [("default", tr("기본")), ("box", tr("상자")), ("pink", tr("분홍 강조")), ("small", tr("작게"))]
_SUBTITLE_POSITIONS = [("bottom", tr("아래쪽")), ("middle", tr("가운데")), ("top", tr("위쪽"))]
_SINGING = [("off", tr("노래 구간 안 봄")), ("mark", tr("노래 구간 표시")), ("skip", tr("노래 구간 제외"))]
#: Which moment of the session is second 0 of the video (see stream2clip.session.Session.origin).
_SESSION_ORIGINS = [("auto", tr("자동")), ("stream", tr("OBS 송출 시작")), ("record", tr("OBS 녹화 시작")), ("session", tr("세션 시작"))]
_PICK_FILE = "\x00file"  # the "choose a .py file" entry of the translator list
_AGENCIES = ["", "hololive", "nijisanji", "vspo", "aogiri", "generic"]


def default_clip_dir() -> Path:
    for base in (Path.home() / "Videos", Path.home() / "Movies", Path.home()):
        if base.is_dir():
            return base / "stream2clip" / "clips"
    return Path.cwd() / "clips"


def mood_for(highlight: Highlight) -> str | None:
    """Which face of the mascot fits a highlight: the reaction the chat showed most."""
    counts = {name: highlight.stats.get(f"react_{name}", 0) for name in ("laugh", "shock", "cute", "hype")}
    best = max(counts, key=lambda name: counts[name])
    if counts[best] <= 0:
        return None
    return {"laugh": "laugh", "shock": "surprised", "cute": "wink", "hype": "cut"}[best]


def _clock(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    return f"{seconds // 3600:d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


class TimelineWidget(QWidget):
    """Excitement bars with one draggable bracket per highlight.

    Drag the middle of a bracket to move it, an edge to change where the clip starts
    or ends. On a long stream a clip is only a few pixels wide, so the view can be
    zoomed: mouse wheel, or double-click a bracket (double-click elsewhere to see the
    whole stream again). ``selected`` is emitted with the highlight index (or -1),
    ``changed`` after every drag step.
    """

    selected = Signal(int)
    changed = Signal(int)
    EDGE = 6  # px around an edge that grabs it
    PAD_X, TOP, BOTTOM = 14, 30, 24

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(150)
        self.setMouseTracking(True)
        self.result: HighlightResult | None = None
        self.highlights: list[Highlight] = []
        self.current = -1
        self.min_length = 5.0
        self.view: tuple[float, float] = (0.0, 1.0)  # visible time range
        self._drag: tuple[int, str, float, float, float] | None = None  # index, part, grab time, start, end

    # ------------------------------------------------------------------ data
    def set_result(self, result: HighlightResult | None) -> None:
        self.result = result
        self.highlights = list(result.highlights) if result else []
        self.current = 0 if self.highlights else -1
        self._drag = None
        self.view = (0.0, self.duration)
        self.update()

    def select(self, index: int) -> None:
        index = index if 0 <= index < len(self.highlights) else -1
        if index != self.current:
            self.current = index
            self.update()
            self.selected.emit(index)

    @property
    def duration(self) -> float:
        return max(self.result.duration, 1e-6) if self.result else 1.0

    # ------------------------------------------------------------------ geometry
    def _plot(self) -> QRectF:
        return QRectF(self.PAD_X, self.TOP, max(1.0, self.width() - 2 * self.PAD_X), max(1.0, self.height() - self.TOP - self.BOTTOM))

    def time_to_x(self, t: float) -> float:
        plot = self._plot()
        v0, v1 = self.view
        return plot.left() + plot.width() * min(1.0, max(0.0, (t - v0) / max(v1 - v0, 1e-6)))

    def x_to_time(self, x: float) -> float:
        plot = self._plot()
        v0, v1 = self.view
        return v0 + (v1 - v0) * min(1.0, max(0.0, (x - plot.left()) / plot.width()))

    # ------------------------------------------------------------------ zoom
    def set_view(self, start: float, end: float) -> None:
        """Show ``start..end`` (kept inside the stream and at least 20 s wide)."""
        span = min(self.duration, max(20.0, end - start))
        start = min(max(0.0, start), self.duration - span)
        self.view = (start, start + span)
        self.update()

    def reset_view(self) -> None:
        self.set_view(0.0, self.duration)

    def zoom_to(self, index: int) -> None:
        """Zoom so highlight ``index`` fills about a third of the width."""
        if 0 <= index < len(self.highlights):
            h = self.highlights[index]
            pad = max(h.duration, 40.0)
            self.set_view(h.start - pad, h.end + pad)

    @property
    def zoomed(self) -> bool:
        return self.view[1] - self.view[0] < self.duration - 1e-6

    def _hit(self, x: float) -> tuple[int, str] | None:
        """Which highlight (and which part of it) is under ``x``; the selected one wins ties."""
        order = sorted(range(len(self.highlights)), key=lambda i: (i != self.current, self.highlights[i].rank))
        v0, v1 = self.view
        for i in order:
            if self.highlights[i].end <= v0 or self.highlights[i].start >= v1:
                continue
            x0, x1 = self.time_to_x(self.highlights[i].start), self.time_to_x(self.highlights[i].end)
            inner = min(self.EDGE, (x1 - x0) / 4)  # edges reach outwards, so a narrow span keeps a middle to grab
            if x0 - self.EDGE <= x <= x0 + inner:
                return i, "start"
            if x1 - inner <= x <= x1 + self.EDGE:
                return i, "end"
            if x0 < x < x1:
                return i, "move"
        return None

    # ------------------------------------------------------------------ mouse
    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        hit = self._hit(event.position().x())
        if hit is None:
            self.select(-1)
            return
        index, part = hit
        h = self.highlights[index]
        self._drag = (index, part, self.x_to_time(event.position().x()), h.start, h.end)
        self.select(index)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        x = event.position().x()
        if self._drag is None:
            hit = self._hit(x)
            shape = Qt.CursorShape.ArrowCursor if hit is None else Qt.CursorShape.SizeAllCursor if hit[1] == "move" else Qt.CursorShape.SizeHorCursor
            self.setCursor(shape)
            return
        index, part, grabbed, start, end = self._drag
        h = self.highlights[index]
        delta = self.x_to_time(x) - grabbed
        if part == "move":
            delta = min(max(delta, -start), self.duration - end)
            h.start, h.end = start + delta, end + delta
        elif part == "start":
            h.start = min(max(0.0, start + delta), end - self.min_length)
        else:
            h.end = max(min(self.duration, end + delta), start + self.min_length)
        h.peak = min(max(h.peak, h.start), h.end)
        self.update()
        self.changed.emit(index)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._drag = None

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._drag = None
        hit = self._hit(event.position().x())
        if hit is None:
            self.reset_view()
        else:
            self.select(hit[0])
            self.zoom_to(hit[0])

    def wheelEvent(self, event) -> None:  # noqa: N802
        if self.result is None or not event.angleDelta().y():
            return
        v0, v1 = self.view
        anchor = self.x_to_time(event.position().x())
        factor = 0.8 if event.angleDelta().y() > 0 else 1.25
        span = min(self.duration, max(20.0, (v1 - v0) * factor))
        share = (anchor - v0) / max(v1 - v0, 1e-6)
        self.set_view(anchor - span * share, anchor - span * share + span)
        event.accept()

    # ------------------------------------------------------------------ paint
    def bars(self, count: int) -> list[float]:
        """Peak score in ``count`` equal time spans of the view (equal spans keep the bars aligned with the time axis)."""
        if self.result is None or not len(self.result.score) or count < 1:
            return []
        score = self.result.score
        v0, v1 = self.view
        edges = np.clip(np.floor(np.linspace(v0, v1, count + 1) / self.result.window).astype(int), 0, len(score) - 1)
        return [float(score[edges[k] : max(edges[k] + 1, edges[k + 1])].max()) for k in range(count)]

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(theme.SURFACE))
        plot = self._plot()
        small = QFont(self.font())
        small.setPointSize(8)
        p.setFont(small)
        if self.result is None:
            p.setPen(QColor(theme.MUTED))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, tr("영상과 채팅을 고르거나 방송 주소를 넣고 하이라이트 찾기 버튼을 누르세요"))
            p.end()
            return

        v0, v1 = self.view
        buckets = max(1, int((v1 - v0) / self.result.window))
        count = max(1, min(buckets, int(plot.width() // 5)))
        values = self.bars(count)
        top_value = max(float(self.result.score.max()), max((h.score for h in self.highlights), default=0.0), 1e-6)
        bar_w = plot.width() / count
        spans = [(h.start, h.end) for h in self.highlights]
        for k, value in enumerate(values):
            mid = v0 + (k + 0.5) / count * (v1 - v0)
            inside = any(s <= mid <= e for s, e in spans)
            height = max(2.0, plot.height() * 0.92 * value / top_value)
            p.fillRect(QRectF(plot.left() + k * bar_w + 0.5, plot.bottom() - height, max(1.0, bar_w - 1.5), height), QColor(theme.LIVE_PINK if inside else "#3A3454"))

        for i, h in enumerate(self.highlights):
            if h.end <= v0 or h.start >= v1:
                continue
            x0, x1 = self.time_to_x(h.start), self.time_to_x(h.end)
            chosen = i == self.current
            color = QColor(theme.HIGHLIGHT if chosen else theme.LIVE_PINK)
            fill = QColor(color)
            fill.setAlpha(46 if chosen else 22)
            box = QRectF(x0, plot.top() - 6, max(2.0, x1 - x0), plot.height() + 12)
            p.fillRect(box, fill)
            p.setPen(QPen(color, 2.5 if chosen else 1.5))
            p.drawRect(box)
            p.drawText(QPointF(x0 + 3, plot.top() - 12), f"{h.rank:02d}")

        p.setPen(QColor(theme.MUTED))
        ticks = 4
        for k in range(ticks + 1):
            t = v0 + (v1 - v0) * k / ticks
            label = _clock(t)
            width = p.fontMetrics().horizontalAdvance(label)
            x = min(max(plot.left(), self.time_to_x(t) - width / 2), plot.right() - width)
            p.drawText(QPointF(x, self.height() - 7), label)
        p.end()


_VIDEO_TYPES = (".mp4", ".mkv", ".webm", ".mov", ".flv", ".ts", ".m4v", ".avi")
_IMAGE_TYPES = (".png", ".jpg", ".jpeg", ".webp", ".bmp")


def kind_of(item: str) -> str:
    """What a dropped file (or address) is: "video", "session", "chat", "info", "subtitles", "image" or ""."""
    from ..sources import is_url

    name = str(item).strip().lower()
    if is_url(name):
        return "video"
    if name.endswith(".info.json"):
        return "info"
    if name.endswith(_VIDEO_TYPES):
        return "video"
    if name.endswith((".srt", ".vtt")):
        return "subtitles"
    if name.endswith(".jsonl"):
        from ..session import is_session

        if is_session(Path(str(item).strip())):  # a recorder's session, not a plain chat log
            return "session"
    if name.endswith((".json", ".jsonl", ".csv", ".xml")):
        return "chat"
    if name.endswith(_IMAGE_TYPES):
        return "image"
    return ""


def open_session(path: str, origin: str = "auto", offset: float = 0.0):
    """``(session, time 0)`` for a session file, or ``(None, 0.0)`` without one; raises ``ValueError`` with a message for the user.

    Takes plain values, so it can run in a worker thread with what was read from the window before.
    """
    if not path:
        return None, 0.0
    from ..session import load_session

    if not Path(path).is_file():
        raise ValueError(tr("세션 파일을 찾을 수 없습니다: {0}").format(path))
    session = load_session(path)
    if origin in ("stream", "record") and not session.output_starts(origin):
        raise ValueError(tr("세션에 OBS 송출 시작 기록이 없습니다. 다른 0초 기준을 고르세요.") if origin == "stream" else tr("세션에 OBS 녹화 시작 기록이 없습니다. 다른 0초 기준을 고르세요."))
    return session, session.origin(origin) + offset


def dropped_items(mime) -> list[str]:
    """Files and addresses in what was dropped (a ``QMimeData``)."""
    from ..sources import is_url

    if mime.hasUrls():
        return [url.toLocalFile() if url.isLocalFile() else url.toString() for url in mime.urls()]
    text = mime.text().strip() if mime.hasText() else ""
    return [text] if text and is_url(text) else []


class HighlightsWindow(QMainWindow):
    """Find, adjust, preview and export highlights."""

    _stage = Signal(str)
    _analysed = Signal(object)
    _previewed = Signal(int, object)
    _progress = Signal(int, int, str)
    _exported = Signal(object)
    _failed = Signal(str)
    _fetched = Signal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("stream2clip 방송 클립 제작"))
        self.setWindowIcon(app_icon())
        self.result: HighlightResult | None = None
        self.busy = False
        self.dialogs = True  # also show failures in a message box (tests turn this off)
        self.last_results: list = []
        self.upload_dialog = None
        self.last_dir = ""
        self._preview_token = 0
        self.sections: dict[int, tuple[Path, float]] = {}  # footage fetched for the highlights of an address: rank -> (file, stream time at its start)
        self._fetched_paths: dict[QLineEdit, str] = {}  # the info / chat fields this window filled in from an address

        root = QWidget(objectName="Root")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(20, 16, 20, 14)
        outer.setSpacing(10)
        outer.addWidget(QLabel(tr("입력 자료"), objectName="Eyebrow"))
        outer.addWidget(self._source_card())
        outer.addWidget(QLabel(tr("하이라이트"), objectName="Eyebrow"))
        self.timeline = TimelineWidget()
        self.timeline.selected.connect(self._on_timeline_selected)
        self.timeline.changed.connect(self._on_span_changed)
        self.timeline.setToolTip(tr("구간 가운데를 끌면 이동, 가장자리를 끌면 시작과 끝 조정 / 휠 또는 구간 더블클릭으로 확대, 빈 곳 더블클릭으로 전체 보기"))
        outer.addWidget(self.timeline)

        middle = QHBoxLayout()
        middle.setSpacing(12)
        self.list = QListWidget()
        self.list.setStyleSheet(f"QListWidget {{ background: {theme.SURFACE}; border: 1px solid {theme.BORDER}; border-radius: 10px; padding: 4px; }}"
                                f"QListWidget::item:selected {{ background: {theme.SURFACE_2}; }}")
        self.list.setWordWrap(True)
        self.list.setIconSize(QSize(34, 34))
        self.list.currentRowChanged.connect(self.timeline.select)
        middle.addWidget(self.list, 3)
        self.preview = QLabel(tr("미리보기"), objectName="Muted")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setFixedSize(172, 300)
        self.preview.setStyleSheet(f"background: #100E18; border: 1px solid {theme.BORDER}; border-radius: 10px;")
        middle.addWidget(self.preview)
        middle.addWidget(self._export_card(), 2)
        outer.addLayout(middle, 1)

        bottom = QHBoxLayout()
        self.mascot_label = QLabel()
        self.mascot_label.setFixedSize(44, 44)
        bottom.addWidget(self.mascot_label)
        self.mood = ""
        self.set_mood("wink")
        self.setAcceptDrops(True)  # a video, chat, info or subtitle file dropped on the window goes into its box
        self.last_compilation = None
        self.last_handoff: list[Path] = []
        self.scenes_skipped = 0  # highlights the last analysis left out for the scene they were in
        self.status = QLabel(tr("영상과 채팅 다시보기를 고르거나 방송 주소를 넣으세요"), objectName="Muted")
        bottom.addWidget(self.status, 1)
        self.progress = QProgressBar()
        self.progress.setFixedWidth(220)
        self.progress.setTextVisible(True)
        self.progress.setStyleSheet(f"QProgressBar {{ background: {theme.SURFACE_2}; border: 1px solid {theme.BORDER}; border-radius: 8px; text-align: center; }}"
                                    f"QProgressBar::chunk {{ background: {theme.LIVE_PINK}; border-radius: 7px; }}")
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        bottom.addWidget(self.progress)
        self.export_button = QPushButton(tr("클립 내보내기"), objectName="Primary")
        self.export_button.setMinimumHeight(38)
        self.export_button.clicked.connect(self.export)
        self.export_button.setEnabled(False)
        bottom.addWidget(self.export_button)
        self.handoff_button = QPushButton(tr("편집용 내보내기"))
        self.handoff_button.setMinimumHeight(38)
        self.handoff_button.setToolTip(tr("체크한 구간을 편집 프로그램용 컷 목록(EDL), 타임라인 마커, 타임스탬프 목록으로 저장"))
        self.handoff_button.clicked.connect(self.export_handoff)
        self.handoff_button.setEnabled(False)
        bottom.addWidget(self.handoff_button)
        self.upload_button = QPushButton(tr("업로드"))
        self.upload_button.setMinimumHeight(38)
        self.upload_button.setToolTip(tr("고른 클립(또는 다른 영상)을 YouTube에 올립니다. 기본은 비공개입니다."))
        self.upload_button.clicked.connect(self.open_upload)
        bottom.addWidget(self.upload_button)
        outer.addLayout(bottom)
        self.setCentralWidget(root)
        self.resize(1080, 760)
        self._restore()

        self._stage.connect(lambda name: self.status.setText(_STAGES.get(name, name)))
        self._analysed.connect(self._on_analysed)
        self._previewed.connect(self._on_previewed)
        self._progress.connect(self._on_progress)
        self._exported.connect(self._on_exported)
        self._failed.connect(self._on_failed)
        self._fetched.connect(self._on_fetched)

    # ------------------------------------------------------------------ layout
    def _path_row(self, grid: QGridLayout, row: int, column: int, label: str, placeholder: str, filters: str) -> QLineEdit:
        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        edit.setToolTip(placeholder)
        browse = QPushButton(tr("찾기"))
        browse.clicked.connect(lambda: self._browse(edit, filters))
        grid.addWidget(QLabel(label), row, column)
        grid.addWidget(edit, row, column + 1)
        grid.addWidget(browse, row, column + 2)
        return edit

    def _browse(self, edit: QLineEdit, filters: str) -> None:
        start = str(Path(edit.text()).parent) if edit.text() else (self.last_dir or str(Path.home()))
        path, _ = QFileDialog.getOpenFileName(self, tr("파일 고르기"), start, filters)
        if path:
            edit.setText(path)
            self.last_dir = str(Path(path).parent)

    def _source_card(self) -> QWidget:
        card = QWidget(objectName="Card")
        grid = QGridLayout(card)
        grid.setContentsMargins(14, 12, 14, 12)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        self.video_edit = self._path_row(grid, 0, 0, tr("영상"), tr("다시보기 파일 (video.mp4) 또는 방송 주소"), "Video (*.mp4 *.mkv *.webm *.mov *.flv *.ts);;All files (*)")
        self.chat_edit = self._path_row(grid, 0, 3, tr("채팅"), "yt-dlp live_chat.json, chat-downloader, TwitchDownloader, CSV", "Chat (*.json *.jsonl *.csv);;All files (*)")
        self.info_edit = self._path_row(grid, 1, 0, tr("정보"), tr("(선택) yt-dlp info.json: 원본 제목, URL, 많이 다시 본 구간"), "JSON (*.json);;All files (*)")
        self.subs_edit = self._path_row(grid, 1, 3, tr("자막"), tr("(선택) SRT, WebVTT: YouTube 자동 자막도 됩니다"), "Subtitles (*.vtt *.srt *.json);;All files (*)")
        self.video_edit.setToolTip(tr("방송 주소를 넣으면 채팅 다시보기로 하이라이트를 찾고 그 구간의 영상만 내려받습니다.\n음량, 웃음소리, 노래 구간은 영상 파일이 있어야 씁니다."))
        self.session_edit = self._path_row(grid, 2, 0, tr("세션"), tr("(선택) 방송 기록기의 세션 파일: 채팅, 표시, 장면, 아바타"), "Session (*.jsonl);;All files (*)")
        self.session_edit.setToolTip(tr("방송 기록기로 기록한 세션 파일. 채팅 칸이 비어 있으면 세션의 채팅과 표시로 하이라이트를 찾습니다.\n채팅 칸에 세션 파일을 넣으면 이 칸으로 옮깁니다."))
        grid.addWidget(QLabel(tr("오디오 트랙")), 2, 3)
        track_row = QHBoxLayout()
        self.track_spin = QSpinBox(minimum=0, maximum=6, value=0)
        self.track_spin.setSpecialValueText(tr("기본"))
        self.track_spin.setToolTip(tr("자막, 무음 구간, 음량, 웃음소리, 노래 구간을 들을 트랙. OBS에서 마이크만 트랙 2로 녹화했다면 2.\n클립에 들어가는 소리는 바뀌지 않습니다."))
        track_row.addWidget(self.track_spin)
        track_row.addStretch(1)
        grid.addLayout(track_row, 2, 4, 1, 2)
        # What to do with the session: a row that takes room only once a session is given.
        self.session_row = QWidget()
        session_options = QHBoxLayout(self.session_row)
        session_options.setContentsMargins(0, 0, 0, 0)
        session_options.setSpacing(8)
        session_options.addWidget(QLabel(tr("0초 기준")))
        self.origin_combo = QComboBox()
        for key, label in _SESSION_ORIGINS:
            self.origin_combo.addItem(label, key)
        self.origin_combo.setToolTip(tr("영상의 0초가 세션의 어느 시각인지. 플랫폼 다시보기는 송출 시작, OBS 녹화 파일은 녹화 시작."))
        session_options.addWidget(self.origin_combo)
        self.offset_spin = QDoubleSpinBox(minimum=-36000.0, maximum=36000.0, value=0.0, singleStep=0.5, decimals=1)
        self.offset_spin.setSuffix(tr("초"))
        self.offset_spin.setToolTip(tr("기준 시각과 영상 0초의 차이. 영상이 기준보다 늦게 시작하면 양수."))
        session_options.addWidget(self.offset_spin)
        session_options.addSpacing(14)
        session_options.addWidget(QLabel(tr("제외 장면")))
        self.skip_scene_edit = QLineEdit()
        self.skip_scene_edit.setPlaceholderText(tr("(선택) 제외할 OBS 장면 이름. 쉼표로 구분 (예: 대기, 휴식)"))
        self.skip_scene_edit.setToolTip(tr("이름에 이 말이 들어간 장면에서 대부분이 지나간 하이라이트를 제외합니다."))
        session_options.addWidget(self.skip_scene_edit, 1)
        self.motion_check = QCheckBox(tr("아바타 움직임 (실험)"))
        self.motion_check.setToolTip(tr("세션에 기록된 VTube Studio 아바타의 움직임이 큰 장면에 점수를 더합니다."))
        session_options.addWidget(self.motion_check)
        grid.addWidget(self.session_row, 3, 0, 1, 6)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(4, 1)
        grid.setColumnMinimumWidth(3, 44)
        options = QHBoxLayout()
        options.setSpacing(8)
        self.audio_check = QCheckBox(tr("음량도 사용"), checked=True)
        options.addWidget(self.audio_check)
        self.laughter_check = QCheckBox(tr("웃음소리 (실험)"))
        self.laughter_check.setToolTip(tr("끊어지는 큰 소리(웃음 같은 소리)가 있는 장면에 점수를 더합니다. 다른 신호로 찾은 장면은 그대로 남습니다."))
        options.addWidget(self.laughter_check)
        self.snap_check = QCheckBox(tr("문장 경계 맞춤"), checked=True)
        self.snap_check.setToolTip(tr("자막 파일이 있으면 구간의 시작과 끝을 말이 끊기지 않는 위치로 옮깁니다 (최대 3초)."))
        options.addWidget(self.snap_check)
        self.singing_combo = QComboBox()
        for key, label in _SINGING:
            self.singing_combo.addItem(label, key)
        self.singing_combo.setToolTip(tr("노래 방송(歌枠)은 곡 저작권 때문에 클립이 제한되는 경우가 많습니다.\n표시: 노래와 겹치는 하이라이트에 표시 / 제외: 대부분이 노래인 하이라이트는 뺌"))
        options.addWidget(self.singing_combo)
        options.addSpacing(14)
        options.addWidget(QLabel(tr("최대")))
        self.top_spin = QSpinBox(minimum=1, maximum=50, value=10)
        self.top_spin.setSuffix(tr("개"))
        options.addWidget(self.top_spin)
        options.addSpacing(14)
        options.addWidget(QLabel(tr("임계값")))
        self.threshold_spin = QDoubleSpinBox(minimum=0.5, maximum=10.0, value=2.0, singleStep=0.1)
        self.threshold_spin.setToolTip(tr("낮추면 더 많이, 높이면 확실한 장면만 찾습니다"))
        options.addWidget(self.threshold_spin)
        options.addStretch(1)
        self.analyse_button = QPushButton(tr("하이라이트 찾기"), objectName="Primary")
        self.analyse_button.setMinimumHeight(34)
        self.analyse_button.clicked.connect(self.analyse)
        options.addWidget(self.analyse_button)
        grid.addLayout(options, 4, 0, 1, 6)
        self.video_edit.textChanged.connect(self._on_source_changed)
        self.chat_edit.textChanged.connect(self._on_chat_changed)
        self.session_edit.textChanged.connect(self._on_session_changed)
        self._on_session_changed()
        return card

    # ------------------------------------------------------------------ session
    def _on_chat_changed(self) -> None:
        """A session file put into the chat box belongs in the session box: its scenes and avatar are used from there."""
        text = self.chat_edit.text().strip()
        if text.lower().endswith(".jsonl") and kind_of(text) == "session":
            self.chat_edit.clear()
            self.session_edit.setText(text)
            if not self.busy:
                self.status.setText(tr("세션 파일을 세션 칸으로 옮겼습니다."))

    def _on_session_changed(self) -> None:
        given = bool(self.session_edit.text().strip())
        self.session_row.setVisible(given)
        for widget in (self.origin_combo, self.offset_spin, self.skip_scene_edit, self.motion_check):
            widget.setEnabled(given)
        button = getattr(self, "session_avatar_button", None)  # the export card is built after this one
        if button is not None:
            button.setEnabled(given and not self.busy and self.layout_combo.currentData() in AVATAR_LAYOUTS)

    def audio_track(self) -> int | None:
        """The audio track to listen to, counted from 0, or ``None`` for the file's default (the box counts from 1, as OBS does)."""
        return self.track_spin.value() - 1 if self.track_spin.value() > 0 else None

    def skipped_scenes(self) -> list[str]:
        return [name.strip() for name in self.skip_scene_edit.text().split(",") if name.strip()]

    def session_choice(self) -> tuple[str, str, float]:
        """What the session boxes say: (file, which moment is second 0, seconds to add)."""
        return self.session_edit.text().strip(), self.origin_combo.currentData(), self.offset_spin.value()

    def load_session(self):
        """``(session, time 0)`` for the session box, or ``(None, 0.0)``; raises ``ValueError`` with a message for the user."""
        return open_session(*self.session_choice())

    def session_avatar(self) -> None:
        """Fill the avatar box from the session's VTube Studio outline during the checked highlights."""
        video = self.video_edit.text().strip()
        if self.busy or not video:
            return
        try:
            session, zero = self.load_session()
            if session is None:
                raise ValueError(tr("세션 파일을 먼저 고르세요."))
            if self.source_url() or not Path(video).is_file():
                raise ValueError(tr("세션의 아바타 위치는 녹화 파일이 있어야 계산합니다."))
            if not session.of("avatar_outline"):
                raise ValueError(tr("세션에 VTube Studio 윤곽 기록이 없습니다. 기록기에서 VTube Studio 연결을 켜고 기록하세요."))
            from ..export import probe
            from ..session import avatar_region

            kind = self.layout_combo.currentData()
            frame = VerticalLayout()  # the frame's size and split; a stack layout itself cannot be made before it has its avatar box
            aspect = 0.8 if kind == "pip" else frame.width / (frame.height * frame.split)  # the pip box: a little taller than wide
            info = probe(video)
            spans = [(h.start, h.end) for h in (self.checked_highlights() or self.timeline.highlights)]
            box = avatar_region(session, (info.width, info.height), aspect=aspect, origin=zero, spans=spans)
            if box is None and spans:  # no outline during the highlights: go by the whole session
                box = avatar_region(session, (info.width, info.height), aspect=aspect, origin=zero)
            if box is None:
                raise ValueError(tr("윤곽을 영상에 맞출 수 없습니다. 기록할 때 VTube Studio를 보여 주는 OBS 소스 이름을 지정하세요."))
        except (ValueError, OSError, RuntimeError) as exc:
            self._on_failed(str(exc))
            return
        self.avatar_edit.setText(str(box))
        self.status.setText(tr("아바타 {0}: 세션의 VTube Studio 윤곽 기준").format(box))
        self.set_mood("wink")
        self.refresh_preview()

    def _export_card(self) -> QWidget:
        card = QWidget(objectName="Card")
        grid = QGridLayout(card)
        grid.setContentsMargins(14, 12, 14, 12)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        grid.addWidget(QLabel(tr("레이아웃")), 0, 0)
        self.layout_combo = QComboBox()
        for key in ("blur", "stack", "pip", "center", "fit", "none"):
            self.layout_combo.addItem(_LAYOUT_LABELS[key], key)
        self.layout_combo.currentIndexChanged.connect(self._on_layout_changed)
        grid.addWidget(self.layout_combo, 0, 1, 1, 2)

        grid.addWidget(QLabel(tr("아바타")), 1, 0)
        self.avatar_edit = QLineEdit()
        self.avatar_edit.setPlaceholderText(tr("x,y,w,h"))
        self.avatar_edit.setToolTip(tr("stack, pip 레이아웃에서 방송 화면 속 아바타의 위치와 크기 (픽셀)"))
        self.avatar_edit.editingFinished.connect(self.refresh_preview)
        grid.addWidget(self.avatar_edit, 1, 1)
        self.avatar_button = QPushButton(tr("자동 찾기"))
        self.avatar_button.setToolTip(tr("애니메 얼굴 검출로 아바타 위치를 찾습니다 (처음 한 번 12MB 모델 다운로드)"))
        self.avatar_button.clicked.connect(self.find_avatar)
        self.session_avatar_button = QPushButton(tr("세션에서"))
        self.session_avatar_button.setToolTip(tr("세션에 기록된 VTube Studio 윤곽으로 아바타 위치를 정합니다 (체크한 하이라이트 구간 기준)."))
        self.session_avatar_button.clicked.connect(self.session_avatar)
        avatar_buttons = QHBoxLayout()
        avatar_buttons.setSpacing(6)
        avatar_buttons.addWidget(self.avatar_button)
        avatar_buttons.addWidget(self.session_avatar_button)
        grid.addLayout(avatar_buttons, 1, 2)

        grid.addWidget(QLabel(tr("아바타 영상")), 2, 0)
        self.avatar_video_edit = QLineEdit()
        self.avatar_video_edit.setPlaceholderText(tr("(선택) 아바타만 녹화한 영상"))
        self.avatar_video_edit.setToolTip(tr("방송과 같은 시간에 아바타만 따로 녹화한 영상입니다. 초록 배경(#00FF00)은 지우고, 투명 배경 영상은 그대로 씁니다.\n넣으면 아바타 위치 대신 이 영상이 stack, pip 레이아웃의 아바타가 됩니다."))
        self.avatar_video_edit.editingFinished.connect(self.refresh_preview)
        grid.addWidget(self.avatar_video_edit, 2, 1)
        self.avatar_video_button = QPushButton(tr("찾기"))
        self.avatar_video_button.clicked.connect(self._pick_avatar_video)
        grid.addWidget(self.avatar_video_button, 2, 2)

        grid.addWidget(QLabel(tr("자막")), 3, 0)
        self.subs_combo = QComboBox()
        self.subs_combo.addItem(tr("자막 파일 사용 (있으면)"), "file")
        self.subs_combo.addItem(tr("없음"), "none")
        self.subs_combo.addItem(tr("받아쓰기 (Whisper small)"), "small")
        self.subs_combo.addItem(tr("받아쓰기 (Whisper medium)"), "medium")
        grid.addWidget(self.subs_combo, 3, 1, 1, 2)
        grid.addWidget(QLabel(tr("언어")), 4, 0)
        self.language_edit = QLineEdit("ja")
        self.language_edit.setToolTip(tr("자막 원문 언어 (ja, ko, en 등). 받아쓰기와 번역에 사용"))
        grid.addWidget(self.language_edit, 4, 1)
        self.karaoke_check = QCheckBox(tr("카라오케"), checked=True)
        self.karaoke_check.setToolTip(tr("말하는 단어에 맞춰 색이 바뀝니다 (번역한 자막에는 적용되지 않습니다)"))
        grid.addWidget(self.karaoke_check, 4, 2)

        grid.addWidget(QLabel(tr("스타일")), 5, 0)
        self.style_combo = QComboBox()
        for key, label in _SUBTITLE_STYLES:
            self.style_combo.addItem(label, key)
        self.style_combo.setToolTip(tr("자막의 모양. 상자는 복잡한 게임 화면 위에서도 읽기 쉽습니다."))
        grid.addWidget(self.style_combo, 5, 1)
        self.position_combo = QComboBox()
        for key, label in _SUBTITLE_POSITIONS:
            self.position_combo.addItem(label, key)
        self.position_combo.setToolTip(tr("자막의 위치. 게임 자체의 대사 창이 아래에 있으면 위쪽을 고르세요."))
        grid.addWidget(self.position_combo, 5, 2)

        grid.addWidget(QLabel(tr("번역")), 6, 0)
        self.translator_combo = QComboBox()
        self.translator_combo.setToolTip(tr("번역 서비스는 내장돼 있지 않습니다. 설치한 번역기 플러그인을 고르거나,\ntranslate(texts, target, source) 함수가 있는 .py 파일을 고르세요 (examples/translators 참고)."))
        self._fill_translators()
        self.translator_combo.activated.connect(self._on_translator_picked)
        grid.addWidget(self.translator_combo, 6, 1)
        translate_row = QHBoxLayout()
        translate_row.setSpacing(6)
        self.target_edit = QLineEdit("ko")
        self.target_edit.setToolTip(tr("번역할 언어 (ko, en 등)"))
        self.target_edit.setFixedWidth(46)
        translate_row.addWidget(self.target_edit)
        self.bilingual_check = QCheckBox(tr("원문 병기"))
        self.bilingual_check.setToolTip(tr("원문 줄 아래에 번역을 함께 넣습니다"))
        translate_row.addWidget(self.bilingual_check)
        grid.addLayout(translate_row, 6, 2)

        grid.addWidget(QLabel(tr("용어집")), 7, 0)
        self.glossary_edit = QLineEdit()
        self.glossary_edit.setPlaceholderText(tr("(선택) 이름 고정 CSV, JSON"))
        self.glossary_edit.setToolTip(tr("source,target 두 열의 CSV 또는 JSON. 버튜버 이름처럼 번역기가 틀리기 쉬운 말을 고정합니다."))
        grid.addWidget(self.glossary_edit, 7, 1)
        pick_glossary = QPushButton(tr("찾기"))
        pick_glossary.clicked.connect(lambda: self._browse(self.glossary_edit, "Glossary (*.csv *.json);;All files (*)"))
        grid.addWidget(pick_glossary, 7, 2)

        grid.addWidget(QLabel(tr("형식")), 8, 0)
        self.format_combo = QComboBox()
        for fmt in ("mp4", "webm", "webp", "gif"):
            self.format_combo.addItem(fmt.upper(), fmt)
        grid.addWidget(self.format_combo, 8, 1)
        self.agency_combo = QComboBox()
        for key in _AGENCIES:
            self.agency_combo.addItem(key or tr("가이드라인 없음"), key)
        self.agency_combo.setToolTip(tr("설명란과 업로드 전 점검에 쓸 기획사 프로필 (체크리스트일 뿐 법적 판단이 아닙니다)"))
        grid.addWidget(self.agency_combo, 8, 2)

        grid.addWidget(QLabel(tr("출처 표기")), 9, 0)
        self.credit_edit = QLineEdit()
        self.credit_edit.setPlaceholderText(tr("(선택) 예: 원본: 채널 이름"))
        self.credit_edit.setToolTip(tr("클립 왼쪽 위에 작게 넣을 문구. 비우면 넣지 않음"))
        grid.addWidget(self.credit_edit, 9, 1)
        self.compile_check = QCheckBox(tr("모음 영상"))
        self.compile_check.setToolTip(tr("내보낸 클립을 방송 순서대로 이어 붙인 영상과 챕터 목록을 함께 저장 (MP4, WebM)"))
        grid.addWidget(self.compile_check, 9, 2)

        grid.addWidget(QLabel(tr("무음 구간")), 10, 0)
        self.silence_check = QCheckBox(tr("조용한 부분 줄이기"))
        self.silence_check.setToolTip(tr("클립 안에서 0.7초 넘게 조용한 부분을 짧은 쉼으로 줄임. 자막도 함께 이동.\n배경 음악이 큰 방송은 줄일 부분이 적고, 말 없이 게임 소리만 작게 나는 장면도 줄어듦"))
        grid.addWidget(self.silence_check, 10, 1, 1, 2)

        grid.addWidget(QLabel(tr("저장")), 11, 0)
        self.output_edit = QLineEdit(str(default_clip_dir()))
        grid.addWidget(self.output_edit, 11, 1)
        pick = QPushButton(tr("폴더"))
        pick.clicked.connect(self._pick_output)
        grid.addWidget(pick, 11, 2)
        grid.setRowStretch(12, 1)
        self._on_layout_changed()
        return card

    # ------------------------------------------------------------------ translator choice
    def _fill_translators(self, chosen: str = "") -> None:
        """Off, the installed plugins, a file chosen earlier, and "choose a file"."""
        from ..plugins import translators

        combo = self.translator_combo
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(tr("번역 안 함"), "")
        names = list(translators())
        for name in names:
            combo.addItem(name, name)
        if chosen and chosen not in names:
            from ..translation import split_translator_spec

            target, attr = split_translator_spec(chosen)
            label = (Path(target).name if target.lower().endswith(".py") else target) + ("" if attr == "translate" else f":{attr}")
            combo.addItem(label, chosen)
        combo.addItem(tr("번역기 파일 고르기 (.py)"), _PICK_FILE)
        combo.setCurrentIndex(max(0, combo.findData(chosen)))
        combo.blockSignals(False)

    def _on_translator_picked(self, index: int) -> None:
        if self.translator_combo.itemData(index) != _PICK_FILE:
            return
        path, _ = QFileDialog.getOpenFileName(self, tr("번역기 파일"), self.last_dir or str(Path.home()), "Python (*.py)")
        self.set_translator(path)

    def set_translator(self, spec: str) -> None:
        """Choose a translator: a plugin name, ``file.py[:function]``, or ``""`` for none."""
        self._fill_translators(spec)

    def translator_choice(self) -> str:
        data = self.translator_combo.currentData()
        return "" if data in (None, _PICK_FILE) else str(data)

    # ------------------------------------------------------------------ remembered settings
    def _restore(self) -> None:
        saved = load_section("highlights")
        for check, key in ((self.audio_check, "audio"), (self.laughter_check, "laughter"), (self.snap_check, "snap"), (self.karaoke_check, "karaoke"), (self.bilingual_check, "bilingual"), (self.compile_check, "compile"), (self.silence_check, "trim_silence"), (self.motion_check, "avatar_motion")):
            if isinstance(saved.get(key), bool):
                check.setChecked(saved[key])
        for combo, key in ((self.singing_combo, "singing"), (self.layout_combo, "layout"), (self.subs_combo, "subtitles"), (self.style_combo, "subtitle_style"), (self.position_combo, "subtitle_position"), (self.format_combo, "format"), (self.agency_combo, "agency"), (self.origin_combo, "session_origin")):
            index = combo.findData(saved.get(key)) if isinstance(saved.get(key), str) else -1
            if index >= 0:
                combo.setCurrentIndex(index)
        for edit, key in ((self.language_edit, "language"), (self.target_edit, "target"), (self.glossary_edit, "glossary"), (self.avatar_video_edit, "avatar_video"), (self.credit_edit, "credit"), (self.skip_scene_edit, "skip_scenes"), (self.output_edit, "output")):
            if isinstance(saved.get(key), str) and saved[key]:
                edit.setText(saved[key])
        if isinstance(saved.get("top"), int):
            self.top_spin.setValue(saved["top"])
        if isinstance(saved.get("audio_track"), int) and not isinstance(saved.get("audio_track"), bool):
            self.track_spin.setValue(saved["audio_track"])
        if isinstance(saved.get("session_offset"), (int, float)) and not isinstance(saved.get("session_offset"), bool):
            self.offset_spin.setValue(float(saved["session_offset"]))
        if isinstance(saved.get("threshold"), (int, float)):
            self.threshold_spin.setValue(float(saved["threshold"]))
        if isinstance(saved.get("translator"), str) and saved["translator"]:
            self.set_translator(saved["translator"])
        if isinstance(saved.get("last_dir"), str):
            self.last_dir = saved["last_dir"]

    def remember(self) -> None:
        save_section("highlights", {
            "audio": self.audio_check.isChecked(), "laughter": self.laughter_check.isChecked(), "snap": self.snap_check.isChecked(), "singing": self.singing_combo.currentData(),
            "top": self.top_spin.value(), "threshold": round(self.threshold_spin.value(), 2),
            "layout": self.layout_combo.currentData(), "subtitles": self.subs_combo.currentData(), "language": self.language_edit.text().strip(),
            "subtitle_style": self.style_combo.currentData(), "subtitle_position": self.position_combo.currentData(), "avatar_video": self.avatar_video_edit.text().strip(),
            "karaoke": self.karaoke_check.isChecked(), "translator": self.translator_choice(), "target": self.target_edit.text().strip(),
            "glossary": self.glossary_edit.text().strip(), "bilingual": self.bilingual_check.isChecked(),
            "format": self.format_combo.currentData(), "agency": self.agency_combo.currentData(), "output": self.output_edit.text().strip(),
            "credit": self.credit_edit.text().strip(), "compile": self.compile_check.isChecked(), "trim_silence": self.silence_check.isChecked(),
            "session_origin": self.origin_combo.currentData(), "session_offset": round(self.offset_spin.value(), 1), "skip_scenes": self.skip_scene_edit.text().strip(),
            "avatar_motion": self.motion_check.isChecked(), "audio_track": self.track_spin.value(),
            "last_dir": self.last_dir,
        })

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self.remember()
        super().closeEvent(event)

    # ------------------------------------------------------------------ dropped files
    def take_files(self, items) -> list[str]:
        """Put dropped files (or a stream address) into the boxes they belong in; returns the kinds that were placed."""
        placed = []
        for item in items:
            kind = kind_of(item)
            edit = {"video": self.video_edit, "chat": self.chat_edit, "info": self.info_edit, "subtitles": self.subs_edit, "session": self.session_edit}.get(kind)
            if edit is None:
                continue
            edit.setText(str(item).strip())
            placed.append(kind)
            if kind == "subtitles":
                self.subs_combo.setCurrentIndex(max(0, self.subs_combo.findData("file")))
        if placed and not self.busy:
            self.status.setText(tr("파일 {0}개 입력됨. 하이라이트 찾기를 눌러 분석").format(len(placed)))
        return placed

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        if self.take_files(dropped_items(event.mimeData())):
            event.acceptProposedAction()

    # ------------------------------------------------------------------ for an editing program
    def export_handoff(self) -> None:
        """Save the checked highlights as a cut list (EDL), timeline markers and a timestamp list; the list is also copied."""
        chosen = self.checked_highlights()
        if not chosen or self.busy:
            return
        from .. import handoff
        from ..export import probe
        from ..sources import is_url

        folder = Path(self.output_edit.text().strip() or str(default_clip_dir()))
        video = self.video_edit.text().strip()
        written = ["timestamps.txt"]
        try:
            folder.mkdir(parents=True, exist_ok=True)
            text = handoff.timestamps(chosen)
            (folder / "timestamps.txt").write_text(text, encoding="utf-8")
            if video and not is_url(video) and Path(video).is_file():
                facts = probe(video)
                if facts.fps:
                    name = Path(video)
                    handoff.write_text(handoff.edl(chosen, fps=facts.fps, title=name.stem, clip_name=name.name, audio=facts.has_audio), folder / "highlights.edl")
                    handoff.write_text(handoff.marker_edl(chosen, fps=facts.fps, title=name.stem), folder / "markers.edl")
                    written += ["highlights.edl", "markers.edl"]
        except (OSError, ValueError, RuntimeError) as exc:
            self._on_failed(str(exc))
            return
        QApplication.clipboard().setText(text)
        self.last_handoff = [folder / name for name in written]
        if len(written) == 1:
            self.status.setText(tr("타임스탬프 목록 저장됨: {0}. 클립보드에도 복사. 컷 목록(EDL)은 영상 파일이 있어야 저장").format(folder))
        else:
            self.status.setText(tr("편집용 파일 저장됨: {0} ({1}). 타임스탬프 목록은 클립보드에도 복사").format(folder, ", ".join(written)))

    def _pick_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, tr("저장 폴더"), self.output_edit.text())
        if path:
            self.output_edit.setText(path)

    # ------------------------------------------------------------------ helpers
    def set_paths(self, *, video: str = "", chat: str = "", info: str = "", subtitles: str = "", output: str = "", session: str = "") -> None:
        self.session_edit.setText(session)
        for edit, value in ((self.video_edit, video), (self.chat_edit, chat), (self.info_edit, info), (self.subs_edit, subtitles), (self.output_edit, output)):
            if value:
                edit.setText(str(value))

    def source_url(self) -> str:
        """The address in the video field, or ``""`` when it holds a file."""
        from ..sources import is_url

        text = self.video_edit.text().strip()
        return text if is_url(text) else ""

    def source_folder(self, url: str) -> Path:
        """Where the info, chat and footage fetched from ``url`` are kept: one folder per stream under the output folder."""
        from ..sources import source_folder_name

        return Path(self.output_edit.text().strip() or default_clip_dir()) / "sources" / source_folder_name(url)

    def footage(self, highlight: Highlight) -> tuple[str, float] | None:
        """``(file, stream time at its start)`` to read ``highlight`` from, or ``None`` when nothing is on disk yet."""
        video = self.video_edit.text().strip()
        if not video:
            return None
        if not self.source_url():
            return video, 0.0
        got = self.sections.get(highlight.rank)
        if got is None or not got[0].is_file() or highlight.peak < got[1]:
            return None
        return str(got[0]), got[1]

    def _on_source_changed(self) -> None:
        """An address has no audio to analyse; footage fetched for another stream is forgotten."""
        local = not self.source_url()
        for widget in (self.audio_check, self.laughter_check, self.singing_combo):
            widget.setEnabled(local)
        self.sections = {}
        for edit, value in self._fetched_paths.items():  # the chat of one stream must not be used with another
            if edit.text() == value:
                edit.clear()
        self._fetched_paths = {}

    def _on_fetched(self, info: str, chat: str) -> None:
        for edit, value in ((self.info_edit, info), (self.chat_edit, chat)):
            if value and not edit.text().strip():
                edit.setText(value)
                self._fetched_paths[edit] = value

    def _download(self, url: str, folder: Path, highlights: list[Highlight], on_progress=None) -> dict[int, tuple[Path, float]]:
        """Fetch the footage of ``highlights`` into ``folder`` (called from a worker thread); files that are already there are reused."""
        from .. import sources

        got = sources.download_highlight_sections(url, highlights, folder / "sections", ytdlp=sources.ytdlp_command(), on_progress=on_progress)
        self.sections.update(got)
        return got

    def set_mood(self, mood: str) -> None:
        """Kiri next to the status line: wink = ready, side (looking at the progress bar) = working, cut = clips done, surprised = failed."""
        if mood != self.mood:
            self.mood = mood
            self.mascot_label.setPixmap(mascot(mood, 44))

    def _set_busy(self, busy: bool, message: str | None = None) -> None:
        self.busy = busy
        if busy:
            self.set_mood("side")  # turned towards the progress bar on its right
        self.analyse_button.setEnabled(not busy)
        self.avatar_button.setEnabled(not busy and self.layout_combo.currentData() in AVATAR_LAYOUTS)
        self.session_avatar_button.setEnabled(not busy and self.layout_combo.currentData() in AVATAR_LAYOUTS and bool(self.session_edit.text().strip()))
        self.export_button.setEnabled(not busy and bool(self.checked_highlights()))
        self.handoff_button.setEnabled(not busy and bool(self.checked_highlights()))
        if message is not None:
            self.status.setText(message)

    def _run(self, work) -> None:
        def guarded() -> None:
            try:
                work()
            except Exception as exc:  # shown in the status bar and a dialog
                self._failed.emit(str(exc))

        threading.Thread(target=guarded, name="stream2clip-highlights", daemon=True).start()

    def _on_failed(self, message: str) -> None:
        self._set_busy(False, tr("실패: {0}").format(message.splitlines()[0][:120]))
        self.set_mood("surprised")
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        if self.dialogs and self.isVisible():
            QMessageBox.warning(self, "stream2clip", message)

    def layout_choice(self) -> VerticalLayout | None:
        """The layout the form describes; raises ``ValueError`` with a message for the user."""
        kind = self.layout_combo.currentData()
        if kind == "none":
            return None
        avatar = None
        if kind in AVATAR_LAYOUTS:
            text = self.avatar_edit.text().strip()
            video = self.avatar_video_edit.text().strip()
            if video:  # the avatar's own recording: no box in the stream is needed
                from ..export import has_alpha

                if not Path(video).is_file():
                    raise ValueError(tr("아바타 영상 파일을 찾을 수 없습니다: {0}").format(video))
                return VerticalLayout(kind, avatar=Region.parse(text) if text else None, avatar_source=video, avatar_key=None if has_alpha(video) else "#00FF00")
            if not text:
                raise ValueError(tr("이 레이아웃은 아바타 위치 또는 아바타 영상이 필요합니다. 자동 찾기 버튼을 누르거나 x,y,w,h를 입력하세요."))
            avatar = Region.parse(text)
        assert kind in LAYOUTS
        return VerticalLayout(kind, avatar=avatar)

    def _pick_avatar_video(self) -> None:
        self._browse(self.avatar_video_edit, "Video (*.mp4 *.mkv *.webm *.mov);;All files (*)")
        self.refresh_preview()

    def checked_highlights(self) -> list[Highlight]:
        return [self.timeline.highlights[i] for i in range(self.list.count()) if self.list.item(i).checkState() == Qt.CheckState.Checked]

    def _item_text(self, h: Highlight) -> str:
        head = tr("#{0:02d}   {1} - {2}   ({3:.0f}초, 점수 {4:.1f})").format(h.rank, _clock(h.start), _clock(h.end), h.duration, h.score)
        return head + ("\n" + " / ".join(h.reasons) if h.reasons else "")

    # ------------------------------------------------------------------ analyse
    def analyse(self) -> None:
        if self.busy:
            return
        video, chat, info = self.video_edit.text().strip(), self.chat_edit.text().strip(), self.info_edit.text().strip()
        if not video:
            self._on_failed(tr("영상 파일을 고르거나 방송 주소를 넣으세요."))
            return
        url = self.source_url()
        config = HighlightConfig(threshold=self.threshold_spin.value(), top=self.top_spin.value())
        audio = self.audio_check.isChecked() and not url
        laughter = self.laughter_check.isChecked() and not url
        singing = self.singing_combo.currentData() if not url else "off"
        spoken = self.subs_edit.text().strip() if self.snap_check.isChecked() else ""
        folder = self.source_folder(url) if url else None
        track = self.audio_track()
        chosen_session = self.session_choice()
        recorded = bool(chosen_session[0])
        skipped = self.skipped_scenes() if recorded else []
        moving = recorded and self.motion_check.isChecked()
        self.scenes_skipped = 0
        self.remember()
        self._set_busy(True, tr("분석 시작"))
        self.progress.setRange(0, 0)  # busy indicator

        def work() -> None:
            from ..pipeline import find_highlights

            nonlocal chat, info
            session, zero = open_session(*chosen_session)  # the session's chat and markers stand in for a chat file
            if url and not ((chat or session is not None) and info):  # the video itself comes later, and only the parts that are exported
                from .. import sources

                got_info, got_chat = sources.fetch_replay(url, folder, info=not info, chat=not chat and session is None, reuse=True, ytdlp=sources.ytdlp_command(), on_stage=self._stage.emit)
                info, chat = info or str(got_info or ""), chat or str(got_chat or "")
                self._fetched.emit(info, chat)
            source = {}
            if info:
                from ..sources import load_info, source_from_info

                src = source_from_info(load_info(info))
                source = {"url": src.url, "title": src.title}
            elif url:
                source = {"url": url}
            messages = motion = None
            if session is not None:
                if not chat:
                    messages = session.messages(zero, marker_delay=config.chat_delay)
                if moving:
                    from ..session import avatar_motion

                    motion = avatar_motion(session, zero, window=config.window, delay=config.chat_delay)
                    if not motion.any():
                        raise ValueError(tr("세션에 아바타 움직임 기록이 없습니다. 기록기에서 VTube Studio 연결을 켜고 기록하세요."))
            result = find_highlights(None if url else video, chat=chat or None, info=info or None, audio=audio, laughter=laughter, config=config, source=source, on_stage=self._stage.emit,
                                     messages=messages, avatar=motion, audio_track=track)
            if session is not None and skipped:
                from ..session import skip_scenes

                kept = sorted(skip_scenes(result.highlights, session.scenes(zero), skipped), key=lambda h: h.rank)
                self.scenes_skipped = len(result.highlights) - len(kept)
                for rank, h in enumerate(kept, start=1):
                    h.rank = rank
                result.highlights = kept
            if singing != "off":
                from ..audio import singing_sections
                from ..highlights import mark_singing

                self._stage.emit("singing")
                mark_singing(result, [(s.start, s.end) for s in singing_sections(video, track=track)], drop=singing == "skip")
            if spoken and Path(spoken).is_file():  # before the spans are shown: they can still be dragged afterwards
                from ..highlights import snap_to_cues
                from ..subtitles import load_subtitles

                snap_to_cues(result.highlights, load_subtitles(spoken), duration=result.duration)
            self._analysed.emit(result)

        self._run(work)

    def _on_analysed(self, result: HighlightResult) -> None:
        self.result = result
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.timeline.set_result(result)
        self.list.blockSignals(True)
        self.list.clear()
        for h in result.highlights:
            item = QListWidgetItem(self._item_text(h))
            face = mood_for(h)
            if face is not None:
                item.setIcon(QIcon(mascot(face, 34)))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.list.addItem(item)
        self.list.blockSignals(False)
        if result.highlights:
            self.list.setCurrentRow(0)
        count = len(result.highlights)
        chat = tr("채팅 {0:,}개, ").format(result.messages) if result.messages else ""
        hint = "" if count else tr(" (임계값을 낮춰 보세요)")
        sung = tr(", 노래 구간 {0}곳").format(len(result.songs)) if result.songs is not None else ""
        if self.scenes_skipped:
            sung += tr(", 장면으로 제외 {0}개").format(self.scenes_skipped)
        self._set_busy(False, tr("{0}{1} 분석, 하이라이트 {2}개{3}{4}").format(chat, _clock(result.duration), count, sung, hint))
        self.set_mood("laugh" if count else "wink")
        self.refresh_preview()

    # ------------------------------------------------------------------ selection / preview
    def _on_timeline_selected(self, index: int) -> None:
        if self.list.currentRow() != index:
            self.list.blockSignals(True)
            self.list.setCurrentRow(index)
            self.list.blockSignals(False)
        self.refresh_preview()

    def _on_span_changed(self, index: int) -> None:
        if 0 <= index < self.list.count():
            self.list.item(index).setText(self._item_text(self.timeline.highlights[index]))

    def _on_layout_changed(self) -> None:
        stack = self.layout_combo.currentData() in AVATAR_LAYOUTS
        self.avatar_edit.setEnabled(stack)
        self.avatar_video_edit.setEnabled(stack)
        self.avatar_video_button.setEnabled(stack)
        self.avatar_button.setEnabled(stack and not self.busy)
        self.session_avatar_button.setEnabled(stack and not self.busy and bool(self.session_edit.text().strip()))
        if self.result is not None:
            self.refresh_preview()

    def refresh_preview(self) -> None:
        """Render one frame of the selected highlight with the current layout (in the background)."""
        index = self.timeline.current
        if index < 0 or not self.video_edit.text().strip():
            self.preview.setPixmap(QPixmap())
            self.preview.setText(tr("미리보기"))
            return
        found = self.footage(self.timeline.highlights[index])
        if found is None:  # an address: the footage of this highlight has not been downloaded yet
            self._preview_token += 1
            self.preview.setPixmap(QPixmap())
            self.preview.setText(tr("내보내면\n미리보기가 보입니다"))
            return
        video, offset = found
        try:
            layout = self.layout_choice()
        except ValueError:
            self.preview.setPixmap(QPixmap())
            self.preview.setText(tr("아바타 위치를\n정하면 보입니다"))
            return
        if layout is not None:  # a small canvas is enough for a still and renders quickly
            layout = replace(layout, width=360, height=640)
        moment = self.timeline.highlights[index].peak - offset
        self._preview_token += 1
        token = self._preview_token

        def work() -> None:
            from ..export import grab_frames

            try:
                frames = grab_frames(video, [moment], layout=layout)
            except Exception:  # a preview that cannot be made is not worth a dialog
                frames = []
            try:
                self._previewed.emit(token, frames[0] if frames else None)
            except RuntimeError:  # the window was closed while the frame was being made
                pass

        threading.Thread(target=work, name="stream2clip-preview", daemon=True).start()

    def _on_previewed(self, token: int, frame: "np.ndarray | None") -> None:
        if token != self._preview_token:
            return  # an older request finished late
        if frame is None:
            self.preview.setPixmap(QPixmap())
            self.preview.setText(tr("미리보기를\n만들 수 없습니다"))
            return
        from ..frames import to_image

        pixmap = QPixmap.fromImage(pil_to_qimage(to_image(frame)))
        self.preview.setText("")
        self.preview.setPixmap(pixmap.scaled(self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    # ------------------------------------------------------------------ avatar
    def find_avatar(self) -> None:
        video = self.video_edit.text().strip()
        if self.busy or not video:
            return
        url = self.source_url()
        sample = None
        if url:  # look at the footage of one highlight instead of the whole stream
            index = self.timeline.current
            if not 0 <= index < len(self.timeline.highlights):
                self._on_failed(tr("먼저 하이라이트를 찾으세요."))
                return
            sample = self.timeline.highlights[index]
        folder = self.source_folder(url) if url else None
        self._set_busy(True, tr("구간 내려받는 중") if url else tr("아바타 찾는 중"))

        def work() -> None:
            from ..detect import default_detector, suggest_avatar_for_video

            footage = video
            if sample is not None:
                footage = str(self._download(url, folder, [sample])[sample.rank][0])
                self._stage.emit("avatar")
            self._exported.emit(("avatar", suggest_avatar_for_video(footage, default_detector())))

        self._run(work)

    # ------------------------------------------------------------------ export
    def export(self) -> None:
        if self.busy:
            return
        chosen = self.checked_highlights()
        video = self.video_edit.text().strip()
        if not chosen or not video:
            return
        try:
            layout = self.layout_choice()
        except ValueError as exc:
            self._on_failed(str(exc))
            return
        options = ExportOptions(format=self.format_combo.currentData(), fps=30, quality=85, layout=layout)
        mode = self.subs_combo.currentData()
        subs_path = self.subs_edit.text().strip() if mode == "file" else ""
        model = mode if mode in ("small", "medium") else None
        language = self.language_edit.text().strip() or None
        karaoke = self.karaoke_check.isChecked()
        look, place = self.style_combo.currentData(), self.position_combo.currentData()
        info_path = self.info_edit.text().strip()
        agency = self.agency_combo.currentData()
        out_dir = self.output_edit.text().strip() or str(default_clip_dir())
        url = self.source_url()
        translator_spec = self.translator_choice()
        target = self.target_edit.text().strip() or "ko"
        glossary_path = self.glossary_edit.text().strip()
        bilingual = self.bilingual_check.isChecked()
        credit = self.credit_edit.text().strip() or None
        trim = 0.7 if self.silence_check.isChecked() else None
        track = self.audio_track()
        joined = self.compile_check.isChecked() and self.format_combo.currentData() in ("mp4", "webm")
        self.last_compilation = None
        if translator_spec and not subs_path and model is None:
            self._on_failed(tr("번역하려면 자막이 필요합니다. 자막 파일을 고르거나 받아쓰기를 켜세요."))
            return
        self.remember()
        self._set_busy(True, tr("클립 {0}개 내보내는 중").format(len(chosen)))
        folder = self.source_folder(url) if url else None
        steps = len(chosen) * (2 if url else 1)  # an address: download each section, then encode it
        self.progress.setRange(0, steps)
        self.progress.setValue(0)

        def work() -> None:
            from ..compliance import get_profile
            from ..pipeline import make_clips
            from ..sources import load_info, source_from_info
            from ..subtitles import FasterWhisperTranscriber, load_subtitles, subtitle_style

            cues = load_subtitles(subs_path) if subs_path else None
            transcriber = FasterWhisperTranscriber(model) if model else None
            source = source_from_info(load_info(info_path)) if info_path else None
            profile = get_profile(agency) if (agency or source) else None
            subtitle_translator = glossary = None
            if translator_spec:
                from ..translation import Glossary, get_translator

                subtitle_translator = get_translator(translator_spec)
                glossary = Glossary.load(glossary_path) if glossary_path else None
            sections = None
            if url:
                sections = self._download(url, folder, chosen, lambda i, n, h: self._progress.emit(i - 1, steps, tr("[{0}/{1}] #{2:02d} {3} - {4} 내려받는 중").format(i, n, h.rank, _clock(h.start), _clock(h.end))))
            done = len(chosen) if url else 0
            results = make_clips(
                None if url else video, chosen, out_dir, options=options, cues=cues, transcriber=transcriber, language=language, karaoke=karaoke,
                subtitle_translator=subtitle_translator, translate_to=target, glossary=glossary, bilingual=bilingual,
                subtitle_style=subtitle_style(look, position=place), credit=credit, trim_silence=trim, audio_track=track,
                source=source, profile=profile, section=(lambda h: sections[h.rank]) if sections is not None else None,
                on_progress=lambda i, n, h: self._progress.emit(done + i - 1, steps, tr("[{0}/{1}] #{2:02d} {3} - {4} 인코딩 중").format(i, n, h.rank, _clock(h.start), _clock(h.end))),
            )
            if joined and results:
                from ..pipeline import compile_folder

                self._progress.emit(steps, steps, tr("모음 영상 만드는 중"))
                self.last_compilation = compile_folder(out_dir)
            self._exported.emit(("clips", results))

        self._run(work)

    def _on_progress(self, done: int, total: int, text: str) -> None:
        self.progress.setRange(0, total)
        self.progress.setValue(done)
        self.status.setText(text)

    def _on_exported(self, payload: tuple) -> None:
        kind, value = payload
        if kind == "avatar":
            if value is None:
                self._on_failed(tr("아바타를 찾지 못했습니다. 같은 자리에 계속 나오는 얼굴이 없습니다. x,y,w,h를 직접 입력하세요."))
                return
            self.avatar_edit.setText(str(value.region))
            self._set_busy(False, tr("아바타 {0}: 프레임 {1}/{2}장에서 확인").format(value.region, value.hits, value.frames))
            self.set_mood("wink")
            self.refresh_preview()
            return
        self.last_results = value
        self.progress.setRange(0, max(1, len(value)))
        self.progress.setValue(len(value))
        warnings = sum(1 for r in value for i in r.issues if i.level in ("error", "warning"))
        note = tr(", 가이드라인 확인 필요 {0}건 (clips.json)").format(warnings) if warnings else ""
        if getattr(self, "last_compilation", None) is not None:
            note += tr(", 모음 영상 {0}").format(self.last_compilation.path.name)
        quiet = sum(r.removed for r in value)
        if quiet >= 0.5:
            note += tr(", 조용한 부분 {0:.0f}초 줄임").format(quiet)
        where = value[0].path.parent if value else self.output_edit.text()
        self._set_busy(False, tr("클립 {0}개 저장됨: {1}{2}").format(len(value), where, note))
        self.set_mood("cut")
        if self.source_url():  # the footage is on disk now, so the still can be shown
            self.refresh_preview()

    # ------------------------------------------------------------------ upload
    def upload_candidate(self):
        """The exported clip that goes with the selected row (else the first one), or ``None``."""
        if not self.last_results:
            return None
        index = self.timeline.current
        if 0 <= index < len(self.timeline.highlights):
            chosen = self.timeline.highlights[index]
            for result in self.last_results:
                if result.highlight is chosen:
                    return result
        return self.last_results[0]

    def open_upload(self):
        """Open the upload form, filled in from the exported clip and its description file."""
        from .upload import UploadDialog

        clip = self.upload_candidate()
        video = description = ""
        if clip is not None:
            video = str(clip.path)
            if clip.description is not None and clip.description.is_file():
                description = clip.description.read_text(encoding="utf-8")
        title = str((self.result.source or {}).get("title", "")) if self.result is not None else ""
        self.upload_dialog = UploadDialog(video, title=title, description=description, parent=self)
        self.upload_dialog.dialogs = self.dialogs
        self.upload_dialog.show()
        return self.upload_dialog
