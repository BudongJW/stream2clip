"""Shortening the quiet stretches of a clip, and asking whether a newer release exists."""

from __future__ import annotations

import io
import json
import subprocess

import numpy as np
import pytest

from stream2clip import __version__, updates
from stream2clip.audio import decode_pcm, sound_parts
from stream2clip.cli import main
from stream2clip.export import probe
from stream2clip.ffmpeg import ExportOptions, build_export_command, build_video_filter, keep_filters
from stream2clip.highlights import Highlight
from stream2clip.pipeline import make_clips
from stream2clip.subtitles import Cue, Word, retime_cues

from .conftest import needs_ffmpeg

RATE = 16000


def recording(*spans: tuple[float, float], length: float, loud: float = 0.5, floor: float = 0.0005) -> np.ndarray:
    """A tone in ``spans``, a faint hiss everywhere else."""
    t = np.arange(int(length * RATE)) / RATE
    rng = np.random.default_rng(3)
    samples = rng.normal(0.0, floor, t.size)
    for a, b in spans:
        samples[(t >= a) & (t < b)] += loud * np.sin(2 * np.pi * 440 * t[(t >= a) & (t < b)])
    return samples.astype(np.float32)


# ----------------------------------------------------------------------------- where the sound is


def test_long_silences_are_cut_down_to_a_short_pause():
    samples = recording((1.0, 3.0), (6.0, 7.0), (7.4, 9.0), length=12.0)
    keep = sound_parts(samples, RATE)
    assert [(round(a, 1), round(b, 1)) for a, b in keep] == [(0.8, 3.2), (5.8, 9.2)]  # a quarter second stays on each side of a silence
    # the 0.4 s gap between the second and third tone is a pause of the speaker, not a silence to cut
    assert sum(b - a for a, b in keep) == pytest.approx(2.5 + 3.5, abs=0.1)
    tight = sound_parts(samples, RATE, min_silence=0.3, pad=0.05)
    assert len(tight) == 3 and tight[1] == pytest.approx((5.95, 7.05), abs=0.03)
    assert sound_parts(samples, RATE, min_silence=5.0) == [(0.0, 12.0)]  # no silence that long


def test_silence_is_measured_against_the_recording_itself():
    quiet_voice = recording((1.0, 3.0), (6.0, 9.0), length=10.0, loud=0.01, floor=0.00001)  # a low microphone is not "all silence"
    assert len(sound_parts(quiet_voice, RATE)) == 2
    music = recording((1.0, 3.0), (6.0, 9.0), length=10.0, loud=0.5, floor=0.1)  # 14 dB under the voice: music, not silence
    assert sound_parts(music, RATE) == [(0.0, 10.0)]
    assert len(sound_parts(music, RATE, level=10.0)) == 2  # ... unless told that this is quiet enough
    nothing = np.zeros(RATE * 4, dtype=np.float32)
    assert sound_parts(nothing, RATE) == [(0.0, 4.0)]  # no sound at all: nothing to tell speech from
    assert sound_parts(np.zeros(0, dtype=np.float32), RATE) == []


def test_cues_follow_what_is_left():
    keep = [(1.0, 3.0), (6.0, 9.0)]
    cues = [
        Cue(1.5, 2.5, "first", (Word(1.5, 2.0, "fi"), Word(2.0, 2.5, "rst"))),
        Cue(2.8, 6.5, "across the cut"),
        Cue(3.5, 5.5, "inside the cut"),
        Cue(7.0, 8.0, "last"),
        Cue(9.5, 11.0, "after the end"),
    ]
    moved = retime_cues(cues, keep)
    assert [c.text for c in moved] == ["first", "across the cut", "last"]  # nothing is left of the other two
    assert (moved[0].start, moved[0].end) == pytest.approx((0.5, 1.5)) and moved[0].words[1].start == pytest.approx(1.0)
    assert (moved[1].start, moved[1].end) == pytest.approx((1.8, 2.5))  # 0.2 s before the cut, 0.5 s after it
    assert (moved[2].start, moved[2].end) == pytest.approx((3.0, 4.0))
    assert retime_cues(cues, [(0.0, 20.0)]) == cues


# ----------------------------------------------------------------------------- the ffmpeg command


