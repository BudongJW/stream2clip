"""The broadcast recorder window: start, mark, stop, open the session in the highlights window - without OBS or VTube Studio."""

from __future__ import annotations

import os
import sys
import time

import pytest

pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from stream2clip.gui.app import create_app  # noqa: E402
from stream2clip.gui.launcher import LauncherWindow  # noqa: E402
from stream2clip.gui.session import MARKER_KEY, SessionWindow  # noqa: E402
from stream2clip.obs import ObsClient  # noqa: E402
from stream2clip.recorder import build_recorder  # noqa: E402
from stream2clip.session import load_session  # noqa: E402
from stream2clip.vts import VtsClient  # noqa: E402

from .test_recorder import FakeObsServer, FakeVts  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return create_app([])


def wait_until(app, condition, seconds=5.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()
        if condition():
            return True
        time.sleep(0.02)
    return False


def fake_recorder(window, tmp_path, obs, vts):
    def make(path):
        return build_recorder(
            path, obs=("127.0.0.1", 4455, None), avatar_source="VTS", vts_url="ws://vts", replay_on_marker=window.replay_check.isChecked(),
            connect_obs=lambda: ObsClient(connect=obs.connect, events=69),
            connect_vts=lambda: VtsClient("ws://vts", token_file=tmp_path / "token", connect=vts.connect),
        )
    return make


def test_record_mark_stop_and_open_in_the_highlights_window(app, tmp_path):
    launcher = LauncherWindow()
    launcher.dialogs = False
    launcher.settings.save_dir = tmp_path
    window = launcher.open_session()
    window.dialogs = False
    assert launcher.open_session() is window  # one recorder window
    obs, vts = FakeObsServer(streaming=True), FakeVts()
    window.make_recorder = fake_recorder(window, tmp_path, obs, vts)
    window.replay_check.setChecked(True)

    window.start()
    assert window.running and not window.chat_edit.isEnabled() and window.mark_button.isEnabled()
    assert wait_until(app, lambda: (window.refresh() or True) and window.state_labels["obs"].text() == "연결됨" and window.state_labels["vts"].text() == "연결됨")
    assert window.state_labels["chat"].text() == "사용 안 함"
    vts.event("ModelOutlineEvent", {"modelName": "Kiri", "modelID": "id-1", "convexHull": [{"x": -0.5, "y": 0.8}, {"x": 0.5, "y": 0.8}, {"x": 0, "y": -1}], "windowSize": {"x": 1920, "y": 1080}})
    window.mark()
    assert window.status.text().startswith("표시함")
    assert wait_until(app, lambda: (window.refresh() or True) and "표시 1" in window.counts_label.text() and "아바타 외곽선 1" in window.counts_label.text())
    window.stop()
    assert wait_until(app, lambda: not window.running)
    assert window.start_button.text() == "기록 시작" and window.highlights_button.isEnabled() and window.status.text().startswith("기록 완료")

    session = load_session(window.last_path)
    assert window.last_path.parent == tmp_path / "sessions"
    assert [e.data["by"] for e in session.of("marker")] == ["button"]
    assert session.of("replay_saved")  # "also save OBS's replay at each marker" was on
    assert session.of("output")[0].data == {"output": "stream", "active": True}

    highlights = window.open_highlights()
    assert highlights is launcher.highlights_window
    assert highlights.chat_edit.text() == os.fspath(window.last_path)
    highlights.close()
    launcher.close()
    assert not window.isVisible()


def test_the_marker_key_goes_through_the_start_window(app, tmp_path):
    launcher = LauncherWindow()
    launcher.dialogs = False
    launcher.settings.save_dir = tmp_path
    window = launcher.open_session()
    window.dialogs = False
    marks = []
    window.mark = lambda by="button": marks.append(by)
    window.hotkey_check.setChecked(True)
    assert MARKER_KEY in launcher._hotkey_names()
    launcher._on_hotkey(MARKER_KEY)
    assert marks == ["hotkey"]
    window.hotkey_check.setChecked(False)
    assert MARKER_KEY not in launcher._hotkey_names()
    launcher.close()


def test_nothing_to_record_is_said_and_the_choices_are_remembered(app, tmp_path):
    window = SessionWindow(save_dir=tmp_path)
    window.dialogs = False
    window.obs_check.setChecked(False)
    window.vts_check.setChecked(False)
    window.chat_edit.setText("")
    window.start()
    assert not window.running and window.status.text().startswith("기록 실패") and "Nothing to record" in window.status.text()
    window.chat_edit.setText("https://chzzk.naver.com/live/0123456789abcdef0123456789abcdef")
    window.source_edit.setText("VTube Studio")
    window.vts_check.setChecked(True)
    window.close()
    again = SessionWindow(save_dir=tmp_path)
    assert again.chat_edit.text().endswith("0123456789abcdef") and again.source_edit.text() == "VTube Studio"
    assert again.vts_check.isChecked() and not again.obs_check.isChecked()
    again.close()


def test_the_recorder_window_runs_on_its_own(app, tmp_path, monkeypatch):
    from stream2clip.gui import session as module

    shown = []
    assert module.main([], run=lambda a: shown.extend(w for w in a.topLevelWidgets() if isinstance(w, SessionWindow) and w.isVisible()) or 0) == 0
    assert shown and shown[0].host is None
    shown[0].close()
