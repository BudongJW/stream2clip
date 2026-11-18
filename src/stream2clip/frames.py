"""Frame conventions.

Every layer exchanges frames as ``numpy.ndarray`` of shape ``(height, width, 4)``
and dtype ``uint8`` in **RGBA** order. This is the lowest common denominator of
MoviePy, OpenCV (after ``cvtColor``), Pillow, PyAV and raw ffmpeg pipes, which is
what makes the toolkit easy to embed in other video projects.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

__all__ = ["ensure_rgba", "to_image", "from_image"]


def ensure_rgba(frame: np.ndarray) -> np.ndarray:
    """Return a contiguous ``(h, w, 4) uint8`` RGBA view/copy of ``frame``.

    Accepts grayscale ``(h, w)``, RGB ``(h, w, 3)`` or RGBA ``(h, w, 4)`` input.
    """
    arr = np.asarray(frame)
    if arr.dtype != np.uint8:
        if np.issubdtype(arr.dtype, np.floating) and arr.size and arr.max() <= 1.0:
            arr = arr * 255.0
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    if arr.ndim == 2:
        arr = np.stack([arr, arr, arr], axis=-1)
    if arr.ndim != 3 or arr.shape[2] not in (3, 4):
        raise ValueError(f"Expected (h, w), (h, w, 3) or (h, w, 4) frame, got shape {arr.shape}")
    if arr.shape[2] == 3:
        alpha = np.full(arr.shape[:2] + (1,), 255, dtype=np.uint8)
        arr = np.concatenate([arr, alpha], axis=-1)
    return np.ascontiguousarray(arr)


def to_image(frame: np.ndarray) -> Image.Image:
    return Image.fromarray(ensure_rgba(frame), "RGBA")


def from_image(image: Image.Image) -> np.ndarray:
    return np.asarray(image.convert("RGBA")).copy()