def test_kept_parts_are_whole_frames_and_the_sound_loses_the_same_parts():
    options = ExportOptions(format="mp4", fps=30, start=10.0, end=20.0, keep=((0.0, 2.0), (3.5, 6.0)), subtitles="clip.ass")
    video, audio = keep_filters(options)
    assert video == ["select='between(n,0,59)+between(n,105,179)'", "setpts=N/(30*TB)"]
    # the sound is chosen by counting 160-sample frames at 48 kHz (300 a second), never by a timestamp
    assert audio == "aresample=48000,asetnsamples=n=160:p=0,aselect='between(n,0,599)+between(n,1050,1799)',asetpts=N/SR/TB"
    graph = build_video_filter(options)
    assert graph.index("fps=30") < graph.index("select=") < graph.index("subtitles=")  # captions are drawn on the shortened clip
    cmd = build_export_command("in.mp4", "out.mp4", options, ffmpeg="ffmpeg")
    complex_graph = cmd[cmd.index("-filter_complex") + 1]
    assert complex_graph.endswith(f";[0:a:0]{audio}[a]") and cmd[cmd.index("-map") + 1] == "[v]" and "[a]" in cmd and "0:a:0?" not in cmd
    silent = build_export_command("in.mp4", "out.gif", ExportOptions(format="gif", fps=10, keep=((0.0, 1.0),)), ffmpeg="ffmpeg")
    assert "select='between(n,0,9)'" in silent[silent.index("-filter_complex") + 1] and "-an" in silent and "aselect" not in " ".join(silent)
    free = keep_filters(ExportOptions(format="mp4", fps=None, keep=((0.5, 1.0),)))
    assert free[0] == ["select='gte(t,0.5000)*lt(t,1.0000)'", "setpts=N/FRAME_RATE/TB"]  # no rate given: chosen by time
    assert keep_filters(ExportOptions(format="mp4")) == ([], "")
    plain = build_export_command("in.mp4", "out.mp4", ExportOptions(format="mp4"), ffmpeg="ffmpeg")
    assert "0:a:0?" in plain and "select" not in " ".join(plain)  # without keep the command is what it was
    for bad in ((), ((2.0, 1.0),), ((0.0, 2.0), (1.0, 3.0))):
        with pytest.raises(ValueError, match="keep"):
            ExportOptions(format="mp4", keep=bad)


# ----------------------------------------------------------------------------- real clips


@pytest.fixture(scope="module")
def flashes(tmp_path_factory):
    """12 s: white picture and a tone in three spans, black and silent between them."""
    spans = [(0.5, 2.5), (5.0, 6.5), (9.0, 11.5)]
    on = "+".join(f"between(t,{a},{b})" for a, b in spans)
    video = tmp_path_factory.mktemp("flashes") / "flashes.mp4"
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", f"color=c=black:s=160x90:r=30:d=12,drawbox=c=white:t=fill:enable='{on}'",
        "-f", "lavfi", "-i", f"aevalsrc='0.5*sin(2*PI*440*t)*({on})':s=48000:d=12",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", str(video),
    ], check=True)
    return video, spans


def white_and_loud(path) -> tuple[np.ndarray, np.ndarray]:
    raw = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path), "-vf", "scale=8:8,format=gray", "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    white = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 64).mean(axis=1) > 128
    pcm = decode_pcm(path, sample_rate=48000)
    loud = np.zeros(len(white), dtype=bool)
    for index in range(len(white)):
        middle = int((index + 0.5) / 30 * 48000)
        piece = pcm[max(0, middle - 240): middle + 240].astype(np.float64)
        loud[index] = piece.size > 0 and float(np.sqrt(np.mean(piece ** 2))) > 0.05
    return white, loud


def runs(flags: np.ndarray) -> list[tuple[int, int]]:
    """(first frame, length) of every stretch that is on - what a failed comparison shows."""
    out, start = [], None
    for index, flag in enumerate(list(flags) + [False]):
        if flag and start is None:
            start = index
        elif not flag and start is not None:
            out.append((start, index - start))
            start = None
    return out


