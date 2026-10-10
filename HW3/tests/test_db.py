import unittest

from expense_tracker.db import Database


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")

    def tearDown(self):
        self.db.close()

    def test_add_and_get(self):
        tx_id = self.db.add_transaction("2026-10-01", "expense", 1250, "Food", "lunch")
        row = self.db.get_transaction(tx_id)
        self.assertEqual(row["amount_cents"], 1250)
        self.assertEqual(row["category"], "Food")
        self.assertEqual(row["kind"], "expense")
        self.assertEqual(row["note"], "lunch")

    def test_missing_transaction_returns_none(self):
        self.assertIsNone(self.db.get_transaction(999))

    def test_delete(self):
        tx_id = self.db.add_transaction("2026-10-01", "expense", 500, "Food")
        self.assertTrue(self.db.delete_transaction(tx_id))
        self.assertFalse(self.db.delete_transaction(tx_id))

    def test_list_filters(self):
        self.db.add_transaction("2026-10-01", "expense", 100, "Food")
        self.db.add_transaction("2026-10-15", "income", 5000, "Salary")
        self.db.add_transaction("2026-11-02", "expense", 200, "Transport")

        self.assertEqual(len(self.db.list_transactions()), 3)
        self.assertEqual(len(self.db.list_transactions(start="2026-10-01", end="2026-10-31")), 2)
        self.assertEqual(len(self.db.list_transactions(kind="income")), 1)
        self.assertEqual(len(self.db.list_transactions(category="Food")), 1)

    def test_list_is_newest_first(self):
        self.db.add_transaction("2026-10-01", "expense", 100, "Food")
        self.db.add_transaction("2026-10-20", "expense", 100, "Food")
        rows = self.db.list_transactions()
        self.assertEqual(rows[0]["date"], "2026-10-20")

    def test_rejects_non_positive_amount(self):
        with self.assertRaises(ValueError):
            self.db.add_transaction("2026-10-01", "expense", 0, "Food")

    def test_rejects_bad_kind(self):
        with self.assertRaises(ValueError):
            self.db.add_transaction("2026-10-01", "transfer", 100, "Food")

    def test_rejects_empty_category(self):
        with self.assertRaises(ValueError):
            self.db.add_transaction("2026-10-01", "expense", 100, "  ")

    def test_budgets(self):
        self.db.set_budget("Food", 5000)
        self.db.set_budget("Transport", 2000)
        self.assertEqual(self.db.get_budgets(), {"Food": 5000, "Transport": 2000})

        self.db.set_budget("Food", 6000)
        self.assertEqual(self.db.get_budgets()["Food"], 6000)

        self.assertTrue(self.db.remove_budget("Food"))
        self.assertNotIn("Food", self.db.get_budgets())
        self.assertFalse(self.db.remove_budget("Food"))

    def test_add_many(self):
        rows = [
            {"date": "2026-10-01", "kind": "expense", "amount_cents": 100, "category": "A"},
            {"date": "2026-10-02", "kind": "income", "amount_cents": 200, "category": "B", "note": "x"},
        ]
        self.assertEqual(self.db.add_many(rows), 2)
        self.assertEqual(len(self.db.list_transactions()), 2)


if __name__ == "__main__":
    unittest.main()
