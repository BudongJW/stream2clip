"""Put the project site together: the pages in ``site/`` plus the brand files and screenshots they show.

    python packaging/build_site.py            # -> dist/site (open index.html, or serve the folder)
    python packaging/build_site.py --pdf      # also print the manuals to stream2clip-guide.pdf / -en.pdf

The pages are plain HTML and CSS, Korean at the top, English under ``en/``, Japanese under ``ja/``. Images are
not kept twice in the repository: the logo,
favicon and mascot come from ``assets/brand`` and the screenshots from ``docs/images``;
:data:`ASSETS` says which file goes where. ``--pdf`` needs Chrome, Chromium or Edge
(``STREAM2CLIP_BROWSER`` names another one); GitHub Pages is built with it by
``.github/workflows/pages.yml``.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
PDF_NAME = "stream2clip-guide.pdf"
#: manual page -> the PDF printed from it (both in the root of the site)
MANUALS: dict[str, str] = {"guide.html": PDF_NAME, "en/guide.html": "stream2clip-guide-en.pdf", "ja/guide.html": "stream2clip-guide-ja.pdf"}

#: path in the built site -> file in the repository
ASSETS: dict[str, str] = {
    "assets/symbol-on-dark.svg": "assets/brand/logo/svg/symbol_color_on-dark.svg",
    "assets/symbol-on-light.svg": "assets/brand/logo/svg/symbol_color_on-light.svg",
    "assets/favicon.ico": "assets/brand/app-icons/web/favicon.ico",
    "assets/favicon.svg": "assets/brand/app-icons/web/favicon.svg",
    "assets/apple-touch-icon.png": "assets/brand/app-icons/web/apple-touch-icon.png",
    "assets/social.png": "assets/brand/03_github-social-preview_1280x640.png",
    "assets/kiri/kiri_wink_512.png": "assets/brand/mascot/kiri_wink_512.png",
    "assets/kiri/kiri_laugh_512.png": "assets/brand/mascot/kiri_laugh_512.png",
    "assets/kiri/kiri_focus_112.png": "assets/brand/mascot/kiri_focus_112.png",
    "assets/shots/launcher.png": "docs/images/launcher.png",
    "assets/shots/highlights_window.png": "docs/images/highlights_window.png",
    "assets/shots/editor.png": "docs/images/editor.png",
    "assets/shots/layouts.png": "docs/images/layouts.png",
    "assets/shots/launcher_ffmpeg.png": "docs/images/launcher_ffmpeg.png",
    "assets/shots/en/launcher_ffmpeg.png": "docs/images/en/launcher_ffmpeg.png",
    "assets/shots/ja/launcher_ffmpeg.png": "docs/images/ja/launcher_ffmpeg.png",
    "assets/shots/en/launcher.png": "docs/images/en/launcher.png",
    "assets/shots/en/highlights_window.png": "docs/images/en/highlights_window.png",
    "assets/shots/en/editor.png": "docs/images/en/editor.png",
    "assets/shots/ja/launcher.png": "docs/images/ja/launcher.png",
    "assets/shots/ja/highlights_window.png": "docs/images/ja/highlights_window.png",
    "assets/shots/ja/editor.png": "docs/images/ja/editor.png",
}

BROWSERS = (
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "msedge", "microsoft-edge",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)


def build(out: str | os.PathLike[str]) -> Path:
    """Copy the pages and their images into ``out`` (emptied first); returns the folder."""
    target = Path(out)
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(SITE, target)
    for name, source in ASSETS.items():
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / source, destination)
    (target / ".nojekyll").write_text("", encoding="utf-8")  # served as it is, no Jekyll pass
    return target


def find_browser(names: tuple[str, ...] = BROWSERS) -> str | None:
    wanted = os.environ.get("STREAM2CLIP_BROWSER")
    for name in ((wanted,) if wanted else names):
        found = shutil.which(name) or (name if Path(name).is_file() else None)
        if found:
            return found
    return None


def pdf_command(browser: str, page: Path, output: Path) -> list[str]:
    """Headless print of ``page``; the time budget lets the web fonts arrive before the page is laid out."""
    return [
        browser, "--headless=new", "--disable-gpu", "--no-sandbox", "--no-pdf-header-footer", "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=20000", f"--print-to-pdf={output}", page.resolve().as_uri(),
    ]


def print_manuals(site: Path, browser: str | None = None, *, run=subprocess.run) -> list[Path]:
    """Print the manual of every language of a built site to its PDF in the site's root."""
    browser = browser or find_browser()
    if not browser:
        raise RuntimeError("No Chrome, Chromium or Edge found for --pdf (set STREAM2CLIP_BROWSER to the program)")
    written = []
    for page, name in MANUALS.items():
        output = (site / name).resolve()
        done = run(pdf_command(browser, site / page, output), capture_output=True, text=True, timeout=180)
        if not output.is_file() or output.stat().st_size < 10_000:
            raise RuntimeError(f"The browser did not write {name} ({done.returncode}):\n{(done.stderr or '')[-600:]}")
        written.append(output)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-o", "--output", default=str(ROOT / "dist" / "site"), help="folder to write (default: dist/site)")
    parser.add_argument("--pdf", action="store_true", help="also print the manuals to PDF (" + ", ".join(MANUALS.values()) + ")")
    args = parser.parse_args(argv)
    site = build(args.output)
    print(f"site   {site}  ({sum(1 for p in site.rglob('*') if p.is_file())} files)")
    if args.pdf:
        for pdf in print_manuals(site):
            print(f"manual {pdf}  ({pdf.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
