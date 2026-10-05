from pydux import configure_store, create_selector
from store.slices.user_slice import user_slice
from store.slices.counter_slice import counter_slice


store = configure_store(
    reducer={
        "user": user_slice,
        "counter": counter_slice,
    },
    devtools=True,
)


select_user_name = lambda state: state["user"]["name"]
select_user_role = lambda state: state["user"]["role"]
select_counter = lambda state: state["counter"]["value"]

select_header = create_selector(
    select_user_name,
    select_user_role,
    select_counter,
    lambda name, role, counter: f"{name} ({role}) | Counter={counter}",
)
