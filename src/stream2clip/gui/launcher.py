"""Main window: capture buttons, recording settings and global hotkeys (F8 / F9)."""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl, Qt
from PySide6.QtGui import QCloseEvent, QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..editor import Document
from . import theme
from .editor import EditorWindow
from .hotkeys import GlobalHotkeys
from .qt import app_icon, pixmap
from .recording import RecordController, RecordSettings

__all__ = ["LauncherWindow"]

_FORMATS = [("gif", "GIF", "어디서나 재생"), ("mp4", "MP4", "가벼운 용량"), ("webp", "WebP", "선명한 화질"), ("webm", "WebM", "투명 영상")]
_WIDTHS = [("원본 크기", None), ("1280px", 1280), ("960px", 960), ("720px", 720), ("480px", 480), ("320px", 320)]


def _eyebrow(text: str) -> QLabel:
    return QLabel(text, objectName="Eyebrow")


class LauncherWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("stream2clip")
        self.setWindowIcon(app_icon())
        self.editors: list[EditorWindow] = []
        self.settings = RecordSettings()

        root = QWidget(objectName="Root")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(28, 24, 28, 20)
        outer.setSpacing(14)

        header = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(pixmap("lockup-on-dark.png").scaledToHeight(48, Qt.TransformationMode.SmoothTransformation))
        header.addWidget(logo)
        header.addStretch(1)
        tagline = QLabel("캡쳐부터 움짤 녹화까지, 한 프로그램으로", objectName="Muted")
        header.addWidget(tagline)
        outer.addLayout(header)

        outer.addWidget(_eyebrow("CAPTURE"))
        outer.addWidget(self._capture_card())
        outer.addWidget(_eyebrow("RECORD"))
        outer.addWidget(self._record_card())

        footer = QHBoxLayout()
        self.status = QLabel(objectName="Muted")
        footer.addWidget(self.status, 1)
        open_folder = QPushButton("저장 폴더 열기")
        open_folder.clicked.connect(lambda: self._open_dir(self.settings.save_dir))
        change = QPushButton("폴더 변경")
        change.clicked.connect(self._change_dir)
        footer.addWidget(open_folder)
        footer.addWidget(change)
        outer.addLayout(footer)
        self.setCentralWidget(root)

        self.controller = RecordController(lambda: self.settings, self)
        self.controller.stateChanged.connect(self._on_record_state)
        self.controller.finished.connect(self._on_record_finished)
        self.controller.failed.connect(self._on_record_failed)

        self.hotkeys = GlobalHotkeys(self)
        backend = self.hotkeys.register(["F8", "F9"])
        self.hotkeys.activated.connect(self._on_hotkey)
        if backend == "none":
            QShortcut(QKeySequence("F8"), self, activated=self.capture_region)
            QShortcut(QKeySequence("F9"), self, activated=self.controller.toggle)
        hotkey_note = "F8 영역 캡쳐 · F9 녹화 시작/정지" + ("" if backend != "none" else " (창이 활성일 때)")
        self._idle_status = f"{hotkey_note} · 저장: {self.settings.save_dir}"
        self.status.setText(self._idle_status)
        self.resize(760, 640)

    # ------------------------------------------------------------------ layout
    def _capture_card(self) -> QWidget:
        card = QWidget(objectName="Card")
        grid = QHBoxLayout(card)
        grid.setContentsMargins(14, 14, 14, 14)
        grid.setSpacing(10)
        for label, slot, tip in (
            ("영역 캡쳐\nF8", self.capture_region, "드래그로 영역을 골라 바로 편집"),
            ("전체 화면 캡쳐\n모든 모니터", self.capture_fullscreen, "모든 모니터를 캡쳐해 편집"),
            ("이미지 열어 편집\nPNG · JPG · WebP", self.open_image, "PNG/JPG/WebP 파일 편집"),
        ):
            btn = QPushButton(label, objectName="BigAction")
            btn.setToolTip(tip)
            btn.clicked.connect(slot)
            grid.addWidget(btn)
        return card

    def _record_card(self) -> QWidget:
        card = QWidget(objectName="Card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(12)

        top = QHBoxLayout()
        title = QVBoxLayout()
        t = QLabel("보이는 그대로 움짤 녹화", objectName="Title")
        sub = QLabel("F9 한 번이면 녹화가 시작됩니다. 다시 F9를 누르면 저장.", objectName="Muted")
        title.addWidget(t)
        title.addWidget(sub)
        top.addLayout(title, 1)
        self.record_button = QPushButton("●  영역 녹화 (F9)", objectName="Primary")
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
        opts.addWidget(QLabel("프레임"), 0, 0)
        self.fps_combo = QComboBox()
        for fps in (10, 15, 24, 30):
            self.fps_combo.addItem(f"{fps} fps", fps)
        self.fps_combo.setCurrentIndex(1)
        self.fps_combo.currentIndexChanged.connect(lambda _: setattr(self.settings, "fps", float(self.fps_combo.currentData())))
        opts.addWidget(self.fps_combo, 0, 1)
        opts.addWidget(QLabel("크기"), 0, 2)
        self.width_combo = QComboBox()
        for label, width in _WIDTHS:
            self.width_combo.addItem(label, width)
        self.width_combo.currentIndexChanged.connect(lambda _: setattr(self.settings, "width", self.width_combo.currentData()))
        opts.addWidget(self.width_combo, 0, 3)
        self.cursor_check = QCheckBox("마우스 커서 표시", checked=True)
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
        self.transparent_check = QCheckBox("투명 배경 녹화")
        self.transparent_check.setStyleSheet("font-weight:800;")
        self.transparent_check.toggled.connect(self._set_transparent)
        tl.addWidget(self.transparent_check)
        tl.addWidget(QLabel("고른 색을 지워 GIF · WebP · WebM을 투명하게", objectName="Muted"), 1)
        self.key_button = QToolButton(objectName="Swatch")
        self.key_button.setToolTip("지울 색")
        tl.addWidget(self.key_button)
        pick = QToolButton(text="스포이드")
        pick.setToolTip("화면에서 지울 색 고르기 (그린스크린 등)")
        pick.clicked.connect(self.pick_key_color)
        tl.addWidget(pick)
        tl.addWidget(QLabel("허용 범위"))
        self.similarity = QSlider(Qt.Orientation.Horizontal, minimum=1, maximum=50, value=12)
        self.similarity.setFixedWidth(110)
        self.similarity.valueChanged.connect(lambda v: setattr(self.settings, "similarity", v / 100))
        tl.addWidget(self.similarity)
        lay.addWidget(transparent)

        self._set_format("gif")
        self._set_key_color(self.settings.key_color)
        return card

    # ------------------------------------------------------------------ settings
    def _set_format(self, key: str) -> None:
        self.settings.format = key
        self.format_buttons[key].setChecked(True)
        mp4 = key == "mp4"
        self.transparent_check.setEnabled(not mp4)
        self.transparent_check.setToolTip("MP4는 투명 배경을 지원하지 않습니다" if mp4 else "")

    def _set_transparent(self, on: bool) -> None:
        self.settings.transparent = on

    def _set_key_color(self, color: str) -> None:
        self.settings.key_color = color
        self.key_button.setStyleSheet(f"QToolButton#Swatch {{ background: {color}; border: 2px solid {theme.PAPER}; }}")
        self.key_button.setToolTip(f"지울 색 {color}")

    def _change_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "저장 폴더", str(self.settings.save_dir))
        if path:
            self.settings.save_dir = Path(path)
            self._idle_status = self._idle_status.rsplit("저장:", 1)[0] + f"저장: {path}"
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
            QMessageBox.warning(self, "캡쳐 실패", str(exc))
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
            QMessageBox.warning(self, "캡쳐 실패", str(exc))
            return
        self._open_editor(Document(image))

    def open_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "이미지 열기", str(Path.home()), "Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif)")
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
                QMessageBox.warning(self, "스포이드", str(exc))
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

    def _on_record_state(self, state: str) -> None:
        labels = {"idle": "●  영역 녹화 (F9)", "selecting": "영역 선택 중…", "recording": "■  정지 (F9)", "encoding": "저장 중…"}
        self.record_button.setText(labels[state])
        self.record_button.setEnabled(state in ("idle", "recording"))
        if state == "selecting":
            self.hide()
        elif state == "encoding":
            self.status.setText(f"{self.settings.format.upper()} 인코딩 중…")
            self.show()
        elif state == "idle" and not self.isVisible():
            self.show()

    def _on_record_finished(self, path: str) -> None:
        self.status.setText(f"저장됨: {path}  ·  {time.strftime('%H:%M:%S')}")
        self.show()

    def _on_record_failed(self, message: str) -> None:
        self.status.setText(self._idle_status)
        self.show()
        QMessageBox.warning(self, "녹화", message)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self.controller.state == "recording":
            self.controller.cancel()
        self.hotkeys.unregister()
        super().closeEvent(event)
