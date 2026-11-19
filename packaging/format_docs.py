"""Keep the label column of the documents' tables on one line when GitHub shows them.

GitHub lays tables out automatically: next to a long text column, a column of short Korean labels is
squeezed to two characters and the labels (and the header itself) break in the middle of a word. Markdown
has no column widths, so the header of every centred first column is made unbreakable and padded to the
width of its longest label:

    | 항목 | 내용 |          ->   | &numsp;&numsp;항&NoBreak;목&numsp;&numsp; | 내용 |
    |:---:|---|                  |:---:|---|
    | 사전 설정 | ... |           | 사전 설정 | ... |

``&NoBreak;`` (word joiner) has no width, ``&numsp;`` (figure space) does not break. Only tables whose first
column is centred (``|:---:|``) are touched: that is how the documents mark a label column.

    python packaging/format_docs.py            # rewrite README.md, CHANGELOG.md, ... and docs/*.md
    python packaging/format_docs.py --check    # exit 1 if a file would change
"""

from __future__ import annotations

import argparse
import math
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ("README.md", "CHANGELOG.md", "CONTRIBUTING.md", "SECURITY.md")

# Widths in pixels as GitHub renders a table cell (measured in Chrome on Windows, 2026-11).
WIDE = 14.72  # Hangul, kana, kanji, full-width forms
NARROW = 8.45  # Latin letters and digits, on average
SPACE = 4.0
CODE = 5.7  # one character inside `code` or <kbd>
CODE_BOX = 11.0  # the padding of a `code` or <kbd> box
PAD = 8.88  # one &numsp;
MARGIN = 6.0
LIMIT = 190.0  # a longer label may wrap

JOIN = "&NoBreak;"
FILL = "&numsp;"
SEPARATOR = re.compile(r"^\|[\s:|-]+\|\s*$")
ENTITIES = re.compile(r"&(?:NoBreak|numsp|nbsp);")


def cells(line: str) -> list[str]:
    """The cells of a table row; a ``|`` inside `code` does not divide."""
    parts, current, in_code = [], [], False
    for ch in line.strip().strip("|"):
        if ch == "`":
            in_code = not in_code
        if ch == "|" and not in_code:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    parts.append("".join(current).strip())
    return parts


def text_width(text: str) -> float:
    total = 0.0
    for ch in text:
        if ch.isspace():
            total += SPACE
        elif unicodedata.east_asian_width(ch) in "WF":
            total += WIDE
        else:
            total += NARROW
    return total


def label_width(cell: str) -> float:
    """How wide a label is when it stays on one line."""
    widest = 0.0
    for line in re.split(r"<br\s*/?>", cell):
        line = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", line).replace("**", "")
        width = 0.0
        for boxed in re.findall(r"`([^`]*)`|<kbd>(.*?)</kbd>", line):
            width += len(boxed[0] or boxed[1]) * CODE + CODE_BOX
        line = re.sub(r"`[^`]*`|<kbd>.*?</kbd>", "", line)
        line = re.sub(r"<[^>]+>", "", line)
        widest = max(widest, width + text_width(line))
    return widest


def plain_header(cell: str) -> str:
    return ENTITIES.sub(lambda found: " " if found.group() == "&nbsp;" else "", cell).strip()


def padded_header(title: str, labels: list[str]) -> str:
    """``title`` as one unbreakable piece, at least as wide as the widest of ``labels``."""
    joined = "&nbsp;".join(JOIN.join(word) for word in title.split())
    need = min(LIMIT, max((label_width(label) for label in labels), default=0.0)) + MARGIN - text_width(title)
    side = max(0, math.ceil(need / PAD / 2))
    return f"{FILL * side}{joined}{FILL * side}"


def format_text(text: str) -> str:
    lines = text.split("\n")
    fenced = False
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.lstrip().startswith("```"):
            fenced = not fenced
        following = lines[index + 1] if index + 1 < len(lines) else ""
        if not fenced and line.startswith("|") and SEPARATOR.match(following) and cells(following)[0] == ":---:":
            head = cells(line)
            title = plain_header(head[0])
            end = index + 2
            while end < len(lines) and lines[end].startswith("|"):
                end += 1
            labels = [cells(row)[0] for row in lines[index + 2:end]]
            if title and not re.search(r"[`<*\[]", title):
                head[0] = padded_header(title, labels)
                lines[index] = "| " + " | ".join(head) + " |"
            index = end
            continue
        index += 1
    return "\n".join(lines)


def documents(root: Path = ROOT) -> list[Path]:
    return [root / name for name in FILES] + sorted((root / "docs").glob("*.md"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true", help="change nothing; exit 1 if a file is not formatted")
    args = parser.parse_args(argv)
    stale = []
    for path in documents():
        before = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        after = format_text(before)
        if after != before:
            stale.append(path)
            if not args.check:
                path.write_text(after, encoding="utf-8", newline="\n")
    for path in stale:
        print(("needs formatting: " if args.check else "formatted: ") + path.relative_to(ROOT).as_posix())
    return 1 if args.check and stale else 0


if __name__ == "__main__":
    sys.exit(main())
