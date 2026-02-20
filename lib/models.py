"""
Typed data models for all Google API resources.

All classes are plain dataclasses — no external dependencies, safe to import
anywhere. Business logic lives in the client classes, not here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


# ── Email ─────────────────────────────────────────────────────────────────────

@dataclass
class EmailMessage:
    """A single Gmail message (one node in a thread)."""

    message_id: str
    thread_id: str
    subject: str
    sender: str
    recipients: list[str]
    date: datetime
    snippet: str
    body_plain: str
    labels: list[str]

    @property
    def is_unread(self) -> bool:
        return "UNREAD" in self.labels

    @property
    def is_important(self) -> bool:
        return "IMPORTANT" in self.labels

    @property
    def is_inbox(self) -> bool:
        return "INBOX" in self.labels


@dataclass
class EmailThread:
    """A Gmail conversation (thread) containing one or more messages."""

    thread_id: str
    subject: str
    messages: list[EmailMessage] = field(default_factory=list)

    @property
    def latest(self) -> Optional[EmailMessage]:
        return self.messages[-1] if self.messages else None

    @property
    def earliest(self) -> Optional[EmailMessage]:
        return self.messages[0] if self.messages else None

    @property
    def participants(self) -> list[str]:
        """Unique senders in thread order (deduplicated, preserving order)."""
        seen: set[str] = set()
        result: list[str] = []
        for msg in self.messages:
            if msg.sender not in seen:
                seen.add(msg.sender)
                result.append(msg.sender)
        return result

    @property
    def is_unread(self) -> bool:
        return any(m.is_unread for m in self.messages)

    @property
    def message_count(self) -> int:
        return len(self.messages)


# ── Calendar ──────────────────────────────────────────────────────────────────

@dataclass
class CalendarEvent:
    """A Google Calendar event."""

    event_id: str
    title: str
    start: datetime
    end: datetime
    description: str = ""
    location: str = ""
    attendees: list[str] = field(default_factory=list)
    organizer: str = ""
    html_link: str = ""
    is_all_day: bool = False

    @property
    def duration_minutes(self) -> int:
        return max(0, int((self.end - self.start).total_seconds() / 60))

    @property
    def start_label(self) -> str:
        """Human-readable start time, or 'all-day' for full-day events."""
        return self.start.strftime("%H:%M") if not self.is_all_day else "all-day"

    @property
    def end_label(self) -> str:
        return self.end.strftime("%H:%M") if not self.is_all_day else ""


# ── Contacts ──────────────────────────────────────────────────────────────────

@dataclass
class Contact:
    """A Google Contacts person record."""

    resource_name: str
    name: str
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    organization: str = ""

    @property
    def primary_email(self) -> Optional[str]:
        return self.emails[0] if self.emails else None

    @property
    def primary_phone(self) -> Optional[str]:
        return self.phones[0] if self.phones else None


# ── Drive ─────────────────────────────────────────────────────────────────────

@dataclass
class DriveFile:
    """A file or folder in Google Drive."""

    file_id: str
    name: str
    mime_type: str
    created_time: datetime
    modified_time: datetime
    web_view_link: str = ""
    size_bytes: Optional[int] = None

    @property
    def is_folder(self) -> bool:
        return self.mime_type == "application/vnd.google-apps.folder"

    @property
    def is_google_doc(self) -> bool:
        return self.mime_type.startswith("application/vnd.google-apps.")

    @property
    def size_kb(self) -> Optional[float]:
        return round(self.size_bytes / 1024, 1) if self.size_bytes is not None else None
