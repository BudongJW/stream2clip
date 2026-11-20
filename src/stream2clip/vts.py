"""VTube Studio's public API (https://github.com/DenchiSoft/VTubeStudio), read only.

What a clipping tool wants from VTube Studio while a stream is on air: where the model is
(``ModelOutlineEvent``, an outline 15 times a second) and how it moves
(``Live2DParameterListRequest``: mouth, eyes, head angles ...). The API is a WebSocket on
``ws://localhost:8001`` (VTube Studio > Settings > Start API). A plugin asks once for a
token: VTube Studio shows a popup and the user allows it; the token is kept and used for
every later connection.

Messages are JSON with ``apiName``, ``apiVersion``, ``requestID``, ``messageType`` and
``data``. The client here is synchronous and polled: :meth:`VtsClient.poll` reads what has
arrived without waiting, like the chat sources of :mod:`stream2clip.live`. Tests and other
hosts pass their own ``connect`` callable.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable

__all__ = ["VtsClient", "VtsError", "token_path", "DEFAULT_URL", "PLUGIN_NAME", "PLUGIN_DEVELOPER"]

DEFAULT_URL = "ws://127.0.0.1:8001"
API_NAME, API_VERSION = "VTubeStudioPublicAPI", "1.0"
PLUGIN_NAME = "stream2clip recorder"
PLUGIN_DEVELOPER = "stream2clip"
TOKEN_DENIED = 50  # ErrorID.TokenRequestDenied: the user clicked "Deny" in the popup


class VtsError(RuntimeError):
    """Anything VTube Studio refused or could not do; ``code`` is its ``errorID`` when there is one."""

    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


def token_path() -> Path:
    """Where the plugin token is kept: ``STREAM2CLIP_VTS_TOKEN``, else the app's config folder (where the app keeps its settings)."""
    override = os.environ.get("STREAM2CLIP_VTS_TOKEN")
    if override:
        return Path(override)
    folder = os.environ.get("STREAM2CLIP_CONFIG_DIR")
    if folder:
        root = Path(folder)
    elif sys.platform == "win32":
        root = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "stream2clip"
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support" / "stream2clip"
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "stream2clip"
    return root / "vtube-studio-token"


def _default_connect(url: str, timeout: float) -> Any:
    try:
        import websocket  # type: ignore[import-not-found]  # the "websocket-client" package, as for OBS
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise VtsError('VTube Studio is reached over a WebSocket: pip install "stream2clip[obs]"') from exc
    try:
        return websocket.create_connection(url, timeout=timeout)
    except OSError as exc:
        raise VtsError(f"Cannot reach VTube Studio at {url}. Is it running with Settings > Start API (allow plugins) switched on?") from exc


def _nothing_yet(error: BaseException) -> bool:
    return isinstance(error, (TimeoutError, BlockingIOError)) or "Timeout" in type(error).__name__


def _icon() -> str | None:
    """The 128 x 128 PNG VTube Studio shows in its popup (the app icon, scaled)."""
    try:
        from importlib.resources import files
        from io import BytesIO

        from PIL import Image

        with files("stream2clip").joinpath("gui/assets/icon_128.png").open("rb") as fh:
            image = Image.open(fh).convert("RGBA")
            if image.size != (128, 128):
                image = image.resize((128, 128))
        out = BytesIO()
        image.save(out, format="PNG")
        return base64.b64encode(out.getvalue()).decode("ascii")
    except Exception:
        return None


