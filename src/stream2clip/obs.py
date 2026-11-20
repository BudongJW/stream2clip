"""OBS Studio replay buffer -> clip, over obs-websocket 5.x (built into OBS 28+).

OBS keeps the last N seconds in memory when its replay buffer is running. One call
saves that buffer to a file and turns it into a GIF / WebP / MP4 with the same export
code as everything else::

    stream2clip replay -o moment.gif --last 15

Protocol (https://github.com/obsproject/obs-websocket, docs/generated/protocol.md):
JSON messages ``{"op": n, "d": {...}}`` - Hello (0), Identify (1), Identified (2),
Event (5), Request (6), RequestResponse (7). Needs the ``websocket-client`` package
(``pip install "stream2clip[obs]"``); tests and other hosts can pass their own
``connect`` callable instead.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Protocol

from .ffmpeg import ExportOptions

__all__ = ["ObsClient", "ObsError", "auth_string", "replay_to_clip"]

OP_HELLO, OP_IDENTIFY, OP_IDENTIFIED, OP_EVENT, OP_REQUEST, OP_RESPONSE = 0, 1, 2, 5, 6, 7
EVENTS_GENERAL = 1 << 0  # EventSubscription::General - ExitStarted ...
EVENTS_SCENES = 1 << 2  # EventSubscription::Scenes - CurrentProgramSceneChanged
EVENTS_OUTPUTS = 1 << 6  # EventSubscription::Outputs - where ReplayBufferSaved is sent
RPC_VERSION = 1


class ObsError(RuntimeError):
    """Anything OBS refused or could not do; ``code`` is obs-websocket's request status when there is one."""

    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


NOT_AVAILABLE = 604  # RequestStatus::InvalidResourceState, e.g. the replay buffer is switched off in the settings


class Connection(Protocol):
    def send(self, text: str) -> Any: ...
    def recv(self) -> str: ...
    def close(self) -> Any: ...


def auth_string(password: str, salt: str, challenge: str) -> str:
    """``base64(sha256(base64(sha256(password + salt)) + challenge))`` as the protocol defines it."""
    secret = base64.b64encode(hashlib.sha256((password + salt).encode("utf-8")).digest()).decode("ascii")
    return base64.b64encode(hashlib.sha256((secret + challenge).encode("utf-8")).digest()).decode("ascii")


def _default_connect(url: str, timeout: float) -> Connection:
    try:
        import websocket  # type: ignore[import-not-found]  # the "websocket-client" package
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ObsError('OBS control needs websocket-client: pip install "stream2clip[obs]"') from exc
    try:
        return websocket.create_connection(url, timeout=timeout)
    except OSError as exc:
        raise ObsError(f"Cannot reach OBS at {url}. Is OBS running with Tools > WebSocket Server Settings > Enable WebSocket server?") from exc


