"""What the Android app asks of the stream2clip core: highlights from a replay's chat, with titles and descriptions.

The app runs this module with Chaquopy, beside the ``stream2clip`` package itself (built in from the
repository's ``src`` folder). An Android app cannot start another Python, so yt-dlp runs in this
process instead of as a command. Everything comes back as JSON text for the Kotlin side.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

#: Highlight lengths per form, from the desktop presets (``stream2clip.presets``).
FORMS = ("shorts", "clip")


def set_language(code: str) -> None:
    """Show the core's texts (highlight reasons, guideline notes) in the phone's language: ko, ja or en."""
    os.environ["STREAM2CLIP_LANG"] = (code or "ko").split("-")[0].lower()


def video_info(url: str) -> dict[str, Any]:
    """yt-dlp's information on a replay, in this process, plus what CHZZK's own API adds (game, start day)."""
    import yt_dlp

    from stream2clip.sources import with_platform_details

    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True, "noprogress": True}) as ydl:
        info = ydl.sanitize_info(ydl.extract_info(url, download=False))
    return with_platform_details(url, info)


def pick_stream(info: dict[str, Any], *, max_height: int = 1080) -> dict[str, Any] | None:
    """The address the phone plays and cuts from: the tallest format with both picture and sound, up to ``max_height``."""
    best = None
    for fmt in info.get("formats") or []:
        if not fmt.get("url") or (fmt.get("vcodec") or "none") == "none" or (fmt.get("acodec") or "none") == "none":
            continue
        height = int(fmt.get("height") or 0)
        if height > max_height:
            continue
        key = (height, float(fmt.get("tbr") or 0))
        if best is None or key > best[0]:
            best = (key, fmt)
    if best is None:
        return None
    fmt = best[1]
    return {"url": fmt["url"], "height": int(fmt.get("height") or 0), "protocol": fmt.get("protocol") or "",
            "headers": {str(k): str(v) for k, v in (fmt.get("http_headers") or {}).items()}}


def _youtube_chat(url: str, work_dir: Path) -> Path:
    """The live chat replay of a YouTube stream, as ``stream2clip fetch`` writes it (yt-dlp in this process)."""
    import yt_dlp

    options = {"quiet": True, "no_warnings": True, "skip_download": True, "writesubtitles": True, "subtitleslangs": ["live_chat"],
               "outtmpl": str(work_dir / "%(id)s.%(ext)s")}
    with yt_dlp.YoutubeDL(options) as ydl:
        ydl.download([url])
    found = sorted(work_dir.glob("*.live_chat.json"))
    if not found:
        raise RuntimeError("no chat replay came back for this video")
    return found[-1]


class _Progress:
    """Forwards the core's stages to the app's ``update(stage, fraction)`` (fraction is -1 when not known)."""

    def __init__(self, sink: Any = None) -> None:
        self.sink = sink

    def __call__(self, stage: str, fraction: float = -1.0) -> None:
        if self.sink is not None:
            self.sink.update(stage, float(fraction))


def analyse(url: str, work_dir: str, form: str = "shorts", language: str = "ko", progress: Any = None) -> str:
    """Find the highlights of a CHZZK, SOOP or YouTube replay from its chat; JSON with the source, a stream and the clips."""
    from stream2clip.chat import load_chat
    from stream2clip.highlights import HighlightConfig
    from stream2clip.pipeline import find_highlights
    from stream2clip.presets import get_preset
    from stream2clip.sources import platform_of, source_from_info

    set_language(language)
    tell = _Progress(progress)
    folder = Path(work_dir)
    folder.mkdir(parents=True, exist_ok=True)
    platform = platform_of(url)

    tell("info")
    try:
        info = video_info(url)
    except Exception as exc:  # noqa: BLE001 - CHZZK and SOOP sometimes refuse; the chat still works
        if platform is None:
            raise
        info = {"webpage_url": url, "info_error": str(exc)}
    source = source_from_info(info)
    info_path = None
    if info.get("heatmap"):  # YouTube's most replayed parts count in the detection, as on the desktop
        info_path = folder / "info.json"
        info_path.write_text(json.dumps({"heatmap": info["heatmap"]}, ensure_ascii=False), encoding="utf-8")

    tell("chat", 0.0)
    if platform is not None:
        from stream2clip.sources import download_replay_chat

        length = float(info.get("duration") or 0)
        chat_path = download_replay_chat(url, folder, on_page=lambda _page, at: tell("chat", min(1.0, at / length) if length else -1.0))
    else:
        chat_path = _youtube_chat(url, folder)
    messages = load_chat(chat_path)

    tell("detect")
    preset = get_preset(form if form in FORMS else "shorts")
    config = HighlightConfig(lead=preset.lead, tail=preset.tail, min_length=preset.min_length, max_length=preset.max_length, top=preset.top)
    result = find_highlights(messages=messages, info=info_path, config=config, source={"url": url, "title": source.title})
    clips = [clip_text(h, source, language) for h in result.highlights]
    stream = pick_stream(info)
    return json.dumps({
        "source": {"url": source.url or url, "title": source.title, "channel": source.channel, "duration": source.duration,
                   "stream_date": source.stream_date, "category": source.category, "game": source.game, "platform": platform or ""},
        "stream": stream, "form": preset.key, "messages": len(messages), "clips": clips,
        "note": info.get("info_error", ""),
    }, ensure_ascii=False)


def clip_text(h: Any, source: Any, language: str = "ko") -> dict[str, Any]:
    """One highlight as the app shows it: times, reasons, and the title, hashtags and description to paste."""
    from stream2clip.compliance import build_description
    from stream2clip.sources import platform_of
    from stream2clip.titles import clip_title, hook_line, title_language

    # No captions on the phone: the stream title's script decides, as on the desktop without subtitles.
    # The phone's language only when the title says nothing (no title, or Latin letters only).
    lang = title_language(fallback=source.title) if source.title else language
    if lang == "en" and language in ("ko", "ja") and not any(ch.isalpha() and ord(ch) < 128 for ch in source.title):
        lang = language
    named = clip_title(peak=h.peak - h.start, channel=source.channel, stream_title=source.title, language=lang,
                       platform=platform_of(source.url) if source.url else None)
    description = build_description(source, start=h.start, end=h.end, summary=" / ".join(h.reasons[:2]), hashtags=named.hashtags, language=named.language)
    # The words drawn on the video: the whole line, not cut to the title's length, and without the [name] tag
    # (the channel is already credited in the corner). The app lets the user rewrite both.
    caption = hook_line((), 0.0, width=CAPTION_WIDTH, fallback=source.title) or named.hook
    return {"rank": h.rank, "start": round(h.start, 2), "end": round(h.end, 2), "peak": round(h.peak, 2), "score": round(h.score, 2),
            "reasons": list(h.reasons), "title": named.title, "caption": caption, "hashtags": list(named.hashtags), "description": description,
            "link": source.timestamp_url(h.start) if source.url else ""}


#: How long the text on the video may be, in full-width characters: three lines on a Short.
CAPTION_WIDTH = 60
