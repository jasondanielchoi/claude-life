"""
SheetsClient — typed, high-level wrapper around the Google Sheets API v4 service.

Covers reading ranges (raw and as dicts), writing, appending, creating spreadsheets,
and applying basic formatting (bold header, freeze row, auto-resize columns).
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from .google_factory import GoogleServiceFactory

logger = logging.getLogger(__name__)

# Type alias for a 2-D grid of cell values
ValueMatrix = list[list[Any]]


class SheetsClient:
    """
    High-level Google Sheets read/write operations.

    Usage:
        factory = GoogleServiceFactory()
        sheets  = SheetsClient(factory)

        data = sheets.read_as_dicts("spreadsheet_id", "Sheet1!A:Z")
        sheets.append_rows("spreadsheet_id", "Sheet1", [["new", "row"]])
    """

    def __init__(self, factory: GoogleServiceFactory) -> None:
        self._svc = factory.sheets

    # ── Read ──────────────────────────────────────────────────────────────────

    def read_range(self, spreadsheet_id: str, range_name: str) -> ValueMatrix:
        """
        Return cell values as a list of rows (list of lists).
        Missing/empty cells are returned as empty strings.
        """
        resp = self._svc.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=range_name,
        ).execute()
        return resp.get("values", [])

    def read_as_dicts(
        self, spreadsheet_id: str, range_name: str
    ) -> list[dict[str, str]]:
        """
        Read a range where the first row contains headers.
        Returns a list of {header: cell_value} dicts, one per data row.

        Example:
            [{"Name": "Alice", "Score": "95"}, {"Name": "Bob", "Score": "88"}]
        """
        rows = self.read_range(spreadsheet_id, range_name)
        if not rows:
            return []
        headers = rows[0]
        result: list[dict[str, str]] = []
        for row in rows[1:]:
            result.append(
                {headers[i]: (row[i] if i < len(row) else "") for i in range(len(headers))}
            )
        return result

    # ── Write ─────────────────────────────────────────────────────────────────

    def write_range(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: ValueMatrix,
        value_input_option: str = "USER_ENTERED",
    ) -> None:
        """
        Overwrite a range with the provided 2-D list of values.

        value_input_option:
            "USER_ENTERED"  — parses values as if a user typed them (formulas, dates work)
            "RAW"           — stores values as-is (no formula evaluation)
        """
        self._svc.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption=value_input_option,
            body={"values": values},
        ).execute()
        logger.info("Wrote %d rows to %s in %s", len(values), range_name, spreadsheet_id)

    def append_rows(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        rows: ValueMatrix,
        value_input_option: str = "USER_ENTERED",
    ) -> None:
        """
        Append rows below the last row that contains data in sheet_name.
        Existing data is never overwritten.
        """
        self._svc.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A1",
            valueInputOption=value_input_option,
            insertDataOption="INSERT_ROWS",
            body={"values": rows},
        ).execute()
        logger.info("Appended %d rows to %s", len(rows), sheet_name)

    def clear_range(self, spreadsheet_id: str, range_name: str) -> None:
        """Clear all values in the given range (structure preserved)."""
        self._svc.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id,
            range=range_name,
        ).execute()
        logger.info("Cleared range %s", range_name)

    # ── Create ────────────────────────────────────────────────────────────────

    def create_spreadsheet(
        self,
        title: str,
        sheet_names: Optional[list[str]] = None,
    ) -> str:
        """
        Create a new Google Sheets spreadsheet and return its spreadsheet_id.

        Args:
            title:       Spreadsheet title visible in Drive.
            sheet_names: Names for the initial sheet tabs. Defaults to ["Sheet1"].
        """
        sheets = [
            {"properties": {"title": name}}
            for name in (sheet_names or ["Sheet1"])
        ]
        body = {"properties": {"title": title}, "sheets": sheets}
        result = self._svc.spreadsheets().create(body=body).execute()
        sid = result["spreadsheetId"]
        logger.info("Created spreadsheet %s: %s", sid, title)
        return sid

    # ── Metadata ──────────────────────────────────────────────────────────────

    def get_sheet_id(self, spreadsheet_id: str, sheet_name: str) -> Optional[int]:
        """Return the numeric sheetId for a named sheet tab, or None if not found."""
        meta = self._svc.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        for sheet in meta.get("sheets", []):
            props = sheet.get("properties", {})
            if props.get("title") == sheet_name:
                return props["sheetId"]
        return None

    def list_sheet_names(self, spreadsheet_id: str) -> list[str]:
        """Return the names of all sheet tabs in a spreadsheet."""
        meta = self._svc.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        return [
            s["properties"]["title"]
            for s in meta.get("sheets", [])
        ]

    # ── Formatting ────────────────────────────────────────────────────────────

    def format_header_row(
        self,
        spreadsheet_id: str,
        sheet_id: int,
        row_index: int = 0,
        bg_color: Optional[dict] = None,
    ) -> None:
        """
        Bold and optionally colour a header row, then freeze it.

        Args:
            spreadsheet_id: Target spreadsheet.
            sheet_id:       Numeric sheet tab ID (from get_sheet_id()).
            row_index:      0-based row index of the header (default 0 = first row).
            bg_color:       RGB dict, e.g. {"red": 0.2, "green": 0.35, "blue": 0.7}.
                            Defaults to a deep blue.
        """
        color = bg_color or {"red": 0.2, "green": 0.35, "blue": 0.7}
        requests = [
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": row_index,
                        "endRowIndex": row_index + 1,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {
                                "bold": True,
                                "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                            },
                            "backgroundColor": color,
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,backgroundColor)",
                }
            },
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": sheet_id,
                        "gridProperties": {"frozenRowCount": row_index + 1},
                    },
                    "fields": "gridProperties.frozenRowCount",
                }
            },
            {
                "autoResizeDimensions": {
                    "dimensions": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": 0,
                        "endIndex": 20,
                    }
                }
            },
        ]
        self._svc.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": requests},
        ).execute()
        logger.info("Formatted header row %d on sheet %d", row_index, sheet_id)
