import tkinter as tk

from pydux.adapters.base import ReactiveBinding
from pydux.adapters.tkinter import TkinterBridge
from store.store import store, select_task_text
from store.slices.task_slice import task_slice


class TaskApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Tkinter + PyDux")
        self.geometry("420x220")

        self._text = tk.StringVar(value="loading...")
        tk.Label(self, textvariable=self._text).pack(padx=16, pady=16)

        tk.Button(
            self,
            text="Add Task",
            command=lambda: store.dispatch(task_slice.actions.add("ship feature")),
        ).pack(padx=16, pady=4)

        tk.Button(
            self,
            text="Clear",
            command=lambda: store.dispatch(task_slice.actions.clear()),
        ).pack(padx=16, pady=4)

        self._binding = ReactiveBinding(
            store=store,
            selector=select_task_text,
            target=self._text.set,
            bridge=TkinterBridge(self),
        )

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        self._binding.dispose()
        self.destroy()


if __name__ == "__main__":
    TaskApp().mainloop()
