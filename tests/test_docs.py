"""The repository's documents: their links lead somewhere, and they keep to the house style (notes, no decoration)."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from urllib.parse import unquote

import pytest

import stream2clip

ROOT = Path(__file__).parents[1]
DOCS = sorted([ROOT / "README.md", ROOT / "CHANGELOG.md", ROOT / "CONTRIBUTING.md", ROOT / "SECURITY.md", *(ROOT / "docs").glob("*.md")])
NAMES = [path.relative_to(ROOT).as_posix() for path in DOCS]

# The same marks the site and the app's own texts do without (tests/test_site.py, tests/test_i18n.py).
UNWANTED_MARKS = "·ㆍ・•‧∙→←↔⇒—–…「」『』〈〉《》【】“”‘’"
EMOJI = re.compile("[\U0001f300-\U0001faff☀-➿⬀-⯿️]")
# Notes end in a noun ("지원", "필요", "가능"), not in a polite or a plain sentence ending.
POLITE = ("니다", "세요", "해요", "에요", "예요", "어요", "아요")
PLAIN_ENDING = re.compile(r"[가-힣]다\.")
FILLER = ("손쉽게", "간편하게", "강력한", "쏙쏙", "다음 버전에서")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def without_fences(text: str) -> str:
    """The document without its fenced blocks (code, diagrams, file trees)."""
    kept, fenced = [], False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            kept.append(line)
    assert not fenced, "a fenced block is left open"
    return "\n".join(kept)


def prose(text: str) -> str:
    """What a reader reads as sentences: no code, no link targets, no HTML tags, no quoted screen texts."""
    text = without_fences(text)
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    text = re.sub(r"`[^`\n]*`", " ", text)
    text = re.sub(r"\]\([^)\s]*\)", "]", text)
    text = re.sub(r"<[^>\n]*>", " ", text)
    return re.sub(r'"[^"\n]*"', " ", text)


def slug(title: str) -> str:
    """The id GitHub gives a heading."""
    title = re.sub(r"<[^>]+>", "", title)
    title = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", title).replace("`", "").strip().lower()
    kept = [ch for ch in title if ch in "-_ " or unicodedata.category(ch)[0] in "LNM"]
    return "".join(kept).replace(" ", "-")


def anchors(path: Path) -> set[str]:
    found: set[str] = set()
    seen: dict[str, int] = {}
    for line in without_fences(read(path)).split("\n"):
        match = re.match(r"^(#{1,6})\s+(.*?)\s*$", line)
        if match:
            name = slug(match.group(2))
            count = seen.get(name, 0)
            seen[name] = count + 1
            found.add(name if count == 0 else f"{name}-{count}")
    return found


def links(text: str) -> list[str]:
    text = without_fences(text)
    return re.findall(r"\]\(([^)\s]+)\)", text) + re.findall(r'(?:href|src|srcset)="([^"]+)"', text)


def test_slug_follows_github():
    assert slug("5. 플러그인: 캡처 백엔드, OCR, 번역기") == "5-플러그인-캡처-백엔드-ocr-번역기"
    assert slug("라이브러리로 쓰기, 다른 프로젝트에 이식") == "라이브러리로-쓰기-다른-프로젝트에-이식"
    assert slug("Windows 실행 파일 (`packaging/`)") == "windows-실행-파일-packaging"


@pytest.mark.parametrize("path", DOCS, ids=NAMES)
def test_links_and_bookmarks_lead_somewhere(path):
    own = anchors(path)
    found = links(read(path))
    assert found or path.name == "SECURITY.md"
    for link in found:
        if link.startswith(("http://", "https://", "mailto:")):
            continue
        target, _, fragment = link.partition("#")
        fragment = unquote(fragment)
        if not target:
            assert not fragment or fragment in own, f"{path.name}: no heading for #{fragment}"
            continue
        destination = (path.parent / unquote(target)).resolve()
        assert destination.exists(), f"{path.name}: {target} does not exist"
        assert ROOT in destination.parents or destination == ROOT, f"{path.name}: {target} leaves the repository"
        if fragment and destination.suffix == ".md":
            assert fragment in anchors(destination), f"{path.name}: {target} has no heading for #{fragment}"


@pytest.mark.parametrize("path", DOCS, ids=NAMES)
def test_no_decorative_marks(path):
    # Fenced blocks keep their diagrams and file trees; everything else, link targets and badge texts included, is read.
    text = unquote(without_fences(read(path)))
    for mark in UNWANTED_MARKS:
        assert mark not in text, f"{path.name}: {mark!r} near {text[max(0, text.index(mark) - 40):text.index(mark) + 20]!r}"
    found = EMOJI.search(text)
    assert not found, f"{path.name}: emoji {found.group()!r}"


@pytest.mark.parametrize("path", DOCS, ids=NAMES)
def test_documents_are_written_as_notes(path):
    text = prose(read(path))
    for ending in POLITE + FILLER:
        assert ending not in text, f"{path.name}: {ending!r} near {text[max(0, text.index(ending) - 40):text.index(ending) + 10]!r}"
    found = PLAIN_ENDING.search(text)
    assert not found, f"{path.name}: sentence ending near {text[max(0, found.start() - 40):found.end()]!r}"


def test_templates_and_asset_notes_keep_the_same_style():
    others = [*(ROOT / ".github").glob("*.md"), *(ROOT / ".github" / "ISSUE_TEMPLATE").glob("*.yml"), *(ROOT / "assets" / "brand").rglob("README.txt")]
    assert len(others) >= 7
    for path in others:
        text = read(path)
        for mark in UNWANTED_MARKS:
            assert mark not in text, f"{path.name}: {mark!r}"
        assert not EMOJI.search(text), path.name
        for ending in POLITE:
            assert ending not in text, f"{path.name}: {ending!r}"
        assert not PLAIN_ENDING.search(text), path.name


def test_tables_have_no_empty_or_placeholder_cells_left_by_editing():
    # Seen after marks were stripped mechanically: cells holding only ":" and lists opened with "- []".
    for path in DOCS:
        for line in without_fences(read(path)).split("\n"):
            if line.startswith("|") and not re.fullmatch(r"\|[\s:|-]+\|", line):
                cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
                assert ":" not in cells and ":," not in " ".join(cells), f"{path.name}: {line[:80]}"
            assert not line.startswith("- []"), f"{path.name}: {line[:80]}"
            assert ", ," not in line, f"{path.name}: {line[:80]}"


def test_readme_names_the_current_version():
    text = read(ROOT / "README.md")
    version = stream2clip.__version__
    assert f"badge/version-{version}-" in text
    for name in re.findall(r"stream2clip-(\d+\.\d+\.\d+)-windows-x64", text):
        assert name == version


def test_readme_test_count_is_the_number_of_tests(request):
    text = read(ROOT / "README.md")
    badge = re.search(r"badge/tests-(\d+)-", text)
    table = re.search(r"\| (\d+)개\. 실제 마우스 이벤트", text)
    assert badge and table and badge.group(1) == table.group(1)
    collected = {Path(str(item.fspath)).name for item in request.session.items}
    every = {path.name for path in (ROOT / "tests").glob("test_*.py")}
    if collected != every:
        pytest.skip("only part of the suite was collected (a selection, or modules skipped for want of a display)")
    assert len(request.session.items) == int(badge.group(1)), "update the tests badge and the tech table in README.md"


def test_testing_document_lists_every_test_file():
    text = read(ROOT / "docs" / "TESTING.md")
    for path in (ROOT / "tests").glob("test_*.py"):
        assert f"`{path.name}`" in text, f"docs/TESTING.md does not describe {path.name}"
    for name in re.findall(r"`(test_\w+\.py)`", text):
        assert (ROOT / "tests" / name).is_file(), f"docs/TESTING.md describes {name}, which does not exist"
