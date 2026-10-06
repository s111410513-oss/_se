"""HTTP transport built on top of :mod:`urllib.request`.

The goal is curl's behaviour rather than urllib's: the HTTP method survives
redirects, ``-L`` is opt-in, a custom ``Host:`` header wins over the URL, and
network level failures are translated into curl's exit codes.
"""

from __future__ import annotations

import base64
import gzip
import http.cookiejar
import socket
import ssl
import time
import zlib
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import (
    HTTPCookieProcessor,
    HTTPRedirectHandler,
    HTTPSHandler,
    ProxyHandler,
    Request,
    build_opener,
)

from . import __version__
from . import cookies as cookie_utils
from .args import Options
from .errors import (
    CouldntConnect,
    CouldntResolveHost,
    HTTPError as CurlHTTPError,
    SSLError,
    Timeout as CurlTimeout,
    TooManyRedirects,
)
from .urls import normalize, with_query

DEFAULT_MAX_REDIRECTS = 50
USER_AGENT = f"curl-lite/{__version__}"
ACCEPT_ENCODINGS = "gzip, deflate"
# Statuses curl also considers retryable with --retry.
RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})
# Headers that describe the previous request and must not survive a redirect.
_DROP_ON_REDIRECT = frozenset({"host", "content-length", "cookie"})


@dataclass
class Response:
    """Everything the CLI needs to know about one completed transfer."""

    url: str  # the URL that produced this response
    effective_url: str  # the final URL after redirects
    status: int
    reason: str
    headers: list[tuple[str, str]]
    body: bytes
    http_version: str
    elapsed: float
    redirects: int
    content_type: str = ""
    jar: http.cookiejar.CookieJar | None = None
    cert_verified: bool = True
    upload_size: int = 0
    ttfb: float = 0.0  # time until the response headers arrived

    @property
    def size(self) -> int:
        return len(self.body)

    def header(self, name: str) -> str:
        lowered = name.lower()
        for key, value in self.headers:
            if key.lower() == lowered:
                return value
        return ""

    def status_line(self) -> str:
        return f"HTTP/{self.http_version} {self.status} {self.reason}".rstrip()

    def raw_headers(self) -> str:
        """The status line plus the header block, CRLF terminated."""
        lines = [self.status_line()]
        lines += [f"{key}: {value}" for key, value in self.headers]
        return "".join(f"{line}\r\n" for line in lines) + "\r\n"

    def header_block(self) -> bytes:
        return self.raw_headers().encode("iso-8859-1")


