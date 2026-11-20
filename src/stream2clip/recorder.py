"""The session recorder: runs on the streamer's PC while the stream is on air.

It records no video - OBS does that. It writes what is only there while the stream runs
into a session file (:mod:`stream2clip.session`) for clipping afterwards:

* the chat as it arrives (Twitch, CHZZK, SOOP, a YouTube stream through yt-dlp, a file),
  and the moments the chat surged
* the streamer's markers: a hotkey, a button, a chat command, a VTube Studio hotkey
* OBS: the program scene, when streaming / recording / the replay buffer started and
  stopped, the replays saved, the canvas size and where the VTube Studio source sits
* VTube Studio: the model's outline (where the avatar is) and its parameters (mouth, eyes,
  head angles), a few times a second

Each part connects on its own and connects again when it drops; one that cannot be
reached does not stop the others. Everything runs in one polling loop (no threads), so
:meth:`SessionRecorder.mark` and :meth:`SessionRecorder.stop` may be called from another
thread (a hotkey, a window) and are picked up at the next turn of the loop.
"""

from __future__ import annotations

import math
import os
import queue
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from .chat import ChatMessage
from .highlights import marker_word
from .live import ChatSource, LiveConfig, SurgeDetector
from .obs import ObsError
from .session import SessionWriter

__all__ = ["Part", "ChatPart", "ObsPart", "VtsPart", "SessionRecorder", "DEFAULT_PARAMETERS", "chat_part", "build_recorder"]

#: The standard Live2D parameters recorded by default (others only with ``parameters=None``).
DEFAULT_PARAMETERS = (
    "ParamAngleX", "ParamAngleY", "ParamAngleZ", "ParamBodyAngleX", "ParamEyeLOpen", "ParamEyeROpen",
    "ParamEyeBallX", "ParamEyeBallY", "ParamBrowLY", "ParamBrowRY", "ParamMouthOpenY", "ParamMouthForm", "ParamCheek",
)


@dataclass
class PartState:
    state: str = "off"  # off | connecting | connected | waiting
    detail: str = ""


class Part:
    """One thing the recorder reads. Subclasses connect in :meth:`_open` and read in :meth:`_read`."""

    name = "part"
    #: Seconds to wait before trying again after a failure.
    retry = 10.0

    def __init__(self, writer: SessionWriter) -> None:
        self.writer = writer
        self.status = PartState()
        self._next_try = 0.0
        self._open_ok = False

    def _set(self, state: str, detail: str = "") -> None:
        if (state, detail) != (self.status.state, self.status.detail):
            self.status = PartState(state, detail)
            self.writer.write("status", source=self.name, state=state, **({"detail": detail} if detail else {}))

    def _open(self, now: float) -> None:  # pragma: no cover - the subclasses' part
        raise NotImplementedError

    def _read(self, now: float) -> None:  # pragma: no cover
        raise NotImplementedError

    def _drop(self) -> None:
        """Close what is open (called before connecting again and on :meth:`close`)."""

    def poll(self, now: float) -> None:
        if not self._open_ok:
            if now < self._next_try:
                return
            self._set("connecting")
            try:
                self._open(now)
            except Exception as exc:
                self._drop()
                self._next_try = now + self.retry
                self._set("waiting", str(exc))
                return
            self._open_ok = True
            self._set("connected")
        try:
            self._read(now)
        except Exception as exc:
            self._drop()
            self._open_ok = False
            self._next_try = now + self.retry
            self._set("waiting", str(exc))

    def close(self) -> None:
        self._drop()
        self._open_ok = False
        self._set("off")


