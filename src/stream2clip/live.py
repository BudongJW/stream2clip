"""Live mode: watch the chat while a stream is on air and act when it surges.

The offline detector reads a whole chat replay and ranks its moments. On air there is no
"whole" yet, so :class:`SurgeDetector` scores every window of chat against the windows
before it - with the same signals and the same robust z-score as
:func:`stream2clip.highlights.detect_highlights` - and reports a :class:`Trigger` when one
stands out. ``stream2clip live`` then saves OBS's replay buffer and cuts the moment out::

    stream2clip live https://www.youtube.com/watch?v=VIDEO_ID -o clips

Chat comes from anything with a ``read()`` that returns the new messages:
:class:`FileFollower` follows a file that some collector keeps appending to, and
:class:`YtDlpLiveChat` runs yt-dlp for a YouTube stream and follows what it writes.
Message times are wall-clock seconds; a message without one counts as "now".
"""

from __future__ import annotations

import math
import os
import subprocess
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol, Sequence

import numpy as np

from .chat import ChatMessage, live_messages
from .highlights import _LABELS, REACTIONS, classify_reactions, is_routine, robust_z

__all__ = ["LiveConfig", "Trigger", "SurgeDetector", "simulate", "ChatSource", "FileFollower", "YtDlpLiveChat", "watch", "clip_span", "ReplayClipper", "SavedClip"]


@dataclass(frozen=True)
class LiveConfig:
    #: Chat is counted in windows of this many seconds.
    window: float = 5.0
    #: Score a window needs to fire (weighted robust z-score, as in the offline detector).
    threshold: float = 3.5
    #: The score is averaged over this many windows: with 2 a modest surge has to last, a huge one still fires alone.
    smooth: int = 2
    #: The "normal" level is taken from this many seconds of chat before the window.
    history: float = 900.0
    #: Nothing fires until this many seconds of chat have been seen.
    warmup: float = 120.0
    #: A window with fewer messages is never a surge, however quiet the chat was before.
    min_messages: int = 5
    #: Seconds between two triggers (one moment makes the chat surge for a while).
    cooldown: float = 90.0
    #: Messages may arrive this late (yt-dlp asks YouTube about every 10 seconds).
    lag: float = 12.0
    #: Viewers react this long after the moment - where the clip is cut, not when it fires.
    chat_delay: float = 8.0
    #: Seconds kept before the moment and after the surge.
    lead: float = 20.0
    tail: float = 10.0
    skip_greetings: bool = True
    weights: dict[str, float] = field(default_factory=lambda: {"rate": 0.30, "unique": 0.20, "reactions": 0.30, "paid": 0.10})

    def __post_init__(self) -> None:
        if self.window <= 0 or self.history < self.window or self.cooldown < 0 or self.lag < 0 or self.smooth < 1:
            raise ValueError("window must be > 0, history >= window, cooldown and lag >= 0, smooth >= 1")


@dataclass
class Trigger:
    """A window of chat that stood out. ``time`` is the end of that window on the chat's clock."""

    time: float
    score: float
    reasons: list[str] = field(default_factory=list)
    stats: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"time": round(self.time, 2), "score": round(self.score, 2), "reasons": list(self.reasons), "stats": {k: round(v, 2) for k, v in self.stats.items()}}


class _Bucket:
    __slots__ = ("rate", "authors", "reactions", "paid", "categories")

    def __init__(self) -> None:
        self.rate = 0
        self.authors: set[str] = set()
        self.reactions = 0
        self.paid = 0
        self.categories = dict.fromkeys(REACTIONS, 0)

    def values(self) -> dict[str, float]:
        return {"rate": float(self.rate), "unique": float(len(self.authors)), "reactions": float(self.reactions), "paid": float(self.paid)}


