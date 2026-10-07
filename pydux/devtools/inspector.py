"""
Framework-agnostic DevTools Inspector transport for PyDux.

Exposes a lightweight HTTP API so any UI framework (Qyro, Tkinter, Kivy,
PyQt, PySide) can inspect action traces and trigger time-travel operations
without embedding framework-specific widgets.

The inspector UI lives in ``pydux/devtools/static`` (index.html, inspector.css,
inspector.js) and is served by this module.
"""

from __future__ import annotations

import json
import errno
import queue
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional

from pydux.devtools.tracker import ActionTrace, PyDuxDevTools


_STATIC_DIR = Path(__file__).resolve().parent / "static"

# Whitelist of servable files: URL path -> (file name, content type).
# Nothing outside this map is ever read from disk.
_STATIC_ROUTES: dict[str, tuple[str, str]] = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/static/inspector.css": ("inspector.css", "text/css; charset=utf-8"),
    "/static/inspector.js": ("inspector.js", "application/javascript; charset=utf-8"),
}

# Raised by the socket layer when the browser closes the SSE connection
# (page reload, tab closed). Not an error for the inspector.
_CLIENT_DISCONNECTED = (
    BrokenPipeError,
    ConnectionResetError,
    ConnectionAbortedError,
)


def _safe_json(value: Any) -> Any:
    """Converts non-serializable objects into JSON-friendly values."""
    try:
        json.dumps(value)
        return value
    except TypeError:
        return json.loads(json.dumps(value, default=str))


def _serialize_trace(trace: ActionTrace) -> dict[str, Any]:
    return {
        "index": trace.index,
        "action": {
            "type": trace.action.type,
            "payload": _safe_json(trace.action.payload),
        },
        "timestamp": trace.timestamp,
        "duration_ms": trace.duration_ms,
        "changed_paths": list(trace.changed_paths),
        "prev_state": _safe_json(trace.prev_state),
        "next_state": _safe_json(trace.next_state),
    }


