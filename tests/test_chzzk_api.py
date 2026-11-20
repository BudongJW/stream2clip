"""CHZZK's Open API (sign-in, tokens, the Socket.IO session) and viewer votes - without CHZZK."""

from __future__ import annotations

import json
import threading
import urllib.parse
import urllib.request

import pytest

from stream2clip.chat import ChatMessage
from stream2clip.chzzk_api import ChzzkApi, ChzzkApiChat, ChzzkApiError, chat_event, login, socket_url
from stream2clip.recorder import ChatPart
from stream2clip.session import SessionWriter, load_session


class FakeOpenApi:
    """CHZZK's REST side: token and session endpoints, recording what was asked."""

    def __init__(self):
        self.calls = []
        self.expired_once = False
        self.issued = 0

    def __call__(self, method, url, headers, body):
        parts = urllib.parse.urlsplit(url)
        data = json.loads(body) if body else {}
        self.calls.append((method, parts.path, dict(urllib.parse.parse_qsl(parts.query)), headers.get("Authorization"), data))
        if parts.path == "/auth/v1/token":
            if data.get("grantType") == "authorization_code" and data.get("code") != "good-code":
                return 401, json.dumps({"code": 401, "message": "INVALID_TOKEN"}).encode()
            self.issued += 1
            return 200, json.dumps({"code": 200, "message": None, "content": {"accessToken": f"access-{self.issued}", "refreshToken": f"refresh-{self.issued}", "tokenType": "Bearer", "expiresIn": "86400"}}).encode()
        if headers.get("Authorization") != f"Bearer access-{self.issued}":
            return 401, json.dumps({"code": 401, "message": "INVALID_TOKEN"}).encode()
        if parts.path == "/open/v1/sessions/auth":
            if self.expired_once is False:
                self.expired_once = True
                return 401, json.dumps({"code": 401, "message": "INVALID_TOKEN"}).encode()  # the day-old token ran out
            return 200, json.dumps({"code": 200, "content": {"url": "https://ssio08.nchat.naver.com:443?auth=SOCKET"}}).encode()
        if parts.path.startswith("/open/v1/sessions/events/subscribe/"):
            return 200, json.dumps({"code": 200, "content": None}).encode()
        return 404, json.dumps({"code": 404, "message": "NOT_FOUND"}).encode()


class Clock:
    def __init__(self, now=1000.0):
        self.now = now

    def __call__(self):
        return self.now


def make_api(tmp_path, server=None, clock=None):
    return ChzzkApi("client-1", "secret-1", token_file=tmp_path / "chzzk.json", send=server or FakeOpenApi(), clock=clock or Clock())


def test_the_client_needs_its_id_and_secret(monkeypatch):
    monkeypatch.delenv("CHZZK_CLIENT_ID", raising=False)
    monkeypatch.delenv("CHZZK_CLIENT_SECRET", raising=False)
    with pytest.raises(ChzzkApiError, match="CHZZK_CLIENT_ID"):
        ChzzkApi()


def test_tokens_are_kept_refreshed_and_used(tmp_path):
    server, clock = FakeOpenApi(), Clock()
    api = make_api(tmp_path, server, clock)
    url = urllib.parse.urlsplit(api.authorize_url("http://localhost:8765/callback", "st"))
    assert url.netloc == "chzzk.naver.com" and url.path == "/account-interlock"
    assert dict(urllib.parse.parse_qsl(url.query)) == {"clientId": "client-1", "redirectUri": "http://localhost:8765/callback", "state": "st"}
    with pytest.raises(ChzzkApiError, match="Not signed in"):
        api.access_token()
    with pytest.raises(ChzzkApiError, match="INVALID_TOKEN"):
        api.exchange("bad-code", "st")
    api.exchange("good-code", "st")
    assert server.calls[-1][4] == {"grantType": "authorization_code", "clientId": "client-1", "clientSecret": "secret-1", "code": "good-code", "state": "st"}
    assert api.signed_in and api.access_token() == "access-1"
    clock.now += 86_400  # a day later the access token has run out: the refresh token gets a new one
    assert api.access_token() == "access-2"
    assert server.calls[-1][4]["grantType"] == "refresh_token" and server.calls[-1][4]["refreshToken"] == "refresh-1"
    # a 401 on a call (the token was revoked or ran out early) refreshes once and tries again
    assert api.session_url() == "https://ssio08.nchat.naver.com:443?auth=SOCKET"
    assert [c[1] for c in server.calls[-3:]] == ["/open/v1/sessions/auth", "/auth/v1/token", "/open/v1/sessions/auth"]
    api.subscribe("chat", "key-1")
    assert server.calls[-1][1:3] == ("/open/v1/sessions/events/subscribe/chat", {"sessionKey": "key-1"})
    assert server.calls[-1][3] == "Bearer access-3"


