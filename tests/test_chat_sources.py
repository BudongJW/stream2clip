from __future__ import annotations

from pathlib import Path

import pytest

from stream2clip.chat import load_chat, parse_amount, save_chat_jsonl
from stream2clip.sources import (
    build_chat_command,
    build_info_command,
    build_section_command,
    build_subs_command,
    heatmap_from_info,
    source_from_info,
)

from .conftest import needs_ffmpeg

DATA = Path(__file__).parent / "data"


@pytest.mark.parametrize(
    "text, expected",
    [("¥1,000", (1000.0, "¥")), ("₩5,000", (5000.0, "₩")), ("$4.99", (4.99, "$")), ("1.000,50 €", (1000.5, "€")), ("CA$2", (2.0, "CA$")), ("", (0.0, None))],
)
def test_parse_amount(text, expected):
    assert parse_amount(text) == expected


def test_youtube_live_chat():
    msgs = load_chat(DATA / "youtube.live_chat.json")
    assert [m.kind for m in msgs] == ["text", "paid", "member"]
    first = msgs[0]
    assert first.time == 12.5 and first.text.startswith("草") and ":_kusa:" in first.emotes
    assert first.author and first.author != "UC_alice"  # hashed
    assert msgs[1].amount == 1000 and msgs[1].currency == "¥" and msgs[1].is_paid


def test_real_youtube_excerpt():
    """48 lines cut from a real yt-dlp ``live_chat.json`` (authors, ids, images removed)."""
    path = DATA / "youtube_real_excerpt.live_chat.json"
    raw = path.read_text(encoding="utf-8")
    assert raw.count("\n") == 48 and "http" not in raw  # nothing left that points at a person
    msgs = load_chat(path)
    kinds = {k: sum(1 for m in msgs if m.kind == k) for k in ("text", "paid", "sticker", "member", "gift")}
    # 40 text lines in the file, 5 of them typed in the waiting room (offset 0); the
    # engagement notice, the ticker copy and the gift redemption are not chat messages.
    assert kinds == {"text": 35, "paid": 2, "sticker": 1, "member": 1, "gift": 1}
    assert msgs[0].time == pytest.approx(4.8, abs=0.1) and msgs[-1].time == pytest.approx(3361.5, abs=0.1)
    assert [(m.amount, m.currency) for m in msgs if m.amount] == [(200.0, "¥"), (190.0, "¥"), (15800.0, "¥")]
    assert all(len(m.author) == 12 and "viewer" not in m.author for m in msgs)
    emote = next(m for m in msgs if m.emotes)
    assert set(emote.emotes) == {":_にんじん:"} and ":_にんじん:" in emote.text  # custom emoji -> shortcut text
    assert any(m.text == "🥕🥕🥕" for m in msgs) and any(m.text == "たしかにw" for m in msgs)  # unicode emoji, split runs


def _yt_line(offset_ms, sent_at, text="hi"):
    import json

    item = {"liveChatTextMessageRenderer": {"message": {"runs": [{"text": text}]}, "authorExternalChannelId": f"UC{sent_at}", "timestampUsec": str(int(sent_at * 1e6))}}
    return json.dumps({"replayChatItemAction": {"actions": [{"addChatItemAction": {"item": item}}], "videoOffsetTimeMsec": str(offset_ms)}})


def test_waiting_room_chat_is_not_stacked_on_the_first_second(tmp_path):
    start = 1_700_000_000.0
    lines = [_yt_line(0, start - 25 + i, "waiting") for i in range(20)]  # typed before the stream: offset 0
    lines.append(_yt_line(0, start + 0.4, "first!"))  # really sent in the first second
    lines += [_yt_line(int(t * 1000), start + t) for t in (3, 8, 15, 21, 30, 44)]
    lines.append(_yt_line(0, start + 90_000, "after the stream"))  # also reported with offset 0
    path = tmp_path / "x.live_chat.json"
    path.write_text("\n".join(lines), encoding="utf-8")
    msgs = load_chat(path)
    assert [m.text for m in msgs if m.time == 0] == ["first!"]
    assert len(msgs) == 7

    # Too few timed messages to know when the stream started: keep everything.
    path.write_text("\n".join(lines[:20] + lines[21:24]), encoding="utf-8")
    assert len(load_chat(path)) == 23