@needs_ffmpeg
def test_trimmed_clip_is_shorter_and_picture_stays_with_sound(flashes, tmp_path):
    video, spans = flashes
    whole = [Highlight(rank=1, start=0.0, end=12.0, peak=6.0, score=1.0)]
    cues = [Cue(0.6, 2.4, "one"), Cue(5.1, 6.4, "two"), Cue(9.1, 11.4, "three"), Cue(3.2, 4.4, "said into the silence")]
    options = ExportOptions(format="mp4", fps=30, quality=80)
    plain = make_clips(video, whole, tmp_path / "plain", options=options, cues=cues, credit="Source: X")[0]
    cut = make_clips(video, whole, tmp_path / "cut", options=options, cues=cues, credit="Source: X", trim_silence=0.7)[0]
    spoken = sum(b - a for a, b in spans)
    assert plain.removed == 0 and cut.removed == pytest.approx(2 * (2.5 - 2 * 0.25), abs=0.3)  # the two 2.5 s silences, each cut down to half a second
    assert probe(plain.path).duration == pytest.approx(12.0, abs=0.2)
    assert probe(cut.path).duration == pytest.approx(12.0 - cut.removed, abs=0.15)

    facts = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,start_time,duration,nb_frames", "-of", "compact", str(cut.path)], capture_output=True, text=True).stdout.split()
    assert len(decode_pcm(cut.path, sample_rate=48000)) / 48000 == pytest.approx(12.0 - cut.removed, abs=0.15), facts  # the sound is as long as the picture
    white, loud = white_and_loud(cut.path)
    apart = white != loud
    assert int(white.sum()) == pytest.approx(spoken * 30, abs=6)  # every white frame is still there ...
    assert int(apart.sum()) <= 12 and not np.any(apart[:-2] & apart[1:-1] & apart[2:]), f"picture {runs(white)}, sound {runs(loud)}"  # ... none more than two frames from its sound

    script = cut.subtitles.read_text(encoding="utf-8")
    lines = [line for line in script.splitlines() if line.startswith("Dialogue: 0")]
    assert len(lines) == 3 and all(line.endswith(word) for line, word in zip(lines, ("one", "two", "three")))  # the cue inside the silence went with it
    assert lines[1].split(",")[1].startswith("0:00:03.1")  # "two" (5.1 s) moved up by the two seconds cut before it
    credit = next(line for line in script.splitlines() if line.startswith("Dialogue: 1"))
    assert credit.split(",")[2] == f"0:00:{12.0 - cut.removed:05.2f}"  # the credit lasts as long as the shortened clip
    index = json.loads((tmp_path / "cut" / "clips.json").read_text(encoding="utf-8"))
    assert index["clips"][0]["removed"] == pytest.approx(cut.removed, abs=0.01) and index["clips"][0]["end"] == 12.0


@needs_ffmpeg
def test_nothing_is_cut_from_a_clip_without_sound_or_without_silence(flashes, tmp_path):
    video, _ = flashes
    mute = tmp_path / "mute.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video), "-an", "-c:v", "copy", str(mute)], check=True)
    options = ExportOptions(format="mp4", fps=30, quality=70)
    whole = [Highlight(rank=1, start=0.0, end=12.0, peak=6.0, score=1.0)]
    assert make_clips(mute, whole, tmp_path / "mute", options=options, trim_silence=0.7)[0].removed == 0  # no sound to go by
    tone = [Highlight(rank=1, start=0.6, end=2.4, peak=1.0, score=1.0)]
    result = make_clips(video, tone, tmp_path / "tone", options=options, trim_silence=0.7)[0]
    assert result.removed == 0 and probe(result.path).duration == pytest.approx(1.8, abs=0.15)
    gif = make_clips(video, whole, tmp_path / "gif", options=ExportOptions(format="gif", fps=10, width=80), trim_silence=0.7)[0]
    assert gif.removed > 3.5 and probe(gif.path).duration == pytest.approx(12.0 - gif.removed, abs=0.3)  # a format without sound is shortened too


@needs_ffmpeg
def test_clips_command_trims_silence(flashes, tmp_path, capsys):
    video, _ = flashes
    highlights = tmp_path / "h.json"
    highlights.write_text(json.dumps({"highlights": [{"rank": 1, "start": 0.0, "end": 12.0}]}), encoding="utf-8")
    base = ["clips", str(video), "--highlights", str(highlights), "--layout", "none", "--quality", "70"]
    assert main([*base, "-o", str(tmp_path / "a"), "--trim-silence"]) == 0
    assert "s of silence removed)" in capsys.readouterr().out
    assert probe(tmp_path / "a" / "clip_01.mp4").duration < 9
    assert main([*base, "-o", str(tmp_path / "b"), "--trim-silence", "4"]) == 0  # only the silences of four seconds: there are none that long
    assert "silence removed" not in capsys.readouterr().out and probe(tmp_path / "b" / "clip_01.mp4").duration == pytest.approx(12.0, abs=0.2)
    assert main([*base, "-o", str(tmp_path / "c")]) == 0
    assert json.loads((tmp_path / "c" / "clips.json").read_text(encoding="utf-8"))["clips"][0]["removed"] == 0


# ----------------------------------------------------------------------------- newer release


