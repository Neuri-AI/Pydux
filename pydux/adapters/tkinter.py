"""
Tkinter Adapter for PyDux 3.0.
Schedules state updates via Tkinter's event loop (widget.after / after_idle).
"""

from typing import Callable, Any
from pydux.adapters.base import MainThreadBridge


class TkinterBridge:
    """Ensures Tkinter widgets are only mutated on the Tk main thread."""

    def __init__(self, root_or_widget: Any):
        self._widget = root_or_widget

    def schedule_on_main_thread(self, fn: Callable[[], None]) -> None:
        try:
            self._widget.after_idle(fn)
        except Exception:
            fn()
