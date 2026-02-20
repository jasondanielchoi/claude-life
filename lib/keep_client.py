"""
KeepClient — typed wrapper around the Google Keep API v1.

⚠️  WORKSPACE ONLY: The Google Keep API is only available to Google Workspace
    accounts (Business/Enterprise). Personal Gmail accounts receive a 403 error.
    All public methods catch this and raise a clear RuntimeError rather than a
    cryptic API error.

Supports listing notes, creating notes, and deleting (trashing) notes.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from googleapiclient.errors import HttpError

from .google_factory import GoogleServiceFactory
from .models import KeepNote

logger = logging.getLogger(__name__)

_WORKSPACE_ERROR = (
    "Google Keep API requires a Google Workspace account. "
    "Personal Gmail accounts are not supported by the Keep API."
)


class KeepClient:
    """
    High-level Google Keep note operations.

    ⚠️  Only available on Google Workspace accounts.

    Usage:
        factory = GoogleServiceFactory()
        keep    = KeepClient(factory)

        notes = keep.list_notes()
        note_name = keep.create_note("Meeting notes", "Key points from today...")
    """

    def __init__(self, factory: GoogleServiceFactory) -> None:
        self._svc = factory.keep

    # ── Read ──────────────────────────────────────────────────────────────────

    def list_notes(self, max_results: int = 20, include_trashed: bool = False) -> list[KeepNote]:
        """
        Return up to max_results notes, newest first.

        Args:
            max_results:     Page size cap.
            include_trashed: Whether to include trashed notes.
        """
        try:
            filter_str = "" if include_trashed else "-trashed"
            kwargs: dict = {"pageSize": max_results}
            if filter_str:
                kwargs["filter"] = filter_str
            resp = self._svc.notes().list(**kwargs).execute()
            return [_parse_note(n) for n in resp.get("notes", [])]
        except HttpError as exc:
            if exc.resp.status == 403:
                raise RuntimeError(_WORKSPACE_ERROR) from exc
            raise

    def get_note(self, name: str) -> KeepNote:
        """
        Fetch a single note by resource name (e.g. 'notes/abc123').
        """
        try:
            raw = self._svc.notes().get(name=name).execute()
            return _parse_note(raw)
        except HttpError as exc:
            if exc.resp.status == 403:
                raise RuntimeError(_WORKSPACE_ERROR) from exc
            raise

    # ── Create ────────────────────────────────────────────────────────────────

    def create_note(self, title: str, text: str = "") -> str:
        """
        Create a new Keep note and return its resource name.

        Args:
            title: Note title.
            text:  Body text content. Can be empty.
        """
        body: dict = {
            "title": title,
            "body": {
                "text": {"text": text}
            },
        }
        try:
            result = self._svc.notes().create(body=body).execute()
            name = result["name"]
            logger.info("Created Keep note %s: %s", name, title)
            return name
        except HttpError as exc:
            if exc.resp.status == 403:
                raise RuntimeError(_WORKSPACE_ERROR) from exc
            raise

    # ── Delete ────────────────────────────────────────────────────────────────

    def delete_note(self, name: str) -> None:
        """
        Delete a note by resource name. This is permanent (not a trash operation).
        """
        try:
            self._svc.notes().delete(name=name).execute()
            logger.info("Deleted Keep note %s", name)
        except HttpError as exc:
            if exc.resp.status == 403:
                raise RuntimeError(_WORKSPACE_ERROR) from exc
            raise


# ── Parser ────────────────────────────────────────────────────────────────────

def _parse_dt(s: str) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_note(raw: dict) -> KeepNote:
    # Extract text content from body
    body = raw.get("body", {})
    text = body.get("text", {}).get("text", "")

    # Labels are resource names like {"name": "labels/abc123"}
    label_names = [lbl.get("name", "") for lbl in raw.get("labels", [])]

    return KeepNote(
        name=raw.get("name", ""),
        title=raw.get("title", ""),
        text_content=text,
        create_time=_parse_dt(raw.get("createTime", "")),
        update_time=_parse_dt(raw.get("updateTime", "")),
        is_trashed=raw.get("trashed", False),
        is_pinned=raw.get("pinned", False),
        labels=label_names,
    )