class ChatPart(Part):
    """The live chat, and the surges a :class:`~stream2clip.live.SurgeDetector` sees in it."""

    name = "chat"
    retry = 30.0  # a channel that is not live yet: ask again in a while

    def __init__(
        self,
        writer: SessionWriter,
        open_source: Callable[[], ChatSource],
        *,
        config: LiveConfig | None = None,
        viewer_votes: int = 0,
        vote_window: float = 30.0,
        vote_cooldown: float = 60.0,
    ) -> None:
        super().__init__(writer)
        self._open_source = open_source
        self._source: ChatSource | None = None
        self.config = config or LiveConfig()
        self.detector = SurgeDetector(self.config, live_from=writer.started)
        self.messages = 0
        self.surges = 0
        #: This many different viewers typing a marker word (``!clip`` ...) within ``vote_window`` seconds leave a marker; 0: off.
        self.viewer_votes = viewer_votes
        self.vote_window = vote_window
        self.vote_cooldown = vote_cooldown
        self._votes: list[tuple[float, str]] = []
        self._last_vote = -1e18
        self.votes = 0

    @property
    def voters(self) -> int:
        """Different viewers who voted in the current window."""
        return len({a for _t, a in self._votes})

    def _vote(self, message: ChatMessage, now: float) -> None:
        """A viewer's marker word counts as a vote; enough different viewers at once make a marker."""
        if message.role in ("owner", "moderator") or marker_word(message, self.config.markers, ("any",)) is None:
            return
        when = message.time if math.isfinite(message.time) else now
        self._votes = [(t, a) for t, a in self._votes if when - t <= self.vote_window] + [(when, message.author or f"anonymous-{len(self._votes)}")]
        voters = {a for _t, a in self._votes}
        if len(voters) >= self.viewer_votes and when - self._last_vote >= self.vote_cooldown:
            first = min(t for t, _a in self._votes)  # viewers type after the moment, like any chat: the first vote is closest to it
            self._last_vote = when
            self._votes = []
            self.votes += 1
            self.writer.write("marker", first, by="viewers", label=f"{len(voters)} viewers")

    def _open(self, now: float) -> None:
        self._source = self._open_source()

    def _drop(self) -> None:
        if self._source is not None:
            try:
                self._source.close()
            except Exception:
                pass
        self._source = None

    def _read(self, now: float) -> None:
        assert self._source is not None
        for message in self._source.read():
            self.writer.chat(message)
            self.messages += 1
            self.detector.add(message, now)
            if self.viewer_votes > 0:
                self._vote(message, now)
        for trigger in self.detector.advance(now):
            if trigger.stats.get("marker"):
                continue  # the marker is in the chat already
            self.surges += 1
            self.writer.write("surge", trigger.time, score=trigger.score, reasons=list(trigger.reasons))
        if self._source.ended:
            raise RuntimeError("the chat ended")


