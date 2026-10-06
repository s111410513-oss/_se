"""Unit tests for the cookie helpers."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from curl_lite import cookies
from curl_lite.errors import UsageError

NETSAMPLE = (
    "# Netscape HTTP Cookie File\n"
    "# This is a generated file! Do not edit.\n"
    "\n"
    "example.com\tFALSE\t/\tFALSE\t0\tsession\tabc123\n"
    "\n"
)


class InlineCookieTests(unittest.TestCase):
    def test_data_detection(self) -> None:
        self.assertTrue(cookies.looks_like_data("a=1"))
        self.assertTrue(cookies.looks_like_data("a=1; b=2"))
        self.assertFalse(cookies.looks_like_data("cookies.txt"))

    def test_parse_inline(self) -> None:
        self.assertEqual(cookies.parse_inline(" a=1 ;b=2 ;"), ["a=1", "b=2"])

    def test_jar_from_inline_data(self) -> None:
        jar = cookies.jar_with("a=1; b=2", "example.com")
        names = sorted(cookie.name for cookie in jar)
        self.assertEqual(names, ["a", "b"])

    def test_domain_is_attached_to_the_request(self) -> None:
        jar = cookies.jar_with("a=1", "example.com")
        cookie = next(iter(jar))
        self.assertEqual(cookie.domain, "example.com")

    def test_empty_value_creates_jar_without_cookies(self) -> None:
        self.assertEqual(len(list(cookies.jar_with(None, "example.com"))), 0)
        self.assertEqual(len(list(cookies.jar_with("", "example.com"))), 0)

    def test_malformed_pair_is_skipped(self) -> None:
        jar = cookies.jar_with(";=1; a=2", "example.com")
        self.assertEqual([cookie.name for cookie in jar], ["a"])


class CookieFileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "cookies.txt")
        Path(self.path).write_text(NETSAMPLE, encoding="utf-8")

    def test_load_netscape_file(self) -> None:
        jar = cookies.load_file(self.path)
        self.assertEqual([(c.name, c.value) for c in jar], [("session", "abc123")])

    def test_missing_file_is_ignored(self) -> None:
        jar = cookies.load_file(os.path.join(self.dir, "absent.txt"))
        self.assertEqual(len(list(jar)), 0)

    def test_malformed_file_is_reported(self) -> None:
        bad = os.path.join(self.dir, "bad.txt")
        Path(bad).write_text("this is not a cookie file at all\n", encoding="utf-8")
        with self.assertRaises(UsageError):
            cookies.load_file(bad)

    def test_jar_from_file_keeps_matching_domain_only(self) -> None:
        jar = cookies.jar_with(self.path, "example.com")
        self.assertEqual([c.name for c in jar], ["session"])
        other = cookies.jar_with(self.path, "other.com")
        self.assertEqual(len(list(other)), 0)

    def test_save_round_trip(self) -> None:
        jar = cookies.jar_with("session=abc123", "example.com")
        target = os.path.join(self.dir, "out", "jar.txt")
        cookies.save(jar, target)
        self.assertIn("# Netscape HTTP Cookie File", Path(target).read_text(encoding="utf-8"))
        reloaded = cookies.load_file(target)
        self.assertEqual([(c.name, c.value) for c in reloaded], [("session", "abc123")])

    def test_save_creates_missing_directories(self) -> None:
        jar = cookies.jar_with("a=1", "example.com")
        target = os.path.join(self.dir, "deep", "nested", "jar.txt")
        cookies.save(jar, target)
        self.assertTrue(os.path.exists(target))


if __name__ == "__main__":
    unittest.main()