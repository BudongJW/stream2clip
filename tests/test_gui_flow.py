"""End-to-end desktop flow on a real (virtual) display: F8 capture and F9 transparent recording.

Runs only when a display is available, e.g. ``xvfb-run -a pytest tests/test_gui_flow.py``.
On Windows it opens windows in the top-left corner, presses F8/F9 for real and moves the
mouse cursor for a few seconds; set ``QT_QPA_PLATFORM=offscreen`` to skip it.
"""

from __future__ import annotations

import os
import shutil
import sys
import time

import pytest

pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
pytest.importorskip("mss")
if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
    pytest.skip("needs an X display (run under xvfb-run)", allow_module_level=True)
if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
    pytest.skip("needs a real Qt platform plugin", allow_module_level=True)
if shutil.which("ffmpeg") is None:
    pytest.skip("needs ffmpeg", allow_module_level=True)

from PIL import Image  # noqa: E402
from PySide6.QtCore import QElapsedTimer, QPoint, Qt, QTimer  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from stream2clip.geometry import Region, round_half_up  # noqa: E402
from stream2clip.gui.app import create_app  # noqa: E402
from stream2clip.gui.selector import ScreenSelector  # noqa: E402


def pump(app, ms):
    timer = QElapsedTimer()
    timer.start()
    while timer.elapsed() < ms:
        app.processEvents()
        time.sleep(0.005)


def visible_selector():
    return next((w for w in QApplication.topLevelWidgets() if isinstance(w, ScreenSelector) and w.isVisible()), None)


