"""Contract tests for Pydux's optional PSX adapter."""

from __future__ import annotations

import threading
from collections.abc import Callable

import pytest

from pydux import Action, Store, StoreProvider, use_dispatch, use_selector
from psx import Button, Fragment, PSXError, Text, component
from psx.core.reconcile import Reconciler
from psx.renderers.headless import HeadlessRenderer


def reducer(state: dict[str, int], action: Action) -> dict[str, int]:
    if action.type == "increment":
        return {**state, "count": state["count"] + 1}
    if action.type == "other":
        return {**state, "other": state["other"] + 1}
    return state


class RecordingStore:
    def __init__(self, store: Store[dict[str, int]]) -> None:
        self.store = store
        self.unsubscribe_calls = 0

    def get_state(self) -> dict[str, int]:
        return self.store.get_state()

    def dispatch(self, action: object) -> object:
        return self.store.dispatch(action)

    def select(self, *args: object, **kwargs: object) -> Callable[[], None]:
        unsubscribe = self.store.select(*args, **kwargs)  # type: ignore[arg-type]

        def tracked() -> None:
            self.unsubscribe_calls += 1
            unsubscribe()

        return tracked


class RecordingInspector:
    def __init__(self) -> None:
        self.stops = 0

    def stop(self) -> None:
        self.stops += 1


@pytest.fixture
def mounted() -> tuple[Reconciler, HeadlessRenderer, Store[dict[str, int]]]:
    renderer = HeadlessRenderer()
    reconciler = Reconciler(renderer)
    store = Store(reducer, {"count": 0, "other": 0})
    yield reconciler, renderer, store
    reconciler.unmount()


def test_provider_dispatch_and_selector_update_on_scheduler_flush(mounted: tuple[Reconciler, HeadlessRenderer, Store[dict[str, int]]]) -> None:
    reconciler, renderer, store = mounted

    @component
    def Counter():
        count = use_selector(lambda state: state["count"])
        dispatch = use_dispatch()
        return Button(str(count), on_click=lambda: dispatch(Action("increment")))

    root = reconciler.render(StoreProvider(store, Counter()))
    label = root.children[0].children[0].handle
    label.events["on_click"].invoke()
    assert label.props["label"] == "0"
    renderer.flush()
    assert label.props["label"] == "1"


def test_only_changed_selector_rerenders(mounted: tuple[Reconciler, HeadlessRenderer, Store[dict[str, int]]]) -> None:
    reconciler, renderer, store = mounted
    renders = {"count": 0, "other": 0}

    @component
    def Count():
        renders["count"] += 1
        return Text(str(use_selector(lambda state: state["count"])))

    @component
    def Other():
        renders["other"] += 1
        return Text(str(use_selector(lambda state: state["other"])))

    reconciler.render(StoreProvider(store, Fragment(Count(), Other())))
    store.dispatch(Action("increment"))
    renderer.flush()
    assert renders == {"count": 2, "other": 1}


def test_unmount_unsubscribes_and_stops_final_inspector(mounted: tuple[Reconciler, HeadlessRenderer, Store[dict[str, int]]]) -> None:
    reconciler, _, store = mounted
    recording = RecordingStore(store)
    inspector = RecordingInspector()
    recording.inspector = inspector

    @component
    def Counter():
        return Text(str(use_selector(lambda state: state["count"])))

    reconciler.render(StoreProvider(recording, Counter()))
    reconciler.unmount()
    reconciler.unmount()
    assert recording.unsubscribe_calls == 1
    assert inspector.stops == 1


def test_worker_dispatch_waits_for_renderer_scheduler(mounted: tuple[Reconciler, HeadlessRenderer, Store[dict[str, int]]]) -> None:
    reconciler, renderer, store = mounted

    @component
    def Counter():
        return Text(str(use_selector(lambda state: state["count"])))

    root = reconciler.render(StoreProvider(store, Counter()))
    label = root.children[0].children[0].handle
    worker = threading.Thread(target=lambda: store.dispatch(Action("increment")))
    worker.start()
    worker.join()
    assert label.props["value"] == "0"
    renderer.flush()
    assert label.props["value"] == "1"


def test_hooks_require_explicit_provider(mounted: tuple[Reconciler, HeadlessRenderer, Store[dict[str, int]]]) -> None:
    reconciler, _, _ = mounted

    @component
    def Invalid():
        return Text(str(use_selector(lambda state: state["count"])))

    with pytest.raises(PSXError):
        reconciler.render(Invalid())
