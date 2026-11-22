"""Highlights window (stream clips): timeline dragging, analysis, preview, export."""

from __future__ import annotations

import json
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
    assert "0:00:20 - 0:00:25" in window.list.item(0).text()

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
    window._set_busy(True, "busy")
    assert window.mood == "side"  # turned towards the progress bar while something runs
    from stream2clip.gui import qt

    wink, side = qt.mascot("wink", 44).toImage(), qt.mascot("side", 44).toImage()
    assert side != wink and qt.mascot("no such picture", 44).toImage() == wink  # an unknown name falls back to the default
    assert all(not qt.mascot(name, 44).isNull() for name in (*qt.MOODS, *qt.VIEWS))
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


def test_pip_layout_asks_for_an_avatar_like_stack(app, window):
    window.layout_combo.setCurrentIndex(window.layout_combo.findData("pip"))
    assert window.avatar_edit.isEnabled() and window.avatar_button.isEnabled()
    with pytest.raises(ValueError, match="아바타"):
        window.layout_choice()
    window.avatar_edit.setText("100,40,60,40")
    layout = window.layout_choice()
    assert layout.kind == "pip" and layout.avatar == Region(100, 40, 60, 40)


@needs_ffmpeg
def test_analysis_moves_span_edges_off_spoken_lines(app, window, stream_files, tmp_path):
    video, chat = stream_files
    window.set_paths(video=str(video), chat=str(chat), output=str(tmp_path / "clips"))
    window.audio_check.setChecked(False)
    window.snap_check.setChecked(False)
    window.analyse()
    wait(app, lambda: not window.busy)
    plain = window.timeline.highlights[0]
    start, end = plain.start, plain.end

    def stamp(t):
        return f"00:00:{int(t):02d},{int(round((t % 1) * 1000)):03d}"

    subs = tmp_path / "subs.srt"  # one line is being spoken across each edge of the span
    subs.write_text(f"1\n{stamp(start - 1)} --> {stamp(start + 1)}\nfirst\n\n2\n{stamp(end - 1)} --> {stamp(end + 1)}\nlast\n", encoding="utf-8")
    window.set_paths(video=str(video), chat=str(chat), subtitles=str(subs), output=str(tmp_path / "clips"))
    window.analyse()
    wait(app, lambda: not window.busy)
    assert (window.timeline.highlights[0].start, window.timeline.highlights[0].end) == (start, end)  # switched off: untouched
    window.snap_check.setChecked(True)
    window.analyse()
    wait(app, lambda: not window.busy)
    snapped = window.timeline.highlights[0]
    assert snapped.start == pytest.approx(start - 1.15, abs=0.01) and snapped.end == pytest.approx(end + 1.15, abs=0.01)


@needs_ffmpeg
def test_caption_look_chosen_in_the_window_reaches_the_clip(app, window, stream_files, tmp_path):
    video, chat = stream_files
    subs = tmp_path / "subs.srt"
    subs.write_text("1\n00:00:00,000 --> 00:00:59,000\n今日は配信です\n", encoding="utf-8")
    out = tmp_path / "clips"
    window.set_paths(video=str(video), chat=str(chat), subtitles=str(subs), output=str(out))
    window.audio_check.setChecked(False)
    window.snap_check.setChecked(False)
    assert [window.style_combo.itemData(i) for i in range(window.style_combo.count())] == ["default", "box", "pink", "small"]
    window.style_combo.setCurrentIndex(window.style_combo.findData("box"))
    window.position_combo.setCurrentIndex(window.position_combo.findData("top"))
    window.analyse()
    wait(app, lambda: not window.busy)
    window.export()
    wait(app, lambda: not window.busy, 120)
    style = next(line for line in (out / "clip_01.ass").read_text(encoding="utf-8").splitlines() if line.startswith("Style:")).split(",")
    assert style[1] == "Noto Sans JP" and style[15] == "3" and style[18] == "8"  # the font of the text, a plate, at the top
    again = HighlightsWindow()  # the choice is remembered
    assert again.style_combo.currentData() == "box" and again.position_combo.currentData() == "top"
    again.close()


# ----------------------------------------------------------------------------- dropped files, hand-off, compilation


