"""Qt helpers: PIL <-> QImage, assets, screen geometry."""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from PySide6.QtCore import QRect
from PySide6.QtGui import QGuiApplication, QIcon, QImage, QPixmap

ASSETS = Path(__file__).with_name("assets")


def asset(name: str) -> str:
    return str(ASSETS / name)


def app_icon() -> QIcon:
    return QIcon(asset("app-icon.png"))


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
