"""The app remembers its settings and reaches the newer features: translation, singing,
laughter, YouTube upload and the OBS replay buffer - all without the real services."""

from __future__ import annotations

import json
import os
import sys
import time

import pytest

pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from stream2clip import plugins  # noqa: E402
from stream2clip.gui import settings  # noqa: E402
from stream2clip.gui.app import create_app  # noqa: E402
from stream2clip.gui.highlights import HighlightsWindow  # noqa: E402
from stream2clip.gui.launcher import LauncherWindow  # noqa: E402
from stream2clip.gui.upload import UploadDialog  # noqa: E402
from stream2clip.obs import ObsClient, ObsError  # noqa: E402

from .conftest import needs_ffmpeg  # noqa: E402
from .test_gui_highlights import stream_files, wait  # noqa: E402, F401
from .test_obs_upload import FakeObs  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return create_app([])


@pytest.fixture
def window(app):
    win = HighlightsWindow()
    win.dialogs = False
    win.show()
    app.processEvents()
    yield win
    win.close()


# ----------------------------------------------------------------------------- settings file


def test_settings_file_round_trip(isolated_settings):
    assert settings.config_dir() == isolated_settings and settings.load_section("record") == {}
    path = settings.save_section("record", {"format": "webp", "fps": 24})
    assert path == isolated_settings / "settings.json"
    settings.save_section("obs", {"port": 4460})
    assert settings.load_section("record") == {"format": "webp", "fps": 24}  # other sections are kept
    assert json.loads(path.read_text(encoding="utf-8"))["obs"] == {"port": 4460}

    path.write_text("{ not json", encoding="utf-8")  # a broken file means defaults, not a crash
    assert settings.load_section("record") == {}
    path.write_text('["a list"]', encoding="utf-8")
    assert settings.load_section("record") == {}
    assert settings.save_section("record", {"format": "gif"}) == path and settings.load_section("record") == {"format": "gif"}


def test_settings_folder_per_platform(monkeypatch, tmp_path):
    monkeypatch.delenv("STREAM2CLIP_CONFIG_DIR")
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setattr(settings.sys, "platform", "win32")
    assert settings.config_dir() == tmp_path / "roaming" / "stream2clip"
    monkeypatch.setattr(settings.sys, "platform", "linux")
    assert settings.settings_path() == tmp_path / "xdg" / "stream2clip" / "settings.json"
    monkeypatch.setattr(settings.sys, "platform", "darwin")
    assert settings.config_dir().parts[-3:] == ("Library", "Application Support", "stream2clip")


