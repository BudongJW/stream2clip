"""Clip edges on spoken lines, markers left by the streamer, the pip layout, an avatar video, Twitch chat."""

from __future__ import annotations

import json
import math
import random
import subprocess

import numpy as np
import pytest

from stream2clip.chat import ChatMessage, load_chat, parse_chzzk, role_of, save_chat_jsonl
from stream2clip.cli import main
from stream2clip.export import export, grab_frames, probe
from stream2clip.ffmpeg import ExportOptions, RawVideoInput, build_export_command, build_video_filter
from stream2clip.geometry import Region
from stream2clip.highlights import Highlight, HighlightConfig, detect_highlights, marker_times, snap_to_cues
from stream2clip.layouts import LAYOUTS, VerticalLayout
from stream2clip.live import FileFollower, LiveConfig, SurgeDetector, TwitchLiveChat, open_chat, parse_twitch_irc, twitch_channel
from stream2clip.pipeline import make_clips
from stream2clip.subtitles import Cue, Word

from .conftest import needs_ffmpeg

# --------------------------------------------------------------------------- clip edges on spoken lines


def spans(*pairs):
    return [Cue(start, end, "line") for start, end in pairs]


def test_edges_inside_a_line_move_to_keep_the_whole_line():
    h = Highlight(1, 101.0, 131.0, 115.0, 3.0)
    moved = snap_to_cues([h], spans((99.5, 102.5), (110.0, 112.0), (129.0, 132.5)))
    assert moved == 1
    assert h.start == pytest.approx(99.35) and h.end == pytest.approx(132.65)  # a breath of silence before and after
    assert h.start <= h.peak <= h.end


def test_an_edge_between_lines_stays_where_it_is():
    h = Highlight(1, 100.0, 130.0, 115.0, 3.0)
    assert snap_to_cues([h], spans((90.0, 99.0), (101.0, 129.0), (131.0, 140.0))) == 0
    assert (h.start, h.end) == (100.0, 130.0)
    assert snap_to_cues([h], []) == 0


def test_a_far_line_start_is_not_chased():
    # The line began 8 s before the clip: going back is too far, its end is 1 s ahead.
    h = Highlight(1, 100.0, 130.0, 115.0, 3.0)
    snap_to_cues([h], spans((92.0, 101.0)), max_shift=3.0)
    assert h.start == pytest.approx(101.15)
    # Neither way is near enough: the edge is left alone.
    h = Highlight(1, 100.0, 130.0, 115.0, 3.0)
    assert snap_to_cues([h], spans((92.0, 108.0)), max_shift=3.0) == 0 and h.start == 100.0
    # The same for the end: forward first, back if that is too far.
    h = Highlight(1, 100.0, 130.0, 115.0, 3.0)
    snap_to_cues([h], spans((129.0, 137.0)), max_shift=3.0)
    assert h.end == pytest.approx(128.85)


def test_back_to_back_lines_are_not_cut_into_and_the_stream_end_is_kept():
    h = Highlight(1, 101.0, 119.0, 110.0, 3.0)
    snap_to_cues([h], spans((98.0, 100.0), (100.0, 103.0), (117.0, 120.5), (120.5, 122.0)), duration=120.0)
    assert h.start == 100.0  # not 99.85: that would be inside the line before
    assert h.end == 120.0  # the line ends at 120.5, the stream at 120


@needs_ffmpeg
def test_clips_command_snaps_before_cutting(green_screen_video, tmp_path, capsys):
    highlights = tmp_path / "h.json"
    highlights.write_text(json.dumps({"highlights": [{"rank": 1, "start": 0.5, "end": 1.4, "score": 3}]}), encoding="utf-8")
    subs = tmp_path / "subs.srt"
    subs.write_text("1\n00:00:00,200 --> 00:00:00,900\nhello\n\n2\n00:00:01,200 --> 00:00:01,700\nworld\n", encoding="utf-8")
    common = ["clips", str(green_screen_video), "--highlights", str(highlights), "--subtitles", str(subs), "--layout", "none", "--fps", "10"]
    assert main([*common, "-o", str(tmp_path / "snapped")]) == 0
    assert "snap   1 of 1 clips" in capsys.readouterr().out
    clip = json.loads((tmp_path / "snapped" / "clips.json").read_text(encoding="utf-8"))["clips"][0]
    assert clip["start"] == pytest.approx(0.05) and clip["end"] == pytest.approx(1.85)
    assert main([*common, "--snap", "0", "-o", str(tmp_path / "plain")]) == 0
    assert "snap   " not in capsys.readouterr().out
    clip = json.loads((tmp_path / "plain" / "clips.json").read_text(encoding="utf-8"))["clips"][0]
    assert (clip["start"], clip["end"]) == (0.5, 1.4)


