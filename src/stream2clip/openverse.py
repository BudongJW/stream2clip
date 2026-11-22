"""Find Creative Commons music and sound effects on Openverse (openverse.org) and read what a track's license asks for.

Openverse indexes openly licensed audio from Freesound, Jamendo, ccMixter and Wikimedia
Commons. Its API needs no key for a few requests (anonymous use is rate limited). This module
only searches and reads one track's facts - title, creator, license, attribution line, the page
it lives on - so that a file the user downloaded from that page can go into the sound library
with them. It downloads nothing and pages through nothing in bulk: the Openverse terms forbid
scraping, and every source site has terms of its own. Openverse does not check the licenses it
lists, so the page itself is the one to trust.

Standard library only; ``get(url) -> bytes`` is replaceable so tests touch no network.
"""

from __future__ import annotations

import json
import re
import urllib.parse
from dataclasses import dataclass
from typing import Callable

__all__ = ["API", "OpenverseAudio", "OpenverseError", "audio_detail", "license_key", "search_audio"]

API = "https://api.openverse.org/v1/audio/"
#: ``get(url) -> bytes``.
Transport = Callable[[str], bytes]
_LENGTHS = {"sound_effect": "shortest", "music": "short,medium"}
_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class OpenverseError(RuntimeError):
    pass


def _http_get(url: str) -> bytes:
    import urllib.error
    import urllib.request

    from . import __version__

    request = urllib.request.Request(url, headers={"User-Agent": f"stream2clip/{__version__} (+https://github.com/BudongJW/stream2clip)", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 - fixed https host
            return response.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise OpenverseError("Openverse asks to slow down (too many requests without a key): try again in a minute") from exc
        raise OpenverseError(f"Openverse answered {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise OpenverseError(f"Openverse cannot be reached: {exc.reason}") from exc


def license_key(code: str | None, version: str | None) -> str:
    """The :data:`stream2clip.soundtrack.LICENSES` key for an Openverse license (``""`` when none fits, e.g. Sampling+)."""
    from .soundtrack import LICENSES

    code = (code or "").strip().lower()
    version = (version or "").strip()
    if code == "cc0":
        return "cc0"
    if code == "pdm":
        return "pdm"
    key = f"cc-{code}-{version}" if code and version else ""
    return key if key in LICENSES else ""


@dataclass(frozen=True)
class OpenverseAudio:
    id: str
    title: str
    creator: str
    license: str
    license_version: str
    license_url: str
    page: str
    provider: str
    attribution: str
    seconds: float | None
    filetype: str

    @classmethod
    def from_api(cls, item: dict) -> "OpenverseAudio":
        duration = item.get("duration")
        return cls(
            id=str(item.get("id") or ""), title=str(item.get("title") or "").strip(), creator=str(item.get("creator") or "").strip(),
            license=str(item.get("license") or ""), license_version=str(item.get("license_version") or ""), license_url=str(item.get("license_url") or ""),
            page=str(item.get("foreign_landing_url") or ""), provider=str(item.get("provider") or item.get("source") or ""),
            attribution=" ".join(str(item.get("attribution") or "").split()), seconds=float(duration) / 1000 if duration else None,
            filetype=str(item.get("filetype") or ""),
        )

    @property
    def key(self) -> str:
        return license_key(self.license, self.license_version)

    def facts(self) -> dict[str, str]:
        """What :meth:`stream2clip.soundtrack.SoundLibrary.add` takes: title, author, page, license key, credit line."""
        return {"title": self.title, "author": self.creator, "url": self.page, "license": self.key, "credit": self.attribution}


def _results(raw: bytes) -> dict:
    try:
        data = json.loads(raw.decode("utf-8"))
    except ValueError as exc:
        raise OpenverseError("Openverse sent something that is not JSON") from exc
    if not isinstance(data, dict):
        raise OpenverseError("Openverse sent an unexpected answer")
    return data


def search_audio(query: str, *, commercial: bool = True, kind: str | None = None, limit: int = 20, get: Transport | None = None) -> list[OpenverseAudio]:
    """One page of Openverse audio for ``query``.

    ``commercial`` keeps to licenses that allow commercial use and changes (what a monetized clip
    with music put to picture needs). ``kind`` narrows by length: ``sound_effect`` under 30 s,
    ``music`` 30 s to 10 min. (Openverse's own category is filled for Jamendo only, so filtering
    on it hid every Freesound track.)
    """
    if not query.strip():
        raise ValueError("Search for something")
    params = {"q": query.strip(), "page_size": str(max(1, min(20, limit)))}
    if commercial:
        params["license_type"] = "commercial,modification"
    if kind:
        if kind not in _LENGTHS:
            raise ValueError("kind is music or sound_effect")
        params["length"] = _LENGTHS[kind]
    data = _results((get or _http_get)(API + "?" + urllib.parse.urlencode(params)))
    return [OpenverseAudio.from_api(item) for item in data.get("results", []) if isinstance(item, dict)]


def audio_detail(audio_id: str, *, get: Transport | None = None) -> OpenverseAudio:
    """The facts of one Openverse track by its id (as ``search_audio`` lists it)."""
    audio_id = audio_id.strip().lower()
    if not _ID.match(audio_id):
        raise ValueError(f"{audio_id!r} is not an Openverse id (8-4-4-4-12 hexadecimal digits)")
    return OpenverseAudio.from_api(_results((get or _http_get)(f"{API}{audio_id}/")))
