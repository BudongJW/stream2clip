"""Audio-only signals: the envelope, laughter-like bursts (experimental) and singing sections."""

from __future__ import annotations

import subprocess

import numpy as np
import pytest

from stream2clip.audio import audio_envelope, laughter_levels
from stream2clip.chat import ChatMessage
from stream2clip.highlights import HighlightConfig, detect_highlights

from .conftest import needs_ffmpeg


def synth(path, expr, seconds=20, tone=220):
    """A tone whose volume follows ``expr`` (an ffmpeg expression of t)."""
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"sine=frequency={tone}:duration={seconds}:sample_rate=16000",
         "-af", f"volume='{expr}':eval=frame", str(path)],
        check=True,
    )
    return path


def chopped_envelope(seconds=30, bursts=((10, 13),), steady=((20, 23),), rate=100):
    """Quiet background, 5 Hz on/off bursts ("ha-ha-ha") and an equally loud steady stretch."""
    t = np.arange(seconds * rate) / rate
    env = np.full(t.size, 0.01)
    for a, b in bursts:
        inside = (t >= a) & (t < b)
        env[inside] = 0.5 * (np.sin(2 * np.pi * 5 * t[inside]) > 0) + 0.01
    for a, b in steady:
        env[(t >= a) & (t < b)] = 0.5
    return env


def test_laughter_score_wants_loud_and_chopped():
    scores = laughter_levels(chopped_envelope(), window=5.0)
    assert len(scores) == 6
    assert int(np.argmax(scores)) == 2 and scores[2] > 2  # the 5 Hz bursts at 10-13 s
    assert scores[4] < scores[2] / 2  # just as loud at 20-23 s, but one steady block
    assert scores[0] == 0 and scores[5] == 0
    assert laughter_levels(np.zeros(50), window=5.0).tolist() == [0.0]  # shorter than the analysis span
    with pytest.raises(ValueError):
        laughter_levels(np.zeros(1000), window=0)


@needs_ffmpeg
def test_envelope_and_laughter_from_a_file(tmp_path):
    # 0-8 s quiet, 8-11 s loud and switched on/off five times a second, 14-17 s loud and steady
    wav = synth(tmp_path / "a.wav", "if(between(t,8,11),0.8*gt(sin(2*PI*5*t),0)+0.01,if(between(t,14,17),0.8,0.01))")
    env = audio_envelope(wav)
    assert len(env) == pytest.approx(2000, abs=5) and env.dtype == np.float32  # 100 frames per second
    assert env[1500:1600].mean() > 20 * env[100:200].mean()
    scores = laughter_levels(wav, window=5.0)
    assert len(scores) == 4 and int(np.argmax(scores)) == 1 and scores[1] > 2 * max(scores[0], scores[2], scores[3], 0.01)


def quiet_chat(duration, burst_at):
    msgs = [ChatMessage(float(t), "なるほど", f"u{t % 37}") for t in range(0, duration, 2)]
    msgs += [ChatMessage(burst_at + 6 + i * 0.05, "草", f"r{i}") for i in range(160)]
    return sorted(msgs, key=lambda m: m.time)


def test_laughter_is_a_bonus_not_a_vote():
    """Switching the experimental signal on must not thin out the highlights found without it."""
    msgs = quiet_chat(1800, 600) + [ChatMessage(1200 + 6 + i * 0.05, "え？", f"s{i}") for i in range(160)]
    msgs.sort(key=lambda m: m.time)
    plain = detect_highlights(msgs, duration=1800).highlights
    assert len(plain) == 2
    bursts = np.zeros(360)
    bursts[121] = 6.0  # laughter-like sound right at the first moment (chat reacts ~6 s later)
    boosted = detect_highlights(msgs, duration=1800, laughter=bursts, laughter_window=5.0).highlights
    assert len(boosted) == 2  # the moment without laughter is still there
    by_start = {round(h.start / 600): h for h in boosted}
    plain_by_start = {round(h.start / 600): h for h in plain}
    assert by_start[1].score > plain_by_start[1].score and by_start[2].score == pytest.approx(plain_by_start[2].score)
    assert any("웃음소리" in reason for reason in by_start[1].reasons) and not any("웃음소리" in r for r in by_start[2].reasons)
    assert by_start[1].stats["laughter_z"] >= 2

    without = {name: weight for name, weight in HighlightConfig().weights.items() if name != "laughter"}
    off = detect_highlights(msgs, duration=1800, laughter=bursts, laughter_window=5.0, config=HighlightConfig(weights=without)).highlights
    assert [h.score for h in off] == pytest.approx([h.score for h in plain])  # weight left out = signal ignored


