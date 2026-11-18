"""Translators from your own code (``--translator file.py``) and the example in ``examples/translators``."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from stream2clip import plugins
from stream2clip.cli import main
from stream2clip.translation import get_translator, is_translator_spec, load_translator, split_translator_spec

from .conftest import needs_ffmpeg

EXAMPLE = Path(__file__).parents[1] / "examples" / "translators" / "openai_compatible.py"

CODE = '''
def translate(texts, target, source=None):
    return [f"{target}:{t}" for t in texts]


def other(texts, target, source=None):
    return [t.upper() for t in texts]


def short(texts, target, source=None):
    return texts[:-1]


class Service:
    def translate(self, texts, target, source=None):
        return ["svc:" + t for t in texts]


ready = Service()
NOT_CALLABLE = 3
'''


def test_spec_parsing():
    assert split_translator_spec("C:/clips/mine.py") == ("C:/clips/mine.py", "translate")  # the drive colon is not a separator
    assert split_translator_spec("C:/clips/mine.py:other") == ("C:/clips/mine.py", "other")
    assert split_translator_spec("mine.PY") == ("mine.PY", "translate")
    assert split_translator_spec("pkg.mod:fn") == ("pkg.mod", "fn")
    assert is_translator_spec("mine.py") and is_translator_spec("pkg.mod:fn") and not is_translator_spec("deepl")


def test_translator_from_your_own_code(tmp_path, monkeypatch):
    """No plugin packaging needed: point at a file or a module."""
    code = tmp_path / "mine.py"
    code.write_text(CODE, encoding="utf-8")
    monkeypatch.setattr(plugins, "_collect", lambda group: {})  # no plugin installed
    assert get_translator(str(code)).translate(["a", "b"], "ko") == ["ko:a", "ko:b"]  # the function named translate
    assert get_translator(f"{code}:other").translate(["a"], "ko") == ["A"]
    assert load_translator(f"{code}:Service").translate(["a"], "ko") == ["svc:a"]  # a class is instantiated
    assert load_translator(f"{code}:ready").translate(["a"], "ko") == ["svc:a"]  # an object with translate() is used as it is
    with pytest.raises(ValueError, match="different number"):
        load_translator(f"{code}:short").translate(["a", "b"], "ko")  # a line count that would break the timing

    monkeypatch.syspath_prepend(str(tmp_path))
    assert get_translator("mine:other").translate(["x"], "ko") == ["X"]  # module:function
    monkeypatch.setenv("STREAM2CLIP_TRANSLATOR", f"{code}:other")
    assert get_translator().translate(["env"], "ko") == ["ENV"]  # the default when no name is given


def test_translator_spec_errors(tmp_path, monkeypatch):
    code = tmp_path / "mine.py"
    code.write_text(CODE, encoding="utf-8")
    for spec, message in (
        (str(tmp_path / "gone.py"), "not found"),
        (f"{code}:missing", "has no 'missing'"),
        (f"{code}:NOT_CALLABLE", "neither a function nor a translator"),
        ("no_such_package_xyz:translate", "Cannot import"),
    ):
        with pytest.raises(RuntimeError, match=message):
            load_translator(spec)
    monkeypatch.setattr(plugins, "_collect", lambda group: {})
    monkeypatch.delenv("STREAM2CLIP_TRANSLATOR", raising=False)
    with pytest.raises(RuntimeError, match="examples/translators"):  # the hint names the quick way
        get_translator()
    # An installed plugin whose name happens to contain a colon still wins over the file reading.
    monkeypatch.setattr(plugins, "_collect", lambda group: {"my:plugin": lambda: "PLUGIN"})
    assert get_translator("my:plugin") == "PLUGIN"


def test_example_translator_talks_to_an_openai_compatible_endpoint(monkeypatch):
    translator = load_translator(str(EXAMPLE))
    posts = []

    def fake_post(url, payload, headers, timeout):
        posts.append((url, payload, headers))
        heading, _, user = payload["messages"][1]["content"].partition(chr(10))
        assert heading == "Translate into Korean (한국어):"  # the target is repeated next to the text
        if not user.startswith("["):  # asked one line at a time
            return {"choices": [{"message": {"content": " 한 줄: " + user + "\n"}}]}
        lines = json.loads(user)
        if len(lines) == 3:  # a model that merges lines
            return {"choices": [{"message": {"content": '["합쳐짐"]'}}]}
        answer = json.dumps([f"번역 {x}" for x in lines], ensure_ascii=False)
        return {"choices": [{"message": {"content": "Here you go:\n```json\n" + answer + "\n```"}}]}

    monkeypatch.setitem(translator._fn.__globals__, "_post", fake_post)
    monkeypatch.setenv("S2C_TRANSLATE_URL", "http://127.0.0.1:9/v1/chat/completions")
    monkeypatch.setenv("S2C_TRANSLATE_MODEL", "test-model")
    monkeypatch.setenv("S2C_TRANSLATE_KEY", "sk-test")
    assert translator.translate(["こんにちは", "草"], "ko", "ja") == ["번역 こんにちは", "번역 草"]  # the array is found inside the chatter
    url, payload, headers = posts[0]
    assert url.endswith(":9/v1/chat/completions") and payload["model"] == "test-model" and payload["temperature"] == 0
    assert headers == {"Authorization": "Bearer sk-test"}
    assert "Japanese" in payload["messages"][0]["content"] and "Korean" in payload["messages"][0]["content"]

    posts.clear()
    monkeypatch.delenv("S2C_TRANSLATE_KEY")
    assert translator.translate(["a", "b", "c"], "ko") == ["한 줄: a", "한 줄: b", "한 줄: c"]  # wrong count: asked again line by line
    assert len(posts) == 4 and posts[1][2] == {}  # no key, no Authorization header
    assert translator.translate([], "ko") == [] and len(posts) == 4


def test_example_uses_only_the_standard_library():
    import ast

    tree = ast.parse(EXAMPLE.read_text(encoding="utf-8"))
    imported = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    imported |= {node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    assert imported <= {"__future__", "json", "os", "urllib", "typing"}  # so it also runs inside the Windows build


@needs_ffmpeg
def test_cli_clips_with_a_translator_file(green_screen_video, tmp_path, monkeypatch):
    monkeypatch.setattr(plugins, "_collect", lambda group: {})
    code = tmp_path / "tr.py"
    code.write_text('def translate(texts, target, source=None):\n    return ["[" + target + "] " + t for t in texts]\n', encoding="utf-8")
    srt = tmp_path / "subs.srt"
    srt.write_text("1\n00:00:00,100 --> 00:00:00,900\nこんにちは\n", encoding="utf-8")
    highlights = tmp_path / "h.json"
    highlights.write_text(json.dumps({"highlights": [{"rank": 1, "start": 0.0, "end": 2.0}]}), encoding="utf-8")
    out = tmp_path / "clips"
    args = ["clips", str(green_screen_video), "--highlights", str(highlights), "--subtitles", str(srt), "--translate", "ko",
            "--translator", str(code), "--layout", "none", "-f", "gif", "--fps", "5", "-o", str(out)]
    assert main(args) == 0
    assert "[ko] こんにちは" in (out / "clip_01.ass").read_text(encoding="utf-8")


def test_example_translator_explains_an_unreachable_endpoint(monkeypatch):
    translator = load_translator(str(EXAMPLE))
    monkeypatch.setenv("S2C_TRANSLATE_URL", "http://127.0.0.1:1/v1/chat/completions")  # nothing listens there
    monkeypatch.setenv("S2C_TRANSLATE_TIMEOUT", "5")
    with pytest.raises(RuntimeError, match="Cannot reach the translation endpoint"):
        translator.translate(["hello"], "ko")
