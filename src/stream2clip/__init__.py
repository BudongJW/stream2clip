"""stream2clip - capture, annotate and record clips from VTuber streams.

Layers (each usable on its own):

* :mod:`stream2clip.ffmpeg`  - pure ffmpeg command/filtergraph builders
* :mod:`stream2clip.chroma`  - color-key transparency (matches ffmpeg ``colorkey``)
* :mod:`stream2clip.capture` - screen capture backends (mss, arrays, plugins)
* :mod:`stream2clip.editor`  - annotation model, renderer, undo/redo
* :mod:`stream2clip.record`  - real-time region recorder
* :mod:`stream2clip.export`  - run ffmpeg exports / probe media
* :mod:`stream2clip.gui`     - optional PySide6 desktop app
"""

from .chroma import apply_colorkey, colorkey_alpha, colorkey_filter
from .export import FFmpegError, MediaInfo, export, probe
from .ffmpeg import ALPHA_FORMATS, FORMATS, ExportOptions, build_export_command, build_video_filter
from .geometry import Region

__version__ = "0.1.0"

__all__ = [
    "ALPHA_FORMATS",
    "FORMATS",
    "ExportOptions",
    "FFmpegError",
    "MediaInfo",
    "Region",
    "__version__",
    "apply_colorkey",
    "build_export_command",
    "build_video_filter",
    "colorkey_alpha",
    "colorkey_filter",
    "export",
    "probe",
]
