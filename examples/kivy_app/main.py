from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label

from pydux.adapters.base import ReactiveBinding
from pydux.adapters.kivy import KivyBridge
from store.store import store, select_player_text
from store.slices.player_slice import player_slice


class PlayerApp(App):
    def build(self):
        root = BoxLayout(orientation="vertical", padding=16, spacing=8)
        self.label = Label(text="loading...")
        root.add_widget(self.label)

        toggle_btn = Button(text="Toggle Play")
        toggle_btn.bind(
            on_press=lambda *_: store.dispatch(player_slice.actions.toggle())
        )
        root.add_widget(toggle_btn)

        self._binding = ReactiveBinding(
            store=store,
            selector=select_player_text,
            target=self._set_text,
            bridge=KivyBridge(),
        )

        return root

    def _set_text(self, text: str) -> None:
        self.label.text = text

    def on_stop(self):
        self._binding.dispose()


if __name__ == "__main__":
    PlayerApp().run()
