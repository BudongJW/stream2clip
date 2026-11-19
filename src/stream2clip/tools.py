"""The other programs stream2clip works with: what is on this PC, what is missing, and fetching ffmpeg.

stream2clip cuts and converts with ffmpeg, a separate program that it does not ship. On Windows
:func:`install_ffmpeg` fetches one pinned build (the "essentials" build of gyan.dev, the Windows
build ffmpeg.org links to and the one ``winget install Gyan.FFmpeg`` installs), checks it against
a pinned SHA-256 and puts ``ffmpeg.exe`` and ``ffprobe.exe`` into :func:`stream2clip.ffmpeg.tools_dir`,
where :func:`stream2clip.ffmpeg.find_ffmpeg` looks. The Windows installer, the button of the app's
start window and ``stream2clip setup --ffmpeg`` all end here.

:func:`components` lists everything else a feature may need (yt-dlp, the face model, the websocket
client, OBS, caption fonts ...), so ``stream2clip setup`` can tell a beginner what is missing and how
to get it. Only the standard library is used.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import shutil
import socket
import subprocess
import sys
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .ffmpeg import FFmpegNotFoundError, find_ffmpeg, find_ffprobe, tools_dir
from .i18n import tr

__all__ = [
    "FFMPEG_BUILD",
    "Component",
    "DownloadCancelled",
    "FfmpegBuild",
    "can_install_ffmpeg",
    "components",
    "download",
    "extract_ffmpeg",
    "ffmpeg_ready",
    "ffmpeg_version",
    "install_ffmpeg",
    "missing_required",
    "report_lines",
    "sha256_of",
]

Progress = Callable[[int, int], None]


@dataclass(frozen=True)
class FfmpegBuild:
    """One downloadable ffmpeg archive, pinned by its SHA-256."""

    version: str
    url: str
    sha256: str
    size: int

    @property
    def filename(self) -> str:
        return self.url.rsplit("/", 1)[1]

    @property
    def megabytes(self) -> int:
        return round(self.size / 1_000_000)


#: The Windows build that is fetched. A newer one is adopted by changing these four values together.
FFMPEG_BUILD = FfmpegBuild(
    version="9.0.2",
    url="https://github.com/GyanD/codexffmpeg/releases/download/9.0.2/ffmpeg-9.0.2-essentials_build.zip",
    sha256="60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba",
    size=114_768_076,
)
#: What is taken out of the archive (its ``bin`` folder), and the licence text that goes with it.
_PROGRAMS = ("ffmpeg.exe", "ffprobe.exe")
_LICENSE = "ffmpeg-LICENSE.txt"


class DownloadCancelled(RuntimeError):
    pass


def sha256_of(path: str | os.PathLike[str]) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def download(
    url: str,
    target: str | os.PathLike[str],
    *,
    sha256: str,
    size: int | None = None,
    on_progress: Progress | None = None,
    cancelled: Callable[[], bool] | None = None,
    opener: Callable[..., Any] | None = None,
) -> Path:
    """Fetch ``url`` into ``target``; the file only appears there when its SHA-256 is the expected one.

    ``on_progress(done, total)`` is called as bytes arrive, ``cancelled()`` is asked between blocks.
    ``opener`` replaces :func:`urllib.request.urlopen` (tests).
    """
    if not url.startswith("https://"):
        raise ValueError(f"Not an https address: {url}")
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    done = 0
    try:
        with (opener or urllib.request.urlopen)(url, timeout=60) as response, partial.open("wb") as fh:  # noqa: S310 - https only, checked above
            total = int(response.headers.get("Content-Length") or 0) or size or 0
            while True:
                if cancelled is not None and cancelled():
                    raise DownloadCancelled("The download was cancelled")
                block = response.read(1 << 16)
                if not block:
                    break
                fh.write(block)
                done += len(block)
                if on_progress is not None:
                    on_progress(done, total)
        got = sha256_of(partial)
        if got != sha256:
            raise RuntimeError(f"The downloaded file has an unexpected checksum ({got[:12]}..., {done:,} bytes): not using it")
        partial.replace(target)
    finally:
        partial.unlink(missing_ok=True)
    return target


def extract_ffmpeg(archive: str | os.PathLike[str], folder: str | os.PathLike[str]) -> list[Path]:
    """Take ``bin/ffmpeg.exe`` and ``bin/ffprobe.exe`` (and the licence text) out of the archive into ``folder``."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    with zipfile.ZipFile(archive) as bundle:
        members = {}
        for info in bundle.infolist():
            parts = info.filename.split("/")
            if len(parts) >= 2 and parts[-2] == "bin" and parts[-1] in _PROGRAMS:
                members[parts[-1]] = info
            elif parts[-1] == "LICENSE" and len(parts) <= 2:
                members[_LICENSE] = info
        absent = [name for name in _PROGRAMS if name not in members]
        if absent:
            raise RuntimeError(f"{Path(archive).name} holds no {' / '.join(absent)}")
        for name, info in members.items():  # written under our own names: nothing in the archive chooses a path
            partial = folder / (name + ".part")
            with bundle.open(info) as source, partial.open("wb") as fh:
                shutil.copyfileobj(source, fh, 1 << 20)
            partial.replace(folder / name)
            written.append(folder / name)
    return written