class ObsClient:
    """A small synchronous obs-websocket client: identify, send requests, collect events."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 4455,
        password: str | None = None,
        *,
        timeout: float = 10.0,
        connect: Callable[[str, float], Connection] | None = None,
        events: int = EVENTS_OUTPUTS,
    ) -> None:
        self.url = f"ws://{host}:{port}"
        self.timeout = timeout
        self.events: list[dict[str, Any]] = []
        self._counter = 0
        self._ws = (connect or _default_connect)(self.url, timeout)
        try:
            hello = self._read()
            if hello.get("op") != OP_HELLO:
                raise ObsError(f"Unexpected first message from {self.url} (not an obs-websocket 5 server?)")
            identify: dict[str, Any] = {"rpcVersion": RPC_VERSION, "eventSubscriptions": events}
            auth = hello["d"].get("authentication")
            if auth:
                if not password:
                    raise ObsError("OBS asks for a WebSocket password (OBS_WEBSOCKET_PASSWORD or --password)")
                identify["authentication"] = auth_string(password, auth["salt"], auth["challenge"])
            self._send(OP_IDENTIFY, identify)
            reply = self._read()
            if reply.get("op") != OP_IDENTIFIED:
                raise ObsError("OBS did not accept the connection (wrong password?)")
            self.obs_version = hello["d"].get("obsStudioVersion", "")
        except Exception:
            self.close()
            raise

    # ------------------------------------------------------------------ plumbing
    def _send(self, op: int, data: dict[str, Any]) -> None:
        self._ws.send(json.dumps({"op": op, "d": data}))

    def _read(self) -> dict[str, Any]:
        try:
            raw = self._ws.recv()
        except Exception as exc:  # closed socket, timeout ...
            raise ObsError(f"Lost the connection to OBS: {exc}") from exc
        if not raw:
            raise ObsError("OBS closed the connection (wrong password?)")
        return json.loads(raw)

    def close(self) -> None:
        try:
            self._ws.close()
        except Exception:
            pass

    def __enter__(self) -> "ObsClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def request(self, request_type: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send one request and return its ``responseData`` (events that arrive meanwhile are kept in ``events``)."""
        self._counter += 1
        request_id = f"s2c-{self._counter}"
        payload: dict[str, Any] = {"requestType": request_type, "requestId": request_id}
        if data:
            payload["requestData"] = data
        self._send(OP_REQUEST, payload)
        while True:
            message = self._read()
            body = message.get("d", {})
            if message.get("op") == OP_EVENT:
                self.events.append(body)
            elif message.get("op") == OP_RESPONSE and body.get("requestId") == request_id:
                status = body.get("requestStatus", {})
                if not status.get("result"):
                    raise ObsError(f"{request_type} failed ({status.get('code')}): {status.get('comment') or 'no details'}", status.get("code"))
                return body.get("responseData") or {}

    def poll(self, wait: float = 0.0) -> list[dict[str, Any]]:
        """The events that have arrived (``{"eventType": ..., "eventData": ...}``), waiting at most ``wait`` seconds for the first."""
        found, self.events = self.events, []
        patience = 0.001 if found else wait
        try:
            while True:
                try:
                    self._ws.settimeout(max(patience, 0.001))  # type: ignore[attr-defined]
                except AttributeError:
                    pass
                try:
                    raw = self._ws.recv()
                except Exception as exc:
                    if isinstance(exc, (TimeoutError, BlockingIOError)) or "Timeout" in type(exc).__name__:
                        return found  # nothing more for now
                    raise ObsError(f"Lost the connection to OBS: {exc}") from exc
                if not raw:
                    raise ObsError("OBS closed the connection")
                message = json.loads(raw)
                if message.get("op") == OP_EVENT:
                    found.append(message.get("d", {}))
                patience = 0.001  # after the first, only what is already there
        finally:
            try:
                self._ws.settimeout(self.timeout)  # type: ignore[attr-defined]
            except AttributeError:
                pass

    def wait_event(self, event_type: str, timeout: float) -> dict[str, Any] | None:
        """The data of the next ``event_type`` event, or ``None`` after ``timeout`` seconds."""
        deadline = time.monotonic() + timeout
        while True:
            for index, event in enumerate(self.events):
                if event.get("eventType") == event_type:
                    return self.events.pop(index).get("eventData") or {}
            if time.monotonic() >= deadline:
                return None
            try:
                message = self._read()
            except ObsError:
                return None
            if message.get("op") == OP_EVENT:
                self.events.append(message.get("d", {}))

    # ------------------------------------------------------------------ replay buffer
    def replay_buffer_active(self) -> bool:
        try:
            return bool(self.request("GetReplayBufferStatus").get("outputActive"))
        except ObsError as exc:
            if exc.code == NOT_AVAILABLE:  # what a freshly installed OBS answers
                raise ObsError(
                    "OBS has no replay buffer yet: switch it on in Settings > Output > Replay Buffer (Enable Replay Buffer), "
                    "then start it (Controls > Start Replay Buffer).", exc.code,
                ) from exc
            raise

    def start_replay_buffer(self, *, wait: float = 5.0) -> bool:
        """Ask OBS to start the replay buffer; ``True`` once it is really running.

        OBS answers "ok" as soon as it has passed the request to its window, which may then
        still ask the user something (an empty scene brings up a "No sources" question) or
        fail to start the output. So the status is checked for up to ``wait`` seconds.
        """
        self.request("StartReplayBuffer")
        deadline = time.monotonic() + wait
        while True:
            if self.replay_buffer_active():
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(min(0.2, max(0.01, wait / 5)))

    def save_replay(self, *, wait: float = 15.0) -> Path:
        """Save the replay buffer and return the path of the file OBS wrote."""
        if not self.replay_buffer_active():
            raise ObsError("The replay buffer is not running. Start it in OBS (Controls > Start Replay Buffer) or pass start_buffer / --start-buffer.")
        self.events = [e for e in self.events if e.get("eventType") != "ReplayBufferSaved"]
        self.request("SaveReplayBuffer")
        saved = self.wait_event("ReplayBufferSaved", wait)
        path = (saved or {}).get("savedReplayPath") or self.request("GetLastReplayBufferReplay").get("savedReplayPath")
        if not path:
            raise ObsError("OBS did not report a saved replay file")
        return Path(path)


def replay_to_clip(
    output: str | os.PathLike[str],
    options: ExportOptions | None = None,
    *,
    last: float | None = None,
    trim_end: float = 0.0,
    client: ObsClient | None = None,
    host: str = "127.0.0.1",
    port: int = 4455,
    password: str | None = None,
    start_buffer: bool = False,
    settle: float = 0.5,
    start_wait: float = 5.0,
) -> tuple[Path, Path]:
    """Save OBS's replay buffer and convert it; returns ``(clip, replay file)``.

    ``last`` keeps only the final seconds of the replay and ``trim_end`` drops the very last
    ones (live mode saves a little after the moment). With ``start_buffer`` a buffer that
    is not running is started first - it then has nothing to save yet, which is reported.
    """
    from dataclasses import replace

    from .export import export, probe

    owned = client is None
    client = client or ObsClient(host, port, password)
    try:
        if start_buffer and not client.replay_buffer_active():
            if not client.start_replay_buffer(wait=start_wait):
                raise ObsError(
                    "OBS accepted the request, but the replay buffer did not start. Look at the OBS window: it may be asking "
                    "a question (an empty scene brings up \"No sources\"), or the output failed to start."
                )
            raise ObsError("The replay buffer was not running; it is started now. Run the command again when the moment has happened.")
        replay = client.save_replay()
    finally:
        if owned:
            client.close()
    deadline = time.monotonic() + 10.0
    while not replay.exists() and time.monotonic() < deadline:  # OBS finishes writing a moment after the event
        time.sleep(0.1)
    if not replay.exists():
        raise ObsError(f"OBS reported {replay}, but the file is not there (OBS on another machine?)")
    time.sleep(settle)
    options = options or ExportOptions()
    if last is not None or trim_end > 0:
        duration = probe(replay).duration or 0.0
        start = max(0.0, duration - last) if last is not None else 0.0
        end = duration - trim_end if trim_end > 0 and duration - trim_end > start + 1.0 else None  # never trim the clip away
        options = replace(options, start=start, end=end)
    return export(replay, output, options), replay
