"""
configure_store for PyDux 3.0.
Simplifies store setup by automatically combining slice reducers,
prepopulating slice states, and enabling PyDuxDevTools by default.
"""

import logging
from typing import Dict, Any, Optional, Sequence, Union
from pydux.core.store import Store
from pydux.core.types import Reducer, Middleware, Action
from pydux.devtools.tracker import PyDuxDevTools, devtools_middleware
from pydux.toolkit.slice import Slice
from pydux.toolkit.async_thunk import create_thunk_middleware


_LOGGER = logging.getLogger("pydux")


def combine_reducers(reducers_dict: Dict[str, Reducer[Any]]) -> Reducer[Dict[str, Any]]:
    """
    Combines multiple slice reducers into a single root reducer.
    Automatically handles @@PYDUX/TIME_TRAVEL for state rollback.
    """
    def root_reducer(state: Optional[Dict[str, Any]] = None, action: Optional[Action] = None) -> Dict[str, Any]:
        if state is None:
            state = {}

        if action is not None and action.type == "@@PYDUX/TIME_TRAVEL":
            # Direct full-state restore for time-travel
            return action.payload

        has_changed = False
        next_state: Dict[str, Any] = {}

        for key, slice_reducer in reducers_dict.items():
            prev_slice = state.get(key, None)
            new_slice = slice_reducer(prev_slice, action)
            next_state[key] = new_slice

            if new_slice is not prev_slice:
                has_changed = True

        return next_state if has_changed or len(state) != len(reducers_dict) else state

    return root_reducer


def configure_store(
    reducer: Union[Reducer[Any], Dict[str, Union[Reducer[Any], Slice]]],
    preloaded_state: Optional[Any] = None,
    middleware: Optional[Sequence[Middleware]] = None,
    devtools: Union[bool, PyDuxDevTools] = True,
    inspector_auto_start: bool = True,
    inspector_host: str = "127.0.0.1",
    inspector_port: int = 8765,
    inspector_log: bool = True,
) -> Store[Any]:
    """
    Configures and creates a PyDux store using the Redux Toolkit pattern.
    
    Args:
        reducer: Either a single root reducer function or a dict of {slice_name: slice.reducer}.
        preloaded_state: Optional initial state override.
        middleware: Optional sequence of custom middleware functions.
        devtools: True (default) creates and binds PyDuxDevTools automatically,
                  or you can pass your own PyDuxDevTools instance, or False to disable.
        inspector_auto_start: If True and devtools are enabled, starts the
                              web inspector server automatically.
        inspector_host: Host interface for the auto-started inspector.
        inspector_port: Preferred inspector port. If occupied, a free port is used.
        inspector_log: Prints inspector startup information to stdout when enabled.
                  
    Returns:
        Configured Store instance. If devtools was enabled, the devtools instance
        is accessible via store.devtools.
    """
    active_devtools: Optional[PyDuxDevTools] = None
    all_middlewares = [create_thunk_middleware()]
    all_middlewares.extend(list(middleware or []))

    # Setup DevTools by default
    if devtools is True:
        active_devtools = PyDuxDevTools()
        all_middlewares.append(devtools_middleware(active_devtools))
    elif isinstance(devtools, PyDuxDevTools):
        active_devtools = devtools
        all_middlewares.append(devtools_middleware(active_devtools))

    # If a dict of reducers is provided, combine them and compute initial state
    if isinstance(reducer, dict):
        reducers_dict: Dict[str, Reducer[Any]] = {
            key: value.reducer if isinstance(value, Slice) else value
            for key, value in reducer.items()
        }
        root_reducer = combine_reducers(reducers_dict)
        # Compute combined initial state by running each slice reducer with dummy action
        computed_initial: Dict[str, Any] = {}
        for key, slice_reducer in reducers_dict.items():
            computed_initial[key] = slice_reducer(None, Action(type="@@PYDUX/INIT"))

        if preloaded_state and isinstance(preloaded_state, dict):
            computed_initial.update(preloaded_state)

        initial_state = computed_initial
    else:
        root_reducer = reducer
        initial_state = preloaded_state if preloaded_state is not None else root_reducer(None, Action(type="@@PYDUX/INIT"))

    store = Store(reducer=root_reducer, initial_state=initial_state, middlewares=all_middlewares)

    # Attach devtools instance attribute if active
    if active_devtools:
        setattr(store, "devtools", active_devtools)

        if inspector_auto_start:
            try:
                from pydux.devtools.inspector import start_inspector

                inspector = start_inspector(
                    store,
                    host=inspector_host,
                    port=inspector_port,
                    auto_reassign_port=True,
                    log_startup=inspector_log,
                )
                setattr(store, "inspector", inspector)
            except Exception:
                _LOGGER.exception(
                    "Failed to auto-start the PyDux inspector. "
                    "Store was created with devtools active."
                )

    return store