# --------------------------------------------------------------------------- markers left by the streamer


def test_roles_are_read_from_each_chat_format(tmp_path):
    assert role_of("OWNER") == "owner" and role_of("VERIFIED", "MODERATOR") == "moderator" and role_of("subscriber", None) == ""
    assert role_of("moderator", "broadcaster") == "owner"  # the streamer is also a moderator of their own chat

    def youtube(badge, text, offset):
        renderer = {"message": {"runs": [{"text": text}]}, "authorExternalChannelId": f"UC{offset}", "timestampUsec": "1700000000000000"}
        if badge:
            renderer["authorBadges"] = [{"liveChatAuthorBadgeRenderer": {"icon": {"iconType": badge}}}]
        action = {"addChatItemAction": {"item": {"liveChatTextMessageRenderer": renderer}}}
        return json.dumps({"replayChatItemAction": {"actions": [action], "videoOffsetTimeMsec": str(offset)}})

    path = tmp_path / "v.live_chat.json"
    path.write_text("\n".join([youtube("OWNER", "!clip", 5000), youtube("MODERATOR", "hi", 6000), youtube(None, "!clip", 7000)]), encoding="utf-8")
    assert [m.role for m in load_chat(path)] == ["owner", "moderator", ""]

    downloader = tmp_path / "cd.json"
    downloader.write_text(json.dumps([
        {"time_in_seconds": 1, "message": "a", "author": {"id": "1", "badges": [{"title": "Owner"}]}},
        {"time_in_seconds": 2, "message": "b", "author": {"id": "2", "badges": [{"name": "moderator", "title": "Moderator"}]}},
        {"time_in_seconds": 3, "message": "c", "author": {"id": "3", "badges": [{"title": "Member (6 months)"}]}},
    ]), encoding="utf-8")
    assert [m.role for m in load_chat(downloader, format="chat-downloader")] == ["owner", "moderator", ""]

    twitch = tmp_path / "tw.json"
    twitch.write_text(json.dumps({"comments": [
        {"content_offset_seconds": 1, "commenter": {"_id": "1"}, "message": {"body": "!clip", "user_badges": [{"_id": "broadcaster", "version": "1"}]}},
        {"content_offset_seconds": 2, "commenter": {"_id": "2"}, "message": {"body": "x", "user_badges": [{"_id": "subscriber", "version": "3"}]}},
    ]}), encoding="utf-8")
    assert [m.role for m in load_chat(twitch, format="twitch")] == ["owner", ""]

    page = {"content": {"videoChats": [
        {"playerMessageTime": 1000, "content": "!클립", "userIdHash": "a", "profile": json.dumps({"userRoleCode": "streamer"})},
        {"playerMessageTime": 2000, "content": "x", "userIdHash": "b", "profile": json.dumps({"userRoleCode": "streaming_chat_manager"})},
        {"playerMessageTime": 3000, "content": "y", "userIdHash": "c", "profile": json.dumps({"userRoleCode": "common_user"})},
        {"playerMessageTime": 4000, "content": "z", "userIdHash": "d", "profile": None},
    ]}}
    messages = parse_chzzk(page)
    assert [m.role for m in messages] == ["owner", "moderator", "", ""]

    saved = save_chat_jsonl(messages, tmp_path / "chzzk_1.chat.jsonl")
    lines = [json.loads(line) for line in saved.read_text(encoding="utf-8").splitlines()]
    assert lines[0]["role"] == "owner" and "role" not in lines[2]
    assert [m.role for m in load_chat(saved)] == ["owner", "moderator", "", ""]


def quiet_chat(duration=1800, seed=1):
    rng = random.Random(seed)
    messages, t = [], 0.0
    while t < duration:
        t += rng.expovariate(0.5)
        messages.append(ChatMessage(t, "なるほど", f"u{rng.randrange(200)}"))
    return messages