def test_the_socket_url_is_engine_io_3_over_websocket():
    url = urllib.parse.urlsplit(socket_url("https://ssio08.nchat.naver.com:443?auth=TOKEN"))
    assert (url.scheme, url.netloc, url.path) == ("wss", "ssio08.nchat.naver.com:443", "/socket.io/")
    assert dict(urllib.parse.parse_qsl(url.query)) == {"auth": "TOKEN", "transport": "websocket", "EIO": "3"}


def test_events_become_chat_messages():
    chat = chat_event("CHAT", {"senderChannelId": "c1", "content": "ㅋㅋ {:smile:}", "emojis": {"smile": "https://x/smile.png"}, "messageTime": 1700000000123, "profile": {"userRoleCode": "streaming_chat_manager"}})
    assert (chat.time, chat.text, chat.emotes, chat.role) == (1700000000.123, "ㅋㅋ :smile:", (":smile:",), "moderator")
    assert len(chat.author) == 12 and chat.author != "c1"  # anonymous
    donation = chat_event("DONATION", {"donationType": "CHAT", "donatorChannelId": "c2", "payAmount": "1,000", "donationText": "잘 봤어요"})
    assert donation.kind == "paid" and donation.amount == 1000.0 and donation.currency == "KRW" and donation.text == "잘 봤어요"
    assert chat_event("SUBSCRIPTION", {"subscriberChannelId": "c3", "tierNo": 1}).kind == "member"
    assert chat_event("OTHER", {}) is None


class FakeSocket:
    def __init__(self, frames):
        self.frames = list(frames)
        self.sent = []
        self.closed = False

    def settimeout(self, value):
        pass

    def send(self, text):
        self.sent.append(text)

    def recv(self):
        if not self.frames:
            raise TimeoutError("nothing yet")
        return self.frames.pop(0)

    def close(self):
        self.closed = True


def test_the_session_subscribes_and_reads_chat_and_donations(tmp_path):
    server = FakeOpenApi()
    api = make_api(tmp_path, server)
    api.exchange("good-code", "st")
    socket = FakeSocket([
        '0{"sid":"abc","pingInterval":20000,"pingTimeout":60000}', "40",
        '42["SYSTEM",{"type":"connected","data":{"sessionKey":"key-9"}}]',
        '42["SYSTEM","{\\"type\\":\\"subscribed\\",\\"data\\":{\\"eventType\\":\\"CHAT\\"}}"]',  # data as a JSON string
        '42["CHAT",{"senderChannelId":"u1","content":"!clip","messageTime":1700000001000,"profile":{"userRoleCode":"streamer"}}]',
        '42["DONATION","{\\"donatorChannelId\\":\\"u2\\",\\"payAmount\\":\\"5000\\",\\"donationText\\":\\"hi\\"}"]',
    ])
    opened = []
    clock = Clock(0.0)

    def connect(url):
        opened.append(url)
        return socket

    chat = ChzzkApiChat(api, connect=connect, clock=clock)
    messages = chat.read()
    assert opened == [socket_url("https://ssio08.nchat.naver.com:443?auth=SOCKET")]
    assert chat.session_key == "key-9"
    subscribed = [c[1].rsplit("/", 1)[1] for c in server.calls if "/subscribe/" in c[1]]
    assert subscribed == ["chat", "donation"]
    assert [(m.text, m.kind, m.amount, m.role) for m in messages] == [("!clip", "text", 0.0, "owner"), ("hi", "paid", 5000.0, "")]
    clock.now = 21.0  # past the ping interval of 20 s
    chat.read()
    assert socket.sent == ["2"]
    socket.frames.append('42["SYSTEM",{"type":"revoked","data":{"eventType":"CHAT"}}]')
    with pytest.raises(ChzzkApiError, match="sign in again"):
        chat.read()
    assert socket.closed


