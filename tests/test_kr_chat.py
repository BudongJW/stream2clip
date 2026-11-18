"""CHZZK / SOOP replay chat: parsing real (anonymized) excerpts and collecting pages without the network."""

from __future__ import annotations

import json
import urllib.error
from pathlib import Path

import pytest

from stream2clip.chat import load_chat, parse_chzzk, parse_soop
from stream2clip.cli import main
from stream2clip.highlights import classify_reactions
from stream2clip.sources import chzzk_video_no, download_replay_chat, fetch_chzzk_chat, fetch_soop_chat, platform_of, soop_title_no

DATA = Path(__file__).parent / "data"
CHZZK = DATA / "chzzk_replay_excerpt.json"
SOOP = DATA / "soop_replay_excerpt.xml"


def test_fixtures_hold_nothing_personal():
    for path in (CHZZK, SOOP):
        raw = path.read_text(encoding="utf-8")
        assert "naver" not in raw and "sooplive" not in raw and "http://" not in raw
        assert raw.count("https://") == raw.count("https://example.invalid/")


def test_chzzk_excerpt():
    msgs = load_chat(CHZZK)  # detected from the "videoChats" pages
    assert len(msgs) == 23 and [m.kind for m in msgs].count("paid") == 3  # 24 in the file, one hidden by moderation
    assert [(m.amount, m.currency) for m in msgs if m.amount] == [(8000.0, "KRW"), (1230.0, "KRW"), (1000.0, "KRW")]
    assert msgs[0].time == pytest.approx(205.777) and msgs[-1].time == pytest.approx(6880.692)  # playerMessageTime, ms -> s
    assert all(len(m.author) == 12 for m in msgs if m.author) and len({m.author for m in msgs}) == 9
    emote = next(m for m in msgs if m.emotes)
    assert emote.emotes[0].startswith(":") and "{:" not in emote.text and emote.emotes[0] in emote.text
    assert "blinded" not in {m.text for m in msgs}
    assert any(classify_reactions(m.text, m.emotes) == {"laugh"} for m in msgs)  # ㅋㅋㅋ


def test_chzzk_single_page_and_odd_input():
    pages = json.loads(CHZZK.read_text(encoding="utf-8"))
    assert len(parse_chzzk(pages[0])) + len(parse_chzzk(pages[1])) == 23
    assert parse_chzzk({"content": {"videoChats": None}}) == [] and parse_chzzk([]) == []
    odd = {"videoChats": [{"playerMessageTime": 1500, "content": "hi", "extras": "not json", "messageTypeCode": 1}]}
    assert [(m.time, m.text, m.author) for m in parse_chzzk(odd)] == [(1.5, "hi", "")]


def test_soop_excerpt():
    msgs = load_chat(SOOP)  # detected from the XML
    kinds = {k: sum(1 for m in msgs if m.kind == k) for k in ("text", "paid", "sticker", "member")}
    assert kinds == {"text": 18, "paid": 3, "sticker": 1, "member": 1}
    assert [(m.amount, m.currency) for m in msgs if m.amount] == [(18.0, "별풍선"), (18.0, "별풍선"), (9.0, "애드벌룬")]
    assert msgs[0].time == pytest.approx(112.85) and msgs[-1].time == pytest.approx(8731.15)
    assert all(m.is_paid for m in msgs if m.kind == "paid")
    # a VOD in several files: the second file's chat starts where the first file ends
    shifted = parse_soop(SOOP.read_text(encoding="utf-8"), offset=3600)
    assert shifted[0].time == pytest.approx(3712.85)


def test_soop_same_viewer_on_two_devices_is_one_chatter():
    xml = "<root><chat><m>a</m><u>fan(2)</u><t>1.0</t></chat><chat><m>b</m><u>fan</u><t>2.0</t></chat><chat><m>c</m><u>other(1)</u><t>3.0</t></chat></root>"
    a, b, c = parse_soop(xml)
    assert a.author == b.author != c.author


def test_urls():
    assert platform_of("https://chzzk.naver.com/video/16230061") == "chzzk"
    assert platform_of("https://vod.sooplive.co.kr/player/212422389") == "soop"
    assert platform_of("https://www.youtube.com/watch?v=x") is None and platform_of("https://www.twitch.tv/videos/1") is None
    assert chzzk_video_no("https://chzzk.naver.com/video/16230061?t=30") == "16230061" and chzzk_video_no("16230061") == "16230061"
    assert soop_title_no("https://vod.sooplive.co.kr/player/212422389/catch") == "212422389" and soop_title_no(" 212422389 ") == "212422389"
    for bad, parse in (("https://chzzk.naver.com/live/abc", chzzk_video_no), ("https://www.sooplive.co.kr/station/x", soop_title_no)):
        with pytest.raises(ValueError):
            parse(bad)


