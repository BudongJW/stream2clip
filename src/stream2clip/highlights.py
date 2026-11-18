"""Highlight ("레전드 장면") detection from chat, audio and replay heatmaps.

Method (see the reference report, section 2):

1. Bucket the stream into ``window``-second slots and compute signals per slot:
   message rate, unique chatters, reaction messages (草 / www / lol / KEKW /
   ㅋㅋ / 888 ... each message counted once), paid events (Super Chat, bits,
   memberships), optional audio loudness and YouTube "most replayed" heatmap.
2. Normalize every signal against **this stream's own baseline** with a robust
   z-score (median / MAD), so quiet and busy channels are treated alike.
3. Weighted sum -> moving average -> peaks above ``threshold``.
4. Chat reacts after the moment happens: shift peaks earlier by ``chat_delay``,
   add ``lead`` / ``tail`` context, merge neighbours, clamp the clip length.
"""

from __future__ import annotations

import json
import math
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

from .chat import ChatMessage
from .sources import HeatmapPoint

__all__ = [
    "REACTIONS",
    "ROUTINE",
    "is_routine",
    "HighlightConfig",
    "Highlight",
    "HighlightResult",
    "classify_reactions",
    "detect_highlights",
    "mark_singing",
    "load_highlights",
    "robust_z",
    "render_timeline",
]

SCHEMA = "stream2clip.highlights/v1"

#: Reaction vocabulary per category (case-insensitive regular expressions).
REACTIONS: dict[str, list[str]] = {
    "laugh": [
        r"草", r"[wｗ]{2,}", r"笑", r"ワロ", r"\blol+\b", r"\blmf?ao+\b", r"kekw", r"omegalul", r"\blul\b",
        r"ㅋ{2,}", r"ㅎ{3,}", r"\bxd\b", r"(?:ha){2,}", r"kusa", r"_lol", r"_www", r"爆笑",
        # A single trailing w is how most Japanese chat laughs ("えｗ", "そうねw"); not "now" / "wow".
        r"(?<![a-z])[wｗ]+$",
    ],
    "hype": [
        r"[!！]{3,}", r"[8８]{3,}", r"ナイス", r"\bnice+\b", r"pog", r"\bgg\b", r"ㄷ{2,}", r"레전드", r"미쳤",
        r"와{2,}", r"神", r"天才", r"すご", r"やば", r"\bclip\b", r"클립", r"切り抜き", r"legend",
        r"👏", r"拍手", r"おーっ", r"助かる",
    ],
    "cute": [r"かわいい|可愛い|かわよ|カワイイ", r"\bcute\b", r"kawaii", r"귀여|귀엽", r"てぇてぇ|尊い", r"tee ?tee", r"きゃー"],
    "shock": [
        r"[?？]{3,}", r"[えぇ]{3,}", r"ㄴㅇㄱ", r"\bwtf\b", r"\bwhat+\b", r"嘘", r"マジ", r"헐",
        r"[!！][?？]|[?？][!！]", r"こっ?わ|怖", r"うわ", r"びっくり", r"はてな", r"焦",
        # The whole message is one short interjection: "え", "え？", "あっ", "ん？", "お？".
        r"^(?:[えぇエ]+|[あぁア]+|[おぉオ]+|[んン])[っッー〜～]*[?？!！]*$",
    ],
}
_COMPILED = {name: re.compile("|".join(patterns), re.IGNORECASE | re.MULTILINE) for name, patterns in REACTIONS.items()}

#: Greetings and goodbyes. Everybody types them at once when a stream starts and ends,
#: which looks exactly like a highlight (on a real archive the sign-off ranked 8th of 10).
ROUTINE: list[str] = [
    r"^こん(?:ばん|にち|ちゃ)", r"^こん(?![など])[ぁ-んァ-ヶ]{1,4}[〜～ー!！♪\s]*$", r"^おは(?:よ|[〜～ー])", r"^おつ", r"^お疲れ", r"^乙[〜～ー!！]*$",
    r"^(?:ばいばい|バイバイ|またね|おやすみ)", r"^(?:待機|初見)",
    r"^(?:hello|hi+|hey|bye+|good ?(?:night|morning|evening)|gn|otsu\w*|kon\w+)\b",
    r"^(?:안녕|ㅎㅇ|하이|ㅂㅂ|ㅂㅇ|바이|수고|고생)",
]
_ROUTINE = re.compile("|".join(ROUTINE), re.IGNORECASE)
_LABELS = {"laugh": "웃음", "hype": "환호", "cute": "귀여움", "shock": "놀람"}
SIGNALS = ("rate", "unique", "reactions", "paid", "audio", "heatmap", "laughter")
#: Experimental signals: added on top of the score instead of averaged into it.
BONUS_SIGNALS = ("laughter",)


