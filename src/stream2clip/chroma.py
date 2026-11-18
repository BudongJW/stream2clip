"""Chroma keying ("transparent background") shared by stills, previews and video.

:func:`colorkey_alpha` reproduces the math of ffmpeg's ``colorkey`` filter so the
in-process preview (editor, GUI) matches what :mod:`stream2clip.ffmpeg` produces
when the same parameters are passed to an export.
"""

from __future__ import annotations

import numpy as np

from .color import parse_color
from .frames import ensure_rgba

__all__ = ["colorkey_alpha", "apply_colorkey", "colorkey_filter", "DEFAULT_KEY_COLOR"]

DEFAULT_KEY_COLOR = "#00FF00"
_MAX_DISTANCE = 255.0 * 255.0 * 3.0


def _validate(similarity: float, blend: float) -> None:
    if not 0.0 < similarity <= 1.0:
        raise ValueError(f"similarity must be in (0, 1], got {similarity}")
    if not 0.0 <= blend <= 1.0:
        raise ValueError(f"blend must be in [0, 1], got {blend}")


def colorkey_alpha(frame: np.ndarray, color: str = DEFAULT_KEY_COLOR, similarity: float = 0.1, blend: float = 0.0) -> np.ndarray:
    """Return the ``(h, w) uint8`` alpha mask ffmpeg ``colorkey`` would compute.

    ``similarity`` is the normalized RGB distance (0..1) under which a pixel is
    keyed out; ``blend`` > 0 produces a soft edge of that width.
    """
    _validate(similarity, blend)
    rgba = ensure_rgba(frame)
    key = np.array(parse_color(color)[:3], dtype=np.float32)
    diff = rgba[..., :3].astype(np.float32) - key
    distance = np.sqrt(np.sum(diff * diff, axis=-1) / _MAX_DISTANCE)
    if blend > 0.0001:
        alpha = np.clip((distance - similarity) / blend, 0.0, 1.0) * 255.0
        return alpha.astype(np.uint8)
    return np.where(distance > similarity, 255, 0).astype(np.uint8)


def apply_colorkey(frame: np.ndarray, color: str = DEFAULT_KEY_COLOR, similarity: float = 0.1, blend: float = 0.0) -> np.ndarray:
    """Return a copy of ``frame`` (RGBA) with pixels close to ``color`` made transparent.

    Existing transparency is preserved (the result is the minimum of both alphas).
    """
    rgba = ensure_rgba(frame).copy()
    mask = colorkey_alpha(rgba, color, similarity, blend)
    rgba[..., 3] = np.minimum(rgba[..., 3], mask)
    return rgba


def colorkey_filter(color: str = DEFAULT_KEY_COLOR, similarity: float = 0.1, blend: float = 0.0) -> str:
    """Return the equivalent ffmpeg filter string, e.g. ``colorkey=0x00FF00:0.1:0``."""
    _validate(similarity, blend)
    r, g, b, _ = parse_color(color)
    return f"colorkey=0x{r:02X}{g:02X}{b:02X}:{similarity:g}:{blend:g}"
