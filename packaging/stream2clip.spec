# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: one folder with two programs sharing the same libraries.

    stream2clip-gui.exe   desktop app (no console window)
    stream2clip.exe       command line (also runs yt-dlp for `fetch`)

Use packaging/build_windows.py rather than calling PyInstaller on this file directly.
Optional parts are chosen with the STREAM2CLIP_BUNDLE environment variable
(comma separated): "asr" adds faster-whisper for --transcribe (much larger).
"""

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

ROOT = Path(SPECPATH).parent
EXTRAS = {part.strip() for part in os.environ.get("STREAM2CLIP_BUNDLE", "").split(",") if part.strip()}
# 16-256 px in one file; 24 px and below use the simplified symbol.
ICON = os.environ.get("STREAM2CLIP_ICON") or str(ROOT / "assets" / "brand" / "app-icons" / "windows" / "stream2clip.ico")

# Qt modules the app never loads; leaving them out saves a few hundred MB.
excludes = [
    "tkinter", "pytest", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick", "PySide6.QtWebChannel",
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets", "PySide6.Qt3DCore", "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtGraphs",
    "PySide6.QtNetwork", "PySide6.QtSql", "PySide6.QtBluetooth", "PySide6.QtPositioning", "PySide6.QtDesigner",
]
if "asr" not in EXTRAS:
    excludes += ["faster_whisper", "ctranslate2", "tokenizers", "huggingface_hub", "av"]

datas = collect_data_files("stream2clip")
hiddenimports = ["stream2clip.gui.highlights", "stream2clip.detect", "stream2clip.capture.mss_backend"]


def analysis(script):
    return Analysis(
        [str(ROOT / "packaging" / script)],
        pathex=[str(ROOT / "src")],
        datas=datas,
        hiddenimports=hiddenimports,
        excludes=excludes,
    )


gui = analysis("entry_gui.py")
cli = analysis("entry_cli.py")
gui_exe = EXE(PYZ(gui.pure), gui.scripts, [], exclude_binaries=True, name="stream2clip-gui", console=False, icon=ICON)
cli_exe = EXE(PYZ(cli.pure), cli.scripts, [], exclude_binaries=True, name="stream2clip", console=True, icon=ICON)
COLLECT(gui_exe, gui.binaries, gui.datas, cli_exe, cli.binaries, cli.datas, name="stream2clip")
