"""Is there a newer release of stream2clip?

One request to GitHub's public API for the latest release of this project; nothing about the
user or the PC is sent with it. The app asks at most once a day and can be told not to ask at
all (its notice has a button for that, and ``STREAM2CLIP_NO_UPDATE_CHECK=1`` turns it off from
outside). Only the standard library is used.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

from . import __version__

__all__ = ["DOWNLOAD_PAGE", "RELEASES_API", "RELEASES_PAGE", "Release", "check_for_update", "enabled", "is_newer", "latest_release", "parse_version"]

RELEASES_API = "https://api.github.com/repos/BudongJW/stream2clip/releases/latest"
RELEASES_PAGE = "https://github.com/BudongJW/stream2clip/releases/latest"
#: Where a person downloads the installer: the project's home page.
DOWNLOAD_PAGE = "https://budongjw.github.io/stream2clip/"
_OWN_PAGES = ("https://github.com/BudongJW/stream2clip/",)


@dataclass(frozen=True)
class Release:
    version: str  # "0.12.0", without the tag's "v"
    url: str      # the release's page


def enabled() -> bool:
    """Whether looking for a newer release is allowed at all (``STREAM2CLIP_NO_UPDATE_CHECK`` forbids it)."""
    return os.environ.get("STREAM2CLIP_NO_UPDATE_CHECK", "").strip().lower() not in ("1", "true", "yes", "on")


def parse_version(text: str) -> tuple[int, ...]:
    """``"v0.11.0"`` -> ``(0, 11, 0)``; ``()`` for anything that is not a plain release number."""
    match = re.fullmatch(r"v?(\d+(?:\.\d+){0,3})", str(text).strip())
    return tuple(int(part) for part in match.group(1).split(".")) if match else ()


def is_newer(candidate: str, current: str = __version__) -> bool:
    """A plain release number above the current one (a pre-release or an unreadable tag is never "newer")."""
    new, now = parse_version(candidate), parse_version(current)
    if not new or not now:
        return False
    width = max(len(new), len(now))
    return new + (0,) * (width - len(new)) > now + (0,) * (width - len(now))


def latest_release(*, opener: Callable[..., Any] | None = None, timeout: float = 5.0) -> Release:
    """The project's latest published release. Raises ``OSError`` when it cannot be asked, ``ValueError`` on an answer that makes no sense."""
    request = urllib.request.Request(RELEASES_API, headers={"User-Agent": "stream2clip", "Accept": "application/vnd.github+json"})
    with (opener or urllib.request.urlopen)(request, timeout=timeout) as response:  # noqa: S310 - fixed https address
        data = json.loads(response.read(1 << 20).decode("utf-8"))
    tag = data.get("tag_name") if isinstance(data, dict) else None
    if not isinstance(tag, str) or not parse_version(tag):
        raise ValueError(f"Unexpected answer about the latest release: {str(data)[:120]}")
    page = data.get("html_url")
    if not (isinstance(page, str) and page.startswith(_OWN_PAGES)):  # a link is only opened when it is the project's own
        page = RELEASES_PAGE
    return Release(tag.strip().lstrip("v"), page)


def check_for_update(current: str = __version__, *, opener: Callable[..., Any] | None = None, timeout: float = 5.0) -> Release | None:
    """The latest release when it is newer than ``current``, else ``None``. Raises like :func:`latest_release`."""
    release = latest_release(opener=opener, timeout=timeout)
    return release if is_newer(release.version, current) else None
