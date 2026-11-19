"""The project site (GitHub Pages): it builds, its links lead somewhere, and it stays on brand."""

from __future__ import annotations

import importlib.util
import posixpath
import re
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath

import pytest

import stream2clip
from stream2clip import brand

ROOT = Path(__file__).parents[1]
PAGES = ("index.html", "guide.html", "en/index.html", "en/guide.html", "ja/index.html", "ja/guide.html")
FOLDERS = {"ko": "", "en": "en/", "ja": "ja/"}


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
            here = PurePosixPath(name).parent
            file = name if target == "" else posixpath.normpath((here / target).as_posix())
            if target.endswith("/") or file == ".":
                file = posixpath.normpath(posixpath.join(file, "index.html"))
            assert not file.startswith(".."), f"{name}: {link} leaves the site"
            if file in site_builder.MANUALS.values():  # written by --pdf
                continue
            assert (built / file).is_file(), f"{name}: {link}"
            if anchor:
                assert anchor in parsed[file].ids, f"{name}: no #{anchor} in {file}"
            checked += 1
    assert checked > 100
    css = (built / "css" / "site.css").read_text(encoding="utf-8")
    urls = re.findall(r'url\("([^"]+)"\)', css)
    assert len(urls) == css.count("url(") == 1 and urls[0].startswith("https://cdn.jsdelivr.net/") and "TwemojiCountryFlags" in urls[0]  # only the flag font; no local file to resolve
    assert (built / ".nojekyll").is_file() and (built / "img" / "timeline.svg").read_text(encoding="utf-8").startswith("<svg")


@pytest.mark.parametrize("home, manual, pdf", [
    ("index.html", "guide.html", "stream2clip-guide.pdf"), ("en/index.html", "guide.html", "../stream2clip-guide-en.pdf"), ("ja/index.html", "guide.html", "../stream2clip-guide-ja.pdf"),
])
def test_download_buttons_follow_the_latest_release(built, home, manual, pdf):
    index = Page((built / home).read_text(encoding="utf-8"))
    buttons = [(link, attrs) for _tag, link, attrs in index.links if "data-download" in attrs]
    assert len(buttons) == 3 and [attrs["data-download"] for _link, attrs in buttons].count("zip") == 1  # installer twice, the zip once
    for link, _attrs in buttons:  # without the script (or the API) they lead to the releases page, never to an old file
        assert link == "https://github.com/BudongJW/stream2clip/releases/latest"
    everything = "".join((built / name).read_text(encoding="utf-8") for name in (*PAGES, "js/site.js"))
    assert "releases/download/" not in everything
    script = (built / "js" / "site.js").read_text(encoding="utf-8")
    assert 'REPO = "BudongJW/stream2clip"' in script and "/releases/latest" in script and "windows-x64-setup" in script and "windows-x64" in script and ".catch(" in script
    links = [link for _tag, link, _attrs in index.links]
    assert manual in links and pdf in links
    assert "data-release=\"date\"" not in (built / home).read_text(encoding="utf-8") and "published_at" not in script  # no release date on the page


@pytest.mark.parametrize("name", ["index.html", "guide.html"])
def test_each_page_links_to_its_other_languages(built, name):
    html = {code: (built / folder / name).read_text(encoding="utf-8") for code, folder in FOLDERS.items()}
    pages = {code: Page(text) for code, text in html.items()}
    tail = "" if name == "index.html" else name
    for code, page in pages.items():
        assert f'<html lang="{code}">' in html[code]
        others = {attrs["hreflang"]: link for tag, link, attrs in page.links if tag == "a" and attrs.get("hreflang")}
        assert set(others) == set(FOLDERS) - {code}  # a link to each other language, none to itself
        for other, link in others.items():
            here = PurePosixPath(FOLDERS[code] + name).parent
            target = posixpath.normpath((here / link).as_posix())
            target = "index.html" if target == "." else target + "/index.html" if link.endswith("/") else target
            assert target == FOLDERS[other] + name, (code, other, link)
        for other in FOLDERS:  # for search engines: every language names all three
            assert f'hreflang="{other}" href="https://budongjw.github.io/stream2clip/{FOLDERS[other]}{tail}"' in html[code]
        assert page.ids == pages["ko"].ids  # the same sections in every language
        for tag in ("h2", "h3", "tr", "li", "pre", "figure"):  # and the same structure: a translation, not a different page
            assert len(re.findall(f"<{tag}[ >]", html[code])) == len(re.findall(f"<{tag}[ >]", html["ko"])), (code, tag)


@pytest.mark.parametrize("page, words", [
    ("guide.html", ("하이라이트 찾기", "리플레이 버퍼", "라이브 모드 시작", "법적 판단이 아님")),
    ("en/guide.html", ("Find highlights", "replay buffer", "Start live mode", "not legal advice")),
    ("ja/guide.html", ("ハイライトを探す", "リプレイバッファ", "ライブモード開始", "法的判断ではない")),
])
def test_the_manual_covers_the_app_and_names_its_version(built, page, words):
    guide = Page((built / page).read_text(encoding="utf-8"))
    for section in ("install", "basics", "capture", "record", "clips", "subtitles", "obs", "live", "cli", "troubleshooting", "notice"):
        assert section in guide.ids
    text = " ".join("".join(guide.text).split())
    major_minor = ".".join(stream2clip.__version__.split(".")[:2])
    assert f"v{major_minor}" in text, "the manual says which version it describes: update it with the release"
    for word in ("winget install Gyan.FFmpeg", "stream2clip-gui.exe", "F8", "F9", "F10", "Smart App Control", *words):
        assert word in text, word
    for planned in ("다음 버전", "예정", "next version", "coming soon", "planned"):  # the manual describes the program as it is
        assert planned not in text


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
        assert 'name="viewport"' in html and "<title>" in html
        assert all("alt" in attrs for tag, _link, attrs in Page(html).links if tag == "img"), name