def test_fetch_chzzk_follows_the_cursor():
    pages = json.loads(CHZZK.read_text(encoding="utf-8"))
    cursor = pages[0]["content"]["nextPlayerMessageTime"]
    asked = []

    def get(url, data=None):
        asked.append(url)
        return json.dumps(pages[0] if "playerMessageTime=0&" in url else pages[1]).encode()

    seen = []
    msgs = fetch_chzzk_chat("https://chzzk.naver.com/video/16230061", get=get, on_page=lambda n, t: seen.append(n))
    assert len(msgs) == 23 and seen == [1, 2] and [m.time for m in msgs] == sorted(m.time for m in msgs)
    assert asked[0].endswith("/v1/videos/16230061/chats?playerMessageTime=0&previousVideoChatSize=50") and f"playerMessageTime={cursor}&" in asked[1]

    with pytest.raises(RuntimeError, match="9004"):
        fetch_chzzk_chat("16230061", get=lambda url, data=None: json.dumps({"code": 9004, "message": "no"}).encode())


def test_fetch_soop_reads_every_piece_of_every_file():
    xml = SOOP.read_bytes()
    view = {"result": 1, "data": {"files": [
        {"chat": "https://chat.invalid/load?rowKey=A_c", "duration": 400_000},  # 400 s -> pieces 0, 300, 600
        {"chat": "https://chat.invalid/load?rowKey=B_c", "duration": 100_000},
    ]}}
    asked = []

    def get(url, data=None):
        asked.append((url, data))
        if data is not None:
            return json.dumps(view).encode()
        if "rowKey=A_c&startTime=0" in url:
            return xml
        if "rowKey=B_c&startTime=0" in url:
            return b"<root><chat><m>late</m><u>x</u><t>5.0</t></chat></root>"
        if "startTime=600" in url:
            raise urllib.error.HTTPError(url, 404, "Not Found", None, None)  # past the last piece
        return b"<root></root>"

    msgs = fetch_soop_chat("https://vod.sooplive.co.kr/player/212422389", get=get)
    assert b"nTitleNo=212422389" in asked[0][1]
    assert [u.rsplit("=", 1)[1] for u, d in asked[1:] if "A_c" in u] == ["0", "300", "600"]
    assert len(msgs) == 24  # 23 from the first file, 1 from the second
    late = next(m for m in msgs if m.text == "late")
    assert late.time == pytest.approx(405.0)  # 5 s into the second file, after 400 s of the first

    with pytest.raises(RuntimeError, match="not available"):
        fetch_soop_chat("212422389", get=lambda url, data=None: json.dumps({"result": -1, "data": {}}).encode())


def test_download_writes_normalized_jsonl_without_names(tmp_path):
    pages = json.loads(CHZZK.read_text(encoding="utf-8"))

    def get(url, data=None):
        return json.dumps(pages[0] if "playerMessageTime=0&" in url else pages[1]).encode()

    path = download_replay_chat("https://chzzk.naver.com/video/16230061", tmp_path, get=get)
    assert path == tmp_path / "chzzk_16230061.chat.jsonl"
    raw = path.read_text(encoding="utf-8")
    assert "viewer" not in raw and "user0" not in raw  # only hashed authors reach the disk
    again = load_chat(path)
    assert len(again) == 23 and sum(m.amount for m in again) == 10230.0 and [m.kind for m in again].count("paid") == 3

    with pytest.raises(ValueError):
        download_replay_chat("https://www.youtube.com/watch?v=x", tmp_path)
    with pytest.raises(RuntimeError, match="no chat"):
        download_replay_chat("https://chzzk.naver.com/video/1", tmp_path, get=lambda url, data=None: b'{"code": 200, "content": {"videoChats": []}}')


def test_cli_fetch_uses_the_replay_api_for_korean_platforms(tmp_path, monkeypatch, capsys):
    from stream2clip import sources

    pages = json.loads(CHZZK.read_text(encoding="utf-8"))
    monkeypatch.setattr(sources, "_http_get", lambda url, data=None: json.dumps(pages[0] if "playerMessageTime=0&" in url else pages[1]).encode())
    monkeypatch.setattr(sources, "fetch_info", lambda url, ytdlp=None, timeout=120: (_ for _ in ()).throw(RuntimeError("yt-dlp failed")))
    monkeypatch.setattr(sources, "ytdlp_command", lambda **kwargs: ["yt-dlp"])
    assert main(["fetch", "https://chzzk.naver.com/video/16230061", "-o", str(tmp_path)]) == 0
    out = capsys.readouterr()
    assert "chzzk_16230061.chat.jsonl" in out.out and "info   (skipped)" in out.err  # chat is still collected without yt-dlp
    assert main(["highlights", "--chat", str(tmp_path / "chzzk_16230061.chat.jsonl")]) == 0
    assert "analysed 23 chat messages" in capsys.readouterr().out
