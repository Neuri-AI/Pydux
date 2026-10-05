"""
Qyro Framework Adapter for PyDux 3.0.
Works seamlessly with qyro.ui.component.Component and qyro.ApplicationContext.
Automatically handles subscription on mount and unsubscription on unmount!
"""

import sys
import logging
from typing import Callable, Any, Optional, Dict, List
from pydux.core.store import Store
from pydux.core.types import Selector, EqualityFn, Unsubscribe


def _get_qt_single_shot() -> Optional[Callable[[int, Callable[[], None]], None]]:
    """Resolve QTimer.singleShot from the active Qt binding, if available."""
    for module_name in ("PySide6.QtCore", "PyQt6.QtCore", "PySide2.QtCore", "PyQt5.QtCore"):
        module = sys.modules.get(module_name)

        if module is None:
            try:
                module = __import__(module_name, fromlist=["QTimer"])
            except ImportError:
                continue

        qtimer = getattr(module, "QTimer", None)
        if qtimer is not None and hasattr(qtimer, "singleShot"):
            return qtimer.singleShot

    return None


def _schedule_on_ui_tick(component: Any, fn: Callable[[], None]) -> bool:
    """Schedule callback on the active UI framework tick (Qt, Tkinter, or Kivy)."""
    single_shot = _get_qt_single_shot()
    if single_shot is not None:
        single_shot(0, fn)
        return True

    tk_after = getattr(component, "after", None)
    if callable(tk_after):
        tk_after(0, fn)
        return True

    try:
        from kivy.clock import Clock  # type: ignore

        Clock.schedule_once(lambda _dt: fn(), 0)
        return True
    except Exception:
        return False


def _select_with_deferred_initial(
    component: Any,
    store: Store[Any],
    selector: Selector[Any, Any],
    on_change: Callable[[Any], None],
    equality_fn: Optional[EqualityFn] = None,
) -> Unsubscribe:
    """Subscribe without immediate fire and dispatch initial value in the UI tick."""
    delivered = {"called": False}

    def tracked_on_change(value: Any) -> None:
        delivered["called"] = True
        on_change(value)

    unsub = store.select(
        selector=selector,
        listener=tracked_on_change,
        equality_fn=equality_fn,
        fire_immediately=False,
    )

    def emit_initial_value() -> None:
        if delivered["called"]:
            return

        try:
            tracked_on_change(selector(store.get_state()))
        except Exception:
            logging.getLogger("pydux").exception(
                "Error while dispatching initial Qyro selector value"
            )

    if _schedule_on_ui_tick(component, emit_initial_value):
        return unsub

    # Last-resort fallback when no known UI scheduler is available.
    # This keeps non-framework test contexts functional.
    emit_initial_value()

    return unsub


class Reactive:
    """
    Mixin for Qyro Component classes.
    Integrates seamlessly into Qyro's lifecycle:
    - component_will_mount
    - render
    - component_will_unmount
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._qyro_store_subscriptions: List[Unsubscribe] = []

    def bind_selector(
        self,
        store: Store[Any],
        selector: Selector[Any, Any],
        on_change: Callable[[Any], None],
        equality_fn: Optional[EqualityFn] = None,
    ) -> Unsubscribe:
        """
        Subscribes to a store slice. The subscription is tracked and
        will be automatically cleaned up when the Qyro component unmounts.

        The first callback is deferred to the next Qt tick so components can
        subscribe during component_will_mount without touching widgets that are
        created later in render().
        """
        if not hasattr(self, "_qyro_store_subscriptions"):
            self._qyro_store_subscriptions = []

        unsub = _select_with_deferred_initial(
            component=self,
            store=store,
            selector=selector,
            on_change=on_change,
            equality_fn=equality_fn,
        )
        self._qyro_store_subscriptions.append(unsub)

        return unsub

    def component_will_unmount(self):
        """Lifecycle hook: clean up all PyDux subscriptions to prevent leaks."""
        if not hasattr(self, "_qyro_store_subscriptions"):
            self._qyro_store_subscriptions = []

        for unsub in self._qyro_store_subscriptions:
            unsub()
        self._qyro_store_subscriptions.clear()

        # Call super if parent component defines component_will_unmount
        if hasattr(super(), "component_will_unmount"):
            super().component_will_unmount()


def connect_qyro(store: Store[Any], selectors: Dict[str, Selector[Any, Any]]):
    """
    Decorator for Qyro components that automatically maps selectors to component properties.
    """
    def decorator(cls):
        orig_mount = getattr(cls, "component_will_mount", None)
        orig_unmount = getattr(cls, "component_will_unmount", None)

        def new_component_will_mount(self):
            if not hasattr(self, "_qyro_unsubs"):
                self._qyro_unsubs = []
            if not hasattr(self, "_qyro_connected_props"):
                self._qyro_connected_props = {}

            for attr_name, selector in selectors.items():
                def make_listener(name: str):
                    def listener(val: Any) -> None:
                        setattr(self, name, val)
                        self._qyro_connected_props[name] = val

                        on_state_change = getattr(self, "on_state_change", None)
                        if callable(on_state_change):
                            on_state_change(dict(self._qyro_connected_props))

                    return listener

                unsub = _select_with_deferred_initial(
                    component=self,
                    store=store,
                    selector=selector,
                    on_change=make_listener(attr_name),
                )
                self._qyro_unsubs.append(unsub)

            if orig_mount:
                orig_mount(self)

        def new_component_will_unmount(self):
            if hasattr(self, "_qyro_unsubs"):
                for unsub in self._qyro_unsubs:
                    unsub()
                self._qyro_unsubs.clear()
            if orig_unmount:
                orig_unmount(self)

        cls.component_will_mount = new_component_will_mount
        cls.component_will_unmount = new_component_will_unmount
        return cls

    return decorator


# Backward-compatible alias for projects already using @pydux(...)
pydux = connect_qyro
