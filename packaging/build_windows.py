"""Build the Windows programs: a folder with stream2clip-gui.exe and stream2clip.exe, and a zip of it.

    pip install -e ".[gui,ingest,detect,build]"
    python packaging/build_windows.py --ffmpeg auto

Result: ``dist/stream2clip/`` and ``dist/stream2clip-<version>-windows-x64.zip``;
with ``--installer`` (needs Inno Setup 6) also ``dist/stream2clip-<version>-windows-x64-setup.exe``,
an installer that asks for the language (Korean, Japanese, English) on its first page.

``--ffmpeg auto`` copies the ffmpeg.exe / ffprobe.exe found on this machine into the
folder, so the programs work on a PC without ffmpeg (they look next to themselves
first). Without it the user needs ffmpeg on PATH. ``--with-asr`` also bundles
faster-whisper for ``--transcribe``.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHIM_LIMIT = 2_000_000  # a real ffmpeg.exe is tens of MB
SPEC = Path(__file__).with_name("stream2clip.spec")
INSTALLER = Path(__file__).with_name("installer.iss")
ISCC_PLACES = (r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe", r"C:\Program Files\Inno Setup 6\ISCC.exe")
APP = "stream2clip"


def project_version() -> str:
    for line in (ROOT / "pyproject.toml").read_text(encoding="utf-8").splitlines():
        if line.startswith("version"):
            return line.split("=", 1)[1].strip().strip('"')
    raise RuntimeError("version not found in pyproject.toml")


def machine_tag(machine: str | None = None) -> str:
    return {"amd64": "x64", "x86_64": "x64", "arm64": "arm64", "aarch64": "arm64"}.get((machine or platform.machine()).lower(), (machine or platform.machine()).lower())


def archive_name(version: str, machine: str | None = None) -> str:
    return f"{APP}-{version}-windows-{machine_tag(machine)}"


def pyinstaller_command(dist: Path, work: Path, python: str | None = None) -> list[str]:
    return [python or sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--distpath", str(dist), "--workpath", str(work), str(SPEC)]


ICONS = ROOT / "assets" / "brand" / "app-icons" / "windows"


def icon_path(choice: str = "symbol") -> Path:
    """``symbol`` (the logo, default), ``kiri`` (the mascot) or the path of an .ico file."""
    path = {"symbol": ICONS / "stream2clip.ico", "kiri": ICONS / "stream2clip_kiri.ico"}.get(choice, Path(choice))
    if not path.is_file():
        raise FileNotFoundError(f"icon not found: {path}")
    return path


def bundle_env(with_asr: bool, base: dict[str, str] | None = None, icon: Path | None = None) -> dict[str, str]:
    env = dict(os.environ if base is None else base)
    env["STREAM2CLIP_BUNDLE"] = "asr" if with_asr else ""
    if icon is not None:
        env["STREAM2CLIP_ICON"] = str(icon)
    return env


def find_ffmpeg_pair(ffmpeg: str) -> tuple[Path, Path]:
    """Resolve ``auto`` / a path to (ffmpeg, ffprobe); both must exist."""
    if ffmpeg == "auto":
        found = shutil.which("ffmpeg")
        if not found:
            raise FileNotFoundError("--ffmpeg auto: ffmpeg is not on PATH")
        exe = Path(found).resolve()
    else:
        exe = Path(ffmpeg)
        if exe.is_dir():
            exe = exe / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    probe = exe.with_name(exe.name.replace("ffmpeg", "ffprobe"))
    for path in (exe, probe):
        if not path.is_file():
            raise FileNotFoundError(f"not found: {path}")
        if path.stat().st_size < SHIM_LIMIT:
            # Chocolatey and Scoop put a tiny launcher on PATH; copied elsewhere it cannot find the real program.
            raise ValueError(f"{path} is only {path.stat().st_size // 1024} KB: a launcher shim, not ffmpeg itself. Pass the real file with --ffmpeg PATH")
    return exe, probe


def copy_ffmpeg(ffmpeg: str, folder: Path) -> list[Path]:
    """Put ffmpeg and ffprobe next to the programs."""
    copied = []
    for source in find_ffmpeg_pair(ffmpeg):
        target = folder / source.name
        shutil.copy2(source, target)
        copied.append(target)
    return copied


def copy_examples(folder: Path) -> list[Path]:
    """Put the example translators next to the programs, so ``--translator translators/openai_compatible.py`` works."""
    target = folder / "translators"
    target.mkdir(parents=True, exist_ok=True)
    copied = []
    for source in sorted((ROOT / "examples" / "translators").glob("*.py")):
        shutil.copy2(source, target / source.name)
        copied.append(target / source.name)
    return copied


def find_iscc(places: tuple[str, ...] = ISCC_PLACES) -> str | None:
    """Inno Setup's command line compiler: ``STREAM2CLIP_ISCC``, PATH, or its usual folders."""
    wanted = os.environ.get("STREAM2CLIP_ISCC")
    if wanted:
        return wanted if Path(wanted).is_file() else None
    found = shutil.which("iscc") or shutil.which("ISCC")
    if found:
        return found
    return next((place for place in places if Path(place).is_file()), None)


