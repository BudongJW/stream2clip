"""Subtitles: read SRT / WebVTT / JSON cues, write karaoke-style ASS, optional Whisper.

YouTube automatic captions downloaded as WebVTT carry per-word timestamps
(``<00:00:01.120><c> word</c>``); they become :class:`Word` entries so the ASS
output can light words up as they are spoken (``\\k`` karaoke tags).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Iterable, Protocol, Sequence, runtime_checkable

from .brand import HIGHLIGHT, INK
from .color import parse_color

__all__ = [
    "Word",
    "Cue",
    "SubtitleStyle",
    "Transcriber",
    "FasterWhisperTranscriber",
    "parse_srt",
    "parse_vtt",
    "load_subtitles",
    "slice_cues",
    "to_ass",
    "write_ass",
    "to_srt",
]


@dataclass(frozen=True)
class Word:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class Cue:
    start: float
    end: float
    text: str
    words: tuple[Word, ...] = field(default_factory=tuple)


# --------------------------------------------------------------------------- parsing

_TS = re.compile(r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})")


def _ts(value: str) -> float:
    m = _TS.search(value)
    if not m:
        raise ValueError(f"Bad timestamp {value!r}")
    h, mnt, s, frac = m.groups()
    return int(h or 0) * 3600 + int(mnt) * 60 + int(s) + int(frac.ljust(3, "0")) / 1000


_TAG = re.compile(r"<[^>]+>")


def parse_srt(text: str) -> list[Cue]:
    cues: list[Cue] = []
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n").strip()):
        lines = [ln for ln in block.split("\n") if ln.strip()]
        idx = next((i for i, ln in enumerate(lines) if "-->" in ln), None)
        if idx is None:
            continue
        start_s, end_s = lines[idx].split("-->")
        body = _TAG.sub("", "\n".join(lines[idx + 1 :])).strip()
        if body:
            cues.append(Cue(_ts(start_s), _ts(end_s), body))
    return cues


_VTT_WORD = re.compile(r"<(\d{2}:\d{2}:\d{2}\.\d{3}|\d{2}:\d{2}\.\d{3})>")


def parse_vtt(text: str) -> list[Cue]:
    cues: list[Cue] = []
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n").strip()):
        lines = block.split("\n")
        idx = next((i for i, ln in enumerate(lines) if "-->" in ln), None)
        if idx is None:
            continue
        start_s, rest = lines[idx].split("-->", 1)
        start, end = _ts(start_s), _ts(rest.strip().split(" ")[0])
        raw = "\n".join(lines[idx + 1 :]).strip()
        if not raw:
            continue
        words: list[Word] = []
        if _VTT_WORD.search(raw):
            # "first<00:00:01.120><c> second</c><00:00:01.500><c> third</c>"
            parts = _VTT_WORD.split(raw.split("\n")[-1])
            t = start
            for i in range(0, len(parts), 2):
                piece = _TAG.sub("", parts[i]).strip()
                nxt = _ts(parts[i + 1]) if i + 1 < len(parts) else end
                if piece:
                    words.append(Word(t, nxt, piece))
                t = nxt
        body = _TAG.sub("", raw).strip()
        if not body:
            continue
        cues.append(Cue(start, end, body, tuple(words)))
    return _dedupe_rolling(cues)


def _dedupe_rolling(cues: list[Cue]) -> list[Cue]:
    """YouTube auto-captions repeat the previous line in every cue; keep only the new text."""
    out: list[Cue] = []
    for cue in cues:
        lines = cue.text.split("\n")
        if out and len(lines) > 1 and lines[0].strip() == out[-1].text.split("\n")[-1].strip():
            cue = replace(cue, text="\n".join(lines[1:]))
        if out and cue.text == out[-1].text and not cue.words:
            continue
        if cue.end - cue.start < 0.05 and not cue.words:
            continue
        out.append(cue)
    return out


def _from_json(data: Any) -> list[Cue]:
    segments = data.get("segments", data) if isinstance(data, dict) else data
    cues = []
    for seg in segments:
        words = tuple(Word(float(w["start"]), float(w["end"]), str(w.get("word", w.get("text", ""))).strip()) for w in seg.get("words", []) or [] if "start" in w)
        cues.append(Cue(float(seg["start"]), float(seg["end"]), str(seg.get("text", "")).strip(), words))
    return cues


def load_subtitles(path: str | os.PathLike[str]) -> list[Cue]:
    """``.srt``, ``.vtt`` or Whisper-style ``.json`` (``segments`` with optional ``words``)."""
    p = Path(path)
    text = p.read_text(encoding="utf-8-sig")
    suffix = p.suffix.lower()
    if suffix == ".srt":
        return parse_srt(text)
    if suffix == ".vtt":
        return parse_vtt(text)
    if suffix == ".json":
        return _from_json(json.loads(text))
    if text.lstrip().startswith("WEBVTT"):
        return parse_vtt(text)
    return parse_srt(text)


def slice_cues(cues: Iterable[Cue], start: float, end: float) -> list[Cue]:
    """Cues overlapping ``start..end``, clipped and shifted so the clip starts at 0."""
    out = []
    for c in cues:
        if c.end <= start or c.start >= end:
            continue
        words = tuple(Word(max(w.start, start) - start, min(w.end, end) - start, w.text) for w in c.words if w.end > start and w.start < end)
        out.append(Cue(max(c.start, start) - start, min(c.end, end) - start, c.text, words))
    return out


# --------------------------------------------------------------------------- writing


@dataclass(frozen=True)
class SubtitleStyle:
    font: str = "Noto Sans KR"
    size: int = 64
    color: str = "#FFFFFF"           # text before it is spoken (karaoke) / normal text
    highlight: str = HIGHLIGHT       # spoken words (karaoke)
    outline: str = INK
    outline_width: float = 5.0
    bold: bool = True
    alignment: int = 2               # numpad layout: 2 = bottom centre, 5 = middle, 8 = top
    margin_v: int = 380              # px on a 1080x1920 canvas: keeps captions above the Shorts / TikTok UI
    margin_h: int = 60
    max_chars: int = 18              # soft line length before wrapping
    #: Sizes above are for a canvas whose short side is 1080 px; other sizes scale proportionally.
    reference: int = 1080


def _ass_color(color: str) -> str:
    r, g, b, a = parse_color(color)
    return f"&H{255 - a:02X}{b:02X}{g:02X}{r:02X}"


def _ass_inline_color(color: str) -> str:
    r, g, b, _ = parse_color(color)
    return f"&H{b:02X}{g:02X}{r:02X}&"


def _ass_time(t: float) -> str:
    t = max(0.0, t)
    cs = int(round(t * 100))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, cs = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", "\\N")


def _wrap(tokens: Sequence[str], max_chars: int) -> list[list[int]]:
    """Group token indices into lines of roughly ``max_chars`` characters (balanced 2 lines max)."""
    total = sum(len(t) for t in tokens)
    if total <= max_chars or len(tokens) <= 1:
        return [list(range(len(tokens)))]
    target = total / 2
    acc, split = 0, len(tokens) - 1
    for i, tok in enumerate(tokens):
        acc += len(tok)
        if acc >= target:
            split = i + 1 if acc - target < len(tok) / 2 else max(1, i)
            break
    split = min(max(1, split), len(tokens) - 1)
    return [list(range(split)), list(range(split, len(tokens)))]


def _is_cjk(ch: str) -> bool:
    return bool(ch) and any(lo <= ord(ch) <= hi for lo, hi in ((0x3040, 0x30FF), (0x3400, 0x9FFF), (0xFF00, 0xFFEF)))


def _cue_line(cue: Cue, style: SubtitleStyle, karaoke: bool) -> str:
    if karaoke and cue.words:
        words = [w for w in cue.words if w.text]
        tokens = [w.text.strip() for w in words]
        lines = _wrap(tokens, style.max_chars)
        parts: list[str] = []
        cursor = cue.start
        for li, idxs in enumerate(lines):
            if li:
                parts.append("\\N")
            for k, i in enumerate(idxs):
                w = words[i]
                gap = max(0.0, w.start - cursor)
                if gap >= 0.01:
                    parts.append(f"{{\\k{int(round(gap * 100))}}}")
                dur = max(1, int(round((w.end - max(w.start, cursor)) * 100)))
                sep = "" if (k == 0 or _is_cjk(tokens[i][:1]) or _is_cjk(tokens[idxs[k - 1]][-1:])) else " "
                parts.append(f"{{\\k{dur}}}{sep}{_escape(tokens[i])}")
                cursor = max(cursor, w.end)
        return "".join(parts)
    explicit = [line.strip() for line in cue.text.strip().split("\n") if line.strip()]
    if len(explicit) > 1:
        # Lines the cue already has (an original above its translation) stay as they are;
        # re-wrapping by length would break in the middle of one of them.
        body = "\\N".join(_escape(line) for line in explicit)
    else:
        text = cue.text.replace("\n", " ").strip()
        tokens = text.split(" ") if " " in text else list(text)
        lines = _wrap(tokens, style.max_chars)
        joiner = " " if " " in text else ""
        body = "\\N".join(_escape(joiner.join(tokens[i] for i in idxs)) for idxs in lines)
    # In karaoke mode the style's primary colour is the highlight; cues without word timing stay plain.
    return (f"{{\\1c{_ass_inline_color(style.color)}}}" + body) if karaoke else body


def to_ass(cues: Iterable[Cue], *, play_res: tuple[int, int] = (1080, 1920), style: SubtitleStyle | None = None, karaoke: bool = True, title: str = "stream2clip") -> str:
    st = style or SubtitleStyle()
    W, H = play_res
    k = min(W, H) / st.reference
    size, outline = max(8, round(st.size * k)), round(st.outline_width * k, 1)
    # margin_v is defined for a 1080x1920 portrait canvas; landscape video keeps captions low (6%).
    margin_v = round(H * st.margin_v / 1920) if H >= W else round(H * 0.06)
    margin_h = round(st.margin_h * k)
    primary, secondary = (st.highlight, st.color) if karaoke else (st.color, st.color)
    header = [
        "[Script Info]",
        f"Title: {title}",
        "ScriptType: v4.00+",
        f"PlayResX: {W}",
        f"PlayResY: {H}",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,{st.font},{size},{_ass_color(primary)},{_ass_color(secondary)},{_ass_color(st.outline)},&H64000000,"
        f"{-1 if st.bold else 0},0,0,0,100,100,0,0,1,{outline:g},0,{st.alignment},{margin_h},{margin_h},{margin_v},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    events = [
        f"Dialogue: 0,{_ass_time(c.start)},{_ass_time(c.end)},Default,,0,0,0,,{_cue_line(c, st, karaoke)}"
        for c in sorted(cues, key=lambda c: c.start)
        if c.end > c.start and (c.text.strip() or c.words)
    ]
    return "\n".join(header + events) + "\n"


def write_ass(cues: Iterable[Cue], path: str | os.PathLike[str], **kwargs: Any) -> Path:
    out = Path(path)
    out.write_text(to_ass(cues, **kwargs), encoding="utf-8")
    return out


def to_srt(cues: Iterable[Cue]) -> str:
    def stamp(t: float) -> str:
        ms = int(round(max(0.0, t) * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"

    return "\n".join(f"{i}\n{stamp(c.start)} --> {stamp(c.end)}\n{c.text}\n" for i, c in enumerate(cues, start=1))


# --------------------------------------------------------------------------- speech to text


@runtime_checkable
class Transcriber(Protocol):
    def transcribe(self, path: str | os.PathLike[str], *, language: str | None = None) -> list[Cue]: ...


class FasterWhisperTranscriber:
    """Word-timestamped transcription with faster-whisper (``pip install "stream2clip[asr]"``).

    For Japanese streams ``kotoba-tech/kotoba-whisper-v2.0-faster`` is a good model id.
    """

    def __init__(self, model: str = "small", *, device: str = "auto", compute_type: str = "default", vad: bool = True) -> None:
        try:
            from faster_whisper import WhisperModel  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError('Transcription needs faster-whisper: pip install "stream2clip[asr]"') from exc
        self._model = WhisperModel(model, device=device, compute_type=compute_type)
        self._vad = vad

    def transcribe(self, path: str | os.PathLike[str], *, language: str | None = None) -> list[Cue]:
        # Decode with our own ffmpeg and hand over samples: faster-whisper's file reader
        # goes through PyAV, and faster-whisper 1.2.1 with PyAV 19 fails in av.open().
        from .audio import decode_pcm

        samples = decode_pcm(path, sample_rate=16000)
        segments, _info = self._model.transcribe(samples, language=language, word_timestamps=True, vad_filter=self._vad)
        cues = []
        for seg in segments:
            words = tuple(Word(float(w.start), float(w.end), w.word.strip()) for w in (seg.words or []))
            cues.append(Cue(float(seg.start), float(seg.end), seg.text.strip(), words))
        return cues
