"""Desktop app entry point (``stream2clip-gui`` / ``stream2clip gui``)."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .qt import app_icon
from .theme import STYLE_SHEET

__all__ = ["create_app", "main", "apply_saved_language"]


APP_ID = "BudongJW.stream2clip"


def _claim_taskbar_identity() -> None:
    """Windows groups taskbar buttons by app id; without our own, a Python-run app shows Python's icon."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:  # pragma: no cover - cosmetic only
        pass


def create_app(argv: list[str] | None = None) -> QApplication:
    app = QApplication.instance()
    if app is None:
        _claim_taskbar_identity()
        app = QApplication(argv if argv is not None else sys.argv[:1])
    app.setApplicationName("stream2clip")
    app.setApplicationDisplayName("stream2clip")
    app.setWindowIcon(app_icon())
    app.setStyleSheet(STYLE_SHEET)
    return app  # type: ignore[return-value]


def apply_saved_language() -> str:
    """Use the language chosen in the app (unless ``STREAM2CLIP_LANG`` says otherwise) - before any window module is imported."""
    import os

    from ..i18n import language, set_language
    from .settings import load_section

    saved = load_section("app").get("language")
    if isinstance(saved, str) and not os.environ.get("STREAM2CLIP_LANG"):
        set_language(saved)
    return language()


def main(files: list[str] | None = None) -> int:
    if files is None:
        files = sys.argv[1:]
    app = create_app()
    apply_saved_language()
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
