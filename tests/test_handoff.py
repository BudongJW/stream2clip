"""Handing highlights to an editing program, the source credit, and compilations."""

from __future__ import annotations

import json
import re
import subprocess

import pytest

from stream2clip import handoff
from stream2clip.cli import main
from stream2clip.export import probe
from stream2clip.ffmpeg import ExportOptions, build_concat_command
from stream2clip.highlights import Highlight
from stream2clip.pipeline import compile_clips, compile_folder, make_clips
from stream2clip.sources import SourceInfo
from stream2clip.subtitles import CREDIT_POSITIONS, Cue, to_ass

from .conftest import needs_ffmpeg

HIGHLIGHTS = [
    Highlight(rank=2, start=422.0, end=452.5, peak=430.0, score=8.1, reasons=["채팅 급증 (평소의 3.2배)", "반응 12회", "후원"]),
    Highlight(rank=1, start=3725.25, end=3760.0, peak=3740.0, score=12.4, reasons=["스트리머 표시 (!clip)"]),
    Highlight(rank=3, start=65.0, end=80.0, peak=70.0, score=5.0, reasons=[]),
]
EVENT = re.compile(r"^(\d{3})  (\S+)\s+(\S+)\s+C\s+(\d\d:\d\d:\d\d:\d\d) (\d\d:\d\d:\d\d:\d\d) (\d\d:\d\d:\d\d:\d\d) (\d\d:\d\d:\d\d:\d\d)\s*$")


def count(code: str, base: int) -> int:
    h, m, s, f = (int(part) for part in code.split(":"))
    return ((h * 60 + m) * 60 + s) * base + f


# ----------------------------------------------------------------------------- timecodes and lists


def test_timecode_counts_frames_at_the_real_rate():
    assert handoff.timecode(0, 30) == "00:00:00:00"
    assert handoff.timecode(3725.25, 30) == "01:02:05:08"  # a quarter second is 7.5 frames: rounded to the nearest
    assert handoff.timecode(1.5, 60) == "00:00:01:30"
    assert handoff.timecode(60, 29.97) == "00:00:59:28"  # 1798 frames shown on a base of 30, as non-drop timecode is
    assert handoff.timecode(10, 23.976) == "00:00:10:00"  # 240 frames on a base of 24
    assert handoff.timecode(-3, 30) == "00:00:00:00"
    with pytest.raises(ValueError, match="frame rate"):
        handoff.timecode(1, 0)


def test_clock_is_the_form_sites_link():
    assert [handoff.clock(t) for t in (0, 65.9, 3599, 3600, 3725.25)] == ["0:00", "1:05", "59:59", "1:00:00", "1:02:05"]


def test_timestamp_list_is_in_stream_order_with_the_reasons():
    assert handoff.timestamps(HIGHLIGHTS) == "1:05 #03\n7:02 채팅 급증 (평소의 3.2배)\n1:02:05 스트리머 표시 (!clip)\n"  # the main reason only
    assert handoff.timestamps(HIGHLIGHTS, order="rank").splitlines()[0] == "1:02:05 스트리머 표시 (!clip)"
    assert handoff.timestamps(HIGHLIGHTS, labels=["가", "나\n다", "라"], offset=-60).splitlines() == ["0:05 가", "6:02 나 다", "1:01:05 라"]
    assert handoff.timestamps([]) == ""
    with pytest.raises(ValueError, match="2 labels for 3"):
        handoff.timestamps(HIGHLIGHTS, labels=["a", "b"])
    with pytest.raises(ValueError, match="Unknown order"):
        handoff.ordered(HIGHLIGHTS, "score")


# ----------------------------------------------------------------------------- EDL


