from pydux import create_slice


player_slice = create_slice(
    name="player",
    initial_state={"track": "Intro", "playing": False},
    reducers={
        "toggle": lambda state, action: state.update({"playing": not state["playing"]}),
        "set_track": lambda state, action: state.update({"track": action.payload}),
    },
)
