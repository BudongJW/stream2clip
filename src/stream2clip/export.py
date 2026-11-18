"""Run ffmpeg exports and probe media files."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

from .ffmpeg import ExportOptions, build_export_command, find_ffprobe

if TYPE_CHECKING:
    import numpy as np

__all__ = ["FFmpegError", "MediaInfo", "export", "grab_frames", "probe", "run_ffmpeg"]


class FFmpegError(RuntimeError):
    def __init__(self, cmd: list[str], returncode: int, stderr: str) -> None:
        tail = "\n".join(stderr.strip().splitlines()[-15:])
        super().__init__(f"ffmpeg exited with code {returncode}:\n{tail}")
        self.cmd = cmd
        self.returncode = returncode
        self.stderr = stderr


@dataclass(frozen=True)
class MediaInfo:
    width: int
    height: int
    duration: float | None
    fps: float | None
    codec: str
    pix_fmt: str | None
    frames: int | None
    has_audio: bool

    @property
    def has_alpha(self) -> bool:
        pix = (self.pix_fmt or "").lower()
        return pix.startswith(("yuva", "rgba", "bgra", "argb", "abgr", "gbrap", "ya", "pal8")) or pix.endswith("a")


def run_ffmpeg(cmd: list[str], *, timeout: float | None = None) -> None:
    proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=timeout, check=False)
    if proc.returncode != 0:
        raise FFmpegError(cmd, proc.returncode, proc.stderr.decode("utf-8", "replace"))


def export(
    input_path: str | os.PathLike[str],
    output_path: str | os.PathLike[str],
    options: ExportOptions | None = None,
    *,
    ffmpeg: str | None = None,
    timeout: float | None = None,
) -> Path:
    """Convert a video file (or a section of it) into a GIF/WebP/MP4/WebM/MOV/APNG clip."""
    options = options or ExportOptions()
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(build_export_command(input_path, out, options, ffmpeg=ffmpeg), timeout=timeout)
    return out


def grab_frames(path: str | os.PathLike[str], times: Sequence[float], *, ffmpeg: str | None = None) -> "list[np.ndarray]":
    """Decode one frame per timestamp as ``(h, w, 4)`` uint8 RGBA arrays (fast seek, source size)."""
    import numpy as np

    from .ffmpeg import find_ffmpeg

    info = probe(path)
    frames = []
    for t in times:
        cmd = [ffmpeg or find_ffmpeg(), "-hide_banner", "-loglevel", "error", "-nostdin", "-ss", f"{max(0.0, t):.3f}", "-i", os.fspath(path),
               "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgba", "-"]
        proc = subprocess.run(cmd, capture_output=True, check=False)
        if proc.returncode != 0:
            raise FFmpegError(cmd, proc.returncode, proc.stderr.decode("utf-8", "replace"))
        if len(proc.stdout) < info.width * info.height * 4:
            continue  # past the end of the file
        frames.append(np.frombuffer(proc.stdout[: info.width * info.height * 4], dtype=np.uint8).reshape(info.height, info.width, 4).copy())
    return frames


def _fraction(value: str | None) -> float | None:
    if not value or value in ("0/0", "N/A"):
        return None
    if "/" in value:
        num, den = value.split("/", 1)
        try:
            return float(num) / float(den) if float(den) else None
        except ValueError:
            return None
    try:
        return float(value)
    except ValueError:
        return None


def probe(path: str | os.PathLike[str], *, ffprobe: str | None = None, count_frames: bool = False) -> MediaInfo:
    cmd = [ffprobe or find_ffprobe(), "-v", "error", "-print_format", "json", "-show_streams", "-show_format"]
    if count_frames:
        cmd.append("-count_frames")
    cmd.append(os.fspath(path))
    proc = subprocess.run(cmd, capture_output=True, check=False)
    if proc.returncode != 0:
        raise FFmpegError(cmd, proc.returncode, proc.stderr.decode("utf-8", "replace"))
    data = json.loads(proc.stdout or b"{}")
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video is None:
        raise ValueError(f"No video stream in {path}")
    duration = _fraction(video.get("duration")) or _fraction(data.get("format", {}).get("duration"))
    frames = video.get("nb_read_frames") or video.get("nb_frames")
    return MediaInfo(
        width=int(video["width"]),
        height=int(video["height"]),
        duration=duration,
        fps=_fraction(video.get("avg_frame_rate")) or _fraction(video.get("r_frame_rate")),
        codec=video.get("codec_name", ""),
        pix_fmt=video.get("pix_fmt"),
        frames=int(frames) if frames not in (None, "N/A") else None,
        has_audio=any(s.get("codec_type") == "audio" for s in streams),
    )
