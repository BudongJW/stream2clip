"""Getting ffmpeg in one step and the report of what is on the PC - without the network."""

from __future__ import annotations

import hashlib
import io
import os
import re
import socket
import sys
import zipfile
from pathlib import Path

import pytest

from stream2clip import ffmpeg as ffmpeg_module
from stream2clip import tools
from stream2clip.cli import build_parser, main


class FakeResponse(io.BytesIO):
    """What urlopen returns, as far as download() uses it."""

    def __init__(self, data: bytes, length: bool = True) -> None:
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data))} if length else {}


def serving(data: bytes, seen: list | None = None, **kwargs):
    def opener(url, timeout=None):
        if seen is not None:
            seen.append(url)
        return FakeResponse(data, **kwargs)

    return opener


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def archive_bytes(*, without: tuple[str, ...] = ()) -> bytes:
    """An archive laid out like the gyan.dev build, plus entries that must not end up on the disk."""
    members = {
        "ffmpeg-9.0.2-essentials_build/bin/ffmpeg.exe": b"MZ ffmpeg",
        "ffmpeg-9.0.2-essentials_build/bin/ffprobe.exe": b"MZ ffprobe",
        "ffmpeg-9.0.2-essentials_build/bin/ffplay.exe": b"MZ ffplay",
        "ffmpeg-9.0.2-essentials_build/LICENSE": b"GNU GENERAL PUBLIC LICENSE",
        "ffmpeg-9.0.2-essentials_build/doc/ffmpeg.html": b"<html>",
        "ffmpeg-9.0.2-essentials_build/presets/bin/notes.txt": b"x",
        "../outside.exe": b"MZ outside",
    }
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as bundle:
        for name, content in members.items():
            if not name.endswith(without or ("\0",)):
                bundle.writestr(name, content)
    return data.getvalue()


@pytest.fixture
def no_ffmpeg(monkeypatch):
    """A PC without ffmpeg: nothing in the environment, nothing on PATH, no optional package."""
    monkeypatch.delenv("STREAM2CLIP_FFMPEG", raising=False)
    monkeypatch.delenv("STREAM2CLIP_FFPROBE", raising=False)
    monkeypatch.setattr(ffmpeg_module.shutil, "which", lambda name: None)
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", None)


@pytest.fixture
def pinned(monkeypatch):
    """The pinned build replaced by a small archive; returns (build, archive bytes)."""
    data = archive_bytes()
    build = tools.FfmpegBuild("9.0.2", "https://example.invalid/ffmpeg-9.0.2-essentials_build.zip", sha(data), len(data))
    monkeypatch.setattr(tools, "FFMPEG_BUILD", build)
    monkeypatch.setattr(sys, "platform", "win32")
    return build, data


# ----------------------------------------------------------------------------- download


def test_download_keeps_only_a_file_with_the_expected_checksum(tmp_path):
    data = b"stream2clip" * 20000
    steps = []
    target = tools.download("https://example.invalid/a.zip", tmp_path / "sub" / "a.zip", sha256=sha(data), on_progress=lambda done, total: steps.append((done, total)), opener=serving(data))
    assert target.read_bytes() == data and steps[-1] == (len(data), len(data)) and len(steps) > 1
    assert [p.name for p in target.parent.iterdir()] == ["a.zip"]  # no partial file is left

    with pytest.raises(RuntimeError, match="unexpected checksum"):
        tools.download("https://example.invalid/b.zip", tmp_path / "b.zip", sha256=sha(b"something else"), opener=serving(data))
    assert not (tmp_path / "b.zip").exists() and not (tmp_path / "b.zip.part").exists()


