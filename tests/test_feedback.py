"""The local record of kept and left-out highlight candidates (feedback.jsonl)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from stream2clip import feedback
from stream2clip.cli import main
from stream2clip.highlights import Highlight


def test_record_load_and_choices(tmp_path):
    path = tmp_path / "feedback.jsonl"
    highlights = [Highlight(1, 100.0, 160.0, 130.0, 4.2, reasons=["草 x40"]), Highlight(2, 300.0, 340.0, 320.0, 2.1)]
    found = [(95.0, 160.0), (300.0, 340.0)]  # the first one was dragged 5 s later
    source = {"url": "https://www.youtube.com/watch?v=abc", "title": "配信", "channel": "", "heatmap": [1, 2]}
    when = datetime(2026, 11, 22, 12, 0, tzinfo=timezone.utc)
    feedback.record(path, highlights, [True, False], found=found, source=source, video="C:/vod/video.mp4", duration=3600.0, now=when)
    path.open("a", encoding="utf-8").write("not json\n")  # a damaged line is skipped, not fatal
    entries = feedback.load(path)
    assert len(entries) == 1
    entry = entries[0]
    assert entry["schema"] == feedback.SCHEMA and entry["at"] == "2026-11-22T12:00:00+00:00" and entry["action"] == "clips"
    assert entry["source"] == {"url": "https://www.youtube.com/watch?v=abc", "title": "配信"}  # only what names the stream
    assert entry["video"] == "video.mp4" and entry["duration"] == 3600.0
    first, second = entry["candidates"]
    assert first["kept"] and first["moved"] and first["found"] == [95.0, 160.0] and first["reasons"] == ["草 x40"]
    assert not second["kept"] and not second["moved"]

    # Exported again with the second one kept after all: the later choice wins.
    feedback.record(path, highlights, [True, True], found=found, source=source, video="video.mp4", action="edit")
    assert feedback.choices(feedback.load(path), url=source["url"]) == [(100.0, 160.0, True), (300.0, 340.0, True)]
    assert feedback.choices(feedback.load(path), video="D:/other/video.mp4") == []  # the address decides when there is one
    assert feedback.summary(feedback.load(path)) == ["配信: 2 exports, kept 3 of 4, moved 2"]
    assert feedback.load(tmp_path / "none.jsonl") == []


def test_feedback_command(tmp_path, capsys):
    path = tmp_path / "feedback.jsonl"
    feedback.record(path, [Highlight(1, 0.0, 30.0, 10.0, 1.0)], [True], video="vod.mp4")
    assert main(["feedback", "--file", str(path)]) == 0
    out = capsys.readouterr().out
    assert "1 exports" in out and "vod.mp4: 1 exports, kept 1 of 1, moved 0" in out
    assert main(["feedback", "--file", str(path), "--clear"]) == 0 and not path.exists()
    assert main(["feedback", "--file", str(path), "--clear"]) == 0 and "nothing to delete" in capsys.readouterr().out


def test_default_place_is_the_settings_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("STREAM2CLIP_CONFIG_DIR", str(tmp_path / "cfg"))
    assert feedback.default_path() == tmp_path / "cfg" / "feedback.jsonl"
    feedback.record(None, [Highlight(1, 0.0, 30.0, 10.0, 1.0)], [False])
    assert json.loads((tmp_path / "cfg" / "feedback.jsonl").read_text(encoding="utf-8"))["candidates"][0]["kept"] is False
