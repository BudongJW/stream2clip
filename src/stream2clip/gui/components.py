"""What the features need on this PC, in a window: the report of ``stream2clip setup`` with buttons.

Each row says whether a component is there, what it is for and how to get it. ffmpeg and the face
model can be fetched from here; "look again" repeats the check after something was installed by
hand, and the latest release can be asked for. The checks run in a thread: looking for OBS and
starting ffmpeg take a moment.
"""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QCloseEvent, QDesktopServices
from PySide6.QtWidgets import QDialog, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .. import __version__, tools
from ..i18n import mark, shown, tr
from .qt import app_icon, mascot

__all__ = ["ComponentsDialog", "short_path"]

_STATES = {"ok": mark("있음"), "missing": mark("없음"), "optional": mark("없음(선택)"), "later": mark("자동")}


def short_path(text: str) -> str:
    """A path as it is shown: the user's own folder is written ``~`` (shorter, and nobody's name ends up in a picture)."""
    home = str(Path.home())
    return text.replace(home, "~").replace(home.replace("\\", "/"), "~") if home and len(home) > 3 else text


class ComponentsDialog(QDialog):
    #: Something was installed from here: whoever opened the window may want to look again.
    changed = Signal()
    _loaded = Signal(object, str)
    _note = Signal(str)
    _finished = Signal(str, str, str)  # what was asked for, what to show, error

    def __init__(self, parent: QWidget | None = None, *, obs_host: str = "127.0.0.1", obs_port: int = 4455) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("구성요소 점검"))
        self.setWindowIcon(app_icon())
        self.obs = (obs_host, obs_port)
        self.busy = False
        self.found: list[tools.Component] = []
        self.badges: dict[str, QLabel] = {}
        self.actions: dict[str, QPushButton] = {}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 16)
        outer.setSpacing(12)
        head = QHBoxLayout()
        head.setSpacing(12)
        self.mascot_label = QLabel()
        self.mascot_label.setPixmap(mascot("turn_right", 48))  # looks at the heading beside it
        head.addWidget(self.mascot_label)
        head.addWidget(QLabel(tr("기능별로 필요한 구성요소와 이 PC의 상태"), objectName="Muted"), 1)
        outer.addLayout(head)
        card = QWidget(objectName="Card")
        self.grid = QGridLayout(card)
        self.grid.setContentsMargins(14, 12, 14, 12)
        self.grid.setHorizontalSpacing(12)
        self.grid.setVerticalSpacing(10)
        self.grid.setColumnStretch(1, 1)
        outer.addWidget(card, 1)

        self.summary = QLabel(objectName="Status")
        self.summary.setWordWrap(True)
        outer.addWidget(self.summary)
        row = QHBoxLayout()
        self.update_label = QLabel(objectName="Muted")
        row.addWidget(self.update_label, 1)
        self.update_open = QPushButton(tr("내려받기 페이지 열기"), objectName="Primary")
        self.update_open.clicked.connect(self.open_update_page)
        self.update_open.setVisible(False)
        row.addWidget(self.update_open)
        self.update_button = QPushButton(tr("새 버전 확인"))
        self.update_button.setToolTip(tr("GitHub의 최신 릴리즈 번호 조회. 사용자와 PC에 관한 정보는 보내지 않음"))
        self.update_button.clicked.connect(self.check_update)
        row.addWidget(self.update_button)
        self.refresh_button = QPushButton(tr("다시 확인"))
        self.refresh_button.clicked.connect(self.refresh)
        row.addWidget(self.refresh_button)
        close = QPushButton(tr("닫기"))
        close.clicked.connect(self.close)
        row.addWidget(close)
        outer.addLayout(row)

        self._loaded.connect(self._show)
        self._note.connect(self.summary.setText)
        self._finished.connect(self._on_finished)
        self.setMinimumWidth(680)
        self.refresh()

    # ------------------------------------------------------------------ what tests replace
    def load(self) -> list[tools.Component]:
        """Look at this PC (tests replace this)."""
        return tools.components(obs=self.obs)

    def install_ffmpeg(self, on_progress, cancelled) -> None:
        """Download ffmpeg into the user's tools folder (tests replace this)."""
        tools.install_ffmpeg(on_progress=on_progress, cancelled=cancelled)

    def download_model(self) -> None:
        """Download the face detection model (tests replace this)."""
        from ..detect import ensure_model

        ensure_model()

    def fetch_release(self):
        """The newer release, or ``None`` when this is the latest (tests replace this)."""
        from .. import updates

        return updates.check_for_update()

    def open_url(self, url: str) -> None:
        """Open a page in the browser (tests replace this)."""
        QDesktopServices.openUrl(QUrl(url))

    # ------------------------------------------------------------------ the list
    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        for button in (self.refresh_button, self.update_button, *self.actions.values()):
            button.setEnabled(not busy)

    def _start(self, work) -> None:
        self._set_busy(True)
        self._thread = threading.Thread(target=work, name="stream2clip-components", daemon=True)
        self._thread.start()

    def _emit(self, signal, *args) -> None:
        try:
            signal.emit(*args)
        except RuntimeError:  # the window was closed meanwhile
            pass

    def refresh(self) -> None:
        """Look again and redraw the rows."""
        if self.busy:
            return
        self.summary.setText(tr("확인 중"))

        def work() -> None:
            try:
                self._emit(self._loaded, self.load(), "")
            except Exception as exc:  # shown instead of the list
                self._emit(self._loaded, [], str(exc) or type(exc).__name__)

        self._start(work)

    def _show(self, found: list, error: str) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self.found = list(found)
        self.badges, self.actions = {}, {}
        for line, item in enumerate(self.found):
            badge = QLabel(_shown_state(item.state), objectName={"ok": "StateOk", "missing": "StateMissing"}.get(item.state, "StateOther"))
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setMinimumWidth(78)
            self.grid.addWidget(badge, line, 0, Qt.AlignmentFlag.AlignTop)
            self.badges[item.key] = badge
            lines = [f"<b>{_plain(item.name)}</b>&nbsp;&nbsp;{_plain(item.use)}"]
            if item.detail:
                lines.append(_breakable(_plain(short_path(item.detail))))  # a long path wraps instead of running out of the window
            if item.fix:
                lines.append(_plain(tr("해결 방법") + ": " + item.fix))
            text = QLabel("<br>".join(lines))
            text.setTextFormat(Qt.TextFormat.RichText)
            text.setWordWrap(True)
            if item.detail:
                text.setToolTip(short_path(item.detail))
            self.grid.addWidget(text, line, 1)
            action = self._action_for(item)
            if action is not None:
                self.grid.addWidget(action, line, 2, Qt.AlignmentFlag.AlignTop)
                self.actions[item.key] = action
        self._set_busy(False)
        if error:
            self.summary.setText(tr("확인 실패: {0}").format(error.splitlines()[0][:120]))
            return
        absent = tools.missing_required(self.found)
        self.summary.setText(tr("필수 구성요소 없음: {0}").format(", ".join(item.name for item in absent)) if absent else tr("필수 구성요소 모두 있음"))

    def _action_for(self, item: tools.Component) -> QPushButton | None:
        if item.key == "ffmpeg" and item.state == "missing" and tools.can_install_ffmpeg():
            button = QPushButton(tr("ffmpeg 내려받기 ({0} MB)").format(tools.FFMPEG_BUILD.megabytes), objectName="Primary")
            button.clicked.connect(self.fetch_ffmpeg)
            return button
        if item.key == "model" and item.state == "later":
            button = QPushButton(tr("지금 내려받기 (12 MB)"))
            button.clicked.connect(self.fetch_model)
            return button
        return None

    # ------------------------------------------------------------------ fetching
    def fetch_ffmpeg(self) -> None:
        if self.busy:
            return
        self._stop.clear()
        self.summary.setText(tr("ffmpeg 내려받는 중"))
        seen = [-1]

        def progress(done: int, total: int) -> None:
            percent = int(done * 100 / total) if total else 0
            if percent != seen[0]:
                seen[0] = percent
                self._emit(self._note, tr("ffmpeg 내려받는 중: {0}% ({1} / {2} MB)").format(percent, round(done / 1e6), round(total / 1e6)))

        def work() -> None:
            try:
                self.install_ffmpeg(progress, self._stop.is_set)
                self._emit(self._finished, "ffmpeg", "", "")
            except Exception as exc:
                self._emit(self._finished, "ffmpeg", "", str(exc) or type(exc).__name__)

        self._start(work)

    def fetch_model(self) -> None:
        if self.busy:
            return
        self.summary.setText(tr("얼굴 검출 모델 내려받는 중"))

        def work() -> None:
            try:
                self.download_model()
                self._emit(self._finished, "model", "", "")
            except Exception as exc:
                self._emit(self._finished, "model", "", str(exc) or type(exc).__name__)

        self._start(work)

    def check_update(self) -> None:
        if self.busy:
            return
        self.update_label.setText(tr("새 버전 확인 중"))
        self.update_open.setVisible(False)

        def work() -> None:
            try:
                release = self.fetch_release()
                self._emit(self._finished, "update", release.version if release else "", "")
            except Exception as exc:
                self._emit(self._finished, "update", "", str(exc) or type(exc).__name__)

        self._start(work)

    def _on_finished(self, what: str, value: str, error: str) -> None:
        self._set_busy(False)
        if what == "update":
            if error:
                self.update_label.setText(tr("새 버전 확인 실패: {0}").format(error.splitlines()[0][:100]))
            elif value:
                self.update_label.setText(tr("새 버전 {0} 있음 (현재 {1})").format(value, __version__))
                self.update_open.setVisible(True)
            else:
                self.update_label.setText(tr("최신 버전 사용 중 ({0})").format(__version__))
            return
        if error:
            self.summary.setText(tr("내려받기 실패: {0}").format(error.splitlines()[0][:120]))
            return
        self.changed.emit()
        self.refresh()

    def open_update_page(self) -> None:
        from .. import updates

        self.open_url(updates.DOWNLOAD_PAGE)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self._stop.set()  # a download in progress stops at the next block
        if self._thread is not None:
            self._thread.join(timeout=5)
        super().closeEvent(event)


def _shown_state(state: str) -> str:
    return shown(_STATES[state]) if state in _STATES else state


def _breakable(text: str) -> str:
    """Let a path wrap after its separators (a zero-width space: nothing is seen where the line does not break)."""
    for separator in (chr(92), "/", "_"):
        text = text.replace(separator, separator + chr(0x200B))
    return text


def _plain(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
