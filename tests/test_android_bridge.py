"""The Android app's bridge to the core (``android/app/src/main/python/s2c_android.py``), run on the PC's Python."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from stream2clip.highlights import Highlight
from stream2clip.sources import SourceInfo

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).parent / "data"
CHZZK_URL = "https://chzzk.naver.com/video/16230061"


@pytest.fixture()
def bridge(monkeypatch):
    spec = importlib.util.spec_from_file_location("s2c_android", ROOT / "android" / "app" / "src" / "main" / "python" / "s2c_android.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv("STREAM2CLIP_LANG", "ko")
    return module


def test_the_stream_the_phone_cuts_from(bridge):
    info = {"formats": [
        {"url": "a", "vcodec": "avc1", "acodec": "none", "height": 1080},  # picture only: the phone needs both
        {"url": "b", "vcodec": "avc1", "acodec": "mp4a", "height": 480, "tbr": 900},
        {"url": "c", "vcodec": "avc1", "acodec": "mp4a", "height": 720, "tbr": 2500, "protocol": "m3u8_native", "http_headers": {"Referer": "https://chzzk.naver.com/"}},
        {"url": "d", "vcodec": "avc1", "acodec": "mp4a", "height": 1440},  # taller than asked
    ]}
    assert bridge.pick_stream(info) == {"url": "c", "height": 720, "protocol": "m3u8_native", "headers": {"Referer": "https://chzzk.naver.com/"}}
    assert bridge.pick_stream(info, max_height=480)["url"] == "b"
    assert bridge.pick_stream({"formats": [{"url": "a", "vcodec": "none", "acodec": "mp4a"}]}) is None and bridge.pick_stream({}) is None


def test_clip_text_is_what_the_desktop_writes(bridge):
    source = SourceInfo(url=CHZZK_URL, title="오늘은 명조 스토리", channel="버튜버 독케익", stream_date="20261117")
    clip = bridge.clip_text(Highlight(1, 1800.0, 1890.0, 1830.0, 9.5, ["채팅 급증"]), source, "ko")
    assert clip["title"] == "[독케익] 오늘은 명조 스토리" and clip["hashtags"] == ["#독케익", "#버튜버", "#치지직", "#키리누키"]
    assert clip["caption"] == "오늘은 명조 스토리"  # the words on the video: no [name] tag, the channel is in the corner
    long_title = SourceInfo(url=CHZZK_URL, title="방전, 오늘은 명조 스토리보고 내일 목사봤할께요오오 【명조】", channel="버튜버 김목사")
    long_clip = bridge.clip_text(Highlight(1, 0.0, 60.0, 30.0, 5.0), long_title, "ko")
    assert long_clip["title"].endswith("...") and long_clip["caption"] == "방전, 오늘은 명조 스토리보고 내일 목사봤할께요오오"  # not cut
    assert clip["link"] == CHZZK_URL + "?currentTime=1800"
    assert clip["description"].startswith("원본 방송\n2026년 11월 17일 방송\n") and "?currentTime=1800" in clip["description"]
    assert (clip["rank"], clip["start"], clip["end"], clip["reasons"]) == (1, 1800.0, 1890.0, ["채팅 급증"])
    # The stream's own language, not the phone's: an English phone still gets the Korean form for a Korean stream
    assert bridge.clip_text(Highlight(1, 1800.0, 1890.0, 1830.0, 9.5), source, "en")["title"] == "[독케익] 오늘은 명조 스토리"
    english = SourceInfo(url="https://www.youtube.com/watch?v=x", title="Minecraft hardcore day 3", channel="Pekora Ch.")
    assert bridge.clip_text(Highlight(1, 0.0, 60.0, 30.0, 5.0), english, "ko")["title"].startswith("Minecraft hardcore day 3")
    assert bridge.clip_text(Highlight(1, 0.0, 60.0, 30.0, 5.0), SourceInfo(url="https://x"), "ja")["hashtags"] == ["#切り抜き"]  # no title: the phone's


def test_analyse_a_chzzk_replay_from_its_chat(bridge, monkeypatch, tmp_path):
    from stream2clip import sources

    pages = json.loads((DATA / "chzzk_replay_excerpt.json").read_text(encoding="utf-8"))
    monkeypatch.setattr(sources, "_http_get", lambda url, data=None: json.dumps(pages[0] if "playerMessageTime=0&" in url else pages[1]).encode())
    info = {"webpage_url": CHZZK_URL, "title": "방송", "channel": "버튜버 독케익", "duration": 120.0, "categories": ["Gaming"], "game": "명조:워더링 웨이브",
            "formats": [{"url": "https://example.invalid/v.m3u8", "vcodec": "avc1", "acodec": "mp4a", "height": 720}]}
    monkeypatch.setattr(bridge, "video_info", lambda url: info)
    stages = []

    class Sink:
        def update(self, stage, fraction):
            stages.append(stage)

    found = json.loads(bridge.analyse(CHZZK_URL, str(tmp_path), "shorts", "ko", Sink()))
    assert found["source"]["platform"] == "chzzk" and found["source"]["game"] == "명조:워더링 웨이브" and found["source"]["category"] == "Gaming"
    assert found["messages"] == 23 and found["form"] == "shorts" and found["stream"]["url"].endswith("v.m3u8")
    assert stages[0] == "info" and "chat" in stages and stages[-1] == "detect"
    assert all(clip["title"].startswith("[독케익]") for clip in found["clips"])
    assert (tmp_path / "chzzk_16230061.chat.jsonl").is_file()  # the chat is kept, authors hashed, as on the desktop


def test_analyse_keeps_going_when_chzzk_refuses_the_info(bridge, monkeypatch, tmp_path):
    from stream2clip import sources

    pages = json.loads((DATA / "chzzk_replay_excerpt.json").read_text(encoding="utf-8"))
    monkeypatch.setattr(sources, "_http_get", lambda url, data=None: json.dumps(pages[0] if "playerMessageTime=0&" in url else pages[1]).encode())

    def refused(url):
        raise RuntimeError("login required")

    monkeypatch.setattr(bridge, "video_info", refused)
    found = json.loads(bridge.analyse(CHZZK_URL, str(tmp_path), "clip", "ko"))
    assert found["stream"] is None and "login required" in found["note"] and found["form"] == "clip" and found["messages"] == 23
    monkeypatch.setattr(bridge, "video_info", refused)
    with pytest.raises(RuntimeError):  # elsewhere the information is the way to the chat
        bridge.analyse("https://www.youtube.com/watch?v=abcdef12345", str(tmp_path / "yt"), "shorts", "ko")


def test_analyse_a_youtube_replay(bridge, monkeypatch, tmp_path):
    chat = tmp_path / "abc.live_chat.json"
    chat.write_bytes((DATA / "youtube_real_excerpt.live_chat.json").read_bytes())
    monkeypatch.setattr(bridge, "video_info", lambda url: {"webpage_url": url, "title": "【雑談】テスト", "channel": "Ch", "duration": 600.0,
                                                           "heatmap": [{"start_time": 0, "end_time": 10, "value": 0.5}]})
    monkeypatch.setattr(bridge, "_youtube_chat", lambda url, folder: chat)
    found = json.loads(bridge.analyse("https://www.youtube.com/watch?v=abcdef12345", str(tmp_path), "shorts", "ja"))
    assert found["source"]["platform"] == "" and found["messages"] > 0 and found["stream"] is None
    assert (tmp_path / "info.json").is_file()  # the most replayed parts count, as on the desktop
