# pydux

PyDux is a Redux Toolkit-inspired state container for Python desktop apps.

- `create_slice` generates a reducer and its action creators from one definition.
- `configure_store` builds the store and composes the slice reducers.
- `store.select(...)` subscribes to a derived value and notifies you only when it changes.
- `create_async_thunk` models async work as `pending` / `fulfilled` / `rejected` actions.
- Optional DevTools record every dispatch and support time travel, with a live web inspector.
- Adapters connect the store to Qt, Tkinter, Kivy and Qyro without tying the core to any of them.

> **Breaking changes (RTK style).** Use `configure_store(...)` instead of the legacy `create_store(...)`
> and `create_slice(...)` for reducer/action colocation. Action types follow `slice_name/action_name`
> (for example `cart/add_item`). No backward compatibility is guaranteed for pre-RTK patterns.

## Contents

- [Install](#install)
- [Quickstart](#quickstart)
- [How it works](#how-it-works)
- [Async thunks](#async-thunks)
- [DevTools and time travel](#devtools-and-time-travel)
- [Binding the store to a UI](#binding-the-store-to-a-ui)
- [Examples](#examples)
- [Dependencies](#dependencies)
- [Benchmarking](#benchmarking)
- [API reference](#api-reference)

## Install

```bash
pip install -e .
```

Run it from the source root (`pydux/`) to install the local package in editable mode.

## Quickstart

```python
from pydux import create_slice, configure_store, create_selector

counter_slice = create_slice(
    name="counter",
    initial_state={"value": 0},
    reducers={
        "increment": lambda state, action: state.update({"value": state["value"] + 1}),
        "decrement": lambda state, action: state.update({"value": state["value"] - 1}),
    },
)

store = configure_store(reducer={"counter": counter_slice}, devtools=True)

select_value = lambda s: s["counter"]["value"]
select_label = create_selector(select_value, lambda v: f"Counter={v}")

def on_counter_change(label: str):
    print("changed:", label)

unsubscribe = store.select(select_label, on_counter_change, fire_immediately=True)

store.dispatch(counter_slice.actions.increment())
store.dispatch(counter_slice.actions.increment())
store.dispatch(counter_slice.actions.decrement())

unsubscribe()
```

## How it works

PyDux has one source of truth, the **store**, and one way to change it: **dispatching actions**.

```
dispatch(action)
     │
     ▼
 middleware ──(thunk: callables are run, not reduced)
     │
     ▼
  reducers ──► new state
     │
     ▼
 selectors re-evaluated ──► only listeners whose value changed are called
     │
     ▼
 DevTools trace recorded (if enabled)
```

### State

The store state is a dictionary with one key per slice. In the quickstart it looks like this:

```python
{"counter": {"value": 2}}
```

Read it with `store.get_state()`. Anything that needs to react to changes should use
[selectors](#selectors-and-selective-subscriptions) instead of reading the state manually.

### Actions

An action describes what happened. It has a `type` and an optional `payload`:

```python
action = counter_slice.actions.increment()
action.type      # "counter/increment"
action.payload   # None
```

Action creators are generated for you by `create_slice`; you rarely build an `Action` by hand.

### Slices

`create_slice` takes a `name`, an `initial_state` and a `reducers` mapping. For each entry it produces:

- a reducer branch that handles the action type `"<name>/<reducer_key>"`;
- an action creator at `slice.actions.<reducer_key>`.

A reducer receives `(state, action)` and, as in the examples, updates the slice state in place
(`state.update(...)`), the same way Redux Toolkit reducers read.

`extra_reducers` handles action types that belong to someone else, such as the actions emitted by a thunk
(see [Async thunks](#async-thunks)). Its keys are full action type strings.

### The store

`configure_store(reducer={...})` combines the slices under their keys and installs the thunk middleware
by default. Pass `devtools=True` to record every dispatch.

```python
store = configure_store(
    reducer={"counter": counter_slice, "user": user_slice},
    devtools=True,
)

store.dispatch(counter_slice.actions.increment())
store.get_state()   # {"counter": {...}, "user": {...}}
```

`combine_reducers` is exported if you want to compose reducers yourself.

### Selectors and selective subscriptions

A selector is a function `state -> value`. `store.select` subscribes to what a selector returns:

```python
unsubscribe = store.select(
    selector,
    listener,
    equality_fn=None,
    fire_immediately=False,
)
```

After every dispatch PyDux evaluates each registered selector and compares the new value with the previous
one using `equality_fn`. The listener runs **only if the value changed**. A UI that shows the user name does
not repaint when the counter changes.

| Parameter | Meaning |
| --- | --- |
| `selector` | Function `state -> value`. |
| `listener` | Called with the new selected value. |
| `equality_fn` | Decides whether two values are the same. Pass one of the helpers below or your own. |
| `fire_immediately` | When `True`, the listener is called once with the current value at subscription time. |

Equality helpers exported by `pydux`:

| Helper | Compares |
| --- | --- |
| `is_identical` | Object identity (`is`). Cheapest. |
| `shallow_equal` | The top level of a container, item by item. |
| `deep_equal` | Nested structures recursively. Most expensive. |

Choose the cheapest one that is correct for what your selector returns. A selector that builds a new
dict on every call will never be identical to the previous value, so give it `shallow_equal` or
`deep_equal`.

`create_selector(*inputs, combiner)` builds a derived selector from other selectors, as in the quickstart:

```python
select_label = create_selector(select_value, lambda v: f"Counter={v}")
```

`store.select(...)` returns an unsubscribe function. Call it when the listener is no longer needed.

## Async thunks

`configure_store` installs thunk middleware, so you can dispatch callables as well as actions.
`create_async_thunk` builds one from a type prefix and a function:

```python
from pydux import create_slice, create_async_thunk, configure_store

jobs_slice = create_slice(
    name="jobs",
    initial_state={"status": "idle", "result": None, "error": None},
    reducers={},
    extra_reducers={
        "jobs/fetch/pending": lambda s, a: s.update({"status": "loading", "error": None}),
        "jobs/fetch/fulfilled": lambda s, a: s.update({"status": "ok", "result": a.payload}),
        "jobs/fetch/rejected": lambda s, a: s.update({"status": "error", "error": a.payload}),
    },
)

fetch_jobs = create_async_thunk("jobs/fetch", lambda: ["compile", "test", "release"])
store = configure_store(reducer={"jobs": jobs_slice})

store.dispatch(fetch_jobs())
```

Dispatching the thunk produces up to three regular actions, built from the prefix you gave it:

| Action type | When | Payload |
| --- | --- | --- |
| `jobs/fetch/pending` | The thunk starts. | none |
| `jobs/fetch/fulfilled` | The function returned a value. | the returned value |
| `jobs/fetch/rejected` | The function raised. | the error information |

Handle them in `extra_reducers`, as above. `create_thunk_middleware` is exported if you need to
install the middleware manually.

## DevTools and time travel

With `devtools=True` the store records a **trace** for each dispatch. `store.devtools` exposes:

| Member | Purpose |
| --- | --- |
| `history` | The list of recorded traces. |
| `undo()` / `redo()` | Step backward or forward through the history. |
| `jump_to_state(index)` | Move to the state recorded at a given trace. |

Each trace contains:

| Field | Meaning |
| --- | --- |
| `index` | Position in the history. |
| `action` | The dispatched action (`type`, `payload`). |
| `timestamp` | When it was dispatched. |
| `duration_ms` | Time spent processing it. |
| `changed_paths` | The parts of the state that changed. |
| `prev_state` / `next_state` | Snapshots before and after. |

Snapshots are deep copies, so tracing has a cost; see [Benchmarking](#benchmarking).

### Inspector (web dashboard)

The inspector is an optional local HTTP server that works with any UI framework
(Qyro, PyQt, PySide, Tkinter, Kivy). It lists every recorded action and lets you view the state diff, the
full state and the payload of each one, and drive undo, redo, jump and replay from the browser.

```python
from pydux import configure_store

store = configure_store(
    reducer={"counter": counter_slice},
    devtools=True,
)

# configure_store auto-starts the inspector when devtools=True
print("Inspector:", store.inspector.base_url)
```

When `devtools=True`, PyDux tries to start the inspector on `127.0.0.1:8765`.
If that port is occupied, it automatically falls back to a free port and prints the final URL in the terminal.

You can still start it manually when you need custom host/port control:

```python
from pydux import start_inspector

inspector = start_inspector(
    store,
    host="127.0.0.1",
    port=9900,
    auto_reassign_port=True,
)
```

Open `store.inspector.base_url` (or `inspector.base_url`) in your browser. The page updates live over Server-Sent Events.
The UI files live in `pydux/devtools/static/`.

#### Where to place inspector setup

- Recommended: let `configure_store(..., devtools=True)` auto-start it where the store is created.
- Reason: there is one inspector per store, and startup/logging happens once.
- App shutdown: if you need explicit cleanup, call `store.inspector.stop()` when your process exits.

| Endpoint | Description |
| --- | --- |
| `GET /health` | Liveness check. |
| `GET /api/traces` | Recorded traces and the active index. |
| `GET /api/state` | Current store state. |
| `POST /api/undo` | Undo one step. |
| `POST /api/redo` | Redo one step. |
| `POST /api/jump` | Jump to a trace. Body: `{"index": <int>}`. |
| `GET /api/events` | SSE stream with `snapshot` and `trace` events. |

## Binding the store to a UI

The core knows nothing about GUI toolkits. Adapters subscribe to the store and push values into widgets.

### Threads and the main-thread bridge

GUI toolkits only allow widget updates from the main thread, but a dispatch can happen anywhere
(for example inside an async thunk). The base adapter defines a small protocol for that:

```python
class MainThreadBridge(Protocol):
    def schedule_on_main_thread(self, fn: Callable[[], None]) -> None: ...
```

`DirectThreadBridge` runs the function immediately and is the default for tests and synchronous code.
Each toolkit adapter provides a bridge that schedules work on its own main loop.

### `ReactiveBinding`

Connects one selector to one callback, such as a widget setter:

```python
from pydux import ReactiveBinding

binding = ReactiveBinding(
    store=store,
    selector=lambda s: s["user"]["name"],
    target=lambda name: label.config(text=name),
    bridge=TkinterBridge(root),   # the bridge for your toolkit
)

# later
binding.dispose()
```

It subscribes with `fire_immediately=True`, so the target receives the current value right away,
and `dispose()` removes the subscription.

### `connect`

A class decorator that injects several values at once:

```python
from pydux.adapters.base import connect

@connect(store, map_state_to_props=lambda s: {"name": s["user"]["name"], "count": s["counter"]["value"]})
class Panel:
    def on_props_changed(self):
        ...  # self.name and self.count are up to date
```

The selected values are set as attributes on the instance, and `on_props_changed()` is called if you define it.

### Qyro

The Qyro adapter follows the Qyro component lifecycle. Subscribe in `component_will_mount`; widgets are
created later in `render()`, so the first value is delivered on the next Qt tick instead of immediately.

```python
from PySide6.QtWidgets import QMainWindow, QLabel
from qyro import ApplicationContext
from qyro.ui.component import Component
from pydux.adapters.qyro import Reactive

class App(QMainWindow, Component, Reactive, ApplicationContext):
    def component_will_mount(self):
        self.bind_selector(store, select_header, self._on_header_change)

    def render(self):
        self._label = QLabel(parent=self)

    def _on_header_change(self, text: str) -> None:
        self._label.setText(text)
```

`bind_selector` returns an unsubscribe function and also tracks every subscription it creates, so they can be
released together in `component_will_unmount`.

To map several selectors to attributes, use the `connect_qyro` decorator:

```python
from pydux.adapters.qyro import connect_qyro

@connect_qyro(store, {"header": select_header, "count": select_count})
class Panel(QWidget, Component):
    def on_state_change(self, props: dict) -> None:
        ...  # called with all connected values after each change
```

Each selector is tracked on its own, so a component is only notified about the values it selected.

## Examples

All demos live under `examples/` and follow a `store/slices` structure.

| Demo | Path | Run |
| --- | --- | --- |
| Qyro (settings and resources included) | `examples/qyro_app/` | `python main.py` |
| PyQt6 | `examples/pyqt6_app/` | `python main.py` |
| PyQt5 | `examples/pyqt5_app/` | `python main.py` |
| Kivy | `examples/kivy_app/` | `python main.py` |
| Tkinter | `examples/tkinter_app/` | `python main.py` |

Run each one from inside its own directory. The Qyro example also contains `settings/` for the base and
per-platform configuration (`base.json`, `windows.json`, `mac.json`, `linux.json`) and `resources/` for icons.

## Dependencies

The core has no GUI dependency. Install the toolkit you want to use:

- PyQt6 demo: `pip install PyQt6`
- PyQt5 demo: `pip install PyQt5`
- Kivy demo: `pip install kivy`
- Qyro demo: install `qyro` and a compatible Qt binding (`PySide6` for this sample)

Tkinter usually ships with standard CPython distributions.

## Benchmarking

DevTools tracing (`devtools=True`) captures deep snapshots and state diffs on every dispatch.
To measure its cost, compare at least:

- Core only (`devtools=False`)
- Core + DevTools (`devtools=True`)

## API reference

### `create_slice(name, initial_state, reducers, extra_reducers=None) -> Slice`

Creates a slice with colocated reducer logic and action creators.

| Parameter | Type | Description |
| --- | --- | --- |
| `name` | `str` | Slice namespace used in action types (`name/reducer_key`). |
| `initial_state` | `Any` | Initial value for the slice. |
| `reducers` | `dict[str, Callable[[state, action], None]]` | Local reducer handlers that mutate slice state. |
| `extra_reducers` | `dict[str, Callable[[state, action], None]]` | Optional handlers keyed by full external action type. |

`Slice` instance members:

| Member | Type | Description |
| --- | --- | --- |
| `name` | `str` | Slice name. |
| `reducer` | `Callable` | Reducer function compatible with `configure_store`. |
| `actions` | object | Generated action creators (`slice.actions.some_action(payload=None)`). |

### `configure_store(...) -> Store`

Signature:

```python
configure_store(
    reducer,
    preloaded_state=None,
    middleware=None,
    devtools=True,
    inspector_auto_start=True,
    inspector_host="127.0.0.1",
    inspector_port=8765,
    inspector_log=True,
)
```

| Parameter | Type | Description |
| --- | --- | --- |
| `reducer` | `Reducer` or `dict[str, Reducer | Slice]` | Root reducer or per-slice reducer map. |
| `preloaded_state` | `Any \\| None` | Optional initial state override. |
| `middleware` | `Sequence[Middleware] \\| None` | Extra middleware appended after thunk middleware. |
| `devtools` | `bool \\| PyDuxDevTools` | Enables built-in tracing (`True`), custom tracker instance, or disabled (`False`). |
| `inspector_auto_start` | `bool` | Auto-starts web inspector if devtools are active. |
| `inspector_host` | `str` | Inspector bind host for auto-start mode. |
| `inspector_port` | `int` | Preferred inspector port. |
| `inspector_log` | `bool` | Prints startup URL in terminal when inspector starts. |

Store attributes added by `configure_store`:

| Attribute | Exists when | Description |
| --- | --- | --- |
| `store.devtools` | `devtools` enabled | `PyDuxDevTools` instance used by middleware. |
| `store.inspector` | `devtools` and `inspector_auto_start` enabled | `PyDuxInspectorServer` instance with `base_url`. |

Port behavior: if `inspector_port` is occupied and auto-start is enabled, PyDux picks a free port automatically.

### `Store`

Main methods:

| Method | Description |
| --- | --- |
| `get_state()` | Returns current full state. |
| `dispatch(action_or_thunk)` | Dispatches actions (and callables when thunk middleware is installed). |
| `select(selector, listener, equality_fn=None, fire_immediately=False)` | Selective subscription; listener runs only when selected value changes. |
| `subscribe(listener)` | Full-state subscription (always notified after dispatch). |

`select(...)` returns an `unsubscribe()` function.

### `create_selector(*inputs, combiner)`

Builds a derived selector from one or more input selectors and a combiner function.

### Equality helpers

| Helper | Description |
| --- | --- |
| `is_identical(a, b)` | Identity comparison (`is`). |
| `shallow_equal(a, b)` | Top-level comparison for container values. |
| `deep_equal(a, b)` | Recursive nested comparison. |

### Async thunks

| API | Description |
| --- | --- |
| `create_async_thunk(type_prefix, payload_creator)` | Generates thunk creator that emits `pending/fulfilled/rejected` actions. |
| `create_thunk_middleware()` | Middleware factory; already installed by `configure_store`. |

### DevTools APIs

`PyDuxDevTools` methods/properties:

| Member | Description |
| --- | --- |
| `history` | Returns recorded action traces. |
| `undo()` / `redo()` | Time-travel navigation. |
| `jump_to_state(index)` | Jumps to a specific trace state. |
| `export_trace_json()` | Exports current trace list as JSON string. |

`start_inspector(store, host="127.0.0.1", port=8765, auto_reassign_port=True, log_startup=True)`:

- Starts (or reuses) a `PyDuxInspectorServer` for stores that expose `store.devtools`.
- If the preferred port is busy and `auto_reassign_port=True`, falls back to a free port.
- Returns `PyDuxInspectorServer` with properties `host`, `port`, `base_url` and method `stop()`.

### UI adapter APIs

| API | Description |
| --- | --- |
| `ReactiveBinding(store, selector, target, bridge=...)` | Binds selector output to a UI callback with main-thread scheduling. |
| `connect(store, map_state_to_props, equality_fn=...)` | Decorator that injects selected props into class instances. |
| `Reactive` | Qyro mixin with `bind_selector(...)` and auto-unsubscribe on unmount. |
| `connect_qyro(store, selectors)` | Qyro decorator that maps selectors to component attributes and optional `on_state_change`. |