@pytest.mark.parametrize("fps", [30.0, 60.0, 29.97, 59.94, 24.0])
def test_edl_cuts_are_the_highlights_placed_back_to_back(fps):
    text = handoff.edl(HIGHLIGHTS, fps=fps, title="테스트\n방송", clip_name="stream [abc].mp4")
    lines = text.splitlines()
    assert lines[:3] == ["TITLE: 테스트 방송", "FCM: NON-DROP FRAME", ""]
    events = [EVENT.match(line).groups() for line in lines if EVENT.match(line)]
    assert [e[0] for e in events] == ["001", "002", "003"] and {e[1] for e in events} == {"AX"} and {e[2] for e in events} == {"AA/V"}
    base = round(fps)
    at = 3600 * base  # timelines start at one hour
    for (_, _, _, src_in, src_out, rec_in, rec_out), h in zip(events, sorted(HIGHLIGHTS, key=lambda h: h.start)):
        assert count(src_in, base) == round(h.start * fps) and count(src_out, base) == round(h.end * fps)
        assert count(rec_in, base) == at  # no gap and no overlap between the cuts
        assert count(rec_out, base) - count(rec_in, base) == count(src_out, base) - count(src_in, base)
        at = count(rec_out, base)
    assert text.count("* FROM CLIP NAME: stream [abc].mp4") == 3  # how an editing program finds the footage
    assert "* COMMENT: stream2clip #02 채팅 급증 (평소의 3.2배) / 반응 12회" in lines and "* COMMENT: stream2clip #03" in lines


def test_edl_options():
    silent = handoff.edl(HIGHLIGHTS, fps=30, audio=False, order="rank", record_start=0)
    events = [EVENT.match(line).groups() for line in silent.splitlines() if EVENT.match(line)]
    assert {e[2] for e in events} == {"V"} and events[0][3] == "01:02:05:08" and events[0][5] == "00:00:00:00"  # best first, from zero
    assert "FROM CLIP NAME" not in silent and silent.startswith("TITLE: stream2clip\n")
    empty = Highlight(rank=4, start=10.0, end=10.0, peak=10.0, score=0.0)
    assert len([line for line in handoff.edl([*HIGHLIGHTS, empty], fps=30).splitlines() if EVENT.match(line)]) == 3  # nothing to cut: left out


def test_edl_is_read_by_an_independent_reader():
    """OpenTimelineIO's CMX3600 reader (not a dependency: the check runs where it is installed)."""
    otio = pytest.importorskip("opentimelineio")
    try:
        timeline = otio.adapters.read_from_string(handoff.edl(HIGHLIGHTS, fps=30, clip_name="stream.mp4"), "cmx_3600", rate=30)
    except otio.exceptions.NotSupportedError:  # the reader is a separate package
        pytest.skip("no CMX3600 adapter")
    clips = list(timeline.video_tracks()[0].find_clips())
    assert [clip.name for clip in clips] == ["stream.mp4"] * 3 and len(timeline.audio_tracks()) == 2
    assert [clip.source_range.start_time.value for clip in clips] == [1950, 12660, 111758]
    assert [clip.source_range.duration.value for clip in clips] == [450, 915, 1042]
    assert timeline.video_tracks()[0].duration().value == 450 + 915 + 1042


def test_marker_list_for_a_timeline_of_the_whole_stream():
    lines = handoff.marker_edl(HIGHLIGHTS, fps=30).splitlines()
    events = [(EVENT.match(line).groups(), lines[i + 1]) for i, line in enumerate(lines) if EVENT.match(line)]
    assert len(events) == 3
    (first, note), (_, second), (last, third) = events
    assert first[3] == first[5] == "01:01:05:00" and first[4] == "01:01:05:01"  # one hour + 1:05, one frame long on the list
    assert note == " |C:ResolveColorPink |M:#03 |D:450"  # ... the marker itself lasts as long as the highlight
    assert second == " |C:ResolveColorPink |M:#02 채팅 급증 (평소의 3.2배) / 반응 12회 |D:915"
    assert last[3] == "02:02:05:08" and third.endswith("|D:1042")
    piped = Highlight(rank=5, start=1.0, end=2.0, peak=1.5, score=1.0, reasons=["a|b"])
    assert "|M:#05 a/b |D:30" in handoff.marker_edl([piped], fps=30, timeline_start=0)  # the field separator cannot be part of a name


def test_files_are_written_with_windows_line_ends(tmp_path):
    out = handoff.write_text(handoff.edl(HIGHLIGHTS, fps=30), tmp_path / "sub" / "cuts.edl")
    data = out.read_bytes()
    assert data.count(b"\r\n") == data.count(b"\n") > 5 and "채팅 급증".encode() in data


