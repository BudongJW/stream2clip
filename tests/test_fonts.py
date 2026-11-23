"""The caption font catalog, the caption looks and places that use it, and how ffmpeg finds the fonts."""

from __future__ import annotations

import hashlib
import io
import re

import pytest

from stream2clip import fonts
from stream2clip.cli import main
from stream2clip.ffmpeg import ExportOptions, build_video_filter
from stream2clip.subtitles import SUBTITLE_POSITIONS, SUBTITLE_STYLES, Cue, SubtitleStyle, caption_font, subtitle_style, to_ass, with_available_font

from .conftest import needs_ffmpeg

PINNED = re.compile(r"^https://raw\.githubusercontent\.com/(google/fonts/[0-9a-f]{40}/ofl/|orioncactus/pretendard/v\d+\.\d+\.\d+/)")


def style_line(ass: str) -> list[str]:
    return next(line for line in ass.splitlines() if line.startswith("Style: Default,")).split(",")


def test_the_catalog_is_pinned_and_free():
    keys = [f.key for f in fonts.CAPTION_FONTS]
    families = [f.family.lower() for f in fonts.CAPTION_FONTS]
    assert len(keys) == len(set(keys)) >= 20 and len(families) == len(set(families))
    for font in fonts.CAPTION_FONTS:
        assert PINNED.match(font.url) and PINNED.match(font.licence_url), font.key  # one commit or one tag: the bytes cannot change
        assert re.fullmatch(r"[0-9a-f]{64}", font.sha256) and font.size > 10_000 and font.url.endswith("/" + font.file)
        assert set(font.scripts) <= {"ko", "ja", "en"} and set(font.roles) <= {"dialogue", "title", "emphasis", "cute", "handwriting", "game"}
        assert font.licence == "OFL-1.1"
    assert {s for f in fonts.CAPTION_FONTS for s in f.scripts} == {"ko", "ja", "en"}
    assert sum(1 for f in fonts.CAPTION_FONTS if "ko" in f.scripts) >= 10  # Korean clips first


def test_every_look_names_a_catalog_font_or_none():
    named = {name: style.font for name, style in SUBTITLE_STYLES.items() if style.font != "auto"}
    assert len(SUBTITLE_STYLES) >= 25 and len(named) >= 20
    assert all(fonts.find(font) is not None for font in named.values()), named
    assert fonts.find("Do Hyeon").key == "do-hyeon" and fonts.find("  do-hyeon ") is fonts.find("DO HYEON") and fonts.find("Comic Sans") is None


def test_install_checks_the_checksum(tmp_path):
    data = b"font bytes" * 2000
    good = fonts.CaptionFont("test", "Test Sans", "Test.ttf", "https://raw.githubusercontent.com/google/fonts/" + "0" * 40 + "/ofl/test/Test.ttf",
                             hashlib.sha256(data).hexdigest(), len(data), ("ko",), ("dialogue",), "https://example.invalid/OFL.txt")

    class Response(io.BytesIO):
        headers = {"Content-Length": str(len(data))}

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    asked = []

    def opener(url, timeout=60):
        asked.append(url)
        return Response(b"Copyright, SIL Open Font License" if url.endswith("OFL.txt") else data)

    path = fonts.install(good, folder=tmp_path, opener=opener)
    assert path == tmp_path / "Test.ttf" and path.read_bytes() == data and fonts.installed(good, tmp_path)
    assert (tmp_path / "Test-LICENSE.txt").read_text(encoding="utf-8").startswith("Copyright")
    assert fonts.install(good, folder=tmp_path, opener=opener) == path and len(asked) == 2  # already there: nothing fetched
    bad = fonts.CaptionFont(**{**good.__dict__, "key": "bad", "file": "Bad.ttf", "sha256": "0" * 64})
    with pytest.raises(RuntimeError, match="checksum"):
        fonts.install(bad, folder=tmp_path, opener=opener)
    assert not (tmp_path / "Bad.ttf").exists() and not fonts.installed(bad, tmp_path)
    with pytest.raises(ValueError):
        fonts.install("no such font", folder=tmp_path)


