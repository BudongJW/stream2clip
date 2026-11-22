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


# ----------------------------------------------------------------------------- ffmpeg notice


def test_start_window_offers_ffmpeg_when_it_is_missing(app, monkeypatch):
    from stream2clip import tools

    state = {"ready": False, "calls": 0}
    monkeypatch.setattr(LauncherWindow, "ffmpeg_ready", lambda self: state["ready"])
    monkeypatch.setattr(tools, "can_install_ffmpeg", lambda: True)
    win = LauncherWindow()
    win.dialogs = False
    assert not win.ffmpeg_notice.isHidden() and not win.ffmpeg_button.isHidden()
    assert win.ffmpeg_label.text() == "ffmpeg 없음. 녹화, 영상 변환, 클립 제작에 필요"
    from PySide6.QtWidgets import QLabel

    for notice in (win.ffmpeg_notice, win.update_notice):  # Kiri at the start of each notice, turned towards its text
        faces = [label for label in notice.findChildren(QLabel) if label.objectName() == "NoticeMascot"]
        assert len(faces) == 1 and not faces[0].pixmap().isNull()
    assert win.ffmpeg_button.text() == f"ffmpeg 내려받기 ({tools.FFMPEG_BUILD.megabytes} MB)"

    def fails(on_progress, cancelled):
        state["calls"] += 1
        on_progress(50, 100)
        raise OSError("no route to host")

    win.install_ffmpeg = fails
    win.fetch_ffmpeg()
    assert win.ffmpeg_busy and not win.ffmpeg_button.isEnabled()
    win.fetch_ffmpeg()  # a second press while busy does nothing
    wait(app, lambda: not win.ffmpeg_busy)
    assert state["calls"] == 1 and win.ffmpeg_label.text() == "ffmpeg 내려받기 실패: no route to host"
    assert win.ffmpeg_button.isEnabled() and not win.ffmpeg_notice.isHidden()  # it can be tried again

    shown = []
    win._ffmpeg_progress.connect(lambda done, total: shown.append(win.ffmpeg_label.text()))

    def works(on_progress, cancelled):
        for done in (1_000_000, 57_000_000, 57_100_000, 114_000_000):  # 57.0 and 57.1 MB are the same percent: one update
            on_progress(done, 114_000_000)
        state["ready"] = True

    win.install_ffmpeg = works
    win.fetch_ffmpeg()
    wait(app, lambda: not win.ffmpeg_busy)
    assert shown == ["ffmpeg 내려받는 중: 0% (1 / 114 MB)", "ffmpeg 내려받는 중: 50% (57 / 114 MB)", "ffmpeg 내려받는 중: 100% (114 / 114 MB)"]
    assert win.ffmpeg_notice.isHidden() and win.status.text() == "ffmpeg 준비됨"
    win.close()


def test_start_window_shows_no_notice_when_ffmpeg_is_there_and_no_button_without_a_download(app, monkeypatch):
    from stream2clip import tools

    monkeypatch.setattr(LauncherWindow, "ffmpeg_ready", lambda self: True)
    win = LauncherWindow()
    assert win.ffmpeg_notice.isHidden()
    win.close()

    state = {"ready": False}
    monkeypatch.setattr(LauncherWindow, "ffmpeg_ready", lambda self: state["ready"])
    monkeypatch.setattr(tools, "can_install_ffmpeg", lambda: False)  # macOS, Linux: a package manager has it
    monkeypatch.setattr(tools, "install_hint", lambda: "brew install ffmpeg")
    win = LauncherWindow()
    assert not win.ffmpeg_notice.isHidden() and win.ffmpeg_button.isHidden()
    assert win.ffmpeg_label.text().endswith("brew install ffmpeg")
    state["ready"] = True  # installed by hand meanwhile
    win.ffmpeg_again.click()
    assert win.ffmpeg_notice.isHidden()
    win.close()


