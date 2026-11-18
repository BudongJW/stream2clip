"""``stream2clip`` command line interface."""

from __future__ import annotations

import argparse
import json
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
        info = fetch_info(args.url, ytdlp=ytdlp)
        (out / "info.json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
        print(f"info   {out / 'info.json'}  ({info.get('title', '')})")
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
    g.add_argument("--top", type=int, default=10, help="maximum number of highlights (default 10)")
    g.add_argument("--threshold", type=float, default=2.0, help="robust z-score needed for a peak (default 2.0)")
    g.add_argument("--window", type=float, default=5.0, help="analysis bucket in seconds (default 5)")
    g.add_argument("--delay", type=float, default=8.0, help="seconds chat lags behind the moment (default 8)")
    g.add_argument("--lead", type=float, default=20.0, help="context before the moment (default 20 s)")
    g.add_argument("--tail", type=float, default=10.0, help="context after the moment (default 10 s)")
    g.add_argument("--min-length", type=float, default=15.0)
    g.add_argument("--max-length", type=float, default=90.0)
    g.add_argument("--keep-greetings", action="store_true", help="count greetings / goodbyes too (they flood the chat when a stream starts and ends)")
    g.add_argument("--plot", help="also draw the timeline as PNG")


def _detect(args: argparse.Namespace, video: str | None):
    from .highlights import HighlightConfig, render_timeline
    from .pipeline import find_highlights

    if not args.chat and not args.info and not (video and args.audio):
        raise ValueError("Give --chat, --info (heatmap) or --audio with a video")
    cfg = HighlightConfig(window=args.window, threshold=args.threshold, chat_delay=args.delay, lead=args.lead, tail=args.tail,
                          min_length=args.min_length, max_length=args.max_length, top=args.top, skip_greetings=not args.keep_greetings)
    src = _source(args)
    result = find_highlights(video, chat=args.chat, chat_format=args.chat_format, info=args.info, audio=args.audio, config=cfg,
                             source={"url": src.url, "title": src.title} if src else {})
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
    g.add_argument("--layout", default="blur", choices=["blur", "center", "fit", "stack", "none"], help="9:16 layout (default blur); 'none' keeps the original framing")
    g.add_argument("--avatar", type=_avatar, help="stack layout: avatar box x,y,w,h in source pixels, or 'auto' to find it with anime face detection")
    g.add_argument("--face-model", help="--avatar auto: ONNX face model file (default: downloaded once, 12 MB)")
    g.add_argument("--avatar-samples", type=int, default=12, help="--avatar auto: frames to look at (default 12)")
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
    from .subtitles import FasterWhisperTranscriber, load_subtitles

    if args.ranks:
        wanted = {int(r) for r in args.ranks.split(",") if r.strip()}
        highlights = [h for h in highlights if h.rank in wanted]
    if not highlights:
        print("no highlights to export")
        return 0
    layout = None
    if args.layout != "none":
        avatar = args.avatar
        if avatar == "auto":
            avatar = _find_avatar(args.video, aspect=args.size[0] / (args.size[1] * args.split), model=args.face_model, samples=args.avatar_samples).region if args.layout == "stack" else None
        layout = VerticalLayout(args.layout, args.size[0], args.size[1], avatar=avatar, game=args.game, split=args.split)
    options = ExportOptions(format=args.format, fps=args.fps, quality=args.quality, layout=layout)
    cues = load_subtitles(args.subtitles) if args.subtitles else None
    transcriber = FasterWhisperTranscriber(args.transcribe) if args.transcribe and cues is None else None
    source = _source(args)
    profile = get_profile(args.agency) if (args.agency or source) else None
    results = make_clips(
        args.video, highlights, args.output, options=options, cues=cues, transcriber=transcriber, language=args.language,
        karaoke=not args.no_karaoke, source=source, profile=profile, registered=True if args.registered else None,
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


def cmd_clips(args: argparse.Namespace) -> int:
    from .highlights import load_highlights

    return _make_clips(args, load_highlights(args.highlights))


def cmd_auto(args: argparse.Namespace) -> int:
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    if not args.plot:
        args.plot = str(out / "timeline.png")
    result = _detect(args, args.video)
    result.save(out / "highlights.json")
    return _make_clips(args, result.highlights)


def cmd_check(args: argparse.Namespace) -> int:
    from .compliance import PROFILES, check_upload, get_profile

    if args.list:
        for key, prof in PROFILES.items():
            print(f"{key:10s} {prof.name}" + (f"  ({prof.guideline_url}, 개정 {prof.revised})" if prof.guideline_url else ""))
        return 0
    source = _source(args)
    if source is None:
        raise ValueError("Give --info or --source-url/--source-title")
    description = Path(args.description).read_text(encoding="utf-8") if args.description else None
    issues = check_upload(source, get_profile(args.agency), description=description, registered=True if args.registered else None, uses_ai=args.uses_ai)
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
    p.set_defaults(func=cmd_fetch)

    p = sub.add_parser("highlights", help="find highlight moments from chat / audio / most-replayed")
    p.add_argument("--video", help="VOD file (duration, and loudness with --audio)")
    p.add_argument("-o", "--output", help="write highlights JSON")
    _add_highlight_args(p)
    p.set_defaults(func=cmd_highlights)

    p = sub.add_parser("clips", help="export highlights as vertical clips with subtitles and descriptions")
    p.add_argument("video")
    p.add_argument("--highlights", required=True, help="JSON from `stream2clip highlights`")
    p.add_argument("-o", "--output", required=True, help="output directory")
    p.add_argument("--info", help="yt-dlp info JSON (source title / URL)")
    p.add_argument("--strict", action="store_true", help="exit 1 when the guideline check finds errors")
    _add_clip_args(p)
    p.set_defaults(func=cmd_clips)

    p = sub.add_parser("auto", help="VOD + chat -> highlights -> clips in one go")
    p.add_argument("video")
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

    p = sub.add_parser("check", help="pre-upload checklist against an agency's clip guideline")
    p.add_argument("--agency", help="hololive | nijisanji | vspo | aogiri | generic")
    p.add_argument("--info", help="yt-dlp info JSON of the source stream")
    p.add_argument("--source-url")
    p.add_argument("--source-title")
    p.add_argument("--channel")
    p.add_argument("--description", help="text file with the planned video description")
    p.add_argument("--registered", action="store_true")
    p.add_argument("--uses-ai", action="store_true", help="AI tools (e.g. automatic transcription) were used")
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
    except (ValueError, RuntimeError, FileNotFoundError, IndexError) as exc:
        print(f"stream2clip: error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
