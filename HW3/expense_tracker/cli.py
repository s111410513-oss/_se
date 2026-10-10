"""Command line interface for expense-tracker."""

from __future__ import annotations

import argparse
import calendar
import csv
import json
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional

from . import __version__
from .db import Database, default_db_path
from . import reports

TABLE_ALIGN = {"r": ">", "l": "<"}


# --------------------------------------------------------------------------
# parsing helpers
# --------------------------------------------------------------------------
def to_cents(text: str) -> int:
    """Parse a money string such as ``12``, ``12.5`` or ``$1,234.56``."""
    cleaned = str(text).strip().replace(",", "").replace("$", "")
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        raise ValueError(f"invalid amount: {text!r}")
    if value <= 0:
        raise ValueError("amount must be positive")
    return int((value * 100).to_integral_value(rounding=ROUND_HALF_UP))


def _amount_arg(text: str) -> int:
    try:
        return to_cents(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc))


def _date_arg(text: str) -> str:
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid date (expected YYYY-MM-DD): {text!r}")
    return text


def _month_bounds(month: str) -> tuple[str, str]:
    try:
        year_s, mon_s = month.split("-")
        year, mon = int(year_s), int(mon_s)
        last = calendar.monthrange(year, mon)[1]
    except (ValueError, calendar.IllegalMonthError):
        raise ValueError(f"invalid month (expected YYYY-MM): {month!r}")
    return f"{year:04d}-{mon:02d}-01", f"{year:04d}-{mon:02d}-{last:02d}"


def resolve_period(args, default_current_month: bool = True) -> tuple[Optional[str], Optional[str]]:
    month = getattr(args, "month", None)
    start = getattr(args, "start", None)
    end = getattr(args, "end", None)
    if month:
        return _month_bounds(month)
    if start or end:
        return start, end
    if default_current_month:
        return _month_bounds(datetime.now().strftime("%Y-%m"))
    return None, None


# --------------------------------------------------------------------------
# rendering helpers
# --------------------------------------------------------------------------
def render_table(headers: list[str], rows: list[list], aligns: list[str] | None = None) -> str:
    aligns = aligns or ["l"] * len(headers)
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    lines = []
    header = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    lines.append(header)
    lines.append("  ".join("-" * w for w in widths))
    for row in rows:
        lines.append(
            "  ".join(
                str(cell).rjust(widths[i]) if aligns[i] == ">" else str(cell).ljust(widths[i])
                for i, cell in enumerate(row)
            )
        )
    return "\n".join(lines)


def _print_summary(summary: dict) -> None:
    print(f"  Income:  {reports.format_cents(summary['income_cents'])}")
    print(f"  Expense: {reports.format_cents(summary['expense_cents'])}")
    print(f"  Balance: {reports.format_cents(summary['balance_cents'])}")
    print(f"  Entries: {summary['count']}")


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------
def cmd_add(db: Database, args) -> int:
    tx_id = db.add_transaction(
        date=args.date,
        kind=args.kind,
        amount_cents=args.amount,
        category=args.category,
        note=args.note,
    )
    print(
        f"Added #{tx_id}: {args.kind} {reports.format_cents(args.amount)} "
        f"[{args.category}] on {args.date}"
    )
    return 0


def cmd_list(db: Database, args) -> int:
    start, end = resolve_period(args, default_current_month=bool(args.month))
    rows = db.list_transactions(
        start=start, end=end, category=args.category, kind=args.kind, limit=args.limit
    )
    if not rows:
        print("No transactions found.")
        return 0
    table = [
        [t["id"], t["date"], t["kind"], t["category"], reports.format_cents(t["amount_cents"]), t["note"]]
        for t in rows
    ]
    print(render_table(["ID", "Date", "Type", "Category", "Amount", "Note"], table,
                       aligns=["r", "l", "l", "l", "r", "l"]))
    print(f"\n{len(rows)} transaction(s).")
    return 0


def cmd_delete(db: Database, args) -> int:
    if db.delete_transaction(args.id):
        print(f"Deleted transaction #{args.id}.")
        return 0
    print(f"No transaction with id {args.id}.", file=sys.stderr)
    return 1