def test_download_takes_https_only_and_can_be_cancelled(tmp_path):
    with pytest.raises(ValueError, match="https"):
        tools.download("http://example.invalid/a.zip", tmp_path / "a.zip", sha256="0" * 64, opener=serving(b"x"))
    data = b"x" * 300_000
    seen = []
    with pytest.raises(tools.DownloadCancelled):
        tools.download("https://example.invalid/a.zip", tmp_path / "a.zip", sha256=sha(data), on_progress=lambda done, total: seen.append(done), cancelled=lambda: len(seen) >= 2, opener=serving(data))
    assert len(seen) == 2 and list(tmp_path.iterdir()) == []
    # without a Content-Length the known size is what progress is measured against
    totals = []
    tools.download("https://example.invalid/a.zip", tmp_path / "a.zip", sha256=sha(data), size=1234, on_progress=lambda done, total: totals.append(total), opener=serving(data, length=False))
    assert set(totals) == {1234}


# ----------------------------------------------------------------------------- the archive


def test_only_the_two_programs_and_the_licence_leave_the_archive(tmp_path):
    archive = tmp_path / "ffmpeg.zip"
    archive.write_bytes(archive_bytes())
    folder = tmp_path / "tools"
    written = tools.extract_ffmpeg(archive, folder)
    assert sorted(p.name for p in written) == ["ffmpeg-LICENSE.txt", "ffmpeg.exe", "ffprobe.exe"]
    assert sorted(p.name for p in folder.iterdir()) == ["ffmpeg-LICENSE.txt", "ffmpeg.exe", "ffprobe.exe"]
    assert (folder / "ffprobe.exe").read_bytes() == b"MZ ffprobe"
    assert not (tmp_path / "outside.exe").exists()  # a path inside the archive never decides where a file goes

    archive.write_bytes(archive_bytes(without=("ffprobe.exe",)))
    with pytest.raises(RuntimeError, match="no ffprobe.exe"):
        tools.extract_ffmpeg(archive, tmp_path / "other")


def test_install_downloads_checks_and_unpacks_where_ffmpeg_is_looked_for(tmp_path, pinned, no_ffmpeg):
    build, data = pinned
    assert not tools.ffmpeg_ready()
    asked = []
    written = tools.install_ffmpeg(opener=serving(data, asked))
    assert asked == [build.url]
    folder = ffmpeg_module.tools_dir()
    assert sorted(p.name for p in folder.iterdir()) == ["ffmpeg-LICENSE.txt", "ffmpeg.exe", "ffprobe.exe"]  # the archive itself is removed
    assert {p.parent for p in written} == {folder}
    assert Path(ffmpeg_module.find_ffmpeg()) == folder / "ffmpeg.exe" and Path(ffmpeg_module.find_ffprobe()) == folder / "ffprobe.exe"
    assert tools.ffmpeg_ready()


def test_install_from_a_file_refuses_anything_but_the_pinned_build(tmp_path, pinned, no_ffmpeg):
    build, data = pinned
    good, other = tmp_path / build.filename, tmp_path / "other.zip"
    good.write_bytes(data)
    other.write_bytes(archive_bytes(without=("ffplay.exe",)))
    with pytest.raises(RuntimeError, match="not the expected ffmpeg 9.0.2 archive"):
        tools.install_ffmpeg(archive=other, folder=tmp_path / "t")
    assert not (tmp_path / "t").exists()
    assert len(tools.install_ffmpeg(archive=good, folder=tmp_path / "t")) == 3
    assert good.is_file()  # a file that was handed over is left alone