def test_chat_downloader_sorted_and_clamped():
    msgs = load_chat(DATA / "chat_downloader.json")
    assert [m.time for m in msgs] == [0.0, 1.0, 3.5]
    assert msgs[1].kind == "paid" and msgs[1].amount == 5.0


def test_twitch_downloader():
    msgs = load_chat(DATA / "twitch.json")
    assert msgs[0].time == 4.0 and msgs[0].amount == 100 and msgs[0].currency == "bits"
    assert msgs[1].emotes == ("KEKW",)


def test_csv_and_jsonl_roundtrip(tmp_path):
    csv = tmp_path / "c.csv"
    csv.write_text('time,user,message,amount\n1:02,kim,ㅋㅋㅋ,\n00:01:05,lee,후원,"₩10,000"\n', encoding="utf-8")
    msgs = load_chat(csv)
    assert msgs[0].time == 62 and msgs[1].amount == 10000 and msgs[1].kind == "paid"
    out = save_chat_jsonl(msgs, tmp_path / "c.jsonl")
    again = load_chat(out)
    assert [(m.time, m.text, m.amount) for m in again] == [(m.time, m.text, m.amount) for m in msgs]


def test_ytdlp_builders():
    y = ["yt-dlp"]
    assert build_info_command("URL", ytdlp=y) == ["yt-dlp", "--dump-single-json", "--no-warnings", "--skip-download", "URL"]
    chat = build_chat_command("URL", "/out", ytdlp=y)
    assert "live_chat" in chat and chat[-1] == "URL"
    sec = build_section_command("URL", "v.mp4", start=3661.5, end=3700, ytdlp=y)
    assert sec[sec.index("--download-sections") + 1] == "*01:01:01.500-01:01:40.000"
    assert "--force-keyframes-at-cuts" in sec
    subs = build_subs_command("URL", "/o", "ja,ko", ytdlp=y)
    assert subs[subs.index("--sub-langs") + 1] == "ja,ko" and "--write-auto-subs" in subs and subs[subs.index("--sub-format") + 1] == "vtt"


def test_ytdlp_auth_args(monkeypatch):
    from stream2clip.sources import ytdlp_command

    monkeypatch.setenv("STREAM2CLIP_YTDLP", "yt-dlp")
    monkeypatch.setenv("STREAM2CLIP_YTDLP_ARGS", "--proxy socks5://x --limit-rate 5M")
    cmd = ytdlp_command(cookies="c.txt", cookies_from_browser="firefox")
    assert cmd == ["yt-dlp", "--cookies", "c.txt", "--cookies-from-browser", "firefox", "--proxy", "socks5://x", "--limit-rate", "5M"]


def test_info_parsing():
    info = {"title": "歌枠", "webpage_url": "https://youtu.be/x?si=1", "channel": "Ch", "duration": 100, "live_status": "was_live", "availability": "public",
            "heatmap": [{"start_time": 0, "end_time": 10, "value": 0.5}, {"start_time": 10, "end_time": 20}]}
    src = source_from_info(info)
    assert src.archive_public and not src.members_only
    assert src.timestamp_url(65.9) == "https://youtu.be/x?si=1&t=65"
    assert len(heatmap_from_info(info)) == 1
    assert source_from_info({"availability": "subscriber_only"}).members_only
    assert not source_from_info({"live_status": "is_live"}).archive_public


@needs_ffmpeg
def test_audio_levels(tmp_path):
    import subprocess

    from stream2clip.audio import audio_levels

    wav = tmp_path / "a.wav"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=f=440:d=6",
                    "-af", "volume='if(between(t,2,4),1,0.01)':eval=frame", str(wav)], check=True)
    levels = audio_levels(wav, window=1.0)
    assert len(levels) == 6
    assert levels[2] - levels[0] > 30 and abs(levels[0] - levels[5]) < 3
