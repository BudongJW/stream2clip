"""CHZZK and SOOP live chat for live mode: addresses, message parsing, the connection (with scripted sockets)."""

from __future__ import annotations

import json
import math
import sys

import pytest

from stream2clip.chat import chzzk_live_message, soop_live_message
from stream2clip.live import ChzzkLiveChat, LiveConfig, SoopLiveChat, SurgeDetector, TwitchLiveChat, _open_websocket, chzzk_channel, open_chat, reads_chat_itself, soop_channel

CHANNEL = "0123456789abcdef0123456789abcdef"
F = chr(12)  # the form feed that ends a field of a SOOP packet


def test_channel_addresses():
    assert chzzk_channel(f"https://chzzk.naver.com/live/{CHANNEL}") == CHANNEL
    assert chzzk_channel(f"https://chzzk.naver.com/{CHANNEL.upper()}?tab=1") == CHANNEL and chzzk_channel(f"m.chzzk.naver.com/live/{CHANNEL}/") == CHANNEL
    assert chzzk_channel("https://chzzk.naver.com/video/16230061") is None  # a replay: that is what fetch is for
    assert soop_channel("https://play.sooplive.co.kr/some_id") == "some_id" and soop_channel("https://play.sooplive.co.kr/some_id/290123456") == "some_id"
    assert soop_channel("https://ch.sooplive.co.kr/some_id") == "some_id"
    assert soop_channel("https://vod.sooplive.co.kr/player/123456") is None
    assert reads_chat_itself(f"https://chzzk.naver.com/live/{CHANNEL}") and reads_chat_itself("https://play.sooplive.co.kr/some_id") and reads_chat_itself("https://www.twitch.tv/abc")
    assert not reads_chat_itself("https://www.youtube.com/watch?v=abc") and not reads_chat_itself("chat.jsonl")


def chzzk_item(text="ㅋㅋㅋ", *, role="common_user", pay=0, kind=1, status="NORMAL", uid="viewer"):
    extras = {"chatType": "STREAMING", **({"payAmount": pay} if pay else {})}
    return {"uid": uid, "msg": text, "msgTime": 1700000000500, "msgTypeCode": kind, "msgStatusType": status,
            "profile": json.dumps({"userIdHash": uid, "nickname": "닉네임", "userRoleCode": role}), "extras": json.dumps(extras)}


def test_chzzk_live_messages():
    plain = chzzk_live_message(chzzk_item("와 {:d_49:} 대박{:d_1:}"))
    assert plain.text == "와 :d_49: 대박:d_1:" and plain.emotes == (":d_49:", ":d_1:") and plain.kind == "text"
    assert plain.time == pytest.approx(1700000000.5) and plain.role == ""
    assert len(plain.author) == 12 and "viewer" not in plain.author  # hashed, the nickname is not kept
    donation = chzzk_live_message(chzzk_item("화이팅", pay=5000, kind=10))
    assert (donation.kind, donation.amount, donation.currency) == ("paid", 5000.0, "KRW")
    assert chzzk_live_message(chzzk_item("!clip", role="streamer")).role == "owner"
    assert chzzk_live_message(chzzk_item("공지", role="streaming_chat_manager")).role == "moderator"
    assert chzzk_live_message(chzzk_item("가려진 말", status="HIDDEN")) is None
    assert math.isnan(chzzk_live_message({"uid": "a", "msg": "시각 없음"}).time)


def soop_chat(text, user="viewer01", nick="닉네임"):
    return SoopLiveChat.packet(5, F.join(["", text, user, "0", "1", "1", nick, "65568|163840", "-1", "", "", "", "", "", "", "", ""]))


def test_soop_live_packets():
    assert SoopLiveChat.packet(0, F) == b"\x1b\t000000000100" + F.encode()
    line = soop_live_message(soop_chat("ㅋㅋㅋ 대박", "viewer01(2)"), "streamer1")
    assert (line.text, line.kind, line.role) == ("ㅋㅋㅋ 대박", "text", "") and math.isnan(line.time)
    assert line.author == soop_live_message(soop_chat("또", "viewer01"), "streamer1").author  # the same viewer on two devices
    assert soop_live_message(soop_chat("!clip", "streamer1"), "streamer1").role == "owner"
    balloon = soop_live_message(SoopLiveChat.packet(18, F.join(["", "streamer1", "fan01", "팬", "33", "0", "0", "9419", "33", "0", "0", "", "", "", "", ""])), "streamer1")
    assert (balloon.kind, balloon.amount, balloon.currency) == ("paid", 33.0, "별풍선")
    ad = soop_live_message(SoopLiveChat.packet(87, F.join(["", "302", "streamer1", "fan02", "팬", "a", "b", "c", "d", "e", "7", "0", "", "", "", "", "", "", "", ""])), "streamer1")
    assert (ad.kind, ad.amount, ad.currency) == ("paid", 7.0, "애드벌룬")
    video = soop_live_message(SoopLiveChat.packet(105, F.join(["", "9419", "streamer1", "fan03", "팬", "10", "0", "0", "0", "0", "fan03", "0", "", "", "", "", "", ""])), "streamer1")
    assert (video.kind, video.amount) == ("paid", 10.0)
    for other in (SoopLiveChat.packet(4, F.join(["", "1", "x"])), SoopLiveChat.packet(18, F.join(["", "streamer1", "fan01", "팬", "many"])), b"not a packet", b""):
        assert soop_live_message(other, "streamer1") is None