def test_unwritable_settings_folder_is_not_an_error(monkeypatch, tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setenv("STREAM2CLIP_CONFIG_DIR", str(blocker / "inside"))  # a file is in the way
    assert settings.save_section("record", {"format": "gif"}) is None and settings.load_section("record") == {}


def test_launcher_remembers_record_settings(app, tmp_path):
    first = LauncherWindow()
    assert first.settings.format == "gif" and first.settings.fps == 15.0  # nothing saved yet: the defaults
    first._set_format("webp")
    first.fps_combo.setCurrentIndex(first.fps_combo.findData(24))
    first.width_combo.setCurrentIndex(first.width_combo.findData(720))
    first.cursor_check.setChecked(False)
    first.transparent_check.setChecked(True)
    first._set_key_color("#FF00FF")
    first.similarity.setValue(30)
    first.settings.save_dir = tmp_path / "out"
    first.obs_host, first.obs_port, first.obs_password = "192.0.2.7", 4460, "hunter2"
    first.replay_last.setValue(30)
    first.close()

    saved = settings.settings_path().read_text(encoding="utf-8")
    assert "hunter2" not in saved and "password" not in saved  # never written

    again = LauncherWindow()
    s = again.settings
    assert (s.format, s.fps, s.width, s.cursor, s.transparent, s.key_color) == ("webp", 24.0, 720, False, True, "#FF00FF")
    assert s.similarity == pytest.approx(0.30) and s.save_dir == tmp_path / "out" and str(tmp_path / "out") in again.status.text()
    assert again.format_buttons["webp"].isChecked() and again.fps_combo.currentData() == 24 and not again.cursor_check.isChecked()
    assert (again.obs_host, again.obs_port, again.obs_password, again.replay_last.value()) == ("192.0.2.7", 4460, "", 30)
    again.close()


def test_launcher_ignores_settings_it_cannot_use(app):
    settings.save_section("record", {"format": "avi", "fps": 999, "cursor": "yes", "key_color": "green", "similarity": 500, "save_dir": 3})
    settings.save_section("obs", {"host": "", "port": 70000, "last": -5})
    win = LauncherWindow()
    assert (win.settings.format, win.settings.fps, win.settings.cursor, win.settings.key_color) == ("gif", 15.0, True, "#00FF00")
    assert (win.obs_host, win.obs_port, win.replay_last.value()) == ("127.0.0.1", 4455, 15)
    win.close()


# ----------------------------------------------------------------------------- OBS replay button


@needs_ffmpeg
def test_replay_button_saves_the_last_seconds(app, green_screen_video, tmp_path):
    from stream2clip.export import probe

    win = LauncherWindow()
    win.dialogs = False
    win.settings.save_dir = tmp_path / "replays"
    win._set_format("mp4")
    win.replay_last.setValue(1)
    server = FakeObs(replay=str(green_screen_video))  # the "replay" OBS saved: a 2 s video
    win.obs_client = lambda: ObsClient(connect=server.connect)
    win.save_replay()
    assert win.replay_busy and not win.replay_button.isEnabled()
    win.save_replay()  # a second press while busy does nothing
    wait(app, lambda: not win.replay_busy)
    assert "저장됨" in win.status.text() and win.replay_button.isEnabled() and server.closed
    clips = list((tmp_path / "replays").glob("replay_*.mp4"))
    assert len(clips) == 1 and probe(clips[0]).duration == pytest.approx(1.0, abs=0.3)
    assert server.requests == ["GetReplayBufferStatus", "SaveReplayBuffer"]
    win.close()


def test_replay_button_reports_a_missing_obs(app, tmp_path):
    win = LauncherWindow()
    win.dialogs = False
    win.settings.save_dir = tmp_path

    def no_obs():
        raise ObsError("Cannot reach OBS at ws://127.0.0.1:4455. Is OBS running?")

    win.obs_client = no_obs
    win.save_replay()
    wait(app, lambda: not win.replay_busy)
    assert win.status.text().startswith("리플레이 실패: Cannot reach OBS") and win.replay_button.isEnabled()

    stopped = FakeObs(active=False)
    win.obs_client = lambda: ObsClient(connect=stopped.connect)
    win.save_replay()
    wait(app, lambda: not win.replay_busy)
    assert "not running" in win.status.text() and stopped.closed
    win.close()


def test_f10_replay_hotkey_is_opt_in(app):
    win = LauncherWindow()
    win.dialogs = False
    registered = []
    win.hotkeys.unregister()
    win.hotkeys.register = lambda keys: registered.append(list(keys)) or "fake"
    saved = []
    win.save_replay = lambda: saved.append(True)

    assert not win.replay_hotkey_check.isChecked() and win._hotkey_names() == ["F8", "F9"]  # off unless asked for
    win._on_hotkey("F10")
    assert saved == [True]  # the key itself is handled...
    win.replay_hotkey_check.setChecked(True)
    assert registered == [["F8", "F9", "F10"]]  # ...but only taken system-wide when switched on
    win.replay_hotkey_check.setChecked(False)
    assert registered[-1] == ["F8", "F9"]
    win.replay_hotkey_check.setChecked(True)
    win.close()

    again = LauncherWindow()  # remembered, and registered from the start
    assert again.replay_hotkey_check.isChecked() and again._hotkey_names() == ["F8", "F9", "F10"]
    again.replay_hotkey_check.setChecked(False)
    again.close()


# ----------------------------------------------------------------------------- highlights window


class FakeTranslator:
    def __init__(self):
        self.calls = []

    def translate(self, texts, target, source=None):
        self.calls.append((list(texts), target, source))
        return [f"《{t}》" for t in texts]


@needs_ffmpeg
def test_export_with_translation_and_glossary(app, window, stream_files, tmp_path, monkeypatch):  # noqa: F811
    video, chat = stream_files
    fake = FakeTranslator()
    monkeypatch.setitem(plugins._RUNTIME["stream2clip.translators"], "fake", lambda: fake)
    subs = tmp_path / "ja.srt"
    subs.write_text("1\n00:00:31,000 --> 00:00:33,000\nぺこらです\n\n2\n00:00:34,000 --> 00:00:36,000\nこんにちは\n", encoding="utf-8")
    glossary = tmp_path / "names.csv"
    glossary.write_text("source,target\nぺこら,페코라\n", encoding="utf-8")
    out = tmp_path / "clips"

    window._fill_translators()
    labels = [window.translator_combo.itemText(i) for i in range(window.translator_combo.count())]
    assert labels[0] == "번역 안 함" and "fake" in labels and labels[-1].startswith("번역기 파일 고르기")
    assert window.translator_choice() == ""

    window.set_paths(video=str(video), chat=str(chat), subtitles=str(subs), output=str(out))
    window.audio_check.setChecked(False)
    window.analyse()
    wait(app, lambda: not window.busy)
    window.layout_combo.setCurrentIndex(window.layout_combo.findData("none"))
    window.format_combo.setCurrentIndex(window.format_combo.findData("gif"))
    window.set_translator("fake")
    window.glossary_edit.setText(str(glossary))
    window.bilingual_check.setChecked(True)
    window.export()
    wait(app, lambda: not window.busy)
    assert "저장됨" in window.status.text()
    ass = (out / "clip_01.ass").read_text(encoding="utf-8")
    assert "《페코라です》" in ass and "ぺこらです" in ass and "《こんにちは》" in ass  # the name went in already fixed; original kept above
    assert fake.calls and fake.calls[0][1:] == ("ko", "ja")

    # Translation without any subtitles is explained before anything starts.
    window.subs_combo.setCurrentIndex(window.subs_combo.findData("none"))
    window.export()
    assert not window.busy and "자막이 필요합니다" in window.status.text()


@needs_ffmpeg
def test_translator_from_a_file(app, window, stream_files, tmp_path):  # noqa: F811
    video, chat = stream_files
    code = tmp_path / "my_translator.py"
    code.write_text("def translate(texts, target, source=None):\n    return [f'{target}:{t}' for t in texts]\n", encoding="utf-8")
    subs = tmp_path / "ja.srt"
    subs.write_text("1\n00:00:31,000 --> 00:00:33,000\nこんにちは\n", encoding="utf-8")
    window.set_translator(str(code))
    assert window.translator_choice() == str(code) and window.translator_combo.currentText() == "my_translator.py"
    window.set_paths(video=str(video), chat=str(chat), subtitles=str(subs), output=str(tmp_path / "clips"))
    window.audio_check.setChecked(False)
    window.analyse()
    wait(app, lambda: not window.busy)
    window.layout_combo.setCurrentIndex(window.layout_combo.findData("none"))
    window.format_combo.setCurrentIndex(window.format_combo.findData("gif"))
    window.target_edit.setText("en")
    window.export()
    wait(app, lambda: not window.busy)
    assert "en:こんにちは" in (tmp_path / "clips" / "clip_01.ass").read_text(encoding="utf-8")

    window.set_translator(str(tmp_path / "gone.py"))  # a file that is not there: reported, not a crash
    window.export()
    wait(app, lambda: not window.busy)
    assert window.status.text().startswith("실패: Translator file not found")


@needs_ffmpeg
def test_singing_and_laughter_options(app, window, stream_files, monkeypatch):  # noqa: F811
    import stream2clip.audio as audio_module
    import stream2clip.pipeline as pipeline_module
    from stream2clip.audio import SingingSection

    video, chat = stream_files
    seen = {}
    real = pipeline_module.find_highlights

    def spy(*args, **kwargs):
        seen.update(kwargs)
        return real(*args, **kwargs)

    monkeypatch.setattr(pipeline_module, "find_highlights", spy)
    monkeypatch.setattr(audio_module, "singing_sections", lambda path, **kwargs: [SingingSection(0.0, 60.0, 0.6)])  # the whole video is a song

    window.set_paths(video=str(video), chat=str(chat))
    window.audio_check.setChecked(False)
    window.laughter_check.setChecked(True)
    window.singing_combo.setCurrentIndex(window.singing_combo.findData("mark"))
    window.analyse()
    wait(app, lambda: not window.busy)
    assert seen["laughter"] is True
    assert window.list.count() == 1 and "노래 구간 1곳" in window.status.text() and "노래 구간과 100% 겹침" in window.list.item(0).text()

    window.singing_combo.setCurrentIndex(window.singing_combo.findData("skip"))
    window.analyse()
    wait(app, lambda: not window.busy)
    assert window.list.count() == 0 and "하이라이트 0개 · 노래 구간 1곳" in window.status.text()

    window.singing_combo.setCurrentIndex(window.singing_combo.findData("off"))
    window.laughter_check.setChecked(False)
    window.analyse()
    wait(app, lambda: not window.busy)
    assert seen["laughter"] is False and window.list.count() == 1 and "노래 구간" not in window.status.text()


def test_highlights_window_remembers_its_choices(app, tmp_path):
    first = HighlightsWindow()
    first.audio_check.setChecked(False)
    first.laughter_check.setChecked(True)
    first.singing_combo.setCurrentIndex(first.singing_combo.findData("skip"))
    first.top_spin.setValue(7)
    first.threshold_spin.setValue(1.6)
    first.layout_combo.setCurrentIndex(first.layout_combo.findData("fit"))
    first.subs_combo.setCurrentIndex(first.subs_combo.findData("none"))
    first.language_edit.setText("ko")
    first.karaoke_check.setChecked(False)
    first.set_translator(str(tmp_path / "tr.py") + ":go")
    first.target_edit.setText("en")
    first.glossary_edit.setText(str(tmp_path / "names.csv"))
    first.bilingual_check.setChecked(True)
    first.format_combo.setCurrentIndex(first.format_combo.findData("webm"))
    first.agency_combo.setCurrentIndex(first.agency_combo.findData("vspo"))
    first.output_edit.setText(str(tmp_path / "clips"))
    first.last_dir = str(tmp_path)
    first.show()
    first.close()

    again = HighlightsWindow()
    assert not again.audio_check.isChecked() and again.laughter_check.isChecked() and again.singing_combo.currentData() == "skip"
    assert again.top_spin.value() == 7 and again.threshold_spin.value() == pytest.approx(1.6)
    assert (again.layout_combo.currentData(), again.subs_combo.currentData(), again.format_combo.currentData(), again.agency_combo.currentData()) == ("fit", "none", "webm", "vspo")
    assert (again.language_edit.text(), again.target_edit.text(), again.bilingual_check.isChecked(), again.karaoke_check.isChecked()) == ("ko", "en", True, False)
    assert again.translator_choice() == str(tmp_path / "tr.py") + ":go" and again.translator_combo.currentText() == "tr.py:go"
    assert again.glossary_edit.text() == str(tmp_path / "names.csv") and again.output_edit.text() == str(tmp_path / "clips") and again.last_dir == str(tmp_path)
    assert again.video_edit.text() == ""  # which stream was open is not remembered
    again.close()


# ----------------------------------------------------------------------------- upload dialog


def test_upload_dialog_shows_what_would_be_sent(app, tmp_path):
    dialog = UploadDialog(str(tmp_path / "clip.mp4"), title="레전드 <장면>", description="원본: https://youtu.be/x")
    dialog.dialogs = False
    assert dialog.title_edit.text() == "레전드 장면" and dialog.privacy_combo.currentData() == "private"
    dialog.tags_edit.setText("버튜버, clip,")
    dialog.shorts_check.setChecked(True)
    body = dialog.preview()
    assert body["status"]["privacyStatus"] == "private" and body["snippet"]["tags"] == ["버튜버", "clip"]
    assert body["snippet"]["description"].endswith("#Shorts")
    assert json.loads(dialog.preview_box.toPlainText()) == body and "아직 아무것도 올리지 않았습니다" in dialog.status.text()

    dialog.title_edit.setText("")
    assert dialog.preview() is None and dialog.status.text().startswith("확인 필요")
    dialog.close()


@needs_ffmpeg
def test_upload_dialog_uploads_in_the_background(app, green_screen_video, tmp_path):
    secrets = tmp_path / "client_secret.json"
    secrets.write_text("{}", encoding="utf-8")
    dialog = UploadDialog(str(green_screen_video), title="t")
    dialog.dialogs = False
    sent = {}

    def fake_uploader(video, resource, client_secrets, on_progress):
        sent.update(video=video, resource=resource, client_secrets=client_secrets)
        on_progress(0.5)
        return {"id": "abc123", "status": {"privacyStatus": "private"}}

    dialog.uploader = fake_uploader
    dialog.upload()
    assert not dialog.busy and "OAuth" in dialog.status.text() and sent == {}  # no client file yet: nothing is sent

    dialog.secrets_edit.setText(str(secrets))
    dialog.shorts_check.setChecked(True)
    assert any("가로 영상" in problem for problem in dialog.problems())  # the 160x120 test video is not a Short
    dialog.preview()
    assert dialog.preview_box.toPlainText().startswith("! ")  # shown above what would be sent
    dialog.upload()
    assert dialog.busy and not dialog.upload_button.isEnabled()
    wait(app, lambda: not dialog.busy)
    assert dialog.video_url == "https://www.youtube.com/watch?v=abc123" and "올렸습니다 (private)" in dialog.status.text()
    assert dialog.progress.value() == 100 and sent["client_secrets"] == str(secrets) and sent["resource"]["status"]["privacyStatus"] == "private"
    assert dialog.preview_box.toPlainText() == dialog.video_url

    def broken(video, resource, client_secrets, on_progress):
        raise RuntimeError("quotaExceeded")

    dialog.uploader = broken
    dialog.upload()
    wait(app, lambda: not dialog.busy)
    assert dialog.status.text() == "실패: quotaExceeded" and dialog.upload_button.isEnabled()
    dialog.video_edit.setText(str(tmp_path / "missing.mp4"))
    dialog.upload()
    assert not dialog.busy and "영상 파일" in dialog.status.text()
    dialog.close()

    again = UploadDialog()  # the client file, tags and Shorts tick are remembered; the privacy is not
    assert again.secrets_edit.text() == str(secrets) and again.shorts_check.isChecked() and again.privacy_combo.currentData() == "private"
    again.close()


@needs_ffmpeg
def test_upload_form_is_filled_from_the_exported_clip(app, window, stream_files, tmp_path):  # noqa: F811
    video, chat = stream_files
    info = tmp_path / "info.json"
    info.write_text(json.dumps({"id": "abc", "title": "【雑談】朝活", "webpage_url": "https://www.youtube.com/watch?v=abc", "duration": 60}), encoding="utf-8")
    empty = window.open_upload()  # nothing exported yet: an empty form for any file
    assert empty.video_edit.text() == "" and empty.title_edit.text() == ""
    empty.close()

    window.set_paths(video=str(video), chat=str(chat), info=str(info), output=str(tmp_path / "clips"))
    window.audio_check.setChecked(False)
    window.analyse()
    wait(app, lambda: not window.busy)
    window.layout_combo.setCurrentIndex(window.layout_combo.findData("none"))
    window.format_combo.setCurrentIndex(window.format_combo.findData("mp4"))
    window.export()
    wait(app, lambda: not window.busy)
    dialog = window.open_upload()
    assert dialog.video_edit.text() == str(tmp_path / "clips" / "clip_01.mp4") and dialog.title_edit.text() == "【雑談】朝活"
    assert "https://www.youtube.com/watch?v=abc" in dialog.description_edit.toPlainText()
    assert dialog.dialogs is False and dialog.privacy_combo.currentData() == "private"
    dialog.close()
    deadline = time.time() + 0.05
    while time.time() < deadline:
        app.processEvents()