class VtsClient:
    """Connect, authenticate, request, subscribe, poll."""

    def __init__(
        self,
        url: str = DEFAULT_URL,
        *,
        token_file: str | os.PathLike[str] | None = None,
        connect: Callable[[str, float], Any] | None = None,
        timeout: float = 5.0,
        approval_wait: float = 120.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.url = url
        self.timeout = timeout
        self.approval_wait = approval_wait
        self.token_file = Path(token_file) if token_file else token_path()
        self._clock = clock
        self._counter = 0
        self._events: list[dict[str, Any]] = []
        self._ws = (connect or _default_connect)(url, timeout)
        try:
            self._authenticate()
        except Exception:
            self.close()
            raise

    # ------------------------------------------------------------------ plumbing
    def _send(self, message_type: str, data: dict[str, Any] | None = None) -> str:
        self._counter += 1
        request_id = f"s2c-{self._counter}"
        body: dict[str, Any] = {"apiName": API_NAME, "apiVersion": API_VERSION, "requestID": request_id, "messageType": message_type}
        if data is not None:
            body["data"] = data
        self._ws.send(json.dumps(body))
        return request_id

    def _recv(self, wait: float) -> dict[str, Any] | None:
        """One message, or ``None`` when nothing came within ``wait`` seconds."""
        try:
            self._ws.settimeout(max(wait, 0.001))
        except Exception:
            pass
        try:
            raw = self._ws.recv()
        except Exception as exc:
            if _nothing_yet(exc):
                return None
            raise VtsError(f"Lost the connection to VTube Studio: {exc}") from exc
        if raw in ("", b"", None):
            raise VtsError("VTube Studio closed the connection")
        try:
            message = json.loads(raw)
        except ValueError:
            return None
        return message if isinstance(message, dict) else None

    def request(self, message_type: str, data: dict[str, Any] | None = None, *, wait: float | None = None) -> dict[str, Any]:
        """Send a request and return the ``data`` of its response (events that come meanwhile are kept for :meth:`poll`)."""
        request_id = self._send(message_type, data)
        deadline = self._clock() + (self.timeout if wait is None else wait)
        while True:
            left = deadline - self._clock()
            if left <= 0:
                raise VtsError(f"VTube Studio did not answer {message_type} in time")
            message = self._recv(min(left, 1.0))
            if message is None:
                continue
            if message.get("requestID") == request_id:
                body = message.get("data") or {}
                if message.get("messageType") == "APIError":
                    raise VtsError(f"{message_type}: {body.get('message') or 'error'} ({body.get('errorID')})", body.get("errorID"))
                return body
            if str(message.get("messageType", "")).endswith("Event"):
                self._events.append(message)

    def _authenticate(self) -> None:
        token = self.token_file.read_text(encoding="utf-8").strip() if self.token_file.is_file() else ""
        names = {"pluginName": PLUGIN_NAME, "pluginDeveloper": PLUGIN_DEVELOPER}
        if token:
            reply = self.request("AuthenticationRequest", {**names, "authenticationToken": token})
            if reply.get("authenticated"):
                return
        # No token yet, or the user took the plugin's access away: ask again (VTube Studio shows a popup).
        data: dict[str, Any] = dict(names)
        icon = _icon()
        if icon:
            data["pluginIcon"] = icon
        try:
            reply = self.request("AuthenticationTokenRequest", data, wait=self.approval_wait)
        except VtsError as exc:
            if exc.code == TOKEN_DENIED:
                raise VtsError("Access was denied in VTube Studio's popup. Allow the plugin there to record the avatar.", exc.code) from exc
            raise
        token = str(reply.get("authenticationToken") or "")
        if not token:
            raise VtsError("VTube Studio gave no token")
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        self.token_file.write_text(token, encoding="utf-8")
        reply = self.request("AuthenticationRequest", {**names, "authenticationToken": token})
        if not reply.get("authenticated"):
            raise VtsError(f"VTube Studio did not accept the token: {reply.get('reason') or 'no reason given'}")

    def close(self) -> None:
        try:
            self._ws.close()
        except Exception:
            pass

    def __enter__(self) -> "VtsClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------ what the recorder uses
    def subscribe(self, event_name: str, config: dict[str, Any] | None = None) -> None:
        self.request("EventSubscriptionRequest", {"eventName": event_name, "subscribe": True, "config": config or {}})

    def parameters(self) -> tuple[dict[str, Any], dict[str, float]]:
        """``({"name": model name, "id": model id}, {parameter: value})`` of the loaded model (empty when none is loaded)."""
        data = self.request("Live2DParameterListRequest")
        model = {"name": str(data.get("modelName") or ""), "id": str(data.get("modelID") or "")}
        if not data.get("modelLoaded"):
            return model, {}
        values = {str(p.get("name")): float(p.get("value")) for p in data.get("parameters") or [] if isinstance(p, dict) and isinstance(p.get("value"), (int, float))}
        return model, values

    def poll(self, wait: float = 0.0) -> list[dict[str, Any]]:
        """The events that have arrived (``{"messageType": ..., "data": ...}``), waiting at most ``wait`` seconds for the first."""
        found, self._events = self._events, []
        patience = 0.001 if found else wait
        while True:
            message = self._recv(patience)
            if message is None:
                return found
            patience = 0.001  # after the first, only what is already there
            if str(message.get("messageType", "")).endswith("Event"):
                found.append(message)
