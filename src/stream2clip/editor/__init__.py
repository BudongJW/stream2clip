"""Screenshot / frame annotation: pen, highlighter, rectangle, arrow, text,
mosaic, transparency (region or color key) and crop, with undo/redo."""

from .document import Document
from .fonts import find_font_path, load_font
from .history import History
from .model import (
    SCHEMA,
    SHAPE_TYPES,
    Arrow,
    ColorKey,
    EditState,
    Highlighter,
    Mosaic,
    Pen,
    Rectangle,
    Shape,
    Text,
    Transparent,
    shape_from_dict,
    shape_to_dict,
    state_from_dict,
    state_to_dict,
    translate_shape,
)
from .render import apply_shape, render, render_overlay, shape_bounds, text_size

__all__ = [
    "SCHEMA",
    "SHAPE_TYPES",
    "Arrow",
    "ColorKey",
    "Document",
    "EditState",
    "Highlighter",
    "History",
    "Mosaic",
    "Pen",
    "Rectangle",
    "Shape",
    "Text",
    "Transparent",
    "apply_shape",
    "find_font_path",
    "load_font",
    "render",
    "render_overlay",
    "shape_bounds",
    "shape_from_dict",
    "shape_to_dict",
    "state_from_dict",
    "state_to_dict",
    "text_size",
    "translate_shape",
]
