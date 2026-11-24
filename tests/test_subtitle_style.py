"""Captions: the font follows the language, lines break between phrases and stay in the frame, ready-made looks."""

from __future__ import annotations

import json
import re

import pytest

from stream2clip import subtitles
from stream2clip.cli import main
from stream2clip.export import export, grab_frames
from stream2clip.ffmpeg import ExportOptions
from stream2clip.subtitles import (
    SUBTITLE_POSITIONS,
    SUBTITLE_STYLES,
    Cue,
    SubtitleStyle,
    Word,
    _phrases,
    _tokens,
    _width,
    _wrap,
    pick_font,
    script_of,
    subtitle_style,
    to_ass,
    write_ass,
)

from .conftest import needs_ffmpeg

N = chr(92) + "N"  # the line break of ASS


def dialogue(ass: str, index: int = 0) -> str:
    return [line for line in ass.splitlines() if line.startswith("Dialogue")][index].split(",,", 2)[-1]


def plain(text: str) -> str:
    return re.sub(r"[{][^}]*[}]", "", text)


def style_line(ass: str) -> list[str]:
    return next(line for line in ass.splitlines() if line.startswith("Style:")).split(",")


# --------------------------------------------------------------------------- fonts


def test_script_of_the_text():
    assert script_of("今日は配信です") == "ja" and script_of("오늘 방송") == "ko" and script_of("hello") == ""
    assert script_of("全部当たっている") == "ja"  # kanji with kana
    assert script_of("我们开始吧") == "zh"  # no kana, no hangul
    assert script_of("한국어 번역 漢字") == "ko" and script_of("") == ""


def test_font_follows_the_language_and_what_is_installed():
    assert pick_font("ja", installed=[]) == "Noto Sans JP" and pick_font("ko", installed=[]) == "Noto Sans KR" and pick_font("", installed=[]) == "Noto Sans"
    windows = ["Malgun Gothic", "Malgun Gothic Bold", "Yu Gothic Bold", "Yu Gothic UI Bold", "Meiryo", "Segoe UI", "Noto Sans KR"]
    assert pick_font("ja", installed=windows) == "Yu Gothic"  # no Noto Sans JP on this machine
    assert pick_font("ko", installed=windows) == "Noto Sans KR"
    assert pick_font("", installed=windows) == "Segoe UI"  # "Noto Sans KR" is not the Latin "Noto Sans"
    assert pick_font("", installed=["Noto Sans Bold", "Segoe UI"]) == "Noto Sans"
    assert pick_font("zh", installed=["Microsoft YaHei"]) == "Microsoft YaHei"
    assert pick_font("xx", installed=["Arial"]) == "Arial"  # an unknown script gets the Latin list


def test_installed_fonts_are_listed_once_and_never_fail(monkeypatch):
    calls = []

    def listing() -> set[str]:
        calls.append(1)
        return {"yu gothic bold", "malgun gothic"}

    monkeypatch.setattr(subtitles, "_installed", None)
    monkeypatch.setattr(subtitles, "_font_names_windows", listing)
    monkeypatch.setattr(subtitles, "_font_names_fontconfig", listing)
    assert subtitles.installed_fonts() == {"yu gothic bold", "malgun gothic"} and subtitles.installed_fonts() and calls == [1]
    assert pick_font("ja") == "Yu Gothic" and pick_font("ko") == "Malgun Gothic"

    def broken() -> set[str]:
        raise OSError("no registry")

    monkeypatch.setattr(subtitles, "_installed", None)
    monkeypatch.setattr(subtitles, "_font_names_windows", broken)
    monkeypatch.setattr(subtitles, "_font_names_fontconfig", broken)
    assert subtitles.installed_fonts() == frozenset() and pick_font("ja") == "Noto Sans JP"


def test_fontconfig_families_are_read(monkeypatch):
    import subprocess

    class Done:
        stdout = "Noto Sans CJK JP,Noto Sans CJK JP Bold\nDejaVu Sans\n\n"

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: Done())
    names = subtitles._font_names_fontconfig()
    assert names == {"noto sans cjk jp", "noto sans cjk jp bold", "dejavu sans"}
    assert pick_font("ja", installed=names) == "Noto Sans CJK JP" and pick_font("", installed=names) == "DejaVu Sans"

    def missing(*args, **kwargs):
        raise FileNotFoundError("fc-list")

    monkeypatch.setattr(subprocess, "run", missing)
    assert subtitles._font_names_fontconfig() == set()


