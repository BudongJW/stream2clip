"""How good are the highlights? Compare them with the moments viewers pointed at.

Viewers leave timestamps in the comments of a stream archive ("1:23:45 here she falls
off the cliff"). They are not a ground truth, but they are picked by people, cost
nothing, and exist for most popular archives - a usable yardstick for the detector's
defaults across many streams instead of tuning on one::

    stream2clip fetch URL -o data/STREAM --comments 150
    stream2clip evaluate data/*

The numbers:

``precision``  share of highlights that contain a viewer-marked moment
``recall``     share of marked moments that fall inside some highlight
``chance``     the precision highlights of the same lengths would get if placed at random
``lift``       precision / chance - above 1 means better than random placement
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Sequence

if TYPE_CHECKING:
    from .highlights import HighlightConfig

__all__ = [
    "Label", "Score", "StreamData", "comment_timestamps", "labels_from_comments", "score_highlights", "combine_scores",
    "load_stream", "evaluate_streams", "parse_sweep", "add_feedback", "f1", "gain", "tune", "held_out",
]

# 1:23:45 or 23:45 - not part of a longer run of digits/colons such as a clock date or a ratio list
_STAMP = re.compile(r"(?<![\d:.])(?:(\d{1,2}):)?(\d{1,2}):(\d{2})(?![\d:])")


@dataclass(frozen=True)
class Label:
    """A moment viewers marked; ``votes`` is how many different comments marked it."""

    time: float
    votes: int = 1


@dataclass(frozen=True)
class Score:
    highlights: int
    labels: int
    hits: int  # highlights that contain a label
    found: int  # labels inside some highlight
    chance: float

    @property
    def precision(self) -> float:
        return self.hits / self.highlights if self.highlights else 0.0

    @property
    def recall(self) -> float:
        return self.found / self.labels if self.labels else 0.0

    @property
    def lift(self) -> float:
        return self.precision / self.chance if self.chance > 0 else 0.0


def comment_timestamps(text: str, duration: float | None = None) -> list[float]:
    """The timestamps written in one comment, in seconds (those beyond the stream's end are dropped)."""
    found = []
    for hours, minutes, seconds in _STAMP.findall(text):
        if int(seconds) >= 60 or (hours and int(minutes) >= 60):
            continue
        value = int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds)
        if duration is None or value <= duration:
            found.append(float(value))
    return found


