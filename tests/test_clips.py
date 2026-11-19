from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from stream2clip.compliance import PROFILES, build_description, check_upload, get_profile
from stream2clip.export import export, probe
from stream2clip.ffmpeg import ExportOptions, build_video_filter, filter_path
from stream2clip.geometry import Region
from stream2clip.highlights import Highlight
from stream2clip.layouts import VerticalLayout
from stream2clip.pipeline import make_clips
from stream2clip.sources import SourceInfo
from stream2clip.subtitles import Cue, Word, load_subtitles, parse_srt, parse_vtt, slice_cues, to_ass, to_srt

from .conftest import needs_ffmpeg

SRC = SourceInfo(url="https://www.youtube.com/watch?v=abc", title="【雑談】テスト", channel="Ch", live_status="was_live", availability="public")


# --------------------------------------------------------------------------- layouts


@pytest.mark.parametrize("kind", ["center", "fit", "blur"])
def test_layout_graph_labels(kind):
    graph = VerticalLayout(kind, 540, 960).graph("[in]", "[out]")
    assert graph.startswith("[in]") and graph.endswith("[out]")


def test_stack_requires_avatar_and_even_sizes():
    with pytest.raises(ValueError):
        VerticalLayout("stack")
    with pytest.raises(ValueError):
        VerticalLayout("blur", 541, 960)
    assert "vstack" in VerticalLayout("stack", avatar=Region(0, 0, 100, 100)).graph()


def test_layout_in_export_graph():
    graph = build_video_filter(ExportOptions(format="mp4", fps=30, crop=Region(0, 0, 100, 100), layout=VerticalLayout("center", 540, 960)))
    assert graph.startswith("[0:v]crop=100:100:0:0,fps=30[pre];[pre]") and graph.endswith("format=yuv420p[v]")


def test_filter_path_escaping():
    assert filter_path("C:\\subs\\a.ass") == "C\\\\:/subs/a.ass"
    assert filter_path("/x/it's [a],b;c.ass") == r"/x/it\\\'s \[a\]\,b\;c.ass"


@needs_ffmpeg
@pytest.mark.parametrize("kind", ["center", "fit", "blur", "stack"])
def test_layouts_render(green_screen_video, tmp_path, kind):
    layout = VerticalLayout(kind, 90, 160, avatar=Region(0, 0, 80, 60) if kind == "stack" else None)
    out = export(green_screen_video, tmp_path / f"{kind}.mp4", ExportOptions(format="mp4", fps=10, layout=layout))
    info = probe(out)
    assert (info.width, info.height) == (90, 160)


# --------------------------------------------------------------------------- subtitles


def test_parse_srt_and_slice():
    cues = parse_srt("1\n00:00:01,000 --> 00:00:03,500\n<i>Hello</i>\nworld\n\n2\n00:01:00,000 --> 00:01:02,000\nlater\n")
    assert cues[0] == Cue(1.0, 3.5, "Hello\nworld")
    sliced = slice_cues(cues, 2.0, 61.0)
    assert sliced[0].start == 0 and sliced[0].end == 1.5 and sliced[1].start == 58.0 and sliced[1].end == 59.0


def test_parse_youtube_vtt_words_and_rolling_dedupe():
    vtt = (
        "WEBVTT\nKind: captions\nLanguage: ja\n\n"
        "00:00:01.000 --> 00:00:03.000 align:start position:0%\n"
        "今日は<00:00:01.500><c>配信</c><00:00:02.000><c>です</c>\n\n"
        "00:00:03.000 --> 00:00:03.010 align:start position:0%\n今日は配信です\n\n"
        "00:00:03.010 --> 00:00:05.000 align:start position:0%\n今日は配信です\nよろしく<00:00:04.000><c>ね</c>\n"
    )
    cues = parse_vtt(vtt)
    assert [c.text for c in cues] == ["今日は配信です", "よろしくね"]
    assert [w.text for w in cues[0].words] == ["今日は", "配信", "です"]
    assert cues[0].words[1].start == 1.5 and cues[0].words[1].end == 2.0


def test_ass_karaoke_and_plain(tmp_path):
    cue = Cue(0.5, 2.0, "a b", (Word(0.5, 1.0, "a"), Word(1.2, 2.0, "b")))
    ass = to_ass([cue, Cue(3, 4, "x{y}")], play_res=(540, 960))
    lines = ass.splitlines()
    assert "PlayResX: 540" in ass and "Style: Default,Noto Sans,32," in ass
    assert lines[-2].endswith("{\\k50}a{\\k20}{\\k80} b")
    assert lines[-1].endswith("x(y)") and "\\1c&HFFFFFF&" in lines[-1]
    assert "\\k" not in to_ass([cue], karaoke=False).splitlines()[-1]


def test_load_subtitles_formats(tmp_path):
    (tmp_path / "a.json").write_text(json.dumps({"segments": [{"start": 0, "end": 1, "text": " hi", "words": [{"start": 0, "end": 1, "word": " hi"}]}]}))
    assert load_subtitles(tmp_path / "a.json")[0].words[0].text == "hi"
    (tmp_path / "b.srt").write_text(to_srt([Cue(0, 1.25, "one")]))
    assert load_subtitles(tmp_path / "b.srt") == [Cue(0, 1.25, "one")]


