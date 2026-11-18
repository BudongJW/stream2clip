"""Plugin registry.

Third-party packages extend stream2clip without forking it by exposing entry
points (``pyproject.toml``)::

    [project.entry-points."stream2clip.capture_backends"]
    obs = "my_pkg.obs:ObsCaptureBackend"

    [project.entry-points."stream2clip.translators"]
    deepl = "my_pkg.deepl:make_translator"      # -> stream2clip.translate.Translator

    [project.entry-points."stream2clip.text_detectors"]
    paddle = "my_pkg.ocr:make_detector"         # -> stream2clip.translate.TextDetector

Host applications can also register factories at runtime with the
``register_*`` helpers, which is the easiest route when embedding.
"""

from __future__ import annotations

from importlib.metadata import entry_points
from typing import Any, Callable

__all__ = [
    "capture_backends",
    "translators",
    "text_detectors",
    "register_capture_backend",
    "register_translator",
    "register_text_detector",
]

Factory = Callable[[], Any]
_RUNTIME: dict[str, dict[str, Factory]] = {
    "stream2clip.capture_backends": {},
    "stream2clip.translators": {},
    "stream2clip.text_detectors": {},
}


def _collect(group: str) -> dict[str, Factory]:
    found: dict[str, Factory] = {}
    try:
        for ep in entry_points(group=group):
            # Defer the import until the factory is actually used.
            found[ep.name] = lambda ep=ep: ep.load()()
    except Exception:  # pragma: no cover - broken metadata should never crash the host
        pass
    found.update(_RUNTIME[group])
    return found


def capture_backends() -> dict[str, Factory]:
    return _collect("stream2clip.capture_backends")


def translators() -> dict[str, Factory]:
    return _collect("stream2clip.translators")


def text_detectors() -> dict[str, Factory]:
    return _collect("stream2clip.text_detectors")


def register_capture_backend(name: str, factory: Factory) -> None:
    _RUNTIME["stream2clip.capture_backends"][name] = factory


def register_translator(name: str, factory: Factory) -> None:
    _RUNTIME["stream2clip.translators"][name] = factory


def register_text_detector(name: str, factory: Factory) -> None:
    _RUNTIME["stream2clip.text_detectors"][name] = factory
