"""
db_to_sheet.py — Query any DB and write results to a Google Sheet.

Usage examples:

  # Write to an existing sheet (overwrites at A1):
  ~/life/.venv/bin/python3 ~/life/scripts/db_to_sheet.py \\
    --query "SELECT * FROM ideas ORDER BY ev_score DESC" \\
    --spreadsheet-id 1abc123 \\
    --sheet Ideas

  # Create a new spreadsheet and populate it:
  ~/life/.venv/bin/python3 ~/life/scripts/db_to_sheet.py \\
    --query "SELECT rank, title, sector FROM ideas" \\
    --create "My Ideas Tracker" \\
    --sheet Ideas \\
    --format-header \\
    --share

  # Append rows instead of overwriting:
  ~/life/.venv/bin/python3 ~/life/scripts/db_to_sheet.py \\
    --query "SELECT * FROM new_leads" \\
    --spreadsheet-id 1abc123 \\
    --append

  # Use a non-default SQLite DB:
  ~/life/.venv/bin/python3 ~/life/scripts/db_to_sheet.py \\
    --db ~/other/data.db \\
    --query "SELECT ..."

  # Use any SQLAlchemy-compatible DB (postgres, mysql, etc.):
  ~/life/.venv/bin/python3 ~/life/scripts/db_to_sheet.py \\
    --dsn "postgresql://user:pass@host/dbname" \\
    --query "SELECT ..."

Output: JSON  { spreadsheet_id, sheet_url, rows_written, headers }
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from lib.google_factory import GoogleServiceFactory
from lib.sheets_client import SheetsClient
from lib.drive_client import DriveClient

logger = logging.getLogger(__name__)

DEFAULT_DB = os.path.expanduser("~/life/data/life.db")


# ── DB helpers ────────────────────────────────────────────────────────────────

def _run_query_sqlite(db_path: str, query: str) -> tuple[list[str], list[list[Any]]]:
    """Execute query against a SQLite file. Returns (headers, rows)."""
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        cur = con.execute(query)
        rows_raw = cur.fetchall()
        if not rows_raw:
            return [], []
        headers = list(rows_raw[0].keys())
        rows = [list(r) for r in rows_raw]
        return headers, rows
    finally:
        con.close()


def _run_query_sqlalchemy(dsn: str, query: str) -> tuple[list[str], list[list[Any]]]:
    """Execute query via SQLAlchemy (supports postgres, mysql, mssql, etc.)."""
    try:
        from sqlalchemy import create_engine, text  # type: ignore
    except ImportError:
        sys.exit("sqlalchemy not installed — run: ~/life/.venv/bin/pip install sqlalchemy")

    engine = create_engine(dsn)
    with engine.connect() as con:
        result = con.execute(text(query))
        headers = list(result.keys())
        rows = [list(r) for r in result.fetchall()]
    return headers, rows


def fetch_data(
    query: str,
    db: str | None,
    dsn: str | None,
) -> tuple[list[str], list[list[Any]]]:
    if dsn:
        logger.debug("Connecting via SQLAlchemy DSN")
        return _run_query_sqlalchemy(dsn, query)
    db_path = db or DEFAULT_DB
    logger.debug("Connecting to SQLite: %s", db_path)
    return _run_query_sqlite(os.path.expanduser(db_path), query)


# ── Sheet helpers ─────────────────────────────────────────────────────────────

def resolve_spreadsheet(
    sheets_client: SheetsClient,
    spreadsheet_id: str | None,
    create_title: str | None,
    sheet_name: str,
) -> str:
    """Return spreadsheet_id — either existing or freshly created."""
    if spreadsheet_id:
        return spreadsheet_id
    if create_title:
        sid = sheets_client.create_spreadsheet(create_title, sheet_names=[sheet_name])
        logger.info("Created spreadsheet: %s", sid)
        return sid
    sys.exit("Provide --spreadsheet-id or --create to specify the target sheet.")


def build_value_matrix(
    headers: list[str],
    rows: list[list[Any]],
    include_header: bool,
) -> list[list[Any]]:
    """Assemble the 2-D list to write, coercing values to JSON-safe types."""
    matrix: list[list[Any]] = []
    if include_header:
        matrix.append(headers)
    for row in rows:
        matrix.append([
            v if isinstance(v, (str, int, float, bool)) else (str(v) if v is not None else "")
            for v in row
        ])
    return matrix


# ── Main ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Query a database and write results to a Google Sheet.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # ── Data source
    src = p.add_mutually_exclusive_group()
    src.add_argument("--db", metavar="PATH",
                     help=f"SQLite file path (default: {DEFAULT_DB})")
    src.add_argument("--dsn", metavar="DSN",
                     help="SQLAlchemy connection string for any other DB")

    p.add_argument("--query", "-q", required=True,
                   help="SQL SELECT to run")

    # ── Sheet target
    dest = p.add_mutually_exclusive_group()
    dest.add_argument("--spreadsheet-id", metavar="ID",
                      help="Existing spreadsheet ID to write into")
    dest.add_argument("--create", metavar="TITLE",
                      help="Create a new spreadsheet with this title")

    p.add_argument("--sheet", default="Sheet1",
                   help="Sheet tab name (default: Sheet1)")
    p.add_argument("--cell", default="A1",
                   help="Top-left cell to write at (default: A1)")

    # ── Write mode
    p.add_argument("--append", action="store_true",
                   help="Append rows below existing data instead of overwriting")
    p.add_argument("--no-header", dest="header", action="store_false", default=True,
                   help="Omit column names from the first row")

    # ── Formatting
    p.add_argument("--format-header", action="store_true",
                   help="Apply bold+freeze formatting to the header row")
    p.add_argument("--share", action="store_true",
                   help="Make spreadsheet public (anyone with link can view)")

    p.add_argument("--debug", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    # 1. Fetch data
    headers, rows = fetch_data(args.query, args.db, args.dsn)
    if not rows and not headers:
        result = {"rows_written": 0, "headers": [], "note": "Query returned no rows"}
        print(json.dumps(result, indent=2))
        return

    logger.info("Query returned %d rows, %d columns", len(rows), len(headers))

    # 2. Connect to Google
    factory = GoogleServiceFactory()
    sheets = SheetsClient(factory)

    # 3. Resolve spreadsheet
    spreadsheet_id = resolve_spreadsheet(
        sheets, args.spreadsheet_id, args.create, args.sheet
    )

    # 4. Build value matrix
    matrix = build_value_matrix(headers, rows, include_header=args.header)

    # 5. Write
    if args.append:
        sheets.append_rows(spreadsheet_id, args.sheet, matrix)
    else:
        range_name = f"{args.sheet}!{args.cell}"
        sheets.write_range(spreadsheet_id, range_name, matrix)

    rows_written = len(rows)
    logger.info("Wrote %d rows to %s", rows_written, spreadsheet_id)

    # 6. Optional formatting
    if args.format_header and args.header and not args.append:
        sheet_id = sheets.get_sheet_id(spreadsheet_id, args.sheet)
        if sheet_id is not None:
            sheets.format_header_row(spreadsheet_id, sheet_id)
            logger.info("Header row formatted")

    # 7. Optional share
    if args.share:
        drive = DriveClient(factory)
        drive.share_with_anyone(spreadsheet_id)
        logger.info("Spreadsheet shared publicly")

    sheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
    print(json.dumps({
        "spreadsheet_id": spreadsheet_id,
        "sheet_url": sheet_url,
        "sheet": args.sheet,
        "rows_written": rows_written,
        "headers": headers,
    }, indent=2))


if __name__ == "__main__":
    main()