def marked(result):
    return [h for h in result.highlights if h.stats.get("marker")]


def test_a_marker_by_the_streamer_always_becomes_a_clip():
    messages = quiet_chat() + [ChatMessage(600.0, "!clip", "streamer", role="owner"), ChatMessage(900.0, "!clip 방금", "viewer")]
    messages.sort(key=lambda m: m.time)
    assert marker_times(messages) == [(600.0, "!clip")]  # the viewer's is not a marker
    result = detect_highlights(messages, duration=1800)
    assert len(marked(result)) == 1
    h = result.highlights[0]
    cfg = HighlightConfig()
    assert h.rank == 1 and h.start == pytest.approx(600 - cfg.chat_delay - cfg.lead) and h.end == pytest.approx(600 - cfg.chat_delay + cfg.tail)
    assert h.reasons[0] == "스트리머 표시 (!clip)" and h.stats["marker"] == 1

    assert marked(detect_highlights(messages, duration=1800, config=HighlightConfig(markers=()))) == []
    anyone = detect_highlights(messages, duration=1800, config=HighlightConfig(marker_roles=("any",)))
    assert [round(h.peak) for h in marked(anyone)] == [592, 892]
    custom = detect_highlights(messages + [ChatMessage(1200.0, "여기 자르기", "mod", role="moderator")], duration=1800, config=HighlightConfig(markers=("여기",)))
    assert [h.reasons[0] for h in marked(custom)] == ["스트리머 표시 (여기)"]


def test_markers_come_first_and_are_kept_on_top_of_the_best():
    rng = random.Random(2)
    messages = quiet_chat(3600)
    for at in (900, 2400):
        messages += [ChatMessage(at + 6 + rng.random() * 10, "草", f"r{rng.randrange(5000)}") for _ in range(150)]
    plain = detect_highlights(sorted(messages, key=lambda m: m.time), duration=3600, config=HighlightConfig(top=1))
    assert len(plain.highlights) == 1 and "marker" not in plain.highlights[0].stats
    # One marker far from the surges, one in the middle of the first surge.
    messages += [ChatMessage(3000.0, "!ts", "s", role="owner"), ChatMessage(912.0, "!clip", "s", role="owner")]
    result = detect_highlights(sorted(messages, key=lambda m: m.time), duration=3600, config=HighlightConfig(top=1))
    assert [bool(h.stats.get("marker")) for h in result.highlights] == [True, True, False]
    assert [h.rank for h in result.highlights] == [1, 2, 3]
    first, second, third = result.highlights
    assert first.start < 900 < first.end and first.reasons[0] == "스트리머 표시 (!clip)" and any("채팅 급증" in reason for reason in first.reasons)  # merged with the surge it is in
    assert second.start < 3000 - 8 < second.end and 2380 < third.peak < 2420


def test_highlights_command_reports_a_marker(tmp_path, capsys):
    rows = ["time,author,text,role"] + [f"{t},u{t % 30},なるほど," for t in range(0, 900, 3)] + ["450,streamer,!clip,owner"]
    chat = tmp_path / "chat.csv"
    chat.write_text("\n".join(rows), encoding="utf-8")
    assert main(["highlights", "--chat", str(chat), "-o", str(tmp_path / "h.json")]) == 0
    assert "스트리머 표시 (!clip)" in capsys.readouterr().out
    assert main(["highlights", "--chat", str(chat), "--no-markers", "-o", str(tmp_path / "h.json")]) == 0
    assert "스트리머 표시" not in capsys.readouterr().out


def test_live_mode_fires_on_a_marker_without_waiting_for_a_surge():
    detector = SurgeDetector(LiveConfig())
    fired = []
    for second in range(0, 60):  # far less than the warm-up
        detector.add(ChatMessage(1000.0 + second, "こんにちは みんな", f"u{second % 5}"))
        if second in (20, 22):  # asked twice: one clip
            detector.add(ChatMessage(1000.0 + second, "!clip", "streamer", role="owner"))
        if second == 40:
            detector.add(ChatMessage(1000.0 + second, "!clip", "viewer"))
        fired += detector.advance(1000.0 + second)
    assert len(fired) == 1
    assert fired[0].reasons[0] == "스트리머 표시 (!clip)" and fired[0].stats["marker"] == 2 and 1020 < fired[0].time <= 1030
    quiet = SurgeDetector(LiveConfig(markers=()))
    for second in range(0, 60):
        quiet.add(ChatMessage(1000.0 + second, "!clip", "streamer", role="owner"))
        assert quiet.advance(1000.0 + second) == []