class Answer(io.BytesIO):
    def __init__(self, data) -> None:
        super().__init__(data if isinstance(data, bytes) else json.dumps(data).encode("utf-8"))


def answering(data, seen: list | None = None):
    def opener(request, timeout=None):
        if seen is not None:
            seen.append(request)
        return Answer(data)

    return opener


def test_versions_are_compared_as_numbers():
    assert updates.parse_version("v0.11.0") == (0, 11, 0) and updates.parse_version(" 1.2 ") == (1, 2)
    assert updates.parse_version("v1.0.0-rc1") == () and updates.parse_version("latest") == () and updates.parse_version("") == ()
    assert updates.is_newer("0.10.0", "0.9.9") and updates.is_newer("v1.0", "0.99.0") and updates.is_newer("0.11.1", "0.11")
    assert not updates.is_newer("0.11.0", "0.11.0") and not updates.is_newer("0.11", "0.11.0") and not updates.is_newer("0.9.0", "0.10.0")
    assert not updates.is_newer("v2.0.0-beta", "0.1.0") and not updates.is_newer("1.0.0", "dev")  # never "newer" when either cannot be read
    assert not updates.is_newer(__version__)


def test_latest_release_is_one_request_that_sends_nothing_about_the_user():
    seen: list = []
    release = updates.latest_release(opener=answering({"tag_name": "v9.8.7", "html_url": "https://github.com/BudongJW/stream2clip/releases/tag/v9.8.7", "body": "x" * 5000}, seen))
    assert release == updates.Release("9.8.7", "https://github.com/BudongJW/stream2clip/releases/tag/v9.8.7")
    assert len(seen) == 1 and seen[0].full_url == updates.RELEASES_API and seen[0].data is None and seen[0].get_method() == "GET"
    assert dict(seen[0].header_items()) == {"User-agent": "stream2clip", "Accept": "application/vnd.github+json"}
    # a link in the answer is used only when it is the project's own page
    elsewhere = updates.latest_release(opener=answering({"tag_name": "v9.8.7", "html_url": "https://example.invalid/get-it-here"}))
    assert elsewhere.url == updates.RELEASES_PAGE
    for odd in ({"message": "rate limit"}, {"tag_name": "nightly"}, ["v1.0.0"], {"tag_name": 3}):
        with pytest.raises(ValueError, match="Unexpected answer"):
            updates.latest_release(opener=answering(odd))
    with pytest.raises(ValueError):
        updates.latest_release(opener=answering(b"<html>not json"))


def test_check_for_update_names_only_a_newer_release(monkeypatch):
    newer = answering({"tag_name": "v99.0.0", "html_url": "https://github.com/BudongJW/stream2clip/releases/tag/v99.0.0"})
    assert updates.check_for_update(opener=newer).version == "99.0.0"
    assert updates.check_for_update("99.0.0", opener=newer) is None
    assert updates.check_for_update(opener=answering({"tag_name": f"v{__version__}"})) is None
    assert not updates.enabled()  # the test run itself never asks (conftest)
    monkeypatch.delenv("STREAM2CLIP_NO_UPDATE_CHECK")
    assert updates.enabled()
    monkeypatch.setenv("STREAM2CLIP_NO_UPDATE_CHECK", "true")
    assert not updates.enabled()


def test_setup_command_asks_about_a_newer_release_only_when_told(monkeypatch, capsys):
    from stream2clip import tools

    monkeypatch.setattr(tools, "components", lambda **kwargs: [])
    monkeypatch.setattr(updates, "check_for_update", lambda *args, **kwargs: pytest.fail("not asked for"))
    assert main(["setup", "--no-obs"]) == 0
    capsys.readouterr()
    monkeypatch.setattr(updates, "check_for_update", lambda *args, **kwargs: updates.Release("99.0.0", updates.RELEASES_PAGE))
    assert main(["setup", "--no-obs", "--check-update"]) == 0
    assert f"새 버전 99.0.0 있음 (현재 {__version__}): {updates.DOWNLOAD_PAGE}" in capsys.readouterr().out
    monkeypatch.setattr(updates, "check_for_update", lambda *args, **kwargs: None)
    assert main(["setup", "--no-obs", "--check-update"]) == 0
    assert f"최신 버전 사용 중 ({__version__})" in capsys.readouterr().out

    def offline(*args, **kwargs):
        raise OSError("no route to host")

    monkeypatch.setattr(updates, "check_for_update", offline)
    assert main(["setup", "--no-obs", "--check-update"]) == 1
    assert "no route to host" in capsys.readouterr().err
