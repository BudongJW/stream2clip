"""Highlights window: 방송 → 클립.

Pick a VOD and its chat replay, find the highlights, fine-tune each span by dragging
it on the timeline, look at a still preview with the chosen layout and export the
checked ones. All the work is done by the core (``pipeline.find_highlights`` /
``pipeline.make_clips``); this module only draws and collects settings.
"""

from __future__ import annotations

import threading
from pathlib import Path

import numpy as np
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QCloseEvent, QColor, QFont, QIcon, QMouseEvent, QPainter, QPaintEvent, QPen, QPixmap
from PySide6.QtWidgets import (
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
from ..layouts import LAYOUTS, VerticalLayout
from . import theme
from .qt import app_icon, mascot, pil_to_qimage
from .settings import load_section, save_section

__all__ = ["HighlightsWindow", "TimelineWidget", "default_clip_dir", "mood_for"]

_LAYOUT_LABELS = {"blur": "blur · 블러 배경", "center": "center · 가운데 채우기", "fit": "fit · 전체 보이기", "stack": "stack · 아바타 위 / 게임 아래", "none": "원본 화면 그대로"}
_STAGES = {
    "chat": "채팅 읽는 중…", "audio": "음량 분석 중… (영상 길이에 따라 수십 초)", "laughter": "웃음소리 찾는 중…",
    "singing": "노래 구간 찾는 중…", "detect": "하이라이트 찾는 중…",
}
_SINGING = [("off", "노래 구간 안 봄"), ("mark", "노래 구간 표시"), ("skip", "노래 구간 제외")]
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
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "영상과 채팅을 고르고 ‘하이라이트 찾기’를 누르세요")
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