# --------------------------------------------------------------------------- pip layout, avatar video


def test_avatar_layouts_say_what_they_need():
    assert "pip" in LAYOUTS
    for kind in ("stack", "pip"):
        with pytest.raises(ValueError, match="avatar"):
            VerticalLayout(kind)
        assert VerticalLayout(kind, avatar_source="avatar.mov").uses_avatar_video
    with pytest.raises(ValueError, match="not by blur"):
        VerticalLayout("blur", avatar_source="avatar.mov")
    with pytest.raises(ValueError, match="corner"):
        VerticalLayout("pip", avatar=Region(0, 0, 10, 10), corner="middle")
    with pytest.raises(ValueError, match="inset"):
        VerticalLayout("pip", avatar=Region(0, 0, 10, 10), inset=0.95)
    with pytest.raises(ValueError, match="avatar_inp"):
        VerticalLayout("pip", avatar_source="avatar.mov").graph()


def test_pip_graph_places_the_box_in_the_chosen_corner():
    graph = VerticalLayout("pip", 540, 960, avatar=Region(900, 100, 300, 400), game=Region(0, 0, 800, 720), corner="bottom-left", inset=0.3).graph("[in]", "[out]")
    assert graph.startswith("[in]split=2") and graph.endswith("[out]")
    assert "crop=300:400:900:100,scale=162:-2" in graph and "crop=800:720:0:0,scale=540:960" in graph
    assert "overlay=22:H-h-22" in graph
    assert "overlay=W-w-22:22" in VerticalLayout("pip", 540, 960, avatar=Region(0, 0, 10, 10)).graph()


def test_avatar_video_is_a_second_input_cut_to_the_same_span():
    layout = VerticalLayout("pip", 540, 960, avatar_source="avatar.mov", avatar_offset=2.5, avatar_key=None)
    options = ExportOptions(format="mp4", fps=30, start=10.0, end=25.0, layout=layout)
    graph = build_video_filter(options)
    assert "[1:v]fps=30,format=rgba[lcut]" in graph and "colorkey" not in graph
    assert "colorkey=0x00FF00" in build_video_filter(ExportOptions(format="mp4", layout=VerticalLayout("stack", avatar_source="a.mp4")))
    cmd = build_export_command("game.mp4", "out.mp4", options, ffmpeg="ffmpeg")
    inputs = [i for i, part in enumerate(cmd) if part == "-i"]
    assert [cmd[i + 1] for i in inputs] == ["game.mp4", "avatar.mov"]
    assert cmd[inputs[0] + 2 : inputs[1]] == ["-ss", "12.500", "-t", "15.000"]
    assert cmd.count("0:a:0?") == 1  # sound still comes from the stream

    late = ExportOptions(format="mp4", start=1.0, end=5.0, layout=VerticalLayout("pip", avatar_source="avatar.mov", avatar_offset=-30.0))
    with pytest.raises(ValueError, match="does not cover"):
        build_export_command("game.mp4", "out.mp4", late, ffmpeg="ffmpeg")
    with pytest.raises(ValueError, match="video file"):
        build_export_command(None, "out.mp4", ExportOptions(format="mp4", layout=layout), raw_input=RawVideoInput(64, 64, 10), ffmpeg="ffmpeg")


def test_sections_keep_the_avatar_video_on_the_stream_clock(tmp_path, monkeypatch):
    seen = []

    def fake_export(video, out, options):
        seen.append((str(video), options.start, options.layout.avatar_offset))
        out.write_bytes(b"")
        return out

    monkeypatch.setattr("stream2clip.pipeline.export", fake_export)
    monkeypatch.setattr("stream2clip.pipeline._output_size", lambda video, options: options.layout.size)
    layout = VerticalLayout("pip", 540, 960, avatar_source="avatar.mov", avatar_offset=1.0)
    highlight = Highlight(1, 3600.0, 3630.0, 3615.0, 3.0)
    # The footage of this highlight starts 3590 s into the stream: the clip starts 10 s into it ...
    make_clips(None, [highlight], tmp_path, options=ExportOptions(format="mp4", layout=layout), section=lambda h: ("part.mp4", 3590.0))
    # ... and 3601 s into the avatar video (10 + 3591).
    assert seen == [("part.mp4", 10.0, 3591.0)]


