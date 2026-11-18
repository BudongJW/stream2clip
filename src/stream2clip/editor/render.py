"""Render annotation documents with Pillow (anti-aliased by local supersampling)."""

from __future__ import annotations

import math

from PIL import Image, ImageDraw

from ..chroma import apply_colorkey
from ..color import parse_color
from ..frames import from_image, to_image
from ..geometry import Region
from .fonts import load_font
from .model import Arrow, ColorKey, EditState, Highlighter, Mosaic, Pen, Rectangle, Shape, Text, Transparent

__all__ = ["render", "render_overlay", "apply_shape", "shape_bounds", "text_size"]

SUPERSAMPLE = 3
_DRAWABLE = (Pen, Highlighter, Rectangle, Arrow, Text)


def text_size(shape: Text, font_path: str | None = None) -> tuple[int, int, int]:
    """Return ``(width, height, padding)`` of a text label including its background padding."""
    font = load_font(shape.size, font_path)
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    left, top, right, bottom = probe.multiline_textbbox((0, 0), shape.text or " ", font=font, spacing=round(shape.size * 0.2))
    pad = round(shape.size * 0.25) if shape.background else 0
    return (right + 2 * pad, bottom + 2 * pad, pad)


def _arrow_head(shape: Arrow) -> tuple[float, float]:
    length = max(shape.width * 3.5, 14.0)
    return length, length * 0.85


def shape_bounds(shape: Shape, font_path: str | None = None) -> Region | None:
    """Pixel bounds of a shape (``None`` for global operations such as color keys)."""
    if isinstance(shape, (Pen, Highlighter)):
        if not shape.points:
            return None
        xs, ys = zip(*shape.points)
        pad = math.ceil(shape.width / 2) + 2
        return Region.from_points(min(xs), min(ys), max(xs), max(ys)).inflate(pad)
    if isinstance(shape, (Rectangle, Mosaic, Transparent)):
        return shape.rect
    if isinstance(shape, Arrow):
        _, head_width = _arrow_head(shape)
        pad = math.ceil(max(shape.width, head_width) / 2) + 2
        return Region.from_points(shape.start[0], shape.start[1], shape.end[0], shape.end[1]).inflate(pad)
    if isinstance(shape, Text):
        w, h, _ = text_size(shape, font_path)
        x, y = round(shape.position[0]), round(shape.position[1])
        return Region(x, y, w, h)
    return None


def _scaled(points: "list[tuple[float, float]] | tuple[tuple[float, float], ...]", origin: Region, ss: int) -> list[tuple[float, float]]:
    return [((x - origin.x) * ss, (y - origin.y) * ss) for x, y in points]


def _stroke(draw: ImageDraw.ImageDraw, pts: list[tuple[float, float]], fill: tuple[int, int, int, int], width: float) -> None:
    radius = width / 2
    if len(pts) == 1 or all(p == pts[0] for p in pts):
        x, y = pts[0]
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill)
        return
    draw.line(pts, fill=fill, width=max(1, round(width)), joint="curve")
    if width > 3:
        for x, y in pts:
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill)


