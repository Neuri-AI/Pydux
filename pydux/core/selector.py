"""
Memoized Selectors for PyDux 3.0.
Prevents re-computations and guarantees components are only notified
when their exact targeted slice of state actually changes.
"""

from typing import (
    Callable,
    Sequence,
    Any,
    Tuple,
    TypeVar,
    cast,
    Dict,
    Optional,
)
import functools

TState = TypeVar("TState")
TResult = TypeVar("TResult")


def is_identical(a: Any, b: Any) -> bool:
    """Referential identity comparator."""
    return a is b


def shallow_equal(a: Any, b: Any) -> bool:
    """
    Shallow equality comparison supporting dicts, lists, tuples,
    dataclasses, and Pydantic models.
    """
    if a is b:
        return True
    if a is None or b is None:
        return a == b

    # If dicts
    if isinstance(a, dict) and isinstance(b, dict):
        if len(a) != len(b):
            return False
        for key, val in a.items():
            if key not in b or b[key] != val:
                return False
        return True

    # If sequences (list, tuple)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) != len(b):
            return False
        return all(x == y for x, y in zip(a, b))

    # Fallback to standard equality
    try:
        return bool(a == b)
    except Exception:
        return False


def deep_equal(a: Any, b: Any) -> bool:
    """Deep structural equality fallback."""
    return a == b


class MemoizedSelector:
    """Wrapper that wraps input selectors and caches computation result."""

    def __init__(
        self,
        input_selectors: Sequence[Callable[[Any], Any]],
        result_fn: Callable[..., Any],
        equality_fn: Callable[[Any, Any], bool] = shallow_equal,
    ):
        self._input_selectors = list(input_selectors)
        self._result_fn = result_fn
        self._equality_fn = equality_fn
        self._last_inputs: Optional[Tuple[Any, ...]] = None
        self._last_result: Any = None
        self._recomputations: int = 0

    def __call__(self, state: Any) -> Any:
        current_inputs = tuple(s(state) for s in self._input_selectors)

        if self._last_inputs is not None:
            # Check if all input slices are equal according to equality_fn
            if len(self._last_inputs) == len(current_inputs) and all(
                self._equality_fn(prev, curr)
                for prev, curr in zip(self._last_inputs, current_inputs)
            ):
                return self._last_result

        # Recompute
        self._last_inputs = current_inputs
        self._last_result = self._result_fn(*current_inputs)
        self._recomputations += 1
        return self._last_result

    @property
    def recomputations(self) -> int:
        """Returns the number of times the computation function ran."""
        return self._recomputations

    def reset_recomputations(self) -> None:
        self._recomputations = 0


def create_selector(
    *args: Any,
    equality_fn: Callable[[Any, Any], bool] = shallow_equal,
) -> Callable[[Any], Any]:
    """
    Creates a memoized selector (Reselect style).
    
    Usage:
        select_cart_items = lambda state: state["cart"]["items"]
        select_discount = lambda state: state["cart"]["discount"]
        
        select_total = create_selector(
            select_cart_items,
            select_discount,
            lambda items, discount: sum(i["price"] * i["qty"] for i in items) * (1 - discount)
        )
    """
    if len(args) < 2:
        raise ValueError("create_selector requires at least one input selector and one result function.")

    input_selectors = args[:-1]
    result_fn = args[-1]

    # If first argument is a list or tuple of selectors
    if len(input_selectors) == 1 and isinstance(input_selectors[0], (list, tuple)):
        input_selectors = input_selectors[0]

    return MemoizedSelector(input_selectors, result_fn, equality_fn=equality_fn)
