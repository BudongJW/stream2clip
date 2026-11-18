"""OBS replay buffer (obs-websocket 5 protocol) and YouTube upload - without OBS and without Google."""

from __future__ import annotations

import base64
import hashlib
import json
import threading

import pytest

from stream2clip.cli import main
from stream2clip.ffmpeg import ExportOptions
from stream2clip.obs import ObsClient, ObsError, auth_string, replay_to_clip
from stream2clip.upload import shorts_problems, upload_video, video_resource, video_url

from .conftest import needs_ffmpeg

# ----------------------------------------------------------------------------- OBS


class FakeObs:
    """Speaks the server side of obs-websocket 5 over an in-memory 'socket'."""

    def __init__(self, *, password=None, active=True, replay="replay.mkv", send_event=True, last_path=True):
        self.password, self.active, self.replay, self.send_event, self.last_path = password, active, replay, send_event, last_path
        self.salt, self.challenge = "c2FsdA==", "Y2hhbGxlbmdl"
        hello = {"obsStudioVersion": "31.0.0", "obsWebSocketVersion": "5.5.4", "rpcVersion": 1}
        if password:
            hello["authentication"] = {"challenge": self.challenge, "salt": self.salt}
        self.outbox = [json.dumps({"op": 0, "d": hello})]
        self.requests, self.identify, self.closed = [], None, False

    def connect(self, url, timeout):
        self.url = url
        return self

    def send(self, text):
        message = json.loads(text)
        if message["op"] == 1:
            self.identify = message["d"]
            expected = auth_string(self.password, self.salt, self.challenge) if self.password else None
            if message["d"].get("authentication") == expected:
                self.outbox.append(json.dumps({"op": 2, "d": {"negotiatedRpcVersion": 1}}))
            else:
                self.outbox.append("")  # the real server closes the socket
        elif message["op"] == 6:
            d = message["d"]
            self.requests.append(d["requestType"])
            ok, data, comment = True, None, None
            if d["requestType"] == "GetReplayBufferStatus":
                data = {"outputActive": self.active}
            elif d["requestType"] == "StartReplayBuffer":
                self.active = True
            elif d["requestType"] == "SaveReplayBuffer":
                if self.send_event:  # the event may arrive before the response
                    self.outbox.append(json.dumps({"op": 5, "d": {"eventType": "ReplayBufferSaved", "eventIntent": 64, "eventData": {"savedReplayPath": self.replay}}}))
            elif d["requestType"] == "GetLastReplayBufferReplay":
                if self.last_path:
                    data = {"savedReplayPath": self.replay}
                else:
                    ok, comment = False, "No replay has been saved yet."
            else:
                ok, comment = False, "unknown request"
            status = {"result": ok, "code": 100 if ok else 600}
            if comment:
                status["comment"] = comment
            reply = {"requestType": d["requestType"], "requestId": d["requestId"], "requestStatus": status}
            if data is not None:
                reply["responseData"] = data
            self.outbox.append(json.dumps({"op": 7, "d": reply}))

    def recv(self):
        if not self.outbox:
            raise TimeoutError("nothing to read")
        return self.outbox.pop(0)

    def close(self):
        self.closed = True


def test_auth_string_matches_the_protocol_definition():
    secret = base64.b64encode(hashlib.sha256(b"supersecretpassword" + b"lM1GncleQOaCu9lT1yeUZhFYnqhsLLP1G5lAGo3ixaI=").digest())
    expected = base64.b64encode(hashlib.sha256(secret + b"+IxH4CnCiqpX1rM9scsNynZzbOe4KhDeYcTNS3PDaeY=").digest()).decode()
    assert auth_string("supersecretpassword", "lM1GncleQOaCu9lT1yeUZhFYnqhsLLP1G5lAGo3ixaI=", "+IxH4CnCiqpX1rM9scsNynZzbOe4KhDeYcTNS3PDaeY=") == expected
    assert len(expected) == 44