def classify_reactions(text: str, emotes: Sequence[str] = ()) -> set[str]:
    """Reaction categories present in one message (each category counted once)."""
    # One line per piece, so patterns anchored with ^ / $ see the message text on its own.
    haystack = text if not emotes else text + "\n" + "\n".join(emotes)
    return {name for name, rx in _COMPILED.items() if rx.search(haystack)}


def is_routine(text: str) -> bool:
    """A greeting or goodbye ("こんぺこ～", "おつかれ", "hello", "안녕하세요") rather than a reaction."""
    return bool(_ROUTINE.search(text.strip()))


@dataclass(frozen=True)
class HighlightConfig:
    window: float = 5.0
    smooth: int = 3
    threshold: float = 2.0
    chat_delay: float = 8.0
    lead: float = 20.0
    tail: float = 10.0
    min_length: float = 15.0
    max_length: float = 90.0
    merge_gap: float = 15.0
    top: int = 10
    #: Leave greetings / goodbyes out of the chat signals (paid events still count).
    skip_greetings: bool = True
    weights: dict[str, float] = field(
        default_factory=lambda: {"rate": 0.30, "unique": 0.20, "reactions": 0.30, "paid": 0.10, "audio": 0.15, "heatmap": 0.15, "laughter": 0.15}
    )

    def __post_init__(self) -> None:
        if self.window <= 0 or self.smooth < 1 or self.top < 1:
            raise ValueError("window must be > 0, smooth >= 1, top >= 1")
        if self.min_length > self.max_length:
            raise ValueError("min_length must be <= max_length")


@dataclass
class Highlight:
    rank: int
    start: float
    end: float
    peak: float
    score: float
    reasons: list[str] = field(default_factory=list)
    stats: dict[str, float] = field(default_factory=dict)

    @property
    def duration(self) -> float:
        return self.end - self.start

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("start", "end", "peak", "score"):
            data[key] = round(data[key], 2)
        data["stats"] = {k: round(v, 2) for k, v in self.stats.items()}
        return data


@dataclass
class HighlightResult:
    window: float
    duration: float
    score: np.ndarray
    signals: dict[str, np.ndarray]
    highlights: list[Highlight]
    source: dict[str, Any] = field(default_factory=dict)
    messages: int = 0  # chat messages analysed (not part of the saved JSON)

    @property
    def times(self) -> np.ndarray:
        return np.arange(len(self.score)) * self.window

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "source": self.source,
            "window": self.window,
            "duration": round(self.duration, 2),
            "highlights": [h.to_dict() for h in self.highlights],
            "timeline": {"score": [round(float(v), 3) for v in self.score]},
        }

    def save(self, path: str | os.PathLike[str]) -> Path:
        out = Path(path)
        out.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return out


# --------------------------------------------------------------------------- math helpers


def robust_z(values: np.ndarray) -> np.ndarray:
    """Positive robust z-score: ``(x - median) / (1.4826 * MAD)`` clipped to [0, 20]."""
    x = np.asarray(values, dtype=np.float64)
    if x.size == 0:
        return x
    med = float(np.median(x))
    dev = np.abs(x - med)
    scale = 1.4826 * float(np.median(dev))
    if scale < 1e-9:
        scale = 1.2533 * float(np.mean(dev))  # sparse signals: fall back to mean absolute deviation
    if scale < 1e-9:
        return np.zeros_like(x)
    return np.clip((x - med) / scale, 0.0, 20.0)


