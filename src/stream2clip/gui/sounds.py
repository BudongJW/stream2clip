"""Sound library window: the free music and effects the user downloaded, with where each came from and its license.

A form over :class:`stream2clip.soundtrack.SoundLibrary`. Adding a file asks for its license
(from the license table), title, author, page and the credit wording the site asks for; the
credit line the descriptions will carry and the license notes are shown before it is saved.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..i18n import tr
from ..soundtrack import LICENSES, Sound, SoundLibrary, check_sounds
from .qt import app_icon

__all__ = ["SoundEntryDialog", "SoundLibraryDialog"]

_KINDS = [("bgm", tr("배경 음악")), ("sfx", tr("효과음"))]
AUDIO_FILES = "Audio (*.mp3 *.wav *.ogg *.m4a *.flac *.opus);;All files (*)"


class SoundEntryDialog(QDialog):
    """The facts of one downloaded file: name, kind, license, title, author, page, credit wording."""

    def __init__(self, file: str, *, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("음원 추가"))
        self.setWindowIcon(app_icon())
        self.file = file
        grid = QGridLayout(self)
        grid.setContentsMargins(18, 16, 18, 14)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        grid.addWidget(QLabel(tr("파일")), 0, 0)
        grid.addWidget(QLabel(Path(file).name, objectName="Muted"), 0, 1)
        grid.addWidget(QLabel(tr("이름")), 1, 0)
        self.name_edit = QLineEdit(Path(file).stem)
        self.name_edit.setToolTip(tr("배경 음악 칸에 넣을 짧은 이름"))
        grid.addWidget(self.name_edit, 1, 1)
        grid.addWidget(QLabel(tr("종류")), 2, 0)
        self.kind_combo = QComboBox()
        for key, label in _KINDS:
            self.kind_combo.addItem(label, key)
        grid.addWidget(self.kind_combo, 2, 1)
        grid.addWidget(QLabel(tr("라이선스")), 3, 0)
        self.license_combo = QComboBox()
        self.license_combo.addItem(tr("고르세요"), "")
        for key, lic in LICENSES.items():
            if key != "builtin":
                self.license_combo.addItem(f"{lic.name} ({key})", key)
        self.license_combo.setToolTip(tr("내려받은 사이트의 이용 약관에 맞는 항목. 목록에 없으면 직접 만든 음원과 산 음원만 own"))
        grid.addWidget(self.license_combo, 3, 1)
        self.title_edit, self.author_edit, self.url_edit, self.credit_edit = QLineEdit(), QLineEdit(), QLineEdit(), QLineEdit()
        self.url_edit.setPlaceholderText(tr("내려받은 페이지 주소"))
        self.credit_edit.setPlaceholderText(tr("(선택) 사이트가 정한 크레디트 문구를 그대로"))
        for row, (label, edit) in enumerate(((tr("제목"), self.title_edit), (tr("작가"), self.author_edit), (tr("주소"), self.url_edit), (tr("크레디트"), self.credit_edit)), start=4):
            grid.addWidget(QLabel(label), row, 0)
            grid.addWidget(edit, row, 1)
            edit.textChanged.connect(self._preview)
        self.license_combo.currentIndexChanged.connect(self._preview)
        self.kind_combo.currentIndexChanged.connect(self._preview)
        self.preview = QLabel(objectName="Muted")
        self.preview.setWordWrap(True)
        self.preview.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        grid.addWidget(self.preview, 8, 0, 1, 2)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton(tr("취소"))
        cancel.clicked.connect(self.reject)
        self.ok_button = QPushButton(tr("추가"), objectName="Primary")
        self.ok_button.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(self.ok_button)
        grid.addLayout(buttons, 9, 0, 1, 2)
        grid.setColumnStretch(1, 1)
        self.resize(560, 0)
        self._preview()

    def sound(self) -> Sound:
        return Sound(Path(self.file), kind=self.kind_combo.currentData(), name=self.name_edit.text().strip(), title=self.title_edit.text().strip(),
                     author=self.author_edit.text().strip(), url=self.url_edit.text().strip(), license=self.license_combo.currentData() or "",
                     credit=self.credit_edit.text().strip())

    def facts(self) -> dict:
        sound = self.sound()
        return {"kind": sound.kind, "name": sound.name, "license": sound.license, "title": sound.title, "author": sound.author, "url": sound.url, "credit": sound.credit}

    def _preview(self) -> None:
        sound = self.sound()
        lines = []
        credit = sound.credit_line() if sound.license else ""
        if credit:
            lines.append(tr("설명란 크레디트: {0}").format(credit))
        lines += [str(issue) for issue in check_sounds([sound]) if issue.level != "info" or "Content ID" not in issue.message]
        self.preview.setText("\n".join(lines))
        self.ok_button.setEnabled(bool(sound.license and sound.name))


class SoundLibraryDialog(QDialog):
    """What the library holds; add a downloaded file, forget one, or pick one as the music of the clips."""

    picked = Signal(str)

    def __init__(self, folder: str | Path | None = None, *, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("stream2clip 음원 목록"))
        self.setWindowIcon(app_icon())
        self.dialogs = True  # file pickers and the entry form (tests turn this off and call add_file)
        self.library = SoundLibrary(folder)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(8)
        note = QLabel(tr("음원은 사이트에서 직접 내려받아 추가합니다. 출처와 라이선스는 설명란 크레디트와 업로드 전 점검에 쓰입니다.\n폴더: {0}").format(self.library.folder), objectName="Muted")
        note.setWordWrap(True)
        note.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(note)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([tr("이름"), tr("종류"), tr("라이선스"), tr("제목, 작가")])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.itemDoubleClicked.connect(lambda _item: self.use_selected())
        layout.addWidget(self.table, 1)
        buttons = QHBoxLayout()
        self.add_button = QPushButton(tr("추가"))
        self.add_button.clicked.connect(self._pick_file)
        self.remove_button = QPushButton(tr("목록에서 빼기"))
        self.remove_button.clicked.connect(self.remove_selected)
        buttons.addWidget(self.add_button)
        buttons.addWidget(self.remove_button)
        buttons.addStretch(1)
        close = QPushButton(tr("닫기"))
        close.clicked.connect(self.reject)
        self.use_button = QPushButton(tr("배경 음악으로 쓰기"), objectName="Primary")
        self.use_button.clicked.connect(self.use_selected)
        buttons.addWidget(close)
        buttons.addWidget(self.use_button)
        layout.addLayout(buttons)
        self.resize(720, 420)
        self.refresh()

    def refresh(self) -> None:
        kinds = dict(_KINDS)
        self.table.setRowCount(len(self.library))
        for row, sound in enumerate(self.library):
            lic = LICENSES.get(sound.license)
            missing = "" if sound.path.is_file() else tr(" (파일 없음)")
            cells = (sound.name + missing, kinds.get(sound.kind, sound.kind), lic.name if lic else tr("기록 없음"), ", ".join(x for x in (sound.title, sound.author) if x))
            for column, text in enumerate(cells):
                self.table.setItem(row, column, QTableWidgetItem(text))
        self.use_button.setEnabled(any(s.kind == "bgm" for s in self.library))
        self.remove_button.setEnabled(len(self.library) > 0)

    def selected(self) -> Sound | None:
        row = self.table.currentRow()
        return self.library.sounds[row] if 0 <= row < len(self.library) else None

    def add_file(self, file: str, facts: dict) -> Sound:
        sound = self.library.add(file, **facts)
        self.refresh()
        self.table.selectRow(len(self.library) - 1)
        return sound

    def _pick_file(self) -> None:
        file, _ = QFileDialog.getOpenFileName(self, tr("내려받은 음원 파일"), str(Path.home() / "Downloads"), AUDIO_FILES)
        if not file:
            return
        entry = SoundEntryDialog(file, parent=self)
        if entry.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.add_file(file, entry.facts())
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, tr("음원 추가"), str(exc))

    def remove_selected(self) -> None:
        sound = self.selected()
        if sound is not None:
            self.library.remove(sound.name)
            self.refresh()

    def use_selected(self) -> None:
        sound = self.selected()
        if sound is None or sound.kind != "bgm":
            return
        self.picked.emit(sound.name)
        self.accept()
