"""Mouse cursor overlay for recordings (screen grabbers usually omit the cursor)."""

from __future__ import annotations

import sys
from typing import Callable

import numpy as np
from PIL import Image, ImageDraw

__all__ = ["CursorProvider", "draw_cursor", "system_cursor_position", "cursor_sprite"]

#: Returns the cursor position in the same physical pixel space as the capture, or None.
CursorProvider = Callable[[], "tuple[int, int] | None"]

# Classic arrow, hotspot at (0, 0), 12x19 logical pixels.
_ARROW = [(0, 0), (0, 16), (4, 12), (7, 18), (9, 17), (6, 11), (11, 11)]
_SPRITES: dict[float, Image.Image] = {}


def cursor_sprite(scale: float = 1.0) -> Image.Image:
    if scale not in _SPRITES:
        ss = 4  # supersample for smooth edges
        size = (int(14 * scale * ss), int(21 * scale * ss))
        img = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        pts = [(1 * ss + x * scale * ss, 1 * ss + y * scale * ss) for x, y in _ARROW]
        draw.polygon(pts, fill=(255, 255, 255, 255), outline=(0, 0, 0, 255), width=max(1, int(1.2 * scale * ss)))
        _SPRITES[scale] = img.resize((size[0] // ss, size[1] // ss), Image.Resampling.LANCZOS)
    return _SPRITES[scale]


def draw_cursor(frame: np.ndarray, x: int, y: int, *, scale: float = 1.0) -> np.ndarray:
    """Alpha-composite an arrow cursor with its hotspot at ``(x, y)`` (frame-local pixels)."""
    h, w = frame.shape[:2]
    sprite = cursor_sprite(scale)
    if x >= w or y >= h or x + sprite.width <= 0 or y + sprite.height <= 0:
        return frame
    img = Image.fromarray(frame, "RGBA")
    img.alpha_composite(sprite, dest=(max(x, 0), max(y, 0)), source=(max(-x, 0), max(-y, 0)))
    return np.asarray(img).copy()


def system_cursor_position() -> "tuple[int, int] | None":
    """Best-effort OS cursor position in physical pixels (Windows natively, else mss-free fallbacks)."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        point = wintypes.POINT()
        if ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
            return (point.x, point.y)
        return None
    return None
