from pydux import configure_store, create_selector
from store.slices.workspace_slice import workspace_slice


store = configure_store(reducer={"workspace": workspace_slice}, devtools=True)

select_active = lambda state: state["workspace"]["active"]
select_count = lambda state: state["workspace"]["count"]

select_title = create_selector(
    select_active,
    select_count,
    lambda active, count: f"Workspace={active} | Count={count}",
)
