"""
Kivy Adapter for PyDux 3.0.
Schedules state updates via Kivy's Clock.schedule_once.
"""

from typing import Callable, Any
from pydux.adapters.base import MainThreadBridge


class KivyBridge:
    """Ensures Kivy widgets and canvas instructions update on the Kivy Clock loop."""

    def __init__(self):
        try:
            from kivy.clock import Clock
            self._clock = Clock
        except ImportError:
            self._clock = None

    def schedule_on_main_thread(self, fn: Callable[[], None]) -> None:
        if self._clock:
            self._clock.schedule_once(lambda dt: fn(), 0)
        else:
            fn()
