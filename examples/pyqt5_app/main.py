import sys
from PyQt5.QtWidgets import QApplication, QLabel, QMainWindow, QPushButton, QVBoxLayout, QWidget

from pydux.adapters.base import ReactiveBinding
from pydux.adapters.qt import QtMainThreadBridge
from store.store import store, select_panel_text
from store.slices.telemetry_slice import telemetry_slice


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQt5 + PyDux")
        self.resize(420, 220)

        root = QWidget()
        layout = QVBoxLayout(root)

        self.label = QLabel("loading...")
        button = QPushButton("Bump RPM")
        button.clicked.connect(lambda: store.dispatch(telemetry_slice.actions.bump_rpm()))

        layout.addWidget(self.label)
        layout.addWidget(button)
        self.setCentralWidget(root)

        self._binding = ReactiveBinding(
            store=store,
            selector=select_panel_text,
            target=self.label.setText,
            bridge=QtMainThreadBridge(),
        )

    def closeEvent(self, event):
        self._binding.dispose()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
