"""Pure ffmpeg command / filtergraph builders.

Nothing in this module spawns a process; every function returns strings or
argument lists. That is deliberate: the same builders can be dropped into any
ffmpeg-based project (autoclip, FunClip, biliup, MoviePy's ``ffmpeg_params``,
shell scripts, ...) without adopting the rest of stream2clip. Running commands
lives in :mod:`stream2clip.export`.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING

from .chroma import DEFAULT_KEY_COLOR, colorkey_filter
from .geometry import Region

if TYPE_CHECKING:  # pragma: no cover
    from .layouts import VerticalLayout

__all__ = [
    "FORMATS",
    "ALPHA_FORMATS",
    "ExportOptions",
    "RawVideoInput",
    "FFmpegNotFoundError",
    "find_ffmpeg",
    "find_ffprobe",
    "build_video_filter",
    "build_export_command",
    "build_capture_command",
    "extension_for",
    "filter_path",
]

#: Output formats understood by :func:`build_export_command`.
FORMATS = ("gif", "webp", "mp4", "webm", "mov", "apng")
#: Formats that can carry transparency.
ALPHA_FORMATS = frozenset({"gif", "webp", "webm", "mov", "apng"})
_EXTENSIONS = {"gif": ".gif", "webp": ".webp", "mp4": ".mp4", "webm": ".webm", "mov": ".mov", "apng": ".png"}
_EVEN_DIMENSIONS = frozenset({"mp4", "webm"})
_AUDIO_CODECS = {"mp4": ["-c:a", "aac", "-b:a", "160k"], "webm": ["-c:a", "libopus", "-b:a", "128k"], "mov": ["-c:a", "pcm_s16le"]}
GIF_DITHERS = ("sierra2_4a", "bayer", "floyd_steinberg", "sierra2", "heckbert", "none")


class FFmpegNotFoundError(RuntimeError):
    pass


def app_dir() -> Path | None:
    """Folder of the program when running as a built executable (PyInstaller), else ``None``."""
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else None


def _find_binary(name: str, env: str) -> str:
    candidate = os.environ.get(env)
    if candidate:
        return candidate
    bundled = app_dir()
    if bundled is not None:  # a copy shipped next to the program wins over whatever is on PATH
        for filename in (name + ".exe", name):
            if (bundled / filename).is_file():
                return str(bundled / filename)
    found = shutil.which(name)
    if found:
        return found
    if name == "ffmpeg":
        try:  # optional: pip install imageio-ffmpeg ships a static binary
            import imageio_ffmpeg  # type: ignore[import-not-found]

            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:  # pragma: no cover - optional dependency
            pass
    raise FFmpegNotFoundError(
        f"{name} not found. Install ffmpeg (https://ffmpeg.org/download.html), add it to PATH, "
        f"or set the {env} environment variable."
    )


def find_ffmpeg() -> str:
    return _find_binary("ffmpeg", "STREAM2CLIP_FFMPEG")


def find_ffprobe() -> str:
    return _find_binary("ffprobe", "STREAM2CLIP_FFPROBE")


def extension_for(fmt: str) -> str:
    return _EXTENSIONS[fmt]


@dataclass(frozen=True)
class ExportOptions:
    """Everything that shapes an exported clip.

    Times are seconds relative to the input. ``crop`` is applied before scaling,
    in source pixels. ``width``/``height`` scale the output keeping aspect ratio
    when only one is given.
    """

    format: str = "gif"
    fps: float | None = 15.0
    width: int | None = None
    height: int | None = None
    crop: Region | None = None
    start: float | None = None
    end: float | None = None
    transparent: bool = False
    #: Color removed when ``transparent`` is set. ``None`` keeps the input's own
    #: alpha channel (e.g. frames rendered with transparency) without keying.
    key_color: str | None = DEFAULT_KEY_COLOR
    similarity: float = 0.12
    blend: float = 0.0
    quality: int = 80
    loop: int = 0
    max_colors: int = 256
    dither: str = "sierra2_4a"
    audio: bool = True
    extra_filters: tuple[str, ...] = field(default_factory=tuple)
    #: 9:16 (or any) layout applied after crop/fps (see :mod:`stream2clip.layouts`).
    layout: "VerticalLayout | None" = None
    #: Subtitle file (.ass/.srt/.vtt) burned in after the layout, timed from the clip start.
    subtitles: "str | os.PathLike[str] | None" = None

    def __post_init__(self) -> None:
        if self.format not in FORMATS:
            raise ValueError(f"Unsupported format {self.format!r}; choose one of {', '.join(FORMATS)}")
        if self.transparent and self.format not in ALPHA_FORMATS:
            raise ValueError(
                f"{self.format.upper()} cannot store transparency; use one of: {', '.join(sorted(ALPHA_FORMATS))}"
            )
        if not 1 <= self.quality <= 100:
            raise ValueError("quality must be in 1..100")
        if not 2 <= self.max_colors <= 256:
            raise ValueError("max_colors must be in 2..256")
        if self.dither not in GIF_DITHERS:
            raise ValueError(f"dither must be one of {', '.join(GIF_DITHERS)}")
        if self.fps is not None and self.fps <= 0:
            raise ValueError("fps must be positive")
        if self.start is not None and self.start < 0:
            raise ValueError("start must be >= 0")
        if self.start is not None and self.end is not None and self.end <= self.start:
            raise ValueError("end must be greater than start")

    @property
    def duration(self) -> float | None:
        if self.end is None:
            return None
        return self.end - (self.start or 0.0)

    def with_format(self, fmt: str) -> "ExportOptions":
        return replace(self, format=fmt)


@dataclass(frozen=True)
class RawVideoInput:
    """Describes raw frames written to ffmpeg's stdin (``-f rawvideo``)."""

    width: int
    height: int
    fps: float
    pix_fmt: str = "rgba"

    def args(self) -> list[str]:
        return [
            "-f", "rawvideo",
            "-pix_fmt", self.pix_fmt,
            "-s", f"{self.width}x{self.height}",
            "-r", f"{self.fps:g}",
            "-i", "-",
        ]


