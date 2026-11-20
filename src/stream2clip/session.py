"""Session files: what happened while a stream was on air, kept for clipping afterwards.

A session file is JSON Lines (``stream2clip.session/v1``, ``schemas/session.v1.schema.json``).
The first line is the header, every other line one event with ``t`` (wall-clock UNIX
seconds) and ``type``::

    {"schema": "stream2clip.session/v1", "started": 1763600000.0, "app": "stream2clip 0.14.0", "sources": {...}}
    {"t": 1763600012.4, "type": "output", "output": "stream", "active": true}
    {"t": 1763600400.1, "type": "chat", "text": "ㅋㅋㅋㅋ", "author": "3f2a...", "kind": "text"}
    {"t": 1763600401.0, "type": "marker", "by": "hotkey"}
    {"t": 1763600401.2, "type": "avatar_outline", "hull": [[-0.4, 0.9], ...], "window": [1920, 1080]}

:class:`stream2clip.recorder.SessionRecorder` writes them on the streamer's PC; this module
reads them back for highlight detection: the chat and the streamer's markers become
:class:`~stream2clip.chat.ChatMessage` s timed from the start of the stream, OBS's scenes
become time spans, and VTube Studio's model outline, placed where OBS shows it, becomes
the avatar box of a vertical layout. Readers skip event types they do not know.
"""

from __future__ import annotations

import json
import math
import os
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

import numpy as np

from .chat import ChatMessage
from .geometry import Region

__all__ = [
    "SCHEMA", "SessionEvent", "SessionWriter", "Session", "SceneSpan", "load_session", "is_session",
    "ItemPlacement", "item_placement", "vts_to_source", "avatar_region", "skip_scenes", "ORIGINS",
]

SCHEMA = "stream2clip.session/v1"
#: What "time 0" of a session is: when OBS started streaming, when it started recording, when the session began; "auto" takes the first of those that happened.
ORIGINS = ("auto", "stream", "record", "session")
#: The marker word a hotkey or button marker becomes in the chat (a word every marker list has by default).
MARKER_WORD = "!clip"


@dataclass(frozen=True)
class SessionEvent:
    t: float
    type: str
    data: dict[str, Any] = field(default_factory=dict)


def _finite(value: Any) -> bool:
    return not isinstance(value, float) or math.isfinite(value)


def _clean(value: Any) -> Any:
    """JSON without NaN / infinity (not valid JSON; an entry holding one is left out) and with short floats."""
    if isinstance(value, float):
        return round(value, 4) if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items() if _finite(v)}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    return value


