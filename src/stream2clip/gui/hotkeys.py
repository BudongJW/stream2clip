"""System-wide hotkeys (F9 to start/stop recording even when the app is not focused).

Windows uses ``RegisterHotKey`` (no extra dependency). Elsewhere ``pynput`` is
used when installed (``pip install "stream2clip[hotkey]"``). If neither works,
the window-level shortcuts registered by the GUI still apply.
"""

from __future__ import annotations

import sys
from typing import Callable

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication, QObject, Signal

__all__ = ["GlobalHotkeys"]

_WM_HOTKEY = 0x0312
_MOD_NOREPEAT = 0x4000
_VK = {"F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73, "F5": 0x74, "F6": 0x75, "F7": 0x76, "F8": 0x77, "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B}


class _WinFilter(QAbstractNativeEventFilter):
    def __init__(self, callback: Callable[[int], None]) -> None:
        super().__init__()
        self._callback = callback

    def nativeEventFilter(self, eventType, message):  # noqa: N802 - Qt API
        if bytes(eventType) in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            from ctypes import wintypes

            msg = wintypes.MSG.from_address(int(message))
            if msg.message == _WM_HOTKEY:
                self._callback(int(msg.wParam))
                return True, 0
        return False, 0


class GlobalHotkeys(QObject):
    """Emit ``activated(name)`` on the Qt thread when a registered key is pressed."""

    activated = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._names: dict[int, str] = {}
        self._filter: _WinFilter | None = None
        self._listener = None
        self.backend = "none"

    def register(self, keys: list[str]) -> str:
        """Register function keys like ``["F8", "F9"]``; returns the backend used."""
        if sys.platform == "win32" and self._register_windows(keys):
            self.backend = "win32"
        elif self._register_pynput(keys):
            self.backend = "pynput"
        return self.backend

    def _register_windows(self, keys: list[str]) -> bool:
        import ctypes

        user32 = ctypes.windll.user32
        ok = False
        for index, key in enumerate(keys, start=1):
            vk = _VK.get(key.upper())
            if vk and user32.RegisterHotKey(None, 0xB000 + index, _MOD_NOREPEAT, vk):
                self._names[0xB000 + index] = key.upper()
                ok = True
        if ok:
            self._filter = _WinFilter(lambda hid: self.activated.emit(self._names.get(hid, "")))
            QCoreApplication.instance().installNativeEventFilter(self._filter)
        return ok

    def _register_pynput(self, keys: list[str]) -> bool:
        try:
            from pynput import keyboard  # type: ignore[import-not-found]
        except Exception:
            return False
        mapping = {f"<{k.lower()}>": (lambda k=k: self.activated.emit(k.upper())) for k in keys}
        try:
            self._listener = keyboard.GlobalHotKeys(mapping)
            self._listener.start()
        except Exception:
            self._listener = None
            return False
        return True

    def unregister(self) -> None:
        if sys.platform == "win32" and self._names:
            import ctypes

            for hid in self._names:
                ctypes.windll.user32.UnregisterHotKey(None, hid)
            self._names.clear()
        if self._filter is not None:
            QCoreApplication.instance().removeNativeEventFilter(self._filter)
            self._filter = None
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
