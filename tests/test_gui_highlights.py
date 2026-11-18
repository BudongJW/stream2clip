"""Highlights window (방송 → 클립): timeline dragging, analysis, preview, export."""

from __future__ import annotations

import os
import random
import subprocess
import sys
import time

import numpy as np
import pytest

pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from stream2clip import plugins  # noqa: E402
from stream2clip.chat import ChatMessage  # noqa: E402
from stream2clip.detect import Face  # noqa: E402
from stream2clip.geometry import Region  # noqa: E402
from stream2clip.gui.app import create_app  # noqa: E402
from stream2clip.gui.highlights import HighlightsWindow, TimelineWidget  # noqa: E402
from stream2clip.highlights import detect_highlights  # noqa: E402

from .conftest import needs_ffmpeg  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return create_app([])


def synthetic_result(duration=3600, moments=(900, 2400)):
    rng = random.Random(3)
    msgs, t = [], 0.0
    while t < duration:
        t += rng.expovariate(0.5)
        msgs.append(ChatMessage(t, "なるほど", f"u{rng.randrange(200)}"))
    for at in moments:
        msgs += [ChatMessage(at + 6 + rng.random() * 15, "草", f"r{rng.randrange(5000)}") for _ in range(150)]
    return detect_highlights(sorted(msgs, key=lambda m: m.time), duration=duration)


def wait(app, condition, seconds=60):
    deadline = time.time() + seconds
    while not condition() and time.time() < deadline:
        app.processEvents()
        time.sleep(0.01)
    assert condition(), "timed out"


@pytest.fixture
def timeline(app):
    widget = TimelineWidget()
    widget.resize(1028, 200)  # plot is 1000 px wide: 3.6 s per pixel for an hour
    widget.set_result(synthetic_result())
    widget.show()
    app.processEvents()
    yield widget
    widget.close()


def drag(widget, x0, x1, y=100):
    QTest.mousePress(widget, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(round(x0), y))
    QTest.mouseMove(widget, QPoint(round((x0 + x1) / 2), y))
    QTest.mouseMove(widget, QPoint(round(x1), y))
    QTest.mouseRelease(widget, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(round(x1), y))


def test_timeline_bars_cover_equal_time_spans(timeline):
    assert len(timeline.highlights) == 2
    bars = timeline.bars(100)  # 36 s each
    assert len(bars) == 100
    # The planted moments (chat reacts ~6-21 s later) must land in the bar that covers that time.
    expected = {int((at + 13) / timeline.duration * 100) for at in (900, 2400)}  # chat peaks ~13 s after each moment
    assert {int(np.argmax(bars[:50])), 50 + int(np.argmax(bars[50:]))} == expected == {25, 66}
    assert timeline.x_to_time(timeline.time_to_x(1234.0)) == pytest.approx(1234.0, abs=2)


def test_drag_edges_and_body(timeline):
    events = []
    timeline.changed.connect(events.append)
    index = min(range(2), key=lambda i: timeline.highlights[i].start)
    h = timeline.highlights[index]
    start, end = h.start, h.end

    drag(timeline, timeline.time_to_x(end), timeline.time_to_x(end) + 20)  # right edge: 20 px = 72 s later
    assert h.end == pytest.approx(end + 72, abs=5) and h.start == start
    assert events and set(events) == {index} and timeline.current == index

    end = h.end
    drag(timeline, timeline.time_to_x(start), timeline.time_to_x(start) - 10)  # left edge: 36 s earlier
    assert h.start == pytest.approx(start - 36, abs=5) and h.end == end

    start, length = h.start, h.end - h.start
    middle = timeline.time_to_x((h.start + h.end) / 2)
    drag(timeline, middle, middle + 30)  # body: the whole span moves, the length stays
    assert h.start == pytest.approx(start + 108, abs=5) and h.end - h.start == pytest.approx(length)
    assert h.start <= h.peak <= h.end


def test_drag_is_clamped(timeline):
    h = timeline.highlights[0]
    timeline.select(0)
    drag(timeline, timeline.time_to_x(h.start), timeline.time_to_x(h.end) + 200)  # start dragged past the end
    assert h.end - h.start == pytest.approx(timeline.min_length)
    h.start, h.end = 3000.0, 3090.0
    middle = timeline.time_to_x(3045.0)
    drag(timeline, middle, middle + 5000)  # far beyond the right edge of the stream
    assert h.end == pytest.approx(timeline.duration) and h.end - h.start == pytest.approx(90.0)
    drag(timeline, timeline.time_to_x(h.start + 45), -5000)
    assert h.start == 0.0 and h.end == pytest.approx(90.0)