@needs_ffmpeg
def test_burned_subtitles_appear_only_while_cued(green_screen_video, tmp_path):
    from stream2clip.subtitles import write_ass

    ass = write_ass([Cue(1.0, 1.8, "███")], tmp_path / "s.ass", play_res=(160, 120), karaoke=False)
    out = export(green_screen_video, tmp_path / "s.mp4", ExportOptions(format="mp4", fps=10, subtitles=ass))

    def frame(t):
        p = tmp_path / f"f{t}.png"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(t), "-i", str(out), "-frames:v", "1", str(p)], check=True)
        return Image.open(p).convert("RGB")

    def white(img):
        import numpy as np

        return int((np.asarray(img).min(axis=2) > 200).sum())

    assert white(frame(1.4)) > 30 and white(frame(0.4)) < 5


# --------------------------------------------------------------------------- compliance


def test_description_puts_source_first():
    text = build_description(SRC, PROFILES["hololive"], start=125, end=170, summary="채팅 급증", uses_ai=True)
    lines = text.splitlines()
    assert lines[1] == SRC.title and lines[2] == "https://www.youtube.com/watch?v=abc&t=125"
    assert "(2:05 ~ 2:50)" in text and "AI" in text
    assert not [i for i in check_upload(SRC, PROFILES["hololive"], description=text, registered=True) if i.level != "info"]


def test_check_catches_violations():
    members = SourceInfo(url=SRC.url, availability="subscriber_only", live_status="is_live")
    issues = check_upload(members, get_profile("hololive"), description="no link here", content_id=True, uses_voice_generation=True)
    errors = " ".join(i.message for i in issues if i.level == "error")
    assert "멤버십" in errors and "아카이브" in errors and "Content ID" in errors and "음성" in errors and "URL" in errors
    nij = check_upload(SRC, get_profile("nijisanji"), registered=False)
    assert any(i.level == "error" and "등록" in i.message for i in nij)
    ao = check_upload(SRC, get_profile("aogiri"), description=SRC.url, uses_ai=True)
    assert any(i.level == "error" and "AI" in i.message for i in ao)
    with pytest.raises(ValueError):
        get_profile("unknown")


def test_source_not_on_top_is_flagged():
    desc = "line1\nline2\nline3\nline4\nline5\n" + SRC.url
    assert any("맨 위" in i.message for i in check_upload(SRC, get_profile("hololive"), description=desc))


# --------------------------------------------------------------------------- pipeline


@needs_ffmpeg
def test_make_clips_end_to_end(green_screen_video, tmp_path):
    highlights = [Highlight(1, 0.2, 1.2, 0.7, 9.0, ["채팅 급증"]), Highlight(2, 1.0, 1.9, 1.5, 5.0, [])]
    cues = [Cue(0.0, 1.5, "레전드", (Word(0.3, 0.9, "레전"), Word(0.9, 1.4, "드")))]
    opts = ExportOptions(format="mp4", fps=10, layout=VerticalLayout("blur", 90, 160))
    results = make_clips(green_screen_video, highlights, tmp_path / "out", options=opts, cues=cues, source=SRC, profile=get_profile("hololive"))
    assert [r.path.name for r in results] == ["clip_01.mp4", "clip_02.mp4"]
    assert results[0].subtitles is not None and "PlayResX: 90" in results[0].subtitles.read_text(encoding="utf-8")
    assert probe(results[0].path).width == 90 and 0.8 <= probe(results[0].path).duration <= 1.3
    assert results[0].description.read_text(encoding="utf-8").startswith("【元配信 / 원본 방송】")
    index = json.loads((tmp_path / "out" / "clips.json").read_text(encoding="utf-8"))
    assert index["agency"] == "hololive" and index["clips"][0]["file"] == "clip_01.mp4"


def test_vspo_profile_follows_the_official_guideline():
    """Checked against https://vspo.jp/en/guide/ (revised 2026-09-17), not hearsay."""
    from stream2clip.compliance import check_upload, get_profile
    from stream2clip.sources import SourceInfo

    vspo = get_profile("vspo")
    assert vspo.guideline_url == "https://vspo.jp/en/guide/" and vspo.revised == "2026-09-17"
    assert vspo.registration == "required" and vspo.permission_number and vspo.source_link_required
    assert not any("미확인" in note for note in vspo.notes)
    source = SourceInfo(url="https://www.youtube.com/watch?v=x", title="t", live_status="was_live", availability="public")
    without = check_upload(source, vspo, description="https://www.youtube.com/watch?v=x")
    assert any(issue.level == "warning" and "허가 번호" in issue.message for issue in without)
    with_number = check_upload(source, vspo, description="https://www.youtube.com/watch?v=x", permission_number="VSPO-0000")
    assert not any(issue.level == "warning" and "허가 번호" in issue.message for issue in with_number)
    assert any(issue.level == "info" and "vspo.jp" in issue.message for issue in with_number)


class FakeTranscriber:
    def __init__(self):
        self.calls = []

    def transcribe(self, path, *, language=None):
        self.calls.append((Path(path).suffix, language))
        return [Cue(0.0, 0.5, "auto")]


@needs_ffmpeg
def test_make_clips_with_transcriber(green_screen_video, tmp_path):
    fake = FakeTranscriber()
    results = make_clips(green_screen_video, [Highlight(1, 0.0, 1.0, 0.5, 1.0)], tmp_path, options=ExportOptions(format="gif", fps=5, width=80), transcriber=fake, language="ja")
    assert fake.calls == [(".wav", "ja")]
    assert "auto" in results[0].subtitles.read_text(encoding="utf-8")
    assert "PlayResX: 80" in results[0].subtitles.read_text(encoding="utf-8")
