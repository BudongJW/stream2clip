"""The brand pictures that show the mascot are drawn from pages in the repository, with the mascot's own emote files."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).parents[1]


@pytest.fixture(scope="module")
def brand():
    spec = importlib.util.spec_from_file_location("build_brand", ROOT / "packaging" / "build_brand.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["build_brand"] = module  # a dataclass looks its module up while it is being defined
    spec.loader.exec_module(module)
    return module


def test_pages_show_only_files_of_the_repository_and_the_mascots_own_emotes(brand):
    for name in ("keyvisual.html", "social.html"):
        files = brand.page_files(brand.SOURCE / name)
        assert files and all(path.is_file() for path in files), [str(p) for p in files if not p.is_file()]
        assert all(ROOT in path.parents for path in files)
        emotes = [path for path in files if path.parent == brand.BRAND / "mascot"]
        assert len(emotes) >= 3 and all(re.fullmatch(r"kiri_[a-z]+_512\.png", path.name) for path in emotes)  # the built emotes, not a drawing of its own
        assert brand.BRAND / "logo" / "png" / "lockup_on-dark.png" in files and brand.SOURCE / "brand.css" in files
        text = (brand.SOURCE / name).read_text(encoding="utf-8")
        assert "http://" not in text and "https://" not in text and "@import" not in text  # nothing is fetched while drawing
        visible = re.sub(r"<(script|style)\b.*?</\1>", "", text, flags=re.S)
        visible = re.sub(r"<[^>]+>", " ", visible)
        assert not any(mark in visible for mark in "·ㆍ・•→←↔—–…「」『』"), name  # the same plain wording as the documents
    css = (brand.SOURCE / "brand.css").read_text(encoding="utf-8")
    for colour in ("#15131F", "#F7F4FA", "#FF4F8B", "#FFD84D"):  # the brand's four colours
        assert colour in css


def test_a_page_that_reaches_outside_is_refused(brand, tmp_path):
    page = tmp_path / "page.html"
    page.write_text('<img src="https://example.invalid/a.png">', encoding="utf-8")
    with pytest.raises(ValueError, match="repository's own files only"):
        brand.page_files(page)
    page.write_text('<link rel="stylesheet" href="x.css"><img src="gone.png">', encoding="utf-8")
    assert [path.name for path in brand.page_files(page)] == ["x.css", "gone.png"]


def test_every_picture_has_its_size_and_the_committed_files_match(brand):
    assert sorted(brand.PICTURES) == ["keyvisual", "social"]
    for pictures in brand.PICTURES.values():
        assert [picture.scale for picture in pictures] == [1, 2] and len({picture.page for picture in pictures}) == 1
        for picture in pictures:
            assert picture.size == (picture.width * picture.scale, picture.height * picture.scale)
            with Image.open(brand.BRAND / picture.output) as image:
                assert image.size == picture.size and image.mode == "RGB", picture.output
    sizes = {picture.output: picture.size for pictures in brand.PICTURES.values() for picture in pictures}
    assert sizes["02_concept-image_keyvisual_1920x1080.png"] == (1920, 1080) and sizes["03_github-social-preview_1280x640.png"] == (1280, 640)


def test_screenshot_command(brand, tmp_path):
    picture = brand.PICTURES["social"][1]
    command = brand.screenshot_command("chrome", brand.SOURCE / picture.page, tmp_path / "out.png", picture, tmp_path / "profile")
    assert command[0] == "chrome" and "--headless=new" in command and "--force-device-scale-factor=2" in command and "--window-size=1280,640" in command
    assert f"--screenshot={tmp_path / 'out.png'}" in command and f"--user-data-dir={tmp_path / 'profile'}" in command  # its own profile: the user's browser is not touched
    assert command[-1].startswith("file:///") and command[-1].endswith("/assets/brand/source/social.html")


def test_a_picture_is_put_in_place_only_when_it_came_out_right(brand, tmp_path):
    picture = brand.PICTURES["social"][0]
    ran = []

    def draws(size):
        def run(command, check, timeout):
            ran.append(command)
            target = next(part for part in command if part.startswith("--screenshot=")).split("=", 1)[1]
            if size is not None:
                Image.new("RGBA", size, (21, 19, 31, 255)).save(target)

        return run

    made = brand.render(picture, tmp_path / "out", "browser", run=draws((1280, 640)))
    assert made == tmp_path / "out" / picture.output and Image.open(made).size == (1280, 640) and Image.open(made).mode == "RGB"
    with pytest.raises(RuntimeError, match="came out 1264x601, not 1280x640"):
        brand.render(picture, tmp_path / "bad", "browser", run=draws((1264, 601)))
    assert not (tmp_path / "bad" / picture.output).exists()
    with pytest.raises(RuntimeError, match="wrote no picture"):
        brand.render(picture, tmp_path / "none", "browser", run=draws(None))

    source = tmp_path / "source"
    source.mkdir()
    (source / picture.page).write_text('<img src="kiri.png">', encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="shows a file that is not there"):
        brand.render(picture, tmp_path / "out", "browser", source=source, run=draws((1280, 640)))


def test_build_and_command(brand, tmp_path, monkeypatch, capsys):
    def run(command, check, timeout):
        target = next(part for part in command if part.startswith("--screenshot=")).split("=", 1)[1]
        width, height = (int(v) for v in next(part for part in command if part.startswith("--window-size=")).split("=", 1)[1].split(","))
        scale = int(next(part for part in command if part.startswith("--force-device-scale-factor=")).split("=", 1)[1])
        Image.new("RGB", (width * scale, height * scale)).save(target)

    made = brand.build(("social",), tmp_path / "one", "browser", run=run)
    assert [path.name for path in made] == ["03_github-social-preview_1280x640.png", "03_github-social-preview@2x.png"]
    monkeypatch.setattr(brand.subprocess, "run", run)
    assert brand.main(["--out", str(tmp_path / "all"), "--browser", "browser"]) == 0
    out = capsys.readouterr().out
    assert out.count("drew   ") == 4 and "02_concept-image_keyvisual@2x.png  (3840x2160)" in out
    monkeypatch.setattr(brand, "find_browser", lambda: None)
    monkeypatch.delenv("STREAM2CLIP_BROWSER", raising=False)
    with pytest.raises(FileNotFoundError, match="needs Chrome or Edge"):
        brand.build(("social",), tmp_path / "x")
