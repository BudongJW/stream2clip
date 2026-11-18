"""Remember the app's choices between runs.

One small JSON file (``settings.json``) in the user's config folder, split into
sections (one per window). Passwords are never written here. A missing or broken
file just means the defaults, and a folder that cannot be written is not an error:
the app then simply forgets.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

__all__ = ["config_dir", "settings_path", "load_section", "save_section"]

FILE_NAME = "settings.json"


def config_dir() -> Path:
    """``STREAM2CLIP_CONFIG_DIR``, else the platform's usual place for app settings."""
    override = os.environ.get("STREAM2CLIP_CONFIG_DIR")
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = os.environ.get("APPDATA")
        return (Path(base) if base else Path.home() / "AppData" / "Roaming") / "stream2clip"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "stream2clip"
    base = os.environ.get("XDG_CONFIG_HOME")
    return (Path(base) if base else Path.home() / ".config") / "stream2clip"


def settings_path() -> Path:
    return config_dir() / FILE_NAME


def _read() -> dict[str, Any]:
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def load_section(name: str) -> dict[str, Any]:
    """What was saved for one window (``{}`` when nothing usable is there)."""
    section = _read().get(name)
    return dict(section) if isinstance(section, dict) else {}


def save_section(name: str, values: dict[str, Any]) -> Path | None:
    """Replace one section, keep the others; returns the file, or ``None`` if it could not be written."""
    data = _read()
    data[name] = values
    path = settings_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        return None
    return path