@pytest.fixture
def game_and_avatar(tmp_path):
    """A blue 320x180 "stream" with a red avatar box at 240,20 (60x80), and a green-screen video of a magenta avatar."""
    game, avatar = tmp_path / "game.mp4", tmp_path / "avatar.mp4"
    common = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi"]
    subprocess.run([*common, "-i", "color=c=0x0000FF:s=320x180:r=10:d=2", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                    "-vf", "drawbox=x=240:y=20:w=60:h=80:color=0xFF0000:t=fill", "-c:v", "libx264", "-qp", "0", "-pix_fmt", "yuv444p", "-c:a", "aac", "-shortest", str(game)], check=True)
    subprocess.run([*common, "-i", "color=c=0x00FF00:s=120x160:r=10:d=2",
                    "-vf", "drawbox=x=30:y=40:w=60:h=120:color=0xFF00FF:t=fill", "-c:v", "libx264", "-qp", "0", "-pix_fmt", "yuv444p", str(avatar)], check=True)
    return game, avatar


def near(pixel, colour, tolerance=40):
    return all(abs(int(a) - b) <= tolerance for a, b in zip(pixel[:3], colour))


RED, BLUE, MAGENTA, INK = (255, 0, 0), (0, 0, 255), (255, 0, 255), (21, 19, 31)


@needs_ffmpeg
def test_pip_puts_the_avatar_box_in_a_corner_of_the_game(game_and_avatar, tmp_path):
    game, _avatar = game_and_avatar
    layout = VerticalLayout("pip", 180, 320, avatar=Region(240, 20, 60, 80), game=Region(0, 0, 100, 180), inset=0.5)
    out = export(game, tmp_path / "pip.mp4", ExportOptions(format="mp4", fps=10, layout=layout))
    info = probe(out)
    assert (info.width, info.height) == (180, 320) and info.duration == pytest.approx(2.0, abs=0.2)
    frame = grab_frames(out, [1.0])[0]
    assert near(frame[60, 130], RED)  # the box: 90 px wide, 8 px from the top right corner
    assert near(frame[60, 30], BLUE) and near(frame[250, 130], BLUE)  # the game everywhere else
    assert near(frame[9, 130], (247, 244, 250), 60)  # the thin frame around the box


@needs_ffmpeg
def test_avatar_video_is_keyed_and_laid_over_the_game(game_and_avatar, tmp_path):
    game, avatar = game_and_avatar
    pip = VerticalLayout("pip", 180, 320, avatar_source=avatar, corner="bottom-left", inset=0.5)
    frame = grab_frames(export(game, tmp_path / "pip.mp4", ExportOptions(format="mp4", fps=10, layout=pip)), [1.0])[0]
    # The avatar video is 90x120 here, 8 px from the bottom left corner: its magenta figure is in the middle.
    assert near(frame[280, 52], MAGENTA)
    assert near(frame[200, 12], BLUE) and near(frame[300, 12], BLUE)  # where its green was, the game shows
    assert near(frame[100, 90], BLUE)

    stack = VerticalLayout("stack", 180, 320, avatar_source=avatar)
    out = export(game, tmp_path / "stack.mp4", ExportOptions(format="mp4", fps=10, layout=stack))
    assert probe(out).duration == pytest.approx(2.0, abs=0.2)  # the plain panel behind the avatar does not run on
    frame = grab_frames(out, [1.0])[0]
    assert near(frame[100, 90], MAGENTA)  # the figure stands in the top panel ...
    assert near(frame[10, 10], INK) and near(frame[120, 170], INK)  # ... on the brand colour, not on green
    assert near(frame[250, 40], BLUE)

    preview = grab_frames(game, [0.5], layout=pip)[0]  # the quick still the app shows
    assert preview.shape == (320, 180, 4) and near(preview[280, 52], MAGENTA)


