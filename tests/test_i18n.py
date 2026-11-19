"""Interface language: the catalogs cover every text of the windows, and the language is chosen predictably."""

from __future__ import annotations

import ast
import json
import os
import string
import subprocess
import sys
from pathlib import Path

import pytest

from stream2clip import i18n

SRC = Path(__file__).parents[1] / "src" / "stream2clip"


def texts_in_code() -> dict[str, str]:
    """Every literal passed to tr() in the GUI modules -> the file it is in."""
    found: dict[str, str] = {}
    for path in sorted((SRC / "gui").glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "tr":
                assert node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str), f"{path.name}: tr() needs a literal"
                found.setdefault(node.args[0].value, path.name)
    return found


def fields(text: str) -> list[tuple[str, str]]:
    return sorted((name, spec or "") for _, name, spec, _ in string.Formatter().parse(text) if name is not None)


@pytest.fixture
def clean_language(monkeypatch):
    """Start from "nothing decided yet" and put the test run's Korean back afterwards."""
    monkeypatch.setattr(i18n, "_current", None)
    yield
    i18n.set_language(None)


@pytest.mark.parametrize("code", ["ja", "en"])
def test_catalog_covers_every_text_of_the_windows(code):
    used = texts_in_code()
    catalog = json.loads((SRC / "locales" / f"{code}.json").read_text(encoding="utf-8"))
    assert len(used) > 200
    assert sorted(set(used) - set(catalog)) == [], "texts in the code without a translation"
    assert sorted(set(catalog) - set(used)) == [], "translations of texts that are no longer in the code"
    for key, value in catalog.items():
        assert fields(key) == fields(value), f"placeholders differ: {key!r}"  # "{0:,}" must survive translation
        assert key.count("\n") == value.count("\n"), f"line breaks differ: {key!r}"  # two-line buttons stay two lines
        if key.strip() and key not in ("개",):  # a counter suffix may be empty in English
            assert value.strip(), f"empty translation: {key!r}"


def test_no_korean_literal_is_left_outside_tr():
    """A new text added without tr() would stay Korean in every language."""
    import re

    hangul = re.compile("[가-힣]")
    allowed = {"launcher.py": {"언어 / 言語 / Language", "다시 시작하면 한국어로 표시됩니다"}}
    left = []
    for path in sorted((SRC / "gui").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        inside_tr = {id(n) for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "tr" for n in ast.walk(node)}
        docstrings = {
            id(node.body[0].value) for node in ast.walk(tree)
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef)) and node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant)
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and hangul.search(node.value):
                if id(node) not in inside_tr and id(node) not in docstrings and node.value not in allowed.get(path.name, set()):
                    left.append((path.name, node.value))
    assert left == []


def test_tr_falls_back_to_korean(clean_language):
    assert i18n.set_language("ko") == "ko" and i18n.tr("저장") == "저장"
    assert i18n.set_language("ja") == "ja" and i18n.tr("저장") == "保存"
    assert i18n.set_language("en") == "en" and i18n.tr("저장") == "Save"
    assert i18n.tr("번역이 아직 없는 문구") == "번역이 아직 없는 문구"  # a missing entry shows the Korean text, never an error
    assert i18n.tr("클립 {0}개 저장됨: {1}{2}").format(3, "clips", "") == "Saved 3 clips: clips"
    assert i18n.catalog("ko") == {} and i18n.catalog("xx") == {}


def test_language_order_explicit_then_environment_then_system(clean_language, monkeypatch):
    monkeypatch.setattr(i18n, "system_language", lambda: "ja")
    monkeypatch.delenv("STREAM2CLIP_LANG")
    assert i18n.language() == "ja"  # the system's language
    monkeypatch.setenv("STREAM2CLIP_LANG", "en_US.UTF-8")
    assert i18n.set_language(None) == "en"  # the environment wins over the system
    assert i18n.set_language("ko-KR") == "ko"  # an explicit choice wins over both
    monkeypatch.setenv("STREAM2CLIP_LANG", "klingon")
    assert i18n.set_language("nonsense") == "ja"  # unknown values are ignored, down to the system's language