def test_closing_the_start_window_stops_a_download(app, monkeypatch):
    import threading

    from stream2clip import tools

    monkeypatch.setattr(LauncherWindow, "ffmpeg_ready", lambda self: False)
    monkeypatch.setattr(tools, "can_install_ffmpeg", lambda: True)
    win = LauncherWindow()
    win.dialogs = False
    started, stopped = threading.Event(), []

    def slow(on_progress, cancelled):
        started.set()
        for _ in range(400):
            if cancelled():
                stopped.append(True)
                raise tools.DownloadCancelled("The download was cancelled")
            time.sleep(0.01)

    win.install_ffmpeg = slow
    win.fetch_ffmpeg()
    assert started.wait(5)
    win.close()
    assert stopped == [True]


# ----------------------------------------------------------------------------- components window


def components_of(state: dict) -> list:
    from stream2clip.tools import Component

    home = str(__import__("pathlib").Path.home())
    ffmpeg = Component("ffmpeg", "ffmpeg", "녹화, 영상 변환, 클립 제작", "ok", home + "\\tools\\ffmpeg.exe (9.0.2)") if state["ffmpeg"] else Component("ffmpeg", "ffmpeg", "녹화, 영상 변환, 클립 제작", "missing", fix="stream2clip setup --ffmpeg")
    model = Component("model", "얼굴 검출 모델", "아바타 위치 자동 검출", "ok", home + "/.cache/model.onnx") if state["model"] else Component("model", "얼굴 검출 모델", "아바타 위치 자동 검출", "later", "첫 사용 시 자동으로 내려받음")
    return [ffmpeg, model, Component("obs", "OBS WebSocket 서버", "리플레이 버퍼 저장", "optional", "127.0.0.1:4460 응답 없음", "OBS <Studio> 실행")]


def test_components_window_lists_this_pc_and_fetches_what_is_missing(app, monkeypatch):
    from stream2clip import tools
    from stream2clip.gui.components import ComponentsDialog, short_path

    home = str(__import__("pathlib").Path.home())
    assert short_path(home + "\\a\\b.exe (1.0)") == "~\\a\\b.exe (1.0)" and short_path("C:\\tools\\ffmpeg.exe") == "C:\\tools\\ffmpeg.exe"

    state = {"ffmpeg": False, "model": False, "looked": 0}

    def load(self):
        state["looked"] += 1
        return components_of(state)

    monkeypatch.setattr(ComponentsDialog, "load", load)
    monkeypatch.setattr(tools, "can_install_ffmpeg", lambda: True)
    dialog = ComponentsDialog(obs_port=4460)
    assert dialog.busy and dialog.summary.text() == "확인 중"
    wait(app, lambda: not dialog.busy)
    assert dialog.obs == ("127.0.0.1", 4460) and [item.key for item in dialog.found] == ["ffmpeg", "model", "obs"]
    assert not dialog.mascot_label.pixmap().isNull()  # Kiri beside the heading
    assert {key: badge.text() for key, badge in dialog.badges.items()} == {"ffmpeg": "없음", "model": "자동", "obs": "없음(선택)"}
    assert dialog.badges["ffmpeg"].objectName() == "StateMissing" and dialog.summary.text() == "필수 구성요소 없음: ffmpeg"
    assert set(dialog.actions) == {"ffmpeg", "model"} and dialog.actions["ffmpeg"].text() == f"ffmpeg 내려받기 ({tools.FFMPEG_BUILD.megabytes} MB)"
    labels = " ".join(label.text() for label in dialog.findChildren(type(dialog.summary)))
    assert "해결 방법: stream2clip setup --ffmpeg" in labels and "OBS &lt;Studio&gt; 실행" in labels  # what a component says is shown as text, never as markup

    def fails(on_progress, cancelled):
        on_progress(10, 100)
        raise OSError("no route to host")

    dialog.install_ffmpeg = fails
    dialog.actions["ffmpeg"].click()
    wait(app, lambda: not dialog.busy)
    assert dialog.summary.text() == "내려받기 실패: no route to host" and state["looked"] == 1 and dialog.actions["ffmpeg"].isEnabled()

    told, notes = [], []
    dialog.changed.connect(lambda: told.append(1))
    dialog._note.connect(notes.append)

    def works(on_progress, cancelled):
        on_progress(57_000_000, 114_000_000)
        state["ffmpeg"] = True

    dialog.install_ffmpeg = works
    dialog.fetch_ffmpeg()
    assert dialog.busy and not dialog.refresh_button.isEnabled()
    dialog.fetch_ffmpeg()  # a second press while busy does nothing
    wait(app, lambda: state["looked"] == 2 and not dialog.busy)
    assert told == [1] and notes == ["ffmpeg 내려받는 중: 50% (57 / 114 MB)"]
    assert dialog.badges["ffmpeg"].text() == "있음" and "ffmpeg" not in dialog.actions and dialog.summary.text() == "필수 구성요소 모두 있음"
    shown = " ".join(label.text() for label in dialog.findChildren(type(dialog.summary)))
    assert home not in shown and "~" in shown  # the user's folder is written ~

    fetched = []
    dialog.download_model = lambda: (fetched.append(1), state.__setitem__("model", True))
    dialog.actions["model"].click()
    wait(app, lambda: state["looked"] == 3 and not dialog.busy)
    assert fetched == [1] and dialog.badges["model"].text() == "있음" and dialog.actions == {}
    dialog.close()


