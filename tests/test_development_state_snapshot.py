"""Development snapshot validation and live subscriber recovery."""
import pytest

from pydux import Action, Store
from pydux.devtools.state_snapshot import capture_store_state, restore_store_state


def reducer(state, action):
    if action.type == "increment":
        return {**state, "count": state["count"] + 1}
    return state


def test_snapshot_is_detached_and_recovers_original_store_subscriptions():
    store = Store(reducer, {"count": 1, "nested": {"names": ["Ada"]}})
    seen = []
    unsubscribe = store.select(lambda s: s["count"], seen.append)
    original = store
    snapshot = capture_store_state(store)
    store.dispatch(Action("increment"))
    assert seen == [2]
    restore_store_state(store, snapshot)
    assert store is original
    assert seen == [2, 1]
    snapshot["state"]["nested"]["names"].append("Grace")
    assert store.get_state()["nested"]["names"] == ["Ada"]
    unsubscribe()
    store.dispatch(Action("increment"))
    assert seen == [2, 1]


@pytest.mark.parametrize("payload", [
    {"version": 0, "state": {}},
    {"version": True, "state": {}},
    {"version": 1},
    {"version": 1, "state": {}, "extra": 2},
    ["version", 1],
    {"version": 1, "state": {"bad": float("nan")}},
    {"version": 1, "state": "x" * 1_048_577},
])
def test_bad_snapshot_leaves_live_state_unchanged(payload):
    store = Store(reducer, {"count": 3})
    with pytest.raises((ValueError, TypeError)):
        restore_store_state(store, payload)
    assert store.get_state() == {"count": 3}


def test_non_serializable_state_is_rejected_without_mutation():
    store = Store(reducer, {"handle": object()})
    with pytest.raises(TypeError):
        capture_store_state(store)


def test_selector_rejection_precedes_live_mutation():
    store = Store(reducer, {"count": 3})
    store.select(lambda s: s["count"], lambda _: None)
    with pytest.raises(KeyError):
        restore_store_state(store, {"version": 1, "state": {"different": 4}})
    assert store.get_state() == {"count": 3}


def test_snapshot_never_includes_reducers_or_callbacks():
    store = Store(reducer, {"count": 5})
    store.select(lambda s: s["count"], lambda _: None)
    assert capture_store_state(store) == {"version": 1, "state": {"count": 5}}