def test_dropped_files_go_into_their_boxes(app, window, tmp_path):
    from PySide6.QtCore import QMimeData, QUrl

    from stream2clip.gui.highlights import dropped_items, kind_of

    kinds = {"vod.MP4": "video", "a.mkv": "video", "https://www.youtube.com/watch?v=abc": "video", "x.info.json": "info", "x.live_chat.json": "chat",
             "chat.csv": "chat", "c.chat.jsonl": "chat", "subs.ja.vtt": "subtitles", "s.srt": "subtitles", "shot.png": "image", "notes.txt": "", "": ""}
    assert {name: kind_of(name) for name in kinds} == kinds

    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(tmp_path / "vod.mp4")), QUrl("https://www.youtube.com/watch?v=abc")])
    assert dropped_items(mime) == [str(tmp_path / "vod.mp4").replace("\\", "/"), "https://www.youtube.com/watch?v=abc"]
    text = QMimeData()
    text.setText(" https://www.twitch.tv/videos/1 ")
    assert dropped_items(text) == ["https://www.twitch.tv/videos/1"]
    text.setText("just some words")
    assert dropped_items(text) == []

    window.subs_combo.setCurrentIndex(window.subs_combo.findData("none"))
    placed = window.take_files([str(tmp_path / "vod.mp4"), str(tmp_path / "vod.live_chat.json"), str(tmp_path / "vod.info.json"), str(tmp_path / "vod.ja.vtt"), str(tmp_path / "readme.txt"), str(tmp_path / "shot.png")])
    assert placed == ["video", "chat", "info", "subtitles"]  # what the window has no box for is left alone
    assert window.video_edit.text().endswith("vod.mp4") and window.chat_edit.text().endswith("vod.live_chat.json")
    assert window.info_edit.text().endswith("vod.info.json") and window.subs_edit.text().endswith("vod.ja.vtt")
    assert window.subs_combo.currentData() == "file" and "파일 4개 입력됨" in window.status.text()
    assert window.acceptDrops() and window.take_files([]) == []
    window.take_files(["https://www.youtube.com/watch?v=abc"])
    assert window.video_edit.text() == "https://www.youtube.com/watch?v=abc"


def test_launcher_sends_dropped_files_where_they_belong(app, tmp_path):
    from PIL import Image

    from stream2clip.gui.launcher import LauncherWindow

    image = tmp_path / "shot.png"
    Image.new("RGB", (64, 48), "#335577").save(image)
    launcher = LauncherWindow()
    assert launcher.acceptDrops()
    assert launcher.take_files([str(image), str(tmp_path / "vod.mp4"), str(tmp_path / "chat.csv"), str(tmp_path / "notes.txt")]) == ["image", "video", "chat"]
    assert len(launcher.editors) == 1
    assert launcher.highlights_window.video_edit.text().endswith("vod.mp4") and launcher.highlights_window.chat_edit.text().endswith("chat.csv")
    for editor in launcher.editors:
        editor.close()
    launcher.highlights_window.close()
    launcher.close()


@needs_ffmpeg
def test_export_for_an_editing_program_then_credit_and_compilation(app, window, stream_files, tmp_path):
    from PySide6.QtWidgets import QApplication

    video, chat = stream_files
    out = tmp_path / "clips"
    window.set_paths(video=str(video), chat=str(chat), output=str(out))
    window.audio_check.setChecked(False)
    assert not window.handoff_button.isEnabled()
    window.analyse()
    wait(app, lambda: not window.busy)
    assert window.handoff_button.isEnabled()

    window.handoff_button.click()
    assert sorted(p.name for p in window.last_handoff) == ["highlights.edl", "markers.edl", "timestamps.txt"]
    cuts = (out / "highlights.edl").read_text(encoding="utf-8")
    assert "* FROM CLIP NAME: vod.mp4" in cuts and "AA/V" in cuts and "TITLE: vod" in cuts
    times = (out / "timestamps.txt").read_text(encoding="utf-8")
    assert times.count("\n") == 1 and QApplication.clipboard().text() == times
    assert "편집용 파일 저장됨" in window.status.text() and "highlights.edl" in window.status.text()

    window.layout_combo.setCurrentIndex(window.layout_combo.findData("none"))
    window.format_combo.setCurrentIndex(window.format_combo.findData("mp4"))
    window.credit_edit.setText("Source: Test Channel")
    window.compile_check.setChecked(True)
    window.export()
    wait(app, lambda: not window.busy)
    assert window.last_compilation is not None and window.last_compilation.path == out / "compilation.mp4" and window.last_compilation.path.is_file()
    assert "모음 영상 compilation.mp4" in window.status.text() and (out / "compilation.txt").is_file()
    assert "Credit,,0,0,0,,Source: Test Channel" in (out / "clip_01.ass").read_text(encoding="utf-8")

    window.remember()
    again = HighlightsWindow()
    assert again.credit_edit.text() == "Source: Test Channel" and again.compile_check.isChecked()
    again.close()

    # A stream address has no file to cut from: the timestamp list is all there is to hand over.
    window.video_edit.setText("https://www.youtube.com/watch?v=abc")
    window.output_edit.setText(str(tmp_path / "other"))
    window.export_handoff()
    assert [p.name for p in window.last_handoff] == ["timestamps.txt"] and "영상 파일이 있어야" in window.status.text()
    assert not (tmp_path / "other" / "highlights.edl").exists()


