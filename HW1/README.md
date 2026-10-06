# curl-lite

> A curl-like HTTP client written in pure Python — **zero runtime dependencies**, standard library only.

[![Tests](https://github.com/s111410513-oss/curl-lite-python/actions/workflows/tests.yml/badge.svg)](https://github.com/s111410513-oss/curl-lite-python/actions/workflows/tests.yml)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Deps](https://img.shields.io/badge/dependencies-none-success.svg)](pyproject.toml)

```console
$ curl-lite -sS -o NUL -w 'HTTP %{http_code}  %{size_download} bytes  %{time_total}s\n' https://httpbin.org/get
HTTP 200  293 bytes  1.016000s
```

---

## Why

`curl` is indispensable on a server, but on a machine without it — or when you want to
*read* the code rather than just run it — a few hundred lines of readable Python gets you
most of the way. This project reimplements the parts of curl's **behaviour** that scripts
actually depend on, using nothing but the Python standard library, and keeps every decision
visible in the source.

Design goals, in priority order:

1. **Familiarity** — the flags, the output shapes and the exit codes match curl, so muscle
   memory and existing scripts carry over.
2. **No dependencies** — `pip install curl-lite` pulls in nothing. Works on an air-gapped box.
3. **Legibility** — a declarative option table instead of 800 lines of `elif argv[0] == ...`.

## Install

```console
$ git clone https://github.com/s111410513-oss/curl-lite-python.git
$ cd curl-lite-python
$ python -m pip install -e .
```

Or run it straight from a checkout without installing:

```console
$ python -m curl_lite https://httpbin.org/get
```

Requires **Python 3.9+**. Windows, macOS and Linux.

## Usage

```console
$ curl-lite --help                      # the authoritative option list
```

### Everyday

```console
# Fetch a page
$ curl-lite https://example.com

# Show the response headers as well (-i), follow redirects (-L)
$ curl-lite -i -L https://httpbin.org/redirect/3

# Download to a file, named after the URL
$ curl-lite -O https://httpbin.org/image/png

# Just the status line (HEAD)
$ curl-lite -I https://httpbin.org/get
HTTP/1.1 200 OK
Date: Mon, 05 Oct 2026 17:43:10 GMT
Content-Type: application/json
Content-Length: 296
...
```

### Talking to an API

```console
# POST a form
$ curl-lite -d 'user=alice&message=hello' https://httpbin.org/post

# POST JSON (sets Content-Type for you)
$ curl-lite --json '{"name":"curl-lite","stars":42}' https://httpbin.org/post

# Custom headers, repeated -H, and a bare DELETE
$ curl-lite -X DELETE -H 'Authorization: Bearer TOKEN' -H 'X-Trace: abc' https://httpbin.org/delete

# Basic auth
$ curl-lite -u user:pass https://httpbin.org/basic-auth/user/pass

# Query string instead of a body
$ curl-lite -G -d 'q=a b' https://httpbin.org/get
```

### Scripts and automation

```console
# Health check: print only the status code
$ curl-lite -sS -o NUL -w '%{http_code}\n' https://httpbin.org/get
200

# Exit non-zero on an HTTP error, so this works in a shell script
$ curl-lite -fsS https://httpbin.org/status/404; echo "exit=$?"
curl-lite: (22) the requested URL returned error: 404
exit=22

# Follow redirects and report where you landed
$ curl-lite -sS -L -o NUL -w 'final=%{url_effective} redirects=%{num_redirects}\n' \
    https://httpbin.org/redirect/3
final=https://httpbin.org/get redirects=3

# Retry a flaky endpoint
$ curl-lite -sS --retry 3 https://httpbin.org/status/503

# Save and replay a session
$ curl-lite -c cookies.txt -o NUL https://httpbin.org/cookies/set?session=1
$ curl-lite -b cookies.txt https://httpbin.org/cookies

# Pipe JSON into another tool
$ curl-lite -sS https://httpbin.org/uuid | python -c "import json,sys;print(json.load(sys.stdin)['uuid'])"
```

### Debugging

```console
$ curl-lite -v https://httpbin.org/post -d 'x=1'
* Connected to httpbin.org port 443
* SSL connection using TLSv1.3
* Server certificate verified against the system trust store
> POST /post HTTP/1.1
> Host: httpbin.org
> User-Agent: curl-lite/0.1.0
> Accept: */*
> Content-Type: application/x-www-form-urlencoded
> Content-Length: 3
> [3 bytes data]
>
< HTTP/1.1 200 OK
< Content-Type: application/json
< Content-Length: 462
...

     Content-Length: 462
     Content-Type: application/json

0         0  100
0         0  3 << upload
0         0  462 << download
```

## Options

| Short | Long | Description |
| :--- | :--- | :--- |
| `-X` | `--request <method>` | HTTP method to use |
| `-G` | `--get` | Move `-d` data into the query string |
| `-d` | `--data <data>` | Send data in the body; `@file` reads a file, `@-` reads stdin |
|  | `--data-raw <data>` | Like `--data` but keeps newlines |
|  | `--data-urlencode <data>` | URL-encode first: `content`, `=content`, `name=content`, `@file` |
|  | `--json <json>` | JSON body with a matching `Content-Type` |
| `-I` | `--head` | Fetch headers only |
| `-H` | `--header <header>` | Add or replace a header (repeatable). `-H 'X:'` deletes it |
| `-A` | `--user-agent <name>` | Set `User-Agent` |
| `-e` | `--referer <url>` | Set `Referer` |
| `-u` | `--user <user:pass>` | HTTP basic auth |
| `-b` | `--cookie <data\|file>` | Inline cookie string, or a cookie file to load |
| `-L` | `--location` | Follow 3xx redirects |
|  | `--max-redirs <n>` | Redirect ceiling (default 50 with `-L`) |
| `-k` | `--insecure` | Skip TLS certificate verification |
|  | `--compressed` | Request gzip/deflate and decompress transparently |
| `-x` | `--proxy <url>` | Route through an HTTP/HTTPS/SOCKS proxy |
|  | `--connect-timeout <s>` | Connection timeout |
|  | `--max-time <s>` | Timeout for the whole transfer |
|  | `--retry <n>` | Retry transient failures with exponential backoff |
| `-i` | `--include` | Include response headers in the output |
| `-o` | `--output <file>` | Write the body to a file (`-o -` for stdout) |
| `-O` | `--remote-name` | Write the body to a file named after the URL |
| `-s` | `--silent` | Hide the progress meter and errors |
| `-S` | `--show-error` | Show errors even when silent |
| `-v` | `--verbose` | Print the request/response trace |
| `-f` | `--fail` | Suppress the body and exit 22 on HTTP ≥ 400 |
| `-w` | `--write-out <fmt>` | Print transfer statistics (`%{http_code}`, `%{time_total}`, …) |
| `-c` | `--cookie-jar <file>` | Write received cookies to a file |

### curl argument syntax that actually works

The parser is hand written, so curl's argument quirks behave identically:

```console
$ curl-lite -sSL https://example.com         # bundled short flags
$ curl-lite -H'Content-Type: text/plain' …  # value glued to the flag
$ curl-lite -H "Content-Type: text/plain" … # value detached
$ curl-lite --max-redirs=3 …                # long option with =
$ curl-lite --url https://example.com       # explicit URL
$ curl-lite example.com/api                 # scheme defaults to http://
```

## Behaviour worth knowing

**Redirects are opt-in.** Without `-L` a 3xx response is printed as-is, exactly like curl.
With `-L`, `301`/`302`/`303` are rewritten to `GET`, while `307`/`308` keep the original
method and body. `Authorization` and cookies are never forwarded to a different host.

**Exit codes match curl**, so shell scripts written against curl keep working:

| Code | Meaning | Code | Meaning |
| --- | :--- | --- | :--- |
| 0 | success | 22 | HTTP error (with `-f`) |
| 2 | bad command line | 23 | write error |
| 6 | could not resolve host | 28 | timeout |
| 7 | could not connect | 35 | TLS error |
| 47 | too many redirects | 130 | interrupted |

**Bytes are never mangled.** Bodies go straight to the binary stream, so binary downloads
and `-i` output are byte-for-byte correct — no newline translation, no encoding guessing.

**`-H 'Name:'` deletes a header.** An empty value removes it instead of sending it empty,
which is how curl behaves.

**`--retry` mirrors curl's retryable set** — connection failures plus `408`, `429`, `500`,
`502`, `503`, `504`, with exponential backoff capped at two seconds.

**Secrets are redacted in `-v` output.** curl prints `Authorization` verbatim; this one
prints `Basic <redacted 9 bytes>`.

## Architecture

```
curl_lite/
├── args.py        curl-style option table + parser → a validated Options object
├── urls.py        URL normalisation (missing scheme, default ports, -O filenames)
├── transport.py   urllib-based HTTP client: redirects, proxy, TLS, cookies, gzip, retry
├── output.py      body/header writing, progress meter, -w formatting
├── verbose.py     the -v trace, formatted like curl's
├── cookies.py     inline cookies, Netscape cookie files, -c jars
├── errors.py      error types carrying curl-compatible exit codes
└── cli.py         orchestration and the process entry point
```

Data flows one way: `args` produces an immutable `Options`, `transport` turns that into a
`Response`, and `cli` decides where the bytes go. Nothing in `args` or `urls` touches the
network, which is why most of the test suite runs without a socket.

Two design decisions worth calling out:

- **`args.py` does not use `argparse`.** `argparse` cannot express `-H"X: y"`, `-sSL`, or
  `--opt=value` alongside `--opt value`. A declarative `Option` table keeps the syntax in
  one place and the validation in one place.
- **`transport.py` overrides urllib's redirect handler.** urllib cannot forward a body across
  a `307`, and follows redirects when you did not ask it to. `CurlRedirectHandler` makes
  curl's rules explicit.

## Tests

```console
$ python -m unittest discover -s tests -t .
Ran 146 tests in 10.4s

OK
```

The suite starts a real `ThreadingHTTPServer` on an ephemeral port, so redirects, cookies,
gzip and binary bodies are exercised over actual sockets rather than mocks. It is offline,
dependency-free and cross-platform — CI runs it on Linux, macOS and Windows for Python
3.9–3.13.

| File | Covers |
| :--- | :--- |
| `tests/test_args.py` | the curl argument grammar and every validation error |
| `tests/test_urls.py` | URL normalisation edge cases |
| `tests/test_cookies.py` | inline cookies, Netscape files, jar round-trips |
| `tests/test_output.py` | header block rendering, `-w` formatting, progress meter |
| `tests/test_cli.py` | end-to-end transfers against a live local server |

## Differences from curl

Honest list of what is **not** implemented:

- **No connection reuse.** `urllib` opens a fresh connection per request, so every transfer
  sends `Connection: close` rather than keep-alive.
- **No multipart uploads.** `-F` / `--form` is not implemented.
- **No HTTP/2**, no client certificates (`--cert` / `--key`), no `--resolve` / `--interface`.
- **`br` and `zstd`** content encodings are passed through undecoded (not in the stdlib).
  `gzip` and `deflate` are decoded.
- **`-w` timings** other than `%{time_total}` and `%{time_starttransfer}` report `0.000000`;
  the stdlib exposes no per-phase timing.
- **`-w` does not implement curl's literal (`%{size}`) and variable (`%{var}`) grammar** —
  both are expanded as variables.

## License

MIT © 2026 [s111410513-oss](https://github.com/s111410513-oss)