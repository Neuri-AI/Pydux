from pydux import configure_store, create_selector
from store.slices.task_slice import task_slice


store = configure_store(reducer={"task": task_slice}, devtools=True)

select_items = lambda state: state["task"]["items"]
select_task_text = create_selector(
    select_items,
    lambda items: "Tasks: " + (", ".join(items) if items else "none"),
)
