from __future__ import annotations

import json

import numpy as np
from PIL import Image

from stream2clip.editor import (
    Arrow,
    ColorKey,
    Document,
    EditState,
    Highlighter,
    Mosaic,
    Pen,
    Rectangle,
    Text,
    Transparent,
    render,
    render_overlay,
    shape_bounds,
    state_from_dict,
    state_to_dict,
)
from stream2clip.geometry import Region


def checker(w: int = 120, h: int = 80) -> Image.Image:
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    yy, xx = np.mgrid[0:h, 0:w]
    arr[((xx // 4 + yy // 4) % 2) == 0] = (255, 255, 255)
    return Image.fromarray(arr, "RGB")


def px(img: Image.Image, x: int, y: int) -> tuple[int, int, int, int]:
    return img.getpixel((x, y))  # type: ignore[return-value]


def test_pen_draws_color():
    base = Image.new("RGB", (60, 60), "white")
    out = render(base, EditState(items=(Pen(((10, 30), (50, 30)), color="#FF0000", width=6),)))
    r, g, b, a = px(out, 30, 30)
    assert r > 240 and g < 20 and b < 20 and a == 255
    assert px(out, 30, 10) == (255, 255, 255, 255)


def test_highlighter_is_translucent():
    base = Image.new("RGB", (60, 60), "white")
    out = render(base, EditState(items=(Highlighter(((5, 30), (55, 30)), color="#0000FF", width=10, opacity=0.5),)))
    r, g, b, _ = px(out, 30, 30)
    assert 100 < r < 160 and b == 255


def test_rectangle_outline_and_fill():
    base = Image.new("RGB", (60, 60), "white")
    out = render(base, EditState(items=(Rectangle(Region(10, 10, 40, 40), color="#000000", width=2, fill="#00FF00"),)))
    assert px(out, 10, 30)[:3] == (0, 0, 0)
    assert px(out, 30, 30)[:3] == (0, 255, 0)
    assert px(out, 5, 5)[:3] == (255, 255, 255)


def test_arrow_head_is_at_end():
    base = Image.new("RGB", (100, 60), "white")
    out = render(base, EditState(items=(Arrow((10, 30), (90, 30), color="#0000FF", width=4),)))
    assert px(out, 86, 30)[2] > 200 and px(out, 86, 30)[0] < 60
    assert px(out, 80, 27)[0] < 120  # head is wider than the shaft (shaft covers y=28..32)
    assert px(out, 40, 27)[0] > 200


def test_text_renders_cjk():
    base = Image.new("RGB", (200, 60), "white")
    shape = Text((5, 5), "버튜버 클립", color="#000000", size=24, background="#FFFF00")
    out = render(base, EditState(items=(shape,)))
    bounds = shape_bounds(shape)
    assert bounds is not None and bounds.width > 60
    dark = np.asarray(out.crop(bounds.as_box()).convert("L")) < 100
    assert dark.sum() > 50
    assert px(out, bounds.x + 2, bounds.y + 2)[:3] == (255, 255, 0)


def test_mosaic_pixelates_region_only():
    base = checker()
    out = render(base, EditState(items=(Mosaic(Region(0, 0, 40, 40), block=10),)))
    patch = np.asarray(out.crop((0, 0, 10, 10)))
    assert (patch == patch[0, 0]).all()
    assert px(out, 60, 60) == px(base.convert("RGBA"), 60, 60)


def test_transparent_region_and_colorkey():
    base = Image.new("RGB", (40, 40), (0, 255, 0))
    base.paste((255, 0, 0), (10, 10, 30, 30))
    out = render(base, EditState(items=(ColorKey("#00FF00", similarity=0.1),)))
    assert px(out, 2, 2)[3] == 0 and px(out, 20, 20)[3] == 255
    out = render(base, EditState(items=(Transparent(Region(10, 10, 5, 5)),)))
    assert px(out, 12, 12)[3] == 0 and px(out, 20, 20)[3] == 255


def test_crop_applies_last():
    base = Image.new("RGB", (100, 50), "white")
    out = render(base, EditState(items=(Pen(((0, 0), (99, 49))),), crop=Region(10, 5, 30, 20)))
    assert out.size == (30, 20)


def test_serialization_roundtrip():
    state = EditState(
        items=(
            Pen(((1, 2), (3.5, 4))),
            Highlighter(((0, 0), (10, 10)), opacity=0.3),
            Rectangle(Region(1, 2, 3, 4), fill="#00000080"),
            Arrow((0, 0), (5, 5)),
            Text((3, 3), "テスト", size=20, background="#FFFFFF"),
            Mosaic(Region(0, 0, 10, 10), block=4),
            Transparent(Region(0, 0, 2, 2)),
            ColorKey("#00FF00", 0.2, 0.1),
        ),
        crop=Region(0, 0, 50, 50),
    )
    data = json.loads(json.dumps(state_to_dict(state, (100, 100))))
    assert data["schema"] == "stream2clip.annotation/v1"
    assert state_from_dict(data) == state


def test_document_undo_redo_dirty_and_save(tmp_path):
    doc = Document(Image.new("RGB", (50, 50), "white"))
    assert doc.dirty and not doc.can_undo
    doc.add(Rectangle(Region(5, 5, 10, 10)))
    doc.add(Pen(((0, 0), (10, 10))))
    assert len(doc.state.items) == 2
    doc.undo()
    assert len(doc.state.items) == 1 and doc.can_redo
    doc.redo()
    assert len(doc.state.items) == 2
    doc.save(tmp_path / "a.png")
    assert not doc.dirty
    doc.move(0, 5, 5)
    assert doc.state.items[0].rect == Region(10, 10, 10, 10) and doc.dirty
    jpg = doc.save(tmp_path / "a.jpg")
    assert Image.open(jpg).mode == "RGB"


def test_hit_test_prefers_topmost():
    doc = Document(Image.new("RGB", (50, 50)))
    doc.add(Rectangle(Region(0, 0, 40, 40)))
    doc.add(Rectangle(Region(10, 10, 10, 10)))
    assert doc.hit_test(15, 15) == 1
    assert doc.hit_test(35, 35) == 0
    assert doc.hit_test(49, 49) is None


def test_overlay_only_contains_annotations():
    base = Image.new("RGB", (50, 50), "white")
    state = EditState(items=(Pen(((5, 25), (45, 25)), color="#FF0000"), Transparent(Region(0, 0, 5, 5))))
    overlay = render_overlay(base.size, state, base=base)
    assert px(overlay, 25, 25)[3] == 255 and px(overlay, 25, 5)[3] == 0


def test_serialized_documents_match_json_schema():
    jsonschema = __import__("pytest").importorskip("jsonschema")
    from importlib.resources import files

    schema = json.loads(files("stream2clip").joinpath("schemas/annotation.v1.schema.json").read_text(encoding="utf-8"))
    state = EditState(
        items=(
            Pen(((1, 2), (3.5, 4))),
            Highlighter(((0, 0), (10, 10))),
            Rectangle(Region(1, 2, 3, 4), fill="#00000080"),
            Arrow((0, 0), (5, 5)),
            Text((3, 3), "テスト", background="#FFFFFF"),
            Mosaic(Region(0, 0, 10, 10)),
            Transparent(Region(0, 0, 2, 2)),
            ColorKey("#00FF00"),
        ),
        crop=Region(0, 0, 50, 50),
    )
    jsonschema.validate(state_to_dict(state, (100, 100)), schema)
    with __import__("pytest").raises(jsonschema.ValidationError):
        jsonschema.validate({"items": [{"type": "pen"}]}, schema)