@needs_ffmpeg
def test_music_and_a_sound_effect_from_the_window(app, window, stream_files, tmp_path):
    from stream2clip.soundtrack import SoundLibrary, write_wav

    video, chat = stream_files
    out = tmp_path / "clips"
    song = write_wav(0.1 * np.sin(2 * np.pi * 1500 * np.arange(48000) / 48000), tmp_path / "song.wav")
    SoundLibrary().add(song, name="song", license="cc-by-4.0", title="Song", author="Ann")  # the app's own library (an empty folder in tests)
    window.set_paths(video=str(video), chat=str(chat), output=str(out))
    window.audio_check.setChecked(False)
    window.analyse()
    wait(app, lambda: not window.busy)
    window.layout_combo.setCurrentIndex(window.layout_combo.findData("none"))
    window.format_combo.setCurrentIndex(window.format_combo.findData("gif"))
    window.bgm_edit.setText("song")
    window.export()
    assert "MP4, WebM" in window.status.text()  # a GIF has no sound to put music in
    window.format_combo.setCurrentIndex(window.format_combo.findData("mp4"))
    window.sfx_combo.setCurrentIndex(window.sfx_combo.findData("auto"))
    window.sfx_time_combo.setCurrentIndex(window.sfx_time_combo.findData("start"))
    window.export()
    wait(app, lambda: not window.busy)
    sounds = window.last_results[0].sounds
    assert [(s.sound.label, s.at) for s in sounds] == [("song", 0.0), ("pop", 0.0)]  # chat laughed (草): the auto effect is a pop
    assert "저장됨" in window.status.text()
    window.remember()
    again = HighlightsWindow()
    assert again.bgm_edit.text() == "song" and again.sfx_combo.currentData() == "auto" and again.sfx_time_combo.currentData() == "start"
    again.close()


def test_sound_library_window(app, window, tmp_path):
    from stream2clip.gui.sounds import SoundEntryDialog
    from stream2clip.soundtrack import SoundLibrary, synth, write_wav

    downloaded = write_wav(synth("ding"), tmp_path / "Downloads" / "cafe.wav")
    entry = SoundEntryDialog(str(downloaded))
    assert entry.name_edit.text() == "cafe" and not entry.ok_button.isEnabled()  # a license has to be chosen
    entry.license_combo.setCurrentIndex(entry.license_combo.findData("otologic"))
    entry.title_edit.setText("Cafe")
    assert entry.ok_button.isEnabled() and "BGM by OtoLogic(CC BY 4.0)" in entry.preview.text()
    entry.license_combo.setCurrentIndex(entry.license_combo.findData("cc-by-nd-4.0"))
    assert "x " in entry.preview.text()  # an error: ND may not be put to picture
    entry.license_combo.setCurrentIndex(entry.license_combo.findData("otologic"))
    facts = entry.facts()
    entry.close()

    dialog = window.open_sound_library()  # tests: built, not shown modally
    assert dialog.table.rowCount() == 0 and not dialog.use_button.isEnabled()
    dialog.add_file(str(downloaded), facts)
    dialog.add_file(str(downloaded), {**facts, "name": "pop2", "kind": "sfx", "license": "cc0"})
    assert dialog.table.rowCount() == 2 and dialog.table.item(0, 2).text() == "OtoLogic, CC BY 4.0"
    assert SoundLibrary().find("cafe").path.parent == SoundLibrary().folder  # copied into the app's library
    dialog.table.selectRow(1)
    dialog.use_selected()  # an effect is not music: nothing is picked
    assert window.bgm_edit.text() == ""
    dialog.table.selectRow(0)
    dialog.use_selected()
    assert window.bgm_edit.text() == "cafe"
    dialog.table.selectRow(1)
    dialog.remove_selected()
    assert dialog.table.rowCount() == 1 and SoundLibrary().find("pop2") is None

    assert not window.loudness_check.isChecked()
    window.loudness_check.setChecked(True)
    window.remember()
    again = HighlightsWindow()
    assert again.loudness_check.isChecked() and again.bgm_edit.text() == "cafe"
    again.close()


