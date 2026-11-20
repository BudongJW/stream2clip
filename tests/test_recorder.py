"""The session recorder and VTube Studio's API - without OBS, VTube Studio or a live chat."""

from __future__ import annotations

import json

import pytest

from stream2clip.chat import ChatMessage
from stream2clip.cli import main
from stream2clip.obs import ObsClient
from stream2clip.recorder import ChatPart, ObsPart, SessionRecorder, VtsPart
from stream2clip.session import SessionWriter, load_session
from stream2clip.vts import VtsClient, VtsError

# ----------------------------------------------------------------------------- VTube Studio


class FakeVts:
    """The server side of VTube Studio's API over an in-memory 'socket'."""

    def __init__(self, *, allow=True, token="tok-1", parameters=None, model="Kiri"):
        self.allow, self.token, self.model = allow, token, model
        self.parameters = parameters if parameters is not None else [{"name": "ParamMouthOpenY", "value": 0.7}, {"name": "ParamAngleX", "value": -12.5}, {"name": "Custom", "value": 3}]
        self.outbox: list[str] = []
        self.requests: list[str] = []
        self.subscribed: list[str] = []
        self.closed = False
        self.timeouts: list[float] = []

    def connect(self, url, timeout):
        self.url = url
        return self

    def _reply(self, request, message_type, data):
        self.outbox.append(json.dumps({"apiName": "VTubeStudioPublicAPI", "apiVersion": "1.0", "requestID": request["requestID"], "messageType": message_type, "data": data}))

    def event(self, message_type, data):
        self.outbox.append(json.dumps({"apiName": "VTubeStudioPublicAPI", "apiVersion": "1.0", "requestID": "", "messageType": message_type, "data": data}))

    def send(self, text):
        request = json.loads(text)
        kind, data = request["messageType"], request.get("data") or {}
        self.requests.append(kind)
        if kind == "AuthenticationTokenRequest":
            assert data["pluginName"] and data["pluginDeveloper"]
            if self.allow:
                self._reply(request, "AuthenticationTokenResponse", {"authenticationToken": self.token})
            else:
                self._reply(request, "APIError", {"errorID": 50, "message": "User has denied API access for your plugin."})
        elif kind == "AuthenticationRequest":
            ok = data.get("authenticationToken") == self.token
            self._reply(request, "AuthenticationResponse", {"authenticated": ok, "reason": "ok" if ok else "Token invalid"})
        elif kind == "EventSubscriptionRequest":
            self.subscribed.append(data["eventName"])
            self._reply(request, "EventSubscriptionResponse", {"subscribedEventCount": len(self.subscribed)})
        elif kind == "Live2DParameterListRequest":
            self._reply(request, "Live2DParameterListResponse", {"modelLoaded": bool(self.model), "modelName": self.model, "modelID": "id-1", "parameters": self.parameters if self.model else []})
        else:
            self._reply(request, "APIError", {"errorID": 2, "message": "unknown"})

    def settimeout(self, value):
        self.timeouts.append(value)

    def recv(self):
        if not self.outbox:
            raise TimeoutError("nothing to read")
        return self.outbox.pop(0)

    def close(self):
        self.closed = True


def test_the_first_connection_asks_for_a_token_and_keeps_it(tmp_path):
    vts = FakeVts()
    token = tmp_path / "token"
    client = VtsClient("ws://vts", token_file=token, connect=vts.connect)
    assert vts.requests == ["AuthenticationTokenRequest", "AuthenticationRequest"]
    assert token.read_text(encoding="utf-8") == "tok-1"
    client.close()
    again = FakeVts()
    VtsClient("ws://vts", token_file=token, connect=again.connect)
    assert again.requests == ["AuthenticationRequest"]  # no popup the second time
    revoked = FakeVts(token="tok-2")  # the user took the access away in VTube Studio, then allowed it again
    VtsClient("ws://vts", token_file=token, connect=revoked.connect)
    assert revoked.requests == ["AuthenticationRequest", "AuthenticationTokenRequest", "AuthenticationRequest"]
    assert token.read_text(encoding="utf-8") == "tok-2"


