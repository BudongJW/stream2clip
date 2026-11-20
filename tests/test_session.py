"""Session files: writing, reading, time 0, scenes, and placing VTube Studio's outline in the video."""

from __future__ import annotations

import json
from importlib.resources import files

import numpy as np
import pytest

from stream2clip.chat import ChatMessage, load_chat
from stream2clip.geometry import Region
from stream2clip.highlights import HighlightConfig, detect_highlights
from stream2clip.session import (
    SCHEMA,
    SceneSpan,
    SessionWriter,
    avatar_region,
    is_session,
    item_placement,
    load_session,
    skip_scenes,
    vts_to_source,
)


class Clock:
    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def _schema():
    return json.loads(files("stream2clip").joinpath("schemas/session.v1.schema.json").read_text(encoding="utf-8"))


def test_every_line_written_follows_the_schema(tmp_path):
    jsonschema = pytest.importorskip("jsonschema")
    clock = Clock()
    path = tmp_path / "s.jsonl"
    with SessionWriter(path, sources={"chat": "chzzk"}, clock=clock) as w:
        w.write("output", output="stream", active=True)
        w.chat(ChatMessage(time=1001.5, text="ㅋㅋㅋ", author="a1b2c3", kind="paid", amount=1000.0, currency="KRW", emotes=(":hi:",), role="moderator"))
        w.chat(ChatMessage(time=float("nan"), text="no time of its own"))
        w.write("marker", by="hotkey")
        w.write("scene", name="Game")
        w.write("obs_video", base=[1920, 1080], output=[1280, 720])
        w.write("avatar_source", source="VTS", scene="Game", transform={"positionX": 0})
        w.write("avatar_outline", hull=[[0, 0], [1, 0], [0, 1]], window=[1920, 1080])
        w.write("avatar_params", values={"ParamMouthOpenY": 0.5, "Broken": float("nan")})
        w.write("avatar_model", name="Kiri", id="abc")
        w.write("surge", score=4.2, reasons=["chat x3"])
        w.write("replay_saved", path="C:/replay.mkv")
        w.write("status", source="obs", state="connected")
        w.write("something_new", whatever=1)  # readers skip what they do not know
    lines = path.read_text(encoding="utf-8").splitlines()
    validator = jsonschema.Draft202012Validator(_schema())
    for line in lines:
        validator.validate(json.loads(line))
    assert json.loads(lines[0])["schema"] == SCHEMA
    assert json.loads(lines[2])["t"] == 1001.5
    assert json.loads(lines[3])["t"] == 1000.0  # a message without a time happened now
    assert json.loads(lines[9])["values"] == {"ParamMouthOpenY": 0.5}  # NaN is not JSON: the entry is left out
    with pytest.raises(jsonschema.ValidationError):
        validator.validate({"t": 1, "type": "chat"})  # a chat event needs its text
    with pytest.raises(ValueError):
        SessionWriter(tmp_path / "x.jsonl").write("Bad Type")


def test_reading_skips_a_cut_off_last_line_and_knows_the_file(tmp_path):
    path = tmp_path / "s.jsonl"
    with SessionWriter(path, clock=Clock()) as w:
        w.write("scene", name="Talk")
    path.write_text(path.read_text(encoding="utf-8") + '{"t": 1002, "type": "sce', encoding="utf-8")
    session = load_session(path)
    assert [e.type for e in session.events] == ["scene"]
    assert is_session(path) and is_session(str(path))
    other = tmp_path / "chat.jsonl"
    other.write_text('{"time": 1, "text": "hi"}\n', encoding="utf-8")
    assert not is_session(other)
    with pytest.raises(ValueError, match="not a stream2clip session"):
        load_session(other)


def _session(tmp_path, events, started=1000.0):
    path = tmp_path / "s.jsonl"
    lines = [json.dumps({"schema": SCHEMA, "started": started})] + [json.dumps({"t": t, "type": kind, **data}) for t, kind, data in events]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return load_session(path)


def test_time_zero_is_the_stream_start_then_the_recording_then_the_session(tmp_path):
    s = _session(tmp_path, [(1010, "output", {"output": "record", "active": True}), (1020, "output", {"output": "stream", "active": True})])
    assert s.origin() == 1020 and s.origin("record") == 1010 and s.origin("session") == 1000
    s = _session(tmp_path, [(1010, "output", {"output": "record", "active": True})])
    assert s.origin() == 1010
    with pytest.raises(ValueError, match="did not start streaming"):
        s.origin("stream")
    assert _session(tmp_path, []).origin() == 1000


