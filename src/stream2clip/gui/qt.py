"""Qt helpers: PIL <-> QImage, assets, screen geometry."""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QGuiApplication, QIcon, QImage, QPixmap

ASSETS = Path(__file__).with_name("assets")


def asset(name: str) -> str:
    return str(ASSETS / name)


#: Sizes of the app icon shipped with the app. 24 px and below use the simplified symbol
#: (no REC dot / play triangle, thicker lines), so the title bar and taskbar stay legible.
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)
#: Kiri, the mascot: wink (default), laugh (funny scene), surprised (twist / something went
#: wrong), cut (clip finished), focus (working).
MOODS = ("wink", "laugh", "surprised", "cut", "focus")


def app_icon() -> QIcon:
    icon = QIcon()
    for size in ICON_SIZES:
        icon.addFile(asset(f"icon_{size}.png"), QSize(size, size))
    return icon


def mascot(mood: str = "wink", size: int = 56) -> QPixmap:
    """Kiri in the given mood, ``size`` logical pixels tall (sharp on HiDPI screens)."""
    name = mood if mood in MOODS else "wink"
    screen = QGuiApplication.primaryScreen()
    ratio = screen.devicePixelRatio() if screen is not None else 1.0
    source = QPixmap(asset(f"kiri_{name}_112.png"))
    pix = source.scaledToHeight(max(1, round(size * ratio)), Qt.TransformationMode.SmoothTransformation)
    pix.setDevicePixelRatio(ratio)
    return pix


def pixmap(name: str) -> QPixmap:
    return QPixmap(asset(name))


def pil_to_qimage(image: Image.Image) -> QImage:
    rgba = image.convert("RGBA")
    data = rgba.tobytes("raw", "RGBA")
    qimg = QImage(data, rgba.width, rgba.height, rgba.width * 4, QImage.Format.Format_RGBA8888)
    return qimg.copy()  # detach from the Python buffer


def qimage_to_pil(qimage: QImage) -> Image.Image:
    img = qimage.convertToFormat(QImage.Format.Format_RGBA8888)
    ptr = img.constBits()
    data = bytes(ptr)[: img.sizeInBytes()]
    pil = Image.frombuffer("RGBA", (img.width(), img.height()), data, "raw", "RGBA", img.bytesPerLine(), 1)
    return pil.copy()


def virtual_geometry() -> QRect:
    """Union of all screens in Qt logical coordinates."""
    rect = QRect()
    for screen in QGuiApplication.screens():
        rect = rect.united(screen.geometry())
    return rect
