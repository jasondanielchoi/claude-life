"""
GoogleServiceFactory — single OAuth2 credential shared across all Google API clients.

All five service objects (Gmail, Calendar, Sheets, Drive, People) are built lazily
and cached, so constructing multiple clients from the same factory does not trigger
repeated auth flows or API client builds.

Usage:
    factory = GoogleServiceFactory()

    # Access service objects directly (built on first access, cached after)
    gmail_svc    = factory.gmail
    calendar_svc = factory.calendar
    sheets_svc   = factory.sheets
    drive_svc    = factory.drive
    people_svc   = factory.people

    # Or pass the factory to a typed client class:
    from lib.gmail_client import GmailClient
    client = GmailClient(factory)
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

# Ensure ~/life is on the path so google_auth.py is importable
_LIFE_DIR = Path("~/life").expanduser()
if str(_LIFE_DIR) not in sys.path:
    sys.path.insert(0, str(_LIFE_DIR))

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from google_auth import get_credentials  # ~/life/google_auth.py


# Default scopes covering all five Google APIs used across Life Ops
ALL_SCOPES: list[str] = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/contacts.readonly",
]


class GoogleServiceFactory:
    """
    Constructs and caches Google API service objects from a single OAuth2 credential.

    Token refresh is handled transparently by google_auth.get_credentials().
    Service objects are built at most once per (api_name, version) pair.
    """

    def __init__(self, scopes: Optional[list[str]] = None) -> None:
        self._scopes: list[str] = scopes or ALL_SCOPES
        self._creds: Optional[Credentials] = None
        self._services: dict[str, Any] = {}

    # ── Credentials ───────────────────────────────────────────────────────────

    @property
    def credentials(self) -> Credentials:
        """Return valid (auto-refreshed) OAuth2 credentials."""
        if self._creds is None or not self._creds.valid:
            self._creds = get_credentials(self._scopes)
        return self._creds

    # ── Internal builder ──────────────────────────────────────────────────────

    def _build(self, name: str, version: str) -> Any:
        """Build and cache a googleapiclient service object."""
        key = f"{name}/{version}"
        if key not in self._services:
            self._services[key] = build(
                name, version, credentials=self.credentials
            )
        return self._services[key]

    # ── Service properties ────────────────────────────────────────────────────

    @property
    def gmail(self) -> Any:
        """Gmail API v1 service object."""
        return self._build("gmail", "v1")

    @property
    def calendar(self) -> Any:
        """Google Calendar API v3 service object."""
        return self._build("calendar", "v3")

    @property
    def sheets(self) -> Any:
        """Google Sheets API v4 service object."""
        return self._build("sheets", "v4")

    @property
    def drive(self) -> Any:
        """Google Drive API v3 service object."""
        return self._build("drive", "v3")

    @property
    def people(self) -> Any:
        """Google People API v1 service object (Contacts)."""
        return self._build("people", "v1")
