"""Effects at a highlight's peak: a punch-in zoom, a word that pops in the captions, a reaction tag.

Clip editors in Japan, Korea and China keep effects sparse and put them on the punchline: an
emphasis caption, a short close-up, a sound on the same frame (reports/클립 특수효과 레퍼런스.md).
This module plans that from what stream2clip already knows about a highlight: where chat peaked,
the sound onset next to it (the same one the automatic sound effect snaps to), the expression
hotkey the streamer pressed (session files), the dominant chat reaction, and word-timed captions.

A plan is a small set of effects under a budget (one hero effect, at most two secondary ones),
anchored to one moment, and skipped when that moment is not clear. It becomes ffmpeg filters (the
zoom, placed after the silence cut and before the captions so the text stays sharp) and ASS
caption events (the emphasised word, the tag). Presets are JSON (``schemas/effects.v1.schema.json``):
``off``, ``subtle`` and ``variety`` are built in, and a file of the same shape can replace them.

Phase 1 of the plan in that report: shakes, flashes, emoji and speed lines come later, and the
flash guard (WCAG 2.3.1, ITU-R BT.1702) comes with the first effect that can flash.
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Sequence

import numpy as np

if TYPE_CHECKING:
    from .subtitles import Cue

__all__ = [
    "PRESETS", "EFFECT_TYPES", "Tag", "EffectPlan", "builtin_preset", "load_preset", "check_preset", "available_filters",
    "zoom_filters", "prominent_words", "plan_effects",
]

#: What a preset may contain in this version, and the ffmpeg filters each needs.
EFFECT_TYPES: dict[str, tuple[str, ...]] = {
    "zoom": ("scale", "crop"),
    "caption_emphasis": ("subtitles",),
    "caption_tag": ("subtitles",),
}
ANCHORS = ("vts_hotkey", "onset", "peak")
REACTIONS = ("laugh", "shock", "cute", "hype")

_ZOOM_SUBTLE = {
    "id": "peak_punch_in", "type": "zoom", "group": "hero",
    "anchor": {"order": ["vts_hotkey", "onset"], "skip_if_none": True},
    "scale": 1.12, "in_ms": 120, "hold_max_ms": 2500, "out_ms": 400,
    "by_reaction": {"laugh": {"scale": 1.08, "in_ms": 300}, "cute": {"scale": 1.05, "in_ms": 1500}, "hype": None},
    "reduced_motion": "emphasis",
}
_EMPHASIS = {"id": "emphasis_word", "type": "caption_emphasis", "group": "secondary", "window_ms": [-2000, 1500], "max_words": 1,
             "scale": 1.25, "pop_ms": 220}
_TAG = {
    "id": "reaction_tag", "type": "caption_tag", "group": "secondary", "min_share": 0.4, "min_count": 5, "duration_ms": 1200,
    "text": {"ko": {"laugh": "ㅋㅋㅋ"}, "ja": {"laugh": "草"}, "en": {"laugh": "LOL"}, "*": {"shock": "!?", "cute": "♡", "hype": "!!"}},
}
#: The built-in presets (numbers are the report's proposals, to be tuned with real clips).
PRESETS: dict[str, dict[str, Any]] = {
    "off": {"schema_version": 1, "id": "s2c.off", "name": "off", "effects": []},
    "subtle": {
        "schema_version": 1, "id": "s2c.subtle", "name": "subtle",
        "budget": {"max_hero": 1, "max_secondary": 2}, "skip_in_teaser": True,
        "effects": [_ZOOM_SUBTLE, _EMPHASIS],
    },
    "variety": {
        "schema_version": 1, "id": "s2c.variety", "name": "variety",
        "budget": {"max_hero": 1, "max_secondary": 2}, "skip_in_teaser": True,
        "effects": [
            {**_ZOOM_SUBTLE, "scale": 1.15, "by_reaction": {"laugh": {"scale": 1.1, "in_ms": 250}, "shock": {"scale": 1.2, "in_ms": 100},
                                                          "cute": {"scale": 1.06, "in_ms": 1200}, "hype": None}},
            {**_EMPHASIS, "max_words": 2},
            _TAG,
        ],
    },
}


def builtin_preset(name: str) -> dict[str, Any]:
    """A copy of a built-in preset (``off``, ``subtle``, ``variety``)."""
    try:
        return copy.deepcopy(PRESETS[name])
    except KeyError as exc:
        raise ValueError(f"No built-in effect preset {name!r}; choose one of {', '.join(PRESETS)} or give a JSON file") from exc


def check_preset(data: Any) -> list[str]:
    """What is wrong with a preset (empty when it can be used); the schema file describes the same rules."""
    problems: list[str] = []
    if not isinstance(data, dict):
        return ["a preset is a JSON object"]
    if data.get("schema_version") != 1:
        problems.append("schema_version must be 1")
    effects = data.get("effects")
    if not isinstance(effects, list):
        return problems + ["effects must be a list"]
    for index, effect in enumerate(effects):
        where = f"effects[{index}]"
        if not isinstance(effect, dict):
            problems.append(f"{where} must be an object")
            continue
        if effect.get("type") not in EFFECT_TYPES:
            problems.append(f"{where}: type must be one of {', '.join(EFFECT_TYPES)}")
        if effect.get("group", "secondary") not in ("hero", "secondary"):
            problems.append(f"{where}: group must be hero or secondary")
        for name in (effect.get("anchor") or {}).get("order", []):
            if name not in ANCHORS:
                problems.append(f"{where}: anchor {name!r} is not one of {', '.join(ANCHORS)}")
        scale = effect.get("scale", 1.0)
        if not isinstance(scale, (int, float)) or not 1.0 <= scale <= 1.5:
            problems.append(f"{where}: scale must be between 1.0 and 1.5")
    budget = data.get("budget") or {}
    for key in ("max_hero", "max_secondary"):
        if key in budget and (not isinstance(budget[key], int) or budget[key] < 0):
            problems.append(f"budget.{key} must be a whole number")
    return problems


def load_preset(spec: str) -> dict[str, Any]:
    """A built-in preset by name, or a JSON file of the same shape."""
    if spec in PRESETS:
        return builtin_preset(spec)
    path = Path(spec)
    if not path.is_file():
        raise ValueError(f"No effect preset {spec!r}: use {', '.join(PRESETS)} or a JSON file")
    data = json.loads(path.read_text(encoding="utf-8"))
    problems = check_preset(data)
    if problems:
        raise ValueError(f"{path.name}: " + "; ".join(problems))
    return data


@lru_cache(maxsize=4)
def available_filters(ffmpeg: str | None = None) -> frozenset[str]:
    """The filter names this ffmpeg has (``ffmpeg -filters``), kept for the session; empty when it does not run."""
    from .ffmpeg import find_ffmpeg

    try:
        listing = subprocess.run([ffmpeg or find_ffmpeg(), "-hide_banner", "-filters"], capture_output=True, text=True, timeout=30, check=False).stdout
    except (OSError, subprocess.TimeoutExpired):
        return frozenset()
    names = set()
    for line in listing.splitlines():
        parts = line.split()
        if len(parts) >= 3 and "->" in parts[2]:  # " TSC scale  V->V  Scale the input video size ..."
            names.add(parts[1])
    return frozenset(names)


# --------------------------------------------------------------------------- rendering


@dataclass(frozen=True)
class Tag:
    """A short reaction line that pops in at ``start`` (seconds on the clip's clock)."""

    start: float
    end: float
    text: str
    reaction: str


@dataclass
class EffectPlan:
    """What one clip gets: ffmpeg filters, the words to pop, the tags, and a record of it."""

    preset: str = "off"
    filters: tuple[str, ...] = ()
    emphasis: tuple[float, ...] = ()  # start times of the words to pop, on the clip's clock
    emphasis_scale: float = 1.25
    tags: tuple[Tag, ...] = ()
    placed: list[dict[str, Any]] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"preset": self.preset, "placed": self.placed, "skipped": self.skipped}


