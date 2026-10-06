"""``-v`` verbose logging, formatted like curl's trace output."""

from __future__ import annotations

import base64
import sys
from typing import TextIO
from urllib.parse import urlparse

from .transport import Response
from .urls import DEFAULT_PORTS

CURL_OK = 100


class VerboseLog:
    """Writes the request/response trace to stderr, curl style."""

    def __init__(self, enabled: bool = True, stream: TextIO | None = None) -> None:
        self.stream = stream or sys.stderr
        self.enabled = enabled

    def line(self, prefix: str, message: str, note: str | None = None) -> None:
        if not self.enabled:
            return
        self.stream.write(f"{prefix} {message}\n")
        if note:
            self.stream.write(f"* {note}\n")
        self.stream.flush()

    # -- request -----------------------------------------------------------

    def request(self, url: str, method: str, headers: dict[str, str], body: bytes | None) -> None:
        if not self.enabled:
            return
        parsed = urlparse(url)
        host = parsed.hostname or ""
        port = parsed.port
        if port is not None and port != DEFAULT_PORTS.get(parsed.scheme):
            self.line(">", f"{method} {parsed.path or '/'} HTTP/1.1")
            self.stream.write(f"> Host: {host}:{port}\n")
        else:
            self.line(">", f"{method} {parsed.path or '/'} HTTP/1.1")
            self.stream.write(f"> Host: {host}\n")

        for name, value in _ordered(headers):
            if name.lower() == "host":
                continue  # already written above, in curl's canonical position
            self.stream.write(f"> {name}: {_redact(name, value)}\n")
        if body:
            self.stream.write(f"> [{len(body)} bytes data]\n")
        self.stream.write("> \n")
        self.stream.flush()

    def connection(self, url: str, insecure: bool = False) -> None:
        if not self.enabled:
            return
        parsed = urlparse(url)
        host = parsed.hostname or url
        port = parsed.port or DEFAULT_PORTS.get(parsed.scheme, 80)
        self.line("*", f"Connected to {host} port {port}")
        if parsed.scheme == "https":
            detail = "TLSv1.3, certificate verification disabled" if insecure else "TLSv1.3"
            self.line("*", f"SSL connection using {detail}")
            if not insecure:
                self.line("*", "Server certificate verified against the system trust store")
        self.stream.flush()

    # -- response ----------------------------------------------------------

    def response(self, response: Response) -> None:
        if not self.enabled:
            return
        self.stream.write(f"< {response.status_line()}\n")
        for name, value in response.headers:
            self.stream.write(f"< {name}: {value}\n")
        self.stream.write("< \n")
        self.stream.flush()

    def redirects(self, count: int) -> None:
        self.line("*", f"Followed {count} redirect{'s' if count != 1 else ''}")

    def timings(self, response: Response, uploaded: int) -> None:
        if not self.enabled:
            return
        self.stream.write(
            "\n"
            "     Content-Length: {size}\n"
            "     Content-Type: {ctype}\n\n"
            "0    {total:>6}  {curl}\n"
            "0    {total}  {upload} << upload\n"
            "0    {total}  {download} << download\n".format(
                size=response.header("Content-Length") or "0",
                ctype=response.header("Content-Type") or "-",
                total=int(response.elapsed * 1_000_000),
                curl=CURL_OK,
                upload=uploaded,
                download=response.size,
            )
        )
        self.stream.flush()


def _ordered(headers: dict[str, str]) -> list[tuple[str, str]]:
    preferred = ("Host", "User-Agent", "Accept", "Authorization", "Cookie", "Content-Type", "Content-Length")
    names = list(headers)
    names.sort(key=lambda key: (preferred.index(key) if key in preferred else len(preferred), key))
    return [(name, headers[name]) for name in names]


def _redact(name: str, value: str) -> str:
    """Hide secrets: curl prints them verbatim, we do not."""
    if name.lower() in ("authorization", "proxy-authorization") and value.lower().startswith("basic "):
        try:
            size = len(base64.b64decode(value.split(" ", 1)[1]))
        except Exception:
            size = 0
        return f"Basic <redacted {size} bytes>"
    return value