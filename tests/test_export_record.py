from __future__ import annotations

import sys
import time

import numpy as np
import pytest
from PIL import Image

from stream2clip.capture import ArrayBackend, draw_cursor
from stream2clip.chroma import colorkey_alpha
from stream2clip.export import export, probe
from stream2clip.ffmpeg import ExportOptions
from stream2clip.geometry import Region
from stream2clip.record import Recorder

from .conftest import moving_square, needs_ffmpeg

pytestmark = needs_ffmpeg


def frames_of(path) -> list[Image.Image]:
    with Image.open(path) as img:
        out = []
        for i in range(getattr(img, "n_frames", 1)):
            img.seek(i)
            out.append(img.convert("RGBA").copy())
        return out


@pytest.mark.parametrize("fmt", ["gif", "webp", "mp4", "webm", "mov", "apng"])
def test_export_formats(green_screen_video, tmp_path, fmt):
    out = export(green_screen_video, tmp_path / f"clip.{fmt}", ExportOptions(format=fmt, fps=10, width=80))
    if fmt == "webp":  # ffprobe cannot decode animated WebP; Pillow can
        frames = frames_of(out)
        assert frames[0].size == (80, 60) and len(frames) >= 15
        return
    info = probe(out)
    assert info.width == 80
    if fmt in ("mp4", "webm", "mov"):
        assert info.has_audio


def test_trim_and_crop(green_screen_video, tmp_path):
    opts = ExportOptions(format="mp4", start=0.5, end=1.5, crop=Region(0, 0, 100, 60), fps=10)
    info = probe(export(green_screen_video, tmp_path / "t.mp4", opts), count_frames=True)
    assert (info.width, info.height) == (100, 60)
    assert info.duration is not None and 0.8 <= info.duration <= 1.3


@pytest.mark.parametrize("fmt", ["gif", "webp", "apng"])
def test_transparent_background_export(green_screen_video, tmp_path, fmt):
    opts = ExportOptions(format=fmt, fps=5, transparent=True, key_color="#00FF00", similarity=0.15)
    frames = frames_of(export(green_screen_video, tmp_path / f"t.{fmt}", opts))
    assert len(frames) >= 5
    first, last = frames[0], frames[-1]
    assert first.getpixel((150, 5))[3] == 0  # background keyed out
    assert first.getpixel((20, 60))[3] == 255  # red square at x=0..40 on frame 0
    # The square moved away: its old position must be transparent again (no GIF ghosting).
    assert last.getpixel((20, 60))[3] == 0


def test_transparent_webm_has_alpha(green_screen_video, tmp_path):
    out = export(green_screen_video, tmp_path / "a.webm", ExportOptions(format="webm", transparent=True))
    import json
    import subprocess

    meta = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-print_format", "json", str(out)], capture_output=True, check=True
    )
    tags = json.loads(meta.stdout)["streams"][0].get("tags", {})
    assert tags.get("alpha_mode") == "1"


def test_numpy_colorkey_matches_ffmpeg(tmp_path):
    rng = np.random.default_rng(0)
    rgb = rng.integers(0, 256, size=(32, 32, 3), dtype=np.uint8)
    rgb[:8] = (0, 255, 0)
    rgb[8:16] = (40, 220, 30)
    src = tmp_path / "noise.png"
    Image.fromarray(rgb, "RGB").save(src)
    out = tmp_path / "keyed.png"
    import subprocess

    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-vf", "format=rgba,colorkey=0x00FF00:0.2:0.1", "-frames:v", "1", str(out)],
        check=True,
    )
    ff_alpha = np.asarray(Image.open(out).convert("RGBA"))[..., 3].astype(int)
    np_alpha = colorkey_alpha(rgb, "#00FF00", 0.2, 0.1).astype(int)
    assert np.abs(ff_alpha - np_alpha).max() <= 1