# ----------------------------------------------------------------------------- the credit line


def test_credit_is_a_line_of_its_own_for_the_whole_clip():
    cues = [Cue(1.0, 3.0, "こんにちは")]
    text = to_ass(cues, credit="원본:  테스트\n채널", duration=12.5)
    styles = [line for line in text.splitlines() if line.startswith("Style: ")]
    assert [line.split(",")[0] for line in styles] == ["Style: Default", "Style: Credit"]
    credit = styles[1].split(",")
    assert credit[1] == "Noto Sans KR" and int(credit[2]) < int(styles[0].split(",")[2]) and credit[18] == "7"  # its own font, smaller, top left
    assert "Dialogue: 1,0:00:00.00,0:00:12.50,Credit,,0,0,0,,원본: 테스트 채널" in text
    assert "Credit" not in to_ass(cues) and "Credit" not in to_ass(cues, credit="   ")
    # without cues the clip's length has to be given; with them it can be read off the last cue
    assert "0:00:03.00,Credit" in to_ass(cues, credit="Source: X")
    with pytest.raises(ValueError, match="length of the clip"):
        to_ass([], credit="Source: X")
    for name, alignment in CREDIT_POSITIONS.items():
        style = next(line for line in to_ass([], credit="{Source}", credit_position=name, duration=5).splitlines() if line.startswith("Style: Credit"))
        assert style.split(",")[18] == str(alignment)
    assert ",,(Source)" in to_ass([], credit="{Source}", duration=5)  # braces would be read as ASS commands
    low = to_ass([], credit="x", credit_position="bottom-right", duration=5).splitlines()
    high = to_ass([], credit="x", credit_position="top-right", duration=5).splitlines()
    margin = lambda lines: int(next(line for line in lines if line.startswith("Style: Credit")).split(",")[21])  # noqa: E731
    assert margin(low) > margin(high) * 3  # a bottom corner of a vertical clip stays above the Shorts buttons
    with pytest.raises(ValueError, match="Unknown credit position"):
        to_ass([], credit="x", credit_position="middle", duration=5)


# ----------------------------------------------------------------------------- joining clips


def test_concat_command_fits_every_clip_into_one_shape():
    cmd = build_concat_command(["a.mp4", "b.mp4", "c.mp4"], "out.mp4", size=(1081, 1920), durations=[10.0, 0.6, 5.0], has_audio=[True, False, True], fps=30, fade=0.5, ffmpeg="ffmpeg")
    graph = cmd[cmd.index("-filter_complex") + 1].split(";")
    assert cmd.count("-i") == 3 and cmd[-1] == "out.mp4" and "libx264" in cmd and "aac" in cmd
    assert graph[0].startswith("[0:v:0]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p")
    assert "fade=t=in" not in graph[0] and "fade=t=out:st=9.500:d=0.500" in graph[0]  # the first clip opens as it is
    assert graph[1] == "[0:a:0]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,afade=t=out:st=9.500:d=0.500[a0]"
    assert "fade=t=in:st=0:d=0.200" in graph[2] and "fade=t=out:st=0.400:d=0.200" in graph[2]  # a short clip: a third of it at most
    assert graph[3] == "anullsrc=r=48000:cl=stereo,atrim=duration=0.600[a1]"  # silence where a clip has no sound
    assert "fade=t=in" in graph[4] and "fade=t=out" not in graph[4]  # the last clip ends as it is
    assert graph[-1] == "[v0][a0][v1][a1][v2][a2]concat=n=3:v=1:a=1[v][a]"
    plain = build_concat_command(["a.mp4"], "out.webm", size=(640, 360), durations=[3.0], has_audio=[True], format="webm", ffmpeg="ffmpeg")
    assert "fade" not in " ".join(plain) and "libvpx-vp9" in plain and "libopus" in plain
    with pytest.raises(ValueError, match="Nothing to join"):
        build_concat_command([], "out.mp4", size=(2, 2), durations=[], has_audio=[])
    with pytest.raises(ValueError, match="one entry per clip"):
        build_concat_command(["a.mp4"], "out.mp4", size=(2, 2), durations=[1.0, 2.0], has_audio=[True])
    with pytest.raises(ValueError, match="video with sound"):
        build_concat_command(["a.mp4"], "out.gif", size=(2, 2), durations=[1.0], has_audio=[True], format="gif")
    assert ExportOptions(format="mp4").format == "mp4"


