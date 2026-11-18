"""Optional OCR detector backed by Tesseract (``pip install "stream2clip[ocr]"``).

Register it from a host application::

    from stream2clip.plugins import register_text_detector
    from stream2clip.translate.tesseract import TesseractDetector
    register_text_detector("tesseract", lambda: TesseractDetector(lang="jpn+eng"))
"""

from __future__ import annotations

from PIL import Image

from ..geometry import Region
from . import TextBlock

__all__ = ["TesseractDetector"]


class TesseractDetector:
    def __init__(self, lang: str = "jpn+eng", min_confidence: float = 50.0) -> None:
        try:
            import pytesseract  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError('TesseractDetector needs: pip install "stream2clip[ocr]" and the tesseract binary') from exc
        self._tess = pytesseract
        self.lang = lang
        self.min_confidence = min_confidence

    def detect(self, image: Image.Image) -> list[TextBlock]:
        data = self._tess.image_to_data(image.convert("RGB"), lang=self.lang, output_type=self._tess.Output.DICT)
        lines: dict[tuple[int, int, int], list[int]] = {}
        for i, word in enumerate(data["text"]):
            if word.strip() and float(data["conf"][i]) >= self.min_confidence:
                key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
                lines.setdefault(key, []).append(i)
        blocks: list[TextBlock] = []
        for indices in lines.values():
            left = min(data["left"][i] for i in indices)
            top = min(data["top"][i] for i in indices)
            right = max(data["left"][i] + data["width"][i] for i in indices)
            bottom = max(data["top"][i] + data["height"][i] for i in indices)
            joiner = "" if any(ord(ch) > 0x2E80 for i in indices for ch in data["text"][i]) else " "
            text = joiner.join(data["text"][i] for i in indices)
            blocks.append(TextBlock(Region(left, top, right - left, bottom - top), text))
        return blocks
