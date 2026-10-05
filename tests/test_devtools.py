import json
import urllib.error
import urllib.request

import pytest

from pydux import configure_store, create_slice, start_inspector
from pydux.devtools.tracker import PyDuxDevTools, compute_state_diff


def make_store(*, devtools=True, auto_start=False):
    counter = create_slice(
        "counter",
        {"value": 0},
        {"add": lambda state, action: state.update(value=state["value"] + action.payload)},
    )
    return configure_store({"counter": counter}, devtools=devtools, inspector_auto_start=auto_start), counter


def test_compute_state_diff_marks_additions_removals_and_changes():
    assert set(compute_state_diff({"a": 1, "nested": {"x": 1}}, {"b": 2, "nested": {"x": 2}})) == {
        "-a", "+b", "~nested.x"
    }


def test_devtools_records_history_and_supports_time_travel():
    store, counter = make_store()
    store.dispatch(counter.actions.add(1))
    store.dispatch(counter.actions.add(2))

    assert [trace.changed_paths for trace in store.devtools.history] == [["~counter.value"], ["~counter.value"]]
    assert store.get_state()["counter"]["value"] == 3

    store.devtools.undo()
    assert store.get_state()["counter"]["value"] == 1
    store.devtools.redo()
    assert store.get_state()["counter"]["value"] == 3
    assert len(store.devtools.history) == 2


def test_devtools_honours_history_limit_notifies_listeners_and_exports_json():
    tools = PyDuxDevTools(max_history=1)
    observed = []
    unsubscribe = tools.subscribe_traces(lambda trace: observed.append(trace.index))
    store, counter = make_store(devtools=tools)

    store.dispatch(counter.actions.add(1))
    store.dispatch(counter.actions.add(1))
    unsubscribe()
    store.dispatch(counter.actions.add(1))

    assert len(tools.history) == 1
    assert observed == [0, 1]
    assert json.loads(tools.export_trace_json())[0]["action"]["type"] == "counter/add"


def request_json(url, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=2) as response:
        return response.status, json.loads(response.read())


def test_inspector_exposes_state_traces_and_controls():
    store, counter = make_store()
    inspector = start_inspector(store, port=0, log_startup=False)
    try:
        store.dispatch(counter.actions.add(3))
        status, health = request_json(f"{inspector.base_url}/health")
        _, traces = request_json(f"{inspector.base_url}/api/traces")
        _, state = request_json(f"{inspector.base_url}/api/state")
        request_json(f"{inspector.base_url}/api/jump", method="POST", body={"index": 0})

        assert status == 200 and health == {"ok": True}
        assert traces["count"] == 1
        assert state["state"]["counter"]["value"] == 3
        assert store.get_state()["counter"]["value"] == 3
    finally:
        inspector.stop()


def test_inspector_rejects_bad_jump_requests_and_requires_devtools():
    store, _ = make_store()
    inspector = start_inspector(store, port=0, log_startup=False)
    try:
        with pytest.raises(urllib.error.HTTPError) as error:
            request_json(f"{inspector.base_url}/api/jump", method="POST", body={"index": "zero"})
        assert error.value.code == 400
    finally:
        inspector.stop()

    without_tools, _ = make_store(devtools=False)
    with pytest.raises(ValueError, match="requires store.devtools"):
        start_inspector(without_tools, port=0, log_startup=False)