def test_recorder_realtime_and_export(tmp_path):
    clock0 = time.monotonic()
    backend = lambda: ArrayBackend(lambda t: moving_square(t))  # noqa: E731
    recorder = Recorder(Region(0, 0, 96, 64), fps=20, backend_factory=backend, max_duration=1.0, output=tmp_path / "rec.mkv")
    recorder.start()
    assert recorder.is_recording
    assert recorder.wait(timeout=10)
    recording = recorder.stop()
    assert time.monotonic() - clock0 < 8
    assert 18 <= recording.frames <= 22
    info = probe(recording.path, count_frames=True)
    assert (info.width, info.height) == (96, 64) and info.frames == recording.frames

    gif = recording.export(tmp_path / "rec.gif", ExportOptions(format="gif", fps=10, transparent=True))
    frames = frames_of(gif)
    assert frames[0].getpixel((90, 5))[3] == 0 and frames[0].getpixel((8, 28))[3] == 255
    mp4 = recording.export(tmp_path / "rec.mp4", ExportOptions(format="mp4", fps=None))
    assert probe(mp4).width == 96


def test_recorder_stop_early(tmp_path):
    recorder = Recorder(Region(0, 0, 32, 32), fps=10, backend_factory=lambda: ArrayBackend(np.zeros((32, 32, 3), np.uint8)))
    recorder.start()
    time.sleep(0.35)
    recording = recorder.stop()
    assert recording.frames >= 2 and recording.path.exists()
    recording.discard()
    assert not recording.path.exists()


def test_recorder_reports_ffmpeg_failure(tmp_path):
    recorder = Recorder(Region(0, 0, 32, 32), fps=10, backend_factory=lambda: ArrayBackend(np.zeros((32, 32, 3), np.uint8)), ffmpeg="/nonexistent/ffmpeg")
    with pytest.raises(RuntimeError, match="failed"):
        recorder.start()


def test_cursor_overlay_clips_at_edges():
    frame = np.zeros((20, 20, 4), np.uint8)
    frame[..., 3] = 255
    out = draw_cursor(frame, -3, -3)
    assert out.shape == frame.shape and out.max() > 0
    assert draw_cursor(frame, 50, 50) is frame


def test_cursor_scales_with_display_scaling():
    def arrow_pixels(scale):
        frame = np.zeros((80, 80, 4), np.uint8)
        frame[..., 3] = 255
        return int((draw_cursor(frame, 10, 10, scale=scale)[..., 0] > 200).sum())

    assert arrow_pixels(1.5) > arrow_pixels(1.25) > arrow_pixels(1.0) > 0


def test_recorder_draws_cursor_at_scale():
    seen = {}

    def keep(frame):
        seen.setdefault("frame", frame.copy())
        return frame

    gray = np.full((300, 200, 3), 100, np.uint8)  # a "screen"; the recorded region is offset inside it
    for scale in (1.0, 2.0):
        seen.clear()
        recorder = Recorder(
            Region(100, 200, 60, 60), fps=10, backend_factory=lambda: ArrayBackend(gray), cursor=lambda: (110, 210), cursor_scale=scale, frame_filter=keep, max_duration=0.2
        )
        recorder.start()
        recorder.wait(timeout=10)
        recorder.stop().discard()
        arrow = np.argwhere(np.abs(seen["frame"][..., 0].astype(int) - 100) > 60)  # white fill + black outline
        # hotspot stays at the cursor position (region-local 10, 10); only the size changes
        assert arrow.min(axis=0).tolist() == pytest.approx([11, 11], abs=2)
        assert arrow.max(axis=0)[0] - arrow.min(axis=0)[0] == pytest.approx(18 * scale, abs=3)


def test_source_alpha_is_preserved_without_keying(tmp_path):
    def frame(t):
        f = np.zeros((32, 48, 4), np.uint8)
        f[8:24, 8:24] = (255, 79, 139, 255)  # opaque square, everything else alpha 0
        return f

    recorder = Recorder(Region(0, 0, 48, 32), fps=10, backend_factory=lambda: ArrayBackend(frame), max_duration=0.5)
    recorder.start()
    recorder.wait(timeout=10)
    recording = recorder.stop()
    gif = recording.export(tmp_path / "a.gif", ExportOptions(format="gif", transparent=True, key_color=None))
    first = frames_of(gif)[0]
    assert first.getpixel((2, 2))[3] == 0 and first.getpixel((16, 16))[3] == 255
    webm = recording.export(tmp_path / "a.webm", ExportOptions(format="webm", transparent=True, key_color=None))
    import json
    import subprocess

    meta = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-print_format", "json", str(webm)], capture_output=True, check=True)
    assert json.loads(meta.stdout)["streams"][0].get("tags", {}).get("alpha_mode") == "1"
    recording.discard()


