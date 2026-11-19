"""Subtitles: read SRT / WebVTT / JSON cues, write karaoke-style ASS, optional Whisper.

YouTube automatic captions downloaded as WebVTT carry per-word timestamps
(``<00:00:01.120><c> word</c>``); they become :class:`Word` entries so the ASS
output can light words up as they are spoken (``\\k`` karaoke tags).
"""

from __future__ import annotations

import json
import math
import os
import re
import unicodedata
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Iterable, Protocol, Sequence, runtime_checkable

from .brand import HIGHLIGHT, INK, LIVE_PINK
from .color import parse_color

__all__ = [
    "Word",
    "Cue",
    "SubtitleStyle",
    "SUBTITLE_STYLES",
    "SUBTITLE_POSITIONS",
    "CREDIT_POSITIONS",
    "subtitle_style",
    "FONT_CANDIDATES",
    "installed_fonts",
    "pick_font",
    "script_of",
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
    #: A font family, or "auto": the first installed one that suits the language of the text (see :func:`pick_font`).
    font: str = "auto"
    size: int = 64
    color: str = "#FFFFFF"           # text before it is spoken (karaoke) / normal text
    highlight: str = HIGHLIGHT       # spoken words (karaoke)
    outline: str = INK
    outline_width: float = 5.0
    bold: bool = True
    alignment: int = 2               # numpad layout: 2 = bottom centre, 5 = middle, 8 = top
    margin_v: int = 380              # px on a 1080x1920 canvas: keeps captions above the Shorts / TikTok UI
    margin_h: int = 60
    max_chars: int = 18              # line length before wrapping, in full-width characters (a Latin letter counts about half)
    max_lines: int = 3               # a longer cue is set smaller instead of running out of the frame
    #: A plate behind the text instead of an outline (``outline`` is its colour, ``outline_width`` its padding).
    box: bool = False
    #: Sizes above are for a canvas whose short side is 1080 px; other sizes scale proportionally.
    reference: int = 1080


#: Ready-made looks for ``--subtitle-style``.
SUBTITLE_STYLES: dict[str, SubtitleStyle] = {
    "default": SubtitleStyle(),
    "box": SubtitleStyle(box=True, outline="#15131FD9", outline_width=14.0),  # readable over a busy game picture
    "pink": SubtitleStyle(highlight=LIVE_PINK),
    "small": SubtitleStyle(size=48, outline_width=3.5, bold=False, max_chars=24),
}
#: Where the captions sit: (alignment, margin from that edge on a 1080x1920 canvas).
SUBTITLE_POSITIONS: dict[str, tuple[int, int]] = {"bottom": (2, 380), "middle": (5, 0), "top": (8, 260)}


def subtitle_style(name: str = "default", *, position: str | None = None, font: str | None = None, size: int | None = None) -> SubtitleStyle:
    """A preset, optionally moved (``bottom`` / ``middle`` / ``top``) and with another font or size."""
    if name not in SUBTITLE_STYLES:
        raise ValueError(f"Unknown subtitle style {name!r}; choose one of {', '.join(SUBTITLE_STYLES)}")
    style = SUBTITLE_STYLES[name]
    if position is not None:
        if position not in SUBTITLE_POSITIONS:
            raise ValueError(f"Unknown subtitle position {position!r}; choose one of {', '.join(SUBTITLE_POSITIONS)}")
        alignment, margin = SUBTITLE_POSITIONS[position]
        style = replace(style, alignment=alignment, margin_v=margin)
    if font:
        style = replace(style, font=font)
    if size:
        style = replace(style, size=size)
    return style


# --------------------------------------------------------------------------- fonts

#: Per script, the families tried in order: Noto first, then what Windows, macOS and Linux bring along.
FONT_CANDIDATES: dict[str, tuple[str, ...]] = {
    "ja": ("Noto Sans JP", "Noto Sans CJK JP", "Yu Gothic", "Meiryo", "Hiragino Sans", "MS Gothic"),
    "ko": ("Noto Sans KR", "Noto Sans CJK KR", "Malgun Gothic", "Apple SD Gothic Neo", "NanumGothic"),
    "zh": ("Noto Sans SC", "Noto Sans CJK SC", "Microsoft YaHei", "PingFang SC"),
    "": ("Noto Sans", "Segoe UI", "Helvetica Neue", "DejaVu Sans", "Arial"),
}
_FACE_WORDS = {"regular", "bold", "light", "medium", "semibold", "semilight", "demibold", "demilight", "extrabold", "extralight", "black", "thin", "heavy", "italic", "oblique", "ui"}
_installed: frozenset[str] | None = None


def script_of(text: str) -> str:
    """``"ja"`` / ``"ko"`` / ``"zh"`` for text mostly in that script, ``""`` otherwise (kana decides for Japanese)."""
    kana = sum(1 for ch in text if 0x3040 <= ord(ch) <= 0x30FF)
    hangul = sum(1 for ch in text if 0xAC00 <= ord(ch) <= 0xD7A3 or 0x1100 <= ord(ch) <= 0x11FF or 0x3130 <= ord(ch) <= 0x318F)
    han = sum(1 for ch in text if 0x3400 <= ord(ch) <= 0x9FFF)
    if hangul > kana and hangul >= han:
        return "ko"
    if kana:
        return "ja"
    return "zh" if han else ""


def _font_names_windows() -> set[str]:
    import winreg

    names: set[str] = set()
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            key = winreg.OpenKey(hive, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts")
        except OSError:
            continue
        with key:
            for index in range(winreg.QueryInfoKey(key)[1]):
                value = winreg.EnumValue(key, index)[0]  # "Yu Gothic Bold & Yu Gothic UI Bold (TrueType)"
                names.update(part.strip().lower() for part in re.sub(r"\s*\([^)]*\)\s*$", "", value).split("&"))
    return names


def _font_names_fontconfig() -> set[str]:
    import subprocess

    try:
        listed = subprocess.run(["fc-list", ":", "family"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20, check=False).stdout
    except (OSError, subprocess.SubprocessError):
        return set()
    return {name.strip().lower() for line in listed.splitlines() for name in line.split(",") if name.strip()}


def installed_fonts() -> frozenset[str]:
    """Lower-case names of the fonts on this machine, as far as they can be listed (empty when they cannot)."""
    global _installed
    if _installed is None:
        try:
            names = _font_names_windows() if os.name == "nt" else _font_names_fontconfig()
        except Exception:  # listing fonts is a convenience: never the reason a clip fails
            names = set()
        _installed = frozenset(names)
    return _installed


def _has_family(family: str, installed: Iterable[str]) -> bool:
    wanted = family.lower()
    for name in installed:
        if name == wanted or (name.startswith(wanted + " ") and set(name[len(wanted):].split()) <= _FACE_WORDS):
            return True
    return False


def pick_font(script: str = "", installed: Iterable[str] | None = None) -> str:
    """The first family for ``script`` that is installed; the first of the list when none is, or none can be listed.

    A Korean font draws Japanese kanji in their Korean shapes and the other way round, so
    the font follows the language of the text rather than being one fixed family.
    """
    families = FONT_CANDIDATES.get(script, FONT_CANDIDATES[""])
    names = installed_fonts() if installed is None else frozenset(name.lower() for name in installed)
    return next((family for family in families if _has_family(family, names)), families[0])


def _cue_text(cue: Cue) -> str:
    return cue.text or "".join(word.text for word in cue.words)


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


def _width(text: str) -> float:
    """Display width in full-width characters: CJK counts 1, everything else about half."""
    return sum(1.0 if unicodedata.east_asian_width(ch) in "WF" else 0.55 for ch in text)


# Written as code points: these are characters of the text being cut, not text this program shows.
_STOPS = "".join(map(chr, (0x3001, 0x3002, 0xFF0C, 0xFF0E, 0xFF01, 0xFF1F, 0x21, 0x3F, 0x2026, 0x2025)))  # ideographic comma and full stop, full-width and plain marks, ellipses
_CLOSING = "".join(map(chr, (0x300D, 0x300F, 0xFF09, 0x29, 0x3011, 0x3015, 0xFF3D, 0x7D)))
_OPENING = "".join(map(chr, (0x300C, 0x300E, 0xFF08, 0x28, 0x3010, 0x3014, 0xFF3B, 0x7B)))
_SMALL_KANA = "".join(map(chr, (0x3083, 0x3085, 0x3087, 0x3063, 0x30E3, 0x30E5, 0x30E7, 0x30C3, 0x3041, 0x3043, 0x3045, 0x3047, 0x3049, 0x30A1, 0x30A3, 0x30A5, 0x30A7, 0x30A9, 0x3093, 0x30F3)))
_KEEP_WITH_PREVIOUS = _STOPS + _CLOSING + _SMALL_KANA + "".join(map(chr, (0x30FC, 0x301C, 0xFF5E, 0x30FB)))  # long vowel mark, wave dashes, middle dot


def _phrases(text: str) -> list[str]:
    """Japanese without spaces, cut where a line may break: after punctuation and where a new phrase starts.

    A phrase usually starts with kanji, katakana or Latin and ends in hiragana (particles,
    endings), so a break before a non-hiragana character that follows hiragana lands between
    phrases rather than inside a word.
    """
    def kind(ch: str) -> str:
        code = ord(ch)
        if 0x3040 <= code <= 0x309F:
            return "hiragana"
        if 0x30A0 <= code <= 0x30FF:
            return "katakana"
        if 0x3400 <= code <= 0x9FFF:
            return "kanji"
        return "other"

    pieces: list[str] = []
    current = ""
    for ch in text:
        previous = current[-1:] if current else ""
        starts = bool(previous) and ch not in _KEEP_WITH_PREVIOUS and (
            previous in _STOPS or ch in _OPENING
            or (kind(previous) == "hiragana" and kind(ch) in ("kanji", "katakana", "other") and not ch.isspace())
        )
        if starts and previous not in _OPENING:
            pieces.append(current)
            current = ""
        current += ch
    if current:
        pieces.append(current)
    return pieces


def _tokens(text: str) -> tuple[list[str], str]:
    """The pieces a line may be broken between, and what joins them."""
    if " " in text:
        return text.split(" "), " "
    pieces = _phrases(text) if any(0x3040 <= ord(ch) <= 0x30FF for ch in text) else list(text)
    return (pieces if len(pieces) > 1 else list(text)), ""


def _wrap(tokens: Sequence[str], max_chars: int, max_lines: int = 3) -> list[list[int]]:
    """Group token indices into lines of about ``max_chars`` full-width characters, as even as the tokens allow."""
    widths = [_width(token) for token in tokens]
    total = sum(widths)
    if total <= max_chars or len(tokens) <= 1:
        return [list(range(len(tokens)))]
    count = min(max_lines, len(tokens), math.ceil(total / max_chars))
    ends, done = [], 0.0  # running width after each token
    for width in widths:
        done += width
        ends.append(done)
    cuts, start = [], 0
    for line in range(1, count):
        target = total * line / count
        candidates = range(start + 1, len(tokens) - (count - line) + 1)
        cut = min(candidates, key=lambda i: abs(ends[i - 1] - target))
        cuts.append(cut)
        start = cut
    edges = [0, *cuts, len(tokens)]
    return [list(range(edges[i], edges[i + 1])) for i in range(len(edges) - 1)]


def _shrink(widest: float, style: SubtitleStyle) -> str:
    """An override tag that sets a cue smaller when its longest line would still run out of the frame."""
    if widest <= style.max_chars * 1.12:
        return ""
    scale = max(55, round(100 * style.max_chars / widest))
    return f"{{\\fscx{scale}\\fscy{scale}}}"


def _is_cjk(ch: str) -> bool:
    return bool(ch) and any(lo <= ord(ch) <= hi for lo, hi in ((0x3040, 0x30FF), (0x3400, 0x9FFF), (0xFF00, 0xFFEF)))


def _cue_line(cue: Cue, style: SubtitleStyle, karaoke: bool, base_font: str | None = None) -> str:
    if karaoke and cue.words:
        words = [w for w in cue.words if w.text]
        tokens = [w.text.strip() for w in words]
        lines = _wrap(tokens, style.max_chars, style.max_lines)
        parts: list[str] = [_shrink(max(_width("".join(tokens[i] for i in idxs)) for idxs in lines), style)]
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
        # re-wrapping by length would break in the middle of one of them. Each keeps the
        # font of its own language: the original is not drawn with the translation's glyphs.
        def line_script(line: str) -> str:
            script = script_of(line)
            # A line of kanji alone inside Japanese text is Japanese, not Chinese.
            return "ja" if script == "zh" and any(0x3040 <= ord(ch) <= 0x30FF for ch in cue.text) else script

        fonts = [pick_font(line_script(line)) if base_font and line_script(line) else base_font for line in explicit]
        mixed = base_font is not None and any(font != base_font for font in fonts)
        shown = [(f"{{\\fn{font}}}" if mixed else "") + _escape(line) for line, font in zip(explicit, fonts)]
        body = _shrink(max(_width(line) for line in explicit), style) + "\\N".join(shown)
    else:
        text = cue.text.replace("\n", " ").strip()
        tokens, joiner = _tokens(text)
        lines = [joiner.join(tokens[i] for i in idxs) for idxs in _wrap(tokens, style.max_chars, style.max_lines)]
        body = _shrink(max(_width(line) for line in lines), style) + "\\N".join(_escape(line) for line in lines)
    # In karaoke mode the style's primary colour is the highlight; cues without word timing stay plain.
    return (f"{{\\1c{_ass_inline_color(style.color)}}}" + body) if karaoke else body


#: Corners a source credit can sit in -> ASS alignment (numpad layout).
CREDIT_POSITIONS: dict[str, int] = {"top-left": 7, "top-right": 9, "bottom-left": 1, "bottom-right": 3}


def to_ass(
    cues: Iterable[Cue],
    *,
    play_res: tuple[int, int] = (1080, 1920),
    style: SubtitleStyle | None = None,
    karaoke: bool = True,
    title: str = "stream2clip",
    credit: str | None = None,
    credit_position: str = "top-left",
    duration: float | None = None,
) -> str:
    """Cues as an ASS script. ``credit`` is a small line shown in a corner for the whole clip
    ("Source: channel name"); it needs ``duration``, the clip's length, when there are no cues to tell it."""
    st = style or SubtitleStyle()
    cues = sorted(cues, key=lambda c: c.start)
    font = pick_font(script_of("".join(_cue_text(c) for c in cues))) if st.font == "auto" else st.font
    W, H = play_res
    k = min(W, H) / st.reference
    size, outline = max(8, round(st.size * k)), round(st.outline_width * k, 1)
    # margin_v is defined for a 1080x1920 portrait canvas; landscape video keeps captions low (6%).
    margin_v = round(H * st.margin_v / 1920) if H >= W else (round(H * 0.06) if st.alignment != 5 else 0)
    border = 3 if st.box else 1
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
        f"Style: Default,{font},{size},{_ass_color(primary)},{_ass_color(secondary)},{_ass_color(st.outline)},&H64000000,"
        f"{-1 if st.bold else 0},0,0,0,100,100,0,0,{border},{outline:g},0,{st.alignment},{margin_h},{margin_h},{margin_v},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    events = [
        f"Dialogue: 0,{_ass_time(c.start)},{_ass_time(c.end)},Default,,0,0,0,,{_cue_line(c, st, karaoke, font)}"
        for c in cues
        if c.end > c.start and (c.text.strip() or c.words)
    ]
    credit = " ".join((credit or "").split())
    if credit:
        if credit_position not in CREDIT_POSITIONS:
            raise ValueError(f"Unknown credit position {credit_position!r}: use one of {', '.join(CREDIT_POSITIONS)}")
        until = duration if duration else max((c.end for c in cues), default=0.0)
        if until <= 0:
            raise ValueError("A credit needs the length of the clip")
        credit_font = pick_font(script_of(credit)) if st.font == "auto" else st.font
        # Small and out of the way; on a portrait canvas the bottom corners stay above the Shorts / TikTok buttons.
        low = credit_position.startswith("bottom")
        margin_cv = round(H * (0.2 if low and H >= W else 0.05))
        header.insert(
            header.index("[Events]") - 1,
            f"Style: Credit,{credit_font},{max(8, round(36 * k))},{_ass_color('#FFFFFF')},{_ass_color('#FFFFFF')},{_ass_color(st.outline)},&H64000000,"
            f"-1,0,0,0,100,100,0,0,1,{round(2 * k, 1):g},0,{CREDIT_POSITIONS[credit_position]},{round(40 * k)},{round(40 * k)},{margin_cv},1",
        )
        events.insert(0, f"Dialogue: 1,{_ass_time(0)},{_ass_time(until)},Credit,,0,0,0,,{_escape(credit)}")
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
