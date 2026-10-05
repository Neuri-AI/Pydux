import sys
from PySide6.QtWidgets import QMainWindow, QLabel, QPushButton
from qyro import ApplicationContext
from qyro.ui.component import Component
from pydux.adapters.qyro import Reactive

from store.store import store, select_header
from store.slices.counter_slice import counter_slice
 

class QyroApp(QMainWindow, Component, Reactive, ApplicationContext):

    def component_will_mount(self):
        self.resize(640, 320)
        self.bind_selector(store, select_header, self._on_header_change)

    def render(self):
        self._label = QLabel(parent=self)
        self._label.move(24, 24)
        self._label.resize(560, 96)

        self._button = QPushButton("Increment", parent=self)
        self._button.move(24, 140)
        self._button.clicked.connect(
            lambda: store.dispatch(counter_slice.actions.increment())
        )

    def _on_header_change(self, text: str) -> None:
        self._label.setText(
            f"App: {self.window_title}\n"
            f"Platform: {self.platform.value}\n"
            f"Frozen: {self.is_frozen}\n"
            f"State: {text}"
        )



if __name__ == "__main__":
    window = QyroApp()
    window.show()
    sys.exit(window.run())