# ----------------------------------------------------------------------------- GPU encoders


def test_mp4_encoder_arguments():
    from stream2clip.ffmpeg import build_concat_command, build_export_command, h264_args

    def video_args(encoder):
        cmd = build_export_command("in.mp4", "out.mp4", ExportOptions(format="mp4", quality=85, encoder=encoder), ffmpeg="ffmpeg")
        return cmd[cmd.index("-c:v") + 1]

    assert [video_args(e) for e in ("libx264", "h264_nvenc", "h264_qsv", "h264_amf")] == ["libx264", "h264_nvenc", "h264_qsv", "h264_amf"]
    assert video_args("auto") == "libx264"  # the builder runs nothing: export() resolves auto
    assert ExportOptions().encoder == "libx264"  # the library stays on the CPU unless asked
    assert h264_args("h264_nvenc", 23)[h264_args("h264_nvenc", 23).index("-cq") + 1] == "23"  # the same quality scale
    with pytest.raises(ValueError, match="encoder"):
        h264_args("h264_vaapi_typo", 23)
    joined = build_concat_command(["a.mp4", "b.mp4"], "c.mp4", size=(1280, 720), durations=[1.0, 1.0], has_audio=[True, True], encoder="h264_qsv", ffmpeg="ffmpeg")
    assert joined[joined.index("-c:v") + 1] == "h264_qsv"


def test_auto_takes_the_first_gpu_encoder_that_works(monkeypatch):
    import subprocess

    export_module = sys.modules["stream2clip.export"]  # the package exports a function of the same name

    tried, works = [], set()

    def run(cmd, **kwargs):
        encoder = cmd[cmd.index("-c:v") + 1]
        tried.append(encoder)
        return subprocess.CompletedProcess(cmd, 0 if encoder in works else 1)

    monkeypatch.setattr(export_module.subprocess, "run", run)
    for working, expected in (({"h264_qsv", "h264_amf"}, "h264_qsv"), (set(), "libx264")):
        works.clear()
        works.update(working)
        export_module.h264_encoder.cache_clear()
        tried.clear()
        assert export_module.h264_encoder("ffmpeg") == expected
    assert tried == ["h264_nvenc", "h264_qsv", "h264_amf"]  # listed is not enough: each is tried on a few frames
    export_module.h264_encoder.cache_clear()
    works.clear()
    works.add("h264_nvenc")
    assert export_module.resolve_encoder(ExportOptions(format="mp4", encoder="auto"), ffmpeg="ffmpeg").encoder == "h264_nvenc"
    assert export_module.resolve_encoder(ExportOptions(format="webm", encoder="auto")).encoder == "auto"  # MP4 only
    export_module.h264_encoder.cache_clear()


def test_a_failing_gpu_encoder_falls_back_to_the_cpu(monkeypatch, tmp_path):
    export_module = sys.modules["stream2clip.export"]  # the package exports a function of the same name

    ran = []

    def run(cmd, timeout=None):
        encoder = cmd[cmd.index("-c:v") + 1]
        ran.append(encoder)
        if encoder != "libx264":
            raise export_module.FFmpegError(cmd, 1, "Cannot load nvcuda.dll")

    monkeypatch.setattr(export_module, "run_ffmpeg", run)
    export(tmp_path / "in.mp4", tmp_path / "out.mp4", ExportOptions(format="mp4", encoder="h264_nvenc", audio=False))
    assert ran == ["h264_nvenc", "libx264"]
    ran.clear()
    with pytest.raises(export_module.FFmpegError):  # the CPU encoder failing is a real error
        monkeypatch.setattr(export_module, "run_ffmpeg", lambda cmd, timeout=None: (_ for _ in ()).throw(export_module.FFmpegError(cmd, 1, "bad input")))
        export(tmp_path / "in.mp4", tmp_path / "out.mp4", ExportOptions(format="mp4", encoder="libx264", audio=False))


def test_cli_encoder_choice(capsys):
    from stream2clip.cli import main

    for choice, name in (("cpu", "libx264"), ("qsv", "h264_qsv"), ("nvenc", "h264_nvenc"), ("amf", "h264_amf")):
        assert main(["convert", "vod.mp4", "-o", "clip.mp4", "--encoder", choice, "--print-command"]) == 0
        assert f"-c:v {name}" in capsys.readouterr().out
