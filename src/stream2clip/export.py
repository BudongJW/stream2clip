"""Run ffmpeg exports and probe media files."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

from .ffmpeg import H264_ENCODERS, ExportOptions, build_export_command, find_ffmpeg, find_ffprobe

if TYPE_CHECKING:
    import numpy as np

    from .layouts import VerticalLayout

__all__ = ["FFmpegError", "MediaInfo", "export", "grab_frames", "h264_encoder", "has_alpha", "measure_loudness", "probe", "resolve_encoder", "run_ffmpeg"]


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


@lru_cache(maxsize=4)
def h264_encoder(ffmpeg: str | None = None) -> str:
    """The first GPU H.264 encoder that encodes a few frames on this PC, else ``libx264``.

    ffmpeg builds list NVENC, QSV and AMF whether or not the PC has the GPU, so each one is
    tried on a tiny picture (about a second at most); the answer is kept for the session.
    """
    exe = ffmpeg or find_ffmpeg()
    for encoder in H264_ENCODERS:
        cmd = [exe, "-hide_banner", "-loglevel", "error", "-nostdin", "-f", "lavfi", "-i", "color=c=black:s=256x144:r=30:d=0.2",
               "-frames:v", "3", "-pix_fmt", "yuv420p", "-c:v", encoder, "-f", "null", "-"]
        try:
            if subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20, check=False).returncode == 0:
                return encoder
        except (OSError, subprocess.TimeoutExpired):
            continue
    return "libx264"


def resolve_encoder(options: ExportOptions, *, ffmpeg: str | None = None) -> ExportOptions:
    """``options`` with ``encoder="auto"`` replaced by the encoder this PC has (MP4 only)."""
    if options.format == "mp4" and options.encoder == "auto":
        return replace(options, encoder=h264_encoder(ffmpeg))
    return options


def export(
    input_path: str | os.PathLike[str],
    output_path: str | os.PathLike[str],
    options: ExportOptions | None = None,
    *,
    ffmpeg: str | None = None,
    timeout: float | None = None,
) -> Path:
    """Convert a video file (or a section of it) into a GIF/WebP/MP4/WebM/MOV/APNG clip.

    With ``options.loudness`` and nothing measured yet, the sound is measured first (one more
    ffmpeg run that writes nothing); a clip without sound, or a silent one, is left as it is.
    ``encoder="auto"`` takes the GPU encoder this PC has; if a GPU encoder fails on a clip (a
    driver too old, the GPU busy with too many encodes), the clip is encoded again with libx264.
    """
    options = resolve_encoder(options or ExportOptions(), ffmpeg=ffmpeg)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if options.loudness is not None and options.loudness.measured is None:
        options = measure_loudness(input_path, options, ffmpeg=ffmpeg, timeout=timeout)
    try:
        run_ffmpeg(build_export_command(input_path, out, options, ffmpeg=ffmpeg), timeout=timeout)
    except FFmpegError:
        if options.format != "mp4" or options.encoder not in H264_ENCODERS:
            raise
        run_ffmpeg(build_export_command(input_path, out, replace(options, encoder="libx264"), ffmpeg=ffmpeg), timeout=timeout)
    return out


def measure_loudness(input_path: str | os.PathLike[str], options: ExportOptions, *, ffmpeg: str | None = None, timeout: float | None = None) -> ExportOptions:
    """``options`` with the first loudness pass filled in (``loudness`` dropped when there is no sound to bring up or down)."""
    from dataclasses import replace

    from .ffmpeg import build_loudness_command, parse_loudnorm

    if options.loudness is None:
        return options
    layers = options.mix is not None and bool(options.mix.layers)
    if not options.audio or (not layers and not probe(input_path).has_audio):
        return replace(options, loudness=None)  # no sound at all: nothing to bring up or down
    cmd = build_loudness_command(input_path, options, ffmpeg=ffmpeg)
    proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=timeout, check=False)
    stderr = proc.stderr.decode("utf-8", "replace")
    if proc.returncode != 0:
        raise FFmpegError(cmd, proc.returncode, stderr)
    measured = parse_loudnorm(stderr)
    return replace(options, loudness=replace(options.loudness, measured=measured) if measured else None)


def grab_frames(path: str | os.PathLike[str], times: Sequence[float], *, layout: "VerticalLayout | None" = None, ffmpeg: str | None = None) -> "list[np.ndarray]":
    """Decode one frame per timestamp as ``(h, w, 4)`` uint8 RGBA arrays (fast seek).

    Frames have the source size, or ``layout.size`` when a layout is given (a quick
    still preview of what a clip will look like).
    """
    import numpy as np

    from .ffmpeg import find_ffmpeg

    if layout is not None:
        width, height = layout.size
        shape = ["-filter_complex", layout.graph("[0:v]", "[v]", avatar_inp="[1:v]" if layout.uses_avatar_video else None), "-map", "[v]"]
    else:
        info = probe(path)
        width, height = info.width, info.height
        shape = []
    frames = []
    for t in times:
        avatar = []
        if layout is not None and layout.uses_avatar_video:
            from .ffmpeg import avatar_decoder_args

            avatar = ["-ss", f"{max(0.0, t + layout.avatar_offset):.3f}", *avatar_decoder_args(layout), "-i", os.fspath(layout.avatar_source)]  # type: ignore[arg-type]
        cmd = [ffmpeg or find_ffmpeg(), "-hide_banner", "-loglevel", "error", "-nostdin", "-ss", f"{max(0.0, t):.3f}", "-i", os.fspath(path),
               *avatar, *shape, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgba", "-"]
        proc = subprocess.run(cmd, capture_output=True, check=False)
        if proc.returncode != 0:
            raise FFmpegError(cmd, proc.returncode, proc.stderr.decode("utf-8", "replace"))
        if len(proc.stdout) < width * height * 4:
            continue  # past the end of the file
        frames.append(np.frombuffer(proc.stdout[: width * height * 4], dtype=np.uint8).reshape(height, width, 4).copy())
    return frames


def has_alpha(path: str | os.PathLike[str], *, ffprobe: str | None = None) -> bool:
    """Whether a video carries its own transparency (ProRes 4444, PNG and the like by pixel format, WebM by its alpha tag)."""
    cmd = [ffprobe or find_ffprobe(), "-v", "error", "-print_format", "json", "-show_streams", os.fspath(path)]
    proc = subprocess.run(cmd, capture_output=True, check=False)
    if proc.returncode != 0:
        raise FFmpegError(cmd, proc.returncode, proc.stderr.decode("utf-8", "replace"))
    video = next((s for s in json.loads(proc.stdout or b"{}").get("streams", []) if s.get("codec_type") == "video"), None)
    if video is None:
        raise ValueError(f"No video stream in {path}")
    pix_fmt = str(video.get("pix_fmt") or "")
    tags = {str(key).lower(): str(value) for key, value in (video.get("tags") or {}).items()}
    return pix_fmt.startswith(("yuva", "rgba", "bgra", "argb", "abgr", "gbrap", "ya")) or tags.get("alpha_mode") == "1"


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
