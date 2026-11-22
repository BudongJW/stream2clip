"""What clip channels do that the clips themselves now carry: titles, hashtags (and more, added alongside)."""

from __future__ import annotations

import json

import pytest

from stream2clip.highlights import Highlight
from stream2clip.subtitles import Cue
from stream2clip.titles import TITLE_LIMIT, clip_title, hashtags, hook_line, talent_name, title_language
from stream2clip.translation import Glossary

from .conftest import needs_ffmpeg

CHANNEL = "Pekora Ch. 兎田ぺこら"
STREAM = "【気のせいすぎるRPG】神ゲーの予感は気のせいではなさそう【ホロライブ/兎田ぺこら】"


# --------------------------------------------------------------------------- titles


def test_talent_name_from_the_channel():
    glossary = Glossary({"兎田ぺこら": "우사다 페코라"})
    assert talent_name(CHANNEL, "ja") == "兎田ぺこら"
    assert talent_name(CHANNEL, "en", glossary) == "Pekora"  # a Korean glossary is not an English name
    assert talent_name(CHANNEL, "ko", glossary) == "우사다 페코라"
    assert talent_name(CHANNEL, "ko") == "Pekora"
    assert talent_name("Shirakami Fubuki Ch.白上フブキ", "ja") == "白上フブキ"
    assert talent_name("", "ja") == ""


def test_the_hook_is_the_line_at_the_peak():
    cues = [Cue(0.0, 2.0, "えー"), Cue(2.0, 4.0, "ふざけんなよ。占い 野郎"), Cue(4.0, 6.0, "1つも当たって ません")]
    assert hook_line(cues, 3.0) == "ふざけんなよ 占い野郎"  # caption spaces inside Japanese go, the stop becomes a space
    assert hook_line(cues, 1.0) == "えー ふざけんなよ 占い野郎"  # too short alone: the next line joins it
    assert hook_line([], 1.0, fallback=STREAM) == "神ゲーの予感は気のせいではなさそう"  # the stream's title without its tags
    long = hook_line([Cue(0, 5, "あ" * 60)], 1.0, width=30)
    assert long.endswith("...") and len(long) <= 31


def test_titles_follow_each_language():
    cues = [Cue(0.0, 3.0, "夢じゃなかった。やっちゃってるじゃん")]
    ja = clip_title(cues=cues, peak=1.0, channel=CHANNEL, agency="hololive", language="ja")
    assert ja.title == "夢じゃなかった やっちゃってるじゃん【兎田ぺこら/ホロライブ切り抜き】"
    assert ja.hashtags == ("#ホロライブ切り抜き", "#兎田ぺこら", "#切り抜き")
    ko = clip_title(cues=[Cue(0, 3, "꿈이 아니었어")], peak=1.0, channel=CHANNEL, agency="hololive", language="ko", glossary=Glossary({"兎田ぺこら": "우사다 페코라"}))
    assert ko.title == "[홀로라이브] 꿈이 아니었어 | 우사다 페코라" and ko.hashtags[0] == "#홀로라이브"
    en = clip_title(cues=[Cue(0, 3, "It wasn't a dream")], peak=1.0, channel=CHANNEL, agency="hololive", language="en", translated=True)
    assert en.title == "It wasn't a dream 【Hololive Clip | Pekora】 [Eng Sub]"
    bare = clip_title(cues=cues, peak=1.0, language="ja")  # no source, no agency: no empty brackets left behind
    assert bare.title == "夢じゃなかった やっちゃってるじゃん【切り抜き】" and bare.hashtags == ("#切り抜き",)
    own = clip_title(cues=cues, peak=1.0, channel=CHANNEL, agency="hololive", language="ja", template="【{talent}】{hook}")
    assert own.title == "【兎田ぺこら】夢じゃなかった やっちゃってるじゃん"
    huge = clip_title(cues=[Cue(0, 3, "word " * 60)], peak=1.0, channel=CHANNEL, agency="hololive", language="en", template="{hook} " + "x" * 90)
    assert len(huge.title) <= TITLE_LIMIT


def test_title_language():
    assert title_language(translate_to="ko", language="ja") == "ko"
    assert title_language(language="ja") == "ja" and title_language(language="es") == "en"
    assert title_language(cues=[Cue(0, 1, "안녕하세요")]) == "ko"
    assert title_language(fallback=STREAM) == "ja" and title_language() == "en"
    assert hashtags("en", agency="nijisanji", talent="Elira Pendora") == ("#NIJISANJI", "#ElIraPendora".replace("I", "i"), "#VTuber")