def test_components_window_asks_about_a_newer_release_when_told(app, monkeypatch):
    from stream2clip import __version__, updates
    from stream2clip.gui.components import ComponentsDialog

    monkeypatch.setattr(ComponentsDialog, "load", lambda self: components_of({"ffmpeg": True, "model": True}))
    asked = []
    monkeypatch.setattr(ComponentsDialog, "fetch_release", lambda self: asked.append(1) or updates.Release("99.0.0", updates.RELEASES_PAGE))
    dialog = ComponentsDialog()
    wait(app, lambda: not dialog.busy)
    assert asked == [] and dialog.update_open.isHidden()  # nothing is asked until the button is pressed
    dialog.update_button.click()
    wait(app, lambda: not dialog.busy)
    assert asked == [1] and dialog.update_label.text() == f"새 버전 99.0.0 있음 (현재 {__version__})" and not dialog.update_open.isHidden()
    opened = []
    dialog.open_url = opened.append
    dialog.update_open.click()
    assert opened == [updates.DOWNLOAD_PAGE]

    dialog.fetch_release = lambda: None
    dialog.check_update()
    wait(app, lambda: not dialog.busy)
    assert dialog.update_label.text() == f"최신 버전 사용 중 ({__version__})" and dialog.update_open.isHidden()

    def offline():
        raise OSError("no route to host")

    dialog.fetch_release = offline
    dialog.check_update()
    wait(app, lambda: not dialog.busy)
    assert dialog.update_label.text() == "새 버전 확인 실패: no route to host"

    def broken(self):
        raise RuntimeError("cannot look")

    monkeypatch.setattr(ComponentsDialog, "load", broken)
    dialog.refresh()
    wait(app, lambda: not dialog.busy)
    assert dialog.summary.text() == "확인 실패: cannot look" and dialog.found == []
    dialog.close()


def test_start_window_opens_the_components_window(app, monkeypatch):
    from stream2clip.gui.components import ComponentsDialog

    looked = []
    monkeypatch.setattr(ComponentsDialog, "load", lambda self: looked.append(self.obs) or components_of({"ffmpeg": True, "model": True}))
    state = {"ready": False}
    monkeypatch.setattr(LauncherWindow, "ffmpeg_ready", lambda self: state["ready"])
    win = LauncherWindow()
    win.obs_port = 4470
    assert not win.ffmpeg_notice.isHidden()
    dialog = win.components_button.click() or win.components_dialog
    wait(app, lambda: not dialog.busy)
    assert looked == [("127.0.0.1", 4470)] and dialog.isVisible()
    state["ready"] = True
    dialog.changed.emit()  # ffmpeg was fetched in that window: the notice of this one goes away
    assert win.ffmpeg_notice.isHidden()
    win.obs_port = 4480
    assert win.open_components() is dialog  # the same window, looking again with the current OBS address
    wait(app, lambda: len(looked) == 2 and not dialog.busy)
    assert looked[1] == ("127.0.0.1", 4480)
    win.close()
    assert not dialog.isVisible()


