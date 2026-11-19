"""Stream -> clips: export every highlight with layout, subtitles and a ready-to-paste description."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Sequence

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

__all__ = ["ClipResult", "default_clip_options", "find_highlights", "make_clips"]


@dataclass
class ClipResult:
    highlight: Highlight
    path: Path
    subtitles: Path | None = None
    description: Path | None = None
    issues: list[Issue] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            **self.highlight.to_dict(),
            "file": self.path.name,
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
) -> HighlightResult:
    """Load the chat archive / info JSON / loudness curve and detect highlights.

    This is the first half of ``stream2clip auto``; ``on_stage`` is told which step
    starts ("chat", "audio", "detect") so a UI can show what it is waiting for.
    ``speech`` is a subtitle file whose reaction lines are scored too (experimental).
    """
    from .audio import audio_levels, laughter_levels
    from .chat import load_chat
    from .sources import heatmap_from_info, load_info

    cfg = config or HighlightConfig()
    stage = on_stage or (lambda _name: None)
    messages = []
    if chat:
        stage("chat")
        messages = load_chat(chat, format=chat_format)
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
    if not messages and levels is None and not heatmap and said is None:
        raise ValueError("Nothing to analyse: give a chat archive, an info JSON with a heatmap, or a video with audio")
    stage("detect")
    return detect_highlights(
        messages, duration=duration, audio=levels, audio_window=cfg.window, heatmap=heatmap,
        laughter=bursts, laughter_window=cfg.window, speech=said, speech_window=cfg.window, config=cfg, source=source or {},
    )


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
) -> list[ClipResult]:
    """Export each highlight; write ``<name>.ass`` / ``<name>.txt`` next to it and a ``clips.json`` index.

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
        sub_path = None
        if clip_cues:
            sub_path = write_ass(clip_cues, out / f"{stem}.ass", play_res=play_res, style=subtitle_style, karaoke=karaoke)
            opts = replace(opts, subtitles=sub_path)

        clip_path = export(clip_video, out / f"{stem}{extension_for(opts.format)}", opts)
        result = ClipResult(h, clip_path, sub_path)
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
