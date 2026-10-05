import sys
from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow, QPushButton, QVBoxLayout, QWidget

from pydux.adapters.base import ReactiveBinding
from pydux.adapters.qt import QtMainThreadBridge
from store.store import store, select_title
from store.slices.workspace_slice import workspace_slice


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQt6 + PyDux")
        self.resize(420, 220)

        root = QWidget()
        layout = QVBoxLayout(root)

        self.label = QLabel("loading...")
        button = QPushButton("Increment")
        button.clicked.connect(lambda: store.dispatch(workspace_slice.actions.increment()))

        layout.addWidget(self.label)
        layout.addWidget(button)
        self.setCentralWidget(root)

        self._binding = ReactiveBinding(
            store=store,
            selector=select_title,
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
    sys.exit(app.exec())
