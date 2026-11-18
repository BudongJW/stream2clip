"""Audio loudness curve of a media file (for highlight detection)."""

from __future__ import annotations

import os
import subprocess

import numpy as np

from .ffmpeg import find_ffmpeg

__all__ = ["audio_levels"]


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


def _rms_db(samples: np.ndarray) -> float:
    if samples.size == 0:
        return -90.0
    rms = float(np.sqrt(np.mean((samples.astype(np.float64) / 32768.0) ** 2)))
    return max(-90.0, 20.0 * np.log10(rms)) if rms > 0 else -90.0
