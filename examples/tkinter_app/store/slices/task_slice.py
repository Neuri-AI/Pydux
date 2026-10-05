from pydux import create_slice


task_slice = create_slice(
    name="task",
    initial_state={"items": ["write docs"]},
    reducers={
        "add": lambda state, action: state["items"].append(action.payload),
        "clear": lambda state, action: state["items"].clear(),
    },
)