def test_identify_with_and_without_password():
    open_server = FakeObs()
    with ObsClient(connect=open_server.connect) as client:
        assert open_server.url == "ws://127.0.0.1:4455" and client.obs_version == "31.0.0"
        assert open_server.identify == {"rpcVersion": 1, "eventSubscriptions": 64}  # Outputs events: ReplayBufferSaved
    assert open_server.closed

    locked = FakeObs(password="hunter2")
    with ObsClient(password="hunter2", connect=locked.connect) as client:
        assert client.replay_buffer_active()
    with pytest.raises(ObsError, match="password"):
        ObsClient(connect=FakeObs(password="hunter2").connect)  # none given
    wrong = FakeObs(password="hunter2")
    with pytest.raises(ObsError, match="wrong password"):
        ObsClient(password="nope", connect=wrong.connect)
    assert wrong.closed


def test_save_replay_uses_the_event_or_asks_for_the_last_file(tmp_path):
    server = FakeObs(replay=str(tmp_path / "Replay 2026-11-19.mkv"))
    with ObsClient(connect=server.connect) as client:
        assert client.save_replay() == tmp_path / "Replay 2026-11-19.mkv"
    assert server.requests == ["GetReplayBufferStatus", "SaveReplayBuffer"]

    quiet = FakeObs(replay="D:/rec/r.mkv", send_event=False)  # no event arrives: fall back to GetLastReplayBufferReplay
    with ObsClient(connect=quiet.connect) as client:
        assert str(client.save_replay(wait=0.05)).replace("\\", "/") == "D:/rec/r.mkv"
    assert quiet.requests[-1] == "GetLastReplayBufferReplay"

    with ObsClient(connect=FakeObs(active=False).connect) as client:
        with pytest.raises(ObsError, match="not running"):
            client.save_replay()
    with ObsClient(connect=FakeObs(send_event=False, last_path=False).connect) as client:
        with pytest.raises(ObsError, match="No replay has been saved"):
            client.save_replay(wait=0.05)


@needs_ffmpeg
def test_replay_to_clip_keeps_the_last_seconds(green_screen_video, tmp_path):
    from stream2clip.export import probe

    server = FakeObs(replay=str(green_screen_video))  # the "replay" OBS saved: a 2 s video
    clip, replay = replay_to_clip(tmp_path / "moment.mp4", ExportOptions(format="mp4"), last=0.8, client=ObsClient(connect=server.connect), settle=0)
    assert replay == green_screen_video and clip.exists()
    assert probe(clip).duration == pytest.approx(0.8, abs=0.25)

    stopped = FakeObs(active=False)
    with pytest.raises(ObsError, match="started now"):
        replay_to_clip(tmp_path / "x.gif", client=ObsClient(connect=stopped.connect), start_buffer=True)
    assert "StartReplayBuffer" in stopped.requests


