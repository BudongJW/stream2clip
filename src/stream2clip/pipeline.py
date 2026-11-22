"""Stream -> clips: export every highlight with layout, subtitles and a ready-to-paste description."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Sequence

import numpy as np

from .chat import ChatMessage
from .compliance import AgencyProfile, Issue, build_description, check_upload
from .export import export, probe, resolve_encoder
from .ffmpeg import ExportOptions, extension_for, find_ffmpeg
from .highlights import Highlight, HighlightConfig, HighlightResult, detect_highlights
from .i18n import tr
from .layouts import VerticalLayout
from .sources import SourceInfo
from .subtitles import Cue, SubtitleStyle, Transcriber, slice_cues, write_ass

if TYPE_CHECKING:
    from .effects import EffectPlan
    from .soundtrack import PlannedSound, Sound, Soundtrack
    from .speakers import SpeakerMap
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
    #: Music and sound effects laid over the clip (``soundtrack``), with where they start and their gain.
    sounds: "list[PlannedSound]" = field(default_factory=list)
    #: Effects left out of the clip, with why (too close to another, after the end).
    skipped_sounds: list[str] = field(default_factory=list)
    #: A suggested title (the line at the peak and a bracket tag, see :mod:`stream2clip.titles`) and hashtags.
    title: str = ""
    hashtags: tuple[str, ...] = ()
    #: A 1280x720 thumbnail (``thumbnails=True``, see :mod:`stream2clip.thumbnails`).
    thumbnail: Path | None = None
    #: Seconds of the peak put in front of the clip (``teaser``); the file is that much longer.
    teaser: float = 0.0
    #: What to look at in the captions before uploading (:func:`stream2clip.subtitles.caption_issues`).
    captions: list[str] = field(default_factory=list)
    #: The effects placed (and those left out, with why): :meth:`stream2clip.effects.EffectPlan.to_dict`.
    effects: dict | None = None

    def to_dict(self) -> dict:
        data = {
            **self.highlight.to_dict(),
            "file": self.path.name,
            "title": self.title or None,
            "hashtags": list(self.hashtags),
            "thumbnail": self.thumbnail.name if self.thumbnail else None,
            "teaser": round(self.teaser, 2),
            "captions": list(self.captions),
            "effects": self.effects,
            "removed": round(self.removed, 2),
            "subtitles": self.subtitles.name if self.subtitles else None,
            "description": self.description.name if self.description else None,
            "issues": [{"level": i.level, "message": i.message} for i in self.issues],
        }
        if self.sounds:
            data["sounds"] = [s.to_dict() for s in self.sounds]
        if self.skipped_sounds:
            data["sounds_skipped"] = list(self.skipped_sounds)
        return data


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
    audio_track: int | None = None,
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
    estimated = None
    if video:
        duration = probe(video).duration
        if cfg.estimate_delay and messages:
            from .highlights import estimate_chat_delay

            stage("delay")
            estimated = estimate_chat_delay(messages, audio_levels(video, window=1.0, track=audio_track))
            if estimated is not None:
                cfg = replace(cfg, chat_delay=round(estimated[0], 1))
        if audio:
            stage("audio")
            levels = audio_levels(video, window=cfg.window, track=audio_track)
        if laughter:
            stage("laughter")
            bursts = laughter_levels(video, window=cfg.window, track=audio_track)
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
    result = detect_highlights(
        messages, duration=duration, audio=levels, audio_window=cfg.window, heatmap=heatmap,
        laughter=bursts, laughter_window=cfg.window, speech=said, speech_window=cfg.window, config=cfg, source=source or {},
        avatar=avatar, avatar_window=cfg.window,
    )
    result.estimated_delay = estimated
    return result


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
    encoder: str = "libx264",
    notes: bool = True,
) -> Compilation:
    """Join finished clips, in the order given, into one video; write ``<name>.txt`` with the chapter list.

    The picture takes the size and frame rate of the first clip unless told otherwise; clips of
    another shape get bars. Captions burned into the clips stay as they are. ``encoder`` is the
    MP4 encoder (``auto``: the GPU this PC has, see :func:`stream2clip.export.h264_encoder`).
    """
    from .export import h264_encoder, run_ffmpeg
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
        encoder=h264_encoder() if encoder == "auto" and fmt == "mp4" else encoder,
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
        names = {path.name for path in files}
        credits: list[str] = []
        for item in data.get("clips", []):
            for sound in item.get("sounds", []) if item.get("file") in names else []:
                if sound.get("credit") and sound["credit"] not in credits:
                    credits.append(sound["credit"])
        if credits:  # the music and effects of the clips are in the compilation too
            from .i18n import tr

            text = text.rstrip("\n") + "\n\n" + tr("BGM, 효과음") + "\n" + "\n".join(credits) + "\n"
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


def _extract_audio(video: str | os.PathLike[str], start: float, end: float, out: Path, track: int | None = None) -> Path:
    from .audio import track_map

    cmd = [find_ffmpeg(), "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-ss", f"{start:.3f}", "-t", f"{end - start:.3f}",
           "-i", os.fspath(video), *track_map(track), "-vn", "-ac", "1", "-ar", "16000", os.fspath(out)]
    subprocess.run(cmd, check=True, capture_output=True)
    return out


def _sound_parts(video: str | os.PathLike[str], start: float, length: float, *, min_silence: float, level: float, track: int | None = None) -> list[tuple[float, float]]:
    """What stays of one cut when its silences are shortened; empty when it has no sound to go by."""
    from .audio import decode_pcm, sound_parts

    if not probe(video).has_audio:
        return []
    rate = 16000
    samples = decode_pcm(video, sample_rate=rate, start=start, duration=length, track=track)
    return sound_parts(samples, rate, min_silence=min_silence, level=level)


class _Sounds:
    """What ``make_clips`` needs to lay a soundtrack over its clips: levels measured once, built-in effects drawn once."""

    def __init__(self, soundtrack: "Soundtrack", folder: Path) -> None:
        self.soundtrack = soundtrack
        self.folder = folder
        self._levels: dict[str, tuple[float, float]] = {}
        self._paths: dict[str, Path] = {}
        self._voice: dict[str, bool] = {}

    def path_of(self, sound: "Sound") -> Path:
        from .soundtrack import render_builtin

        if sound.builtin:
            if sound.name not in self._paths:
                self._paths[sound.name] = render_builtin(sound.name, self.folder)
            return self._paths[sound.name]
        if not sound.path.is_file():
            raise FileNotFoundError(f"Sound file not found: {sound.path}")
        return sound.path

    def levels(self, sound: "Sound") -> tuple[float, float]:
        from .soundtrack import RATE, active_level, measure, synth

        key = f"builtin:{sound.name}" if sound.builtin else os.fspath(sound.path)
        if key not in self._levels:
            if sound.builtin:
                samples = synth(sound.name)
                self._levels[key] = (active_level(samples, RATE), len(samples) / RATE)
            elif sound.kind == "bgm":
                self._levels[key] = measure(self.path_of(sound), start=self.soundtrack.music_start or None, duration=90.0)
            else:
                self._levels[key] = measure(self.path_of(sound), duration=None)
        return self._levels[key]

    def voice(self, video: str | os.PathLike[str], start: float, length: float) -> "tuple[float, np.ndarray] | None":
        """(active level, 16 kHz samples) of the clip's own (first) audio track; ``None`` when the video has no sound."""
        from .audio import decode_pcm
        from .soundtrack import active_level

        key = os.fspath(video)
        if key not in self._voice:
            self._voice[key] = probe(video).has_audio
        if not self._voice[key]:
            return None
        samples = decode_pcm(video, sample_rate=16000, start=start, duration=length, track=0)
        return active_level(samples, 16000), samples


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
    audio_track: int | None = None,
    soundtrack: "Soundtrack | None" = None,
    loudness: float | None = None,
    title_template: str | None = None,
    add_hashtags: bool = True,
    guests: Sequence[str] = (),
    links: Sequence[str] = (),
    contact_note: bool = False,
    thumbnails: bool = False,
    context: str | None = None,
    context_seconds: float = 3.0,
    teaser: float = 0.0,
    speakers: "SpeakerMap | None" = None,
    speaker_tracks: Sequence[int] = (),
    speaker_names: bool = False,
    effects: "str | dict | None" = None,
    reduced_motion: bool = False,
    hotkeys: Sequence[float] = (),
) -> list[ClipResult]:
    """Export each highlight; write ``<name>.ass`` / ``<name>.txt`` next to it and a ``clips.json`` index.

    ``credit`` is a short line burned into a corner of every clip for its whole length, such as
    the name of the original channel.

    ``soundtrack`` lays background music and sound effects over every clip (see
    :mod:`stream2clip.soundtrack`): the music sits under the clip's own sound and is lowered
    while someone speaks, an effect at the peak lands on the highlight's top moment (after
    ``trim_silence``, on where that moment went). The credits go into each description and
    the licenses into the guideline check.

    ``loudness`` brings each clip's finished sound to that many LUFS (YouTube turns louder
    videos down to about -14 and leaves quieter ones as they are), measured in a first pass.

    Every clip gets a suggested title in the language of its subtitles (:func:`stream2clip.titles.clip_title`;
    ``title_template`` changes its form, ``"game"`` adds the game; ``guests`` are named as ``(w.이름)``)
    and, with ``add_hashtags``, hashtags at the end of its description (three; five in Korean, with the
    platform and 키리누키). The description is written in the title's language and opens with the day of
    the stream; ``links`` (the streamer's channels) follow the channel line, ``contact_note`` asks
    viewers to report a problem for a streamer without clip guidelines. ``thumbnails`` writes ``<name>.jpg`` (1280x720): the sharpest frame around the
    peak, zoomed onto the layout's avatar box when there is one, with the first words of the title.

    ``context`` is a line at the top for the first ``context_seconds`` of each clip (what is going on;
    ``"auto"``: the stream's topic, from its title). ``teaser`` puts that many seconds of the peak
    (from just before the sound rises) in front of the clip, the way clip channels open with the
    best moment (MP4, WebM, MOV).

    Lines that say who speaks (whisperX transcripts, an RTTM file, see :mod:`stream2clip.speakers`) are
    outlined in that speaker's colour; ``speaker_tracks`` finds the speaker of each line from audio
    tracks with one microphone each (the loudest one). ``speakers`` names the labels and picks the
    colours, ``speaker_names`` puts the name in front of each line.

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
    options = resolve_encoder(options or default_clip_options())  # "auto": find the GPU encoder once for every clip
    if loudness is not None:
        from .ffmpeg import Loudness

        options = replace(options, loudness=Loudness(target=loudness))

    def footage(h: Highlight) -> tuple[str | os.PathLike[str], float]:
        if section is None:
            assert video is not None
            return video, 0.0
        path, offset = section(h)
        return path, float(offset)

    play_res = _output_size(video, options) if section is None else None
    fx = None
    if effects is not None:
        from .effects import load_preset

        fx = load_preset(effects) if isinstance(effects, str) else effects
    ai = uses_ai if uses_ai is not None else (transcriber is not None or subtitle_translator is not None)
    results: list[ClipResult] = []
    scratch = tempfile.TemporaryDirectory(prefix="stream2clip-sounds-") if soundtrack else None
    sounds = _Sounds(soundtrack, Path(scratch.name)) if soundtrack and scratch is not None else None
    try:
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
                    wav = _extract_audio(clip_video, max(0.0, h.start - offset), h.end - offset, Path(tmp) / "clip.wav", track=audio_track)
                    clip_cues = transcriber.transcribe(wav, language=language)
            if clip_cues and glossary is not None:
                clip_cues = glossary.fix_cues(clip_cues)  # names recognition misheard, in transcripts and downloaded subtitles
            if clip_cues and subtitle_translator is not None:
                from .translation import translate_cues

                clip_cues = translate_cues(clip_cues, subtitle_translator, target=translate_to, source=language, glossary=glossary, bilingual=bilingual)
            length, removed = h.end - h.start, 0.0
            if clip_cues and speaker_tracks:
                clip_cues = _speakers_by_track(clip_cues, clip_video, max(0.0, h.start - offset), h.end - h.start, speaker_tracks)
            if clip_cues and any(c.speaker for c in clip_cues):
                from .speakers import SpeakerMap

                speakers = speakers if speakers is not None else SpeakerMap()
                clip_cues = speakers.name(clip_cues)
            colors = speakers.colors() if speakers is not None else None
            spoken = list(clip_cues or [])  # on the cut's own clock, before any silence is taken out (for the teaser)
            keep: list[tuple[float, float]] = []
            if trim_silence and trim_silence > 0:
                keep = _sound_parts(clip_video, opts.start or 0.0, length, min_silence=trim_silence, level=silence_level, track=audio_track)
                left = sum(b - a for a, b in keep)
                if keep and length - left >= 0.3:  # a few frames are not worth another cut
                    removed, length = length - left, left
                    opts = replace(opts, keep=tuple(keep))
                    if clip_cues:
                        from .subtitles import retime_cues

                        clip_cues = retime_cues(clip_cues, keep)
                else:
                    keep = []
            sub_path = None
            situation = _context_text(context, source)
            fx_plan = None
            if fx is not None and fx.get("effects"):
                fx_plan = _plan_effects(fx, h, clip_video, opts, keep, spoken, clip_cues or [], length, play_res, hotkeys,
                                     reduced_motion=reduced_motion, audio_track=audio_track, language=language,
                                     translated=subtitle_translator is not None, translate_to=translate_to, source=source)
                opts = replace(opts, effects=fx_plan.filters)
            if clip_cues or credit or situation or (fx_plan is not None and fx_plan.tags):
                sub_path = write_ass(
                    clip_cues or [], out / f"{stem}.ass", play_res=play_res, style=subtitle_style, karaoke=karaoke,
                    credit=credit, credit_position=credit_position, duration=length, context=situation, context_seconds=context_seconds,
                    speaker_colors=colors, speaker_names=speaker_names,
                    emphasis=fx_plan.emphasis if fx_plan else (), emphasis_scale=fx_plan.emphasis_scale if fx_plan else 1.25, tags=fx_plan.tags if fx_plan else (),
                )
                opts = replace(opts, subtitles=sub_path)
            planned, skipped = [], []
            if sounds is not None:
                from .soundtrack import onset_near, plan_mix, sounding_spans
                from .subtitles import clip_time

                heard = sounds.voice(clip_video, opts.start or 0.0, h.end - h.start)
                peak = chat_peak = min(max(0.0, h.peak - h.start), h.end - h.start)
                if heard is not None and sounds.soundtrack.snap and any(e.when == "peak" for e in sounds.soundtrack.effects):
                    peak = onset_near(heard[1], 16000, peak)
                if heard is not None:  # where the talk is, from the sound itself, on the clip's (shortened) clock
                    talk = [(clip_time(a, keep), clip_time(b, keep)) if keep else (a, b) for a, b in sounding_spans(heard[1], 16000)]
                else:
                    talk = [(c.start, c.end) for c in clip_cues or []]
                plan = plan_mix(
                    sounds.soundtrack, index - 1, length=length, voice_level=heard[0] if heard is not None else None,
                    peak=clip_time(peak, keep) if keep else peak, peak_on_sound=peak != chat_peak, lines=[span for span in talk if span[1] > span[0]],
                    reactions=h.stats, levels=sounds.levels, path_of=sounds.path_of,
                )
                if plan is not None:
                    opts = replace(opts, mix=plan.mix)
                    planned, skipped = plan.sounds, plan.skipped

            clip_path = export(clip_video, out / f"{stem}{extension_for(opts.format)}", opts)
            opened = 0.0
            if teaser > 0 and opts.format in ("mp4", "webm", "mov"):
                opened = _open_with_teaser(clip_path, clip_video, h, offset, opts, spoken, teaser, out / f"{stem}.teaser.ass",
                                           play_res=play_res, style=subtitle_style, karaoke=karaoke, credit=credit, credit_position=credit_position,
                                           speaker_colors=colors, speaker_names=speaker_names)
            result = ClipResult(h, clip_path, sub_path, removed=removed, sounds=planned, skipped_sounds=skipped, teaser=opened)
            named = _title_for(h, clip_cues or [], keep, source, profile, language=language, translate_to=translate_to if subtitle_translator else None,
                               glossary=glossary if subtitle_translator else None, template=title_template, guests=guests)
            result.title, result.hashtags = named.title, (named.hashtags if add_hashtags else ())
            if thumbnails:
                result.thumbnail = _thumbnail(clip_video, h, offset, opts, named.hook, out / f"{stem}.jpg")
            if source is not None:
                used = [p.sound for p in planned]
                text = build_description(source, profile, start=h.start, end=h.end, summary=" / ".join(h.reasons[:2]), uses_ai=ai, credits=_credits(used),
                                         hashtags=result.hashtags, language=named.language, links=links, contact_note=contact_note)
                result.description = out / f"{stem}.txt"
                result.description.write_text(text, encoding="utf-8")
                result.issues = check_upload(source, profile, description=text, registered=registered, uses_ai=ai, sounds=used, length=length)
            from .thumbnails import sensational_words

            loud = sensational_words(result.title, named.hook)
            if loud:
                result.issues.insert(0, Issue("warning", tr("제목과 썸네일 문구에 과장된 표현({0})이 있습니다. 기획사 가이드라인은 과장되거나 오해를 부르는 제목과 썸네일을 금지합니다.").format(", ".join(loud))))
            from .compliance import originality_issues

            own = originality_issues(captions=bool(clip_cues), translated=subtitle_translator is not None and bool(clip_cues), context=bool(situation),
                                     teaser=opened > 0, profile=profile)
            from .subtitles import caption_issues

            result.captions = caption_issues(clip_cues or [], subtitle_style)  # per clip, apart from the guideline check
            result.effects = fx_plan.to_dict() if fx_plan is not None else None  # (plan is the soundtrack's, above)
            result.issues = [i for i in own if i.level != "info"] + result.issues + [i for i in own if i.level == "info"]
            results.append(result)
    finally:
        if scratch is not None:
            scratch.cleanup()

    index_data = {
        "schema": "stream2clip.clips/v1",
        "video": os.fspath(video) if video is not None else None,
        "source": source.__dict__ if source is not None else None,
        "agency": profile.key if profile is not None else None,
        "clips": [r.to_dict() for r in results],
    }
    (out / "clips.json").write_text(json.dumps(index_data, ensure_ascii=False, indent=2), encoding="utf-8")
    return results


def _title_for(h: Highlight, cues: "Sequence[Cue]", keep, source: SourceInfo | None, profile: AgencyProfile | None, *, language: str | None,
               translate_to: str | None, glossary: "Glossary | None", template: str | None, guests: Sequence[str] = ()):
    """The suggested title of one clip: the line at its peak (on the clip's own, possibly shortened, clock) and a tag."""
    from .sources import platform_of
    from .subtitles import clip_time
    from .titles import AGENCY_NAMES, clip_title, stream_topic, title_language

    peak = min(max(0.0, h.peak - h.start), h.end - h.start)
    stream_title = source.title if source is not None else ""
    channel = source.channel if source is not None else ""
    lang = title_language(translate_to=translate_to, language=language, cues=cues, fallback=stream_title)
    agency = profile.key if profile is not None and profile.key in AGENCY_NAMES else None
    game = (source.game if source is not None else "") or (stream_topic(stream_title, channel=channel) if template == "game" else "")
    return clip_title(cues=cues, peak=clip_time(peak, keep) if keep else peak, channel=channel, stream_title=stream_title, agency=agency, language=lang,
                      glossary=glossary, template=template, translated=translate_to is not None, guests=guests, game=game,
                      platform=platform_of(source.url) if source is not None and source.url else None)


def _speakers_by_track(cues: "Sequence[Cue]", video: str | os.PathLike[str], start: float, length: float, tracks: Sequence[int]) -> list[Cue]:
    """Each line's speaker: the audio track (one microphone each) loudest while it is said."""
    from .audio import decode_pcm
    from .speakers import assign_from_tracks

    rate = 8000
    heard = {number: decode_pcm(video, sample_rate=rate, start=start, duration=length, track=number) for number in tracks}
    return assign_from_tracks(cues, heard, rate)


def _context_text(context: str | None, source: SourceInfo | None) -> str:
    """The top line of a clip's first seconds: given, or with ``"auto"`` the stream's topic from its title."""
    if not context or not context.strip():
        return ""
    if context.strip().lower() != "auto":
        return " ".join(context.split())
    from .titles import context_line

    return context_line(source.title, channel=source.channel) if source is not None else ""


#: The teaser starts this long before the moment it shows, so the first word is not cut.
TEASER_LEAD = 0.4



def _plan_effects(fx: dict, h: Highlight, clip_video: Any, opts: ExportOptions, keep: Sequence[tuple[float, float]], spoken: Sequence[Cue],
                  cues: Sequence[Cue], length: float, frame: tuple[int, int], hotkeys: Sequence[float], *, reduced_motion: bool,
                  audio_track: int | None, language: str | None, translated: bool, translate_to: str | None, source: Any) -> "EffectPlan":
    """The effects of one clip: its sound onset and hotkey near the peak, its chat reaction, its loudest words."""
    from .effects import available_filters, default_focus, plan_effects
    from .soundtrack import onset_near
    from .subtitles import clip_time
    from .titles import title_language

    cut = h.end - h.start
    peak = min(max(0.0, h.peak - h.start), cut)
    samples = None
    if probe(clip_video).has_audio:
        from .audio import decode_pcm

        samples = decode_pcm(clip_video, sample_rate=16000, start=opts.start or 0.0, duration=cut, track=audio_track)
    onset = None
    if samples is not None:
        found = onset_near(samples, 16000, peak)
        onset = found if found != peak else None  # onset_near hands back the peak itself when nothing rises
    near = [t - h.start for t in hotkeys if abs((t - h.start) - peak) <= 1.0]
    hotkey = min(near, key=lambda t: abs(t - peak)) if near else None
    words = spoken if not translated and any(c.words for c in spoken) else None
    lang = title_language(translate_to=translate_to if translated else None, language=language, cues=cues,
                          fallback=getattr(source, "title", "") if source is not None else "")
    return plan_effects(
        fx, length=length, peak=peak, onset=onset, hotkey=hotkey, stats=h.stats, cues=cues,
        words_from=(words, samples, 16000) if words is not None else None,
        to_clip=(lambda t: clip_time(t, keep)) if keep else (lambda t: t),
        frame=frame, focus=default_focus(opts.layout), language=lang, filters=available_filters(), reduced_motion=reduced_motion,
    )

def _open_with_teaser(
    clip: Path, video: str | os.PathLike[str], h: Highlight, offset: float, opts: ExportOptions, cues: "Sequence[Cue]", seconds: float, ass: Path,
    *, play_res, style, karaoke: bool, credit: str | None, credit_position: str, speaker_colors=None, speaker_names: bool = False,
) -> float:
    """Put ``seconds`` of the peak (with the same layout, captions and credit) in front of ``clip``; returns how long the teaser is."""
    from .audio import decode_pcm
    from .export import run_ffmpeg
    from .ffmpeg import build_concat_command
    from .soundtrack import onset_near

    start, end = opts.start or 0.0, (opts.end if opts.end is not None else h.end - offset)
    peak = min(max(h.peak - offset, start), end)
    if probe(video).has_audio:  # chat says roughly when; the sound says when exactly
        samples = decode_pcm(video, sample_rate=16000, start=start, duration=end - start, track=0)
        peak = start + onset_near(samples, 16000, peak - start)
    first = max(start, peak - TEASER_LEAD)
    last = min(end, first + seconds + TEASER_LEAD)
    if last - first < 0.5:
        return 0.0
    rel = first - start
    teaser_cues = [replace(c, start=max(0.0, c.start - rel), end=c.end - rel, words=tuple(replace(w, start=max(0.0, w.start - rel), end=w.end - rel) for w in c.words))
                   for c in cues if c.end > rel and c.start < rel + (last - first)]
    subs = None
    if teaser_cues or credit:
        subs = write_ass(teaser_cues, ass, play_res=play_res, style=style, karaoke=karaoke, credit=credit, credit_position=credit_position, duration=last - first,
                         speaker_colors=speaker_colors, speaker_names=speaker_names)
    part = clip.with_name(clip.stem + ".teaser" + clip.suffix)
    teaser_opts = replace(opts, start=first, end=last, keep=None, mix=None, subtitles=subs, effects=())  # the peak's effects play once, in the clip
    export(video, part, teaser_opts)
    joined = clip.with_name(clip.stem + ".joined" + clip.suffix)
    facts = [probe(part), probe(clip)]
    try:
        run_ffmpeg(build_concat_command(
            [part, clip], joined, size=(facts[1].width, facts[1].height), durations=[float(f.duration or 0) for f in facts],
            has_audio=[f.has_audio for f in facts], fps=facts[1].fps or opts.fps or 30.0, quality=opts.quality, format=opts.format,
            encoder=opts.encoder,
        ))
        joined.replace(clip)
    finally:
        part.unlink(missing_ok=True)
        joined.unlink(missing_ok=True)
        if subs is not None:
            Path(subs).unlink(missing_ok=True)
    return round(float(facts[0].duration or 0.0), 2)


def _thumbnail(video: str | os.PathLike[str], h: Highlight, offset: float, opts: ExportOptions, hook: str, out: Path) -> Path | None:
    """The sharpest of seven frames from 1.5 s before to 1.5 s after the peak, with the first words of the hook."""
    from .export import grab_frames
    from .thumbnails import make_thumbnail, pick_frame, thumbnail_text

    first, last = opts.start or 0.0, (opts.end if opts.end is not None else h.end - offset)
    peak = min(max(h.peak - offset, first), last)
    times = sorted({round(min(max(peak + d, first), max(first, last - 0.1)), 3) for d in (-1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5)})
    frames = grab_frames(video, times)
    if not frames:
        return None
    face = opts.layout.avatar if opts.layout is not None and getattr(opts.layout, "avatar", None) is not None and not opts.layout.uses_avatar_video else None
    return make_thumbnail(pick_frame(frames), thumbnail_text(hook), out, face=face)


def _credits(sounds: "Sequence[Sound]") -> list[str]:
    if not sounds:
        return []
    from .soundtrack import credit_lines

    return credit_lines(sounds)