def test_a_denied_popup_is_explained(tmp_path):
    vts = FakeVts(allow=False)
    with pytest.raises(VtsError, match="denied") as info:
        VtsClient("ws://vts", token_file=tmp_path / "token", connect=vts.connect)
    assert info.value.code == 50 and vts.closed


def test_parameters_and_events(tmp_path):
    vts = FakeVts()
    client = VtsClient("ws://vts", token_file=tmp_path / "token", connect=vts.connect)
    model, values = client.parameters()
    assert model == {"name": "Kiri", "id": "id-1"} and values == {"ParamMouthOpenY": 0.7, "ParamAngleX": -12.5, "Custom": 3.0}
    vts.event("ModelOutlineEvent", {"convexHull": [{"x": 0, "y": 0}] * 3})
    vts.event("ModelLoadedEvent", {"modelLoaded": True})
    assert [e["messageType"] for e in client.poll()] == ["ModelOutlineEvent", "ModelLoadedEvent"]
    assert client.poll() == []
    vts.model = ""
    assert client.parameters() == ({"name": "", "id": "id-1"}, {})


# ----------------------------------------------------------------------------- OBS


class FakeObsServer:
    """Enough of obs-websocket 5 for the recorder: video settings, scenes, outputs, scene items, events."""

    def __init__(self, *, scene="Game", streaming=False, items=None):
        self.scene, self.streaming = scene, streaming
        self.items = items if items is not None else {("Game", "VTS"): (7, True, {"sourceWidth": 1920, "sourceHeight": 1080, "positionX": 960, "positionY": 0, "scaleX": 0.5, "scaleY": 1.0, "alignment": 5, "boundsType": "OBS_BOUNDS_NONE"})}
        self.outbox = [json.dumps({"op": 0, "d": {"obsStudioVersion": "31.0.0", "rpcVersion": 1}})]
        self.requests: list[str] = []
        self.identify = None
        self.closed = False
        self.drop = False

    def connect(self, url, timeout):
        return self

    def event(self, kind, data):
        self.outbox.append(json.dumps({"op": 5, "d": {"eventType": kind, "eventIntent": 1, "eventData": data}}))

    def send(self, text):
        message = json.loads(text)
        if message["op"] == 1:
            self.identify = message["d"]
            self.outbox.append(json.dumps({"op": 2, "d": {"negotiatedRpcVersion": 1}}))
            return
        d = message["d"]
        kind, data = d["requestType"], d.get("requestData") or {}
        self.requests.append(kind)
        ok, out = True, {}
        if kind == "GetVideoSettings":
            out = {"baseWidth": 1920, "baseHeight": 1080, "outputWidth": 1280, "outputHeight": 720, "fpsNumerator": 60, "fpsDenominator": 1}
        elif kind == "GetCurrentProgramScene":
            out = {"currentProgramSceneName": self.scene, "sceneName": self.scene}
        elif kind == "GetStreamStatus":
            out = {"outputActive": self.streaming}
        elif kind == "GetRecordStatus":
            out = {"outputActive": False}
        elif kind == "GetReplayBufferStatus":
            ok = False  # switched off in the settings
        elif kind in ("GetSceneItemId", "GetSceneItemEnabled", "GetSceneItemTransform"):
            found = self.items.get((data["sceneName"], data.get("sourceName", "VTS")))
            if found is None:
                ok = False
            elif kind == "GetSceneItemId":
                out = {"sceneItemId": found[0]}
            elif kind == "GetSceneItemEnabled":
                out = {"sceneItemEnabled": found[1]}
            else:
                out = {"sceneItemTransform": found[2]}
        elif kind == "SaveReplayBuffer":
            self.event("ReplayBufferSaved", {"savedReplayPath": "C:/replays/r1.mkv"})
        else:
            ok = False
        status = {"result": ok, "code": 100 if ok else 600}
        self.outbox.append(json.dumps({"op": 7, "d": {"requestType": kind, "requestId": d["requestId"], "requestStatus": status, "responseData": out}}))

    def settimeout(self, value):
        pass

    def recv(self):
        if self.drop:
            raise ConnectionResetError("gone")
        if not self.outbox:
            raise TimeoutError("nothing to read")
        return self.outbox.pop(0)

    def close(self):
        self.closed = True