@needs_ffmpeg
def test_quiet_parts_are_shortened_when_asked(app, window, tmp_path):
    from stream2clip.export import probe

    # 60 s: a tone for the first two seconds of every ten, silence otherwise; the chat bursts at 0:30.
    video = tmp_path / "vod.mp4"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=160x90:r=10:d=60",
         "-f", "lavfi", "-i", "aevalsrc='0.5*sin(2*PI*440*t)*lt(mod(t,10),2)':s=48000:d=60", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", str(video)],
        check=True,
    )
    rows = ["time,author,text"] + [f"{t}.5,u{t % 9},hm" for t in range(0, 60, 2)] + [f"{36 + i * 0.07:.2f},r{i},lol" for i in range(80)]
    chat = tmp_path / "chat.csv"
    chat.write_text("\n".join(rows), encoding="utf-8")
    out = tmp_path / "clips"
    window.set_paths(video=str(video), chat=str(chat), output=str(out))
    window.audio_check.setChecked(False)
    window.analyse()
    wait(app, lambda: not window.busy)
    assert window.list.count() >= 1
    h = window.timeline.highlights[0]
    h.start, h.end = 20.0, 50.0
    window.layout_combo.setCurrentIndex(window.layout_combo.findData("none"))
    window.format_combo.setCurrentIndex(window.format_combo.findData("mp4"))
    assert not window.silence_check.isChecked()  # off unless asked for
    window.silence_check.setChecked(True)
    window.export()
    wait(app, lambda: not window.busy)
    result = window.last_results[0]
    assert result.removed == pytest.approx(3 * 7.5, abs=1.5)  # three 8 s silences, each cut down to half a second
    assert probe(result.path).duration == pytest.approx(30.0 - result.removed, abs=0.4)
    assert "조용한 부분" in window.status.text() and "초 줄임" in window.status.text()
    window.remember()
    again = HighlightsWindow()
    assert again.silence_check.isChecked()
    again.close()


# ----------------------------------------------------------------------------- session files


def write_session(path, events, started=1000.0):
    """A session file with the given (time, type, data) events."""
    from stream2clip.session import SCHEMA

    lines = [json.dumps({"schema": SCHEMA, "started": started})] + [json.dumps({"t": t, "type": kind, **data}) for t, kind, data in events]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def recorded_session(path):
    """Recorded from 1000: OBS records from 1010. A waiting scene for the first 20 s of the recording, then a game scene with a chat burst at 0:45."""
    events = [(1000, "scene", {"name": "대기 화면"}), (1010, "output", {"output": "record", "active": True}), (1030, "scene", {"name": "Game"})]
    events += [(1010 + second + 0.5, "chat", {"text": "hi", "author": f"a{second}"}) for second in range(0, 60, 2)]
    events += [(1055 + i * 0.07, "chat", {"text": "ㅋㅋㅋㅋ", "author": f"w{i}"}) for i in range(80)]
    return write_session(path, events)