class SessionWriter:
    """Append events to a session file, one flushed line each, from any thread."""

    def __init__(
        self,
        path: str | os.PathLike[str],
        *,
        app: str | None = None,
        sources: dict[str, str] | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        from . import __version__

        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._clock = clock
        self._lock = threading.Lock()
        self.started = clock()
        self.counts: dict[str, int] = {}
        self._fh = self.path.open("w", encoding="utf-8", newline="\n")
        header = {"schema": SCHEMA, "started": self.started, "app": app or f"stream2clip {__version__}", "sources": dict(sources or {})}
        self._line(header)

    def _line(self, obj: dict[str, Any]) -> None:
        self._fh.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n")
        self._fh.flush()

    def write(self, type: str, t: float | None = None, **data: Any) -> dict[str, Any]:
        """Write one event (``t`` defaults to now) and return it."""
        if not re.fullmatch(r"[a-z_]+", type):
            raise ValueError(f"Event types are lower-case words: {type!r}")
        when = self._clock() if t is None or not math.isfinite(t) else float(t)
        event = {"t": round(when, 3), "type": type, **_clean(data)}
        with self._lock:
            if self._fh.closed:
                raise ValueError("The session file is closed")
            self._line(event)
            self.counts[type] = self.counts.get(type, 0) + 1
        return event

    def chat(self, message: ChatMessage) -> dict[str, Any]:
        """A chat message as it arrived; one without a time of its own happened now."""
        data: dict[str, Any] = {"text": message.text, "author": message.author, "kind": message.kind}
        if message.amount:
            data["amount"] = message.amount
            data["currency"] = message.currency
        if message.emotes:
            data["emotes"] = list(message.emotes)
        if message.role:
            data["role"] = message.role
        return self.write("chat", message.time, **data)

    def close(self) -> None:
        with self._lock:
            if not self._fh.closed:
                self._fh.close()

    def __enter__(self) -> "SessionWriter":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


@dataclass(frozen=True)
class SceneSpan:
    start: float
    end: float
    name: str


@dataclass
class Session:
    path: Path
    started: float
    app: str = ""
    sources: dict[str, str] = field(default_factory=dict)
    events: list[SessionEvent] = field(default_factory=list)

    def of(self, *types: str) -> list[SessionEvent]:
        return [e for e in self.events if e.type in types]

    def output_starts(self, output: str) -> list[float]:
        return [e.t for e in self.events if e.type == "output" and e.data.get("output") == output and e.data.get("active")]

    def origin(self, which: str = "auto") -> float:
        """The wall-clock time that is second 0 of the video the session goes with.

        "stream": when OBS started streaming (a platform's VOD starts there), "record": when it
        started recording (a local recording), "session": when the session began. "auto" takes
        the stream, else the recording, else the session.
        """
        if which not in ORIGINS:
            raise ValueError(f"Unknown origin {which!r}; choose one of {', '.join(ORIGINS)}")
        if which in ("auto", "stream") and self.output_starts("stream"):
            return self.output_starts("stream")[0]
        if which == "stream":
            raise ValueError(f"{self.path.name}: OBS did not start streaming while the session was recorded; choose another origin")
        if which in ("auto", "record") and self.output_starts("record"):
            return self.output_starts("record")[0]
        if which == "record":
            raise ValueError(f"{self.path.name}: OBS did not start recording while the session was recorded; choose another origin")
        return self.started

    @property
    def end(self) -> float:
        return max([self.started] + [e.t for e in self.events])

    def messages(self, origin: float | None = None, *, marker_delay: float = 8.0) -> list[ChatMessage]:
        """The chat and the streamer's markers, timed in seconds from ``origin`` (default: :meth:`origin`).

        A hotkey or button marker is pressed at the moment, while chat comes ``marker_delay``
        seconds after it; the marker is moved by that much so that highlight detection, which
        takes the delay off every chat marker, lands on the press. A marker left by viewers'
        votes is chat itself and keeps its time.
        """
        zero = self.origin() if origin is None else origin
        found: list[ChatMessage] = []
        for e in self.events:
            if e.type == "chat":
                d = e.data
                found.append(ChatMessage(
                    time=e.t - zero, text=str(d.get("text") or ""), author=str(d.get("author") or ""), kind=str(d.get("kind") or "text"),
                    amount=float(d.get("amount") or 0.0), currency=d.get("currency"), emotes=tuple(d.get("emotes") or ()), role=str(d.get("role") or ""),
                ))
            elif e.type == "marker":
                shift = 0.0 if e.data.get("by") == "viewers" else marker_delay
                found.append(ChatMessage(time=e.t - zero + shift, text=MARKER_WORD, author="", role="owner"))
        found.sort(key=lambda m: m.time)
        return [m for m in found if m.time >= 0]

    def scenes(self, origin: float | None = None) -> list[SceneSpan]:
        """The OBS program scene over time, in seconds from ``origin``."""
        zero = self.origin() if origin is None else origin
        changes = [(e.t - zero, str(e.data.get("name") or "")) for e in self.events if e.type == "scene"]
        spans: list[SceneSpan] = []
        end = self.end - zero
        for i, (start, name) in enumerate(changes):
            stop = changes[i + 1][0] if i + 1 < len(changes) else end
            if stop > max(start, 0.0):
                spans.append(SceneSpan(max(start, 0.0), stop, name))
        return spans


def is_session(text_or_path: str | os.PathLike[str]) -> bool:
    """Whether a file (or its first line) is a session file."""
    if isinstance(text_or_path, os.PathLike) or (isinstance(text_or_path, str) and "\n" not in text_or_path and not text_or_path.lstrip().startswith("{")):
        try:
            with Path(text_or_path).open("r", encoding="utf-8-sig") as fh:
                first = fh.readline()
        except OSError:
            return False
    else:
        first = str(text_or_path).lstrip("﻿").split("\n", 1)[0]
    try:
        head = json.loads(first)
    except ValueError:
        return False
    return isinstance(head, dict) and head.get("schema") == SCHEMA


def load_session(path: str | os.PathLike[str]) -> Session:
    """Read a session file; a line cut off by a crash at the end is left out."""
    p = Path(path)
    lines = p.read_text(encoding="utf-8-sig").splitlines()
    if not lines:
        raise ValueError(f"{p.name} is empty")
    try:
        head = json.loads(lines[0])
    except ValueError as exc:
        raise ValueError(f"{p.name} is not a stream2clip session file") from exc
    if not isinstance(head, dict) or head.get("schema") != SCHEMA:
        found = head.get("schema") if isinstance(head, dict) else None
        raise ValueError(f"{p.name} is not a stream2clip session file" + (f" (schema {found!r}, expected {SCHEMA!r})" if found else ""))
    events: list[SessionEvent] = []
    for number, raw in enumerate(lines[1:], start=2):
        if not raw.strip():
            continue
        try:
            obj = json.loads(raw)
        except ValueError:
            if number == len(lines):
                break  # the last line was being written when the program stopped
            raise ValueError(f"{p.name}, line {number}: not JSON") from None
        if not isinstance(obj, dict) or not isinstance(obj.get("t"), (int, float)) or not isinstance(obj.get("type"), str):
            continue
        data = {k: v for k, v in obj.items() if k not in ("t", "type")}
        events.append(SessionEvent(float(obj["t"]), obj["type"], data))
    events.sort(key=lambda e: e.t)
    return Session(p, float(head["started"]), str(head.get("app") or ""), dict(head.get("sources") or {}), events)


# --------------------------------------------------------------------------- where OBS shows VTube Studio

ALIGN_LEFT, ALIGN_RIGHT, ALIGN_TOP, ALIGN_BOTTOM = 1, 2, 4, 8


@dataclass(frozen=True)
class ItemPlacement:
    """How a source's pixels land on the OBS canvas: ``canvas = (left + (x - crop_left) * scale_x, top + (y - crop_top) * scale_y)``."""

    source_size: tuple[float, float]
    left: float
    top: float
    scale_x: float
    scale_y: float
    crop_left: float = 0.0
    crop_top: float = 0.0
    #: The part of the canvas the source is visible in (x0, y0, x1, y1).
    visible: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)

    def to_canvas(self, points: np.ndarray) -> np.ndarray:
        pts = np.asarray(points, dtype=np.float64).reshape(-1, 2)
        return np.column_stack((self.left + (pts[:, 0] - self.crop_left) * self.scale_x, self.top + (pts[:, 1] - self.crop_top) * self.scale_y))


