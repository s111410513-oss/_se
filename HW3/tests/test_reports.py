import unittest

from expense_tracker import reports


def tx(date, kind, cents, category, note=""):
    return {"date": date, "kind": kind, "amount_cents": cents, "category": category, "note": note}


class FormatTests(unittest.TestCase):
    def test_format_positive(self):
        self.assertEqual(reports.format_cents(123456), "$1,234.56")

    def test_format_negative(self):
        self.assertEqual(reports.format_cents(-500), "-$5.00")

    def test_format_zero(self):
        self.assertEqual(reports.format_cents(0), "$0.00")


class BarTests(unittest.TestCase):
    def test_full_bar(self):
        self.assertEqual(reports.bar(100, 100, 10), "#" * 10)

    def test_half_bar(self):
        self.assertEqual(len(reports.bar(50, 100, 10)), 5)

    def test_zero_max_is_empty(self):
        self.assertEqual(reports.bar(10, 0, 10), "")

    def test_minimum_visible(self):
        self.assertEqual(len(reports.bar(1, 1000, 10)), 1)


class SummarizeTests(unittest.TestCase):
    def test_totals(self):
        rows = [tx("2026-10-01", "income", 5000, "Salary"), tx("2026-10-02", "expense", 1200, "Food")]
        s = reports.summarize(rows)
        self.assertEqual(s["income_cents"], 5000)
        self.assertEqual(s["expense_cents"], 1200)
        self.assertEqual(s["balance_cents"], 3800)
        self.assertEqual(s["count"], 2)

    def test_empty(self):
        s = reports.summarize([])
        self.assertEqual(s["balance_cents"], 0)
        self.assertEqual(s["count"], 0)


class GroupTests(unittest.TestCase):
    def test_group_by_category_expense_sorted(self):
        rows = [
            tx("2026-10-01", "expense", 300, "Food"),
            tx("2026-10-02", "expense", 700, "Transport"),
            tx("2026-10-03", "expense", 200, "Food"),
            tx("2026-10-04", "income", 9999, "Salary"),
        ]
        grouped = reports.group_by_category(rows, kind="expense")
        self.assertEqual(grouped[0]["category"], "Transport")
        self.assertEqual(grouped[0]["total_cents"], 700)
        self.assertEqual(grouped[1]["category"], "Food")
        self.assertEqual(grouped[1]["total_cents"], 500)
        self.assertEqual(grouped[1]["count"], 2)

    def test_group_by_month(self):
        rows = [
            tx("2026-09-10", "expense", 100, "Food"),
            tx("2026-10-01", "income", 5000, "Salary"),
            tx("2026-10-05", "expense", 200, "Food"),
        ]
        months = reports.group_by_month(rows)
        self.assertEqual([m["month"] for m in months], ["2026-09", "2026-10"])
        self.assertEqual(months[1]["balance_cents"], 4800)


class BudgetStatusTests(unittest.TestCase):
    def test_status(self):
        budgets = {"Food": 1000, "Transport": 500}
        spent = {"Food": 800, "Transport": 600}
        status = reports.budget_status(budgets, spent)
        by_cat = {s["category"]: s for s in status}
        self.assertFalse(by_cat["Food"]["over"])
        self.assertEqual(by_cat["Food"]["remaining_cents"], 200)
        self.assertTrue(by_cat["Transport"]["over"])
        self.assertEqual(by_cat["Transport"]["remaining_cents"], -100)


if __name__ == "__main__":
    unittest.main()