def test_a_session_file_is_told_from_a_chat_log_and_put_in_its_box(app, window, tmp_path):
    from stream2clip.gui.highlights import kind_of

    session = recorded_session(tmp_path / "stream.jsonl")
    plain = tmp_path / "chat.jsonl"
    plain.write_text(json.dumps({"time": 1.0, "author": "a", "text": "hi"}) + "\n", encoding="utf-8")
    assert kind_of(str(session)) == "session" and kind_of(str(plain)) == "chat" and kind_of(str(tmp_path / "missing.jsonl")) == "chat"

    for widget in (window.origin_combo, window.offset_spin, window.skip_scene_edit, window.motion_check):
        assert not widget.isEnabled()  # nothing to set without a session
    assert window.take_files([str(session), str(plain)]) == ["session", "chat"]
    assert window.session_edit.text() == str(session) and window.chat_edit.text() == str(plain)
    assert window.origin_combo.isEnabled() and window.skip_scene_edit.isEnabled() and window.motion_check.isEnabled()

    window.set_paths()
    window.chat_edit.setText(str(session))  # the box people know: a session put there moves to its own
    assert window.chat_edit.text() == "" and window.session_edit.text() == str(session) and "세션 칸으로" in window.status.text()
    window.chat_edit.setText(str(plain))
    assert window.chat_edit.text() == str(plain)
    assert [window.origin_combo.itemData(i) for i in range(window.origin_combo.count())] == ["auto", "stream", "record", "session"]
    assert window.audio_track() is None and window.track_spin.text() == "기본"
    window.track_spin.setValue(2)
    assert window.audio_track() == 1  # the box counts from 1 like OBS, ffmpeg from 0
    window.skip_scene_edit.setText(" 대기 , ,휴식")
    assert window.skipped_scenes() == ["대기", "휴식"]


@needs_ffmpeg
def test_session_stands_in_for_the_chat_and_its_scenes_leave_highlights_out(app, window, stream_files, tmp_path):
    video, _chat = stream_files
    session = recorded_session(tmp_path / "stream.jsonl")
    window.set_paths(video=str(video), session=str(session), output=str(tmp_path / "clips"))
    window.audio_check.setChecked(False)
    window.analyse()
    wait(app, lambda: not window.busy)
    found = [(h.start, h.end) for h in window.timeline.highlights]
    assert len(found) == 1 and "채팅 110개" in window.status.text(), window.status.text()  # 30 + 80 lines of the session
    assert found[0][0] < 37 < found[0][1]  # the burst at 0:45 of the recording, less the chat delay: second 0 is the recording's start, not the session's

    window.skip_scene_edit.setText("대기")  # the highlight is in the game scene: it stays
    window.analyse()
    wait(app, lambda: not window.busy)
    assert len(window.timeline.highlights) == 1 and window.scenes_skipped == 0 and "장면으로 제외" not in window.status.text()
    window.skip_scene_edit.setText("휴식, game")
    window.analyse()
    wait(app, lambda: not window.busy)
    assert not window.timeline.highlights and window.scenes_skipped == 1 and "장면으로 제외 1개" in window.status.text(), window.status.text()

    window.skip_scene_edit.clear()
    window.offset_spin.setValue(10.0)  # the video starts ten seconds after the recording began: everything is that much earlier in it
    window.analyse()
    wait(app, lambda: not window.busy)
    shifted = [(h.start, h.end) for h in window.timeline.highlights]
    assert len(shifted) == 1 and shifted[0][1] == pytest.approx(found[0][1] - 10.0, abs=5.5), (found, shifted)
    assert window.scenes_skipped == 0 and "채팅 105개" in window.status.text()  # five lines came before the video began

    window.origin_combo.setCurrentIndex(window.origin_combo.findData("stream"))
    window.analyse()
    wait(app, lambda: not window.busy)
    assert window.status.text() == "실패: 세션에 OBS 송출 시작 기록이 없습니다. 다른 0초 기준을 고르세요."
    window.origin_combo.setCurrentIndex(window.origin_combo.findData("auto"))
    window.session_edit.setText(str(tmp_path / "gone.jsonl"))
    window.analyse()
    wait(app, lambda: not window.busy)
    assert window.status.text().startswith("실패: 세션 파일을 찾을 수 없습니다")


