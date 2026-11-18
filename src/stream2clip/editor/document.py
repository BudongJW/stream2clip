"""Mutable editing session around an immutable :class:`EditState` history."""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
from typing import Any

from PIL import Image

from ..geometry import Region
from .history import History
from .model import EditState, Shape, state_from_dict, state_to_dict, translate_shape
from .render import render, render_overlay, shape_bounds

__all__ = ["Document"]

_FLATTEN_FORMATS = {"JPEG", "BMP"}


class Document:
    """An image plus annotations, with undo/redo and save/dirty tracking.

    Example::

        doc = Document(Image.new("RGB", (100, 80), "white"))
        doc.add(Rectangle(Region(10, 10, 40, 30)))
        doc.save("out.png")
    """

    def __init__(self, image: Image.Image, state: EditState | None = None, *, source_path: str | os.PathLike[str] | None = None, font_path: str | None = None) -> None:
        self.image = image.convert("RGBA")
        self.history: History[EditState] = History(state or EditState())
        self._saved: EditState | None = self.history.current if source_path else None
        self.source_path = Path(source_path) if source_path else None
        self.font_path = font_path

    # ------------------------------------------------------------------ construction
    @classmethod
    def open(cls, path: str | os.PathLike[str], *, annotations: str | os.PathLike[str] | None = None) -> "Document":
        with Image.open(path) as img:
            img.load()
            image = img.convert("RGBA")
        state = None
        if annotations:
            state = state_from_dict(Path(annotations).read_text(encoding="utf-8"))
        return cls(image, state, source_path=path)

    # ------------------------------------------------------------------ state
    @property
    def state(self) -> EditState:
        return self.history.current

    @property
    def size(self) -> tuple[int, int]:
        return self.image.size

    @property
    def output_size(self) -> tuple[int, int]:
        if self.state.crop is not None:
            clipped = self.state.crop.clamp(*self.size)
            if clipped is not None:
                return (clipped.width, clipped.height)
        return self.size

    @property
    def dirty(self) -> bool:
        return self._saved is None or self.state != self._saved

    @property
    def can_undo(self) -> bool:
        return self.history.can_undo

    @property
    def can_redo(self) -> bool:
        return self.history.can_redo

    def commit(self, state: EditState) -> EditState:
        return self.history.push(state)

    def add(self, shape: Shape) -> int:
        self.commit(self.state.with_item(shape))
        return len(self.state.items) - 1

    def remove(self, index: int) -> None:
        self.commit(self.state.without(index))

    def replace(self, index: int, shape: Shape) -> None:
        self.commit(self.state.replaced(index, shape))

    def move(self, index: int, dx: float, dy: float) -> None:
        self.replace(index, translate_shape(self.state.items[index], dx, dy))

    def set_crop(self, crop: Region | None) -> None:
        if crop is not None:
            crop = crop.clamp(*self.size)
        self.commit(self.state.with_crop(crop))

    def clear(self) -> None:
        self.commit(EditState())

    def undo(self) -> EditState:
        return self.history.undo()

    def redo(self) -> EditState:
        return self.history.redo()

    def hit_test(self, x: float, y: float, *, tolerance: int = 4) -> int | None:
        """Index of the top-most shape whose bounds contain ``(x, y)``."""
        for index in range(len(self.state.items) - 1, -1, -1):
            bounds = shape_bounds(self.state.items[index], self.font_path)
            if bounds is not None and bounds.inflate(tolerance).contains(x, y):
                return index
        return None

    # ------------------------------------------------------------------ output
    def render(self, *, apply_crop: bool = True) -> Image.Image:
        return render(self.image, self.state, font_path=self.font_path, apply_crop=apply_crop)

    def render_overlay(self) -> Image.Image:
        return render_overlay(self.size, self.state, base=self.image, font_path=self.font_path)

    def to_dict(self) -> dict[str, Any]:
        return state_to_dict(self.state, self.size)

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def save(self, path: str | os.PathLike[str], *, format: str | None = None, quality: int = 92, background: str = "white") -> Path:
        """Render and save. JPEG/BMP are flattened onto ``background``."""
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        image = self.render()
        fmt = (format or Image.registered_extensions().get(out.suffix.lower(), "PNG")).upper()
        if fmt in _FLATTEN_FORMATS:
            flat = Image.new("RGB", image.size, background)
            flat.paste(image, mask=image.getchannel("A"))
            image = flat
        params: dict[str, Any] = {}
        if fmt in ("JPEG", "WEBP"):
            params["quality"] = quality
        image.save(out, format=fmt, **params)
        self._saved = self.state
        return out

    def save_annotations(self, path: str | os.PathLike[str]) -> Path:
        out = Path(path)
        out.write_text(self.to_json(), encoding="utf-8")
        return out

    def to_png_bytes(self) -> bytes:
        buffer = io.BytesIO()
        self.render().save(buffer, format="PNG")
        return buffer.getvalue()
