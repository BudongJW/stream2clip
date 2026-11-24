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

__all__ = [
    "SENSATIONAL", "STICKER_STYLES", "THUMBNAIL_SIZE", "font_file", "headline_lines", "key_word", "main_reaction", "make_sticker_thumbnail",
    "make_thumbnail", "pick_art", "pick_frame", "sensational_words", "sharpness", "sticker", "thumbnail_text",
]

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


# --------------------------------------------------------------------------- sticker thumbnails (Korean clip channels)

#: How Korean VTuber clip channels make thumbnails (reports/독케익 키리누키 채널 분석.md, section 8): the streamer's
#: illustration cut out with a white outline like a sticker, one or two lines of heavy text with the key word in
#: yellow, a chat line in a speech bubble and a symbol, over the scene. Only a few use the frame as it is.
STICKER_STYLES = ("frame", "sticker")
KEY_FILL = "#FFE14D"
PLAIN_FILL = "#FFFFFF"
#: Expression names in an illustration folder's file names, per chat reaction (``react_*`` stats).
ART_FOR_REACTION = {
    "laugh": ("laugh", "smile"), "shock": ("surprised", "shock"), "cute": ("cute", "wink"), "hype": ("hype", "cheer", "wink"), "sad": ("sad", "cry"),
}
#: A symbol beside the character for a reaction (shock reads as "!?" on these channels).
SYMBOL_FOR_REACTION = {"shock": "!?"}
#: The heaviest font of the caption font catalog per script, when it has been fetched (stream2clip fonts).
HEADLINE_FONTS = {"ko": ("BlackHanSans-Regular.ttf", "DoHyeon-Regular.ttf"), "ja": ("DelaGothicOne-Regular.ttf",), "": ("Anton-Regular.ttf",)}


def main_reaction(stats: "dict[str, float] | None") -> str:
    """The chat reaction with the most messages in a highlight (``react_<name>`` stats), or ``""``."""
    counts = {key[6:]: value for key, value in (stats or {}).items() if key.startswith("react_") and value > 0}
    return max(counts, key=counts.get) if counts else ""


def pick_art(art: "str | os.PathLike[str] | None", reaction: str = "") -> Path | None:
    """The illustration for a thumbnail: ``art`` itself when it is a picture, else the folder's picture named for
    ``reaction`` (laugh, surprised, wink ...), else the folder's first picture."""
    if not art:
        return None
    path = Path(art)
    if path.is_file():
        return path
    pictures = sorted(p for p in path.glob("*") if p.suffix.lower() in (".png", ".webp")) if path.is_dir() else []

    def biggest(found: list[Path]) -> Path:  # one expression may come in several sizes: the largest draws sharpest
        def area(picture: Path) -> int:
            try:
                with Image.open(picture) as image:
                    return image.width * image.height
            except Exception:  # not a picture after all: last
                return 0

        return max(found, key=area)

    for word in ART_FOR_REACTION.get(reaction, ()):
        found = [picture for picture in pictures if word.lower() in picture.stem.lower()]
        if found:
            return biggest(found)
    return biggest(pictures) if pictures else None


def headline_lines(hook: str, *, per_line: float = 7.0, lines: int = 2) -> list[str]:
    """The hook's first words on one or two short lines (about seven full-width characters each)."""
    words = " ".join(hook.replace("...", " ").split()).split(" ")
    out: list[str] = []
    for word in words:
        if not word:
            continue
        if out and _width(out[-1] + " " + word) <= per_line:
            out[-1] += " " + word
        elif len(out) < lines:
            out.append(word if _width(word) <= per_line * 1.5 else thumbnail_text(word, width=per_line * 1.5))
        else:
            break
    return out


def key_word(lines: Sequence[str], quotes: Sequence[str] = ()) -> str:
    """The word to colour: one the chat also typed, else the last word."""
    words = [w for line in lines for w in line.split(" ") if w]
    for quote in quotes:
        for word in words:
            if len(word) >= 2 and (word in quote or quote in word):
                return word
    return words[-1] if words else ""


def headline_font(script: str) -> str | None:
    """The heaviest catalog font fetched for ``script``, else a bold system font."""
    try:
        from .fonts import fonts_dir

        folder = fonts_dir()
        for name in HEADLINE_FONTS.get(script if script in HEADLINE_FONTS else "", ()):
            if (folder / name).is_file():
                return str(folder / name)
    except Exception:  # the catalog is a nicety: a system font does the job
        pass
    return font_file(script)