def test_over_a_real_websocket(tmp_path):
    """The same conversation through real sockets: websocket-client talking to a websockets server."""
    pytest.importorskip("websocket")
    serve = pytest.importorskip("websockets.sync.server").serve
    fake = FakeObs(password="pw", replay=str(tmp_path / "r.mkv"))

    def handler(connection):
        connection.send(fake.outbox.pop(0))
        for text in connection:
            fake.send(text)
            while fake.outbox:
                connection.send(fake.outbox.pop(0))

    with serve(handler, "127.0.0.1", 0) as server:
        port = server.socket.getsockname()[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()
        with ObsClient(port=port, password="pw", timeout=5) as client:
            assert client.replay_buffer_active() and client.save_replay() == tmp_path / "r.mkv"
        server.shutdown()


def test_cli_replay_reports_a_missing_obs(capsys):
    pytest.importorskip("websocket")
    assert main(["replay", "-o", "x.gif", "--port", "1"]) == 1  # nothing listens there
    assert "Cannot reach OBS" in capsys.readouterr().err


# ----------------------------------------------------------------------------- YouTube


def test_video_resource_defaults_to_private():
    body = video_resource("  레전드   장면  ", "원본: https://youtu.be/x", tags=["버튜버", " ", "clip"])
    assert body == {
        "snippet": {"title": "레전드 장면", "description": "원본: https://youtu.be/x", "categoryId": "20", "tags": ["버튜버", "clip"]},
        "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False},
    }
    public = video_resource("t", privacy="public", synthetic_media=True, language="ko", made_for_kids=True)
    assert public["status"] == {"privacyStatus": "public", "selfDeclaredMadeForKids": True, "containsSyntheticMedia": True}
    assert public["snippet"]["defaultLanguage"] == "ko"


def test_video_resource_rejects_what_youtube_rejects():
    for kwargs in ({"title": ""}, {"title": "x" * 101}, {"title": "a<b"}, {"title": "t", "description": "x>y"}, {"title": "t", "privacy": "hidden"}, {"title": "t", "description": "가" * 2000}):
        with pytest.raises(ValueError):
            video_resource(**kwargs)
    assert len(video_resource("x" * 100)["snippet"]["title"]) == 100


def test_shorts_tag_and_checks():
    assert video_resource("t", "desc", shorts=True)["snippet"]["description"] == "desc\n\n#Shorts"
    assert video_resource("t #shorts", "desc", shorts=True)["snippet"]["description"] == "desc"  # already there
    assert shorts_problems(1080, 1920, 59.0) == [] and shorts_problems(1080, 1080, 180.0) == []
    assert len(shorts_problems(1920, 1080, 200.0)) == 2


class FakeYouTube:
    def __init__(self, steps):
        self.steps, self.calls = list(steps), []

    def videos(self):
        return self

    def insert(self, **kwargs):
        self.calls.append(kwargs)
        return self

    def next_chunk(self):
        progress, response = self.steps.pop(0)
        status = None if progress is None else type("Status", (), {"progress": lambda self, p=progress: p})()
        return status, response


def test_upload_reports_progress_and_returns_the_video(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"0" * 10)
    service = FakeYouTube([(0.4, None), (0.8, None), (None, {"id": "abc123", "status": {"privacyStatus": "private"}})])
    body = video_resource("t")
    seen = []
    response = upload_video(video, body, service=service, media="MEDIA", on_progress=seen.append)
    assert response["id"] == "abc123" and video_url(response["id"]) == "https://www.youtube.com/watch?v=abc123"
    assert seen == [0.4, 0.8, 1.0]
    assert service.calls == [{"part": "snippet,status", "body": body, "media_body": "MEDIA"}]
    with pytest.raises(FileNotFoundError):
        upload_video(tmp_path / "missing.mp4", body, service=service, media="MEDIA")


@needs_ffmpeg
def test_cli_upload_dry_run_sends_nothing(green_screen_video, tmp_path, capsys):
    description = tmp_path / "clip_01.txt"
    description.write_text("【元配信 / 원본 방송】\nhttps://www.youtube.com/watch?v=x&t=10\n", encoding="utf-8")
    args = ["upload", str(green_screen_video), "--title", "레전드 장면", "--description-file", str(description), "--tags", "vtuber,clip", "--shorts", "--dry-run"]
    assert main(args) == 0
    out = capsys.readouterr()
    body = json.loads(out.out.split("dry run")[0])
    assert body["status"]["privacyStatus"] == "private" and body["snippet"]["tags"] == ["vtuber", "clip"]
    assert body["snippet"]["description"].endswith("#Shorts") and "가로 영상" in out.err  # 160x120 is not vertical

    assert main(["upload", str(green_screen_video), "--title", "t"]) == 1  # no client secrets, no dry run
    assert "--client-secrets" in capsys.readouterr().err
    assert main(["upload", str(green_screen_video), "--title", "t", "--client-secrets", str(tmp_path / "none.json")]) == 1
    assert capsys.readouterr().err.strip() != ""
