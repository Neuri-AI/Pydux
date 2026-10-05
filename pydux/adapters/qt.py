"""
Qt Adapter for PySide6, PySide2, PyQt5, and PyQt6.
Uses Qt MetaObject and QTimer.singleShot safely on the Qt event loop,
without locking PyDux core to Qt dependencies.
"""

from typing import Callable, Any, Optional
from pydux.adapters.base import MainThreadBridge


class QtMainThreadBridge:
    """Dispatches calls onto the Qt GUI event loop safely."""

    def __init__(self):
        # Auto-detect Qt binding
        self._qtimer = None
        for mod_name in ("PySide6.QtCore", "PyQt6.QtCore", "PySide2.QtCore", "PyQt5.QtCore"):
            try:
                mod = __import__(mod_name, fromlist=["QTimer"])
                self._qtimer = getattr(mod, "QTimer")
                break
            except ImportError:
                continue

    def schedule_on_main_thread(self, fn: Callable[[], None]) -> None:
        if self._qtimer:
            self._qtimer.singleShot(0, fn)
        else:
            fn()
