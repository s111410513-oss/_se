"""Tests for the curl-flavoured command line parser."""

from __future__ import annotations

import unittest

from curl_lite.args import help_text, parse, version_text
from curl_lite.errors import UsageError


class OptionSyntaxTests(unittest.TestCase):
    def test_bundled_short_flags(self) -> None:
        opts = parse(["-sSL", "example.com"])
        self.assertTrue(opts.silent)
        self.assertTrue(opts.show_error)
        self.assertTrue(opts.follow_redirects)
        self.assertEqual(opts.urls, ["example.com"])

    def test_glued_short_value(self) -> None:
        opts = parse(["-HAccept: text/plain", "example.com"])
        self.assertEqual(opts.headers, ["Accept: text/plain"])

    def test_short_value_with_equals(self) -> None:
        opts = parse(["-d=name=value", "example.com"])
        self.assertEqual(opts.data, ["name=value"])

    def test_detached_short_value(self) -> None:
        opts = parse(["-o", "out.bin", "example.com"])
        self.assertEqual(opts.output, "out.bin")

    def test_long_value_with_equals(self) -> None:
        opts = parse(["--request=PUT", "example.com"])
        self.assertEqual(opts.method, "PUT")

    def test_long_value_detached(self) -> None:
        opts = parse(["--max-redirs", "3", "example.com"])
        self.assertEqual(opts.max_redirects, 3)

    def test_repeatable_header(self) -> None:
        opts = parse(["-H", "A: 1", "-H", "B: 2", "example.com"])
        self.assertEqual(opts.headers, ["A: 1", "B: 2"])

    def test_double_dash_ends_options(self) -> None:
        opts = parse(["-s", "--", "-not-an-option"])
        self.assertTrue(opts.silent)
        self.assertEqual(opts.urls, ["-not-an-option"])

    def test_multiple_urls(self) -> None:
        opts = parse(["example.com", "example.org"])
        self.assertEqual(opts.urls, ["example.com", "example.org"])

    def test_url_flag_is_equivalent(self) -> None:
        opts = parse(["--url", "example.com"])
        self.assertEqual(opts.urls, ["example.com"])


class ValidationTests(unittest.TestCase):
    def test_missing_url(self) -> None:
        with self.assertRaises(UsageError):
            parse([])

    def test_unknown_short_option(self) -> None:
        with self.assertRaisesRegex(UsageError, "unknown option -Z"):
            parse(["-Z", "example.com"])

    def test_unknown_long_option(self) -> None:
        with self.assertRaisesRegex(UsageError, "unknown option --nope"):
            parse(["--nope", "example.com"])

    def test_missing_value(self) -> None:
        with self.assertRaisesRegex(UsageError, "requires a value"):
            parse(["-o"])

    def test_value_on_flag(self) -> None:
        with self.assertRaisesRegex(UsageError, "does not take a value"):
            parse(["--silent=1", "example.com"])

    def test_non_numeric_max_redirs(self) -> None:
        with self.assertRaisesRegex(UsageError, "invalid number"):
            parse(["--max-redirs", "abc", "example.com"])

    def test_negative_timeout_rejected(self) -> None:
        with self.assertRaisesRegex(UsageError, "must be greater than 0"):
            parse(["--max-time", "0", "example.com"])

    def test_json_conflicts_with_data(self) -> None:
        with self.assertRaisesRegex(UsageError, "cannot combine"):
            parse(["--json", "{}", "-d", "x=1", "example.com"])


class PayloadTests(unittest.TestCase):
    def test_data_strips_newlines(self) -> None:
        opts = parse(["-d", "a=1\nb=2", "example.com"])
        self.assertEqual(opts.body, "a=1b=2")
        self.assertEqual(opts.content_type, "application/x-www-form-urlencoded")

    def test_data_raw_keeps_newlines(self) -> None:
        opts = parse(["--data-raw", "a=1\nb=2", "example.com"])
        self.assertEqual(opts.body, "a=1\nb=2")

    def test_multiple_data_joined_with_ampersand(self) -> None:
        opts = parse(["-d", "a=1", "-d", "b=2", "example.com"])
        self.assertEqual(opts.body, "a=1&b=2")

    def test_data_urlencode_name_equals_content(self) -> None:
        opts = parse(["--data-urlencode", "q=a b&c", "example.com"])
        self.assertEqual(opts.body, "q=a%20b%26c")

    def test_data_urlencode_bare_content(self) -> None:
        opts = parse(["--data-urlencode", "a b&c", "example.com"])
        self.assertEqual(opts.body, "a%20b%26c")

    def test_data_urlencode_equals_prefix(self) -> None:
        opts = parse(["--data-urlencode", "=a b", "example.com"])
        self.assertEqual(opts.body, "a%20b")

    def test_json_sets_content_type(self) -> None:
        opts = parse(["--json", '{"a":1}', "example.com"])
        self.assertEqual(opts.body, '{"a":1}')
        self.assertEqual(opts.content_type, "application/json")

    def test_get_flag_does_not_leak_into_body(self) -> None:
        opts = parse(["-G", "-d", "a=1", "example.com"])
        self.assertTrue(opts.use_get)
        self.assertEqual(opts.body, "a=1")


class HelpTests(unittest.TestCase):
    def test_help_lists_every_option(self) -> None:
        from curl_lite.args import OPTIONS

        text = help_text()
        for opt in OPTIONS:
            self.assertIn(opt.help_flags, text)

    def test_version_mentions_the_name(self) -> None:
        self.assertTrue(version_text().startswith("curl-lite/"))


if __name__ == "__main__":
    unittest.main()