def test_chat_and_markers_become_messages_timed_from_the_stream(tmp_path):
    s = _session(tmp_path, [
        (1005, "chat", {"text": "before the stream"}),
        (1010, "output", {"output": "stream", "active": True}),
        (1100, "chat", {"text": "ㅋㅋ", "author": "x", "kind": "paid", "amount": 500, "currency": "KRW", "role": "owner"}),
        (1200, "marker", {"by": "hotkey"}),
    ])
    messages = s.messages(marker_delay=8.0)
    assert [(m.time, m.text) for m in messages] == [(90.0, "ㅋㅋ"), (198.0, "!clip")]
    assert messages[0].is_paid and messages[0].role == "owner"
    assert messages[1].role == "owner"
    # load_chat reads a session file like any other chat archive
    assert [m.text for m in load_chat(s.path)] == ["ㅋㅋ", "!clip"]
    # ... and the hotkey marker lands on the press: the chat delay comes off again
    result = detect_highlights(messages, duration=600, config=HighlightConfig(chat_delay=8.0, lead=20, tail=10))
    marked = [h for h in result.highlights if h.stats.get("marker")]
    assert marked and abs(marked[0].peak - 190.0) < 1e-6


def test_scenes_are_spans_and_can_be_left_out(tmp_path):
    s = _session(tmp_path, [
        (1000, "scene", {"name": "대기 화면"}),
        (1000, "output", {"output": "stream", "active": True}),
        (1300, "scene", {"name": "Game"}),
        (2000, "scene", {"name": "Ending (대기)"}),
        (2100, "chat", {"text": "bye"}),
    ])
    assert s.scenes() == [SceneSpan(0.0, 300.0, "대기 화면"), SceneSpan(300.0, 1000.0, "Game"), SceneSpan(1000.0, 1100.0, "Ending (대기)")]

    class H:
        def __init__(self, start, end):
            self.start, self.end = start, end

    kept = skip_scenes([H(100, 150), H(280, 340), H(500, 560), H(990, 1040)], s.scenes(), ["대기"])
    assert [(h.start, h.end) for h in kept] == [(280, 340), (500, 560)]


# ----------------------------------------------------------------------------- OBS placement


def test_a_scaled_cropped_source_at_its_top_left_corner():
    p = item_placement({"sourceWidth": 1920, "sourceHeight": 1080, "positionX": 1000, "positionY": 200, "scaleX": 0.5, "scaleY": 0.5,
                        "cropLeft": 100, "cropTop": 40, "alignment": 5, "boundsType": "OBS_BOUNDS_NONE"})
    assert np.allclose(p.to_canvas(np.array([[100, 40], [1920, 1080]])), [[1000, 200], [1910, 720]])
    assert p.visible == (1000, 200, 1910, 720)


def test_the_alignment_says_which_point_the_position_is():
    centre = item_placement({"sourceWidth": 200, "sourceHeight": 100, "positionX": 500, "positionY": 300, "scaleX": 1, "scaleY": 1, "alignment": 0})
    assert (centre.left, centre.top) == (400, 250)
    bottom_right = item_placement({"sourceWidth": 200, "sourceHeight": 100, "positionX": 500, "positionY": 300, "scaleX": 2, "scaleY": 2, "alignment": 2 | 8})
    assert (bottom_right.left, bottom_right.top) == (100, 100)


def test_a_bounding_box_sizes_the_source_like_obs_does():
    t = {"sourceWidth": 1000, "sourceHeight": 1000, "positionX": 0, "positionY": 0, "alignment": 5, "boundsWidth": 400, "boundsHeight": 200, "boundsAlignment": 0}
    inner = item_placement({**t, "boundsType": "OBS_BOUNDS_SCALE_INNER"})
    assert (inner.scale_x, inner.left, inner.top) == (0.2, 100.0, 0.0)  # 200 x 200, centred in the 400 x 200 box
    outer = item_placement({**t, "boundsType": "OBS_BOUNDS_SCALE_OUTER"})
    assert outer.scale_x == 0.4 and outer.visible == (0.0, 0.0, 400.0, 200.0)  # 400 x 400, cut to the box
    stretch = item_placement({**t, "boundsType": "OBS_BOUNDS_STRETCH"})
    assert (stretch.scale_x, stretch.scale_y) == (0.4, 0.2)
    assert item_placement({**t, "boundsType": "OBS_BOUNDS_MAX_ONLY", "boundsWidth": 4000, "boundsHeight": 4000}).scale_x == 1.0