def cmd_summary(db: Database, args) -> int:
    start, end = resolve_period(args)
    rows = db.list_transactions(start=start, end=end)
    period = f"{start or '...'} .. {end or '...'}"
    print(f"Summary for {period}")
    _print_summary(reports.summarize(rows))
    return 0


def cmd_report(db: Database, args) -> int:
    start, end = resolve_period(args)
    rows = db.list_transactions(start=start, end=end)
    print(f"Report for {start or '...'} .. {end or '...'}")
    print("-" * 48)
    _print_summary(reports.summarize(rows))

    expenses = reports.group_by_category(rows, kind="expense")
    print("\nExpenses by category:")
    if not expenses:
        print("  (none)")
    else:
        top = expenses[0]["total_cents"]
        total = sum(r["total_cents"] for r in expenses)
        for row in expenses:
            pct = row["total_cents"] / total * 100 if total else 0
            print(
                f"  {row['category'][:14]:<14} {reports.format_cents(row['total_cents']):>12}  "
                f"{reports.bar(row['total_cents'], top, 24):<24} {pct:5.1f}%"
            )

    incomes = reports.group_by_category(rows, kind="income")
    if incomes:
        print("\nIncome by category:")
        for row in incomes:
            print(f"  {row['category'][:14]:<14} {reports.format_cents(row['total_cents']):>12}")

    monthly = reports.group_by_month(rows)
    if len(monthly) > 1:
        print("\nBy month:")
        for b in monthly:
            print(
                f"  {b['month']}  income {reports.format_cents(b['income_cents']):>12}  "
                f"expense {reports.format_cents(b['expense_cents']):>12}  "
                f"balance {reports.format_cents(b['balance_cents']):>12}"
            )

    budgets = db.get_budgets()
    if budgets:
        spent = {r["category"]: r["total_cents"] for r in expenses}
        status = reports.budget_status(budgets, spent)
        if status:
            print("\nBudget status:")
            for row in status:
                flag = "OVER" if row["over"] else "ok"
                print(
                    f"  {row['category'][:14]:<14} "
                    f"{reports.format_cents(row['spent_cents']):>12} / "
                    f"{reports.format_cents(row['budget_cents']):>12}  "
                    f"({row['percent']:5.1f}%)  {flag}"
                )
    return 0


def cmd_budget(db: Database, args) -> int:
    if args.budget_command == "set":
        db.set_budget(args.category, args.amount)
        print(f"Budget for [{args.category}] set to {reports.format_cents(args.amount)}.")
        return 0
    if args.budget_command == "remove":
        if db.remove_budget(args.category):
            print(f"Removed budget for [{args.category}].")
            return 0
        print(f"No budget set for [{args.category}].", file=sys.stderr)
        return 1
    # list
    budgets = db.get_budgets()
    if not budgets:
        print("No budgets set.")
        return 0
    rows = [[cat, reports.format_cents(amt)] for cat, amt in budgets.items()]
    print(render_table(["Category", "Monthly budget"], rows, aligns=["l", "r"]))
    return 0


def cmd_export(db: Database, args) -> int:
    start, end = resolve_period(args, default_current_month=bool(args.month))
    rows = db.list_transactions(start=start, end=end, category=args.category, kind=args.kind)

    if args.format == "json":
        payload = [
            {
                "date": t["date"],
                "kind": t["kind"],
                "amount": f"{Decimal(t['amount_cents']) / 100:.2f}",
                "category": t["category"],
                "note": t["note"],
            }
            for t in rows
        ]
        text = json.dumps(payload, indent=2, ensure_ascii=False)
    else:
        import io

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["date", "kind", "amount", "category", "note"])
        for t in rows:
            writer.writerow(
                [t["date"], t["kind"], f"{Decimal(t['amount_cents']) / 100:.2f}", t["category"], t["note"]]
            )
        text = buf.getvalue()

    if args.output == "-":
        print(text, end="" if text.endswith("\n") else "\n")
    else:
        with open(args.output, "w", newline="", encoding="utf-8") as fh:
            fh.write(text)
        print(f"Exported {len(rows)} transaction(s) to {args.output}.")
    return 0