def _smooth(x: np.ndarray, n: int) -> np.ndarray:
    if n <= 1 or x.size == 0:
        return x
    kernel = np.ones(n) / n
    return np.convolve(np.pad(x, (n // 2, n - 1 - n // 2), mode="edge"), kernel, mode="valid")


def _resample(values: np.ndarray, src_window: float, n: int, window: float) -> np.ndarray:
    centers = (np.arange(n) + 0.5) * window
    src_centers = (np.arange(len(values)) + 0.5) * src_window
    if len(values) == 0:
        return np.zeros(n)
    return np.interp(centers, src_centers, values)


# --------------------------------------------------------------------------- detection


def _bucket_chat(messages: Iterable[ChatMessage], n: int, window: float, skip_greetings: bool = True) -> dict[str, Any]:
    rate = np.zeros(n)
    reactions = np.zeros(n)
    paid = np.zeros(n)
    authors: list[set[str]] = [set() for _ in range(n)]
    per_category = {name: np.zeros(n) for name in REACTIONS}
    for m in messages:
        i = min(n - 1, int(m.time // window))
        if i < 0:
            continue
        if m.is_paid or m.kind == "member":
            paid[i] += 1
        if skip_greetings and m.kind == "text" and is_routine(m.text):
            continue
        rate[i] += 1
        if m.author:
            authors[i].add(m.author)
        cats = classify_reactions(m.text, m.emotes)
        if cats:
            reactions[i] += 1
            for c in cats:
                per_category[c][i] += 1
    unique = np.array([len(a) for a in authors], dtype=np.float64)
    return {"rate": rate, "unique": unique, "reactions": reactions, "paid": paid, "categories": per_category}


def detect_highlights(
    messages: Sequence[ChatMessage] = (),
    *,
    duration: float | None = None,
    audio: np.ndarray | None = None,
    audio_window: float | None = None,
    heatmap: Sequence[HeatmapPoint] = (),
    laughter: np.ndarray | None = None,
    laughter_window: float | None = None,
    config: HighlightConfig | None = None,
    source: dict[str, Any] | None = None,
) -> HighlightResult:
    """Find the most exciting moments. Any subset of chat / audio / heatmap may be given.

    ``laughter`` is the optional, experimental :func:`stream2clip.audio.laughter_levels` curve.
    """
    cfg = config or HighlightConfig()
    w = cfg.window
    candidates = [duration or 0.0]
    if messages:
        candidates.append(max(m.time for m in messages) + w)
    if audio is not None and len(audio):
        candidates.append(len(audio) * (audio_window or w))
    if heatmap:
        candidates.append(max(p.end for p in heatmap))
    total = max(candidates)
    if total <= 0:
        raise ValueError("Nothing to analyse: give chat messages, audio levels, a heatmap or a duration")
    n = max(1, math.ceil(total / w))

    raw: dict[str, np.ndarray] = {}
    chat = _bucket_chat(messages, n, w, cfg.skip_greetings) if messages else None
    if chat is not None:
        for key in ("rate", "unique", "reactions", "paid"):
            raw[key] = chat[key]
    if audio is not None and len(audio):
        raw["audio"] = _resample(np.asarray(audio, dtype=np.float64), audio_window or w, n, w)
    if laughter is not None and len(laughter):
        raw["laughter"] = _resample(np.asarray(laughter, dtype=np.float64), laughter_window or w, n, w)
    if heatmap:
        centers = (np.arange(n) + 0.5) * w
        hm_centers = np.array([(p.start + p.end) / 2 for p in heatmap])
        raw["heatmap"] = np.interp(centers, hm_centers, np.array([p.value for p in heatmap]))

    signals = {key: robust_z(values) for key, values in raw.items()}
    weights = {k: v for k, v in cfg.weights.items() if k in signals and v > 0}
    # Bonus signals can lift a moment but never count against one that lacks them: they are
    # left out of the divisor, so switching one on does not thin out the other highlights.
    core = sum(v for k, v in weights.items() if k not in BONUS_SIGNALS)
    if not weights:
        score = np.zeros(n)
    else:
        score = sum(signals[k] * v for k, v in weights.items()) / (core or sum(weights.values()))
    score = _smooth(np.asarray(score, dtype=np.float64), cfg.smooth)

    highlights = _pick(score, cfg, total)
    for h in highlights:
        h.reasons, h.stats = _explain(h, raw, chat, signals, cfg)
    return HighlightResult(window=w, duration=total, score=score, signals=signals, highlights=highlights, source=source or {}, messages=len(messages))


def _pick(score: np.ndarray, cfg: HighlightConfig, total: float) -> list[Highlight]:
    w = cfg.window
    taken = np.zeros(score.size, dtype=bool)
    floor = cfg.threshold * 0.6
    found: list[Highlight] = []
    for i in np.argsort(-score, kind="stable"):
        if score[i] < cfg.threshold:
            break
        if taken[i]:
            continue
        left = right = int(i)
        while left > 0 and not taken[left - 1] and score[left - 1] >= floor:
            left -= 1
        while right < score.size - 1 and not taken[right + 1] and score[right + 1] >= floor:
            right += 1
        taken[left : right + 1] = True
        peak = (i + 0.5) * w - cfg.chat_delay
        start = left * w - cfg.chat_delay - cfg.lead
        end = (right + 1) * w - cfg.chat_delay + cfg.tail
        found.append(Highlight(rank=0, start=start, end=end, peak=peak, score=float(score[i])))

    found.sort(key=lambda h: h.start)
    merged: list[Highlight] = []
    for h in found:
        if merged and h.start - merged[-1].end <= cfg.merge_gap:
            prev = merged[-1]
            best = prev if prev.score >= h.score else h
            merged[-1] = Highlight(0, prev.start, max(prev.end, h.end), best.peak, max(prev.score, h.score))
        else:
            merged.append(h)

    for h in merged:
        _clamp(h, cfg, total)
    merged.sort(key=lambda h: -h.score)
    merged = merged[: cfg.top]
    for rank, h in enumerate(merged, start=1):
        h.rank = rank
    return merged


def _clamp(h: Highlight, cfg: HighlightConfig, total: float) -> None:
    if h.end - h.start > cfg.max_length:
        h.start = max(h.start, h.peak - cfg.max_length * 0.6)
        h.end = h.start + cfg.max_length
    if h.end - h.start < cfg.min_length:
        pad = (cfg.min_length - (h.end - h.start)) / 2
        h.start -= pad
        h.end += pad
    if h.start < 0:
        h.end = min(total, h.end - h.start)
        h.start = 0.0
    if h.end > total:
        h.start = max(0.0, h.start - (h.end - total))
        h.end = total
    h.peak = min(max(h.peak, h.start), h.end)


def _explain(h: Highlight, raw: dict[str, np.ndarray], chat: dict[str, Any] | None, signals: dict[str, np.ndarray], cfg: HighlightConfig) -> tuple[list[str], dict[str, float]]:
    w = cfg.window
    # Signals live on the chat clock: undo the delay correction when reading them back.
    lo = max(0, int((h.start + cfg.chat_delay) // w))
    hi = max(lo + 1, int(math.ceil((h.end + cfg.chat_delay) / w)))
    peak_i = min(len(next(iter(signals.values()))) - 1, max(0, int((h.peak + cfg.chat_delay) // w))) if signals else 0
    reasons: list[str] = []
    stats: dict[str, float] = {}
    if chat is not None:
        rate = raw["rate"]
        base = max(1e-9, float(np.median(rate)))
        local = float(rate[max(0, peak_i - 1) : peak_i + 2].mean())
        ratio = local / base if base > 1e-6 else float("inf")
        stats["chat_per_min"] = local * 60 / w
        stats["chat_ratio"] = ratio if math.isfinite(ratio) else 99.0
        if local > 0:
            per_min = local * 60 / w
            ratio_text = f"평소의 {ratio:.1f}배" if math.isfinite(ratio) and base > 1e-6 else "평소엔 거의 없음"
            reasons.append(f"채팅 급증 {per_min:.0f}/분 ({ratio_text})")
        cats = {c: int(v[lo:hi].sum()) for c, v in chat["categories"].items()}
        total_react = int(raw["reactions"][lo:hi].sum())
        stats["reactions"] = total_react
        for name, count in cats.items():
            stats[f"react_{name}"] = count
        if total_react:
            detail = " · ".join(f"{_LABELS[c]} {n}" for c, n in sorted(cats.items(), key=lambda kv: -kv[1]) if n)
            reasons.append(f"반응 {total_react}개 ({detail})")
        paid = int(raw["paid"][lo:hi].sum())
        stats["paid"] = paid
        if paid:
            reasons.append(f"슈퍼챗·후원·멤버십 {paid}건")
        stats["messages"] = float(rate[lo:hi].sum())
    if "audio" in raw:
        audio = raw["audio"]
        delta = float(audio[max(0, peak_i - 1) : peak_i + 2].max() - np.median(audio))
        stats["audio_db_above"] = delta
        if delta >= 3:
            reasons.append(f"음량 +{delta:.0f} dB")
    if "laughter" in raw:
        burst = float(signals["laughter"][max(0, peak_i - 2) : peak_i + 2].max())
        stats["laughter_z"] = burst
        if burst >= 2:
            reasons.append("웃음소리 같은 소리 (추정)")
    if "heatmap" in raw:
        value = float(raw["heatmap"][lo:hi].max())
        stats["heatmap"] = value
        if signals["heatmap"][lo:hi].max() >= 1:
            reasons.append(f"많이 다시 본 구간 ({value:.2f})")
    return reasons, stats


def mark_singing(result: HighlightResult, sections: Sequence[tuple[float, float]], *, drop: bool = False, mostly: float = 0.5) -> HighlightResult:
    """Note on every highlight how much of it is inside a singing section (``stats["singing"]``, 0..1).

    Songs matter for clipping: music rights are separate from the stream, and some agency
    guidelines forbid reposting singing parts. With ``drop`` the highlights that are
    ``mostly`` a song are removed and the rest re-ranked.
    """
    kept: list[Highlight] = []
    for h in result.highlights:
        inside = sum(max(0.0, min(h.end, end) - max(h.start, start)) for start, end in sections)
        fraction = min(1.0, inside / max(h.duration, 1e-9))
        h.stats["singing"] = fraction
        if fraction > 0 and not any("노래 구간" in reason for reason in h.reasons):
            h.reasons.append(f"노래 구간과 {fraction:.0%} 겹침")
        if not (drop and fraction >= mostly):
            kept.append(h)
    if drop:
        for rank, h in enumerate(sorted(kept, key=lambda h: -h.score), start=1):
            h.rank = rank
        result.highlights = sorted(kept, key=lambda h: h.rank)
    return result


def load_highlights(path: str | os.PathLike[str]) -> list[Highlight]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = data.get("highlights", data if isinstance(data, list) else [])
    out = []
    for i, item in enumerate(items, start=1):
        out.append(
            Highlight(
                rank=int(item.get("rank", i)),
                start=float(item["start"]),
                end=float(item["end"]),
                peak=float(item.get("peak", (float(item["start"]) + float(item["end"])) / 2)),
                score=float(item.get("score", 0)),
                reasons=list(item.get("reasons", [])),
                stats=dict(item.get("stats", {})),
            )
        )
    return out


# --------------------------------------------------------------------------- visualisation


def _clock(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def render_timeline(result: HighlightResult, path: str | os.PathLike[str] | None = None, *, width: int = 1600, height: int = 420):
    """Draw the excitement timeline with highlight brackets (brand colours) as a PIL image."""
    from PIL import Image, ImageDraw

    from .editor.fonts import load_font
    from .brand import HIGHLIGHT, INK, LIVE_PINK, MUTED_BAR, PAPER

    img = Image.new("RGB", (width, height), INK)
    draw = ImageDraw.Draw(img)
    pad_l, pad_r, top, bottom = 60, 40, 104, 70
    plot_w, plot_h = width - pad_l - pad_r, height - top - bottom
    title_font, label_font, small = load_font(26), load_font(18), load_font(15)
    draw.text((pad_l, 20), "stream2clip · 하이라이트 타임라인", font=title_font, fill=PAPER)
    summary = f"{len(result.highlights)}개 구간 · 길이 {_clock(result.duration)}"
    draw.text((width - pad_r - draw.textlength(summary, font=label_font), 26), summary, font=label_font, fill="#8A8499")

    score = result.score
    n = len(score)
    peak = max(float(score.max()) if n else 1.0, result.highlights[0].score if result.highlights else 1.0, 1e-6)
    bar_count = max(1, min(n, plot_w // 6))
    edges = np.linspace(0, n, bar_count + 1).round().astype(int)  # equal time spans per bar
    bins = [score[edges[k] : max(edges[k] + 1, edges[k + 1])] for k in range(bar_count)] if n else []
    bar_w = plot_w / bar_count

    def x_of(t: float) -> float:
        return pad_l + plot_w * min(1.0, max(0.0, t / max(result.duration, 1e-6)))

    spans = [(h.start, h.end) for h in result.highlights]
    base_y = top + plot_h
    for k, chunk in enumerate(bins):
        v = float(chunk.max())
        t_mid = (k + 0.5) / bar_count * result.duration
        inside = any(s <= t_mid <= e for s, e in spans)
        h = max(3.0, plot_h * 0.92 * v / peak)
        x0 = pad_l + k * bar_w + 1
        draw.rounded_rectangle((x0, base_y - h, x0 + max(1.0, bar_w - 2), base_y), radius=min(3, int(bar_w / 2)), fill=LIVE_PINK if inside else MUTED_BAR)

    for h in result.highlights:
        x0, x1 = x_of(h.start), x_of(h.end)
        y0, y1 = top - 8, base_y + 8
        for x, d in ((x0, 1), (x1, -1)):
            draw.line((x, y0, x, y1), fill=LIVE_PINK, width=3)
            draw.line((x, y0, x + 8 * d, y0), fill=LIVE_PINK, width=3)
            draw.line((x, y1, x + 8 * d, y1), fill=LIVE_PINK, width=3)
        draw.text((x0 + 4, top - 36), f"{h.rank:02d}", font=label_font, fill=HIGHLIGHT if h.rank == 1 else LIVE_PINK)

    ticks = 4 if result.duration > 60 else 2
    for k in range(ticks + 1):
        t = result.duration * k / ticks
        label = _clock(t)
        tw = draw.textlength(label, font=small)
        x = min(max(pad_l, x_of(t) - tw / 2), width - pad_r - tw)
        draw.text((x, base_y + 22), label, font=small, fill="#8A8499")
    if path is not None:
        img.save(path)
    return img
