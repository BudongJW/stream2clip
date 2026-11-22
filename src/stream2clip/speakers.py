"""Who says each line in a collab, so captions can be coloured per talent.

Paid Japanese clip editing colours the captions per speaker as a matter of course, and per-speaker
caption styles were still Premiere Pro users' most asked-for feature in 2025
(reports/키리누키 영상 레퍼런스 검토.md). The speaker of a line comes from one of three places:

* a transcript that already says (whisperX and other diarization tools write ``speaker`` per
  segment; :func:`stream2clip.subtitles.load_subtitles` keeps it),
* an RTTM file, the usual output of a diarization tool (:func:`read_rttm`, :func:`assign_from_spans`),
* an OBS recording with each microphone on its own audio track: whoever's track is loudest during
  the line (:func:`assign_from_tracks`).

``--speaker LABEL=NAME:#COLOUR`` turns a label (``SPEAKER_00``, or a track number) into a name and a
caption colour; labels without a colour take the next of :data:`PALETTE`. numpy only.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np

from .subtitles import Cue

__all__ = ["PALETTE", "Speaker", "SpeakerMap", "assign_from_spans", "assign_from_tracks", "read_rttm"]

#: Outline colours for speakers without one: distinct on a white caption and from each other.
PALETTE = ("#FF5C9A", "#3FA7FF", "#F2A100", "#2DBE6C", "#9B6BFF", "#FF7A3D", "#00B8B0", "#E04848")
_SPEC = re.compile(r"^(?P<label>[^=:]+?)\s*(?:=\s*(?P<name>[^:#]*?))?\s*(?::\s*(?P<color>#?[0-9A-Fa-f]{6}))?\s*$")


@dataclass(frozen=True)
class Speaker:
    name: str
    color: str


@dataclass
class SpeakerMap:
    """Labels to names and colours; a label it has not been told about gets its own name and the next colour."""

    known: dict[str, Speaker] = field(default_factory=dict)
    _given: int = 0

    @classmethod
    def parse(cls, specs: Iterable[str]) -> "SpeakerMap":
        """From ``LABEL=NAME:#RRGGBB`` strings (name and colour each optional)."""
        result = cls()
        for spec in specs:
            match = _SPEC.match(spec.strip())
            if not match or not match.group("label").strip():
                raise ValueError(f"A speaker is LABEL=NAME:#RRGGBB (name and colour optional), not {spec!r}")
            label = match.group("label").strip()
            name = (match.group("name") or "").strip() or label
            color = match.group("color")
            color = ("#" + color.lstrip("#")).upper() if color else result._next_color()
            result.known[label] = Speaker(name, color)
        return result

    def _next_color(self) -> str:
        color = PALETTE[self._given % len(PALETTE)]
        self._given += 1
        return color

    def resolve(self, label: str) -> Speaker:
        if label not in self.known:
            by_name = next((s for s in self.known.values() if s.name == label), None)
            self.known[label] = by_name or Speaker(label, self._next_color())
        return self.known[label]

    def name(self, cues: Sequence[Cue]) -> list[Cue]:
        """The cues with their labels replaced by the names."""
        return [replace(c, speaker=self.resolve(c.speaker).name) if c.speaker else c for c in cues]

    def colors(self) -> dict[str, str]:
        """Name to colour, for :func:`stream2clip.subtitles.to_ass`."""
        return {s.name: s.color for s in self.known.values()}


def read_rttm(path: str | os.PathLike[str]) -> list[tuple[float, float, str]]:
    """``(start, end, label)`` spans from an RTTM file (``SPEAKER file 1 start duration <NA> <NA> label ...``)."""
    spans = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) >= 8 and parts[0] == "SPEAKER":
            start, length = float(parts[3]), float(parts[4])
            spans.append((start, start + length, parts[7]))
    return sorted(spans)


def assign_from_spans(cues: Sequence[Cue], spans: Sequence[tuple[float, float, str]], *, share: float = 0.3) -> list[Cue]:
    """Give each cue the label that speaks most of it (at least ``share`` of its length); cues keep a speaker they have."""
    out = []
    for cue in cues:
        if cue.speaker or cue.end <= cue.start:
            out.append(cue)
            continue
        talk: dict[str, float] = {}
        for a, b, label in spans:
            overlap = min(b, cue.end) - max(a, cue.start)
            if overlap > 0:
                talk[label] = talk.get(label, 0.0) + overlap
        best = max(talk, key=lambda label: talk[label]) if talk else ""
        out.append(replace(cue, speaker=best) if best and talk[best] >= share * (cue.end - cue.start) else cue)
    return out


def _db(samples: np.ndarray) -> float:
    if samples.size == 0:
        return -90.0
    return float(10 * np.log10(np.mean(np.asarray(samples, dtype=np.float64) ** 2) + 1e-12))


def assign_from_tracks(
    cues: Sequence[Cue], tracks: "dict[int, np.ndarray]", rate: int, *, margin: float = 6.0,
) -> list[Cue]:
    """Give each cue the track whose microphone is loudest while it is said (by ``margin`` dB over the next).

    ``tracks`` maps an audio track number to its samples, on the cues' clock. The label given is the
    track number as text, for a :class:`SpeakerMap` to name. Cues keep a speaker they already have.
    """
    out = []
    for cue in cues:
        if cue.speaker or len(tracks) < 2:
            out.append(cue)
            continue
        a, b = int(max(0.0, cue.start) * rate), int(max(0.0, cue.end) * rate)
        levels = sorted(((_db(samples[a:b]), number) for number, samples in tracks.items()), reverse=True)
        if levels[0][0] > -60.0 and levels[0][0] - levels[1][0] >= margin:
            out.append(replace(cue, speaker=str(levels[0][1])))
        else:
            out.append(cue)
    return out
