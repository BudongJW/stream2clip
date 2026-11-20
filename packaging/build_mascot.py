"""Turn the mascot's master pictures into the files the app, the site and the README use.

    python packaging/build_mascot.py                     rebuild everything from assets/brand/mascot/source
    python packaging/build_mascot.py --check             fail when a built file is not what its master gives
    python packaging/build_mascot.py --sheet sheet.png   all emotes on a dark and a light background, to look at
    python packaging/build_mascot.py --add shy shy.png   take a new master in (see --background)

A master is one picture of the character per emote, as it came out of an image generator: on a
plain background, or already cut out. The same steps are applied to each, so a new emote looks
like the others:

1. the background is removed - a plain colour is keyed out from the border inwards, so a part of
   the character that has the same colour (a white hoodie on white) stays;
2. the edge is cleaned: half-transparent pixels take the colour of the character next to them
   instead of the background they were mixed with, which is what shows as a pale halo on a dark
   window, and the faintest of them are dropped;
3. the picture is scaled to each size with its transparency taken into account;
4. the sizes the app shows are copied into the package.

``source/manifest.json`` lists the emotes and how each master was made (generator, prompt, seed),
so that a picture can be made again or continued. Only numpy and Pillow are used; nothing is
downloaded and no model runs here - generating the masters is done wherever a GPU is.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
MASCOT = ROOT / "assets" / "brand" / "mascot"
SOURCE = MASCOT / "source"
APP_ASSETS = ROOT / "src" / "stream2clip" / "gui" / "assets"
MANIFEST = "manifest.json"
INK, PAPER = (21, 19, 31), (247, 244, 250)

#: Alpha from which a pixel's own colour is trusted, and below which a pixel is dropped.
SOLID, FAINT = 0.92, 0.10


# --------------------------------------------------------------------------- pixels


def _neighbours(values: np.ndarray, known: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Sum of the known neighbours' values and how many there are, for every pixel (8 neighbours)."""
    height, width = known.shape
    padded_values = np.pad(values * known[..., None], ((1, 1), (1, 1), (0, 0)))
    padded_known = np.pad(known.astype(np.float64), 1)
    total = np.zeros_like(values)
    count = np.zeros((height, width))
    for dy in (0, 1, 2):
        for dx in (0, 1, 2):
            if dy == 1 and dx == 1:
                continue
            total += padded_values[dy:dy + height, dx:dx + width]
            count += padded_known[dy:dy + height, dx:dx + width]
    return total, count


def bleed(rgb: np.ndarray, known: np.ndarray, *, reach: int = 8) -> np.ndarray:
    """Give every pixel that is not ``known`` the colour of the known pixels nearest to it, up to ``reach`` pixels away."""
    colours = rgb.astype(np.float64).copy()
    known = known.copy()
    for _ in range(reach):
        if known.all():
            break
        total, count = _neighbours(colours, known)
        fresh = ~known & (count > 0)
        if not fresh.any():
            break
        colours[fresh] = total[fresh] / count[fresh][:, None]
        known |= fresh
    return colours


def shrunk(alpha: np.ndarray, pixels: int) -> np.ndarray:
    """``alpha`` with the shape drawn in by ``pixels`` (the lowest value among each pixel's neighbours).

    The frame of the picture does not count as an edge: a bust that runs out of the picture at the bottom stays whole there.
    """
    height, width = alpha.shape
    for _ in range(max(0, pixels)):
        padded = np.pad(alpha, 1, constant_values=1.0)
        alpha = np.min([padded[dy:dy + height, dx:dx + width] for dy in (0, 1, 2) for dx in (0, 1, 2)], axis=0)
    return alpha


def clean_edge(image: Image.Image, *, solid: float = SOLID, faint: float = FAINT, shrink: int = 0) -> Image.Image:
    """Recolour the half-transparent rim from the character's own pixels and drop its faintest part.

    A cut-out keeps a trace of the background in the pixels along its edge; on a window of
    another colour that trace is a halo. The rim's transparency is kept, only what shows through
    it changes - so an outline stays as smooth as it was. ``shrink`` first draws the shape in by
    that many pixels: for a cut-out whose outermost opaque pixels are background too.
    """
    pixels = np.asarray(image.convert("RGBA")).astype(np.float64)
    alpha = shrunk(pixels[..., 3] / 255.0, shrink)
    trusted = alpha >= solid
    if not trusted.any():
        return image.convert("RGBA")
    colours = bleed(pixels[..., :3], trusted)
    kept = np.clip((alpha - faint) / (solid - faint), 0.0, 1.0)
    out = np.dstack([np.where(trusted[..., None], pixels[..., :3], colours), kept * 255.0])
    out[kept <= 0, :3] = 0
    return Image.fromarray(np.clip(np.rint(out), 0, 255).astype(np.uint8), "RGBA")


