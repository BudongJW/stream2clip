"""The mascot's pictures are built from their masters: background removed, edge cleaned, every size made the same way."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

ROOT = Path(__file__).parents[1]
GREEN, LAVENDER, WHITE = (0, 255, 0), (205, 195, 235), (255, 255, 255)


@pytest.fixture(scope="module")
def mascot():
    spec = importlib.util.spec_from_file_location("build_mascot", ROOT / "packaging" / "build_mascot.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def character(size: int = 256, *, ring: bool = False) -> Image.Image:
    """A pink head with a black outline and white eyes on a transparent canvas, drawn with soft edges.

    With ``ring`` an arm closes off a gap: a loop whose inside is background.
    """
    big = size * 4
    canvas = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.ellipse((big * 0.2, big * 0.15, big * 0.8, big * 0.75), fill=(20, 18, 28, 255))
    draw.ellipse((big * 0.23, big * 0.18, big * 0.77, big * 0.72), fill=(255, 79, 139, 255))
    for x in (0.38, 0.62):
        draw.ellipse((big * (x - 0.05), big * 0.38, big * (x + 0.05), big * 0.48), fill=(255, 255, 255, 255))
    draw.rectangle((big * 0.3, big * 0.7, big * 0.7, big), fill=(250, 246, 232, 255))  # a cream hoodie that runs out of the picture
    if ring:
        draw.ellipse((big * 0.02, big * 0.5, big * 0.3, big * 0.8), outline=(20, 18, 28, 255), width=big // 40)
    return canvas.resize((size, size), Image.Resampling.LANCZOS)


def on(colour: tuple[int, int, int], picture: Image.Image) -> Image.Image:
    flat = Image.new("RGBA", picture.size, colour + (255,))
    flat.alpha_composite(picture)
    return flat.convert("RGB")


def alpha(picture: Image.Image) -> np.ndarray:
    return np.asarray(picture.convert("RGBA"))[..., 3] / 255.0


# ----------------------------------------------------------------------------- the edge


def test_a_halo_of_background_in_the_rim_is_recoloured_from_the_character(mascot):
    truth = character()
    # A cut-out as a careless tool leaves it: the right transparency, but lavender still mixed into the rim.
    mixed = np.asarray(on(LAVENDER, truth)).astype(np.uint8)
    dirty = Image.fromarray(np.dstack([mixed, np.asarray(truth)[..., 3]]), "RGBA")
    assert mascot.fringe(dirty) > 0.1
    clean = mascot.clean_edge(dirty)
    assert mascot.fringe(clean) < 0.02
    pixels = np.asarray(clean).astype(float)
    rim = (pixels[..., 3] > 20) & (pixels[..., 3] < 235) & (np.arange(256)[:, None] < 150)  # the outline's rim, above the hoodie
    assert rim.sum() > 100 and pixels[rim][:, :3].mean() < 60  # dark like the outline beside it, no longer lavender
    solid = np.asarray(truth)[..., 3] == 255
    assert np.array_equal(np.asarray(clean)[solid], np.asarray(dirty)[solid])  # the character itself is not touched
    assert (pixels[pixels[..., 3] == 0][:, :3] == 0).all()  # nothing is hidden in fully transparent pixels
    assert alpha(clean)[alpha(dirty) < mascot.FAINT].max() == 0  # the faintest haze is dropped
    empty = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    assert np.array_equal(np.asarray(mascot.clean_edge(empty)), np.asarray(empty))


def test_shrinking_draws_the_shape_in_but_not_at_the_frame(mascot):
    truth = character()
    before, after = alpha(truth), alpha(mascot.clean_edge(truth, shrink=2))
    assert (after > 0.5).sum() < (before > 0.5).sum() - 500  # two pixels off all round
    assert after[-1, 100:156].min() == 1.0  # the hoodie still fills the bottom row: the frame is no edge
    line = np.zeros((9, 9))
    line[4] = 1.0
    assert mascot.shrunk(line, 1).max() == 0 and np.array_equal(mascot.shrunk(line, 0), line)
    assert mascot.shrunk(np.ones((5, 5)), 3).min() == 1.0


def test_bleed_reaches_only_so_far(mascot):
    rgb = np.zeros((1, 12, 3))
    rgb[0, 0] = (200, 100, 50)
    known = np.zeros((1, 12), dtype=bool)
    known[0, 0] = True
    filled = mascot.bleed(rgb, known, reach=5)
    assert np.allclose(filled[0, 5], (200, 100, 50)) and np.allclose(filled[0, 6], 0)


# ----------------------------------------------------------------------------- the background


def test_a_plain_background_is_removed_from_the_frame_inwards(mascot):
    truth = character()
    for colour in (GREEN, (0, 71, 255)):
        master = on(colour, truth)
        assert mascot.border_colour(master) == colour
        cut = mascot.cut_out(master)
        assert np.abs(alpha(cut) - alpha(truth)).mean() < 0.01
        assert mascot.fringe(cut) < 0.03  # the background's share is taken out of the mixed pixels
        assert alpha(cut)[alpha(truth) == 1].min() == 1.0
    # A background in a colour of the character that reaches the frame (cream behind the cream hoodie)
    # takes that part with it: why a master is made on a colour the character does not have.
    hoodie = (slice(200, 256), slice(100, 156))
    assert alpha(mascot.cut_out(on((250, 246, 232), truth)))[hoodie].max() == 0.0
    assert alpha(mascot.cut_out(on(LAVENDER, truth)))[hoodie].min() == 1.0  # far enough from cream to be told apart


def test_white_eyes_stay_on_a_white_background_but_a_named_colour_goes_everywhere(mascot):
    truth = character(ring=True)
    eyes = (slice(100, 118), slice(92, 104))
    white = mascot.cut_out(on(WHITE, truth))
    assert alpha(white)[eyes].min() == 1.0  # the same colour as the background, but not connected to it
    assert mascot.background_clash(on(WHITE, truth)) > 0.01  # ... which is reported: such a master is a risk
    green = on(GREEN, truth)
    inside_the_loop = (slice(160, 172), slice(36, 48))
    assert mascot.background_clash(green) > 0.003  # the gap the arm closes off looks like an island too
    assert alpha(mascot.cut_out(green))[inside_the_loop].min() == 1.0  # from the frame inwards the gap stays filled
    assert alpha(mascot.cut_out(green, "#00FF00"))[inside_the_loop].max() == 0.0  # naming the colour clears it
    assert alpha(mascot.cut_out(green, "#00FF00"))[eyes].min() == 1.0
    assert mascot.background_clash(on(GREEN, character())) == 0.0
    with pytest.raises(ValueError, match="auto, transparent or #RRGGBB"):
        mascot.cut_out(green, "green")


def test_a_picture_that_is_already_cut_out_keeps_its_shape(mascot):
    truth = character()
    assert mascot.has_transparency(truth) and not mascot.has_transparency(on(GREEN, truth)) and not mascot.has_transparency(truth.convert("RGB"))
    kept = mascot.cut_out(truth)
    assert np.abs(alpha(kept) - alpha(truth)).mean() < 0.01
    assert np.array_equal(np.asarray(mascot.cut_out(truth, "transparent")), np.asarray(kept))


# ----------------------------------------------------------------------------- sizes


def test_scaling_weights_colours_by_their_transparency(mascot):
    truth = mascot.clean_edge(character())
    small = mascot.scaled(truth, 56)
    assert small.size == (56, 56) and small.mode == "RGBA"
    pixels = np.asarray(small).astype(float)
    rim = (pixels[..., 3] > 30) & (pixels[..., 3] < 220) & (np.arange(56)[:, None] < 32)
    assert rim.sum() > 20 and pixels[rim][:, :3].mean() < 90  # the rim of the small picture is outline-dark: no pale or black fringe from empty pixels
    assert np.asarray(small)[28, 28].tolist() == [255, 79, 139, 255]
    same = mascot.scaled(truth, 256)
    assert np.array_equal(np.asarray(same), np.asarray(truth)) and same is not truth


# ----------------------------------------------------------------------------- files


@pytest.fixture
def workshop(mascot, tmp_path):
    """A source folder with two masters (one cut out, one on green), and empty places for what is built."""
    source = tmp_path / "source"
    source.mkdir()
    character(256).save(source / "kiri_wink.png")
    on(GREEN, character(256, ring=True)).save(source / "kiri_cut.png")
    manifest = {
        "character": "kiri", "sizes": [128, 56, 28], "app_sizes": [56],
        "emotes": {"wink": {"file": "kiri_wink.png", "background": "transparent"}, "cut": {"file": "kiri_cut.png", "background": "#00FF00", "shrink": 1}},
    }
    (source / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return source, tmp_path / "out", tmp_path / "app"


def test_every_size_is_built_and_the_app_gets_its_copies(mascot, workshop):
    source, out, app = workshop
    written = mascot.build(source, out, app)
    assert sorted(p.name for p in out.iterdir()) == ["kiri_cut_128.png", "kiri_cut_28.png", "kiri_cut_56.png", "kiri_wink_128.png", "kiri_wink_28.png", "kiri_wink_56.png"]
    assert sorted(p.name for p in app.iterdir()) == ["kiri_cut_56.png", "kiri_wink_56.png"] and len(written) == 8
    assert (out / "kiri_wink_56.png").read_bytes() == (app / "kiri_wink_56.png").read_bytes()
    assert Image.open(out / "kiri_cut_128.png").size == (128, 128) and alpha(Image.open(out / "kiri_cut_128.png"))[0, 0] == 0  # the green is gone
    assert mascot.stale(source, out, app) == []

    Image.new("RGBA", (56, 56), (255, 0, 0, 255)).save(app / "kiri_wink_56.png")  # edited by hand
    (out / "kiri_cut_28.png").unlink()
    assert sorted(p.name for p in mascot.stale(source, out, app)) == ["kiri_cut_28.png", "kiri_wink_56.png"]
    mascot.build(source, out, app)
    assert mascot.stale(source, out, app) == []
    assert mascot.build(source, out, app=None) and len(mascot.targets(source, out, None)) == 6
    one = Image.open(out / "kiri_wink_56.png")
    nudged = Image.fromarray(np.clip(np.asarray(one).astype(int) + 2, 0, 255).astype(np.uint8), "RGBA")
    assert mascot.same_picture(one, nudged) and not mascot.same_picture(one, one.resize((28, 28)))  # rounding is not a change, another picture is
    assert not mascot.same_picture(one, Image.fromarray(np.clip(np.asarray(one).astype(int) + 9, 0, 255).astype(np.uint8), "RGBA"))

    page = mascot.sheet(mascot.render(source), 56)
    assert page.size == (112, 112) and page.getpixel((0, 0)) == mascot.INK and page.getpixel((0, 111 - 55)) == mascot.PAPER
    with pytest.raises(ValueError, match="no emote of 99 px"):
        mascot.sheet(mascot.render(source), 99)


def test_masters_that_cannot_be_used_are_refused(mascot, workshop):
    source, _, _ = workshop
    data = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    character(64).save(source / "kiri_wink.png")
    with pytest.raises(ValueError, match="at least 128 px"):
        mascot.render(source)
    Image.new("RGBA", (256, 200)).save(source / "kiri_wink.png")
    with pytest.raises(ValueError, match="a master is square"):
        mascot.render(source)
    (source / "kiri_wink.png").unlink()
    with pytest.raises(FileNotFoundError, match="the master of 'wink' is missing"):
        mascot.load_manifest(source)
    (source / "manifest.json").write_text(json.dumps({**data, "app_sizes": [64]}), encoding="utf-8")
    with pytest.raises(ValueError, match="app_sizes must be among sizes"):
        mascot.load_manifest(source)
    (source / "manifest.json").write_text(json.dumps({"character": "kiri"}), encoding="utf-8")
    with pytest.raises(ValueError, match="missing 'sizes'"):
        mascot.load_manifest(source)


def test_a_new_master_is_taken_in_with_how_it_was_made(mascot, workshop, tmp_path):
    source, out, app = workshop
    fresh = tmp_path / "shy.png"
    on(GREEN, character(256)).save(fresh)
    target = mascot.add_master("shy", fresh, source=source, generator="some model", prompt="kiri, shy", seed="42")
    entry = json.loads((source / "manifest.json").read_text(encoding="utf-8"))["emotes"]["shy"]
    assert target == source / "kiri_shy.png" and entry == {"file": "kiri_shy.png", "background": "auto", "generator": "some model", "prompt": "kiri, shy", "seed": "42"}
    mascot.build(source, out, app)
    assert (out / "kiri_shy_128.png").is_file() and (app / "kiri_shy_56.png").is_file()

    with pytest.raises(ValueError, match="already an emote"):
        mascot.add_master("shy", fresh, source=source)
    with pytest.raises(ValueError, match="lower-case letters"):
        mascot.add_master("Shy Face", fresh, source=source)
    small = tmp_path / "small.png"
    character(64).save(small)
    with pytest.raises(ValueError, match="square and at least 128 px"):
        mascot.add_master("tiny", small, source=source)

    # White behind white eyes: refused unless the colour is named, another one is used, or it is forced.
    risky = tmp_path / "risky.png"
    on(WHITE, character(256)).save(risky)
    with pytest.raises(ValueError, match="#FFFFFF also fills .* --background #FFFFFF"):
        mascot.add_master("risky", risky, source=source)
    assert "risky" not in json.loads((source / "manifest.json").read_text(encoding="utf-8"))["emotes"] and not (source / "kiri_risky.png").exists()
    assert mascot.add_master("risky", risky, source=source, force=True).is_file()
    looped = tmp_path / "looped.png"
    on(GREEN, character(256, ring=True)).save(looped)
    with pytest.raises(ValueError, match="--background #00FF00"):
        mascot.add_master("looped", looped, source=source)
    assert mascot.add_master("looped", looped, source=source, background="#00FF00").is_file()


# ----------------------------------------------------------------------------- the project's own files


def test_the_projects_mascot_files_are_what_their_masters_give(mascot):
    data = mascot.load_manifest()
    assert data["character"] == "kiri" and data["sizes"] == [512, 112, 56, 28] and data["app_sizes"] == [112, 56]
    from stream2clip.gui import qt

    assert set(data["emotes"]) == set(qt.MOODS)  # every mood the app shows has a master, and nothing else is built
    for entry in data["emotes"].values():
        assert entry["generator"] and "prompt" in entry and "seed" in entry  # how a picture was made stays with it
    assert mascot.stale() == [], "run: python packaging/build_mascot.py"
    for name in data["emotes"]:
        assert mascot.fringe(Image.open(mascot.MASCOT / f"kiri_{name}_512.png")) < 0.02
        for size in data["app_sizes"]:
            file = f"kiri_{name}_{size}.png"
            assert (mascot.MASCOT / file).read_bytes() == (mascot.APP_ASSETS / file).read_bytes()


def test_command_checks_and_builds(mascot, workshop, monkeypatch, capsys, tmp_path):
    source, out, app = workshop
    monkeypatch.setattr(mascot, "SOURCE", source)
    monkeypatch.setattr(mascot, "MASCOT", out)
    monkeypatch.setattr(mascot, "APP_ASSETS", app)
    monkeypatch.setattr(mascot, "ROOT", tmp_path)
    for name in ("build", "stale", "render", "targets", "load_manifest", "add_master"):  # the defaults were bound when the module was loaded
        function = getattr(mascot, name)
        defaults = tuple({mascot_default: new for mascot_default, new in ((ROOT / "assets" / "brand" / "mascot" / "source", source), (ROOT / "assets" / "brand" / "mascot", out), (ROOT / "src" / "stream2clip" / "gui" / "assets", app))}.get(value, value) for value in (function.__defaults__ or ()))
        monkeypatch.setattr(function, "__defaults__", defaults)
        if function.__kwdefaults__:
            monkeypatch.setattr(function, "__kwdefaults__", {key: (source if value == ROOT / "assets" / "brand" / "mascot" / "source" else value) for key, value in function.__kwdefaults__.items()})
    assert mascot.main(["--check"]) == 1
    assert "stale  out" in capsys.readouterr().out.replace("\\", "/")
    assert mascot.main(["--sheet", str(tmp_path / "sheet.png"), "--sheet-size", "56"]) == 0
    assert "built  8 files from 2 masters" in capsys.readouterr().out and Image.open(tmp_path / "sheet.png").size == (112, 112)
    assert mascot.main(["--check"]) == 0
    fresh = tmp_path / "wave.png"
    on(GREEN, character(256)).save(fresh)
    assert mascot.main(["--add", "wave", str(fresh), "--generator", "some model", "--seed", "7"]) == 0
    assert "added  source/kiri_wave.png" in capsys.readouterr().out.replace("\\", "/") and (out / "kiri_wave_128.png").is_file()
