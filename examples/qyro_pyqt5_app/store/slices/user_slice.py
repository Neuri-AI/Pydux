from pydux import create_slice


user_slice = create_slice(
    name="user",
    initial_state={"name": "Alice", "role": "Architect"},
    reducers={
        "set_name": lambda state, action: state.update({"name": action.payload}),
        "set_role": lambda state, action: state.update({"role": action.payload}),
    },
)
