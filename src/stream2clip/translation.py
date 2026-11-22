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
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Iterable, Sequence

from .subtitles import Cue, Word, _is_cjk

if TYPE_CHECKING:
    from .translate import Translator

__all__ = ["Glossary", "translate_cues", "holodex_names", "get_translator", "load_translator", "is_translator_spec", "split_translator_spec"]

HOLODEX_API = "https://holodex.net/api/v2"


def _cell(cells: list[str], columns: dict[str, int], name: str) -> str:
    n = columns.get(name)
    return cells[n] if n is not None and n < len(cells) else ""


@dataclass(frozen=True)
class Glossary:
    """Fixed translations: ``{"兎田ぺこら": "우사다 페코라", "ぺこら": "페코라"}``.

    The same names also help speech recognition. :meth:`names` are given to the transcriber as
    hints, and ``heard`` maps what recognition writes instead of a name back to the name
    (``{"ペコラ": "ぺこら"}``), in transcripts and in downloaded subtitles alike.
    """

    terms: dict[str, str] = field(default_factory=dict)
    #: Misheard spelling to the name it should be (from the ``heard`` column).
    heard: dict[str, str] = field(default_factory=dict)
    #: Every name in the file, in its order, with or without a translation.
    vocabulary: tuple[str, ...] = ()

    @classmethod
    def load(cls, path: str | os.PathLike[str]) -> "Glossary":
        """``.json`` or CSV ``source,target[,note][,heard]``; ``heard`` lists misheard spellings separated by ``|``.

        JSON is ``{"source": "target"}`` or ``{"source": {"target": "...", "heard": ["...", "..."]}}``.
        A row without a target still counts as a name for recognition; it is not translated.
        """
        p = Path(path)
        text = p.read_text(encoding="utf-8-sig")
        rows: list[tuple[str, str, list[str]]] = []
        if p.suffix.lower() == ".json":
            for key, value in json.loads(text).items():
                if isinstance(value, dict):
                    heard = value.get("heard") or []
                    rows.append((str(key), str(value.get("target") or ""), [str(h) for h in ([heard] if isinstance(heard, str) else heard)]))
                else:
                    rows.append((str(key), str(value or ""), []))
        else:
            columns = {"source": 0, "target": 1, "heard": 3}
            for i, row in enumerate(csv.reader(io.StringIO(text))):
                cells = [cell.strip() for cell in row]
                if i == 0 and len(cells) >= 2 and cells[0].lower() == "source" and cells[1].lower() == "target":
                    columns = {name.lower(): n for n, name in enumerate(cells)}
                    continue
                rows.append((_cell(cells, columns, "source"), _cell(cells, columns, "target"), _cell(cells, columns, "heard").split("|")))
        terms: dict[str, str] = {}
        heard: dict[str, str] = {}
        vocabulary: list[str] = []
        for source, target, variants in rows:
            source, target = source.strip(), target.strip()
            if not source:
                continue
            if target:
                terms[source] = target
            for variant in variants:
                if variant.strip() and variant.strip() != source:
                    heard[variant.strip()] = source
            if source not in vocabulary:
                vocabulary.append(source)
        return cls(terms, heard, tuple(vocabulary))

    def save(self, path: str | os.PathLike[str], notes: dict[str, str] | None = None) -> Path:
        out = Path(path)
        names = list(self.vocabulary) or list(self.terms)
        with out.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["source", "target", "note", "heard"])
            for source in names:
                variants = "|".join(v for v, name in self.heard.items() if name == source)
                writer.writerow([source, self.terms.get(source, ""), (notes or {}).get(source, ""), variants])
        return out

    def apply(self, text: str) -> str:
        """Replace every term, longest first so a full name wins over the nickname inside it."""
        for source in sorted(self.terms, key=len, reverse=True):
            if source in text:
                text = text.replace(source, self.terms[source])
        return text

    def names(self, limit: int = 30) -> list[str]:
        """The names to give speech recognition as hints, in file order (the first ``limit``)."""
        return list(self.vocabulary or tuple(self.terms))[:limit]

    def fix(self, text: str) -> str:
        """``text`` with misheard spellings put back to the names, longest first."""
        for variant in sorted(self.heard, key=len, reverse=True):
            if variant in text:
                text = text.replace(variant, self.heard[variant])
        return text

    def fix_cues(self, cues: Iterable[Cue]) -> list[Cue]:
        """Cues with misheard names fixed in the text and in the karaoke words.

        A name that recognition split over several words becomes one word spanning their time,
        so the karaoke still lights it up as it is said.
        """
        cues = list(cues)
        if not self.heard:
            return cues
        return [replace(c, text=self.fix(c.text), words=self._fix_words(c.words)) for c in cues]

    def _fix_words(self, words: tuple[Word, ...]) -> tuple[Word, ...]:
        if not words:
            return words
        tokens = [w.text.strip() for w in words]
        joined, spans = "", []
        for i, token in enumerate(tokens):
            if i and token and joined and not (_is_cjk(token[:1]) or _is_cjk(joined[-1:])):
                joined += " "
            spans.append((len(joined), len(joined) + len(token)))
            joined += token
        hits: list[tuple[int, int, str]] = []
        taken = [False] * len(joined)
        for variant in sorted(self.heard, key=len, reverse=True):
            at = joined.find(variant)
            while at >= 0:
                end = at + len(variant)
                if not any(taken[at:end]):
                    hits.append((at, end, self.heard[variant]))
                    taken[at:end] = [True] * (end - at)
                at = joined.find(variant, end)
        if not hits:
            return words
        out: list[Word] = []
        i = 0
        for at, end, name in sorted(hits):
            first = next(k for k, (a, b) in enumerate(spans) if b > at)
            last = max(k for k, (a, b) in enumerate(spans) if a < end)
            if first < i:
                continue
            out.extend(words[i:first])
            head = tokens[first][: at - spans[first][0]]
            tail = tokens[last][end - spans[last][0]:]
            out.append(Word(words[first].start, words[last].end, head + name + tail))
            i = last + 1
        out.extend(words[i:])
        return tuple(out)

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