def border_colour(image: Image.Image, *, ring: int = 4) -> tuple[int, int, int]:
    """The colour of a picture's frame: the median of a few pixels along its four sides."""
    pixels = np.asarray(image.convert("RGB"))
    ring = max(1, min(ring, min(pixels.shape[:2]) // 2))
    frame = np.concatenate([pixels[:ring].reshape(-1, 3), pixels[-ring:].reshape(-1, 3), pixels[:, :ring].reshape(-1, 3), pixels[:, -ring:].reshape(-1, 3)])
    return tuple(int(v) for v in np.median(frame, axis=0))


def key_background(image: Image.Image, colour: tuple[int, int, int] | None = None, *, near: float = 0.06, far: float = 0.16, everywhere: bool = False) -> Image.Image:
    """Cut a character off a plain background.

    Pixels within ``near`` of the background colour (as a fraction of the distance from black
    to white) become transparent, pixels beyond ``far`` stay, and those between are partly
    transparent with the background taken out of their colour. Only what is connected to the
    frame is removed, so a part of the character in the background's colour stays opaque -
    unless ``everywhere`` is set: then the colour goes wherever it is, also from a gap the
    character closes off (between an arm and the body), which is right for a colour the
    character does not have.
    """
    rgb = np.asarray(image.convert("RGB")).astype(np.float64)
    back = np.array(colour if colour is not None else border_colour(image), dtype=np.float64)
    distance = np.sqrt(((rgb - back) ** 2).sum(axis=2)) / (255.0 * np.sqrt(3.0))
    like = distance < far
    # Flood from outside the picture through everything that looks like the background.
    mask = Image.fromarray(np.pad(like, 1, constant_values=True).astype(np.uint8) * 255, "L").copy()  # a copy: the array's own memory is read-only
    ImageDraw.floodfill(mask, (0, 0), 128)
    outside = like if everywhere else np.asarray(mask)[1:-1, 1:-1] == 128
    alpha = np.where(outside, np.clip((distance - near) / (far - near), 0.0, 1.0), 1.0)
    # What is left of a mixed pixel once the background's share is taken out of it.
    share = np.maximum(alpha, 1e-3)[..., None]
    front = np.clip((rgb - (1.0 - share) * back) / share, 0.0, 255.0)
    out = np.dstack([np.where((alpha > 0.5)[..., None], front, rgb), alpha * 255.0])
    return Image.fromarray(np.clip(np.rint(out), 0, 255).astype(np.uint8), "RGBA")


def background_clash(image: Image.Image, colour: tuple[int, int, int] | None = None, *, far: float = 0.16) -> float:
    """The share of a picture that has the background's colour without being background: islands the flood from the frame does not reach.

    Whites of the eyes on a white background, for example. Where there are such islands, parts of
    the character that do touch the background in that colour are cut away with it - the master
    should be made on a colour the character does not have (plain green is the usual choice).
    """
    rgb = np.asarray(image.convert("RGB")).astype(np.float64)
    back = np.array(colour if colour is not None else border_colour(image), dtype=np.float64)
    like = np.sqrt(((rgb - back) ** 2).sum(axis=2)) / (255.0 * np.sqrt(3.0)) < far
    mask = Image.fromarray(np.pad(like, 1, constant_values=True).astype(np.uint8) * 255, "L").copy()
    ImageDraw.floodfill(mask, (0, 0), 128)
    islands = like & (np.asarray(mask)[1:-1, 1:-1] != 128)
    return float(islands.mean())


def has_transparency(image: Image.Image) -> bool:
    return image.mode in ("RGBA", "LA", "PA") and np.asarray(image.convert("RGBA"))[..., 3].min() < 250


def cut_out(image: Image.Image, background: str = "auto", *, shrink: int = 0) -> Image.Image:
    """The character without its background.

    ``background``: ``auto`` (already cut out, or the frame's plain colour, removed from the frame
    inwards), ``transparent`` (leave the transparency as it is) or ``#RRGGBB`` - a colour the
    character does not have, removed wherever it is.
    """
    if background == "transparent" or (background == "auto" and has_transparency(image)):
        return clean_edge(image, shrink=shrink)
    colour = None
    if background != "auto":
        text = background.lstrip("#")
        if len(text) != 6:
            raise ValueError(f"background must be auto, transparent or #RRGGBB, not {background!r}")
        colour = tuple(int(text[i:i + 2], 16) for i in (0, 2, 4))
    return clean_edge(key_background(image, colour, everywhere=colour is not None), shrink=shrink)


def fringe(image: Image.Image, *, solid: float = SOLID) -> float:
    """How far the colour of the half-transparent rim is from the character next to it: 0 (the same) to 1.

    Weighted by how visible each rim pixel is. A cut-out with background left in its edge
    scores high; after :func:`clean_edge` the score is 0.
    """
    pixels = np.asarray(image.convert("RGBA")).astype(np.float64)
    alpha = pixels[..., 3] / 255.0
    trusted = alpha >= solid
    rim = (alpha > 0.02) & ~trusted
    if not trusted.any() or not rim.any():
        return 0.0
    beside = bleed(pixels[..., :3], trusted)
    apart = np.sqrt(((pixels[..., :3] - beside) ** 2).sum(axis=2)) / (255.0 * np.sqrt(3.0))
    return float((apart[rim] * alpha[rim]).sum() / alpha[rim].sum())


def scaled(image: Image.Image, size: int) -> Image.Image:
    """``image`` at ``size`` pixels square. Colours are weighted by their transparency, so nothing dark or pale creeps in at the edge."""
    if image.size == (size, size):
        return image.copy()
    pixels = np.asarray(image.convert("RGBA")).astype(np.float64) / 255.0
    weighted = np.dstack([pixels[..., :3] * pixels[..., 3:], pixels[..., 3]])
    bands = [Image.fromarray(weighted[..., i].astype(np.float32), "F").resize((size, size), Image.Resampling.LANCZOS) for i in range(4)]
    small = np.dstack([np.asarray(band, dtype=np.float64) for band in bands])
    alpha = np.clip(small[..., 3], 0.0, 1.0)
    colour = np.where(alpha[..., None] > 1e-4, small[..., :3] / np.maximum(alpha[..., None], 1e-4), 0.0)
    out = np.dstack([np.clip(colour, 0.0, 1.0), alpha]) * 255.0
    return Image.fromarray(np.clip(np.rint(out), 0, 255).astype(np.uint8), "RGBA")


# --------------------------------------------------------------------------- files


def load_manifest(source: Path = SOURCE) -> dict:
    data = json.loads((source / MANIFEST).read_text(encoding="utf-8"))
    for key in ("character", "sizes", "app_sizes", "emotes"):
        if key not in data:
            raise ValueError(f"{MANIFEST}: missing {key!r}")
    if not set(data["app_sizes"]) <= set(data["sizes"]):
        raise ValueError(f"{MANIFEST}: app_sizes must be among sizes")
    for name, entry in data["emotes"].items():
        if not (source / entry["file"]).is_file():
            raise FileNotFoundError(f"{MANIFEST}: the master of {name!r} is missing: {entry['file']}")
    return data


def render(source: Path = SOURCE) -> dict[str, Image.Image]:
    """Every file the masters give: name -> picture."""
    data = load_manifest(source)
    largest = max(data["sizes"])
    built: dict[str, Image.Image] = {}
    for name, entry in data["emotes"].items():
        master = Image.open(source / entry["file"])
        if master.width != master.height:
            raise ValueError(f"{entry['file']} is {master.width}x{master.height}: a master is square")
        if master.width < largest:
            raise ValueError(f"{entry['file']} is {master.width} px: a master is at least {largest} px")
        clean = cut_out(master, entry.get("background", "auto"), shrink=int(entry.get("shrink", 0)))
        for size in data["sizes"]:
            built[f"{data['character']}_{name}_{size}.png"] = scaled(clean, size)
    return built


def targets(source: Path = SOURCE, out: Path = MASCOT, app: Path | None = APP_ASSETS) -> dict[Path, str]:
    """Where each built file goes -> its name in :func:`render`."""
    data = load_manifest(source)
    places = {}
    for name in data["emotes"]:
        for size in data["sizes"]:
            file = f"{data['character']}_{name}_{size}.png"
            places[out / file] = file
            if app is not None and size in data["app_sizes"]:
                places[app / file] = file
    return places


def build(source: Path = SOURCE, out: Path = MASCOT, app: Path | None = APP_ASSETS) -> list[Path]:
    built = render(source)
    written = []
    for path, name in targets(source, out, app).items():
        path.parent.mkdir(parents=True, exist_ok=True)
        built[name].save(path, optimize=True)
        written.append(path)
    return written


def same_picture(one: Image.Image, other: Image.Image, *, tolerance: int = 3) -> bool:
    """Whether two pictures show the same thing: equal size, and no value further apart than ``tolerance`` of 255.

    Scaling rounds a little differently from one Pillow or processor to the next; a rebuilt file is not
    "changed" for that.
    """
    a, b = np.asarray(one.convert("RGBA")).astype(np.int16), np.asarray(other.convert("RGBA")).astype(np.int16)
    return a.shape == b.shape and int(np.abs(a - b).max()) <= tolerance


def stale(source: Path = SOURCE, out: Path = MASCOT, app: Path | None = APP_ASSETS) -> list[Path]:
    """Built files that are missing or do not show what their master gives (compared pixel by pixel)."""
    built = render(source)
    wrong = []
    for path, name in targets(source, out, app).items():
        if not path.is_file() or not same_picture(Image.open(path), built[name]):
            wrong.append(path)
    return wrong


def sheet(pictures: dict[str, Image.Image], size: int, *, backgrounds: tuple[tuple[int, int, int], ...] = (INK, PAPER)) -> Image.Image:
    """The emotes of one size side by side, once per background: what a person looks at before the files go out."""
    chosen = [picture for name, picture in pictures.items() if name.endswith(f"_{size}.png")]
    if not chosen:
        raise ValueError(f"no emote of {size} px")
    canvas = Image.new("RGB", (size * len(chosen), size * len(backgrounds)))
    for row, colour in enumerate(backgrounds):
        for column, picture in enumerate(chosen):
            tile = Image.new("RGBA", (size, size), colour + (255,))
            tile.alpha_composite(picture)
            canvas.paste(tile.convert("RGB"), (column * size, row * size))
    return canvas


#: Above this share of background-coloured islands a master is not taken in with ``background="auto"``.
CLASH_LIMIT = 0.003


def add_master(name: str, picture: Path, *, background: str = "auto", source: Path = SOURCE, force: bool = False, **record: str) -> Path:
    """Copy a new master in and list it in the manifest; ``record`` (generator, prompt, seed ...) is kept with it.

    With ``background="auto"`` a master whose background colour also shows inside the character
    is refused (``force`` takes it anyway): either the character has that colour and would lose
    parts, or it closes off gaps that stay filled - name the colour instead, or make the master on another.
    """
    if not name.isidentifier() or not name.islower():
        raise ValueError(f"an emote is named with lower-case letters, digits and _: {name!r}")
    data = json.loads((source / MANIFEST).read_text(encoding="utf-8"))
    if name in data["emotes"]:
        raise ValueError(f"{name!r} is already an emote: replace its master file instead")
    with Image.open(picture) as image:
        if image.width != image.height or image.width < max(data["sizes"]):
            raise ValueError(f"{picture.name} is {image.width}x{image.height}: a master is square and at least {max(data['sizes'])} px")
        if background == "auto" and not has_transparency(image) and not force:
            clash = background_clash(image)
            if clash > CLASH_LIMIT:
                colour = "#%02X%02X%02X" % border_colour(image)
                raise ValueError(
                    f"{picture.name}: its background colour {colour} also fills {clash:.1%} of the picture away from the frame. "
                    f"If the character does not have that colour, pass --background {colour} (gaps it closes off are cleared too); "
                    "if it does, make the master on a colour it does not have (plain green is usual). --force takes it as it is."
                )
    target = source / f"{data['character']}_{name}.png"
    shutil.copyfile(picture, target)
    data["emotes"][name] = {"file": target.name, "background": background, **{key: value for key, value in record.items() if value}}
    (source / MANIFEST).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="do not write: exit with 1 when a built file is missing or differs from what its master gives")
    parser.add_argument("--sheet", metavar="FILE", help="also save all emotes on a dark and a light background")
    parser.add_argument("--sheet-size", type=int, default=None, help="size of the emotes on the sheet (default: the largest)")
    parser.add_argument("--add", nargs=2, metavar=("NAME", "FILE"), help="take a new master in before building")
    parser.add_argument("--background", default="auto", help="--add: auto (default: already cut out, or the frame's plain colour), transparent, or the background's #RRGGBB")
    parser.add_argument("--generator", help="--add: what made the master")
    parser.add_argument("--prompt", help="--add: the prompt it was made with")
    parser.add_argument("--seed", help="--add: the seed it was made with")
    parser.add_argument("--force", action="store_true", help="--add: take a master whose background colour also shows inside the character")
    args = parser.parse_args(argv)

    if args.add:
        target = add_master(args.add[0], Path(args.add[1]), background=args.background, force=args.force, generator=args.generator, prompt=args.prompt, seed=args.seed)
        print(f"added  {target.relative_to(ROOT)}")
    if args.check:
        wrong = stale()
        for path in wrong:
            print(f"stale  {path.relative_to(ROOT)}")
        if wrong:
            print("run: python packaging/build_mascot.py")
        return 1 if wrong else 0
    written = build()
    print(f"built  {len(written)} files from {len(load_manifest()['emotes'])} masters")
    if args.sheet:
        size = args.sheet_size or max(load_manifest()["sizes"])
        sheet(render(), size).save(args.sheet)
        print(f"sheet  {args.sheet}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
