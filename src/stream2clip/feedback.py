"""A local record of which highlight candidates were kept and which were left out.

Every export from the highlights window (clips, or the cut list for an editing program) adds one
line to ``feedback.jsonl`` in the app's settings folder: the stream, and for each candidate its
span as found, its span as exported, its score and reasons, and whether it was kept. Nothing leaves
the PC. The record is what lets detection be tuned to a channel (``evaluate --feedback``): kept
candidates are the moments this editor wanted, left-out ones the moments they did not.

The window's setting turns it off; ``stream2clip feedback --clear`` deletes it.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

if TYPE_CHECKING:
    from .highlights import Highlight

__all__ = ["SCHEMA", "default_path", "record", "load", "choices", "summary"]

SCHEMA = "stream2clip.feedback/v1"


def default_path() -> Path:
    """``feedback.jsonl`` in the app's settings folder (``STREAM2CLIP_CONFIG_DIR`` moves it)."""
    from .gui.settings import config_dir  # no Qt: the settings module is plain Python

    return config_dir() / "feedback.jsonl"


def record(
    path: str | os.PathLike[str] | None,
    highlights: "Sequence[Highlight]",
    kept: Sequence[bool],
    *,
    found: "Sequence[tuple[float, float] | None] | None" = None,
    source: dict[str, Any] | None = None,
    video: str = "",
    duration: float | None = None,
    action: str = "clips",
    effects: str = "",
    now: datetime | None = None,
) -> Path:
    """Add one export to the record. ``found`` holds each candidate's span before it was moved by hand;
    ``effects`` is the effect preset the clips were made with, so the record says which effects people kept."""
    if len(kept) != len(highlights) or (found is not None and len(found) != len(highlights)):
        raise ValueError("kept (and found) need one entry per highlight")
    out = Path(path) if path is not None else default_path()
    candidates = []
    for index, (h, keep) in enumerate(zip(highlights, kept)):
        span = found[index] if found is not None else None
        candidates.append({
            "rank": h.rank, "start": round(h.start, 2), "end": round(h.end, 2), "peak": round(h.peak, 2), "score": round(h.score, 3),
            "reasons": list(h.reasons), "kept": bool(keep),
            "found": [round(span[0], 2), round(span[1], 2)] if span is not None else None,
            "moved": span is not None and (abs(span[0] - h.start) >= 0.5 or abs(span[1] - h.end) >= 0.5),
        })
    entry = {
        "schema": SCHEMA, "at": (now or datetime.now(timezone.utc)).isoformat(timespec="seconds"), "action": action,
        "source": {k: v for k, v in (source or {}).items() if k in ("url", "title", "channel") and v},
        "video": Path(video).name if video else "", "duration": round(duration, 1) if duration else None, "effects": effects or "off",
        "candidates": candidates,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return out


def load(path: str | os.PathLike[str] | None = None) -> list[dict[str, Any]]:
    """The exports in the record, oldest first; lines that are not readable are skipped."""
    p = Path(path) if path is not None else default_path()
    if not p.is_file():
        return []
    entries = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if isinstance(entry, dict) and entry.get("schema") == SCHEMA:
            entries.append(entry)
    return entries


def _same_stream(entry: dict[str, Any], *, url: str = "", video: str = "") -> bool:
    source = entry.get("source") or {}
    if source.get("url"):  # file names repeat (fetch saves video.mp4): with an address, only the address counts
        return bool(url) and source["url"] == url
    return bool(video) and entry.get("video") == Path(video).name


def choices(entries: Sequence[dict[str, Any]], *, url: str = "", video: str = "") -> list[tuple[float, float, bool]]:
    """``(start, end, kept)`` for one stream, as exported last: a later export of the same stream replaces earlier ones."""
    latest: dict[tuple[float, float], tuple[float, float, bool]] = {}
    for entry in entries:
        if not _same_stream(entry, url=url, video=video):
            continue
        for c in entry.get("candidates") or []:
            key = tuple(c.get("found") or (c["start"], c["end"]))
            latest[key] = (float(c["start"]), float(c["end"]), bool(c.get("kept")))
    return sorted(latest.values())


def summary(entries: Sequence[dict[str, Any]]) -> list[str]:
    """One line per stream: how many exports, candidates kept of those offered, and spans moved by hand."""
    streams: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        name = (entry.get("source") or {}).get("title") or (entry.get("source") or {}).get("url") or entry.get("video") or "?"
        streams.setdefault(name, []).append(entry)
    lines = []
    for name, group in streams.items():
        offered = [c for entry in group for c in entry.get("candidates") or []]
        kept = sum(1 for c in offered if c.get("kept"))
        moved = sum(1 for c in offered if c.get("moved"))
        lines.append(f"{name}: {len(group)} exports, kept {kept} of {len(offered)}, moved {moved}")
    return lines
