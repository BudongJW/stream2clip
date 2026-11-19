"""Editor window: 캡쳐하고 바로 편집.

Toolbar: 선택 · 펜 · 형광펜 · 네모 · 화살표 · 글자 · 모자이크 · 투명 · 자르기,
palette swatches, 팔레트 (color dialog), 스포이드 (eyedropper), 굵기, 번역.
Bottom bar: size + saved state, zoom, 되돌리기, 복사, 저장, 닫기.
"""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QColor, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QColorDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..color import PALETTE, to_hex
from ..editor import Document, Text
from ..i18n import tr
from . import theme
from .canvas import TOOLS, EditorCanvas, ToolState
from .qt import app_icon, pil_to_qimage

__all__ = ["EditorWindow", "default_save_dir"]

_SAVE_FILTERS = "PNG (*.png);;JPEG (*.jpg *.jpeg);;WebP (*.webp);;BMP (*.bmp);;Annotation JSON (*.json)"


def default_save_dir() -> Path:
    for base in (Path.home() / "Pictures", Path.home()):
        if base.is_dir():
            return base / "stream2clip"
    return Path.cwd()


class _ColorDot(QLabel):
    def __init__(self, color: str) -> None:
        super().__init__()
        self.setFixedSize(12, 12)
        self.set_color(color)

    def set_color(self, color: str) -> None:
        self.setStyleSheet(f"background:{color}; border-radius:6px; border:1px solid {theme.BORDER};")