# ----------------------------------------------------------------------------- newer release


def test_start_window_tells_about_a_newer_release(app, monkeypatch):
    from stream2clip import __version__, updates

    asked = []

    def newer(self):
        asked.append(1)
        return updates.Release("99.1.0", "https://github.com/BudongJW/stream2clip/releases/tag/v99.1.0")

    monkeypatch.setattr(LauncherWindow, "fetch_release", newer)
    quiet = LauncherWindow()  # the test run forbids asking (conftest): nothing is fetched, nothing shown
    assert asked == [] and quiet.update_notice.isHidden() and not quiet.check_updates()
    quiet.close()

    monkeypatch.delenv("STREAM2CLIP_NO_UPDATE_CHECK")
    win = LauncherWindow()
    wait(app, lambda: not win.update_notice.isHidden())
    assert asked == [1] and win.update_label.text() == f"새 버전 99.1.0 있음 (현재 {__version__})"
    opened = []
    win.open_url = opened.append
    win.update_open.click()
    assert opened == [updates.DOWNLOAD_PAGE]
    saved = settings.load_section("app")
    assert saved["update_latest"] == "99.1.0" and saved["update_checked"] > 0
    assert not win.check_updates()  # asked a moment ago: once a day is enough
    assert win.check_updates(now=saved["update_checked"] + 90000)  # ... a day later it asks again
    wait(app, lambda: len(asked) == 2)
    win._update_thread.join(5)
    app.processEvents()  # the answer is taken in before the window goes
    win.close()

    again = LauncherWindow()  # the same day: the answer is shown again without asking
    assert len(asked) == 2 and not again.update_notice.isHidden()
    again.language_combo.activated.emit(again.language_combo.findData("ja"))  # another setting of the app does not wipe the answer
    assert settings.load_section("app")["update_latest"] == "99.1.0" and settings.load_section("app")["language"] == "ja"
    again.update_skip.click()
    assert again.update_notice.isHidden() and settings.load_section("app")["update_skipped"] == "99.1.0"
    again.close()
    settings.save_section("app", {**settings.load_section("app"), "language": "ko"})

    skipped = LauncherWindow()
    assert skipped.update_notice.isHidden()  # that version is not mentioned again ...
    skipped.show_update("99.2.0")
    assert not skipped.update_notice.isHidden()  # ... the next one is
    skipped.update_off.click()
    assert skipped.update_notice.isHidden() and settings.load_section("app")["update_check"] is False and skipped.status.text() == "새 버전 알림 꺼짐"
    skipped.close()

    off = LauncherWindow()
    assert off.update_notice.isHidden() and not off.check_updates(force=True) and len(asked) == 2  # turned off: never asked
    off.close()


