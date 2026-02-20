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


# ── Docs ──────────────────────────────────────────────────────────────────────

@dataclass
class GoogleDoc:
    """A Google Docs document."""

    doc_id: str
    title: str
    body_text: str          # plain text extracted from all paragraphs and tables
    revision_id: str = ""
    url: str = ""

    @property
    def word_count(self) -> int:
        return len(self.body_text.split())


# ── Slides ────────────────────────────────────────────────────────────────────

@dataclass
class Slide:
    """A single slide within a Google Slides presentation."""

    slide_id: str
    index: int
    text_content: str       # concatenated text from all shapes on this slide
    notes: str = ""         # speaker notes


@dataclass
class Presentation:
    """A Google Slides presentation."""

    presentation_id: str
    title: str
    slides: list[Slide] = field(default_factory=list)
    url: str = ""

    @property
    def slide_count(self) -> int:
        return len(self.slides)

    @property
    def full_text(self) -> str:
        """All slide text joined by slide separators."""
        return "\n---\n".join(
            f"[Slide {s.index + 1}] {s.text_content}" for s in self.slides
        )


# ── Tasks ─────────────────────────────────────────────────────────────────────

@dataclass
class Task:
    """A single Google Task."""

    task_id: str
    title: str
    status: str             # 'needsAction' | 'completed'
    notes: str = ""
    due: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    parent_id: Optional[str] = None

    @property
    def is_done(self) -> bool:
        return self.status == "completed"


@dataclass
class TaskList:
    """A Google Tasks list (container for tasks)."""

    list_id: str
    title: str
    updated: Optional[datetime] = None


# ── Keep ──────────────────────────────────────────────────────────────────────

@dataclass
class KeepNote:
    """A Google Keep note.

    Note: Google Keep API is only available on Google Workspace accounts.
    Personal Gmail accounts will receive a 403 error.
    """

    name: str               # resource name: "notes/abc123"
    title: str
    text_content: str
    create_time: Optional[datetime] = None
    update_time: Optional[datetime] = None
    is_trashed: bool = False
    is_pinned: bool = False
    labels: list[str] = field(default_factory=list)

    @property
    def note_id(self) -> str:
        """Short ID extracted from the resource name."""
        return self.name.split("/")[-1] if "/" in self.name else self.name


# ── Meet ──────────────────────────────────────────────────────────────────────

@dataclass
class MeetingSpace:
    """A Google Meet meeting space (persistent room with a stable URI)."""

    name: str               # resource name: "spaces/abc123"
    meeting_uri: str        # e.g. https://meet.google.com/abc-defg-hij
    meeting_code: str       # e.g. "abc-defg-hij"

    @property
    def space_id(self) -> str:
        return self.name.split("/")[-1] if "/" in self.name else self.name


# ── Drive Labels ──────────────────────────────────────────────────────────────

@dataclass
class LabelField:
    """A single field definition within a Drive Label."""

    field_id: str
    display_name: str
    field_type: str         # 'TEXT' | 'INTEGER' | 'DATE' | 'SELECTION' | 'USER'


@dataclass
class DriveLabel:
    """A Google Drive Label (metadata schema that can be applied to files)."""

    label_id: str
    name: str               # resource name: "labels/abc123"
    title: str
    description: str = ""
    label_type: str = ""    # 'ADMIN' | 'SHARED'
    fields: list[LabelField] = field(default_factory=list)
    is_published: bool = False
