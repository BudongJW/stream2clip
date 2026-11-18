"""``stream2clip`` command line interface."""

from __future__ import annotations

import argparse
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


# ----------------------------------------------------------------------------- parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stream2clip", description="Capture, annotate and record clips (GIF/WebP/MP4) with transparent backgrounds.")
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

    p = sub.add_parser("gui", help="open the desktop app")
    p.add_argument("files", nargs="*", help="images to open in the editor")
    p.set_defaults(func=cmd_gui)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except (ValueError, RuntimeError, FileNotFoundError, IndexError) as exc:
        print(f"stream2clip: error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
