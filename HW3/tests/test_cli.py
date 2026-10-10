import csv
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

from expense_tracker import cli


class ParseTests(unittest.TestCase):
    def test_to_cents_variants(self):
        self.assertEqual(cli.to_cents("10"), 1000)
        self.assertEqual(cli.to_cents("10.5"), 1050)
        self.assertEqual(cli.to_cents("$1,234.56"), 123456)
        self.assertEqual(cli.to_cents("0.01"), 1)

    def test_to_cents_rounding(self):
        self.assertEqual(cli.to_cents("0.005"), 1)

    def test_to_cents_rejects_bad_input(self):
        for bad in ("abc", "-1", "0", ""):
            with self.assertRaises(ValueError):
                cli.to_cents(bad)

    def test_month_bounds(self):
        self.assertEqual(cli._month_bounds("2026-02"), ("2026-02-01", "2026-02-28"))
        self.assertEqual(cli._month_bounds("2024-02"), ("2024-02-01", "2024-02-29"))

    def test_month_bounds_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            cli._month_bounds("2026-13")


class CliEndToEndTests(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.remove(self.db_path)  # let Database create it fresh

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(["--db", self.db_path, *argv])
        return code, out.getvalue(), err.getvalue()

    def test_add_list_summary(self):
        code, out, _ = self.run_cli("add", "12.50", "Food", "-d", "2026-10-01", "-n", "lunch")
        self.assertEqual(code, 0)
        self.assertIn("Added #1", out)

        code, out, _ = self.run_cli("add", "3000", "Salary", "-t", "income", "-d", "2026-10-01")
        self.assertEqual(code, 0)

        code, out, _ = self.run_cli("list", "-m", "2026-10")
        self.assertIn("Food", out)
        self.assertIn("Salary", out)

        code, out, _ = self.run_cli("summary", "-m", "2026-10")
        # income $3000.00 - expense $12.50 = $2,987.50
        self.assertIn("$2,987.50", out)

    def test_delete_missing_returns_error(self):
        code, _, err = self.run_cli("delete", "42")
        self.assertEqual(code, 1)
        self.assertIn("No transaction", err)

    def test_budget_flow(self):
        code, out, _ = self.run_cli("budget", "set", "Food", "100")
        self.assertEqual(code, 0)
        self.assertIn("Budget for [Food]", out)
        code, out, _ = self.run_cli("budget", "list")
        self.assertIn("Food", out)
        code, out, _ = self.run_cli("budget", "remove", "Food")
        self.assertEqual(code, 0)

    def test_export_import_roundtrip(self):
        self.run_cli("add", "12.50", "Food", "-d", "2026-10-01", "-n", "lunch")
        self.run_cli("add", "3000", "Salary", "-t", "income", "-d", "2026-10-02")

        fd, csv_path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        try:
            code, _, _ = self.run_cli("export", csv_path, "-m", "2026-10")
            self.assertEqual(code, 0)
            with open(csv_path, newline="", encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(len(rows), 2)
            self.assertEqual({r["amount"] for r in rows}, {"12.50", "3000.00"})

            # import into a second database
            fd2, db2 = tempfile.mkstemp(suffix=".db")
            os.close(fd2)
            os.remove(db2)
            try:
                out = io.StringIO()
                with redirect_stdout(out):
                    code = cli.main(["--db", db2, "import", csv_path])
                self.assertEqual(code, 0)
                self.assertIn("Imported 2", out.getvalue())
            finally:
                if os.path.exists(db2):
                    os.remove(db2)
        finally:
            os.remove(csv_path)

    def test_report_shows_budget_over(self):
        self.run_cli("budget", "set", "Food", "10")
        self.run_cli("add", "20", "Food", "-d", "2026-10-05")
        code, out, _ = self.run_cli("report", "-m", "2026-10")
        self.assertEqual(code, 0)
        self.assertIn("OVER", out)


if __name__ == "__main__":
    unittest.main()
