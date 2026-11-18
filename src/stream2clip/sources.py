"""VOD / chat / metadata acquisition through yt-dlp (``pip install "stream2clip[ingest]"``).

Builders return argument lists (no side effects) so they can be reused or
logged; the ``fetch_*`` / ``download_*`` helpers run them. yt-dlp is invoked as
``python -m yt_dlp`` when installed as a package, else the ``yt-dlp`` binary.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "SourceInfo",
    "HeatmapPoint",
    "ytdlp_command",
    "build_info_command",
    "build_chat_command",
    "build_section_command",
    "build_subs_command",
    "download_subs",
    "fetch_info",
    "download_chat",
    "download_section",
    "download_video",
    "heatmap_from_info",
    "source_from_info",
    "load_info",
]


@dataclass(frozen=True)
class HeatmapPoint:
    """YouTube "most replayed" sample (value 0..1)."""

    start: float
    end: float
    value: float


@dataclass(frozen=True)
class SourceInfo:
    """What the clip pipeline needs to know about the original stream."""

    url: str = ""
    title: str = ""
    channel: str = ""
    channel_url: str = ""
    duration: float | None = None
    upload_date: str | None = None
    live_status: str | None = None  # is_live | was_live | is_upcoming | post_live | not_live
    availability: str | None = None  # public | unlisted | subscriber_only | needs_auth | premium_only
    extractor: str = ""

    @property
    def archive_public(self) -> bool:
        return self.live_status in (None, "was_live", "not_live") and self.availability in (None, "public", "unlisted")

    @property
    def members_only(self) -> bool:
        return self.availability in ("subscriber_only", "premium_only", "needs_auth")

    def timestamp_url(self, seconds: float) -> str:
        """Link to a moment of the source (YouTube/Twitch style ``t=`` parameter)."""
        if not self.url:
            return ""
        sep = "&" if "?" in self.url else "?"
        return f"{self.url}{sep}t={int(seconds)}"


def ytdlp_command(*, cookies: str | os.PathLike[str] | None = None, cookies_from_browser: str | None = None) -> list[str]:
    """yt-dlp invocation plus auth options.

    YouTube often answers "Sign in to confirm you're not a bot" to servers and
    some home IPs; pass a Netscape ``cookies`` file or ``cookies_from_browser``
    ("chrome", "firefox", "edge" ...). Extra flags can also come from the
    ``STREAM2CLIP_YTDLP_ARGS`` environment variable.
    """
    env = os.environ.get("STREAM2CLIP_YTDLP")
    if env:
        base = [env]
    else:
        try:
            import yt_dlp  # noqa: F401

            base = [sys.executable, "-m", "yt_dlp"]
        except ImportError:
            found = shutil.which("yt-dlp")
            if not found:
                raise RuntimeError('yt-dlp not found: pip install "stream2clip[ingest]" (or install the yt-dlp binary)') from None
            base = [found]
    if cookies:
        base += ["--cookies", os.fspath(cookies)]
    if cookies_from_browser:
        base += ["--cookies-from-browser", cookies_from_browser]
    extra = os.environ.get("STREAM2CLIP_YTDLP_ARGS")
    if extra:
        import shlex

        base += shlex.split(extra)
    return base


def build_info_command(url: str, *, ytdlp: list[str] | None = None) -> list[str]:
    return [*(ytdlp or ytdlp_command()), "--dump-single-json", "--no-warnings", "--skip-download", url]


def build_chat_command(url: str, out_dir: str | os.PathLike[str], *, ytdlp: list[str] | None = None) -> list[str]:
    """Download the YouTube live chat replay (``<id>.live_chat.json``) without the video."""
    template = str(Path(out_dir) / "%(id)s.%(ext)s")
    return [*(ytdlp or ytdlp_command()), "--skip-download", "--write-subs", "--sub-langs", "live_chat", "--no-warnings", "-o", template, url]


def build_subs_command(url: str, out_dir: str | os.PathLike[str], langs: str = "ja", *, ytdlp: list[str] | None = None) -> list[str]:
    """Download (automatic) captions as WebVTT - they carry per-word timing for karaoke subtitles."""
    template = str(Path(out_dir) / "%(id)s.%(ext)s")
    return [*(ytdlp or ytdlp_command()), "--skip-download", "--write-subs", "--write-auto-subs", "--sub-langs", langs,
            "--sub-format", "vtt", "--no-warnings", "-o", template, url]


def _hms(seconds: float) -> str:
    h, rem = divmod(max(0.0, seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"


def build_section_command(
    url: str,
    output: str | os.PathLike[str],
    *,
    start: float | None = None,
    end: float | None = None,
    max_height: int = 1080,
    ytdlp: list[str] | None = None,
) -> list[str]:
    """Download only ``start..end`` of a VOD (keyframe-accurate cuts) as MP4."""
    cmd = [
        *(ytdlp or ytdlp_command()),
        "-f", f"bv*[height<={max_height}]+ba/b[height<={max_height}]/b",
        "--merge-output-format", "mp4",
        "--no-warnings",
        "-o", os.fspath(output),
    ]
    if start is not None or end is not None:
        cmd += ["--download-sections", f"*{_hms(start or 0)}-{_hms(end) if end is not None else 'inf'}", "--force-keyframes-at-cuts"]
    cmd.append(url)
    return cmd


def _run(cmd: list[str], timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    if proc.returncode != 0:
        tail = "\n".join((proc.stderr or "").strip().splitlines()[-10:])
        raise RuntimeError(f"yt-dlp failed ({proc.returncode}):\n{tail}")
    return proc


def fetch_info(url: str, *, ytdlp: list[str] | None = None, timeout: float | None = 120) -> dict[str, Any]:
    return json.loads(_run(build_info_command(url, ytdlp=ytdlp), timeout).stdout)


def download_chat(url: str, out_dir: str | os.PathLike[str], *, ytdlp: list[str] | None = None, timeout: float | None = None) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    before = set(out.glob("*.live_chat.json"))
    _run(build_chat_command(url, out, ytdlp=ytdlp), timeout)
    created = sorted(set(out.glob("*.live_chat.json")) - before) or sorted(out.glob("*.live_chat.json"))
    if not created:
        raise RuntimeError("yt-dlp finished but produced no live_chat.json (no chat replay for this video?)")
    return created[-1]


def download_subs(url: str, out_dir: str | os.PathLike[str], langs: str = "ja", *, ytdlp: list[str] | None = None, timeout: float | None = None) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    before = set(out.glob("*.vtt"))
    _run(build_subs_command(url, out, langs, ytdlp=ytdlp), timeout)
    return sorted(set(out.glob("*.vtt")) - before)


def download_section(url: str, output: str | os.PathLike[str], start: float | None = None, end: float | None = None, *, max_height: int = 1080, ytdlp: list[str] | None = None, timeout: float | None = None) -> Path:
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    _run(build_section_command(url, out, start=start, end=end, max_height=max_height, ytdlp=ytdlp), timeout)
    return out


def download_video(url: str, output: str | os.PathLike[str], *, max_height: int = 1080, ytdlp: list[str] | None = None, timeout: float | None = None) -> Path:
    return download_section(url, output, max_height=max_height, ytdlp=ytdlp, timeout=timeout)


def load_info(path: str | os.PathLike[str]) -> dict[str, Any]:
    """Read a yt-dlp ``--dump-single-json`` / ``--write-info-json`` file."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def heatmap_from_info(info: dict[str, Any]) -> list[HeatmapPoint]:
    return [
        HeatmapPoint(float(p["start_time"]), float(p["end_time"]), float(p["value"]))
        for p in info.get("heatmap") or []
        if {"start_time", "end_time", "value"} <= p.keys()
    ]


def source_from_info(info: dict[str, Any]) -> SourceInfo:
    return SourceInfo(
        url=info.get("webpage_url") or info.get("original_url") or "",
        title=info.get("title") or "",
        channel=info.get("channel") or info.get("uploader") or "",
        channel_url=info.get("channel_url") or info.get("uploader_url") or "",
        duration=float(info["duration"]) if info.get("duration") else None,
        upload_date=info.get("upload_date"),
        live_status=info.get("live_status"),
        availability=info.get("availability"),
        extractor=info.get("extractor_key") or info.get("extractor") or "",
    )
