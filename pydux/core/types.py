"""
Type definitions, Generics, and Protocols for PyDux 3.0.
Works with standard Python dicts, dataclasses, and Pydantic v2 models.
"""

from typing import (
    TypeVar,
    Generic,
    Callable,
    Any,
    Dict,
    Optional,
    Protocol,
    Union,
    Sequence,
)
from dataclasses import dataclass, field
import time

TState = TypeVar("TState")
TResult = TypeVar("TResult")
TSelected = TypeVar("TSelected")


@dataclass(frozen=True)
class Action:
    """Immutable representation of a dispatched state mutation intent."""
    type: str
    payload: Any = None
    meta: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.type or not isinstance(self.type, str):
            raise ValueError("Action.type must be a non-empty string.")


Reducer = Callable[[TState, Action], TState]
Selector = Callable[[TState], TResult]
EqualityFn = Callable[[Any, Any], bool]
Listener = Callable[[TSelected], None]
Unsubscribe = Callable[[], None]
Dispatch = Callable[[Any], Any]
Middleware = Callable[["Any", Dispatch], Dispatch]


class StoreProtocol(Protocol[TState]):
    """Standard store contract."""

    def get_state(self) -> TState:
        ...

    def dispatch(self, action: Any) -> Any:
        ...

    def subscribe(self, listener: Callable[[TState], None]) -> Unsubscribe:
        ...

    def select(
        self,
        selector: Selector[TState, TSelected],
        listener: Listener[TSelected],
        equality_fn: Optional[EqualityFn] = None,
    ) -> Unsubscribe:
        ...
