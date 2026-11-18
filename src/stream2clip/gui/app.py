"""Desktop app entry point (``stream2clip-gui`` / ``stream2clip gui``)."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .qt import app_icon
from .theme import STYLE_SHEET

__all__ = ["create_app", "main"]


def create_app(argv: list[str] | None = None) -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(argv if argv is not None else sys.argv[:1])
    app.setApplicationName("stream2clip")
    app.setApplicationDisplayName("stream2clip")
    app.setWindowIcon(app_icon())
    app.setStyleSheet(STYLE_SHEET)
    return app  # type: ignore[return-value]


def main(files: list[str] | None = None) -> int:
    if files is None:
        files = sys.argv[1:]
    app = create_app()
    from .launcher import LauncherWindow

    launcher = LauncherWindow()
    if files:
        for path in files:
            launcher.open_path(path)
    else:
        launcher.show()
    return app.exec()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
