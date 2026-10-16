"""Optional Pydux state hooks for declarative PSX component trees."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar, cast

from psx import component
from psx.core.errors import PSXError
from psx.core.hooks import provide_context, use_context, use_effect, use_state
from psx.core.vnode import VNode

TState = TypeVar("TState")
TSelected = TypeVar("TSelected")
_STORE_CONTEXT = object()


def StoreProvider(store: object, child: VNode) -> VNode:
    """Provide exactly one existing Pydux store to a PSX subtree."""
    _validate_store(store)
    return _StoreProvider(child, store=store)


@component
def _StoreProvider(store: object, children: tuple[object, ...]) -> VNode:
    provide_context(_STORE_CONTEXT, store)
    use_effect(lambda: _lease_inspector(store), [store])
    if len(children) != 1 or not isinstance(children[0], VNode):
        raise TypeError("StoreProvider requires exactly one VNode child.")
    return children[0]


def use_dispatch() -> Callable[[object], object]:
    """Return the dispatch method of the nearest explicit StoreProvider."""
    store = _store_from_context()
    return cast(Callable[[object], object], getattr(store, "dispatch"))


def use_selector(
    selector: Callable[[TState], TSelected],
    equality_fn: Callable[[TSelected, TSelected], bool] | None = None,
) -> TSelected:
    """Subscribe the current PSX component to a selected Pydux slice."""
    store = _store_from_context()
    initial = selector(cast(TState, store.get_state()))
    selected, set_selected = use_state(lambda: initial)

    def subscribe() -> Callable[[], None]:
        def on_change(value: TSelected) -> None:
            set_selected(value)

        return store.select(
            selector=selector,
            listener=on_change,
            equality_fn=equality_fn,
            fire_immediately=True,
        )

    use_effect(subscribe, [store, selector, equality_fn])
    return cast(TSelected, selected)


def _store_from_context() -> Any:
    try:
        store = use_context(_STORE_CONTEXT)
    except LookupError as exc:
        raise PSXError("use_selector() and use_dispatch() require an ancestor StoreProvider.") from exc
    _validate_store(store)
    return store


def _validate_store(store: object) -> None:
    required = ("get_state", "dispatch", "select")
    missing = [name for name in required if not callable(getattr(store, name, None))]
    if missing:
        raise TypeError(f"StoreProvider expected a Pydux-compatible store; missing {', '.join(missing)}.")


def _lease_inspector(store: object) -> Callable[[], None]:
    """Stop an auto-started inspector after its last provider unmounts."""
    leases = int(getattr(store, "_pydux_psx_inspector_leases", 0)) + 1
    setattr(store, "_pydux_psx_inspector_leases", leases)

    def release() -> None:
        remaining = max(0, int(getattr(store, "_pydux_psx_inspector_leases", 1)) - 1)
        setattr(store, "_pydux_psx_inspector_leases", remaining)
        if remaining:
            return
        inspector = getattr(store, "inspector", None)
        stop = getattr(inspector, "stop", None)
        if callable(stop):
            stop()

    return release


__all__ = ["StoreProvider", "use_dispatch", "use_selector"]