class ObsPart(Part):
    """OBS over obs-websocket: scenes, outputs, saved replays, the canvas and the VTube Studio source."""

    name = "obs"
    #: Seconds between two looks at where the VTube Studio source is when OBS says nothing (it does say when a source is moved, shown or hidden).
    placement_every = 15.0
    #: Seconds after such a word from OBS before looking: a source being dragged sends many.
    placement_settle = 0.3

    #: The obs-websocket vendor name of the Source Record plugin (a filter that records one source to a file of its own).
    record_vendor = "source-record"

    def __init__(self, writer: SessionWriter, connect: Callable[[], Any], *, avatar_source: str | None = None, record_avatar: bool = False) -> None:
        super().__init__(writer)
        self._connect = connect
        self.avatar_source = avatar_source
        #: Start the Source Record filter on the VTube Studio source with the session and stop it at the end.
        self.record_avatar = record_avatar and bool(avatar_source)
        self._avatar_recording = False
        self.client: Any = None
        self.scene = ""
        self._outputs: dict[str, bool] = {}
        self._placement: Any = None
        self._next_placement = 0.0
        self.replays = 0
        self._replay_wanted = False

    def _open(self, now: float) -> None:
        self.client = self._connect()
        video = self.client.request("GetVideoSettings")
        self.writer.write("obs_video", base=[video.get("baseWidth", 0), video.get("baseHeight", 0)], output=[video.get("outputWidth", 0), video.get("outputHeight", 0)])
        scene = self.client.request("GetCurrentProgramScene")
        self._scene(str(scene.get("currentProgramSceneName") or scene.get("sceneName") or ""))
        for output, request in (("stream", "GetStreamStatus"), ("record", "GetRecordStatus"), ("replay_buffer", "GetReplayBufferStatus")):
            try:
                status = self.client.request(request)
            except Exception:
                continue  # e.g. no replay buffer configured
            active = bool(status.get("outputActive"))
            running = status.get("outputDuration")  # milliseconds; the stream and the recording say how long they have been on
            # Already on when the recorder connected: second 0 of the video is when it began, not now.
            began = now - float(running) / 1000.0 if active and isinstance(running, (int, float)) and running > 0 else None
            self._output(output, active, began)
        self._next_placement = 0.0
        if self.record_avatar and not self._avatar_recording:  # after a lost connection the plugin is still recording: not started twice
            self._avatar_record(True)

    def _avatar_record(self, start: bool) -> None:
        """Start or stop the avatar's own recording and write when: clips line the two recordings up by that time.

        The recording is the Source Record plugin's (not part of this program); it is only asked
        over obs-websocket's vendor requests. Without the plugin or its filter the session goes on.
        """
        what = "started" if start else "stopped"
        try:
            answer = self.client.request("CallVendorRequest", {"vendorName": self.record_vendor, "requestType": "record_start" if start else "record_stop", "requestData": {"source": self.avatar_source}})
        except ObsError as exc:
            if exc.code is None:  # the connection, not the request
                raise
            self.writer.write("status", source="obs", state="connected", detail=f"avatar recording not {what}: {exc} (is the Source Record plugin installed?)")
            return
        if (answer.get("responseData") or {}).get("success") is False:
            self.writer.write("status", source="obs", state="connected", detail=f"avatar recording not {what}: no Source Record filter on the source {self.avatar_source!r}")
            return
        self._avatar_recording = start
        self.writer.write("avatar_record", active=start, source=self.avatar_source, by=self.record_vendor)

    def close(self) -> None:
        if self._avatar_recording and self.client is not None:
            try:
                self._avatar_record(False)
            except Exception:
                pass
        super().close()

    def _drop(self) -> None:
        if self.client is not None:
            try:
                self.client.close()
            except Exception:
                pass
        self.client = None

    def _scene(self, name: str) -> None:
        if name and name != self.scene:
            self.scene = name
            self.writer.write("scene", name=name)
            self._next_placement = 0.0  # the VTube Studio source may be somewhere else (or nowhere) in this scene

    def _output(self, output: str, active: bool, when: float | None = None) -> None:
        if self._outputs.get(output) != active:
            self._outputs[output] = active
            self.writer.write("output", when, output=output, active=active)

    def _place(self) -> None:
        """Write where the VTube Studio source is in the program scene when that changed (an empty transform: not shown)."""
        transform: dict[str, Any] = {}
        try:
            item = self.client.request("GetSceneItemId", {"sceneName": self.scene, "sourceName": self.avatar_source})
            item_id = item.get("sceneItemId")
            if self.client.request("GetSceneItemEnabled", {"sceneName": self.scene, "sceneItemId": item_id}).get("sceneItemEnabled"):
                transform = self.client.request("GetSceneItemTransform", {"sceneName": self.scene, "sceneItemId": item_id}).get("sceneItemTransform") or {}
        except ObsError as exc:
            if exc.code is None:  # the connection, not the request
                raise
            transform = {}  # not in this scene (obs-websocket: resource not found)
        key = (self.scene, tuple(sorted((k, v) for k, v in transform.items() if isinstance(v, (int, float, str)))))
        if key != self._placement:
            self._placement = key
            self.writer.write("avatar_source", source=self.avatar_source, scene=self.scene, transform=transform)

    def _read(self, now: float) -> None:
        if self._replay_wanted:
            self._replay_wanted = False
            try:
                self.save_replay()
            except ObsError as exc:
                if exc.code is None:  # the connection, not the request
                    raise
                self.writer.write("status", source="obs", state="connected", detail=f"replay not saved: {exc}")
        for event in self.client.poll(0.0):
            kind, data = event.get("eventType"), event.get("eventData") or {}
            if kind == "CurrentProgramSceneChanged":
                self._scene(str(data.get("sceneName") or ""))
            elif kind in ("StreamStateChanged", "RecordStateChanged", "ReplayBufferStateChanged"):
                state = str(data.get("outputState") or "")
                output = {"StreamStateChanged": "stream", "RecordStateChanged": "record", "ReplayBufferStateChanged": "replay_buffer"}[kind]
                if state.endswith("_STARTED"):
                    self._output(output, True)
                elif state.endswith("_STOPPED"):
                    self._output(output, False)
            elif kind in ("SceneItemTransformChanged", "SceneItemEnableStateChanged", "SceneItemCreated", "SceneItemRemoved"):
                if data.get("sceneName") in (None, self.scene):  # moved, shown or hidden in the scene on air: look again in a moment
                    self._next_placement = min(self._next_placement, now + self.placement_settle)
            elif kind == "ReplayBufferSaved":
                self.replays += 1
                self.writer.write("replay_saved", path=str(data.get("savedReplayPath") or ""))
            elif kind == "ExitStarted":
                raise RuntimeError("OBS is closing")
        if self.avatar_source and now >= self._next_placement:
            self._next_placement = now + self.placement_every
            self._place()

    def ask_replay(self) -> None:
        """Have the replay buffer saved at this part's next turn (from any thread: the connection is used by one thread only)."""
        self._replay_wanted = True

    def save_replay(self) -> None:
        """Ask OBS to save its replay buffer (the saved file arrives as a ``replay_saved`` event)."""
        if self.client is None:
            raise RuntimeError("OBS is not connected")
        self.client.request("SaveReplayBuffer")


