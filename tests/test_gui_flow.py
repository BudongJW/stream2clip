"""End-to-end desktop flow on a real (virtual) display: F8 capture and F9 transparent recording.

Runs only when a display is available, e.g. ``xvfb-run -a pytest tests/test_gui_flow.py``.
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
    bg.setWindowFlag(Qt.WindowType.FramelessWindowHint)
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
    assert editor.doc.size == (200, 120)
    assert editor.doc.image.getpixel((editor.doc.size[0] - 2, 2))[:3] == (0, 255, 0)
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
