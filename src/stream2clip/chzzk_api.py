"""CHZZK's official Open API (https://chzzk.gitbook.io/chzzk): the chat and donations of one's own channel.

The unofficial reader of :mod:`stream2clip.live` reads any channel's chat as a viewer. The
Open API is the sanctioned way, but only for a channel whose owner signed in: the streamer
registers an application in the CHZZK developer center (client id and secret, a login
redirect URL such as ``http://localhost:8765/callback``), signs in once with
``stream2clip chzzk login`` and then records with ``--chat chzzk-api``.

Flow (all from the documentation):

1. ``GET https://chzzk.naver.com/account-interlock?clientId&redirectUri&state`` in the
   browser; CHZZK sends ``code`` and ``state`` to the redirect URL.
2. ``POST /auth/v1/token`` (``grantType=authorization_code``) -> access token (1 day) and
   refresh token (30 days, used once). Kept in the app's config folder.
3. ``GET /open/v1/sessions/auth`` -> a Socket.IO URL (Socket.IO client 1.x - 2.0.3).
4. The socket says ``SYSTEM`` ``connected`` with a ``sessionKey``; ``POST
   /open/v1/sessions/events/subscribe/chat`` and ``/donation`` with it.
5. ``CHAT`` and ``DONATION`` events arrive on the socket.

Socket.IO 2 runs on Engine.IO 3: text frames ``0{...}`` (open, with the ping interval),
``40`` (namespace joined), ``2``/``3`` (ping/pong, the client pings), ``42[event, data]``.
"""

from __future__ import annotations

import json
import math
import os
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

from .chat import ChatMessage, author_key, role_of

__all__ = ["ChzzkApi", "ChzzkApiError", "ChzzkApiChat", "token_path", "login", "socket_url", "API_SOURCE"]

OPENAPI = "https://openapi.chzzk.naver.com"
AUTHORIZE = "https://chzzk.naver.com/account-interlock"
#: What ``--chat`` takes to read one's own channel through the Open API.
API_SOURCE = "chzzk-api"
_EMOJI_SPLIT = "{:"


class ChzzkApiError(RuntimeError):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def token_path() -> Path:
    """Where the tokens are kept: ``STREAM2CLIP_CHZZK_TOKEN``, else the app's config folder."""
    override = os.environ.get("STREAM2CLIP_CHZZK_TOKEN")
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
    return root / "chzzk-token.json"


def _send(method: str, url: str, headers: dict[str, str], body: bytes | None) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 - fixed https hosts
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


