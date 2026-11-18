from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
needs_ffmpeg = pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg/ffprobe not installed")


@pytest.fixture
def green_screen_video(tmp_path: Path) -> Path:
    """2 s, 160x120, 10 fps: a red square moving over a pure green background."""
    out = tmp_path / "green.mp4"
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "color=c=0x00FF00:s=160x120:r=10:d=2",
            "-f", "lavfi", "-i", "color=c=0xFF0000:s=40x40:r=10:d=2",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-filter_complex", "[0][1]overlay=x='t*40':y=40:shortest=1[v]",
            "-map", "[v]", "-map", "2:a",
            "-c:v", "libx264", "-qp", "0", "-pix_fmt", "yuv444p", "-c:a", "aac", "-shortest",
            str(out),
        ],
        check=True,
    )
    return out


def moving_square(t: float, size: tuple[int, int] = (96, 64)) -> np.ndarray:
    w, h = size
    frame = np.zeros((h, w, 4), dtype=np.uint8)
    frame[..., 1] = 255  # green background
    frame[..., 3] = 255
    x = int(t * 60) % (w - 16)
    frame[20:36, x : x + 16] = (255, 0, 0, 255)
    return frame