def test_start_window_stays_quiet_when_up_to_date_or_offline(app, monkeypatch):
    monkeypatch.delenv("STREAM2CLIP_NO_UPDATE_CHECK")
    calls = []

    def offline(self):
        calls.append("offline")
        raise OSError("no route to host")

    monkeypatch.setattr(LauncherWindow, "fetch_release", offline)
    win = LauncherWindow()
    wait(app, lambda: calls == ["offline"])
    win._update_thread.join(5)
    app.processEvents()
    assert win.update_notice.isHidden() and "update_checked" not in settings.load_section("app")  # no answer: it asks again next time
    win.close()

    def latest(self):
        calls.append("latest")
        return None

    monkeypatch.setattr(LauncherWindow, "fetch_release", latest)
    win = LauncherWindow()
    wait(app, lambda: "update_checked" in settings.load_section("app"))
    assert calls == ["offline", "latest"] and win.update_notice.isHidden() and settings.load_section("app")["update_latest"] == ""
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
    assert window.list.count() == 0 and "하이라이트 0개, 노래 구간 1곳" in window.status.text()

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
    assert body["paidProductPlacementDetails"] == {"hasPaidProductPlacement": False} and not dialog.paid_check.isChecked()
    dialog.paid_check.setChecked(True)
    body = dialog.preview()
    assert body["paidProductPlacementDetails"] == {"hasPaidProductPlacement": True}
    assert json.loads(dialog.preview_box.toPlainText()) == body and "아직 아무것도 올리지 않았습니다" in dialog.status.text()

    dialog.title_edit.setText("")
    assert dialog.preview() is None and dialog.status.text().startswith("확인 필요")

    # Nothing in the form covers anything else (the preview box once sat on the OAuth file row).
    grid, taken = dialog.layout(), {}
    for index in range(grid.count()):
        row, column, rows, columns = grid.getItemPosition(index)
        for cell in ((r, c) for r in range(row, row + rows) for c in range(column, column + columns)):
            assert cell not in taken, f"grid cell {cell} is used twice"
            taken[cell] = index
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
    assert dialog.video_edit.text() == str(tmp_path / "clips" / "clip_01.mp4")
    # The clip's suggested title (no captions: the stream title without its tag, in the Japanese clip form).
    assert dialog.title_edit.text() == window.last_results[0].title == "朝活【切り抜き】"
    assert "https://www.youtube.com/watch?v=abc" in dialog.description_edit.toPlainText()
    assert dialog.dialogs is False and dialog.privacy_combo.currentData() == "private"
    dialog.close()
    deadline = time.time() + 0.05
    while time.time() < deadline:
        app.processEvents()


# ----------------------------------------------------------------------------- starting from an address
@needs_ffmpeg
def test_highlights_from_an_address(app, window, tmp_path, monkeypatch):
    import shutil
    import subprocess
    from pathlib import Path

    from stream2clip import sources

    footage = tmp_path / "footage.mp4"  # long enough for any section that is asked for
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=160x90:r=5:d=100", "-f", "lavfi", "-i", "sine=frequency=440:duration=100",
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(footage)], check=True)
    url = "https://www.youtube.com/watch?v=abcdef12345"
    asked, fetched = [], []

    def fake_chat(u, out, ytdlp=None):
        asked.append("chat")
        rows = ["time,author,text"] + [f"{t},u{t % 30},なるほど" for t in range(0, 1800, 3)] + [f"{906 + i * 0.05:.2f},r{i},草" for i in range(160)]
        path = Path(out) / "chat.csv"
        path.write_text("\n".join(rows), encoding="utf-8")
        return path

    def fake_section(u, output, start=None, end=None, *, max_height=1080, ytdlp=None, timeout=None):
        fetched.append((u, start, end))
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(footage, output)
        return Path(output)

    monkeypatch.setattr(sources, "ytdlp_command", lambda **kwargs: ["yt-dlp"])  # yt-dlp itself is not needed (nor installed in CI)
    monkeypatch.setattr(sources, "fetch_info", lambda u, ytdlp=None: asked.append("info") or {"id": "abcdef12345", "title": "【雑談】朝活", "webpage_url": u, "duration": 1800})
    monkeypatch.setattr(sources, "download_chat", fake_chat)
    monkeypatch.setattr(sources, "download_section", fake_section)

    out = tmp_path / "clips"
    assert window.audio_check.isEnabled() and window.singing_combo.isEnabled()
    window.set_paths(video=url, output=str(out))
    assert not window.audio_check.isEnabled() and not window.laughter_check.isEnabled() and not window.singing_combo.isEnabled()  # they need the video file
    window.audio_check.setChecked(True)
    window.top_spin.setValue(1)
    window.analyse()
    wait(app, lambda: not window.busy)
    work = out / "sources" / "youtube_abcdef12345"
    assert asked == ["info", "chat"] and fetched == []  # no video yet
    assert window.info_edit.text() == str(work / "info.json") and window.chat_edit.text() == str(work / "chat.csv")
    assert window.list.count() == 1 and "하이라이트 1개" in window.status.text()
    assert "내보내면" in window.preview.text()  # nothing to show a still from

    window.layout_combo.setCurrentIndex(window.layout_combo.findData("none"))
    window.format_combo.setCurrentIndex(window.format_combo.findData("gif"))
    window.export()
    wait(app, lambda: not window.busy, 60)
    assert "저장됨" in window.status.text(), window.status.text()
    h = window.timeline.highlights[0]
    assert fetched == [(url, pytest.approx(h.start - 2), pytest.approx(h.end + 2))]  # only the highlight, with a little room
    assert (out / "clip_01.gif").is_file() and len(list((work / "sections").glob("section_01_*.mp4"))) == 1
    assert url in (out / "clip_01.txt").read_text(encoding="utf-8")  # the description names the stream
    assert window.progress.value() == window.progress.maximum() == 1
    wait(app, lambda: window.preview.pixmap() is not None and not window.preview.pixmap().isNull(), 20)  # the still comes from the downloaded section

    window.analyse()  # again: the chat and info on disk are used
    wait(app, lambda: not window.busy)
    assert asked == ["info", "chat"]
    window.export()
    wait(app, lambda: not window.busy, 60)
    assert len(fetched) == 1  # and so is the footage

    window.video_edit.setText(str(footage))  # back to a file: the audio options are available again
    assert window.audio_check.isEnabled() and window.sections == {}
    assert window.info_edit.text() == "" and window.chat_edit.text() == ""  # what was fetched for that stream does not stay for another source

    mine = tmp_path / "my_chat.csv"
    mine.write_text("time,author,text\n1,a,草\n", encoding="utf-8")
    window.set_paths(video=url, chat=str(mine))
    window.video_edit.setText(url + "0")
    assert window.chat_edit.text() == str(mine)  # a file the user chose is left alone