def cmd_import(db: Database, args) -> int:
    added = 0
    errors = 0
    with open(args.file, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for lineno, raw in enumerate(reader, start=2):
            try:
                date = _date_arg((raw.get("date") or "").strip())
                kind = (raw.get("kind") or "expense").strip().lower()
                if kind not in ("income", "expense"):
                    raise ValueError(f"invalid kind {kind!r}")
                amount = to_cents(raw.get("amount") or "")
                category = (raw.get("category") or "").strip()
                note = (raw.get("note") or "").strip()
                db.add_transaction(date, kind, amount, category, note)
                added += 1
            except (ValueError, KeyError) as exc:
                errors += 1
                print(f"  line {lineno}: skipped ({exc})", file=sys.stderr)
    print(f"Imported {added} transaction(s); {errors} skipped.")
    return 1 if errors and not added else 0


# --------------------------------------------------------------------------
# argument parser
# --------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="expense",
        description="Track income and expenses, analyse spending, and manage budgets.",
    )
    parser.add_argument("--version", action="version", version=f"expense-tracker {__version__}")
    parser.add_argument("--db", default=str(default_db_path()), help="Path to the SQLite database file.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="Record a transaction.")
    p_add.add_argument("amount", type=_amount_arg, help="Amount, e.g. 12.50")
    p_add.add_argument("category", help="Category, e.g. Food")
    p_add.add_argument("-t", "--type", dest="kind", choices=["expense", "income"], default="expense")
    p_add.add_argument("-d", "--date", type=_date_arg, default=datetime.now().strftime("%Y-%m-%d"))
    p_add.add_argument("-n", "--note", default="")
    p_add.set_defaults(func=cmd_add)

    p_list = sub.add_parser("list", help="List transactions.")
    p_list.add_argument("--from", dest="start", type=_date_arg)
    p_list.add_argument("--to", dest="end", type=_date_arg)
    p_list.add_argument("-m", "--month", help="Filter by month, e.g. 2026-10")
    p_list.add_argument("-c", "--category")
    p_list.add_argument("-t", "--type", dest="kind", choices=["expense", "income"])
    p_list.add_argument("-l", "--limit", type=int, default=50)
    p_list.set_defaults(func=cmd_list)

    p_del = sub.add_parser("delete", help="Delete a transaction by id.")
    p_del.add_argument("id", type=int)
    p_del.set_defaults(func=cmd_delete)

    p_sum = sub.add_parser("summary", help="Show totals for a period (default: this month).")
    _add_period_args(p_sum)
    p_sum.set_defaults(func=cmd_summary)

    p_rep = sub.add_parser("report", help="Full breakdown: categories, months, budgets.")
    _add_period_args(p_rep)
    p_rep.set_defaults(func=cmd_report)

    p_bud = sub.add_parser("budget", help="Manage monthly budgets.")
    bsub = p_bud.add_subparsers(dest="budget_command", required=True)
    b_set = bsub.add_parser("set", help="Set a monthly budget.")
    b_set.add_argument("category")
    b_set.add_argument("amount", type=_amount_arg)
    bsub.add_parser("list", help="List budgets.")
    b_rm = bsub.add_parser("remove", help="Remove a budget.")
    b_rm.add_argument("category")
    p_bud.set_defaults(func=cmd_budget)

    p_exp = sub.add_parser("export", help="Export transactions to CSV or JSON.")
    p_exp.add_argument("output", help="Output path, or - for stdout.")
    p_exp.add_argument("-f", "--format", choices=["csv", "json"], default="csv")
    p_exp.add_argument("--from", dest="start", type=_date_arg)
    p_exp.add_argument("--to", dest="end", type=_date_arg)
    p_exp.add_argument("-m", "--month")
    p_exp.add_argument("-c", "--category")
    p_exp.add_argument("-t", "--type", dest="kind", choices=["expense", "income"])
    p_exp.set_defaults(func=cmd_export)

    p_imp = sub.add_parser("import", help="Import transactions from a CSV file.")
    p_imp.add_argument("file")
    p_imp.set_defaults(func=cmd_import)

    return parser


def _add_period_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--from", dest="start", type=_date_arg)
    p.add_argument("--to", dest="end", type=_date_arg)
    p.add_argument("-m", "--month", help="Use a whole month, e.g. 2026-10")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    db = Database(args.db if args.db else ":memory:")
    try:
        return args.func(db, args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