class SurgeDetector:
    """Feed it messages as they arrive; :meth:`advance` returns the windows that stood out.

    A window is judged once it can no longer change: ``lag`` seconds after its end, or as
    soon as a later message has been seen. With ``live_from`` set, windows that ended
    before that time only build the history (the backlog a collector delivers at the start).
    """

    def __init__(self, config: LiveConfig | None = None, *, live_from: float | None = None) -> None:
        self.config = config or LiveConfig()
        self.live_from = live_from
        self.triggers: list[Trigger] = []
        self.messages = 0
        self.late = 0  # messages for a window that had already been judged
        self._open: dict[int, _Bucket] = {}
        self._next: int | None = None  # index of the oldest window not judged yet
        self._newest = -math.inf  # time of the newest message
        size = max(1, int(round(self.config.history / self.config.window)))
        self._history: dict[str, deque[float]] = {key: deque(maxlen=size) for key in ("rate", "unique", "reactions", "paid")}
        self._last_fired = -math.inf
        self._scores: deque[float] = deque(maxlen=self.config.smooth)

    # ------------------------------------------------------------------ input
    def add(self, message: ChatMessage, now: float | None = None) -> None:
        """Count one message. ``now`` stands in for a message that carries no time of its own."""
        t = message.time
        if not math.isfinite(t):
            if now is None:
                return
            t = now
        index = int(t // self.config.window)
        if self._next is not None and index < self._next:
            self.late += 1
            return
        if self._next is None:
            self._next = index
        self.messages += 1
        self._newest = max(self._newest, t)
        bucket = self._open.get(index)
        if bucket is None:
            bucket = self._open[index] = _Bucket()
        if message.is_paid or message.kind == "member":
            bucket.paid += 1
        if self.config.skip_greetings and message.kind == "text" and is_routine(message.text):
            return
        bucket.rate += 1
        if message.author:
            bucket.authors.add(message.author)
        found = classify_reactions(message.text, message.emotes)
        if found:
            bucket.reactions += 1
            for name in found:
                bucket.categories[name] += 1

    # ------------------------------------------------------------------ judging
    def seen(self) -> float:
        """Seconds of chat judged so far (capped at ``history``)."""
        return len(self._history["rate"]) * self.config.window

    def advance(self, now: float) -> list[Trigger]:
        """Judge every window that is complete at ``now``; returns the new triggers."""
        cfg = self.config
        if self._next is None:
            return []
        w = cfg.window
        # complete: a later window already has a message, or no message can still arrive
        limit = max(int(self._newest // w), int(math.floor((now - cfg.lag) / w)))
        if limit - self._next > 2 * (self._history["rate"].maxlen or 1):  # a gap longer than the history: start over
            for values in self._history.values():
                values.clear()
            self._open = {i: b for i, b in self._open.items() if i >= limit}
            self._next = limit
        fired: list[Trigger] = []
        while self._next < limit:
            index = self._next
            bucket = self._open.pop(index, None) or _Bucket()
            trigger = self._judge(index, bucket)
            for key, value in bucket.values().items():
                self._history[key].append(value)
            self._next = index + 1
            if trigger is not None:
                fired.append(trigger)
        self.triggers.extend(fired)
        return fired

    def _judge(self, index: int, bucket: _Bucket) -> Trigger | None:
        cfg = self.config
        end = (index + 1) * cfg.window
        values = bucket.values()
        weights = {k: v for k, v in cfg.weights.items() if k in values and v > 0}
        if self.seen() < cfg.warmup or not weights:
            return None
        self._scores.append(sum(float(robust_z(np.array([*self._history[k], values[k]]))[-1]) * v for k, v in weights.items()) / sum(weights.values()))
        score = sum(self._scores) / cfg.smooth  # windows before the warm-up count as calm
        if score < cfg.threshold or values["rate"] < cfg.min_messages:
            return None
        if end - self._last_fired < cfg.cooldown or (self.live_from is not None and end < self.live_from):
            return None
        self._last_fired = end
        return Trigger(end, score, *self._explain(bucket))

    def _explain(self, bucket: _Bucket) -> tuple[list[str], dict[str, float]]:
        w = self.config.window
        per_min = bucket.rate * 60 / w
        base = float(np.median(np.array(self._history["rate"]))) if self._history["rate"] else 0.0
        stats: dict[str, float] = {"chat_per_min": per_min, "messages": float(bucket.rate), "reactions": float(bucket.reactions), "paid": float(bucket.paid)}
        if base > 1e-6:
            stats["chat_ratio"] = bucket.rate / base
            reasons = [f"채팅 급증 {per_min:.0f}/분 (평소의 {bucket.rate / base:.1f}배)"]
        else:
            stats["chat_ratio"] = 99.0
            reasons = [f"채팅 급증 {per_min:.0f}/분 (평소엔 거의 없음)"]
        for name, count in bucket.categories.items():
            stats[f"react_{name}"] = float(count)
        if bucket.reactions:
            detail = " · ".join(f"{_LABELS[c]} {n}" for c, n in sorted(bucket.categories.items(), key=lambda kv: -kv[1]) if n)
            reasons.append(f"반응 {bucket.reactions}개 ({detail})")
        if bucket.paid:
            reasons.append(f"슈퍼챗·후원·멤버십 {bucket.paid}건")
        return reasons, stats


def simulate(messages: Iterable[ChatMessage], config: LiveConfig | None = None) -> list[Trigger]:
    """What live mode would have fired on for a finished chat (``message.time`` is the clock)."""
    detector = SurgeDetector(config)
    last = 0.0
    for message in sorted(messages, key=lambda m: m.time):
        detector.add(message)
        last = message.time
        detector.advance(last)  # only what a later message has completed: nothing is known ahead of time
    detector.advance(last + detector.config.lag + detector.config.window)
    return detector.triggers


def clip_span(trigger_time: float, saved_at: float, config: LiveConfig | None = None) -> tuple[float, float]:
    """Where the moment sits in a replay saved at ``saved_at``: ``(seconds to keep, seconds to drop at the end)``.

    The surge window ended at ``trigger_time``; the moment that caused it was ``chat_delay``
    earlier. The clip runs from ``lead`` before the window to ``tail`` after it.
    """
    cfg = config or LiveConfig()
    start = trigger_time - cfg.window - cfg.chat_delay - cfg.lead
    end = trigger_time - cfg.chat_delay + cfg.tail
    return max(1.0, saved_at - start), max(0.0, saved_at - end)


# --------------------------------------------------------------------------- chat sources


class ChatSource(Protocol):
    ended: bool

    def read(self) -> list[ChatMessage]: ...
    def close(self) -> None: ...


class FileFollower:
    """Messages appended to a file since the last :meth:`read` (one JSON object per line).

    What is already in the file at the first read is the backlog: its messages are passed
    on if they carry a time (they become the history) and dropped if they do not - they
    would all count as "now" and look like a surge.
    """

    def __init__(self, path: str | os.PathLike[str], *, parse: Callable[[str], Sequence[ChatMessage]] = live_messages) -> None:
        self.path = Path(path)
        self.ended = False
        self._parse = parse
        self._position = 0
        self._rest = b""
        self._first = True

    def read(self) -> list[ChatMessage]:
        try:
            size = self.path.stat().st_size
        except OSError:
            return []  # not there yet
        if size < self._position:  # the file was replaced: start again
            self._position, self._rest = 0, b""
        if size == self._position:
            return []
        with self.path.open("rb") as fh:
            fh.seek(self._position)
            data = fh.read()
        self._position += len(data)
        *lines, self._rest = (self._rest + data).split(b"\n")  # the last piece may still be growing
        found: list[ChatMessage] = []
        for raw in lines:
            text = raw.decode("utf-8", errors="replace").strip()
            if text:
                found.extend(self._parse(text))
        if self._first:
            found = [m for m in found if math.isfinite(m.time)]
            self._first = False
        return found

    def close(self) -> None:
        self.ended = True


class YtDlpLiveChat:
    """Run yt-dlp on a live YouTube stream and follow the chat it records into ``folder``."""

    def __init__(self, url: str, folder: str | os.PathLike[str], *, ytdlp: list[str] | None = None, popen: Callable[..., Any] = subprocess.Popen) -> None:
        from .sources import ytdlp_command

        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.ended = False
        for old in self.folder.glob("live.live_chat.json*"):
            old.unlink()
        self.log = self.folder / "yt-dlp.log"
        self.command = [*(ytdlp or ytdlp_command()), "--skip-download", "--write-subs", "--sub-langs", "live_chat", "--no-progress", "-o", str(self.folder / "live.%(ext)s"), url]
        self._log = self.log.open("w", encoding="utf-8", errors="replace")
        self._process = popen(self.command, stdout=self._log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        self._follower = FileFollower(self.folder / "live.live_chat.json.part")
        self._any = False

    def read(self) -> list[ChatMessage]:
        found = self._follower.read()
        self._any = self._any or bool(found)
        if not found and not self.ended and self._process.poll() is not None:
            self.ended = True
            self._log.close()
            if not self._any:  # it never got to the chat: say why
                tail = "\n".join(self.log.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-6:])
                raise RuntimeError(f"yt-dlp stopped without any chat (is the stream live, and does it have a chat?):\n{tail}")
        return found

    def close(self) -> None:
        self.ended = True
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=10)
            except Exception:  # still there: no more patience
                self._process.kill()
        if not self._log.closed:
            self._log.close()


# --------------------------------------------------------------------------- the loop


def watch(
    source: ChatSource,
    detector: SurgeDetector,
    on_trigger: Callable[[Trigger], None],
    *,
    clock: Callable[[], float] = time.time,
    sleep: Callable[[float], None] = time.sleep,
    poll: float = 1.0,
    until: float | None = None,
    max_triggers: int | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> int:
    """Read, judge, act - until the source ends, ``until`` (clock time) passes or enough has fired.

    ``on_trigger`` is called once the surge has had ``tail`` seconds to play out, so the
    replay that is saved then holds the whole moment. Returns the number of triggers.
    """
    cfg = detector.config
    waiting: list[Trigger] = []
    count = 0
    while True:
        now = clock()
        for message in source.read():
            detector.add(message, now)
        waiting.extend(detector.advance(now))
        while waiting and now >= waiting[0].time - cfg.chat_delay + cfg.tail:
            on_trigger(waiting.pop(0))
            count += 1
        if max_triggers is not None and count >= max_triggers:
            break
        if source.ended and not waiting:
            break
        if until is not None and now >= until:
            break
        if should_stop is not None and should_stop():
            break
        sleep(poll)
    return count


# --------------------------------------------------------------------------- what a trigger does


@dataclass
class SavedClip:
    trigger: Trigger
    clip: Path
    replay: Path
    #: Set when the replay buffer was shorter than the clip that was wanted.
    note: str = ""


class ReplayClipper:
    """Turn a trigger into a clip: save OBS's replay buffer and cut the moment out of it.

    ``connect`` returns a connected :class:`stream2clip.obs.ObsClient`; a new one is made for
    every trigger, so an OBS that was restarted during a long stream is not a problem.
    """

    def __init__(
        self,
        out_dir: str | os.PathLike[str],
        connect: Callable[[], Any],
        *,
        options: Any = None,
        config: LiveConfig | None = None,
        clock: Callable[[], float] = time.time,
        name: str = "live_%Y%m%d_%H%M%S",
    ) -> None:
        from .ffmpeg import ExportOptions

        self.out_dir = Path(out_dir)
        self.connect = connect
        self.options = options or ExportOptions(format="mp4")
        self.config = config or LiveConfig()
        self.clock = clock
        self.name = name
        self.saved: list[SavedClip] = []

    def check(self, *, start_buffer: bool = False) -> str:
        """Make sure OBS answers and its replay buffer runs; returns OBS's version. Raises ``ObsError`` with what to do."""
        from .obs import ObsError

        client = self.connect()
        try:
            if not client.replay_buffer_active():
                if not start_buffer:
                    raise ObsError("The replay buffer is not running. Start it in OBS (Controls > Start Replay Buffer) or pass --start-buffer.")
                if not client.start_replay_buffer():
                    raise ObsError('OBS accepted the request, but the replay buffer did not start. Look at the OBS window: it may be asking a question ("No sources").')
            return str(getattr(client, "obs_version", ""))
        finally:
            client.close()

    def __call__(self, trigger: Trigger) -> SavedClip:
        from .export import probe
        from .ffmpeg import extension_for
        from .obs import replay_to_clip

        self.out_dir.mkdir(parents=True, exist_ok=True)
        stem = time.strftime(self.name, time.localtime(trigger.time))
        output = self.out_dir / f"{stem}{extension_for(self.options.format)}"
        client = self.connect()
        try:
            keep, drop = clip_span(trigger.time, self.clock(), self.config)
            clip, replay = replay_to_clip(output, self.options, last=keep, trim_end=drop, client=client)
        finally:
            client.close()
        length = probe(replay).duration or 0.0
        note = ""
        if length + 1.0 < keep:
            note = f"the replay buffer holds {length:.0f} s but the clip wanted {keep:.0f} s: raise Settings > Output > Replay Buffer > Maximum Replay Time in OBS"
        saved = SavedClip(trigger, clip, replay, note)
        self.saved.append(saved)
        return saved