def _offset(alignment: int, width: float, height: float) -> tuple[float, float]:
    dx = 0.0 if alignment & ALIGN_LEFT else (width if alignment & ALIGN_RIGHT else width / 2)
    dy = 0.0 if alignment & ALIGN_TOP else (height if alignment & ALIGN_BOTTOM else height / 2)
    return dx, dy


def item_placement(transform: dict[str, Any]) -> ItemPlacement:
    """Where an OBS scene item's pixels land on the canvas, from obs-websocket's ``sceneItemTransform``.

    Follows libobs: the crop comes off the source first, then the scale (or the bounds box and
    its type) sizes it, and the alignment says which point of the box ``position`` is. Rotated
    and mirrored items are refused - give the box by hand for those.
    """
    def num(key: str, default: float = 0.0) -> float:
        value = transform.get(key, default)
        return float(value) if isinstance(value, (int, float)) else default

    rotation = num("rotation") % 360
    if min(rotation, 360 - rotation) > 0.01:
        raise ValueError(f"The VTube Studio source is rotated ({rotation:g} degrees); give the avatar box by hand")
    sw, sh = num("sourceWidth"), num("sourceHeight")
    cl, cr, ct, cb = num("cropLeft"), num("cropRight"), num("cropTop"), num("cropBottom")
    cw, ch = sw - cl - cr, sh - ct - cb
    if cw <= 0 or ch <= 0:
        raise ValueError("The VTube Studio source has no size in OBS (is it showing anything?)")
    alignment = int(num("alignment", ALIGN_LEFT | ALIGN_TOP))
    px, py = num("positionX"), num("positionY")
    bounds = str(transform.get("boundsType") or "OBS_BOUNDS_NONE")
    if bounds == "OBS_BOUNDS_NONE":
        sx, sy = num("scaleX", 1.0), num("scaleY", 1.0)
        if sx <= 0 or sy <= 0:
            raise ValueError("The VTube Studio source is mirrored in OBS; give the avatar box by hand")
        w, h = cw * sx, ch * sy
        dx, dy = _offset(alignment, w, h)
        left, top = px - dx, py - dy
        visible = (left, top, left + w, top + h)
    else:
        bw, bh = num("boundsWidth"), num("boundsHeight")
        if bw <= 0 or bh <= 0:
            raise ValueError("The VTube Studio source has an empty bounding box in OBS")
        inner, outer = min(bw / cw, bh / ch), max(bw / cw, bh / ch)
        fixed = {
            "OBS_BOUNDS_STRETCH": (bw / cw, bh / ch),
            "OBS_BOUNDS_SCALE_INNER": (inner, inner),
            "OBS_BOUNDS_SCALE_OUTER": (outer, outer),
            "OBS_BOUNDS_SCALE_TO_WIDTH": (bw / cw, bw / cw),
            "OBS_BOUNDS_SCALE_TO_HEIGHT": (bh / ch, bh / ch),
            "OBS_BOUNDS_MAX_ONLY": (min(1.0, inner), min(1.0, inner)),
        }
        if bounds not in fixed:
            raise ValueError(f"Unknown OBS bounding box type {bounds!r}")
        sx, sy = fixed[bounds]
        w, h = cw * sx, ch * sy
        bdx, bdy = _offset(alignment, bw, bh)
        box_left, box_top = px - bdx, py - bdy
        inside = int(num("boundsAlignment", 0))
        cdx = 0.0 if inside & ALIGN_LEFT else (bw - w if inside & ALIGN_RIGHT else (bw - w) / 2)
        cdy = 0.0 if inside & ALIGN_TOP else (bh - h if inside & ALIGN_BOTTOM else (bh - h) / 2)
        left, top = box_left + cdx, box_top + cdy
        visible = (left, top, left + w, top + h)
        if transform.get("cropToBounds") or bounds == "OBS_BOUNDS_SCALE_OUTER":
            visible = (max(left, box_left), max(top, box_top), min(left + w, box_left + bw), min(top + h, box_top + bh))
    return ItemPlacement((sw, sh), left, top, sx, sy, cl, ct, visible)


