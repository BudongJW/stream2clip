"""VOD / chat / metadata acquisition through yt-dlp (``pip install "stream2clip[ingest]"``).

Builders return argument lists (no side effects) so they can be reused or
logged; the ``fetch_*`` / ``download_*`` helpers run them. yt-dlp is invoked as
``python -m yt_dlp`` when installed as a package, else the ``yt-dlp`` binary.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Sequence

if TYPE_CHECKING:
    from .chat import ChatMessage

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
    "platform_of",
    "chzzk_video_no",
    "soop_title_no",
    "fetch_chzzk_chat",
    "fetch_soop_chat",
    "download_replay_chat",
    "is_url",
    "download_highlight_sections",
    "source_folder_name",
    "fetch_replay",
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
    elif getattr(sys, "frozen", False):
        # Built executable: there is no "python -m"; the command line program runs yt-dlp itself.
        cli = Path(sys.executable).with_name("stream2clip.exe" if os.name == "nt" else "stream2clip")
        base = [str(cli if cli.is_file() else sys.executable), "yt-dlp"]
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


def build_info_command(url: str, *, ytdlp: list[str] | None = None, comments: int = 0) -> list[str]:
    """``comments`` > 0 also puts that many top comments into the JSON (viewers' timestamps, see ``evaluation``)."""
    cmd = [*(ytdlp or ytdlp_command()), "--dump-single-json", "--no-warnings", "--skip-download"]
    if comments > 0:
        cmd += ["--write-comments", "--extractor-args", f"youtube:max_comments={int(comments)},all,0,0;comment_sort=top"]
    return [*cmd, url]


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
    ffmpeg_input_args: Sequence[str] = (),
) -> list[str]:
    """Download only ``start..end`` of a VOD (keyframe-accurate cuts) as MP4.

    ``ffmpeg_input_args`` are handed to the ffmpeg that yt-dlp runs for a section download.
    """
    section = start is not None or end is not None
    formats = f"bv*[height<={max_height}]+ba/b[height<={max_height}]/b"
    if section:
        # A section is read by ffmpeg in one connection. YouTube serves its DASH formats to such a reader at a
        # crawl (a 64 s section had not arrived after 6 minutes), its HLS formats at full speed (13 s) - so HLS first.
        hls = "[protocol*=m3u8]"
        formats = f"bv*{hls}[height<={max_height}]+ba{hls}/b{hls}[height<={max_height}]/" + formats
    cmd = [
        *(ytdlp or ytdlp_command()),
        "-f", formats,
        "--merge-output-format", "mp4",
        "--no-warnings",
        "-o", os.fspath(output),
    ]
    if section:
        cmd += ["--download-sections", f"*{_hms(start or 0)}-{_hms(end) if end is not None else 'inf'}", "--force-keyframes-at-cuts"]
        if ffmpeg_input_args:
            cmd += ["--downloader-args", "ffmpeg_i:" + " ".join(ffmpeg_input_args)]
    cmd.append(url)
    return cmd


_HLS_PICKY: dict[str, list[str]] = {}


def hls_relaxed_args(ffmpeg: str | None = None) -> list[str]:
    """``["-extension_picky", "0"]`` when this ffmpeg has that switch (7.1 and later), else ``[]``.

    Newer ffmpeg refuses HLS segments whose file extension does not match the detected
    format. CHZZK serves fragmented MP4 as ``.m4s``, so a section download dies with
    "mismatches allowed extensions" unless the check is switched off for that download.
    """
    from .ffmpeg import find_ffmpeg

    try:
        binary = ffmpeg or find_ffmpeg()
    except Exception:
        return []
    if binary not in _HLS_PICKY:
        try:
            proc = subprocess.run([binary, "-hide_banner", "-h", "demuxer=hls"], capture_output=True, text=True, timeout=20, check=False)
            text = (proc.stdout or "") + (proc.stderr or "")
        except (OSError, subprocess.SubprocessError):
            text = ""
        _HLS_PICKY[binary] = ["-extension_picky", "0"] if "extension_picky" in text else []
    return list(_HLS_PICKY[binary])


def is_url(text: object) -> bool:
    return isinstance(text, str) and text.lower().startswith(("http://", "https://"))