def test_narrow_spans_can_still_be_moved_and_zoomed(timeline):
    # Three hours on 1000 px: a 45 s clip is about 4 px wide.
    timeline.result.duration = 3 * 3600
    timeline.reset_view()
    h = timeline.highlights[0]
    h.start, h.end = 5000.0, 5045.0
    timeline.select(0)
    x0, x1 = timeline.time_to_x(h.start), timeline.time_to_x(h.end)
    assert x1 - x0 < 5
    assert timeline._hit((x0 + x1) / 2) == (0, "move")  # the middle is not swallowed by the edges
    assert timeline._hit(x0 - 4) == (0, "start") and timeline._hit(x1 + 4) == (0, "end")

    QTest.mouseDClick(timeline, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(round((x0 + x1) / 2), 100))
    assert timeline.zoomed and timeline.view[0] < h.start < h.end < timeline.view[1]
    width = timeline.time_to_x(h.end) - timeline.time_to_x(h.start)
    assert width > 250  # now a comfortable target
    drag(timeline, timeline.time_to_x(h.end), timeline.time_to_x(h.end) + width / 45 * 3)  # 3 seconds later
    assert h.end == pytest.approx(5048.0, abs=0.5) and h.start == 5000.0
    assert len(timeline.bars(20)) == 20
    QTest.mouseDClick(timeline, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(20, 100))  # empty area
    assert not timeline.zoomed and timeline.view == (0.0, timeline.duration)


def test_click_selects_and_deselects(timeline):
    picked = []
    timeline.selected.connect(picked.append)
    other = 1 - timeline.current
    h = timeline.highlights[other]
    QTest.mouseClick(timeline, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(round(timeline.time_to_x((h.start + h.end) / 2)), 100))
    assert timeline.current == other and picked == [other]
    QTest.mouseClick(timeline, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(round(timeline.time_to_x(60)), 100))
    assert timeline.current == -1 and picked == [other, -1]


@pytest.fixture
def stream_files(tmp_path):
    """A 60 s test-pattern video with sound and a chat log with one burst at 0:30."""
    video = tmp_path / "vod.mp4"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=160x90:r=10:d=60",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=60", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-shortest", str(video)],
        check=True,
    )
    rng = random.Random(5)
    rows = ["time,author,text"]
    rows += [f"{t + rng.random():.2f},u{rng.randrange(40)},なるほど" for t in range(0, 60, 2)]
    rows += [f"{30 + 6 + rng.random() * 6:.2f},r{i},草" for i in range(80)]
    chat = tmp_path / "chat.csv"
    chat.write_text("\n".join(rows), encoding="utf-8")
    return video, chat


@pytest.fixture
def window(app):
    win = HighlightsWindow()
    win.dialogs = False
    win.show()
    app.processEvents()
    yield win
    win.close()


@needs_ffmpeg
def test_find_adjust_preview_export(app, window, stream_files, tmp_path):
    video, chat = stream_files
    out = tmp_path / "clips"
    window.set_paths(video=str(video), chat=str(chat), output=str(out))
    window.audio_check.setChecked(False)
    assert not window.export_button.isEnabled()
    window.analyse()
    assert window.busy and not window.analyse_button.isEnabled()
    wait(app, lambda: not window.busy)
    assert window.list.count() == 1 and "하이라이트 1개" in window.status.text() and "채팅 110개" in window.status.text()
    assert window.export_button.isEnabled()
    wait(app, lambda: not window.preview.pixmap().isNull(), 20)  # a frame with the default blur layout
    assert window.preview.pixmap().height() > window.preview.pixmap().width()

    # Fine-tune on the timeline: keep 5 seconds, the list follows.
    h = window.timeline.highlights[0]
    h.start, h.end = 20.0, 60.0
    window.timeline.update()
    drag(window.timeline, window.timeline.time_to_x(60.0), window.timeline.time_to_x(25.0), y=90)
    assert h.end == pytest.approx(25.0, abs=1.0)
    assert "0:00:20 – 0:00:25" in window.list.item(0).text()

    window.layout_combo.setCurrentIndex(window.layout_combo.findData("none"))
    window.format_combo.setCurrentIndex(window.format_combo.findData("mp4"))
    window.export()
    wait(app, lambda: not window.busy)
    assert "저장됨" in window.status.text() and window.progress.value() == window.progress.maximum() == 1
    clip = window.last_results[0].path
    assert clip == out / "clip_01.mp4" and (out / "clips.json").exists()
    from stream2clip.export import probe

    assert probe(clip).duration == pytest.approx(h.end - h.start, abs=0.5)  # the dragged length, not the detected one


