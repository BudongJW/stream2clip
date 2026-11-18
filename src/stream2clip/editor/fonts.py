"""Font discovery with CJK (Korean/Japanese) coverage first."""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

__all__ = ["find_font_path", "load_font"]


def _candidates() -> list[Path]:
    paths: list[Path] = []
    if sys.platform == "win32":
        fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        paths += [fonts / name for name in ("malgun.ttf", "YuGothM.ttc", "meiryo.ttc", "msgothic.ttc", "arial.ttf")]
    elif sys.platform == "darwin":
        paths += [
            Path("/System/Library/Fonts/AppleSDGothicNeo.ttc"),
            Path("/System/Library/Fonts/ヒラギノ角ゴシック W4.ttc"),
            Path("/Library/Fonts/NanumGothic.ttf"),
            Path("/System/Library/Fonts/Helvetica.ttc"),
        ]
    paths += [
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf"),
        Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    return paths


@lru_cache(maxsize=1)
def find_font_path() -> str | None:
    """``STREAM2CLIP_FONT`` env var, then well-known CJK-capable system fonts."""
    env = os.environ.get("STREAM2CLIP_FONT")
    if env and Path(env).is_file():
        return env
    for path in _candidates():
        if path.is_file():
            return str(path)
    return None


@lru_cache(maxsize=64)
def load_font(size: float, path: str | None = None) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    size = max(1, round(size))
    path = path or find_font_path()
    if path:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)
