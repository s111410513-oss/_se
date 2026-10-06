"""Tests for URL normalisation and the derived ``-O`` file name."""

from __future__ import annotations

import unittest

from curl_lite.errors import UsageError
from curl_lite.urls import filename_from_url, normalize, with_query


class NormalizeTests(unittest.TestCase):
    def test_bare_host_defaults_to_http(self) -> None:
        self.assertEqual(normalize("example.com"), "http://example.com/")

    def test_bare_host_with_port(self) -> None:
        self.assertEqual(normalize("example.com:8080/x"), "http://example.com:8080/x")

    def test_scheme_and_host_are_lowercased(self) -> None:
        self.assertEqual(normalize("HTTP://Example.COM/Path"), "http://example.com/Path")

    def test_default_port_is_dropped(self) -> None:
        self.assertEqual(normalize("http://example.com:80/a"), "http://example.com/a")
        self.assertEqual(normalize("https://example.com:443/a"), "https://example.com/a")

    def test_non_default_port_is_kept(self) -> None:
        self.assertEqual(normalize("http://example.com:8080/"), "http://example.com:8080/")

    def test_query_is_preserved(self) -> None:
        self.assertEqual(normalize("example.com/a?b=1&c=2"), "http://example.com/a?b=1&c=2")

    def test_fragment_is_dropped(self) -> None:
        self.assertEqual(normalize("http://example.com/a#frag"), "http://example.com/a")

    def test_ipv6_literal(self) -> None:
        self.assertEqual(normalize("http://[::1]:8080/"), "http://[::1]:8080/")

    def test_userinfo_is_preserved(self) -> None:
        self.assertEqual(normalize("http://user:pw@example.com/"), "http://user:pw@example.com/")

    def test_empty_url(self) -> None:
        with self.assertRaises(UsageError):
            normalize("   ")

    def test_unsupported_scheme(self) -> None:
        with self.assertRaisesRegex(UsageError, "unsupported"):
            normalize("ftp://example.com")

    def test_mailto_is_rejected(self) -> None:
        with self.assertRaises(UsageError):
            normalize("mailto:someone@example.com")


class QueryTests(unittest.TestCase):
    def test_with_query_appends(self) -> None:
        self.assertEqual(with_query("http://e.com/?a=1", "b=2"), "http://e.com/?a=1&b=2")

    def test_with_query_without_existing_query(self) -> None:
        self.assertEqual(with_query("http://e.com/", "b=2"), "http://e.com/?b=2")

    def test_with_query_noop(self) -> None:
        self.assertEqual(with_query("http://e.com/", ""), "http://e.com/")


class RemoteNameTests(unittest.TestCase):
    def test_uses_basename(self) -> None:
        self.assertEqual(filename_from_url("http://e.com/dir/file.zip"), "file.zip")

    def test_falls_back_to_index_html(self) -> None:
        self.assertEqual(filename_from_url("http://e.com/"), "index.html")
        self.assertEqual(filename_from_url("http://e.com"), "index.html")

    def test_percent_decoding(self) -> None:
        self.assertEqual(filename_from_url("http://e.com/a%20b.txt"), "a b.txt")


if __name__ == "__main__":
    unittest.main()