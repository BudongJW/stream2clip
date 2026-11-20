"""Render the brand pictures that show the mascot: the key visual and the social preview.

    python packaging/build_brand.py                  render all four files into assets/brand
    python packaging/build_brand.py --only social    one of them (keyvisual, social)
    python packaging/build_brand.py --out DIR        somewhere else, to look at before replacing

The pictures are pages (``assets/brand/source/keyvisual.html``, ``social.html``) drawn by a
headless Chrome or Edge, like the manual's PDF. They show the mascot's own emote files, so when
the character changes - new masters, then ``python packaging/build_mascot.py`` - running this
once more brings the README's top picture, the site's link preview and GitHub's social preview
up to date with it. Texts are edited in the pages.

A browser draws with the fonts of the machine it runs on: Noto Sans KR and a monospace font
(JetBrains Mono, else Cascadia Mono or Consolas) should be installed. That is why the result is
looked at by a person and committed, not checked pixel by pixel in the tests.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_site import find_browser  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BRAND = ROOT / "assets" / "brand"
SOURCE = BRAND / "source"


@dataclass(frozen=True)
class Picture:
    page: str      # the page in assets/brand/source
    output: str    # the file in assets/brand
    width: int     # the page's size in CSS pixels
    height: int
    scale: int     # pixels per CSS pixel

    @property
    def size(self) -> tuple[int, int]:
        return self.width * self.scale, self.height * self.scale


PICTURES: dict[str, tuple[Picture, ...]] = {
    "keyvisual": (
        Picture("keyvisual.html", "02_concept-image_keyvisual_1920x1080.png", 1920, 1080, 1),
        Picture("keyvisual.html", "02_concept-image_keyvisual@2x.png", 1920, 1080, 2),
    ),
    "social": (
        Picture("social.html", "03_github-social-preview_1280x640.png", 1280, 640, 1),
        Picture("social.html", "03_github-social-preview@2x.png", 1280, 640, 2),
    ),
}


class _Files(HTMLParser):
    """The files a page loads: pictures, style sheets."""

    def __init__(self) -> None:
        super().__init__()
        self.found: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if value and ((tag == "img" and name == "src") or (tag == "link" and name == "href")):
                self.found.append(value)


def page_files(page: Path) -> list[Path]:
    """What a page shows, as paths; a page that reaches outside the repository is refused."""
    reader = _Files()
    reader.feed(page.read_text(encoding="utf-8"))
    files = []
    for name in reader.found:
        if "://" in name or name.startswith("//"):
            raise ValueError(f"{page.name} loads {name}: a brand picture is drawn from the repository's own files only")
        files.append((page.parent / name).resolve())
    return files


def screenshot_command(browser: str, page: Path, output: Path, picture: Picture, profile: Path) -> list[str]:
    return [
        browser, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run", "--no-default-browser-check",
        f"--user-data-dir={profile}", f"--force-device-scale-factor={picture.scale}", f"--window-size={picture.width},{picture.height}",
        "--virtual-time-budget=5000", f"--screenshot={output}", page.resolve().as_uri(),
    ]


def render(picture: Picture, out: Path, browser: str, *, source: Path = SOURCE, run=None) -> Path:
    """Draw one picture; it is only put in place when the browser wrote a file of the expected size."""
    page = source / picture.page
    missing = [str(path) for path in page_files(page) if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"{picture.page} shows a file that is not there: {missing[0]}")
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="stream2clip-brand-") as tmp:
        shot = Path(tmp) / "shot.png"
        (run or subprocess.run)(screenshot_command(browser, page, shot, picture, Path(tmp) / "profile"), check=True, timeout=180)
        if not shot.is_file():
            raise RuntimeError(f"the browser wrote no picture for {picture.page}")
        with Image.open(shot) as image:
            if image.size != picture.size:
                raise RuntimeError(f"{picture.page} came out {image.width}x{image.height}, not {picture.size[0]}x{picture.size[1]}")
            image.convert("RGB").save(out / picture.output, optimize=True)
    return out / picture.output


def build(names: tuple[str, ...] = tuple(PICTURES), out: Path = BRAND, browser: str | None = None, *, run=None) -> list[Path]:
    browser = browser or os.environ.get("STREAM2CLIP_BROWSER") or find_browser()
    if not browser:
        raise FileNotFoundError("Rendering the brand pictures needs Chrome or Edge: install one, or name it with --browser")
    return [render(picture, out, browser, run=run) for name in names for picture in PICTURES[name]]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", choices=sorted(PICTURES), action="append", help="render only this picture (can be given more than once)")
    parser.add_argument("--out", default=str(BRAND), help="where to write (default: assets/brand)")
    parser.add_argument("--browser", help="Chrome or Edge to draw with (default: the one found on this machine)")
    args = parser.parse_args(argv)
    for path in build(tuple(args.only) if args.only else tuple(PICTURES), Path(args.out), args.browser):
        with Image.open(path) as image:
            print(f"drew   {path.name}  ({image.width}x{image.height})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
