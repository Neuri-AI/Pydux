# PyDux

> **A Redux Toolkit-inspired state container for Python desktop applications.**

[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue.svg)](https://python.org)
![GitHub Release](https://img.shields.io/github/v/release/Neuri-AI/pydux?include_prereleases&display_name=release&color=stable)
![GitHub Issues](https://img.shields.io/github/issues/Neuri-AI/pydux?color=%23ab7df8)
![GitHub Issues Closed](https://img.shields.io/github/issues-closed/Neuri-AI/pydux?color=green)
![GitHub forks](https://img.shields.io/github/forks/Neuri-AI/pydux)
![GitHub stars](https://img.shields.io/github/stars/Neuri-AI/pydux)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Sponsor](https://img.shields.io/badge/Sponsor-Buy%20Me%20a%20Coffee-FFDD00?logo=buymeacoffee&logoColor=000000)](https://buymeacoffee.com/neuri)


PyDux gives Python desktop apps one observable source of truth. Dispatch actions,
let reducers update state, and subscribe only to the values a view needs.

## Features

- Redux Toolkit-style slices with generated action creators.
- Selectors and selective subscriptions.
- Async thunks with `pending`, `fulfilled`, and `rejected` actions.
- Optional DevTools, time travel, and a local web inspector.
- Adapters for Qt, Tkinter, Kivy, and [Qyro](https://github.com/Neuri-AI/qyro).

## Installation

```bash
pip install pydux

# With Qyro and PySide6
pip install "pydux[qyro,pyside6]"
```

See the [installation guide](docs/getting-started/installation.mdx) for every
optional framework extra and Poetry commands.

## Quick example

```python
from pydux import configure_store, create_slice

counter = create_slice(
    name="counter",
    initial_state={"value": 0},
    reducers={
        "increment": lambda state, action: state.update(value=state["value"] + 1),
    },
)

store = configure_store({"counter": counter}, devtools=False)
store.dispatch(counter.actions.increment())

print(store.get_state())  # {"counter": {"value": 1}}
```

## Documentation

The complete Mintlify documentation lives in [`docs/`](docs/index.mdx):

- [Get started](docs/getting-started/quickstart.mdx)
- [Core concepts](docs/concepts/store-and-slices.mdx)
- [Async thunks](docs/guides/async-thunks.mdx)
- [DevTools and inspector](docs/guides/devtools.mdx)
- [Qyro integration](docs/integrations/qyro.mdx)
- [API reference](docs/reference/api.mdx)

To preview it locally, install Mintlify and run `mint dev` from `docs/`.

## Qyro ecosystem

PyDux manages state. [Qyro Runtime](https://github.com/Neuri-AI/qyro) provides
application context, resources, settings, and lifecycle; [Qyro CLI](https://github.com/Neuri-AI/qyro-cli)
scaffolds, builds, packages, and signs applications.

---

## License

MIT. See [LICENSE](LICENSE).
---

## 👥 Organization & Maintainers

- **Organization:** [Neuri](https://github.com/Neuri-AI)
- **Lead Maintainer:** Luis Alfredo De Los Reyes ([luisalfredoreyes98@gmail.com](mailto:luisalfredoreyes98@gmail.com))
- **Ecosystem:** [Qyro](https://github.com/Neuri-AI/qyro) • [Qyro CLI](https://github.com/Neuri-AI/qyro-cli) • [Boilerplates](https://github.com/Neuri-AI)
