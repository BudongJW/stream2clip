"""Clips from a stream's address: only the footage of the highlights is downloaded."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from stream2clip import sources
from stream2clip.cli import main
from stream2clip.ffmpeg import ExportOptions
from stream2clip.highlights import Highlight
from stream2clip.pipeline import make_clips
from stream2clip.sources import SourceInfo, build_section_command, download_highlight_sections, download_section, hls_relaxed_args, is_url
from stream2clip.subtitles import Cue

from .conftest import needs_ffmpeg


def highlight(rank, start, end):
    return Highlight(rank=rank, start=start, end=end, peak=(start + end) / 2, score=5.0, reasons=["채팅 급증"])


def test_is_url():
    assert is_url("https://chzzk.naver.com/video/1") and is_url("HTTP://example.com/v")
    assert not is_url("vod/video.mp4") and not is_url("C:/clips/https.mp4") and not is_url(None)


def test_section_command_can_pass_options_to_ffmpeg():
    plain = build_section_command("URL", "v.mp4", start=10, end=20, ytdlp=["yt-dlp"])
    assert "--downloader-args" not in plain
    relaxed = build_section_command("URL", "v.mp4", start=10, end=20, ytdlp=["yt-dlp"], ffmpeg_input_args=["-extension_picky", "0"])
    assert relaxed[relaxed.index("--downloader-args") + 1] == "ffmpeg_i:-extension_picky 0" and relaxed[-1] == "URL"
    whole = build_section_command("URL", "v.mp4", ytdlp=["yt-dlp"], ffmpeg_input_args=["-extension_picky", "0"])
    assert "--downloader-args" not in whole  # a whole download does not go through ffmpeg's HLS reader


def test_sections_prefer_hls_formats():
    """Seen on a real YouTube archive: a 64 s section took over 6 minutes from the DASH formats and 13 s from HLS."""
    whole = build_section_command("URL", "v.mp4", max_height=480, ytdlp=["yt-dlp"])
    assert whole[whole.index("-f") + 1] == "bv*[height<=480]+ba/b[height<=480]/b"
    part = build_section_command("URL", "v.mp4", start=10, end=20, max_height=480, ytdlp=["yt-dlp"])
    choice = part[part.index("-f") + 1].split("/")
    assert choice[:2] == ["bv*[protocol*=m3u8][height<=480]+ba[protocol*=m3u8]", "b[protocol*=m3u8][height<=480]"]
    assert choice[2:] == ["bv*[height<=480]+ba", "b[height<=480]", "b"]  # sites without HLS still work as before


def test_hls_switch_is_only_used_when_ffmpeg_has_it(monkeypatch):
    answers = {"new": "  -extension_picky   <boolean>  .D... Be picky with all extensions matching (default true)", "old": "  -allowed_extensions <string>"}
    asked = []

    def fake_run(cmd, **kwargs):
        asked.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout=answers[cmd[0]], stderr="")

    monkeypatch.setattr(sources.subprocess, "run", fake_run)
    monkeypatch.setattr(sources, "_HLS_PICKY", {})
    assert hls_relaxed_args("new") == ["-extension_picky", "0"] and hls_relaxed_args("old") == []
    assert hls_relaxed_args("new") == ["-extension_picky", "0"] and len(asked) == 2  # asked once per program
    assert asked[0][1:] == ["-hide_banner", "-h", "demuxer=hls"]

    def broken(cmd, **kwargs):
        raise OSError("no such program")

    monkeypatch.setattr(sources.subprocess, "run", broken)
    assert hls_relaxed_args("missing") == []


def test_chzzk_sections_switch_the_extension_check_off(monkeypatch, tmp_path):
    """Seen with ffmpeg 8.1 on a real CHZZK replay: "mismatches allowed extensions" for its .m4s segments."""
    commands = []
    monkeypatch.setattr(sources, "_run", lambda cmd, timeout=None: commands.append(cmd))
    monkeypatch.setattr(sources, "hls_relaxed_args", lambda ffmpeg=None: ["-extension_picky", "0"])
    y = ["yt-dlp"]
    download_section("https://chzzk.naver.com/video/16230061", tmp_path / "a.mp4", 600, 620, ytdlp=y)
    download_section("https://chzzk.naver.com/video/16230061", tmp_path / "b.mp4", ytdlp=y)  # whole video
    download_section("https://www.youtube.com/watch?v=abc", tmp_path / "c.mp4", 600, 620, ytdlp=y)  # another site
    assert ["--downloader-args" in cmd for cmd in commands] == [True, False, False]


def test_only_the_highlights_are_downloaded(tmp_path):
    calls = []

    def fake_download(url, path, start, end, *, max_height, ytdlp):
        calls.append((url, Path(path).name, start, end, max_height))
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(b"video")
        return Path(path)

    seen = []
    hs = [highlight(1, 5020.0, 5110.0), highlight(2, 1.0, 31.0)]
    found = download_highlight_sections("URL", hs, tmp_path / "sections", max_height=480, download=fake_download, on_progress=lambda i, n, h: seen.append((i, n, h.rank)))
    assert calls == [("URL", "section_01_0050180-0051120.mp4", 5018.0, 5112.0, 480), ("URL", "section_02_0000000-0000330.mp4", 0.0, 33.0, 480)]  # padded, not below zero
    assert found[1] == (tmp_path / "sections" / "section_01_0050180-0051120.mp4", 5018.0) and found[2][1] == 0.0
    assert seen == [(1, 2, 1), (2, 2, 2)]

    download_highlight_sections("URL", hs, tmp_path / "sections", max_height=480, download=fake_download)
    assert len(calls) == 2  # already there: an interrupted run continues instead of starting over
    hs[0].end = 5140.0  # a different span is a different file
    download_highlight_sections("URL", hs, tmp_path / "sections", max_height=480, download=fake_download)
    assert len(calls) == 3 and calls[-1][3] == 5142.0


@needs_ffmpeg
def test_clips_from_sections_keep_stream_time(green_screen_video, tmp_path):
    """The 2 s test video stands in for footage that starts 100 s into the stream."""
    from stream2clip.export import probe

    h = highlight(1, 100.5, 101.5)
    cues = [Cue(100.6, 101.2, "こんにちは"), Cue(30.0, 31.0, "elsewhere in the stream")]
    source = SourceInfo(url="https://www.youtube.com/watch?v=abc", title="title")
    results = make_clips(
        None, [h], tmp_path / "out", options=ExportOptions(format="mp4", fps=10), cues=cues, source=source,
        section=lambda item: (green_screen_video, 100.0),
    )
    clip = results[0].path
    assert probe(clip).duration == pytest.approx(1.0, abs=0.25)  # cut at 0.5-1.5 s of the file
    ass = results[0].subtitles.read_text(encoding="utf-8")
    assert "こんにちは" in ass and "elsewhere" not in ass  # subtitles are still looked up in stream time
    assert "t=100" in results[0].description.read_text(encoding="utf-8")  # and so is the link to the source
    assert json.loads((tmp_path / "out" / "clips.json").read_text(encoding="utf-8"))["video"] is None
    with pytest.raises(ValueError, match="video or a section"):
        make_clips(None, [h], tmp_path / "out")


@needs_ffmpeg
def test_cli_clips_and_auto_from_an_address(tmp_path, monkeypatch, capsys):
    fetched = []
    footage = tmp_path / "footage.mp4"  # long enough for any section the commands ask for
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=160x90:r=5:d=100", "-f", "lavfi", "-i", "sine=frequency=440:duration=100",
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(footage)], check=True)

    def fake_section(url, output, start=None, end=None, *, max_height=1080, ytdlp=None, timeout=None):
        fetched.append((url, start, end, max_height))
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(footage, output)
        return Path(output)

    monkeypatch.setattr(sources, "download_section", fake_section)
    monkeypatch.setattr(sources, "ytdlp_command", lambda **kwargs: ["yt-dlp"])  # yt-dlp itself is not needed (nor installed in CI)
    url = "https://www.youtube.com/watch?v=abc"
    highlights = tmp_path / "h.json"
    highlights.write_text(json.dumps({"highlights": [{"rank": 1, "start": 600.5, "end": 601.5}]}), encoding="utf-8")
    out = tmp_path / "clips"
    assert main(["clips", url, "--highlights", str(highlights), "--layout", "none", "-f", "gif", "--fps", "5", "--max-height", "480", "-o", str(out)]) == 0
    assert fetched == [(url, 598.5, 603.5, 480)]
    assert (out / "clip_01.gif").is_file() and len(list((out / "sections").glob("section_01_*.mp4"))) == 1
    assert "download [1/1]" in capsys.readouterr().out

    # auto: the chat replay and info are fetched first, the video only in parts
    chat = tmp_path / "chat.csv"
    rows = ["time,author,text"] + [f"{t},u{t % 30},なるほど" for t in range(0, 1800, 3)] + [f"{906 + i * 0.05:.2f},r{i},草" for i in range(160)]
    chat.write_text("\n".join(rows), encoding="utf-8")
    asked = []
    monkeypatch.setattr(sources, "fetch_info", lambda u, ytdlp=None: asked.append("info") or {"id": "abc", "title": "配信", "webpage_url": u, "duration": 1800})
    monkeypatch.setattr(sources, "download_chat", lambda u, o, ytdlp=None: asked.append("chat") or chat)
    fetched.clear()
    auto_out = tmp_path / "auto"
    assert main(["auto", url, "--layout", "none", "-f", "gif", "--fps", "5", "--top", "1", "-o", str(auto_out)]) == 0
    assert asked == ["info", "chat"] and len(fetched) == 1 and fetched[0][1] == pytest.approx(900 - 20 - 2, abs=10)
    assert (auto_out / "clip_01.gif").is_file() and (auto_out / "info.json").is_file() and (auto_out / "highlights.json").is_file()
    assert url in (auto_out / "clip_01.txt").read_text(encoding="utf-8")  # the description names the source

    assert main(["auto", url, "--audio", "-o", str(tmp_path / "x")]) == 1
    assert "needs the whole video" in capsys.readouterr().err


def test_one_folder_per_stream():
    name = sources.source_folder_name
    assert name("https://www.youtube.com/watch?v=kyMhlh8MGDE") == "youtube_kyMhlh8MGDE"
    assert name("https://www.youtube.com/watch?list=PL1&v=kyMhlh8MGDE&t=10s") == "youtube_kyMhlh8MGDE"
    assert name("https://youtu.be/kyMhlh8MGDE?t=3") == name("https://www.youtube.com/live/kyMhlh8MGDE") == "youtube_kyMhlh8MGDE"
    assert name("https://chzzk.naver.com/video/16230061") == "chzzk_16230061"
    assert name("https://vod.sooplive.co.kr/player/212422389") == "soop_212422389"
    assert name("https://www.twitch.tv/videos/2345678901") == "twitch_2345678901"
    other = name("https://example.com/streams/today?x=1")
    assert other.startswith("url_") and len(other) == 14 and other == name(" https://example.com/streams/today?x=1 ")
    assert other != name("https://example.com/streams/yesterday")
    assert name("https://chzzk.naver.com/live/abc").startswith("url_")  # no replay number in it


def test_fetch_replay_gets_info_and_chat_but_no_video(tmp_path, monkeypatch):
    asked = []

    def fake_chat(url, out, ytdlp=None):
        asked.append("chat")
        path = Path(out) / "abc.live_chat.json"
        path.write_text("", encoding="utf-8")
        return path

    monkeypatch.setattr(sources, "fetch_info", lambda u, ytdlp=None: asked.append("info") or {"id": "abc", "title": "配信"})
    monkeypatch.setattr(sources, "download_chat", fake_chat)
    url = "https://www.youtube.com/watch?v=abcdef12345"
    stages = []
    folder = tmp_path / "work"
    info, chat = sources.fetch_replay(url, folder, ytdlp=["yt-dlp"], on_stage=stages.append)
    assert info == folder / "info.json" and json.loads(info.read_text(encoding="utf-8"))["title"] == "配信"
    assert chat == folder / "abc.live_chat.json" and asked == ["info", "chat"] and stages == ["fetch-info", "fetch-chat"]

    assert sources.fetch_replay(url, folder, ytdlp=["yt-dlp"]) == (info, chat) and len(asked) == 4  # asked again unless told to reuse
    assert sources.fetch_replay(url, folder, reuse=True, ytdlp=["yt-dlp"], on_stage=stages.append) == (info, chat)
    assert len(asked) == 4 and len(stages) == 2  # what is on disk is kept
    assert sources.fetch_replay(url, folder, info=False, ytdlp=["yt-dlp"]) == (None, chat) and asked[4:] == ["chat"]

    # CHZZK and SOOP may refuse the info request; the chat is still collected.
    def refused(u, ytdlp=None):
        raise RuntimeError("yt-dlp failed (1):\nERROR: login required")

    def fake_replay_chat(u, out):
        path = Path(out) / "chzzk_16230061.chat.jsonl"
        path.write_text("", encoding="utf-8")
        return path

    monkeypatch.setattr(sources, "fetch_info", refused)
    monkeypatch.setattr(sources, "download_replay_chat", fake_replay_chat)
    warnings = []
    info, chat = sources.fetch_replay("https://chzzk.naver.com/video/16230061", tmp_path / "kr", ytdlp=["yt-dlp"], warn=warnings.append)
    assert info is None and chat.name == "chzzk_16230061.chat.jsonl" and "login required" in warnings[0]
    with pytest.raises(RuntimeError, match="login required"):  # elsewhere the info is the way to the chat, so it is an error
        sources.fetch_replay(url, tmp_path / "other", ytdlp=["yt-dlp"])
