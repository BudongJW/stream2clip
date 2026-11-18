"""Small, dependency-free geometry primitives shared by every layer."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

__all__ = ["Region", "round_half_up"]

_CSV = re.compile(r"^\s*(-?\d+)\s*[, ]\s*(-?\d+)\s*[, ]\s*(\d+)\s*[, ]\s*(\d+)\s*$")
_GEOMETRY = re.compile(r"^\s*(\d+)x(\d+)([+-]\d+)([+-]\d+)\s*$")


def round_half_up(value: float) -> int:
    """Round to the nearest integer with ``n.5`` going up (``round()`` goes to even)."""
    return math.floor(value + 0.5)


@dataclass(frozen=True)
class Region:
    """Axis-aligned rectangle in integer pixel coordinates (x, y = top-left)."""

    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if self.width < 0 or self.height < 0:
            raise ValueError(f"Region size must be non-negative, got {self.width}x{self.height}")

    @classmethod
    def from_points(cls, x0: float, y0: float, x1: float, y1: float) -> "Region":
        """Build a normalized region from two arbitrary corner points.

        Halves round up (not to even like :func:`round`), so edges that land on
        ``n.5`` at 125% / 150% display scaling always move the same way and a
        region keeps its size wherever it is on the screen.
        """
        left, right = sorted((round_half_up(x0), round_half_up(x1)))
        top, bottom = sorted((round_half_up(y0), round_half_up(y1)))
        return cls(left, top, right - left, bottom - top)

    @classmethod
    def parse(cls, text: str) -> "Region":
        """Parse ``"x,y,w,h"`` or X11-style ``"WxH+X+Y"``."""
        match = _CSV.match(text)
        if match:
            x, y, w, h = (int(v) for v in match.groups())
            return cls(x, y, w, h)
        match = _GEOMETRY.match(text)
        if match:
            w, h, x, y = (int(v) for v in match.groups())
            return cls(x, y, w, h)
        raise ValueError(f"Cannot parse region {text!r}; expected 'x,y,w,h' or 'WxH+X+Y'")

    @classmethod
    def from_list(cls, values: "list[int] | tuple[int, ...]") -> "Region":
        x, y, w, h = (int(v) for v in values)
        return cls(x, y, w, h)

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    @property
    def is_empty(self) -> bool:
        return self.width == 0 or self.height == 0

    def as_box(self) -> tuple[int, int, int, int]:
        """Return ``(left, top, right, bottom)`` as used by Pillow."""
        return (self.x, self.y, self.right, self.bottom)

    def to_list(self) -> list[int]:
        return [self.x, self.y, self.width, self.height]

    def contains(self, px: float, py: float) -> bool:
        return self.x <= px < self.right and self.y <= py < self.bottom

    def intersect(self, other: "Region") -> "Region | None":
        left, top = max(self.x, other.x), max(self.y, other.y)
        right, bottom = min(self.right, other.right), min(self.bottom, other.bottom)
        if right <= left or bottom <= top:
            return None
        return Region(left, top, right - left, bottom - top)

    def clamp(self, width: int, height: int) -> "Region | None":
        """Intersect with a ``width`` x ``height`` canvas anchored at the origin."""
        return self.intersect(Region(0, 0, width, height))

    def translate(self, dx: int, dy: int) -> "Region":
        return Region(self.x + dx, self.y + dy, self.width, self.height)

    def inflate(self, amount: int) -> "Region":
        return Region(self.x - amount, self.y - amount, self.width + 2 * amount, self.height + 2 * amount)

    def scale(self, factor: float) -> "Region":
        """Scale every coordinate (e.g. logical -> physical pixels on HiDPI screens)."""
        return Region.from_points(self.x * factor, self.y * factor, self.right * factor, self.bottom * factor)

    def even(self) -> "Region":
        """Shrink width/height to even numbers (required by yuv420 encoders)."""
        return Region(self.x, self.y, self.width - self.width % 2, self.height - self.height % 2)

    def __str__(self) -> str:
        return f"{self.x},{self.y},{self.width},{self.height}"