def _scale_filter(options: ExportOptions) -> str | None:
    even = options.format in _EVEN_DIMENSIONS
    if options.width is None and options.height is None:
        return "scale=trunc(iw/2)*2:trunc(ih/2)*2" if even else None
    auto = "-2" if even else "-1"
    w = str(options.width) if options.width else auto
    h = str(options.height) if options.height else auto
    if even:
        # Fixed sizes still have to be even for yuv420p.
        w = str(options.width - options.width % 2) if options.width else w
        h = str(options.height - options.height % 2) if options.height else h
    return f"scale={w}:{h}:flags=lanczos"


def filter_path(path: str | os.PathLike[str]) -> str:
    """Escape a file path for use as a filter option inside a filtergraph (two ffmpeg escaping levels)."""
    value = os.fspath(path).replace("\\", "/")
    value = re.sub(r"([\\':])", r"\\\1", value)  # option level
    return re.sub(r"([\\'\[\],;])", r"\\\1", value)  # graph level


def build_video_filter(options: ExportOptions) -> str:
    """Return a ``-filter_complex`` graph reading ``[0:v]`` and writing ``[v]``."""
    pre: list[str] = []
    if options.crop is not None:
        c = options.crop
        pre.append(f"crop={c.width}:{c.height}:{c.x}:{c.y}")
    if options.fps is not None:
        pre.append(f"fps={options.fps:g}")
    scale = _scale_filter(options)
    prefix, src = "", "[0:v]"
    if options.layout is not None:
        prefix = f"[0:v]{','.join(pre) or 'null'}[pre];{options.layout.graph('[pre]', '[lay]')};"
        src = "[lay]"
        chain: list[str] = [scale] if scale and (options.width or options.height) else []
    else:
        chain = pre + ([scale] if scale else [])
    if options.subtitles is not None:
        chain.append(f"subtitles=filename={filter_path(options.subtitles)}")
    chain.extend(options.extra_filters)
    if options.transparent:
        chain.append("format=rgba")
        if options.key_color is not None:
            chain.append(colorkey_filter(options.key_color, options.similarity, options.blend))

    fmt = options.format
    if fmt == "gif":
        if options.transparent:
            palettegen = f"palettegen=max_colors={options.max_colors}:reserve_transparent=1:stats_mode=full"
            paletteuse = f"paletteuse=dither={options.dither}:alpha_threshold=128"
        else:
            palettegen = f"palettegen=max_colors={options.max_colors}:stats_mode=diff"
            paletteuse = f"paletteuse=dither={options.dither}:diff_mode=rectangle"
        head = ",".join(chain) if chain else "null"
        return f"{prefix}{src}{head},split[s0][s1];[s0]{palettegen}[p];[s1][p]{paletteuse}[v]"

    pix_fmt = {
        ("webp", False): "yuv420p",
        ("webp", True): "yuva420p",
        ("mp4", False): "yuv420p",
        ("webm", False): "yuv420p",
        ("webm", True): "yuva420p",
        ("mov", False): "yuv422p10le",
        ("mov", True): "yuva444p10le",
        ("apng", False): "rgb24",
        ("apng", True): "rgba",
    }[(fmt, options.transparent)]
    chain.append(f"format={pix_fmt}")
    return f"{prefix}{src}{','.join(chain)}[v]"