def _run(cmd: list[str], timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    if proc.returncode != 0:
        tail = "\n".join((proc.stderr or "").strip().splitlines()[-10:])
        raise RuntimeError(f"yt-dlp failed ({proc.returncode}):\n{tail}")
    return proc


def fetch_info(url: str, *, ytdlp: list[str] | None = None, timeout: float | None = 120, comments: int = 0) -> dict[str, Any]:
    return json.loads(_run(build_info_command(url, ytdlp=ytdlp, comments=comments), timeout if comments <= 0 else None).stdout)


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
    section = start is not None or end is not None
    extra = hls_relaxed_args() if section and platform_of(url) == "chzzk" else []
    _run(build_section_command(url, out, start=start, end=end, max_height=max_height, ytdlp=ytdlp, ffmpeg_input_args=extra), timeout)
    return out


def download_highlight_sections(
    url: str,
    highlights: "Sequence[Any]",
    out_dir: str | os.PathLike[str],
    *,
    pad: float = 2.0,
    max_height: int = 1080,
    ytdlp: list[str] | None = None,
    download: Callable[..., Path] | None = None,
    on_progress: Callable[[int, int, Any], None] | None = None,
) -> dict[int, tuple[Path, float]]:
    """Download only the footage of each highlight: ``{rank: (file, stream time at the file's start)}``.

    A three-hour stream is not fetched to cut five clips out of it. Each file covers the
    highlight plus ``pad`` seconds on both sides; a file that is already there is reused,
    so a run that was interrupted continues where it stopped.
    """
    fetch = download or download_section
    out = Path(out_dir)
    found: dict[int, tuple[Path, float]] = {}
    for index, h in enumerate(highlights, start=1):
        start = max(0.0, float(h.start) - pad)
        end = float(h.end) + pad
        path = out / f"section_{h.rank:02d}_{int(start * 10):07d}-{int(end * 10):07d}.mp4"
        if on_progress is not None:
            on_progress(index, len(highlights), h)
        if not (path.is_file() and path.stat().st_size > 0):
            fetch(url, path, start, end, max_height=max_height, ytdlp=ytdlp)
        found[h.rank] = (path, start)
    return found


def source_folder_name(url: str) -> str:
    """A folder name for what is fetched from one address: ``youtube_<id>``, ``chzzk_<number>`` ... or a short hash."""
    platform = platform_of(url)
    found: tuple[str, str] | None = None
    if platform == "chzzk":
        match = re.search(r"/video/(\d+)", url)
        found = ("chzzk", match.group(1)) if match else None
    elif platform == "soop":
        match = re.search(r"/player/(\d+)", url) or re.search(r"[?&]nTitleNo=(\d+)", url)
        found = ("soop", match.group(1)) if match else None
    else:
        for name, pattern in (
            ("youtube", r"(?:youtube\.com/(?:watch\?(?:.*&)?v=|live/|shorts/|embed/)|youtu\.be/)([A-Za-z0-9_-]{6,})"),
            ("twitch", r"twitch\.tv/videos/(\d+)"),
        ):
            match = re.search(pattern, url)
            if match:
                found = (name, match.group(1))
                break
    if found is None:
        import hashlib

        return "url_" + hashlib.sha1(url.strip().encode("utf-8")).hexdigest()[:10]
    return f"{found[0]}_{found[1]}"


def fetch_replay(
    url: str,
    out_dir: str | os.PathLike[str],
    *,
    info: bool = True,
    chat: bool = True,
    reuse: bool = False,
    ytdlp: list[str] | None = None,
    on_stage: Callable[[str], None] | None = None,
    warn: Callable[[str], None] | None = None,
    note: Callable[[str], None] | None = None,
) -> tuple[Path | None, Path | None]:
    """Fetch what highlight detection needs from an address - the info JSON and the chat replay, not the video.

    Returns ``(info.json or None, chat file or None)``; a part that was not asked for is
    ``None``. CHZZK and SOOP sometimes refuse the info request: that is reported through
    ``warn`` and the chat is still collected. With ``reuse`` files that are already in
    ``out_dir`` are kept (use a folder per address, see :func:`source_folder_name`).
    ``note`` hears reminders such as :func:`replay_expiry_note` for a SOOP replay.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stage = on_stage or (lambda _name: None)
    korean = platform_of(url)
    info_path: Path | None = None
    chat_path: Path | None = None
    if info:
        target = out / "info.json"
        if reuse and target.is_file() and target.stat().st_size > 0:
            info_path = target
        else:
            stage("fetch-info")
            try:
                data = fetch_info(url, ytdlp=ytdlp)
            except RuntimeError as exc:
                if not korean:
                    raise
                if warn is not None:
                    warn(str(exc))
            else:
                target.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                info_path = target
    if chat:
        existing = sorted(out.glob("*.chat.jsonl" if korean else "*.live_chat.json")) if reuse else []
        if existing:
            chat_path = existing[-1]
        else:
            stage("fetch-chat")
            chat_path = Path(download_replay_chat(url, out) if korean else download_chat(url, out, ytdlp=ytdlp))
    reminder = replay_expiry_note(url, load_info(info_path) if info_path is not None else None)
    if reminder and note is not None:
        note(reminder)
    return info_path, chat_path


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


# --------------------------------------------------------------------------- CHZZK / SOOP replay chat

CHZZK_API = "https://api.chzzk.naver.com/service"
SOOP_VIEW_API = "https://api.m.sooplive.co.kr/station/video/a/view"
#: ``get(url, data=None) -> bytes``; tests pass their own so nothing touches the network.
Transport = Callable[..., bytes]


def _http_get(url: str, data: bytes | None = None) -> bytes:
    import urllib.request

    headers = {"User-Agent": "Mozilla/5.0 (stream2clip)"}
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    request = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - fixed https hosts
        return response.read()


def platform_of(url: str) -> str | None:
    """``"chzzk"`` / ``"soop"`` for their replay URLs, else ``None`` (yt-dlp handles the rest)."""
    lowered = url.lower()
    if "chzzk.naver.com" in lowered:
        return "chzzk"
    if "sooplive.co.kr" in lowered or "afreecatv.com" in lowered:
        return "soop"
    return None


#: Since 2026-06-01 SOOP deletes a basic streamer's replay 90 days after it went up (a year once it has
#: 50 unique views); clips and Catch videos stay. https://sooplive.helpshift.com/hc/en/3-soop/faq/284-notice-changes-to-vod-replay-retention-policy/
SOOP_REPLAY_DAYS = 90


def replay_expiry_note(url: str, info: "dict[str, Any] | None" = None, *, today: "date | None" = None) -> str | None:
    """A reminder to keep a SOOP replay's video and chat before SOOP deletes it; ``None`` for other sites.

    With the info JSON's ``upload_date`` (or ``timestamp``) it also says how long ago the replay went up.
    """
    if platform_of(url or "") != "soop":
        return None
    from .i18n import tr

    rule = tr("SOOP 다시보기는 일반 스트리머 기준 올라온 지 {0}일 후 삭제(고유 조회 50회 이상이면 1년).").format(SOOP_REPLAY_DAYS)
    uploaded = None
    if info:
        if str(info.get("upload_date") or "").isdigit() and len(str(info["upload_date"])) == 8:
            uploaded = datetime.strptime(str(info["upload_date"]), "%Y%m%d").date()
        elif isinstance(info.get("timestamp"), (int, float)):
            uploaded = datetime.fromtimestamp(float(info["timestamp"]), tz=timezone.utc).date()
    if uploaded is None:
        return rule + " " + tr("클립에 쓸 영상과 채팅은 미리 받아 두기")
    days = ((today or date.today()) - uploaded).days
    return rule + " " + tr("이 다시보기는 올라온 지 {0}일. 클립에 쓸 영상과 채팅은 미리 받아 두기").format(max(0, days))


def chzzk_video_no(url_or_number: str) -> str:
    """``https://chzzk.naver.com/video/16230061`` (or just the number) -> ``"16230061"``."""
    match = re.search(r"/video/(\d+)", url_or_number) or re.fullmatch(r"\s*(\d+)\s*", url_or_number)
    if not match:
        raise ValueError(f"Not a CHZZK replay URL (expected .../video/<number>): {url_or_number}")
    return match.group(1)


def soop_title_no(url_or_number: str) -> str:
    """``https://vod.sooplive.co.kr/player/212422389`` (or just the number) -> ``"212422389"``."""
    match = re.search(r"/player/(\d+)", url_or_number) or re.search(r"[?&]nTitleNo=(\d+)", url_or_number) or re.fullmatch(r"\s*(\d+)\s*", url_or_number)
    if not match:
        raise ValueError(f"Not a SOOP VOD URL (expected .../player/<number>): {url_or_number}")
    return match.group(1)


def fetch_chzzk_chat(video: str, *, get: Transport | None = None, max_pages: int = 20000, on_page: Callable[[int, float], None] | None = None) -> "list[ChatMessage]":
    """Download the whole chat of a CHZZK replay (no login). Old replays may have no chat left."""
    from .chat import parse_chzzk

    get = get or _http_get
    number = chzzk_video_no(video)
    messages: list = []
    cursor, previous = 0, None
    for page_index in range(max_pages):
        page = json.loads(get(f"{CHZZK_API}/v1/videos/{number}/chats?playerMessageTime={cursor}&previousVideoChatSize=50"))
        if page.get("code") not in (None, 200):
            raise RuntimeError(f"CHZZK chat request failed: {page.get('code')} {page.get('message')}")
        messages += parse_chzzk(page)
        if on_page is not None:
            on_page(page_index + 1, cursor / 1000)
        cursor = (page.get("content") or {}).get("nextPlayerMessageTime")
        if cursor is None or cursor == previous:
            break
        previous = cursor
    messages.sort(key=lambda m: m.time)
    return messages


def fetch_soop_chat(video: str, *, get: Transport | None = None, on_page: Callable[[int, float], None] | None = None) -> "list[ChatMessage]":
    """Download the whole chat of a SOOP VOD (no login for public VODs).

    A VOD can be several files; each has its own chat, read in 300-second pieces, and
    its times are shifted by the length of the files before it.
    """
    import urllib.error
    import urllib.parse

    from .chat import parse_soop

    get = get or _http_get
    number = soop_title_no(video)
    view = json.loads(get(SOOP_VIEW_API, urllib.parse.urlencode({"nTitleNo": number, "nApiLevel": 10, "nPlaylistIdx": 0}).encode()))
    data = view.get("data") or {}
    files = data.get("files") or []
    if view.get("result") != 1 or not files:
        raise RuntimeError(f"SOOP VOD {number} is not available (private, deleted or login required)")
    messages: list = []
    offset, pages = 0.0, 0
    for part in files:
        length = float(part.get("duration") or 0) / 1000
        chat_url = part.get("chat")
        start = 0
        while chat_url and start < length + 300:
            try:
                xml = get(f"{chat_url}{'&' if '?' in chat_url else '?'}startTime={start}").decode("utf-8", "replace")
            except urllib.error.HTTPError as exc:
                if exc.code == 404:  # past the last piece
                    break
                raise
            messages += parse_soop(xml, offset=offset)
            pages += 1
            if on_page is not None:
                on_page(pages, offset + start)
            start += 300
        offset += length
    messages.sort(key=lambda m: m.time)
    return messages


def download_replay_chat(url: str, out_dir: str | os.PathLike[str], *, get: Transport | None = None, on_page: Callable[[int, float], None] | None = None) -> Path:
    """Collect CHZZK / SOOP replay chat and save it normalized as ``<platform>_<id>.chat.jsonl``.

    The file has one ``{"time", "text", "author", "kind", "amount", "currency"}`` object per
    line with authors already hashed - nicknames and user ids are not written to disk.
    """
    from .chat import save_chat_jsonl

    platform = platform_of(url)
    if platform == "chzzk":
        number, messages = chzzk_video_no(url), fetch_chzzk_chat(url, get=get, on_page=on_page)
    elif platform == "soop":
        number, messages = soop_title_no(url), fetch_soop_chat(url, get=get, on_page=on_page)
    else:
        raise ValueError(f"Not a CHZZK or SOOP URL: {url}")
    if not messages:
        raise RuntimeError("no chat messages came back (the replay has no chat, or it has expired)")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    return save_chat_jsonl(messages, out / f"{platform}_{number}.chat.jsonl")
