import asyncio

import pytest

from pydux import Action, configure_store, create_async_thunk, create_slice


def make_counter_slice():
    return create_slice(
        name="counter",
        initial_state={"value": 0, "status": "idle", "error": None},
        reducers={
            "add": lambda state, action: state.update(value=state["value"] + action.payload),
            "reset": lambda state, action: {"value": 0, "status": "idle", "error": None},
        },
        extra_reducers={
            "counter/load/pending": lambda state, action: state.update(status="loading"),
            "counter/load/fulfilled": lambda state, action: state.update(status="done", value=action.payload),
            "counter/load/rejected": lambda state, action: state.update(status="failed", error=action.payload),
        },
    )


def test_slice_creates_namespaced_actions_and_immutable_drafts():
    counter = make_counter_slice()
    initial = {"value": 1, "status": "idle", "error": None}

    action = counter.actions.add(2, meta={"source": "test"})
    next_state = counter.reducer(initial, action)

    assert action.type == "counter/add"
    assert action.meta == {"source": "test"}
    assert initial["value"] == 1
    assert next_state["value"] == 3
    assert counter.reducer(initial, Action("other/action")) is initial


def test_slice_supports_returning_a_replacement_state_and_extra_reducers():
    counter = make_counter_slice()

    assert counter.reducer(None, Action("@@INIT"))["value"] == 0
    assert counter.reducer({"value": 3, "status": "idle", "error": None}, counter.actions.reset()) == {
        "value": 0,
        "status": "idle",
        "error": None,
    }
    assert counter.reducer(None, Action("counter/load/fulfilled", 9))["value"] == 9


def test_slice_rejects_an_empty_name_and_unknown_action_creator():
    with pytest.raises(ValueError):
        create_slice("", {}, {})
    with pytest.raises(AttributeError):
        make_counter_slice().actions.missing


def test_configure_store_combines_slices_and_honours_preloaded_state():
    counter = make_counter_slice()
    store = configure_store(
        {"counter": counter},
        preloaded_state={"counter": {"value": 5, "status": "idle", "error": None}},
        devtools=False,
    )

    store.dispatch(counter.actions.add(2))

    assert store.get_state()["counter"]["value"] == 7
    assert not hasattr(store, "devtools")


def test_custom_middleware_wraps_dispatch_in_declared_order():
    events = []

    def middleware(store, next_dispatch):
        def dispatch(action):
            events.append(("before", action.type))
            result = next_dispatch(action)
            events.append(("after", action.type))
            return result
        return dispatch

    store = configure_store({"counter": make_counter_slice()}, middleware=[middleware], devtools=False)
    store.dispatch(Action("counter/add", 1))

    assert events == [("before", "counter/add"), ("after", "counter/add")]


def test_async_thunk_dispatches_pending_and_fulfilled_actions():
    counter = make_counter_slice()
    store = configure_store({"counter": counter}, devtools=False)
    load = create_async_thunk("counter/load", lambda value: value * 2)

    assert store.dispatch(load(4)) == 8
    assert store.get_state()["counter"] == {"value": 8, "status": "done", "error": None}


def test_async_thunk_dispatches_rejected_action_and_reraises():
    counter = make_counter_slice()
    store = configure_store({"counter": counter}, devtools=False)
    load = create_async_thunk("counter/load", lambda: (_ for _ in ()).throw(ValueError("offline")))

    with pytest.raises(ValueError, match="offline"):
        store.dispatch(load())

    assert store.get_state()["counter"]["status"] == "failed"
    assert store.get_state()["counter"]["error"] == "offline"


def test_async_thunk_resolves_coroutines():
    async def load():
        await asyncio.sleep(0)
        return 6

    counter = make_counter_slice()
    store = configure_store({"counter": counter}, devtools=False)

    assert store.dispatch(create_async_thunk("counter/load", load)()) == 6
    assert store.get_state()["counter"]["value"] == 6
