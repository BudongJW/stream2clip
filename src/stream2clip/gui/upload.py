"""Upload dialog: send one clip to YouTube.

A form over ``stream2clip.upload``. Nothing is sent until "업로드" is pressed, the
privacy defaults to private, and "보낼 내용 보기" shows exactly what would be sent.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QDateTime, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QWidget,
)

from ..i18n import tr
from . import theme
from .qt import app_icon
from .settings import load_section, save_section

__all__ = ["UploadDialog"]

_PRIVACY = [("private", tr("비공개")), ("unlisted", tr("일부 공개 (링크가 있는 사람만)")), ("public", tr("공개"))]
Uploader = Callable[[str, dict, str, Callable[[float], None]], dict]
#: ``(video id, image, client secrets, shorts, on_wait)``: sets the thumbnail once the video is up.
Thumbnailer = Callable[[str, str, str, bool, Callable[[str], None]], Any]


def _default_uploader(video: str, resource: dict, client_secrets: str, on_progress: Callable[[float], None], *, scopes: Any = None) -> dict:
    from ..upload import SCOPES, load_credentials, upload_video

    return upload_video(video, resource, credentials=load_credentials(client_secrets, scopes=scopes or SCOPES), on_progress=on_progress)


def _default_thumbnailer(video_id: str, image: str, client_secrets: str, shorts: bool, on_wait: Callable[[str], None]) -> Any:
    from ..upload import SCOPES, THUMBNAIL_SCOPES, load_credentials, set_thumbnail

    credentials = load_credentials(client_secrets, scopes=THUMBNAIL_SCOPES if shorts else SCOPES)
    return set_thumbnail(video_id, image, credentials=credentials, shorts=shorts, on_wait=on_wait)


class UploadDialog(QDialog):
    """Title, description, privacy and your own OAuth client file; then upload in the background."""

    _progress = Signal(float)
    _done = Signal(object)
    _failed = Signal(str)
    _note = Signal(str)

    def __init__(self, video: str = "", *, title: str = "", description: str = "", thumbnail: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("stream2clip YouTube 업로드"))
        self.setWindowIcon(app_icon())
        self.busy = False
        self.dialogs = True  # ask before a public upload, show failures in a box (tests turn this off)
        self.uploader: Uploader = _default_uploader
        self.thumbnailer: Thumbnailer = _default_thumbnailer
        self.video_url = ""
        saved = load_section("upload")

        grid = QGridLayout(self)
        grid.setContentsMargins(18, 16, 18, 14)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        grid.addWidget(QLabel(tr("영상")), 0, 0)
        self.video_edit = QLineEdit(video)
        grid.addWidget(self.video_edit, 0, 1)
        pick_video = QPushButton(tr("찾기"))
        pick_video.clicked.connect(lambda: self._browse(self.video_edit, "Video (*.mp4 *.webm *.mov *.mkv);;All files (*)"))
        grid.addWidget(pick_video, 0, 2)

        grid.addWidget(QLabel(tr("제목")), 1, 0)
        self.title_edit = QLineEdit(title.replace("<", "").replace(">", "")[:100])
        self.title_edit.setMaxLength(100)
        self.title_edit.setPlaceholderText(tr("최대 100자"))
        grid.addWidget(self.title_edit, 1, 1, 1, 2)

        grid.addWidget(QLabel(tr("설명")), 2, 0)
        self.description_edit = QPlainTextEdit(description)
        self.description_edit.setPlaceholderText(tr("원본 방송 주소, 제목 등 (기획사 가이드라인이 요구하는 표기)"))
        self.description_edit.setMinimumHeight(150)
        grid.addWidget(self.description_edit, 2, 1, 1, 2)

        grid.addWidget(QLabel(tr("태그")), 3, 0)
        self.tags_edit = QLineEdit(str(saved.get("tags", "")))
        self.tags_edit.setPlaceholderText(tr("쉼표로 구분"))
        grid.addWidget(self.tags_edit, 3, 1, 1, 2)

        grid.addWidget(QLabel(tr("공개 범위")), 4, 0)
        row = QHBoxLayout()
        self.privacy_combo = QComboBox()
        for key, label in _PRIVACY:
            self.privacy_combo.addItem(label, key)  # always starts at private: publishing is a choice made each time
        row.addWidget(self.privacy_combo, 1)
        self.shorts_check = QCheckBox(tr("Shorts (#Shorts 붙이기)"), checked=bool(saved.get("shorts", False)))
        row.addWidget(self.shorts_check)
        self.paid_check = QCheckBox(tr("유료 광고 포함"))  # declared each time, like the privacy
        self.paid_check.setToolTip(tr("협찬, 간접 광고(PPL), 보증 광고가 있으면 선택. 선택하지 않으면 유료 광고가 없는 영상으로 YouTube에 알림"))
        row.addWidget(self.paid_check)
        grid.addLayout(row, 4, 1, 1, 2)

        grid.addWidget(QLabel(tr("예약")), 5, 0)
        schedule = QHBoxLayout()
        self.schedule_check = QCheckBox(tr("예약 게시"))
        self.schedule_check.setToolTip(tr("비공개로 올린 뒤 정한 시각에 YouTube가 공개로 바꿉니다."))
        schedule.addWidget(self.schedule_check)
        self.schedule_edit = QDateTimeEdit(QDateTime.currentDateTime().addSecs(3600))
        self.schedule_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.schedule_edit.setCalendarPopup(True)
        self.schedule_edit.setEnabled(False)
        schedule.addWidget(self.schedule_edit, 1)
        self.schedule_check.toggled.connect(self._on_schedule_toggled)
        grid.addLayout(schedule, 5, 1, 1, 2)

        grid.addWidget(QLabel(tr("썸네일")), 6, 0)
        self.thumbnail_edit = QLineEdit(thumbnail)
        self.thumbnail_edit.setPlaceholderText(tr("(선택) JPEG 또는 PNG, 50MB 이하"))
        self.thumbnail_edit.setToolTip(tr("업로드 후 맞춤 썸네일로 설정. Shorts는 YouTube 처리가 끝난 뒤 설정(몇 분 걸림).\n채널 인증으로 맞춤 썸네일이 켜진 채널만 가능"))
        grid.addWidget(self.thumbnail_edit, 6, 1)
        pick_thumbnail = QPushButton(tr("찾기"))
        pick_thumbnail.clicked.connect(lambda: self._browse(self.thumbnail_edit, "Image (*.jpg *.jpeg *.png);;All files (*)"))
        grid.addWidget(pick_thumbnail, 6, 2)

        grid.addWidget(QLabel(tr("OAuth 파일")), 7, 0)
        self.secrets_edit = QLineEdit(str(saved.get("client_secrets", "")))
        self.secrets_edit.setPlaceholderText(tr("Google Cloud에서 받은 client_secret.json (본인 프로젝트)"))
        self.secrets_edit.setToolTip(tr("YouTube Data API를 켠 본인 Google Cloud 프로젝트의 데스크톱 앱 유형 OAuth 클라이언트 파일입니다.\n처음 한 번 브라우저에서 동의하면 같은 폴더에 token.json이 저장됩니다."))
        grid.addWidget(self.secrets_edit, 7, 1)
        pick_secrets = QPushButton(tr("찾기"))
        pick_secrets.clicked.connect(lambda: self._browse(self.secrets_edit, "JSON (*.json);;All files (*)"))
        grid.addWidget(pick_secrets, 7, 2)

        self.preview_box = QPlainTextEdit(readOnly=True)
        self.preview_box.setPlaceholderText(tr("보낼 내용 보기 버튼을 누르면 YouTube에 보낼 내용이 여기에 표시됩니다. 업로드는 실행되지 않습니다."))
        self.preview_box.setMaximumHeight(130)
        grid.addWidget(self.preview_box, 8, 0, 1, 3)  # below the OAuth row, not on it

        bottom = QHBoxLayout()
        self.status = QLabel(tr("비공개로 올린 뒤 YouTube 스튜디오에서 확인하고 공개하는 것을 권합니다"), objectName="Muted")
        self.status.setWordWrap(True)
        bottom.addWidget(self.status, 1)
        self.progress = QProgressBar()
        self.progress.setFixedWidth(140)
        self.progress.setRange(0, 100)
        self.progress.setStyleSheet(f"QProgressBar {{ background: {theme.SURFACE_2}; border: 1px solid {theme.BORDER}; border-radius: 8px; text-align: center; }}"
                                    f"QProgressBar::chunk {{ background: {theme.LIVE_PINK}; border-radius: 7px; }}")
        bottom.addWidget(self.progress)
        self.preview_button = QPushButton(tr("보낼 내용 보기"))
        self.preview_button.clicked.connect(self.preview)
        bottom.addWidget(self.preview_button)
        self.upload_button = QPushButton(tr("업로드"), objectName="Primary")
        self.upload_button.setMinimumHeight(36)
        self.upload_button.clicked.connect(self.upload)
        bottom.addWidget(self.upload_button)
        grid.addLayout(bottom, 9, 0, 1, 3)
        grid.setColumnStretch(1, 1)
        self.resize(640, 600)

        self._progress.connect(lambda fraction: self.progress.setValue(int(round(fraction * 100))))
        self._done.connect(self._on_done)
        self._failed.connect(self._on_failed)
        self._note.connect(self.status.setText)

    # ------------------------------------------------------------------ helpers
    def _browse(self, edit: QLineEdit, filters: str) -> None:
        start = str(Path(edit.text()).parent) if edit.text() else str(Path.home())
        path, _ = QFileDialog.getOpenFileName(self, tr("파일 고르기"), start, filters)
        if path:
            edit.setText(path)

    def _on_schedule_toggled(self, on: bool) -> None:
        """A scheduled video is uploaded private: YouTube publishes it at the time chosen."""
        self.schedule_edit.setEnabled(on)
        if on:
            self.privacy_combo.setCurrentIndex(self.privacy_combo.findData("private"))
        self.privacy_combo.setEnabled(not on)

    def resource(self) -> dict[str, Any]:
        """The ``videos.insert`` body the form describes; raises ``ValueError`` if YouTube would refuse it."""
        from ..upload import video_resource

        tags = [t for t in self.tags_edit.text().split(",") if t.strip()]
        when = self.schedule_edit.dateTime().toPython() if self.schedule_check.isChecked() else None
        return video_resource(
            self.title_edit.text(), self.description_edit.toPlainText(), tags=tags,
            privacy=self.privacy_combo.currentData(), shorts=self.shorts_check.isChecked(), publish_at=when,
            paid_placement=self.paid_check.isChecked(),
        )

    def problems(self) -> list[str]:
        """Why the video would not count as a Short (only when Shorts is ticked and the file can be read)."""
        if not self.shorts_check.isChecked():
            return []
        try:
            from ..export import probe
            from ..upload import shorts_problems

            info = probe(self.video_edit.text().strip())
            return shorts_problems(info.width, info.height, info.duration)
        except Exception:
            return []

    def _fail(self, message: str) -> None:
        self.status.setText(tr("확인 필요: {0}").format(message.splitlines()[0][:140]))

    # ------------------------------------------------------------------ actions
    def preview(self) -> dict[str, Any] | None:
        try:
            body = self.resource()
        except ValueError as exc:
            self._fail(str(exc))
            return None
        notes = "".join(f"! {p}\n" for p in self.problems())
        self.preview_box.setPlainText(notes + json.dumps(body, ensure_ascii=False, indent=2))
        self.status.setText(tr("보낼 내용입니다. 아직 아무것도 올리지 않았습니다."))
        return body

    def upload(self) -> None:
        if self.busy:
            return
        video, secrets = self.video_edit.text().strip(), self.secrets_edit.text().strip()
        if not video or not Path(video).is_file():
            self._fail(tr("올릴 영상 파일을 고르세요."))
            return
        body = self.preview()
        if body is None:
            return
        if not secrets or not Path(secrets).is_file():
            self._fail(tr("OAuth 클라이언트 파일(client_secret.json)을 고르세요."))
            return
        from ..upload import THUMBNAIL_SCOPES, thumbnail_problem

        thumbnail = self.thumbnail_edit.text().strip()
        if thumbnail and thumbnail_problem(thumbnail):
            self._fail(thumbnail_problem(thumbnail) or "")
            return
        shorts = self.shorts_check.isChecked()
        privacy = self.privacy_combo.currentData()
        if privacy == "public" and self.dialogs:
            answer = QMessageBox.question(self, tr("공개 업로드"), tr("바로 공개로 올립니다. 올린 뒤에는 되돌리기 어렵습니다. 계속할까요?"))
            if answer != QMessageBox.StandardButton.Yes:
                return
        save_section("upload", {"client_secrets": secrets, "tags": self.tags_edit.text(), "shorts": self.shorts_check.isChecked()})
        self.busy = True
        self.upload_button.setEnabled(False)
        self.progress.setValue(0)
        self.status.setText(tr("업로드 중 (처음이면 브라우저에서 Google 동의 화면이 열립니다)"))
        uploader, thumbnailer = self.uploader, self.thumbnailer

        def work() -> None:
            try:
                if uploader is _default_uploader and thumbnail and shorts:
                    response = _default_uploader(video, body, secrets, self._progress.emit, scopes=THUMBNAIL_SCOPES)  # one consent for both
                else:
                    response = uploader(video, body, secrets, self._progress.emit)
            except Exception as exc:  # shown in the status line and a dialog
                self._failed.emit(str(exc))
                return
            if thumbnail:  # the video is up whatever happens to the thumbnail
                self._note.emit(tr("썸네일 설정 중"))
                try:
                    thumbnailer(response["id"], thumbnail, secrets, shorts, lambda state: self._note.emit(tr("YouTube 처리 대기 중 ({0}), 끝나면 썸네일 설정").format(state)))
                    response = {**response, "thumbnail": thumbnail}
                except Exception as exc:
                    response = {**response, "thumbnail_error": str(exc)}
            self._done.emit(response)

        threading.Thread(target=work, name="stream2clip-upload", daemon=True).start()

    def _on_done(self, response: dict) -> None:
        from ..upload import video_url

        self.busy = False
        self.upload_button.setEnabled(True)
        self.progress.setValue(100)
        self.video_url = video_url(response["id"])
        privacy = response.get("status", {}).get("privacyStatus", self.privacy_combo.currentData())
        message = tr("올렸습니다 ({0}): {1}").format(privacy, self.video_url)
        if response.get("thumbnail"):
            message += tr(", 썸네일 설정됨")
        elif response.get("thumbnail_error"):
            message += "\n" + tr("썸네일 실패: {0}").format(str(response["thumbnail_error"]).splitlines()[0][:140])
        self.status.setText(message)
        self.preview_box.setPlainText(self.video_url)

    def _on_failed(self, message: str) -> None:
        self.busy = False
        self.upload_button.setEnabled(True)
        self.progress.setValue(0)
        self.status.setText(tr("실패: {0}").format(message.splitlines()[0][:140]))
        if self.dialogs and self.isVisible():
            QMessageBox.warning(self, tr("YouTube 업로드"), message)
