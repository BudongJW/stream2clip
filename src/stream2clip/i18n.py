"""Interface language: Korean (the language the texts are written in), Japanese, English.

``tr("저장")`` returns the text in the current language. Korean texts are the keys, so
the code reads as before and a missing translation falls back to Korean instead of
failing. The catalogs are plain JSON files in ``stream2clip/locales``.

The language is, in this order: :func:`set_language`, the ``STREAM2CLIP_LANG``
environment variable, the language chosen in the Windows installer (a ``language.txt``
next to the programs), the system's language (Korean / Japanese, anything else gets
English). Texts placed in module-level tables are looked up when that module is
imported, so the app decides the language before it imports its windows.
"""

from __future__ import annotations

import json
import locale
import os
import sys
from pathlib import Path

__all__ = ["LANGUAGES", "language", "set_language", "tr", "mark", "shown", "catalog", "system_language", "installed_language", "INSTALL_FILE"]

LANGUAGES = {"ko": "한국어", "ja": "日本語", "en": "English"}
#: Written by the Windows installer next to the programs: the language picked on its first page.
INSTALL_FILE = "language.txt"
_current: str | None = None
_catalogs: dict[str, dict[str, str]] = {}


def _normalize(code: str | None) -> str | None:
    if not code:
        return None
    short = code.strip().lower().replace("-", "_").split("_")[0]
    aliases = {"korean": "ko", "kor": "ko", "japanese": "ja", "jpn": "ja", "jp": "ja", "english": "en", "eng": "en", "c": "en", "posix": "en"}
    short = aliases.get(short, short)
    return short if short in LANGUAGES else None


def system_language() -> str:
    """``ko`` / ``ja`` when the system is set to that language, else ``en``."""
    names: list[str | None] = []
    if sys.platform == "win32":
        try:
            import ctypes

            lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF  # primary language id
            names.append({0x12: "ko", 0x11: "ja", 0x09: "en"}.get(lang_id))
        except Exception:
            pass
    names += [os.environ.get(name) for name in ("LC_ALL", "LC_MESSAGES", "LANG")]
    try:
        names.append(locale.getlocale()[0])
    except (ValueError, TypeError):
        pass
    for name in names:
        code = _normalize(name)
        if code:
            return code
    return "en"


def installed_language(folder: str | os.PathLike[str] | None = None) -> str | None:
    """The language chosen when the programs were installed, or ``None`` (not installed that way, unreadable file).

    ``folder`` is where the programs are; by default the folder of the built executable.
    """
    if folder is None:
        if not getattr(sys, "frozen", False):
            return None
        folder = Path(sys.executable).parent
    try:
        return _normalize((Path(folder) / INSTALL_FILE).read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError):
        return None


def language() -> str:
    global _current
    if _current is None:
        _current = _normalize(os.environ.get("STREAM2CLIP_LANG")) or installed_language() or system_language()
    return _current


def set_language(code: str | None) -> str:
    """Choose the language (``None`` goes back to the environment / system setting); returns the one in use."""
    global _current
    _current = _normalize(code)
    return language()


def catalog(code: str) -> dict[str, str]:
    """Korean text -> translation for one language (empty for Korean itself or a missing file)."""
    if code not in _catalogs:
        data: dict[str, str] = {}
        path = Path(__file__).parent / "locales" / f"{code}.json"
        if code != "ko" and path.is_file():
            loaded = json.loads(path.read_text(encoding="utf-8"))
            data = {str(k): str(v) for k, v in loaded.items()}
        _catalogs[code] = data
    return _catalogs[code]


def tr(text: str) -> str:
    """``text`` (written in Korean) in the current language."""
    code = language()
    if code == "ko":
        return text
    return catalog(code).get(text, text)


def mark(text: str) -> str:
    """A text that sits in a table and is translated where it is shown, with :func:`shown`. Returned unchanged.

    The catalogs are checked against every text passed to :func:`tr` or to this function.
    """
    return text


def shown(text: str) -> str:
    """The current language's version of a text that went through :func:`mark`."""
    return tr(text)