def test_obs_poll_returns_what_has_arrived_without_waiting():
    obs = FakeObsServer()
    client = ObsClient(connect=obs.connect, events=1 | 4 | 64)
    assert obs.identify["eventSubscriptions"] == 69
    assert client.poll(0.5) == []
    obs.event("CurrentProgramSceneChanged", {"sceneName": "Talk"})
    obs.event("StreamStateChanged", {"outputActive": True, "outputState": "OBS_WEBSOCKET_OUTPUT_STARTED"})
    assert [e["eventType"] for e in client.poll()] == ["CurrentProgramSceneChanged", "StreamStateChanged"]


# ----------------------------------------------------------------------------- the recorder


class Clock:
    def __init__(self, now=1000.0):
        self.now = now

    def __call__(self):
        return self.now


class ListChat:
    """A chat source that hands out prepared messages, then raises once if asked to."""

    def __init__(self, batches):
        self.batches = list(batches)
        self.ended = False
        self.closed = False

    def read(self):
        return self.batches.pop(0) if self.batches else []

    def close(self):
        self.closed = True


def test_the_recorder_writes_obs_vts_chat_and_markers(tmp_path):
    clock = Clock()
    writer = SessionWriter(tmp_path / "s.jsonl", sources={"obs": "fake"}, clock=clock)
    obs, vts = FakeObsServer(), FakeVts()
    recorder = SessionRecorder(writer, [], save_replay_on_marker=True, clock=clock, sleep=lambda s: None)
    chat = ListChat([[ChatMessage(time=1000.5, text="hello", author="a")], [ChatMessage(time=1001.0, text="ㅋㅋ", author="b", kind="paid", amount=1000, currency="KRW")]])
    recorder.parts = [
        ChatPart(writer, lambda: chat),
        ObsPart(writer, lambda: ObsClient(connect=obs.connect, events=69), avatar_source="VTS"),
        VtsPart(writer, lambda: VtsClient("ws://vts", token_file=tmp_path / "token", connect=vts.connect), outline_every=0.5, parameters_every=0.2, marker_hotkeys=["Clip it"], on_marker=recorder.mark),
    ]
    recorder.step()
    vts.event("ModelOutlineEvent", {"modelName": "Kiri", "modelID": "id-1", "convexHull": [{"x": -0.5, "y": 0.8}, {"x": 0.5, "y": 0.8}, {"x": 0, "y": -1}], "windowSize": {"x": 1920, "y": 1080}})
    vts.event("ModelOutlineEvent", {"modelName": "Kiri", "modelID": "id-1", "convexHull": [{"x": -0.4, "y": 0.8}, {"x": 0.5, "y": 0.8}, {"x": 0, "y": -1}], "windowSize": {"x": 1920, "y": 1080}})
    obs.event("StreamStateChanged", {"outputActive": False, "outputState": "OBS_WEBSOCKET_OUTPUT_STARTING"})
    obs.event("StreamStateChanged", {"outputActive": True, "outputState": "OBS_WEBSOCKET_OUTPUT_STARTED"})
    clock.now = 1001.0
    recorder.step()
    recorder.mark("button")
    obs.event("CurrentProgramSceneChanged", {"sceneName": "Talk"})  # the VTS source is not in this scene
    vts.event("HotkeyTriggeredEvent", {"hotkeyName": "clip it", "hotkeyID": "h1"})
    vts.event("HotkeyTriggeredEvent", {"hotkeyName": "Wave"})
    clock.now = 1002.0
    recorder.step()
    recorder.step()  # the VTS hotkey marker asked for in the step before
    recorder.stop()
    recorder.run()
    assert chat.closed and obs.closed and vts.closed

    session = load_session(tmp_path / "s.jsonl")
    kinds = [e.type for e in session.events]
    assert kinds.count("chat") == 2 and kinds.count("avatar_outline") == 1 and kinds.count("marker") == 2
    assert [e.data["by"] for e in session.of("marker")] == ["button", "vts_hotkey"]
    assert session.of("marker")[1].data["label"] == "clip it"
    assert [e.data for e in session.of("output")] == [{"output": "stream", "active": False}, {"output": "record", "active": False}, {"output": "stream", "active": True}]
    assert session.origin() == 1001.0
    assert [e.data["name"] for e in session.of("scene")] == ["Game", "Talk"]
    placed = session.of("avatar_source")
    assert placed[0].data["transform"]["positionX"] == 960 and placed[-1].data == {"source": "VTS", "scene": "Talk", "transform": {}}
    params = session.of("avatar_params")
    assert params and set(params[0].data["values"]) == {"ParamMouthOpenY", "ParamAngleX"}  # the standard ones only
    assert session.of("avatar_model")[0].data == {"name": "Kiri", "id": "id-1"}
    assert [e.data["path"] for e in session.of("replay_saved")] == ["C:/replays/r1.mkv", "C:/replays/r1.mkv"]  # one per marker
    assert {e.data["source"] for e in session.of("status") if e.data["state"] == "connected"} == {"chat", "obs", "vts"}
    assert session.of("obs_video")[0].data == {"base": [1920, 1080], "output": [1280, 720]}


