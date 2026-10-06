"""Cookie handling: inline ``-b`` values, cookie files and ``-c`` jars."""

from __future__ import annotations

import re
from http.cookiejar import Cookie, CookieJar, LoadError, MozillaCookieJar
from pathlib import Path

from .errors import UsageError

# curl treats a -b argument as a filename only when it looks like a path,
# i.e. it contains no '=' character.
_LOOKS_LIKE_DATA = re.compile(r"=")


def looks_like_data(argument: str) -> bool:
    """True when ``-b`` should be interpreted as an inline cookie string."""
    return bool(_LOOKS_LIKE_DATA.search(argument))


def parse_inline(value: str) -> list[str]:
    """Normalise ``a=1; b=2`` into a list of ``name=value`` pairs."""
    pairs = []
    for chunk in value.split(";"):
        chunk = chunk.strip()
        if chunk:
            pairs.append(chunk)
    return pairs


def load_file(path: str) -> MozillaCookieJar:
    """Read a Netscape-format cookie file into a jar.

    curl ignores a missing cookie file, so we do the same; a malformed one is
    reported, because silently dropping every cookie is worse.
    """
    jar = MozillaCookieJar(path)
    try:
        jar.load(ignore_discard=True, ignore_expires=True)
    except FileNotFoundError:
        pass
    except LoadError as exc:
        raise UsageError(f"failed to load cookies from '{path}': {exc}") from exc
    except OSError as exc:
        raise UsageError(f"failed to read cookie file '{path}': {exc}") from exc
    return jar


def _to_cookie(name: str, value: str, domain: str = "", path: str = "/") -> Cookie:
    return Cookie(
        version=0,
        name=name,
        value=value,
        port=None,
        port_specified=False,
        domain=domain,
        domain_specified=bool(domain),
        domain_initial_dot=domain.startswith("."),
        path=path,
        path_specified=True,
        secure=False,
        expires=None,
        discard=True,
        comment=None,
        comment_url=None,
        rest={},
    )


def jar_with(value: str | None, default_domain: str) -> CookieJar:
    """Build a cookie jar from the ``-b`` argument.

    ``value`` may be an inline cookie string or the path of a cookie file; the
    domain of the target request is used so that inline cookies are actually
    sent (a cookie cannot be attached to a request before its host is known).
    """
    jar: MozillaCookieJar = MozillaCookieJar()
    if not value:
        return jar

    if looks_like_data(value):
        for pair in parse_inline(value):
            name, _, cookie_value = pair.partition("=")
            name = name.strip()
            if not name:
                continue
            jar.set_cookie(_to_cookie(name, cookie_value.strip(), domain=default_domain))
    else:
        for cookie in load_file(value):
            if cookie.domain in ("", default_domain):
                jar.set_cookie(cookie)
    return jar


def save(jar: CookieJar, path: str) -> None:
    """Persist ``jar`` to ``path`` in Netscape format, like ``curl -c``."""
    target = Path(path)
    try:
        parent = target.parent
        if str(parent) and not parent.exists():
            parent.mkdir(parents=True, exist_ok=True)
        jar.save(path, ignore_discard=True, ignore_expires=True)  # type: ignore[arg-type]
    except (OSError, AttributeError) as exc:
        raise UsageError(f"failed to write cookie jar '{path}': {exc}") from exc