"""
Core Store for PyDux 3.0.
Decoupled from any GUI framework. Eliminates the legacy Pydux/PPGStore full-fanout
problem by using selective notifications and slice memoization.
"""

from typing import (
    Generic,
    Callable,
    List,
    Any,
    Optional,
    Sequence,
    Dict,
)
import threading
import logging
from pydux.core.types import (
    TState,
    TSelected,
    Action,
    Reducer,
    Selector,
    EqualityFn,
    Listener,
    Unsubscribe,
    Middleware,
    Dispatch,
)
from pydux.core.selector import shallow_equal


class _Subscription(Generic[TState, TSelected]):
    """Holds a subscriber with its selector, comparator, and previous slice value."""

    __slots__ = ("selector", "listener", "equality_fn", "last_value", "active")

    def __init__(
        self,
        selector: Selector[TState, TSelected],
        listener: Listener[TSelected],
        equality_fn: EqualityFn,
        initial_value: TSelected,
    ):
        self.selector = selector
        self.listener = listener
        self.equality_fn = equality_fn
        self.last_value: TSelected = initial_value
        self.active: bool = True


class Store(Generic[TState]):
    """
    Thread-safe, observable state container.
    Guarantees that subscribers are ONLY called if their selected slice has changed.
    """

    def __init__(
        self,
        reducer: Reducer[TState],
        initial_state: TState,
        middlewares: Optional[Sequence[Middleware]] = None,
    ):
        self._reducer: Reducer[TState] = reducer
        self._state: TState = initial_state
        self._subscriptions: List[_Subscription[TState, Any]] = []
        self._lock = threading.RLock()
        self._is_dispatching: bool = False

        # Build middleware dispatch chain
        self._dispatch: Dispatch = self._internal_dispatch
        if middlewares:
            for mw in reversed(middlewares):
                self._dispatch = mw(self, self._dispatch)

    def get_state(self) -> TState:
        """Returns the current state."""
        with self._lock:
            return self._state

    def dispatch(self, action: Any) -> Any:
        """Dispatches an action through the middleware chain to the reducer."""
        return self._dispatch(action)

    def _internal_dispatch(self, action: Any) -> Any:
        if not isinstance(action, Action):
            raise TypeError(
                "Store.dispatch expected an Action. "
                "To dispatch callables, use configure_store() which installs thunk middleware."
            )

        with self._lock:
            if self._is_dispatching:
                raise RuntimeError("Reducers may not dispatch actions.")

            try:
                self._is_dispatching = True
                self._state = self._reducer(self._state, action)
            finally:
                self._is_dispatching = False

            # Notify only affected subscribers
            self._notify_subscribers()

        return action

    def select(
        self,
        selector: Selector[TState, TSelected],
        listener: Listener[TSelected],
        equality_fn: Optional[EqualityFn] = None,
        fire_immediately: bool = False,
    ) -> Unsubscribe:
        """
        Subscribes to a specific slice of the store.
        The listener is ONLY invoked if equality_fn(prev_slice, next_slice) is False.
        """
        cmp_fn = equality_fn or shallow_equal
        with self._lock:
            initial_val = selector(self._state)
            sub = _Subscription(selector, listener, cmp_fn, initial_val)
            self._subscriptions.append(sub)

        if fire_immediately:
            listener(initial_val)

        def unsubscribe():
            with self._lock:
                sub.active = False
                if sub in self._subscriptions:
                    self._subscriptions.remove(sub)

        return unsubscribe

    def subscribe(self, listener: Callable[[TState], None]) -> Unsubscribe:
        """
        Full store subscription (equivalent to select with identity).
        Prefer select() in GUI widgets to avoid unnecessary re-renders.
        """
        return self.select(
            selector=lambda s: s,
            listener=listener,
            equality_fn=lambda a, b: False, # always notify for full store
        )

    def _notify_subscribers(self) -> None:
        """Runs selective notifications. Only fires if slice changed."""
        current_state = self._state
        # Shallow copy list to permit unsubscribes during iteration
        active_subs = [s for s in self._subscriptions if s.active]

        for sub in active_subs:
            if not sub.active:
                continue

            try:
                new_slice = sub.selector(current_state)
                # Check equality against previous slice value
                if not sub.equality_fn(sub.last_value, new_slice):
                    sub.last_value = new_slice
                    sub.listener(new_slice)
            except Exception as e:
                # Isolate listener failures from crashing the store
                logging.getLogger("pydux").exception(
                    f"Error in PyDux subscriber notification: {e}"
                )