class ChzzkApi:
    """Tokens and the REST calls the recorder needs. ``send(method, url, headers, body) -> (status, body)`` is replaceable for tests."""

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        *,
        token_file: str | os.PathLike[str] | None = None,
        send: Callable[[str, str, dict[str, str], bytes | None], tuple[int, bytes]] | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.client_id = client_id or os.environ.get("CHZZK_CLIENT_ID", "")
        self.client_secret = client_secret or os.environ.get("CHZZK_CLIENT_SECRET", "")
        if not self.client_id or not self.client_secret:
            raise ChzzkApiError("The CHZZK Open API needs the application's client id and secret: CHZZK_CLIENT_ID and CHZZK_CLIENT_SECRET (CHZZK developer center)")
        self.token_file = Path(token_file) if token_file else token_path()
        self._send = send or _send
        self._clock = clock

    # ------------------------------------------------------------------ tokens
    def authorize_url(self, redirect_uri: str, state: str) -> str:
        return AUTHORIZE + "?" + urllib.parse.urlencode({"clientId": self.client_id, "redirectUri": redirect_uri, "state": state})

    def _tokens(self) -> dict[str, Any]:
        try:
            data = json.loads(self.token_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _keep(self, content: dict[str, Any]) -> dict[str, Any]:
        expires = float(content.get("expiresIn") or 86400)
        tokens = {"accessToken": content.get("accessToken", ""), "refreshToken": content.get("refreshToken", ""), "expiresAt": self._clock() + expires}
        if not tokens["accessToken"]:
            raise ChzzkApiError("CHZZK gave no access token")
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        self.token_file.write_text(json.dumps(tokens), encoding="utf-8")
        try:
            os.chmod(self.token_file, 0o600)  # only this user may read it
        except OSError:
            pass
        return tokens

    def exchange(self, code: str, state: str) -> dict[str, Any]:
        """The tokens for the ``code`` CHZZK sent to the redirect URL (kept in :attr:`token_file`)."""
        content = self._call("POST", "/auth/v1/token", body={"grantType": "authorization_code", "clientId": self.client_id, "clientSecret": self.client_secret, "code": code, "state": state}, auth=None)
        return self._keep(content)

    def refresh(self) -> dict[str, Any]:
        refresh_token = self._tokens().get("refreshToken")
        if not refresh_token:
            raise ChzzkApiError("Not signed in to CHZZK: run  stream2clip chzzk login")
        content = self._call("POST", "/auth/v1/token", body={"grantType": "refresh_token", "refreshToken": refresh_token, "clientId": self.client_id, "clientSecret": self.client_secret}, auth=None)
        return self._keep(content)

    def access_token(self) -> str:
        tokens = self._tokens()
        if not tokens.get("accessToken"):
            raise ChzzkApiError("Not signed in to CHZZK: run  stream2clip chzzk login")
        if float(tokens.get("expiresAt") or 0) - 60 <= self._clock():
            tokens = self.refresh()
        return str(tokens["accessToken"])

    @property
    def signed_in(self) -> bool:
        return bool(self._tokens().get("refreshToken"))

    # ------------------------------------------------------------------ calls
    def _call(self, method: str, path: str, *, params: dict[str, str] | None = None, body: dict[str, Any] | None = None, auth: str | None = "user") -> Any:
        url = OPENAPI + path + ("?" + urllib.parse.urlencode(params) if params else "")
        for attempt in (1, 2):
            headers = {"Content-Type": "application/json", "User-Agent": "stream2clip"}
            if auth == "user":
                headers["Authorization"] = "Bearer " + self.access_token()
            status, raw = self._send(method, url, headers, json.dumps(body).encode("utf-8") if body is not None else None)
            try:
                reply = json.loads(raw or b"{}")
            except ValueError:
                reply = {}
            if status == 401 and auth == "user" and attempt == 1:
                self.refresh()  # the access token ran out (1 day): once more with a new one
                continue
            if status >= 400 or (isinstance(reply.get("code"), int) and reply["code"] >= 400):
                raise ChzzkApiError(f"CHZZK {method} {path}: {reply.get('message') or status}", status)
            return reply.get("content")
        raise ChzzkApiError(f"CHZZK {method} {path}: not authorized", 401)  # pragma: no cover - the loop returns or raises

    def session_url(self) -> str:
        content = self._call("GET", "/open/v1/sessions/auth") or {}
        url = content.get("url") if isinstance(content, dict) else None
        if not url:
            raise ChzzkApiError("CHZZK gave no session URL")
        return str(url)

    def subscribe(self, event: str, session_key: str) -> None:
        """``event``: chat, donation or subscription."""
        self._call("POST", f"/open/v1/sessions/events/subscribe/{event}", params={"sessionKey": session_key})


def socket_url(url: str) -> str:
    """The Socket.IO URL CHZZK gives (``https://host:443?auth=...``) -> the WebSocket of Engine.IO 3."""
    parts = urllib.parse.urlsplit(url)
    scheme = "wss" if parts.scheme in ("https", "wss") else "ws"
    query = urllib.parse.parse_qsl(parts.query) + [("transport", "websocket"), ("EIO", "3")]
    return urllib.parse.urlunsplit((scheme, parts.netloc, "/socket.io/", urllib.parse.urlencode(query), ""))


def _data(value: Any) -> dict[str, Any]:
    """Event data arrives as an object or as a JSON string."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return {}
    return value if isinstance(value, dict) else {}


def _emotes(text: str, emojis: Any) -> tuple[str, tuple[str, ...]]:
    names = tuple(f":{key}:" for key in (emojis or {}) if isinstance(emojis, dict))
    if _EMOJI_SPLIT in text:  # "{:name:}" in the text, as in the unofficial chat: the same ":name:" form
        for key in emojis or {}:
            text = text.replace("{:" + str(key) + ":}", f":{key}:")
    return text, names


def chat_event(kind: str, data: dict[str, Any]) -> ChatMessage | None:
    """A ``CHAT`` / ``DONATION`` / ``SUBSCRIPTION`` event as a :class:`ChatMessage` (time: wall clock, or NaN for "now")."""
    if kind == "CHAT":
        text, emotes = _emotes(str(data.get("content") or ""), data.get("emojis"))
        stamp = data.get("messageTime")
        profile = data.get("profile") if isinstance(data.get("profile"), dict) else {}
        return ChatMessage(
            time=float(stamp) / 1000 if isinstance(stamp, (int, float)) else math.nan, text=text,
            author=author_key(str(data.get("senderChannelId") or "")), emotes=emotes, role=role_of(profile.get("userRoleCode")),
        )
    if kind == "DONATION":
        text, emotes = _emotes(str(data.get("donationText") or ""), data.get("emojis"))
        try:
            amount = float(str(data.get("payAmount") or "0").replace(",", ""))
        except ValueError:
            amount = 0.0
        return ChatMessage(time=math.nan, text=text, author=author_key(str(data.get("donatorChannelId") or "")), kind="paid", amount=amount, currency="KRW", emotes=emotes)
    if kind == "SUBSCRIPTION":
        return ChatMessage(time=math.nan, text="", author=author_key(str(data.get("subscriberChannelId") or "")), kind="member")
    return None


class ChzzkApiChat:
    """One's own channel's chat and donations through the Open API, as a :class:`~stream2clip.live.ChatSource`."""

    name = "CHZZK Open API"

    def __init__(self, api: ChzzkApi, *, connect: Callable[..., Any] | None = None, clock: Callable[[], float] = time.monotonic, events: tuple[str, ...] = ("chat", "donation")) -> None:
        self.api = api
        self.ended = False
        self.events = events
        self._connect = connect
        self._clock = clock
        self._socket: Any = None
        self._ping_every = 25.0
        self._last_ping = 0.0
        self.session_key = ""

    def _open(self) -> None:
        from .live import _open_websocket

        url = socket_url(self.api.session_url())
        self._socket = (self._connect or _open_websocket)(url)
        try:
            self._socket.settimeout(0.05)
        except Exception:
            pass
        self._last_ping = self._clock()
        self.session_key = ""

    def _drop(self) -> None:
        if self._socket is not None:
            try:
                self._socket.close()
            except Exception:
                pass
        self._socket = None

    def _frame(self, frame: str) -> list[ChatMessage]:
        if frame.startswith("0"):  # Engine.IO open: how often to ping
            try:
                self._ping_every = float(json.loads(frame[1:]).get("pingInterval", 25000)) / 1000
            except ValueError:
                pass
            return []
        if not frame.startswith("42"):
            return []  # "40" (namespace joined), "3" (pong) ...
        try:
            name, *rest = json.loads(frame[2:])
        except (ValueError, TypeError):
            return []
        data = _data(rest[0] if rest else {})
        if name == "SYSTEM":
            inner = _data(data.get("data"))
            if data.get("type") == "connected" and inner.get("sessionKey"):
                self.session_key = str(inner["sessionKey"])
                for event in self.events:
                    self.api.subscribe(event, self.session_key)
            elif data.get("type") == "revoked":
                raise ChzzkApiError(f"CHZZK took the {inner.get('eventType', '')} permission back: sign in again (stream2clip chzzk login)")
            return []
        message = chat_event(str(name), data)
        return [message] if message is not None else []

    def read(self) -> list[ChatMessage]:
        if self.ended:
            return []
        if self._socket is None:
            self._open()
        from .live import _nothing_yet

        found: list[ChatMessage] = []
        try:
            if self._clock() - self._last_ping >= self._ping_every:
                self._socket.send("2")
                self._last_ping = self._clock()
            while True:
                frame = self._socket.recv()
                if frame in ("", b"", None):
                    self._drop()
                    break
                found.extend(self._frame(frame.decode("utf-8") if isinstance(frame, bytes) else str(frame)))
        except ChzzkApiError:
            self._drop()
            raise
        except Exception as error:
            if not _nothing_yet(error):
                self._drop()
        return found

    def close(self) -> None:
        self.ended = True
        self._drop()


def login(
    api: ChzzkApi,
    redirect_uri: str = "http://localhost:8765/callback",
    *,
    open_browser: Callable[[str], Any] | None = None,
    timeout: float = 300.0,
    on_url: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Sign in once: open CHZZK's consent page and catch the code on ``redirect_uri`` (a local address)."""
    from http.server import BaseHTTPRequestHandler, HTTPServer

    parts = urllib.parse.urlsplit(redirect_uri)
    if parts.hostname not in ("localhost", "127.0.0.1"):
        raise ChzzkApiError("The login redirect URL must be a local address such as http://localhost:8765/callback (and the same in the CHZZK developer center)")
    state = secrets.token_urlsafe(16)
    caught: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - http.server API
            query = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(self.path).query))
            if urllib.parse.urlsplit(self.path).path == (parts.path or "/") and "code" in query:
                caught.update(query)
                body = "stream2clip: signed in to CHZZK. This tab can be closed.".encode("utf-8")
                self.send_response(200)
            else:
                body = b"stream2clip: waiting for CHZZK"
                self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: Any) -> None:
            pass

    server = HTTPServer((parts.hostname or "127.0.0.1", parts.port or 80), Handler)
    server.timeout = 1.0
    url = api.authorize_url(redirect_uri, state)
    if on_url is not None:
        on_url(url)
    if open_browser is None:
        import webbrowser

        open_browser = webbrowser.open
    open_browser(url)
    deadline = time.monotonic() + timeout
    try:
        while "code" not in caught and time.monotonic() < deadline:
            server.handle_request()
    finally:
        server.server_close()
    if "code" not in caught:
        raise ChzzkApiError("No answer from CHZZK's sign-in page in time")
    if caught.get("state") != state:
        raise ChzzkApiError("The answer from CHZZK's sign-in page does not match this request (state); try again")
    return api.exchange(caught["code"], caught["state"])