class CurlRedirectHandler(HTTPRedirectHandler):
    """Redirect handler implementing curl's method-rewriting rules.

    curl turns 301/302/303 into ``GET`` but keeps the original method and body
    for 307/308.  urllib's stock handler cannot do the latter at all, so the
    decision is made explicitly here.
    """

    def __init__(self, max_redirects: int, counter: list[int], follow: bool = True) -> None:
        self.max_redirects = max_redirects
        self.counter = counter
        self.follow = follow

    def redirect_request(  # type: ignore[override]
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> Request | None:
        if not self.follow:
            return None  # urllib then surfaces the 3xx as an HTTPError

        self.counter[0] += 1
        if self.counter[0] > self.max_redirects:
            raise TooManyRedirects(
                f"maximum ({self.max_redirects}) redirects followed",
                hint="raise the limit with --max-redirs",
            )

        method = req.get_method()
        data = req.data
        if code not in (307, 308):  # curl's default: rewrite to GET
            method = "HEAD" if method == "HEAD" else "GET"
            data = None

        dropped = set(_DROP_ON_REDIRECT)
        if _host_of(newurl) != _host_of(req.full_url):
            dropped.add("authorization")  # never leak credentials off-host
        headers_to_keep = {k: v for k, v in req.headers.items() if k.lower() not in dropped}

        return Request(
            newurl,
            data=data,
            headers=headers_to_keep,
            origin_req_host=req.origin_req_host,
            method=method,
        )


def _host_of(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def build_ssl_context(insecure: bool) -> ssl.SSLContext:
    """Return a TLS context, honouring ``-k`` / ``--insecure``."""
    context = ssl.create_default_context()
    if insecure:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    return context


def build_proxy_handler(proxy: str | None) -> ProxyHandler:
    """Turn ``-x`` into a urllib proxy handler; ``None`` means "no proxy"."""
    if not proxy:
        return ProxyHandler({})
    scheme, _, rest = proxy.partition("://")
    if not rest:
        rest, scheme = scheme, "http"
    if not rest:
        raise CouldntConnect("invalid proxy: no host given")
    scheme = scheme.lower()
    if scheme not in ("http", "https", "socks5", "socks5h", "socks4", "socks4a"):
        raise CouldntConnect(f"unsupported proxy scheme '{scheme}'")
    return ProxyHandler({"http": f"{scheme}://{rest}", "https": f"{scheme}://{rest}"})


def basic_auth_header(user: str) -> str:
    """Encode ``-u user:password`` into an ``Authorization`` header value."""
    if ":" not in user:
        user += ":"
    token = base64.b64encode(user.encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def split_header(raw: str) -> tuple[str, str]:
    """Split ``Name: value``; a colon-less header means an empty value.

    That convention lets ``-H 'Accept:'`` delete a header curl would send.
    """
    if ":" not in raw:
        return raw.strip(), ""
    name, _, value = raw.partition(":")
    return name.strip(), value.strip()


class Session:
    """Per-invocation HTTP client that shares cookies across requests."""

    def __init__(self, opts: Options) -> None:
        self.opts = opts
        self._redirects = [0]
        handlers: list = [build_proxy_handler(opts.proxy), HTTPSHandler(context=build_ssl_context(opts.insecure))]
        limit = opts.max_redirects if opts.max_redirects is not None else DEFAULT_MAX_REDIRECTS
        handlers.append(CurlRedirectHandler(limit, self._redirects, follow=opts.follow_redirects))
        self.opener = build_opener(*handlers)
        # Suppress urllib's own "Python-urllib/3.11" User-Agent; curl-lite
        # sends its own (or none at all, when -H deletes it).
        self.opener.addheaders = []
        self.jar: http.cookiejar.CookieJar = cookie_utils.jar_with(
            opts.cookie, self._default_host()
        )
        self.opener.add_handler(HTTPCookieProcessor(self.jar))

    def _default_host(self) -> str:
        if not self.opts.urls:
            return ""
        try:
            return urlparse(normalize(self.opts.urls[0])).hostname or ""
        except Exception:  # a bad URL is reported later, by the CLI
            return ""

    # -- request building --------------------------------------------------

    def prepare(self, url: str) -> tuple[str, str, dict[str, str], bytes | None]:
        """Return ``(url, method, headers, body)`` for one transfer."""
        opts = self.opts
        url = normalize(url)
        payload = opts.body

        if payload is not None and opts.use_get:
            url = with_query(url, payload)
            payload = None

        method = opts.method
        if payload is not None:
            body: bytes | None = payload.encode("utf-8")
            method = method or "POST"
        else:
            body = None
            method = method or ("HEAD" if opts.head else "GET")

        headers = self._build_headers(url)

        if body is not None:
            headers.setdefault("Content-Length", str(len(body)))
        elif method in ("POST", "PUT", "PATCH") and "content-length" not in {k.lower() for k in headers}:
            # Servers wait for a body when a body-carrying method is declared.
            headers["Content-Length"] = "0"

        return url, method, headers, body

    def _build_headers(self, url: str) -> dict[str, str]:
        opts = self.opts
        headers: dict[str, str] = {"Accept": "*/*"}

        host = urlparse(url).hostname or ""
        if host:
            headers["Host"] = host
        if opts.user_agent:
            headers["User-Agent"] = opts.user_agent
        if opts.referer:
            headers["Referer"] = opts.referer
        if opts.user:
            headers["Authorization"] = basic_auth_header(opts.user)
        if opts.compressed:
            headers["Accept-Encoding"] = ACCEPT_ENCODINGS
        if opts.content_type:
            headers["Content-Type"] = opts.content_type

        # -H is applied last so that it always wins, including deletions.
        deleted: set[str] = set()
        for raw in opts.headers:
            name, value = split_header(raw)
            if not name:
                continue
            lowered = name.lower()
            for existing in [key for key in headers if key.lower() == lowered]:
                headers.pop(existing)
            if value == "":
                deleted.add(lowered)  # curl's "remove this header" syntax
                continue
            headers[name] = value

        if "user-agent" not in deleted and not any(key.lower() == "user-agent" for key in headers):
            headers["User-Agent"] = USER_AGENT
        return headers

    # -- execution ---------------------------------------------------------

    def fetch(self, url: str) -> Response:
        """Perform one transfer, retrying transient failures when asked."""
        attempts = max(0, self.opts.retry) + 1
        for attempt in range(attempts):
            try:
                response = self._fetch_once(url)
            except (CurlHTTPError, TooManyRedirects):
                raise
            except (CouldntConnect, CouldntResolveHost, CurlTimeout) as exc:
                if attempt + 1 >= attempts:
                    raise
                time.sleep(_backoff(attempt))
                last_error: Exception | None = exc
            else:
                if response.status not in RETRYABLE_STATUS or attempt + 1 >= attempts:
                    return response
                time.sleep(_backoff(attempt))
        raise last_error or CouldntConnect(f"could not connect to {url}")

    def _fetch_once(self, url: str) -> Response:
        target, method, headers, body = self.prepare(url)
        request = Request(target, data=body, headers=headers, method=method)
        request.add_unredirected_header("Connection", "close")

        cookie_header = self._cookie_header(target)
        if cookie_header and "cookie" not in {k.lower() for k in headers}:
            request.add_unredirected_header("Cookie", cookie_header)

        self._redirects[0] = 0
        started = time.monotonic()
        try:
            raw = self.opener.open(request, timeout=self.opts.max_time or self.opts.connect_timeout)
        except HTTPError as exc:
            elapsed = time.monotonic() - started
            return self._handle_http_error(exc, elapsed, upload_size=len(body or b""))
        except URLError as exc:
            raise _translate_error(exc, target) from exc
        except socket.timeout as exc:
            raise CurlTimeout(f"connection timed out while connecting to {_host_of(target)}") from exc
        except ssl.SSLError as exc:
            raise SSLError(f"TLS error connecting to {_host_of(target)}: {getattr(exc, 'reason', exc)}") from exc
        except OSError as exc:
            raise CouldntConnect(f"could not connect to {_host_of(target)}: {exc}") from exc

        ttfb = time.monotonic() - started
        elapsed = time.monotonic() - started
        with raw:
            payload = raw.read()
            response = Response(
                url=target,
                effective_url=raw.geturl(),
                status=raw.status,
                reason=raw.reason or reason_for(raw.status),
                headers=list(raw.headers.items()),
                body=payload,
                http_version=_http_version(raw),
                elapsed=elapsed,
                redirects=self._redirects[0],
                content_type=raw.headers.get_content_type(),
                jar=self.jar,
                cert_verified=not self.opts.insecure,
                upload_size=len(body or b""),
                ttfb=ttfb,
            )
        self._decode(response)
        return response

    def _handle_http_error(self, exc: HTTPError, elapsed: float, upload_size: int = 0) -> Response:
        with exc:
            payload = exc.read()
        response = Response(
            url=exc.url or "",
            effective_url=exc.url or "",
            status=exc.code,
            reason=exc.reason or reason_for(exc.code),
            headers=list(exc.headers.items()) if exc.headers else [],
            body=payload,
            http_version=_http_version(exc),
            elapsed=elapsed,
            redirects=self._redirects[0],
            jar=self.jar,
            cert_verified=not self.opts.insecure,
            upload_size=upload_size,
        )
        self._decode(response)
        if self.opts.fail and response.status >= 400:
            raise CurlHTTPError(f"the requested URL returned error: {response.status}")
        return response

    def _cookie_header(self, url: str) -> str:
        probe = Request(url)
        self.jar.add_cookie_header(probe)
        return probe.get_header("Cookie", "")

    # -- content decoding --------------------------------------------------

    def _decode(self, response: Response) -> None:
        """Transparently undo ``--compressed`` (Content-Encoding removal)."""
        encoding = response.header("Content-Encoding").strip().lower()
        if not self.opts.compressed or not encoding or not response.body:
            return
        try:
            if encoding == "gzip":
                response.body = gzip.decompress(response.body)
            elif encoding == "deflate":
                response.body = zlib.decompress(response.body, -zlib.MAX_WBITS)
            else:  # br/zstd are not in the stdlib; hand the bytes over as-is
                return
        except (OSError, zlib.error) as exc:
            raise CouldntConnect(f"failed to decode the '{encoding}' response: {exc}") from exc
        stale = ("content-encoding", "content-length")
        response.headers = [(k, v) for k, v in response.headers if k.lower() not in stale]

    # -- cookies -----------------------------------------------------------

    def store_cookies(self, path: str | None) -> None:
        if path:
            cookie_utils.save(self.jar, path)


def _backoff(attempt: int) -> float:
    """Exponential backoff capped at two seconds, like curl's --retry."""
    return min(0.25 * 2**attempt, 2.0)


def reason_for(status: int) -> str:
    try:
        return HTTPStatus(status).phrase
    except ValueError:
        return "Unknown"


def _http_version(raw: Any) -> str:
    version = getattr(raw, "version", None)
    if isinstance(version, int):
        return "1.1" if version >= 11 else "1.0"
    return "1.1"


def _translate_error(exc: URLError, url: str) -> Exception:
    reason = exc.reason
    host = _host_of(url) or url
    if isinstance(reason, ssl.SSLCertVerificationError):
        return SSLError(
            f"TLS certificate verification failed for {host}: {reason.reason}",
            hint="pass --insecure (-k) to skip verification",
        )
    if isinstance(reason, ssl.SSLError):
        return SSLError(f"TLS error connecting to {host}: {getattr(reason, 'reason', reason)}")
    if isinstance(reason, socket.gaierror):
        return CouldntResolveHost(f"could not resolve host: {host}")
    if isinstance(reason, (socket.timeout, TimeoutError)):
        return CurlTimeout(f"operation timed out while connecting to {host}")
    if isinstance(reason, ConnectionRefusedError):
        return CouldntConnect(f"could not connect to {host}: connection refused")
    if isinstance(reason, OSError) and reason.errno == 11001:
        return CouldntResolveHost(f"could not resolve host: {host}")
    return CouldntConnect(f"could not connect to {host}: {reason}")