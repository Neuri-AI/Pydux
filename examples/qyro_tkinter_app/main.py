import tkinter as tk
from qyro import ApplicationContext
from qyro.ui.component import Component

from pydux.adapters.qyro import Reactive

from store.store import store, select_header
from store.slices.counter_slice import counter_slice


class QyroTkinterApp(tk.Tk, Component, Reactive, ApplicationContext):

    def _format_text(self, text: str) -> str:
        return (
            f"App: {self.window_title}\n"
            f"Platform: {self.platform.value}\n"
            f"Frozen: {self.is_frozen}\n"
            f"State: {text}"
        )

    def component_will_mount(self):
        self.geometry("640x480")
        self.minsize(640, 480)
        self.bind_selector(store, select_header, self._on_header_change)

    def render(self):
        self._label = tk.Label(
            self,
            text=self._format_text("Loading..."),
            justify="left"
        )
        self._label.place(x=50, y=50)

        self._button = tk.Button(
            self,
            text="Increment",
            command=lambda: store.dispatch(counter_slice.actions.increment())
        )
        self._button.place(x=50, y=150)

    def _on_header_change(self, text: str) -> None:
        self._label.config(
            text=self._format_text(text),
            justify="left"
        )


if __name__ == "__main__":
    window = QyroTkinterApp()
    import sys
    sys.exit(window.run())
