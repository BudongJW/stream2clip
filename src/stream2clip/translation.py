"""Subtitle translation (JP -> KR and others) with a name glossary.

stream2clip ships no translation service. :func:`translate_cues` sends subtitle text
through any :class:`~stream2clip.translate.Translator` (a registered plugin or a plain
function wrapped in ``CallableTranslator``) and keeps the timing.

Machine translation mangles VTuber names more than anything else, so a
:class:`Glossary` pins them: every glossary term is swapped for its translation
*before* the text goes to the translator (a Korean name inside a Japanese sentence is
left alone by translators) and any term that survives untranslated is swapped
afterwards.
"""

from __future__ import annotations

import csv
import io
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Iterable, Sequence

from .subtitles import Cue

if TYPE_CHECKING:
    from .translate import Translator

__all__ = ["Glossary", "translate_cues", "holodex_names", "get_translator", "load_translator", "is_translator_spec", "split_translator_spec"]

HOLODEX_API = "https://holodex.net/api/v2"


@dataclass(frozen=True)
class Glossary:
    """Fixed translations: ``{"兎田ぺこら": "우사다 페코라", "ぺこら": "페코라"}``."""

    terms: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | os.PathLike[str]) -> "Glossary":
        """``.json`` (an object) or CSV with ``source,target`` columns; rows without a target are skipped."""
        p = Path(path)
        text = p.read_text(encoding="utf-8-sig")
        if p.suffix.lower() == ".json":
            data = json.loads(text)
            return cls({str(k): str(v) for k, v in data.items() if k and v})
        terms: dict[str, str] = {}
        for row in csv.reader(io.StringIO(text)):
            if len(row) < 2 or not row[0].strip() or not row[1].strip():
                continue
            if row[0].strip().lower() == "source" and row[1].strip().lower() == "target":
                continue
            terms[row[0].strip()] = row[1].strip()
        return cls(terms)

    def save(self, path: str | os.PathLike[str], notes: dict[str, str] | None = None) -> Path:
        out = Path(path)
        with out.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["source", "target", "note"])
            for source, target in self.terms.items():
                writer.writerow([source, target, (notes or {}).get(source, "")])
        return out

    def apply(self, text: str) -> str:
        """Replace every term, longest first so a full name wins over the nickname inside it."""
        for source in sorted(self.terms, key=len, reverse=True):
            if source in text:
                text = text.replace(source, self.terms[source])
        return text

    def __len__(self) -> int:
        return len(self.terms)


def translate_cues(
    cues: Iterable[Cue],
    translator: "Translator",
    *,
    target: str = "ko",
    source: str | None = None,
    glossary: Glossary | None = None,
    bilingual: bool = False,
    batch: int = 40,
) -> list[Cue]:
    """Translate cue text and keep the timing.

    Word timings belong to the original words, so translated cues carry none (they are
    shown as plain captions, not karaoke). ``bilingual`` keeps the original line above the
    translation. Text is sent in batches of ``batch`` cues so the translator sees context.
    """
    cues = list(cues)
    texts = [c.text.replace("\n", " ").strip() for c in cues]
    prepared = [glossary.apply(t) if glossary else t for t in texts]
    translated: list[str] = []
    for start in range(0, len(prepared), max(1, batch)):
        chunk = prepared[start : start + max(1, batch)]
        wanted = [t for t in chunk if t]
        result = list(translator.translate(wanted, target, source)) if wanted else []
        if len(result) != len(wanted):
            raise ValueError(f"The translator returned {len(result)} lines for {len(wanted)}")
        answers = iter(result)
        translated += [next(answers) if t else "" for t in chunk]
    out = []
    for cue, original, text in zip(cues, texts, translated):
        text = (glossary.apply(text) if glossary else text).strip()
        if bilingual and original and text and text != original:
            text = f"{original}\n{text}"
        out.append(Cue(cue.start, cue.end, text or original, speaker=cue.speaker))
    return out


def split_translator_spec(spec: str) -> tuple[str, str]:
    """``("file.py" or "package.module", name)``; the name defaults to ``translate``. A drive letter is not a separator."""
    if spec.lower().endswith(".py"):
        return spec, "translate"
    target, _, attr = spec.rpartition(":")
    return target, attr or "translate"


