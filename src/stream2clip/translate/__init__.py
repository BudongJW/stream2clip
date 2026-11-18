"""Image text translation ("번역 (한국어)") as pluggable OCR + translator pairs.

stream2clip ships no network translation service. A host app or plugin
provides a :class:`TextDetector` (OCR) and a :class:`Translator`; the editor
then overlays translated labels as ordinary annotation shapes, so the result
stays editable and serializable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol, Sequence, runtime_checkable

from PIL import Image

from ..geometry import Region
from ..plugins import text_detectors, translators
from ..editor.model import Rectangle, Shape, Text

__all__ = [
    "TextBlock",
    "TextDetector",
    "Translator",
    "CallableTranslator",
    "translate_image",
    "available_pipeline",
]


@dataclass(frozen=True)
class TextBlock:
    region: Region
    text: str


@runtime_checkable
class TextDetector(Protocol):
    def detect(self, image: Image.Image) -> list[TextBlock]: ...


@runtime_checkable
class Translator(Protocol):
    def translate(self, texts: Sequence[str], target: str, source: str | None = None) -> list[str]: ...


class CallableTranslator:
    """Adapt ``fn(texts, target, source) -> list[str]`` (e.g. an LLM call) to :class:`Translator`."""

    def __init__(self, fn: Callable[[Sequence[str], str, "str | None"], list[str]]) -> None:
        self._fn = fn

    def translate(self, texts: Sequence[str], target: str, source: str | None = None) -> list[str]:
        result = list(self._fn(texts, target, source))
        if len(result) != len(texts):
            raise ValueError("Translator returned a different number of strings")
        return result


def translate_image(
    image: Image.Image,
    detector: TextDetector,
    translator: Translator,
    *,
    target: str = "ko",
    source: str | None = None,
    color: str = "#111111",
    background: str = "#FFFFFFE6",
) -> list[Shape]:
    """Detect text, translate it and return shapes that cover each block with its translation."""
    blocks = [b for b in detector.detect(image) if b.text.strip()]
    if not blocks:
        return []
    translated = translator.translate([b.text for b in blocks], target, source)
    shapes: list[Shape] = []
    for block, text in zip(blocks, translated):
        size = max(10.0, block.region.height * 0.8)
        shapes.append(Rectangle(block.region, color=background, width=0, fill=background))
        shapes.append(Text((block.region.x, block.region.y), text, color=color, size=size))
    return shapes


def available_pipeline() -> "tuple[TextDetector, Translator] | None":
    """First registered detector + translator pair, or ``None`` if none are installed."""
    detectors, trans = text_detectors(), translators()
    if not detectors or not trans:
        return None
    detector = next(iter(detectors.values()))()
    translator = next(iter(trans.values()))()
    return detector, translator
