"""The broadcast recorder window: keep it open while streaming, clip from what it wrote afterwards.

A thin shell over :func:`stream2clip.recorder.build_recorder`. The recorder runs in a
thread; the window looks at it twice a second (states of the chat, OBS and VTube Studio,
counts). A marker comes from the button, from F11 (opt-in, system-wide) or from a
VTube Studio hotkey. When the recording stops, the session opens in the highlights window
as the chat of the stream.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..i18n import tr
from .qt import app_icon, mascot
from .settings import load_section, save_section

__all__ = ["SessionWindow", "MARKER_KEY", "main"]

MARKER_KEY = "F11"
#: Different viewers typing !clip within 30 seconds that leave a marker, when viewer votes are on.
VIEWER_VOTES = 3


def _state_text(state: str, detail: str) -> str:
    words = {"off": tr("꺼짐"), "connecting": tr("연결 중"), "connected": tr("연결됨"), "waiting": tr("다시 연결 대기")}
    text = words.get(state, state)
    return f"{text}: {detail.splitlines()[0][:90]}" if detail and state == "waiting" else text


class SessionWindow(QWidget):
    """Start and stop a session recording; leave markers; see what is connected."""

    def __init__(self, *, save_dir: Path, obs: tuple[str, int, str] = ("127.0.0.1", 4455, ""), host: Any = None) -> None:
        super().__init__(None, Qt.WindowType.Window)
        self.setWindowTitle(tr("방송 기록기"))
        self.setWindowIcon(app_icon())
        self.setObjectName("Root")
        self.save_dir = Path(save_dir)
        self.obs_host, self.obs_port, self.obs_password = obs
        self.host = host  # the start window: its F-key registration and its highlights window
        self.recorder: Any = None
        self.path: Path | None = None
        self.last_path: Path | None = None
        self.error = ""
        self._thread: threading.Thread | None = None
        self._own_hotkeys: Any = None
        self.dialogs = True

        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 18, 22, 16)
        outer.setSpacing(12)
        top = QHBoxLayout()
        kiri = QLabel()
        kiri.setPixmap(mascot("focus", 52))
        top.addWidget(kiri)
        words = QVBoxLayout()
        words.addWidget(QLabel(tr("방송 기록기"), objectName="Title"))
        sub = QLabel(tr("방송 중 채팅, 표시, OBS 장면, VTube Studio 아바타를 기록해 두고 방송 후 클립 제작에 사용"), objectName="Muted")
        sub.setWordWrap(True)
        words.addWidget(sub)
        top.addLayout(words, 1)
        outer.addLayout(top)

        card = QWidget(objectName="Card")
        grid = QGridLayout(card)
        grid.setContentsMargins(14, 12, 14, 12)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        grid.addWidget(QLabel(tr("채팅")), 0, 0)
        self.chat_edit = QLineEdit()
        self.chat_edit.setPlaceholderText(tr("본인 채널의 CHZZK, SOOP, Twitch, YouTube 라이브 주소 (비우면 채팅 없이 기록)"))
        grid.addWidget(self.chat_edit, 0, 1, 1, 2)
        self.obs_check = QCheckBox(tr("OBS 장면, 송출과 녹화 시작 기록"))
        self.obs_check.setChecked(True)
        grid.addWidget(QLabel("OBS"), 1, 0)
        grid.addWidget(self.obs_check, 1, 1)
        self.obs_button = QPushButton(tr("연결 설정"))
        self.obs_button.clicked.connect(self.edit_obs)
        grid.addWidget(self.obs_button, 1, 2)
        grid.addWidget(QLabel("VTube Studio"), 2, 0)
        self.vts_check = QCheckBox(tr("아바타 위치와 표정 기록 (VTube Studio 설정에서 API 켜기)"))
        self.vts_check.setToolTip(tr("처음 연결할 때 VTube Studio에 표시되는 플러그인 허용 창에서 허용을 누르세요."))
        grid.addWidget(self.vts_check, 2, 1, 1, 2)
        grid.addWidget(QLabel(tr("VTS 소스")), 3, 0)
        self.source_edit = QLineEdit()
        self.source_edit.setPlaceholderText(tr("OBS에서 VTube Studio를 표시하는 소스 이름 (아바타 영역 자동 지정용)"))
        grid.addWidget(self.source_edit, 3, 1, 1, 2)
        grid.addWidget(QLabel(tr("표시")), 4, 0)
        marks = QHBoxLayout()
        self.replay_check = QCheckBox(tr("표시할 때 OBS 리플레이도 저장"))
        marks.addWidget(self.replay_check)
        self.hotkey_check = QCheckBox(MARKER_KEY)
        self.hotkey_check.setToolTip(tr("켜면 방송 중 어느 프로그램에서든 {0}로 표시를 남깁니다.\n켜 둔 동안 다른 프로그램은 {0}을 받지 못합니다.").format(MARKER_KEY))
        self.hotkey_check.toggled.connect(self._set_hotkey)
        marks.addWidget(self.hotkey_check)
        self.votes_check = QCheckBox(tr("시청자 투표"))
        self.votes_check.setToolTip(tr("시청자 {0}명이 30초 안에 !clip을 입력하면 표시를 남깁니다.").format(VIEWER_VOTES))
        marks.addWidget(self.votes_check)
        marks.addStretch(1)
        grid.addLayout(marks, 4, 1, 1, 2)
        grid.setColumnStretch(1, 1)
        outer.addWidget(card)

        buttons = QHBoxLayout()
        self.start_button = QPushButton(tr("기록 시작"), objectName="BigAction")
        self.start_button.clicked.connect(self.toggle)
        buttons.addWidget(self.start_button, 1)
        self.mark_button = QPushButton(tr("지금 표시"), objectName="BigAction")
        self.mark_button.setToolTip(tr("이 순간을 클립 후보로 표시합니다. 하이라이트 검출 시 항상 클립에 포함됩니다."))
        self.mark_button.setEnabled(False)
        self.mark_button.clicked.connect(self._mark_pressed)
        buttons.addWidget(self.mark_button, 1)
        outer.addLayout(buttons)

        state = QWidget(objectName="Card")
        rows = QGridLayout(state)
        rows.setContentsMargins(14, 10, 14, 10)
        self.state_labels: dict[str, QLabel] = {}
        for row, (key, name) in enumerate((("chat", tr("채팅")), ("obs", "OBS"), ("vts", "VTube Studio"))):
            rows.addWidget(QLabel(name), row, 0)
            label = QLabel(tr("꺼짐"), objectName="Muted")
            self.state_labels[key] = label
            rows.addWidget(label, row, 1)
        rows.setColumnStretch(1, 1)
        self.counts_label = QLabel("", objectName="Muted")
        rows.addWidget(self.counts_label, 3, 0, 1, 2)
        outer.addWidget(state)

        bottom = QHBoxLayout()
        self.status = QLabel(tr("저장 폴더: {0}").format(self.session_dir()), objectName="Muted")
        self.status.setWordWrap(True)
        bottom.addWidget(self.status, 1)
        folder = QPushButton(tr("폴더 열기"))
        folder.clicked.connect(self.open_folder)
        bottom.addWidget(folder)
        self.highlights_button = QPushButton(tr("하이라이트 찾기"))
        self.highlights_button.setToolTip(tr("방금 기록한 세션을 하이라이트 창의 채팅으로 엽니다."))
        self.highlights_button.setEnabled(False)
        self.highlights_button.clicked.connect(self.open_highlights)
        bottom.addWidget(self.highlights_button)
        outer.addLayout(bottom)

        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.refresh)
        self._restore()
        self.resize(640, 560)

    # ------------------------------------------------------------------ settings
    def _restore(self) -> None:
        saved = load_section("session")
        if isinstance(saved.get("chat"), str):
            self.chat_edit.setText(saved["chat"])
        if isinstance(saved.get("source"), str):
            self.source_edit.setText(saved["source"])
        for box, key in ((self.obs_check, "obs"), (self.vts_check, "vts"), (self.replay_check, "replay"), (self.hotkey_check, "hotkey"), (self.votes_check, "votes")):
            if isinstance(saved.get(key), bool):
                box.setChecked(saved[key])

    def remember(self) -> None:
        save_section("session", {
            "chat": self.chat_edit.text().strip(), "source": self.source_edit.text().strip(), "obs": self.obs_check.isChecked(),
            "vts": self.vts_check.isChecked(), "replay": self.replay_check.isChecked(), "hotkey": self.hotkey_check.isChecked(),
            "votes": self.votes_check.isChecked(),
        })

    def session_dir(self) -> Path:
        return self.save_dir / "sessions"

    def open_folder(self) -> None:
        folder = self.session_dir()
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(os.fspath(folder)))

    # Bound methods, not lambdas: a lambda holding the window in one of its own connections keeps it
    # alive until the interpreter exits, after the application, and destroying it then crashes.
    def _mark_pressed(self) -> None:
        self.mark("button")

    def _hotkey_pressed(self, _name: str = "") -> None:
        self.mark("hotkey")

    def edit_obs(self) -> None:
        from .launcher import ObsDialog

        dialog = ObsDialog(self.obs_host, self.obs_port, self.obs_password, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.obs_host = dialog.host_edit.text().strip() or "127.0.0.1"
            self.obs_port = dialog.port_spin.value()
            self.obs_password = dialog.password_edit.text()
            if self.host is not None:  # the start window's replay button uses the same OBS
                self.host.obs_host, self.host.obs_port, self.host.obs_password = self.obs_host, self.obs_port, self.obs_password

    # ------------------------------------------------------------------ the marker key
    def _set_hotkey(self, on: bool) -> None:
        """Take or give back the system-wide marker key (opt-in, like F10 for the replay)."""
        if self.host is not None and hasattr(self.host, "set_extra_hotkey"):
            self.host.set_extra_hotkey(MARKER_KEY, self._hotkey_pressed if on else None)
            return
        from .hotkeys import GlobalHotkeys

        if self._own_hotkeys is not None:
            self._own_hotkeys.unregister()
            self._own_hotkeys = None
        if on:
            self._own_hotkeys = GlobalHotkeys(self)
            self._own_hotkeys.register([MARKER_KEY])
            self._own_hotkeys.activated.connect(self._hotkey_pressed)

    # ------------------------------------------------------------------ recording
    def make_recorder(self, path: Path) -> Any:
        """The recorder for the current choices (tests replace this)."""
        from ..live import LiveConfig
        from ..recorder import build_recorder

        password = self.obs_password or os.environ.get("OBS_WEBSOCKET_PASSWORD") or None
        return build_recorder(
            path, chat=self.chat_edit.text().strip() or None, live_config=LiveConfig(),
            obs=(self.obs_host, self.obs_port, password) if self.obs_check.isChecked() else None,
            avatar_source=self.source_edit.text().strip() or None, vts_url="ws://127.0.0.1:8001" if self.vts_check.isChecked() else None,
            replay_on_marker=self.replay_check.isChecked(), viewer_votes=VIEWER_VOTES if self.votes_check.isChecked() else 0,
        )

    @property
    def running(self) -> bool:
        return self._thread is not None

    def toggle(self) -> None:
        if self.running:
            self.stop()
        else:
            self.start()

    def start(self) -> None:
        if self.running:
            return
        self.error = ""
        path = self.session_dir() / time.strftime("session-%Y%m%d-%H%M%S.jsonl")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            recorder = self.make_recorder(path)
        except (ValueError, OSError) as exc:
            self._fail(str(exc))
            return
        self.recorder, self.path = recorder, path
        self.remember()

        def work(rec: Any = recorder) -> None:
            try:
                rec.run(poll=0.1)
            except Exception as exc:  # shown when the window looks next
                self.error = str(exc)

        self._thread = threading.Thread(target=work, name="stream2clip-session", daemon=True)
        self._thread.start()
        self.start_button.setText(tr("기록 중지"))
        self.mark_button.setEnabled(True)
        self.highlights_button.setEnabled(False)
        for widget in (self.chat_edit, self.obs_check, self.obs_button, self.vts_check, self.source_edit, self.replay_check, self.votes_check):
            widget.setEnabled(False)
        self.status.setText(tr("기록 중: {0}").format(path))
        self.timer.start()
        self.refresh()

    def stop(self) -> None:
        if self.recorder is not None:
            self.recorder.stop()
            self.start_button.setEnabled(False)  # until the parts have let go
            self.status.setText(tr("기록 종료 중"))

    def mark(self, by: str = "button") -> None:
        if self.recorder is not None and self.running:
            self.recorder.mark(by)
            self.status.setText(tr("표시함 ({0})").format(time.strftime("%H:%M:%S")))

    def refresh(self) -> None:
        """Show the states and counts; notice when the recording thread has ended."""
        recorder = self.recorder
        if recorder is not None:
            names = {part.name: part for part in recorder.parts}
            for key, label in self.state_labels.items():
                part = names.get(key)
                label.setText(_state_text(part.status.state, part.status.detail) if part is not None else tr("사용 안 함"))
            counts = recorder.writer.counts
            self.counts_label.setText(tr("채팅 {0}, 급증 {1}, 표시 {2}, 아바타 외곽선 {3}").format(
                counts.get("chat", 0), counts.get("surge", 0), counts.get("marker", 0), counts.get("avatar_outline", 0)))
        if self._thread is not None and not self._thread.is_alive():
            self._finished()

    def _finished(self) -> None:
        self._thread = None
        self.timer.stop()
        self.last_path = self.path
        self.recorder = None
        self.start_button.setText(tr("기록 시작"))
        self.start_button.setEnabled(True)
        self.mark_button.setEnabled(False)
        for widget in (self.chat_edit, self.obs_check, self.obs_button, self.vts_check, self.source_edit, self.replay_check, self.votes_check):
            widget.setEnabled(True)
        if self.error:
            self._fail(self.error)
        else:
            self.status.setText(tr("기록 완료: {0}").format(self.last_path))
        self.highlights_button.setEnabled(self.last_path is not None and self.last_path.is_file())

    def _fail(self, message: str) -> None:
        self.status.setText(tr("기록 실패: {0}").format(message.splitlines()[0][:110]))
        if self.dialogs and self.isVisible():
            QMessageBox.warning(self, tr("방송 기록기"), message)

    def open_highlights(self):
        """The highlights window with the session as the stream's chat."""
        if self.last_path is None:
            return None
        if self.host is not None and hasattr(self.host, "open_highlights"):
            window = self.host.open_highlights()
        else:
            from .highlights import HighlightsWindow

            window = HighlightsWindow()
            window.show()
            self._highlights = window
        window.set_paths(chat=os.fspath(self.last_path))
        return window

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self.recorder is not None:
            self.recorder.stop()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        self.timer.stop()
        if self.hotkey_check.isChecked():
            self._set_hotkey(False)
        self.remember()
        super().closeEvent(event)


def main(argv: list[str] | None = None, *, run: Callable[[Any], int] | None = None) -> int:
    """``stream2clip-recorder``: the recorder window on its own, without the rest of the app."""
    import sys

    from .app import apply_saved_language, create_app
    from .recording import default_video_dir

    app = create_app(sys.argv[:1] if argv is None else argv)
    apply_saved_language()
    saved = load_section("record")
    folder = Path(saved["save_dir"]) if isinstance(saved.get("save_dir"), str) and saved["save_dir"] else default_video_dir()
    obs = load_section("obs")
    host = obs["host"] if isinstance(obs.get("host"), str) and obs["host"] else "127.0.0.1"
    port = obs["port"] if isinstance(obs.get("port"), int) and 1 <= obs["port"] <= 65535 else 4455
    window = SessionWindow(save_dir=folder, obs=(host, port, ""))
    window.show()
    return (run or (lambda a: a.exec()))(app)
