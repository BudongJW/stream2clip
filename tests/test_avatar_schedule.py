"""An avatar video with its own transparency, the avatar video in the highlights window, scheduled uploads."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest

from stream2clip.cli import main
from stream2clip.export import FFmpegError, export, grab_frames, has_alpha
from stream2clip.ffmpeg import ExportOptions, avatar_decoder_args, build_export_command
from stream2clip.layouts import VerticalLayout
from stream2clip.upload import scheduled_time, video_resource

from .conftest import needs_ffmpeg

BLUE, MAGENTA = (0, 0, 255), (255, 0, 255)


def near(pixel, colour, tolerance=45):
    return all(abs(int(a) - b) <= tolerance for a, b in zip(pixel[:3], colour))


@pytest.fixture
def game(tmp_path):
    out = tmp_path / "game.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=0x0000FF:s=320x180:r=10:d=2", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                    "-c:v", "libx264", "-qp", "0", "-pix_fmt", "yuv444p", "-c:a", "aac", "-shortest", str(out)], check=True)
    return out


@pytest.fixture
def green_avatar(tmp_path):
    out = tmp_path / "avatar_green.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=0x00FF00:s=120x160:r=10:d=2",
                    "-vf", "drawbox=x=30:y=40:w=60:h=120:color=0xFF00FF:t=fill", "-c:v", "libx264", "-qp", "0", "-pix_fmt", "yuv444p", str(out)], check=True)
    return out


# --------------------------------------------------------------------------- transparency of the avatar video


def test_webm_transparency_needs_the_libvpx_decoder():
    keyed = VerticalLayout("pip", avatar_source="avatar.webm")
    own = VerticalLayout("pip", avatar_source="Avatar.WEBM", avatar_key=None)
    assert avatar_decoder_args(keyed) == [] and avatar_decoder_args(own) == ["-c:v", "libvpx-vp9"]
    assert avatar_decoder_args(VerticalLayout("pip", avatar_source="avatar.mov", avatar_key=None)) == []
    cmd = build_export_command("game.mp4", "out.mp4", ExportOptions(format="mp4", start=1.0, end=3.0, layout=own), ffmpeg="ffmpeg")
    second = len(cmd) - 1 - cmd[::-1].index("-i")
    assert cmd[second - 2:second + 2] == ["-c:v", "libvpx-vp9", "-i", "Avatar.WEBM"]


@needs_ffmpeg
def test_transparent_avatar_videos_are_recognised_and_used_as_they_are(game, green_avatar, tmp_path, capsys):
    assert not has_alpha(green_avatar) and not has_alpha(game)
    # The same avatar with its green removed, saved the two ways streamers get an alpha recording.
    webm = export(green_avatar, tmp_path / "avatar.webm", ExportOptions(format="webm", fps=10, transparent=True, key_color="#00FF00"))
    mov = export(green_avatar, tmp_path / "avatar.mov", ExportOptions(format="mov", fps=10, transparent=True, key_color="#00FF00"))
    assert has_alpha(webm) and has_alpha(mov)
    with pytest.raises(FFmpegError):
        has_alpha(tmp_path / "missing.mp4")

    for avatar in (webm, mov):
        layout = VerticalLayout("pip", 180, 320, avatar_source=avatar, avatar_key=None, corner="bottom-left", inset=0.5)
        frame = grab_frames(export(game, tmp_path / f"pip_{avatar.suffix[1:]}.mp4", ExportOptions(format="mp4", fps=10, layout=layout)), [1.0])[0]
        assert near(frame[280, 52], MAGENTA), avatar.name  # the figure ...
        assert near(frame[200, 12], BLUE) and near(frame[300, 12], BLUE), avatar.name  # ... and the game through what is transparent

    highlights = tmp_path / "h.json"
    highlights.write_text(json.dumps({"highlights": [{"rank": 1, "start": 0.2, "end": 1.6, "score": 3}]}), encoding="utf-8")
    common = ["clips", str(game), "--highlights", str(highlights), "--layout", "pip", "--corner", "bottom-left", "--inset", "0.5", "--size", "180x320", "--fps", "10"]
    assert main([*common, "--avatar-video", str(webm), "-o", str(tmp_path / "auto_alpha")]) == 0
    assert "its own transparency is used" in capsys.readouterr().out
    frame = grab_frames(tmp_path / "auto_alpha" / "clip_01.mp4", [0.5])[0]
    assert near(frame[280, 52], MAGENTA) and near(frame[200, 12], BLUE)
    assert main([*common, "--avatar-video", str(green_avatar), "-o", str(tmp_path / "auto_green")]) == 0
    assert "#00FF00 is removed" in capsys.readouterr().out
    frame = grab_frames(tmp_path / "auto_green" / "clip_01.mp4", [0.5])[0]
    assert near(frame[280, 52], MAGENTA) and near(frame[200, 12], BLUE)


# --------------------------------------------------------------------------- the highlights window


@needs_ffmpeg
def test_avatar_video_in_the_highlights_window(game, green_avatar, tmp_path):
    pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from stream2clip.geometry import Region
    from stream2clip.gui.app import create_app
    from stream2clip.gui.highlights import HighlightsWindow

    create_app([])
    window = HighlightsWindow()
    window.dialogs = False
    try:
        window.layout_combo.setCurrentIndex(window.layout_combo.findData("blur"))
        assert not window.avatar_video_edit.isEnabled()
        window.layout_combo.setCurrentIndex(window.layout_combo.findData("pip"))
        assert window.avatar_video_edit.isEnabled() and window.avatar_video_button.isEnabled()
        with pytest.raises(ValueError, match="아바타 위치 또는 아바타 영상"):
            window.layout_choice()
        window.avatar_video_edit.setText(str(tmp_path / "missing.mp4"))
        with pytest.raises(ValueError, match="찾을 수 없습니다"):
            window.layout_choice()
        window.avatar_video_edit.setText(str(green_avatar))
        layout = window.layout_choice()  # no box in the stream is needed now
        assert layout.kind == "pip" and layout.uses_avatar_video and layout.avatar is None and layout.avatar_key == "#00FF00"
        window.avatar_edit.setText("10,20,60,80")  # with a box as well: the part of the avatar video to use
        assert window.layout_choice().avatar == Region(10, 20, 60, 80)
        alpha = export(green_avatar, tmp_path / "avatar.webm", ExportOptions(format="webm", fps=10, transparent=True, key_color="#00FF00"))
        window.avatar_edit.clear()
        window.avatar_video_edit.setText(str(alpha))
        assert window.layout_choice().avatar_key is None  # a transparent recording is used as it is
        frame = grab_frames(game, [0.5], layout=window.layout_choice())[0]  # what the preview draws
        assert frame.shape == (1920, 1080, 4)
        window.remember()
        again = HighlightsWindow()
        assert again.avatar_video_edit.text() == str(alpha)
        again.close()
    finally:
        window.close()


# --------------------------------------------------------------------------- scheduled uploads


NOW = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)


def test_scheduled_time_reads_local_and_zoned_times():
    assert scheduled_time("2026-12-24T18:00:00+09:00") == datetime(2026, 12, 24, 9, 0, tzinfo=timezone.utc)
    assert scheduled_time(datetime(2026, 12, 24, 9, 0, tzinfo=timezone.utc)).hour == 9
    local = datetime(2026, 12, 24, 18, 0)
    assert scheduled_time("2026-12-24 18:00") == local.astimezone(timezone.utc) == scheduled_time(local)  # no zone: the local time
    with pytest.raises(ValueError, match="Not a date and time"):
        scheduled_time("tomorrow evening")


def test_a_scheduled_video_is_private_and_carries_the_time():
    body = video_resource("제목", publish_at="2026-12-24T18:00:00+09:00", now=NOW)
    assert body["status"]["privacyStatus"] == "private" and body["status"]["publishAt"] == "2026-12-24T09:00:00Z"
    assert "publishAt" not in video_resource("제목")["status"] and "publishAt" not in video_resource("제목", publish_at="")["status"]
    with pytest.raises(ValueError, match="leave the privacy at private"):
        video_resource("제목", privacy="public", publish_at=NOW + timedelta(days=1), now=NOW)
    with pytest.raises(ValueError, match="not in the future"):
        video_resource("제목", publish_at=NOW - timedelta(minutes=1), now=NOW)
    with pytest.raises(ValueError, match="not in the future"):
        video_resource("제목", publish_at="2020-01-01 00:00")


def test_upload_command_schedules(tmp_path, capsys):
    later = (datetime.now() + timedelta(days=2)).replace(second=0, microsecond=0)
    assert main(["upload", "clip.mp4", "--title", "t", "--publish-at", later.strftime("%Y-%m-%d %H:%M"), "--dry-run"]) == 0
    sent = json.loads(capsys.readouterr().out.split("dry run")[0])
    assert sent["status"] == {"privacyStatus": "private", "selfDeclaredMadeForKids": False, "publishAt": later.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    assert main(["upload", "clip.mp4", "--title", "t", "--privacy", "public", "--publish-at", later.strftime("%Y-%m-%d %H:%M"), "--dry-run"]) == 1
    assert "private" in capsys.readouterr().err


def test_upload_dialog_schedules(tmp_path):
    pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QDateTime

    from stream2clip.gui.app import create_app
    from stream2clip.gui.upload import UploadDialog

    create_app([])
    dialog = UploadDialog(str(tmp_path / "clip.mp4"), title="제목")
    dialog.dialogs = False
    try:
        assert not dialog.schedule_edit.isEnabled() and "publishAt" not in dialog.resource()["status"]
        dialog.privacy_combo.setCurrentIndex(dialog.privacy_combo.findData("public"))
        dialog.schedule_check.setChecked(True)
        assert dialog.schedule_edit.isEnabled() and dialog.privacy_combo.currentData() == "private" and not dialog.privacy_combo.isEnabled()
        when = datetime.now().replace(second=0, microsecond=0) + timedelta(days=3)
        dialog.schedule_edit.setDateTime(QDateTime(when.year, when.month, when.day, when.hour, when.minute, 0))
        status = dialog.resource()["status"]
        assert status["privacyStatus"] == "private" and status["publishAt"] == when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        past = datetime.now() - timedelta(days=1)
        dialog.schedule_edit.setDateTime(QDateTime(past.year, past.month, past.day, past.hour, past.minute, 0))
        with pytest.raises(ValueError, match="not in the future"):
            dialog.resource()
        dialog.schedule_check.setChecked(False)
        assert dialog.privacy_combo.isEnabled() and "publishAt" not in dialog.resource()["status"]
    finally:
        dialog.close()
