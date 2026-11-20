"""Main window: capture buttons, recording settings, global hotkeys (F8 / F9), OBS replay and live mode.

While ffmpeg is missing, a notice under the header says so and (on Windows) offers to download it.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QCloseEvent, QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import __version__, tools
from ..editor import Document
from ..ffmpeg import ExportOptions
from ..i18n import LANGUAGES, language, tr
from . import theme
from .editor import EditorWindow
from .hotkeys import GlobalHotkeys
from .qt import app_icon, mascot, pixmap
from .recording import RecordController, RecordSettings
from .settings import load_section, save_section

__all__ = ["LauncherWindow", "ObsDialog"]

_FORMATS = [("gif", "GIF", tr("어디서나 재생")), ("mp4", "MP4", tr("가벼운 용량")), ("webp", "WebP", tr("선명한 화질")), ("webm", "WebM", tr("투명 영상"))]
_LIVE_LEVELS = [("low", tr("낮음"), 4.5), ("normal", tr("보통"), 3.5), ("high", tr("높음"), 2.5)]  # key, label, threshold
_WIDTHS = [(tr("원본 크기"), None), ("1280px", 1280), ("960px", 960), ("720px", 720), ("480px", 480), ("320px", 320)]


def _eyebrow(text: str) -> QLabel:
    return QLabel(text, objectName="Eyebrow")


class ObsDialog(QDialog):
    """Where OBS listens (Tools > WebSocket Server Settings). The password is kept only while the app runs."""

    def __init__(self, host: str, port: int, password: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("OBS 연결"))
        form = QFormLayout(self)
        self.host_edit = QLineEdit(host)
        self.port_spin = QSpinBox(minimum=1, maximum=65535, value=port)
        self.password_edit = QLineEdit(password)
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText(tr("비워 두면 OBS_WEBSOCKET_PASSWORD 환경 변수"))
        form.addRow(tr("주소"), self.host_edit)
        form.addRow(tr("포트"), self.port_spin)
        form.addRow(tr("비밀번호"), self.password_edit)
        note = QLabel(tr("OBS 도구 메뉴의 WebSocket 서버 설정에서 서버를 켜고, 리플레이 버퍼를 시작해 두세요.\n비밀번호는 저장하지 않습니다."), objectName="Muted")
        note.setWordWrap(True)
        form.addRow(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)


class LauncherWindow(QMainWindow):
    _replay_done = Signal(str)
    _replay_failed = Signal(str)
    _live_note = Signal(str, str)
    _ffmpeg_progress = Signal(int, int)
    _ffmpeg_done = Signal(str)
    _update_answer = Signal(str, str)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("stream2clip")
        self.setWindowIcon(app_icon())
        self.editors: list[EditorWindow] = []
        self.settings = RecordSettings()
        self.obs_host, self.obs_port, self.obs_password = "127.0.0.1", 4455, ""
        self.replay_busy = False
        self.live_running = False
        self.live_clips = 0
        self.live_poll = 1.0  # seconds between two looks at the chat
        self._live_stop = threading.Event()
        self._live_thread: threading.Thread | None = None
        self.ffmpeg_busy = False
        self._ffmpeg_stop = threading.Event()
        self._ffmpeg_thread: threading.Thread | None = None
        self.dialogs = True  # show failures in a message box too (tests turn this off)

        root = QWidget(objectName="Root")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(28, 24, 28, 20)
        outer.setSpacing(14)

        header = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(pixmap("lockup-on-dark.png").scaledToHeight(48, Qt.TransformationMode.SmoothTransformation))
        header.addWidget(logo)
        header.addStretch(1)
        tagline = QLabel(tr("화면 캡쳐, 녹화, 방송 클립 제작"), objectName="Muted")
        header.addWidget(tagline)
        self.components_dialog = None
        self.components_button = QPushButton(tr("구성요소 점검"))
        self.components_button.setToolTip(tr("ffmpeg, OBS 연결 등 기능별로 필요한 구성요소가 이 PC에 있는지 확인"))
        self.components_button.clicked.connect(self.open_components)
        header.addWidget(self.components_button)
        outer.addLayout(header)
        self.ffmpeg_notice = self._ffmpeg_notice()
        outer.addWidget(self.ffmpeg_notice)
        self.update_notice = self._update_notice()
        outer.addWidget(self.update_notice)

        outer.addWidget(_eyebrow(tr("캡쳐")))
        outer.addWidget(self._capture_card())
        outer.addWidget(_eyebrow(tr("녹화")))
        outer.addWidget(self._record_card())
        outer.addWidget(_eyebrow(tr("클립")))
        outer.addWidget(self._clips_card())

        footer = QHBoxLayout()
        self.status = QLabel(objectName="Muted")
        footer.addWidget(self.status, 1)
        open_folder = QPushButton(tr("저장 폴더 열기"))
        open_folder.clicked.connect(lambda: self._open_dir(self.settings.save_dir))
        change = QPushButton(tr("폴더 변경"))
        change.clicked.connect(self._change_dir)
        footer.addWidget(open_folder)
        footer.addWidget(change)
        self.language_combo = QComboBox()
        self.language_combo.setToolTip("언어 / 言語 / Language")
        for code, name in LANGUAGES.items():
            self.language_combo.addItem(name, code)
        self.language_combo.setCurrentIndex(max(0, self.language_combo.findData(language())))
        self.language_combo.activated.connect(self._set_language)
        footer.addWidget(self.language_combo)
        outer.addLayout(footer)
        self.setCentralWidget(root)
        self._restore()
        self._replay_done.connect(self._on_replay_done)
        self._replay_failed.connect(self._on_replay_failed)
        self._live_note.connect(self._on_live)
        self._ffmpeg_progress.connect(self._on_ffmpeg_progress)
        self._ffmpeg_done.connect(self._on_ffmpeg_done)
        self._update_answer.connect(self._on_update_answer)

        self.controller = RecordController(lambda: self.settings, self)
        self.controller.stateChanged.connect(self._on_record_state)
        self.controller.finished.connect(self._on_record_finished)
        self.controller.failed.connect(self._on_record_failed)

        self.hotkeys = GlobalHotkeys(self)
        backend = self.hotkeys.register(self._hotkey_names())
        self.hotkeys.activated.connect(self._on_hotkey)
        if backend == "none":
            QShortcut(QKeySequence("F8"), self, activated=self.capture_region)
            QShortcut(QKeySequence("F9"), self, activated=self.controller.toggle)
        self._hotkey_note = tr("F8 영역 캡쳐, F9 녹화 시작/정지") + ("" if backend != "none" else tr(" (창이 활성일 때)"))
        self._idle_status = tr("{0}, 저장: {1}").format(self._hotkey_note, self.settings.save_dir)
        self.status.setText(self._idle_status)
        self.resize(760, 780)
        self.setAcceptDrops(True)  # an image opens in the editor, stream files go to the highlights window
        self.check_ffmpeg()
        self.check_updates()

    # ------------------------------------------------------------------ components
    def open_components(self):
        """The window that lists what the features need on this PC; ffmpeg fetched there makes the notice here go away."""
        from .components import ComponentsDialog

        if self.components_dialog is None:
            self.components_dialog = ComponentsDialog(self, obs_host=self.obs_host, obs_port=self.obs_port)
            self.components_dialog.changed.connect(self.check_ffmpeg)
        else:
            self.components_dialog.obs = (self.obs_host, self.obs_port)  # where OBS is looked for may have been changed since
            self.components_dialog.refresh()
        self.components_dialog.show()
        self.components_dialog.raise_()
        self.components_dialog.activateWindow()
        return self.components_dialog

    # ------------------------------------------------------------------ newer release
    def _update_notice(self) -> QWidget:
        """The row shown when a newer release exists: open the download page, skip that version, or stop asking."""
        card = QWidget(objectName="Notice")
        row = QHBoxLayout(card)
        row.setContentsMargins(14, 10, 14, 10)
        row.setSpacing(10)
        self.update_version, self.update_url = "", ""
        self._update_thread: threading.Thread | None = None
        row.addWidget(self._notice_mascot())
        self.update_label = QLabel()
        self.update_label.setWordWrap(True)
        row.addWidget(self.update_label, 1)
        self.update_open = QPushButton(tr("내려받기 페이지 열기"), objectName="Primary")
        self.update_open.clicked.connect(self.open_update_page)
        row.addWidget(self.update_open)
        self.update_skip = QPushButton(tr("이 버전 건너뛰기"))
        self.update_skip.clicked.connect(self.skip_update)
        row.addWidget(self.update_skip)
        self.update_off = QPushButton(tr("알림 끄기"))
        self.update_off.setToolTip(tr("새 버전 확인 중지. 설정 파일(settings.json)의 update_check 항목을 지우면 다시 확인"))
        self.update_off.clicked.connect(self.stop_update_checks)
        row.addWidget(self.update_off)
        card.setVisible(False)
        return card

    def _app_settings(self, **changes) -> dict:
        """The app's own section of the settings; ``changes`` are saved without dropping what else is there."""
        data = load_section("app")
        if changes:
            data.update(changes)
            save_section("app", data)
        return data

    def fetch_release(self):
        """The newer release, or ``None`` when this is the latest (tests replace this)."""
        from .. import updates

        return updates.check_for_update()

    def open_url(self, url: str) -> None:
        """Open a page in the browser (tests replace this)."""
        QDesktopServices.openUrl(QUrl(url))

    def check_updates(self, *, force: bool = False, now: float | None = None) -> bool:
        """Ask, at most once a day, whether a newer release exists; returns whether a request was started.

        Nothing is asked when it was turned off (the notice's button, or ``STREAM2CLIP_NO_UPDATE_CHECK``).
        An answer from earlier today is shown again without asking.
        """
        from .. import updates

        saved = self._app_settings()
        if not updates.enabled() or saved.get("update_check") is False:
            return False
        known, page = saved.get("update_latest"), saved.get("update_url")
        if isinstance(known, str) and known:
            self.show_update(known, page if isinstance(page, str) else "")
        now = time.time() if now is None else now
        last = saved.get("update_checked")
        if not force and isinstance(last, (int, float)) and 0 <= now - last < 86400:
            return False

        def work() -> None:
            try:
                release = self.fetch_release()
            except Exception:  # offline, or an answer that makes no sense: nothing to say, ask again next time
                return
            try:
                self._update_answer.emit(release.version if release else "", release.url if release else "")
            except RuntimeError:  # the window was closed meanwhile
                pass

        self._update_thread = threading.Thread(target=work, name="stream2clip-update", daemon=True)
        self._update_thread.start()
        return True

    def _on_update_answer(self, version: str, url: str) -> None:
        self._app_settings(update_checked=time.time(), update_latest=version, update_url=url)
        self.show_update(version, url)

    def show_update(self, version: str, url: str = "") -> None:
        """Show the notice for a release that is newer than this program and was not skipped; hide it otherwise."""
        from .. import updates

        wanted = bool(version) and updates.is_newer(version) and self._app_settings().get("update_skipped") != version
        self.update_notice.setVisible(wanted)
        if wanted:
            self.update_version, self.update_url = version, url or updates.RELEASES_PAGE
            self.update_label.setText(tr("새 버전 {0} 있음 (현재 {1})").format(version, __version__))

    def open_update_page(self) -> None:
        from .. import updates

        self.open_url(updates.DOWNLOAD_PAGE)

    def skip_update(self) -> None:
        self._app_settings(update_skipped=self.update_version)
        self.update_notice.setVisible(False)

    def stop_update_checks(self) -> None:
        self._app_settings(update_check=False)
        self.update_notice.setVisible(False)
        self.status.setText(tr("새 버전 알림 꺼짐"))

    # ------------------------------------------------------------------ ffmpeg
    def _ffmpeg_notice(self) -> QWidget:
        """The row shown while ffmpeg is missing: what it is needed for, a download button (Windows) and "look again"."""
        build = tools.FFMPEG_BUILD
        card = QWidget(objectName="Notice")
        row = QHBoxLayout(card)
        row.setContentsMargins(14, 10, 14, 10)
        row.setSpacing(10)
        row.addWidget(self._notice_mascot())
        self.ffmpeg_label = QLabel()
        self.ffmpeg_label.setWordWrap(True)
        row.addWidget(self.ffmpeg_label, 1)
        self.ffmpeg_button = QPushButton(tr("ffmpeg 내려받기 ({0} MB)").format(build.megabytes), objectName="Primary")
        self.ffmpeg_button.setToolTip(tr("ffmpeg.org가 안내하는 Windows용 빌드 {0}을 GitHub에서 내려받아 SHA-256 확인 후 사용자 폴더에 저장").format(build.version))
        self.ffmpeg_button.clicked.connect(self.fetch_ffmpeg)
        self.ffmpeg_button.setVisible(tools.can_install_ffmpeg())
        row.addWidget(self.ffmpeg_button)
        self.ffmpeg_again = QPushButton(tr("다시 확인"))
        self.ffmpeg_again.setToolTip(tr("ffmpeg를 직접 설치한 후 다시 확인"))
        self.ffmpeg_again.clicked.connect(self.check_ffmpeg)
        row.addWidget(self.ffmpeg_again)
        return card

    @staticmethod
    def _notice_mascot() -> QLabel:
        """Kiri at the start of a notice, turned towards its text."""
        label = QLabel(objectName="NoticeMascot")
        label.setPixmap(mascot("turn_right", 36))
        return label

    def ffmpeg_ready(self) -> bool:
        """Whether ffmpeg and ffprobe are found (tests replace this)."""
        return tools.ffmpeg_ready()

    def install_ffmpeg(self, on_progress, cancelled) -> None:
        """Download ffmpeg into the user's tools folder (tests replace this)."""
        tools.install_ffmpeg(on_progress=on_progress, cancelled=cancelled)

    def check_ffmpeg(self) -> bool:
        """Show the notice when ffmpeg is missing, hide it when it is there."""
        ready = self.ffmpeg_ready()
        self.ffmpeg_notice.setVisible(not ready)
        if not ready and not self.ffmpeg_busy:
            hint = "" if tools.can_install_ffmpeg() else "\n" + tools.install_hint()
            self.ffmpeg_label.setText(tr("ffmpeg 없음. 녹화, 영상 변환, 클립 제작에 필요") + hint)
        return ready

    def fetch_ffmpeg(self) -> None:
        if self.ffmpeg_busy:
            return
        self.ffmpeg_busy = True
        self.ffmpeg_button.setEnabled(False)
        self.ffmpeg_again.setEnabled(False)
        self.ffmpeg_label.setText(tr("ffmpeg 내려받는 중"))
        self._ffmpeg_stop.clear()
        seen = [-1]

        def progress(done: int, total: int) -> None:
            percent = int(done * 100 / total) if total else 0
            if percent != seen[0]:  # one signal per percent, not one per block
                seen[0] = percent
                self._ffmpeg_progress.emit(done, total)

        def work() -> None:
            try:
                self.install_ffmpeg(progress, self._ffmpeg_stop.is_set)
                message = ""
            except Exception as exc:  # shown in the notice and a dialog
                message = str(exc) or type(exc).__name__
            try:
                self._ffmpeg_done.emit(message)
            except RuntimeError:  # the window was closed meanwhile
                pass

        self._ffmpeg_thread = threading.Thread(target=work, name="stream2clip-ffmpeg", daemon=True)
        self._ffmpeg_thread.start()

    def _on_ffmpeg_progress(self, done: int, total: int) -> None:
        percent = int(done * 100 / total) if total else 0
        self.ffmpeg_label.setText(tr("ffmpeg 내려받는 중: {0}% ({1} / {2} MB)").format(percent, round(done / 1e6), round(total / 1e6)))

    def _on_ffmpeg_done(self, message: str) -> None:
        self.ffmpeg_busy = False
        self.ffmpeg_button.setEnabled(True)
        self.ffmpeg_again.setEnabled(True)
        if message:
            self.ffmpeg_label.setText(tr("ffmpeg 내려받기 실패: {0}").format(message.splitlines()[0][:110]))
            if self.dialogs and self.isVisible():
                QMessageBox.warning(self, "ffmpeg", message)
        elif self.check_ffmpeg():
            self.status.setText(tr("ffmpeg 준비됨"))

    # ------------------------------------------------------------------ layout
    def _capture_card(self) -> QWidget:
        card = QWidget(objectName="Card")
        grid = QHBoxLayout(card)
        grid.setContentsMargins(14, 14, 14, 14)
        grid.setSpacing(10)
        for label, slot, tip in (
            (tr("영역 캡쳐\nF8"), self.capture_region, tr("드래그로 영역을 골라 바로 편집")),
            (tr("전체 화면 캡쳐\n모든 모니터"), self.capture_fullscreen, tr("모든 모니터를 캡쳐해 편집")),
            (tr("이미지 열어 편집\nPNG, JPG, WebP"), self.open_image, tr("PNG/JPG/WebP 파일 편집")),
        ):
            btn = QPushButton(label, objectName="BigAction")
            btn.setToolTip(tip)
            btn.clicked.connect(slot)
            grid.addWidget(btn)
        return card

    def _clips_card(self) -> QWidget:
        card = QWidget(objectName="Card")
        rows = QVBoxLayout(card)
        rows.setContentsMargins(16, 12, 16, 12)
        rows.setSpacing(10)
        row = QHBoxLayout()
        row.setSpacing(12)
        kiri = QLabel()
        kiri.setPixmap(mascot("wink", 52))
        row.addWidget(kiri)
        text = QVBoxLayout()
        text.addWidget(QLabel(tr("방송 클립 제작"), objectName="Title"))
        text.addWidget(QLabel(tr("채팅 반응 기반 하이라이트 검출, 구간 조정, 9:16 클립 내보내기"), objectName="Muted"))
        row.addLayout(text, 1)
        self.highlights_button = QPushButton(tr("하이라이트 찾기"))
        self.highlights_button.setMinimumHeight(44)
        self.highlights_button.clicked.connect(self.open_highlights)
        row.addWidget(self.highlights_button)
        rows.addLayout(row)

        replay = QHBoxLayout()
        replay.setSpacing(8)
        label = QLabel(tr("OBS 리플레이"))
        label.setStyleSheet("font-weight:800;")
        replay.addWidget(label)
        replay.addWidget(QLabel(tr("방금 지나간 장면을 위 녹화 형식으로 저장"), objectName="Muted"), 1)
        replay.addWidget(QLabel(tr("마지막")))
        self.replay_last = QSpinBox(minimum=0, maximum=600, value=15)
        self.replay_last.setSuffix(tr("초"))
        self.replay_last.setSpecialValueText(tr("전체"))
        self.replay_last.setToolTip(tr("리플레이 버퍼에서 마지막 몇 초만 남길지 (전체 = 버퍼 그대로)"))
        replay.addWidget(self.replay_last)
        self.replay_hotkey_check = QCheckBox("F10")
        self.replay_hotkey_check.setToolTip(tr("켜면 방송 중 어느 프로그램에서든 F10으로 리플레이를 저장합니다.\n켜 둔 동안 다른 프로그램은 F10을 받지 못합니다."))
        self.replay_hotkey_check.toggled.connect(self._set_replay_hotkey)
        replay.addWidget(self.replay_hotkey_check)
        connect = QPushButton(tr("연결 설정"))
        connect.clicked.connect(self.edit_obs)
        replay.addWidget(connect)
        self.replay_button = QPushButton(tr("리플레이 저장"))
        self.replay_button.setToolTip(tr("OBS의 리플레이 버퍼를 저장해 클립으로 만듭니다 (OBS 28 이상, WebSocket 서버 켜기)"))
        self.replay_button.clicked.connect(self.save_replay)
        replay.addWidget(self.replay_button)
        rows.addLayout(replay)

        live = QHBoxLayout()
        live.setSpacing(8)
        label = QLabel(tr("라이브 모드"))
        label.setStyleSheet("font-weight:800;")
        live.addWidget(label)
        self.live_edit = QLineEdit()
        self.live_edit.setPlaceholderText(tr("YouTube, Twitch, CHZZK, SOOP 라이브 주소"))
        self.live_edit.setToolTip(tr("방송 중 채팅이 급증하면 OBS 리플레이 버퍼를 저장하고 해당 장면을 클립으로 만듭니다.\nOBS 리플레이 버퍼의 최대 시간을 60초 이상으로 설정하세요."))
        live.addWidget(self.live_edit, 1)
        live.addWidget(QLabel(tr("민감도")))
        self.live_level = QComboBox()
        for key, name, _threshold in _LIVE_LEVELS:
            self.live_level.addItem(name, key)
        self.live_level.setCurrentIndex(1)
        self.live_level.setToolTip(tr("높을수록 작은 채팅 급증에도 저장합니다."))
        live.addWidget(self.live_level)
        self.live_button = QPushButton(tr("라이브 모드 시작"))
        self.live_button.clicked.connect(self.toggle_live)
        live.addWidget(self.live_button)
        rows.addLayout(live)
        return card

    # ------------------------------------------------------------------ OBS replay
    def edit_obs(self) -> None:
        dialog = ObsDialog(self.obs_host, self.obs_port, self.obs_password, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.obs_host = dialog.host_edit.text().strip() or "127.0.0.1"
            self.obs_port = dialog.port_spin.value()
            self.obs_password = dialog.password_edit.text()

    def _hotkey_names(self) -> list[str]:
        return ["F8", "F9"] + (["F10"] if self.replay_hotkey_check.isChecked() else [])

    def _set_replay_hotkey(self, on: bool) -> None:
        """Take or give back the system-wide F10 (opt-in: other programs lose the key while it is on)."""
        if getattr(self, "hotkeys", None) is None:
            return  # still starting up: the keys are registered once, a little later
        self.hotkeys.unregister()
        self.hotkeys.register(self._hotkey_names())

    def obs_client(self):
        """Connect to OBS with the current settings (tests replace this)."""
        from ..obs import ObsClient

        return ObsClient(self.obs_host, self.obs_port, self.obs_password or os.environ.get("OBS_WEBSOCKET_PASSWORD") or None)

    def save_replay(self) -> None:
        if self.replay_busy:
            return
        self.replay_busy = True
        self.replay_button.setEnabled(False)
        self.status.setText(tr("OBS 리플레이 저장 중"))
        output = self.settings.save_dir / f"replay_{time.strftime('%Y%m%d_%H%M%S')}.{self.settings.format}"
        options = ExportOptions(format=self.settings.format, fps=self.settings.fps, width=self.settings.width)
        last = float(self.replay_last.value()) or None

        def work() -> None:
            try:
                from ..obs import replay_to_clip

                output.parent.mkdir(parents=True, exist_ok=True)
                client = self.obs_client()
                try:
                    clip, _replay = replay_to_clip(output, options, last=last, client=client)
                finally:
                    client.close()
                self._replay_done.emit(str(clip))
            except Exception as exc:  # shown in the status line and a dialog
                self._replay_failed.emit(str(exc))

        threading.Thread(target=work, name="stream2clip-replay", daemon=True).start()

    def _on_replay_done(self, path: str) -> None:
        self.replay_busy = False
        self.replay_button.setEnabled(True)
        self.status.setText(tr("저장됨: {0}, {1}").format(path, time.strftime('%H:%M:%S')))

    def _on_replay_failed(self, message: str) -> None:
        self.replay_busy = False
        self.replay_button.setEnabled(True)
        self.status.setText(tr("리플레이 실패: {0}").format(message.splitlines()[0][:110]))
        if self.dialogs and self.isVisible():
            QMessageBox.warning(self, tr("OBS 리플레이"), message)

    # ------------------------------------------------------------------ live mode
    def live_config(self):
        """The detector settings for the chosen sensitivity (tests replace this)."""
        from ..live import LiveConfig

        thresholds = {key: threshold for key, _name, threshold in _LIVE_LEVELS}
        return LiveConfig(threshold=thresholds.get(self.live_level.currentData(), 3.5))

    def live_source(self, url: str, folder: Path):
        """Where the chat comes from: the chat of Twitch, CHZZK or SOOP itself, or yt-dlp recording the live chat into ``folder`` (tests replace this)."""
        from ..live import open_chat

        return open_chat(url, folder)[0]

    def toggle_live(self) -> None:
        if self.live_running:
            self.stop_live()
        else:
            self.start_live()

    def start_live(self) -> None:
        """Watch the chat of a live stream; every surge saves OBS's replay buffer as a clip in the save folder."""
        from ..sources import is_url

        if self.live_running:
            return
        url = self.live_edit.text().strip()
        if not is_url(url):
            self._on_live("failed", tr("YouTube, Twitch, CHZZK, SOOP의 라이브 주소를 입력하세요."))
            return
        config = self.live_config()
        out = self.settings.save_dir
        options = ExportOptions(format=self.settings.format, fps=self.settings.fps, width=self.settings.width)
        poll = self.live_poll
        self.live_running = True
        self.live_clips = 0
        self._live_stop.clear()
        self.live_button.setText(tr("라이브 모드 중지"))
        self.live_edit.setEnabled(False)
        self.live_level.setEnabled(False)
        self.status.setText(tr("라이브 모드 준비 중: OBS 연결 확인"))
        self.remember()

        def work() -> None:
            from ..live import ReplayClipper, SurgeDetector, watch

            source = None
            try:
                clipper = ReplayClipper(out, self.obs_client, options=options, config=config)
                clipper.check()  # OBS missing or the buffer stopped is said now, not at the first surge
                source = self.live_source(url, out / "live_chat")
                detector = SurgeDetector(config, live_from=time.time())
                self._live_note.emit("status", "")

                def fired(trigger) -> None:
                    try:
                        saved = clipper(trigger)
                    except Exception as exc:  # OBS closed meanwhile, disk full: keep watching
                        self._live_note.emit("warning", str(exc))
                        return
                    self._live_note.emit("short" if saved.note else "clip", str(saved.clip))

                watch(source, detector, fired, poll=poll, should_stop=self._live_stop.is_set)
                self._live_note.emit("stopped", "")
            except Exception as exc:  # shown in the status line and a dialog
                message = str(exc)
                if "replay buffer is not running" in message.lower():  # the commonest case, said in the user's language
                    message = tr("OBS 리플레이 버퍼가 실행 중이 아닙니다. OBS에서 리플레이 버퍼를 시작한 후 다시 실행하세요.")
                self._live_note.emit("failed", message)
            finally:
                if source is not None:
                    source.close()

        self._live_thread = threading.Thread(target=work, name="stream2clip-live", daemon=True)
        self._live_thread.start()

    def stop_live(self) -> None:
        if self.live_running:
            self._live_stop.set()
            self.live_button.setEnabled(False)  # until the loop has let go of the chat
            self.status.setText(tr("라이브 모드 종료 중"))

    def _on_live(self, kind: str, text: str) -> None:
        now = time.strftime("%H:%M:%S")
        if kind == "status":
            self.status.setText(tr("라이브 모드 실행 중: 채팅 급증 시 리플레이를 저장합니다"))
        elif kind in ("clip", "short"):
            self.live_clips += 1
            message = tr("라이브 모드: 클립 저장 {0} ({1})").format(text, now)
            if kind == "short":  # the replay buffer was shorter than the clip
                message += tr(" / OBS 최대 리플레이 시간을 60초 이상으로 늘리세요")
            self.status.setText(message)
        elif kind == "warning":
            self.status.setText(tr("라이브 모드: 저장 실패 ({0})").format(text.splitlines()[0][:100]))
        else:  # "failed" before or during the watch, "stopped" at the end
            self.live_running = False
            self.live_button.setText(tr("라이브 모드 시작"))
            self.live_button.setEnabled(True)
            self.live_edit.setEnabled(True)
            self.live_level.setEnabled(True)
            if kind == "stopped":
                self.status.setText(tr("라이브 모드 종료: 클립 {0}개 저장").format(self.live_clips))
            else:
                self.status.setText(tr("라이브 모드 실패: {0}").format(text.splitlines()[0][:110]))
                if self.dialogs and self.isVisible():
                    QMessageBox.warning(self, tr("라이브 모드"), text)

    def open_highlights(self):
        from .highlights import HighlightsWindow

        if getattr(self, "highlights_window", None) is None:
            self.highlights_window = HighlightsWindow()
        self.highlights_window.show()
        self.highlights_window.raise_()
        self.highlights_window.activateWindow()
        return self.highlights_window

    def _record_card(self) -> QWidget:
        card = QWidget(objectName="Card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(12)

        top = QHBoxLayout()
        title = QVBoxLayout()
        t = QLabel(tr("녹화 설정"), objectName="Title")
        sub = QLabel(tr("F9로 녹화 시작, 다시 F9로 정지 및 저장"), objectName="Muted")
        title.addWidget(t)
        title.addWidget(sub)
        top.addLayout(title, 1)
        self.record_button = QPushButton(tr("●  영역 녹화 (F9)"), objectName="Primary")
        self.record_button.setMinimumHeight(44)
        self.record_button.clicked.connect(self.controller_toggle)
        top.addWidget(self.record_button)
        lay.addLayout(top)

        fmt_row = QHBoxLayout()
        fmt_row.setSpacing(8)
        self.format_group = QButtonGroup(self)
        self.format_buttons: dict[str, QToolButton] = {}
        for key, label, sub_label in _FORMATS:
            btn = QToolButton(checkable=True)
            btn.setText(f"{label}\n{sub_label}")
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            btn.setMinimumSize(110, 54)
            btn.clicked.connect(lambda _=False, k=key: self._set_format(k))
            self.format_group.addButton(btn)
            self.format_buttons[key] = btn
            fmt_row.addWidget(btn)
        fmt_row.addStretch(1)
        lay.addLayout(fmt_row)

        opts = QGridLayout()
        opts.setHorizontalSpacing(10)
        opts.setVerticalSpacing(8)
        opts.addWidget(QLabel(tr("프레임")), 0, 0)
        self.fps_combo = QComboBox()
        for fps in (10, 15, 24, 30):
            self.fps_combo.addItem(f"{fps} fps", fps)
        self.fps_combo.setCurrentIndex(1)
        self.fps_combo.currentIndexChanged.connect(lambda _: setattr(self.settings, "fps", float(self.fps_combo.currentData())))
        opts.addWidget(self.fps_combo, 0, 1)
        opts.addWidget(QLabel(tr("크기")), 0, 2)
        self.width_combo = QComboBox()
        for label, width in _WIDTHS:
            self.width_combo.addItem(label, width)
        self.width_combo.currentIndexChanged.connect(lambda _: setattr(self.settings, "width", self.width_combo.currentData()))
        opts.addWidget(self.width_combo, 0, 3)
        self.cursor_check = QCheckBox(tr("마우스 커서 표시"), checked=True)
        self.cursor_check.toggled.connect(lambda on: setattr(self.settings, "cursor", on))
        opts.addWidget(self.cursor_check, 0, 4)
        opts.setColumnStretch(5, 1)
        lay.addLayout(opts)

        transparent = QWidget(objectName="Card")
        transparent.setStyleSheet("QWidget#Card { background: #1A2420; border-color: #2C4038; }")
        tl = QHBoxLayout(transparent)
        tl.setContentsMargins(12, 10, 12, 10)
        tl.setSpacing(10)
        self.transparent_check = QCheckBox(tr("투명 배경 녹화"))
        self.transparent_check.setStyleSheet("font-weight:800;")
        self.transparent_check.toggled.connect(self._set_transparent)
        tl.addWidget(self.transparent_check)
        tl.addWidget(QLabel(tr("고른 색을 지워 GIF, WebP, WebM을 투명하게"), objectName="Muted"), 1)
        self.key_button = QToolButton(objectName="Swatch")
        self.key_button.setToolTip(tr("지울 색"))
        tl.addWidget(self.key_button)
        pick = QToolButton(text=tr("스포이드"))
        pick.setToolTip(tr("화면에서 지울 색 고르기 (그린스크린 등)"))
        pick.clicked.connect(self.pick_key_color)
        tl.addWidget(pick)
        tl.addWidget(QLabel(tr("허용 범위")))
        self.similarity = QSlider(Qt.Orientation.Horizontal, minimum=1, maximum=50, value=12)
        self.similarity.setFixedWidth(110)
        self.similarity.valueChanged.connect(lambda v: setattr(self.settings, "similarity", v / 100))
        tl.addWidget(self.similarity)
        lay.addWidget(transparent)

        self._set_format("gif")
        self._set_key_color(self.settings.key_color)
        return card

    # ------------------------------------------------------------------ settings
    def _restore(self) -> None:
        """Put back what was chosen last time; anything unreadable is skipped."""
        saved = load_section("record")
        if saved.get("format") in self.format_buttons:
            self._set_format(saved["format"])
        for combo, key in ((self.fps_combo, "fps"), (self.width_combo, "width")):
            index = combo.findData(saved.get(key)) if key in saved else -1
            if index >= 0:
                combo.setCurrentIndex(index)
        if isinstance(saved.get("cursor"), bool):
            self.cursor_check.setChecked(saved["cursor"])
        if isinstance(saved.get("transparent"), bool):
            self.transparent_check.setChecked(saved["transparent"] and self.settings.format != "mp4")
        color = saved.get("key_color")
        if isinstance(color, str) and len(color) == 7 and color.startswith("#"):
            self._set_key_color(color)
        if isinstance(saved.get("similarity"), int) and 1 <= saved["similarity"] <= 50:
            self.similarity.setValue(saved["similarity"])
        if isinstance(saved.get("save_dir"), str) and saved["save_dir"]:
            self.settings.save_dir = Path(saved["save_dir"])
        obs = load_section("obs")
        if isinstance(obs.get("host"), str) and obs["host"]:
            self.obs_host = obs["host"]
        if isinstance(obs.get("port"), int) and 1 <= obs["port"] <= 65535:
            self.obs_port = obs["port"]
        if isinstance(obs.get("last"), int) and 0 <= obs["last"] <= 600:
            self.replay_last.setValue(obs["last"])
        if isinstance(obs.get("hotkey"), bool):
            self.replay_hotkey_check.setChecked(obs["hotkey"])
        live = load_section("live")
        if isinstance(live.get("url"), str):
            self.live_edit.setText(live["url"])
        index = self.live_level.findData(live.get("level")) if isinstance(live.get("level"), str) else -1
        if index >= 0:
            self.live_level.setCurrentIndex(index)

    def _set_language(self, index: int) -> None:
        """Remember the language; windows that are already open keep theirs, so it applies from the next start."""
        code = self.language_combo.itemData(index)
        self._app_settings(language=code)
        if code != language():
            # said in the language that was chosen, so it can be read by whoever chose it
            notice = {"ko": "다시 시작하면 한국어로 표시됩니다", "ja": "再起動すると日本語で表示されます", "en": "English is used after a restart"}
            self.status.setText(notice.get(code, ""))

    def remember(self) -> None:
        save_section("record", {
            "format": self.settings.format, "fps": self.fps_combo.currentData(), "width": self.width_combo.currentData(),
            "cursor": self.settings.cursor, "transparent": self.settings.transparent, "key_color": self.settings.key_color,
            "similarity": self.similarity.value(), "save_dir": str(self.settings.save_dir),
        })
        save_section("obs", {"host": self.obs_host, "port": self.obs_port, "last": self.replay_last.value(), "hotkey": self.replay_hotkey_check.isChecked()})  # never the password
        save_section("live", {"url": self.live_edit.text().strip(), "level": self.live_level.currentData()})

    def _set_format(self, key: str) -> None:
        self.settings.format = key
        self.format_buttons[key].setChecked(True)
        mp4 = key == "mp4"
        self.transparent_check.setEnabled(not mp4)
        self.transparent_check.setToolTip(tr("MP4는 투명 배경을 지원하지 않습니다") if mp4 else "")

    def _set_transparent(self, on: bool) -> None:
        self.settings.transparent = on

    def _set_key_color(self, color: str) -> None:
        self.settings.key_color = color
        self.key_button.setStyleSheet(f"QToolButton#Swatch {{ background: {color}; border: 2px solid {theme.PAPER}; }}")
        self.key_button.setToolTip(tr("지울 색 {0}").format(color))

    def _change_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, tr("저장 폴더"), str(self.settings.save_dir))
        if path:
            self.settings.save_dir = Path(path)
            self._idle_status = tr("{0}, 저장: {1}").format(self._hotkey_note, path)
            self.status.setText(self._idle_status)

    @staticmethod
    def _open_dir(path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    # ------------------------------------------------------------------ capture
    def _hide_then(self, callback, delay_ms: int = 250) -> None:
        self.hide()
        QTimer.singleShot(delay_ms, callback)

    def capture_region(self) -> None:
        if self.controller.state != "idle":
            return
        self._hide_then(self._open_region_selector)

    def _open_region_selector(self) -> None:
        from .selector import ScreenSelector

        try:
            selector = ScreenSelector("region")
        except Exception as exc:
            self.show()
            QMessageBox.warning(self, tr("캡쳐 실패"), str(exc))
            return
        selector.regionSelected.connect(lambda _region, image, _rect: self._open_editor(Document(image)))
        selector.cancelled.connect(self.show)
        selector.show()
        self._selector = selector

    def capture_fullscreen(self) -> None:
        self._hide_then(self._grab_fullscreen)

    def _grab_fullscreen(self) -> None:
        from .selector import grab_virtual_screen

        try:
            image, _ = grab_virtual_screen()
        except Exception as exc:
            self.show()
            QMessageBox.warning(self, tr("캡쳐 실패"), str(exc))
            return
        self._open_editor(Document(image))

    def take_files(self, items) -> list[str]:
        """Dropped files: images open in the editor; a video, chat, info or subtitle file (or an address) goes to the highlights window."""
        from .highlights import kind_of

        kinds = [(kind_of(item), item) for item in items]
        placed = []
        for kind, item in kinds:
            if kind == "image":
                self.open_path(item)
                placed.append(kind)
        rest = [item for kind, item in kinds if kind and kind != "image"]
        if rest:
            placed += self.open_highlights().take_files(rest)
        return placed

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        from .highlights import dropped_items

        if self.take_files(dropped_items(event.mimeData())):
            event.acceptProposedAction()

    def open_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, tr("이미지 열기"), str(Path.home()), "Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif)")
        if path:
            self.open_path(path)

    def open_path(self, path: str | Path, annotations: str | Path | None = None) -> EditorWindow:
        return self._open_editor(Document.open(path, annotations=annotations))

    def _open_editor(self, doc: Document) -> EditorWindow:
        editor = EditorWindow(doc)
        editor.destroyed.connect(lambda *_: self.editors.remove(editor) if editor in self.editors else None)
        self.editors.append(editor)
        editor.show()
        editor.raise_()
        editor.activateWindow()
        self.show()
        return editor

    def pick_key_color(self) -> None:
        def open_picker() -> None:
            from .selector import ScreenSelector

            try:
                selector = ScreenSelector("color")
            except Exception as exc:
                self.show()
                QMessageBox.warning(self, tr("스포이드"), str(exc))
                return
            selector.colorPicked.connect(lambda c: (self._set_key_color(c), self.transparent_check.setChecked(True), self.show()))
            selector.cancelled.connect(self.show)
            selector.show()
            self._selector = selector

        self._hide_then(open_picker)

    # ------------------------------------------------------------------ recording
    def controller_toggle(self) -> None:
        if self.controller.state == "idle":
            self.hide()
        self.controller.toggle()

    def _on_hotkey(self, name: str) -> None:
        if name == "F9":
            self.controller_toggle()
        elif name == "F8":
            self.capture_region()
        elif name == "F10":
            self.save_replay()

    def _on_record_state(self, state: str) -> None:
        labels = {"idle": tr("●  영역 녹화 (F9)"), "selecting": tr("영역 선택 중"), "recording": tr("■  정지 (F9)"), "encoding": tr("저장 중")}
        self.record_button.setText(labels[state])
        self.record_button.setEnabled(state in ("idle", "recording"))
        if state == "selecting":
            self.hide()
        elif state == "encoding":
            self.status.setText(tr("{0} 인코딩 중").format(self.settings.format.upper()))
            self.show()
        elif state == "idle" and not self.isVisible():
            self.show()

    def _on_record_finished(self, path: str) -> None:
        self.status.setText(tr("저장됨: {0}, {1}").format(path, time.strftime('%H:%M:%S')))
        self.show()

    def _on_record_failed(self, message: str) -> None:
        self.status.setText(self._idle_status)
        self.show()
        QMessageBox.warning(self, tr("녹화"), message)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self.controller.state == "recording":
            self.controller.cancel()
        self._live_stop.set()  # the watcher lets go of yt-dlp within a moment
        if self._live_thread is not None:
            self._live_thread.join(timeout=5)
        if self.components_dialog is not None:
            self.components_dialog.close()
        self._ffmpeg_stop.set()  # a download in progress stops at the next block; its partial file is removed
        if self._ffmpeg_thread is not None:
            self._ffmpeg_thread.join(timeout=5)
        self.hotkeys.unregister()
        self.remember()
        super().closeEvent(event)