@pytest.fixture(scope="module")
def stream(tmp_path_factory):
    """A 40 s test pattern with a tone."""
    video = tmp_path_factory.mktemp("stream") / "stream.mp4"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=320x180:r=30:d=40", "-f", "lavfi", "-i", "sine=frequency=440:duration=40",
         "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(video)],
        check=True,
    )
    return video


SHORT = [
    Highlight(rank=2, start=20.0, end=24.0, peak=22.0, score=5.0, reasons=["채팅 급증"]),
    Highlight(rank=1, start=4.0, end=7.0, peak=5.0, score=9.0, reasons=["스트리머 표시 (!clip)"]),
    Highlight(rank=3, start=30.0, end=33.0, peak=31.0, score=3.0, reasons=[]),
]
SOURCE = SourceInfo(url="https://www.youtube.com/watch?v=abc", title="테스트 방송", channel="테스트 채널", live_status="was_live", availability="public")


@needs_ffmpeg
def test_credit_is_burned_into_a_clip_without_subtitles(stream, tmp_path):
    from PIL import Image

    options = ExportOptions(format="mp4", fps=30, quality=70)
    plain = make_clips(stream, SHORT[1:2], tmp_path / "plain", options=options)[0]
    marked = make_clips(stream, SHORT[1:2], tmp_path / "marked", options=options, credit="Source: Test Channel", credit_position="bottom-right")[0]
    assert plain.subtitles is None and marked.subtitles is not None and "Source: Test Channel" in marked.subtitles.read_text(encoding="utf-8")
    frames = []
    for clip in (plain.path, marked.path):
        still = clip.with_suffix(".png")
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", "1", "-i", str(clip), "-frames:v", "1", str(still)], check=True)
        frames.append(Image.open(still).convert("L"))
    width, height = frames[0].size
    corner = (width // 2, height * 3 // 4, width, height)
    changed = lambda box: sum(abs(a - b) > 40 for a, b in zip(frames[0].crop(box).tobytes(), frames[1].crop(box).tobytes()))  # noqa: E731
    assert changed(corner) > 25, "nothing was drawn in the corner"
    assert changed((0, 0, width // 2, height // 2)) < 5, "the opposite corner changed too"


@needs_ffmpeg
def test_clips_are_joined_in_stream_order_with_chapters(stream, tmp_path):
    out = tmp_path / "clips"
    options = ExportOptions(format="mp4", fps=30, quality=70)
    make_clips(stream, SHORT, out, options=options, source=SOURCE)
    made = compile_folder(out, fade=0.3)
    assert made.path == out / "compilation.mp4" and [part[2].name for part in made.parts] == ["clip_01.mp4", "clip_02.mp4", "clip_03.mp4"]
    info = probe(made.path)
    assert info.duration == pytest.approx(10.0, abs=0.4) and info.has_audio and (info.width, info.height) == (320, 180)
    assert made.duration == pytest.approx(info.duration, abs=0.4)
    notes = made.notes.read_text(encoding="utf-8")
    assert notes.splitlines()[1:4] == ["테스트 방송", "https://www.youtube.com/watch?v=abc", "테스트 채널"]  # the source first, as a description needs it
    assert "0:00 스트리머 표시 (!clip)\n0:03 채팅 급증\n0:07 #03\n" in notes
    assert "0:03 https://www.youtube.com/watch?v=abc&t=20" in notes  # where each part is in the original stream

    best = compile_folder(out / "clips.json", tmp_path / "best.webm", order="rank", ranks={1, 2}, notes=False)
    assert [part[2].name for part in best.parts] == ["clip_01.mp4", "clip_02.mp4"] and best.notes is None and probe(best.path).codec == "vp9"
    with pytest.raises(FileNotFoundError, match="No clips.json"):
        compile_folder(tmp_path)
    with pytest.raises(ValueError, match="lists no clips"):
        compile_folder(out, ranks={9})


@needs_ffmpeg
def test_clips_of_another_shape_and_without_sound_are_joined_too(stream, tmp_path):
    silent = tmp_path / "silent.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=180x320:r=15:d=2", "-pix_fmt", "yuv420p", str(silent)], check=True)
    part = tmp_path / "part.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-t", "3", "-i", str(stream), "-c", "copy", str(part)], check=True)
    made = compile_clips([part, silent], tmp_path / "both.mp4", labels=["가로", "세로\n무음"])
    info = probe(made.path)
    assert (info.width, info.height) == (320, 180) and info.fps == pytest.approx(30, abs=0.5) and info.has_audio  # the first clip sets the shape
    assert info.duration == pytest.approx(5.0, abs=0.3)
    assert made.chapters() == "0:00 가로\n0:03 세로 무음\n" and made.notes.read_text(encoding="utf-8") == made.chapters()
    tall = compile_clips([part, silent], tmp_path / "tall.mp4", size=(180, 320), fps=15, notes=False)
    assert (probe(tall.path).width, probe(tall.path).height) == (180, 320) and tall.notes is None
    with pytest.raises(ValueError, match="saved as"):
        compile_clips([part], tmp_path / "x.gif")
    with pytest.raises(ValueError, match="one of the clips"):
        compile_clips([part, silent], part)
    with pytest.raises(FileNotFoundError, match="Clip not found"):
        compile_clips([tmp_path / "nothing.mp4"], tmp_path / "x.mp4")
    with pytest.raises(ValueError, match="1 labels for 2"):
        compile_clips([part, silent], tmp_path / "x.mp4", labels=["a"])
    with pytest.raises(ValueError, match="No clips"):
        compile_clips([], tmp_path / "x.mp4")


