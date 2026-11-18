"""Audio loudness curve of a media file (for highlight detection)."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass

import numpy as np

from .ffmpeg import find_ffmpeg

__all__ = ["SingingSection", "audio_levels", "audio_envelope", "decode_pcm", "laughter_levels", "singing_sections"]


def audio_levels(path: str | os.PathLike[str], *, window: float = 10.0, sample_rate: int = 8000, ffmpeg: str | None = None) -> np.ndarray:
    """Return RMS loudness in dBFS for consecutive ``window``-second buckets.

    Audio is decoded to mono ``sample_rate`` Hz 16-bit PCM and streamed, so
    multi-hour VODs use constant memory. Silent buckets are -90 dB.
    """
    if window <= 0:
        raise ValueError("window must be positive")
    cmd = [
        ffmpeg or find_ffmpeg(), "-hide_banner", "-loglevel", "error", "-nostdin",
        "-i", os.fspath(path), "-vn", "-ac", "1", "-ar", str(sample_rate), "-f", "s16le", "-",
    ]
    chunk = max(1, int(round(window * sample_rate)))
    levels: list[float] = []
    buffer = np.empty(0, dtype=np.int16)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdout is not None
    try:
        while True:
            data = proc.stdout.read(chunk * 2 * 8)
            if not data:
                break
            buffer = np.concatenate([buffer, np.frombuffer(data[: len(data) - len(data) % 2], dtype=np.int16)])
            while buffer.size >= chunk:
                levels.append(_rms_db(buffer[:chunk]))
                buffer = buffer[chunk:]
        if buffer.size >= chunk // 4:
            levels.append(_rms_db(buffer))
    finally:
        stderr = proc.stderr.read().decode("utf-8", "replace") if proc.stderr else ""
        code = proc.wait()
    if code != 0:
        raise RuntimeError(f"ffmpeg could not decode audio from {path}: {stderr.strip()[-400:]}")
    return np.array(levels, dtype=np.float64)


def audio_envelope(path: str | os.PathLike[str], *, rate: int = 100, sample_rate: int = 8000, ffmpeg: str | None = None) -> np.ndarray:
    """RMS amplitude (0..1) in ``1 / rate`` second frames, streamed so hours of audio stay small in memory."""
    cmd = [
        ffmpeg or find_ffmpeg(), "-hide_banner", "-loglevel", "error", "-nostdin",
        "-i", os.fspath(path), "-vn", "-ac", "1", "-ar", str(sample_rate), "-f", "s16le", "-",
    ]
    hop = max(1, sample_rate // rate)
    frames: list[np.ndarray] = []
    rest = np.empty(0, dtype=np.int16)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdout is not None
    try:
        while True:
            data = proc.stdout.read(hop * 2 * 2000)
            if not data:
                break
            samples = np.concatenate([rest, np.frombuffer(data[: len(data) - len(data) % 2], dtype=np.int16)])
            whole = samples.size // hop
            if whole:
                block = samples[: whole * hop].astype(np.float32).reshape(whole, hop) / 32768.0
                frames.append(np.sqrt(np.mean(block * block, axis=1)))
            rest = samples[whole * hop :]
    finally:
        stderr = proc.stderr.read().decode("utf-8", "replace") if proc.stderr else ""
        code = proc.wait()
    if code != 0:
        raise RuntimeError(f"ffmpeg could not decode audio from {path}: {stderr.strip()[-400:]}")
    return np.concatenate(frames) if frames else np.empty(0, dtype=np.float32)


def laughter_levels(source: "str | os.PathLike[str] | np.ndarray", *, window: float = 5.0, rate: int = 100, ffmpeg: str | None = None) -> np.ndarray:
    """Experimental: how much each ``window`` sounds like a burst of laughter (0 = not at all).

    Laughter is loud and chopped into a few bursts per second ("ha-ha-ha"). Each second is
    scored by how loud it is compared with the rest of the stream, plus a bonus when the
    strongest rhythm of its loudness envelope is 3.5-8 Hz; a window gets the best second in
    it. There is no speech model behind this - fast excited talking scores too. On one real
    stream the top moments were followed by 2.1x the usual laughing in chat (loudness
    alone: 1.7x), which is why the signal is opt-in.

    ``source`` is a media file or an envelope from :func:`audio_envelope`.
    """
    if window <= 0:
        raise ValueError("window must be positive")
    envelope = source if isinstance(source, np.ndarray) else audio_envelope(source, rate=rate, ffmpeg=ffmpeg)
    span, step = 2 * rate, rate  # 2 s of envelope, scored every second
    if envelope.size < span:
        return np.zeros(max(1, int(np.ceil(envelope.size / rate / window))))
    count = (envelope.size - span) // step + 1
    index = np.arange(span)[None, :] + (np.arange(count) * step)[:, None]
    pieces = envelope[index].astype(np.float64)
    level = 20.0 * np.log10(np.sqrt(np.mean(pieces * pieces, axis=1)) + 1e-9)
    median = float(np.median(level))
    spread = 1.4826 * float(np.median(np.abs(level - median))) or float(np.std(level)) or 1.0
    loud = (level - median) / spread
    spectrum = np.abs(np.fft.rfft((pieces - pieces.mean(axis=1, keepdims=True)) * np.hanning(span)[None, :], axis=1)) ** 2
    freqs = np.fft.rfftfreq(span, d=1.0 / rate)
    strongest = freqs[1:][np.argmax(spectrum[:, 1:], axis=1)]
    chopped = (strongest >= 3.5) & (strongest <= 8.0) & (spectrum[:, 1:].max(axis=1) > 1e-12)
    score = np.clip(loud + 2.0 * chopped, 0.0, None) * chopped  # loud alone is the loudness signal's job
    per_window = max(1, int(round(window)))
    buckets = int(np.ceil(envelope.size / rate / window))
    out = np.zeros(buckets)
    for i in range(buckets):
        chunk = score[i * per_window : (i + 1) * per_window]
        if chunk.size:
            out[i] = float(chunk.max())
    return out


def decode_pcm(path: str | os.PathLike[str], *, sample_rate: int = 16000, ffmpeg: str | None = None) -> np.ndarray:
    """Decode a media file to mono float32 samples in -1..1 (what speech models take as input)."""
    cmd = [
        ffmpeg or find_ffmpeg(), "-hide_banner", "-loglevel", "error", "-nostdin",
        "-i", os.fspath(path), "-vn", "-ac", "1", "-ar", str(sample_rate), "-f", "f32le", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg could not decode audio from {path}: {proc.stderr.decode('utf-8', 'replace').strip()[-400:]}")
    return np.frombuffer(proc.stdout[: len(proc.stdout) - len(proc.stdout) % 4], dtype=np.float32)


def _rms_db(samples: np.ndarray) -> float:
    if samples.size == 0:
        return -90.0
    rms = float(np.sqrt(np.mean((samples.astype(np.float64) / 32768.0) ** 2)))
    return max(-90.0, 20.0 * np.log10(rms)) if rms > 0 else -90.0


# --------------------------------------------------------------------------- singing sections

_SING_RATE = 8000
_SING_FRAME = 512  # 64 ms
_SING_HOP = 256  # 32 ms


@dataclass(frozen=True)
class SingingSection:
    """A stretch that sounds like a song. ``score`` is the share of time a pitch was being held."""

    start: float
    end: float
    score: float

    @property
    def duration(self) -> float:
        return self.end - self.start


def _tone_track(pcm: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per 32 ms frame: strongest frequency in 150-1200 Hz, how much it stands out, and the level."""
    frames = max(0, (pcm.size - _SING_FRAME) // _SING_HOP + 1)
    freq = np.zeros(frames, dtype=np.float32)
    tonal = np.zeros(frames, dtype=np.float32)
    level = np.zeros(frames, dtype=np.float32)
    window = np.hanning(_SING_FRAME).astype(np.float32)
    freqs = np.fft.rfftfreq(_SING_FRAME, 1.0 / _SING_RATE)
    band = (freqs >= 150) & (freqs <= 1200)
    band_freqs = freqs[band]
    for start in range(0, frames, 4000):  # in blocks, to keep the FFT input small
        index = np.arange(start, min(frames, start + 4000))
        raw = pcm[index[:, None] * _SING_HOP + np.arange(_SING_FRAME)[None, :]].astype(np.float32)
        magnitude = np.abs(np.fft.rfft(raw * window[None, :], axis=1))[:, band]
        freq[index] = band_freqs[magnitude.argmax(axis=1)]
        tonal[index] = magnitude.max(axis=1) / (magnitude.mean(axis=1) + 1e-9)
        level[index] = np.sqrt(np.mean(raw * raw, axis=1))
    return freq, tonal, level


def singing_sections(
    source: "str | os.PathLike[str] | np.ndarray",
    *,
    min_length: float = 60.0,
    window: float = 10.0,
    steadiness: float = 0.75,
    held_pitch: float = 0.05,
    ffmpeg: str | None = None,
) -> list[SingingSection]:
    """Find the songs in a stream (歌枠, karaoke) from the audio alone.

    Two things have to be true for at least ``min_length`` seconds:

    * the sound is *sustained* - the loudness in each ``window`` varies little
      (std / mean of the envelope below ``steadiness``); talking has pauses, music does not
    * someone is *holding notes* - the strongest tone stays on one pitch for a quarter of a
      second or more during at least ``held_pitch`` of the time. Speech never does, and
      background music alone (a waiting screen) rarely does.

    Checked on one karaoke stream and one game stream: 10 sections in the first (86% of
    YouTube's own [音楽] caption markers fell inside them), none in the second. It is a
    heuristic, not a music classifier: quiet a-cappella humming or a game with a constant
    loud score can fool it.

    ``source`` is a media file, or mono float samples at 8 kHz.
    """
    pcm = source if isinstance(source, np.ndarray) else decode_pcm(source, sample_rate=_SING_RATE, ffmpeg=ffmpeg)
    freq, tonal, level = _tone_track(np.asarray(pcm, dtype=np.float32))
    per = max(1, int(round(window * _SING_RATE / _SING_HOP)))
    count = freq.size // per
    if count == 0:
        return []

    # frames that belong to a run of >= 8 frames (0.25 s) on the same pitch with a clear tone
    step = np.abs(np.log2((freq[1:] + 1e-9) / (freq[:-1] + 1e-9)))
    same = np.concatenate([[False], step < 0.045]) & (tonal > 6.0)
    held = np.zeros(freq.size, dtype=bool)
    run = 0
    for i in range(freq.size):
        run = run + 1 if same[i] else 0
        if run >= 8:
            held[i - 7 : i + 1] = True

    levels = level[: count * per].reshape(count, per).astype(np.float64)
    variation = levels.std(axis=1) / (levels.mean(axis=1) + 1e-9)
    share = held[: count * per].reshape(count, per).mean(axis=1)
    audible = levels.mean(axis=1) > 1e-4
    steady = (variation < steadiness) & audible
    padded = np.pad(steady.astype(float), 2, mode="edge")
    smooth = np.array([np.median(padded[i : i + 5]) for i in range(count)]) > 0.5  # ignore a stray window either way

    sections: list[SingingSection] = []
    need = max(1, int(np.ceil(min_length / window)))
    start = None
    for i, flag in enumerate(list(smooth) + [False]):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            score = float(share[start:i].mean())
            if i - start >= need and score >= held_pitch:
                sections.append(SingingSection(start * window, i * window, round(score, 3)))
            start = None
    return sections
