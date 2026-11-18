"""Example subtitle translator for stream2clip: any OpenAI-compatible chat endpoint.

stream2clip has no translation service built in. This file shows how little it takes to
connect one - a function ``translate(texts, target, source) -> list[str]`` - and works
as it is with a local Ollama, LM Studio or llama.cpp server, or a hosted service that
speaks the same API::

    stream2clip clips video.mp4 --highlights h.json --subtitles ja.vtt \
        --translate ko --translator examples/translators/openai_compatible.py

Settings (environment variables):

    S2C_TRANSLATE_URL     default http://127.0.0.1:11434/v1/chat/completions  (Ollama)
    S2C_TRANSLATE_MODEL   default qwen2.5:7b
    S2C_TRANSLATE_KEY     API key, if the endpoint wants one
    S2C_TRANSLATE_TIMEOUT seconds to wait for one answer (default 300)

Only the standard library is used, so the file also works with the Windows build.
Copy it and change the prompt to taste; the name glossary (``--glossary``) is applied by
stream2clip before and after this function runs.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Sequence

DEFAULT_URL = "http://127.0.0.1:11434/v1/chat/completions"
DEFAULT_MODEL = "qwen2.5:7b"
LANGUAGES = {"ko": "Korean (한국어)", "ja": "Japanese (日本語)", "en": "English", "zh": "Chinese (中文)", "id": "Indonesian", "es": "Spanish"}


def _language(code: str | None) -> str:
    return LANGUAGES.get((code or "").lower(), code or "the original language")


def _post(url: str, payload: dict, headers: dict[str, str], timeout: float) -> dict:
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - the URL is the user's own setting
        return json.loads(response.read().decode("utf-8"))


def _ask(system: str, user: str) -> str:
    url = os.environ.get("S2C_TRANSLATE_URL", DEFAULT_URL)
    key = os.environ.get("S2C_TRANSLATE_KEY")
    payload = {
        "model": os.environ.get("S2C_TRANSLATE_MODEL", DEFAULT_MODEL),
        "temperature": 0,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    try:
        answer = _post(url, payload, headers, float(os.environ.get("S2C_TRANSLATE_TIMEOUT", "300")))
    except urllib.error.HTTPError as exc:  # e.g. 404 for a model that is not installed, 401 for a missing key
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"The translation endpoint {url} answered {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Cannot reach the translation endpoint {url} ({exc.reason}). Is the server running? Set S2C_TRANSLATE_URL to change it.") from exc
    return answer["choices"][0]["message"]["content"]


def _parse_list(text: str, expected: int) -> list[str] | None:
    """The JSON array inside the answer, if it has exactly the lines we asked for."""
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except ValueError:
        return None
    if not isinstance(data, list) or len(data) != expected:
        return None
    return [str(item).strip() for item in data]


def translate(texts: Sequence[str], target: str, source: str | None = None) -> list[str]:
    """Translate subtitle lines; the answer has one line per input line, in the same order."""
    texts = list(texts)
    if not texts:
        return []
    to = _language(target)
    style = (
        f"You are a subtitle translator. Translate livestream subtitles from {_language(source)} into {to}. "
        f"Every line of your answer must be written in {to}, never in another language. "
        "Keep it short and natural, as spoken. Keep names and words that are already in the target language as they are. "
    )
    answer = _ask(
        style + "The user sends a JSON array of lines. Reply with only a JSON array of the translated lines: same length, same order.",
        f"Translate into {to}:\n" + json.dumps(texts, ensure_ascii=False),
    )
    lines = _parse_list(answer, len(texts))
    if lines is not None:
        return lines
    # The model merged or split lines: ask again one line at a time so the timing still matches.
    return [_ask(style + "Reply with only the translation of the user's line.", f"Translate into {to}:\n{line}").strip() for line in texts]
