"""Development-only state-schema reconciliation for coordinated hot reload.

The coordinator calls reconfigure_store with freshly evaluated slice definitions.
Existing values win; new default keys and newly introduced slices are added.
No new store, middleware chain, subscriptions, or inspector server are created.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from pydux.core.store import Store
from pydux.core.types import Action
from pydux.toolkit.configure_store import combine_reducers
from pydux.toolkit.slice import Slice


def _merge_defaults(defaults: Any, current: Any) -> Any:
    """Preserve runtime values and keys while filling missing default keys."""
    if isinstance(defaults, dict) and isinstance(current, dict):
        merged = copy.deepcopy(current)
        for key, default in defaults.items():
            if key in current:
                merged[key] = _merge_defaults(default, current[key])
            else:
                merged[key] = copy.deepcopy(default)
        return merged
    # The current value is authoritative, including None/False/empty containers.
    return copy.deepcopy(current)


def reconfigure_store(store: Store, slices: Mapping[str, Any]) -> Store:
    """Hot-swap slices and defaults into an existing store.

    Call only after the new Python module has evaluated successfully. This API
    is intended for development; production/frozen apps should not invoke it.
    A slice absent from the new mapping is preserved until explicitly migrated.
    """
    if not isinstance(slices, Mapping):
        raise TypeError("slices must be a mapping of names to reducers or Slice objects")

    previous = getattr(store, "_pydux_slice_definitions", {})
    combined = dict(previous)
    combined.update(slices)
    reducers = {
        name: value.reducer if isinstance(value, Slice) else value
        for name, value in combined.items()
    }
    if not all(callable(r) for r in reducers.values()):
        raise TypeError("All slice reducers must be callable")

    # Build and validate everything before mutating the live store.
    old_state = store.get_state()
    if not isinstance(old_state, dict):
        raise TypeError("Slice reconciliation requires a dictionary root state")
    next_state = copy.deepcopy(old_state)
    for name, reducer in reducers.items():
        initial = reducer(None, Action(type="@@PYDUX/INIT"))
        next_state[name] = (
            _merge_defaults(initial, old_state[name])
            if name in old_state else copy.deepcopy(initial)
        )
    new_reducer = combine_reducers(reducers)
    # Atomic swap retains the store identity, middleware and subscriptions.
    store.replace_reducer(new_reducer, next_state)
    setattr(store, "_pydux_slice_definitions", combined)

    inspector = getattr(store, "inspector", None)
    broadcast = getattr(inspector, "_broadcast_snapshot", None)
    if callable(broadcast):
        broadcast()
    return store
