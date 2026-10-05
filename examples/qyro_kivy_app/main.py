from kivy.app import App
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.core.window import Window
from qyro import ApplicationContext
from qyro.ui.component import Component

from pydux.adapters.qyro import Reactive

from store.store import store, select_header
from store.slices.counter_slice import counter_slice


class QyroKivyApp(App, Component, Reactive, ApplicationContext):

    def _format_text(self, text: str) -> str:
        return (
            f"App: {self.window_title}\n"
            f"Platform: {self.platform.value}\n"
            f"Frozen: {self.is_frozen}\n"
            f"State: {text}"
        )

    def component_will_mount(self):
        Window.size = (640, 480)
        Window.minimum_width = 640
        Window.minimum_height = 480
        self.bind_selector(store, select_header, self._on_header_change)

    def render(self):
        layout = BoxLayout(orientation='vertical', padding=50, spacing=20)

        self._label = Label(
            text=self._format_text("Loading..."),
            halign="left",
            valign="middle",
            size_hint_y=0.8
        )
        self._label.bind(size=self._label.setter("text_size"))

        self._button = Button(
            text="Increment",
            size_hint=(None, None),
            size=(120, 45),
            on_press=lambda x: store.dispatch(counter_slice.actions.increment())
        )
        layout.add_widget(self._label)
        layout.add_widget(self._button)
        return layout

    def _on_header_change(self, text: str) -> None:
        self._label.text = self._format_text(text)

    def build(self):
        return self.render()


if __name__ == "__main__":
    QyroKivyApp().run()
