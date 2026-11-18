from __future__ import annotations

import numpy as np
import pytest

from stream2clip.chroma import apply_colorkey, colorkey_alpha, colorkey_filter
from stream2clip.color import PALETTE, parse_color, to_hex
from stream2clip.ffmpeg import ExportOptions, RawVideoInput, build_export_command, build_video_filter
from stream2clip.frames import ensure_rgba
from stream2clip.geometry import Region


class TestRegion:
    def test_parse_formats(self):
        assert Region.parse("10,20,300,200") == Region(10, 20, 300, 200)
        assert Region.parse("300x200+10+20") == Region(10, 20, 300, 200)
        with pytest.raises(ValueError):
            Region.parse("nope")

    def test_from_points_normalizes(self):
        assert Region.from_points(50, 40, 10, 5) == Region(10, 5, 40, 35)

    def test_clamp_and_intersect(self):
        r = Region(-10, -10, 50, 50)
        assert r.clamp(30, 30) == Region(0, 0, 30, 30)
        assert Region(100, 100, 5, 5).clamp(30, 30) is None

    def test_even_and_scale(self):
        assert Region(0, 0, 101, 51).even() == Region(0, 0, 100, 50)
        assert Region(10, 10, 20, 20).scale(1.5) == Region(15, 15, 30, 30)


class TestColor:
    def test_parse(self):
        assert parse_color("#F00") == (255, 0, 0, 255)
        assert parse_color("0x00ff00") == (0, 255, 0, 255)
        assert parse_color("#11223344") == (0x11, 0x22, 0x33, 0x44)
        assert parse_color("red") == parse_color(PALETTE["red"])
        assert to_hex((1, 2, 3)) == "#010203"


class TestFrames:
    def test_ensure_rgba_from_rgb_and_gray(self):
        assert ensure_rgba(np.zeros((4, 5, 3), np.uint8)).shape == (4, 5, 4)
        assert ensure_rgba(np.zeros((4, 5), np.uint8)).shape == (4, 5, 4)
        assert ensure_rgba(np.ones((2, 2, 3), np.float32))[0, 0, 0] == 255


class TestChroma:
    def test_hard_key(self):
        frame = np.array([[[0, 255, 0], [255, 0, 0], [10, 250, 10]]], dtype=np.uint8)
        alpha = colorkey_alpha(frame, "#00FF00", similarity=0.1)
        assert alpha.tolist() == [[0, 255, 0]]

    def test_blend_is_soft(self):
        frame = np.array([[[0, 255, 0], [60, 200, 60], [255, 0, 255]]], dtype=np.uint8)
        alpha = colorkey_alpha(frame, "#00FF00", similarity=0.05, blend=0.3)
        assert alpha[0, 0] == 0 and 0 < alpha[0, 1] < 255 and alpha[0, 2] == 255

    def test_apply_keeps_existing_alpha(self):
        frame = np.array([[[255, 0, 0, 100]]], dtype=np.uint8)
        assert apply_colorkey(frame, "#00FF00")[0, 0, 3] == 100

    def test_filter_string(self):
        assert colorkey_filter("#00ff00", 0.12, 0) == "colorkey=0x00FF00:0.12:0"
        with pytest.raises(ValueError):
            colorkey_filter("#00ff00", 0, 0)


class TestFFmpegBuilders:
    def test_mp4_rejects_transparency(self):
        with pytest.raises(ValueError, match="transparency"):
            ExportOptions(format="mp4", transparent=True)

    def test_gif_graph_uses_palette(self):
        graph = build_video_filter(ExportOptions(format="gif", fps=12, width=320))
        assert graph.startswith("[0:v]fps=12,scale=320:-1:flags=lanczos,split[s0][s1]")
        assert "palettegen" in graph and graph.endswith("[v]")

    def test_transparent_gif_reserves_transparency(self):
        graph = build_video_filter(ExportOptions(format="gif", transparent=True, key_color="#00FF00"))
        assert "colorkey=0x00FF00" in graph and "reserve_transparent=1" in graph

    def test_crop_scale_order_and_even_sizes(self):
        opts = ExportOptions(format="mp4", crop=Region(10, 20, 101, 99), width=301)
        graph = build_video_filter(opts)
        assert graph.index("crop=101:99:10:20") < graph.index("scale=300:-2")
        assert graph.endswith("format=yuv420p[v]")

    def test_webp_alpha_pixfmt(self):
        assert build_video_filter(ExportOptions(format="webp", transparent=True)).endswith("format=yuva420p[v]")

    def test_command_with_trim_and_audio(self):
        cmd = build_export_command("in.mp4", "out.mp4", ExportOptions(format="mp4", start=5, end=12.5), ffmpeg="ffmpeg")
        assert cmd[:2] == ["ffmpeg", "-hide_banner"]
        assert cmd[cmd.index("-ss") + 1] == "5.000" and cmd[cmd.index("-t") + 1] == "7.500"
        assert "0:a:0?" in cmd and cmd[-1] == "out.mp4"

    def test_gif_has_no_audio(self):
        cmd = build_export_command("in.mp4", "out.gif", ExportOptions(format="gif"), ffmpeg="ffmpeg")
        assert "-an" in cmd and "-loop" in cmd

    def test_raw_input(self):
        cmd = build_export_command(None, "o.webp", ExportOptions(format="webp"), raw_input=RawVideoInput(64, 48, 15), ffmpeg="ffmpeg")
        assert cmd[cmd.index("-s") + 1] == "64x48" and cmd[cmd.index("-i") + 1] == "-"

    def test_invalid_times(self):
        with pytest.raises(ValueError):
            ExportOptions(start=10, end=5)