def talk_like(seconds, rate=8000, seed=0):
    """Short syllables with gliding pitch and pauses between them."""
    rng = np.random.default_rng(seed)
    out = np.zeros(seconds * rate, np.float32)
    pos = 0
    while pos < out.size:
        length, gap = int(rate * rng.uniform(0.08, 0.2)), int(rate * rng.uniform(0.05, 0.4))
        n = min(length, out.size - pos)
        t = np.arange(n) / rate
        f0, f1 = rng.uniform(150, 400), rng.uniform(150, 400)
        out[pos : pos + n] = 0.5 * np.sin(2 * np.pi * (f0 + (f1 - f0) * t / (length / rate)) * t)
        pos += length + gap
    return out


def song_like(seconds, rate=8000, seed=1):
    """Notes held for half a second each over a steady quiet backing."""
    rng = np.random.default_rng(seed)
    out = 0.05 * rng.standard_normal(seconds * rate)
    notes = [262, 294, 330, 349, 392, 440, 494, 523]
    half = rate // 2
    for k in range(seconds * 2):
        out[k * half : (k + 1) * half] += 0.4 * np.sin(2 * np.pi * notes[rng.integers(len(notes))] * np.arange(half) / rate)
    return out.astype(np.float32)


def test_singing_sections_find_the_song_between_the_talk():
    from stream2clip.audio import singing_sections

    pcm = np.concatenate([talk_like(60), song_like(120), talk_like(40, seed=2)])
    found = singing_sections(pcm)
    assert len(found) == 1
    song = found[0]
    assert song.start == pytest.approx(60, abs=10) and song.end == pytest.approx(180, abs=10) and song.duration > 100
    assert song.score > 0.3  # notes are held most of the time
    assert singing_sections(talk_like(200)) == []  # talking alone: pauses, no held notes
    assert singing_sections(song_like(40)) == []  # a jingle shorter than min_length
    assert len(singing_sections(song_like(40), min_length=20)) == 1
    steady_noise = (0.3 * np.random.default_rng(3).standard_normal(120 * 8000)).astype(np.float32)
    assert singing_sections(steady_noise) == []  # sustained but nobody is holding a note
    assert singing_sections(np.zeros(1000, np.float32)) == []


def test_mark_and_skip_singing():
    from stream2clip.highlights import mark_singing

    msgs = quiet_chat(1800, 600) + [ChatMessage(1200 + 6 + i * 0.05, "88888", f"s{i}") for i in range(160)]
    msgs.sort(key=lambda m: m.time)
    result = detect_highlights(msgs, duration=1800)
    assert len(result.highlights) == 2
    mark_singing(result, [(1100.0, 1400.0)])  # a song around the second moment
    by_start = {round(h.start / 600): h for h in result.highlights}
    assert by_start[1].stats["singing"] == 0 and not any("노래" in r for r in by_start[1].reasons)
    assert by_start[2].stats["singing"] == pytest.approx(1.0) and any("노래 구간" in r for r in by_start[2].reasons)

    mark_singing(result, [(1100.0, 1400.0)], drop=True)
    assert [round(h.start / 600) for h in result.highlights] == [1] and result.highlights[0].rank == 1


@needs_ffmpeg
def test_cli_singing_and_mark(tmp_path, capsys):
    import json
    import wave

    from stream2clip.cli import main

    pcm = np.concatenate([talk_like(30), song_like(90), talk_like(20, seed=2)])
    wav = tmp_path / "stream.wav"
    with wave.open(str(wav), "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(8000)
        fh.writeframes((np.clip(pcm, -1, 1) * 32767).astype(np.int16).tobytes())
    out = tmp_path / "songs.json"
    assert main(["singing", str(wav), "-o", str(out)]) == 0
    assert "1 singing sections" in capsys.readouterr().out
    section = json.loads(out.read_text(encoding="utf-8"))["sections"][0]
    assert section["start"] == pytest.approx(30, abs=10) and section["end"] == pytest.approx(120, abs=10)
