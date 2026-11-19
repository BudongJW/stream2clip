"""The project site (GitHub Pages): it builds, its links lead somewhere, and it stays on brand."""

from __future__ import annotations

import importlib.util
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

import stream2clip
from stream2clip import brand

ROOT = Path(__file__).parents[1]
PAGES = ("index.html", "guide.html")


@pytest.fixture(scope="module")
def site_builder():
    spec = importlib.util.spec_from_file_location("build_site", ROOT / "packaging" / "build_site.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def built(site_builder, tmp_path_factory):
    return site_builder.build(tmp_path_factory.mktemp("site") / "out")


class Page(HTMLParser):
    """Collects what a page links to, the ids it defines and its visible text."""

    def __init__(self, text: str) -> None:
        super().__init__()
        self.links: list[tuple[str, str, dict[str, str | None]]] = []
        self.ids: set[str] = set()
        self.text: list[str] = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(values["id"])
        for name in ("href", "src"):
            if values.get(name):
                self.links.append((tag, values[name], values))

    def handle_data(self, data):
        self.text.append(data)


def pages(folder: Path) -> dict[str, Page]:
    return {name: Page((folder / name).read_text(encoding="utf-8")) for name in PAGES}


def test_every_file_the_pages_show_is_in_the_built_site(site_builder, built):
    for source in site_builder.ASSETS.values():
        assert (ROOT / source).is_file(), source  # the brand files and screenshots are not kept twice
    parsed = pages(built)
    checked = 0
    for name, page in parsed.items():
        for _tag, link, _attrs in page.links:
            if link.startswith(("https://", "mailto:")):
                continue
            assert not link.startswith(("http://", "/", "//")), f"{name}: {link} would break under /stream2clip/"
            target, _, anchor = link.partition("#")
            if target == site_builder.PDF_NAME:  # written by --pdf
                continue
            file = name if target == "" else "index.html" if target == "./" else target
            assert (built / file).is_file(), f"{name}: {link}"
            if anchor:
                assert anchor in parsed[file].ids, f"{name}: no #{anchor} in {file}"
            checked += 1
    assert checked > 30
    css = (built / "css" / "site.css").read_text(encoding="utf-8")
    assert not re.findall(r"url\(", css)  # nothing else to resolve
    assert (built / ".nojekyll").is_file() and (built / "img" / "timeline.svg").read_text(encoding="utf-8").startswith("<svg")


def test_download_buttons_follow_the_latest_release(built):
    index = Page((built / "index.html").read_text(encoding="utf-8"))
    buttons = [(link, attrs) for _tag, link, attrs in index.links if "data-download" in attrs]
    assert len(buttons) == 2
    for link, _attrs in buttons:  # without the script (or the API) they lead to the releases page, never to an old file
        assert link == "https://github.com/BudongJW/stream2clip/releases/latest"
    everything = "".join((built / name).read_text(encoding="utf-8") for name in (*PAGES, "js/site.js"))
    assert "releases/download/" not in everything
    script = (built / "js" / "site.js").read_text(encoding="utf-8")
    assert 'REPO = "BudongJW/stream2clip"' in script and "/releases/latest" in script and "windows-x64" in script and ".catch(" in script
    guide_links = [link for _tag, link, attrs in index.links if link.startswith("guide.html") or link == "stream2clip-guide.pdf"]
    assert "guide.html" in guide_links and "stream2clip-guide.pdf" in guide_links


def test_the_manual_covers_the_app_and_names_its_version(built):
    guide = Page((built / "guide.html").read_text(encoding="utf-8"))
    for section in ("install", "first-run", "capture", "record", "clips", "subtitles", "obs", "live", "cli", "trouble", "rules"):
        assert section in guide.ids
    text = " ".join("".join(guide.text).split())
    major_minor = ".".join(stream2clip.__version__.split(".")[:2])
    assert f"v{major_minor}" in text, "the manual says which version it describes: update it with the release"
    for word in ("winget install Gyan.FFmpeg", "stream2clip-gui.exe", "F8", "F9", "F10", "하이라이트 찾기", "리플레이 버퍼", "Smart App Control", "법적 판단이 아닙니다"):
        assert word in text, word


def test_the_site_is_on_brand_and_names_nobody(built):
    css = (built / "css" / "site.css").read_text(encoding="utf-8")
    for color in (brand.INK, brand.PAPER, brand.LIVE_PINK, brand.HIGHLIGHT):
        assert color.lower() in css.lower()
    for face in ("Outfit", "Noto Sans KR", "JetBrains Mono"):
        assert face in css
    for path in built.rglob("*"):
        if path.suffix in (".html", ".css", ".js", ".svg"):
            text = path.read_text(encoding="utf-8")
            assert "Users\\" not in text and "/Users/" not in text and "/home/" not in text, path.name
    for name in PAGES:
        html = (built / name).read_text(encoding="utf-8")
        assert '<html lang="ko">' in html and 'name="viewport"' in html and "<title>" in html
        assert all("alt" in attrs for tag, _link, attrs in Page(html).links if tag == "img"), name


def test_manual_pdf_is_printed_by_a_browser(site_builder, built, monkeypatch, tmp_path):
    command = site_builder.pdf_command("chrome", built / "guide.html", built / "out.pdf")
    assert command[0] == "chrome" and "--headless=new" in command and command[-1].startswith("file:") and command[-1].endswith("/guide.html")
    assert f"--print-to-pdf={built / 'out.pdf'}" in command and "--no-pdf-header-footer" in command

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        target = Path(next(part for part in cmd if part.startswith("--print-to-pdf=")).split("=", 1)[1])
        target.write_bytes(b"%PDF-1.7\n" + b"x" * 20_000)

    pdf = site_builder.print_manual(built, "my-browser", run=fake_run)
    assert pdf.name == site_builder.PDF_NAME and pdf.parent == built.resolve() and calls[0][0] == "my-browser"
    pdf.unlink()

    class Failed:
        returncode, stderr = 1, "cannot open display"

    with pytest.raises(RuntimeError, match="cannot open display"):
        site_builder.print_manual(built, "my-browser", run=lambda cmd, **kwargs: Failed())

    program = tmp_path / "browser.exe"
    program.write_bytes(b"")
    monkeypatch.setenv("STREAM2CLIP_BROWSER", str(program))
    assert site_builder.find_browser() == str(program)
    monkeypatch.setenv("STREAM2CLIP_BROWSER", str(tmp_path / "missing.exe"))
    assert site_builder.find_browser() is None
    with pytest.raises(RuntimeError, match="STREAM2CLIP_BROWSER"):
        site_builder.print_manual(built)


def test_build_replaces_an_older_build(site_builder, tmp_path):
    out = tmp_path / "site"
    out.mkdir()
    (out / "old.html").write_text("stale", encoding="utf-8")
    assert site_builder.main(["-o", str(out)]) == 0
    assert not (out / "old.html").exists() and (out / "index.html").is_file() and (out / "assets" / "kiri" / "kiri_wink_512.png").is_file()
