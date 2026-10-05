"""
UI-Agnostic Reactive Binding & Thread Dispatcher.
Decouples PyDux from any concrete GUI library while providing
rock-solid main thread synchronization.
"""

from typing import (
    Callable,
    Any,
    Optional,
    Protocol,
    TypeVar,
    Dict,
)
from pydux.core.store import Store
from pydux.core.types import Selector, Unsubscribe, EqualityFn

T = TypeVar("T")


class MainThreadBridge(Protocol):
    """
    Protocol to safely schedule a callable onto the GUI's main thread.
    Required by desktop frameworks (Qt, Tkinter, Kivy) to avoid threading crashes.
    """

    def schedule_on_main_thread(self, fn: Callable[[], None]) -> None:
        ...


class DirectThreadBridge:
    """Default fallback bridge for pure synchronous execution or tests."""

    def schedule_on_main_thread(self, fn: Callable[[], None]) -> None:
        fn()


class ReactiveBinding:
    """
    Connects a specific PyDux selector to any widget setter or callback.
    Automatically handles main-thread dispatching.
    
    Example:
        ReactiveBinding(
            store=store,
            selector=lambda s: s["user"]["name"],
            target=lambda name: label.config(text=name),
            bridge=TkinterBridge(root)
        )
    """

    def __init__(
        self,
        store: Store[Any],
        selector: Selector[Any, T],
        target: Callable[[T], None],
        equality_fn: Optional[EqualityFn] = None,
        bridge: Optional[MainThreadBridge] = None,
    ):
        self._bridge = bridge or DirectThreadBridge()
        self._target = target

        def safe_listener(value: T):
            self._bridge.schedule_on_main_thread(lambda: self._target(value))

        self._unsubscribe = store.select(
            selector=selector,
            listener=safe_listener,
            equality_fn=equality_fn,
            fire_immediately=True,
        )

    def dispose(self) -> None:
        """Tears down the subscription."""
        if self._unsubscribe:
            self._unsubscribe()
            self._unsubscribe = None


def connect(
    store: Store[Any],
    map_state_to_props: Optional[Callable[[Any], Dict[str, Any]]] = None,
    bridge: Optional[MainThreadBridge] = None,
):
    """
    Class decorator for framework-agnostic component state injection.
    """
    def decorator(cls):
        orig_init = cls.__init__

        def new_init(self, *args, **kwargs):
            orig_init(self, *args, **kwargs)
            self._pydux_unsubscribers = []
            active_bridge = bridge or getattr(self, "_pydux_bridge", DirectThreadBridge())

            if map_state_to_props:
                def on_state_slice(props: Dict[str, Any]):
                    for prop_name, prop_val in props.items():
                        setattr(self, prop_name, prop_val)
                    if hasattr(self, "on_props_changed") and callable(self.on_props_changed):
                        self.on_props_changed()

                unsub = store.select(
                    selector=map_state_to_props,
                    listener=lambda p: active_bridge.schedule_on_main_thread(lambda: on_state_slice(p)),
                    fire_immediately=True,
                )
                self._pydux_unsubscribers.append(unsub)

        cls.__init__ = new_init
        return cls

    return decorator