@needs_ffmpeg
def test_avatar_motion_and_audio_track_reach_the_detector_and_the_clips(app, window, stream_files, tmp_path, monkeypatch):
    from stream2clip import pipeline

    video, _chat = stream_files
    events = [(1000, "output", {"output": "record", "active": True})]
    events += [(1000 + second + 0.5, "chat", {"text": "hi", "author": f"a{second}"}) for second in range(0, 60, 2)]
    events += [(1036 + i * 0.07, "chat", {"text": "ㅋㅋㅋㅋ", "author": f"w{i}"}) for i in range(80)]
    quiet = write_session(tmp_path / "quiet.jsonl", events)
    moving = write_session(tmp_path / "moving.jsonl", events + [(1000 + i * 0.2, "avatar_params", {"values": {"ParamAngleX": 30.0 if 150 <= i < 175 and i % 2 else 0.0}}) for i in range(300)])
    seen = {}
    find, make = pipeline.find_highlights, pipeline.make_clips
    monkeypatch.setattr(pipeline, "find_highlights", lambda *args, **kwargs: seen.update(find=kwargs) or find(*args, **kwargs))
    monkeypatch.setattr(pipeline, "make_clips", lambda *args, **kwargs: seen.update(make=kwargs) or make(*args, **kwargs))

    window.set_paths(video=str(video), session=str(quiet), output=str(tmp_path / "clips"))
    window.audio_check.setChecked(False)
    window.motion_check.setChecked(True)
    window.analyse()
    wait(app, lambda: not window.busy)
    assert window.status.text().startswith("실패: 세션에 아바타 움직임 기록이 없습니다")  # asked for, but this session has none

    window.session_edit.setText(str(moving))
    window.track_spin.setValue(1)
    window.analyse()
    wait(app, lambda: not window.busy)
    assert seen["find"]["avatar"] is not None and seen["find"]["avatar"].any() and seen["find"]["audio_track"] == 0
    assert len(seen["find"]["messages"]) == 110 and seen["find"]["chat"] is None
    assert window.list.count() >= 1

    window.motion_check.setChecked(False)
    window.track_spin.setValue(0)
    window.analyse()
    wait(app, lambda: not window.busy)
    assert seen["find"]["avatar"] is None and seen["find"]["audio_track"] is None

    window.track_spin.setValue(1)
    window.layout_combo.setCurrentIndex(window.layout_combo.findData("none"))
    window.format_combo.setCurrentIndex(window.format_combo.findData("mp4"))
    window.export()
    wait(app, lambda: not window.busy)
    assert seen["make"]["audio_track"] == 0 and window.last_results

    window.origin_combo.setCurrentIndex(window.origin_combo.findData("record"))
    window.offset_spin.setValue(-2.5)
    window.skip_scene_edit.setText("대기")
    window.motion_check.setChecked(True)
    window.track_spin.setValue(2)
    window.remember()
    again = HighlightsWindow()
    assert (again.origin_combo.currentData(), again.offset_spin.value(), again.skip_scene_edit.text(), again.motion_check.isChecked(), again.track_spin.value()) == ("record", -2.5, "대기", True, 2)
    assert again.session_edit.text() == ""  # which file is not remembered, like the video and the chat
    again.close()


@needs_ffmpeg
def test_avatar_box_comes_from_the_sessions_outline(app, window, stream_files, tmp_path):
    video, _chat = stream_files  # 160 x 90
    # VTube Studio fills the right half of a 1920 x 1080 canvas; the model stands in the middle of its window.
    transform = {"sourceWidth": 1920, "sourceHeight": 1080, "positionX": 960, "positionY": 0, "scaleX": 0.5, "scaleY": 1.0, "alignment": 5}
    events = [(1000, "output", {"output": "record", "active": True}), (1000, "obs_video", {"base": [1920, 1080], "output": [160, 90]}),
              (1000, "avatar_source", {"source": "VTS", "scene": "Game", "transform": transform})]
    events += [(1001 + i, "avatar_outline", {"hull": [[-0.5, 0.8], [0.5, 0.8], [0.5, -1.4], [-0.5, -1.4]], "window": [1920, 1080]}) for i in range(40)]
    with_outline = write_session(tmp_path / "vts.jsonl", events)
    without = write_session(tmp_path / "plain.jsonl", events[:1])

    assert not window.session_avatar_button.isEnabled()  # no session, and the default layout takes no avatar
    window.set_paths(video=str(video), session=str(with_outline))
    assert not window.session_avatar_button.isEnabled()
    window.layout_combo.setCurrentIndex(window.layout_combo.findData("stack"))
    assert window.session_avatar_button.isEnabled()
    window.session_avatar_button.click()
    assert window.avatar_edit.text(), window.status.text()
    box = Region.parse(window.avatar_edit.text())
    # the model on the canvas: x 960 + (0.25..0.75) x 960 = 1200..1680; in the 160 px wide video 100..140
    assert box.x <= 100 and box.x + box.width >= 140 and box.x >= 80 and "세션의 VTube Studio 윤곽" in window.status.text()

    window.avatar_edit.clear()
    window.session_edit.setText(str(without))
    window.session_avatar_button.click()
    assert window.avatar_edit.text() == "" and window.status.text().startswith("실패: 세션에 VTube Studio 윤곽 기록이 없습니다")
    window.session_edit.setText(str(with_outline))
    window.video_edit.setText("https://www.youtube.com/watch?v=abc")
    window.session_avatar()
    assert window.status.text().startswith("실패: 세션의 아바타 위치는 녹화 파일이 있어야")
    window.video_edit.setText(str(video))
    window.session_edit.clear()
    assert not window.session_avatar_button.isEnabled()



