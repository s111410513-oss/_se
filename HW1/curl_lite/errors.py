"""Error types mapped onto curl-compatible exit codes."""

from __future__ import annotations

# Exit codes mirror the well known curl values so shell scripts written for
# curl keep working when they are pointed at curl-lite.
EXIT_OK = 0
EXIT_UNSUPPORTED_FEATURE = 1
EXIT_FAILED_INIT = 2
EXIT_COULDNT_RESOLVE_HOST = 6
EXIT_COULDNT_CONNECT = 7
EXIT_HTTP_RETURNED_ERROR = 22
EXIT_WRITE_ERROR = 23
EXIT_OPERATION_TIMEDOUT = 28
EXIT_SSL_CONNECT_ERROR = 35
EXIT_TOO_MANY_REDIRECTS = 47
EXIT_BAD_FUNCTION_ARGUMENT = 2


class CurlLiteError(Exception):
    """Base class for every error curl-lite reports to the user."""

    exit_code = EXIT_UNSUPPORTED_FEATURE

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint


class UsageError(CurlLiteError):
    """Bad command line: unknown flag, missing value, conflicting options."""

    exit_code = EXIT_BAD_FUNCTION_ARGUMENT


class CouldntResolveHost(CurlLiteError):
    exit_code = EXIT_COULDNT_RESOLVE_HOST


class CouldntConnect(CurlLiteError):
    exit_code = EXIT_COULDNT_CONNECT


class HTTPError(CurlLiteError):
    """Raised by ``--fail`` when the server answers with >= 400."""

    exit_code = EXIT_HTTP_RETURNED_ERROR


class WriteError(CurlLiteError):
    exit_code = EXIT_WRITE_ERROR


class Timeout(CurlLiteError):
    exit_code = EXIT_OPERATION_TIMEDOUT


class SSLError(CurlLiteError):
    exit_code = EXIT_SSL_CONNECT_ERROR


class TooManyRedirects(CurlLiteError):
    exit_code = EXIT_TOO_MANY_REDIRECTS