def test_capture_and_transparent_recording(tmp_path):
    app = create_app([])
    from stream2clip.gui.launcher import LauncherWindow

    bg = QLabel()
    # Always on top: Windows does not let a background process raise a new window over
    # the active one, and the capture would show whatever application was in front.
    bg.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
    bg.setStyleSheet("background:#15131F")
    bg.setGeometry(0, 0, 640, 480)
    bg.show()
    green = QLabel(bg)
    green.setStyleSheet("background:#00FF00")
    green.setGeometry(40, 40, 200, 120)
    green.show()
    dot = QLabel(green)
    dot.setStyleSheet("background:#FF4F8B")
    dot.setGeometry(0, 40, 30, 30)
    dot.show()
    anim = QTimer()
    anim.timeout.connect(lambda: dot.move((dot.x() + 6) % 170, 40))
    anim.start(40)

    launcher = LauncherWindow()
    launcher.settings.save_dir = tmp_path
    launcher.show()
    pump(app, 300)

    # F8: region capture opens an editor with exactly the selected pixels.
    launcher._on_hotkey("F8")
    pump(app, 700)
    sel = visible_selector()
    assert sel is not None
    QTest.mousePress(sel, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(40, 40))
    QTest.mouseMove(sel, QPoint(140, 100))
    QTest.mouseRelease(sel, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(239, 159))
    pump(app, 300)
    editor = launcher.editors[-1]
    # Physical pixels: 200 x 120 at 100%, 250 x 150 on a 125% display.
    scale = app.primaryScreen().devicePixelRatio()
    w, h = editor.doc.size
    assert (w, h) == (round_half_up(200 * scale), round_half_up(120 * scale))
    for corner in ((2, 2), (w - 3, 2), (2, h - 3), (w - 3, h - 3)):  # aligned on every side
        assert editor.doc.image.getpixel(corner)[:3] == (0, 255, 0)
    editor._force_close = True
    editor.close()

    # F9: select the green box, record, F9 again -> transparent GIF.
    launcher._set_format("gif")
    launcher.transparent_check.setChecked(True)
    launcher.settings.fps = 10.0
    result = {}
    launcher.controller.finished.connect(lambda p: result.setdefault("path", p))
    launcher.controller.failed.connect(lambda m: result.setdefault("error", m))
    launcher._on_hotkey("F9")
    pump(app, 700)
    sel = visible_selector()
    assert sel is not None
    QTest.mousePress(sel, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(40, 40))
    QTest.mouseRelease(sel, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(239, 159))
    pump(app, 1500)
    assert launcher.controller.state == "recording"
    launcher._on_hotkey("F9")
    deadline = time.time() + 30
    while not result and time.time() < deadline:
        pump(app, 100)
    assert "path" in result, result
    gif = Image.open(result["path"])
    assert gif.n_frames >= 5
    opaque_columns = []
    for index in range(gif.n_frames):
        gif.seek(index)
        frame = gif.convert("RGBA")
        w, h = frame.size
        assert frame.getpixel((w - 3, 3))[3] == 0  # green keyed out in every frame
        xs = [x for x in range(w) if frame.getpixel((x, h // 2))[3] == 255]
        if xs:
            opaque_columns.append(min(xs))
    assert len(set(opaque_columns)) > 2  # the dot moves and leaves no ghost
    launcher.close()
    bg.close()


# ---------------------------------------------------------------------------- Windows
# The checks below use Win32 directly so they do not depend on the code under test:
# keys are injected at OS level and window rectangles are read back in physical pixels.

_VK = {"F8": 0x77, "F9": 0x78}
_TOPMOST = Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool


def _press(key):
    import ctypes

    ctypes.windll.user32.keybd_event(_VK[key], 0, 0, 0)
    ctypes.windll.user32.keybd_event(_VK[key], 0, 2, 0)  # KEYEVENTF_KEYUP


def _window_region(widget) -> Region:
    import ctypes
    from ctypes import wintypes

    rect = wintypes.RECT()
    ctypes.windll.user32.GetWindowRect(wintypes.HWND(int(widget.winId())), ctypes.byref(rect))
    return Region(rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)


def _drag(selector, rect):
    QTest.mousePress(selector, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, rect.topLeft())
    QTest.mouseMove(selector, rect.center())
    QTest.mouseRelease(selector, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, rect.bottomRight())


@pytest.mark.skipif(sys.platform != "win32", reason="Win32 hotkeys, cursor and physical window rectangles")
def test_windows_global_hotkeys_scaling_border_and_cursor(tmp_path):
    import ctypes
    from ctypes import wintypes

    from PySide6.QtCore import QRect

    from stream2clip.gui.launcher import LauncherWindow

    user32 = ctypes.windll.user32
    app = create_app([])
    bg = QLabel()
    bg.setWindowFlags(_TOPMOST)
    bg.setStyleSheet("background:#15131F")
    bg.setGeometry(0, 0, 640, 480)
    bg.show()
    green = QLabel()
    green.setWindowFlags(_TOPMOST)
    green.setStyleSheet("background:#00FF00")
    green.show()

    launcher = LauncherWindow()
    launcher.settings.save_dir = tmp_path
    launcher.show()
    pump(app, 400)
    saved = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(saved))
    try:
        if launcher.hotkeys.backend != "win32" or sorted(launcher.hotkeys._names.values()) != ["F8", "F9"]:
            pytest.skip("F8/F9 are registered by another program")

        # F8 from anywhere -> selector. An even and an odd rectangle: at 125% the odd one
        # lands on fractional pixels and must still match the window's physical pixels.
        for rect in (QRect(40, 40, 200, 120), QRect(41, 43, 201, 119)):
            green.setGeometry(rect)
            green.raise_()
            pump(app, 300)
            _press("F8")
            pump(app, 900)
            sel = visible_selector()
            assert sel is not None, "global F8 did not open the selector"
            picked = []
            sel.regionSelected.connect(lambda region, _image, _rect, picked=picked: picked.append(region))
            _drag(sel, rect)
            pump(app, 500)
            target = _window_region(green)
            assert picked == [target]
            editor = launcher.editors[-1]
            assert editor.doc.size == (target.width, target.height)
            colors = editor.doc.image.convert("RGB").getcolors()
            assert colors is not None and [c for _, c in colors] == [(0, 255, 0)]  # nothing but the window
            editor._force_close = True
            editor.close()
            pump(app, 300)

        # F9 from anywhere -> record -> F9 again while the launcher is hidden.
        launcher._set_format("webp")
        launcher.transparent_check.setChecked(False)
        launcher.settings.fps = 10.0
        result = {}
        launcher.controller.finished.connect(lambda p: result.setdefault("path", p))
        launcher.controller.failed.connect(lambda m: result.setdefault("error", m))
        _press("F9")
        pump(app, 900)
        sel = visible_selector()
        assert sel is not None, "global F9 did not open the selector"
        scale = sel._sx
        _drag(sel, green.geometry())
        pump(app, 700)
        assert launcher.controller.state == "recording"
        region = _window_region(green)
        for strip in launcher.controller._frame.strips:  # border and REC bar stay outside
            assert _window_region(strip).intersect(region) is None
        assert _window_region(launcher.controller._bar).intersect(region) is None
        user32.SetCursorPos(region.x + 60, region.y + 20)
        pump(app, 1200)
        assert not launcher.isVisible()
        _press("F9")
        pump(app, 300)
        assert launcher.controller.state != "recording", "global F9 did not stop the recording"
        deadline = time.time() + 30
        while not result and time.time() < deadline:
            pump(app, 100)
        assert "path" in result, result

        clip = Image.open(result["path"])
        assert clip.size == (region.width, region.height)  # a still scene: identical frames get merged
        inside = (60 + round(1 + 3 * scale), 20 + round(1 + 8 * scale))  # a point inside the arrow
        with_cursor = 0
        for index in range(clip.n_frames):
            clip.seek(index)
            frame = clip.convert("RGB")
            w, h = frame.size
            edge = [frame.getpixel((x, y)) for x in range(w) for y in (0, h - 1)] + [frame.getpixel((x, y)) for y in range(h) for x in (0, w - 1)]
            assert all(g > 180 and r < 90 and b < 90 for r, g, b in edge)  # no border, no neighbours
            with_cursor += all(v > 200 for v in frame.getpixel(inside))
        assert with_cursor >= 1  # drawn where GetCursorPos said, at the display's scale
    finally:
        user32.SetCursorPos(saved.x, saved.y)
        launcher.close()
        green.close()
        bg.close()
        pump(app, 100)
