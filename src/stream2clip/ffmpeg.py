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
from typing import TYPE_CHECKING, Sequence

from .chroma import DEFAULT_KEY_COLOR, colorkey_filter
from .geometry import Region

if TYPE_CHECKING:  # pragma: no cover
    from .layouts import VerticalLayout

__all__ = [
    "FORMATS",
    "ALPHA_FORMATS",
    "AudioLayer",
    "AudioMix",
    "ExportOptions",
    "Loudness",
    "audio_filters",
    "build_loudness_command",
    "parse_loudnorm",
    "RawVideoInput",
    "FFmpegNotFoundError",
    "find_ffmpeg",
    "find_ffprobe",
    "tools_dir",
    "build_video_filter",
    "build_export_command",
    "build_capture_command",
    "build_concat_command",
    "keep_filters",
    "mix_filters",
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


def tools_dir() -> Path:
    """Where a downloaded ffmpeg is kept: ``STREAM2CLIP_TOOLS_DIR`` or the user cache (see :mod:`stream2clip.tools`)."""
    base = os.environ.get("STREAM2CLIP_TOOLS_DIR")
    return Path(base) if base else Path.home() / ".cache" / "stream2clip" / "tools"


def _find_binary(name: str, env: str) -> str:
    candidate = os.environ.get(env)
    if candidate:
        return candidate
    bundled = app_dir()
    if bundled is not None:  # a copy shipped next to the program wins over whatever is on PATH
        for filename in (name + ".exe", name):
            if (bundled / filename).is_file():
                return str(bundled / filename)
    fetched = tools_dir()  # what "stream2clip setup --ffmpeg" (or the installer, or the app's button) downloaded
    for filename in (name + ".exe", name):
        if (fetched / filename).is_file():
            return str(fetched / filename)
    found = shutil.which(name)
    if found:
        return found
    if name == "ffmpeg":
        try:  # optional: pip install imageio-ffmpeg ships a static binary
            import imageio_ffmpeg  # type: ignore[import-not-found]

            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:  # pragma: no cover - optional dependency
            pass
    get = "run 'stream2clip setup --ffmpeg' (or use the download button of the app)" if sys.platform == "win32" else "install ffmpeg (https://ffmpeg.org/download.html) and add it to PATH"
    raise FFmpegNotFoundError(f"{name} not found: {get}, or set the {env} environment variable.")


def find_ffmpeg() -> str:
    return _find_binary("ffmpeg", "STREAM2CLIP_FFMPEG")


def find_ffprobe() -> str:
    return _find_binary("ffprobe", "STREAM2CLIP_FFPROBE")


def extension_for(fmt: str) -> str:
    return _EXTENSIONS[fmt]


@dataclass(frozen=True)
class AudioLayer:
    """One sound file played over a clip: background music or a sound effect.

    ``at`` is where it starts in the finished clip, ``offset`` where in the file it starts
    playing. ``loop`` repeats the file until the clip ends (music). ``gain`` is in dB.
    ``fade_in`` opens the layer, ``fade_out`` closes it at the end of the clip. ``duck``
    lowers the layer while the clip's own sound is louder than ``duck_threshold`` (linear
    amplitude, see ffmpeg ``sidechaincompress``).
    """

    path: "str | os.PathLike[str]"
    gain: float = 0.0
    at: float = 0.0
    offset: float = 0.0
    loop: bool = False
    fade_in: float = 0.0
    fade_out: float = 0.0
    duck: bool = False
    duck_threshold: float = 0.05
    duck_ratio: float = 8.0

    def __post_init__(self) -> None:
        if self.at < 0 or self.offset < 0 or self.fade_in < 0 or self.fade_out < 0:
            raise ValueError("at, offset and fades of a sound are seconds, not negative")
        if not 0.000977 <= self.duck_threshold <= 1.0:
            raise ValueError("duck_threshold is a linear level in 0.001..1")
        if not 1.0 <= self.duck_ratio <= 20.0:
            raise ValueError("duck_ratio must be in 1..20")


@dataclass(frozen=True)
class AudioMix:
    """Sounds laid over a clip's own sound (``voice``: the input has sound to keep).

    ``length`` is the length of the finished clip in seconds; every layer stops there.
    The mix goes through a limiter at ``limit`` dBFS so that added sounds never clip.
    """

    layers: tuple[AudioLayer, ...]
    length: float
    voice: bool = True
    voice_gain: float = 0.0
    limit: float = -1.0

    def __post_init__(self) -> None:
        if self.length <= 0:
            raise ValueError("A mix needs the clip's length")
        if not -24.0 <= self.limit <= 0.0:
            raise ValueError("limit is in dBFS, -24..0")


@dataclass(frozen=True)
class Loudness:
    """Bring a clip's sound to ``target`` LUFS with ffmpeg's ``loudnorm`` in two passes.

    The first pass only measures (:func:`build_loudness_command`, read by :func:`parse_loudnorm`);
    ``measured`` then holds (integrated, true peak, range, threshold, offset) and the export
    applies one fixed gain (``linear=true``) instead of riding the level. YouTube turns loud
    videos down to about -14 LUFS and leaves quiet ones as they are, so -14 is the default.
    """

    target: float = -14.0
    true_peak: float = -1.5
    lra: float = 11.0
    measured: "tuple[float, float, float, float, float] | None" = None

    def __post_init__(self) -> None:
        if not -40.0 <= self.target <= -5.0:
            raise ValueError("The loudness target is in LUFS, -40..-5")
        if not -9.0 <= self.true_peak <= 0.0:
            raise ValueError("The true peak limit is in dBTP, -9..0")

    def filter(self) -> str:
        if self.measured is None:
            return f"loudnorm=I={self.target:g}:TP={self.true_peak:g}:LRA={self.lra:g}:print_format=json"
        i, tp, lra, thresh, offset = self.measured
        span = min(20.0, max(self.lra, lra + 1.0))  # a target range narrower than the clip's own would make loudnorm ride the level
        return (f"loudnorm=I={self.target:g}:TP={self.true_peak:g}:LRA={span:g}:measured_I={i:.2f}:measured_TP={tp:.2f}"
                f":measured_LRA={lra:.2f}:measured_thresh={thresh:.2f}:offset={offset:.2f}:linear=true,aresample=48000")


def parse_loudnorm(stderr: str) -> "tuple[float, float, float, float, float] | None":
    """The values the first ``loudnorm`` pass printed, or ``None`` when there was nothing to measure (silence)."""
    import json

    end = stderr.rfind("}")
    start = stderr.rfind("{", 0, end)
    if start < 0 or end < 0:
        return None
    try:
        data = json.loads(stderr[start : end + 1])
        values = tuple(float(data[key]) for key in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset"))
    except (ValueError, KeyError):
        return None
    if any(v != v or v in (float("inf"), float("-inf")) for v in values) or values[0] < -70.0:
        return None
    return values  # type: ignore[return-value]


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
    #: Parts of the cut that stay, as (start, end) seconds from its beginning; the rest is dropped and
    #: what stays is closed up (see :func:`stream2clip.audio.sound_parts`). Subtitle times are those of the result.
    keep: "tuple[tuple[float, float], ...] | None" = None
    #: Background music and sound effects laid over the clip's sound (see :mod:`stream2clip.soundtrack`).
    mix: AudioMix | None = None
    #: Bring the finished sound to a loudness target (two passes; :func:`stream2clip.export.export` measures first).
    loudness: Loudness | None = None
    #: H.264 encoder for MP4: ``libx264`` (CPU), ``h264_nvenc``, ``h264_qsv``, ``h264_amf`` (GPU), or ``auto``.
    #: The builder is pure, so it writes ``auto`` as libx264; :func:`stream2clip.export.export` resolves
    #: ``auto`` to the first GPU encoder that works on this PC (:func:`stream2clip.export.h264_encoder`).
    encoder: str = "libx264"
    #: Effect filters on the finished clip's clock (a punch-in zoom, see :mod:`stream2clip.effects`): after the
    #: silence is cut and before the captions, so the captions stay sharp and in place.
    effects: tuple[str, ...] = ()

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
        if self.keep is not None:
            last = 0.0
            if not self.keep:
                raise ValueError("keep must name at least one part")
            for a, b in self.keep:
                if a < last or b <= a:
                    raise ValueError("keep must be (start, end) parts in order, without overlap")
                last = b
        if self.mix is not None and self.mix.layers and self.format not in _AUDIO_CODECS:
            raise ValueError(f"{self.format.upper()} has no sound: music and sound effects need one of {', '.join(sorted(_AUDIO_CODECS))}")
        if self.loudness is not None and self.format not in _AUDIO_CODECS:
            raise ValueError(f"{self.format.upper()} has no sound to bring to a loudness: use one of {', '.join(sorted(_AUDIO_CODECS))}")

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


#: The sound of a clip that loses parts is brought to this rate, so that its parts can be counted in samples.
_KEEP_RATE = 48000


def keep_filters(options: ExportOptions, *, audio_in: str = "[0:a:0]", audio_out: str = "[a]") -> tuple[list[str], str]:
    """What drops everything outside ``options.keep`` and closes the result up: (video filters, audio graph).

    Both are chosen by counting, not by timestamps: with a known frame rate the picture by frame
    number, the sound - brought to 48 kHz - by sample number (``atrim`` per part, then ``concat``).
    Each part is then a whole number of picture frames with exactly its sound, whatever timestamps
    the file or the ffmpeg at hand gives its frames, and the two stay together across many cuts.
    The audio graph reads ``audio_in`` and writes ``audio_out``.
    """
    if not options.keep:
        return [], ""
    fps = options.fps
    if fps:
        spans = [(int(round(a * fps)), int(round(b * fps))) for a, b in options.keep]
        spans = [(i, j) for i, j in spans if j > i]
        times = [(i / fps, j / fps) for i, j in spans]
        picture = "+".join(f"between(n,{i},{j - 1})" for i, j in spans)
        video = [f"select='{picture}'", f"setpts=N/({fps:g}*TB)"]
    else:
        times = list(options.keep)
        picture = "+".join(f"gte(t,{a:.4f})*lt(t,{b:.4f})" for a, b in times)
        video = [f"select='{picture}'", "setpts=N/FRAME_RATE/TB"]
    cuts = [(int(round(a * _KEEP_RATE)), int(round(b * _KEEP_RATE))) for a, b in times]
    cuts = [(i, j) for i, j in cuts if j > i]
    if len(cuts) == 1:
        i, j = cuts[0]
        return video, f"{audio_in}aresample={_KEEP_RATE},atrim=start_sample={i}:end_sample={j},asetpts=N/SR/TB{audio_out}"
    parts = [f"{audio_in}aresample={_KEEP_RATE},asplit={len(cuts)}" + "".join(f"[ka{k}]" for k in range(len(cuts)))]
    parts += [f"[ka{k}]atrim=start_sample={i}:end_sample={j},asetpts=N/SR/TB[kb{k}]" for k, (i, j) in enumerate(cuts)]
    parts.append("".join(f"[kb{k}]" for k in range(len(cuts))) + f"concat=n={len(cuts)}:v=0:a=1{audio_out}")
    return video, ";".join(parts)


_MIX_FORMAT = "aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo"


def _seconds(value: float) -> str:
    return f"{value:.3f}"


def mix_filters(mix: AudioMix, *, first_input: int, voice_in: str | None = "[0:a:0]", audio_out: str = "[a]") -> str:
    """The audio graph that lays ``mix.layers`` over the clip's own sound and writes ``audio_out``.

    ``voice_in`` is the clip's sound (a label, or ``None`` when ``mix.voice`` is false: silence
    of ``mix.length`` stands in for it). Layer ``k`` is read from input ``first_input + k``,
    opened by :func:`mix_input_args`. Every layer is brought to 48 kHz stereo, set to its gain,
    faded, moved to its place with ``adelay``, and cut at the end of the clip. Ducked layers are
    lowered by ``sidechaincompress`` keyed on the clip's sound. ``amix`` runs with
    ``normalize=0`` so that adding a layer does not lower the voice, and ``duration=first`` so
    that the clip's sound decides the length; ``alimiter`` (auto level off) keeps peaks under
    ``mix.limit``.
    """
    length = mix.length
    parts: list[str] = []
    playing = [(k, layer) for k, layer in enumerate(mix.layers) if length - layer.at > 0.01]  # a sound placed after the end is left out
    ducked = [k for k, layer in playing if layer.duck]
    if mix.voice and voice_in is not None:  # padded to the clip's length: duration=first then always gives the whole clip
        voice = f"{voice_in}{_MIX_FORMAT}" + (f",volume={mix.voice_gain:g}dB" if mix.voice_gain else "") + f",atrim=duration={_seconds(length)},apad=whole_dur={_seconds(length)}"
    else:
        voice = f"anullsrc=r=48000:cl=stereo,atrim=duration={_seconds(length)},aformat=sample_fmts=fltp:channel_layouts=stereo"
    if ducked and mix.voice and voice_in is not None:
        parts.append(f"{voice},asplit={len(ducked) + 1}[mv]" + "".join(f"[mk{k}]" for k in ducked))
    else:
        ducked = []  # nothing to duck under
        parts.append(f"{voice}[mv]")
    labels = ["[mv]"]
    for k, layer in playing:
        room = length - layer.at
        chain = [_MIX_FORMAT, f"atrim=duration={_seconds(room)}"]
        if layer.gain:
            chain.append(f"volume={layer.gain:g}dB")
        if layer.fade_in > 0:
            chain.append(f"afade=t=in:st=0:d={_seconds(min(layer.fade_in, room / 2))}")
        if layer.fade_out > 0:
            fade = min(layer.fade_out, room / 2)
            chain.append(f"afade=t=out:st={_seconds(room - fade)}:d={_seconds(fade)}")
        if layer.at > 0:
            chain.append(f"adelay=delays={int(round(layer.at * 1000))}:all=1")
        label = f"[ml{k}]"
        if k in ducked:
            parts.append(f"[{first_input + k}:a:0]{','.join(chain)}[mr{k}]")
            parts.append(
                f"[mr{k}][mk{k}]sidechaincompress=threshold={layer.duck_threshold:.4f}:ratio={layer.duck_ratio:g}:attack=50:release=600{label}"
            )
        else:
            parts.append(f"[{first_input + k}:a:0]{','.join(chain)}{label}")
        labels.append(label)
    limit = 10 ** (mix.limit / 20)
    tail = f"alimiter=limit={max(0.0625, limit):.4f}:level=0"
    if len(labels) == 1:
        parts.append(f"[mv]{tail}{audio_out}")
    else:
        parts.append("".join(labels) + f"amix=inputs={len(labels)}:duration=first:dropout_transition=0:normalize=0,{tail}{audio_out}")
    return ";".join(parts)


def mix_input_args(mix: AudioMix) -> list[str]:
    """``-i`` options for the layers of ``mix``, in order (music that loops is read with ``-stream_loop -1``)."""
    args: list[str] = []
    for layer in mix.layers:
        if layer.loop:
            args += ["-stream_loop", "-1"]
        if layer.offset > 0:
            args += ["-ss", _seconds(layer.offset)]
        args += ["-i", os.fspath(layer.path)]
    return args


def build_video_filter(options: ExportOptions) -> str:
    """Return a ``-filter_complex`` graph reading ``[0:v]`` and writing ``[v]``.

    A layout that takes the avatar from its own video also reads ``[1:v]``.
    """
    pre: list[str] = []
    if options.crop is not None:
        c = options.crop
        pre.append(f"crop={c.width}:{c.height}:{c.x}:{c.y}")
    if options.fps is not None:
        pre.append(f"fps={options.fps:g}")
    scale = _scale_filter(options)
    prefix, src = "", "[0:v]"
    if options.layout is not None:
        avatar_inp = "[1:v]" if options.layout.uses_avatar_video else None
        prefix = f"[0:v]{','.join(pre) or 'null'}[pre];{options.layout.graph('[pre]', '[lay]', avatar_inp=avatar_inp, fps=options.fps)};"
        src = "[lay]"
        chain: list[str] = [scale] if scale and (options.width or options.height) else []
    else:
        chain = pre + ([scale] if scale else [])
    chain.extend(keep_filters(options)[0])  # before the captions: their times are those of the shortened clip
    chain.extend(options.effects)
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


#: GPU H.264 encoders, in the order ``auto`` tries them (NVIDIA, Intel, AMD).
H264_ENCODERS = ("h264_nvenc", "h264_qsv", "h264_amf")
ENCODERS = ("libx264", *H264_ENCODERS, "auto")


def h264_args(encoder: str, crf: int) -> list[str]:
    """Video codec arguments for MP4 with ``encoder`` at about the quality of libx264's ``crf``."""
    if encoder == "h264_nvenc":
        return ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", str(crf), "-b:v", "0", "-movflags", "+faststart"]
    if encoder == "h264_qsv":
        return ["-c:v", "h264_qsv", "-preset", "medium", "-global_quality", str(crf), "-movflags", "+faststart"]
    if encoder == "h264_amf":
        return ["-c:v", "h264_amf", "-quality", "quality", "-rc", "cqp", "-qp_i", str(crf), "-qp_p", str(crf), "-movflags", "+faststart"]
    if encoder not in ("libx264", "auto"):
        raise ValueError(f"Unknown encoder {encoder!r}: use one of {', '.join(ENCODERS)}")
    return ["-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-movflags", "+faststart"]


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
        return h264_args(options.encoder, crf)
    if fmt == "webm":
        crf = round(63 - q * 0.4)  # quality 80 -> crf 31
        return ["-c:v", "libvpx-vp9", "-b:v", "0", "-crf", str(crf), "-row-mt", "1", "-deadline", "good", "-cpu-used", "4"]
    if fmt == "mov":
        profile = "4444" if options.transparent else "3"
        return ["-c:v", "prores_ks", "-profile:v", profile, "-vendor", "apl0"]
    raise AssertionError(fmt)  # pragma: no cover


def avatar_input_args(options: ExportOptions) -> list[str]:
    """The second input of a layout that takes the avatar from its own video, cut to the same span as the first."""
    layout = options.layout
    if layout is None or not layout.uses_avatar_video:
        return []
    start = (options.start or 0.0) + layout.avatar_offset
    if start < 0:
        raise ValueError(f"The avatar video starts {-start:.1f} s after this clip does: it does not cover the clip")
    args = ["-ss", f"{start:.3f}"]
    if options.duration is not None:
        args += ["-t", f"{options.duration:.3f}"]
    return args + avatar_decoder_args(layout) + ["-i", os.fspath(layout.avatar_source)]  # type: ignore[arg-type]


def avatar_decoder_args(layout: "VerticalLayout") -> list[str]:
    """ffmpeg's own VP9 decoder drops the alpha plane of a WebM: when the file's transparency is to be used, libvpx reads it."""
    if layout.avatar_key is None and os.fspath(layout.avatar_source).lower().endswith(".webm"):  # type: ignore[arg-type]
        return ["-c:v", "libvpx-vp9"]
    return []


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
        cmd += avatar_input_args(options)
    else:
        if options.layout is not None and options.layout.uses_avatar_video:
            raise ValueError("A layout with an avatar video needs a video file as its main input")
        cmd += raw_input.args()

    wants_audio = options.audio and raw_input is None and options.format in _AUDIO_CODECS
    graph = build_video_filter(options)
    mix = _mix_of(options)
    if mix is not None:
        if not wants_audio:
            raise ValueError("Music and sound effects need a video file with sound kept (audio=True)")
        cmd += mix_input_args(mix)
    audio = audio_filters(options) if wants_audio else None
    if audio:
        cmd += ["-filter_complex", f"{graph};{audio}", "-map", "[v]", "-map", "[a]"] + _AUDIO_CODECS[options.format]
    elif wants_audio:
        cmd += ["-filter_complex", graph, "-map", "[v]", "-map", "0:a:0?"] + _AUDIO_CODECS[options.format]
    else:
        cmd += ["-filter_complex", graph, "-map", "[v]", "-an"]
    cmd += _codec_args(options)
    cmd.append(os.fspath(output_path))
    return cmd


def _mix_of(options: ExportOptions) -> AudioMix | None:
    return options.mix if options.mix is not None and options.mix.layers else None


def audio_filters(options: ExportOptions, *, audio_out: str = "[a]") -> str | None:
    """The audio graph of an export (``None``: the input's first audio track is copied through as it is).

    In order: silences cut (``keep``), music and effects laid over what is left (``mix``, read
    from the inputs after the video and the avatar video), loudness brought to its target.
    """
    mix = _mix_of(options)
    loud = options.loudness
    head = audio_out if loud is None else "[pre]"
    if mix is not None:
        first = 1 + (1 if options.layout is not None and options.layout.uses_avatar_video else 0)
        if mix.voice and options.keep:  # the clip's sound loses its silences first, then the music goes under what is left
            graph = keep_filters(options, audio_out="[kv]")[1] + ";" + mix_filters(mix, first_input=first, voice_in="[kv]", audio_out=head)
        else:
            graph = mix_filters(mix, first_input=first, voice_in="[0:a:0]" if mix.voice else None, audio_out=head)
    elif options.keep:  # the sound loses the same parts as the picture (the input must have sound)
        graph = keep_filters(options, audio_out=head)[1]
    elif loud is not None:
        return f"[0:a:0]{loud.filter()}{audio_out}"
    else:
        return None
    return graph if loud is None else f"{graph};[pre]{loud.filter()}{audio_out}"


def build_loudness_command(input_path: str | os.PathLike[str], options: ExportOptions, *, ffmpeg: str | None = None) -> list[str]:
    """First loudness pass: run the export's audio graph through ``loudnorm`` that only measures (no file is written).

    Its log ends with the JSON that :func:`parse_loudnorm` reads.
    """
    if options.loudness is None:
        raise ValueError("No loudness target to measure for")
    measuring = replace(options, loudness=replace(options.loudness, measured=None))
    cmd = [ffmpeg or find_ffmpeg(), "-hide_banner", "-nostats", "-loglevel", "info", "-nostdin"]
    if options.start is not None:
        cmd += ["-ss", f"{options.start:.3f}"]
    if options.duration is not None:
        cmd += ["-t", f"{options.duration:.3f}"]
    cmd += ["-i", os.fspath(input_path), *avatar_input_args(options)]
    mix = _mix_of(options)
    if mix is not None:
        cmd += mix_input_args(mix)
    cmd += ["-filter_complex", audio_filters(measuring) or "", "-map", "[a]", "-vn", "-f", "null", "-"]
    return cmd


def build_concat_command(
    inputs: "Sequence[str | os.PathLike[str]]",
    output_path: str | os.PathLike[str],
    *,
    size: tuple[int, int],
    durations: "Sequence[float]",
    has_audio: "Sequence[bool]",
    fps: float = 30.0,
    fade: float = 0.0,
    quality: int = 85,
    format: str = "mp4",
    encoder: str = "libx264",
    ffmpeg: str | None = None,
    overwrite: bool = True,
) -> list[str]:
    """Join clips into one video: each is fitted into ``size`` (bars where the shape differs), brought to ``fps``
    and encoded once. A clip without sound gets silence, so sound and picture stay together.

    ``fade`` seconds of fade to black end each clip and open the next (0: hard cuts). ``durations`` and
    ``has_audio`` describe the inputs, one entry each (see :func:`stream2clip.export.probe`).
    """
    if not inputs:
        raise ValueError("Nothing to join")
    if not len(inputs) == len(durations) == len(has_audio):
        raise ValueError("inputs, durations and has_audio must have one entry per clip")
    if format not in _AUDIO_CODECS:
        raise ValueError(f"A compilation is a video with sound: use one of {', '.join(sorted(_AUDIO_CODECS))}, not {format}")
    width, height = (int(side) - int(side) % 2 for side in size)
    cmd = [ffmpeg or find_ffmpeg(), "-hide_banner", "-loglevel", "error", "-nostdin", "-y" if overwrite else "-n"]
    for path in inputs:
        cmd += ["-i", os.fspath(path)]
    parts, last = [], len(inputs) - 1
    for index, (length, sound) in enumerate(zip(durations, has_audio)):
        ramp = min(fade, length / 3) if fade > 0 else 0.0
        video = [f"scale={width}:{height}:force_original_aspect_ratio=decrease", f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2", "setsar=1", f"fps={fps:g}", "format=yuv420p"]
        audio = ["aresample=48000", "aformat=sample_fmts=fltp:channel_layouts=stereo"]
        if ramp and index > 0:
            video.append(f"fade=t=in:st=0:d={ramp:.3f}")
            audio.append(f"afade=t=in:st=0:d={ramp:.3f}")
        if ramp and index < last:
            video.append(f"fade=t=out:st={max(0.0, length - ramp):.3f}:d={ramp:.3f}")
            audio.append(f"afade=t=out:st={max(0.0, length - ramp):.3f}:d={ramp:.3f}")
        parts.append(f"[{index}:v:0]{','.join(video)}[v{index}]")
        if sound:
            parts.append(f"[{index}:a:0]{','.join(audio)}[a{index}]")
        else:
            parts.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={length:.3f}[a{index}]")
    parts.append("".join(f"[v{index}][a{index}]" for index in range(len(inputs))) + f"concat=n={len(inputs)}:v=1:a=1[v][a]")
    cmd += ["-filter_complex", ";".join(parts), "-map", "[v]", "-map", "[a]"]
    cmd += _AUDIO_CODECS[format] + _codec_args(ExportOptions(format=format, quality=quality, encoder=encoder))
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
