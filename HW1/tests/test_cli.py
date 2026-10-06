"""End-to-end tests driving the CLI against a local HTTP server."""

from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from unittest import mock

from curl_lite import cli
from curl_lite.args import parse
from curl_lite.errors import (
    CouldntConnect,
    CouldntResolveHost,
    HTTPError,
    TooManyRedirects,
    UsageError,
)

from .helpers import (
    TestServer,
    echo,
    gzip_route,
    require_cookie,
    set_auth,
    set_cookie,
)


class FakeStdout:
    """Stands in for ``sys.stdout`` while capturing binary output."""

    def __init__(self) -> None:
        self.buffer = io.BytesIO()
        self._text = io.StringIO()

    def write(self, data: str) -> int:
        return self._text.write(data)

    def flush(self) -> None:
        pass

    def text(self) -> str:
        return self._text.getvalue()

    def bytes(self) -> bytes:
        return self.buffer.getvalue()


def invoke(argv: list[str]) -> tuple[int, FakeStdout, str]:
    """Run the CLI with stdout/stderr captured; returns ``(code, stdout, stderr)``."""
    stdout = FakeStdout()
    stderr = io.StringIO()
    with mock.patch.object(sys, "stdout", stdout), mock.patch.object(sys, "stderr", stderr):
        code = cli.main(argv)
    return code, stdout, stderr.getvalue()


class CLITestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = (
            TestServer()
            .start()
            .route("/echo", echo)
            .html("/hello", "<h1>hello</h1>")
            .route("/cookie", set_cookie)
            .route("/needs-cookie", require_cookie)
            .route("/gzip", gzip_route)
            .route("/auth", set_auth)
            .route("/404", lambda r, b: r._respond(404, b"missing"))
            .route("/500", lambda r, b: r._respond(500, b"boom"))
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.stop()

    def setUp(self) -> None:
        del self.server.requests[:]

    def url(self, path: str) -> str:
        return self.server.url(path)


class BasicRequestTests(CLITestCase):
    def test_get_writes_body_to_stdout(self) -> None:
        code, out, _ = invoke([self.url("/hello")])
        self.assertEqual(code, 0)
        self.assertEqual(out.bytes(), b"<h1>hello</h1>")

    def test_get_uses_get_method(self) -> None:
        invoke([self.url("/echo")])
        self.assertEqual(self.server.last_request()["method"], "GET")

    def test_default_user_agent(self) -> None:
        invoke([self.url("/echo")])
        self.assertTrue(self.server.last_request()["headers"]["user-agent"].startswith("curl-lite/"))

    def test_custom_user_agent(self) -> None:
        invoke(["-A", "my-agent/1.0", self.url("/echo")])
        self.assertEqual(self.server.last_request()["headers"]["user-agent"], "my-agent/1.0")

    def test_request_flag_changes_method(self) -> None:
        invoke(["-X", "DELETE", self.url("/echo")])
        self.assertEqual(self.server.last_request()["method"], "DELETE")

    def test_head_flag(self) -> None:
        code, out, _ = invoke(["-I", self.url("/hello")])
        self.assertEqual(code, 0)
        text = out.bytes().decode()
        self.assertIn("HTTP/1.1 200 OK", text)
        self.assertIn("Content-Type: text/html", text)
        self.assertTrue(text.endswith("\r\n\r\n"))

    def test_head_does_not_print_a_body(self) -> None:
        _, out, _ = invoke(["-I", self.url("/hello")])
        self.assertNotIn("<h1>hello</h1>", out.bytes().decode())

    def test_silent_head_still_prints_headers(self) -> None:
        _, out, _ = invoke(["-s", "-I", self.url("/hello")])
        self.assertIn("HTTP/1.1 200 OK", out.bytes().decode())

    def test_include_headers(self) -> None:
        _, out, _ = invoke(["-i", self.url("/hello")])
        text = out.bytes().decode()
        self.assertIn("HTTP/1.1 200 OK", text)
        self.assertIn("Content-Type: text/html", text)
        self.assertTrue(text.endswith("<h1>hello</h1>"))

    def test_scheme_is_optional(self) -> None:
        _, out, _ = invoke([self.url("/hello").replace("http://", "")])
        self.assertEqual(out.bytes(), b"<h1>hello</h1>")

    def test_unknown_flag_exits_2(self) -> None:
        code, _, err = invoke(["--bogus", self.url("/hello")])
        self.assertEqual(code, 2)
        self.assertIn("unknown option", err)


class DataTests(CLITestCase):
    def test_data_becomes_post(self) -> None:
        invoke(["-d", "a=1&b=2", self.url("/echo")])
        request = self.server.last_request()
        self.assertEqual(request["method"], "POST")
        self.assertEqual(request["body"], "a=1&b=2")

    def test_data_content_type(self) -> None:
        invoke(["-d", "a=1", self.url("/echo")])
        self.assertEqual(
            self.server.last_request()["headers"]["content-type"],
            "application/x-www-form-urlencoded",
        )

    def test_json_sets_content_type_and_body(self) -> None:
        invoke(["--json", '{"x":1}', self.url("/echo")])
        request = self.server.last_request()
        self.assertEqual(request["headers"]["content-type"], "application/json")
        self.assertEqual(request["body"], '{"x":1}')

    def test_data_from_file(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as handle:
            handle.write("from file")
            path = handle.name
        try:
            invoke(["-d", f"@{path}", self.url("/echo")])
            self.assertEqual(self.server.last_request()["body"], "from file")
        finally:
            os.unlink(path)

    def test_data_from_missing_file(self) -> None:
        code, _, err = invoke(["-d", "@nope.txt", self.url("/echo")])
        self.assertEqual(code, 2)
        self.assertIn("failed to read data", err)

    def test_get_moves_data_into_query(self) -> None:
        invoke(["-G", "-d", "a=1", self.url("/echo")])
        request = self.server.last_request()
        self.assertEqual(request["method"], "GET")
        self.assertEqual(request["path"], "/echo?a=1")
        self.assertEqual(request["body"], "")

    def test_multiple_data_flags(self) -> None:
        invoke(["-d", "a=1", "-d", "b=2", self.url("/echo")])
        self.assertEqual(self.server.last_request()["body"], "a=1&b=2")

    def test_urlencode(self) -> None:
        invoke(["--data-urlencode", "q=a b", self.url("/echo")])
        self.assertEqual(self.server.last_request()["body"], "q=a%20b")


class HeaderTests(CLITestCase):
    def test_custom_header(self) -> None:
        invoke(["-H", "X-Test: yes", self.url("/echo")])
        self.assertEqual(self.server.last_request()["headers"]["x-test"], "yes")

    def test_header_replaces_default_user_agent(self) -> None:
        invoke(["-H", "User-Agent: mine", self.url("/echo")])
        self.assertEqual(self.server.last_request()["headers"]["user-agent"], "mine")

    def test_empty_header_removes_it(self) -> None:
        invoke(["-H", "User-Agent:", self.url("/echo")])
        self.assertNotIn("user-agent", self.server.last_request()["headers"])

    def test_referer(self) -> None:
        invoke(["-e", "https://ref.example/", self.url("/echo")])
        self.assertEqual(self.server.last_request()["headers"]["referer"], "https://ref.example/")


class RedirectTests(CLITestCase):
    def test_redirect_is_not_followed_by_default(self) -> None:
        server = self.server
        server.redirect("/r1", "/hello")
        code, out, _ = invoke([self.url("/r1")])
        self.assertEqual(code, 0)
        self.assertEqual(out.bytes(), b"")

    def test_location_follows_redirect(self) -> None:
        self.server.redirect("/r2", "/hello")
        _, out, _ = invoke(["-L", self.url("/r2")])
        self.assertEqual(out.bytes(), b"<h1>hello</h1>")

    def test_max_redirs_zero_stops(self) -> None:
        self.server.redirect("/r3", "/hello")
        _, out, _ = invoke(["-L", "--max-redirs", "0", self.url("/r3")])
        self.assertEqual(out.bytes(), b"")

    def test_max_redirs_error(self) -> None:
        self.server.redirect("/r4", "/hello")
        code, _, err = invoke(["-L", "--max-redirs", "1", self.url("/r4")])
        # exactly one redirect is allowed, so this succeeds
        self.assertEqual(code, 0)

    def test_redirect_loop_is_detected(self) -> None:
        self.server.redirect("/loop", "/loop")
        code, _, err = invoke(["-L", "--max-redirs", "3", self.url("/loop")])
        self.assertEqual(code, 47)
        self.assertIn("redirects followed", err)

    def test_redirect_preserves_headers(self) -> None:
        self.server.redirect("/to-echo", "/echo")
        invoke(["-L", "-H", "X-Keep: 1", self.url("/to-echo")])
        self.assertEqual(self.server.last_request()["headers"]["x-keep"], "1")

    def test_303_becomes_get(self) -> None:
        self.server.redirect("/see-other", "/echo", status=303)
        invoke(["-L", "-d", "a=1", self.url("/see-other")])
        request = self.server.last_request()
        self.assertEqual(request["method"], "GET")
        self.assertEqual(request["body"], "")

    def test_307_keeps_method_and_body(self) -> None:
        self.server.redirect("/keep", "/echo", status=307)
        invoke(["-L", "-d", "a=1", self.url("/keep")])
        request = self.server.last_request()
        self.assertEqual(request["method"], "POST")
        self.assertEqual(request["body"], "a=1")

    def test_auth_survives_a_same_host_redirect(self) -> None:
        self.server.redirect("/to-auth", "/auth")
        invoke(["-L", "-u", "user:pass", self.url("/to-auth")])
        self.assertEqual(self.server.last_request()["headers"]["authorization"], "Basic dXNlcjpwYXNz")


class OutputFileTests(CLITestCase):
    def test_output_flag_writes_file(self) -> None:
        directory = tempfile.mkdtemp()
        path = os.path.join(directory, "out.html")
        _, out, _ = invoke(["-o", path, self.url("/hello")])
        self.assertEqual(out.bytes(), b"")
        with open(path, "rb") as handle:
            self.assertEqual(handle.read(), b"<h1>hello</h1>")

    def test_output_dash_means_stdout(self) -> None:
        _, out, _ = invoke(["-o", "-", self.url("/hello")])
        self.assertEqual(out.bytes(), b"<h1>hello</h1>")

    def test_remote_name_uses_url_basename(self) -> None:
        directory = tempfile.mkdtemp()
        cwd = os.getcwd()
        os.chdir(directory)
        try:
            invoke(["-O", self.url("/hello")])
            self.assertTrue(os.path.exists(os.path.join(directory, "hello")))
        finally:
            os.chdir(cwd)

    def test_include_headers_with_output_file(self) -> None:
        directory = tempfile.mkdtemp()
        path = os.path.join(directory, "both.txt")
        invoke(["-i", "-o", path, self.url("/hello")])
        with open(path, "rb") as handle:
            content = handle.read()
        self.assertIn(b"HTTP/1.1 200 OK", content)
        self.assertTrue(content.endswith(b"<h1>hello</h1>"))

    def test_binary_body_is_not_mangled(self) -> None:
        payload = bytes(range(256))

        def binary(request, body: bytes) -> None:
            request._respond(200, payload, {"Content-Type": "application/octet-stream"})

        self.server.route("/binary", binary)
        _, out, _ = invoke([self.url("/binary")])
        self.assertEqual(out.bytes(), payload)


class FailTests(CLITestCase):
    def test_404_body_is_shown_by_default(self) -> None:
        code, out, _ = invoke([self.url("/404")])
        self.assertEqual(code, 0)
        self.assertEqual(out.bytes(), b"missing")

    def test_fail_suppresses_body_and_exits_22(self) -> None:
        code, out, err = invoke(["-f", self.url("/404")])
        self.assertEqual(code, 22)
        self.assertEqual(out.bytes(), b"")
        self.assertIn("returned error: 404", err)

    def test_fail_allows_success(self) -> None:
        code, out, _ = invoke(["-f", self.url("/hello")])
        self.assertEqual(code, 0)
        self.assertEqual(out.bytes(), b"<h1>hello</h1>")


class CookieTests(CLITestCase):
    def test_inline_cookie_is_sent(self) -> None:
        invoke(["-b", "session=abc123", self.url("/needs-cookie")])
        self.assertEqual(self.server.last_request()["headers"]["cookie"], "session=abc123")

    def test_cookie_jar_round_trip(self) -> None:
        jar = os.path.join(tempfile.mkdtemp(), "cookies.txt")
        invoke(["-c", jar, self.url("/cookie")])
        self.assertTrue(os.path.exists(jar))
        invoke(["-b", jar, self.url("/needs-cookie")])
        self.assertIn("session=abc123", self.server.last_request()["headers"]["cookie"])

    def test_inline_cookie_overrides_header_removal(self) -> None:
        invoke(["-b", "a=1; b=2", self.url("/echo")])
        cookie = self.server.last_request()["headers"]["cookie"]
        self.assertIn("a=1", cookie)
        self.assertIn("b=2", cookie)

    def test_missing_cookie_file_is_ignored(self) -> None:
        code, out, _ = invoke(["-b", os.path.join(tempfile.mkdtemp(), "none.txt"), self.url("/hello")])
        self.assertEqual(code, 0)
        self.assertEqual(out.bytes(), b"<h1>hello</h1>")


class AuthTests(CLITestCase):
    def test_basic_auth(self) -> None:
        invoke(["-u", "user:pass", self.url("/auth")])
        self.assertEqual(self.server.last_request()["headers"]["authorization"], "Basic dXNlcjpwYXNz")

    def test_auth_header_is_redacted_in_verbose(self) -> None:
        _, _, err = invoke(["-u", "user:pass", "-v", self.url("/auth")])
        self.assertIn("<redacted", err)
        self.assertNotIn("dXNlcjpwYXNz", err)


class CompressionTests(CLITestCase):
    def test_compressed_is_decompressed(self) -> None:
        _, out, _ = invoke(["--compressed", self.url("/gzip")])
        self.assertEqual(out.bytes(), b"compressed payload")

    def test_without_flag_the_raw_bytes_are_shown(self) -> None:
        _, out, _ = invoke([self.url("/gzip")])
        self.assertNotEqual(out.bytes(), b"compressed payload")

    def test_accept_encoding_is_sent(self) -> None:
        invoke(["--compressed", self.url("/echo")])
        self.assertIn("gzip", self.server.last_request()["headers"]["accept-encoding"])


class VerboseTests(CLITestCase):
    def test_verbose_shows_request_and_response(self) -> None:
        _, _, err = invoke(["-v", self.url("/hello")])
        self.assertIn("> GET /hello HTTP/1.1", err)
        self.assertIn("> Host: 127.0.0.1", err)
        self.assertIn("< HTTP/1.1 200 OK", err)
        self.assertIn("< Content-Type: text/html", err)

    def test_verbose_shows_body_size(self) -> None:
        _, _, err = invoke(["-v", "-d", "hello", self.url("/echo")])
        self.assertIn("[5 bytes data]", err)

    def test_quiet_hides_errors(self) -> None:
        code, _, err = invoke(["-s", self.url("/404"), "-f"])
        self.assertEqual(code, 22)
        self.assertEqual(err, "")

    def test_show_error_overrides_silent(self) -> None:
        code, _, err = invoke(["-sS", self.url("/404"), "-f"])
        self.assertEqual(code, 22)
        self.assertIn("returned error: 404", err)


class WriteOutTests(CLITestCase):
    def test_http_code(self) -> None:
        _, out, _ = invoke(["-o", os.devnull, "-w", "%{http_code}", self.url("/hello")])
        self.assertEqual(out.text(), "200\n")

    def test_multiple_variables_and_escapes(self) -> None:
        _, out, _ = invoke(
            ["-o", os.devnull, "-w", "%{http_code} %{size_download} %{url_effective}\\n", self.url("/hello")]
        )
        self.assertEqual(out.text(), f"200 14 {self.url('/hello')}\n")

    def test_unknown_variable_is_left_alone(self) -> None:
        _, out, _ = invoke(["-o", os.devnull, "-w", "%{nope}\\n", self.url("/hello")])
        self.assertEqual(out.text(), "%{nope}\n")


class RetryTests(CLITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.attempts = {"n": 0}

    def _flaky(self, fail_times: int, status: int = 503) -> None:
        def handler(request, body: bytes) -> None:
            self.attempts["n"] += 1
            if self.attempts["n"] <= fail_times:
                request._respond(status, b"try again")
            else:
                request._respond(200, b"recovered", {"Content-Type": "text/plain"})

        self.server.route("/flaky", handler)

    def test_retry_recovers_from_transient_status(self) -> None:
        self._flaky(2)
        _, out, _ = invoke(["--retry", "3", self.url("/flaky")])
        self.assertEqual(out.bytes(), b"recovered")
        self.assertEqual(self.attempts["n"], 3)

    def test_retry_gives_up_after_n_attempts(self) -> None:
        self._flaky(99)
        _, out, _ = invoke(["--retry", "1", self.url("/flaky")])
        self.assertEqual(out.bytes(), b"try again")
        self.assertEqual(self.attempts["n"], 2)

    def test_no_retry_without_the_flag(self) -> None:
        self._flaky(99)
        _, out, _ = invoke([self.url("/flaky")])
        self.assertEqual(out.bytes(), b"try again")
        self.assertEqual(self.attempts["n"], 1)

    def test_404_is_not_retried(self) -> None:
        self._flaky(99, status=404)
        invoke(["--retry", "3", self.url("/flaky")])
        self.assertEqual(self.attempts["n"], 1)


class NetworkErrorTests(unittest.TestCase):
    def test_connection_refused(self) -> None:
        # port 1 is reserved and nothing listens there
        code, _, err = invoke(["http://127.0.0.1:1/"])
        self.assertEqual(code, 7)
        self.assertIn("could not connect", err)

    def test_unknown_host(self) -> None:
        code, _, err = invoke(["http://this-host-does-not-exist.invalid/"])
        self.assertEqual(code, 6)
        self.assertIn("could not resolve host", err)


class VersionAndHelpTests(unittest.TestCase):
    def test_version(self) -> None:
        code, out, _ = invoke(["--version"])
        self.assertEqual(code, 0)
        self.assertTrue(out.text().startswith("curl-lite/"))

    def test_help(self) -> None:
        code, out, _ = invoke(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("Usage: curl-lite", out.text())

    def test_help_needs_no_url(self) -> None:
        code, out, _ = invoke(["--help"])
        self.assertEqual(code, 0)


class ParseOnlyTests(unittest.TestCase):
    """Checks that parsing never touches the network."""

    def test_usage_error_has_exit_code_2(self) -> None:
        self.assertEqual(UsageError("x").exit_code, 2)
        self.assertEqual(HTTPError("x").exit_code, 22)
        self.assertEqual(CouldntConnect("x").exit_code, 7)
        self.assertEqual(CouldntResolveHost("x").exit_code, 6)
        self.assertEqual(TooManyRedirects("x").exit_code, 47)

    def test_parse_returns_options_without_io(self) -> None:
        opts = parse(["-s", "-o", "x", "example.com"])
        self.assertEqual(opts.output, "x")


if __name__ == "__main__":
    unittest.main()