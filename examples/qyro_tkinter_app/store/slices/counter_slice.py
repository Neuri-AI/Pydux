from pydux import create_slice


counter_slice = create_slice(
    name="counter",
    initial_state={"value": 0},
    reducers={
        "increment": lambda state, action: state.update({"value": state["value"] + 1}),
        "decrement": lambda state, action: state.update({"value": state["value"] - 1}),
    },
)
