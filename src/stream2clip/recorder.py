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

import os
import queue
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

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

    def __init__(self, writer: SessionWriter, open_source: Callable[[], ChatSource], *, config: LiveConfig | None = None) -> None:
        super().__init__(writer)
        self._open_source = open_source
        self._source: ChatSource | None = None
        self.detector = SurgeDetector(config or LiveConfig(), live_from=writer.started)
        self.messages = 0
        self.surges = 0

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
    #: Seconds between two looks at where the VTube Studio source is (it can be moved by hand at any time).
    placement_every = 15.0

    def __init__(self, writer: SessionWriter, connect: Callable[[], Any], *, avatar_source: str | None = None) -> None:
        super().__init__(writer)
        self._connect = connect
        self.avatar_source = avatar_source
        self.client: Any = None
        self.scene = ""
        self._outputs: dict[str, bool] = {}
        self._placement: Any = None
        self._next_placement = 0.0
        self.replays = 0

    def _open(self, now: float) -> None:
        self.client = self._connect()
        video = self.client.request("GetVideoSettings")
        self.writer.write("obs_video", base=[video.get("baseWidth", 0), video.get("baseHeight", 0)], output=[video.get("outputWidth", 0), video.get("outputHeight", 0)])
        scene = self.client.request("GetCurrentProgramScene")
        self._scene(str(scene.get("currentProgramSceneName") or scene.get("sceneName") or ""))
        for output, request in (("stream", "GetStreamStatus"), ("record", "GetRecordStatus"), ("replay_buffer", "GetReplayBufferStatus")):
            try:
                active = bool(self.client.request(request).get("outputActive"))
            except Exception:
                continue  # e.g. no replay buffer configured
            self._output(output, active)
        self._next_placement = 0.0

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

    def _output(self, output: str, active: bool) -> None:
        if self._outputs.get(output) != active:
            self._outputs[output] = active
            self.writer.write("output", output=output, active=active)

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
            elif kind == "ReplayBufferSaved":
                self.replays += 1
                self.writer.write("replay_saved", path=str(data.get("savedReplayPath") or ""))
            elif kind == "ExitStarted":
                raise RuntimeError("OBS is closing")
        if self.avatar_source and now >= self._next_placement:
            self._next_placement = now + self.placement_every
            self._place()

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

    def part(self, name: str) -> Part | None:
        return next((p for p in self.parts if p.name == name), None)

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
            self.writer.write("marker", when, by=by, **({"label": label} if label else {}))
            obs = self.part("obs")
            if self.save_replay_on_marker and isinstance(obs, ObsPart) and obs.client is not None:
                try:
                    obs.save_replay()
                except Exception as exc:
                    self.writer.write("status", source="obs", state="connected", detail=f"replay not saved: {exc}")

    def step(self) -> None:
        """One turn of the loop: markers first (their time is when they were asked for), then every part."""
        self._take_marks()
        now = self._clock()
        for part in self.parts:
            part.poll(now)

    def run(self, *, poll: float = 0.1, until: float | None = None, on_step: Callable[["SessionRecorder"], None] | None = None) -> None:
        """Record until :meth:`stop` (or the clock passes ``until``), then close the parts and the file."""
        try:
            while not self._stop.is_set():
                self.step()
                if on_step is not None:
                    on_step(self)
                if until is not None and self._clock() >= until:
                    break
                self._sleep(poll)
        finally:  # also on Ctrl+C: the markers asked for so far are kept, the file is closed properly
            try:
                self._take_marks()
            except Exception:
                pass
            for part in self.parts:
                try:
                    part.close()
                except Exception:
                    pass
            self.writer.close()


def chat_part(writer: SessionWriter, source: str, folder: str, *, config: LiveConfig | None = None, ytdlp: list[str] | None = None) -> ChatPart:
    """A :class:`ChatPart` for a channel address or a file, as ``stream2clip live`` reads it."""
    from .live import open_chat

    return ChatPart(writer, lambda: open_chat(source, folder, ytdlp=ytdlp)[0], config=config)


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
    connect_obs: Callable[[], Any] | None = None,
    connect_vts: Callable[[], Any] | None = None,
) -> SessionRecorder:
    """The recorder for these choices, writing to ``path`` (``recorder.writer``).

    ``chat``: a channel address or a chat file; ``obs``: ``(host, port, password)``;
    ``vts_url``: VTube Studio's API address (``None``: no VTube Studio); ``parameters``:
    "default" (the standard face and head ones), "all" or "none".
    """
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
        parts.append(chat_part(writer, chat, os.fspath(out.with_name(out.stem + "-chat")), config=live_config, ytdlp=ytdlp))
    if obs is not None:
        if connect_obs is None:
            from .obs import EVENTS_GENERAL, EVENTS_OUTPUTS, EVENTS_SCENES, ObsClient

            host, port, password = obs
            connect_obs = lambda: ObsClient(host, port, password, timeout=5.0, events=EVENTS_GENERAL | EVENTS_SCENES | EVENTS_OUTPUTS)  # noqa: E731
        parts.append(ObsPart(writer, connect_obs, avatar_source=avatar_source))
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