# ----------------------------------------------------------------------------- the commands


def saved(tmp_path, highlights=SHORT):
    path = tmp_path / "highlights.json"
    path.write_text(json.dumps({"highlights": [h.to_dict() for h in highlights]}, ensure_ascii=False), encoding="utf-8")
    return path


def test_timeline_command_prints_the_timestamps(tmp_path, capsys):
    assert main(["timeline", str(saved(tmp_path))]) == 0
    assert capsys.readouterr().out == "0:04 스트리머 표시 (!clip)\n0:20 채팅 급증\n0:30 #03\n"
    assert main(["timeline", str(saved(tmp_path)), "--order", "rank", "--ranks", "2,3"]) == 0
    assert capsys.readouterr().out == "0:20 채팅 급증\n0:30 #03\n"
    assert main(["timeline", str(saved(tmp_path)), "--ranks", "9"]) == 0
    assert "no highlights" in capsys.readouterr().out
    assert main(["timeline", str(saved(tmp_path)), "--edl", str(tmp_path / "x.edl")]) == 1  # no video, no rate: no timecode
    assert "frame rate" in capsys.readouterr().err and not (tmp_path / "x.edl").exists()


def test_timeline_command_writes_the_files_with_a_given_rate(tmp_path, capsys):
    edl, markers, times = tmp_path / "out" / "cuts.edl", tmp_path / "out" / "markers.edl", tmp_path / "out" / "times.txt"
    assert main(["timeline", str(saved(tmp_path)), "--fps", "60", "--title", "내 방송", "--edl", str(edl), "--markers", str(markers), "--timestamps", str(times)]) == 0
    out = capsys.readouterr().out
    assert "(3 cuts, 60 fps)" in out and "(3 markers, 60 fps)" in out and "times  " in out and "0:04" not in out
    text = edl.read_text(encoding="utf-8")
    assert text.startswith("TITLE: 내 방송") and "00:00:04:00 00:00:07:00 01:00:00:00 01:00:03:00" in text and "FROM CLIP NAME" not in text
    assert "|D:180" in markers.read_text(encoding="utf-8") and times.read_text(encoding="utf-8").count("\n") == 3


