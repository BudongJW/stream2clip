"""Upload a clip to YouTube (Data API v3 ``videos.insert``).

Uploading publishes under *your* channel, so nothing here runs without your own
Google Cloud OAuth client (``client_secret.json``) and your consent in the browser,
and the privacy status defaults to ``private`` - the API itself defaults to public
when the field is left out.

Quota, from the method's reference page (checked 2026-11,
https://developers.google.com/youtube/v3/docs/videos/insert): one call costs 1 unit of
the Video Uploads quota bucket, limited to 100 calls a day. Check the page before
relying on it - quota rules have changed before.

Needs ``pip install "stream2clip[upload]"`` (google-api-python-client, google-auth-oauthlib).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

from .i18n import tr

__all__ = ["SCOPES", "PRIVACY", "video_resource", "scheduled_time", "shorts_problems", "load_credentials", "upload_video", "video_url"]

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
PRIVACY = ("private", "unlisted", "public")
TITLE_LIMIT = 100
DESCRIPTION_LIMIT = 5000
GAMING_CATEGORY = "20"


def video_resource(
    title: str,
    description: str = "",
    *,
    tags: Sequence[str] = (),
    category_id: str = GAMING_CATEGORY,
    privacy: str = "private",
    made_for_kids: bool = False,
    synthetic_media: bool | None = None,
    language: str | None = None,
    shorts: bool = False,
    publish_at: "datetime | str | None" = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """The ``snippet`` / ``status`` body for ``videos.insert``; raises ``ValueError`` for what YouTube would reject.

    ``synthetic_media`` sets ``status.containsSyntheticMedia`` (altered or synthetic content
    disclosure). ``shorts`` adds ``#Shorts`` to the description when it is not there yet.
    ``publish_at`` schedules the video: it is uploaded private and YouTube makes it public at
    that time (a ``datetime``, or text like ``2026-12-24 18:00``; without a time zone it is
    local time). YouTube only takes a schedule for a private video, and only a future one.
    """
    title = " ".join(title.split())
    if not title:
        raise ValueError("A title is required")
    if len(title) > TITLE_LIMIT:
        raise ValueError(f"The title is {len(title)} characters; YouTube allows {TITLE_LIMIT}")
    if "<" in title or ">" in title or "<" in description or ">" in description:
        raise ValueError("YouTube does not accept < or > in titles and descriptions")
    if privacy not in PRIVACY:
        raise ValueError(f"privacy must be one of {', '.join(PRIVACY)}")
    if shorts and "#shorts" not in (title + " " + description).lower():
        description = (description.rstrip() + "\n\n#Shorts").lstrip()
    if len(description.encode("utf-8")) > DESCRIPTION_LIMIT:
        raise ValueError(f"The description is over {DESCRIPTION_LIMIT} bytes")
    snippet: dict[str, Any] = {"title": title, "description": description, "categoryId": str(category_id)}
    cleaned = [t.strip() for t in tags if t and t.strip()]
    if cleaned:
        snippet["tags"] = cleaned
    if language:
        snippet["defaultLanguage"] = language
    status: dict[str, Any] = {"privacyStatus": privacy, "selfDeclaredMadeForKids": bool(made_for_kids)}
    if publish_at is not None and publish_at != "":
        if privacy != "private":
            raise ValueError("A scheduled video is uploaded private and made public by YouTube at the time given: leave the privacy at private")
        when = scheduled_time(publish_at)
        if when <= (now or datetime.now(timezone.utc)).astimezone(timezone.utc):
            raise ValueError(f"The time to publish at ({when:%Y-%m-%d %H:%M} UTC) is not in the future")
        status["publishAt"] = when.strftime("%Y-%m-%dT%H:%M:%SZ")
    if synthetic_media is not None:
        status["containsSyntheticMedia"] = bool(synthetic_media)
    return {"snippet": snippet, "status": status}


def scheduled_time(value: "datetime | str") -> datetime:
    """A publishing time in UTC. Text is ``YYYY-MM-DD HH:MM`` or ISO 8601; a time without a zone is the local time."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.strip())
        except ValueError:
            raise ValueError(f'Not a date and time: {value!r} (write it like "2026-12-24 18:00")') from None
    return value.astimezone(timezone.utc)  # a naive datetime counts as local time


