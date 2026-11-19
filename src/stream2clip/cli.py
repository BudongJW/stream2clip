"""``stream2clip`` command line interface."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
import time
from pathlib import Path

from . import __version__
from .ffmpeg import FORMATS, ExportOptions, build_export_command
from .geometry import Region

_EXT_TO_FORMAT = {".gif": "gif", ".webp": "webp", ".mp4": "mp4", ".webm": "webm", ".mov": "mov", ".png": "apng", ".apng": "apng"}


def parse_time(text: str) -> float:
    """Parse ``SS``, ``MM:SS`` or ``HH:MM:SS`` (fractions allowed)."""
    parts = text.strip().split(":")
    if not 1 <= len(parts) <= 3:
        raise argparse.ArgumentTypeError(f"invalid time {text!r}")
    try:
        seconds = 0.0
        for part in parts:
            seconds = seconds * 60 + float(part)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid time {text!r}") from exc
    return seconds


def _region(text: str) -> Region:
    try:
        return Region.parse(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _avatar(text: str) -> "Region | str":
    return "auto" if text.strip().lower() == "auto" else _region(text)


def _format_for(path: Path, explicit: str | None) -> str:
    if explicit:
        return explicit
    fmt = _EXT_TO_FORMAT.get(path.suffix.lower())
    if fmt is None:
        raise SystemExit(f"Cannot infer format from {path.name!r}; pass --format ({', '.join(FORMATS)})")
    return fmt


def _add_export_args(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group("output")
    g.add_argument("-f", "--format", choices=FORMATS, help="output format (default: from file extension)")
    g.add_argument("--fps", type=float, help="output frame rate")
    g.add_argument("--width", type=int, help="scale to this width (keeps aspect ratio)")
    g.add_argument("--height", type=int, help="scale to this height (keeps aspect ratio)")
    g.add_argument("--quality", type=int, default=80, help="1-100 (WebP quality / video CRF mapping)")
    g.add_argument("--colors", type=int, default=256, help="GIF palette size (2-256)")
    g.add_argument("--dither", default="sierra2_4a", help="GIF dithering (sierra2_4a, bayer, floyd_steinberg, none, ...)")
    g.add_argument("--loop", type=int, default=0, help="loop count for GIF/WebP/APNG (0 = forever)")
    t = p.add_argument_group("transparent background (GIF/WebP/WebM/MOV/APNG)")
    t.add_argument("--transparent", action="store_true", help="remove --key-color from every frame")
    t.add_argument("--key-color", default="#00FF00", help="color to remove (default: #00FF00 green screen; 'none' keeps the source alpha)")
    t.add_argument("--similarity", type=float, default=0.12, help="0-1 distance treated as the key color")
    t.add_argument("--blend", type=float, default=0.0, help="0-1 soft edge width (use 0 for GIF)")


def _export_options(args: argparse.Namespace, output: Path, *, default_fps: float | None = None, **extra) -> ExportOptions:
    return ExportOptions(
        format=_format_for(output, args.format),
        fps=args.fps if args.fps is not None else default_fps,
        width=args.width,
        height=args.height,
        quality=args.quality,
        max_colors=args.colors,
        dither=args.dither,
        loop=args.loop,
        transparent=args.transparent,
        key_color=None if args.key_color.lower() == "none" else args.key_color,
        similarity=args.similarity,
        blend=args.blend,
        **extra,
    )


# ----------------------------------------------------------------------------- commands


def cmd_monitors(args: argparse.Namespace) -> int:
    from .capture import default_backend

    backend = default_backend()
    try:
        print(f"virtual screen: {backend.virtual_screen()}")
        for i, mon in enumerate(backend.monitors()):
            print(f"monitor {i}: {mon}  ({mon.width}x{mon.height})")
    finally:
        backend.close()
    return 0


def cmd_capture(args: argparse.Namespace) -> int:
    from .capture import grab_image
    from .editor import Document, state_from_dict

    if args.delay:
        time.sleep(args.delay)
    image = grab_image(args.region, monitor=args.monitor)
    doc = Document(image)
    if args.annotations:
        doc.commit(state_from_dict(Path(args.annotations).read_text(encoding="utf-8")))
    out = doc.save(args.output)
    print(f"saved {out} ({doc.output_size[0]}x{doc.output_size[1]})")
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    from .capture import default_backend, system_cursor_position
    from .record import Recorder, keep_intermediate

    output = Path(args.output)
    options = _export_options(args, output, default_fps=args.capture_fps)
    region = args.region
    if region is None:
        backend = default_backend()
        try:
            region = backend.monitors()[args.monitor or 0] if backend.monitors() else backend.virtual_screen()
        finally:
            backend.close()
    recorder = Recorder(region, fps=args.capture_fps, cursor=None if args.no_cursor else system_cursor_position, max_duration=args.duration)
    recorder.start()
    print(f"recording {region} at {args.capture_fps:g} fps", end="")
    try:
        if args.duration:
            print(f" for {args.duration:g}s ... (Ctrl+C to stop early)", flush=True)
            recorder.wait()
        else:
            print(" ... press Enter (or Ctrl+C) to stop", flush=True)
            input()
    except KeyboardInterrupt:
        pass
    recording = recorder.stop()
    print(f"captured {recording.frames} frames ({recording.duration:.1f}s), encoding {options.format} ...", flush=True)
    try:
        out = recording.export(output, options)
        print(f"saved {out}")
    finally:
        if args.keep_raw:
            keep_intermediate(recording, args.keep_raw)
        else:
            recording.discard()
    return 0


def cmd_convert(args: argparse.Namespace) -> int:
    from .export import export

    output = Path(args.output)
    options = _export_options(
        args, output, start=args.start, end=args.end, crop=args.crop, audio=not args.no_audio, default_fps=None
    )
    if args.print_command:
        print(shlex.join(build_export_command(args.input, output, options)))
        return 0
    out = export(args.input, output, options)
    print(f"saved {out}")
    return 0


def cmd_annotate(args: argparse.Namespace) -> int:
    from .editor import Document

    doc = Document.open(args.image, annotations=args.annotations)
    if args.overlay:
        out = Path(args.output)
        doc.render_overlay().save(out)
    else:
        out = doc.save(args.output)
    print(f"saved {out}")
    return 0


def cmd_gui(args: argparse.Namespace) -> int:
    try:
        from .gui.app import main as gui_main
    except ImportError as exc:  # pragma: no cover - depends on extras
        raise SystemExit(f'GUI needs PySide6: pip install "stream2clip[gui]" ({exc})') from exc
    return gui_main(args.files)


# ----------------------------------------------------------------------------- stream -> clips


def _size(text: str) -> tuple[int, int]:
    try:
        w, h = (int(v) for v in text.lower().split("x"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid size {text!r}; expected WxH") from exc
    return w, h


def _source(args: argparse.Namespace):
    from .sources import SourceInfo, load_info, source_from_info

    info_path = getattr(args, "info", None)
    if info_path:
        src = source_from_info(load_info(info_path))
    else:
        src = SourceInfo()
    overrides = {k: v for k, v in (("url", getattr(args, "source_url", None)), ("title", getattr(args, "source_title", None)), ("channel", getattr(args, "channel", None))) if v}
    if overrides:
        from dataclasses import replace as _replace

        src = _replace(src, **overrides)
    return src if (src.url or src.title) else None


def cmd_fetch(args: argparse.Namespace) -> int:
    from .sources import download_chat, download_replay_chat, download_section, download_subs, fetch_info, platform_of, ytdlp_command

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    korean = platform_of(args.url)  # CHZZK / SOOP: chat comes from their own replay API, not yt-dlp
    ytdlp = ytdlp_command(cookies=args.cookies, cookies_from_browser=args.cookies_from_browser)
    try:
        info = fetch_info(args.url, ytdlp=ytdlp, comments=args.comments) if args.comments else fetch_info(args.url, ytdlp=ytdlp)
        (out / "info.json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
        print(f"info   {out / 'info.json'}  ({info.get('title', '')})" + (f"  + {len(info.get('comments') or [])} comments" if args.comments else ""))
    except RuntimeError as exc:
        if not korean:
            raise
        print(f"info   (skipped) {exc}", file=sys.stderr)
    if not args.no_chat:
        try:
            if korean:
                print(f"chat   {download_replay_chat(args.url, out)}")
            else:
                print(f"chat   {download_chat(args.url, out, ytdlp=ytdlp)}")
        except (RuntimeError, ValueError, OSError) as exc:
            print(f"chat   (skipped) {exc}", file=sys.stderr)
    if args.subs:
        try:
            for path in download_subs(args.url, out, args.subs, ytdlp=ytdlp):
                print(f"subs   {path}")
        except RuntimeError as exc:
            print(f"subs   (skipped) {exc}", file=sys.stderr)
    if args.video or args.start is not None or args.end is not None:
        video = download_section(args.url, out / "video.mp4", args.start, args.end, max_height=args.max_height, ytdlp=ytdlp)
        print(f"video  {video}")
    return 0


def _add_highlight_args(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group("highlight detection")
    g.add_argument("--chat", help="chat archive: yt-dlp live_chat.json, chat-downloader JSON, TwitchDownloader JSON, CHZZK / SOOP replay chat, CSV/JSONL")
    g.add_argument("--chat-format", choices=["youtube", "chat-downloader", "twitch", "chzzk", "soop", "csv", "jsonl", "json"], help="force the chat format")
    g.add_argument("--info", help="yt-dlp info JSON (most-replayed heatmap, title/URL for descriptions)")
    g.add_argument("--audio", action="store_true", help="also use the video's loudness")
    g.add_argument("--laughter", action="store_true", help="experimental: also score laughter-like bursts in the audio")
    g.add_argument("--speech", metavar="SUBTITLES", help="experimental: also score reaction words in this subtitle file (what the streamer says); a way to find moments in a stream without chat")
    g.add_argument("--mark-singing", action="store_true", help="find the songs in the video and say which highlights overlap one")
    g.add_argument("--skip-singing", action="store_true", help="like --mark-singing, and leave out highlights that are mostly a song")
    g.add_argument("--top", type=int, default=10, help="maximum number of highlights (default 10)")
    g.add_argument("--threshold", type=float, default=2.0, help="robust z-score needed for a peak (default 2.0)")
    g.add_argument("--window", type=float, default=5.0, help="analysis bucket in seconds (default 5)")
    g.add_argument("--delay", type=float, default=8.0, help="seconds chat lags behind the moment (default 8)")
    g.add_argument("--lead", type=float, default=20.0, help="context before the moment (default 20 s)")
    g.add_argument("--tail", type=float, default=10.0, help="context after the moment (default 10 s)")
    g.add_argument("--min-length", type=float, default=15.0)
    g.add_argument("--max-length", type=float, default=90.0)
    g.add_argument("--keep-greetings", action="store_true", help="count greetings / goodbyes too (they flood the chat when a stream starts and ends)")
    _add_marker_args(g)
    g.add_argument("--plot", help="also draw the timeline as PNG")


def _add_marker_args(g) -> None:
    g.add_argument("--marker", action="append", metavar="WORD", help="chat command of the streamer or a moderator that always makes a clip; repeat for more (default: !clip !클립 !切り抜き !ts !mark)")
    g.add_argument("--marker-anyone", action="store_true", help="take the marker from every chatter, not only the streamer and moderators")
    g.add_argument("--no-markers", action="store_true", help="ignore marker commands")


def _markers(args: argparse.Namespace) -> dict:
    """``markers`` / ``marker_roles`` for HighlightConfig and LiveConfig."""
    from .highlights import DEFAULT_MARKERS

    words = () if args.no_markers else tuple(args.marker or DEFAULT_MARKERS)
    return {"markers": words, "marker_roles": ("any",) if args.marker_anyone else ("owner", "moderator")}


def _detect(args: argparse.Namespace, video: str | None):
    from .highlights import HighlightConfig, render_timeline
    from .pipeline import find_highlights

    if not args.chat and not args.info and not (video and args.audio) and not args.speech:
        raise ValueError("Give --chat, --info (heatmap), --audio with a video, or --speech with subtitles")
    cfg = HighlightConfig(window=args.window, threshold=args.threshold, chat_delay=args.delay, lead=args.lead, tail=args.tail,
                          min_length=args.min_length, max_length=args.max_length, top=args.top, skip_greetings=not args.keep_greetings, **_markers(args))
    src = _source(args)
    result = find_highlights(video, chat=args.chat, chat_format=args.chat_format, info=args.info, audio=args.audio, laughter=bool(video and args.laughter), speech=args.speech, config=cfg,
                             source={"url": src.url, "title": src.title} if src else {})
    if video and (args.mark_singing or args.skip_singing):
        from .audio import singing_sections
        from .highlights import mark_singing

        songs = singing_sections(video)
        print(f"singing  {len(songs)} sections" + (": " + ", ".join(f"{_clock(s.start)}-{_clock(s.end)}" for s in songs) if songs else ""))
        mark_singing(result, [(s.start, s.end) for s in songs], drop=args.skip_singing)
    print(f"analysed {result.messages} chat messages over {result.duration / 60:.1f} min -> {len(result.highlights)} highlights")
    for h in result.highlights:
        print(f"  #{h.rank:02d}  {_clock(h.start)} - {_clock(h.end)}  score {h.score:5.1f}  {' / '.join(h.reasons)}")
    if args.plot:
        render_timeline(result, args.plot)
        print(f"timeline {args.plot}")
    return result


def _run_ytdlp(args: list[str]) -> int:
    try:
        import yt_dlp
    except ImportError:
        print('stream2clip: error: yt-dlp is not installed: pip install "stream2clip[ingest]"', file=sys.stderr)
        return 1
    try:
        yt_dlp.main(args)
    except SystemExit as exc:  # yt-dlp always exits; hand its status back
        return exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    return 0


def _clock(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 3600:d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def cmd_highlights(args: argparse.Namespace) -> int:
    result = _detect(args, args.video)
    if args.output:
        result.save(args.output)
        print(f"saved {args.output}")
    return 0


def _add_clip_args(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group("clip output")
    g.add_argument("--layout", default="blur", choices=["blur", "center", "fit", "stack", "pip", "none"], help="9:16 layout (default blur): stack = avatar above the game, pip = avatar in a corner of the game; 'none' keeps the original framing")
    g.add_argument("--avatar", type=_avatar, help="stack / pip layout: avatar box x,y,w,h in source pixels, or 'auto' to find it with anime face detection")
    g.add_argument("--avatar-video", metavar="FILE", help="stack / pip layout: take the avatar from its own recording (green screen or alpha) instead of a box in the stream")
    g.add_argument("--avatar-key", default="auto", metavar="COLOR", help="colour removed from --avatar-video: 'auto' (default) uses the file's own transparency when it has one and removes #00FF00 otherwise; 'none' always uses the file's transparency")
    g.add_argument("--avatar-offset", type=float, default=0.0, metavar="SECONDS", help="--avatar-video: seconds its recording started before the stream's (negative: after)")
    g.add_argument("--corner", default="top-right", choices=["top-left", "top-right", "bottom-left", "bottom-right"], help="pip layout: where the avatar goes (default top-right)")
    g.add_argument("--inset", type=float, default=0.42, help="pip layout: avatar width as a fraction of the frame (default 0.42)")
    g.add_argument("--face-model", help="--avatar auto: ONNX face model file (default: downloaded once, 12 MB)")
    g.add_argument("--avatar-samples", type=int, default=12, help="--avatar auto: frames to look at (default 12)")
    g.add_argument("--max-height", type=int, default=1080, help="when the video is an address: the largest picture height to download (default 1080)")
    g.add_argument("--cookies", help="when the video is an address: Netscape cookies.txt for yt-dlp")
    g.add_argument("--cookies-from-browser", metavar="BROWSER", help="when the video is an address: let yt-dlp read cookies from chrome / firefox / edge ...")
    g.add_argument("--game", type=_region, help="stack layout: game box x,y,w,h (default: whole frame)")
    g.add_argument("--split", type=float, default=0.42, help="stack layout: avatar panel height fraction")
    g.add_argument("--size", type=_size, default=(1080, 1920), help="layout canvas WxH (default 1080x1920)")
    g.add_argument("-f", "--format", choices=FORMATS, default="mp4")
    g.add_argument("--fps", type=float, default=30)
    g.add_argument("--quality", type=int, default=85)
    g.add_argument("--ranks", help="only these highlight ranks, e.g. 1,2,5")
    s = p.add_argument_group("subtitles")
    s.add_argument("--subtitles", help="SRT / WebVTT / Whisper JSON for the whole VOD (YouTube auto-captions work)")
    s.add_argument("--transcribe", metavar="MODEL", help='transcribe each clip with faster-whisper (e.g. "small", "large-v3")')
    s.add_argument("--language", help="speech language for --transcribe (ja, ko, en ...)")
    s.add_argument("--no-karaoke", action="store_true", help="plain captions instead of word-by-word highlighting")
    s.add_argument("--subtitle-style", default="default", choices=["default", "box", "pink", "small"], help="look of the captions: box = on a dark plate, pink = pink highlight, small = smaller and lighter")
    s.add_argument("--subtitle-position", default="bottom", choices=["bottom", "middle", "top"], help="where the captions sit (default bottom; top keeps them off a game's own text box)")
    s.add_argument("--font", metavar="FAMILY", help="caption font (default: an installed font for the language of the text)")
    s.add_argument("--font-size", type=int, metavar="PIXELS", help="caption size on a 1080 px wide frame (default 64)")
    s.add_argument("--snap", type=float, default=3.0, metavar="SECONDS", help="with --subtitles: move a clip edge that falls inside a spoken line to the edge of that line, by at most this much (default 3; 0 = leave the edges alone)")
    s.add_argument("--translate", metavar="LANG", help='translate the subtitles (e.g. "ko") with a translator plugin; none is built in')
    s.add_argument("--translator", metavar="NAME", help="translator plugin name, or your own code: file.py[:function] or module:function (default: the first plugin installed)")
    s.add_argument("--glossary", help="CSV (source,target) or JSON of fixed translations, e.g. VTuber names")
    s.add_argument("--bilingual", action="store_true", help="keep the original line above the translation")
    c = p.add_argument_group("description & guideline check")
    c.add_argument("--agency", help="hololive | nijisanji | vspo | aogiri | generic")
    c.add_argument("--source-url", help="original stream URL (default: from --info)")
    c.add_argument("--source-title", help="original stream title")
    c.add_argument("--channel", help="original channel name")
    c.add_argument("--registered", action="store_true", help="your clip channel is registered with the agency")


def _make_clips(args: argparse.Namespace, highlights) -> int:
    from .compliance import get_profile
    from .layouts import VerticalLayout
    from .pipeline import make_clips
    from .subtitles import FasterWhisperTranscriber, load_subtitles, subtitle_style

    if args.ranks:
        wanted = {int(r) for r in args.ranks.split(",") if r.strip()}
        highlights = [h for h in highlights if h.rank in wanted]
    if not highlights:
        print("no highlights to export")
        return 0
    from .sources import download_highlight_sections, is_url, ytdlp_command

    sections = None
    video, sample_video = args.video, args.video
    if is_url(args.video):  # only the footage of the highlights is downloaded, not the whole stream
        folder = Path(args.output) / "sections"
        sections = download_highlight_sections(
            args.video, highlights, folder, max_height=args.max_height,
            ytdlp=ytdlp_command(cookies=args.cookies, cookies_from_browser=args.cookies_from_browser),
            on_progress=lambda i, n, h: print(f"download [{i}/{n}] #{h.rank:02d} {_clock(h.start)} - {_clock(h.end)}", flush=True),
        )
        video, sample_video = None, os.fspath(sections[highlights[0].rank][0])
    layout = None
    if args.layout != "none":
        avatar = args.avatar
        if avatar == "auto":
            aspect = args.size[0] / (args.size[1] * args.split) if args.layout == "stack" else 0.8  # the pip box: a little taller than wide
            avatar = _find_avatar(sample_video, aspect=aspect, model=args.face_model, samples=args.avatar_samples).region if args.layout in ("stack", "pip") else None
        key = args.avatar_key
        if key.lower() == "auto" and args.avatar_video:
            from .export import has_alpha

            key = "none" if has_alpha(args.avatar_video) else "#00FF00"
            print(f"avatar {args.avatar_video}: " + ("its own transparency is used" if key == "none" else "#00FF00 is removed"))
        layout = VerticalLayout(
            args.layout, args.size[0], args.size[1], avatar=avatar, game=args.game, split=args.split, corner=args.corner, inset=args.inset,
            avatar_source=args.avatar_video, avatar_key=None if key.lower() == "none" else ("#00FF00" if key.lower() == "auto" else key), avatar_offset=args.avatar_offset,
        )
    options = ExportOptions(format=args.format, fps=args.fps, quality=args.quality, layout=layout)
    cues = load_subtitles(args.subtitles) if args.subtitles else None
    transcriber = FasterWhisperTranscriber(args.transcribe) if args.transcribe and cues is None else None
    subtitle_translator = glossary = None
    if args.translate:
        from .translation import Glossary, get_translator

        if cues is None and transcriber is None:
            raise ValueError("--translate needs subtitles: give --subtitles or --transcribe")
        subtitle_translator = get_translator(args.translator)
        glossary = Glossary.load(args.glossary) if args.glossary else None
    source = _source(args)
    profile = get_profile(args.agency) if (args.agency or source) else None
    results = make_clips(
        video, highlights, args.output, options=options, cues=cues, transcriber=transcriber, language=args.language,
        section=(lambda h: sections[h.rank]) if sections is not None else None,
        karaoke=not args.no_karaoke, source=source, profile=profile, registered=True if args.registered else None,
        subtitle_style=subtitle_style(args.subtitle_style, position=args.subtitle_position, font=args.font, size=args.font_size),
        subtitle_translator=subtitle_translator, translate_to=args.translate or "ko", glossary=glossary, bilingual=args.bilingual,
        on_progress=lambda i, n, h: print(f"[{i}/{n}] #{h.rank:02d} {_clock(h.start)} - {_clock(h.end)}", flush=True),
    )
    for r in results:
        print(f"  {r.path}" + (f"  (+ {r.subtitles.name})" if r.subtitles else "") + (f"  (+ {r.description.name})" if r.description else ""))
    problems = [i for r in results for i in r.issues if i.level in ("error", "warning")]
    if results and results[0].issues:
        print("guideline check:")
        for issue in results[0].issues:
            print(f"  {issue}")
    print(f"index {Path(args.output) / 'clips.json'}")
    return 1 if any(i.level == "error" for i in problems) and args.strict else 0


def _find_avatar(video: str, *, aspect: float, model: str | None, samples: int):
    from .detect import OnnxFaceDetector, default_detector, suggest_avatar_for_video

    detector = OnnxFaceDetector(model) if model else default_detector()
    suggestion = suggest_avatar_for_video(video, detector, samples=samples, aspect=aspect)
    if suggestion is None:
        raise ValueError("No avatar found: no anime face stays in one place in the sampled frames. Give the box yourself with --avatar x,y,w,h")
    print(f"avatar {suggestion.region}  (face {suggestion.face}, in {suggestion.hits}/{suggestion.frames} frames, score {suggestion.score:.2f})")
    return suggestion


def cmd_avatar(args: argparse.Namespace) -> int:
    suggestion = _find_avatar(args.video, aspect=args.size[0] / (args.size[1] * args.split), model=args.face_model, samples=args.samples)
    if args.preview:
        from .detect import draw_suggestion, sample_times
        from .export import grab_frames, probe

        times = sample_times(probe(args.video).duration or 0.0, 3)
        frames = grab_frames(args.video, times[1:2])
        if frames:
            draw_suggestion(frames[0], suggestion).save(args.preview)
            print(f"preview {args.preview}")
    return 0


def _snap(args: argparse.Namespace, highlights) -> None:
    """Move clip edges off the middle of a spoken line (before anything is downloaded or cut)."""
    if not args.subtitles or args.snap <= 0 or not highlights:
        return
    from .highlights import snap_to_cues
    from .subtitles import load_subtitles

    moved = snap_to_cues(highlights, load_subtitles(args.subtitles), max_shift=args.snap)
    print(f"snap   {moved} of {len(highlights)} clips moved to the edge of a spoken line")


def cmd_clips(args: argparse.Namespace) -> int:
    from .highlights import load_highlights

    highlights = load_highlights(args.highlights)
    _snap(args, highlights)
    return _make_clips(args, highlights)


def _prepare_from_url(args: argparse.Namespace, out: Path) -> None:
    """``auto <URL>``: fetch what highlight detection needs (chat replay, info) - the video comes later, in parts."""
    from .sources import fetch_replay, load_info, ytdlp_command

    for option in ("audio", "laughter", "mark_singing", "skip_singing"):
        if getattr(args, option, False):
            raise ValueError(f"--{option.replace('_', '-')} needs the whole video. Download it first (stream2clip fetch URL -o DIR --video) and give the file instead of the address.")
    ytdlp = ytdlp_command(cookies=args.cookies, cookies_from_browser=args.cookies_from_browser)
    info, chat = fetch_replay(
        args.video, out, info=not args.info, chat=not args.chat, ytdlp=ytdlp,
        on_stage=lambda name: print(f"fetch  {name.removeprefix('fetch-')} ...", flush=True),
        warn=lambda message: print(f"info   (skipped) {message}", file=sys.stderr),
    )
    if info is not None:
        args.info = str(info)
        print(f"info   {args.info}  ({load_info(info).get('title', '')})")
    if chat is not None:
        args.chat = str(chat)
        print(f"chat   {args.chat}")


def cmd_auto(args: argparse.Namespace) -> int:
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    if not args.plot:
        args.plot = str(out / "timeline.png")
    from .sources import is_url

    if is_url(args.video):
        _prepare_from_url(args, out)
        result = _detect(args, None)
    else:
        result = _detect(args, args.video)
    _snap(args, result.highlights)
    result.save(out / "highlights.json")
    return _make_clips(args, result.highlights)


def cmd_replay(args: argparse.Namespace) -> int:
    import os

    from .obs import replay_to_clip

    output = Path(args.output)
    options = _export_options(args, output)
    password = args.password or os.environ.get("OBS_WEBSOCKET_PASSWORD")
    clip, replay = replay_to_clip(output, options, last=args.last, host=args.host, port=args.port, password=password, start_buffer=args.start_buffer)
    print(f"replay {replay}")
    print(f"saved  {clip}")
    return 0


def _live_config(args: argparse.Namespace):
    from .live import LiveConfig

    return LiveConfig(
        threshold=args.threshold, smooth=args.smooth, cooldown=args.cooldown, warmup=args.warmup, history=args.history,
        min_messages=args.min_messages, lag=args.lag, chat_delay=args.delay, lead=args.lead, tail=args.tail, **_markers(args),
    )


def cmd_live(args: argparse.Namespace) -> int:
    from .live import ReplayClipper, SurgeDetector, open_chat, reads_chat_itself, simulate, watch
    from .sources import is_url, ytdlp_command

    config = _live_config(args)
    out = Path(args.output)
    if args.simulate:  # a finished chat: what would have fired, and when
        from .chat import load_chat

        if is_url(args.source):
            raise ValueError("--simulate reads a chat file (fetch the replay first: stream2clip fetch URL -o DIR)")
        messages = load_chat(args.source)
        triggers = simulate(messages, config)
        hours = (max((m.time for m in messages), default=0.0) / 3600) or 1.0
        for t in triggers:
            print(f"{_clock(t.time)}  score {t.score:4.1f}  {' / '.join(t.reasons)}")
        print(f"{len(triggers)} triggers in {len(messages):,} messages ({len(triggers) / hours:.1f} per hour)")
        return 0

    clipper = None
    if not args.no_obs:
        from .obs import ObsClient

        password = args.password or os.environ.get("OBS_WEBSOCKET_PASSWORD")
        options = _export_options(args, Path(f"clip.{args.format or 'mp4'}"))
        clipper = ReplayClipper(out, lambda: ObsClient(args.host, args.port, password), options=options, config=config)
        version = clipper.check(start_buffer=args.start_buffer)  # before the long wait, not at the first surge
        print(f"obs    OBS {version}, replay buffer running", flush=True)
    out.mkdir(parents=True, exist_ok=True)
    started = time.time()
    # yt-dlp is only looked for when it is the one that reads the chat: a file or a Twitch channel works without it.
    through_ytdlp = is_url(args.source) and not reads_chat_itself(args.source)
    ytdlp = ytdlp_command(cookies=args.cookies, cookies_from_browser=args.cookies_from_browser) if through_ytdlp else None
    source, described = open_chat(args.source, out / "chat", ytdlp=ytdlp)
    print(f"chat   {described}", flush=True)
    detector = SurgeDetector(config, live_from=started)
    log = out / "live.jsonl"

    def stamp(seconds: float) -> str:
        return time.strftime("%H:%M:%S", time.localtime(seconds))

    def fired(trigger) -> None:
        what = "marker    " if trigger.stats.get("marker") else f"surge {trigger.score:.1f}"  # a marker has no score: it was asked for
        print(f"[{stamp(trigger.time)}] {what}  {' / '.join(trigger.reasons)}", flush=True)
        entry = {**trigger.to_dict(), "at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(trigger.time))}
        if clipper is not None:
            try:
                saved = clipper(trigger)
            except (RuntimeError, OSError, ValueError) as exc:  # OBS closed, buffer stopped, disk full: keep watching
                print(f"           not saved: {exc}", file=sys.stderr, flush=True)
                entry["error"] = str(exc)
            else:
                print(f"           saved {saved.clip}", flush=True)
                entry.update(clip=str(saved.clip), replay=str(saved.replay))
                if saved.note:
                    print(f"           note: {saved.note}", file=sys.stderr, flush=True)
                    entry["note"] = saved.note
        with log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    reported = [started]

    def heartbeat() -> bool:
        now = time.time()
        if args.verbose and now - reported[0] >= 60:
            reported[0] = now
            print(f"[{stamp(now)}] {detector.messages:,} messages, {detector.seen():.0f} s of history, {len(detector.triggers)} surges", flush=True)
        return False

    print(f"watch  threshold {config.threshold:g}, cooldown {config.cooldown:g} s, Ctrl+C to stop", flush=True)
    try:
        count = watch(source, detector, fired, until=started + args.duration if args.duration else None, max_triggers=args.max_clips, should_stop=heartbeat)
    except KeyboardInterrupt:
        count = len(detector.triggers)
    finally:
        source.close()
    print(f"done   {count} surges in {detector.messages:,} messages" + (f", {len(clipper.saved)} clips in {out}" if clipper is not None else ""))
    return 0


def cmd_language(args: argparse.Namespace) -> int:
    from . import i18n

    print(i18n.language())
    if args.verbose:
        print(f"environment STREAM2CLIP_LANG: {os.environ.get('STREAM2CLIP_LANG') or '-'}")
        print(f"installer ({i18n.INSTALL_FILE}): {i18n.installed_language() or '-'}")
        print(f"system: {i18n.system_language()}")
    return 0


def cmd_upload(args: argparse.Namespace) -> int:
    from .export import probe
    from .upload import load_credentials, shorts_problems, upload_video, video_resource, video_url

    description = Path(args.description_file).read_text(encoding="utf-8") if args.description_file else (args.description or "")
    tags = [t for t in (args.tags or "").split(",") if t.strip()]
    resource = video_resource(
        args.title, description, tags=tags, category_id=args.category, privacy=args.privacy, made_for_kids=args.made_for_kids,
        synthetic_media=True if args.synthetic_media else None, language=args.language, shorts=args.shorts, publish_at=args.publish_at,
    )
    if args.shorts:
        info = probe(args.video)
        for problem in shorts_problems(info.width, info.height, info.duration):
            print(f"! {problem}", file=sys.stderr)
    if args.dry_run:
        print(json.dumps(resource, ensure_ascii=False, indent=2))
        print("dry run: nothing was uploaded")
        return 0
    if not args.client_secrets:
        raise ValueError("--client-secrets is required to upload (your own OAuth client file); use --dry-run to only see what would be sent")
    credentials = load_credentials(args.client_secrets, args.token)
    print(f"uploading {args.video} as {args.privacy} ...", flush=True)
    response = upload_video(args.video, resource, credentials=credentials, on_progress=lambda f: print(f"  {f:4.0%}", flush=True))
    print(f"uploaded {video_url(response['id'])}  ({response.get('status', {}).get('privacyStatus', args.privacy)})")
    if resource["status"].get("publishAt"):
        print(f"scheduled to become public at {resource['status']['publishAt']}")
    return 0


def cmd_evaluate(args: argparse.Namespace) -> int:
    from .evaluation import evaluate_streams, load_stream, parse_sweep
    from .highlights import HighlightConfig

    streams = []
    for folder in args.folders:
        try:
            stream = load_stream(folder, min_votes=args.min_votes)
        except ValueError as exc:  # one incomplete folder should not stop the others
            print(f"skip   {exc}", file=sys.stderr)
            continue
        if not stream.labels:
            print(f"skip   {stream.name}: no timestamps in its comments (fetch with --comments N)", file=sys.stderr)
            continue
        streams.append(stream)
    if not streams:
        raise ValueError("No stream with viewer timestamps to compare against")
    base = HighlightConfig(top=args.top)
    settings = [("defaults", base)]
    for sweep in args.sweep:
        settings += parse_sweep(sweep, base)

    def line(name: str, s) -> str:
        return f"{name:<28.28} {s.highlights:>4} {s.labels:>6} {s.precision:>9.0%} {s.recall:>7.0%} {s.chance:>7.0%} {s.lift:>5.2f}"

    report = []
    header = f"{'':<28} {'clip':>4} {'marked':>6} {'precision':>9} {'recall':>7} {'chance':>7} {'lift':>5}"
    for label, cfg in settings:
        rows, pooled = evaluate_streams(streams, cfg, tolerance=args.tolerance)
        print(f"\n[{label}]")
        print(header)
        for name, score in rows:
            print(line(name, score))
        print(line(f"all {len(rows)} streams", pooled))
        report.append({"setting": label, "streams": {name: vars(score) for name, score in rows},
                       "pooled": {**vars(pooled), "precision": pooled.precision, "recall": pooled.recall, "lift": pooled.lift}})
    if args.output:
        Path(args.output).write_text(json.dumps({"schema": "stream2clip.evaluation/v1", "tolerance": args.tolerance, "results": report}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nsaved {args.output}")
    return 0


def cmd_singing(args: argparse.Namespace) -> int:
    from .audio import singing_sections

    songs = singing_sections(args.video, min_length=args.min_length)
    for index, song in enumerate(songs, start=1):
        print(f"  #{index:02d}  {_clock(song.start)} - {_clock(song.end)}  ({song.duration:.0f}s, held pitch {song.score:.0%})")
    print(f"{len(songs)} singing sections, {sum(s.duration for s in songs) / 60:.1f} min in total")
    if args.output:
        data = {"schema": "stream2clip.singing/v1", "video": str(args.video), "sections": [{"start": s.start, "end": s.end, "score": s.score} for s in songs]}
        Path(args.output).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"saved {args.output}")
    return 0


def cmd_glossary(args: argparse.Namespace) -> int:
    import os

    from .translation import Glossary, holodex_names

    if args.holodex:
        key = args.api_key or os.environ.get("HOLODEX_API_KEY", "")
        glossary, notes = holodex_names(args.holodex, key)
        glossary.save(args.output, notes)
        print(f"saved {args.output}  ({len(glossary)} names from Holodex; edit the target column to the spelling you want)")
        return 0
    glossary = Glossary.load(args.output)
    print(f"{args.output}: {len(glossary)} terms")
    if args.text:
        print(glossary.apply(args.text))
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    from .compliance import PROFILES, check_upload, get_profile
    from .i18n import shown, tr

    if args.list:
        for key, prof in PROFILES.items():
            print(f"{key:10s} {shown(prof.name)}" + (f"  ({prof.guideline_url}, {tr('개정 {0}').format(prof.revised)})" if prof.guideline_url else ""))
        return 0
    source = _source(args)
    if source is None and not args.vrm:
        raise ValueError("Give --info or --source-url/--source-title, or a model with --vrm")
    issues = []
    if args.vrm:  # what the avatar's own licence allows
        from .vrm import check_vrm, read_vrm_meta

        meta = read_vrm_meta(args.vrm)
        for line in meta.summary():
            print(line)
        issues += check_vrm(meta, monetized=args.monetized or args.corporation, corporation=args.corporation)
    if source is not None:
        description = Path(args.description).read_text(encoding="utf-8") if args.description else None
        issues += check_upload(source, get_profile(args.agency), description=description, registered=True if args.registered else None, uses_ai=args.uses_ai)
    for issue in issues:
        print(issue)
    return 1 if any(i.level == "error" for i in issues) else 0


# ----------------------------------------------------------------------------- parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stream2clip", description="Stream in. Clips out. - capture, annotate, record and auto-clip VTuber streams.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("monitors", help="list monitors and their coordinates")
    p.set_defaults(func=cmd_monitors)

    p = sub.add_parser("capture", help="screenshot a region / monitor / whole screen")
    where = p.add_mutually_exclusive_group()
    where.add_argument("--region", type=_region, help="x,y,w,h or WxH+X+Y (physical pixels)")
    where.add_argument("--monitor", type=int, help="0-based monitor index")
    p.add_argument("--delay", type=float, default=0, help="seconds to wait before capturing")
    p.add_argument("--annotations", help="apply a stream2clip.annotation/v1 JSON file")
    p.add_argument("-o", "--output", required=True, help="png / jpg / webp / bmp")
    p.set_defaults(func=cmd_capture)

    p = sub.add_parser("record", help="record a screen region to GIF / WebP / MP4 / WebM / MOV / APNG")
    where = p.add_mutually_exclusive_group()
    where.add_argument("--region", type=_region, help="x,y,w,h or WxH+X+Y (physical pixels)")
    where.add_argument("--monitor", type=int, help="0-based monitor index (default: first)")
    p.add_argument("--duration", type=float, help="stop after N seconds (default: until Enter)")
    p.add_argument("--capture-fps", type=float, default=15, help="capture rate (default 15)")
    p.add_argument("--no-cursor", action="store_true", help="do not draw the mouse cursor")
    p.add_argument("--keep-raw", help="also keep the lossless FFV1 recording at this path")
    p.add_argument("-o", "--output", required=True)
    _add_export_args(p)
    p.set_defaults(func=cmd_record)

    p = sub.add_parser("convert", help="cut / crop / convert a video (e.g. a stream VOD) into a clip")
    p.add_argument("input")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--start", type=parse_time, help="start time (SS, MM:SS or HH:MM:SS)")
    p.add_argument("--end", type=parse_time, help="end time")
    p.add_argument("--crop", type=_region, help="crop x,y,w,h in source pixels (before scaling)")
    p.add_argument("--no-audio", action="store_true", help="drop audio (MP4/WebM/MOV)")
    p.add_argument("--print-command", action="store_true", help="print the ffmpeg command instead of running it")
    _add_export_args(p)
    p.set_defaults(func=cmd_convert)

    p = sub.add_parser("annotate", help="apply an annotation JSON to an image")
    p.add_argument("image")
    p.add_argument("--annotations", required=True, help="stream2clip.annotation/v1 JSON")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--overlay", action="store_true", help="write only the annotation layer (transparent PNG)")
    p.set_defaults(func=cmd_annotate)

    p = sub.add_parser("fetch", help="download info, chat replay (and optionally the VOD / a section) with yt-dlp")
    p.add_argument("url")
    p.add_argument("-o", "--output", required=True, help="directory")
    p.add_argument("--video", action="store_true", help="also download the video")
    p.add_argument("--start", type=parse_time, help="download only from here")
    p.add_argument("--end", type=parse_time, help="download only until here")
    p.add_argument("--max-height", type=int, default=1080)
    p.add_argument("--no-chat", action="store_true")
    p.add_argument("--cookies", help="Netscape cookies.txt for yt-dlp (fixes \"Sign in to confirm you're not a bot\")")
    p.add_argument("--cookies-from-browser", metavar="BROWSER", help="let yt-dlp read cookies from chrome / firefox / edge ...")
    p.add_argument("--subs", metavar="LANGS", help='also download captions as WebVTT (auto captions included), e.g. "ja" or "ja,ko"')
    p.add_argument("--comments", type=int, default=0, metavar="N", help="also keep the N top comments in info.json (viewers' timestamps for `stream2clip evaluate`)")
    p.set_defaults(func=cmd_fetch)

    p = sub.add_parser("evaluate", help="score the detector against the timestamps viewers left in the comments")
    p.add_argument("folders", nargs="+", help="folders made by `fetch URL -o FOLDER --comments N` (chat replay + info.json)")
    p.add_argument("--sweep", action="append", default=[], metavar="NAME=V1,V2", help="try several values of one setting, e.g. threshold=1.5,2,2.5 or delay=4,8,12 (repeatable)")
    p.add_argument("--tolerance", type=float, default=10.0, help="seconds a marked moment may lie outside a highlight and still count (default 10)")
    p.add_argument("--min-votes", type=int, default=1, help="only use moments marked by at least this many comments (default 1)")
    p.add_argument("--top", type=int, default=10, help="maximum number of highlights per stream (default 10)")
    p.add_argument("-o", "--output", help="write the numbers as JSON")
    p.set_defaults(func=cmd_evaluate)

    p = sub.add_parser("highlights", help="find highlight moments from chat / audio / most-replayed")
    p.add_argument("--video", help="VOD file (duration, and loudness with --audio)")
    p.add_argument("-o", "--output", help="write highlights JSON")
    _add_highlight_args(p)
    p.set_defaults(func=cmd_highlights)

    p = sub.add_parser("clips", help="export highlights as vertical clips with subtitles and descriptions")
    p.add_argument("video", help="VOD file, or the stream's address: then only the highlights' footage is downloaded")
    p.add_argument("--highlights", required=True, help="JSON from `stream2clip highlights`")
    p.add_argument("-o", "--output", required=True, help="output directory")
    p.add_argument("--info", help="yt-dlp info JSON (source title / URL)")
    p.add_argument("--strict", action="store_true", help="exit 1 when the guideline check finds errors")
    _add_clip_args(p)
    p.set_defaults(func=cmd_clips)

    p = sub.add_parser("auto", help="VOD + chat -> highlights -> clips in one go")
    p.add_argument("video", help="VOD file, or the stream's address: chat replay is fetched and only the highlights' footage is downloaded")
    p.add_argument("-o", "--output", required=True, help="output directory")
    p.add_argument("--strict", action="store_true", help="exit 1 when the guideline check finds errors")
    _add_highlight_args(p)
    _add_clip_args(p)
    p.set_defaults(func=cmd_auto)

    p = sub.add_parser("avatar", help="suggest the avatar box for --layout stack (anime face detection)")
    p.add_argument("video")
    p.add_argument("--preview", help="save a frame with the suggested box drawn on it")
    p.add_argument("--samples", type=int, default=12, help="frames to look at (default 12)")
    p.add_argument("--split", type=float, default=0.42, help="avatar panel height fraction the box is shaped for")
    p.add_argument("--size", type=_size, default=(1080, 1920), help="layout canvas WxH (default 1080x1920)")
    p.add_argument("--face-model", help="ONNX face model file (default: downloaded once, 12 MB)")
    p.set_defaults(func=cmd_avatar)

    p = sub.add_parser("replay", help="save OBS's replay buffer and turn it into a clip (obs-websocket)")
    p.add_argument("-o", "--output", required=True, help="clip to write, e.g. moment.gif / .webp / .mp4")
    p.add_argument("--last", type=float, help="keep only the last N seconds of the replay")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=4455)
    p.add_argument("--password", help="WebSocket server password (default: OBS_WEBSOCKET_PASSWORD)")
    p.add_argument("--start-buffer", action="store_true", help="start the replay buffer if it is not running (then run the command again later)")
    _add_export_args(p)
    p.set_defaults(func=cmd_replay)

    p = sub.add_parser("live", help="watch a live chat and save OBS's replay buffer as a clip when it surges")
    p.add_argument("source", help="address of a live YouTube stream or of a Twitch, CHZZK or SOOP channel, or a chat file a collector keeps appending to (JSON lines)")
    p.add_argument("-o", "--output", default="live", help="folder for the clips, the chat and live.jsonl (default: live)")
    p.add_argument("--no-obs", action="store_true", help="only report the surges (no OBS, nothing saved)")
    p.add_argument("--simulate", action="store_true", help="SOURCE is a finished chat replay: print what would have fired")
    p.add_argument("--duration", type=float, help="stop after this many seconds")
    p.add_argument("--max-clips", type=int, help="stop after this many surges")
    p.add_argument("-v", "--verbose", action="store_true", help="print a status line every minute")
    d = p.add_argument_group("when it fires")
    d.add_argument("--threshold", type=float, default=3.5, help="how far above normal the chat must be (default 3.5; higher = fewer clips)")
    d.add_argument("--smooth", type=int, default=2, help="windows of 5 s the surge must last (default 2)")
    d.add_argument("--cooldown", type=float, default=90.0, help="seconds between two clips (default 90)")
    d.add_argument("--warmup", type=float, default=120.0, help="seconds of chat to see before anything fires (default 120)")
    d.add_argument("--history", type=float, default=900.0, help="seconds of chat that count as 'normal' (default 900)")
    d.add_argument("--min-messages", type=int, default=8, help="messages a 5 s window needs to count at all (default 8)")
    d.add_argument("--lag", type=float, default=12.0, help="how late chat may arrive, in seconds (default 12)")
    _add_marker_args(d)
    c = p.add_argument_group("what is cut out of the replay")
    c.add_argument("--delay", type=float, default=8.0, help="seconds viewers need to react (default 8; add your stream latency if you are the streamer)")
    c.add_argument("--lead", type=float, default=20.0, help="seconds kept before the moment (default 20)")
    c.add_argument("--tail", type=float, default=10.0, help="seconds kept after the surge (default 10)")
    o = p.add_argument_group("OBS and yt-dlp")
    o.add_argument("--host", default="127.0.0.1")
    o.add_argument("--port", type=int, default=4455)
    o.add_argument("--password", help="WebSocket server password (default: OBS_WEBSOCKET_PASSWORD)")
    o.add_argument("--start-buffer", action="store_true", help="start the replay buffer if it is not running")
    o.add_argument("--cookies", help="cookies file for yt-dlp")
    o.add_argument("--cookies-from-browser", help="browser to take cookies from (yt-dlp)")
    _add_export_args(p)
    p.set_defaults(func=cmd_live)

    p = sub.add_parser("language", help="show the interface language the app starts in (before a choice made in the app itself)")
    p.add_argument("-v", "--verbose", action="store_true", help="also show where it could come from")
    p.set_defaults(func=cmd_language)

    p = sub.add_parser("upload", help="upload a clip to YouTube (private unless you say otherwise)")
    p.add_argument("video")
    p.add_argument("--title", required=True)
    p.add_argument("--description", help="description text")
    p.add_argument("--description-file", help="read the description from a file, e.g. clips/clip_01.txt")
    p.add_argument("--tags", help="comma separated")
    p.add_argument("--privacy", choices=["private", "unlisted", "public"], default="private")
    p.add_argument("--publish-at", metavar="WHEN", help='keep the video private and make it public at this time, e.g. "2026-12-24 18:00" (your local time)')
    p.add_argument("--category", default="20", help="YouTube category id (default 20 = Gaming)")
    p.add_argument("--language", help="default language of the title / description, e.g. ko")
    p.add_argument("--made-for-kids", action="store_true")
    p.add_argument("--synthetic-media", action="store_true", help="declare altered or synthetic content (AI voice, AI video ...)")
    p.add_argument("--shorts", action="store_true", help="add #Shorts and warn when the video is not vertical or longer than 3 minutes")
    p.add_argument("--client-secrets", help="your Google Cloud OAuth client file (Desktop app)")
    p.add_argument("--token", help="where to keep the refresh token (default: token.json next to the client file)")
    p.add_argument("--dry-run", action="store_true", help="print what would be sent and stop")
    p.set_defaults(func=cmd_upload)

    p = sub.add_parser("singing", help="find the songs in a stream (karaoke / 歌枠) from its audio")
    p.add_argument("video")
    p.add_argument("-o", "--output", help="write the sections as JSON")
    p.add_argument("--min-length", type=float, default=60.0, help="shortest section in seconds (default 60)")
    p.set_defaults(func=cmd_singing)

    p = sub.add_parser("glossary", help="name glossary for subtitle translation (draft one from Holodex, or check a file)")
    p.add_argument("output", help="glossary file (CSV source,target or JSON)")
    p.add_argument("--holodex", metavar="ORG", help='write a draft from Holodex channel names, e.g. "Hololive", "Nijisanji", "VSpo"')
    p.add_argument("--api-key", help="Holodex API key (default: HOLODEX_API_KEY)")
    p.add_argument("--text", help="show this text with the glossary applied")
    p.set_defaults(func=cmd_glossary)

    p = sub.add_parser("check", help="pre-upload checklist against an agency's clip guideline")
    p.add_argument("--agency", help="hololive | nijisanji | vspo | aogiri | generic")
    p.add_argument("--info", help="yt-dlp info JSON of the source stream")
    p.add_argument("--source-url")
    p.add_argument("--source-title")
    p.add_argument("--channel")
    p.add_argument("--description", help="text file with the planned video description")
    p.add_argument("--registered", action="store_true")
    p.add_argument("--uses-ai", action="store_true", help="AI tools (e.g. automatic transcription) were used")
    p.add_argument("--vrm", metavar="FILE", help="a VRM avatar: show what its licence allows (who may use it, commercial use, credit) and check it")
    p.add_argument("--monetized", action="store_true", help="--vrm: the channel earns money (ads, memberships, Super Chat)")
    p.add_argument("--corporation", action="store_true", help="--vrm: the channel is run by a company")
    p.add_argument("--list", action="store_true", help="list known agency profiles")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("gui", help="open the desktop app")
    p.add_argument("files", nargs="*", help="images to open in the editor")
    p.set_defaults(func=cmd_gui)
    return parser


def _tolerant_output() -> None:
    """Never die while printing.

    Results contain Korean, Japanese and emoji (reasons, stream titles). A real console
    shows them, but redirected output uses the system code page (cp1252, cp949 ...) and
    ``print`` raised UnicodeEncodeError there. Redirected output becomes UTF-8 unless
    ``PYTHONIOENCODING`` says otherwise; anything that still cannot be shown is replaced.
    """
    import os

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            if stream.isatty() or os.environ.get("PYTHONIOENCODING"):
                reconfigure(errors="replace")
            else:
                reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):  # closed or exotic stream: leave it alone
            pass


def main(argv: list[str] | None = None) -> int:
    _tolerant_output()
    raw = sys.argv[1:] if argv is None else list(argv)
    if raw[:1] == ["yt-dlp"]:  # `stream2clip yt-dlp ...`: how the built executable runs yt-dlp for `fetch`
        return _run_ytdlp(raw[1:])
    args = build_parser().parse_args(raw)
    try:
        return int(args.func(args) or 0)
    except (ValueError, RuntimeError, FileNotFoundError, IndexError, OSError) as exc:
        print(f"stream2clip: error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
