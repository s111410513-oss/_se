"""URL normalisation helpers shared by the transport and the output layer."""

from __future__ import annotations

import posixpath
from urllib.parse import ParseResult, quote, unquote, urlparse, urlunparse

from .errors import UsageError

DEFAULT_PORTS = {"http": 80, "https": 443, "ws": 80, "wss": 443}
SUPPORTED_SCHEMES = frozenset({"http", "https"})


def normalize(raw: str) -> str:
    """Turn a user supplied URL into a canonical absolute http(s) URL.

    curl is famously forgiving: ``example.com``, ``example.com:8080/x`` and
    ``HTTP://Example.COM`` all work.  This keeps that behaviour.
    """
    url = raw.strip()
    if not url:
        raise UsageError("empty URL")

    if "://" not in url:
        # Not a URL and not a bare host: assume http, like curl's default.
        if _looks_like_missing_scheme(url):
            url = "http://" + url
        else:
            raise UsageError(f"unsupported URL scheme in '{raw}'", hint="only http and https are supported")

    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme not in SUPPORTED_SCHEMES:
        raise UsageError(f"unsupported URL scheme '{scheme}://'")

    if not parsed.hostname:
        raise UsageError(f"no host in URL '{raw}'")

    netloc = _build_netloc(parsed)
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"

    return urlunparse((scheme, netloc, path, "", "", ""))


def _looks_like_missing_scheme(url: str) -> bool:
    """Reject things like ``mailto:x`` or ``ftp://x`` that lack a host part."""
    lowered = url.lower()
    if lowered.startswith(("mailto:", "file:", "data:", "ftp:", "telnet:")):
        return False
    return "//" not in url.split("://")[0]


def _build_netloc(parsed: ParseResult) -> str:
    host = parsed.hostname or ""
    userinfo = ""
    if parsed.username:
        userinfo = quote(parsed.username, safe="")
        if parsed.password:
            userinfo += ":" + quote(parsed.password, safe="")
        userinfo += "@"

    host = host.encode("idna").decode("ascii") if _non_ascii(host) else host
    if ":" in host:  # IPv6 literal
        host = f"[{host}]"

    port = parsed.port
    if port is not None and port != DEFAULT_PORTS.get(parsed.scheme.lower()):
        return f"{userinfo}{host}:{port}"
    return f"{userinfo}{host}"


def _non_ascii(text: str) -> bool:
    return any(ord(char) > 127 for char in text)


def with_query(url: str, addition: str) -> str:
    """Append an already encoded query string to ``url`` (used by ``-G``)."""
    if not addition:
        return url
    parsed = urlparse(url)
    query = f"{parsed.query}&{addition}" if parsed.query else addition
    return urlunparse(parsed._replace(query=query))


def filename_from_url(url: str) -> str:
    """Derive the ``-O`` output name from a URL, the way curl does."""
    path = urlparse(url).path
    name = posixpath.basename(path.rstrip("/"))
    if not name:
        name = "index.html"
    return unquote(name)