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


# --------------------------------------------------------------------------- context line and teaser


def test_context_line_is_the_streams_topic():
    from stream2clip.titles import context_line

    assert context_line(STREAM, channel=CHANNEL) == "気のせいすぎるRPG"
    assert context_line("【マイクラ】建築【にじさんじ/月ノ美兎】", channel="月ノ美兎") == "マイクラ"
    assert context_line("【#hololiveEnglish】Chill chat stream") == "Chill chat stream"  # the tag says who: the title says what
    assert context_line("") == ""


def test_context_line_in_the_captions():
    from stream2clip.subtitles import to_ass

    ass = to_ass([Cue(0.5, 2.0, "hi")], play_res=(1080, 1920), context="気のせいすぎるRPG", context_seconds=3.0, credit="Source: Ch", duration=10.0)
    style = next(line for line in ass.splitlines() if line.startswith("Style: Context,"))
    assert style.split(",")[15] == "3" and style.split(",")[18] == "8"  # a plate, at the top
    assert style.split(",")[21] == str(round(1920 * 0.1))  # below the credit in the top corner
    event = next(line for line in ass.splitlines() if ",Context," in line)
    assert event.startswith("Dialogue: 2,0:00:00.00,0:00:03.00,Context,") and event.endswith("気のせいすぎるRPG")
    alone = to_ass([], play_res=(1920, 1080), context="topic", duration=2.0)
    assert ",0:00:02.00,Context," in alone and next(line for line in alone.splitlines() if line.startswith("Style: Context,")).split(",")[21] == str(round(1080 * 0.05))
    assert "Context" not in to_ass([Cue(0, 1, "x")])


@needs_ffmpeg
def test_teaser_opens_the_clip_with_its_peak(green_screen_video, tmp_path):
    import subprocess

    import numpy as np

    from stream2clip.export import probe
    from stream2clip.ffmpeg import ExportOptions
    from stream2clip.pipeline import make_clips

    def square_x(path, at):
        raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", str(at), "-i", str(path), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                             capture_output=True, check=True).stdout
        frame = np.frombuffer(raw, dtype=np.uint8).reshape(120, 160, 3).astype(int)
        red = (frame[..., 0] > 150) & (frame[..., 1] < 100)
        return float(np.nonzero(red)[1].mean())

    h = Highlight(1, 0.0, 1.8, 1.2, 5.0)
    opts = ExportOptions(format="mp4", fps=10)
    plain = make_clips(green_screen_video, [h], tmp_path / "plain", options=opts)[0]
    teased = make_clips(green_screen_video, [h], tmp_path / "teased", options=opts, teaser=0.5, context="what is going on", cues=[Cue(1.0, 1.6, "now")])[0]
    assert teased.teaser == pytest.approx(0.9, abs=0.15)  # 0.4 s before the peak and 0.5 s of it
    assert probe(teased.path).duration == pytest.approx(probe(plain.path).duration + teased.teaser, abs=0.2)
    assert square_x(teased.path, 0.05) == pytest.approx(square_x(plain.path, 0.85), abs=6)  # it opens on the peak's picture ...
    assert square_x(teased.path, teased.teaser + 0.05) == pytest.approx(square_x(plain.path, 0.05), abs=6)  # ... then the clip from its start
    assert "what is going on" in teased.subtitles.read_text(encoding="utf-8")
    assert not list((tmp_path / "teased").glob("*.teaser*")) and not list((tmp_path / "teased").glob("*.joined*"))  # nothing left over
    gif = make_clips(green_screen_video, [h], tmp_path / "gif", options=ExportOptions(format="gif", fps=5, width=80), teaser=0.5)[0]
    assert gif.teaser == 0.0  # pictures without sound are not joined


# --------------------------------------------------------------------------- presets


