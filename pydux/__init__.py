"""
PyDux 3.0 — UI-Agnostic State Management for Python Desktop Applications.
Supports modern Redux Toolkit style (create_slice, configure_store, create_async_thunk)
with memoized selectors, zero redundant re-renders, and full Qyro/PySide/Tkinter/Kivy support.
"""

# Redux Toolkit style modern API
from pydux.toolkit.slice import create_slice, Slice
from pydux.toolkit.configure_store import configure_store, combine_reducers
from pydux.toolkit.async_thunk import create_async_thunk, create_thunk_middleware

# Core Store & Selectors
from pydux.core.store import Store
from pydux.core.selector import create_selector, shallow_equal, deep_equal, is_identical
from pydux.core.types import Action, Reducer, Selector, Middleware, Dispatch

# DevTools & Time-Travel
from pydux.devtools.tracker import PyDuxDevTools, devtools_middleware
from pydux.devtools.inspector import PyDuxInspectorServer, start_inspector

# UI Adapters & Framework Bridges
from pydux.adapters.base import MainThreadBridge, ReactiveBinding, connect
from pydux.adapters.qyro import Reactive, connect_qyro

__version__ = "3.0.0"
__all__ = [
    # Redux Toolkit API
    "create_slice",
    "configure_store",
    "create_async_thunk",
    "create_thunk_middleware",
    "combine_reducers",
    "Slice",

    # Core Store & Selectors
    "Store",
    "create_selector",
    "shallow_equal",
    "deep_equal",
    "is_identical",
    "Action",
    "Reducer",
    "Selector",
    "Middleware",
    "Dispatch",

    # DevTools
    "PyDuxDevTools",
    "devtools_middleware",
    "PyDuxInspectorServer",
    "start_inspector",

    # Adapters
    "MainThreadBridge",
    "ReactiveBinding",
    "connect",
    "Reactive",
    "connect_qyro",
]