def _codec_args(options: ExportOptions) -> list[str]:
    q = options.quality
    fmt = options.format
    if fmt == "gif":
        return ["-f", "gif", "-loop", str(options.loop)]
    if fmt == "webp":
        return ["-c:v", "libwebp_anim", "-lossless", "0", "-quality", str(q), "-compression_level", "4",
                "-loop", str(options.loop), "-f", "webp"]
    if fmt == "apng":
        return ["-c:v", "apng", "-plays", str(options.loop), "-f", "apng"]
    if fmt == "mp4":
        crf = round(51 - q * 0.33)  # quality 80 -> crf 25, 100 -> 18
        return ["-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-movflags", "+faststart"]
    if fmt == "webm":
        crf = round(63 - q * 0.4)  # quality 80 -> crf 31
        return ["-c:v", "libvpx-vp9", "-b:v", "0", "-crf", str(crf), "-row-mt", "1", "-deadline", "good", "-cpu-used", "4"]
    if fmt == "mov":
        profile = "4444" if options.transparent else "3"
        return ["-c:v", "prores_ks", "-profile:v", profile, "-vendor", "apl0"]
    raise AssertionError(fmt)  # pragma: no cover


def build_export_command(
    input_path: str | os.PathLike[str] | None,
    output_path: str | os.PathLike[str],
    options: ExportOptions,
    *,
    raw_input: RawVideoInput | None = None,
    ffmpeg: str | None = None,
    overwrite: bool = True,
) -> list[str]:
    """Build an ffmpeg command converting ``input_path`` (or raw stdin frames) into a clip."""
    if (input_path is None) == (raw_input is None):
        raise ValueError("Pass exactly one of input_path or raw_input")
    cmd = [ffmpeg or find_ffmpeg(), "-hide_banner", "-loglevel", "error"]
    if raw_input is None:
        cmd.append("-nostdin")
    cmd.append("-y" if overwrite else "-n")
    if raw_input is None:
        if options.start is not None:
            cmd += ["-ss", f"{options.start:.3f}"]
        if options.duration is not None:
            cmd += ["-t", f"{options.duration:.3f}"]
        cmd += ["-i", os.fspath(input_path)]  # type: ignore[arg-type]
    else:
        cmd += raw_input.args()

    cmd += ["-filter_complex", build_video_filter(options), "-map", "[v]"]
    wants_audio = options.audio and raw_input is None and options.format in _AUDIO_CODECS
    if wants_audio:
        cmd += ["-map", "0:a:0?"] + _AUDIO_CODECS[options.format]
    else:
        cmd += ["-an"]
    cmd += _codec_args(options)
    cmd.append(os.fspath(output_path))
    return cmd


def build_capture_command(raw_input: RawVideoInput, output_path: str | os.PathLike[str], *, ffmpeg: str | None = None) -> list[str]:
    """Lossless intermediate used while recording (FFV1 in Matroska, keeps alpha)."""
    return [
        ffmpeg or find_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
        *raw_input.args(),
        "-c:v", "ffv1", "-level", "3", "-g", "1", "-pix_fmt", "bgra",
        "-f", "matroska", os.fspath(output_path),
    ]
