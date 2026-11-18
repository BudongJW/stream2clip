from __future__ import annotations

import json
import shlex

import pytest
from PIL import Image

from stream2clip.cli import main, parse_time

from .conftest import needs_ffmpeg


def test_parse_time():
    assert parse_time("90") == 90
    assert parse_time("1:30") == 90
    assert parse_time("01:02:03.5") == 3723.5


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