def vts_to_source(points: np.ndarray, source_size: tuple[float, float]) -> np.ndarray:
    """VTube Studio window coordinates (x -1..1 left to right, y -1..1 bottom to top) -> source pixels."""
    pts = np.asarray(points, dtype=np.float64).reshape(-1, 2)
    w, h = source_size
    return np.column_stack(((pts[:, 0] + 1) / 2 * w, (1 - pts[:, 1]) / 2 * h))


def avatar_region(
    session: Session,
    video_size: tuple[int, int],
    *,
    aspect: float,
    origin: float | None = None,
    spans: Sequence[tuple[float, float]] = (),
    vts_region: Region | None = None,
    margin: float = 0.06,
) -> Region | None:
    """The avatar box for a vertical layout, from VTube Studio's model outline while the session ran.

    The outline is placed in the video where OBS showed VTube Studio (the session's
    ``avatar_source`` and ``obs_video`` events) or, with ``vts_region``, in that box of the
    video. Only outlines inside ``spans`` (seconds from ``origin``) count when spans are given.
    The box keeps ``aspect`` (width / height) and starts just above the top of the model, so a
    model taller than the box shows head and shoulders. ``None`` when nothing can be placed.
    """
    vw, vh = video_size
    zero = session.origin() if origin is None else origin
    placement: ItemPlacement | None = None
    scale = (1.0, 1.0)
    boxes: list[tuple[float, float, float, float]] = []
    for e in session.events:
        if e.type == "obs_video":
            base = e.data.get("base") or [0, 0]
            if base[0] and base[1]:
                scale = (vw / float(base[0]), vh / float(base[1]))
        elif e.type == "avatar_source" and vts_region is None:
            try:
                placement = item_placement(e.data.get("transform") or {})
            except ValueError:
                placement = None
        elif e.type == "avatar_outline":
            hull = e.data.get("hull") or []
            if len(hull) < 3 or (spans and not any(a <= e.t - zero <= b for a, b in spans)):
                continue
            if vts_region is not None:
                pts = vts_to_source(np.asarray(hull), (vts_region.width, vts_region.height)) + (vts_region.x, vts_region.y)
                clip = (vts_region.x, vts_region.y, vts_region.x + vts_region.width, vts_region.y + vts_region.height)
            elif placement is not None:
                pts = placement.to_canvas(vts_to_source(np.asarray(hull), placement.source_size)) * scale
                v = placement.visible
                clip = (v[0] * scale[0], v[1] * scale[1], v[2] * scale[0], v[3] * scale[1])
            else:
                continue
            x0, y0 = max(pts[:, 0].min(), clip[0], 0), max(pts[:, 1].min(), clip[1], 0)
            x1, y1 = min(pts[:, 0].max(), clip[2], vw), min(pts[:, 1].max(), clip[3], vh)
            if x1 - x0 >= 4 and y1 - y0 >= 4:
                boxes.append((x0, y0, x1, y1))
    if not boxes:
        return None
    arr = np.asarray(boxes)
    # Where the model usually is: a stray frame (a jump, a moment off screen) does not stretch the box.
    x0, y0 = np.percentile(arr[:, 0], 5), np.percentile(arr[:, 1], 5)
    x1, y1 = np.percentile(arr[:, 2], 95), np.percentile(arr[:, 3], 95)
    width, height = x1 - x0, y1 - y0
    box_w, box_h = width * (1 + margin), width * (1 + margin) / aspect
    if box_h > height * (1 + margin):  # a wide, short model (or a crop): fit the height instead
        box_h = height * (1 + margin)
        box_w = box_h * aspect
    # Whole, even sizes (what the encoders want) that keep the aspect, inside the video.
    w = max(2, min(int(round(box_w)), vw, int(vh * aspect)) // 2 * 2)
    h = max(2, min(int(round(w / aspect)), vh) // 2 * 2)
    cx = (x0 + x1) / 2
    left = int(round(min(max(0.0, cx - w / 2), vw - w)))
    top = int(round(min(max(0.0, y0 - h * margin / 2), vh - h)))
    return Region(left, top, w, h)


def skip_scenes(highlights: Iterable[Any], scenes: Sequence[SceneSpan], names: Sequence[str], *, mostly: float = 0.5) -> list[Any]:
    """The highlights that are not ``mostly`` inside a scene whose name contains one of ``names`` (case does not matter)."""
    words = [n.strip().lower() for n in names if n.strip()]
    skipped = [s for s in scenes if any(w in s.name.lower() for w in words)]
    kept = []
    for h in highlights:
        inside = sum(max(0.0, min(h.end, s.end) - max(h.start, s.start)) for s in skipped)
        if inside < mostly * max(h.end - h.start, 1e-9):
            kept.append(h)
    return kept
