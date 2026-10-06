"""Unit tests for response rendering helpers."""

from __future__ import annotations

import io
import unittest

from curl_lite.args import parse
from curl_lite.output import Output, ProgressMeter, format_write_out
from curl_lite.transport import Response
from curl_lite.urls import filename_from_url


def make_response(**kwargs) -> Response:
    base = dict(
        url="http://e.com/a",
        effective_url="http://e.com/a",
        status=200,
        reason="OK",
        headers=[("Content-Type", "text/html"), ("Content-Length", "4")],
        body=b"body",
        http_version="1.1",
        elapsed=0.25,
        redirects=1,
        upload_size=9,
        ttfb=0.125,
    )
    base.update(kwargs)
    return Response(**base)


class HeaderBlockTests(unittest.TestCase):
    def test_status_line_includes_protocol(self) -> None:
        self.assertEqual(make_response().status_line(), "HTTP/1.1 200 OK")

    def test_http_1_0(self) -> None:
        self.assertEqual(make_response(http_version="1.0").status_line(), "HTTP/1.0 200 OK")

    def test_raw_headers_end_with_blank_line(self) -> None:
        block = make_response().raw_headers()
        self.assertTrue(block.startswith("HTTP/1.1 200 OK\r\n"))
        self.assertTrue(block.endswith("\r\n\r\n"))
        self.assertIn("Content-Length: 4\r\n", block)

    def test_header_lookup_is_case_insensitive(self) -> None:
        self.assertEqual(make_response().header("content-type"), "text/html")
        self.assertEqual(make_response().header("missing"), "")

    def test_size(self) -> None:
        self.assertEqual(make_response().size, 4)


class OutputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stream = io.BytesIO()
        self.output = Output(parse(["example.com"]), stdout=self.stream)

    def test_body_goes_to_the_given_stream(self) -> None:
        response = make_response()
        self.output.write_headers(response)
        self.output.write_response(response)
        self.assertEqual(self.stream.getvalue(), b"body")

    def test_include_headers_prepends_the_block(self) -> None:
        output = Output(parse(["-i", "example.com"]), stdout=self.stream)
        response = make_response()
        output.write_headers(response)
        output.write_response(response)
        self.assertTrue(self.stream.getvalue().startswith(b"HTTP/1.1 200 OK"))
        self.assertTrue(self.stream.getvalue().endswith(b"body"))

    def test_output_dash_targets_stdout(self) -> None:
        output = Output(parse(["-o", "-", "example.com"]), stdout=self.stream)
        self.assertEqual(output.target_for("http://e.com/a"), "-")
        output.open_target("http://e.com/a")
        output.write_response(make_response())
        self.assertEqual(self.stream.getvalue(), b"body")

    def test_output_flag_targets_the_file(self) -> None:
        output = Output(parse(["-o", "x.txt", "example.com"]), stdout=self.stream)
        self.assertEqual(output.target_for("http://e.com/a"), "x.txt")

    def test_remote_name_targets_the_basename(self) -> None:
        output = Output(parse(["-O", "example.com"]), stdout=self.stream)
        self.assertEqual(output.target_for("http://e.com/dir/a.txt"), "a.txt")

    def test_dash_is_not_a_filename(self) -> None:
        self.assertEqual(filename_from_url("http://e.com/"), "index.html")


class WriteOutTests(unittest.TestCase):
    def test_http_code(self) -> None:
        self.assertEqual(format_write_out("%{http_code}", make_response()), "200")

    def test_size_download(self) -> None:
        self.assertEqual(format_write_out("%{size_download}", make_response()), "4")

    def test_redirects(self) -> None:
        self.assertEqual(format_write_out("%{num_redirects}", make_response()), "1")

    def test_timings_are_formatted(self) -> None:
        self.assertEqual(format_write_out("%{time_total}", make_response()), "0.250000")

    def test_escaped_newline(self) -> None:
        self.assertEqual(format_write_out("a\\nb", make_response()), "a\nb")

    def test_url_effective(self) -> None:
        self.assertEqual(format_write_out("%{url_effective}", make_response(effective_url="http://x/y")), "http://x/y")

    def test_multiple_variables(self) -> None:
        self.assertEqual(format_write_out("%{http_code} %{size_download}", make_response()), "200 4")

    def test_unknown_variable_is_untouched(self) -> None:
        self.assertEqual(format_write_out("%{bogus}", make_response()), "%{bogus}")


class ProgressMeterTests(unittest.TestCase):
    def test_disabled_meter_writes_nothing(self) -> None:
        meter = ProgressMeter(100, "label", enabled=False)
        meter.update(50)
        meter.finish()  # must not raise

    def test_meter_writes_to_the_given_stream_when_a_tty(self) -> None:
        stream = io.StringIO()
        stream.isatty = lambda: True  # type: ignore[method-assign]
        meter = ProgressMeter(100, "label", enabled=True, stream=stream)
        meter.update(100)
        meter.finish()
        self.assertIn("100%", stream.getvalue())


if __name__ == "__main__":
    unittest.main()