def test_system_language_reads_the_usual_variables(monkeypatch):
    monkeypatch.setattr(i18n.sys, "platform", "linux")
    for name in ("LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(i18n.locale, "getlocale", lambda: (None, None))
    assert i18n.system_language() == "en"
    monkeypatch.setenv("LANG", "ja_JP.UTF-8")
    assert i18n.system_language() == "ja"
    monkeypatch.setenv("LC_ALL", "ko_KR.UTF-8")
    assert i18n.system_language() == "ko"
    monkeypatch.setenv("LC_ALL", "C")
    assert i18n.system_language() == "en"
    monkeypatch.setenv("LC_ALL", "fr_FR.UTF-8")  # not offered: the next variable decides
    assert i18n.system_language() == "ja"


def test_saved_language_is_applied_before_the_windows_load(clean_language, monkeypatch):
    pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from stream2clip.gui import settings
    from stream2clip.gui.app import apply_saved_language

    monkeypatch.setattr(i18n, "system_language", lambda: "en")
    monkeypatch.delenv("STREAM2CLIP_LANG")
    assert apply_saved_language() == "en"  # nothing saved
    settings.save_section("app", {"language": "ja"})
    assert apply_saved_language() == "ja"
    monkeypatch.setenv("STREAM2CLIP_LANG", "ko")  # the environment variable is the stronger wish
    monkeypatch.setattr(i18n, "_current", None)
    assert apply_saved_language() == "ko"
    settings.save_section("app", {"language": 7})
    monkeypatch.delenv("STREAM2CLIP_LANG")
    monkeypatch.setattr(i18n, "_current", None)
    assert apply_saved_language() == "en"  # a value that is not a language is ignored


CHECK_WINDOWS = """
import os, sys
from stream2clip.gui.app import create_app
app = create_app([])
from stream2clip.gui.launcher import LauncherWindow
win = LauncherWindow()
h = win.open_highlights()
print("|".join([win.record_button.text(), win.highlights_button.text(), h.windowTitle(), h.export_button.text(), h.singing_combo.itemText(1),
                win.language_combo.currentText(), h.status.text()]))
win.language_combo.setCurrentIndex(win.language_combo.findData("ja"))
win._set_language(win.language_combo.currentIndex())
print(win.status.text())
h.close()
win.close()  # a normal close: gives the F8/F9 keys back and writes the settings
sys.stdout.flush()
"""


@pytest.mark.parametrize("code, expected", [
    ("en", ["●  Record an area (F9)", "Find highlights", "stream2clip Stream clips", "Export clips", "Mark songs", "English", "Choose the video and its chat replay, or paste the stream address"]),
    ("ja", ["●  範囲を録画 (F9)", "ハイライトを探す", "stream2clip 配信クリップ作成", "クリップを書き出す", "歌の区間を表示", "日本語", "動画とチャットリプレイを選ぶか、配信のURLを入れてください"]),
])
def test_windows_come_up_in_the_chosen_language(code, expected, tmp_path):
    """In a fresh process: tables of labels are translated when their module is imported."""
    pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    env = {**os.environ, "STREAM2CLIP_LANG": code, "STREAM2CLIP_CONFIG_DIR": str(tmp_path), "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8"}
    done = subprocess.run([sys.executable, "-c", CHECK_WINDOWS], capture_output=True, text=True, encoding="utf-8", env=env, timeout=120)
    assert done.returncode == 0, done.stderr[-800:]
    lines = done.stdout.strip().splitlines()
    assert lines[0].split("|") == expected
    notice = "再起動すると日本語で表示されます"  # said in the language that was picked
    assert (lines[1] == notice) if code == "en" else (notice not in lines[1])  # nothing to announce when it is already Japanese
    saved = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert saved["app"] == {"language": "ja"}


def test_texts_carry_no_decorative_marks():
    """Middle dots, arrows, dashes, ellipses and corner brackets are not used in what the program shows."""
    marks = "·ㆍ・•→←↔—–…「」『』〈〉《》“”‘’※"
    for code in ("ja", "en"):
        catalog = json.loads((SRC / "locales" / f"{code}.json").read_text(encoding="utf-8"))
        for key, value in catalog.items():
            assert not any(mark in key or mark in value for mark in marks), (code, key, value)
    left = []
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = {
            id(node.body[0].value) for node in ast.walk(tree)
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef)) and node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant)
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings and any(mark in node.value for mark in marks):
                left.append((path.name, node.value[:60]))
    assert left == []


def test_language_chosen_in_the_installer(tmp_path, monkeypatch, clean_language, capsys):
    """The installer leaves language.txt next to the programs; it ranks below the environment and above the system."""
    assert i18n.installed_language() is None  # not a built program: nothing to read
    assert i18n.installed_language(tmp_path) is None
    (tmp_path / i18n.INSTALL_FILE).write_text("ja\n", encoding="utf-8")
    assert i18n.installed_language(tmp_path) == "ja"
    (tmp_path / i18n.INSTALL_FILE).write_bytes(b"\xef\xbb\xbfko")  # written by another tool, with a byte order mark
    assert i18n.installed_language(tmp_path) == "ko"
    (tmp_path / i18n.INSTALL_FILE).write_text("klingon", encoding="utf-8")
    assert i18n.installed_language(tmp_path) is None

    (tmp_path / i18n.INSTALL_FILE).write_text("ja", encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "stream2clip.exe"))
    monkeypatch.setattr(i18n, "system_language", lambda: "en")
    monkeypatch.delenv("STREAM2CLIP_LANG", raising=False)
    monkeypatch.setattr(i18n, "_current", None)
    assert i18n.language() == "ja"
    monkeypatch.setenv("STREAM2CLIP_LANG", "ko")
    monkeypatch.setattr(i18n, "_current", None)
    assert i18n.language() == "ko"
    assert i18n.set_language("en") == "en"  # the choice made in the app itself comes first

    from stream2clip.cli import main

    monkeypatch.delenv("STREAM2CLIP_LANG")
    monkeypatch.setattr(i18n, "_current", None)
    assert main(["language", "-v"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "ja" and "installer (language.txt): ja" in out and "system: en" in out