# ----------------------------------------------------------------------------- live mode in the launcher
class ScriptedChat:
    """A live chat: minutes of ordinary talk are there at the start, then one burst arrives."""

    def __init__(self, *, fails: str = "") -> None:
        self.ended, self.closed, self.reads, self.fails = False, False, 0, fails

    def read(self):
        import math

        from stream2clip.chat import ChatMessage

        self.reads += 1
        if self.fails:
            raise RuntimeError(self.fails)
        if self.reads == 1:
            now = time.time()
            return [ChatMessage(now - 400 + i * 2.5, "なるほど", author=f"u{i % 7}") for i in range(160)]
        if self.reads == 3:
            return [ChatMessage(math.nan, "草", author=f"r{i}") for i in range(40)]  # no time of their own: they count as "now"
        return []

    def close(self) -> None:
        self.closed = True


def quick_live_config():
    from stream2clip.live import LiveConfig

    return LiveConfig(smooth=1, warmup=60.0, lag=0.0, chat_delay=0.0, tail=0.0, lead=3.0)


@needs_ffmpeg
def test_live_mode_saves_a_clip_when_the_chat_surges(app, green_screen_video, tmp_path):
    win = LauncherWindow()
    win.dialogs = False
    win.settings.save_dir = tmp_path / "live"
    win._set_format("mp4")
    win.live_poll = 0.05
    assert [win.live_level.itemData(i) for i in range(win.live_level.count())] == ["low", "normal", "high"] and win.live_level.currentData() == "normal"
    assert win.live_config().threshold == 3.5
    servers = []

    def connect_obs():
        servers.append(FakeObs(replay=str(green_screen_video)))  # the "replay buffer": a 2 s video
        return ObsClient(connect=servers[-1].connect)

    win.obs_client = connect_obs
    chat, asked = ScriptedChat(), []
    win.live_source = lambda url, folder: asked.append((url, folder)) or chat
    win.start_live()
    assert not win.live_running and "주소를 입력" in win.status.text() and asked == []  # nothing to watch yet

    url = "https://www.youtube.com/watch?v=abcdef12345"
    win.live_edit.setText(url)
    win.live_level.setCurrentIndex(win.live_level.findData("high"))
    assert win.live_config().threshold == 2.5
    win.live_config = quick_live_config
    win.toggle_live()
    assert win.live_running and win.live_button.text() == "라이브 모드 중지" and not win.live_edit.isEnabled()
    win.start_live()  # already running: nothing happens
    wait(app, lambda: win.live_clips == 1, 30)
    assert "클립 저장" in win.status.text() and "60초 이상" in win.status.text()  # the 2 s buffer is shorter than the clip that was wanted
    assert len(list((tmp_path / "live").glob("live_*.mp4"))) == 1 and asked == [(url, tmp_path / "live" / "live_chat")]
    assert len(servers) == 2 and all(server.closed for server in servers)  # one connection to check, one for the surge

    win.toggle_live()
    wait(app, lambda: not win.live_running)
    assert win.status.text() == "라이브 모드 종료: 클립 1개 저장" and chat.closed
    assert win.live_button.text() == "라이브 모드 시작" and win.live_button.isEnabled() and win.live_edit.isEnabled()
    assert settings.load_section("live") == {"url": url, "level": "high"}
    win.close()

    again = LauncherWindow()  # the address and the sensitivity come back
    assert again.live_edit.text() == url and again.live_level.currentData() == "high"
    again.close()


