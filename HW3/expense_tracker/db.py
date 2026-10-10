"""SQLite persistence layer for expense-tracker.

Money is stored as integer cents to avoid floating point rounding errors.
Dates are stored as ISO ``YYYY-MM-DD`` strings so that lexicographic
comparison equals chronological comparison (which makes range queries
trivial and index friendly).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

KINDS = ("income", "expense")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    date         TEXT    NOT NULL,
    kind         TEXT    NOT NULL CHECK (kind IN ('income', 'expense')),
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    category     TEXT    NOT NULL,
    note         TEXT    NOT NULL DEFAULT '',
    created_at   TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tx_date     ON transactions (date);
CREATE INDEX IF NOT EXISTS idx_tx_category ON transactions (category);

CREATE TABLE IF NOT EXISTS budgets (
    category     TEXT    PRIMARY KEY,
    amount_cents INTEGER NOT NULL CHECK (amount_cents >= 0)
);
"""


def default_db_path() -> Path:
    """Return the default database location outside the project tree."""
    home = Path.home()
    return home / ".expense-tracker" / "data.db"


class Database:
    """Thin wrapper around a sqlite3 connection."""

    def __init__(self, path: str | Path = None):
        self.path = default_db_path() if path is None else Path(path)
        if str(path) != ":memory:" and str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path if path is not None else self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    # -- lifecycle -----------------------------------------------------
    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- transactions --------------------------------------------------
    def add_transaction(
        self,
        date: str,
        kind: str,
        amount_cents: int,
        category: str,
        note: str = "",
    ) -> int:
        if kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}, got {kind!r}")
        if amount_cents <= 0:
            raise ValueError("amount_cents must be positive")
        if not category.strip():
            raise ValueError("category must not be empty")
        cur = self.conn.execute(
            """
            INSERT INTO transactions (date, kind, amount_cents, category, note, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                date,
                kind,
                int(amount_cents),
                category.strip(),
                note.strip(),
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def get_transaction(self, tx_id: int) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM transactions WHERE id = ?", (tx_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_transactions(
        self,
        start: Optional[str] = None,
        end: Optional[str] = None,
        category: Optional[str] = None,
        kind: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[dict]:
        clauses: list[str] = []
        params: list = []
        if start:
            clauses.append("date >= ?")
            params.append(start)
        if end:
            clauses.append("date <= ?")
            params.append(end)
        if category:
            clauses.append("category = ?")
            params.append(category)
        if kind:
            clauses.append("kind = ?")
            params.append(kind)

        sql = "SELECT * FROM transactions"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY date DESC, id DESC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))

        return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def delete_transaction(self, tx_id: int) -> bool:
        cur = self.conn.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
        self.conn.commit()
        return cur.rowcount > 0

    def add_many(self, rows: Iterable[dict]) -> int:
        """Bulk insert. Each row needs date/kind/amount_cents/category/note."""
        n = 0
        for r in rows:
            self.add_transaction(
                date=r["date"],
                kind=r["kind"],
                amount_cents=int(r["amount_cents"]),
                category=r["category"],
                note=r.get("note", ""),
            )
            n += 1
        return n

    # -- budgets -------------------------------------------------------
    def set_budget(self, category: str, amount_cents: int) -> None:
        if amount_cents < 0:
            raise ValueError("budget must not be negative")
        self.conn.execute(
            """
            INSERT INTO budgets (category, amount_cents) VALUES (?, ?)
            ON CONFLICT(category) DO UPDATE SET amount_cents = excluded.amount_cents
            """,
            (category.strip(), int(amount_cents)),
        )
        self.conn.commit()

    def remove_budget(self, category: str) -> bool:
        cur = self.conn.execute("DELETE FROM budgets WHERE category = ?", (category,))
        self.conn.commit()
        return cur.rowcount > 0

    def get_budgets(self) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT category, amount_cents FROM budgets ORDER BY category"
        ).fetchall()
        return {r["category"]: r["amount_cents"] for r in rows}