#: Marks and habits the pages do without: the copy is plain business Korean, and the layout carries no decoration.
UNWANTED_MARKS = "·ㆍ・•‧∙→←↔⇒—–…「」『』〈〉《》【】“”‘’✨✅🚀"
UNWANTED_PHRASES = (
    "됩니다", "하세요", "해요", "합니다", "입니다", "습니다", "세요.", "걸음", "쏙쏙", "손쉽게", "간편하게", "강력한",
    "です", "ます", "ください", "ましょう", "簡単に", "手軽に",
)
UNWANTED_WORDS = ("easily", "simply", "seamless", "seamlessly", "powerful", "effortless", "just", "you", "your", "we", "our", "let's", "amazing")
UNWANTED_STYLES = ("backdrop-filter", "text-transform", "@keyframes", "animation", "gradient", "transition", "letter-spacing: .", "border-left:")


def test_copy_is_plain_and_free_of_decorative_marks(built):
    for name in PAGES:
        html = (built / name).read_text(encoding="utf-8")
        page = Page(html)
        said = "".join(page.text) + " ".join(str(value) for _tag, _link, attrs in page.links for value in attrs.values() if value)
        said += " ".join(re.findall(r'content="([^"]*)"', html))
        for mark in UNWANTED_MARKS:
            assert mark not in said, f"{name}: {mark!r}"
        visible = re.sub(r"<(script|style|pre)\b.*?</\1>", " ", html, flags=re.S)
        assert "&lt;" not in visible and "&gt;" not in visible, name  # no angle brackets in the text either
        for phrase in UNWANTED_PHRASES:
            assert phrase not in said, f"{name}: {phrase!r} (write notes, not sentences)"
        for word in UNWANTED_WORDS:
            assert not re.search(rf"\b{re.escape(word)}\b", said, re.IGNORECASE), f"{name}: {word!r} (state the fact, do not address the reader)"
    css = (built / "css" / "site.css").read_text(encoding="utf-8")
    rules = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    for style in UNWANTED_STYLES:
        assert style not in rules, style
    assert "position: sticky" not in rules.split(".toc")[0]  # the header scrolls away with the page


def test_manual_pdf_is_printed_by_a_browser(site_builder, built, monkeypatch, tmp_path):
    command = site_builder.pdf_command("chrome", built / "guide.html", built / "out.pdf")
    assert command[0] == "chrome" and "--headless=new" in command and command[-1].startswith("file:") and command[-1].endswith("/guide.html")
    assert f"--print-to-pdf={built / 'out.pdf'}" in command and "--no-pdf-header-footer" in command

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        target = Path(next(part for part in cmd if part.startswith("--print-to-pdf=")).split("=", 1)[1])
        target.write_bytes(b"%PDF-1.7\n" + b"x" * 20_000)

    pdfs = site_builder.print_manuals(built, "my-browser", run=fake_run)
    assert [pdf.name for pdf in pdfs] == ["stream2clip-guide.pdf", "stream2clip-guide-en.pdf", "stream2clip-guide-ja.pdf"] and all(pdf.parent == built.resolve() for pdf in pdfs)
    assert [call[0] for call in calls] == ["my-browser"] * 3 and calls[1][-1].endswith("/en/guide.html") and calls[2][-1].endswith("/ja/guide.html")
    for pdf in pdfs:
        pdf.unlink()

    class Failed:
        returncode, stderr = 1, "cannot open display"

    with pytest.raises(RuntimeError, match="cannot open display"):
        site_builder.print_manuals(built, "my-browser", run=lambda cmd, **kwargs: Failed())

    program = tmp_path / "browser.exe"
    program.write_bytes(b"")
    monkeypatch.setenv("STREAM2CLIP_BROWSER", str(program))
    assert site_builder.find_browser() == str(program)
    monkeypatch.setenv("STREAM2CLIP_BROWSER", str(tmp_path / "missing.exe"))
    assert site_builder.find_browser() is None
    with pytest.raises(RuntimeError, match="STREAM2CLIP_BROWSER"):
        site_builder.print_manuals(built)


def test_build_replaces_an_older_build(site_builder, tmp_path):
    out = tmp_path / "site"
    out.mkdir()
    (out / "old.html").write_text("stale", encoding="utf-8")
    assert site_builder.main(["-o", str(out)]) == 0
    assert not (out / "old.html").exists() and (out / "index.html").is_file() and (out / "assets" / "kiri" / "kiri_wink_512.png").is_file()


@pytest.mark.parametrize("name", PAGES)
def test_language_is_chosen_from_a_dropdown_with_flags(built, name):
    html = (built / name).read_text(encoding="utf-8")
    menu = re.search(r'<details class="lang">(.*?)</details>', html, re.S)
    assert menu, name
    body = menu.group(1)
    assert [flag for flag in ("🇰🇷", "🇺🇸", "🇯🇵") if flag in body] == ["🇰🇷", "🇺🇸", "🇯🇵"] and body.count('class="flag"') == 4  # the current one in the button, all three in the list
    assert body.count("<li>") == 3 and body.count('aria-current="true"') == 1 and "<summary" in body
    assert "site.js" in html  # closes the menu on a click elsewhere