def load_translator(spec: str) -> "Translator":
    """A translator from your own code: ``file.py``, ``file.py:name`` or ``package.module:name``.

    ``name`` (default ``translate``) may be a function ``fn(texts, target, source) -> list[str]``,
    a class with a ``translate`` method, or an object that already has one. This is the
    quick way to connect a translation service without packaging a plugin - see
    ``examples/translators``.
    """
    import importlib
    import importlib.util

    from .translate import CallableTranslator

    target, attr = split_translator_spec(spec)
    if target.lower().endswith(".py"):
        path = Path(target).expanduser()
        if not path.is_file():
            raise RuntimeError(f"Translator file not found: {path}")
        module_spec = importlib.util.spec_from_file_location(f"stream2clip_translator_{path.stem}", path)
        if module_spec is None or module_spec.loader is None:
            raise RuntimeError(f"Cannot load {path} as Python code")
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
    else:
        try:
            module = importlib.import_module(target)
        except ImportError as exc:
            raise RuntimeError(f"Cannot import translator module {target!r}: {exc}") from exc
    found = getattr(module, attr, None)
    if found is None:
        raise RuntimeError(f"{target} has no {attr!r}")
    if isinstance(found, type):
        found = found()
    if hasattr(found, "translate"):
        return found
    if not callable(found):
        raise RuntimeError(f"{target}:{attr} is neither a function nor a translator")
    return CallableTranslator(found)


def is_translator_spec(name: str) -> bool:
    """``file.py``, ``file.py:name`` or ``module:name`` rather than the name of an installed plugin."""
    return name.lower().endswith(".py") or ":" in name


def get_translator(name: str | None = None) -> "Translator":
    """A translator by plugin name, from your own code (:func:`load_translator`), or the first plugin installed.

    Without a name the ``STREAM2CLIP_TRANSLATOR`` environment variable is used if set.
    """
    from .plugins import translators

    name = name or os.environ.get("STREAM2CLIP_TRANSLATOR") or None
    available = translators()
    if name is not None and name not in available and is_translator_spec(name):
        return load_translator(name)
    if not available:
        raise RuntimeError(
            "No translator is installed. stream2clip has no built-in translation service: point at your own code "
            "(--translator file.py, see examples/translators), register one "
            "(stream2clip.plugins.register_translator) or install a plugin - see docs/PORTING.md."
        )
    if name is None:
        return next(iter(available.values()))()
    if name not in available:
        raise RuntimeError(f"Unknown translator {name!r}; installed: {', '.join(available)}")
    return available[name]()


def holodex_names(
    org: str,
    api_key: str,
    *,
    get: Callable[[str, dict[str, str]], bytes] | None = None,
    limit: int = 50,
    max_pages: int = 40,
) -> tuple[Glossary, dict[str, str]]:
    """A draft name glossary for an organization (``"Hololive"``, ``"Nijisanji"``, ``"VSpo"`` ...) from Holodex.

    Holodex has Japanese and English names, not Korean ones: the draft maps each Japanese
    name to the English name so a translator keeps it consistent. Edit the ``target``
    column of the saved CSV to the Korean spelling you want. Needs a Holodex API key
    (https://holodex.net -> account settings). Returns the glossary and a note per term.
    """
    import urllib.parse
    import urllib.request

    def default_get(url: str, headers: dict[str, str]) -> bytes:
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - fixed https host
            return response.read()

    fetch = get or default_get
    if not api_key:
        raise ValueError("Holodex needs an API key (HOLODEX_API_KEY)")
    terms: dict[str, str] = {}
    notes: dict[str, str] = {}
    for page in range(max_pages):
        query = urllib.parse.urlencode({"type": "vtuber", "org": org, "limit": limit, "offset": page * limit})
        channels: list[dict[str, Any]] = json.loads(fetch(f"{HOLODEX_API}/channels?{query}", {"X-APIKEY": api_key, "User-Agent": "stream2clip"}))
        for channel in channels:
            name, english = (channel.get("name") or "").strip(), (channel.get("english_name") or "").strip()
            if name and english and name != english and not channel.get("inactive"):
                terms[name] = english
                notes[name] = " / ".join(part for part in (channel.get("org") or org, channel.get("group") or "") if part)
        if len(channels) < limit:
            break
    return Glossary(terms), notes


def glossary_from(items: Sequence[tuple[str, str]]) -> Glossary:
    return Glossary({s: t for s, t in items if s and t})
