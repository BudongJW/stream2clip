"""GUI tests. Run headless with QT_QPA_PLATFORM=offscreen (set automatically here)."""

from __future__ import annotations

import os
import sys

import pytest

pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image  # noqa: E402
from PySide6.QtCore import QPoint, QRect, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from stream2clip.editor import ColorKey, Document, Mosaic, Pen, Rectangle  # noqa: E402
from stream2clip.geometry import Region  # noqa: E402
from stream2clip.gui.app import create_app  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return create_app([])


@pytest.fixture
def editor(app, tmp_path):
    from stream2clip.gui.editor import EditorWindow

    img = Image.new("RGB", (400, 300), "#334455")
    img.paste((0, 255, 0), (300, 0, 400, 100))
    win = EditorWindow(Document(img), save_dir=tmp_path)
    win.canvas.set_zoom(1.0)
    win.show()
    app.processEvents()
    yield win
    win._force_close = True
    win.close()


def drag(widget, a, b, steps=5):
    QTest.mousePress(widget, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(*a))
    for i in range(1, steps + 1):
        QTest.mouseMove(widget, QPoint(a[0] + (b[0] - a[0]) * i // steps, a[1] + (b[1] - a[1]) * i // steps))
    QTest.mouseRelease(widget, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(*b))


def test_toolbar_matches_reference(editor):
    labels = [b.text() for b in editor.tool_buttons.values()]
    assert labels == ["선택", "펜", "형광펜", "네모", "화살표", "글자", "모자이크", "투명", "자르기"]
    assert len(editor.swatches) == 8
    assert editor.translate_btn.text() == "번역 (한국어)"
    assert editor.status_label.text() == "400 × 300 px · 저장 안 됨"


def test_draw_undo_save(editor, tmp_path):
    c = editor.canvas
    editor._select_tool("pen")
    drag(c, (10, 10), (100, 60))
    editor._select_tool("rect")
    drag(c, (120, 120), (220, 200))
    items = editor.doc.state.items
    assert isinstance(items[0], Pen) and len(items[0].points) > 2
    assert isinstance(items[1], Rectangle) and items[1].rect == Region(120, 120, 100, 80)
    editor.undo()
    assert len(editor.doc.state.items) == 1
    editor.redo()
    out = tmp_path / "shot.png"
    assert editor.save_to(out)
    assert Image.open(out).size == (400, 300)
    assert editor.status_label.text().endswith("저장됨")


def test_mosaic_transparent_crop(editor):
    c = editor.canvas
    editor._select_tool("mosaic")
    drag(c, (10, 150), (110, 250))
    assert isinstance(editor.doc.state.items[-1], Mosaic)
    editor._select_tool("transparent")
    QTest.mouseClick(c, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(350, 50))
    key = editor.doc.state.items[-1]
    assert isinstance(key, ColorKey) and key.color == "#00FF00"
    assert editor.doc.render().getpixel((350, 50))[3] == 0
    editor._select_tool("crop")
    drag(c, (50, 40), (250, 140))
    assert editor.doc.state.crop == Region(50, 40, 200, 100)
    assert editor.status_label.text().startswith("200 × 100 px")


def test_select_move_delete(editor):
    c = editor.canvas
    editor._select_tool("rect")
    drag(c, (20, 20), (80, 80))
    editor._select_tool("select")
    drag(c, (50, 50), (150, 70))
    assert editor.doc.state.items[0].rect == Region(120, 40, 60, 60)
    c.delete_selected()
    assert editor.doc.state.items == ()


def test_eyedropper_sets_color(editor):
    editor.picker_btn.setChecked(True)
    QTest.mouseClick(editor.canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(350, 50))
    assert editor.tools.color == "#00FF00" and not editor.picker_btn.isChecked()


def test_selector_maps_to_physical_pixels(app):
    from stream2clip.gui.selector import ScreenSelector

    sel = ScreenSelector("region", screenshot=Image.new("RGB", (100, 100), "red"), physical=Region(0, 0, 100, 100))
    got = []
    sel.regionSelected.connect(lambda region, image, rect: got.append((region, image.size)))
    sel._sx = sel._sy = 2.0  # pretend a 200% HiDPI screen
    sel._emit_region(QRect(5, 10, 20, 15))
    assert got and got[0][0] == Region(10, 20, 40, 30) and got[0][1] == (40, 30)


def test_recording_frame_never_covers_region(app):
    from stream2clip.gui.recording import RecordingFrame

    rect = QRect(100, 100, 300, 200)
    frame = RecordingFrame(rect)
    assert all(not strip.geometry().intersects(rect) for strip in frame.strips)
    frame.close()


def test_record_settings_mp4_has_no_alpha():
    from stream2clip.gui.recording import RecordSettings

    assert RecordSettings(format="mp4", transparent=True).export_options().transparent is False
    assert RecordSettings(format="webp", transparent=True).export_options().transparent is True


def test_launcher_builds(app):
    from stream2clip.gui.launcher import LauncherWindow

    win = LauncherWindow()
    win._set_format("mp4")
    assert not win.transparent_check.isEnabled()
    win._set_format("gif")
    assert win.transparent_check.isEnabled()
    win.close()
