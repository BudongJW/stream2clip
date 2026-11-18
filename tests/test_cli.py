from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path

import pytest
from PIL import Image

from stream2clip.cli import main, parse_time

from .conftest import needs_ffmpeg


def test_parse_time():
    assert parse_time("90") == 90
    assert parse_time("1:30") == 90
    assert parse_time("01:02:03.5") == 3723.5


def test_output_survives_a_legacy_code_page(monkeypatch):
    """Found by running the built program on an English Windows runner: printing "채팅 급증" to a pipe crashed."""
    import io

    from stream2clip.cli import main as cli_main

    monkeypatch.delenv("PYTHONIOENCODING", raising=False)
    raw = io.BytesIO()
    piped = io.TextIOWrapper(raw, encoding="cp1252")  # what a redirected stdout looks like there
    monkeypatch.setattr(sys, "stdout", piped)
    chat = Path(__file__).parent / "data" / "youtube_real_excerpt.live_chat.json"
    assert cli_main(["highlights", "--chat", str(chat)]) == 0
    piped.flush()
    text = raw.getvalue().decode("utf-8")
    assert "채팅 급증" in text and "analysed 40 chat messages" in text

    # With an explicit PYTHONIOENCODING the encoding is kept and unknown characters are replaced, not fatal.
    monkeypatch.setenv("PYTHONIOENCODING", "cp1252")
    raw = io.BytesIO()
    piped = io.TextIOWrapper(raw, encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", piped)
    assert cli_main(["highlights", "--chat", str(chat)]) == 0
    piped.flush()
    assert b"analysed 40 chat messages" in raw.getvalue() and b"?" in raw.getvalue()


def test_print_command(capsys):
    assert main(["convert", "vod.mp4", "-o", "clip.webp", "--start", "1:00", "--end", "1:10", "--crop", "0,0,640,360", "--transparent", "--print-command"]) == 0
    cmd = shlex.split(capsys.readouterr().out)
    assert cmd[cmd.index("-ss") + 1] == "60.000" and cmd[-1] == "clip.webp"
    assert any("colorkey=0x00FF00" in part for part in cmd)


def test_mp4_transparent_is_an_error(capsys):
    assert main(["convert", "vod.mp4", "-o", "clip.mp4", "--transparent", "--print-command"]) == 1
    assert "transparency" in capsys.readouterr().err


@needs_ffmpeg
def test_convert_runs(green_screen_video, tmp_path):
    out = tmp_path / "c.gif"
    assert main(["convert", str(green_screen_video), "-o", str(out), "--fps", "5", "--width", "64", "--transparent"]) == 0
    assert Image.open(out).size == (64, 48)


def test_annotate(tmp_path):
    img = tmp_path / "in.png"
    Image.new("RGB", (40, 30), "white").save(img)
    doc = tmp_path / "a.json"
    doc.write_text(json.dumps({"schema": "stream2clip.annotation/v1", "items": [{"type": "rect", "rect": [5, 5, 10, 10], "color": "#FF0000", "width": 2}], "crop": [0, 0, 20, 20]}))
    out = tmp_path / "out.png"
    assert main(["annotate", str(img), "--annotations", str(doc), "-o", str(out)]) == 0
    assert Image.open(out).size == (20, 20)
    assert main(["annotate", str(img), "--annotations", str(doc), "-o", str(tmp_path / "ov.png"), "--overlay"]) == 0
    assert Image.open(tmp_path / "ov.png").getpixel((1, 1))[3] == 0


@pytest.mark.parametrize("bad", [["convert", "x.mp4", "-o", "x.unknown"]])
def test_unknown_extension(bad):
    with pytest.raises(SystemExit):
        main(bad)


@needs_ffmpeg
def test_auto_pipeline(green_screen_video, tmp_path, capsys):
    import random

    rng = random.Random(0)
    rows = ["time,author,text"]
    rows += [f"{rng.random() * 2:.2f},u{i % 7},hi" for i in range(10)]
    rows += [f"{1.0 + rng.random() * 0.3:.2f},r{i},草" for i in range(40)]
    chat = tmp_path / "chat.csv"
    chat.write_text("\n".join(rows), encoding="utf-8")
    out = tmp_path / "out"
    code = main(["auto", str(green_screen_video), "--chat", str(chat), "--window", "0.25", "--delay", "0", "--lead", "0.2",
                 "--tail", "0.2", "--min-length", "0.5", "--max-length", "1.5", "--threshold", "1.5",
                 "--size", "90x160", "--fps", "10", "--source-url", "https://youtu.be/x", "--source-title", "t", "--agency", "hololive", "-o", str(out)])
    text = capsys.readouterr().out
    assert code == 0, text
    assert (out / "highlights.json").exists() and (out / "timeline.png").exists() and (out / "clip_01.mp4").exists()
    assert "https://youtu.be/x" in (out / "clip_01.txt").read_text(encoding="utf-8")


def test_check_command(tmp_path, capsys):
    assert main(["check", "--list"]) == 0
    assert "hololive" in capsys.readouterr().out
    assert main(["check", "--agency", "hololive", "--source-url", "https://youtu.be/x", "--source-title", "t"]) == 0
    desc = tmp_path / "d.txt"
    desc.write_text("no link", encoding="utf-8")
    assert main(["check", "--agency", "hololive", "--source-url", "https://youtu.be/x", "--description", str(desc)]) == 1
