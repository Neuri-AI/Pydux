"""Bounded, opt-in development snapshots of JSON-compatible Pydux state.

Snapshots contain data only; reducers, middleware and subscriptions remain owned
by the live Store and must never be serialized.
"""
from __future__ import annotations

import json
from typing import Any

MAX_SNAPSHOT_BYTES = 1_048_576
SNAPSHOT_VERSION = 1


def _json_copy(value: Any) -> Any:
    encoded = json.dumps(value, allow_nan=False, separators=(",", ":"), ensure_ascii=False)
    if len(encoded.encode("utf-8")) > MAX_SNAPSHOT_BYTES:
        raise ValueError("Development state snapshot exceeds the size limit.")
    return json.loads(encoded)


def capture_store_state(store: Any) -> dict[str, Any]:
    """Capture a detached JSON snapshot without retaining the live store."""
    if not callable(getattr(store, "get_state", None)):
        raise TypeError("Expected a Pydux store.")
    return {"version": SNAPSHOT_VERSION, "state": _json_copy(store.get_state())}


def restore_store_state(store: Any, snapshot: dict[str, Any]) -> None:
    """Restore validated data while retaining the store's subscriber identities.

    This is intended for explicitly registered development stores, never for
    arbitrary objects loaded from a source module. Validation is completed
    before the live state or subscriber caches are touched.
    """
    if type(snapshot) is not dict or set(snapshot) != {"version", "state"}:
        raise ValueError("Invalid development state snapshot envelope.")
    if type(snapshot["version"]) is not int or snapshot["version"] != SNAPSHOT_VERSION:
        raise ValueError("Unsupported development state snapshot version.")
    candidate = _json_copy(snapshot["state"])
    lock = getattr(store, "_lock", None)
    if lock is None or not hasattr(store, "_subscriptions") or not hasattr(store, "_state"):
        raise TypeError("Expected a Pydux Store instance.")
    with lock:
        if store._is_dispatching:
            raise RuntimeError("Cannot restore state while dispatching.")
        # Validate selectors before mutating the live store.
        selected = [(sub, sub.selector(candidate)) for sub in store._subscriptions if sub.active]
        store._state = candidate
        for sub, value in selected:
            sub.last_value = value
