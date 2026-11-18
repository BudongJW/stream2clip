"""In-memory capture backend: a fixed image or a callable producing frames.

Used by tests and by pipelines that already have pixels (a decoded video frame,
a game engine render target, a VTuber app's Spout texture copied to numpy...).
"""

from __future__ import annotations

import time
from typing import Callable

import numpy as np

from ..frames import ensure_rgba
from ..geometry import Region

__all__ = ["ArrayBackend"]


class ArrayBackend:
    name = "array"

    def __init__(self, source: "np.ndarray | Callable[[float], np.ndarray]") -> None:
        self._source = source
        self._t0 = time.monotonic()
        first = self._frame()
        self._height, self._width = first.shape[:2]

    def _frame(self) -> np.ndarray:
        if callable(self._source):
            return ensure_rgba(self._source(time.monotonic() - self._t0))
        return ensure_rgba(self._source)

    def virtual_screen(self) -> Region:
        return Region(0, 0, self._width, self._height)

    def monitors(self) -> list[Region]:
        return [self.virtual_screen()]

    def grab(self, region: Region | None = None) -> np.ndarray:
        frame = self._frame()
        if region is None:
            return frame.copy()
        clipped = region.clamp(frame.shape[1], frame.shape[0])
        if clipped is None:
            raise ValueError(f"Region {region} is outside the {frame.shape[1]}x{frame.shape[0]} source")
        return frame[clipped.y : clipped.bottom, clipped.x : clipped.right].copy()

    def close(self) -> None:
        pass
