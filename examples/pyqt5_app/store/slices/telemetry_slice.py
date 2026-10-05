from pydux import create_slice


telemetry_slice = create_slice(
    name="telemetry",
    initial_state={"rpm": 900, "status": "idle"},
    reducers={
        "set_status": lambda state, action: state.update({"status": action.payload}),
        "bump_rpm": lambda state, action: state.update({"rpm": state["rpm"] + 100}),
    },
)