def test_ass_uses_the_font_of_the_text():
    assert style_line(to_ass([Cue(0, 1, "今日は配信です")]))[1] == "Noto Sans JP"
    assert style_line(to_ass([Cue(0, 1, "오늘 방송")]))[1] == "Noto Sans KR"
    assert style_line(to_ass([Cue(0, 1, "", (Word(0, 1, "配信"), Word(1, 2, "です")))]))[1] == "Noto Sans JP"  # karaoke cues have their text in the words
    assert style_line(to_ass([Cue(0, 1, "今日は配信です")], style=SubtitleStyle(font="Meiryo")))[1] == "Meiryo"  # a named font is kept
    # An original above its translation: each line in its own font, the style follows the majority of all text.
    both = to_ass([Cue(0, 1, "海を直接見る\n바다를 직접 본다")], karaoke=False)
    text = dialogue(both)
    assert "{" + chr(92) + "fnNoto Sans JP}海を" in text and "{" + chr(92) + "fnNoto Sans KR}바다를" in text
    assert chr(92) + "fn" not in dialogue(to_ass([Cue(0, 1, "一行目\n二行目です")], karaoke=False))  # one language: no overrides


# --------------------------------------------------------------------------- wrapping


def test_width_counts_latin_as_half():
    assert _width("日本語") == 3 and _width("한국어") == 3 and _width("abcd") == pytest.approx(2.2)


def test_japanese_is_cut_between_phrases():
    assert _phrases("マリオカートで一位を取ったらスパチャ読みますね") == ["マリオカートで", "一位を", "取ったら", "スパチャ読みますね"]
    assert _phrases("ちょっと待って、それは聞いてない") == ["ちょっと", "待って、", "それは", "聞いてない"]
    assert _phrases("「えっ」って言ったよね？") == ["「えっ」って", "言ったよね？"]  # brackets and small kana stay with their word
    assert _tokens("오늘 방송 시작")[0] == ["오늘", "방송", "시작"] and _tokens("我们开始吧")[0] == list("我们开始吧")
    assert _tokens("ありがとうございます")[0] == list("ありがとうございます")  # one phrase only: characters, so it can still be broken


def test_lines_are_balanced_and_break_between_tokens():
    tokens, joiner = _tokens("マリオカートで一位を取ったらスパチャ読みますね")
    lines = [joiner.join(tokens[i] for i in idxs) for idxs in _wrap(tokens, 18)]
    assert lines == ["マリオカートで一位を", "取ったらスパチャ読みますね"]
    assert _wrap(["short"], 18) == [[0]] and _wrap(list("短い文"), 18) == [[0, 1, 2]]
    words = ["word"] * 30  # 30 x 2.2 = 66 wide: three lines at most, about even
    three = _wrap(words, 18)
    assert len(three) == 3 and [len(line) for line in three] == [10, 10, 10]
    assert [index for line in three for index in line] == list(range(30))


def test_a_cue_too_long_for_three_lines_is_set_smaller():
    long_text = "今日は配信に来てくれてありがとうございます、本当に嬉しいです！また明日も同じ時間に配信するのでよろしくお願いします"
    text = dialogue(to_ass([Cue(0, 3, long_text)], karaoke=False))
    assert text.count(N) == 2 and plain(text).replace(N, "") == long_text
    scale = re.match(r"[{]" + re.escape(chr(92)) + r"fscx(\d+)" + re.escape(chr(92)) + r"fscy(\d+)[}]", text)
    assert scale and scale.group(1) == scale.group(2) and 55 <= int(scale.group(1)) < 100
    assert "fscx" not in dialogue(to_ass([Cue(0, 3, "短い字幕です")], karaoke=False))
    sentence = [Cue(0, 3, "That was the funniest thing I have ever seen on this stream honestly")]
    english = dialogue(to_ass(sentence, play_res=(1920, 1080), karaoke=False))
    assert english.count(N) == 1 and "fscx" not in english  # Latin letters are narrow: two lines are enough on a horizontal clip
    assert dialogue(to_ass(sentence, karaoke=False)).count(N) == 2  # a Short's letters are bigger: three lines


