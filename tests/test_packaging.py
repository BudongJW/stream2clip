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
    assert build.archive_name("0.3.0", "AMD64") == "stream2clip-0.3.0-windows-x64"
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

    archive = build.make_zip(folder, "stream2clip-0.3.0-windows-x64")
    assert archive.name == "stream2clip-0.3.0-windows-x64.zip"
    with zipfile.ZipFile(archive) as z:  # unpacks into one folder
        assert sorted(z.namelist()) == ["stream2clip/", "stream2clip/ffmpeg.exe", "stream2clip/ffprobe.exe", "stream2clip/stream2clip.exe"] or \
            sorted(n for n in z.namelist() if not n.endswith("/")) == ["stream2clip/ffmpeg.exe", "stream2clip/ffprobe.exe", "stream2clip/stream2clip.exe"]


def test_example_translators_ship_with_the_build(build, tmp_path):
    copied = build.copy_examples(tmp_path)
    assert [p.name for p in copied] == ["openai_compatible.py"] and (tmp_path / "translators" / "openai_compatible.py").is_file()
    assert build.copy_examples(tmp_path) == copied  # building twice over the same folder is fine


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


def test_installer_offers_ffmpeg_when_there_is_none():
    """The download is a task of its own: offered when ffmpeg is not found, checked against the pinned SHA-256."""
    text = (ROOT / "packaging" / "installer.iss").read_text(encoding="utf-8-sig")
    assert 'Name: "ffmpeg"; Description: "{cm:FfmpegTask}"; Check: FfmpegMissing' in text  # ticked unless the user unticks it
    for code in ("ko", "ja", "en"):
        for message in ("FfmpegTask", "FfmpegPage", "FfmpegPageNote", "FfmpegInstalling", "FfmpegFailed", "FfmpegNote"):
            assert f"{code}.{message}=" in text
        assert "{#FfmpegSize} MB" in next(line for line in text.splitlines() if line.startswith(f"{code}.FfmpegTask="))
    assert "#ifndef FfmpegUrl" in text and "#error" in text  # compiled without the pinned build: stop, do not guess one
    assert "DownloadPage.Add('{#FfmpegUrl}', '{#FfmpegFile}', '{#FfmpegSha256}')" in text
    # the installed program unpacks it - the same command a person can run - and only when the download succeeded
    run = next(line for line in text.splitlines() if line.startswith('Filename: "{app}\\stream2clip.exe"'))
    assert 'setup --ffmpeg --no-obs --from ""{tmp}\\{#FfmpegFile}""' in run and "Tasks: ffmpeg" in run and "Check: FfmpegFetched" in run and "runhidden" in run
    # the three places stream2clip itself looks in
    missing = text.split("function FfmpegMissing")[1].split("end;")[0]
    assert "GetEnv('PATH')" in missing and "{%USERPROFILE}\\.cache\\stream2clip\\tools\\ffmpeg.exe" in missing and "BesideThePrograms" in missing
    assert "(CurPageID = wpFinished) and FfmpegMissing" in text  # the last page mentions ffmpeg only when it is still missing
    # a failed download does not stop the installation
    handler = text.split("DownloadPage.Download;")[1].split("finally")[0]
    assert "except" in handler and "Result := False" not in handler and "SuppressibleMsgBox" in handler
    removed = text.split("[UninstallDelete]")[1].split("[Code]")[0]
    for name in ("ffmpeg.exe", "ffprobe.exe", "ffmpeg-LICENSE.txt"):
        assert f'Type: files; Name: "{{%USERPROFILE}}\\.cache\\stream2clip\\tools\\{name}"' in removed
    from stream2clip import ffmpeg, tools

    assert ffmpeg.tools_dir.__doc__ and tools._LICENSE == "ffmpeg-LICENSE.txt"


def test_installer_asks_for_the_language_and_tells_the_app(build, tmp_path, monkeypatch):
    script = (ROOT / "packaging" / "installer.iss").read_bytes()
    assert script.startswith(b"\xef\xbb\xbf")  # Inno Setup reads Korean and Japanese text correctly only with the byte order mark
    text = script.decode("utf-8-sig")
    assert "ShowLanguageDialog=yes" in text and "PrivilegesRequired=lowest" in text
    for code, messages in (("ko", "Korean.isl"), ("ja", "Japanese.isl"), ("en", "Default.isl")):
        assert f'Name: "{code}"; MessagesFile: "compiler:' in text and messages in text
        assert f"{code}.DesktopShortcut=" in text and f"{code}.StartApp=" in text and f"{code}.FfmpegNote=" in text
    from stream2clip import i18n

    assert rf"{{app}}\{i18n.INSTALL_FILE}'), ActiveLanguage" in text  # the language codes are the app's own: ko, ja, en
    files = text.split("[Files]")[1].split("[Icons]")[0]
    assert files.count("Source:") == 1 and "ffmpeg" not in files  # ffmpeg is not part of the installer

    assert build.installer_name("0.5.1", "AMD64") == "stream2clip-0.5.1-windows-x64-setup"
    folder, dist = tmp_path / "dist" / "stream2clip", tmp_path / "dist"
    folder.mkdir(parents=True)
    command = build.installer_command("ISCC.exe", folder, dist, "0.5.1", "AMD64")
    assert command[0] == "ISCC.exe" and command[-1].endswith("installer.iss") and "/DAppVersion=0.5.1" in command
    from stream2clip.tools import FFMPEG_BUILD

    # the build the installer offers to download is the one pinned in the package, nothing typed twice
    for define in (f"/DFfmpegUrl={FFMPEG_BUILD.url}", f"/DFfmpegFile={FFMPEG_BUILD.filename}", f"/DFfmpegSha256={FFMPEG_BUILD.sha256}", f"/DFfmpegSize={FFMPEG_BUILD.megabytes}"):
        assert define in command
    assert f"/DSourceDir={folder.resolve()}" in command and f"/DOutputDir={dist.resolve()}" in command and "/DOutputName=stream2clip-0.5.1-windows-x64-setup" in command

    ran = []

    def fake_run(cmd, check):
        ran.append(cmd)
        (dist / f"{build.installer_name('0.5.1')}.exe").write_bytes(b"MZ")

    setup = build.make_installer(folder, dist, "0.5.1", iscc="ISCC.exe", run=fake_run)
    assert setup.name == f"{build.installer_name('0.5.1')}.exe" and ran[0][0] == "ISCC.exe"
    with pytest.raises(FileNotFoundError, match="without writing"):
        build.make_installer(folder, dist, "9.9.9", iscc="ISCC.exe", run=lambda cmd, check: None)

    compiler = tmp_path / "ISCC.exe"
    compiler.write_bytes(b"")
    monkeypatch.setenv("STREAM2CLIP_ISCC", str(compiler))
    assert build.find_iscc() == str(compiler)
    monkeypatch.setenv("STREAM2CLIP_ISCC", str(tmp_path / "missing.exe"))
    assert build.find_iscc() is None
    with pytest.raises(FileNotFoundError, match="Inno Setup 6"):
        build.make_installer(folder, dist, "0.5.1")