def can_install_ffmpeg() -> bool:
    """Whether :func:`install_ffmpeg` has a build for this system (Windows; elsewhere a package manager has ffmpeg)."""
    return sys.platform == "win32"


def install_hint() -> str:
    """How to get ffmpeg on this system, in one line."""
    if sys.platform == "win32":
        return tr("stream2clip setup --ffmpeg 실행 또는 앱 시작 화면의 ffmpeg 내려받기 사용")
    if sys.platform == "darwin":
        return tr("터미널에서 brew install ffmpeg 실행")
    return tr("배포판의 패키지 관리자로 ffmpeg 설치 (예: sudo apt install ffmpeg)")


def install_ffmpeg(
    *,
    archive: str | os.PathLike[str] | None = None,
    folder: str | os.PathLike[str] | None = None,
    build: FfmpegBuild | None = None,
    on_progress: Progress | None = None,
    cancelled: Callable[[], bool] | None = None,
    opener: Callable[..., Any] | None = None,
) -> list[Path]:
    """Put ffmpeg and ffprobe where stream2clip looks for them; returns the files written.

    Without ``archive`` the pinned build is downloaded (115 MB). With it, that already downloaded
    file is used - it must be the pinned build, its SHA-256 is checked all the same.
    """
    if not can_install_ffmpeg():
        raise RuntimeError(f"There is no ffmpeg download for this system: {install_hint()}")
    build = build or FFMPEG_BUILD
    folder = Path(folder) if folder is not None else tools_dir()
    if archive is not None:
        got = sha256_of(archive)
        if got != build.sha256:
            raise RuntimeError(f"{Path(archive).name} is not the expected ffmpeg {build.version} archive (checksum {got[:12]}...): not using it")
        return extract_ffmpeg(archive, folder)
    fetched = download(build.url, folder / build.filename, sha256=build.sha256, size=build.size, on_progress=on_progress, cancelled=cancelled, opener=opener)
    try:
        return extract_ffmpeg(fetched, folder)
    finally:
        fetched.unlink(missing_ok=True)


def ffmpeg_ready() -> bool:
    """Both ffmpeg and ffprobe are found."""
    try:
        find_ffmpeg()
        find_ffprobe()
    except FFmpegNotFoundError:
        return False
    return True


def ffmpeg_version(program: str | os.PathLike[str]) -> str | None:
    """"9.0.2-essentials_build-www.gyan.dev" from the first line of ``ffmpeg -version``; ``None`` when it does not run."""
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        out = subprocess.run([os.fspath(program), "-version"], capture_output=True, text=True, timeout=15, creationflags=flags, check=False).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    words = out.split()
    return words[2] if len(words) > 2 and words[1] == "version" else None


# --------------------------------------------------------------------------- what is on this PC


@dataclass(frozen=True)
class Component:
    """One thing a feature needs. ``state``: "ok", "missing" (needed, absent), "optional" (absent, only some
    features need it) or "later" (fetched by itself on first use)."""

    key: str
    name: str
    use: str
    state: str
    detail: str = ""
    fix: str = ""

    @property
    def found(self) -> bool:
        return self.state == "ok"