@needs_ffmpeg
def test_clips_carry_their_title_and_hashtags(green_screen_video, tmp_path):
    from stream2clip.compliance import get_profile
    from stream2clip.ffmpeg import ExportOptions
    from stream2clip.pipeline import make_clips
    from stream2clip.sources import SourceInfo

    source = SourceInfo(url="https://www.youtube.com/watch?v=abc", title=STREAM, channel=CHANNEL, live_status="was_live", availability="public")
    cues = [Cue(0.0, 1.5, "やばい！")]
    results = make_clips(green_screen_video, [Highlight(1, 0.0, 1.8, 0.8, 5.0)], tmp_path, options=ExportOptions(format="mp4", fps=10), cues=cues,
                         source=source, profile=get_profile("hololive"))
    clip = results[0]
    assert clip.title == "やばい！【兎田ぺこら/ホロライブ切り抜き】" and clip.hashtags[0] == "#ホロライブ切り抜き"
    description = clip.description.read_text(encoding="utf-8")
    assert description.rstrip().endswith("#ホロライブ切り抜き #兎田ぺこら #切り抜き")
    assert json.loads((tmp_path / "clips.json").read_text(encoding="utf-8"))["clips"][0]["title"] == clip.title
    plain = make_clips(green_screen_video, [Highlight(1, 0.0, 1.8, 0.8, 5.0)], tmp_path / "b", options=ExportOptions(format="mp4", fps=10), cues=cues,
                       source=source, profile=get_profile("hololive"), add_hashtags=False)[0]
    assert "#" not in plain.description.read_text(encoding="utf-8")


def test_hook_needs_text():
    with pytest.raises(KeyError):
        clip_title(cues=[], language="ja", template="{nothing}")


# --------------------------------------------------------------------------- thumbnails


def picture(width: int = 854, height: int = 480):
    """A flat grey game screen with an orange-red 'avatar' block in the lower right."""
    import numpy as np

    frame = np.full((height, width, 4), 90, dtype=np.uint8)
    frame[..., 3] = 255
    frame[210:480, 650:854, :3] = (230, 60, 40)
    rng = np.random.default_rng(0)
    frame[20:200, 40:500, :3] = rng.integers(0, 255, (180, 460, 3))  # detail
    return frame


def test_thumbnail_text_and_frame_choice():
    import numpy as np

    from stream2clip.thumbnails import pick_frame, sharpness, thumbnail_text

    assert thumbnail_text("夢じゃなかった やっちゃってるじゃん") == "夢じゃなかった"
    assert thumbnail_text("ちょっと待ってくださいよ本当に意味が分からない") in ("ちょっと待って", "ちょっと")  # cut between phrases, 10 wide at most
    assert thumbnail_text("Wait what") == "Wait"
    sharp = picture()
    blurred = sharp.copy()
    blurred[..., :3] = 128  # one flat colour: nothing to see
    flash = sharp.copy()
    flash[..., :3] = 255
    assert pick_frame([blurred, sharp, flash]) is sharp
    assert sharpness(flash) < sharpness(sharp)
    with pytest.raises(ValueError):
        pick_frame([])
    assert np.asarray(picture()).shape == (480, 854, 4)


def test_thumbnail_zooms_onto_the_avatar_and_keeps_text_away(tmp_path):
    import numpy as np
    from PIL import Image

    from stream2clip.geometry import Region
    from stream2clip.thumbnails import font_file, make_thumbnail

    plain = make_thumbnail(picture(), "", tmp_path / "plain.jpg")
    face = make_thumbnail(picture(), "", tmp_path / "face.jpg", face=Region(650, 210, 204, 270))
    for path in (plain, face):
        image = Image.open(path)
        assert image.size == (1280, 720) and image.format == "JPEG" and path.stat().st_size < 2_000_000

    def red_share(path):
        pixels = np.asarray(Image.open(path).convert("RGB")).astype(int)
        return float(((pixels[..., 0] > 170) & (pixels[..., 1] < 110)).mean())

    assert red_share(face) > 1.6 * red_share(plain)  # zoomed: the avatar now fills most of the height
    font = font_file("")
    if font is None:
        pytest.skip("no bold Latin font on this machine")
    marked = make_thumbnail(picture(), "WOW", tmp_path / "text.jpg", face=Region(650, 210, 204, 270), font=font)
    pixels = np.asarray(Image.open(marked).convert("RGB")).astype(int)
    yellow = (pixels[..., 0] > 200) & (pixels[..., 1] > 180) & (pixels[..., 2] < 120)
    assert yellow[:, :640].sum() > 20 * yellow[:, 640:].sum()  # on the side away from the face
    assert yellow[360:, 960:].sum() == 0  # the duration badge's corner stays free


def test_sensational_words():
    from stream2clip.thumbnails import sensational_words

    assert sensational_words("【放送事故】やばい", "SHOCKING drama") == ["放送事故", "SHOCKING", "drama"]
    assert sensational_words("夢じゃなかった") == []


@needs_ffmpeg
def test_clips_can_bring_a_thumbnail(green_screen_video, tmp_path):
    from PIL import Image

    from stream2clip.ffmpeg import ExportOptions
    from stream2clip.pipeline import make_clips

    results = make_clips(green_screen_video, [Highlight(1, 0.0, 1.8, 0.8, 5.0)], tmp_path, options=ExportOptions(format="mp4", fps=10),
                         cues=[Cue(0.0, 1.5, "放送事故")], thumbnails=True)
    clip = results[0]
    assert clip.thumbnail == tmp_path / "clip_01.jpg" and Image.open(clip.thumbnail).size == (1280, 720)
    assert json.loads((tmp_path / "clips.json").read_text(encoding="utf-8"))["clips"][0]["thumbnail"] == "clip_01.jpg"
    assert any(issue.level == "warning" and "放送事故" in issue.message for issue in clip.issues)