def test_a_part_that_cannot_connect_waits_and_tries_again(tmp_path):
    clock = Clock()
    writer = SessionWriter(tmp_path / "s.jsonl", clock=clock)
    attempts = []

    def connect():
        attempts.append(clock.now)
        if len(attempts) < 2:
            raise ConnectionRefusedError("VTube Studio is not running")
        return VtsClient("ws://vts", token_file=tmp_path / "token", connect=FakeVts().connect)

    part = VtsPart(writer, connect, parameters_every=0.0)
    part.poll(clock.now)
    assert part.status.state == "waiting" and "not running" in part.status.detail
    clock.now += 5
    part.poll(clock.now)  # too soon
    assert len(attempts) == 1
    clock.now += 6
    part.poll(clock.now)
    assert part.status.state == "connected" and len(attempts) == 2
    # a connection that drops is opened again after the wait
    part.client._ws.recv = lambda: (_ for _ in ()).throw(ConnectionResetError("gone"))
    part.poll(clock.now)
    assert part.status.state == "waiting"
    part.close()
    writer.close()
    states = [(e.data["source"], e.data["state"]) for e in load_session(tmp_path / "s.jsonl").of("status")]
    assert states[:3] == [("vts", "connecting"), ("vts", "waiting"), ("vts", "connecting")] and states[-1] == ("vts", "off")


def test_the_chat_part_writes_surges(tmp_path):
    from stream2clip.live import LiveConfig

    clock = Clock(10_000.0)
    writer = SessionWriter(tmp_path / "s.jsonl", clock=clock)
    batches = []
    for second in range(0, 400):  # quiet chat, then a burst
        n = 1 if second % 10 == 0 else 0
        if 300 <= second < 310:
            n = 6
        batches.append([ChatMessage(time=10_000.0 + second, text="ㅋㅋㅋ" if n > 1 else "hi", author=f"u{second}-{i}") for i in range(n)])
    chat = ListChat(batches)
    part = ChatPart(writer, lambda: chat, config=LiveConfig(warmup=60, history=300, min_messages=5, lag=1, cooldown=30))
    for _ in batches:
        clock.now += 1
        part.poll(clock.now)
    writer.close()
    session = load_session(tmp_path / "s.jsonl")
    assert len(session.of("chat")) == sum(len(b) for b in batches)
    surges = session.of("surge")
    assert surges and all(10_295 <= e.t <= 10_320 for e in surges) and surges[0].data["score"] > 0