def test_caption_size_follows_the_frame():
    """Korean clip channels caption at about 5.5% of a horizontal clip's height and 4.5% of a Short's, ten letters to a line."""
    style = SubtitleStyle()
    wide, tall = style.for_frame(1920, 1080), style.for_frame(1080, 1920)
    assert (wide.size, wide.max_chars, wide.outline_width) == (80, 22, 7.5)
    assert (tall.size, tall.max_chars, tall.outline_width) == (112, 12, 10.5) and tall.for_frame(1080, 1920) == tall  # the outline grows with the letters
    shadow = style_line(to_ass([Cue(0, 1, "字幕です")]))[17]
    assert shadow == "4.2" and style_line(to_ass([Cue(0, 1, "字幕です")], style=subtitle_style("box")))[17] == "0"  # a soft shadow; a plate needs none
    assert style_line(to_ass([Cue(0, 1, "字幕です")]))[2] == "112" and style_line(to_ass([Cue(0, 1, "字幕です")], play_res=(1920, 1080)))[2] == "80"
    given = subtitle_style(size=64)  # one size for every frame, lines as long as it leaves room for
    assert (given.for_frame(1920, 1080).size, given.for_frame(1080, 1920).size) == (64, 64)
    assert (given.for_frame(1920, 1080).max_chars, given.for_frame(1080, 1920).max_chars) == (28, 21)
    small = subtitle_style("small")
    assert small.for_frame(1080, 1920).size < tall.size and small.for_frame(1920, 1080).size < wide.size


def test_karaoke_words_wrap_with_the_same_rules():
    words = tuple(Word(0.3 * i, 0.3 * i + 0.3, text) for i, text in enumerate(["マリオ", "カート", "で", "一位", "を", "取ったら", "スパチャ", "読み", "ますね"]))
    text = dialogue(to_ass([Cue(0, 3, "", words)]))
    assert text.count(N) == 1 and plain(text).replace(N, "") == "マリオカートで一位を取ったらスパチャ読みますね"
    assert text.count(chr(92) + "k") == len(words)


# --------------------------------------------------------------------------- looks


def test_presets_and_positions():
    assert {"default", "box", "pink", "small"} <= set(SUBTITLE_STYLES) and {"bottom", "middle", "top"} <= set(SUBTITLE_POSITIONS)
    assert subtitle_style() == SubtitleStyle()
    top = subtitle_style("box", position="top", font="Meiryo", size=40)
    assert top.box and top.alignment == 8 and top.font == "Meiryo" and top.size == 40
    with pytest.raises(ValueError, match="subtitle style"):
        subtitle_style("neon")
    with pytest.raises(ValueError, match="subtitle position"):
        subtitle_style("box", position="left")

    cue = [Cue(0, 1, "字幕です")]
    default, box = style_line(to_ass(cue)), style_line(to_ass(cue, style=subtitle_style("box")))
    assert default[15] == "1" and box[15] == "3"  # BorderStyle: outline, plate
    assert box[5].startswith("&H26")  # the plate is slightly see-through (alpha D9 -> 26 in ASS)
    pink = style_line(to_ass(cue, style=subtitle_style("pink")))
    assert pink[3] == "&H008B4FFF" and default[3] == "&H004DD8FF"  # karaoke highlight: live pink, brand yellow
    small = style_line(to_ass(cue, style=subtitle_style("small")))
    assert int(small[2]) < int(default[2]) and small[7] == "0" and default[7] == "-1"  # smaller, not bold
    assert style_line(to_ass(cue, style=subtitle_style(position="top")))[18] == "8"
    assert style_line(to_ass(cue, style=subtitle_style(position="middle")))[18:22] == ["5", "60", "60", "0"]


