"""Response rendering: headers, body, progress meter and ``-w`` stats."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import BinaryIO, TextIO

from .args import Options
from .errors import WriteError
from .transport import Response
from .urls import filename_from_url


class Output:
    """Writes the payload of a transfer to stdout or to a file.

    curl streams bytes, so binary bodies must never be decoded or mangled by a
    newline translation: everything is written through the binary stream.
    """

    def __init__(self, opts: Options, stdout: BinaryIO | None = None, stderr: TextIO | None = None) -> None:
        self.opts = opts
        self.stdout = stdout or sys.stdout.buffer
        self.stderr = stderr or sys.stderr
        self._path: str | None = None
        self._handle: BinaryIO | None = None
        self._header_bytes = b""
        self._body_bytes = 0

    # -- destination -------------------------------------------------------

    def target_for(self, url: str) -> str | None:
        """Resolve where the body for ``url`` should go."""
        opts = self.opts
        if opts.output:
            return opts.output
        if opts.remote_name:
            return filename_from_url(url)
        return None

    def open_target(self, url: str) -> None:
        path = self.target_for(url)
        self._path = path
        if path is None or path == "-":
            self._handle = None
            return
        try:
            self._handle = Path(path).open("wb")
        except OSError as exc:
            raise WriteError(f"failed to open '{path}' for writing: {exc.strerror}") from exc

    def close(self) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None

    @property
    def path(self) -> str | None:
        return self._path

    # -- writing -----------------------------------------------------------

    def write_response(self, response: Response) -> None:
        """Emit headers (with ``-i``) followed by the body."""
        if self.opts.include_headers:
            self.write_header_block()
        self._write(response.body)
        self._body_bytes += len(response.body)

    def write_header_block(self) -> None:
        """Emit only the buffered status line + headers (used by ``-I``)."""
        self._write(self._header_bytes)

    def write_headers(self, response: Response) -> None:
        """Buffer the header block so ``-i``/``-I`` can emit it."""
        self._header_bytes = response.header_block()

    def _write(self, data: bytes) -> None:
        if not data:
            return
        stream = self._handle if self._handle is not None else self.stdout
        try:
            stream.write(data)
        except BrokenPipeError as exc:
            raise WriteError("broken pipe while writing output") from exc
        except OSError as exc:
            raise WriteError(f"failed to write output: {exc}") from exc

    @property
    def body_bytes(self) -> int:
        return self._body_bytes


def flush_stdout() -> None:
    try:
        sys.stdout.flush()
    except (BrokenPipeError, ValueError):
        pass


class ProgressMeter:
    """A minimal curl-style progress bar, drawn on stderr."""

    WIDTH = 32

    def __init__(self, total: int, label: str, enabled: bool, stream: TextIO | None = None) -> None:
        self.total = max(0, total)
        self.label = label
        self.stream = stream or sys.stderr
        self.enabled = enabled and _is_tty(self.stream)
        self.done = 0
        self._last = -1

    def update(self, count: int) -> None:
        self.done += count
        if not self.enabled:
            return
        step = max(1, self.total // self.WIDTH) if self.total else 0
        position = self.done // step if step else 0
        if position == self._last:
            return
        self._last = position
        self._render()

    def finish(self) -> None:
        if not self.enabled:
            return
        self.enabled = False
        self.stream.write("\r" + " " * (self.WIDTH + 40) + "\r")
        self.stream.flush()

    def _render(self) -> None:
        if self.total:
            fraction = min(1.0, self.done / self.total)
            filled = int(fraction * self.WIDTH)
            bar = "#" * filled + "-" * (self.WIDTH - filled)
            text = f"\r{self.label} {bar} {100 * fraction:3.0f}%  {self.done}/{self.total}"
        else:
            text = f"\r{self.label} {self.done} bytes"
        self.stream.write(text)
        self.stream.flush()


def _is_tty(stream: TextIO) -> bool:
    try:
        return bool(stream.isatty())
    except (AttributeError, ValueError, OSError):
        return False


def format_write_out(template: str, response: Response) -> str:
    """Expand a ``-w`` format string using curl's variable names."""
    values = {
        "url_effective": response.effective_url,
        "http_code": str(response.status),
        "http_version": response.http_version.replace("1.", ""),
        "size_download": str(response.size),
        "size_header": str(len(response.raw_headers())),
        "size_upload": str(response.upload_size),
        "time_total": f"{response.elapsed:.6f}",
        "time_starttransfer": f"{response.ttfb:.6f}",
        "time_namelookup": "0.000000",
        "time_connect": "0.000000",
        "time_pretransfer": "0.000000",
        "time_appconnect": "0.000000",
        "time_total_us": str(int(response.elapsed * 1_000_000)),
        "time_starttransfer_us": str(int(response.ttfb * 1_000_000)),
        "num_redirects": str(response.redirects),
        "num_connects": "1",
        "content_type": response.content_type or response.header("Content-Type"),
        "remote_ip": "",
        "local_ip": "127.0.0.1",
        "local_port": "0",
        "scheme": response.effective_url.split(":", 1)[0] if ":" in response.effective_url else "",
        "errormsg": "",
        "json": "",
        "exitcode": "0",
    }
    out = template.replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r")
    for key, value in values.items():
        out = out.replace("%{" + key + "}", value).replace("{" + key + "}", value)
    return out