"""Annotation document model (format ``stream2clip.annotation/v1``).

Shapes are immutable dataclasses whose coordinates are in **source image
pixels**. A document is an ordered list of shapes plus an optional crop; it is
rendered non-destructively on top of the original image, so it can be stored
as JSON next to a screenshot or video frame and re-applied by other tools.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, fields, replace
from typing import Any, ClassVar, Union

from ..color import DEFAULT_COLOR, PALETTE, to_hex
from ..geometry import Region

__all__ = [
    "SCHEMA",
    "Point",
    "Pen",
    "Highlighter",
    "Rectangle",
    "Arrow",
    "Text",
    "Mosaic",
    "Transparent",
    "ColorKey",
    "Shape",
    "SHAPE_TYPES",
    "EditState",
    "shape_to_dict",
    "shape_from_dict",
    "translate_shape",
    "state_to_dict",
    "state_from_dict",
]

SCHEMA = "stream2clip.annotation/v1"
Point = tuple[float, float]


@dataclass(frozen=True)
class Pen:
    """Freehand stroke (펜)."""

    kind: ClassVar[str] = "pen"
    points: tuple[Point, ...]
    color: str = DEFAULT_COLOR
    width: float = 6.0


@dataclass(frozen=True)
class Highlighter:
    """Translucent wide stroke (형광펜); overlapping parts of one stroke don't darken."""

    kind: ClassVar[str] = "highlighter"
    points: tuple[Point, ...]
    color: str = PALETTE["yellow"]
    width: float = 18.0
    opacity: float = 0.4


@dataclass(frozen=True)
class Rectangle:
    """Rectangle outline, optionally filled (네모)."""

    kind: ClassVar[str] = "rect"
    rect: Region
    color: str = DEFAULT_COLOR
    width: float = 6.0
    fill: str | None = None


@dataclass(frozen=True)
class Arrow:
    """Straight arrow from ``start`` to ``end`` (화살표)."""

    kind: ClassVar[str] = "arrow"
    start: Point
    end: Point
    color: str = DEFAULT_COLOR
    width: float = 6.0


@dataclass(frozen=True)
class Text:
    """Text label anchored at its top-left corner (글자)."""

    kind: ClassVar[str] = "text"
    position: Point
    text: str
    color: str = DEFAULT_COLOR
    size: float = 28.0
    background: str | None = None


@dataclass(frozen=True)
class Mosaic:
    """Pixelate a region (모자이크)."""

    kind: ClassVar[str] = "mosaic"
    rect: Region
    block: int = 12


@dataclass(frozen=True)
class Transparent:
    """Erase a region to full transparency (투명 - 영역)."""

    kind: ClassVar[str] = "transparent"
    rect: Region


@dataclass(frozen=True)
class ColorKey:
    """Make every pixel close to ``color`` transparent (투명 - 색상, chroma key)."""

    kind: ClassVar[str] = "colorkey"
    color: str
    similarity: float = 0.1
    blend: float = 0.0


Shape = Union[Pen, Highlighter, Rectangle, Arrow, Text, Mosaic, Transparent, ColorKey]
SHAPE_TYPES: dict[str, type] = {cls.kind: cls for cls in (Pen, Highlighter, Rectangle, Arrow, Text, Mosaic, Transparent, ColorKey)}


@dataclass(frozen=True)
class EditState:
    """Immutable snapshot used for undo/redo."""

    items: tuple[Shape, ...] = ()
    crop: Region | None = None

    def with_item(self, shape: Shape) -> "EditState":
        return replace(self, items=self.items + (shape,))

    def without(self, index: int) -> "EditState":
        return replace(self, items=self.items[:index] + self.items[index + 1 :])

    def replaced(self, index: int, shape: Shape) -> "EditState":
        return replace(self, items=self.items[:index] + (shape,) + self.items[index + 1 :])

    def with_crop(self, crop: Region | None) -> "EditState":
        return replace(self, crop=crop)


# --------------------------------------------------------------------------- helpers


def _round(value: float) -> float | int:
    rounded = round(float(value), 2)
    return int(rounded) if rounded.is_integer() else rounded


def shape_to_dict(shape: Shape) -> dict[str, Any]:
    out: dict[str, Any] = {"type": shape.kind}
    for f in fields(shape):
        value = getattr(shape, f.name)
        if isinstance(value, Region):
            value = value.to_list()
        elif f.name == "points":
            value = [[_round(x), _round(y)] for x, y in value]
        elif f.name in ("start", "end", "position"):
            value = [_round(value[0]), _round(value[1])]
        elif f.name in ("color", "fill", "background") and value is not None:
            value = to_hex(value, alpha=len(value) == 9)
        elif isinstance(value, float):
            value = _round(value)
        out[f.name] = value
    return out


def shape_from_dict(data: dict[str, Any]) -> Shape:
    kind = data.get("type")
    cls = SHAPE_TYPES.get(kind)  # type: ignore[arg-type]
    if cls is None:
        raise ValueError(f"Unknown shape type {kind!r}")
    kwargs: dict[str, Any] = {}
    for f in fields(cls):
        if f.name not in data:
            continue
        value = data[f.name]
        if f.name == "rect":
            value = Region.from_list(value)
        elif f.name == "points":
            value = tuple((float(x), float(y)) for x, y in value)
        elif f.name in ("start", "end", "position"):
            value = (float(value[0]), float(value[1]))
        kwargs[f.name] = value
    return cls(**kwargs)


def translate_shape(shape: Shape, dx: float, dy: float) -> Shape:
    """Move a shape by ``(dx, dy)`` pixels. Color keys are global and unaffected."""
    if isinstance(shape, (Pen, Highlighter)):
        return replace(shape, points=tuple((x + dx, y + dy) for x, y in shape.points))
    if isinstance(shape, (Rectangle, Mosaic, Transparent)):
        return replace(shape, rect=shape.rect.translate(round(dx), round(dy)))
    if isinstance(shape, Arrow):
        return replace(shape, start=(shape.start[0] + dx, shape.start[1] + dy), end=(shape.end[0] + dx, shape.end[1] + dy))
    if isinstance(shape, Text):
        return replace(shape, position=(shape.position[0] + dx, shape.position[1] + dy))
    return shape


def state_to_dict(state: EditState, size: tuple[int, int] | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {"schema": SCHEMA}
    if size is not None:
        data["canvas"] = {"width": size[0], "height": size[1]}
    data["crop"] = state.crop.to_list() if state.crop else None
    data["items"] = [shape_to_dict(item) for item in state.items]
    return data


def state_from_dict(data: dict[str, Any] | str) -> EditState:
    if isinstance(data, str):
        data = json.loads(data)
    schema = data.get("schema", SCHEMA)
    if schema != SCHEMA:
        raise ValueError(f"Unsupported annotation schema {schema!r} (expected {SCHEMA!r})")
    crop = data.get("crop")
    return EditState(
        items=tuple(shape_from_dict(item) for item in data.get("items", [])),
        crop=Region.from_list(crop) if crop else None,
    )

