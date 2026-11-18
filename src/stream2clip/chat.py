"""Chat archives -> a normalized list of :class:`ChatMessage`.

Supported inputs (auto-detected by :func:`load_chat`):

* yt-dlp YouTube live chat replay (``*.live_chat.json``, one JSON action per line)
* chat-downloader (xenova) JSON output (a list of message dicts)
* TwitchDownloader chat JSON (``{"comments": [...]}``)
* generic CSV / JSONL with at least ``time`` and ``text`` columns
  (``author``, ``amount``, ``currency``, ``kind`` optional) - handy for CHZZK /
  SOOP collectors or any custom scraper.

Author names are hashed: highlight detection only needs to tell chatters apart.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator

__all__ = ["ChatMessage", "load_chat", "parse_amount", "save_chat_jsonl", "author_key"]


@dataclass(frozen=True)
class ChatMessage:
    """One chat event. ``time`` is seconds from the start of the VOD."""

    time: float
    text: str
    author: str = ""
    kind: str = "text"  # text | paid | member | gift | sticker
    amount: float = 0.0
    currency: str | None = None
    emotes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_paid(self) -> bool:
        return self.kind in ("paid", "sticker", "gift") or self.amount > 0


def author_key(name_or_id: str) -> str:
    """Stable anonymous id for an author (first 12 hex chars of SHA-1)."""
    if not name_or_id:
        return ""
    return hashlib.sha1(name_or_id.encode("utf-8")).hexdigest()[:12]


_AMOUNT = re.compile(r"([^\d\s.,]*)\s*([\d.,]+)\s*([^\d\s.,]*)")


def parse_amount(text: str | None) -> tuple[float, str | None]:
    """Parse ``"¥1,000"``, ``"₩5,000"``, ``"$4.99"``, ``"1.000,50 €"`` into ``(amount, currency)``."""
    if not text:
        return 0.0, None
    match = _AMOUNT.search(text.strip())
    if not match:
        return 0.0, None
    prefix, number, suffix = match.groups()
    currency = (prefix or suffix or "").strip() or None
    if "," in number and "." in number:
        # whichever separator comes last is the decimal point
        if number.rfind(",") > number.rfind("."):
            number = number.replace(".", "").replace(",", ".")
        else:
            number = number.replace(",", "")
    elif "," in number:
        head, _, tail = number.rpartition(",")
        number = number.replace(",", "") if len(tail) == 3 else head.replace(",", "") + "." + tail
    try:
        return float(number), currency
    except ValueError:
        return 0.0, currency


# --------------------------------------------------------------------------- yt-dlp live chat


def _runs_text(message: dict[str, Any] | None) -> tuple[str, tuple[str, ...]]:
    if not message:
        return "", ()
    if "simpleText" in message:
        return message["simpleText"], ()
    parts: list[str] = []
    emotes: list[str] = []
    for run in message.get("runs", []):
        if "text" in run:
            parts.append(run["text"])
        elif "emoji" in run:
            emoji = run["emoji"]
            shortcut = (emoji.get("shortcuts") or [None])[0]
            label = shortcut or emoji.get("emojiId", "")
            if emoji.get("isCustomEmoji"):
                emotes.append(label)
                parts.append(label)
            else:
                parts.append(emoji.get("emojiId", label))
    return "".join(parts), tuple(emotes)


def _youtube_actions(line: dict[str, Any]) -> Iterator[tuple[float | None, dict[str, Any]]]:
    replay = line.get("replayChatItemAction")
    if replay is not None:
        offset = replay.get("videoOffsetTimeMsec")
        for action in replay.get("actions", []):
            yield (int(offset) / 1000 if offset is not None else None), action
    else:
        for action in line.get("actions", []) or [line]:
            yield None, action


def _parse_youtube_item(item: dict[str, Any], offset: float | None) -> ChatMessage | None:
    renderers = {
        "liveChatTextMessageRenderer": "text",
        "liveChatPaidMessageRenderer": "paid",
        "liveChatPaidStickerRenderer": "sticker",
        "liveChatMembershipItemRenderer": "member",
        "liveChatSponsorshipsGiftPurchaseAnnouncementRenderer": "gift",
    }
    for key, kind in renderers.items():
        r = item.get(key)
        if r is None:
            continue
        if kind == "gift":
            header = r.get("header", {}).get("liveChatSponsorshipsHeaderRenderer", {})
            text, emotes = _runs_text(header.get("primaryText"))
            author = header.get("authorName", {}).get("simpleText", "") or r.get("authorExternalChannelId", "")
        else:
            text, emotes = _runs_text(r.get("message") or r.get("headerSubtext"))
            author = r.get("authorExternalChannelId") or r.get("authorName", {}).get("simpleText", "")
        amount, currency = parse_amount(r.get("purchaseAmountText", {}).get("simpleText"))
        time = offset
        if time is None and "videoOffsetTimeMsec" in r:
            time = int(r["videoOffsetTimeMsec"]) / 1000
        if time is None:
            return None
        return ChatMessage(time=max(0.0, time), text=text, author=author_key(author), kind=kind, amount=amount, currency=currency, emotes=emotes)
    return None


def _item_timestamp(item: dict[str, Any]) -> float | None:
    """Wall-clock time the item was sent (``timestampUsec``), in seconds."""
    for renderer in item.values():
        if isinstance(renderer, dict) and renderer.get("timestampUsec"):
            try:
                return int(renderer["timestampUsec"]) / 1e6
            except (TypeError, ValueError):
                return None
    return None


def _drop_outside_stream(messages: list[ChatMessage], stamps: list[float | None]) -> list[ChatMessage]:
    """Remove messages that sit at 0:00 only because they were not sent during the stream.

    The replay gives everything typed in the waiting room (and the odd message sent
    after the stream ended) a video offset of 0. On a real archive that was ~50
    messages stacked on the first second - a fake burst right at the start. The
    wall-clock ``timestampUsec`` minus the offset is the same for every message sent
    during the stream (it is the stream's start time), so offset-0 messages whose
    timestamp is not that start time are dropped.
    """
    starts = sorted(ts - m.time for m, ts in zip(messages, stamps) if ts is not None and m.time > 0)
    if len(starts) < 5:
        return messages
    start = starts[len(starts) // 2]
    return [m for m, ts in zip(messages, stamps) if not (m.time == 0 and ts is not None and abs(ts - start) > 2.0)]


def _load_ytdlp_live_chat(lines: Iterable[str]) -> list[ChatMessage]:
    out: list[ChatMessage] = []
    stamps: list[float | None] = []
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            line = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for offset, action in _youtube_actions(line):
            add = action.get("addChatItemAction")
            if add is None:
                continue
            item = add.get("item", {})
            msg = _parse_youtube_item(item, offset)
            if msg is not None:
                out.append(msg)
                stamps.append(_item_timestamp(item))
    return _drop_outside_stream(out, stamps)


# --------------------------------------------------------------------------- other formats


def _load_chat_downloader(items: list[dict[str, Any]]) -> list[ChatMessage]:
    out: list[ChatMessage] = []
    kinds = {"paid_message": "paid", "paid_sticker": "sticker", "membership_item": "member", "sponsorships_gift_purchase_announcement": "gift"}
    for item in items:
        time = item.get("time_in_seconds")
        if time is None:
            continue
        author = item.get("author", {})
        money = item.get("money") or {}
        emotes = tuple(e.get("name", "") for e in item.get("emotes", []) if isinstance(e, dict))
        out.append(
            ChatMessage(
                time=max(0.0, float(time)),
                text=item.get("message", "") or "",
                author=author_key(str(author.get("id") or author.get("name") or "")),
                kind=kinds.get(item.get("message_type", ""), "text"),
                amount=float(money.get("amount", 0) or 0),
                currency=money.get("currency"),
                emotes=emotes,
            )
        )
    return out


def _load_twitch_downloader(data: dict[str, Any]) -> list[ChatMessage]:
    out: list[ChatMessage] = []
    for comment in data.get("comments", []):
        message = comment.get("message", {})
        commenter = comment.get("commenter") or {}
        emotes = tuple(
            frag.get("text", "")
            for frag in message.get("fragments", []) or []
            if frag.get("emoticon")
        )
        bits = float(message.get("bits_spent", 0) or 0)
        out.append(
            ChatMessage(
                time=max(0.0, float(comment.get("content_offset_seconds", 0))),
                text=message.get("body", "") or "",
                author=author_key(str(commenter.get("_id") or commenter.get("name") or commenter.get("display_name") or "")),
                kind="paid" if bits else "text",
                amount=bits,
                currency="bits" if bits else None,
                emotes=emotes,
            )
        )
    return out


def _parse_time(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if ":" in text:
        seconds = 0.0
        for part in text.split(":"):
            seconds = seconds * 60 + float(part)
        return seconds
    return float(text)


def _generic_row(row: dict[str, Any]) -> ChatMessage | None:
    keys = {k.lower().strip(): v for k, v in row.items() if k is not None}
    time = next((keys[k] for k in ("time", "time_in_seconds", "offset", "seconds", "t") if k in keys and keys[k] not in (None, "")), None)
    text = next((keys[k] for k in ("text", "message", "body", "content", "msg") if k in keys), None)
    if time is None or text is None:
        return None
    amount_raw = keys.get("amount")
    if isinstance(amount_raw, (int, float)):
        amount, currency = float(amount_raw), keys.get("currency")
    else:
        amount, currency = parse_amount(str(amount_raw)) if amount_raw else (0.0, None)
        currency = keys.get("currency") or currency
    kind = str(keys.get("kind") or keys.get("type") or ("paid" if amount else "text"))
    return ChatMessage(
        time=max(0.0, _parse_time(time)),
        text=str(text),
        author=author_key(str(keys.get("author") or keys.get("user") or keys.get("name") or "")),
        kind=kind,
        amount=amount,
        currency=currency,
    )


def _load_generic(rows: Iterable[dict[str, Any]]) -> list[ChatMessage]:
    return [msg for msg in (_generic_row(r) for r in rows) if msg is not None]


# --------------------------------------------------------------------------- entry points


def load_chat(path: str | os.PathLike[str], *, format: str | None = None) -> list[ChatMessage]:
    """Load and normalize a chat archive; messages are returned sorted by time.

    ``format``: ``"youtube"`` (yt-dlp live_chat), ``"chat-downloader"``,
    ``"twitch"`` (TwitchDownloader), ``"csv"``, ``"jsonl"`` or ``None`` to detect.
    """
    p = Path(path)
    text = p.read_text(encoding="utf-8-sig")
    fmt = format or _detect(p, text)
    if fmt == "youtube":
        msgs = _load_ytdlp_live_chat(text.splitlines())
    elif fmt == "chat-downloader":
        msgs = _load_chat_downloader(json.loads(text))
    elif fmt == "twitch":
        msgs = _load_twitch_downloader(json.loads(text))
    elif fmt == "csv":
        msgs = _load_generic(csv.DictReader(io.StringIO(text)))
    elif fmt == "jsonl":
        msgs = _load_generic(json.loads(line) for line in text.splitlines() if line.strip())
    elif fmt == "json":
        msgs = _load_generic(json.loads(text))
    else:
        raise ValueError(f"Unknown chat format {fmt!r}")
    msgs.sort(key=lambda m: m.time)
    return msgs


def _detect(path: Path, text: str) -> str:
    head = text.lstrip()[:4000]
    if path.suffix.lower() == ".csv":
        return "csv"
    if "replayChatItemAction" in head or "addChatItemAction" in head:
        return "youtube"
    if head.startswith("{") and '"comments"' in head and "content_offset_seconds" in text[:200000]:
        return "twitch"
    if head.startswith("["):
        return "chat-downloader" if "time_in_seconds" in head else "json"
    if head.startswith("{"):
        return "jsonl"
    return "csv"


def save_chat_jsonl(messages: Iterable[ChatMessage], path: str | os.PathLike[str]) -> Path:
    """Write the normalized form (one JSON object per line) - readable back with ``format="jsonl"``."""
    out = Path(path)
    with out.open("w", encoding="utf-8") as fh:
        for m in messages:
            fh.write(json.dumps({"time": round(m.time, 3), "text": m.text, "author": m.author, "kind": m.kind, "amount": m.amount, "currency": m.currency}, ensure_ascii=False) + "\n")
    return out