class VtsPart(Part):
    """VTube Studio: the model's outline and parameters; a VTube Studio hotkey can be a marker."""

    name = "vts"

    def __init__(
        self,
        writer: SessionWriter,
        connect: Callable[[], Any],
        *,
        outline_every: float = 0.5,
        parameters_every: float = 0.2,
        parameters: Sequence[str] | None = DEFAULT_PARAMETERS,
        marker_hotkeys: Sequence[str] = (),
        on_marker: Callable[[str, str], None] | None = None,
    ) -> None:
        super().__init__(writer)
        self._connect = connect
        self.client: Any = None
        self.outline_every = outline_every
        self.parameters_every = parameters_every
        self.parameters = None if parameters is None else frozenset(parameters)
        self.marker_hotkeys = {h.strip().lower() for h in marker_hotkeys if h.strip()}
        self._on_marker = on_marker
        self._model = ("", "")
        self._last_outline = -1e18
        self._last_parameters = -1e18
        self.outlines = 0

    def _open(self, now: float) -> None:
        self.client = self._connect()
        self.client.subscribe("ModelOutlineEvent", {"draw": False})
        self.client.subscribe("ModelLoadedEvent")
        if self.marker_hotkeys:
            self.client.subscribe("HotkeyTriggeredEvent")

    def _drop(self) -> None:
        if self.client is not None:
            try:
                self.client.close()
            except Exception:
                pass
        self.client = None

    def _model_is(self, name: str, model_id: str) -> None:
        if name and (name, model_id) != self._model:
            self._model = (name, model_id)
            self.writer.write("avatar_model", name=name, id=model_id)

    def _read(self, now: float) -> None:
        for event in self.client.poll(0.0):
            kind, data = event.get("messageType"), event.get("data") or {}
            if kind == "ModelOutlineEvent":
                self._model_is(str(data.get("modelName") or ""), str(data.get("modelID") or ""))
                if now - self._last_outline >= self.outline_every:
                    hull = [[float(p.get("x", 0.0)), float(p.get("y", 0.0))] for p in data.get("convexHull") or [] if isinstance(p, dict)]
                    if len(hull) >= 3:
                        window = data.get("windowSize") or {}
                        self._last_outline = now
                        self.outlines += 1
                        self.writer.write("avatar_outline", hull=hull, window=[window.get("x", 0), window.get("y", 0)])
            elif kind == "ModelLoadedEvent" and data.get("modelLoaded"):
                self._model_is(str(data.get("modelName") or ""), str(data.get("modelID") or ""))
            elif kind == "HotkeyTriggeredEvent":
                name = str(data.get("hotkeyName") or "")
                if name.strip().lower() in self.marker_hotkeys and self._on_marker is not None:
                    self._on_marker("vts_hotkey", name)
        if self.parameters_every > 0 and now - self._last_parameters >= self.parameters_every:
            self._last_parameters = now
            model, values = self.client.parameters()
            self._model_is(model.get("name", ""), model.get("id", ""))
            if self.parameters is not None:
                values = {k: v for k, v in values.items() if k in self.parameters}
            if values:
                self.writer.write("avatar_params", values=values)