def test_there_is_a_download_for_windows_only(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    assert not tools.can_install_ffmpeg()
    with pytest.raises(RuntimeError, match="apt install ffmpeg"):
        tools.install_ffmpeg(folder=tmp_path, opener=serving(b""))
    monkeypatch.setattr(sys, "platform", "darwin")
    assert "brew install ffmpeg" in tools.install_hint()
    monkeypatch.setattr(sys, "platform", "win32")
    assert "stream2clip setup --ffmpeg" in tools.install_hint() and tools.can_install_ffmpeg()


def test_the_pinned_build_is_complete_and_the_texts_agree_with_it():
    build = tools.FFMPEG_BUILD
    assert build.url.startswith("https://github.com/GyanD/codexffmpeg/releases/download/") and build.url.endswith(f"/ffmpeg-{build.version}-essentials_build.zip")
    assert re.fullmatch(r"[0-9a-f]{64}", build.sha256) and build.size > 50_000_000
    assert build.filename == f"ffmpeg-{build.version}-essentials_build.zip" and build.megabytes == round(build.size / 1e6)
    setup = next(a for a in build_parser()._subparsers._group_actions[0].choices["setup"]._actions if "--ffmpeg" in a.option_strings)
    assert f"{build.megabytes} MB" in setup.help  # the size in the help is the size of the pinned build


# ----------------------------------------------------------------------------- where ffmpeg is found


def test_a_fetched_ffmpeg_comes_after_one_beside_the_program_and_before_path(tmp_path, monkeypatch, no_ffmpeg):
    fetched = ffmpeg_module.tools_dir()
    assert str(fetched) == os.environ["STREAM2CLIP_TOOLS_DIR"]  # the tests' own empty folder
    monkeypatch.setattr(ffmpeg_module.shutil, "which", lambda name: f"/usr/bin/{name}")
    assert ffmpeg_module.find_ffmpeg() == "/usr/bin/ffmpeg"
    (fetched / "ffmpeg.exe").write_bytes(b"")
    assert Path(ffmpeg_module.find_ffmpeg()) == fetched / "ffmpeg.exe"  # fetched for this app: wins over whatever is on PATH
    assert ffmpeg_module.find_ffprobe() == "/usr/bin/ffprobe"
    beside = tmp_path / "app"
    beside.mkdir()
    (beside / "ffmpeg.exe").write_bytes(b"")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(beside / "stream2clip.exe"))
    assert Path(ffmpeg_module.find_ffmpeg()) == beside.resolve() / "ffmpeg.exe"
    monkeypatch.setenv("STREAM2CLIP_FFMPEG", "custom-ffmpeg")
    assert ffmpeg_module.find_ffmpeg() == "custom-ffmpeg"
    monkeypatch.delenv("STREAM2CLIP_TOOLS_DIR")
    assert ffmpeg_module.tools_dir() == Path.home() / ".cache" / "stream2clip" / "tools"


def test_the_error_names_the_one_step_fix_on_windows(monkeypatch, no_ffmpeg):
    monkeypatch.setattr(sys, "platform", "win32")
    with pytest.raises(ffmpeg_module.FFmpegNotFoundError, match="stream2clip setup --ffmpeg"):
        ffmpeg_module.find_ffmpeg()
    monkeypatch.setattr(sys, "platform", "linux")
    with pytest.raises(ffmpeg_module.FFmpegNotFoundError, match="ffmpeg.org"):
        ffmpeg_module.find_ffprobe()


# ----------------------------------------------------------------------------- the report


def test_report_says_what_is_missing_and_how_to_get_it(monkeypatch, no_ffmpeg):
    monkeypatch.setattr(sys, "platform", "win32")
    found = {item.key: item for item in tools.components(obs=None)}
    assert list(found)[:2] == ["ffmpeg", "ffprobe"] and "obs" not in found
    assert found["ffmpeg"].state == "missing" and "stream2clip setup --ffmpeg" in found["ffmpeg"].fix
    assert [item.key for item in tools.missing_required(list(found.values()))] == ["ffmpeg", "ffprobe"]
    assert {"yt-dlp", "model", "websocket", "fonts", "asr", "upload"} <= set(found)
    assert all(item.state in ("ok", "missing", "optional", "later") for item in found.values())
    lines = tools.report_lines(list(found.values()))
    assert lines[0].startswith("[없음] ffmpeg: ") and "    해결 방법: stream2clip setup --ffmpeg" in lines[1]
    assert lines[-1] == "필수 구성요소 없음: ffmpeg, ffprobe"

    monkeypatch.setattr(ffmpeg_module.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(tools, "ffmpeg_version", lambda path: "9.0.2")
    found = tools.components(obs=None)
    assert found[0].found and found[0].detail == "/usr/bin/ffmpeg (9.0.2)" and not tools.missing_required(found)
    assert tools.report_lines(found)[-1] == "필수 구성요소 모두 있음"


def test_report_notices_a_listening_obs_port():
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]
        answer = next(item for item in tools.components(obs=("127.0.0.1", port)) if item.key == "obs")
        assert answer.found and f"127.0.0.1:{port}" in answer.detail
    silent = next(item for item in tools.components(obs=("127.0.0.1", port)) if item.key == "obs")  # closed again
    assert silent.state == "optional" and "WebSocket" in silent.fix