class FakeWebSocket:
    """Hands out scripted frames; ``None`` (or nothing left) means "nothing for now"."""

    def __init__(self, frames):
        self.frames = list(frames)
        self.sent: list = []
        self.closed = False
        self.timeout = None

    def send(self, data):
        self.sent.append(data)

    def send_binary(self, data):
        self.sent.append(data)

    def settimeout(self, value):
        self.timeout = value

    def recv(self):
        if not self.frames or self.frames[0] is None:
            if self.frames:
                self.frames.pop(0)
            raise TimeoutError
        return self.frames.pop(0)

    def close(self):
        self.closed = True


class Clock:
    def __init__(self, now=1000.0):
        self.now = now

    def __call__(self):
        return self.now


def test_chzzk_chat_is_read_as_a_viewer_who_is_not_signed_in():
    asked = []

    def get(url, data=None):
        asked.append(url)
        if "live-status" in url:
            return json.dumps({"code": 200, "content": {"status": "OPEN", "chatChannelId": "N1abcd"}}).encode()
        return json.dumps({"code": 200, "content": {"accessToken": "token-for-reading", "extraToken": "x"}}).encode()

    first = FakeWebSocket([
        json.dumps({"cmd": 10100, "retCode": 0, "bdy": {"sid": "s"}}),
        json.dumps({"cmd": 93101, "bdy": [chzzk_item("첫 번째"), chzzk_item("가려짐", status="HIDDEN"), chzzk_item("두 번째", role="streamer")]}), None,
        json.dumps({"cmd": 0}), json.dumps({"cmd": 93102, "bdy": [chzzk_item("후원", pay=1000, kind=10)]}), "not json", None,
        "",  # closed by the server
    ])
    second = FakeWebSocket([json.dumps({"cmd": 93101, "bdy": [chzzk_item("다시 연결")]})])
    sockets, urls, clock = [first, second], [], Clock()
    chat = ChzzkLiveChat(f"https://chzzk.naver.com/live/{CHANNEL}", get=get, connect=lambda url, **options: urls.append(url) or sockets.pop(0), clock=clock)
    assert chat.channel == CHANNEL and asked == []  # nothing happens before the first read

    messages = chat.read()
    assert [m.text for m in messages] == ["첫 번째", "두 번째"] and messages[1].role == "owner"
    assert asked[0].endswith(f"/channels/{CHANNEL}/live-status") and "channelId=N1abcd" in asked[1] and "chatType=STREAMING" in asked[1]
    expected_server = sum(ord(ch) for ch in "N1abcd") % 9 + 1
    assert urls == [f"wss://kr-ss{expected_server}.chat.naver.com/chat"]
    hello = json.loads(first.sent[0])
    assert hello["cmd"] == 100 and hello["cid"] == "N1abcd" and hello["bdy"]["accTkn"] == "token-for-reading" and hello["bdy"]["auth"] == "READ" and hello["bdy"]["uid"] is None
    assert first.timeout == 0.05

    paid = chat.read()
    assert [m.kind for m in paid] == ["paid"] and json.loads(first.sent[-1]) == {"ver": "3", "cmd": 10000}  # the server's "are you there" was answered
    clock.now += 25
    assert chat.read() == [] and first.closed  # the keep-alive went out, then the server closed
    assert {"ver": "3", "cmd": 0} in [json.loads(sent) for sent in first.sent]
    assert [m.text for m in chat.read()] == ["다시 연결"] and len(urls) == 2  # connected again, with a new token
    chat.close()
    assert chat.ended and second.closed and chat.read() == []