class SessionRecorder:
    """Poll the parts until :meth:`stop`; :meth:`mark` leaves a marker (from any thread)."""

    def __init__(
        self,
        writer: SessionWriter,
        parts: Sequence[Part],
        *,
        save_replay_on_marker: bool = False,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.writer = writer
        self.parts = list(parts)
        self.save_replay_on_marker = save_replay_on_marker
        self._clock = clock
        self._sleep = sleep
        self._marks: "queue.Queue[tuple[float, str, str]]" = queue.Queue()
        self._stop = threading.Event()
        self.markers = 0
        self.last_marker = 0.0
        #: The OBS widget, when one was started (closed with the recorder).
        self.widget: Any = None

    def part(self, name: str) -> Part | None:
        return next((p for p in self.parts if p.name == name), None)

    def state(self) -> dict[str, Any]:
        """What the OBS widget shows: votes so far and needed (0: votes off), markers left, when the last one was."""
        chat = self.part("chat")
        needed = chat.viewer_votes if isinstance(chat, ChatPart) else 0
        return {"votes": chat.voters if isinstance(chat, ChatPart) and needed else 0, "needed": needed,
                "markers": self.writer.counts.get("marker", 0), "last_marker": self.last_marker}

    def mark(self, by: str = "hotkey", label: str = "") -> None:
        """Leave a marker now (written at the next turn of the loop, with the time of the call)."""
        self._marks.put((self._clock(), by, label))

    def stop(self) -> None:
        self._stop.set()

    @property
    def stopped(self) -> bool:
        return self._stop.is_set()

    def _take_marks(self) -> None:
        while True:
            try:
                when, by, label = self._marks.get_nowait()
            except queue.Empty:
                return
            self.markers += 1
            self.last_marker = when
            self.writer.write("marker", when, by=by, **({"label": label} if label else {}))
            obs = self.part("obs")
            if self.save_replay_on_marker and isinstance(obs, ObsPart) and obs.client is not None:
                obs.ask_replay()

    def step(self) -> None:
        """One turn of the loop: markers first (their time is when they were asked for), then every part."""
        self._take_marks()
        now = self._clock()
        for part in self.parts:
            part.poll(now)

    def _drive(self, part: Part, poll: float) -> None:
        while not self._stop.is_set():
            part.poll(self._clock())
            self._stop.wait(poll)

    def run(self, *, poll: float = 0.1, until: float | None = None, on_step: Callable[["SessionRecorder"], None] | None = None, threads: bool = True) -> None:
        """Record until :meth:`stop` (or the clock passes ``until``), then close the parts and the file.

        Every part reads on a thread of its own: an event gets the time it is read at, and a part
        that waits for its connection (seconds, when nothing listens) must not hold up the others.
        ``threads=False`` reads them in turn on this thread, as :meth:`step` does.
        """
        workers: list[threading.Thread] = []
        try:
            if threads and not self._stop.is_set():
                workers = [threading.Thread(target=self._drive, args=(part, poll), name=f"stream2clip-{part.name}", daemon=True) for part in self.parts]
                for worker in workers:
                    worker.start()
            while not self._stop.is_set():
                if workers:
                    self._take_marks()
                else:
                    self.step()
                if on_step is not None:
                    on_step(self)
                if until is not None and self._clock() >= until:
                    break
                self._sleep(poll)
        finally:  # also on Ctrl+C: the markers asked for so far are kept, the file is closed properly
            self._stop.set()
            for worker in workers:
                worker.join(timeout=5.0)
            try:
                self._take_marks()
                now = self._clock()
                for part, worker in zip(self.parts, workers):
                    if part._open_ok and not worker.is_alive():
                        part.poll(now)  # what was asked for or arrived in the last moment: a marker's replay, the last chat lines
            except Exception:
                pass
            for part in self.parts:
                try:
                    part.close()
                except Exception:
                    pass
            if self.widget is not None:
                self.widget.close()
                self.widget = None
            self.writer.close()

    def serve_widget(self, port: int = 8790) -> str:
        """Start the OBS browser source (see :mod:`stream2clip.widget`) and return its address."""
        from .widget import WidgetServer

        self.widget = WidgetServer(self.state, port=port)
        return self.widget.url


def chat_part(writer: SessionWriter, source: str, folder: str, *, config: LiveConfig | None = None, ytdlp: list[str] | None = None, viewer_votes: int = 0) -> ChatPart:
    """A :class:`ChatPart` for a channel address, ``chzzk-api`` or a file, as ``stream2clip live`` reads it."""
    from .live import open_chat

    return ChatPart(writer, lambda: open_chat(source, folder, ytdlp=ytdlp)[0], config=config, viewer_votes=viewer_votes)


def build_recorder(
    path: str | os.PathLike[str],
    *,
    chat: str | None = None,
    live_config: LiveConfig | None = None,
    ytdlp: list[str] | None = None,
    obs: tuple[str, int, str | None] | None = None,
    avatar_source: str | None = None,
    vts_url: str | None = None,
    outline_every: float = 0.5,
    parameters: str = "default",
    parameters_every: float = 0.2,
    vts_hotkeys: Sequence[str] = (),
    replay_on_marker: bool = False,
    viewer_votes: int = 0,
    record_avatar: bool = False,
    connect_obs: Callable[[], Any] | None = None,
    connect_vts: Callable[[], Any] | None = None,
) -> SessionRecorder:
    """The recorder for these choices, writing to ``path`` (``recorder.writer``).

    ``chat``: a channel address or a chat file; ``obs``: ``(host, port, password)``;
    ``vts_url``: VTube Studio's API address (``None``: no VTube Studio); ``parameters``:
    "default" (the standard face and head ones), "all" or "none". ``viewer_votes``: so many
    different viewers typing ``!clip`` within 30 seconds leave a marker (0: off).
    ``record_avatar``: start and stop the Source Record filter on ``avatar_source`` with the session.
    """
    if record_avatar and (obs is None or not avatar_source):
        raise ValueError("Recording the avatar apart needs OBS and the name of the source that shows VTube Studio")
    out = Path(path)
    sources: dict[str, str] = {}
    if chat:
        sources["chat"] = chat
    if obs is not None:
        sources["obs"] = f"ws://{obs[0]}:{obs[1]}" + (f"  (VTube Studio source: {avatar_source})" if avatar_source else "")
    if vts_url:
        sources["vts"] = vts_url
    if not sources:
        raise ValueError("Nothing to record: choose the chat, OBS or VTube Studio")
    writer = SessionWriter(out, sources=sources)
    recorder = SessionRecorder(writer, [], save_replay_on_marker=replay_on_marker)
    parts: list[Part] = []
    if chat:
        parts.append(chat_part(writer, chat, os.fspath(out.with_name(out.stem + "-chat")), config=live_config, ytdlp=ytdlp, viewer_votes=viewer_votes))
    if obs is not None:
        if connect_obs is None:
            from .obs import EVENTS_GENERAL, EVENTS_ITEM_TRANSFORMS, EVENTS_OUTPUTS, EVENTS_SCENE_ITEMS, EVENTS_SCENES, ObsClient

            host, port, password = obs
            events = EVENTS_GENERAL | EVENTS_SCENES | EVENTS_OUTPUTS | ((EVENTS_SCENE_ITEMS | EVENTS_ITEM_TRANSFORMS) if avatar_source else 0)
            connect_obs = lambda: ObsClient(host, port, password, timeout=5.0, events=events)  # noqa: E731
        parts.append(ObsPart(writer, connect_obs, avatar_source=avatar_source, record_avatar=record_avatar))
    if vts_url:
        if connect_vts is None:
            from .vts import VtsClient

            connect_vts = lambda: VtsClient(vts_url)  # noqa: E731
        chosen = {"all": None, "none": ()}.get(parameters, DEFAULT_PARAMETERS)
        parts.append(VtsPart(
            writer, connect_vts, outline_every=outline_every, parameters_every=0.0 if parameters == "none" else parameters_every,
            parameters=chosen, marker_hotkeys=vts_hotkeys, on_marker=recorder.mark,
        ))
    recorder.parts = parts
    return recorder