def test_open_chat_takes_the_api_for_chzzk_api(monkeypatch, tmp_path):
    from stream2clip.live import open_chat, reads_chat_itself

    monkeypatch.setenv("CHZZK_CLIENT_ID", "id")
    monkeypatch.setenv("CHZZK_CLIENT_SECRET", "secret")
    source, described = open_chat("chzzk-api", tmp_path)
    assert isinstance(source, ChzzkApiChat) and "Open API" in described
    assert reads_chat_itself("chzzk-api")


def test_login_catches_the_code_on_the_local_redirect(tmp_path):
    import socket as sockets

    with sockets.socket() as probe:  # a free port for the redirect
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = FakeOpenApi()
    api = make_api(tmp_path, server)
    redirect = f"http://127.0.0.1:{port}/callback"
    answers = []

    def browser(url):
        state = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))["state"]

        def visit():
            for path in ("/favicon.ico", f"/callback?code=good-code&state={state}"):
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as reply:
                        answers.append(reply.status)
                except urllib.error.HTTPError as exc:
                    answers.append(exc.code)

        threading.Thread(target=visit, daemon=True).start()

    tokens = login(api, redirect, open_browser=browser, timeout=10)
    assert tokens["accessToken"] == "access-1" and answers == [404, 200]
    with pytest.raises(ChzzkApiError, match="local address"):
        login(api, "https://example.com/callback", open_browser=lambda url: None)


def test_chzzk_logout_forgets_the_tokens(tmp_path, monkeypatch, capsys):
    from stream2clip.cli import main

    token = tmp_path / "chzzk.json"
    monkeypatch.setenv("STREAM2CLIP_CHZZK_TOKEN", str(token))
    token.write_text("{}", encoding="utf-8")
    assert main(["chzzk", "logout"]) == 0 and not token.exists()
    assert main(["chzzk", "logout"]) == 0
    assert "not signed in" in capsys.readouterr().out


# ----------------------------------------------------------------------------- viewer votes


class ListChat:
    def __init__(self, batches):
        self.batches, self.ended = list(batches), False

    def read(self):
        return self.batches.pop(0) if self.batches else []

    def close(self):
        pass


def test_enough_viewers_typing_clip_leave_a_marker(tmp_path):
    clock = Clock()
    writer = SessionWriter(tmp_path / "s.jsonl", clock=clock)

    def msg(t, author, text="!clip", role=""):
        return ChatMessage(time=t, text=text, author=author, role=role)

    batches = [
        [msg(1000, "a"), msg(1001, "a"), msg(1002, "owner", role="owner")],  # the same viewer twice, the streamer's own does not count as a vote
        [msg(1010, "b"), msg(1035, "c")],  # c is 35 s after a: a has dropped out of the 30 s window
        [msg(1038, "d", "!CLIP please")],  # b, c, d within 30 s: a marker at b's vote
        [msg(1050, "e"), msg(1051, "f"), msg(1052, "g")],  # three more right after: the cooldown holds them back
        [msg(1200, "h"), msg(1201, "i"), msg(1202, "j", "nice")],  # only two votes
    ]
    part = ChatPart(writer, lambda: ListChat(batches), viewer_votes=3)
    for _ in batches:
        clock.now += 1
        part.poll(clock.now)
    writer.close()
    session = load_session(tmp_path / "s.jsonl")
    markers = session.of("marker")
    assert [(e.t, e.data) for e in markers] == [(1010.0, {"by": "viewers", "label": "3 viewers"})]
    # viewers' votes are chat: the marker keeps its time, a hotkey marker would be moved by the chat delay
    assert [m.time for m in session.messages(origin=1000.0) if m.text == "!clip" and m.author == ""] == [10.0]