def test_chzzk_chat_explains_a_channel_that_is_not_live():
    def offline(url, data=None):
        return json.dumps({"code": 200, "content": {"status": "CLOSE", "chatChannelId": None}}).encode()

    with pytest.raises(RuntimeError, match="no chat to read now"):
        ChzzkLiveChat(CHANNEL, get=offline, connect=lambda url, **options: FakeWebSocket([])).read()
    with pytest.raises(ValueError, match="Not a CHZZK channel"):
        ChzzkLiveChat("https://chzzk.naver.com/video/123")

    def unreachable(url, data=None):
        raise OSError("no route")

    chat = ChzzkLiveChat(CHANNEL, get=unreachable, retries=2)
    assert chat.read() == []
    with pytest.raises(RuntimeError, match="Could not reach the CHZZK chat"):
        chat.read()


def test_soop_chat_is_read_as_a_viewer_who_is_not_signed_in():
    posted = []

    def get(url, data=None):
        posted.append((url, data))
        return json.dumps({"CHANNEL": {"RESULT": 1, "BJID": "streamer1", "CHDOMAIN": "CHAT-XX.sooplive.co.kr", "CHPT": "8060", "CHATNO": "8836", "FTK": "f"}}).encode()

    balloon = SoopLiveChat.packet(18, F.join(["", "streamer1", "fan01", "팬", "100", "0", "0", "1", "100", "0", "0", "", "", "", "", ""]))
    sock = FakeWebSocket([SoopLiveChat.packet(1, "ok"), SoopLiveChat.packet(2, F.join(["", "8836", "streamer1"])), soop_chat("안녕하세요"), soop_chat("오늘 방송", "streamer1"), balloon, None])
    opened, clock = [], Clock()
    chat = SoopLiveChat("https://play.sooplive.co.kr/Streamer1/290123456", get=get, connect=lambda url, **options: opened.append((url, options)) or sock, clock=clock)
    messages = chat.read()
    assert [(m.text, m.kind, m.role) for m in messages] == [("안녕하세요", "text", ""), ("오늘 방송", "text", "owner"), ("", "paid", "")]
    assert posted[0][0].endswith("player_live_api.php?bjid=Streamer1") and b"bid=Streamer1" in posted[0][1] and b"type=live" in posted[0][1]
    assert opened == [("wss://chat-xx.sooplive.co.kr:8061/Websocket/streamer1", {"subprotocols": ["chat"]})]  # the port after the one the API names
    assert sock.sent[0] == SoopLiveChat.packet(1, F * 3 + "16" + F) and sock.sent[1] == SoopLiveChat.packet(2, F + "8836" + F * 5)
    clock.now += 60
    assert chat.read() == [] and sock.sent[-1] == SoopLiveChat.packet(0, F)  # keep-alive
    chat.close()
    assert sock.closed

    def needs_login(url, data=None):
        return json.dumps({"CHANNEL": {"RESULT": -6}}).encode()

    with pytest.raises(RuntimeError, match="no chat to read now"):
        SoopLiveChat("some_id", get=needs_login, connect=lambda url, **options: sock).read()
    with pytest.raises(ValueError, match="Not a SOOP channel"):
        SoopLiveChat("https://vod.sooplive.co.kr/player/1")


def test_open_chat_picks_the_reader_for_each_site(tmp_path):
    chat, described = open_chat(f"https://chzzk.naver.com/live/{CHANNEL}", tmp_path)
    assert isinstance(chat, ChzzkLiveChat) and "CHZZK chat" in described
    chat, described = open_chat("https://play.sooplive.co.kr/some_id", tmp_path)
    assert isinstance(chat, SoopLiveChat) and chat.streamer == "some_id" and "SOOP chat" in described
    assert isinstance(open_chat("https://www.twitch.tv/abc", tmp_path)[0], TwitchLiveChat)


def test_missing_websocket_client_is_explained(monkeypatch):
    monkeypatch.setitem(sys.modules, "websocket", None)  # as if websocket-client were not installed
    with pytest.raises(RuntimeError, match=r"stream2clip\[obs\]"):
        _open_websocket("wss://example.invalid/chat")
    with pytest.raises(RuntimeError, match=r"stream2clip\[obs\]"):
        ChzzkLiveChat(CHANNEL, get=lambda url, data=None: json.dumps({"content": {"chatChannelId": "c", "accessToken": "t"}}).encode()).read()


def test_soop_messages_without_a_time_count_as_now():
    detector = SurgeDetector(LiveConfig(warmup=60, min_messages=5))
    fired = []
    for second in range(0, 300):
        now = 5000.0 + second
        packets = [soop_chat("ㅇㅇ", f"viewer{second % 30}")] if second % 3 == 0 else []
        if 240 <= second < 252:
            packets += [soop_chat("ㅋㅋㅋㅋ 미쳤다", f"fan{second}_{i}") for i in range(8)]
        for raw in packets:
            detector.add(soop_live_message(raw, "streamer1"), now)
        fired += detector.advance(now)
    assert len(fired) == 1 and 5240 < fired[0].time <= 5260
