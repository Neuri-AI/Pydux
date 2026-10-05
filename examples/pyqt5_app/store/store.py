from pydux import configure_store, create_selector
from store.slices.telemetry_slice import telemetry_slice


store = configure_store(reducer={"telemetry": telemetry_slice}, devtools=True)

select_rpm = lambda state: state["telemetry"]["rpm"]
select_status = lambda state: state["telemetry"]["status"]

select_panel_text = create_selector(
    select_rpm,
    select_status,
    lambda rpm, status: f"RPM={rpm} | status={status}",
)