# ----------------------------------------------------------------------------- the command line


def test_session_record_and_show_on_the_command_line(tmp_path, capsys):
    chat_file = tmp_path / "chat.jsonl"
    chat_file.write_text("", encoding="utf-8")
    out = tmp_path / "s.jsonl"
    assert main(["session", "record", "-o", str(out), "--chat", str(chat_file), "--no-obs", "--duration", "0.3"]) == 0
    text = capsys.readouterr().out
    assert "session" in text and "chat" in text and "done" in text
    session = load_session(out)
    assert session.sources["chat"] == str(chat_file)
    assert main(["session", "record", "-o", str(out), "--no-obs", "--chat", str(chat_file), "--duration", "0.1"]) == 1  # will not overwrite
    assert "exists already" in capsys.readouterr().err
    assert main(["session", "record", "-o", str(tmp_path / "none.jsonl"), "--no-obs"]) == 1
    assert "Nothing to record" in capsys.readouterr().err

    # what `show` prints for a session with a stream, scenes, a marker and a surge
    lines = [
        {"schema": "stream2clip.session/v1", "started": 1000.0, "app": "test", "sources": {"obs": "ws://x"}},
        {"t": 1010.0, "type": "output", "output": "stream", "active": True},
        {"t": 1010.0, "type": "scene", "name": "Opening"},
        {"t": 1310.0, "type": "scene", "name": "Game"},
        {"t": 1700.0, "type": "marker", "by": "hotkey"},
        {"t": 1800.0, "type": "surge", "score": 4.5, "reasons": ["chat x4"]},
        {"t": 1900.0, "type": "status", "source": "vts", "state": "waiting", "detail": "not running"},
    ]
    shown = tmp_path / "shown.jsonl"
    shown.write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")
    assert main(["session", "show", str(shown)]) == 0
    text = capsys.readouterr().out
    assert "0:00:00 - 0:05:00  Opening" in text and "0:05:00 - 0:14:50  Game" in text
    assert "0:11:30  marker  hotkey" in text and "0:13:10  surge 4.5  chat x4" in text
    assert "connection problems: 1" in text
    assert main(["session", "show", str(shown), "--offset", "10"]) == 0
    assert "0:11:20  marker" in capsys.readouterr().out


# ----------------------------------------------------------------------------- the OBS widget


def test_the_widget_shows_the_votes_and_markers(tmp_path):
    import urllib.error
    import urllib.request

    clock = Clock()
    writer = SessionWriter(tmp_path / "s.jsonl", clock=clock)
    chat = ListChat([[ChatMessage(time=1000.0, text="!clip", author="a"), ChatMessage(time=1001.0, text="!clip", author="b")]])
    recorder = SessionRecorder(writer, [ChatPart(writer, lambda: chat, viewer_votes=3)], clock=clock, sleep=lambda s: None)
    url = recorder.serve_widget(0)
    try:
        page = urllib.request.urlopen(url, timeout=5).read().decode("utf-8")
        assert "fetch(\"state\"" in page and "background:transparent" in page
        state = lambda: json.loads(urllib.request.urlopen(url.replace("/widget", "/state"), timeout=5).read())  # noqa: E731
        assert state() == {"votes": 0, "needed": 3, "markers": 0, "last_marker": 0.0}
        recorder.step()
        assert state()["votes"] == 2
        recorder.mark("button")
        recorder.step()
        assert state()["markers"] == 1 and state()["last_marker"] == 1000.0
        with pytest.raises(urllib.error.HTTPError) as missing:
            urllib.request.urlopen(url.replace("/widget", "/elsewhere"), timeout=5)
        assert missing.value.code == 404
    finally:
        recorder.stop()
        recorder.run()
    assert recorder.widget is None  # closed with the recorder