@needs_ffmpeg
def test_position_moves_the_captions_on_the_picture(tmp_path, green_screen_video):
    def lit_rows(position: str) -> tuple[int, int]:
        ass = write_ass([Cue(0, 2, "WWWWWW")], tmp_path / f"{position}.ass", play_res=(160, 120), style=subtitle_style(position=position, font="Arial"), karaoke=False)
        out = export(green_screen_video, tmp_path / f"{position}.mp4", ExportOptions(format="mp4", fps=10, subtitles=ass))
        frame = grab_frames(out, [1.0])[0]
        white = (frame[:, :, :3].min(axis=2) > 200).sum(axis=1)  # the caption is the only white on green and red
        rows = [y for y, count in enumerate(white) if count > 3]
        assert rows, position
        return rows[0], rows[-1]

    bottom, middle, top = lit_rows("bottom"), lit_rows("middle"), lit_rows("top")
    assert top[1] < middle[0] < middle[1] < bottom[0]
    assert top[0] < 40 and bottom[1] > 90 and 40 < (middle[0] + middle[1]) / 2 < 80


@needs_ffmpeg
def test_clips_command_takes_the_look_of_the_captions(tmp_path, green_screen_video, capsys):
    highlights = tmp_path / "h.json"
    highlights.write_text(json.dumps({"highlights": [{"rank": 1, "start": 0.2, "end": 1.6, "score": 3}]}), encoding="utf-8")
    subs = tmp_path / "subs.srt"
    subs.write_text("1\n00:00:00,000 --> 00:00:02,000\n今日は配信です\n", encoding="utf-8")
    out = tmp_path / "clips"
    code = main(["clips", str(green_screen_video), "--highlights", str(highlights), "--subtitles", str(subs), "--snap", "0", "--layout", "none", "--fps", "10",
                 "--subtitle-style", "box", "--subtitle-position", "top", "--font", "Meiryo", "--font-size", "40", "-o", str(out)])
    assert code == 0, capsys.readouterr().out
    style = style_line((out / "clip_01.ass").read_text(encoding="utf-8"))
    assert style[1] == "Meiryo" and style[15] == "3" and style[18] == "8"
    assert main(["clips", str(green_screen_video), "--highlights", str(highlights), "--subtitles", str(subs), "--snap", "0", "--layout", "none", "--fps", "10", "-o", str(tmp_path / "plain")]) == 0
    assert style_line((tmp_path / "plain" / "clip_01.ass").read_text(encoding="utf-8"))[1] == "Noto Sans JP"


# --------------------------------------------------------------------------- checking captions before upload


def test_caption_check_before_upload():
    from stream2clip.subtitles import Cue, caption_issues

    fine = [Cue(0.0, 2.0, "今日は配信するよ"), Cue(2.0, 4.0, "Hello everyone"), Cue(4.0, 6.0, "今日は配信するよ\n오늘은 방송할게")]
    assert caption_issues(fine) == []  # an original above its translation is read as one line or the other
    fast = Cue(0.0, 1.0, "これはとても速く読まなければならない字幕です")  # 22 letters in a second
    wide = Cue(1.0, 9.0, "あ" * 120)  # three lines of 40: wider than the frame even at the smallest size
    flash = Cue(9.0, 9.1, "えっ")
    loop = Cue(10.0, 13.0, "ありがとうありがとうありがとうありがとう")
    laugh = Cue(13.0, 16.0, "はははははははは")  # laughter, not a loop
    invented = Cue(16.0, 19.0, "ご視聴ありがとうございました")
    same = [Cue(20.0 + i, 21.0 + i, "そうだね") for i in range(4)]
    found = caption_issues([fast, wide, flash, loop, laugh, invented, *same], SubtitleStyle().for_frame(1080, 1920))  # as on a Short
    assert len(found) == 6
    assert "2줄이 읽기에 빠름" in found[0] and found[0].endswith("字幕です")
    assert "1줄이 길어 화면 밖" in found[1] and found[1].endswith("あ" * 24 + "...")  # a long example is cut
    assert "0.3" in found[2] and "えっ" in found[2]
    assert "4번 이어짐" in found[3] and "そうだね" in found[3]
    assert "되풀이" in found[4] and "ありがとう" in found[4] and "ご視聴" in found[5]
    assert caption_issues([Cue(0.0, 1.0, "うん")] * 2) == []  # twice in a row is talk, not a loop
