"""Live mode: surges in a chat that is still being written, and the replay clip they lead to."""

from __future__ import annotations

import json
import math
import subprocess
import sys
import time

import pytest

from stream2clip import obs
from stream2clip.chat import ChatMessage, live_messages, load_chat
from stream2clip.cli import main
from stream2clip.export import probe
from stream2clip.ffmpeg import ExportOptions
from stream2clip.live import FileFollower, LiveConfig, ReplayClipper, SurgeDetector, Trigger, YtDlpLiveChat, clip_span, simulate, watch
from stream2clip.obs import ObsClient, ObsError, replay_to_clip

from .conftest import needs_ffmpeg
from .test_obs_upload import FakeObs


def calm(start: float, end: float, *, every: float = 2.5, text: str = "なるほど") -> list[ChatMessage]:
    """An ordinary chat: one message every ``every`` seconds from a handful of people."""
    count = int((end - start) / every)
    return [ChatMessage(start + i * every, text, author=f"u{i % 7}") for i in range(count)]


def burst(at: float, count: int = 40, *, text: str = "草", length: float = 4.0) -> list[ChatMessage]:
    return [ChatMessage(at + i * length / count, text, author=f"r{i}") for i in range(count)]


def uneven(start: float, end: float) -> list[ChatMessage]:
    """A chat with its ordinary ups and downs: one to three messages per 5 s window."""
    counts = [1, 2, 3, 2, 1, 3, 2, 2]
    out: list[ChatMessage] = []
    for w in range(int(start // 5), int(end // 5)):
        out += [ChatMessage(w * 5 + 0.5 + i, "なるほど", author=f"u{w}_{i}") for i in range(counts[w % len(counts)])]
    return out


def crowd(at: float, count: int = 12) -> list[ChatMessage]:
    """More people talking, without any reaction words."""
    return [ChatMessage(at + i * 4.0 / count, "それな", author=f"c{at}_{i}") for i in range(count)]


QUICK = LiveConfig(smooth=1, warmup=60.0, cooldown=60.0)


# ----------------------------------------------------------------------------- the detector


def test_a_burst_fires_once_and_says_why():
    triggers = simulate([*calm(0, 600), *burst(300.5)], QUICK)
    assert [t.time for t in triggers] == [305.0]  # the end of the window the burst fell into
    t = triggers[0]
    assert t.score >= 10 and t.reasons[0].startswith("채팅 급증 504/분 (평소의 21.0배)") and t.reasons[1] == "반응 40개 (웃음 40)"
    assert t.stats["messages"] == 42 and t.stats["react_laugh"] == 40 and t.to_dict()["time"] == 305.0
    assert simulate(calm(0, 600), QUICK) == []  # nothing stands out in an even chat


def test_what_does_not_fire():
    assert simulate([*calm(0, 600), *burst(30.5)], QUICK) == []  # too early: nothing to compare with yet
    assert simulate([*calm(0, 600, every=30), *burst(310.5, 4)], QUICK) == []  # four messages are not a surge, however quiet it was
    assert len(simulate([*calm(0, 600, every=30), *burst(310.5, 5)], QUICK)) == 1
    hello = burst(300.5, text="こんばんは")  # everybody greets at once: routine, not a moment
    assert simulate([*calm(0, 600), *hello], QUICK) == []
    paid = [ChatMessage(300.5 + i * 0.1, "ナイス", author=f"p{i}", kind="paid", amount=500) for i in range(12)]
    fired = simulate([*calm(0, 600), *paid], QUICK)
    assert len(fired) == 1 and fired[0].reasons[-1] == "슈퍼챗·후원·멤버십 12건"


def test_cooldown_and_lasting_surges():
    chat = [*calm(0, 900), *burst(300.5), *burst(330.5), *burst(480.5)]
    assert [t.time for t in simulate(chat, QUICK)] == [305.0, 485.0]  # the second burst came within the cooldown
    assert [t.time for t in simulate(chat, LiveConfig(smooth=1, warmup=60.0, cooldown=20.0))] == [305.0, 335.0, 485.0]
    # By default the score is averaged over two windows: a modest surge has to last to fire
    # (a huge one, as above, still fires on its own).
    short = [*uneven(0, 600), *crowd(300.5)]
    lasting = [*uneven(0, 600), *crowd(300.5), *crowd(305.5)]
    default = LiveConfig(warmup=60.0)
    assert default.smooth == 2 and simulate(short, default) == []
    assert [t.time for t in simulate(short, LiveConfig(smooth=1, warmup=60.0))] == [305.0]
    assert [t.time for t in simulate(lasting, default)] == [310.0]
    with pytest.raises(ValueError):
        LiveConfig(window=0)
    with pytest.raises(ValueError):
        LiveConfig(smooth=0)


def test_windows_are_judged_only_when_complete():
    detector = SurgeDetector(LiveConfig(smooth=1, warmup=60.0, lag=12.0))
    for m in calm(1000, 1300):
        detector.add(m)
    for m in burst(1300.5):
        detector.add(m)
    assert detector.advance(1304.0) == []  # the window (1300-1305) is still open
    assert detector.advance(1310.0) == []  # closed, but chat for it may still arrive (lag)
    detector.add(ChatMessage(1303.0, "草", author="late"))
    fired = detector.advance(1317.0)
    assert [t.time for t in fired] == [1305.0] and fired[0].stats["messages"] == 41 and detector.triggers == fired
    detector.add(ChatMessage(1301.0, "草", author="too late"))  # that window has been judged
    assert detector.late == 1 and detector.advance(1400.0) == []
    assert detector.seen() == 385.0 and detector.messages == 161  # 1000 to 1385: what can no longer change at 1400

    # A later message completes the windows before it without waiting for the lag.
    quick = SurgeDetector(LiveConfig(smooth=1, warmup=60.0))
    for m in [*calm(0, 300), *burst(300.5), ChatMessage(306.0, "次")]:
        quick.add(m)
    assert [t.time for t in quick.advance(306.0)] == [305.0]


def test_messages_without_a_time_count_as_now_and_the_backlog_only_builds_history():
    detector = SurgeDetector(LiveConfig(smooth=1, warmup=60.0, lag=1.0), live_from=5000.0)
    for m in [*calm(4000, 5000), *burst(4500.5)]:  # delivered at the start: happened before we were watching
        detector.add(m)
    assert detector.advance(5000.0) == [] and detector.seen() == 900.0
    for i in range(30):
        detector.add(ChatMessage(math.nan, "草", author=f"n{i}"), now=5007.0)
    detector.add(ChatMessage(math.nan, "no clock"))  # nowhere to put it
    assert [t.time for t in detector.advance(5012.0)] == [5010.0]

    # After a gap longer than the history the old "normal" says nothing about now.
    detector.add(ChatMessage(50000.0, "おかえり", author="a"))
    assert detector.advance(50010.0) == [] and detector.seen() <= 10.0


def test_where_the_moment_is_in_the_replay():
    cfg = LiveConfig()
    # window ended at 1000, saved 20 s later: the moment (8 s before the surge) plus 20 s lead, 10 s tail
    keep, drop = clip_span(1000.0, 1020.0, cfg)
    assert keep == 20 + 5 + 8 + 20 and drop == 20 + 8 - 10
    assert clip_span(1000.0, 1001.0, cfg) == (34.0, 0.0)  # saved before the tail is over: nothing to drop
    assert clip_span(1000.0, 900.0, cfg)[0] == 1.0  # clocks that disagree never give a negative length


# ----------------------------------------------------------------------------- reading the chat


def youtube_line(text: str, stamp: float, *, author: str = "UC123", renderer: str = "liveChatTextMessageRenderer", **extra) -> str:
    """One line as yt-dlp writes it for a chat that is live (the offset is outside the action there)."""
    item = {renderer: {"message": {"runs": [{"text": text}]}, "authorExternalChannelId": author, "timestampUsec": str(int(stamp * 1e6)), **extra}}
    return json.dumps({"replayChatItemAction": {"actions": [{"clickTrackingParams": "x", "addChatItemAction": {"item": item, "clientId": "c"}}]}, "videoOffsetTimeMsec": "4222", "isLive": True}, ensure_ascii=False)


def test_lines_of_a_live_chat():
    (msg,) = live_messages(youtube_line("草www", 1795058477.25))
    assert msg.time == pytest.approx(1795058477.25) and msg.text == "草www" and msg.kind == "text" and len(msg.author) == 12 and "UC123" not in msg.author
    (paid,) = live_messages(youtube_line("ナイス", 1795058480.0, renderer="liveChatPaidMessageRenderer", purchaseAmountText={"simpleText": "¥500"}))
    assert paid.kind == "paid" and paid.amount == 500
    assert live_messages(json.dumps({"replayChatItemAction": {"actions": [{"removeChatItemAction": {}}]}, "isLive": True})) == []

    (plain,) = live_messages('{"text": "ㅋㅋㅋㅋ", "author": "a"}')
    assert math.isnan(plain.time) and plain.text == "ㅋㅋㅋㅋ"
    assert live_messages('{"timestamp": 1795058500123, "message": "hi", "user": "b"}')[0].time == pytest.approx(1795058500.123)  # milliseconds
    assert live_messages('{"time": 1795058500.5, "text": "gg", "amount": "₩5,000"}')[0].kind == "paid"
    assert live_messages("not json") == [] and live_messages("[1, 2]") == [] and live_messages('{"author": "nothing said"}') == []


def test_a_chat_recorded_live_can_be_read_afterwards(tmp_path):
    path = tmp_path / "live.live_chat.json"
    path.write_text("\n".join(youtube_line(f"m{i}", 1795058000.0 + i * 30) for i in range(5)), encoding="utf-8")
    messages = load_chat(path)
    assert [m.time for m in messages] == [0.0, 30.0, 60.0, 90.0, 120.0]  # no video offsets in such a file: counted from its first message


def test_following_a_file(tmp_path):
    path = tmp_path / "chat.jsonl"
    follower = FileFollower(path)
    assert follower.read() == []  # not there yet
    path.write_text('{"time": 100, "text": "old"}\n{"text": "old, no time"}\n{"time": 101, "te', encoding="utf-8")
    assert [m.text for m in follower.read()] == ["old"]  # backlog without a time is dropped; the half line waits
    assert follower.read() == []
    with path.open("a", encoding="utf-8") as fh:
        fh.write('xt": "split"}\n\n{"text": "now"}\nnot json\n')
    got = follower.read()
    assert [m.text for m in got] == ["split", "now"] and math.isnan(got[1].time)
    path.write_text('{"text": "new file"}\n', encoding="utf-8")  # replaced by the collector
    assert [m.text for m in follower.read()] == ["new file"]
    follower.close()
    assert follower.ended


class FakeProcess:
    def __init__(self, command, **kwargs):
        self.command, self.kwargs, self.code, self.terminated = command, kwargs, None, False

    def poll(self):
        return self.code

    def terminate(self):
        self.terminated, self.code = True, 1

    def wait(self, timeout=None):
        return self.code


def test_yt_dlp_records_and_we_follow(tmp_path):
    started = []

    def popen(command, **kwargs):
        started.append(FakeProcess(command, **kwargs))
        return started[-1]

    (tmp_path / "live.live_chat.json.part").write_text("stale", encoding="utf-8")  # from an earlier run
    source = YtDlpLiveChat("https://www.youtube.com/watch?v=abc", tmp_path, ytdlp=["yt-dlp"], popen=popen)
    command = started[0].command
    assert command[0] == "yt-dlp" and command[-1].endswith("v=abc") and "--skip-download" in command and command[command.index("--sub-langs") + 1] == "live_chat"
    assert command[command.index("-o") + 1] == str(tmp_path / "live.%(ext)s")
    assert source.read() == [] and not source.ended
    (tmp_path / "live.live_chat.json.part").write_text(youtube_line("草", 1795058477.0) + "\n", encoding="utf-8")
    assert [m.text for m in source.read()] == ["草"]
    started[0].code = 0  # the stream ended
    assert source.read() == [] and source.ended
    source.close()

    # yt-dlp that never reaches the chat is an error with its last words, not a silent wait.
    def failing(command, **kwargs):
        kwargs["stdout"].write("ERROR: [youtube] abc: This live stream recording is not available.\n")
        kwargs["stdout"].flush()
        process = FakeProcess(command, **kwargs)
        process.code = 1
        return process

    broken = YtDlpLiveChat("https://www.youtube.com/watch?v=abc", tmp_path / "b", ytdlp=["yt-dlp"], popen=failing)
    with pytest.raises(RuntimeError, match="not available"):
        broken.read()
    broken.close()

    running = YtDlpLiveChat("https://www.youtube.com/watch?v=abc", tmp_path / "c", ytdlp=["yt-dlp"], popen=popen)
    running.close()
    assert started[-1].terminated


# ----------------------------------------------------------------------------- the loop


class ScriptedSource:
    """Hands out messages once the (fake) clock has reached their time."""

    def __init__(self, messages, clock, *, ends_at=None):
        self.messages, self.clock, self.ends_at, self.ended, self.closed = sorted(messages, key=lambda m: m.time), clock, ends_at, False, False

    def read(self):
        now = self.clock()
        ready = [m for m in self.messages if m.time <= now]
        self.messages = self.messages[len(ready):]
        if self.ends_at is not None and now >= self.ends_at:
            self.ended = True
        return ready

    def close(self):
        self.closed = True


def test_the_loop_acts_when_the_moment_has_played_out():
    now = [1000.0]
    acted = []

    def sleep(seconds):
        now[0] += seconds

    cfg = LiveConfig(smooth=1, warmup=60.0, lag=2.0, chat_delay=8.0, tail=10.0)
    source = ScriptedSource([*calm(1000, 1700), *burst(1300.5), *burst(1500.5)], lambda: now[0], ends_at=1600.0)
    detector = SurgeDetector(cfg)
    count = watch(source, detector, lambda t: acted.append((t.time, now[0])), clock=lambda: now[0], sleep=sleep, poll=1.0)
    # judged at window end + lag = 1307; the surge may play out until 1305 - 8 + 10 = 1307
    assert count == 2 and acted == [(1305.0, 1307.0), (1505.0, 1507.0)] and now[0] == 1600.0

    now[0] = 1000.0
    source = ScriptedSource([*calm(1000, 1700), *burst(1300.5), *burst(1500.5)], lambda: now[0])
    assert watch(source, SurgeDetector(cfg), acted.append, clock=lambda: now[0], sleep=sleep, max_triggers=1) == 1 and now[0] == 1307.0
    now[0] = 1000.0
    source = ScriptedSource(calm(1000, 1700), lambda: now[0])
    assert watch(source, SurgeDetector(cfg), acted.append, clock=lambda: now[0], sleep=sleep, until=1100.0) == 0 and now[0] == 1100.0
    stops = iter([False, False, True])
    assert watch(ScriptedSource([], lambda: now[0]), SurgeDetector(cfg), acted.append, clock=lambda: now[0], sleep=sleep, should_stop=lambda: next(stops)) == 0


# ----------------------------------------------------------------------------- the clip


@pytest.fixture
def replay_file(tmp_path):
    """A 60 s "replay buffer" file (test pattern with sound)."""
    path = tmp_path / "Replay 2026-11-19 12-00-00.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=160x90:r=10:d=60", "-f", "lavfi", "-i", "sine=frequency=440:duration=60",
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path)], check=True)
    return path