def _has(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def _program(key: str, find: Callable[[], str], use: str) -> Component:
    try:
        path = find()
    except FFmpegNotFoundError:
        return Component(key, key, use, "missing", fix=install_hint())
    version = ffmpeg_version(path)
    return Component(key, key, use, "ok", f"{path} ({version})" if version else path)


def _listening(host: str, port: int, timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def components(*, obs: tuple[str, int] | None = ("127.0.0.1", 4455)) -> list[Component]:
    """Everything stream2clip works with on this PC. ``obs`` is where OBS's WebSocket server is looked for (``None``: not looked for)."""
    built = bool(getattr(sys, "frozen", False))
    found = [
        _program("ffmpeg", find_ffmpeg, tr("녹화, 영상 변환, 클립 제작")),
        _program("ffprobe", find_ffprobe, tr("영상 길이와 해상도 확인")),
    ]

    use = tr("방송 주소에서 영상과 채팅 받기")
    if built or os.environ.get("STREAM2CLIP_YTDLP") or _has("yt_dlp") or shutil.which("yt-dlp"):
        found.append(Component("yt-dlp", "yt-dlp", use, "ok", tr("프로그램에 포함") if built else ""))
    else:
        found.append(Component("yt-dlp", "yt-dlp", use, "optional", fix='pip install "stream2clip[ingest]"'))

    use = tr("아바타 위치 자동 검출")
    name = tr("얼굴 검출 모델")
    if not _has("onnxruntime"):
        found.append(Component("model", name, use, "optional", fix='pip install "stream2clip[detect]"'))
    else:
        from .detect import model_path

        path = model_path()
        if path.is_file():
            found.append(Component("model", name, use, "ok", str(path)))
        else:
            found.append(Component("model", name, use, "later", tr("첫 사용 시 자동으로 내려받음 (12 MB). 미리 받으려면 stream2clip setup --model")))

    use = tr("OBS 리플레이 버퍼, Twitch, CHZZK, SOOP 라이브 채팅")
    if _has("websocket"):
        found.append(Component("websocket", "websocket-client", use, "ok", tr("프로그램에 포함") if built else ""))
    else:
        found.append(Component("websocket", "websocket-client", use, "optional", fix='pip install "stream2clip[obs]"'))

    if obs is not None:
        use = tr("리플레이 버퍼 저장, 라이브 모드")
        name = tr("OBS WebSocket 서버")
        address = f"{obs[0]}:{obs[1]}"
        if _listening(*obs):
            found.append(Component("obs", name, use, "ok", tr("{0} 응답").format(address)))
        else:
            found.append(Component("obs", name, use, "optional", tr("{0} 응답 없음").format(address), tr("OBS Studio 실행 후 도구, WebSocket 서버 설정에서 서버 사용")))

    from .subtitles import _has_family, installed_fonts, pick_font

    use = tr("클립에 자막 입히기")
    name = tr("자막 글꼴")
    fonts = installed_fonts()
    picked = [pick_font(script, fonts) for script in ("ko", "ja", "")]  # the first of the list when none is installed
    names = list(dict.fromkeys(family for family in picked if _has_family(family, fonts)))
    if names:
        found.append(Component("fonts", name, use, "ok", ", ".join(names)))
    else:
        found.append(Component("fonts", name, use, "optional", tr("자막용 글꼴을 찾지 못함. ffmpeg의 기본 글꼴로 표시")))

    use = tr("자막 받아쓰기 (Whisper)")
    if _has("faster_whisper"):
        found.append(Component("asr", "faster-whisper", use, "ok"))
    else:
        found.append(Component("asr", "faster-whisper", use, "optional", tr("파이썬 패키지에서 제공") if built else "", 'pip install "stream2clip[asr]"'))

    use = tr("YouTube 업로드")
    if _has("googleapiclient") and _has("google_auth_oauthlib"):
        found.append(Component("upload", "google-api-python-client", use, "ok"))
    else:
        found.append(Component("upload", "google-api-python-client", use, "optional", tr("파이썬 패키지에서 제공") if built else "", 'pip install "stream2clip[upload]"'))
    return found


def missing_required(found: list[Component]) -> list[Component]:
    return [item for item in found if item.state == "missing"]


def report_lines(found: list[Component]) -> list[str]:
    """The components as lines of text, for ``stream2clip setup``."""
    states = {"ok": tr("있음"), "missing": tr("없음"), "optional": tr("없음(선택)"), "later": tr("자동")}
    lines = []
    for item in found:
        lines.append(f"[{states[item.state]}] {item.name}: {item.use}")
        if item.detail:
            lines.append(f"    {item.detail}")
        if item.fix:
            lines.append(f"    {tr('해결 방법')}: {item.fix}")
    absent = missing_required(found)
    lines.append("")
    if absent:
        lines.append(tr("필수 구성요소 없음: {0}").format(", ".join(item.name for item in absent)))
    else:
        lines.append(tr("필수 구성요소 모두 있음"))
    return lines
