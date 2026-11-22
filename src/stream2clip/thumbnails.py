"""Thumbnails in the way clip channels make them: a big face, a few big words, nothing in the bottom-right.

From Japanese thumbnail guides (reports/키리누키 영상 레퍼런스 검토.md): a large face with a clear
emotion, 5-10 characters of text in the thickest font at hand with a heavy outline, two to four
colours, a calmer background, and the bottom-right corner left free for the duration badge.

The frame is the sharpest of a few taken around the highlight's peak; when the avatar's box is known
the picture is zoomed so that it fills about half the height. Pillow and numpy only.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from .subtitles import _phrases, _width, script_of

if TYPE_CHECKING:  # pragma: no cover
    from .geometry import Region

__all__ = ["SENSATIONAL", "THUMBNAIL_SIZE", "font_file", "make_thumbnail", "pick_frame", "sensational_words", "sharpness", "thumbnail_text"]

THUMBNAIL_SIZE = (1280, 720)  # what YouTube asks for (16:9, at least 640 wide, under 2 MB)
TEXT_FILL = "#FFE14D"
TEXT_EDGE = "#15131F"
#: Bold families per script, in the order tried, with the file names they come in.
BOLD_FONTS: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "ja": (("Noto Sans JP", ("NotoSansJP-Black.ttf", "NotoSansJP-Bold.ttf", "NotoSansJP-VF.ttf")), ("Yu Gothic", ("YuGothB.ttc",)), ("Meiryo", ("meiryob.ttc",)),
           ("Hiragino Sans", ("ヒラギノ角ゴシック W8.ttc", "Hiragino Sans GB.ttc"))),
    "ko": (("Noto Sans KR", ("NotoSansKR-Black.ttf", "NotoSansKR-Bold.ttf", "NotoSansKR-VF.ttf")), ("Malgun Gothic", ("malgunbd.ttf",)),
           ("Apple SD Gothic Neo", ("AppleSDGothicNeo.ttc",))),
    "": (("Arial", ("arialbd.ttf", "Arial Bold.ttf")), ("Segoe UI", ("segoeuib.ttf",)), ("DejaVu Sans", ("DejaVuSans-Bold.ttf",))),
}


def _font_dirs() -> list[Path]:
    if sys.platform == "win32":
        return [Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts", Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Fonts"]
    if sys.platform == "darwin":
        return [Path("/System/Library/Fonts"), Path("/Library/Fonts"), Path.home() / "Library" / "Fonts"]
    return [Path("/usr/share/fonts"), Path("/usr/local/share/fonts"), Path.home() / ".local" / "share" / "fonts", Path.home() / ".fonts"]


def font_file(script: str = "") -> str | None:
    """A bold font file that draws ``script`` (``ja`` / ``ko`` / ``""``), or ``None`` when none is found."""
    candidates = BOLD_FONTS.get(script, BOLD_FONTS[""]) + (BOLD_FONTS[""] if script == "zh" else ())
    for _family, files in candidates:
        for folder in _font_dirs():
            for name in files:
                path = folder / name
                if path.is_file():
                    return str(path)
    if sys.platform != "win32":  # fontconfig knows where everything is
        for family, _files in candidates:
            try:
                found = subprocess.run(["fc-match", "-f", "%{file}", f"{family}:bold"], capture_output=True, text=True, timeout=10, check=False).stdout.strip()
            except (OSError, subprocess.SubprocessError):
                break
            if found and Path(found).is_file() and family.split()[0].lower() in Path(found).name.lower():
                return found
    return None


def thumbnail_text(hook: str, *, width: float = 10.0) -> str:
    """The first words of the hook that fit ``width`` full-width characters (5-10 reads at phone size)."""
    hook = " ".join(hook.replace("...", " ").split())
    first = hook.split(" ")[0] if hook else ""
    if _width(first) <= width:
        return first
    out = ""
    for piece in _phrases(first) if any(0x3040 <= ord(ch) <= 0x30FF for ch in first) else list(first):
        if _width(out + piece) > width:
            break
        out += piece
    return out or first[: int(width)]


def sharpness(frame: np.ndarray) -> float:
    """How much fine detail a frame has (variance of a Laplacian of its grey levels): blurred motion scores low."""
    grey = np.asarray(frame[..., :3], dtype=np.float32).mean(axis=2)
    lap = -4 * grey[1:-1, 1:-1] + grey[:-2, 1:-1] + grey[2:, 1:-1] + grey[1:-1, :-2] + grey[1:-1, 2:]
    level = float(grey.mean())
    exposure = 1.0 if 40 <= level <= 215 else 0.3  # a black or white flash is not a thumbnail
    return float(lap.var()) * exposure


def pick_frame(frames: Sequence[np.ndarray]) -> np.ndarray:
    if not frames:
        raise ValueError("No frame to make a thumbnail from")
    return max(frames, key=sharpness)


#: How much of the thumbnail's height the avatar's box (head and shoulders, as the layouts use it) fills.
FOCUS_FILL = 0.8


def _cover(image: Image.Image, size: tuple[int, int], focus: "tuple[float, float, float] | None" = None) -> Image.Image:
    """Fill ``size``; with ``focus`` (centre x, centre y, height as fractions) zoom until that box fills ``FOCUS_FILL`` of the height."""
    w, h = image.size
    tw, th = size
    scale = max(tw / w, th / h)
    if focus is not None:
        scale = max(scale, min(3.0, FOCUS_FILL * th / max(focus[2] * h, 1)))
    image = image.resize((max(tw, round(w * scale)), max(th, round(h * scale))), Image.Resampling.LANCZOS)
    cx, cy = (focus[0] * image.width, focus[1] * image.height) if focus is not None else (image.width / 2, image.height / 2)
    left = int(min(max(cx - tw / 2, 0), image.width - tw))
    top = int(min(max(cy - th * 0.45, 0), image.height - th))
    return image.crop((left, top, left + tw, top + th))


def make_thumbnail(
    frame: np.ndarray,
    text: str,
    out: str | os.PathLike[str],
    *,
    face: "Region | None" = None,
    size: tuple[int, int] = THUMBNAIL_SIZE,
    font: str | None = None,
) -> Path:
    """Write a JPEG thumbnail: the frame (zoomed onto ``face`` when given), ``text`` big with a heavy outline.

    The text goes on the side away from the face, at the top; the bottom-right stays free for the
    duration badge. Without a font that draws the text the picture is written without it.
    """
    image = Image.fromarray(np.ascontiguousarray(frame[..., :3]))
    focus = None
    if face is not None:
        focus = ((face.x + face.width / 2) / image.width, (face.y + face.height / 2) / image.height, face.height / image.height)
    picture = _cover(image, size, focus)
    picture = ImageEnhance.Contrast(ImageEnhance.Color(picture).enhance(1.15)).enhance(1.08)
    w, h = picture.size
    text = " ".join(text.split())
    path = font or (font_file(script_of(text)) if text else None)
    if text and path:
        face_on_left = focus is not None and focus[0] < 0.5
        draw = ImageDraw.Draw(picture)
        size_px = int(h * 0.24)
        typeface = ImageFont.truetype(path, size_px)
        while size_px > 24:
            typeface = ImageFont.truetype(path, size_px)
            box = draw.textbbox((0, 0), text, font=typeface, stroke_width=max(4, size_px // 9))
            if box[2] - box[0] <= w * 0.62:
                break
            size_px = int(size_px * 0.9)
        stroke = max(4, size_px // 9)
        box = draw.textbbox((0, 0), text, font=typeface, stroke_width=stroke)
        tw, th = box[2] - box[0], box[3] - box[1]
        x = int(w - tw - w * 0.04) if face_on_left else int(w * 0.04)
        y = int(h * 0.06)
        # a soft dark band behind the words keeps them readable on any picture
        band = Image.new("L", (w, h), 0)
        ImageDraw.Draw(band).rectangle((x - 30, y - 20, x + tw + 30, y + th + 40), fill=150)
        picture = Image.composite(Image.new("RGB", (w, h), (0, 0, 0)), picture, band.filter(ImageFilter.GaussianBlur(28)))
        draw = ImageDraw.Draw(picture)
        draw.text((x - box[0], y - box[1]), text, font=typeface, fill=TEXT_FILL, stroke_width=stroke, stroke_fill=TEXT_EDGE)
    target = Path(out)
    target.parent.mkdir(parents=True, exist_ok=True)
    quality = 92
    while True:
        picture.save(target, "JPEG", quality=quality, optimize=True)
        if target.stat().st_size < 2_000_000 or quality <= 60:
            return target
        quality -= 8


#: Words that make a title or thumbnail look like news of trouble; the agencies forbid exaggerated or
#: misleading titles and thumbnails (にじさんじ Article 5, ぶいすぽっ!). A checklist, not a judgement.
SENSATIONAL = re.compile(r"炎上|放送事故|閲覧注意|衝撃|暴露|引退|喧嘩|不仲|논란|방송사고|충격|폭로|은퇴|불화|\b(?:shocking|exposed|leaked|drama|scandal)\b", re.IGNORECASE)


def sensational_words(*texts: str) -> list[str]:
    """The exaggerating words found in ``texts``, each once."""
    found: list[str] = []
    for text in texts:
        for match in SENSATIONAL.finditer(text or ""):
            word = match.group(0)
            if word.lower() not in [f.lower() for f in found]:
                found.append(word)
    return found