class EditorWindow(QMainWindow):
    def __init__(self, document: Document, *, save_dir: Path | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.doc = document
        self.save_dir = save_dir or default_save_dir()
        self.tools = ToolState(tool="select")
        self.setWindowTitle(tr("stream2clip · 편집"))
        self.setWindowIcon(app_icon())
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        root = QWidget(objectName="Root")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_toolbar())

        self.canvas = EditorCanvas(self.doc, self.tools)
        self.scroll = QScrollArea()
        self.scroll.setWidget(self.canvas)
        self.scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll.setWidgetResizable(False)
        layout.addWidget(self.scroll, 1)
        layout.addWidget(self._build_bottom_bar())
        self.setCentralWidget(root)

        self.canvas.changed.connect(self._update_status)
        self.canvas.colorPicked.connect(self._on_color_picked)
        self.canvas.textRequested.connect(self._add_text)
        self.canvas.zoomChanged.connect(lambda z: self.zoom_button.setText(f"{round(z * 100)}%"))
        self._install_shortcuts()
        self._select_tool("select")
        self._set_color(self.tools.color)
        self._update_status()

        w, h = self.doc.size
        screen = QGuiApplication.primaryScreen().availableGeometry() if QGuiApplication.primaryScreen() else None
        max_w, max_h = (screen.width() * 0.85, screen.height() * 0.8) if screen else (1400, 900)
        self.resize(int(max(900, min(w + 40, max_w))), int(max(420, min(h + 170, max_h))))
        if w > max_w - 40 or h > max_h - 170:
            self.canvas.set_zoom(min((max_w - 40) / w, (max_h - 170) / h))

    # ------------------------------------------------------------------ UI
    def _build_toolbar(self) -> QWidget:
        bar = QWidget(objectName="Toolbar")
        rows = QVBoxLayout(bar)
        rows.setContentsMargins(12, 10, 12, 10)
        rows.setSpacing(8)

        row1 = QHBoxLayout()
        row1.setSpacing(6)
        self.tool_group = QButtonGroup(self)
        self.tool_group.setExclusive(True)
        self.tool_buttons: dict[str, QToolButton] = {}
        for tool_id, label, key, hint in TOOLS:
            btn = QToolButton(text=label, checkable=True)
            btn.setToolTip(f"{label} ({key}) — {hint}")
            btn.clicked.connect(lambda _=False, t=tool_id: self._select_tool(t))
            self.tool_group.addButton(btn)
            self.tool_buttons[tool_id] = btn
            row1.addWidget(btn)
        row1.addSpacing(8)

        self.swatch_group = QButtonGroup(self)
        self.swatch_group.setExclusive(True)
        self.swatches: dict[str, QToolButton] = {}
        for name, color in PALETTE.items():
            sw = QToolButton(objectName="Swatch", checkable=True)
            sw.setStyleSheet(f"QToolButton#Swatch {{ background: {color}; }}")
            sw.setToolTip(f"{name} {color}")
            sw.clicked.connect(lambda _=False, c=color: self._set_color(c))
            self.swatch_group.addButton(sw)
            self.swatches[color] = sw
            row1.addWidget(sw)
        row1.addSpacing(8)

        palette_btn = QToolButton(text=tr("팔레트"))
        palette_btn.setToolTip(tr("다른 색 고르기"))
        palette_btn.clicked.connect(self._open_palette)
        row1.addWidget(palette_btn)
        self.picker_btn = QToolButton(text=tr("스포이드"), checkable=True)
        self.picker_btn.setToolTip(tr("이미지에서 색 뽑기 (I)"))
        self.picker_btn.toggled.connect(self._toggle_picker)
        row1.addWidget(self.picker_btn)
        row1.addStretch(1)
        rows.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(6)
        width_box = QWidget(objectName="Card")
        wl = QHBoxLayout(width_box)
        wl.setContentsMargins(10, 2, 6, 2)
        self.color_dot = _ColorDot(self.tools.color)
        wl.addWidget(self.color_dot)
        wl.addWidget(QLabel(tr("굵기")))
        self.width_spin = QSpinBox(minimum=1, maximum=40, value=self.tools.width)
        self.width_spin.setToolTip(tr("선 굵기 · 글자 크기 · 모자이크 블록 크기 ( [ / ] )"))
        self.width_spin.setFixedWidth(64)
        self.width_spin.valueChanged.connect(self._set_width)
        wl.addWidget(self.width_spin)
        row2.addWidget(width_box)

        self.translate_btn = QPushButton(tr("번역 (한국어)"))
        self.translate_btn.setToolTip(tr("이미지 속 글자를 한국어로 번역해 덮어쓰기 (OCR·번역 플러그인 필요)"))
        self.translate_btn.clicked.connect(self._translate)
        row2.addWidget(self.translate_btn)
        self.hint_label = QLabel(objectName="Muted")
        row2.addSpacing(8)
        row2.addWidget(self.hint_label, 1)
        rows.addLayout(row2)
        return bar

    def _build_bottom_bar(self) -> QWidget:
        bar = QWidget(objectName="BottomBar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(8)
        self.status_label = QLabel(objectName="Status")
        row.addWidget(self.status_label)
        row.addStretch(1)
        self.zoom_button = QPushButton("100%")
        self.zoom_button.setToolTip(tr("100% ↔ 창에 맞추기 (Ctrl + 휠로 확대/축소)"))
        self.zoom_button.clicked.connect(self._toggle_zoom)
        self.undo_button = QPushButton(tr("되돌리기"))
        self.undo_button.setToolTip(tr("Ctrl+Z (다시 실행: Ctrl+Y)"))
        self.undo_button.clicked.connect(self.undo)
        copy_button = QPushButton(tr("복사"))
        copy_button.setToolTip(tr("클립보드로 복사 (Ctrl+C)"))
        copy_button.clicked.connect(self.copy_to_clipboard)
        save_button = QPushButton(tr("저장"), objectName="Primary")
        save_button.setToolTip("Ctrl+S")
        save_button.clicked.connect(self.save_as)
        close_button = QPushButton(tr("닫기"))
        close_button.clicked.connect(self.close)
        for widget in (self.zoom_button, self.undo_button, copy_button, save_button, close_button):
            row.addWidget(widget)
        return bar

    def _install_shortcuts(self) -> None:
        pairs = [
            (QKeySequence.StandardKey.Undo, self.undo),
            (QKeySequence.StandardKey.Redo, self.redo),
            (QKeySequence("Ctrl+Y"), self.redo),
            (QKeySequence.StandardKey.Copy, self.copy_to_clipboard),
            (QKeySequence.StandardKey.Save, self.save_as),
            (QKeySequence("Escape"), lambda: self._select_tool("select")),
            (QKeySequence("I"), lambda: self.picker_btn.toggle()),
            (QKeySequence("["), lambda: self.width_spin.setValue(self.width_spin.value() - 1)),
            (QKeySequence("]"), lambda: self.width_spin.setValue(self.width_spin.value() + 1)),
            (QKeySequence("Ctrl+0"), lambda: self.canvas.set_zoom(1.0)),
        ]
        for tool_id, _, key, _ in TOOLS:
            pairs.append((QKeySequence(key), lambda t=tool_id: self._select_tool(t)))
        for seq, slot in pairs:
            QShortcut(seq, self, activated=slot)

    # ------------------------------------------------------------------ actions
    def _select_tool(self, tool_id: str) -> None:
        self.tools.tool = tool_id
        self.tool_buttons[tool_id].setChecked(True)
        if self.picker_btn.isChecked():
            self.picker_btn.setChecked(False)
        if tool_id != "select":
            self.canvas.selected = None
            self.canvas.update()
        hint = next(h for t, _, _, h in TOOLS if t == tool_id)
        self.hint_label.setText(hint)
        self.canvas.setCursor(Qt.CursorShape.ArrowCursor if tool_id == "select" else Qt.CursorShape.CrossCursor)

    def _set_color(self, color: str) -> None:
        color = to_hex(color)
        self.tools.color = color
        self.color_dot.set_color(color)
        swatch = self.swatches.get(color)
        if swatch is not None:
            swatch.setChecked(True)
        else:
            self.swatch_group.setExclusive(False)
            for sw in self.swatches.values():
                sw.setChecked(False)
            self.swatch_group.setExclusive(True)

    def _set_width(self, value: int) -> None:
        self.tools.width = value

    def _open_palette(self) -> None:
        color = QColorDialog.getColor(QColor(self.tools.color), self, tr("색 고르기"))
        if color.isValid():
            self._set_color(color.name())

    def _toggle_picker(self, on: bool) -> None:
        self.tools.picking = on
        self.canvas.setCursor(Qt.CursorShape.PointingHandCursor if on else Qt.CursorShape.CrossCursor)
        if on:
            self.hint_label.setText(tr("이미지를 클릭해서 색 뽑기"))

    def _on_color_picked(self, color: str) -> None:
        self._set_color(color)
        self.picker_btn.setChecked(False)
        self._select_tool(self.tools.tool)

    def _add_text(self, x: float, y: float) -> None:
        text, ok = QInputDialog.getMultiLineText(self, tr("글자"), tr("넣을 글자:"))
        if ok and text.strip():
            self.doc.add(Text((x, y), text, color=self.tools.color, size=self.tools.text_size))
            self.canvas.refresh()
            self._update_status()

    def _translate(self) -> None:
        from ..translate import available_pipeline, translate_image

        pipeline = available_pipeline()
        if pipeline is None:
            QMessageBox.information(
                self,
                tr("번역 플러그인 없음"),
                tr("번역에는 OCR(글자 인식)과 번역기 플러그인이 필요합니다.\n\n"
                "stream2clip.plugins.register_text_detector / register_translator 로 등록하거나\n"
                "entry point(stream2clip.text_detectors, stream2clip.translators)를 제공하는 패키지를 설치하세요.\n"
                "자세한 내용: docs/PORTING.md"),
            )
            return
        detector, translator = pipeline
        try:
            shapes = translate_image(self.doc.render(apply_crop=False), detector, translator, target="ko")
        except Exception as exc:  # plugin errors should not kill the editor
            QMessageBox.warning(self, tr("번역 실패"), str(exc))
            return
        if not shapes:
            QMessageBox.information(self, tr("번역"), tr("인식된 글자가 없습니다."))
            return
        state = self.doc.state
        for shape in shapes:
            state = state.with_item(shape)
        self.doc.commit(state)
        self.canvas.refresh()
        self._update_status()

    def _toggle_zoom(self) -> None:
        if abs(self.canvas.zoom - 1.0) > 1e-3:
            self.canvas.set_zoom(1.0)
            return
        viewport = self.scroll.viewport().size()
        w, h = self.doc.size
        self.canvas.set_zoom(min(1.0, (viewport.width() - 8) / w, (viewport.height() - 8) / h))

    def undo(self) -> None:
        self.doc.undo()
        self.canvas.selected = None
        self.canvas.refresh()
        self._update_status()

    def redo(self) -> None:
        self.doc.redo()
        self.canvas.refresh()
        self._update_status()

    def copy_to_clipboard(self) -> None:
        QGuiApplication.clipboard().setImage(pil_to_qimage(self.doc.render()))
        self.status_label.setText(self._status_text() + tr(" · 복사됨"))

    def save_as(self) -> bool:
        self.save_dir.mkdir(parents=True, exist_ok=True)
        default = self.doc.source_path or self.save_dir / time.strftime("stream2clip_%Y%m%d_%H%M%S.png")
        path, _ = QFileDialog.getSaveFileName(self, tr("저장"), str(default), _SAVE_FILTERS)
        if not path:
            return False
        return self.save_to(Path(path))

    def save_to(self, path: Path) -> bool:
        try:
            if path.suffix.lower() == ".json":
                self.doc.save_annotations(path)
            else:
                if not path.suffix:
                    path = path.with_suffix(".png")
                self.doc.save(path)
                self.doc.source_path = path
        except Exception as exc:
            QMessageBox.warning(self, tr("저장 실패"), str(exc))
            return False
        self._update_status()
        return True

    # ------------------------------------------------------------------ status
    def _status_text(self) -> str:
        w, h = self.doc.output_size
        state = tr("저장 안 됨") if self.doc.dirty else tr("저장됨")
        return f"{w} × {h} px · {state}"

    def _update_status(self) -> None:
        self.status_label.setText(self._status_text())
        self.undo_button.setEnabled(self.doc.can_undo)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self.doc.dirty and self.doc.state.items and not getattr(self, "_force_close", False):
            answer = QMessageBox.question(
                self,
                tr("닫기"),
                tr("저장하지 않은 편집이 있습니다. 저장할까요?"),
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            )
            if answer == QMessageBox.StandardButton.Cancel or (answer == QMessageBox.StandardButton.Save and not self.save_as()):
                event.ignore()
                return
        event.accept()
