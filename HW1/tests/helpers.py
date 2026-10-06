"""Shared test helpers: an in-process HTTP server with deterministic routes."""

from __future__ import annotations

import gzip
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from curl_lite.args import Options, parse


class RecordingHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "curl-lite-test/1.0"

    # -- plumbing ----------------------------------------------------------

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        pass  # keep the test output clean

    @property
    def routes(self) -> dict[str, Any]:
        return self.server.routes  # type: ignore[attr-defined]

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length else b""

    def _respond(
        self,
        status: int,
        body: bytes = b"",
        headers: dict[str, str | list[str]] | None = None,
    ) -> None:
        self.send_response(status)
        for name, value in (headers or {}).items():
            for item in [value] if isinstance(value, str) else value:
                self.send_header(name, item)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _record(self, body: bytes) -> dict[str, Any]:
        record = {
            "method": self.command,
            "path": self.path,
            "headers": {k.lower(): v for k, v in self.headers.items()},
            "body": body.decode("utf-8", "replace"),
        }
        self.server.requests.append(record)  # type: ignore[attr-defined]
        return record

    # -- dispatch ----------------------------------------------------------

    def _dispatch(self) -> None:
        body = self._read_body()
        self._record(body)
        path = self.path.split("?", 1)[0]

        route = self.routes.get(path)
        if route is None:
            self._respond(404, b"not found")
            return
        route(self, body)

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = _dispatch


class TestServer:
    """A threaded HTTP server bound to an ephemeral port."""

    def __init__(self) -> None:
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), RecordingHandler)
        self._server.routes = {}  # type: ignore[attr-defined]
        self._server.requests = []  # type: ignore[attr-defined]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> "TestServer":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    # -- configuration -----------------------------------------------------

    def route(self, path: str, handler) -> "TestServer":
        self._server.routes[path] = handler  # type: ignore[attr-defined]
        return self

    def html(self, path: str, text: str = "<h1>hello</h1>", **headers: str) -> "TestServer":
        def handler(request: RecordingHandler, body: bytes) -> None:
            request._respond(200, text.encode("utf-8"), {"Content-Type": "text/html", **headers})

        return self.route(path, handler)

    def json_route(self, path: str, payload: Any, status: int = 200) -> "TestServer":
        def handler(request: RecordingHandler, body: bytes) -> None:
            request._respond(
                status,
                json.dumps(payload).encode("utf-8"),
                {"Content-Type": "application/json"},
            )

        return self.route(path, handler)

    def redirect(self, path: str, location: str, status: int = 302) -> "TestServer":
        def handler(request: RecordingHandler, body: bytes) -> None:
            request._respond(status, b"", {"Location": location})

        return self.route(path, handler)

    # -- accessors ---------------------------------------------------------

    @property
    def base(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def url(self, path: str) -> str:
        return f"{self.base}{path}"

    @property
    def requests(self) -> list[dict[str, Any]]:
        return self._server.requests  # type: ignore[attr-defined]

    def last_request(self) -> dict[str, Any]:
        return self.requests[-1]


# --- reusable route factories ---------------------------------------------


def echo(request: RecordingHandler, body: bytes) -> None:
    """Reflect the request back as JSON, like httpbin's /echo."""
    payload = {
        "method": request.command,
        "path": request.path,
        "headers": {k.lower(): v for k, v in request.headers.items()},
        "body": body.decode("utf-8", "replace"),
    }
    request._respond(200, json.dumps(payload).encode("utf-8"), {"Content-Type": "application/json"})


def set_cookie(request: RecordingHandler, body: bytes) -> None:
    request._respond(
        200,
        b"cookie set",
        {"Set-Cookie": ["session=abc123; Path=/", "theme=dark; Path=/"]},
    )


def require_cookie(request: RecordingHandler, body: bytes) -> None:
    cookie = request.headers.get("Cookie", "")
    if "session=abc123" in cookie:
        request._respond(200, cookie.encode("utf-8"), {"Content-Type": "text/plain"})
    else:
        request._respond(401, b"missing cookie", {"Content-Type": "text/plain"})


def gzip_route(request: RecordingHandler, body: bytes) -> None:
    payload = gzip.compress(b"compressed payload")
    request._respond(200, payload, {"Content-Type": "text/plain", "Content-Encoding": "gzip"})


def set_auth(request: RecordingHandler, body: bytes) -> None:
    if request.headers.get("Authorization") == "Basic dXNlcjpwYXNz":  # user:pass
        request._respond(200, b"authenticated")
    else:
        request._respond(401, b"nope", {"WWW-Authenticate": 'Basic realm="test"'})


def make_options(*argv: str) -> Options:
    return parse(list(argv))


__all__ = [
    "TestServer",
    "echo",
    "gzip_route",
    "make_options",
    "require_cookie",
    "set_auth",
    "set_cookie",
]