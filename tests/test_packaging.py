"""Windows packaging helpers and what the programs do differently when built (frozen)."""

from __future__ import annotations

import importlib.util
import sys
import zipfile
from pathlib import Path

import pytest

from stream2clip import ffmpeg as ffmpeg_module
from stream2clip.cli import main
from stream2clip.sources import ytdlp_command

ROOT = Path(__file__).parents[1]


@pytest.fixture(scope="module")
def build():
    spec = importlib.util.spec_from_file_location("build_windows", ROOT / "packaging" / "build_windows.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_names_and_command(build, tmp_path):
    assert build.project_version() == __import__("stream2clip").__version__
    assert build.archive_name("0.2.0", "AMD64") == "stream2clip-0.2.0-windows-x64"
    assert build.archive_name("1.0", "ARM64") == "stream2clip-1.0-windows-arm64"
    cmd = build.pyinstaller_command(tmp_path / "dist", tmp_path / "work", python="py")
    assert cmd[:3] == ["py", "-m", "PyInstaller"] and cmd[-1].endswith("stream2clip.spec") and Path(cmd[-1]).is_file()
    assert str(tmp_path / "dist") in cmd and "--noconfirm" in cmd
    assert build.bundle_env(False, {})["STREAM2CLIP_BUNDLE"] == "" and build.bundle_env(True, {"A": "1"}) == {"A": "1", "STREAM2CLIP_BUNDLE": "asr"}
    for entry in ("entry_gui.py", "entry_cli.py"):
        assert (ROOT / "packaging" / entry).is_file()


def test_launcher_shims_are_not_copied(build, tmp_path):
    # Chocolatey / Scoop put a small launcher on PATH; copying that instead of ffmpeg ships a broken app.
    suffix = ".exe" if sys.platform == "win32" else ""
    (tmp_path / f"ffmpeg{suffix}").write_bytes(b"x" * 30_000)
    (tmp_path / f"ffprobe{suffix}").write_bytes(b"x" * 30_000)
    with pytest.raises(ValueError, match="shim"):
        build.find_ffmpeg_pair(str(tmp_path))  # a folder is accepted too
    with pytest.raises(ValueError, match="shim"):
        build.find_ffmpeg_pair(str(tmp_path / f"ffmpeg{suffix}"))
    with pytest.raises(FileNotFoundError):
        build.find_ffmpeg_pair(str(tmp_path / "missing" / "ffmpeg.exe"))


def test_icon_choice(build, tmp_path):
    assert build.icon_path().name == "stream2clip.ico" and build.icon_path("kiri").name == "stream2clip_kiri.ico"
    assert build.icon_path("symbol").is_file() and build.icon_path("kiri").is_file()
    mine = tmp_path / "mine.ico"
    mine.write_bytes(b"")
    assert build.icon_path(str(mine)) == mine
    with pytest.raises(FileNotFoundError):
        build.icon_path(str(tmp_path / "nope.ico"))
    assert build.bundle_env(False, {}, icon=mine) == {"STREAM2CLIP_BUNDLE": "", "STREAM2CLIP_ICON": str(mine)}


def test_ffmpeg_is_copied_next_to_the_programs_and_zipped(build, tmp_path, monkeypatch):
    monkeypatch.setattr(build, "SHIM_LIMIT", 4)
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "ffmpeg.exe").write_bytes(b"ffmpeg")
    with pytest.raises(FileNotFoundError, match="ffprobe"):  # both are needed
        build.copy_ffmpeg(str(tools / "ffmpeg.exe"), tmp_path)
    (tools / "ffprobe.exe").write_bytes(b"ffprobe")

    folder = tmp_path / "dist" / "stream2clip"
    folder.mkdir(parents=True)
    (folder / "stream2clip.exe").write_bytes(b"x" * 10)
    copied = build.copy_ffmpeg(str(tools / "ffmpeg.exe"), folder)
    assert sorted(p.name for p in copied) == ["ffmpeg.exe", "ffprobe.exe"] and (folder / "ffprobe.exe").read_bytes() == b"ffprobe"
    assert build.folder_size(folder) == 10 + 6 + 7

    archive = build.make_zip(folder, "stream2clip-0.2.0-windows-x64")
    assert archive.name == "stream2clip-0.2.0-windows-x64.zip"
    with zipfile.ZipFile(archive) as z:  # unpacks into one folder
        assert sorted(z.namelist()) == ["stream2clip/", "stream2clip/ffmpeg.exe", "stream2clip/ffprobe.exe", "stream2clip/stream2clip.exe"] or \
            sorted(n for n in z.namelist() if not n.endswith("/")) == ["stream2clip/ffmpeg.exe", "stream2clip/ffprobe.exe", "stream2clip/stream2clip.exe"]


def test_built_program_prefers_the_ffmpeg_beside_it(tmp_path, monkeypatch):
    monkeypatch.delenv("STREAM2CLIP_FFMPEG", raising=False)
    monkeypatch.delenv("STREAM2CLIP_FFPROBE", raising=False)
    assert ffmpeg_module.app_dir() is None  # running from source
    (tmp_path / "ffmpeg.exe").write_bytes(b"")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "stream2clip-gui.exe"))
    assert ffmpeg_module.app_dir() == tmp_path.resolve()
    assert Path(ffmpeg_module.find_ffmpeg()) == tmp_path.resolve() / "ffmpeg.exe"
    # ffprobe was not shipped: fall back to PATH (or the usual error) rather than a wrong path
    monkeypatch.setattr(ffmpeg_module.shutil, "which", lambda name: f"/usr/bin/{name}")
    assert ffmpeg_module.find_ffprobe() == "/usr/bin/ffprobe"
    monkeypatch.setenv("STREAM2CLIP_FFMPEG", "custom-ffmpeg")  # an explicit setting still wins
    assert ffmpeg_module.find_ffmpeg() == "custom-ffmpeg"


def test_built_program_runs_ytdlp_through_the_command_line_program(tmp_path, monkeypatch):
    monkeypatch.delenv("STREAM2CLIP_YTDLP", raising=False)
    monkeypatch.delenv("STREAM2CLIP_YTDLP_ARGS", raising=False)
    cli_name = "stream2clip.exe" if sys.platform == "win32" else "stream2clip"
    (tmp_path / cli_name).write_bytes(b"")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "stream2clip-gui.exe"))
    assert ytdlp_command(cookies_from_browser="edge") == [str(tmp_path / cli_name), "yt-dlp", "--cookies-from-browser", "edge"]


def test_ytdlp_passthrough(monkeypatch, capsys):
    import types

    seen = {}

    def fake_main(args):
        seen["args"] = args
        raise SystemExit(3)

    monkeypatch.setitem(sys.modules, "yt_dlp", types.SimpleNamespace(main=fake_main))
    assert main(["yt-dlp", "--version", "-o", "x"]) == 3  # not parsed as stream2clip options
    assert seen["args"] == ["--version", "-o", "x"]
    monkeypatch.setitem(sys.modules, "yt_dlp", None)  # not installed
    assert main(["yt-dlp", "--version"]) == 1 and "ingest" in capsys.readouterr().err