def _draw_layer(shape: Shape, canvas: tuple[int, int], font_path: str | None) -> tuple[Image.Image, tuple[int, int]] | None:
    bounds = shape_bounds(shape, font_path)
    if bounds is None:
        return None
    if isinstance(shape, Rectangle):
        bounds = bounds.inflate(1)
    clipped = bounds.clamp(*canvas)
    if clipped is None:
        return None

    if isinstance(shape, Text):
        layer = Image.new("RGBA", (bounds.width, bounds.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        _, _, pad = text_size(shape, font_path)
        if shape.background:
            draw.rounded_rectangle((0, 0, bounds.width - 1, bounds.height - 1), radius=pad, fill=parse_color(shape.background))
        font = load_font(shape.size, font_path)
        draw.multiline_text((pad, pad), shape.text, font=font, fill=parse_color(shape.color), spacing=round(shape.size * 0.2))
        offset = (clipped.x - bounds.x, clipped.y - bounds.y)
        layer = layer.crop((offset[0], offset[1], offset[0] + clipped.width, offset[1] + clipped.height))
        return layer, (clipped.x, clipped.y)

    ss = SUPERSAMPLE
    layer = Image.new("RGBA", (clipped.width * ss, clipped.height * ss), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    if isinstance(shape, (Pen, Highlighter)):
        color = parse_color(shape.color)
        opaque = (color[0], color[1], color[2], 255) if isinstance(shape, Highlighter) else color
        _stroke(draw, _scaled(shape.points, clipped, ss), opaque, shape.width * ss)
    elif isinstance(shape, Rectangle):
        r = shape.rect
        box = ((r.x - clipped.x) * ss, (r.y - clipped.y) * ss, (r.right - clipped.x) * ss - 1, (r.bottom - clipped.y) * ss - 1)
        if box[2] > box[0] and box[3] > box[1]:
            draw.rectangle(
                box,
                outline=parse_color(shape.color) if shape.width > 0 else None,
                width=max(1, round(shape.width * ss)),
                fill=parse_color(shape.fill) if shape.fill else None,
            )
    elif isinstance(shape, Arrow):
        (x0, y0), (x1, y1) = _scaled([shape.start, shape.end], clipped, ss)
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy)
        if length >= 1:
            ux, uy = dx / length, dy / length
            head_len, head_width = (v * ss for v in _arrow_head(shape))
            head_len = min(head_len, length)
            base_x, base_y = x1 - ux * head_len, y1 - uy * head_len
            shaft_end = (x1 - ux * head_len * 0.7, y1 - uy * head_len * 0.7)
            color = parse_color(shape.color)
            _stroke(draw, [(x0, y0), shaft_end], color, shape.width * ss)
            px, py = -uy * head_width / 2, ux * head_width / 2
            draw.polygon([(x1, y1), (base_x + px, base_y + py), (base_x - px, base_y - py)], fill=color)

    layer = layer.resize((clipped.width, clipped.height), Image.Resampling.BOX)
    if isinstance(shape, Highlighter):
        opacity = max(0.0, min(1.0, shape.opacity)) * parse_color(shape.color)[3] / 255
        layer.putalpha(layer.getchannel("A").point(lambda v: round(v * opacity)))
    return layer, (clipped.x, clipped.y)


def _mosaic(img: Image.Image, rect: Region, block: int) -> None:
    clipped = rect.clamp(*img.size)
    if clipped is None:
        return
    block = max(2, int(block))
    patch = img.crop(clipped.as_box())
    small = patch.resize((max(1, clipped.width // block), max(1, clipped.height // block)), Image.Resampling.BOX)
    img.paste(small.resize(patch.size, Image.Resampling.NEAREST), (clipped.x, clipped.y))


def apply_shape(img: Image.Image, shape: Shape, *, font_path: str | None = None) -> Image.Image:
    """Apply one shape to an RGBA image (in place when possible) and return it."""
    if isinstance(shape, Mosaic):
        _mosaic(img, shape.rect, shape.block)
    elif isinstance(shape, Transparent):
        clipped = shape.rect.clamp(*img.size)
        if clipped is not None:
            img.paste((0, 0, 0, 0), clipped.as_box())
    elif isinstance(shape, ColorKey):
        img = to_image(apply_colorkey(from_image(img), shape.color, shape.similarity, shape.blend))
    elif isinstance(shape, _DRAWABLE):
        drawn = _draw_layer(shape, img.size, font_path)
        if drawn is not None:
            layer, offset = drawn
            img.alpha_composite(layer, dest=offset)
    else:  # pragma: no cover - guarded by the type union
        raise TypeError(f"Unknown shape {shape!r}")
    return img


def render(base: Image.Image, state: EditState, *, font_path: str | None = None, apply_crop: bool = True) -> Image.Image:
    """Return a new RGBA image with every shape applied in order, then the crop."""
    img = base.convert("RGBA")
    if img is base:
        img = img.copy()
    for shape in state.items:
        img = apply_shape(img, shape, font_path=font_path)
    if apply_crop and state.crop is not None:
        clipped = state.crop.clamp(*img.size)
        if clipped is not None:
            img = img.crop(clipped.as_box())
    return img


def render_overlay(size: tuple[int, int], state: EditState, *, base: Image.Image | None = None, font_path: str | None = None) -> Image.Image:
    """Render only the annotations on a transparent canvas.

    The result can be composited over the original media by any video editor or
    OBS image source. Mosaic patches are included when ``base`` is given;
    transparency/color-key operations cannot be expressed as an overlay and are
    skipped.
    """
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    source = base.convert("RGBA") if base is not None else None
    for shape in state.items:
        if isinstance(shape, Mosaic) and source is not None:
            clipped = shape.rect.clamp(*size)
            if clipped is None:
                continue
            patch = render(source, EditState(items=(shape,)), apply_crop=False).crop(clipped.as_box())
            overlay.paste(patch, (clipped.x, clipped.y))
        elif isinstance(shape, _DRAWABLE):
            apply_shape(overlay, shape, font_path=font_path)
    if state.crop is not None:
        clipped = state.crop.clamp(*size)
        if clipped is not None:
            overlay = overlay.crop(clipped.as_box())
    return overlay
