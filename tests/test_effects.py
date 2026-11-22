"""Effects at a highlight's peak: presets, the plan, the zoom on real frames, the caption pops and tags."""

from __future__ import annotations

import json
import subprocess
from importlib.resources import files

import numpy as np
import pytest

from stream2clip import effects
from stream2clip.cli import main
from stream2clip.effects import PRESETS, Tag, check_preset, load_preset, plan_effects, prominent_words, zoom_filters
from stream2clip.export import export
from stream2clip.ffmpeg import ExportOptions
from stream2clip.highlights import Highlight
from stream2clip.subtitles import Cue as C
from stream2clip.subtitles import SubtitleStyle, Word, to_ass

from .conftest import needs_ffmpeg

ALL = frozenset({"scale", "crop", "subtitles"})


def frame_at(path, at, size=(160, 90)):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", str(at), "-i", str(path), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.uint8).reshape(size[1], size[0]).astype(float)


# --------------------------------------------------------------------------- presets


def test_built_in_presets_follow_the_schema(tmp_path):
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(files("stream2clip").joinpath("schemas/effects.v1.schema.json").read_text(encoding="utf-8"))
    for name, preset in PRESETS.items():
        jsonschema.Draft202012Validator(schema).validate(preset)
        assert check_preset(preset) == [], name
    assert load_preset("subtle") == PRESETS["subtle"] and load_preset("subtle") is not PRESETS["subtle"]  # a copy to change
    saved = effects.write_preset("variety", tmp_path / "mine.json")
    assert load_preset(str(saved)) == PRESETS["variety"]
    (tmp_path / "bad.json").write_text(json.dumps({"schema_version": 1, "effects": [{"type": "explode", "scale": 3}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="type must be one of") as found:
        load_preset(str(tmp_path / "bad.json"))
    assert "scale must be between" in str(found.value)
    with pytest.raises(ValueError, match="subtle"):
        load_preset("loud")


def test_filters_this_ffmpeg_has(monkeypatch):
    listing = "Filters:\n  T.. = Timeline support\n ... scale             V->V       Scale the input video size\n TSC crop     V->V   Crop\n"

    def run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout=listing)

    monkeypatch.setattr(effects.subprocess, "run", run)
    effects.available_filters.cache_clear()
    assert effects.available_filters("fake-ffmpeg") == frozenset({"scale", "crop"})
    effects.available_filters.cache_clear()


# --------------------------------------------------------------------------- the zoom


def test_zoom_expressions():
    scale, crop = zoom_filters((1080, 1920), start=2.0, scale=1.2, zoom_in=0.12, hold=1.0, zoom_out=0.4)
    assert scale.startswith("scale=w='trunc(1080*") and scale.endswith(":eval=frame") and "clip((t-2)/0.12,0,1)" in scale
    assert "clip((t-3.12)/0.4,0,1)" in scale and "1+0.2*" in scale  # back to 1 after the hold
    assert crop.startswith("crop=1080:1920:x='clip(0.5*iw-1080/2,0,iw-1080)'")


@needs_ffmpeg
def test_zoom_on_real_frames(tmp_path):
    src = tmp_path / "bars.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "smptebars=size=160x90:rate=10:duration=4", "-pix_fmt", "yuv420p", str(src)], check=True)
    zoom = tuple(zoom_filters((160, 90), start=1.0, scale=1.3, zoom_in=0.2, hold=1.0, zoom_out=0.3, focus=(0.5, 0.5)))
    out = export(src, tmp_path / "zoom.mp4", ExportOptions(format="mp4", fps=10, effects=zoom, audio=False))
    before, during, after = frame_at(out, 0.5), frame_at(out, 1.6), frame_at(out, 3.5)
    plain = frame_at(src, 1.6)
    assert np.abs(before - plain).mean() < 3 and np.abs(after - plain).mean() < 3  # the picture as it was outside the zoom
    assert np.abs(during - plain).mean() > 8  # larger in the middle of it, same frame size


# --------------------------------------------------------------------------- choosing words


def test_the_loudest_longest_word_near_the_moment():
    rate = 1000
    samples = np.zeros(6 * rate)
    samples[int(2.0 * rate): int(2.6 * rate)] = 0.8  # "すごい" said loud
    samples[int(1.0 * rate): int(1.4 * rate)] = 0.1
    cues = [C(0.9, 3.0, "ほんとにすごい", (Word(1.0, 1.4, "ほんと"), Word(1.5, 1.6, "に"), Word(2.0, 2.6, "すごい"))),
            C(5.0, 5.8, "やばい", (Word(5.0, 5.8, "やばい"),))]
    assert prominent_words(cues, samples, rate, around=2.0, before=2.0, after=1.5) == [(2.0, 2.6, "すごい")]
    assert prominent_words(cues, samples, rate, around=2.0, before=2.0, after=4.0, count=3) == [(2.0, 2.6, "すごい"), (5.0, 5.8, "やばい")]  # one per line
    assert all(text != "に" for _, _, text in prominent_words(cues, None, rate, around=1.5, before=1, after=1, count=5))  # one letter: a particle
    assert prominent_words([C(0, 1, "no words")], samples, rate, around=0.5, before=1, after=1) == []


# --------------------------------------------------------------------------- planning


def plan(preset="variety", **kwargs):
    base = dict(length=40.0, peak=20.0, onset=19.6, stats={"react_laugh": 30, "react_shock": 2}, frame=(1080, 1920), language="ja", filters=ALL)
    base.update(kwargs)
    return plan_effects(load_preset(preset), **base)


def test_plan_anchors_on_the_onset_and_reads_the_chat():
    made = plan(cues=[C(19.0, 21.5, "x")])
    zoom, tag = made.placed[0], made.placed[-1]
    assert zoom["type"] == "zoom" and zoom["at"] == 19.6 and zoom["anchor"] == "onset" and zoom["scale"] == 1.1  # laugh: a gentle zoom
    assert tag == {"id": "reaction_tag", "type": "caption_tag", "at": 19.6, "text": "草", "reaction": "laugh"}
    assert len(made.filters) == 2 and made.tags == (Tag(19.6, 20.8, "草", "laugh"),)
    assert any("word timing" in reason for reason in made.skipped)  # no words given: no emphasis

    hotkey = plan(hotkey=19.9)
    assert hotkey.placed[0]["anchor"] == "vts_hotkey" and hotkey.placed[0]["at"] == 19.9  # the streamer's own press comes first
    assert plan(language="ko").tags[0].text == "ㅋㅋㅋ" and plan(language="en").tags[0].text == "LOL"
    shock = plan(stats={"react_shock": 20})
    assert shock.tags[0].text == "!?" and shock.placed[0]["scale"] == 1.2
    assert plan(to_clip=lambda t: t - 5.0).placed[0]["at"] == 14.6  # onto the clip's clock after silence was cut


def test_plan_holds_back():
    quiet = plan(onset=None)
    assert not quiet.filters and any("no clear moment" in r for r in quiet.skipped)  # no onset, no hotkey: no zoom
    assert quiet.tags  # the tag still has its moment (the peak)
    assert not plan(stats={"react_hype": 30}).filters  # hype: the captions grow, the picture does not
    assert not plan(stats={"react_laugh": 3, "react_shock": 3}).tags  # nothing stands out in the chat
    still = plan(reduced_motion=True)
    assert not still.filters and still.emphasis_scale == pytest.approx(1.4) and any("reduced motion" in r for r in still.skipped)
    tight = load_preset("variety")
    tight["budget"]["max_secondary"] = 1
    rate = 1000
    words = [C(19.0, 21.0, "すごいね", (Word(19.5, 20.2, "すごい"),))]
    spent = plan_effects(tight, length=40.0, peak=20.0, onset=19.6, stats={"react_laugh": 30}, words_from=(words, np.ones(40 * rate) * 0.1, rate),
                         language="ja", filters=ALL)
    assert [p["type"] for p in spent.placed] == ["zoom", "caption_emphasis"] and any("budget" in r for r in spent.skipped)
    bare = plan(filters=frozenset({"subtitles"}))
    assert not bare.filters and any("no scale, crop" in r for r in bare.skipped)  # this ffmpeg lacks the filters: left out, said why
    assert plan_effects(load_preset("off"), length=40.0, peak=20.0).placed == []
    assert plan(peak=39.8, onset=39.8).placed[0]["type"] != "zoom"  # no room for a zoom at the very end


# --------------------------------------------------------------------------- captions


def test_the_word_pops_and_the_tag_appears():
    cue = C(1.0, 3.0, "これはすごい", (Word(1.0, 1.5, "これは"), Word(1.8, 2.4, "すごい")))
    ass = to_ass([cue], emphasis=[1.8], emphasis_scale=1.25, tags=[Tag(1.8, 3.0, "草", "laugh")])
    line = next(row for row in ass.splitlines() if row.startswith("Dialogue: 0,"))
    assert "\\t(800,910,\\fscx125\\fscy125)" in line and "\\3c&H8B4FFF&" in line and "すごい{\\r\\fscx100\\fscy100}" in line
    assert line.index("これは") < line.index("\\t(800")  # only that word
    tag = next(row for row in ass.splitlines() if row.startswith("Dialogue: 3,"))
    assert ",Tag," in tag and "\\pos(821,538)" in tag and tag.endswith("草") and "Style: Tag," in ass
    boxed = to_ass([cue], emphasis=[1.8], style=SubtitleStyle(box=True))
    assert "\\fscx125" in boxed and "\\3c&H8B4FFF&" not in boxed  # a plate keeps its colour
    assert "\\t(" not in to_ass([cue])  # nothing asked for, nothing added


# --------------------------------------------------------------------------- end to end


@needs_ffmpeg
def test_clips_with_effects(tmp_path, capsys):
    video = tmp_path / "vod.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "smptebars=size=160x90:rate=10:duration=12",
                    "-f", "lavfi", "-i", "aevalsrc='0.6*sin(2*PI*440*t)*between(t,6,7.5)':s=16000:d=12", "-shortest",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(video)], check=True)
    srt = tmp_path / "subs.srt"
    srt.write_text("1\n00:00:05,500 --> 00:00:07,500\nすごいね\n", encoding="utf-8")
    highlights = tmp_path / "h.json"
    highlights.write_text(json.dumps({"highlights": [{"rank": 1, "start": 2.0, "end": 11.0, "peak": 6.5, "score": 5.0,
                                                      "stats": {"react_shock": 40}}]}), encoding="utf-8")
    out = tmp_path / "clips"
    assert main(["clips", str(video), "--highlights", str(highlights), "--subtitles", str(srt), "--layout", "none", "-f", "mp4", "--fps", "10",
                 "--fx", "variety", "--language", "ja", "-o", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "effects: zoom x1.2 at 4.0s (onset)" in printed and "tag !? (shock)" in printed  # the tone starts 4 s into the cut
    data = json.loads((out / "clips.json").read_text(encoding="utf-8"))["clips"][0]["effects"]
    assert data["preset"] == "variety" and [p["type"] for p in data["placed"]] == ["zoom", "caption_tag"]
    assert "Style: Tag," in (out / "clip_01.ass").read_text(encoding="utf-8")
    plain = tmp_path / "plain"
    assert main(["clips", str(video), "--highlights", str(highlights), "--layout", "none", "-f", "mp4", "--fps", "10", "-o", str(plain)]) == 0
    assert json.loads((plain / "clips.json").read_text(encoding="utf-8"))["clips"][0]["effects"] is None  # off unless asked
    capsys.readouterr()
    assert main(["fx"]) == 0 and "variety" in capsys.readouterr().out
    assert main(["fx", "subtle", "-o", str(tmp_path / "s.json")]) == 0 and load_preset(str(tmp_path / "s.json")) == PRESETS["subtle"]


def test_feedback_notes_the_effect_preset(tmp_path):
    from stream2clip import feedback

    path = feedback.record(tmp_path / "f.jsonl", [Highlight(1, 0.0, 30.0, 10.0, 1.0)], [True], effects="subtle")
    assert feedback.load(path)[0]["effects"] == "subtle"
    assert feedback.load(feedback.record(tmp_path / "g.jsonl", [Highlight(1, 0.0, 30.0, 10.0, 1.0)], [True]))[0]["effects"] == "off"