def test_missing_for_and_the_fonts_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("STREAM2CLIP_FONTS_DIR", str(tmp_path))
    assert fonts.fonts_dir() == tmp_path and fonts.installed_families() == set()
    do_hyeon = fonts.find("do-hyeon")
    (tmp_path / do_hyeon.file).write_bytes(b"x" * do_hyeon.size)
    assert fonts.installed_families() == {"do hyeon"}
    assert [f.key for f in fonts.missing_for(["Do Hyeon", "Black Han Sans", "Black Han Sans", "Arial"])] == ["black-han-sans"]


def test_caption_font_by_script_and_weight():
    assert caption_font(subtitle_style("dohyeon"), "ko") == ("Do Hyeon", False)  # heavy by design: no synthetic bold
    assert caption_font(subtitle_style("sunflower"), "ko") == ("Sunflower", True)  # its bold is a face of the family
    family, _ = caption_font(subtitle_style("dohyeon"), "ja")
    assert family != "Do Hyeon"  # a Korean font draws no kana: a Japanese font instead
    assert caption_font(subtitle_style("telop"), "ja")[0] == "Rounded Mplus 1c Black" and caption_font(subtitle_style("telop"), "")[0] == "Rounded Mplus 1c Black"
    assert caption_font(subtitle_style(font="Comic Sans MS"), "en") == ("Comic Sans MS", True)  # not in the catalog: as given
    line = style_line(to_ass([Cue(0, 1, "진짜 맛있다")], style=subtitle_style("pink-pop")))
    assert line[1] == "Jua" and line[7] == "0" and line[5] == "&H00FFFFFF"  # white edge around the pink fill


def test_places_for_both_orientations():
    assert set(SUBTITLE_POSITIONS) >= {"bottom", "low", "middle", "top", "under-video", "over-video", "above-video"}
    cue = [Cue(0, 1, "자막")]
    tall = style_line(to_ass(cue, style=subtitle_style(position="under-video")))
    assert (tall[18], tall[21]) == ("8", "1300")  # just under the picture of a blur layout
    wide = style_line(to_ass(cue, play_res=(1920, 1080), style=subtitle_style(position="under-video")))
    assert (wide[18], wide[21]) == ("2", "65")  # a horizontal clip has no band: low, as at the bottom
    above = style_line(to_ass(cue, play_res=(1920, 1080), style=subtitle_style(position="above-video")))
    assert above[18] == "8"
    low = style_line(to_ass(cue, play_res=(1920, 1080), style=subtitle_style(position="low")))
    assert (low[18], low[21]) == ("2", "32")  # 3% of the height: close to the edge, as horizontal Korean clips set them


def test_ffmpeg_is_told_where_the_fonts_are(tmp_path):
    graph = build_video_filter(ExportOptions(subtitles=tmp_path / "c.ass", fonts_dir=tmp_path / "fonts"))
    assert "subtitles=filename=" in graph and ":fontsdir=" in graph and graph.index(":fontsdir=") > graph.index("c.ass")
    assert "fontsdir" not in build_video_filter(ExportOptions(subtitles=tmp_path / "c.ass"))