def test_presets_fill_what_was_not_given(tmp_path):
    from stream2clip.cli import _apply_preset, build_parser
    from stream2clip.presets import PRESETS, get_preset

    def parsed(*extra):
        args = build_parser().parse_args(["auto", "v.mp4", "-o", str(tmp_path), "--chat", "c.json", *extra])
        _apply_preset(args)
        return args

    shorts = parsed()
    assert (shorts.layout, shorts.top, shorts.min_length, shorts.max_length, shorts.compile_to, shorts.context) == ("blur", 10, 15.0, 90.0, None, None)
    clip = parsed("--preset", "clip")
    assert (clip.layout, clip.min_length, clip.max_length, clip.context, clip.compile_to) == ("none", 60.0, 180.0, "auto", None)
    long = parsed("--preset", "long")
    assert (long.layout, long.top, long.compile_to, long.fade) == ("none", 6, "", 0.3)
    own = parsed("--preset", "long", "--layout", "blur", "--top", "3", "--context", "my words", "--fade", "0")
    assert (own.layout, own.top, own.context, own.fade) == ("blur", 3, "my words", 0.0)  # what is given wins
    assert set(PRESETS) == {"shorts", "clip", "long"} and get_preset(None).key == "shorts"
    with pytest.raises(ValueError):
        get_preset("square")
    highlights = build_parser().parse_args(["highlights", "--preset", "clip", "--chat", "c.json"])
    _apply_preset(highlights)
    assert (highlights.lead, highlights.tail) == (45.0, 30.0)


# --------------------------------------------------------------------------- originality


def test_originality_check():
    from stream2clip.compliance import REUSED_CONTENT_URL, get_profile, originality_issues

    bare = originality_issues(captions=False)
    assert [i.level for i in bare] == ["warning", "info"] and "재사용" in bare[0].message and REUSED_CONTENT_URL in bare[1].message
    assert originality_issues(captions=False, profile=get_profile("vspo"))[0].level == "error"  # VSPO forbids cut-only videos
    for added in ({"captions": True}, {"captions": False, "context": True}, {"captions": False, "teaser": True}):
        assert [i.level for i in originality_issues(**added)] == ["info"]


@needs_ffmpeg
def test_cut_only_clips_are_flagged(green_screen_video, tmp_path):
    from stream2clip.ffmpeg import ExportOptions
    from stream2clip.pipeline import make_clips

    h = Highlight(1, 0.0, 1.8, 0.8, 5.0)
    bare = make_clips(green_screen_video, [h], tmp_path / "a", options=ExportOptions(format="mp4", fps=10))[0]
    assert bare.issues[0].level == "warning" and "재사용" in bare.issues[0].message
    captioned = make_clips(green_screen_video, [h], tmp_path / "b", options=ExportOptions(format="mp4", fps=10), cues=[Cue(0.2, 1.0, "hi")])[0]
    assert not [i for i in captioned.issues if i.level != "info"]
    assert json.loads((tmp_path / "a" / "clips.json").read_text(encoding="utf-8"))["clips"][0]["issues"][0]["level"] == "warning"


# --------------------------------------------------------------------------- speakers


def test_speaker_map_names_and_colours():
    from stream2clip.speakers import PALETTE, SpeakerMap

    speakers = SpeakerMap.parse(["SPEAKER_00=ぺこら:#57c7ff", "SPEAKER_01=みこ", "2:#FF0000"])
    assert speakers.resolve("SPEAKER_00").name == "ぺこら" and speakers.resolve("SPEAKER_00").color == "#57C7FF"
    assert speakers.resolve("SPEAKER_01").color == PALETTE[0]  # no colour given: the palette's next
    assert speakers.resolve("2").name == "2" and speakers.resolve("2").color == "#FF0000"
    assert speakers.resolve("SPEAKER_07").color == PALETTE[1]  # one it was not told about
    named = speakers.name([Cue(0, 1, "a", speaker="SPEAKER_00"), Cue(1, 2, "b")])
    assert [c.speaker for c in named] == ["ぺこら", ""]
    assert speakers.colors()["ぺこら"] == "#57C7FF"
    with pytest.raises(ValueError):
        SpeakerMap.parse(["=nobody"])


def test_speakers_from_rttm_and_transcripts(tmp_path):
    from stream2clip.speakers import assign_from_spans, read_rttm
    from stream2clip.subtitles import load_subtitles

    rttm = tmp_path / "talk.rttm"
    rttm.write_text("SPEAKER talk 1 0.00 2.00 <NA> <NA> SPEAKER_00 <NA> <NA>\nSPEAKER talk 1 2.00 3.00 <NA> <NA> SPEAKER_01 <NA> <NA>\n", encoding="utf-8")
    spans = read_rttm(rttm)
    assert spans == [(0.0, 2.0, "SPEAKER_00"), (2.0, 5.0, "SPEAKER_01")]
    cues = assign_from_spans([Cue(0.5, 1.5, "a"), Cue(2.5, 4.0, "b"), Cue(9.0, 10.0, "c"), Cue(1.8, 3.0, "d", speaker="X")], spans)
    assert [c.speaker for c in cues] == ["SPEAKER_00", "SPEAKER_01", "", "X"]  # nobody at 9 s; a speaker already given stays
    whisperx = tmp_path / "x.json"
    whisperx.write_text(json.dumps({"segments": [{"start": 0, "end": 1, "text": "hi", "speaker": "SPEAKER_01"}]}), encoding="utf-8")
    assert load_subtitles(whisperx)[0].speaker == "SPEAKER_01"


