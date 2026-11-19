"""Hand the highlights over to an editing program: a cut list (EDL), timeline markers, a timestamp list.

stream2clip makes finished vertical clips, but a longer edit is done in an editor. These pure
functions turn a list of highlights into text an editor reads, so the search for the moments
does not have to be repeated by hand:

* :func:`edl` - a CMX3600 edit decision list: the highlights as cuts of the stream's video, one
  after the other. DaVinci Resolve, Premiere Pro, Vegas and others import it as a timeline.
* :func:`marker_edl` - the highlights as markers on a timeline that holds the whole stream
  (DaVinci Resolve: Timelines > Import > Timeline Markers from EDL).
* :func:`timestamps` - ``0:07:02 text`` lines, for a comment or a description.

Only the standard library is used; nothing here reads a video. Give the frame rate of the video
(:func:`stream2clip.export.probe`) - a timecode counts frames.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Sequence

from .highlights import Highlight

__all__ = ["ORDERS", "clock", "edl", "frames", "marker_edl", "ordered", "timecode", "timestamps", "write_text"]

#: How the highlights are put in a row: as they happened, or best first.
ORDERS = ("time", "rank")
#: Timelines of editing programs start at one hour by convention; an EDL's record times follow it.
TIMELINE_START = 3600.0


def ordered(highlights: Iterable[Highlight], order: str = "time") -> list[Highlight]:
    if order not in ORDERS:
        raise ValueError(f"Unknown order {order!r}: use one of {', '.join(ORDERS)}")
    return sorted(highlights, key=(lambda h: (h.start, h.rank)) if order == "time" else (lambda h: (h.rank, h.start)))


def frames(seconds: float, fps: float) -> int:
    """The frame a moment falls on."""
    if not fps or fps <= 0:
        raise ValueError(f"A timecode needs the frame rate of the video, not {fps!r}")
    return int(round(max(0.0, seconds) * fps))


def timecode(seconds: float, fps: float) -> str:
    """``HH:MM:SS:FF`` (non-drop-frame): frames counted at the real rate, shown on the nearest whole base.

    29.97 and 59.94 fps are shown on a base of 30 and 60, as editing programs do for non-drop timecode.
    """
    return _from_frames(frames(seconds, fps), fps)


def _from_frames(count: int, fps: float) -> str:
    base = max(1, int(round(fps)))
    return f"{count // (base * 3600):02d}:{count // (base * 60) % 60:02d}:{count // base % 60:02d}:{count % base:02d}"


def clock(seconds: float) -> str:
    """``1:02:03`` for an hour or more, ``2:03`` below it - the form sites turn into links."""
    total = max(0, int(seconds))
    return f"{total // 3600}:{total % 3600 // 60:02d}:{total % 60:02d}" if total >= 3600 else f"{total // 60}:{total % 60:02d}"


def _one_line(text: str) -> str:
    return " ".join(str(text).split())


def _label(h: Highlight, reasons: int = 2) -> str:
    return _one_line(" / ".join(h.reasons[:reasons])) if h.reasons else ""


def edl(
    highlights: Iterable[Highlight],
    *,
    fps: float,
    title: str = "stream2clip",
    clip_name: str = "",
    reel: str = "AX",
    audio: bool = True,
    order: str = "time",
    record_start: float = TIMELINE_START,
) -> str:
    """A CMX3600 cut list: every highlight is one cut of the stream's video, placed one after the other.

    ``clip_name`` is the video's file name: editing programs find the footage by it. Source times
    count from the start of that file, record times from ``record_start`` (one hour, the usual
    start of a timeline). Cut lengths are whole frames, so the cuts sit back to back.
    """
    lines = [f"TITLE: {_one_line(title) or 'stream2clip'}", "FCM: NON-DROP FRAME", ""]
    track = "AA/V" if audio else "V"
    at = int(round(record_start * max(1, round(fps))))  # a timecode, so counted on the base: one hour is 01:00:00:00 at 29.97 fps too
    for number, h in enumerate(ordered(highlights, order), start=1):
        first, last = frames(h.start, fps), frames(h.end, fps)
        if last <= first:
            continue
        lines.append(f"{number:03d}  {reel[:8]:<8s} {track:<5s} C        {_from_frames(first, fps)} {_from_frames(last, fps)} {_from_frames(at, fps)} {_from_frames(at + last - first, fps)}")
        at += last - first
        if clip_name:
            lines.append(f"* FROM CLIP NAME: {_one_line(clip_name)}")
        note = _label(h)
        lines.append(f"* COMMENT: stream2clip #{h.rank:02d}" + (f" {note}" if note else ""))
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def marker_edl(
    highlights: Iterable[Highlight],
    *,
    fps: float,
    title: str = "stream2clip",
    color: str = "ResolveColorPink",
    timeline_start: float = TIMELINE_START,
) -> str:
    """The highlights as timeline markers, in the EDL form DaVinci Resolve reads and writes.

    For a timeline that holds the whole stream from its first frame: a marker starts where the
    highlight starts and lasts as long as it does. ``timeline_start`` is the timeline's start timecode.
    """
    lines = [f"TITLE: {_one_line(title) or 'stream2clip'}", "FCM: NON-DROP FRAME", ""]
    start = int(round(timeline_start * max(1, round(fps))))  # the timeline's start is a timecode, counted on the base
    for number, h in enumerate(ordered(highlights, "time"), start=1):
        first, length = start + frames(h.start, fps), max(1, frames(h.end, fps) - frames(h.start, fps))
        at, after = _from_frames(first, fps), _from_frames(first + 1, fps)
        name = f"#{h.rank:02d}" + (f" {_label(h)}" if h.reasons else "")
        lines.append(f"{number:03d}  001      V     C        {at} {after} {at} {after}  ")
        lines.append(f" |C:{color} |M:{name.replace('|', '/')} |D:{length}")
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def timestamps(highlights: Iterable[Highlight], *, order: str = "time", labels: Sequence[str] | None = None, offset: float = 0.0) -> str:
    """``0:07:02 text`` per highlight. ``labels`` replaces the reasons; ``offset`` shifts every time (a trimmed upload)."""
    rows = ordered(highlights, order)
    if labels is not None and len(labels) != len(rows):
        raise ValueError(f"{len(labels)} labels for {len(rows)} highlights")
    lines = []
    for index, h in enumerate(rows):
        text = _one_line(labels[index]) if labels is not None else (_label(h, 1) or f"#{h.rank:02d}")  # a list to read: the main reason only
        lines.append(f"{clock(h.start + offset)} {text}".rstrip())
    return "\n".join(lines) + ("\n" if lines else "")


def write_text(text: str, path: str | os.PathLike[str]) -> Path:
    """Write with CRLF line ends: the form editing programs on Windows expect of an EDL, and fine elsewhere."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="\r\n")
    return out