@needs_ffmpeg
def test_clips_fetch_the_font_of_the_look(tmp_path, green_screen_video, monkeypatch, capsys):
    import json

    from stream2clip import subtitles

    folder = tmp_path / "fonts"
    monkeypatch.setenv("STREAM2CLIP_FONTS_DIR", str(folder))
    monkeypatch.setattr(subtitles, "installed_fonts", lambda: frozenset({"malgun gothic"}))
    fetched = []

    def fake_install(font, **kw):  # lands the file as a download would (its size is what counts as fetched)
        fetched.append(font.key)
        folder.mkdir(exist_ok=True)
        (folder / font.file).write_bytes(b"x" * font.size)

    monkeypatch.setattr(fonts, "install", fake_install)
    highlights = tmp_path / "h.json"
    highlights.write_text(json.dumps({"highlights": [{"rank": 1, "start": 0.2, "end": 1.6, "score": 3}]}), encoding="utf-8")
    subs = tmp_path / "subs.srt"
    subs.write_text("1\n00:00:00,000 --> 00:00:02,000\n진짜 맛있다\n", encoding="utf-8")
    args = ["clips", str(green_screen_video), "--highlights", str(highlights), "--subtitles", str(subs), "--snap", "0", "--layout", "none", "--fps", "10",
            "--subtitle-style", "black-han", "--subtitle-position", "low"]
    code = main([*args, "-o", str(tmp_path / "out")])
    assert code == 0, capsys.readouterr().err
    assert fetched == ["black-han-sans"] and "fetching" in capsys.readouterr().out
    assert style_line((tmp_path / "out" / "clip_01.ass").read_text(encoding="utf-8"))[1] == "Black Han Sans"

    (folder / fonts.find("black-han-sans").file).unlink()

    def offline(font, **kw):
        raise OSError("no connection")

    monkeypatch.setattr(fonts, "install", offline)
    code = main([*args, "-o", str(tmp_path / "offline")])
    assert code == 0, capsys.readouterr().err  # no font: the clips are still made
    assert "not fetched" in capsys.readouterr().err
    assert style_line((tmp_path / "offline" / "clip_01.ass").read_text(encoding="utf-8"))[1] == "Malgun Gothic"


def test_a_look_whose_font_is_missing_falls_back(tmp_path, monkeypatch):
    from stream2clip import subtitles

    monkeypatch.setattr(subtitles, "installed_fonts", lambda: frozenset({"malgun gothic"}))
    cute, plain = subtitle_style("cute"), SubtitleStyle()
    stand_in = with_available_font(cute, tmp_path)
    assert stand_in.font == "auto" and cute.size > plain.size  # Dongle draws small: its look is set big
    assert (stand_in.size, stand_in.portrait_size, stand_in.max_chars, stand_in.portrait_max_chars) == (plain.size, plain.portrait_size, plain.max_chars, plain.portrait_max_chars)
    assert (stand_in.color, stand_in.outline, stand_in.alignment, stand_in.margin_v) == (cute.color, cute.outline, cute.alignment, cute.margin_v)
    assert stand_in.outline_width < cute.outline_width  # thinner with the smaller letters
    dongle = fonts.find(cute.font)
    (tmp_path / dongle.file).write_bytes(b"x" * dongle.size)
    assert with_available_font(cute, tmp_path) is cute  # fetched
    monkeypatch.setattr(subtitles, "installed_fonts", lambda: frozenset({"dongle"}))
    assert with_available_font(cute, tmp_path / "empty") is cute  # installed on this PC
    assert with_available_font(subtitle_style("box"), tmp_path / "empty") == subtitle_style("box")  # the automatic font: nothing to fetch
    assert with_available_font(subtitle_style(font="Comic Sans MS"), tmp_path / "empty").font == "Comic Sans MS"  # not a catalog font: as given


def test_fonts_command(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("STREAM2CLIP_FONTS_DIR", str(tmp_path))
    assert main(["fonts", "--script", "ja"]) == 0
    listed = capsys.readouterr().out
    assert "Dela Gothic One" in listed and "Do Hyeon" not in listed and "telop-yellow" in listed
    fetched = []
    monkeypatch.setattr(fonts, "install", lambda font, **kw: fetched.append(font.key))
    assert main(["fonts", "do-hyeon", "Gugi"]) == 0 and fetched == ["do-hyeon", "gugi"]
    capsys.readouterr()
    assert main(["fonts", "wingdings"]) != 0 and "No caption font" in capsys.readouterr().err
