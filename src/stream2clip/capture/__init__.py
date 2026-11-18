"""Screen capture backends.

A backend is anything implementing :class:`CaptureBackend`. The default uses
`mss <https://github.com/BoboTiG/python-mss>`_ (Windows / macOS / X11). Other
projects can register their own backend (e.g. an OBS source, a game capture
hook, a video file) through :func:`stream2clip.plugins.register_capture_backend`
or the ``stream2clip.capture_backends`` entry-point group.
"""

from __future__ import annotations

from typing import Callable, Protocol, runtime_checkable

import numpy as np
from PIL import Image

from ..frames import to_image
from ..geometry import Region
from .array import ArrayBackend
from .cursor import draw_cursor, system_cursor_position

__all__ = [
    "CaptureBackend",
    "ArrayBackend",
    "BackendFactory",
    "default_backend",
    "grab_image",
    "draw_cursor",
    "system_cursor_position",
]


@runtime_checkable
class CaptureBackend(Protocol):
    """Minimal interface: report screen geometry and grab RGBA pixels."""

    name: str

    def virtual_screen(self) -> Region:
        """Bounding box of all monitors in physical pixels."""

    def monitors(self) -> list[Region]:
        """Individual monitors in physical pixels."""

    def grab(self, region: Region | None = None) -> np.ndarray:
        """Return an ``(h, w, 4) uint8`` RGBA frame of ``region`` (default: virtual screen)."""

    def close(self) -> None: ...


BackendFactory = Callable[[], CaptureBackend]


def default_backend() -> CaptureBackend:
    """Return the best available backend (plugins first, then mss)."""
    from ..plugins import capture_backends

    for name, factory in capture_backends().items():
        if name != "mss":
            try:
                return factory()
            except Exception:  # pragma: no cover - broken third-party plugin
                continue
    from .mss_backend import MssBackend

    return MssBackend()


def grab_image(region: Region | None = None, *, monitor: int | None = None, backend: CaptureBackend | None = None) -> Image.Image:
    """Capture a region, a monitor (0-based index) or the whole virtual screen as a PIL image."""
    owned = backend is None
    backend = backend or default_backend()
    try:
        if monitor is not None:
            monitors = backend.monitors()
            if not 0 <= monitor < len(monitors):
                raise IndexError(f"Monitor {monitor} not found; {len(monitors)} available")
            region = monitors[monitor]
        return to_image(backend.grab(region))
    finally:
        if owned:
            backend.close()
