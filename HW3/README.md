# expense-tracker

A small, **dependency-free** command line tool to track income and expenses,
analyse spending by category and month, set monthly budgets, and import/export
your data. Everything is stored in a single SQLite file, so backing up is just
copying one file.

Requires Python 3.10+. No third-party packages.

## Install

Run it directly from the project directory:

```powershell
python -m expense_tracker --help
```

Or install it so the `expense` command is available anywhere:

```powershell
pip install -e .
expense --help
```

## Quick start

```powershell
expense add 42.50 Food -d 2026-10-02 -n "groceries"   # expense (default)
expense add 3000 Salary -t income -d 2026-10-01       # income
expense budget set Food 400                           # monthly budget
expense list -m 2026-10                               # this month's entries
expense report -m 2026-10                             # full breakdown
```

## Commands

| Command | Description |
| --- | --- |
| `add AMOUNT CATEGORY [-t income\|expense] [-d DATE] [-n NOTE]` | Record a transaction (date defaults to today). |
| `list [--from D] [--to D] [-m YYYY-MM] [-c CATEGORY] [-t TYPE] [-l N]` | List transactions. |
| `delete ID` | Delete a transaction. |
| `summary [--from D] [--to D] [-m YYYY-MM]` | Income / expense / balance totals. |
| `report [--from D] [--to D] [-m YYYY-MM]` | Category and month breakdown plus budget status. |
| `budget set CATEGORY AMOUNT` | Set a monthly budget. |
| `budget list` / `budget remove CATEGORY` | Inspect or remove budgets. |
| `export OUTPUT [-f csv\|json] ...` | Export (use `-` for stdout). |
| `import FILE` | Import transactions from a CSV file. |

Periods default to the current month for `summary`/`report`. Amounts accept
`12`, `12.5`, `$1,234.56`, etc. Dates use `YYYY-MM-DD`.

### Examples

```powershell
expense report --from 2026-01-01 --to 2026-12-31
expense export backup.json -f json -m 2026-10
expense import backup.csv
```

## Data & storage

- Money is stored as **integer cents** (no floating point rounding errors).
- The database lives at `~/.expense-tracker/data.db` by default.
- Override it with the global `--db PATH` option (put it before the command):

```powershell
expense --db D:\finance\my.db report -m 2026-10
```

### CSV format

`import` expects a header row with these columns (extra columns are ignored):

```csv
date,kind,amount,category,note
2026-10-01,income,3000.00,Salary,
2026-10-02,expense,42.50,Food,groceries
```

## Tests

```powershell
python -m unittest discover -s tests -v
```

## Project layout

```
expense_tracker/
  db.py        SQLite schema + CRUD (transactions, budgets)
  reports.py   pure functions: totals, grouping, formatting, ASCII bars
  cli.py       argparse commands and rendering
  __main__.py  enables `python -m expense_tracker`
tests/         unittest suite for db, reports and an end-to-end CLI flow
```
