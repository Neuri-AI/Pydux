"""Regression tests for development-time slice reconciliation and inspector bootstrap."""

from pydux import configure_store, create_slice, reconfigure_store


def slice_user(initial):
    return create_slice(
        name="user",
        initial_state=initial,
        reducers={"set_data": lambda state, action: {**state, **action.payload}},
    )


def test_reconfigure_preserves_live_values_and_adds_defaults():
    old = slice_user({"name": "fredo", "nested": {"a": 1}})
    store = configure_store({"user": old}, devtools=False)
    seen = []
    store.select(lambda state: state["user"], seen.append)
    store.dispatch(old.actions.set_data({"name": "Luis"}))

    updated = slice_user({
        "name": "initial",
        "email": "alfredo@neuri.ai",
        "nested": {"a": 0, "b": 2},
    })
    same_store = reconfigure_store(store, {"user": updated})
    assert same_store is store
    assert store.get_state()["user"] == {
        "name": "Luis",
        "email": "alfredo@neuri.ai",
        "nested": {"a": 1, "b": 2},
    }
    assert seen[-1]["email"] == "alfredo@neuri.ai"


def test_new_slice_and_new_reducer_are_active_without_recreating_store():
    original = slice_user({"name": "fredo"})
    store = configure_store({"user": original}, devtools=False)
    new_user = create_slice(
        name="user",
        initial_state={"name": "default"},
        reducers={"set_data": lambda state, action: {"name": action.payload.upper()}},
    )
    settings = create_slice(name="settings", initial_state={"theme": "dark"}, reducers={})
    reconfigure_store(store, {"user": new_user, "settings": settings})
    assert store.get_state()["settings"] == {"theme": "dark"}
    store.dispatch(new_user.actions.set_data("luis"))
    assert store.get_state()["user"]["name"] == "LUIS"
    assert store.get_state()["settings"] == {"theme": "dark"}


def test_invalid_reconfiguration_does_not_damage_live_store():
    user = slice_user({"name": "fredo"})
    store = configure_store({"user": user}, devtools=False)
    try:
        reconfigure_store(store, {"bad": lambda state, action: 1 / 0})
    except ZeroDivisionError:
        pass
    else:
        raise AssertionError("expected malformed slice failure")
    store.dispatch(user.actions.set_data({"name": "safe"}))
    assert store.get_state()["user"]["name"] == "safe"


def test_inspector_snapshot_contains_initial_state_before_actions():
    user = slice_user({"name": "fredo"})
    store = configure_store({"user": user}, devtools=True, inspector_auto_start=False)
    from pydux.devtools.inspector import PyDuxInspectorServer
    inspector = PyDuxInspectorServer(store.devtools, port=0)
    snapshot = inspector._snapshot_payload()
    assert snapshot["history"] == []
    assert snapshot["active_index"] == -1
    assert snapshot["state"] == {"user": {"name": "fredo"}}
