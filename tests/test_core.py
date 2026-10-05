import pytest

from pydux import Action, Store, create_selector, deep_equal, is_identical, shallow_equal


def increment_reducer(state, action):
    if action.type == "increment":
        return {**state, "count": state["count"] + action.payload}
    return state


def test_action_requires_a_non_empty_string_type():
    with pytest.raises(ValueError):
        Action("")
    with pytest.raises(ValueError):
        Action(None)  # type: ignore[arg-type]


def test_store_dispatches_actions_and_returns_the_action():
    store = Store(increment_reducer, {"count": 0})
    action = Action("increment", 2)

    assert store.dispatch(action) is action
    assert store.get_state() == {"count": 2}


def test_store_rejects_non_actions_without_thunk_middleware():
    store = Store(increment_reducer, {"count": 0})

    with pytest.raises(TypeError, match="expected an Action"):
        store.dispatch(lambda: None)


def test_select_notifies_only_when_the_selected_value_changes():
    store = Store(increment_reducer, {"count": 0, "name": "Ada"})
    observed = []
    store.select(lambda state: state["name"], observed.append)

    store.dispatch(Action("increment", 1))

    assert observed == []


def test_select_can_fire_immediately_and_unsubscribe():
    store = Store(increment_reducer, {"count": 0})
    observed = []
    unsubscribe = store.select(lambda state: state["count"], observed.append, fire_immediately=True)

    store.dispatch(Action("increment", 1))
    unsubscribe()
    store.dispatch(Action("increment", 1))

    assert observed == [0, 1]


def test_subscriber_exceptions_do_not_break_dispatch():
    store = Store(increment_reducer, {"count": 0})
    store.select(lambda state: state["count"], lambda _: (_ for _ in ()).throw(RuntimeError("boom")))

    store.dispatch(Action("increment", 1))

    assert store.get_state() == {"count": 1}


def test_subscribe_receives_every_dispatch_even_when_state_is_unchanged():
    store = Store(increment_reducer, {"count": 0})
    states = []
    store.subscribe(states.append)

    store.dispatch(Action("unknown"))
    store.dispatch(Action("increment", 1))

    assert states == [{"count": 0}, {"count": 1}]


def test_equality_helpers_cover_identity_shallow_and_deep_values():
    same = {"a": [1, 2]}
    assert is_identical(same, same)
    assert not is_identical({"a": 1}, {"a": 1})
    assert shallow_equal({"a": 1}, {"a": 1})
    assert not shallow_equal({"a": 1}, {"a": 2})
    assert deep_equal({"a": {"b": [1]}}, {"a": {"b": [1]}})


def test_memoized_selector_recomputes_only_when_inputs_change():
    calls = []
    selector = create_selector(lambda state: state["count"], lambda count: calls.append(count) or count * 2)

    assert selector({"count": 2}) == 4
    assert selector({"count": 2, "other": True}) == 4
    assert selector({"count": 3}) == 6
    assert selector.recomputations == 2
    assert calls == [2, 3]


def test_create_selector_requires_an_input_and_result_function():
    with pytest.raises(ValueError, match="at least one"):
        create_selector(lambda state: state)