def _num(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


def zoom_filters(frame: tuple[int, int], *, start: float, scale: float, zoom_in: float, hold: float, zoom_out: float,
                 focus: tuple[float, float] = (0.5, 0.45)) -> list[str]:
    """A punch-in: the picture grows to ``scale`` over ``zoom_in`` s from ``start`` (ease out), stays ``hold`` s and goes
    back over ``zoom_out`` s (ease in and out), around ``focus`` (fractions of the frame). ``scale`` and ``crop``
    with time expressions: unlike ``zoompan`` they keep the frame rate and do not jitter."""
    w, h = frame
    t0, t1 = start, start + zoom_in + hold
    grow = f"(1-pow(1-clip((t-{_num(t0)})/{_num(max(zoom_in, 0.01))},0,1),3))"
    back = f"((1-cos(PI*clip((t-{_num(t1)})/{_num(max(zoom_out, 0.01))},0,1)))/2)"
    z = f"(1+{_num(scale - 1)}*{grow}*(1-{back}))"
    cx, cy = focus
    return [
        f"scale=w='trunc({w}*{z}/2)*2':h='trunc({h}*{z}/2)*2':eval=frame",
        f"crop={w}:{h}:x='clip({_num(cx)}*iw-{w}/2,0,iw-{w})':y='clip({_num(cy)}*ih-{h}/2,0,ih-{h})'",
    ]


def prominent_words(cues: "Sequence[Cue]", samples: np.ndarray | None, rate: int, *, around: float, before: float, after: float,
                    count: int = 1) -> list[tuple[float, float, str]]:
    """The words said loudest and longest near ``around`` (``(start, end, text)`` on the cues' clock).

    Prosody, not meaning: a word's loudness and its length per letter, as z-scores against the other words of
    the clip (stressed words are louder and drawn out). Without sound, the longest words. One word per line.
    Words of one letter are left out: on their own they are mostly particles (が, は, 은) that carry no stress.
    """
    words = [(w.start, w.end, w.text.strip(), index) for index, cue in enumerate(cues) for w in cue.words
             if w.end > w.start and sum(ch.isalnum() for ch in w.text) >= 2]
    if not words:
        return []
    length = np.array([(b - a) / max(1, sum(ch.isalnum() for ch in text)) for a, b, text, _ in words])
    loud = np.zeros(len(words))
    if samples is not None and len(samples):
        for i, (a, b, _, _) in enumerate(words):
            part = np.asarray(samples[int(a * rate): max(int(a * rate) + 1, int(b * rate))], dtype=np.float64)
            loud[i] = 10 * np.log10(np.mean(part * part) + 1e-12) if part.size else -120.0

    def z(values: np.ndarray) -> np.ndarray:
        spread = values.std()
        return (values - values.mean()) / spread if spread > 1e-9 else np.zeros_like(values)

    score = z(loud) + 0.5 * z(length)
    chosen: list[tuple[float, float, str]] = []
    lines: set[int] = set()
    for i in np.argsort(-score):
        a, b, text, line = words[int(i)]
        if around - before <= a <= around + after and line not in lines:
            chosen.append((a, b, text))
            lines.add(line)
            if len(chosen) >= count:
                break
    return sorted(chosen)


def _reaction(stats: dict[str, float] | None) -> tuple[str, float, float]:
    counts = {name: float((stats or {}).get(f"react_{name}", 0)) for name in REACTIONS}
    total = sum(counts.values())
    best = max(counts, key=lambda name: counts[name])
    return (best, counts[best], counts[best] / total) if total > 0 else ("", 0.0, 0.0)


def _tag_text(effect: dict[str, Any], language: str, reaction: str) -> str:
    table = effect.get("text") or {}
    return str((table.get(language) or {}).get(reaction) or (table.get("*") or {}).get(reaction) or "")


def plan_effects(
    preset: dict[str, Any],
    *,
    length: float,
    peak: float,
    onset: float | None = None,
    hotkey: float | None = None,
    stats: dict[str, float] | None = None,
    cues: "Sequence[Cue]" = (),
    words_from: "tuple[Sequence[Cue], np.ndarray | None, int] | None" = None,
    to_clip: Callable[[float], float] = lambda t: t,
    frame: tuple[int, int] = (1080, 1920),
    focus: tuple[float, float] = (0.5, 0.45),
    language: str = "ja",
    filters: frozenset[str] | None = None,
    reduced_motion: bool = False,
) -> EffectPlan:
    """Plan the effects of one clip.

    ``peak``, ``onset`` (``None`` when no clear sound onset was found) and ``hotkey`` (an expression
    hotkey pressed near the peak) are on the cut's own clock, before silence is taken out;
    ``to_clip`` turns such a time into the finished clip's clock (``subtitles.clip_time``). ``cues``
    are the finished captions; ``words_from`` holds the uncut captions with the cut's sound
    (16 kHz) for choosing the emphasised words. ``filters`` is :func:`available_filters`.
    """
    name = str(preset.get("name") or preset.get("id") or "custom")
    plan = EffectPlan(preset=name)
    effects = list(preset.get("effects") or [])
    if not effects:
        return plan
    budget = {"hero": int((preset.get("budget") or {}).get("max_hero", 1)), "secondary": int((preset.get("budget") or {}).get("max_secondary", 2))}
    used = {"hero": 0, "secondary": 0}
    reaction, reaction_count, reaction_share = _reaction(stats)
    anchors = {"vts_hotkey": hotkey, "onset": onset, "peak": peak}
    moment = next((anchors[a] for a in ("vts_hotkey", "onset") if anchors[a] is not None), peak)  # where text effects land
    extra_emphasis = 0.0

    def missing(effect: dict[str, Any]) -> list[str]:
        return [f for f in EFFECT_TYPES.get(effect.get("type"), ()) if filters is not None and f not in filters]

    for effect in effects:
        kind, group = effect.get("type"), effect.get("group", "secondary")
        label = str(effect.get("id") or kind)
        if missing(effect):
            plan.skipped.append(f"{label}: this ffmpeg has no {', '.join(missing(effect))}")
            continue
        if used[group] >= budget[group]:
            plan.skipped.append(f"{label}: the {group} budget of {budget[group]} is spent")
            continue
        if kind == "zoom":
            order = (effect.get("anchor") or {}).get("order") or ["onset"]
            at = next((anchors[a] for a in order if anchors.get(a) is not None), None)
            via = next((a for a in order if anchors.get(a) is not None), "")
            if at is None:
                if (effect.get("anchor") or {}).get("skip_if_none", True):
                    plan.skipped.append(f"{label}: no clear moment to zoom on (no sound onset or hotkey near the peak)")
                    continue
                at, via = peak, "peak"
            tuning = dict(effect)
            if reaction in (effect.get("by_reaction") or {}):
                special = effect["by_reaction"][reaction]
                if special is None:
                    plan.skipped.append(f"{label}: no zoom for {reaction}")
                    continue
                tuning.update({k: v for k, v in special.items()})
            if reduced_motion:
                extra_emphasis = 0.15  # the caption grows more instead of the picture
                plan.skipped.append(f"{label}: reduced motion, the emphasised word grows instead")
                continue
            start = to_clip(at)
            zoom_in, zoom_out = tuning.get("in_ms", 120) / 1000, tuning.get("out_ms", 400) / 1000
            said = next((c for c in cues if c.start <= start <= c.end), None)
            hold = min(tuning.get("hold_max_ms", 2500) / 1000, max(0.6, (said.end - start) if said else 1.5))
            hold = max(0.0, min(hold, length - start - zoom_in - zoom_out))
            if start >= length - 0.5:
                plan.skipped.append(f"{label}: the moment is at the very end of the clip")
                continue
            scale = float(tuning.get("scale", 1.12))
            centre = tuple(tuning["focus"]) if isinstance(tuning.get("focus"), (list, tuple)) and len(tuning["focus"]) == 2 else focus
            plan.filters += tuple(zoom_filters(frame, start=start, scale=scale, zoom_in=zoom_in, hold=hold, zoom_out=zoom_out, focus=centre))
            plan.placed.append({"id": label, "type": kind, "at": round(start, 2), "anchor": via, "scale": scale,
                                "length": round(zoom_in + hold + zoom_out, 2), "reaction": reaction or None})
            used[group] += 1
        elif kind == "caption_emphasis":
            if words_from is None:
                plan.skipped.append(f"{label}: the captions have no word timing (translated or from a file without it)")
                continue
            before, after = (abs(x) / 1000 for x in (effect.get("window_ms") or [-2000, 1500]))
            raw_cues, samples, rate = words_from
            chosen = prominent_words(raw_cues, samples, rate, around=moment, before=before, after=after, count=int(effect.get("max_words", 1)))
            if not chosen:
                plan.skipped.append(f"{label}: no word near the moment")
                continue
            plan.emphasis = tuple(sorted(to_clip(a) for a, _, _ in chosen))
            plan.emphasis_scale = float(effect.get("scale", 1.25))
            plan.placed.append({"id": label, "type": kind, "at": [round(t, 2) for t in plan.emphasis], "words": [w for _, _, w in chosen]})
            used[group] += 1
        elif kind == "caption_tag":
            if not reaction or reaction_share < float(effect.get("min_share", 0.4)) or reaction_count < float(effect.get("min_count", 5)):
                plan.skipped.append(f"{label}: no reaction stands out in the chat")
                continue
            text = _tag_text(effect, language, reaction)
            if not text:
                plan.skipped.append(f"{label}: no text for {reaction} in {language}")
                continue
            start = to_clip(moment)
            plan.tags += (Tag(start, min(length, start + effect.get("duration_ms", 1200) / 1000), text, reaction),)
            plan.placed.append({"id": label, "type": kind, "at": round(start, 2), "text": text, "reaction": reaction})
            used[group] += 1
    plan.emphasis_scale += extra_emphasis
    return plan


def default_focus(layout: Any) -> tuple[float, float]:
    """Where a zoom centres: the avatar panel of a stacked layout, else a little above the middle."""
    if layout is not None and getattr(layout, "kind", "") == "stack":
        return 0.5, max(0.1, float(getattr(layout, "split", 0.42)) / 2)
    return 0.5, 0.45


def write_preset(name: str, path: str | os.PathLike[str]) -> Path:
    """Save a built-in preset as JSON, to edit and give back with ``--fx FILE``."""
    out = Path(path)
    out.write_text(json.dumps(builtin_preset(name), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out
