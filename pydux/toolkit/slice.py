"""
Redux Toolkit style create_slice for PyDux 3.0.
Generates action creators and slice reducers automatically.
Supports Immer-style apparent mutation (draft state modification) or returning new state.
"""

from typing import Dict, Any, Callable, Optional, Union
import copy
from pydux.core.types import Action, Reducer


class ActionCreator:
    """Callable action creator producing typed Action instances."""

    def __init__(self, action_type: str):
        self.type = action_type

    def __call__(self, payload: Any = None, **kwargs) -> Action:
        meta = kwargs.get("meta", {})
        return Action(type=self.type, payload=payload, meta=meta)

    def __repr__(self) -> str:
        return f"<ActionCreator type='{self.type}'>"


class ActionNamespace:
    """Container allowing dot-access for action creators: slice.actions.add_item(payload)."""

    def __init__(self, actions: Dict[str, ActionCreator]):
        self._actions = actions

    def __getattr__(self, name: str) -> ActionCreator:
        if name in self._actions:
            return self._actions[name]
        raise AttributeError(f"Action '{name}' not found on slice.")

    def __dir__(self):
        return list(super().__dir__()) + list(self._actions.keys())


class Slice:
    """
    Complete slice bundle containing:
    - name: namespace prefix
    - actions: dot-accessible action creators
    - reducer: pure reducer function with Immer-style draft support
    - initial_state: baseline state of this slice
    """

    def __init__(
        self,
        name: str,
        initial_state: Any,
        reducers: Dict[str, Callable[[Any, Action], Any]],
        extra_reducers: Optional[Dict[str, Callable[[Any, Action], Any]]] = None,
    ):
        self.name = name
        self.initial_state = initial_state
        self._case_reducers = reducers
        self._extra_reducers = extra_reducers or {}

        # 1. Build action creators: e.g. slice.actions.add_item
        actions_dict: Dict[str, ActionCreator] = {}
        for action_name in reducers.keys():
            full_type = f"{name}/{action_name}"
            actions_dict[action_name] = ActionCreator(full_type)

        self.actions = ActionNamespace(actions_dict)

        # 2. Build the slice reducer function
        def slice_reducer(state: Any = None, action: Optional[Action] = None) -> Any:
            if state is None:
                state = copy.deepcopy(self.initial_state)

            if action is None:
                return state

            # Check for extra reducers (e.g. async thunk actions)
            if action.type in self._extra_reducers:
                target_case = self._extra_reducers[action.type]
                draft = copy.deepcopy(state)
                result = target_case(draft, action)
                return draft if result is None else result

            # Check if action belongs to this slice
            prefix = f"{self.name}/"
            if not action.type.startswith(prefix):
                return state

            case_name = action.type[len(prefix):]
            if case_name not in self._case_reducers:
                return state

            target_case = self._case_reducers[case_name]

            # Immer-style mutation:
            # We pass a deepcopy draft. If the user mutates draft in-place
            # (e.g. draft["items"].append(...) returning None), we return the draft.
            # If the user explicitly returns a new value, we use that value.
            draft = copy.deepcopy(state)
            result = target_case(draft, action)

            return draft if result is None else result

        self.reducer: Reducer[Any] = slice_reducer

    def __repr__(self) -> str:
        return f"<Slice name='{self.name}'>"


def create_slice(
    name: str,
    initial_state: Any,
    reducers: Dict[str, Callable[[Any, Action], Any]],
    extra_reducers: Optional[Dict[str, Callable[[Any, Action], Any]]] = None,
) -> Slice:
    """
    Creates a Redux Toolkit style slice.
    
    Example:
        cart_slice = create_slice(
            name="cart",
            initial_state={"items": [], "coupon": False},
            reducers={
                "add_item": lambda state, action: state["items"].append(action.payload),
                "toggle_coupon": lambda state, action: state.update({"coupon": not state["coupon"]}),
                "clear": lambda state, action: {"items": [], "coupon": False},
            }
        )
        
        # Action creators are automatically available:
        action = cart_slice.actions.add_item({"name": "Sensor", "price": 40})
        # -> Action(type="cart/add_item", payload={"name": "Sensor", "price": 40})
    """
    if not name or not isinstance(name, str):
        raise ValueError("Slice name must be a non-empty string.")

    return Slice(name=name, initial_state=initial_state, reducers=reducers, extra_reducers=extra_reducers)
