"""Stream -> clips: export every highlight with layout, subtitles and a ready-to-paste description."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Sequence

import numpy as np

from .chat import ChatMessage
from .compliance import AgencyProfile, Issue, build_description, check_upload
from .export import export, probe
from .ffmpeg import ExportOptions, extension_for, find_ffmpeg
from .highlights import Highlight, HighlightConfig, HighlightResult, detect_highlights
from .layouts import VerticalLayout
from .sources import SourceInfo
from .subtitles import Cue, SubtitleStyle, Transcriber, slice_cues, write_ass

if TYPE_CHECKING:
    from .translate import Translator
    from .translation import Glossary

__all__ = ["ClipResult", "Compilation", "compile_clips", "compile_folder", "default_clip_options", "find_highlights", "make_clips"]


@dataclass
class ClipResult:
    highlight: Highlight
    path: Path
    subtitles: Path | None = None
    description: Path | None = None
    issues: list[Issue] = field(default_factory=list)
    #: Seconds of silence taken out of the clip (``trim_silence``); the file is that much shorter than the highlight.
    removed: float = 0.0

    def to_dict(self) -> dict:
        return {
            **self.highlight.to_dict(),
            "file": self.path.name,
            "removed": round(self.removed, 2),
            "subtitles": self.subtitles.name if self.subtitles else None,
            "description": self.description.name if self.description else None,
            "issues": [{"level": i.level, "message": i.message} for i in self.issues],
        }


def find_highlights(
    video: str | os.PathLike[str] | None = None,
    *,
    chat: str | os.PathLike[str] | None = None,
    chat_format: str | None = None,
    info: str | os.PathLike[str] | None = None,
    audio: bool = False,
    laughter: bool = False,
    speech: str | os.PathLike[str] | None = None,
    config: HighlightConfig | None = None,
    source: dict | None = None,
    on_stage: Callable[[str], None] | None = None,
    messages: Sequence[ChatMessage] | None = None,
    avatar: np.ndarray | None = None,
) -> HighlightResult:
    """Load the chat archive / info JSON / loudness curve and detect highlights.

    This is the first half of ``stream2clip auto``; ``on_stage`` is told which step
    starts ("chat", "audio", "detect") so a UI can show what it is waiting for.
    ``speech`` is a subtitle file whose reaction lines are scored too (experimental).
    ``messages`` are chat messages already loaded (a session file's, for one), used instead of ``chat``;
    ``avatar`` an avatar movement curve on the chat clock (experimental, ``session.avatar_motion``).
    """
    from .audio import audio_levels, laughter_levels
    from .chat import load_chat
    from .sources import heatmap_from_info, load_info

    cfg = config or HighlightConfig()
    stage = on_stage or (lambda _name: None)
    if chat:
        stage("chat")
        messages = load_chat(chat, format=chat_format)
    messages = list(messages or [])
    heatmap = heatmap_from_info(load_info(info)) if info else []
    duration = None
    levels = None
    bursts = None
    if video:
        duration = probe(video).duration
        if audio:
            stage("audio")
            levels = audio_levels(video, window=cfg.window)
        if laughter:
            stage("laughter")
            bursts = laughter_levels(video, window=cfg.window)
    said = None
    if speech:  # experimental: reaction words in the subtitles, for a stream without chat
        from .highlights import speech_levels
        from .subtitles import load_subtitles

        said = speech_levels(load_subtitles(speech), window=cfg.window, delay=cfg.chat_delay)
        if not said.any():
            said = None  # no reaction line in these subtitles: the signal has nothing to say
            if not messages and levels is None and not heatmap:
                raise ValueError(f"No reaction words (やばい, えっ, すごい, wow ...) were found in {os.fspath(speech)}: with nothing else to analyse, there is no highlight to find")
    if avatar is not None and not np.any(avatar):
        avatar = None
    if not messages and levels is None and not heatmap and said is None and avatar is None:
        raise ValueError("Nothing to analyse: give a chat archive, an info JSON with a heatmap, or a video with audio")
    stage("detect")
    return detect_highlights(
        messages, duration=duration, audio=levels, audio_window=cfg.window, heatmap=heatmap,
        laughter=bursts, laughter_window=cfg.window, speech=said, speech_window=cfg.window, config=cfg, source=source or {},
        avatar=avatar, avatar_window=cfg.window,
    )


@dataclass
class Compilation:
    """One video made of several clips."""

    path: Path
    #: (start in the compilation, label, clip file) per part, in playing order.
    parts: list[tuple[float, str, Path]]
    #: Chapter list (and, when the clips came with their source, the description) written next to the video.
    notes: Path | None = None

    @property
    def duration(self) -> float:
        return self.parts[-1][0] + probe(self.parts[-1][2]).duration if self.parts else 0.0

    def chapters(self) -> str:
        """``0:00 label`` per part: pasted into a description, YouTube turns these into chapters
        (it wants the first at 0:00, at least three, each ten seconds or longer)."""
        from .handoff import clock

        return "".join(f"{clock(start)} {label}".rstrip() + "\n" for start, label, _ in self.parts)


def compile_clips(
    clips: "Sequence[str | os.PathLike[str]]",
    out_path: str | os.PathLike[str],
    *,
    labels: Sequence[str] | None = None,
    size: tuple[int, int] | None = None,
    fps: float | None = None,
    fade: float = 0.0,
    quality: int = 85,
    notes: bool = True,
) -> Compilation:
    """Join finished clips, in the order given, into one video; write ``<name>.txt`` with the chapter list.

    The picture takes the size and frame rate of the first clip unless told otherwise; clips of
    another shape get bars. Captions burned into the clips stay as they are.
    """
    from .export import run_ffmpeg
    from .ffmpeg import _AUDIO_CODECS, build_concat_command

    files = [Path(clip) for clip in clips]
    if not files:
        raise ValueError("No clips to compile")
    missing = [str(path) for path in files if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Clip not found: {missing[0]}")
    if labels is not None and len(labels) != len(files):
        raise ValueError(f"{len(labels)} labels for {len(files)} clips")
    out = Path(out_path)
    fmt = out.suffix.lower().lstrip(".")
    if fmt not in _AUDIO_CODECS:
        raise ValueError(f"A compilation is saved as {', '.join('.' + name for name in sorted(_AUDIO_CODECS))}, not {out.suffix or out.name!r}")
    if out.resolve() in {path.resolve() for path in files}:
        raise ValueError(f"{out.name} is one of the clips: choose another name for the compilation")
    facts = [probe(path) for path in files]
    still = [path.name for path, info in zip(files, facts) if not info.duration]
    if still:
        raise ValueError(f"{still[0]} has no length: only videos can be compiled")
    out.parent.mkdir(parents=True, exist_ok=True)
    durations = [float(info.duration) for info in facts]
    run_ffmpeg(build_concat_command(
        files, out, size=size or (facts[0].width, facts[0].height), fps=fps or facts[0].fps or 30.0,
        durations=durations, has_audio=[info.has_audio for info in facts], fade=fade, quality=quality, format=fmt,
    ))
    starts = [sum(durations[:index]) for index in range(len(files))]
    names = [" ".join(str(label).split()) for label in labels] if labels is not None else [path.stem for path in files]
    result = Compilation(out, list(zip(starts, names, files)))
    if notes:
        result.notes = out.with_suffix(".txt")
        result.notes.write_text(result.chapters(), encoding="utf-8")
    return result


def compile_folder(
    folder: str | os.PathLike[str],
    out_path: str | os.PathLike[str] | None = None,
    *,
    order: str = "time",
    ranks: "set[int] | None" = None,
    **options,
) -> Compilation:
    """Compile the clips of one ``make_clips`` run (a folder with ``clips.json``, or that file).

    The parts are labelled with the reasons they were picked for. When the clips came with their
    source, the notes start with the description for that source and list each part's place in
    the original stream.
    """
    from .handoff import clock, ordered
    from .highlights import Highlight

    index = Path(folder)
    index = index / "clips.json" if index.is_dir() else index
    if not index.is_file():
        raise FileNotFoundError(f"No clips.json in {Path(folder)}: export clips first, or give the clip files themselves")
    data = json.loads(index.read_text(encoding="utf-8"))
    rows = {}
    for item in data.get("clips", []):
        h = Highlight(rank=int(item.get("rank", len(rows) + 1)), start=float(item["start"]), end=float(item["end"]), peak=float(item.get("peak", item["start"])),
                      score=float(item.get("score", 0)), reasons=list(item.get("reasons", [])))
        if (ranks is None or h.rank in ranks) and item.get("file"):
            rows[id(h)] = (h, index.parent / item["file"])
    chosen = ordered([h for h, _ in rows.values()], order)
    if not chosen:
        raise ValueError(f"{index} lists no clips to compile")
    files = [rows[id(h)][1] for h in chosen]
    labels = [h.reasons[0] if h.reasons else f"#{h.rank:02d}" for h in chosen]  # chapter titles: the main reason, to be reworded by hand
    wants_notes = options.pop("notes", True)
    result = compile_clips(files, out_path or index.parent / f"compilation{files[0].suffix}", labels=labels, notes=False, **options)
    if wants_notes:
        text = result.chapters()
        source = SourceInfo(**{key: value for key, value in (data.get("source") or {}).items() if key in SourceInfo.__dataclass_fields__}) if data.get("source") else None
        if source is not None and source.url:
            from .compliance import get_profile

            profile = get_profile(data["agency"]) if data.get("agency") else None
            where = "".join(f"{clock(start)} {source.timestamp_url(h.start)}\n" for (start, _, _), h in zip(result.parts, chosen))
            text = build_description(source, profile).rstrip("\n") + "\n\n" + text + "\n" + where
        result.notes = result.path.with_suffix(".txt")
        result.notes.write_text(text, encoding="utf-8")
    return result


def default_clip_options() -> ExportOptions:
    """Vertical 1080x1920 MP4 at 30 fps with the blurred-background layout."""
    return ExportOptions(format="mp4", fps=30, layout=VerticalLayout("blur"), quality=85)


def _output_size(video: str | os.PathLike[str], options: ExportOptions) -> tuple[int, int]:
    if options.layout is not None:
        return options.layout.size
    info = probe(video)
    w, h = (options.crop.width, options.crop.height) if options.crop else (info.width, info.height)
    if options.width and options.height:
        return options.width, options.height
    if options.width:
        return options.width, max(2, round(h * options.width / w))
    if options.height:
        return max(2, round(w * options.height / h)), options.height
    return w, h


def _extract_audio(video: str | os.PathLike[str], start: float, end: float, out: Path) -> Path:
    cmd = [find_ffmpeg(), "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-ss", f"{start:.3f}", "-t", f"{end - start:.3f}",
           "-i", os.fspath(video), "-vn", "-ac", "1", "-ar", "16000", os.fspath(out)]
    subprocess.run(cmd, check=True, capture_output=True)
    return out


def _sound_parts(video: str | os.PathLike[str], start: float, length: float, *, min_silence: float, level: float) -> list[tuple[float, float]]:
    """What stays of one cut when its silences are shortened; empty when it has no sound to go by."""
    from .audio import decode_pcm, sound_parts

    if not probe(video).has_audio:
        return []
    rate = 16000
    samples = decode_pcm(video, sample_rate=rate, start=start, duration=length)
    return sound_parts(samples, rate, min_silence=min_silence, level=level)


def make_clips(
    video: str | os.PathLike[str] | None,
    highlights: Sequence[Highlight],
    out_dir: str | os.PathLike[str],
    *,
    options: ExportOptions | None = None,
    cues: Sequence[Cue] | None = None,
    transcriber: Transcriber | None = None,
    subtitle_translator: "Translator | None" = None,
    translate_to: str = "ko",
    glossary: "Glossary | None" = None,
    bilingual: bool = False,
    language: str | None = None,
    karaoke: bool = True,
    subtitle_style: SubtitleStyle | None = None,
    source: SourceInfo | None = None,
    profile: AgencyProfile | None = None,
    registered: bool | None = None,
    uses_ai: bool | None = None,
    name: str = "clip_{rank:02d}",
    on_progress: Callable[[int, int, Highlight], None] | None = None,
    section: Callable[[Highlight], "tuple[str | os.PathLike[str], float]"] | None = None,
    credit: str | None = None,
    credit_position: str = "top-left",
    trim_silence: float | None = None,
    silence_level: float = 24.0,
) -> list[ClipResult]:
    """Export each highlight; write ``<name>.ass`` / ``<name>.txt`` next to it and a ``clips.json`` index.

    ``credit`` is a short line burned into a corner of every clip for its whole length, such as
    the name of the original channel.

    ``trim_silence`` shortens the pauses inside each clip: a stretch that stays ``silence_level``
    dB below the clip's loud parts for at least that many seconds is cut down to a short pause.
    Captions move with what is left.

    Normally every clip is cut from ``video``. With ``section`` each highlight has its own
    footage instead - ``section(h)`` returns ``(file, stream time at the file's start)`` - so
    only those parts of a stream need to be downloaded (``video`` may then be ``None``).
    Highlight times, subtitles and descriptions stay in stream time either way.
    """
    if video is None and section is None:
        raise ValueError("make_clips needs a video or a section function")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    options = options or default_clip_options()

    def footage(h: Highlight) -> tuple[str | os.PathLike[str], float]:
        if section is None:
            assert video is not None
            return video, 0.0
        path, offset = section(h)
        return path, float(offset)

    play_res = _output_size(video, options) if section is None else None
    ai = uses_ai if uses_ai is not None else (transcriber is not None or subtitle_translator is not None)
    results: list[ClipResult] = []
    for index, h in enumerate(highlights, start=1):
        if on_progress is not None:
            on_progress(index, len(highlights), h)
        stem = name.format(rank=h.rank, start=int(h.start), index=index)
        clip_video, offset = footage(h)
        if play_res is None:
            play_res = _output_size(clip_video, options)
        opts = replace(options, start=max(0.0, h.start - offset), end=h.end - offset)
        if offset and opts.layout is not None and opts.layout.uses_avatar_video:
            # The avatar video is on the stream's clock; this footage starts ``offset`` seconds into it.
            opts = replace(opts, layout=replace(opts.layout, avatar_offset=opts.layout.avatar_offset + offset))

        clip_cues: list[Cue] | None = slice_cues(cues, h.start, h.end) if cues is not None else None
        if clip_cues is None and transcriber is not None:
            with tempfile.TemporaryDirectory(prefix="stream2clip-asr-") as tmp:
                wav = _extract_audio(clip_video, max(0.0, h.start - offset), h.end - offset, Path(tmp) / "clip.wav")
                clip_cues = transcriber.transcribe(wav, language=language)
        if clip_cues and subtitle_translator is not None:
            from .translation import translate_cues

            clip_cues = translate_cues(clip_cues, subtitle_translator, target=translate_to, source=language, glossary=glossary, bilingual=bilingual)
        length, removed = h.end - h.start, 0.0
        if trim_silence and trim_silence > 0:
            keep = _sound_parts(clip_video, opts.start or 0.0, length, min_silence=trim_silence, level=silence_level)
            left = sum(b - a for a, b in keep)
            if keep and length - left >= 0.3:  # a few frames are not worth another cut
                removed, length = length - left, left
                opts = replace(opts, keep=tuple(keep))
                if clip_cues:
                    from .subtitles import retime_cues

                    clip_cues = retime_cues(clip_cues, keep)
        sub_path = None
        if clip_cues or credit:
            sub_path = write_ass(
                clip_cues or [], out / f"{stem}.ass", play_res=play_res, style=subtitle_style, karaoke=karaoke,
                credit=credit, credit_position=credit_position, duration=length,
            )
            opts = replace(opts, subtitles=sub_path)

        clip_path = export(clip_video, out / f"{stem}{extension_for(opts.format)}", opts)
        result = ClipResult(h, clip_path, sub_path, removed=removed)
        if source is not None:
            text = build_description(source, profile, start=h.start, end=h.end, summary=" / ".join(h.reasons[:2]), uses_ai=ai)
            result.description = out / f"{stem}.txt"
            result.description.write_text(text, encoding="utf-8")
            result.issues = check_upload(source, profile, description=text, registered=registered, uses_ai=ai)
        results.append(result)

    index_data = {
        "schema": "stream2clip.clips/v1",
        "video": os.fspath(video) if video is not None else None,
        "source": source.__dict__ if source is not None else None,
        "agency": profile.key if profile is not None else None,
        "clips": [r.to_dict() for r in results],
    }
    (out / "clips.json").write_text(json.dumps(index_data, ensure_ascii=False, indent=2), encoding="utf-8")
    return results