@needs_ffmpeg
def test_clips_command_takes_an_avatar_video(game_and_avatar, tmp_path, capsys):
    game, avatar = game_and_avatar
    highlights = tmp_path / "h.json"
    highlights.write_text(json.dumps({"highlights": [{"rank": 1, "start": 0.2, "end": 1.6, "score": 3}]}), encoding="utf-8")
    out = tmp_path / "clips"
    code = main(["clips", str(game), "--highlights", str(highlights), "--layout", "pip", "--avatar-video", str(avatar), "--corner", "top-left", "--inset", "0.5",
                 "--size", "180x320", "--fps", "10", "-o", str(out)])
    assert code == 0, capsys.readouterr().out
    frame = grab_frames(out / "clip_01.mp4", [0.5])[0]
    assert near(frame[90, 52], MAGENTA) and near(frame[250, 90], BLUE)
    assert main(["clips", str(game), "--highlights", str(highlights), "--layout", "pip", "-o", str(out)]) == 1  # no avatar given
    assert "avatar" in capsys.readouterr().err


# --------------------------------------------------------------------------- Twitch chat


def test_live_command_names_a_marker_as_such(tmp_path, capsys):
    log = tmp_path / "chat.jsonl"
    now = __import__("time").time()
    # the marker, and a later message that closes its 5 s window
    lines = [{"text": "!clip", "author": "s", "role": "owner", "time": now + 1}, {"text": "hello", "author": "v", "time": now + 7}]
    log.write_text("".join(json.dumps(line) + chr(10) for line in lines), encoding="utf-8")
    assert main(["live", str(log), "--no-obs", "--duration", "2", "--tail", "0", "-o", str(tmp_path / "out")]) == 0
    out = capsys.readouterr().out
    assert "marker" in out and "스트리머 표시 (!clip)" in out and "surge 0.0" not in out


def test_twitch_channel_addresses():
    assert twitch_channel("https://www.twitch.tv/Some_Name") == "some_name"
    assert twitch_channel("twitch.tv/abc/") == "abc" and twitch_channel("https://m.twitch.tv/abc?sr=a") == "abc"
    for other in ("https://www.twitch.tv/videos/123", "https://www.twitch.tv/abc/clip/xyz", "https://www.youtube.com/watch?v=abc", "chat.jsonl", "https://www.twitch.tv/directory"):
        assert twitch_channel(other) is None


def test_twitch_chat_lines():
    line = ("@badge-info=;badges=broadcaster/1,subscriber/12;bits=250;color=#FF0000;display-name=Name;emotes=25:0-4,12-16/1902:6-10;"
            "mod=0;tmi-sent-ts=1700000000123;user-id=4242 :name!name@name.tmi.twitch.tv PRIVMSG #chan :Kappa Keepo Kappa nice")
    message = parse_twitch_irc(line)
    assert message.text == "Kappa Keepo Kappa nice" and message.time == pytest.approx(1700000000.123)
    assert message.kind == "paid" and message.amount == 250 and message.currency == "bits"
    assert message.emotes == ("Kappa", "Keepo") and message.role == "owner"
    assert len(message.author) == 12 and "4242" not in message.author and "name" not in message.author  # hashed

    plain = parse_twitch_irc("@badges=moderator/1;tmi-sent-ts=1700000001000;user-id=7 :m!m@m.tmi.twitch.tv PRIVMSG #chan :\x01ACTION waves\x01")
    assert (plain.text, plain.kind, plain.role) == ("waves", "text", "moderator")
    assert parse_twitch_irc("@mod=1;user-id=8 :x!x@x.tmi.twitch.tv PRIVMSG #chan :!clip").role == "moderator"
    assert math.isnan(parse_twitch_irc(":x!x@x.tmi.twitch.tv PRIVMSG #chan :no tags").time)

    sub = parse_twitch_irc("@msg-id=resub;system-msg=Name\\ssubscribed\\sfor\\s6\\smonths;tmi-sent-ts=1700000002000;user-id=9 :tmi.twitch.tv USERNOTICE #chan :love it")
    assert (sub.kind, sub.text) == ("member", "love it")
    assert parse_twitch_irc("@msg-id=submysterygift;user-id=9 :tmi.twitch.tv USERNOTICE #chan").kind == "gift"
    assert parse_twitch_irc("@msg-id=raid;user-id=9 :tmi.twitch.tv USERNOTICE #chan") is None
    for other in (":tmi.twitch.tv 001 justinfan1 :Welcome, GLHF!", "PING :tmi.twitch.tv", ":x!x@x JOIN #chan", ""):
        assert parse_twitch_irc(other) is None


