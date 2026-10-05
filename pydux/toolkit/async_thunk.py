"""
create_async_thunk for PyDux 3.0.
Simplifies asynchronous operations (e.g. background data loading,
serial port hardware reads) by automatically dispatching pending,
fulfilled, and rejected action stages.
"""

from typing import Callable, Any, Optional
import asyncio
import inspect
import threading
from pydux.core.types import Action, Middleware


def _resolve_awaitable(result: Any) -> Any:
    """Resolves awaitables for sync dispatch workflows."""
    if not inspect.isawaitable(result):
        return result

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(result)

    # If we're already in an event loop thread, run awaitable in a helper thread.
    output = {"value": None, "error": None}

    def runner() -> None:
        try:
            output["value"] = asyncio.run(result)
        except Exception as exc:  # pragma: no cover - passthrough branch
            output["error"] = exc

    t = threading.Thread(target=runner, daemon=True)
    t.start()
    t.join()

    if output["error"] is not None:
        raise output["error"]
    return output["value"]


class AsyncThunk:
    """Async action dispatcher that orchestrates pending/fulfilled/rejected lifecycle."""

    def __init__(self, type_prefix: str, payload_creator: Callable[..., Any]):
        self.type_prefix = type_prefix
        self.payload_creator = payload_creator
        self.pending = f"{type_prefix}/pending"
        self.fulfilled = f"{type_prefix}/fulfilled"
        self.rejected = f"{type_prefix}/rejected"

    def __call__(self, *args, **kwargs) -> Callable[[Any], Any]:
        """Returns a thunk callable executable by the store dispatch."""
        async_thunk_instance = self

        def thunk_runner(
            dispatch: Callable[[Any], Any],
            get_state: Optional[Callable[[], Any]] = None,
            extra_argument: Any = None,
        ):
            # 1. Dispatch pending action
            dispatch(Action(type=async_thunk_instance.pending, payload=kwargs.get("arg", args[0] if args else None)))

            try:
                # 2. Execute payload creator
                result = async_thunk_instance.payload_creator(*args, **kwargs)
                result = _resolve_awaitable(result)
                # 3. Dispatch fulfilled action
                dispatch(Action(type=async_thunk_instance.fulfilled, payload=result))
                return result
            except Exception as exc:
                # 4. Dispatch rejected action
                dispatch(Action(type=async_thunk_instance.rejected, payload=str(exc), meta={"error": True}))
                raise exc

        return thunk_runner


def create_async_thunk(type_prefix: str, payload_creator: Callable[..., Any]) -> AsyncThunk:
    """
    Creates an async thunk action creator.
    
    Example:
        fetch_sensor_data = create_async_thunk(
            "telemetry/fetchData",
            lambda device_id: serial_port.read_packet(device_id)
        )
        
        # Dispatches:
        # 1. Action("telemetry/fetchData/pending")
        # 2. Action("telemetry/fetchData/fulfilled", result) or rejected on error
    """
    return AsyncThunk(type_prefix=type_prefix, payload_creator=payload_creator)


def create_thunk_middleware(extra_argument: Any = None) -> Middleware:
    """Redux-style thunk middleware for dispatching callables."""

    def enhancer(store: Any, next_dispatch: Callable[[Any], Any]) -> Callable[[Any], Any]:
        def dispatch_wrapper(action: Any) -> Any:
            if callable(action) and not isinstance(action, Action):
                return action(store.dispatch, store.get_state, extra_argument)
            return next_dispatch(action)

        return dispatch_wrapper

    return enhancer