@needs_ffmpeg
def test_replay_can_be_trimmed_at_both_ends(replay_file, tmp_path):
    fake = FakeObs(replay=str(replay_file))
    clip, _ = replay_to_clip(tmp_path / "a.mp4", ExportOptions(format="mp4"), last=30.0, trim_end=10.0, client=ObsClient(connect=fake.connect), settle=0)
    assert probe(clip).duration == pytest.approx(20.0, abs=0.5)
    fake = FakeObs(replay=str(replay_file))
    clip, _ = replay_to_clip(tmp_path / "b.mp4", ExportOptions(format="mp4"), last=5.0, trim_end=59.5, client=ObsClient(connect=fake.connect), settle=0)
    assert probe(clip).duration == pytest.approx(5.0, abs=0.5)  # a trim that would leave nothing is ignored


@needs_ffmpeg
def test_a_trigger_becomes_a_clip(replay_file, tmp_path, monkeypatch):
    monkeypatch.setattr(obs.time, "sleep", lambda seconds: None)
    fakes = []

    def connect():
        fakes.append(FakeObs(replay=str(replay_file)))
        return ObsClient(connect=fakes[-1].connect)

    when = time.mktime((2026, 11, 19, 21, 30, 5, 0, 0, -1))
    clipper = ReplayClipper(tmp_path / "out", connect, options=ExportOptions(format="mp4", fps=10), clock=lambda: when + 12.0)
    assert clipper.check() == "31.0.0" and fakes[0].closed
    saved = clipper(Trigger(when, 4.2, ["채팅 급증"]))
    assert saved.clip == tmp_path / "out" / "live_20261119_213005.mp4" and saved.replay == replay_file and saved.note == ""
    assert probe(saved.clip).duration == pytest.approx(20 + 5 + 10, abs=0.6)  # lead + window + tail around the moment (keep 45 s, drop the last 10)
    assert fakes[1].closed and "SaveReplayBuffer" in fakes[1].requests and clipper.saved == [saved]

    # OBS's default buffer (20 s here: the last part of the file) is shorter than the clip that is wanted.
    short = tmp_path / "short.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-sseof", "-20", "-i", str(replay_file), "-c", "copy", str(short)], check=True)
    clipper = ReplayClipper(tmp_path / "out2", lambda: ObsClient(connect=FakeObs(replay=str(short)).connect), clock=lambda: when + 12.0)
    assert "Maximum Replay Time" in clipper(Trigger(when, 4.2)).note

    stopped = ReplayClipper(tmp_path / "out3", lambda: ObsClient(connect=FakeObs(active=False).connect))
    with pytest.raises(ObsError, match="--start-buffer"):
        stopped.check()
    asks = ReplayClipper(tmp_path / "out3", lambda: ObsClient(connect=FakeObs(active=False, starts=False).connect))
    with pytest.raises(ObsError, match="did not start"):
        asks.check(start_buffer=True)
    assert ReplayClipper(tmp_path / "out3", lambda: ObsClient(connect=FakeObs(active=False).connect)).check(start_buffer=True) == "31.0.0"


