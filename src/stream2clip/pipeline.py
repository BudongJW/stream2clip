"""Stream -> clips: export every highlight with layout, subtitles and a ready-to-paste description."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable, Sequence

from .compliance import AgencyProfile, Issue, build_description, check_upload
from .export import export, probe
from .ffmpeg import ExportOptions, extension_for, find_ffmpeg
from .highlights import Highlight
from .layouts import VerticalLayout
from .sources import SourceInfo
from .subtitles import Cue, SubtitleStyle, Transcriber, slice_cues, write_ass

__all__ = ["ClipResult", "default_clip_options", "make_clips"]


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
    video: str | os.PathLike[str],
    highlights: Sequence[Highlight],
    out_dir: str | os.PathLike[str],
    *,
    options: ExportOptions | None = None,
    cues: Sequence[Cue] | None = None,
    transcriber: Transcriber | None = None,
    language: str | None = None,
    karaoke: bool = True,
    subtitle_style: SubtitleStyle | None = None,
    source: SourceInfo | None = None,
    profile: AgencyProfile | None = None,
    registered: bool | None = None,
    uses_ai: bool | None = None,
    name: str = "clip_{rank:02d}",
    on_progress: Callable[[int, int, Highlight], None] | None = None,
) -> list[ClipResult]:
    """Export each highlight; write ``<name>.ass`` / ``<name>.txt`` next to it and a ``clips.json`` index."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    options = options or default_clip_options()
    play_res = _output_size(video, options)
    ai = uses_ai if uses_ai is not None else transcriber is not None
    results: list[ClipResult] = []
    for index, h in enumerate(highlights, start=1):
        if on_progress is not None:
            on_progress(index, len(highlights), h)
        stem = name.format(rank=h.rank, start=int(h.start), index=index)
        opts = replace(options, start=h.start, end=h.end)

        clip_cues: list[Cue] | None = slice_cues(cues, h.start, h.end) if cues is not None else None
        if clip_cues is None and transcriber is not None:
            with tempfile.TemporaryDirectory(prefix="stream2clip-asr-") as tmp:
                wav = _extract_audio(video, h.start, h.end, Path(tmp) / "clip.wav")
                clip_cues = transcriber.transcribe(wav, language=language)
        sub_path = None
        if clip_cues:
            sub_path = write_ass(clip_cues, out / f"{stem}.ass", play_res=play_res, style=subtitle_style, karaoke=karaoke)
            opts = replace(opts, subtitles=sub_path)

        clip_path = export(video, out / f"{stem}{extension_for(opts.format)}", opts)
        result = ClipResult(h, clip_path, sub_path)
        if source is not None:
            text = build_description(source, profile, start=h.start, end=h.end, summary=" / ".join(h.reasons[:2]), uses_ai=ai)
            result.description = out / f"{stem}.txt"
            result.description.write_text(text, encoding="utf-8")
            result.issues = check_upload(source, profile, description=text, registered=registered, uses_ai=ai)
        results.append(result)

    index_data = {
        "schema": "stream2clip.clips/v1",
        "video": os.fspath(video),
        "source": source.__dict__ if source is not None else None,
        "agency": profile.key if profile is not None else None,
        "clips": [r.to_dict() for r in results],
    }
    (out / "clips.json").write_text(json.dumps(index_data, ensure_ascii=False, indent=2), encoding="utf-8")
    return results
