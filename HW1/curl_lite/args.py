"""A small curl-flavoured command line parser.

``argparse`` cannot reproduce curl's quirks: short flags may be bundled
(``-sSL``), a value may be glued to the flag (``-H"A: b"``, ``-d=x``) or
detached (``-H "A: b"``), and long options accept ``--name=value``.  This
module implements that syntax on top of a declarative option table so the rest
of the program only ever sees a validated :class:`Options` object.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence
from urllib.parse import quote

from .errors import UsageError

FLAG = "flag"  # boolean switch, takes no value
VALUE = "value"  # requires a value, always a string


@dataclass(frozen=True)
class Option:
    short: str | None
    long: str
    kind: str
    dest: str
    help: str
    arg: str = ""  # placeholder shown in --help, e.g. "<header>"
    metavar: str | None = None  # value quoted in error messages

    @property
    def takes_value(self) -> bool:
        return self.kind == VALUE

    @property
    def help_flags(self) -> str:
        if self.short:
            return f"-{self.short}, --{self.long}"
        return f"    --{self.long}"


OPTIONS: tuple[Option, ...] = (
    # --- request shaping ---------------------------------------------------
    Option("X", "request", VALUE, "method", "HTTP method to use", "<method>", "METHOD"),
    Option("G", "get", FLAG, "use_get", "Move -d data into the query string"),
    Option("d", "data", VALUE, "data", "Send data in the request body", "<data>", "DATA"),
    Option(None, "data-raw", VALUE, "data_raw", "Like --data but keeps newlines", "<data>"),
    Option(None, "data-urlencode", VALUE, "data_urlencode", "URL-encode the data before sending", "<data>"),
    Option(None, "json", VALUE, "json", "Send a JSON body with the matching Content-Type", "<json>"),
    Option("I", "head", FLAG, "head", "Fetch headers only (HEAD request)"),
    # --- headers -----------------------------------------------------------
    Option("H", "header", VALUE, "headers", "Add/replace a request header (repeatable)", "<header>", "HEADER"),
    Option("A", "user-agent", VALUE, "user_agent", "Set the User-Agent header", "<name>", "NAME"),
    Option("e", "referer", VALUE, "referer", "Set the Referer header", "<url>", "URL"),
    Option("u", "user", VALUE, "user", "Server user:password for basic auth", "<user:password>", "USER"),
    Option("b", "cookie", VALUE, "cookie", "Cookie header value, or a cookie file to read", "<data|file>", "DATA"),
    # --- networking --------------------------------------------------------
    Option("L", "location", FLAG, "follow_redirects", "Follow 3xx redirects"),
    Option(None, "max-redirs", VALUE, "max_redirects", "Maximum number of redirects", "<n>", "NUM"),
    Option("k", "insecure", FLAG, "insecure", "Allow insecure TLS connections"),
    Option(None, "compressed", FLAG, "compressed", "Ask for a compressed response and decompress it"),
    Option("x", "proxy", VALUE, "proxy", "Route the request through a proxy", "<[proto://]host[:port]>", "PROXY"),
    Option(None, "connect-timeout", VALUE, "connect_timeout", "Seconds to wait while connecting", "<secs>", "SECONDS"),
    Option(None, "max-time", VALUE, "max_time", "Seconds allowed for the whole transfer", "<secs>", "SECONDS"),
    Option(None, "retry", VALUE, "retry", "Retry transient failures this many times", "<n>", "NUM"),
    # --- output ------------------------------------------------------------
    Option("i", "include", FLAG, "include_headers", "Include response headers in the output"),
    Option("o", "output", VALUE, "output", "Write the body to a file (-o - for stdout)", "<file>", "FILE"),
    Option("O", "remote-name", FLAG, "remote_name", "Write the body to a file named after the URL"),
    Option("s", "silent", FLAG, "silent", "Hide the progress meter and errors"),
    Option("S", "show-error", FLAG, "show_error", "Show errors even when silent"),
    Option("v", "verbose", FLAG, "verbose", "Make the operation more talkative"),
    Option("f", "fail", FLAG, "fail", "Fail silently (no body) on HTTP errors"),
    Option(
        "w", "write-out", VALUE, "write_out", "Print transfer statistics using a format string", "<format>", "FORMAT"
    ),
    Option("c", "cookie-jar", VALUE, "cookie_jar", "Write received cookies to a file", "<file>", "FILE"),
    # --- misc --------------------------------------------------------------
    Option(None, "url", VALUE, "urls", "The URL to fetch (same as a bare argument)", "<url>", "URL"),
    Option(None, "version", FLAG, "show_version", "Show the version and exit"),
    Option(None, "help", FLAG, "show_help", "Show this help and exit"),
)

_BY_SHORT: dict[str, Option] = {o.short: o for o in OPTIONS if o.short}
_BY_LONG: dict[str, Option] = {o.long: o for o in OPTIONS}

# destinations that accumulate instead of overwriting
LIST_DESTS = frozenset({"headers", "data", "data_raw", "data_urlencode", "urls"})


@dataclass
class Options:
    """Validated view of the command line."""

    urls: list[str] = field(default_factory=list)
    method: str | None = None
    use_get: bool = False
    data: list[str] = field(default_factory=list)
    data_raw: list[str] = field(default_factory=list)
    data_urlencode: list[str] = field(default_factory=list)
    json_body: str | None = None
    headers: list[str] = field(default_factory=list)
    user_agent: str | None = None
    referer: str | None = None
    user: str | None = None
    cookie: str | None = None
    follow_redirects: bool = False
    max_redirects: int | None = None
    insecure: bool = False
    compressed: bool = False
    proxy: str | None = None
    connect_timeout: float | None = None
    max_time: float | None = None
    retry: int = 0
    include_headers: bool = False
    output: str | None = None
    remote_name: bool = False
    silent: bool = False
    show_error: bool = False
    verbose: bool = False
    fail: bool = False
    write_out: str | None = None
    cookie_jar: str | None = None
    show_help: bool = False
    show_version: bool = False

    # derived by :meth:`Parser.to_options`
    body: str | None = None
    content_type: str | None = None

    @property
    def quiet(self) -> bool:
        """True when nothing but the payload should reach stdout/stderr."""
        return self.silent and not self.show_error


class Parser:
    """Turns ``argv`` into :class:`Options`, raising :class:`UsageError`."""

    def __init__(self, argv: Sequence[str]) -> None:
        self.argv = list(argv)
        self.cursor = 0
        self.values: dict[str, object] = {}
        self.positional: list[str] = []
        self._parse()

    # -- option lookup -----------------------------------------------------

    @staticmethod
    def _lookup_short(flag: str) -> Option:
        try:
            return _BY_SHORT[flag]
        except KeyError:
            raise UsageError(f"unknown option -{flag}") from None

    @staticmethod
    def _lookup_long(name: str) -> Option:
        try:
            return _BY_LONG[name]
        except KeyError:
            raise UsageError(f"unknown option --{name}") from None

    def _store(self, opt: Option, value: str | None) -> None:
        if not opt.takes_value:
            self.values[opt.dest] = True
            return
        assert value is not None
        if opt.dest in LIST_DESTS:
            bucket = self.values.setdefault(opt.dest, [])
            assert isinstance(bucket, list)
            bucket.append(value)
        else:
            self.values[opt.dest] = value

    def _next_value(self, opt: Option, spelling: str) -> str:
        if self.cursor >= len(self.argv):
            raise UsageError(f"option {spelling} requires a value")
        value = self.argv[self.cursor]
        self.cursor += 1
        return value

    # -- token handling ----------------------------------------------------

    def _parse(self) -> None:
        while self.cursor < len(self.argv):
            token = self.argv[self.cursor]
            self.cursor += 1

            if token == "--":
                self.positional.extend(self.argv[self.cursor:])
                return
            if token.startswith("--"):
                self._handle_long(token[2:])
            elif token.startswith("-") and token != "-":
                self._handle_short_cluster(token[1:])
            else:
                self.positional.append(token)

    def _handle_long(self, body: str) -> None:
        name, sep, inline = body.partition("=")
        opt = self._lookup_long(name)
        if not opt.takes_value:
            if sep:
                raise UsageError(f"option --{opt.long} does not take a value")
            self._store(opt, None)
            return
        self._store(opt, inline if sep else self._next_value(opt, f"--{opt.long}"))

    def _handle_short_cluster(self, body: str) -> None:
        pos = 0
        while pos < len(body):
            flag = body[pos]
            pos += 1
            opt = self._lookup_short(flag)
            if not opt.takes_value:
                self._store(opt, None)
                continue
            rest = body[pos:]
            pos = len(body)
            if rest:  # -d=x, -H"A: b": the remainder is the value
                self._store(opt, rest[1:] if rest.startswith("=") else rest)
            else:
                self._store(opt, self._next_value(opt, f"-{flag}"))

    # -- construction ------------------------------------------------------

    def to_options(self) -> Options:
        opts = Options()

        opts.show_help = bool(self.values.get("show_help"))
        opts.show_version = bool(self.values.get("show_version"))

        urls = list(self.values.get("urls") or [])  # type: ignore[arg-type]
        urls.extend(self.positional)
        if not urls and not (opts.show_help or opts.show_version):
            raise UsageError("no URL specified", hint="try 'curl-lite --help'")
        opts.urls = urls

        opts.method = _upper(self.values.get("method"))
        opts.use_get = bool(self.values.get("use_get"))
        opts.data = list(self.values.get("data") or [])  # type: ignore[arg-type]
        opts.data_raw = list(self.values.get("data_raw") or [])  # type: ignore[arg-type]
        opts.data_urlencode = list(self.values.get("data_urlencode") or [])  # type: ignore[arg-type]
        opts.json_body = _as_str(self.values.get("json"))
        opts.head = bool(self.values.get("head"))
        opts.headers = list(self.values.get("headers") or [])  # type: ignore[arg-type]
        opts.user_agent = _as_str(self.values.get("user_agent"))
        opts.referer = _as_str(self.values.get("referer"))
        opts.user = _as_str(self.values.get("user"))
        opts.cookie = _as_str(self.values.get("cookie"))
        opts.follow_redirects = bool(self.values.get("follow_redirects"))
        opts.max_redirects = _as_int(self.values.get("max_redirects"), "--max-redirs")
        opts.insecure = bool(self.values.get("insecure"))
        opts.compressed = bool(self.values.get("compressed"))
        opts.proxy = _as_str(self.values.get("proxy"))
        opts.connect_timeout = _as_float(self.values.get("connect_timeout"), "--connect-timeout")
        opts.max_time = _as_float(self.values.get("max_time"), "--max-time")
        opts.retry = _as_int(self.values.get("retry"), "--retry") or 0
        opts.include_headers = bool(self.values.get("include_headers"))
        opts.output = _as_str(self.values.get("output"))
        opts.remote_name = bool(self.values.get("remote_name"))
        opts.silent = bool(self.values.get("silent"))
        opts.show_error = bool(self.values.get("show_error"))
        opts.verbose = bool(self.values.get("verbose"))
        opts.fail = bool(self.values.get("fail"))
        opts.write_out = _as_str(self.values.get("write_out"))
        opts.cookie_jar = _as_str(self.values.get("cookie_jar"))

        self._derive_payload(opts)
        return opts

    def _derive_payload(self, opts: Options) -> None:
        """Collapse the payload flags into ``body`` plus ``content_type``."""
        if opts.json_body is not None and (opts.data or opts.data_raw or opts.data_urlencode):
            raise UsageError("cannot combine --json with -d/--data-raw/--data-urlencode")

        chunks = [_read_data_argument(v) for v in opts.data]
        chunks += [_read_data_argument(v, raw=True) for v in opts.data_raw]
        chunks += [_urlencode_argument(v) for v in opts.data_urlencode]

        if opts.json_body is not None:
            opts.body = opts.json_body
            opts.content_type = "application/json"
        elif chunks:
            opts.body = "&".join(chunks)
            opts.content_type = "application/x-www-form-urlencoded"


def _read_data_argument(value: str, raw: bool = False) -> str:
    """Expand a ``@filename`` data argument, mirroring ``curl -d @file``."""
    if not value.startswith("@"):
        # curl strips newlines from -d but keeps them in --data-raw
        return value if raw else value.replace("\r\n", "").replace("\n", "")
    path = value[1:]
    try:
        if path == "-":
            return sys.stdin.buffer.read().decode("utf-8", "replace")
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise UsageError(f"failed to read data from file '{path}': {exc.strerror}") from exc


def _urlencode_argument(value: str) -> str:
    """Implement curl's four ``--data-urlencode`` forms.

    ``content``      percent-encode the whole value
    ``=content``     percent-encode ``content``
    ``name=content`` encode only the content part, keep the name verbatim
    ``@file`` / ``name@file``  read the file first, then encode
    """
    if value.startswith("@"):
        return quote(_read_data_argument(value, raw=True), safe="")
    if value.startswith("="):
        return quote(value[1:], safe="")
    name, sep, content = value.partition("=")
    if not sep:
        return quote(value, safe="")
    if content.startswith("@"):
        content = _read_data_argument(content, raw=True)
    return f"{name}={quote(content, safe='')}"


def _upper(value: object) -> str | None:
    text = _as_str(value)
    return text.upper() if text else None


def _as_str(value: object) -> str | None:
    return None if value is None else str(value)


def _as_int(value: object, flag: str) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value))
    except ValueError:
        raise UsageError(f"invalid number '{value}' for {flag}") from None


def _as_float(value: object, flag: str) -> float | None:
    if value is None:
        return None
    try:
        result = float(str(value))
    except ValueError:
        raise UsageError(f"invalid number '{value}' for {flag}") from None
    if result <= 0:
        raise UsageError(f"{flag} must be greater than 0")
    return result


def parse(argv: Sequence[str]) -> Options:
    """Parse ``argv`` (without the program name) into :class:`Options`."""
    return Parser(argv).to_options()


def help_text(program: str = "curl-lite") -> str:
    """Render ``--help`` in a curl-ish layout."""
    lines = [
        f"Usage: {program} [options...] <url>",
        "",
        "A curl-like HTTP client. The scheme may be omitted, so",
        f"  {program} example.com/api?x=1",
        "is the same as",
        f"  {program} http://example.com/api?x=1",
        "",
        "Options:",
    ]
    for opt in OPTIONS:
        flags = f"  {opt.help_flags} {opt.arg}".rstrip()
        lines.append(f"{flags:<38}{opt.help}")
    lines += [
        "",
        "Examples:",
        f"  {program} https://example.com",
        f"  {program} -i -L https://example.com",
        f"""  {program} -X POST -H "Content-Type: application/json" --json '{{"a":1}}' example.com/api""",
        f"  {program} -o page.html -A 'Mozilla/5.0' https://example.com",
        f"  {program} -sS -o /dev/null -w '%{{http_code}}\\n' https://example.com",
        "",
        f"Run '{program} --version' for version information.",
    ]
    return "\n".join(lines)


def version_text() -> str:
    from . import __version__

    return f"curl-lite/{__version__} (python-urllib, zero dependencies)"