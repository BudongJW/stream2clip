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
    word = text.strip().lower()
    return word if word in ("auto", "session") else _region(text)


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
    g.add_argument("--encoder", choices=["auto", "cpu", "nvenc", "qsv", "amf"], default="auto",
                   help="MP4 video encoder: auto (default) takes the GPU this PC has (NVIDIA NVENC, Intel QSV, AMD AMF) and falls back to the CPU (libx264)")
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
        encoder=_encoder(args),
        **extra,
    )


def _encoder(args: argparse.Namespace) -> str:
    """The ``--encoder`` choice as an ffmpeg encoder name (``auto`` is resolved when the clip is made)."""
    choice = getattr(args, "encoder", "auto") or "auto"
    return {"cpu": "libx264", "nvenc": "h264_nvenc", "qsv": "h264_qsv", "amf": "h264_amf"}.get(choice, "auto")


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
    from .sources import download_chat, download_replay_chat, download_section, download_subs, fetch_info, platform_of, replay_expiry_note, with_platform_details, ytdlp_command

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    korean = platform_of(args.url)  # CHZZK / SOOP: chat comes from their own replay API, not yt-dlp
    ytdlp = ytdlp_command(cookies=args.cookies, cookies_from_browser=args.cookies_from_browser)
    info = None
    try:
        info = fetch_info(args.url, ytdlp=ytdlp, comments=args.comments) if args.comments else fetch_info(args.url, ytdlp=ytdlp)
        info = with_platform_details(args.url, info)  # CHZZK: game or not, the game, the day the stream began
        (out / "info.json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
        print(f"info   {out / 'info.json'}  ({info.get('title', '')})" + (f"  + {len(info.get('comments') or [])} comments" if args.comments else ""))
    except RuntimeError as exc:
        if not korean:
            raise
        print(f"info   (skipped) {exc}", file=sys.stderr)
    reminder = replay_expiry_note(args.url, info)
    if reminder:
        print(f"note   {reminder}", file=sys.stderr)
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


def _delay(text: str) -> "float | str":
    """``--delay``: seconds, or ``auto``."""
    if text.strip().lower() == "auto":
        return "auto"
    return float(text)


def _add_highlight_args(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group("highlight detection")
    g.add_argument("--chat", help="chat archive: yt-dlp live_chat.json, chat-downloader JSON, TwitchDownloader JSON, CHZZK / SOOP replay chat, CSV/JSONL")
    g.add_argument("--chat-format", choices=["youtube", "chat-downloader", "twitch", "chzzk", "soop", "csv", "jsonl", "json", "session"], help="force the chat format")
    g.add_argument("--info", help="yt-dlp info JSON (most-replayed heatmap, title/URL for descriptions)")
    g.add_argument("--audio", action="store_true", help="also use the video's loudness")
    g.add_argument("--laughter", action="store_true", help="experimental: also score laughter-like bursts in the audio")
    g.add_argument("--speech", metavar="SUBTITLES", help="experimental: also score reaction words in this subtitle file (what the streamer says); a way to find moments in a stream without chat")
    g.add_argument("--mark-singing", action="store_true", help="find the songs in the video and say which highlights overlap one")
    g.add_argument("--skip-singing", action="store_true", help="like --mark-singing, and leave out highlights that are mostly a song")
    g.add_argument("--top", type=int, help="maximum number of highlights (default: from --preset; shorts 10)")
    g.add_argument("--threshold", type=float, default=2.0, help="robust z-score needed for a peak (default 2.0)")
    g.add_argument("--window", type=float, default=5.0, help="analysis bucket in seconds (default 5)")
    g.add_argument("--profile", metavar="FILE", help="settings tuned for a channel (evaluate --tune --save-profile): signal weights, threshold and chat delay")
    g.add_argument("--delay", type=_delay, default=8.0, metavar="SECONDS|auto",
                   help="seconds chat lags behind the moment (default 8); auto estimates it from the video's sound and keeps 8 when no clear lag shows")
    g.add_argument("--lead", type=float, help="context before the moment (default: from --preset; shorts 20 s)")
    g.add_argument("--tail", type=float, help="context after the moment (default: from --preset; shorts 10 s)")
    g.add_argument("--min-length", type=float, help="shortest highlight in seconds (default: from --preset; shorts 15)")
    g.add_argument("--max-length", type=float, help="longest highlight in seconds (default: from --preset; shorts 90)")
    g.add_argument("--keep-greetings", action="store_true", help="count greetings / goodbyes too (they flood the chat when a stream starts and ends)")
    g.add_argument("--skip-scene", action="append", metavar="NAME", help="with --session: leave out highlights that are mostly in an OBS scene whose name contains NAME (e.g. a waiting or ending screen); repeat for more")
    _add_marker_args(g)
    g.add_argument("--plot", help="also draw the timeline as PNG")


def _add_session_args(p: argparse.ArgumentParser, *, detect: bool = True) -> None:
    g = p.add_argument_group("session file (stream2clip session record)")
    g.add_argument("--session", metavar="FILE", help="session recorded while streaming: its chat and markers (when --chat is not given), its OBS scenes for --skip-scene, and VTube Studio's outline for --avatar session")
    g.add_argument("--session-origin", choices=["auto", "stream", "record", "session"], default="auto", help="what time 0 of the video is: when OBS started streaming (a platform's VOD), recording (a local recording), or the session; auto: the first of those")
    g.add_argument("--session-offset", type=float, default=0.0, metavar="SECONDS", help="seconds the video starts after that time (negative: before)")
    if detect:  # what highlight detection takes from the session
        g.add_argument("--avatar-motion", action="store_true", help="experimental: also score how much the VTube Studio avatar moved (its parameters in --session)")


def _session(args: argparse.Namespace):
    """``(session, time 0)`` for ``--session``, or ``(None, 0.0)``."""
    if not getattr(args, "session", None):
        return None, 0.0
    from .session import load_session

    session = load_session(args.session)
    return session, session.origin(args.session_origin) + args.session_offset


def _add_audio_track_arg(p: argparse.ArgumentParser) -> None:
    p.add_argument("--audio-track", type=int, metavar="N", help="audio track to listen to for subtitles, silences, loudness, laughter and songs: 0 is the first (an OBS recording with the microphone alone on track 2: 1); the clips keep the first track")


def _add_marker_args(g) -> None:
    g.add_argument("--marker", action="append", metavar="WORD", help="chat command of the streamer or a moderator that always makes a clip; repeat for more (default: !clip !클립 !切り抜き !ts !mark)")
    g.add_argument("--marker-anyone", action="store_true", help="take the marker from every chatter, not only the streamer and moderators")
    g.add_argument("--no-markers", action="store_true", help="ignore marker commands")


def _markers(args: argparse.Namespace) -> dict:
    """``markers`` / ``marker_roles`` for HighlightConfig and LiveConfig."""
    from .highlights import DEFAULT_MARKERS

    words = () if args.no_markers else tuple(args.marker or DEFAULT_MARKERS)
    return {"markers": words, "marker_roles": ("any",) if args.marker_anyone else ("owner", "moderator")}


def _apply_preset(args: argparse.Namespace) -> None:
    """Fill what was not given on the command line from ``--preset`` (shorts, clip, long)."""
    from .presets import get_preset

    preset = get_preset(getattr(args, "preset", None))
    for name, value in (("top", preset.top), ("lead", preset.lead), ("tail", preset.tail), ("min_length", preset.min_length), ("max_length", preset.max_length),
                        ("layout", preset.layout), ("fade", preset.fade), ("context", preset.context), ("karaoke", preset.karaoke)):
        if hasattr(args, name) and getattr(args, name) is None:
            setattr(args, name, value)
    if preset.compile and hasattr(args, "compile_to") and args.compile_to is None:
        args.compile_to = ""  # joined, under the default name


def _detect(args: argparse.Namespace, video: str | None):
    from .highlights import HighlightConfig, render_timeline
    from .pipeline import find_highlights

    _apply_preset(args)
    session, zero = _session(args)
    if not args.chat and not args.info and not (video and args.audio) and not args.speech and session is None:
        raise ValueError("Give --chat, --info (heatmap), --audio with a video, --speech with subtitles, or --session")
    if args.skip_scene and session is None:
        raise ValueError("--skip-scene needs the scenes of a --session file")
    auto_delay = args.delay == "auto"
    if auto_delay and not (video and (args.chat or session is not None)):
        raise ValueError("--delay auto compares the chat with the video's sound: give the video and the chat")
    cfg = HighlightConfig(window=args.window, threshold=args.threshold, chat_delay=8.0 if auto_delay else args.delay, estimate_delay=auto_delay,
                          lead=args.lead, tail=args.tail, min_length=args.min_length, max_length=args.max_length, top=args.top,
                          skip_greetings=not args.keep_greetings, **_markers(args))
    if getattr(args, "profile", None):
        from .highlights import load_profile

        cfg = load_profile(args.profile, cfg)
        print(f"profile {args.profile}: threshold {cfg.threshold:g}, chat delay {cfg.chat_delay:g} s")
    src = _source(args)
    if getattr(args, "avatar_motion", False) and session is None:
        raise ValueError("--avatar-motion needs the avatar parameters of a --session file")
    motion = None
    if getattr(args, "avatar_motion", False):
        from .session import avatar_motion

        motion = avatar_motion(session, zero, window=cfg.window, delay=cfg.chat_delay)
        if not motion.any():
            raise ValueError(f"{args.session} holds no avatar parameters: record with  stream2clip session record --vts")
    messages = session.messages(zero, marker_delay=cfg.chat_delay) if session is not None and not args.chat else None
    if messages is not None:
        print(f"session {args.session}: {len(messages):,} chat messages and markers")
    result = find_highlights(video, chat=args.chat, chat_format=args.chat_format, info=args.info, audio=args.audio, laughter=bool(video and args.laughter), speech=args.speech, config=cfg,
                             source={"url": src.url, "title": src.title} if src else {}, messages=messages, avatar=motion, audio_track=args.audio_track)
    if session is not None and args.skip_scene:
        from .session import skip_scenes

        before = len(result.highlights)
        kept = skip_scenes(result.highlights, session.scenes(zero), args.skip_scene)
        for rank, h in enumerate(sorted(kept, key=lambda h: h.rank), start=1):
            h.rank = rank
        result.highlights = sorted(kept, key=lambda h: h.rank)
        print(f"scenes  {before - len(kept)} highlights left out (in a scene named like {', '.join(args.skip_scene)})")
    if video and (args.mark_singing or args.skip_singing):
        from .audio import singing_sections
        from .highlights import mark_singing

        songs = singing_sections(video, track=args.audio_track)
        print(f"singing  {len(songs)} sections" + (": " + ", ".join(f"{_clock(s.start)}-{_clock(s.end)}" for s in songs) if songs else ""))
        mark_singing(result, [(s.start, s.end) for s in songs], drop=args.skip_singing)
    if auto_delay:
        found = result.estimated_delay
        print(f"chat delay {found[0]:.1f} s, estimated from the sound (agreement {found[1]:.2f})" if found
              else f"chat delay {cfg.chat_delay:g} s: the sound showed no clear lag")
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
    from .subtitles import SUBTITLE_POSITIONS, SUBTITLE_STYLES

    g = p.add_argument_group("clip output")
    g.add_argument("--layout", choices=["blur", "center", "fit", "stack", "pip", "none"], help="9:16 layout (default: from --preset; shorts blur, clip and long none): stack = avatar above the game, pip = avatar in a corner of the game; 'none' keeps the original framing")
    g.add_argument("--avatar", type=_avatar, help="stack / pip layout: avatar box x,y,w,h in source pixels, 'auto' to find it with anime face detection, or 'session' to take it from the VTube Studio outline in --session")
    g.add_argument("--vts-region", type=_region, metavar="X,Y,W,H", help="--avatar session: where VTube Studio's whole view is in the video, when the session does not know where OBS put it")
    g.add_argument("--avatar-video", metavar="FILE", help="stack / pip layout: take the avatar from its own recording (green screen or alpha) instead of a box in the stream")
    g.add_argument("--avatar-key", default="auto", metavar="COLOR", help="colour removed from --avatar-video: 'auto' (default) uses the file's own transparency when it has one and removes #00FF00 otherwise; 'none' always uses the file's transparency")
    g.add_argument("--avatar-offset", type=float, default=None, metavar="SECONDS", help="--avatar-video: seconds its recording started before the stream's (negative: after; default: from --session when the recorder started that recording, else 0)")
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
    g.add_argument("--encoder", choices=["auto", "cpu", "nvenc", "qsv", "amf"], default="auto",
                   help="MP4 video encoder: auto (default) takes the GPU this PC has (NVIDIA NVENC, Intel QSV, AMD AMF) and falls back to the CPU (libx264)")
    g.add_argument("--ranks", help="only these highlight ranks, e.g. 1,2,5")
    g.add_argument("--trim-silence", type=float, nargs="?", const=0.7, metavar="SECONDS", help="shorten pauses inside each clip: silences of this length or longer (default 0.7) are cut down to a short pause; captions move along")
    g.add_argument("--silence-level", type=float, default=24.0, metavar="DB", help="--trim-silence: how far below the clip's loud parts counts as silent (default 24 dB; smaller cuts more)")
    g.add_argument("--loudness", type=float, nargs="?", const=-14.0, metavar="LUFS", help="bring each clip's sound to this loudness (default -14, where YouTube turns louder videos down), measured in a first pass; MP4, WebM, MOV")
    s = p.add_argument_group("subtitles")
    s.add_argument("--subtitles", help="SRT / WebVTT / Whisper JSON for the whole VOD (YouTube auto-captions work)")
    s.add_argument("--transcribe", metavar="MODEL", help='transcribe each clip with faster-whisper (e.g. "small", "large-v3")')
    s.add_argument("--language", help="speech language for --transcribe (ja, ko, en ...)")
    s.add_argument("--karaoke", action=argparse.BooleanOptionalAction, default=None,
                   help="light the words up as they are spoken; --no-karaoke: plain sentence captions (default: from --preset, karaoke for shorts, sentences for clip and long)")
    s.add_argument("--subtitle-style", default="default", choices=list(SUBTITLE_STYLES), metavar="LOOK",
                   help="look of the captions: default, box (on a dark plate), pink (pink highlight), small; with a free font fetched on first use: "
                        "dohyeon, black-han, gothic-black, yellow, pink-pop, plate, cute, handwriting, game, sunflower, pretendard, nanum, brush, doodle (Korean), "
                        "telop, telop-yellow, zen-maru, rocknroll, reggae (Japanese), impact, comic, heavy, poster (English). `stream2clip fonts` lists the fonts")
    s.add_argument("--subtitle-position", default="bottom", choices=list(SUBTITLE_POSITIONS), metavar="PLACE",
                   help="where the captions sit: bottom (default, above the Shorts buttons), low (near the bottom edge), middle, top, "
                        "under-video / over-video / above-video (on a Short: under, on or over the stream picture)")
    s.add_argument("--font", metavar="FAMILY", help="caption font (default: an installed font for the language of the text)")
    s.add_argument("--font-size", type=int, metavar="PIXELS", help="caption size on a frame whose short side is 1080 px, for both orientations (default: 80 on horizontal clips, 112 on Shorts, as Korean clip channels caption)")
    s.add_argument("--snap", type=float, default=3.0, metavar="SECONDS", help="with --subtitles: move a clip edge that falls inside a spoken line to the edge of that line, by at most this much (default 3; 0 = leave the edges alone)")
    s.add_argument("--translate", metavar="LANG", help='translate the subtitles (e.g. "ko") with a translator plugin; none is built in')
    s.add_argument("--translator", metavar="NAME", help="translator plugin name, or your own code: file.py[:function] or module:function (default: the first plugin installed)")
    s.add_argument("--glossary", help="CSV (source,target,note,heard) or JSON of names, e.g. VTuber names: fixed in translation, given to --transcribe as hints, and their misheard spellings (heard, separated by |) corrected in the subtitles")
    s.add_argument("--bilingual", action="store_true", help="keep the original line above the translation")
    s.add_argument("--speaker", action="append", metavar="LABEL=NAME:#COLOR", help="name and caption colour of a speaker in a collab, e.g. SPEAKER_00=ぺこら:#57C7FF (a diarization label, or an audio track number with --speaker-tracks); name and colour optional; repeat per speaker")
    s.add_argument("--speakers-rttm", metavar="FILE", help="who speaks when, from a diarization tool (RTTM, on the video's clock): each subtitle line is given its speaker; whisperX JSON subtitles carry speakers themselves")
    s.add_argument("--speaker-tracks", metavar="N,N", help="audio tracks with one microphone each (0 is the first): each line's speaker is the loudest track; name them with --speaker N=NAME")
    s.add_argument("--speaker-names", action="store_true", help="put the speaker's name in front of each line")
    c = p.add_argument_group("description & guideline check")
    c.add_argument("--agency", help="hololive | nijisanji | vspo | aogiri | generic")
    c.add_argument("--source-url", help="original stream URL (default: from --info)")
    c.add_argument("--source-title", help="original stream title")
    c.add_argument("--channel", help="original channel name")
    c.add_argument("--registered", action="store_true", help="your clip channel is registered with the agency")
    c.add_argument("--credit", metavar="TEXT", help="burn a small source line into a corner of every clip; 'auto' writes the original channel's name (from --info or --channel)")
    c.add_argument("--title-template", metavar="FORM", help="form of the suggested titles, with {hook} (the line at the peak), {talent}, {agency}, {clip}, {game}, {guests}; "
                                                         "default per language, e.g. Japanese '{hook}{guests}【{talent}/{agency}{clip}】', Korean without an agency '[{talent}] {hook}{guests}'; "
                                                         "'game' puts the game in a second bracket, e.g. '[{talent}][{game}] {hook}' (the game from CHZZK, else the stream title's bracket tag)")
    c.add_argument("--guest", action="append", metavar="NAME", help="someone else in the collab, named after the hook as (w.NAME); repeat per guest")
    c.add_argument("--streamer-link", action="append", metavar="URL", help="a link of the streamer's own (official YouTube channel, CHZZK channel) under the channel line of each description; repeat per link")
    c.add_argument("--contact-note", action="store_true", help="add a line for a streamer without clip guidelines: tell me in the comments if something is a problem and I will fix or remove it")
    c.add_argument("--context", metavar="TEXT", help="a line of what is going on, at the top of each clip's first seconds; 'auto' takes the stream's topic from its title (the bracket tag that is not the agency or the talent)")
    c.add_argument("--context-seconds", type=float, default=3.0, metavar="SECONDS", help="--context: how long the line stays (default 3)")
    c.add_argument("--fx", default="off", metavar="PRESET|FILE",
                   help="effects at each clip's peak: off (default), subtle (a punch-in zoom on the sound onset, one word of the captions popping), "
                        "variety (stronger zoom, two words, a reaction tag such as 草 or !?), or a JSON preset (stream2clip fx subtle -o my.json)")
    c.add_argument("--fx-reduced-motion", action="store_true", help="--fx without moving the picture: the emphasised word grows more instead of a zoom")
    c.add_argument("--teaser", type=float, nargs="?", const=2.0, metavar="SECONDS", help="open each clip with this many seconds of its peak (default 2), cut from just before the sound rises; MP4, WebM, MOV")
    c.add_argument("--thumbnail", action="store_true", help="also write <clip>.jpg (1280x720): the sharpest frame around the peak, zoomed onto the avatar box when the layout has one, with the first words of the title")
    c.add_argument("--thumbnail-style", choices=["frame", "sticker"], help="frame (default): the scene with the first words; sticker: as Korean clip channels make them, "
                   "with the illustration (--thumbnail-art, else the avatar's box) as a sticker, two lines with the key word in yellow, "
                   "the chat line typed most at the peak in a bubble and !? for a shock. Implies --thumbnail")
    c.add_argument("--thumbnail-art", metavar="PICTURE_OR_FOLDER", help="the streamer's illustration for sticker thumbnails: a transparent PNG, or a folder "
                   "of expressions picked by the chat's main reaction (file names with laugh, surprised, wink, sad ...). Implies --thumbnail-style sticker")
    c.add_argument("--no-hashtags", action="store_true", help="leave the suggested hashtags (agency, talent, general; in Korean also the platform and kirinuki) out of the descriptions")
    c.add_argument("--credit-position", default="top-left", choices=["top-left", "top-right", "bottom-left", "bottom-right"], help="corner of the --credit line (default top-left)")
    m = p.add_argument_group("music & sound effects")
    m.add_argument("--bgm", action="append", metavar="FILE|NAME", help="background music under every clip: a file, or a name in the sound library (see 'stream2clip sounds'); give it more than once to take the tracks in turn")
    m.add_argument("--bgm-under", type=float, default=12.0, metavar="DB", help="how far below the clip's own sound the music plays, measured on each clip (default 12; it goes lower still while someone speaks)")
    m.add_argument("--bgm-volume", type=float, metavar="DB", help="fixed music gain in dB instead of --bgm-under")
    m.add_argument("--bgm-start", type=float, default=0.0, metavar="SECONDS", help="start the music this far into the track (skip an intro)")
    m.add_argument("--no-duck", action="store_true", help="keep the music at one level instead of lowering it while someone speaks")
    m.add_argument("--sfx", action="append", metavar="NAME[@WHEN]", help="a sound effect in every clip: built-in pop / ding / whoosh / boom / sparkle, auto (picked by what chat reacted with), a library name or a file; WHEN = peak (default), start, end or seconds from the start; give it more than once for more effects")
    m.add_argument("--sfx-under", type=float, default=3.0, metavar="DB", help="how far below the clip's own sound the effects play (default 3)")
    m.add_argument("--sfx-gap", type=float, default=3.0, metavar="SECONDS", help="keep this much between two effects in one clip (default 3; 0: none). An effect too close to one given before it moves by up to 1.5 s, or is left out")
    m.add_argument("--no-sfx-snap", action="store_true", help="put effects exactly where asked: by default a peak effect moves to the nearest sharp rise in the sound (a shout, a laugh) within 2.5 s before to 1 s after the peak, and the others move out of the middle of talk by up to 0.75 s")
    m.add_argument("--sounds", metavar="DIR", help="sound library folder (default: 'sounds' in the app's settings folder)")
    p.add_argument("--compile", dest="compile_to", nargs="?", const="", metavar="FILE", help="also join the clips, in stream order, into one video with a chapter list (default name: compilation.mp4 in the output folder)")
    p.add_argument("--fade", type=float, metavar="SECONDS", help="--compile: fade to black between the clips (default: from --preset; 0 = hard cuts, long 0.3)")


def _add_preset_arg(p: argparse.ArgumentParser) -> None:
    p.add_argument("--preset", choices=["shorts", "clip", "long"], default="shorts", help="what to make: shorts (9:16, 15-90 s, the default), clip (horizontal 1-3 min with a context line, as Korean and English clip channels post), long (horizontal clips of 45-150 s joined into one video of about 10 min with chapters, as Japanese clip channels post); options given here win over the preset")


def _soundtrack(args: argparse.Namespace):
    """The --bgm / --sfx options as a Soundtrack (``None`` when neither is given)."""
    if not (getattr(args, "bgm", None) or getattr(args, "sfx", None)):
        return None
    from .soundtrack import Effect, SoundLibrary, Soundtrack, resolve_sound

    library = SoundLibrary(args.sounds) if args.sounds else SoundLibrary()
    music = tuple(resolve_sound(spec, "bgm", library) for spec in args.bgm or ())
    effects = tuple(Effect.parse(spec, library) for spec in args.sfx or ())
    return Soundtrack(music=music, effects=effects, under=args.bgm_under, volume=args.bgm_volume, duck=not args.no_duck,
                      music_start=args.bgm_start, effect_under=args.sfx_under, snap=not args.no_sfx_snap, effect_gap=args.sfx_gap)


def _fetch_caption_fonts(families: "list[str]") -> None:
    """Fetch the catalog fonts a caption look names and this PC does not have yet (pinned, checksum checked).

    A font that cannot be fetched (no connection, a checksum that does not match) does not stop the clips:
    their captions keep the look's colours and place in the automatic font (``with_available_font``).
    """
    from .fonts import install, missing_for
    from .subtitles import _has_family, installed_fonts

    system = installed_fonts()
    for font in missing_for([f for f in families if not _has_family(f, system)]):
        print(f"font   {font.family}: fetching {font.megabytes} MB ({font.licence}) from {font.url.split('/')[2]}", flush=True)
        try:
            install(font)
        except (OSError, RuntimeError) as exc:
            print(f"font   {font.family}: not fetched ({exc}); the captions use the automatic font", file=sys.stderr, flush=True)


def _make_clips(args: argparse.Namespace, highlights) -> int:
    from .compliance import get_profile
    from .layouts import VerticalLayout
    from .pipeline import make_clips
    from .subtitles import FasterWhisperTranscriber, load_subtitles, subtitle_style

    _apply_preset(args)
    hotkeys: list[float] = []
    if getattr(args, "session", None) and args.fx != "off":
        session, zero = _session(args)
        hotkeys = [at for at, _name in session.hotkeys(zero)]

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
        aspect = args.size[0] / (args.size[1] * args.split) if args.layout == "stack" else 0.8  # the pip box: a little taller than wide
        if avatar == "auto":
            avatar = _find_avatar(sample_video, aspect=aspect, model=args.face_model, samples=args.avatar_samples).region if args.layout in ("stack", "pip") else None
        elif avatar == "session":
            avatar = _session_avatar(args, sample_video, highlights, aspect) if args.layout in ("stack", "pip") else None
        key = args.avatar_key
        if key.lower() == "auto" and args.avatar_video:
            from .export import has_alpha

            key = "none" if has_alpha(args.avatar_video) else "#00FF00"
            print(f"avatar {args.avatar_video}: " + ("its own transparency is used" if key == "none" else "#00FF00 is removed"))
        layout = VerticalLayout(
            args.layout, args.size[0], args.size[1], avatar=avatar, game=args.game, split=args.split, corner=args.corner, inset=args.inset,
            avatar_source=args.avatar_video, avatar_key=None if key.lower() == "none" else ("#00FF00" if key.lower() == "auto" else key), avatar_offset=_avatar_offset(args),
        )
    options = ExportOptions(format=args.format, fps=args.fps, quality=args.quality, layout=layout, encoder=_encoder(args))
    cues = load_subtitles(args.subtitles) if args.subtitles else None
    speakers, tracks = None, ()
    if args.speaker:
        from .speakers import SpeakerMap

        speakers = SpeakerMap.parse(args.speaker)
    if args.speakers_rttm:
        from .speakers import assign_from_spans, read_rttm

        if cues is None:
            raise ValueError("--speakers-rttm gives the subtitle lines their speakers: give --subtitles too")
        cues = assign_from_spans(cues, read_rttm(args.speakers_rttm))
    if args.speaker_tracks:
        tracks = tuple(int(part) for part in args.speaker_tracks.split(",") if part.strip())
        if len(tracks) < 2:
            raise ValueError("--speaker-tracks needs two or more audio tracks, e.g. 1,2")
    glossary = None
    if args.glossary:
        from .translation import Glossary

        glossary = Glossary.load(args.glossary)
    hints = glossary.names() if glossary is not None else ()
    transcriber = FasterWhisperTranscriber(args.transcribe, hotwords=hints) if args.transcribe and cues is None else None
    subtitle_translator = None
    if args.translate:
        from .translation import get_translator

        if cues is None and transcriber is None:
            raise ValueError("--translate needs subtitles: give --subtitles or --transcribe")
        subtitle_translator = get_translator(args.translator)
    source = _source(args)
    profile = get_profile(args.agency) if (args.agency or source) else None
    credit = (args.credit or "").strip()
    if credit.lower() == "auto":
        from .i18n import tr

        channel = (source.channel if source else "") or (args.channel or "")
        if not channel:
            raise ValueError("--credit auto needs the name of the original channel: give --info or --channel")
        credit = tr("원본: {0}").format(channel)
    soundtrack = _soundtrack(args)
    if soundtrack is not None:
        for sound in soundtrack.music:
            print(f"music  {sound.label}" + (f"  ({sound.license})" if sound.license else "  (license not recorded)"))
    if args.thumbnail_art and not Path(args.thumbnail_art).exists():
        raise ValueError(f"--thumbnail-art: no such picture or folder: {args.thumbnail_art}")
    look = subtitle_style(args.subtitle_style, position=args.subtitle_position, font=args.font, size=args.font_size)
    if cues is not None or transcriber is not None:
        _fetch_caption_fonts([look.font])
    results = make_clips(
        video, highlights, args.output, options=options, cues=cues, transcriber=transcriber, language=args.language,
        section=(lambda h: sections[h.rank]) if sections is not None else None,
        karaoke=args.karaoke is not False, source=source, profile=profile, registered=True if args.registered else None,
        subtitle_style=look,
        subtitle_translator=subtitle_translator, translate_to=args.translate or "ko", glossary=glossary, bilingual=args.bilingual,
        credit=credit or None, credit_position=args.credit_position, trim_silence=args.trim_silence, silence_level=args.silence_level,
        audio_track=args.audio_track, on_progress=lambda i, n, h: print(f"[{i}/{n}] #{h.rank:02d} {_clock(h.start)} - {_clock(h.end)}", flush=True),
        soundtrack=soundtrack, loudness=args.loudness, title_template=args.title_template, add_hashtags=not args.no_hashtags,
        guests=tuple(args.guest or ()), links=tuple(args.streamer_link or ()), contact_note=args.contact_note,
        thumbnails=args.thumbnail or bool(args.thumbnail_style or args.thumbnail_art),
        thumbnail_style=args.thumbnail_style or ("sticker" if args.thumbnail_art else "frame"), thumbnail_art=args.thumbnail_art,
        context=args.context, context_seconds=args.context_seconds, teaser=args.teaser or 0.0,
        speakers=speakers, speaker_tracks=tracks, speaker_names=args.speaker_names,
        effects=None if args.fx == "off" else args.fx, reduced_motion=args.fx_reduced_motion, hotkeys=hotkeys,
    )
    for r in results:
        print(f"  {r.path}" + (f"  (+ {r.subtitles.name})" if r.subtitles else "") + (f"  (+ {r.description.name})" if r.description else "")
              + (f"  ({r.removed:.1f} s of silence removed)" if r.removed else "")
              + (f"  (opens with {r.teaser:.1f} s of the peak)" if r.teaser else "")
              + ("  (" + ", ".join(f"{s.sound.label} {s.at:.1f}s" + (f" moved {s.moved:+.1f}" if s.moved else "") for s in r.sounds) + ")" if r.sounds else ""))
        for reason in r.skipped_sounds:
            print(f"    left out: {reason}")
        if r.title:
            print(f"    title: {r.title}" + (f"  {' '.join(r.hashtags)}" if r.hashtags else ""))
        if r.thumbnail:
            print(f"    thumbnail: {r.thumbnail.name}")
        for note in r.captions:
            print(f"    captions: {note}")
        if r.effects:
            placed = ", ".join(_effect_note(e) for e in r.effects["placed"])
            print(f"    effects: {placed or 'none'}")
            for reason in r.effects["skipped"]:
                print(f"      left out: {reason}")
    problems = [i for r in results for i in r.issues if i.level in ("error", "warning")]
    if results and results[0].issues:
        print("guideline check:")
        for issue in results[0].issues:
            print(f"  {issue}")
    print(f"index {Path(args.output) / 'clips.json'}")
    if args.compile_to is not None and results:
        from .pipeline import compile_folder

        _report_compilation(compile_folder(args.output, args.compile_to or None, fade=args.fade, encoder=_encoder(args)))
    return 1 if any(i.level == "error" for i in problems) and args.strict else 0


def _report_compilation(made) -> None:
    print(f"joined {made.path}  ({len(made.parts)} clips, {_clock(made.duration)})")
    if made.notes is not None:
        print(f"notes  {made.notes}")


def cmd_compile(args: argparse.Namespace) -> int:
    from .pipeline import compile_clips, compile_folder

    options = {"fade": args.fade, "quality": args.quality, "fps": args.fps, "size": args.size, "encoder": _encoder(args)}
    first = Path(args.clips[0])
    if len(args.clips) == 1 and (first.is_dir() or first.suffix.lower() == ".json"):
        ranks = {int(r) for r in args.ranks.split(",") if r.strip()} if args.ranks else None
        made = compile_folder(first, args.output, order=args.order, ranks=ranks, **options)
    else:
        if args.ranks or args.order != "time":
            raise ValueError("--ranks and --order go with a clips folder; clip files are joined in the order given")
        if not args.output:
            raise ValueError("Joining clip files needs a name for the result: -o compilation.mp4")
        made = compile_clips(args.clips, args.output, **options)
    _report_compilation(made)
    return 0


def _avatar_offset(args: argparse.Namespace) -> float:
    """``--avatar-offset``, or what the session says about when the avatar's own recording began."""
    if args.avatar_offset is not None:
        return float(args.avatar_offset)
    if not args.avatar_video or not getattr(args, "session", None):
        return 0.0
    session, zero = _session(args)
    offset = session.avatar_offset(zero) if session is not None else None
    if offset is None:
        return 0.0
    print(f"avatar offset {offset:+.2f} s  (when its recording began, from {args.session})")
    return offset


def _session_avatar(args: argparse.Namespace, video: str, highlights, aspect: float) -> Region:
    """The avatar box from the session's VTube Studio outline during the highlights (``--avatar session``)."""
    from .export import probe
    from .session import avatar_region

    session, zero = _session(args)
    if session is None:
        raise ValueError("--avatar session needs --session (a session file recorded with --vts)")
    if not session.of("avatar_outline"):
        raise ValueError(f"{args.session} holds no VTube Studio outline: record it with  stream2clip session record --vts")
    info = probe(video)
    spans = [(h.start, h.end) for h in highlights]
    box = avatar_region(session, (info.width, info.height), aspect=aspect, origin=zero, spans=spans, vts_region=args.vts_region)
    if box is None and spans:
        box = avatar_region(session, (info.width, info.height), aspect=aspect, origin=zero, vts_region=args.vts_region)
    if box is None:
        raise ValueError("The outline cannot be placed in the video: record with --vts-source NAME (the OBS source showing VTube Studio), or give --vts-region x,y,w,h")
    print(f"avatar {box}  (VTube Studio outline from {args.session})")
    return box


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


def _handoff(highlights, *, video: str | None, fps: float | None, title: str | None, order: str, edl: str | None, markers: str | None, timestamps: str | None) -> list[str]:
    """Write the files an editing program (or a comment box) takes; returns what was written, as lines to print."""
    from . import handoff
    from .sources import is_url

    lines = []
    local = video if video and not is_url(video) else None
    if edl or markers:
        audio = True
        if local:
            from .export import probe

            facts = probe(local)
            audio = facts.has_audio
            fps = fps or facts.fps
        if not fps:
            raise ValueError("A timecode counts frames: give the video file, or its frame rate with --fps")
        name = title or (Path(local).stem if local else "stream2clip")
        if edl:
            handoff.write_text(handoff.edl(highlights, fps=fps, title=name, clip_name=Path(local).name if local else "", audio=audio, order=order), edl)
            lines.append(f"edl    {edl}  ({len(highlights)} cuts, {fps:g} fps)")
        if markers:
            handoff.write_text(handoff.marker_edl(highlights, fps=fps, title=name), markers)
            lines.append(f"marker {markers}  ({len(highlights)} markers, {fps:g} fps)")
    if timestamps:
        target = Path(timestamps)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(handoff.timestamps(highlights, order=order), encoding="utf-8")
        lines.append(f"times  {timestamps}")
    return lines


def cmd_timeline(args: argparse.Namespace) -> int:
    from . import handoff
    from .highlights import load_highlights

    highlights = load_highlights(args.highlights)
    if args.ranks:
        wanted = {int(r) for r in args.ranks.split(",") if r.strip()}
        highlights = [h for h in highlights if h.rank in wanted]
    if not highlights:
        print("no highlights to hand over")
        return 0
    lines = _handoff(highlights, video=args.video, fps=args.fps, title=args.title, order=args.order, edl=args.edl, markers=args.markers, timestamps=args.timestamps)
    for line in lines:
        print(line)
    if not lines:  # nothing to write: the timestamp list, to copy from the terminal
        print(handoff.timestamps(highlights, order=args.order), end="")
    return 0


def _prepare_from_url(args: argparse.Namespace, out: Path) -> None:
    """``auto <URL>``: fetch what highlight detection needs (chat replay, info) - the video comes later, in parts."""
    from .sources import fetch_replay, load_info, ytdlp_command

    for option in ("audio", "laughter", "mark_singing", "skip_singing"):
        if getattr(args, option, False):
            raise ValueError(f"--{option.replace('_', '-')} needs the whole video. Download it first (stream2clip fetch URL -o DIR --video) and give the file instead of the address.")
    ytdlp = ytdlp_command(cookies=args.cookies, cookies_from_browser=args.cookies_from_browser)
    info, chat = fetch_replay(
        args.video, out, info=not args.info, chat=not (args.chat or args.session), ytdlp=ytdlp,
        on_stage=lambda name: print(f"fetch  {name.removeprefix('fetch-')} ...", flush=True),
        warn=lambda message: print(f"info   (skipped) {message}", file=sys.stderr),
        note=lambda message: print(f"note   {message}", file=sys.stderr),
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
    if result.highlights:
        # For whoever goes on in an editing program: the same moments as a cut list and a timestamp list.
        whole = not is_url(args.video)
        for line in _handoff(
            result.highlights, video=args.video, fps=None, title=None, order="time",
            edl=str(out / "highlights.edl") if whole else None, markers=None, timestamps=str(out / "timestamps.txt"),
        ):
            print(line)
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


def _session_recorder(args: argparse.Namespace):
    """The writer and the recorder ``session record`` runs (the app's recorder window builds the same)."""
    from .live import LiveConfig, reads_chat_itself
    from .recorder import build_recorder
    from .sources import is_url, ytdlp_command

    out = Path(args.output or time.strftime("session-%Y%m%d-%H%M%S.jsonl"))
    if out.exists() and not args.overwrite:
        raise ValueError(f"{out} exists already; choose another name or pass --overwrite")
    ytdlp = None
    if args.chat and is_url(args.chat) and not reads_chat_itself(args.chat):  # a YouTube live chat comes through yt-dlp
        ytdlp = ytdlp_command(cookies=args.cookies, cookies_from_browser=args.cookies_from_browser)
    password = args.password or os.environ.get("OBS_WEBSOCKET_PASSWORD")
    recorder = build_recorder(
        out, chat=args.chat, live_config=LiveConfig(**_markers(args)), ytdlp=ytdlp,
        obs=None if args.no_obs else (args.host, args.port, password), avatar_source=args.vts_source,
        vts_url=args.vts_url if args.vts else None, outline_every=args.outline_every, parameters=args.parameters,
        parameters_every=args.parameters_every, vts_hotkeys=args.vts_hotkey or (), replay_on_marker=args.replay_on_marker, record_avatar=args.avatar_record,
        viewer_votes=args.viewer_votes,
    )
    return recorder.writer, recorder


def cmd_session_record(args: argparse.Namespace) -> int:
    import threading

    writer, recorder = _session_recorder(args)
    print(f"session {writer.path}", flush=True)
    for name, what in json.loads(writer.path.read_text(encoding="utf-8").splitlines()[0]).get("sources", {}).items():
        print(f"  {name:5s} {what}", flush=True)
    if args.widget is not None:
        print(f"widget  {recorder.serve_widget(args.widget)}  (OBS: Sources > Browser, 400 x 120)", flush=True)
    print("Press Enter to leave a marker, Ctrl+C to stop.", flush=True)

    def keys() -> None:  # every Enter is a marker
        for _line in sys.stdin:
            recorder.mark("enter")
            print(f"[{time.strftime('%H:%M:%S')}] marker", flush=True)

    if sys.stdin is not None and sys.stdin.isatty():
        threading.Thread(target=keys, daemon=True).start()
    shown: dict[str, tuple[str, str]] = {}
    last = [time.time()]

    def report(rec) -> None:
        for part in rec.parts:
            state = (part.status.state, part.status.detail)
            if shown.get(part.name) != state:
                shown[part.name] = state
                print(f"[{time.strftime('%H:%M:%S')}] {part.name:5s} {state[0]}" + (f": {state[1]}" if state[1] else ""), flush=True)
        if args.verbose and time.time() - last[0] >= 60:
            last[0] = time.time()
            print(f"[{time.strftime('%H:%M:%S')}] " + ", ".join(f"{k} {v}" for k, v in sorted(writer.counts.items())), flush=True)

    try:
        recorder.run(until=time.time() + args.duration if args.duration else None, on_step=report)
    except KeyboardInterrupt:
        pass  # run() has written the pending markers and closed the parts and the file
    print(f"done    {writer.path}: " + ", ".join(f"{k} {v}" for k, v in sorted(writer.counts.items())))
    return 0


def cmd_session_show(args: argparse.Namespace) -> int:
    from .session import load_session

    session = load_session(args.file)
    zero = session.origin(args.origin) + args.offset
    print(f"session {session.path}  ({session.app or 'unknown program'})")
    print(f"  began   {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(session.started))}, {(session.end - session.started) / 60:.1f} min of events")
    for name, what in session.sources.items():
        print(f"  {name:7s} {what}")
    for output in ("stream", "record"):
        starts = session.output_starts(output)
        if starts:
            print(f"  {output:7s} started " + ", ".join(time.strftime("%H:%M:%S", time.localtime(t)) for t in starts))
    print(f"  time 0  {time.strftime('%H:%M:%S', time.localtime(zero))} ({args.origin})")
    counts: dict[str, int] = {}
    for e in session.events:
        counts[e.type] = counts.get(e.type, 0) + 1
    print("  events  " + (", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "none"))
    scenes = session.scenes(zero)
    if scenes:
        print("scenes")
        for s in scenes:
            print(f"  {_clock(s.start)} - {_clock(s.end)}  {s.name}")
    moments = [(e.t - zero, "marker", e.data.get("label") or e.data.get("by") or "") for e in session.of("marker")]
    moments += [(e.t - zero, f"surge {float(e.data.get('score') or 0):.1f}", " / ".join(e.data.get("reasons") or [])) for e in session.of("surge")]
    if moments:
        print("moments (time in the video)")
        for t, what, detail in sorted(moments):
            print(f"  {_clock(t)}  {what}" + (f"  {detail}" if detail else ""))
    problems = [e for e in session.of("status") if e.data.get("state") == "waiting"]
    if problems:
        print(f"connection problems: {len(problems)} (the first: {problems[0].data.get('source')}: {problems[0].data.get('detail', '')})")
    return 0


def cmd_chzzk_login(args: argparse.Namespace) -> int:
    from .chzzk_api import ChzzkApi, login

    api = ChzzkApi(args.client_id, args.client_secret)
    print(f"Waiting for CHZZK's sign-in on {args.redirect} (5 minutes) ...", flush=True)
    login(api, args.redirect, open_browser=(lambda url: None) if args.no_browser else None, on_url=lambda url: print(f"sign in  {url}", flush=True))
    print(f"signed in; tokens kept in {api.token_file}. Record with:  stream2clip session record --chat chzzk-api")
    return 0


def cmd_chzzk_logout(args: argparse.Namespace) -> int:
    from .chzzk_api import token_path

    path = token_path()
    if path.exists():
        path.unlink()
        print(f"removed {path}")
    else:
        print("not signed in")
    return 0


def _effect_note(effect: dict) -> str:
    kind = effect.get("type")
    if kind == "zoom":
        return f"zoom x{effect['scale']:g} at {effect['at']:.1f}s ({effect['anchor']})"
    if kind == "caption_emphasis":
        return "emphasis " + " ".join(effect.get("words") or [])
    if kind == "caption_tag":
        return f"tag {effect.get('text')} ({effect.get('reaction')})"
    return str(effect.get("id"))


def cmd_fx(args: argparse.Namespace) -> int:
    from .effects import PRESETS, builtin_preset, write_preset

    if not args.preset:
        for name, preset in PRESETS.items():
            kinds = ", ".join(e["type"] for e in preset["effects"]) or "no effects"
            print(f"{name:<8} {kinds}")
        print("write one out to edit it: stream2clip fx subtle -o my.json, then clips --fx my.json")
        return 0
    if args.output:
        print(f"saved {write_preset(args.preset, args.output)}")
    else:
        print(json.dumps(builtin_preset(args.preset), ensure_ascii=False, indent=2))
    return 0


def cmd_feedback(args: argparse.Namespace) -> int:
    from .feedback import default_path, load, summary

    path = Path(args.file) if args.file else default_path()
    if args.clear:
        if path.is_file():
            path.unlink()
            print(f"deleted {path}")
        else:
            print(f"nothing to delete: {path}")
        return 0
    entries = load(path)
    print(f"{path}: {len(entries)} exports")
    for line in summary(entries):
        print(f"  {line}")
    return 0


def cmd_language(args: argparse.Namespace) -> int:
    from . import i18n

    print(i18n.language())
    if args.verbose:
        print(f"environment STREAM2CLIP_LANG: {os.environ.get('STREAM2CLIP_LANG') or '-'}")
        print(f"installer ({i18n.INSTALL_FILE}): {i18n.installed_language() or '-'}")
        print(f"system: {i18n.system_language()}")
    return 0


def _download_progress(megabytes: int, step: int = 10):
    """Called with (done, total) bytes: prints a line every ``step`` percent."""
    shown = [0]

    def progress(done: int, total: int) -> None:
        percent = int(done * 100 / total) if total else 0
        if percent >= shown[0] + step or (total and done >= total and shown[0] < 100):
            shown[0] = 100 if done >= total else percent - percent % step
            print(f"  {shown[0]:3d}%  {done / 1e6:.0f} / {megabytes} MB", flush=True)

    return progress


def cmd_fonts(args: argparse.Namespace) -> int:
    from .fonts import CAPTION_FONTS, find, fonts_dir, install, installed
    from .subtitles import SUBTITLE_STYLES

    if args.install:
        wanted = list(CAPTION_FONTS) if [w.lower() for w in args.install] == ["all"] else [find(w) for w in args.install]
        unknown = [w for w, f in zip(args.install, wanted) if f is None]
        if unknown:
            raise ValueError(f"No caption font {', '.join(unknown)}; `stream2clip fonts` lists them")
        for font in wanted:
            assert font is not None
            if installed(font):
                print(f"have   {font.family}")
                continue
            print(f"fetch  {font.family} ({font.megabytes} MB, {font.licence})", flush=True)
            install(font)
        print(f"folder {fonts_dir()}")
        return 0
    looks: dict[str, list[str]] = {}
    for name, style in SUBTITLE_STYLES.items():
        entry = find(style.font)
        if entry is not None:
            looks.setdefault(entry.key, []).append(name)
    print(f"{'font':24} {'family':28} {'MB':>4}  {'scripts':9} {'used for':22} looks")
    for font in CAPTION_FONTS:
        if args.script and args.script not in font.scripts:
            continue
        mark = "*" if installed(font) else " "
        print(f"{mark}{font.key:23} {font.family:28} {font.megabytes:>4}  {','.join(font.scripts):9} {','.join(font.roles):22} {','.join(looks.get(font.key, []))}")
    print(f"\n* fetched, in {fonts_dir()}. All are free fonts (SIL Open Font License); a look that needs one fetches it on first use.")
    return 0


def cmd_setup(args: argparse.Namespace) -> int:
    from . import tools
    from .ffmpeg import find_ffmpeg
    from .i18n import tr

    if (args.archive or args.force) and not args.ffmpeg:
        raise ValueError("--from and --force go with --ffmpeg")
    if args.ffmpeg:
        build = tools.FFMPEG_BUILD
        if tools.ffmpeg_ready() and not args.force:
            print(tr("ffmpeg 이미 있음: {0}").format(find_ffmpeg()))
        else:
            if not args.archive:
                print(tr("ffmpeg {0} 내려받는 중 ({1} MB): {2}").format(build.version, build.megabytes, build.url), flush=True)
            for path in tools.install_ffmpeg(archive=args.archive, on_progress=_download_progress(build.megabytes)):
                print(tr("저장: {0}").format(path))
    if args.model:
        from .detect import ensure_model

        print(tr("얼굴 검출 모델: {0}").format(ensure_model()))
    if args.check_update:
        from . import updates

        release = updates.check_for_update()
        if release is None:
            print(tr("최신 버전 사용 중 ({0})").format(__version__))
        else:
            print(tr("새 버전 {0} 있음 (현재 {1})").format(release.version, __version__) + f": {updates.DOWNLOAD_PAGE}")
    found = tools.components(obs=None if args.no_obs else ("127.0.0.1", args.obs_port))
    for line in tools.report_lines(found):
        print(line)
    return 1 if tools.missing_required(found) else 0


def cmd_upload(args: argparse.Namespace) -> int:
    from .export import probe
    from .upload import SCOPES, THUMBNAIL_SCOPES, clips_source, load_credentials, resolve_category, set_thumbnail, shorts_problems, thumbnail_problem, upload_video, video_resource, video_url

    description = Path(args.description_file).read_text(encoding="utf-8") if args.description_file else (args.description or "")
    tags = [t for t in (args.tags or "").split(",") if t.strip()]
    resource = video_resource(
        args.title, description, tags=tags, category_id=resolve_category(args.category, clips_source(args.video)), privacy=args.privacy, made_for_kids=args.made_for_kids,
        synthetic_media=True if args.synthetic_media else None, paid_placement=args.paid_placement, language=args.language, shorts=args.shorts, publish_at=args.publish_at,
    )
    if args.shorts:
        info = probe(args.video)
        for problem in shorts_problems(info.width, info.height, info.duration):
            print(f"! {problem}", file=sys.stderr)
    if args.thumbnail and thumbnail_problem(args.thumbnail):
        raise ValueError(thumbnail_problem(args.thumbnail))  # before anything is sent
    if args.dry_run:
        print(json.dumps(resource, ensure_ascii=False, indent=2))
        if args.thumbnail:
            print(f"thumbnail {args.thumbnail}" + ("  (set once YouTube has processed the Short)" if args.shorts else ""))
        print("dry run: nothing was uploaded")
        return 0
    if not args.client_secrets:
        raise ValueError("--client-secrets is required to upload (your own OAuth client file); use --dry-run to only see what would be sent")
    # A Short's thumbnail waits for YouTube's processing, which takes read access to see.
    credentials = load_credentials(args.client_secrets, args.token, scopes=THUMBNAIL_SCOPES if args.thumbnail and args.shorts else SCOPES)
    print(f"uploading {args.video} as {args.privacy} ...", flush=True)
    response = upload_video(args.video, resource, credentials=credentials, on_progress=lambda f: print(f"  {f:4.0%}", flush=True))
    print(f"uploaded {video_url(response['id'])}  ({response.get('status', {}).get('privacyStatus', args.privacy)})")
    if resource["status"].get("publishAt"):
        print(f"scheduled to become public at {resource['status']['publishAt']}")
    if args.thumbnail:
        try:
            set_thumbnail(response["id"], args.thumbnail, credentials=credentials, shorts=args.shorts,
                          on_wait=lambda state: print(f"  YouTube is processing the video ({state}) ...", flush=True))
        except (RuntimeError, TimeoutError, ValueError) as exc:
            print(f"! thumbnail not set: {exc} (the video is uploaded)", file=sys.stderr)
            return 1
        print(f"thumbnail {args.thumbnail}")
    return 0


def cmd_evaluate(args: argparse.Namespace) -> int:
    from .evaluation import add_feedback, evaluate_streams, f1, gain, held_out, load_stream, parse_sweep, tune
    from .highlights import HighlightConfig, save_profile

    streams = []
    for folder in args.folders:
        try:
            stream = load_stream(folder, min_votes=args.min_votes, sound=args.audio)
        except ValueError as exc:  # one incomplete folder should not stop the others
            print(f"skip   {exc}", file=sys.stderr)
            continue
        streams.append(stream)
    if args.feedback is not None:
        from .feedback import load

        added = add_feedback(streams, load(args.feedback or None))
        print(f"feedback {added} kept highlights added as marked moments")
    for stream in [s for s in streams if not s.labels]:
        print(f"skip   {stream.name}: no timestamps in its comments (fetch with --comments N) and no kept highlights", file=sys.stderr)
        streams.remove(stream)
    if not streams:
        raise ValueError("No stream with viewer timestamps to compare against")
    if args.audio:
        print(f"sound  {sum(1 for s in streams if s.levels is not None)} of {len(streams)} streams have their video")
    flags = {"tolerance": args.tolerance, "heatmap": args.heatmap, "sound": args.audio}
    base = HighlightConfig(top=args.top)
    settings = [("defaults", base)]
    for sweep in args.sweep:
        settings += parse_sweep(sweep, base)

    def line(name: str, s) -> str:
        return f"{name:<28.28} {s.highlights:>4} {s.labels:>6} {s.precision:>9.0%} {s.recall:>7.0%} {s.chance:>7.0%} {s.lift:>5.2f}"

    report = []
    header = f"{'':<28} {'clip':>4} {'marked':>6} {'precision':>9} {'recall':>7} {'chance':>7} {'lift':>5}"
    for label, cfg in settings:
        rows, pooled = evaluate_streams(streams, cfg, **flags)
        print(f"\n[{label}]")
        print(header)
        for name, score in rows:
            print(line(name, score))
        print(line(f"all {len(rows)} streams", pooled))
        report.append({"setting": label, "streams": {name: vars(score) for name, score in rows},
                       "pooled": {**vars(pooled), "precision": pooled.precision, "recall": pooled.recall, "lift": pooled.lift}})
    if args.tune:
        tuned, pooled = tune(streams, base, trials=args.tune, seed=args.seed, **flags)
        plain = evaluate_streams(streams, base, **flags)[1]
        print(f"\n[tuned: {args.tune} tries on these {len(streams)} streams]")
        print(header)
        print(line("defaults", plain))
        print(line("tuned", pooled))
        changed = {k: v for k, v in tuned.weights.items() if base.weights.get(k) != v}
        print(f"  weights {json.dumps(changed)}, threshold {tuned.threshold:g}, chat delay {tuned.chat_delay:g} s")
        report.append({"setting": "tuned", "weights": tuned.weights, "threshold": tuned.threshold, "chat_delay": tuned.chat_delay,
                       "pooled": {**vars(pooled), "precision": pooled.precision, "recall": pooled.recall, "lift": pooled.lift}})
        if len(streams) >= 3:
            kept, moved = held_out(streams, base, trials=args.tune, seed=args.seed, **flags)
            print(f"  on streams left out of the tuning: precision above chance {gain(kept):+.0%} with the defaults, {gain(moved):+.0%} tuned"
                  f" (precision {kept.precision:.0%} -> {moved.precision:.0%}, recall {kept.recall:.0%} -> {moved.recall:.0%}, F1 {f1(kept):.2f} -> {f1(moved):.2f})")
            report[-1]["held_out"] = {"defaults": {"gain": gain(kept), "f1": f1(kept)}, "tuned": {"gain": gain(moved), "f1": f1(moved)}}
        if args.save_profile:
            save_profile(args.save_profile, tuned, note=f"evaluate --tune {args.tune} on {len(streams)} streams")
            print(f"profile {args.save_profile}  (use with highlights / auto --profile)")
    elif args.save_profile:
        raise ValueError("--save-profile saves what --tune N found: add --tune")
    if args.output:
        Path(args.output).write_text(json.dumps({"schema": "stream2clip.evaluation/v1", "tolerance": args.tolerance, "results": report}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nsaved {args.output}")
    return 0


def cmd_singing(args: argparse.Namespace) -> int:
    from .audio import singing_sections

    songs = singing_sections(args.video, min_length=args.min_length, track=args.audio_track)
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


def _library(args: argparse.Namespace):
    from .soundtrack import SoundLibrary

    return SoundLibrary(args.sounds) if getattr(args, "sounds", None) else SoundLibrary()


def cmd_sounds_list(args: argparse.Namespace) -> int:
    from .soundtrack import BUILTIN_EFFECTS

    library = _library(args)
    print(f"library {library.folder}  ({len(library)} sounds)")
    for sound in library:
        missing = "" if sound.path.is_file() else "  (file missing)"
        print(f"  {sound.kind}  {sound.name:<20} {sound.license or '(license not recorded)':<18} {sound.title or sound.path.name}{missing}")
        line = sound.credit_line()
        if line:
            print(f"        credit: {line}")
    print("built-in effects (no credit needed): " + ", ".join(BUILTIN_EFFECTS) + ", auto")
    return 0


def cmd_sounds_add(args: argparse.Namespace) -> int:
    library = _library(args)
    facts = {"license": args.license, "title": args.title, "author": args.author, "url": args.url, "credit": args.credit}
    if args.openverse:
        from .openverse import audio_detail

        found = audio_detail(args.openverse)
        print(f"openverse {found.title} by {found.creator} ({found.license} {found.license_version}, {found.provider})  {found.page}")
        if not found.key and not args.license:
            raise ValueError(f"Openverse lists the license {found.license} {found.license_version}, which has no license key here: read the page and give --license")
        facts = {key: value if value else found.facts()[key] for key, value in facts.items()}
    if not facts["license"]:
        raise ValueError("Give --license (see 'stream2clip sounds licenses'), or --openverse ID")
    sound = library.add(args.file, kind=args.kind, name=args.name or "", copy=not args.keep_in_place, hit=args.hit, tags=tuple(args.tag), **facts)
    print(f"added  {sound.name}  ({sound.kind}, {sound.license})  {sound.path}")
    line = sound.credit_line()
    if line:
        print(f"credit {line}")
    from .soundtrack import check_sounds

    for issue in check_sounds([sound]):
        print(f"  {issue}")
    return 0


def cmd_sounds_search(args: argparse.Namespace) -> int:
    from .openverse import search_audio

    found = search_audio(args.query, commercial=not args.any_license, kind=args.kind, limit=args.limit)
    for item in found:
        length = f"{item.seconds:.0f}s" if item.seconds else "?"
        key = item.key or f"{item.license} {item.license_version} (no key: read the page)"
        print(f"{item.id}  {length:>5}  {key:<18} {item.title}  by {item.creator}  [{item.provider}]")
        print(f"{'':38}{item.page}")
    print(f"{len(found)} results from Openverse (openverse.org; it does not check the licenses it lists and does not endorse this program).")
    print("Download from the page itself, then: stream2clip sounds add FILE --openverse ID")
    return 0


def cmd_sounds_remove(args: argparse.Namespace) -> int:
    library = _library(args)
    try:
        sound = library.remove(args.name)
    except KeyError:
        raise ValueError(f"No sound named {args.name!r} in {library.folder}") from None
    print(f"removed {sound.name}")
    return 0


def cmd_sounds_licenses(args: argparse.Namespace) -> int:
    from .soundtrack import LICENSES

    for lic in LICENSES.values():
        allows = [f"credit {lic.attribution}"]
        if not lic.commercial:
            allows.append("non-commercial only")
        if not lic.sync:
            allows.append("not in videos")
        if not lic.video_tools:
            allows.append("not through video tools")
        if not lic.social:
            allows.append("not on video sites")
        print(f"{lic.key:<24} {lic.name}  ({', '.join(allows)})")
        if lic.url:
            print(f"{'':<24} {lic.url}  (read {lic.checked})")
    return 0


def cmd_sounds_builtin(args: argparse.Namespace) -> int:
    from .soundtrack import BUILTIN_EFFECTS, render_builtin

    for name in args.names or BUILTIN_EFFECTS:
        print(f"saved  {render_builtin(name, args.output)}")
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
    p.add_argument("--heatmap", action="store_true", help="also use the most-replayed curve of each info.json")
    p.add_argument("--audio", action="store_true", help="also use the loudness of a video in a folder (read once, kept as *.levels1s.npy)")
    p.add_argument("--feedback", nargs="?", const="", metavar="FILE",
                   help="add the highlights kept at exports from the app (feedback.jsonl in the settings folder, or FILE) as marked moments")
    p.add_argument("--tune", type=int, default=0, metavar="N", help="try N random settings (weights, threshold, chat delay) and report the best, and how it does on streams left out")
    p.add_argument("--seed", type=int, default=1, help="--tune: the random seed (default 1)")
    p.add_argument("--save-profile", metavar="FILE", help="--tune: save the best settings as a profile for highlights / auto --profile")
    p.add_argument("-o", "--output", help="write the numbers as JSON")
    p.set_defaults(func=cmd_evaluate)

    p = sub.add_parser("highlights", help="find highlight moments from chat / audio / most-replayed")
    _add_preset_arg(p)
    p.add_argument("--video", help="VOD file (duration, and loudness with --audio)")
    p.add_argument("-o", "--output", help="write highlights JSON")
    _add_highlight_args(p)
    _add_session_args(p)
    _add_audio_track_arg(p)
    p.set_defaults(func=cmd_highlights)

    p = sub.add_parser("compile", help="join finished clips into one video with a chapter list")
    p.add_argument("clips", nargs="+", help="a folder with clips.json (from `clips` or `auto`), or the clip files in playing order")
    p.add_argument("-o", "--output", help="the video to write: .mp4, .webm or .mov (default for a folder: compilation.<type of the clips> in it)")
    p.add_argument("--order", choices=["time", "rank"], default="time", help="a folder's clips as they happened in the stream (default) or best first")
    p.add_argument("--ranks", help="a folder: only these highlight ranks, e.g. 1,2,5")
    p.add_argument("--fade", type=float, default=0.0, metavar="SECONDS", help="fade to black between the clips (default 0: hard cuts)")
    p.add_argument("--size", type=_size, help="picture WxH (default: that of the first clip; clips of another shape get bars)")
    p.add_argument("--fps", type=float, help="frame rate (default: that of the first clip)")
    p.add_argument("--quality", type=int, default=85)
    p.add_argument("--encoder", choices=["auto", "cpu", "nvenc", "qsv", "amf"], default="auto", help="MP4 video encoder (default auto: the GPU this PC has, else the CPU)")
    p.set_defaults(func=cmd_compile)

    p = sub.add_parser("timeline", help="hand the highlights to an editing program: cut list (EDL), timeline markers, timestamp list")
    p.add_argument("highlights", help="highlights JSON from `stream2clip highlights -o`")
    p.add_argument("--video", help="the stream's video file: its name and frame rate go into the EDL")
    p.add_argument("--fps", type=float, help="frame rate for the timecodes (default: read from --video)")
    p.add_argument("--edl", metavar="FILE", help="write a CMX3600 cut list: the highlights as cuts of the video, one after the other (DaVinci Resolve, Premiere Pro, Vegas ...)")
    p.add_argument("--markers", metavar="FILE", help="write the highlights as timeline markers for a timeline holding the whole stream (DaVinci Resolve: Import, Timeline Markers from EDL)")
    p.add_argument("--timestamps", metavar="FILE", help="write '0:07:02 text' lines, for a comment or a description (printed when no file is asked for)")
    p.add_argument("--order", choices=["time", "rank"], default="time", help="order of the cuts and lines: as they happened (default) or best first")
    p.add_argument("--ranks", help="only these highlight ranks, e.g. 1,2,5")
    p.add_argument("--title", help="title written into the EDL (default: the video's name)")
    p.set_defaults(func=cmd_timeline)

    p = sub.add_parser("clips", help="export highlights as vertical clips with subtitles and descriptions")
    _add_preset_arg(p)
    p.add_argument("video", help="VOD file, or the stream's address: then only the highlights' footage is downloaded")
    p.add_argument("--highlights", required=True, help="JSON from `stream2clip highlights`")
    p.add_argument("-o", "--output", required=True, help="output directory")
    p.add_argument("--info", help="yt-dlp info JSON (source title / URL)")
    p.add_argument("--strict", action="store_true", help="exit 1 when the guideline check finds errors")
    _add_clip_args(p)
    _add_session_args(p, detect=False)
    _add_audio_track_arg(p)
    p.set_defaults(func=cmd_clips)

    p = sub.add_parser("auto", help="VOD + chat -> highlights -> clips in one go")
    _add_preset_arg(p)
    p.add_argument("video", help="VOD file, or the stream's address: chat replay is fetched and only the highlights' footage is downloaded")
    p.add_argument("-o", "--output", required=True, help="output directory")
    p.add_argument("--strict", action="store_true", help="exit 1 when the guideline check finds errors")
    _add_highlight_args(p)
    _add_clip_args(p)
    _add_session_args(p)
    _add_audio_track_arg(p)
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

    p = sub.add_parser("session", help="record what happens while you stream (chat, markers, OBS scenes, the VTube Studio avatar) for clipping afterwards")
    ss = p.add_subparsers(dest="session_command", required=True)
    r = ss.add_parser("record", help="record a session file until Ctrl+C (Enter leaves a marker)")
    r.add_argument("-o", "--output", help="session file to write (default: session-<date>-<time>.jsonl)")
    r.add_argument("--overwrite", action="store_true", help="replace an existing file")
    r.add_argument("--chat", metavar="SOURCE", help="your channel: a Twitch, CHZZK or SOOP channel address, a YouTube live address (yt-dlp), 'chzzk-api' (CHZZK's Open API, after  stream2clip chzzk login), or a chat file a collector appends to")
    r.add_argument("--viewer-votes", type=int, default=0, metavar="N", help="N different viewers typing a marker word (!clip ...) within 30 s leave a marker (default 0: off)")
    r.add_argument("--widget", type=int, nargs="?", const=8790, metavar="PORT", help="serve an OBS browser source showing the votes and markers on 127.0.0.1 (default port 8790)")
    r.add_argument("--duration", type=float, help="stop after this many seconds")
    r.add_argument("-v", "--verbose", action="store_true", help="print the event counts every minute")
    _add_marker_args(r)
    o = r.add_argument_group("OBS")
    o.add_argument("--no-obs", action="store_true", help="do not connect to OBS")
    o.add_argument("--host", default="127.0.0.1")
    o.add_argument("--port", type=int, default=4455)
    o.add_argument("--password", help="WebSocket server password (default: OBS_WEBSOCKET_PASSWORD)")
    o.add_argument("--vts-source", metavar="NAME", help="name of the OBS source that shows VTube Studio: its place on the canvas is recorded, so the avatar box can be found later")
    o.add_argument("--replay-on-marker", action="store_true", help="also save OBS's replay buffer at every marker")
    o.add_argument("--avatar-record", action="store_true", help="start and stop the Source Record filter (an OBS plugin) on the --vts-source source with the session; its start is written, so clips find --avatar-offset")
    v = r.add_argument_group("VTube Studio")
    v.add_argument("--vts", action="store_true", help="record the model's outline and parameters (VTube Studio > Settings > Start API; allow the plugin in the popup once)")
    v.add_argument("--vts-url", default="ws://127.0.0.1:8001", help="VTube Studio API address (default ws://127.0.0.1:8001)")
    v.add_argument("--outline-every", type=float, default=0.5, metavar="SECONDS", help="seconds between two recorded outlines (default 0.5; VTube Studio sends 15 a second)")
    v.add_argument("--parameters", choices=["default", "all", "none"], default="default", help="which model parameters to record: the standard face and head ones (default), all, or none")
    v.add_argument("--parameters-every", type=float, default=0.2, metavar="SECONDS", help="seconds between two parameter readings (default 0.2)")
    v.add_argument("--vts-hotkey", action="append", metavar="NAME", help="a VTube Studio hotkey whose name makes it a marker; repeat for more")
    y = r.add_argument_group("yt-dlp (YouTube chat)")
    y.add_argument("--cookies", help="cookies file for yt-dlp")
    y.add_argument("--cookies-from-browser", help="browser to take cookies from (yt-dlp)")
    r.set_defaults(func=cmd_session_record)
    s = ss.add_parser("show", help="what a session file holds: scenes, markers and surges at their time in the video")
    s.add_argument("file", help="session file (.jsonl)")
    s.add_argument("--origin", choices=["auto", "stream", "record", "session"], default="auto", help="what time 0 of the video is: when OBS started streaming (a platform's VOD), recording (a local recording), or the session; auto: the first of those")
    s.add_argument("--offset", type=float, default=0.0, metavar="SECONDS", help="seconds the video starts after that time (negative: before)")
    s.set_defaults(func=cmd_session_show)

    p = sub.add_parser("chzzk", help="CHZZK's official Open API for your own channel: sign in once, then  session record --chat chzzk-api")
    cs = p.add_subparsers(dest="chzzk_command", required=True)
    c = cs.add_parser("login", help="sign in in the browser (the application's client id and secret: --client-id/--client-secret or CHZZK_CLIENT_ID/CHZZK_CLIENT_SECRET)")
    c.add_argument("--client-id", help="the application's client id (CHZZK developer center)")
    c.add_argument("--client-secret", help="the application's client secret")
    c.add_argument("--redirect", default="http://localhost:8765/callback", help="the login redirect URL registered with the application (a local address; default http://localhost:8765/callback)")
    c.add_argument("--no-browser", action="store_true", help="print the sign-in address instead of opening the browser")
    c.set_defaults(func=cmd_chzzk_login)
    c = cs.add_parser("logout", help="forget the CHZZK tokens kept on this PC")
    c.set_defaults(func=cmd_chzzk_logout)

    p = sub.add_parser("fx", help="the built-in effect presets (--fx): list them, show one as JSON or save it to edit")
    p.add_argument("preset", nargs="?", choices=["off", "subtle", "variety"], help="the preset to show or save")
    p.add_argument("-o", "--output", help="save it as this JSON file")
    p.set_defaults(func=cmd_fx)

    p = sub.add_parser("feedback", help="the record of which highlights were kept or left out at each export from the app (kept on this PC)")
    p.add_argument("--file", help="the record to read (default: feedback.jsonl in the app's settings folder)")
    p.add_argument("--clear", action="store_true", help="delete the record")
    p.set_defaults(func=cmd_feedback)

    p = sub.add_parser("language", help="show the interface language the app starts in (before a choice made in the app itself)")
    p.add_argument("-v", "--verbose", action="store_true", help="also show where it could come from")
    p.set_defaults(func=cmd_language)

    p = sub.add_parser("fonts", help="caption fonts to choose from (free fonts clip channels use): list them, or fetch some for --subtitle-style / --font")
    p.add_argument("install", nargs="*", metavar="FONT", help="fetch these fonts (keys or family names from the list), or 'all'; nothing: list them")
    p.add_argument("--script", choices=["ko", "ja", "en"], help="list only the fonts that draw this script")
    p.set_defaults(func=cmd_fonts)

    p = sub.add_parser("setup", help="show what the features need on this PC and what is missing (ffmpeg, yt-dlp, OBS ...); --ffmpeg fetches ffmpeg")
    p.add_argument("--ffmpeg", action="store_true", help="Windows: download ffmpeg and ffprobe (115 MB, checked against a pinned SHA-256) into the user's tools folder; nothing is fetched when ffmpeg is already found")
    p.add_argument("--from", dest="archive", metavar="ZIP", help="with --ffmpeg: take the programs out of this already downloaded archive of the pinned build instead of downloading")
    p.add_argument("--force", action="store_true", help="with --ffmpeg: fetch even when ffmpeg is already found")
    p.add_argument("--model", action="store_true", help="download the face detection model now (12 MB) instead of on first use")
    p.add_argument("--check-update", action="store_true", help="ask GitHub whether a newer release exists (one request; nothing about this PC is sent)")
    p.add_argument("--obs-port", type=int, default=4455, help="port of OBS's WebSocket server to look for (default: 4455)")
    p.add_argument("--no-obs", action="store_true", help="do not look for OBS")
    p.set_defaults(func=cmd_setup)

    p = sub.add_parser("upload", help="upload a clip to YouTube (private unless you say otherwise)")
    p.add_argument("video")
    p.add_argument("--title", required=True)
    p.add_argument("--description", help="description text")
    p.add_argument("--description-file", help="read the description from a file, e.g. clips/clip_01.txt")
    p.add_argument("--tags", help="comma separated")
    p.add_argument("--privacy", choices=["private", "unlisted", "public"], default="private")
    p.add_argument("--publish-at", metavar="WHEN", help='keep the video private and make it public at this time, e.g. "2026-12-24 18:00" (your local time)')
    p.add_argument("--category", default="auto", help="auto (default: Gaming for a game stream, by the clips.json next to the video, else People & Blogs), people (22), gaming (20), entertainment (24) or a YouTube category id")
    p.add_argument("--language", help="default language of the title / description, e.g. ko")
    p.add_argument("--made-for-kids", action="store_true")
    p.add_argument("--synthetic-media", action="store_true", help="declare altered or synthetic content (AI voice, AI video ...)")
    p.add_argument("--paid-placement", action="store_true", help="declare paid product placement, sponsorship or endorsement; without it the video is declared free of them")
    p.add_argument("--shorts", action="store_true", help="add #Shorts and warn when the video is not vertical or longer than 3 minutes")
    p.add_argument("--thumbnail", metavar="IMAGE", help="set this JPEG or PNG as the thumbnail after the upload (clips --thumbnail makes one); for --shorts it waits until YouTube has processed the video")
    p.add_argument("--client-secrets", help="your Google Cloud OAuth client file (Desktop app)")
    p.add_argument("--token", help="where to keep the refresh token (default: token.json next to the client file)")
    p.add_argument("--dry-run", action="store_true", help="print what would be sent and stop")
    p.set_defaults(func=cmd_upload)

    p = sub.add_parser("singing", help="find the songs in a stream (karaoke / 歌枠) from its audio")
    p.add_argument("video")
    p.add_argument("-o", "--output", help="write the sections as JSON")
    p.add_argument("--min-length", type=float, default=60.0, help="shortest section in seconds (default 60)")
    _add_audio_track_arg(p)
    p.set_defaults(func=cmd_singing)

    p = sub.add_parser("glossary", help="name glossary for subtitle translation (draft one from Holodex, or check a file)")
    p.add_argument("output", help="glossary file (CSV source,target or JSON)")
    p.add_argument("--holodex", metavar="ORG", help='write a draft from Holodex channel names, e.g. "Hololive", "Nijisanji", "VSpo"')
    p.add_argument("--api-key", help="Holodex API key (default: HOLODEX_API_KEY)")
    p.add_argument("--text", help="show this text with the glossary applied")
    p.set_defaults(func=cmd_glossary)

    p = sub.add_parser("sounds", help="the sound library for --bgm / --sfx: free music and effects you downloaded, with their source and license")
    p.add_argument("--sounds", metavar="DIR", help="library folder (default: 'sounds' in the app's settings folder)")
    ss = p.add_subparsers(dest="sounds_command", metavar="command")
    s = ss.add_parser("list", help="what the library holds (the default)")
    s.set_defaults(func=cmd_sounds_list)
    s = ss.add_parser("add", help="put a downloaded file in the library with where it came from and its license")
    s.add_argument("file")
    s.add_argument("--kind", choices=["bgm", "sfx"], default="bgm", help="background music (default) or a sound effect")
    s.add_argument("--name", help="short name for --bgm / --sfx (default: the file name)")
    s.add_argument("--license", help="license key (see 'stream2clip sounds licenses'), e.g. cc-by-4.0, pixabay, opentracks, own; needed unless --openverse gives it")
    s.add_argument("--title", help="title of the track")
    s.add_argument("--author", help="who made it (the name the license asks to be credited)")
    s.add_argument("--url", help="the page it was downloaded from")
    s.add_argument("--credit", help="the credit line exactly as the site asks for it (default: built from title, author, page and license)")
    s.add_argument("--hit", type=float, default=0.0, metavar="SECONDS", help="sfx: where in the file its hit is, so that this moment lands on the peak")
    s.add_argument("--tag", action="append", default=[], help="a word to sort by (funny, chill, hype ...); give it more than once")
    s.add_argument("--keep-in-place", action="store_true", help="remember the file where it is instead of copying it into the library folder")
    s.set_defaults(func=cmd_sounds_add)
    s.add_argument("--openverse", metavar="ID", help="fill title, author, page, license and credit from this Openverse track (see 'sounds search'); options given here win")
    s = ss.add_parser("search", help="search Creative Commons music and effects on Openverse (no key needed): title, license and the page to download from")
    s.add_argument("query")
    s.add_argument("--kind", choices=["music", "sound_effect"], help="only music or only sound effects")
    s.add_argument("--any-license", action="store_true", help="also list licenses that forbid commercial use or changes (by default only ones a monetized clip can use)")
    s.add_argument("--limit", type=int, default=10, help="how many results (default 10, at most 20)")
    s.set_defaults(func=cmd_sounds_search)
    s = ss.add_parser("remove", help="forget a sound (a file copied into the library folder stays there)")
    s.add_argument("name")
    s.set_defaults(func=cmd_sounds_remove)
    s = ss.add_parser("licenses", help="the license keys a sound can name, what each allows and where its official text is")
    s.set_defaults(func=cmd_sounds_licenses)
    s = ss.add_parser("builtin", help="write the built-in effects as WAV files, to listen to them or use them in an editing program")
    s.add_argument("names", nargs="*", help="which effects (default: all)")
    s.add_argument("-o", "--output", default=".", help="folder (default: the current one)")
    s.set_defaults(func=cmd_sounds_builtin)
    p.set_defaults(func=cmd_sounds_list)

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