def test_rotated_or_empty_sources_are_refused():
    with pytest.raises(ValueError, match="rotated"):
        item_placement({"sourceWidth": 10, "sourceHeight": 10, "rotation": 90})
    assert item_placement({"sourceWidth": 10, "sourceHeight": 10, "rotation": 360, "scaleX": 1, "scaleY": 1}).left == 0
    with pytest.raises(ValueError, match="no size"):
        item_placement({})


def test_vts_coordinates_run_left_to_right_and_bottom_to_top():
    assert np.allclose(vts_to_source(np.array([[-1, 1], [1, -1], [0, 0]]), (1920, 1080)), [[0, 0], [1920, 1080], [960, 540]])


def _outline(t, x0, x1, y0, y1):
    """An outline (VTS coordinates) with the given extents."""
    return (t, "avatar_outline", {"hull": [[x0, y1], [x1, y1], [x1, y0], [x0, y0]], "window": [1920, 1080]})


def test_the_avatar_box_follows_the_outline_where_obs_shows_vts(tmp_path):
    # VTS fills the right half of a 1920 x 1080 canvas; the video is 1280 x 720.
    transform = {"sourceWidth": 1920, "sourceHeight": 1080, "positionX": 960, "positionY": 0, "scaleX": 0.5, "scaleY": 1.0, "alignment": 5}
    events = [
        (1000, "output", {"output": "stream", "active": True}),
        (1000, "obs_video", {"base": [1920, 1080], "output": [1280, 720]}),
        (1000, "avatar_source", {"source": "VTS", "scene": "Game", "transform": transform}),
    ]
    # the model: x -0.5..0.5 of the VTS window, from the top (y 0.8) down past the bottom edge
    events += [_outline(1001 + i, -0.5, 0.5, -1.4, 0.8) for i in range(20)]
    events += [_outline(1030, -1.0, -0.9, 0.9, 1.0)]  # one stray frame in a corner
    s = _session(tmp_path, events)
    box = avatar_region(s, (1280, 720), aspect=1.0)
    # model on the canvas: x 960 + (0.25..0.75) * 960 = 1200..1680, top (1 - 0.8) / 2 * 1080 = 108; in the video x 800..1120, top 72
    assert box is not None
    assert box.x <= 800 and box.x + box.width >= 1120 and box.width % 2 == 0 and box.height == box.width
    assert 50 <= box.y <= 72
    # a span with no outline in it: nothing to go by
    assert avatar_region(s, (1280, 720), aspect=1.0, spans=[(500, 600)]) is None


def test_without_obs_the_vts_box_can_be_given(tmp_path):
    s = _session(tmp_path, [_outline(1001 + i, -0.5, 0.5, -0.5, 0.5) for i in range(5)])
    box = avatar_region(s, (1920, 1080), aspect=2.0, vts_region=Region(1000, 100, 800, 800))
    # the model: x 1200..1600, y 300..700 of the video -> 400 wide, a 2:1 box is 400 x 200 ... grown by the margin
    assert box is not None and box.width == 2 * box.height
    assert 1150 <= box.x <= 1200 and box.x + box.width >= 1600
    assert avatar_region(_session(tmp_path, [_outline(1001, -0.5, 0.5, -0.5, 0.5)]), (1920, 1080), aspect=1.0) is None  # no placement known


def test_a_hidden_source_does_not_place_the_outline(tmp_path):
    s = _session(tmp_path, [
        (1000, "obs_video", {"base": [1920, 1080], "output": [1920, 1080]}),
        (1000, "avatar_source", {"source": "VTS", "scene": "Talk", "transform": {}}),
        _outline(1001, -0.5, 0.5, -0.5, 0.5),
    ])
    assert avatar_region(s, (1920, 1080), aspect=1.0) is None


# ----------------------------------------------------------------------------- the command line


