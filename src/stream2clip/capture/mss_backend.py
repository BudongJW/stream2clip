"""Cross-platform screen capture through ``mss`` (pip install "stream2clip[capture]")."""

from __future__ import annotations

import sys
import threading

import numpy as np

from ..geometry import Region

__all__ = ["MssBackend", "enable_dpi_awareness"]


def enable_dpi_awareness() -> None:
    """On Windows, opt into per-monitor DPI awareness so coordinates are physical pixels."""
    if sys.platform != "win32":
        return
    import ctypes

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
    except Exception:  # pragma: no cover - Windows only / already set
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


class MssBackend:
    """mss handles are thread-affine, so one is created lazily per thread."""

    name = "mss"

    def __init__(self) -> None:
        try:
            import mss  # noqa: F401
        except ImportError as exc:  # pragma: no cover - depends on extras
            raise RuntimeError('Screen capture needs mss: pip install "stream2clip[capture]"') from exc
        self._local = threading.local()
        self._all: list[object] = []
        self._lock = threading.Lock()

    def _sct(self):
        sct = getattr(self._local, "sct", None)
        if sct is None:
            import mss

            factory = getattr(mss, "MSS", None) or mss.mss  # mss >= 10 renamed the class
            sct = factory()
            self._local.sct = sct
            with self._lock:
                self._all.append(sct)
        return sct

    @staticmethod
    def _to_region(mon: dict) -> Region:
        return Region(int(mon["left"]), int(mon["top"]), int(mon["width"]), int(mon["height"]))

    def virtual_screen(self) -> Region:
        return self._to_region(self._sct().monitors[0])

    def monitors(self) -> list[Region]:
        return [self._to_region(m) for m in self._sct().monitors[1:]]

    def grab(self, region: Region | None = None) -> np.ndarray:
        region = region or self.virtual_screen()
        shot = self._sct().grab({"left": region.x, "top": region.y, "width": region.width, "height": region.height})
        bgra = np.frombuffer(shot.bgra, dtype=np.uint8).reshape(shot.height, shot.width, 4)
        rgba = bgra[..., [2, 1, 0, 3]].copy()
        rgba[..., 3] = 255  # screen pixels are always opaque
        return rgba

    def close(self) -> None:
        with self._lock:
            for sct in self._all:
                try:
                    sct.close()  # type: ignore[attr-defined]
                except Exception:  # pragma: no cover
                    pass
            self._all.clear()
        self._local = threading.local()
