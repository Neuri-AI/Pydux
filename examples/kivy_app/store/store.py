from pydux import configure_store, create_selector
from store.slices.player_slice import player_slice


store = configure_store(reducer={"player": player_slice}, devtools=True)

select_track = lambda state: state["player"]["track"]
select_playing = lambda state: state["player"]["playing"]

select_player_text = create_selector(
    select_track,
    select_playing,
    lambda track, playing: f"Track={track} | playing={playing}",
)