def _recorded(tmp_path):
    """A session with a stream, an opening scene full of chat, a game scene and two hotkey markers."""
    events = [(1000, "output", {"output": "stream", "active": True}), (1000, "scene", {"name": "Opening (대기)"}), (1600, "scene", {"name": "Game"})]
    for second in range(0, 1200, 4):  # steady chat
        events.append((1000 + second, "chat", {"text": "hi", "author": f"a{second}"}))
    for second in range(100, 110):  # a burst while waiting
        events += [(1000 + second, "chat", {"text": "ㅋㅋㅋㅋ", "author": f"w{second}{i}"}) for i in range(8)]
    events += [(1900, "marker", {"by": "hotkey"}), (2100, "marker", {"by": "enter"})]
    return _session(tmp_path, events).path


def test_highlights_from_a_session_alone(tmp_path, capsys):
    from stream2clip.cli import main
    from stream2clip.highlights import load_highlights

    path = _recorded(tmp_path)
    out = tmp_path / "h.json"
    assert main(["highlights", "--session", str(path), "-o", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "session" in printed
    highlights = load_highlights(out)
    marked = sorted(h.peak for h in highlights if h.stats.get("marker"))
    assert marked == [900.0, 1100.0]  # the presses, in seconds from the stream start
    assert any(90 <= h.peak <= 115 for h in highlights)  # the burst in the opening
    # the opening scene is left out on request
    assert main(["highlights", "--session", str(path), "--skip-scene", "대기", "-o", str(out)]) == 0
    assert "1 highlights left out" in capsys.readouterr().out
    kept = load_highlights(out)
    assert not any(h.end < 600 for h in kept) and [h.rank for h in kept] == list(range(1, len(kept) + 1))
    assert main(["highlights", "--chat", str(path), "--skip-scene", "x", "-o", str(out)]) == 1
    assert "needs the scenes" in capsys.readouterr().err


def test_auto_takes_the_chat_from_the_session(tmp_path, capsys, monkeypatch):
    from stream2clip import cli

    fetched = {}

    def fake_fetch(url, out, *, info, chat, ytdlp, on_stage, warn):
        fetched.update(info=info, chat=chat)
        return None, None

    monkeypatch.setattr("stream2clip.sources.fetch_replay", fake_fetch)
    monkeypatch.setattr("stream2clip.sources.ytdlp_command", lambda **kw: ["yt-dlp"])
    args = cli.build_parser().parse_args(["auto", "https://chzzk.naver.com/video/123", "-o", str(tmp_path / "o"), "--session", str(_recorded(tmp_path))])
    cli._prepare_from_url(args, tmp_path / "o")
    assert fetched == {"info": True, "chat": False}  # the chat is in the session: no replay to fetch


def test_avatar_session_puts_the_box_where_the_model_is(tmp_path, capsys):
    from .conftest import HAS_FFMPEG

    if not HAS_FFMPEG:
        pytest.skip("ffmpeg/ffprobe not installed")
    import subprocess

    from stream2clip.cli import main

    video = tmp_path / "vod.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc=s=320x180:r=10:d=6", "-pix_fmt", "yuv420p", str(video)], check=True)
    events = [(1000, "output", {"output": "stream", "active": True})]
    events += [_outline(1000 + i * 0.5, 0.2, 0.8, -1.0, 0.9) for i in range(12)]
    session = _session(tmp_path, events).path
    highlights = tmp_path / "h.json"
    highlights.write_text(json.dumps({"highlights": [{"rank": 1, "start": 1.0, "end": 4.0, "peak": 2.0, "score": 3.0, "reasons": []}]}), encoding="utf-8")
    out = tmp_path / "clips"
    code = main(["clips", str(video), "--highlights", str(highlights), "-o", str(out), "--layout", "stack", "--avatar", "session", "--session", str(session),
                 "--vts-region", "160,0,160,180", "--size", "180x320", "--format", "mp4"])
    printed = capsys.readouterr()
    assert code == 0, printed.err
    line = next(text for text in printed.out.splitlines() if text.startswith("avatar"))
    box = Region.parse(line.split()[1])
    # the model is at x 0.2..0.8 of the VTS view, which is the right half of the video: x 256..304
    assert box.x <= 256 and box.x + box.width >= 304 and box.y <= 9
    assert list(out.glob("*.mp4"))
    # without --vts-region and without an OBS placement there is nothing to go by
    assert main(["clips", str(video), "--highlights", str(highlights), "-o", str(out), "--layout", "stack", "--avatar", "session", "--session", str(session)]) == 1
    assert "cannot be placed" in capsys.readouterr().err