def shorts_problems(width: int, height: int, duration: float | None) -> list[str]:
    """Why YouTube would not treat a video as a Short (vertical or square, three minutes at most)."""
    problems = []
    if width > height:
        problems.append(tr("가로 영상입니다 ({0}×{1}). Shorts는 세로 또는 정사각형이어야 합니다.").format(width, height))
    if duration is not None and duration > 180:
        problems.append(tr("길이가 {0:.0f}초입니다. Shorts는 3분(180초) 이하여야 합니다.").format(duration))
    return problems


def load_credentials(client_secrets: str | os.PathLike[str], token_path: str | os.PathLike[str] | None = None, *, scopes: Sequence[str] = SCOPES):
    """OAuth credentials for the installed-app flow; opens the browser for consent the first time.

    The refresh token is kept in ``token_path`` (default: ``token.json`` next to the client
    secrets) so later uploads do not ask again. Keep both files out of version control.
    """
    try:
        from google.auth.transport.requests import Request  # type: ignore[import-not-found]
        from google.oauth2.credentials import Credentials  # type: ignore[import-not-found]
        from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError('YouTube upload needs extra packages: pip install "stream2clip[upload]"') from exc
    secrets = Path(client_secrets)
    if not secrets.is_file():
        raise FileNotFoundError(f"OAuth client file not found: {secrets} (create an OAuth client of type Desktop app in Google Cloud and download it)")
    token = Path(token_path) if token_path else secrets.with_name("token.json")
    credentials = Credentials.from_authorized_user_file(str(token), list(scopes)) if token.is_file() else None
    if credentials and credentials.expired and credentials.refresh_token:  # pragma: no cover - needs Google
        credentials.refresh(Request())
    if not credentials or not credentials.valid:  # pragma: no cover - needs a browser and Google
        credentials = InstalledAppFlow.from_client_secrets_file(str(secrets), list(scopes)).run_local_server(port=0)
    token.write_text(credentials.to_json(), encoding="utf-8")  # pragma: no cover
    return credentials  # pragma: no cover


def upload_video(
    path: str | os.PathLike[str],
    resource: dict[str, Any],
    *,
    credentials: Any = None,
    service: Any = None,
    media: Any = None,
    chunk_size: int = 8 * 1024 * 1024,
    on_progress: Callable[[float], None] | None = None,
) -> dict[str, Any]:
    """Resumable upload; returns the API's video resource (``["id"]`` is the new video id).

    Pass ``credentials`` from :func:`load_credentials`, or an already built ``service``
    (and ``media``) - that is what the tests do, so nothing is sent anywhere.
    """
    video = Path(path)
    if not video.is_file():
        raise FileNotFoundError(f"No such video: {video}")
    if service is None or media is None:
        try:
            from googleapiclient.discovery import build  # type: ignore[import-not-found]
            from googleapiclient.http import MediaFileUpload  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError('YouTube upload needs extra packages: pip install "stream2clip[upload]"') from exc
        if service is None:  # pragma: no cover - needs Google
            if credentials is None:
                raise ValueError("credentials or service is required")
            service = build("youtube", "v3", credentials=credentials, cache_discovery=False)
        if media is None:
            media = MediaFileUpload(str(video), chunksize=chunk_size, resumable=True, mimetype="video/*")
    request = service.videos().insert(part="snippet,status", body=resource, media_body=media)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status is not None and on_progress is not None:
            on_progress(float(status.progress()))
    if on_progress is not None:
        on_progress(1.0)
    return response


def video_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"