def test_ffmpeg_version_reads_the_first_line(monkeypatch, tmp_path):
    class Done:
        stdout = "ffmpeg version 9.0.2-essentials_build-www.gyan.dev Copyright (c) 2000-2026 the FFmpeg developers\nbuilt with gcc\n"

    monkeypatch.setattr(tools.subprocess, "run", lambda *args, **kwargs: Done())
    assert tools.ffmpeg_version("ffmpeg") == "9.0.2-essentials_build-www.gyan.dev"
    monkeypatch.undo()
    assert tools.ffmpeg_version(tmp_path / "missing.exe") is None  # a program that does not run has no version


# ----------------------------------------------------------------------------- the command


def test_setup_command_reports_and_tells_by_its_exit_code(monkeypatch, capsys, no_ffmpeg):
    monkeypatch.setattr(sys, "platform", "win32")
    assert main(["setup", "--no-obs"]) == 1
    out = capsys.readouterr().out
    assert "[없음] ffmpeg" in out and "필수 구성요소 없음: ffmpeg, ffprobe" in out
    assert main(["setup", "--from", "x.zip"]) == 1
    assert "--from and --force go with --ffmpeg" in capsys.readouterr().err


def test_setup_command_installs_ffmpeg_from_the_installers_download(tmp_path, pinned, capsys, no_ffmpeg, monkeypatch):
    build, data = pinned
    archive = tmp_path / build.filename
    archive.write_bytes(data)
    monkeypatch.setattr(tools, "download", lambda *args, **kwargs: pytest.fail("--from must not download"))
    assert main(["setup", "--ffmpeg", "--no-obs", "--from", str(archive)]) == 0  # exactly what the installer runs
    out = capsys.readouterr().out
    folder = ffmpeg_module.tools_dir()
    assert f"저장: {folder / 'ffmpeg.exe'}" in out and "[있음] ffmpeg" in out and "필수 구성요소 모두 있음" in out
    assert (folder / "ffprobe.exe").is_file()

    monkeypatch.setattr(tools, "install_ffmpeg", lambda **kwargs: pytest.fail("already there: nothing is fetched"))
    assert main(["setup", "--ffmpeg", "--no-obs"]) == 0
    assert "ffmpeg 이미 있음" in capsys.readouterr().out


def test_setup_command_downloads_and_shows_progress(pinned, capsys, no_ffmpeg, monkeypatch):
    build, data = pinned
    real = tools.download
    monkeypatch.setattr(tools, "download", lambda url, target, **kwargs: real(url, target, **{**kwargs, "opener": serving(data)}))
    assert main(["setup", "--ffmpeg", "--no-obs"]) == 0
    out = capsys.readouterr().out
    assert f"ffmpeg 9.0.2 내려받는 중 ({build.megabytes} MB): {build.url}" in out and " 100%" in out
    assert tools.ffmpeg_ready()


def test_setup_with_another_archive_is_an_error_not_a_crash(tmp_path, pinned, capsys, no_ffmpeg):
    other = tmp_path / "other.zip"
    other.write_bytes(b"PK not the build")
    assert main(["setup", "--ffmpeg", "--no-obs", "--from", str(other)]) == 1
    assert "not the expected ffmpeg" in capsys.readouterr().err
    assert not tools.ffmpeg_ready()
