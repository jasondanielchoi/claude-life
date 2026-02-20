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


# All scopes across the full Life Ops Google integration suite
ALL_SCOPES: list[str] = [
    # ── Original five ─────────────────────────────────────────────────────────
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/contacts.readonly",
    # ── New — verified working on personal Gmail ──────────────────────────────
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/meetings.space.created",     # Meet (create/modify spaces made by this app)
    "https://www.googleapis.com/auth/meetings.space.readonly",   # Meet (read any space)
    # ── Excluded — requires service account or org-level approval ─────────────
    # "https://www.googleapis.com/auth/drive.labels"
    # ── Excluded — Workspace accounts only ────────────────────────────────────
    # "https://www.googleapis.com/auth/keep"
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

    @property
    def docs(self) -> Any:
        """Google Docs API v1 service object."""
        return self._build("docs", "v1")

    @property
    def slides(self) -> Any:
        """Google Slides API v1 service object."""
        return self._build("slides", "v1")

    @property
    def tasks(self) -> Any:
        """Google Tasks API v1 service object."""
        return self._build("tasks", "v1")

    @property
    def keep(self) -> Any:
        """Google Keep API v1 service object. Requires Google Workspace account."""
        return self._build("keep", "v1")

    @property
    def meet(self) -> Any:
        """Google Meet REST API v2 service object."""
        return self._build("meet", "v2")

    @property
    def drive_labels(self) -> Any:
        """Drive Labels API v2 service object."""
        return self._build("drivelabels", "v2")
