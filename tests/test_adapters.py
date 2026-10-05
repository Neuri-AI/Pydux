from pydux import Action, Store
from pydux.adapters.base import DirectThreadBridge, ReactiveBinding, connect
from pydux.adapters.tkinter import TkinterBridge


def reducer(state, action):
    return {**state, "value": action.payload} if action.type == "set" else state


def test_reactive_binding_emits_initial_value_and_stops_after_disposal():
    store = Store(reducer, {"value": 1})
    values = []
    binding = ReactiveBinding(store, lambda state: state["value"], values.append)

    store.dispatch(Action("set", 2))
    binding.dispose()
    store.dispatch(Action("set", 3))

    assert values == [1, 2]


def test_connect_populates_props_and_calls_component_hook():
    store = Store(reducer, {"value": 1})

    @connect(store, lambda state: {"value": state["value"]}, DirectThreadBridge())
    class Component:
        def __init__(self):
            self.calls = 0

        def on_props_changed(self):
            self.calls += 1

    component = Component()
    store.dispatch(Action("set", 2))

    assert (component.value, component.calls) == (2, 2)


def test_tkinter_bridge_uses_after_idle_and_falls_back_when_it_fails():
    calls = []

    class Widget:
        def after_idle(self, callback):
            calls.append("scheduled")
            callback()

    TkinterBridge(Widget()).schedule_on_main_thread(lambda: calls.append("called"))
    assert calls == ["scheduled", "called"]