@needs_ffmpeg
def test_unchecked_highlights_are_not_exported(app, window, stream_files):
    video, chat = stream_files
    window.set_paths(video=str(video), chat=str(chat))
    window.audio_check.setChecked(False)
    window.analyse()
    wait(app, lambda: not window.busy)
    window.list.item(0).setCheckState(Qt.CheckState.Unchecked)
    assert window.checked_highlights() == []
    window.export()
    assert not window.busy


def test_stack_layout_asks_for_an_avatar(app, window):
    window.set_paths(video="missing.mp4")
    window.timeline.set_result(synthetic_result())
    window._on_analysed(window.timeline.result)
    window.layout_combo.setCurrentIndex(window.layout_combo.findData("stack"))
    assert window.avatar_edit.isEnabled() and window.avatar_button.isEnabled()
    window.export()
    assert not window.busy and window.status.text().startswith("실패") and "아바타" in window.status.text()
    window.avatar_edit.setText("100,40,60,40")
    assert window.layout_choice().avatar == Region(100, 40, 60, 40)
    window.layout_combo.setCurrentIndex(window.layout_combo.findData("blur"))
    assert not window.avatar_edit.isEnabled() and window.layout_choice().kind == "blur"


@needs_ffmpeg
def test_avatar_button_fills_the_box(app, window, stream_files, monkeypatch):
    class Steady:
        def detect(self, image):
            return [Face(Region(100, 30, 30, 30), 0.9)]

    monkeypatch.setitem(plugins._RUNTIME["stream2clip.face_detectors"], "steady", Steady)
    window.set_paths(video=str(stream_files[0]))
    window.layout_combo.setCurrentIndex(window.layout_combo.findData("stack"))
    window.find_avatar()
    wait(app, lambda: not window.busy)
    box = Region.parse(window.avatar_edit.text())
    assert box.contains(100, 30) and box.right <= 160 and box.bottom <= 90
    assert "12/12" in window.status.text()


def test_mascot_follows_the_state(app, window):
    from stream2clip.gui.highlights import mood_for
    from stream2clip.highlights import Highlight

    assert window.mood == "wink" and not window.mascot_label.pixmap().isNull()
    window._set_busy(True, "…")
    assert window.mood == "focus"
    window._on_analysed(synthetic_result())  # two planted "草" moments
    assert window.mood == "laugh" and not window.list.item(0).icon().isNull()
    window._on_exported(("clips", []))
    assert window.mood == "cut"
    window._on_failed("boom")
    assert window.mood == "surprised"

    def face(**stats):
        return mood_for(Highlight(1, 0, 10, 5, 1.0, stats=stats))

    assert face(react_laugh=9, react_shock=2) == "laugh" and face(react_shock=5, react_laugh=1) == "surprised"
    assert face(react_cute=3) == "wink" and face(react_hype=4) == "cut" and face() is None and face(react_laugh=0) is None


def test_failures_are_reported_in_the_status_line(app, window, tmp_path):
    window.analyse()  # no video picked
    assert window.status.text().startswith("실패") and not window.busy and window.mood == "surprised"
    window.set_paths(video=str(tmp_path / "nope.mp4"), chat=str(tmp_path / "nope.csv"))
    window.analyse()
    wait(app, lambda: not window.busy)
    assert window.status.text().startswith("실패") and window.analyse_button.isEnabled()


def test_launcher_opens_the_highlights_window(app):
    from stream2clip.gui.launcher import LauncherWindow

    launcher = LauncherWindow()
    win = launcher.open_highlights()
    assert isinstance(win, HighlightsWindow) and win.isVisible()
    assert launcher.open_highlights() is win  # reused, not opened twice
    win.close()
    launcher.close()