@needs_ffmpeg
def test_form_sets_the_lengths_and_the_opening_reaches_the_clips(app, window, stream_files, tmp_path, monkeypatch):
    from stream2clip import pipeline

    video, chat = stream_files
    seen = {}
    find, make = pipeline.find_highlights, pipeline.make_clips
    monkeypatch.setattr(pipeline, "find_highlights", lambda *args, **kwargs: seen.update(find=kwargs) or find(*args, **kwargs))
    monkeypatch.setattr(pipeline, "make_clips", lambda *args, **kwargs: seen.update(make=kwargs) or make(*args, **kwargs))

    assert window.preset_combo.currentData() == "shorts" and not window.context_check.isChecked()
    window.apply_preset("long")
    assert window.layout_combo.currentData() == "none" and window.compile_check.isChecked() and window.top_spin.value() == 6
    window.apply_preset("clip")
    assert window.layout_combo.currentData() == "none" and not window.compile_check.isChecked()
    assert window.context_check.isChecked() and window.top_spin.value() == 8

    window.set_paths(video=str(video), chat=str(chat), output=str(tmp_path / "clips"))
    window.audio_check.setChecked(False)
    window.analyse()
    wait(app, lambda: not window.busy)
    config = seen["find"]["config"]
    assert (config.lead, config.tail, config.min_length, config.max_length) == (45.0, 30.0, 60.0, 180.0)
    assert window.list.count() == 1

    window.teaser_check.setChecked(True)
    window.thumbnail_check.setChecked(True)
    window.format_combo.setCurrentIndex(window.format_combo.findData("mp4"))
    window.export()
    wait(app, lambda: not window.busy, 120)
    assert (seen["make"]["context"], seen["make"]["teaser"], seen["make"]["thumbnails"]) == ("auto", 2.0, True)
    clip = window.last_results[0]
    assert clip.teaser > 0 and clip.thumbnail is not None and clip.thumbnail.exists()
    dialog = window.open_upload()
    assert dialog.thumbnail_edit.text() == str(clip.thumbnail)  # the clip's thumbnail goes up with it
    dialog.close()

    window.remember()
    again = HighlightsWindow()
    assert again.preset_combo.currentData() == "clip"
    assert again.context_check.isChecked() and again.teaser_check.isChecked() and again.thumbnail_check.isChecked()
    again.close()


@needs_ffmpeg
def test_larger_models_and_the_glossary_reach_the_transcriber(app, window, stream_files, tmp_path, monkeypatch):
    from stream2clip import subtitles
    from stream2clip.subtitles import Cue

    made = []

    class Transcriber:
        def __init__(self, model, *, hotwords=()):
            made.append((model, list(hotwords)))

        def transcribe(self, path, *, language=None):
            return [Cue(0.0, 1.0, "ペコラです")]

    monkeypatch.setattr(subtitles, "FasterWhisperTranscriber", Transcriber)
    models = [window.subs_combo.itemData(i) for i in range(window.subs_combo.count())]
    assert models[-4:] == ["small", "medium", "large-v3-turbo", "large-v3"]

    video, chat = stream_files
    glossary = tmp_path / "names.csv"
    glossary.write_text("source,target,note,heard\nぺこら,,,ペコラ\n", encoding="utf-8")
    window.set_paths(video=str(video), chat=str(chat), output=str(tmp_path / "clips"))
    window.audio_check.setChecked(False)
    window.analyse()
    wait(app, lambda: not window.busy)
    window.subs_combo.setCurrentIndex(window.subs_combo.findData("large-v3-turbo"))
    window.glossary_edit.setText(str(glossary))
    window.layout_combo.setCurrentIndex(window.layout_combo.findData("none"))
    window.format_combo.setCurrentIndex(window.format_combo.findData("mp4"))
    window.export()
    wait(app, lambda: not window.busy, 120)
    assert made == [("large-v3-turbo", ["ぺこら"])]  # the names are hints even without a translator
    assert "ぺこらです" in window.last_results[0].subtitles.read_text(encoding="utf-8")  # and the misheard one is fixed