def sticker(art: Image.Image, outline: int) -> Image.Image:
    """``art`` as a die-cut sticker: a white outline of ``outline`` px around its shape and a soft shadow below."""
    art = art.convert("RGBA")
    pad = outline * 3
    alpha = Image.new("L", (art.width + 2 * pad, art.height + 2 * pad), 0)
    alpha.paste(art.getchannel("A"), (pad, pad))
    grown = alpha.point(lambda v: 255 if v > 40 else 0)
    for _ in range(max(1, outline // 2)):  # 2 px a pass: a rounded outline that follows the shape
        grown = grown.filter(ImageFilter.MaxFilter(5))
    grown = grown.filter(ImageFilter.GaussianBlur(1.2))
    out = Image.new("RGBA", alpha.size, (0, 0, 0, 0))
    shadow = Image.new("RGBA", alpha.size, (0, 0, 0, 0))
    shadow.putalpha(grown.filter(ImageFilter.GaussianBlur(outline * 0.8)).point(lambda v: int(v * 0.45)))
    out.alpha_composite(shadow, (outline // 2, outline))
    white = Image.new("RGBA", alpha.size, (255, 255, 255, 0))
    white.putalpha(grown)
    out.alpha_composite(white)
    out.alpha_composite(art, (pad, pad))
    return out.crop(out.getbbox())


def _avatar_card(frame: Image.Image, face: "Region") -> Image.Image:
    """The avatar's box from the frame, with a little room around it, as a rounded card (no illustration given)."""
    margin = 0.15
    left = max(0, int(face.x - face.width * margin))
    top = max(0, int(face.y - face.height * margin))
    right = min(frame.width, int(face.x + face.width * (1 + margin)))
    bottom = min(frame.height, int(face.y + face.height * (1 + margin)))
    card = frame.crop((left, top, right, bottom)).convert("RGBA")
    mask = Image.new("L", card.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, card.width - 1, card.height - 1), radius=max(8, min(card.size) // 10), fill=255)
    card.putalpha(mask)
    return card


def _bubble(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], tail: tuple[int, int], *, edge: int) -> None:
    left, top, right, bottom = box
    tx, ty = tail
    base = max(left + 30, min(tx + 40, right - 60))
    draw.polygon([(base, bottom - 4), (base + 36, bottom - 4), (tx, ty)], fill=PLAIN_FILL, outline=TEXT_EDGE)
    draw.rounded_rectangle(box, radius=(bottom - top) // 2, fill=PLAIN_FILL, outline=TEXT_EDGE, width=edge)
    draw.polygon([(base + edge, bottom - edge - 1), (base + 36 - edge, bottom - edge - 1), (tx + 2, ty - edge * 2)], fill=PLAIN_FILL)


def make_sticker_thumbnail(
    frame: np.ndarray,
    hook: str,
    out: str | os.PathLike[str],
    *,
    art: "str | os.PathLike[str] | None" = None,
    face: "Region | None" = None,
    quote: str = "",
    reaction: str = "",
    size: tuple[int, int] = THUMBNAIL_SIZE,
    font: str | None = None,
) -> Path:
    """Write a JPEG thumbnail as Korean clip channels make them.

    The scene at the back (softened), the illustration ``art`` as a sticker on the left (without one, the
    avatar's box ``face`` from the frame as a card), the hook's first words on one or two lines at the top
    right with the key word in yellow, the chat line ``quote`` in a speech bubble under them, and "!?" for a
    shock. The bottom-right corner stays free for the duration badge.
    """
    background = Image.fromarray(np.ascontiguousarray(frame[..., :3]))
    w, h = size
    picture = _cover(background, size).filter(ImageFilter.GaussianBlur(2.5))
    picture = ImageEnhance.Brightness(ImageEnhance.Color(picture).enhance(1.1)).enhance(0.82)
    shade = Image.linear_gradient("L").rotate(90, expand=True).resize((w, h))  # darker towards the right: the words are there
    picture = Image.composite(Image.new("RGB", size, (10, 8, 18)), picture, shade.point(lambda v: int(v * 0.55)))
    canvas = picture.convert("RGBA")

    character = None
    art_path = Path(art) if art else None
    if art_path is not None and art_path.is_file():
        character = sticker(Image.open(art_path), outline=max(8, h // 50))
    elif face is not None:
        character = sticker(_avatar_card(background, face), outline=max(8, h // 50))
    right_of_character = int(w * 0.05)
    if character is not None:
        scale = min(h * 0.96 / character.height, w * 0.5 / character.width)
        character = character.resize((max(1, round(character.width * scale)), max(1, round(character.height * scale))), Image.Resampling.LANCZOS)
        x, y = int(w * 0.02), h - character.height + int(h * 0.02)
        canvas.alpha_composite(character, (x, max(y, 0)))
        right_of_character = x + character.width

    draw = ImageDraw.Draw(canvas)
    lines = headline_lines(hook)
    keyword = key_word(lines, [quote] if quote else [])
    path = font or (headline_font(script_of(hook)) if lines else None)
    left_edge = max(int(w * 0.46), right_of_character - int(w * 0.06))
    room = w - left_edge - int(w * 0.04)
    text_bottom = int(h * 0.06)
    if lines and path:
        size_px = int(h * 0.2)
        while size_px > 28:
            typeface = ImageFont.truetype(path, size_px)
            stroke = max(5, size_px // 7)
            widths = [draw.textbbox((0, 0), line, font=typeface, stroke_width=stroke)[2] for line in lines]
            if max(widths) <= room:
                break
            size_px = int(size_px * 0.92)
        typeface = ImageFont.truetype(path, size_px)
        stroke = max(5, size_px // 7)
        y = int(h * 0.06)
        for line in lines:
            box = draw.textbbox((0, 0), line, font=typeface, stroke_width=stroke)
            x = w - int(w * 0.04) - (box[2] - box[0])
            for word in line.split(" "):
                fill = KEY_FILL if word == keyword else PLAIN_FILL
                part = draw.textbbox((0, 0), word + " ", font=typeface, stroke_width=stroke)
                draw.text((x + size_px // 18, y + size_px // 14 - box[1]), word, font=typeface, fill=(0, 0, 0, 150), stroke_width=stroke, stroke_fill=(0, 0, 0, 150))
                draw.text((x, y - box[1]), word, font=typeface, fill=fill, stroke_width=stroke, stroke_fill=TEXT_EDGE)
                x += part[2] - part[0] - stroke
            y += int((box[3] - box[1]) * 1.02)
        text_bottom = y

    quote = " ".join(quote.split())
    quote_font = font or (font_file(script_of(quote)) if quote else None)
    if quote and quote_font:
        size_px = int(h * 0.07)
        typeface = ImageFont.truetype(quote_font, size_px)
        while size_px > 18 and draw.textbbox((0, 0), quote, font=typeface)[2] > w * 0.36:
            size_px = int(size_px * 0.9)
            typeface = ImageFont.truetype(quote_font, size_px)
        box = draw.textbbox((0, 0), quote, font=typeface)
        pad_x, pad_y = int(size_px * 0.9), int(size_px * 0.45)
        bw, bh = box[2] - box[0] + 2 * pad_x, box[3] - box[1] + 2 * pad_y
        right = w - int(w * 0.06)
        top = min(text_bottom + int(h * 0.05), int(h * 0.78) - bh)  # never down into the duration badge's corner
        bubble = (right - bw, top, right, top + bh)
        _bubble(draw, bubble, (max(left_edge - int(w * 0.02), bubble[0] - int(w * 0.05)), bubble[3] + int(h * 0.06)), edge=max(3, size_px // 14))
        draw.text((bubble[0] + pad_x - box[0], top + pad_y - box[1]), quote, font=typeface, fill=TEXT_EDGE)

    symbol = SYMBOL_FOR_REACTION.get(reaction, "")
    symbol_font = font or font_file("")
    if symbol and symbol_font and character is not None:  # at the character's top-left: the words own the top right
        typeface = ImageFont.truetype(symbol_font, int(h * 0.17))
        draw.text((int(w * 0.015), int(h * 0.02)), symbol, font=typeface, fill="#FF3B5C", stroke_width=max(5, h // 90), stroke_fill=PLAIN_FILL)

    target = Path(out)
    target.parent.mkdir(parents=True, exist_ok=True)
    result = canvas.convert("RGB")
    quality = 92
    while True:
        result.save(target, "JPEG", quality=quality, optimize=True)
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
