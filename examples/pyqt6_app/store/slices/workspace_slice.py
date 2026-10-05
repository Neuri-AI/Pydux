from pydux import create_slice


workspace_slice = create_slice(
    name="workspace",
    initial_state={"active": "alpha", "count": 1},
    reducers={
        "set_active": lambda state, action: state.update({"active": action.payload}),
        "increment": lambda state, action: state.update({"count": state["count"] + 1}),
    },
)