class FakeSocket:
    """Hands out scripted chunks; ``None`` means "nothing for now", ``b""`` that the server closed."""

    def __init__(self, chunks):
        self.chunks = list(chunks)
        self.sent = b""
        self.closed = False

    def sendall(self, data):
        self.sent += data

    def settimeout(self, value):
        pass

    def recv(self, size):
        if not self.chunks or self.chunks[0] is None:
            if self.chunks:
                self.chunks.pop(0)
            raise BlockingIOError
        return self.chunks.pop(0)

    def close(self):
        self.closed = True


def test_twitch_chat_is_read_as_an_anonymous_viewer():
    first = FakeSocket([
        b":tmi.twitch.tv 001 justinfan1 :Welcome\r\n@tmi-sent-ts=1700000000000;user-id=1 :a!a@a PRIVMSG #chan :hel", None,
        b"lo\r\nPING :tmi.twitch.tv\r\n@tmi-sent-ts=1700000001000;user-id=2 :b!b@b PRIVMSG #chan :KEKW\r\n", None,
        b"",  # Twitch closes the connection
    ])
    second = FakeSocket([b"@tmi-sent-ts=1700000009000;user-id=3 :c!c@c PRIVMSG #chan :back\r\n"])
    sockets = [first, second]
    chat = TwitchLiveChat("https://www.twitch.tv/Chan", connect=lambda: sockets.pop(0))
    assert chat.channel == "chan" and first.sent == b""  # nothing happens before the first read
    assert chat.read() == []  # "hel" is half a line
    login = first.sent.decode()
    assert "NICK justinfan" in login and "JOIN #chan\r\n" in login and "PASS" not in login
    assert [m.text for m in chat.read()] == ["hello", "KEKW"]
    assert first.sent.endswith(b"PONG :tmi.twitch.tv\r\n")
    assert chat.read() == [] and first.closed  # closed: connect again at the next read
    assert [m.text for m in chat.read()] == ["back"] and b"JOIN #chan" in second.sent
    chat.close()
    assert chat.ended and second.closed and chat.read() == []


def test_twitch_chat_gives_up_when_twitch_cannot_be_reached():
    def refuse():
        raise OSError("no route")

    chat = TwitchLiveChat("chan", connect=refuse, retries=3)
    assert chat.read() == [] and chat.read() == []
    with pytest.raises(RuntimeError, match="Could not reach Twitch chat"):
        chat.read()
    with pytest.raises(ValueError, match="Not a Twitch channel"):
        TwitchLiveChat("not a channel!")


def test_open_chat_picks_the_source(tmp_path, monkeypatch):
    chat, described = open_chat("https://www.twitch.tv/chan", tmp_path)
    assert isinstance(chat, TwitchLiveChat) and "twitch.tv/chan" in described
    log = tmp_path / "chat.jsonl"
    chat, described = open_chat(str(log), tmp_path)
    assert isinstance(chat, FileFollower) and str(log) in described
    started = []
    monkeypatch.setattr("stream2clip.live.YtDlpLiveChat", lambda url, folder, ytdlp=None: started.append((url, ytdlp)) or "yt")
    assert open_chat("https://www.youtube.com/watch?v=abc", tmp_path, ytdlp=["yt-dlp"]) == ("yt", "https://www.youtube.com/watch?v=abc  (yt-dlp, about every 10 s)")
    assert started == [("https://www.youtube.com/watch?v=abc", ["yt-dlp"])]


def test_live_command_needs_yt_dlp_only_for_addresses_it_reads(tmp_path, monkeypatch, capsys):
    def missing(**_options):
        raise RuntimeError("yt-dlp is not installed")

    monkeypatch.setattr("stream2clip.sources.ytdlp_command", missing)
    log = tmp_path / "chat.jsonl"
    log.write_text("", encoding="utf-8")
    assert main(["live", str(log), "--no-obs", "--duration", "0.2", "-o", str(tmp_path / "out")]) == 0
    assert "following" in capsys.readouterr().out
    assert main(["live", "https://www.youtube.com/watch?v=abc", "--no-obs", "--duration", "0.2", "-o", str(tmp_path / "out")]) == 1
    assert "yt-dlp is not installed" in capsys.readouterr().err