class PyDuxInspectorServer:
    """HTTP API for PyDux DevTools inspection and time-travel control."""

    def __init__(
        self,
        devtools: PyDuxDevTools,
        host: str = "127.0.0.1",
        port: int = 8765,
    ):
        self._devtools = devtools
        self._host = host
        self._port = port
        self._httpd: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._trace_unsubscribe: Optional[callable] = None
        self._event_queues: list[queue.Queue[dict[str, Any]]] = []
        self._events_lock = threading.Lock()
        self._started = False

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    @property
    def base_url(self) -> str:
        return f"http://{self._host}:{self._port}"

    def _current_state(self) -> Any:
        store = getattr(self._devtools, "_store", None)
        return store.get_state() if store is not None else None

    def _snapshot_payload(self) -> dict[str, Any]:
        history = [_serialize_trace(trace) for trace in self._devtools.history]
        active_index = getattr(self._devtools, "_current_index", len(history) - 1)
        return {
            "ok": True,
            "active_index": active_index,
            "count": len(history),
            "history": history,
            "state": _safe_json(self._current_state()),
        }

    def _register_event_queue(self) -> queue.Queue[dict[str, Any]]:
        q: queue.Queue[dict[str, Any]] = queue.Queue()
        with self._events_lock:
            self._event_queues.append(q)
        return q

    def _unregister_event_queue(self, q: queue.Queue[dict[str, Any]]) -> None:
        with self._events_lock:
            if q in self._event_queues:
                self._event_queues.remove(q)

    def _broadcast_event(self, event: str, data: dict[str, Any]) -> None:
        packet = {"event": event, "data": data}
        with self._events_lock:
            targets = list(self._event_queues)

        for q in targets:
            try:
                q.put_nowait(packet)
            except queue.Full:
                continue

    def _on_trace(self, trace: ActionTrace) -> None:
        active_index = getattr(self._devtools, "_current_index", trace.index)
        self._broadcast_event(
            "trace",
            {
                "trace": _serialize_trace(trace),
                "active_index": active_index,
                "prev_active_index": max(active_index - 1, -1),
                "state": _safe_json(self._current_state()),
            },
        )

    def _broadcast_snapshot(self) -> None:
        self._broadcast_event("snapshot", self._snapshot_payload())

    def start(self) -> None:
        """Starts the inspector HTTP server in a background thread."""
        if self._started:
            return

        server = self

        class _Handler(BaseHTTPRequestHandler):
            def handle(self) -> None:
                """Treat a browser closing an HTTP/SSE socket as expected."""
                try:
                    super().handle()
                except _CLIENT_DISCONNECTED:
                    # BaseHTTPRequestHandler otherwise prints a traceback for
                    # a normal tab close while it is reading the next request.
                    return

            def _send_json(self, payload: dict[str, Any], status: int = HTTPStatus.OK) -> None:
                data = json.dumps(payload, ensure_ascii=True, default=str).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.end_headers()
                self.wfile.write(data)

            def _send_static(self, file_name: str, content_type: str) -> None:
                try:
                    data = (_STATIC_DIR / file_name).read_bytes()
                except OSError:
                    self._send_json(
                        {"ok": False, "error": f"Missing inspector asset: {file_name}"},
                        status=HTTPStatus.INTERNAL_SERVER_ERROR,
                    )
                    return
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)

            def _read_json(self) -> dict[str, Any]:
                length = int(self.headers.get("Content-Length", "0") or "0")
                if length <= 0:
                    return {}
                body = self.rfile.read(length)
                if not body:
                    return {}
                try:
                    decoded = json.loads(body.decode("utf-8"))
                    return decoded if isinstance(decoded, dict) else {}
                except json.JSONDecodeError:
                    return {}

            def do_OPTIONS(self) -> None:  # noqa: N802
                self.send_response(HTTPStatus.NO_CONTENT)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.end_headers()

            def do_GET(self) -> None:  # noqa: N802
                route = _STATIC_ROUTES.get(self.path.split("?", 1)[0])
                if route is not None:
                    self._send_static(*route)
                    return

                if self.path.startswith("/api/events"):
                    q = server._register_event_queue()
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Connection", "keep-alive")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()

                    def send_event(name: str, payload: dict[str, Any]) -> None:
                        encoded = json.dumps(payload, ensure_ascii=True, default=str)
                        self.wfile.write(f"event: {name}\n".encode("utf-8"))
                        self.wfile.write(f"data: {encoded}\n\n".encode("utf-8"))
                        self.wfile.flush()

                    try:
                        send_event("snapshot", server._snapshot_payload())

                        while True:
                            try:
                                packet = q.get(timeout=15.0)
                            except queue.Empty:
                                self.wfile.write(b": keepalive\n\n")
                                self.wfile.flush()
                                continue

                            send_event(packet["event"], packet["data"])
                    except _CLIENT_DISCONNECTED:
                        pass
                    finally:
                        server._unregister_event_queue(q)
                    return

                if self.path == "/health":
                    self._send_json({"ok": True})
                    return

                if self.path == "/api/traces":
                    snapshot = server._snapshot_payload()
                    snapshot.pop("state", None)
                    self._send_json(snapshot)
                    return

                if self.path == "/api/state":
                    self._send_json(
                        {
                            "ok": True,
                            "state": _safe_json(server._current_state()),
                        }
                    )
                    return

                self._send_json(
                    {
                        "ok": False,
                        "error": "Not Found",
                    },
                    status=HTTPStatus.NOT_FOUND,
                )

            def do_POST(self) -> None:  # noqa: N802
                payload = self._read_json()

                if self.path == "/api/undo":
                    server._devtools.undo()
                    server._broadcast_snapshot()
                    self._send_json({"ok": True})
                    return

                if self.path == "/api/redo":
                    server._devtools.redo()
                    server._broadcast_snapshot()
                    self._send_json({"ok": True})
                    return

                if self.path == "/api/jump":
                    index = payload.get("index")
                    if not isinstance(index, int):
                        self._send_json(
                            {"ok": False, "error": "index must be an integer"},
                            status=HTTPStatus.BAD_REQUEST,
                        )
                        return
                    server._devtools.jump_to_state(index)
                    server._broadcast_snapshot()
                    self._send_json({"ok": True})
                    return

                self._send_json(
                    {
                        "ok": False,
                        "error": "Not Found",
                    },
                    status=HTTPStatus.NOT_FOUND,
                )

            def log_message(self, format: str, *args: Any) -> None:
                # Silence base HTTP server logs to avoid noisy stdout in GUI apps.
                return

        self._httpd = ThreadingHTTPServer((self._host, self._port), _Handler)
        self._port = int(self._httpd.server_address[1])
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            name="pydux-inspector-server",
            daemon=True,
        )
        self._trace_unsubscribe = self._devtools.subscribe_traces(self._on_trace)
        self._thread.start()
        self._started = True

    def stop(self) -> None:
        """Stops the background inspector server if running."""
        if not self._started:
            return

        if self._trace_unsubscribe is not None:
            try:
                self._trace_unsubscribe()
            except Exception:
                pass
            self._trace_unsubscribe = None

        with self._events_lock:
            queues = list(self._event_queues)
            self._event_queues.clear()

        for q in queues:
            try:
                q.put_nowait({"event": "shutdown", "data": {"ok": True}})
            except queue.Full:
                pass

        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.0)

        self._thread = None
        self._httpd = None
        self._started = False


def start_inspector(
    store: Any,
    host: str = "127.0.0.1",
    port: int = 8765,
    auto_reassign_port: bool = True,
    log_startup: bool = True,
) -> PyDuxInspectorServer:
    """
    Starts an inspector server for an existing configured store.

    The store must expose `store.devtools` (enabled via configure_store(devtools=True)
    or by passing a PyDuxDevTools instance).

    If the preferred port is busy and auto_reassign_port=True, a free OS-assigned
    port is selected automatically.
    """
    existing = getattr(store, "inspector", None)
    if isinstance(existing, PyDuxInspectorServer):
        return existing

    devtools = getattr(store, "devtools", None)
    if not isinstance(devtools, PyDuxDevTools):
        raise ValueError(
            "Inspector requires store.devtools. "
            "Enable it with configure_store(..., devtools=True)."
        )

    preferred_port = port
    used_fallback_port = False

    try:
        server = PyDuxInspectorServer(devtools=devtools, host=host, port=preferred_port)
        server.start()
    except OSError as exc:
        is_addr_in_use = getattr(exc, "errno", None) in (errno.EADDRINUSE, 10048)
        if not auto_reassign_port or not is_addr_in_use:
            raise

        used_fallback_port = True
        server = PyDuxInspectorServer(devtools=devtools, host=host, port=0)
        server.start()

    setattr(store, "inspector", server)

    if log_startup:
        if used_fallback_port:
            print(
                f"[PyDux] Inspector port {preferred_port} was busy. "
                f"Using {server.base_url}"
            )
        else:
            print(f"[PyDux] Inspector running at {server.base_url}")

    return server