def test_speakers_from_microphone_tracks():
    import numpy as np

    from stream2clip.speakers import assign_from_tracks

    rate = 8000
    t = np.arange(3 * rate) / rate
    a = (0.3 * np.sin(2 * np.pi * 200 * t) * (t < 1.0)).astype(np.float32) + 0.001
    b = (0.3 * np.sin(2 * np.pi * 300 * t) * ((t >= 1.0) & (t < 2.0))).astype(np.float32) + 0.001
    cues = assign_from_tracks([Cue(0.1, 0.9, "a"), Cue(1.1, 1.9, "b"), Cue(2.1, 2.9, "quiet"), Cue(0.5, 1.5, "both")], {1: a, 2: b}, rate)
    assert [c.speaker for c in cues] == ["1", "2", "", ""]  # silence and an even split stay unknown


def test_speaker_colours_in_the_captions():
    from stream2clip.subtitles import _ass_color, to_ass

    cues = [Cue(0, 1, "a", speaker="ぺこら"), Cue(1, 2, "b", speaker="みこ"), Cue(2, 3, "c")]
    ass = to_ass(cues, play_res=(1080, 1920), speaker_colors={"ぺこら": "#57C7FF", "みこ": "#FF5C9A"}, speaker_names=True)
    styles = {line.split(",")[0][7:]: line.split(",") for line in ass.splitlines() if line.startswith("Style: ")}
    assert styles["Speaker1"][5] == _ass_color("#57C7FF") and styles["Speaker2"][5] == _ass_color("#FF5C9A")
    events = [line for line in ass.splitlines() if line.startswith("Dialogue")]
    assert ",Speaker1,ぺこら," in events[0] and "ぺこら: " in events[0] and ",Default,," in events[2]
    plain = to_ass(cues, play_res=(1080, 1920))  # no colours: every line keeps the default look
    assert "Speaker1" not in plain


@needs_ffmpeg
def test_collab_clip_with_a_microphone_per_track(tmp_path):
    import subprocess

    from stream2clip.ffmpeg import ExportOptions
    from stream2clip.pipeline import make_clips
    from stream2clip.speakers import SpeakerMap

    video = tmp_path / "collab.mkv"
    subprocess.run(  # track 0 the mix, track 1 one talent (first second), track 2 the other (second second)
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=gray:s=160x120:r=10:d=2",
         "-f", "lavfi", "-i", r"aevalsrc=0.3*sin(2*PI*200*t)*lt(t\,1)+0.3*sin(2*PI*300*t)*gte(t\,1):s=16000:d=2",
         "-f", "lavfi", "-i", r"aevalsrc=0.3*sin(2*PI*200*t)*lt(t\,1)+0.0005*sin(2*PI*50*t):s=16000:d=2",
         "-f", "lavfi", "-i", r"aevalsrc=0.3*sin(2*PI*300*t)*gte(t\,1)+0.0005*sin(2*PI*50*t):s=16000:d=2",
         "-map", "0:v", "-map", "1:a", "-map", "2:a", "-map", "3:a", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(video)],
        check=True,
    )
    cues = [Cue(0.1, 0.9, "first"), Cue(1.1, 1.9, "second")]
    results = make_clips(video, [Highlight(1, 0.0, 2.0, 1.0, 1.0)], tmp_path / "out", options=ExportOptions(format="mp4", fps=10), cues=cues,
                         speakers=SpeakerMap.parse(["1=Pekora:#57C7FF", "2=Miko:#FF5C9A"]), speaker_tracks=(1, 2))
    ass = results[0].subtitles.read_text(encoding="utf-8")
    assert ",Speaker1,Pekora," in ass and ",Speaker2,Miko," in ass