def test_twitch_messages_drive_the_detector():
    rng = random.Random(4)
    detector = SurgeDetector(LiveConfig(warmup=60, min_messages=5))
    fired = []
    for second in range(0, 300):
        lines = [f"@tmi-sent-ts={(1700000000 + second) * 1000};user-id={rng.randrange(40)} :u!u@u PRIVMSG #chan :ok"] if second % 3 == 0 else []
        if 240 <= second < 252:
            lines += [f"@tmi-sent-ts={(1700000000 + second) * 1000 + i};user-id={1000 + rng.randrange(500)} :u!u@u PRIVMSG #chan :LUL KEKW" for i in range(8)]
        for line in lines:
            detector.add(parse_twitch_irc(line))
        fired += detector.advance(1700000000.0 + second)
    assert len(fired) == 1 and 1700000240 < fired[0].time <= 1700000260
    assert np.isfinite(fired[0].score) and any("채팅 급증" in reason for reason in fired[0].reasons)


# --------------------------------------------------------------------------- reaction words in the subtitles (experimental)


def test_speech_levels_count_reaction_lines():
    from stream2clip.highlights import speech_levels

    cues = [Cue(2.0, 4.0, "今日はここまで"), Cue(12.0, 13.0, "えっ"), Cue(13.0, 15.0, "やばいやばい"), Cue(31.0, 33.0, "", (Word(31.0, 32.0, "すご"), Word(32.0, 33.0, "い")))]
    assert speech_levels(cues, window=5.0).tolist() == [0, 0, 2, 0, 0, 0, 1]
    assert speech_levels(cues, window=5.0, delay=8.0).tolist() == [0, 0, 0, 0, 2, 0, 0, 1]  # moved onto the chat's clock
    assert speech_levels([Cue(0, 1, "普通の話")]).size == 0


def test_a_stream_without_chat_is_searched_by_what_the_streamer_says(tmp_path, capsys):
    lines, t = [], 0
    for index in range(240):  # 20 minutes of talk, one line every 5 s ...
        said = "それでね、次の話なんだけど"
        if 120 <= index < 123:  # ... and at 10:00 the streamer is startled three lines in a row
            said = ["えっ", "やばいやばい", "うわああ"][index - 120]
        lines.append(f"{index + 1}\n00:{t // 60:02d}:{t % 60:02d},000 --> 00:{(t + 4) // 60:02d}:{(t + 4) % 60:02d},000\n{said}\n")
        t += 5
    subs = tmp_path / "talk.srt"
    subs.write_text("\n".join(lines), encoding="utf-8")
    assert main(["highlights", "--speech", str(subs), "-o", str(tmp_path / "h.json")]) == 0
    out = capsys.readouterr().out
    assert "analysed 0 chat messages" in out and "자막 속 반응 표현 3회" in out
    found = json.loads((tmp_path / "h.json").read_text(encoding="utf-8"))["highlights"]
    assert len(found) == 1 and found[0]["start"] < 600 < found[0]["end"] and found[0]["stats"]["speech_reactions"] == 3
    assert main(["highlights", "-o", str(tmp_path / "none.json")]) == 1
    assert "--speech" in capsys.readouterr().err
    calm = tmp_path / "calm.srt"  # subtitles without a single reaction line: say so, instead of a puzzling error
    calm.write_text("1\n00:00:01,000 --> 00:00:04,000\n今日は配信に来てくれてありがとうございます\n", encoding="utf-8")
    assert main(["highlights", "--speech", str(calm), "-o", str(tmp_path / "calm.json")]) == 1
    assert "No reaction words" in capsys.readouterr().err and not (tmp_path / "calm.json").exists()


def test_speech_is_only_used_when_asked_for():
    from stream2clip.highlights import speech_levels

    messages = quiet_chat(1800)
    cues = [Cue(900.0 + i, 901.0 + i, "やばい") for i in range(0, 12, 2)]
    plain = detect_highlights(messages, duration=1800)
    with_speech = detect_highlights(messages, duration=1800, speech=speech_levels(cues, delay=HighlightConfig().chat_delay))
    assert "speech" not in plain.signals and "speech" in with_speech.signals
    assert any(h.start < 900 < h.end and h.stats.get("speech_reactions") for h in with_speech.highlights)
    assert not any(h.start < 900 < h.end for h in plain.highlights)