# ----------------------------------------------------------------------------- command line


def test_cli_simulate(tmp_path, capsys):
    chat = tmp_path / "chat.csv"
    rows = ["time,author,text"] + [f"{m.time},{m.author},{m.text}" for m in [*calm(0, 900), *burst(300.5, 80, length=9.0)]]
    chat.write_text("\n".join(rows), encoding="utf-8")
    assert main(["live", str(chat), "--simulate"]) == 0
    out = capsys.readouterr().out
    assert "0:05:05  score" in out and "채팅 급증" in out and "1 triggers in 440 messages" in out
    assert main(["live", str(chat), "--simulate", "--threshold", "50"]) == 0
    assert "0 triggers" in capsys.readouterr().out
    assert main(["live", "https://www.youtube.com/watch?v=abc", "--simulate"]) == 1
    assert "fetch the replay first" in capsys.readouterr().err


@needs_ffmpeg
def test_cli_live_follows_a_file_and_saves_clips(replay_file, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(obs.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(obs, "_default_connect", lambda url, timeout: FakeObs(replay=str(replay_file)).connect(url, timeout))
    chat = tmp_path / "chat.jsonl"

    def collect() -> None:
        """What a collector has written: minutes of ordinary chat and a surge in the window that begins next."""
        start = (time.time() // 5 + 1) * 5
        lines = [json.dumps({"time": m.time, "text": m.text, "author": m.author}, ensure_ascii=False) for m in [*calm(start - 400, start + 20), *burst(start + 0.5, 60)]]
        chat.write_text("\n".join(lines) + "\n", encoding="utf-8")

    collect()
    out = tmp_path / "live"
    args = ["live", str(chat), "-o", str(out), "--smooth", "1", "--lag", "0", "--tail", "0", "--delay", "0", "--lead", "3", "--max-clips", "1", "--duration", "30", "--fps", "10"]
    assert main(args) == 0
    printed = capsys.readouterr()
    assert "obs    OBS 31.0.0, replay buffer running" in printed.out and "surge" in printed.out and "done   1 surges" in printed.out
    (clip,) = out.glob("live_*.mp4")
    assert 1.0 <= (probe(clip).duration or 0) <= 30.0
    (entry,) = [json.loads(line) for line in (out / "live.jsonl").read_text(encoding="utf-8").splitlines()]
    assert entry["clip"] == str(clip) and entry["reasons"][0].startswith("채팅 급증") and entry["score"] >= 3.5 and entry["at"].startswith("20")

    # OBS that is not there is said before the wait starts; with --no-obs it is never asked.
    def refuse(url, timeout):
        raise ObsError(f"Cannot reach OBS at {url}.")

    monkeypatch.setattr(obs, "_default_connect", refuse)
    assert main(args) == 1
    assert "Cannot reach OBS" in capsys.readouterr().err
    assert main(["live", str(chat), "-o", str(tmp_path / "dry"), "--no-obs", "--duration", "1"]) == 0
    printed = capsys.readouterr()
    assert "obs  " not in printed.out and "done   0 surges in" in printed.out and not list((tmp_path / "dry").glob("*.mp4"))


def test_live_needs_only_the_core():
    code = "import sys, stream2clip.live; assert 'PySide6' not in sys.modules and 'websocket' not in sys.modules and 'yt_dlp' not in sys.modules"
    assert subprocess.run([sys.executable, "-c", code], capture_output=True, text=True).returncode == 0
