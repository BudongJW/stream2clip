"""Main window: capture buttons, recording settings and global hotkeys (F8 / F9)."""

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
        note = QLabel(tr("OBS의 도구 → WebSocket 서버 설정에서 서버를 켜고, 리플레이 버퍼를 시작해 두세요.\n비밀번호는 저장하지 않습니다."), objectName="Muted")
        note.setWordWrap(True)
        form.addRow(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)


class LauncherWindow(QMainWindow):
    _replay_done = Signal(str)
    _replay_failed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("stream2clip")
        self.setWindowIcon(app_icon())
        self.editors: list[EditorWindow] = []
        self.settings = RecordSettings()
        self.obs_host, self.obs_port, self.obs_password = "127.0.0.1", 4455, ""
        self.replay_busy = False
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
        tagline = QLabel(tr("캡쳐부터 움짤 녹화까지, 한 프로그램으로"), objectName="Muted")
        header.addWidget(tagline)
        outer.addLayout(header)

        outer.addWidget(_eyebrow("CAPTURE"))
        outer.addWidget(self._capture_card())
        outer.addWidget(_eyebrow("RECORD"))
        outer.addWidget(self._record_card())
        outer.addWidget(_eyebrow("CLIPS"))
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
        self.language_combo.setToolTip("언어 · 言語 · Language")
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
        self._hotkey_note = tr("F8 영역 캡쳐 · F9 녹화 시작/정지") + ("" if backend != "none" else tr(" (창이 활성일 때)"))
        self._idle_status = tr("{0} · 저장: {1}").format(self._hotkey_note, self.settings.save_dir)
        self.status.setText(self._idle_status)
        self.resize(760, 780)

    # ------------------------------------------------------------------ layout
    def _capture_card(self) -> QWidget:
        card = QWidget(objectName="Card")
        grid = QHBoxLayout(card)
        grid.setContentsMargins(14, 14, 14, 14)
        grid.setSpacing(10)
        for label, slot, tip in (
            (tr("영역 캡쳐\nF8"), self.capture_region, tr("드래그로 영역을 골라 바로 편집")),
            (tr("전체 화면 캡쳐\n모든 모니터"), self.capture_fullscreen, tr("모든 모니터를 캡쳐해 편집")),
            (tr("이미지 열어 편집\nPNG · JPG · WebP"), self.open_image, tr("PNG/JPG/WebP 파일 편집")),
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
        text.addWidget(QLabel(tr("방송 → 클립"), objectName="Title"))
        text.addWidget(QLabel(tr("채팅 반응으로 하이라이트를 찾아 구간을 다듬고 9:16 클립으로 내보냅니다."), objectName="Muted"))
        row.addLayout(text, 1)
        self.highlights_button = QPushButton(tr("하이라이트 찾기"))
        self.highlights_button.setMinimumHeight(44)
        self.highlights_button.clicked.connect(self.open_highlights)
        row.addWidget(self.highlights_button)
        rows.addLayout(row)

        replay = QHBoxLayout()
        replay.setSpacing(8)
        label = QLabel(tr("OBS 리플레이 → 클립"))
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
        self.status.setText(tr("OBS 리플레이 저장 중…"))
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
        self.status.setText(tr("저장됨: {0}  ·  {1}").format(path, time.strftime('%H:%M:%S')))

    def _on_replay_failed(self, message: str) -> None:
        self.replay_busy = False
        self.replay_button.setEnabled(True)
        self.status.setText(tr("리플레이 실패: {0}").format(message.splitlines()[0][:110]))
        if self.dialogs and self.isVisible():
            QMessageBox.warning(self, tr("OBS 리플레이"), message)

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
        t = QLabel(tr("보이는 그대로 움짤 녹화"), objectName="Title")
        sub = QLabel(tr("F9 한 번이면 녹화가 시작됩니다. 다시 F9를 누르면 저장."), objectName="Muted")
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
        tl.addWidget(QLabel("NEW", objectName="Badge"))
        self.transparent_check = QCheckBox(tr("투명 배경 녹화"))
        self.transparent_check.setStyleSheet("font-weight:800;")
        self.transparent_check.toggled.connect(self._set_transparent)
        tl.addWidget(self.transparent_check)
        tl.addWidget(QLabel(tr("고른 색을 지워 GIF · WebP · WebM을 투명하게"), objectName="Muted"), 1)
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

    def _set_language(self, index: int) -> None:
        """Remember the language; windows that are already open keep theirs, so it applies from the next start."""
        code = self.language_combo.itemData(index)
        save_section("app", {"language": code})
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
            self._idle_status = tr("{0} · 저장: {1}").format(self._hotkey_note, path)
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
        labels = {"idle": tr("●  영역 녹화 (F9)"), "selecting": tr("영역 선택 중…"), "recording": tr("■  정지 (F9)"), "encoding": tr("저장 중…")}
        self.record_button.setText(labels[state])
        self.record_button.setEnabled(state in ("idle", "recording"))
        if state == "selecting":
            self.hide()
        elif state == "encoding":
            self.status.setText(tr("{0} 인코딩 중…").format(self.settings.format.upper()))
            self.show()
        elif state == "idle" and not self.isVisible():
            self.show()

    def _on_record_finished(self, path: str) -> None:
        self.status.setText(tr("저장됨: {0}  ·  {1}").format(path, time.strftime('%H:%M:%S')))
        self.show()

    def _on_record_failed(self, message: str) -> None:
        self.status.setText(self._idle_status)
        self.show()
        QMessageBox.warning(self, tr("녹화"), message)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self.controller.state == "recording":
            self.controller.cancel()
        self.hotkeys.unregister()
        self.remember()
        super().closeEvent(event)