def test_live_mode_says_what_is_wrong_before_it_waits(app, tmp_path):
    win = LauncherWindow()
    win.dialogs = False
    win.settings.save_dir = tmp_path
    win.live_poll = 0.05
    win.live_config = quick_live_config
    win.live_edit.setText("https://www.youtube.com/watch?v=abcdef12345")
    sources = []
    win.live_source = lambda url, folder: sources.append(ScriptedChat()) or sources[-1]

    def refuse():
        raise ObsError("Cannot reach OBS at ws://127.0.0.1:4455.")

    win.obs_client = refuse
    win.start_live()
    wait(app, lambda: not win.live_running)
    assert "라이브 모드 실패" in win.status.text() and "Cannot reach OBS" in win.status.text() and sources == []
    assert win.live_button.text() == "라이브 모드 시작" and win.live_edit.isEnabled()

    win.obs_client = lambda: ObsClient(connect=FakeObs(active=False).connect)  # OBS is there, its replay buffer is not running
    win.start_live()
    wait(app, lambda: not win.live_running)
    assert "리플레이 버퍼가 실행 중이 아닙니다" in win.status.text() and sources == []

    win.obs_client = lambda: ObsClient(connect=FakeObs().connect)
    win.live_source = lambda url, folder: sources.append(ScriptedChat(fails="yt-dlp stopped without any chat (is the stream live?)")) or sources[-1]
    win.start_live()
    wait(app, lambda: not win.live_running)
    assert "is the stream live" in win.status.text() and sources[-1].closed

    win.live_source = lambda url, folder: sources.append(ScriptedChat()) or sources[-1]
    win.start_live()
    wait(app, lambda: "실행 중" in win.status.text())
    win.close()  # closing the window stops the watcher and lets go of the chat
    assert sources[-1].closed


def test_live_mode_reads_twitch_chat_for_a_twitch_address(app, tmp_path):
    from stream2clip.live import TwitchLiveChat

    win = LauncherWindow()
    win.dialogs = False
    assert "Twitch" in win.live_edit.placeholderText()
    source = win.live_source("https://www.twitch.tv/some_channel", tmp_path)
    assert isinstance(source, TwitchLiveChat) and source.channel == "some_channel"  # nothing is connected before the first read
    source.close()
    from stream2clip.live import ChzzkLiveChat, SoopLiveChat

    assert "CHZZK" in win.live_edit.placeholderText() and "SOOP" in win.live_edit.placeholderText()
    assert isinstance(win.live_source("https://chzzk.naver.com/live/" + "ab" * 16, tmp_path), ChzzkLiveChat)
    assert isinstance(win.live_source("https://play.sooplive.co.kr/some_id", tmp_path), SoopLiveChat)
    win.close()