def labels_from_comments(comments: Iterable[Any], *, duration: float | None = None, gap: float = 20.0, min_votes: int = 1) -> list[Label]:
    """Group the timestamps of all comments into moments.

    ``comments`` are strings or yt-dlp comment objects (``{"text": ...}``). Timestamps within
    ``gap`` seconds of each other are one moment, placed at their median; a comment counts once
    per moment however often it repeats it.
    """
    stamps: list[tuple[float, int]] = []
    for index, comment in enumerate(comments):
        text = comment.get("text", "") if isinstance(comment, dict) else str(comment)
        stamps += [(t, index) for t in comment_timestamps(text or "", duration)]
    stamps.sort()
    groups: list[list[tuple[float, int]]] = []
    for stamp in stamps:
        if groups and stamp[0] - groups[-1][-1][0] <= gap:
            groups[-1].append(stamp)
        else:
            groups.append([stamp])
    labels = []
    for group in groups:
        times = sorted(t for t, _ in group)
        votes = len({author for _, author in group})
        if votes >= min_votes:
            labels.append(Label(times[len(times) // 2], votes))
    return labels


def _union_length(intervals: Sequence[tuple[float, float]], low: float, high: float) -> float:
    total, edge = 0.0, low
    for start, end in sorted(intervals):
        start, end = max(start, edge), min(end, high)
        if end > start:
            total += end - start
            edge = end
    return total


def score_highlights(highlights: Sequence[Any], labels: Sequence[Label], duration: float, *, tolerance: float = 10.0) -> Score:
    """Compare highlights (anything with ``start`` / ``end``) with marked moments.

    A highlight "hits" when a label lies inside it, give or take ``tolerance`` seconds.
    ``chance`` answers "how often would a span this long hit if dropped anywhere in the
    stream?" - with many labels or long highlights a high precision means little.
    """
    times = [label.time for label in labels]
    hits = sum(1 for h in highlights if any(h.start - tolerance <= t <= h.end + tolerance for t in times))
    found = sum(1 for t in times if any(h.start - tolerance <= t <= h.end + tolerance for h in highlights))
    chances = []
    for h in highlights:
        length = max(0.0, h.end - h.start)
        room = max(duration - length, 1e-9)
        # start positions s in [0, duration - length] for which [s, s + length] would contain a label
        chances.append(min(1.0, _union_length([(t - length - tolerance, t + tolerance) for t in times], 0.0, room) / room))
    chance = sum(chances) / len(chances) if chances else 0.0
    return Score(len(highlights), len(labels), hits, found, chance)


def combine_scores(scores: Sequence[Score]) -> Score:
    """Pool several streams: counts are added, ``chance`` is averaged by the number of highlights."""
    highlights = sum(s.highlights for s in scores)
    chance = sum(s.chance * s.highlights for s in scores) / highlights if highlights else 0.0
    return Score(highlights, sum(s.labels for s in scores), sum(s.hits for s in scores), sum(s.found for s in scores), chance)


@dataclass
class StreamData:
    """One stream of an evaluation set: its chat, its length and the moments viewers marked."""

    name: str
    messages: list
    duration: float
    labels: list[Label]
    #: The most-replayed curve of the info JSON (empty when YouTube has none for the stream).
    heatmap: list = field(default_factory=list)
    #: Loudness per second, when the folder holds the video and ``sound`` was asked for.
    levels: Any = None
    url: str = ""
    #: Chat counted into buckets once, for the many detections of tuning (see ``detect_highlights``).
    cache: dict = field(default_factory=dict, repr=False, compare=False)


def _sound_of(root: Path) -> Any:
    """Loudness per second of the video in ``root``, kept next to it as ``<name>.levels1s.npy``; ``None`` without a video."""
    import numpy as np

    videos = sorted(path for ext in ("*.mp4", "*.mkv", "*.webm", "*.mov") for path in root.glob(ext))
    if not videos:
        return None
    cached = videos[0].with_name(videos[0].stem + ".levels1s.npy")
    if cached.is_file():
        return np.load(cached)
    from .audio import audio_levels

    levels = audio_levels(videos[0], window=1.0)
    np.save(cached, levels)
    return levels


def load_stream(folder: str | os.PathLike[str], *, min_votes: int = 1, sound: bool = False) -> StreamData:
    """Read a folder made by ``stream2clip fetch URL -o FOLDER --comments N`` (chat replay + info JSON with comments).

    With ``sound`` the loudness of a video in the folder is read too (once; it is kept as ``*.levels1s.npy``).
    """
    from .chat import load_chat

    root = Path(folder)
    chats = sorted([*root.glob("*.live_chat.json"), *root.glob("*.chat.jsonl"), *root.glob("chat.*")])
    infos = sorted([*root.glob("info.json"), *root.glob("*.info.json")])
    if not chats:
        raise ValueError(f"{root}: no chat replay (*.live_chat.json, *.chat.jsonl)")
    if not infos:
        raise ValueError(f"{root}: no info.json")
    loaded = [json.loads(path.read_text(encoding="utf-8")) for path in infos]
    info = next((data for data in loaded if data.get("comments")), loaded[0])  # the one fetched with --comments, if there are several
    messages = load_chat(chats[0])
    duration = float(info.get("duration") or (max((m.time for m in messages), default=0.0)))
    labels = labels_from_comments(info.get("comments") or [], duration=duration, min_votes=min_votes)
    from .sources import heatmap_from_info

    url = str(info.get("webpage_url") or info.get("original_url") or "")
    return StreamData(root.name, messages, duration, labels, heatmap_from_info(info), _sound_of(root) if sound else None, url)


def evaluate_streams(
    streams: Sequence[StreamData],
    config: "HighlightConfig | None" = None,
    *,
    tolerance: float = 10.0,
    heatmap: bool = False,
    sound: bool = False,
) -> tuple[list[tuple[str, Score]], Score]:
    """Detect highlights in every stream and score them: ``([(name, score)...], pooled score)``.

    From the chat alone unless ``heatmap`` (the most-replayed curve) or ``sound`` (a stream's loudness,
    see :func:`load_stream`) are added.
    """
    from .highlights import HighlightConfig, detect_highlights

    cfg = config or HighlightConfig()
    rows = []
    for stream in streams:
        result = detect_highlights(stream.messages, duration=stream.duration, config=cfg, heatmap=stream.heatmap if heatmap else (),
                                   audio=stream.levels if sound else None, audio_window=1.0, cache=stream.cache)
        rows.append((stream.name, score_highlights(result.highlights, stream.labels, stream.duration, tolerance=tolerance)))
    return rows, combine_scores([score for _, score in rows])


def add_feedback(streams: Sequence[StreamData], entries: Sequence[dict]) -> int:
    """Add the candidates kept in the app's record (:mod:`stream2clip.feedback`) as marked moments; returns how many."""
    from .feedback import choices

    added = 0
    for stream in streams:
        kept = [Label((start + end) / 2, 1) for start, end, keep in choices(entries, url=stream.url) if keep]
        stream.labels = sorted([*stream.labels, *kept], key=lambda label: label.time)
        added += len(kept)
    return added


def f1(score: Score) -> float:
    """Highlights that hit marked moments and moments the highlights catch, together (reported, not tuned for)."""
    p, r = score.precision, score.recall
    return 2 * p * r / (p + r) if p + r else 0.0


def gain(score: Score) -> float:
    """What tuning aims at: how much more often the highlights hit a marked moment than spans of the same
    lengths dropped at random would. Longer or more highlights hit more by chance too, so they do not pay."""
    return score.precision - score.chance


#: The chat signals whose weights tuning changes (the heatmap and loudness too when they are used).
TUNED_WEIGHTS = ("rate", "unique", "reactions", "paid")


def tune(
    streams: Sequence[StreamData],
    base: "HighlightConfig",
    *,
    trials: int = 300,
    seed: int = 1,
    tolerance: float = 10.0,
    heatmap: bool = False,
    sound: bool = False,
) -> tuple["HighlightConfig", Score]:
    """Random search for the settings that score best on these streams (:func:`gain` of the pooled score).

    The weights of the chat signals (and of the heatmap and the loudness when they are used) take values
    from 0 to 0.6, the threshold from 1.2 to 2.8 and the chat delay from 4 to 16 seconds. ``base`` is
    tried first, so the result is never worse than it on these streams.
    """
    import random

    rng = random.Random(seed)
    names = [*TUNED_WEIGHTS, *(["heatmap"] if heatmap else []), *(["audio"] if sound else [])]
    best_cfg, best = base, evaluate_streams(streams, base, tolerance=tolerance, heatmap=heatmap, sound=sound)[1]
    for _ in range(trials):
        weights = dict(base.weights)
        weights.update({name: round(rng.uniform(0.0, 0.6), 3) for name in names})
        if not any(weights[name] for name in TUNED_WEIGHTS):
            continue
        cfg = replace(base, weights=weights, threshold=round(rng.uniform(1.2, 2.8), 2), chat_delay=round(rng.uniform(4.0, 16.0), 1))
        pooled = evaluate_streams(streams, cfg, tolerance=tolerance, heatmap=heatmap, sound=sound)[1]
        if gain(pooled) > gain(best):
            best_cfg, best = cfg, pooled
    return best_cfg, best


def held_out(streams: Sequence[StreamData], base: "HighlightConfig", **options: Any) -> tuple[Score, Score]:
    """How tuning does on a stream it has not seen: each stream is scored with the settings tuned on the
    others (leave one out). Returns ``(base, tuned)`` pooled over the held-out streams."""
    flags = {key: options[key] for key in ("tolerance", "heatmap", "sound") if key in options}
    plain, tuned = [], []
    for index, stream in enumerate(streams):
        others = [s for i, s in enumerate(streams) if i != index]
        cfg, _ = tune(others, base, **options)
        plain.append(evaluate_streams([stream], base, **flags)[1])
        tuned.append(evaluate_streams([stream], cfg, **flags)[1])
    return combine_scores(plain), combine_scores(tuned)


def parse_sweep(text: str, config: "HighlightConfig") -> list[tuple[str, "HighlightConfig"]]:
    """``"threshold=1.5,2,2.5"`` -> one labelled config per value (the field must exist and be a number)."""
    name, _, values = text.partition("=")
    name = name.strip().replace("-", "_")
    name = {"delay": "chat_delay"}.get(name, name)
    current = getattr(config, name, None)
    if not values or isinstance(current, bool) or not isinstance(current, (int, float)):
        raise ValueError(f"Cannot sweep {text!r}: use NAME=V1,V2 with a numeric setting such as threshold, delay, lead, tail, window, top")
    kind = int if isinstance(current, int) else float
    return [(f"{name}={kind(float(v))}", replace(config, **{name: kind(float(v))})) for v in values.split(",") if v.strip()]
