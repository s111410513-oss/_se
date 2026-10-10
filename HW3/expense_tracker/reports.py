"""Pure, side-effect free helpers for turning transactions into report data.

Keeping these functions free of I/O makes them trivial to unit test and
lets the CLI decide how to render the results.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable

ZERO = 0


def format_cents(cents: int) -> str:
    """Format integer cents as a human friendly ``$1,234.56`` string."""
    sign = "-" if cents < 0 else ""
    value = Decimal(abs(int(cents))) / 100
    return f"{sign}${value:,.2f}"


def bar(value: int, max_value: int, width: int = 30) -> str:
    """Render a proportional ASCII bar of the given ``width``."""
    if max_value <= 0 or value <= 0:
        return ""
    filled = max(1, round(value / max_value * width))
    return "#" * min(width, filled)


def summarize(transactions: Iterable[dict]) -> dict:
    """Return income/expense/balance totals for a set of transactions."""
    txns = list(transactions)
    income = sum(t["amount_cents"] for t in txns if t["kind"] == "income")
    expense = sum(t["amount_cents"] for t in txns if t["kind"] == "expense")
    return {
        "income_cents": income,
        "expense_cents": expense,
        "balance_cents": income - expense,
        "count": len(txns),
    }


def group_by_category(transactions: Iterable[dict], kind: str = "expense") -> list[dict]:
    """Aggregate totals per category for one ``kind``, largest first."""
    totals: dict[str, int] = {}
    counts: dict[str, int] = {}
    for t in transactions:
        if t["kind"] != kind:
            continue
        totals[t["category"]] = totals.get(t["category"], 0) + t["amount_cents"]
        counts[t["category"]] = counts.get(t["category"], 0) + 1
    result = [
        {"category": cat, "total_cents": total, "count": counts[cat]}
        for cat, total in totals.items()
    ]
    result.sort(key=lambda row: (-row["total_cents"], row["category"]))
    return result


def group_by_month(transactions: Iterable[dict]) -> list[dict]:
    """Aggregate income/expense/balance per ``YYYY-MM``, oldest first."""
    buckets: dict[str, dict] = {}
    for t in transactions:
        month = t["date"][:7]
        b = buckets.setdefault(month, {"month": month, "income_cents": 0, "expense_cents": 0})
        if t["kind"] == "income":
            b["income_cents"] += t["amount_cents"]
        else:
            b["expense_cents"] += t["amount_cents"]
    rows = list(buckets.values())
    for b in rows:
        b["balance_cents"] = b["income_cents"] - b["expense_cents"]
    rows.sort(key=lambda r: r["month"])
    return rows


def budget_status(budgets: dict[str, int], spent: dict[str, int]) -> list[dict]:
    """Combine budgets with actual spending into rich status rows."""
    rows = []
    for category, limit in budgets.items():
        used = spent.get(category, 0)
        pct = (used / limit * 100) if limit else 0.0
        rows.append(
            {
                "category": category,
                "budget_cents": limit,
                "spent_cents": used,
                "remaining_cents": limit - used,
                "percent": pct,
                "over": used > limit,
            }
        )
    rows.sort(key=lambda r: (-r["percent"], r["category"]))
    return rows
