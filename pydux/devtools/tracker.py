"""
State Tracking & Time-Travel Debugger Addon for PyDux 3.0.
Captures action history, state transitions, diff calculation,
and provides full undo/redo and time-travel replay.
"""

from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
import time
import json
import copy
from pydux.core.types import Action, Middleware, Dispatch


@dataclass
class ActionTrace:
    index: int
    action: Action
    prev_state: Any
    next_state: Any
    timestamp: float
    duration_ms: float
    changed_paths: List[str] = field(default_factory=list)


def compute_state_diff(prev: Any, curr: Any, path: str = "") -> List[str]:
    """Recursively computes paths that changed between two states."""
    diffs = []
    if prev is curr:
        return diffs

    if isinstance(prev, dict) and isinstance(curr, dict):
        all_keys = set(prev.keys()) | set(curr.keys())
        for k in all_keys:
            sub_path = f"{path}.{k}" if path else str(k)
            if k not in prev:
                diffs.append(f"+{sub_path}")
            elif k not in curr:
                diffs.append(f"-{sub_path}")
            elif prev[k] != curr[k]:
                if isinstance(prev[k], dict) and isinstance(curr[k], dict):
                    diffs.extend(compute_state_diff(prev[k], curr[k], sub_path))
                else:
                    diffs.append(f"~{sub_path}")
    elif prev != curr:
        diffs.append(path or "root")

    return diffs


class PyDuxDevTools:
    """
    Central inspector engine for monitoring state transitions and time-traveling.
    """

    def __init__(self, max_history: int = 100):
        self._max_history = max_history
        self._history: List[ActionTrace] = []
        self._current_index: int = -1
        self._store = None
        self._listeners: List[Callable[[ActionTrace], None]] = []

    def set_store(self, store: Any) -> None:
        self._store = store

    def add_trace(self, trace: ActionTrace) -> None:
        if len(self._history) >= self._max_history:
            self._history.pop(0)

        self._history.append(trace)
        self._current_index = len(self._history) - 1

        for listener in self._listeners:
            listener(trace)

    def subscribe_traces(self, listener: Callable[[ActionTrace], None]) -> Callable[[], None]:
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    @property
    def history(self) -> List[ActionTrace]:
        return list(self._history)

    def jump_to_state(self, index: int) -> None:
        """Time travels to state at given history index."""
        if 0 <= index < len(self._history) and self._store:
            target_trace = self._history[index]
            self._current_index = index
            # Dispatch synthetic time-travel action
            self._store.dispatch(
                Action(type="@@PYDUX/TIME_TRAVEL", payload=target_trace.next_state)
            )

    def undo(self) -> None:
        if self._current_index > 0:
            self.jump_to_state(self._current_index - 1)

    def redo(self) -> None:
        if self._current_index < len(self._history) - 1:
            self.jump_to_state(self._current_index + 1)

    def export_trace_json(self) -> str:
        """Serializes current trace history for diagnostic reporting."""
        serializable = []
        for t in self._history:
            serializable.append({
                "index": t.index,
                "action": {"type": t.action.type, "payload": str(t.action.payload)},
                "timestamp": t.timestamp,
                "duration_ms": t.duration_ms,
                "changed_paths": t.changed_paths,
            })
        return json.dumps(serializable, indent=2)


def devtools_middleware(devtools: PyDuxDevTools) -> Middleware:
    """Middleware that intercepts all dispatched actions and records traces."""
    def enhancer(store: Any, next_dispatch: Dispatch) -> Dispatch:
        devtools.set_store(store)

        def dispatch_wrapper(action: Action) -> Action:
            # Bypass recording for internal time-travel replays
            if action.type == "@@PYDUX/TIME_TRAVEL":
                return next_dispatch(action)

            prev_state = copy.deepcopy(store.get_state())
            t0 = time.perf_counter()

            result = next_dispatch(action)

            duration = (time.perf_counter() - t0) * 1000.0
            next_state = store.get_state()
            diffs = compute_state_diff(prev_state, next_state)

            trace = ActionTrace(
                index=len(devtools.history),
                action=action,
                prev_state=prev_state,
                next_state=copy.deepcopy(next_state),
                timestamp=time.time(),
                duration_ms=duration,
                changed_paths=diffs,
            )
            devtools.add_trace(trace)
            return result

        return dispatch_wrapper

    return enhancer