class HighlightsWindow(QMainWindow):
    """Find, adjust, preview and export highlights."""

    _stage = Signal(str)
    _analysed = Signal(object)
    _previewed = Signal(int, object)
    _progress = Signal(int, int, str)
    _exported = Signal(object)
    _failed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("stream2clip · 방송 → 클립")
        self.setWindowIcon(app_icon())
        self.result: HighlightResult | None = None
        self.busy = False
        self.dialogs = True  # also show failures in a message box (tests turn this off)
        self.last_results: list = []
        self.upload_dialog = None
        self.last_dir = ""
        self._preview_token = 0

        root = QWidget(objectName="Root")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(20, 16, 20, 14)
        outer.setSpacing(10)
        outer.addWidget(QLabel("SOURCE", objectName="Eyebrow"))
        outer.addWidget(self._source_card())
        outer.addWidget(QLabel("HIGHLIGHTS", objectName="Eyebrow"))
        self.timeline = TimelineWidget()
        self.timeline.selected.connect(self._on_timeline_selected)
        self.timeline.changed.connect(self._on_span_changed)
        self.timeline.setToolTip("구간 가운데를 끌면 이동, 가장자리를 끌면 시작 · 끝 조정 / 휠 또는 구간 더블클릭으로 확대, 빈 곳 더블클릭으로 전체 보기")
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
        self.preview = QLabel("미리보기", objectName="Muted")
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
        self.status = QLabel("영상과 채팅 다시보기를 고르세요", objectName="Muted")
        bottom.addWidget(self.status, 1)
        self.progress = QProgressBar()
        self.progress.setFixedWidth(220)
        self.progress.setTextVisible(True)
        self.progress.setStyleSheet(f"QProgressBar {{ background: {theme.SURFACE_2}; border: 1px solid {theme.BORDER}; border-radius: 8px; text-align: center; }}"
                                    f"QProgressBar::chunk {{ background: {theme.LIVE_PINK}; border-radius: 7px; }}")
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        bottom.addWidget(self.progress)
        self.export_button = QPushButton("클립 내보내기", objectName="Primary")
        self.export_button.setMinimumHeight(38)
        self.export_button.clicked.connect(self.export)
        self.export_button.setEnabled(False)
        bottom.addWidget(self.export_button)
        self.upload_button = QPushButton("업로드…")
        self.upload_button.setMinimumHeight(38)
        self.upload_button.setToolTip("고른 클립(또는 다른 영상)을 YouTube에 올립니다. 기본은 비공개입니다.")
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

    # ------------------------------------------------------------------ layout
    def _path_row(self, grid: QGridLayout, row: int, column: int, label: str, placeholder: str, filters: str) -> QLineEdit:
        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        edit.setToolTip(placeholder)
        browse = QPushButton("찾기")
        browse.clicked.connect(lambda: self._browse(edit, filters))
        grid.addWidget(QLabel(label), row, column)
        grid.addWidget(edit, row, column + 1)
        grid.addWidget(browse, row, column + 2)
        return edit

    def _browse(self, edit: QLineEdit, filters: str) -> None:
        start = str(Path(edit.text()).parent) if edit.text() else (self.last_dir or str(Path.home()))
        path, _ = QFileDialog.getOpenFileName(self, "파일 고르기", start, filters)
        if path:
            edit.setText(path)
            self.last_dir = str(Path(path).parent)

    def _source_card(self) -> QWidget:
        card = QWidget(objectName="Card")
        grid = QGridLayout(card)
        grid.setContentsMargins(14, 12, 14, 12)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        self.video_edit = self._path_row(grid, 0, 0, "영상", "다시보기 파일 (video.mp4)", "Video (*.mp4 *.mkv *.webm *.mov *.flv *.ts);;All files (*)")
        self.chat_edit = self._path_row(grid, 0, 3, "채팅", "yt-dlp live_chat.json · chat-downloader · TwitchDownloader · CSV", "Chat (*.json *.jsonl *.csv);;All files (*)")
        self.info_edit = self._path_row(grid, 1, 0, "정보", "(선택) yt-dlp info.json — 원본 제목 · URL · 많이 다시 본 구간", "JSON (*.json);;All files (*)")
        self.subs_edit = self._path_row(grid, 1, 3, "자막", "(선택) SRT · WebVTT — YouTube 자동 자막도 됩니다", "Subtitles (*.vtt *.srt *.json);;All files (*)")
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(4, 1)
        grid.setColumnMinimumWidth(3, 44)
        options = QHBoxLayout()
        options.setSpacing(8)
        self.audio_check = QCheckBox("음량도 사용", checked=True)
        options.addWidget(self.audio_check)
        self.laughter_check = QCheckBox("웃음소리 (실험)")
        self.laughter_check.setToolTip("끊어지는 큰 소리(웃음 같은 소리)가 있는 장면에 점수를 더합니다. 다른 신호로 찾은 장면은 그대로 남습니다.")
        options.addWidget(self.laughter_check)
        self.singing_combo = QComboBox()
        for key, label in _SINGING:
            self.singing_combo.addItem(label, key)
        self.singing_combo.setToolTip("노래 방송(歌枠)은 곡 저작권 때문에 클립이 제한되는 경우가 많습니다.\n표시: 노래와 겹치는 하이라이트에 표시 / 제외: 대부분이 노래인 하이라이트는 뺌")
        options.addWidget(self.singing_combo)
        options.addSpacing(14)
        options.addWidget(QLabel("최대"))
        self.top_spin = QSpinBox(minimum=1, maximum=50, value=10)
        self.top_spin.setSuffix("개")
        options.addWidget(self.top_spin)
        options.addSpacing(14)
        options.addWidget(QLabel("임계값"))
        self.threshold_spin = QDoubleSpinBox(minimum=0.5, maximum=10.0, value=2.0, singleStep=0.1)
        self.threshold_spin.setToolTip("낮추면 더 많이, 높이면 확실한 장면만 찾습니다")
        options.addWidget(self.threshold_spin)
        options.addStretch(1)
        self.analyse_button = QPushButton("하이라이트 찾기", objectName="Primary")
        self.analyse_button.setMinimumHeight(34)
        self.analyse_button.clicked.connect(self.analyse)
        options.addWidget(self.analyse_button)
        grid.addLayout(options, 2, 0, 1, 6)
        return card

    def _export_card(self) -> QWidget:
        card = QWidget(objectName="Card")
        grid = QGridLayout(card)
        grid.setContentsMargins(14, 12, 14, 12)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        grid.addWidget(QLabel("레이아웃"), 0, 0)
        self.layout_combo = QComboBox()
        for key in ("blur", "stack", "center", "fit", "none"):
            self.layout_combo.addItem(_LAYOUT_LABELS[key], key)
        self.layout_combo.currentIndexChanged.connect(self._on_layout_changed)
        grid.addWidget(self.layout_combo, 0, 1, 1, 2)

        grid.addWidget(QLabel("아바타"), 1, 0)
        self.avatar_edit = QLineEdit()
        self.avatar_edit.setPlaceholderText("x,y,w,h (stack 레이아웃)")
        self.avatar_edit.editingFinished.connect(self.refresh_preview)
        grid.addWidget(self.avatar_edit, 1, 1)
        self.avatar_button = QPushButton("자동 찾기")
        self.avatar_button.setToolTip("애니메 얼굴 검출로 아바타 위치를 찾습니다 (처음 한 번 12MB 모델 다운로드)")
        self.avatar_button.clicked.connect(self.find_avatar)
        grid.addWidget(self.avatar_button, 1, 2)

        grid.addWidget(QLabel("자막"), 2, 0)
        self.subs_combo = QComboBox()
        self.subs_combo.addItem("자막 파일 사용 (있으면)", "file")
        self.subs_combo.addItem("없음", "none")
        self.subs_combo.addItem("받아쓰기 · Whisper small", "small")
        self.subs_combo.addItem("받아쓰기 · Whisper medium", "medium")
        grid.addWidget(self.subs_combo, 2, 1, 1, 2)
        grid.addWidget(QLabel("언어"), 3, 0)
        self.language_edit = QLineEdit("ja")
        self.language_edit.setToolTip("자막 원문 언어 (ja, ko, en …) — 받아쓰기와 번역에 씁니다")
        grid.addWidget(self.language_edit, 3, 1)
        self.karaoke_check = QCheckBox("카라오케", checked=True)
        self.karaoke_check.setToolTip("말하는 단어에 맞춰 색이 바뀝니다 (번역한 자막에는 적용되지 않습니다)")
        grid.addWidget(self.karaoke_check, 3, 2)

        grid.addWidget(QLabel("번역"), 4, 0)
        self.translator_combo = QComboBox()
        self.translator_combo.setToolTip("번역 서비스는 내장돼 있지 않습니다. 설치한 번역기 플러그인을 고르거나,\ntranslate(texts, target, source) 함수가 있는 .py 파일을 고르세요 (examples/translators 참고).")
        self._fill_translators()
        self.translator_combo.activated.connect(self._on_translator_picked)
        grid.addWidget(self.translator_combo, 4, 1)
        translate_row = QHBoxLayout()
        translate_row.setSpacing(6)
        self.target_edit = QLineEdit("ko")
        self.target_edit.setToolTip("번역할 언어 (ko, en …)")
        self.target_edit.setFixedWidth(46)
        translate_row.addWidget(self.target_edit)
        self.bilingual_check = QCheckBox("원문 병기")
        self.bilingual_check.setToolTip("원문 줄 아래에 번역을 함께 넣습니다")
        translate_row.addWidget(self.bilingual_check)
        grid.addLayout(translate_row, 4, 2)

        grid.addWidget(QLabel("용어집"), 5, 0)
        self.glossary_edit = QLineEdit()
        self.glossary_edit.setPlaceholderText("(선택) 이름 고정 CSV · JSON")
        self.glossary_edit.setToolTip("source,target 두 열의 CSV 또는 JSON. 버튜버 이름처럼 번역기가 틀리기 쉬운 말을 고정합니다.")
        grid.addWidget(self.glossary_edit, 5, 1)
        pick_glossary = QPushButton("찾기")
        pick_glossary.clicked.connect(lambda: self._browse(self.glossary_edit, "Glossary (*.csv *.json);;All files (*)"))
        grid.addWidget(pick_glossary, 5, 2)

        grid.addWidget(QLabel("형식"), 6, 0)
        self.format_combo = QComboBox()
        for fmt in ("mp4", "webm", "webp", "gif"):
            self.format_combo.addItem(fmt.upper(), fmt)
        grid.addWidget(self.format_combo, 6, 1)
        self.agency_combo = QComboBox()
        for key in _AGENCIES:
            self.agency_combo.addItem(key or "가이드라인 없음", key)
        self.agency_combo.setToolTip("설명란과 업로드 전 점검에 쓸 기획사 프로필 (체크리스트일 뿐 법적 판단이 아닙니다)")
        grid.addWidget(self.agency_combo, 6, 2)

        grid.addWidget(QLabel("저장"), 7, 0)
        self.output_edit = QLineEdit(str(default_clip_dir()))
        grid.addWidget(self.output_edit, 7, 1)
        pick = QPushButton("폴더")
        pick.clicked.connect(self._pick_output)
        grid.addWidget(pick, 7, 2)
        grid.setRowStretch(8, 1)
        self._on_layout_changed()
        return card

    # ------------------------------------------------------------------ translator choice
    def _fill_translators(self, chosen: str = "") -> None:
        """Off, the installed plugins, a file chosen earlier, and "choose a file"."""
        from ..plugins import translators

        combo = self.translator_combo
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("번역 안 함", "")
        names = list(translators())
        for name in names:
            combo.addItem(name, name)
        if chosen and chosen not in names:
            from ..translation import split_translator_spec

            target, attr = split_translator_spec(chosen)
            label = (Path(target).name if target.lower().endswith(".py") else target) + ("" if attr == "translate" else f":{attr}")
            combo.addItem(label, chosen)
        combo.addItem("번역기 파일 고르기… (.py)", _PICK_FILE)
        combo.setCurrentIndex(max(0, combo.findData(chosen)))
        combo.blockSignals(False)

    def _on_translator_picked(self, index: int) -> None:
        if self.translator_combo.itemData(index) != _PICK_FILE:
            return
        path, _ = QFileDialog.getOpenFileName(self, "번역기 파일", self.last_dir or str(Path.home()), "Python (*.py)")
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
        for check, key in ((self.audio_check, "audio"), (self.laughter_check, "laughter"), (self.karaoke_check, "karaoke"), (self.bilingual_check, "bilingual")):
            if isinstance(saved.get(key), bool):
                check.setChecked(saved[key])
        for combo, key in ((self.singing_combo, "singing"), (self.layout_combo, "layout"), (self.subs_combo, "subtitles"), (self.format_combo, "format"), (self.agency_combo, "agency")):
            index = combo.findData(saved.get(key)) if isinstance(saved.get(key), str) else -1
            if index >= 0:
                combo.setCurrentIndex(index)
        for edit, key in ((self.language_edit, "language"), (self.target_edit, "target"), (self.glossary_edit, "glossary"), (self.output_edit, "output")):
            if isinstance(saved.get(key), str) and saved[key]:
                edit.setText(saved[key])
        if isinstance(saved.get("top"), int):
            self.top_spin.setValue(saved["top"])
        if isinstance(saved.get("threshold"), (int, float)):
            self.threshold_spin.setValue(float(saved["threshold"]))
        if isinstance(saved.get("translator"), str) and saved["translator"]:
            self.set_translator(saved["translator"])
        if isinstance(saved.get("last_dir"), str):
            self.last_dir = saved["last_dir"]

    def remember(self) -> None:
        save_section("highlights", {
            "audio": self.audio_check.isChecked(), "laughter": self.laughter_check.isChecked(), "singing": self.singing_combo.currentData(),
            "top": self.top_spin.value(), "threshold": round(self.threshold_spin.value(), 2),
            "layout": self.layout_combo.currentData(), "subtitles": self.subs_combo.currentData(), "language": self.language_edit.text().strip(),
            "karaoke": self.karaoke_check.isChecked(), "translator": self.translator_choice(), "target": self.target_edit.text().strip(),
            "glossary": self.glossary_edit.text().strip(), "bilingual": self.bilingual_check.isChecked(),
            "format": self.format_combo.currentData(), "agency": self.agency_combo.currentData(), "output": self.output_edit.text().strip(),
            "last_dir": self.last_dir,
        })

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self.remember()
        super().closeEvent(event)

    def _pick_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "저장 폴더", self.output_edit.text())
        if path:
            self.output_edit.setText(path)

    # ------------------------------------------------------------------ helpers
    def set_paths(self, *, video: str = "", chat: str = "", info: str = "", subtitles: str = "", output: str = "") -> None:
        for edit, value in ((self.video_edit, video), (self.chat_edit, chat), (self.info_edit, info), (self.subs_edit, subtitles), (self.output_edit, output)):
            if value:
                edit.setText(str(value))

    def set_mood(self, mood: str) -> None:
        """Kiri next to the status line: wink = ready, focus = working, cut = clips done, surprised = failed."""
        if mood != self.mood:
            self.mood = mood
            self.mascot_label.setPixmap(mascot(mood, 44))

    def _set_busy(self, busy: bool, message: str | None = None) -> None:
        self.busy = busy
        if busy:
            self.set_mood("focus")
        self.analyse_button.setEnabled(not busy)
        self.avatar_button.setEnabled(not busy and self.layout_combo.currentData() == "stack")
        self.export_button.setEnabled(not busy and bool(self.checked_highlights()))
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
        self._set_busy(False, f"실패: {message.splitlines()[0][:120]}")
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
        if kind == "stack":
            text = self.avatar_edit.text().strip()
            if not text:
                raise ValueError("stack 레이아웃은 아바타 위치가 필요합니다. ‘자동 찾기’를 누르거나 x,y,w,h를 입력하세요.")
            avatar = Region.parse(text)
        assert kind in LAYOUTS
        return VerticalLayout(kind, avatar=avatar)

    def checked_highlights(self) -> list[Highlight]:
        return [self.timeline.highlights[i] for i in range(self.list.count()) if self.list.item(i).checkState() == Qt.CheckState.Checked]

    def _item_text(self, h: Highlight) -> str:
        head = f"#{h.rank:02d}   {_clock(h.start)} – {_clock(h.end)}   ({h.duration:.0f}초 · 점수 {h.score:.1f})"
        return head + ("\n" + " / ".join(h.reasons) if h.reasons else "")

    # ------------------------------------------------------------------ analyse
    def analyse(self) -> None:
        if self.busy:
            return
        video, chat, info = self.video_edit.text().strip(), self.chat_edit.text().strip(), self.info_edit.text().strip()
        if not video:
            self._on_failed("영상 파일을 고르세요.")
            return
        config = HighlightConfig(threshold=self.threshold_spin.value(), top=self.top_spin.value())
        audio = self.audio_check.isChecked()
        laughter = self.laughter_check.isChecked()
        singing = self.singing_combo.currentData()
        self.remember()
        self._set_busy(True, "분석 시작…")
        self.progress.setRange(0, 0)  # busy indicator

        def work() -> None:
            from ..pipeline import find_highlights

            source = {}
            if info:
                from ..sources import load_info, source_from_info

                src = source_from_info(load_info(info))
                source = {"url": src.url, "title": src.title}
            result = find_highlights(video, chat=chat or None, info=info or None, audio=audio, laughter=laughter, config=config, source=source, on_stage=self._stage.emit)
            if singing != "off":
                from ..audio import singing_sections
                from ..highlights import mark_singing

                self._stage.emit("singing")
                mark_singing(result, [(s.start, s.end) for s in singing_sections(video)], drop=singing == "skip")
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
        chat = f"채팅 {result.messages:,}개 · " if result.messages else ""
        hint = "" if count else " — 임계값을 낮춰 보세요"
        sung = f" · 노래 구간 {len(result.songs)}곳" if result.songs is not None else ""
        self._set_busy(False, f"{chat}{_clock(result.duration)} 분석 → 하이라이트 {count}개{sung}{hint}")
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
        stack = self.layout_combo.currentData() == "stack"
        self.avatar_edit.setEnabled(stack)
        self.avatar_button.setEnabled(stack and not self.busy)
        if self.result is not None:
            self.refresh_preview()

    def refresh_preview(self) -> None:
        """Render one frame of the selected highlight with the current layout (in the background)."""
        index = self.timeline.current
        video = self.video_edit.text().strip()
        if index < 0 or not video:
            self.preview.setPixmap(QPixmap())
            self.preview.setText("미리보기")
            return
        try:
            layout = self.layout_choice()
        except ValueError:
            self.preview.setPixmap(QPixmap())
            self.preview.setText("아바타 위치를\n정하면 보입니다")
            return
        if layout is not None:  # a small canvas is enough for a still and renders quickly
            layout = VerticalLayout(layout.kind, 360, 640, avatar=layout.avatar, game=layout.game, split=layout.split)
        moment = self.timeline.highlights[index].peak
        self._preview_token += 1
        token = self._preview_token

        def work() -> None:
            from ..export import grab_frames

            try:
                frames = grab_frames(video, [moment], layout=layout)
            except Exception:  # a preview that cannot be made is not worth a dialog
                frames = []
            self._previewed.emit(token, frames[0] if frames else None)

        threading.Thread(target=work, name="stream2clip-preview", daemon=True).start()

    def _on_previewed(self, token: int, frame: "np.ndarray | None") -> None:
        if token != self._preview_token:
            return  # an older request finished late
        if frame is None:
            self.preview.setPixmap(QPixmap())
            self.preview.setText("미리보기를\n만들 수 없습니다")
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
        self._set_busy(True, "아바타 찾는 중…")

        def work() -> None:
            from ..detect import default_detector, suggest_avatar_for_video

            self._exported.emit(("avatar", suggest_avatar_for_video(video, default_detector())))

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
        info_path = self.info_edit.text().strip()
        agency = self.agency_combo.currentData()
        out_dir = self.output_edit.text().strip() or str(default_clip_dir())
        translator_spec = self.translator_choice()
        target = self.target_edit.text().strip() or "ko"
        glossary_path = self.glossary_edit.text().strip()
        bilingual = self.bilingual_check.isChecked()
        if translator_spec and not subs_path and model is None:
            self._on_failed("번역하려면 자막이 필요합니다. 자막 파일을 고르거나 받아쓰기를 켜세요.")
            return
        self.remember()
        self._set_busy(True, f"클립 {len(chosen)}개 내보내는 중…")
        self.progress.setRange(0, len(chosen))
        self.progress.setValue(0)

        def work() -> None:
            from ..compliance import get_profile
            from ..pipeline import make_clips
            from ..sources import load_info, source_from_info
            from ..subtitles import FasterWhisperTranscriber, load_subtitles

            cues = load_subtitles(subs_path) if subs_path else None
            transcriber = FasterWhisperTranscriber(model) if model else None
            source = source_from_info(load_info(info_path)) if info_path else None
            profile = get_profile(agency) if (agency or source) else None
            subtitle_translator = glossary = None
            if translator_spec:
                from ..translation import Glossary, get_translator

                subtitle_translator = get_translator(translator_spec)
                glossary = Glossary.load(glossary_path) if glossary_path else None
            results = make_clips(
                video, chosen, out_dir, options=options, cues=cues, transcriber=transcriber, language=language, karaoke=karaoke,
                subtitle_translator=subtitle_translator, translate_to=target, glossary=glossary, bilingual=bilingual,
                source=source, profile=profile,
                on_progress=lambda i, n, h: self._progress.emit(i - 1, n, f"[{i}/{n}] #{h.rank:02d} {_clock(h.start)} – {_clock(h.end)} 인코딩 중…"),
            )
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
                self._on_failed("아바타를 찾지 못했습니다. 같은 자리에 계속 나오는 얼굴이 없습니다. x,y,w,h를 직접 입력하세요.")
                return
            self.avatar_edit.setText(str(value.region))
            self._set_busy(False, f"아바타 {value.region} — 프레임 {value.hits}/{value.frames}장에서 확인")
            self.set_mood("wink")
            self.refresh_preview()
            return
        self.last_results = value
        self.progress.setRange(0, max(1, len(value)))
        self.progress.setValue(len(value))
        warnings = sum(1 for r in value for i in r.issues if i.level in ("error", "warning"))
        note = f" · 가이드라인 확인 필요 {warnings}건 (clips.json)" if warnings else ""
        where = value[0].path.parent if value else self.output_edit.text()
        self._set_busy(False, f"클립 {len(value)}개 저장됨: {where}{note}")
        self.set_mood("cut")

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
