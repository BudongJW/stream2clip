"""Chat archives -> a normalized list of :class:`ChatMessage`.

Supported inputs (auto-detected by :func:`load_chat`):

* yt-dlp YouTube live chat replay (``*.live_chat.json``, one JSON action per line) -
  also when it was recorded while the stream was live
* chat-downloader (xenova) JSON output (a list of message dicts)
* TwitchDownloader chat JSON (``{"comments": [...]}``)
* CHZZK replay chat (the ``videoChats`` pages of its API) and SOOP replay chat XML -
  ``stream2clip fetch`` collects both and saves them already normalized
* a session file written while the stream was on air (:mod:`stream2clip.session`)
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
import math
import os
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Iterable, Iterator

__all__ = ["ChatMessage", "load_chat", "live_messages", "parse_amount", "parse_chzzk", "parse_soop", "chzzk_live_message", "soop_live_message", "role_of", "save_chat_jsonl", "author_key"]


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
    #: "owner" (the streamer), "moderator", or "" - used for the markers a streamer leaves in chat.
    role: str = ""

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


_ROLES = {
    "owner": "owner", "broadcaster": "owner", "streamer": "owner",
    "moderator": "moderator", "mod": "moderator", "streaming_channel_manager": "moderator", "streaming_chat_manager": "moderator",
}


def role_of(*names: Any) -> str:
    """The first of ``names`` (badge types, role codes) that says streamer or moderator."""
    found = {_ROLES.get(str(name).strip().lower(), "") for name in names if name}
    return "owner" if "owner" in found else ("moderator" if "moderator" in found else "")


def _youtube_role(renderer: dict[str, Any]) -> str:
    badges = (b.get("liveChatAuthorBadgeRenderer", {}) for b in renderer.get("authorBadges") or [] if isinstance(b, dict))
    return role_of(*((badge.get("icon") or {}).get("iconType") for badge in badges))


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
        return ChatMessage(time=max(0.0, time), text=text, author=author_key(author), kind=kind, amount=amount, currency=currency, emotes=emotes, role=_youtube_role(r))
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
    live: list[int] = []  # recorded while the stream was live: no video offset, only the time it was sent
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
            stamp = _item_timestamp(item)
            on_air = offset is None and line.get("isLive") and stamp is not None
            msg = _parse_youtube_item(item, stamp if on_air else offset)
            if msg is not None:
                if on_air:
                    live.append(len(out))
                out.append(msg)
                stamps.append(stamp)
    if live:  # there is no "start of the video" in such a file: count from its first message
        start = min(out[i].time for i in live)
        for i in live:
            out[i] = replace(out[i], time=out[i].time - start)
    return _drop_outside_stream(out, stamps)


def live_messages(raw: str) -> list[ChatMessage]:
    """The messages in one line of a chat that is being recorded while the stream is on air.

    Understands the lines yt-dlp writes for a live YouTube chat and plain JSON objects
    (``{"text": ..., "author": ..., "time": ...}``, the fields of the generic format).
    ``time`` is wall-clock seconds here - from YouTube's ``timestampUsec`` or the line's
    ``time`` / ``timestamp`` - and NaN when the line has none (the reader then uses "now").
    """
    try:
        line = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(line, dict):
        return []
    found: list[ChatMessage] = []
    if "replayChatItemAction" in line or "addChatItemAction" in line or "actions" in line:
        for _offset, action in _youtube_actions(line):
            item = (action.get("addChatItemAction") or {}).get("item", {})
            msg = _parse_youtube_item(item, 0.0)
            if msg is not None:
                stamp = _item_timestamp(item)
                found.append(replace(msg, time=stamp if stamp is not None else math.nan))
        return found
    keys = {str(k).lower().strip() for k in line}
    stamp = next((line[k] for k in line if str(k).lower().strip() in ("time", "timestamp", "t") and line[k] not in (None, "")), None)
    if not keys & {"time", "time_in_seconds", "offset", "seconds", "t"}:
        line = {**line, "time": 0}
    msg = _generic_row(line)
    if msg is None:
        return []
    try:
        when = float(stamp) if stamp is not None else math.nan
    except (TypeError, ValueError):
        when = math.nan
    if when > 1e11:  # milliseconds
        when /= 1000
    return [replace(msg, time=when)]


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
                role=role_of(*(name for badge in author.get("badges") or [] if isinstance(badge, dict) for name in (badge.get("name"), badge.get("title")))),
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
                role=role_of(*(badge.get("_id") for badge in message.get("user_badges") or [] if isinstance(badge, dict))),
            )
        )
    return out


# --------------------------------------------------------------------------- CHZZK / SOOP replays

_CHZZK_EMOJI = re.compile(r"\{:([^:{}\s]+):\}")
_SOOP_SESSION = re.compile(r"\(\d+\)$")


def _json_object(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    try:
        value = json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def parse_chzzk(data: Any) -> list[ChatMessage]:
    """CHZZK replay chat: one API page (``{"content": {"videoChats": [...]}}``) or a list of pages.

    ``playerMessageTime`` is the offset in the replay (ms). Emoji tokens ``{:name:}`` become
    ``:name:``, donations (``messageTypeCode`` 10) carry ``payAmount`` in won, and messages
    hidden by moderation are skipped.
    """
    pages = data if isinstance(data, list) else [data]
    out: list[ChatMessage] = []
    for page in pages:
        content = page.get("content", page) if isinstance(page, dict) else {}
        for m in content.get("videoChats") or []:
            if m.get("messageStatusType", "NORMAL") != "NORMAL" or m.get("playerMessageTime") is None:
                continue
            extras = _json_object(m.get("extras"))
            raw = m.get("content") or ""
            amount = float(extras.get("payAmount") or 0)
            paid = m.get("messageTypeCode") == 10 or amount > 0
            out.append(
                ChatMessage(
                    time=max(0.0, float(m["playerMessageTime"]) / 1000),
                    text=_CHZZK_EMOJI.sub(lambda g: f":{g.group(1)}:", raw),
                    author=author_key(str(m.get("userIdHash") or "")),
                    kind="paid" if paid else "text",
                    amount=amount,
                    currency="KRW" if amount else None,
                    emotes=tuple(f":{name}:" for name in _CHZZK_EMOJI.findall(raw)),
                    role=role_of(_json_object(m.get("profile")).get("userRoleCode")),
                )
            )
    return out


def chzzk_live_message(item: dict[str, Any]) -> ChatMessage | None:
    """One message of CHZZK's live chat (an entry of ``bdy`` in a chat or donation frame); ``None`` when it is hidden.

    The fields are the live names of what :func:`parse_chzzk` reads from a replay: ``msg``,
    ``msgTime`` (wall clock, ms), ``uid``, ``msgTypeCode``. The time is wall-clock seconds.
    """
    if item.get("msgStatusType", "NORMAL") != "NORMAL":
        return None
    extras = _json_object(item.get("extras"))
    raw = str(item.get("msg") or "")
    amount = float(extras.get("payAmount") or 0)
    paid = item.get("msgTypeCode") == 10 or amount > 0
    stamp = item.get("msgTime") or item.get("ctime")
    return ChatMessage(
        time=float(stamp) / 1000 if stamp else math.nan,
        text=_CHZZK_EMOJI.sub(lambda g: f":{g.group(1)}:", raw),
        author=author_key(str(item.get("uid") or "")),
        kind="paid" if paid else "text",
        amount=amount,
        currency="KRW" if amount else None,
        emotes=tuple(f":{name}:" for name in _CHZZK_EMOJI.findall(raw)),
        role=role_of(_json_object(item.get("profile")).get("userRoleCode")),
    )


def soop_live_message(packet: bytes, streamer: str = "") -> ChatMessage | None:
    """One packet of SOOP's live chat as a message; ``None`` for everything that is not chat or a donation.

    A packet is ``ESC TAB``, a 4-digit service number, a 6-digit body length, 2 more digits,
    then the fields, each ended by a form feed. Service 5 is a chat line (message, user id),
    18 star balloons (streamer, user id, nickname, count), 87 ad balloons and 105 video
    balloons (count further back). Packets carry no time: the reader uses "now".
    ``streamer`` is the id of the channel's owner, whose own lines get the role "owner".
    """
    if len(packet) < 14 or packet[:2] != b"\x1b\t":
        return None
    service = packet[2:6]
    parts = packet[14:].decode("utf-8", errors="replace").split("\x0c")

    def who(value: str) -> tuple[str, str]:
        name = _SOOP_SESSION.sub("", value)
        return author_key(name), ("owner" if streamer and name == streamer else "")

    def balloons(user: int, count: int, unit: str) -> ChatMessage | None:
        if len(parts) <= max(user, count) or not parts[count].isdigit():
            return None
        return ChatMessage(math.nan, "", who(parts[user])[0], kind="paid", amount=float(parts[count]), currency=unit)

    if service == b"0005" and len(parts) > 2:
        author, role = who(parts[2])
        return ChatMessage(math.nan, parts[1], author, role=role)
    if service == b"0018":
        return balloons(2, 4, "별풍선")
    if service == b"0087":
        return balloons(3, 10, "애드벌룬")
    if service == b"0105":
        return balloons(3, 5, "별풍선")
    return None


def parse_soop(text: str, *, offset: float = 0.0) -> list[ChatMessage]:
    """SOOP replay chat XML (one ``ChatLoadSplit`` response).

    ``<t>`` is seconds into the file; ``offset`` is added for VODs split into several files.
    Star balloons and ad balloons are paid events with the balloon count as the amount,
    OGQ stickers are stickers, fan club joins and subscriptions are membership events.
    The same viewer on two devices (``id(2)``) counts as one chatter.
    """
    import xml.etree.ElementTree as ET

    out: list[ChatMessage] = []
    for el in ET.fromstring(text):
        stamp = el.findtext("t")
        if stamp is None:
            continue
        time = max(0.0, float(stamp) + offset)
        author = author_key(_SOOP_SESSION.sub("", el.findtext("u") or el.findtext("s") or ""))
        if el.tag == "chat":
            out.append(ChatMessage(time, el.findtext("m") or "", author))
        elif el.tag in ("balloon", "adballoon", "vodballoon"):
            count = float(el.findtext("c") or 0)
            out.append(ChatMessage(time, el.findtext("m") or "", author, kind="paid", amount=count, currency="애드벌룬" if el.tag == "adballoon" else "별풍선"))
        elif el.tag == "ogq":
            out.append(ChatMessage(time, el.findtext("m") or "", author, kind="sticker"))
        elif el.tag in ("fanclub", "subscription", "follow"):
            out.append(ChatMessage(time, "", author, kind="member"))
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
        role=role_of(keys.get("role")),
    )


def _load_generic(rows: Iterable[dict[str, Any]]) -> list[ChatMessage]:
    return [msg for msg in (_generic_row(r) for r in rows) if msg is not None]


# --------------------------------------------------------------------------- entry points


def load_chat(path: str | os.PathLike[str], *, format: str | None = None) -> list[ChatMessage]:
    """Load and normalize a chat archive; messages are returned sorted by time.

    ``format``: ``"youtube"`` (yt-dlp live_chat), ``"chat-downloader"``,
    ``"twitch"`` (TwitchDownloader), ``"chzzk"``, ``"soop"``, ``"csv"``, ``"jsonl"``,
    ``"session"`` (a session file of :mod:`stream2clip.recorder`: its chat and markers, timed
    from when OBS started streaming) or ``None`` to detect.
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
    elif fmt == "chzzk":
        msgs = parse_chzzk(json.loads(text))
    elif fmt == "soop":
        msgs = parse_soop(text)
    elif fmt == "csv":
        msgs = _load_generic(csv.DictReader(io.StringIO(text)))
    elif fmt == "jsonl":
        msgs = _load_generic(json.loads(line) for line in text.splitlines() if line.strip())
    elif fmt == "json":
        msgs = _load_generic(json.loads(text))
    elif fmt == "session":  # what the session recorder wrote while the stream was on air
        from .session import load_session

        msgs = load_session(p).messages()
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
    if '"videoChats"' in head and "playerMessageTime" in text[:200000]:
        return "chzzk"
    if head.startswith("<") and "<root" in head and ("<chat>" in text or "<balloon>" in text):
        return "soop"
    if head.startswith("{") and '"comments"' in head and "content_offset_seconds" in text[:200000]:
        return "twitch"
    if head.startswith("["):
        return "chat-downloader" if "time_in_seconds" in head else "json"
    if head.startswith("{") and '"stream2clip.session/v1"' in head.split("\n", 1)[0]:
        return "session"
    if head.startswith("{"):
        return "jsonl"
    return "csv"


def save_chat_jsonl(messages: Iterable[ChatMessage], path: str | os.PathLike[str]) -> Path:
    """Write the normalized form (one JSON object per line) - readable back with ``format="jsonl"``."""
    out = Path(path)
    with out.open("w", encoding="utf-8") as fh:
        for m in messages:
            fh.write(json.dumps({"time": round(m.time, 3), "text": m.text, "author": m.author, "kind": m.kind, "amount": m.amount, "currency": m.currency, **({"role": m.role} if m.role else {})}, ensure_ascii=False) + "\n")
    return out