@needs_ffmpeg
def test_timeline_command_reads_name_and_rate_from_the_video(stream, tmp_path, capsys):
    edl = tmp_path / "cuts.edl"
    assert main(["timeline", str(saved(tmp_path)), "--video", str(stream), "--edl", str(edl)]) == 0
    assert "(3 cuts, 30 fps)" in capsys.readouterr().out
    text = edl.read_text(encoding="utf-8")
    assert text.startswith("TITLE: stream") and text.count("* FROM CLIP NAME: stream.mp4") == 3 and "AA/V" in text


@needs_ffmpeg
def test_clips_command_with_credit_and_compilation(stream, tmp_path, capsys):
    out = tmp_path / "clips"
    base = ["clips", str(stream), "--highlights", str(saved(tmp_path)), "-o", str(out), "--layout", "none", "--quality", "70"]
    assert main([*base, "--credit", "auto"]) == 1
    assert "--credit auto needs the name of the original channel" in capsys.readouterr().err
    assert main([*base, "--credit", "auto", "--channel", "테스트 채널", "--source-url", SOURCE.url, "--compile", "--fade", "0.2"]) == 0
    printed = capsys.readouterr().out
    assert "joined " in printed and "(3 clips, 0:00:10)" in printed and "notes  " in printed
    assert "Credit,,0,0,0,,원본: 테스트 채널" in (out / "clip_01.ass").read_text(encoding="utf-8")
    assert probe(out / "compilation.mp4").duration == pytest.approx(10.0, abs=0.4)
    assert (out / "compilation.txt").read_text(encoding="utf-8").count("&t=") == 3


@needs_ffmpeg
def test_compile_command(stream, tmp_path, capsys):
    out = tmp_path / "clips"
    make_clips(stream, SHORT, out, options=ExportOptions(format="mp4", fps=30, quality=70))
    assert main(["compile", str(out), "--order", "rank", "--ranks", "1,3", "-o", str(tmp_path / "two.mp4")]) == 0
    assert "(2 clips, 0:00:06)" in capsys.readouterr().out and (tmp_path / "two.txt").read_text(encoding="utf-8").startswith("0:00 스트리머 표시 (!clip)\n0:03 #03")
    files = [str(out / "clip_03.mp4"), str(out / "clip_01.mp4")]
    assert main(["compile", *files, "-o", str(tmp_path / "given.mp4"), "--size", "160x90", "--fps", "15"]) == 0
    info = probe(tmp_path / "given.mp4")
    assert (info.width, info.height) == (160, 90) and info.fps == pytest.approx(15, abs=0.5)
    assert (tmp_path / "given.txt").read_text(encoding="utf-8") == "0:00 clip_03\n0:03 clip_01\n"  # files: the order given, named after themselves
    capsys.readouterr()
    assert main(["compile", *files]) == 1
    assert "needs a name for the result" in capsys.readouterr().err
    assert main(["compile", *files, "-o", str(tmp_path / "x.mp4"), "--ranks", "1"]) == 1
    assert "go with a clips folder" in capsys.readouterr().err


@needs_ffmpeg
def test_auto_leaves_a_cut_list_and_timestamps_beside_the_highlights(stream, tmp_path, capsys):
    rows = ["time,author,text"] + [f"{t}.5,u{t % 7},hi" for t in range(0, 40, 2)] + [f"{20 + i * 0.05:.2f},r{i},lol" for i in range(60)]
    chat = tmp_path / "chat.csv"
    chat.write_text("\n".join(rows), encoding="utf-8")
    out = tmp_path / "auto"
    assert main(["auto", str(stream), "--chat", str(chat), "-o", str(out), "--layout", "none", "--min-length", "5", "--max-length", "8", "--quality", "60"]) == 0
    printed = capsys.readouterr().out
    assert "edl    " in printed and "times  " in printed
    cuts = (out / "highlights.edl").read_text(encoding="utf-8")
    found = json.loads((out / "highlights.json").read_text(encoding="utf-8"))["highlights"]
    assert len(found) >= 1 and cuts.count("* FROM CLIP NAME: stream.mp4") == len(found)
    assert (out / "timestamps.txt").read_text(encoding="utf-8").count("\n") == len(found)