def installer_name(version: str, machine: str | None = None) -> str:
    return archive_name(version, machine) + "-setup"


def installer_command(iscc: str, folder: Path, dist: Path, version: str, machine: str | None = None) -> list[str]:
    """Compile packaging/installer.iss: the built folder goes in, ``<name>-setup.exe`` comes out in ``dist``."""
    return [
        iscc, "/Qp", f"/DAppVersion={version}", f"/DSourceDir={folder.resolve()}", f"/DOutputDir={dist.resolve()}",
        f"/DOutputName={installer_name(version, machine)}", str(INSTALLER),
    ]


def make_installer(folder: Path, dist: Path, version: str, *, iscc: str | None = None, run=subprocess.run) -> Path:
    iscc = iscc or find_iscc()
    if not iscc:
        raise FileNotFoundError("--installer needs Inno Setup 6 (ISCC.exe): install it or set STREAM2CLIP_ISCC to its path")
    run(installer_command(iscc, folder, dist, version), check=True)
    setup = dist / f"{installer_name(version)}.exe"
    if not setup.is_file():
        raise FileNotFoundError(f"Inno Setup finished without writing {setup}")
    return setup


def make_zip(folder: Path, name: str) -> Path:
    return Path(shutil.make_archive(str(folder.parent / name), "zip", root_dir=folder.parent, base_dir=folder.name))


def folder_size(folder: Path) -> int:
    return sum(f.stat().st_size for f in folder.rglob("*") if f.is_file())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dist", default=str(ROOT / "dist"), help="output directory (default: dist)")
    parser.add_argument("--work", default=str(ROOT / "build" / "pyinstaller"), help="PyInstaller work directory")
    parser.add_argument("--ffmpeg", help="'auto' or the path of ffmpeg.exe (or its folder): copy ffmpeg and ffprobe into the app folder")
    parser.add_argument("--with-asr", action="store_true", help="bundle faster-whisper for --transcribe (adds a few hundred MB)")
    parser.add_argument("--icon", default="symbol", help="program icon: symbol (default), kiri (mascot) or an .ico path")
    parser.add_argument("--no-zip", action="store_true", help="only build the folder")
    parser.add_argument("--installer", action="store_true", help="also build the installer with Inno Setup 6 (asks for the language: Korean, Japanese, English)")
    parser.add_argument("--installer-only", action="store_true", help="do not build: make the installer from an already built folder")
    parser.add_argument("--copy-ffmpeg-only", action="store_true", help="do not build: just copy --ffmpeg into an already built folder")
    args = parser.parse_args(argv)

    dist = Path(args.dist)
    if args.ffmpeg:
        find_ffmpeg_pair(args.ffmpeg)  # fail before the long build, not after it
    if args.copy_ffmpeg_only:
        if not args.ffmpeg or not (dist / APP).is_dir():
            parser.error("--copy-ffmpeg-only needs --ffmpeg and an existing build in --dist")
        for path in copy_ffmpeg(args.ffmpeg, dist / APP):
            print(f"added  {path.name}  ({path.stat().st_size / 1e6:.0f} MB)")
        return 0
    if args.installer_only:
        if not (dist / APP).is_dir():
            parser.error("--installer-only needs an existing build in --dist")
        setup = make_installer(dist / APP, dist, project_version())
        print(f"setup  {setup}  ({setup.stat().st_size / 1e6:.0f} MB)")
        return 0
    if args.installer and not find_iscc():
        parser.error("--installer needs Inno Setup 6 (ISCC.exe): install it or set STREAM2CLIP_ISCC to its path")  # before the long build
    subprocess.run(pyinstaller_command(dist, Path(args.work)), check=True, env=bundle_env(args.with_asr, icon=icon_path(args.icon)), cwd=ROOT)
    folder = dist / APP
    print(f"built  {folder}  ({folder_size(folder) / 1e6:.0f} MB)")
    if args.ffmpeg:
        for path in copy_ffmpeg(args.ffmpeg, folder):
            print(f"added  {path.name}  ({path.stat().st_size / 1e6:.0f} MB)")
    for path in copy_examples(folder):
        print(f"added  translators/{path.name}")
    if not args.no_zip:
        archive = make_zip(folder, archive_name(project_version()))
        print(f"zip    {archive}  ({archive.stat().st_size / 1e6:.0f} MB)")
    if args.installer:
        setup = make_installer(folder, dist, project_version())
        print(f"setup  {setup}  ({setup.stat().st_size / 1e6:.0f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
