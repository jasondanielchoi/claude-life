"""
CalendarClient — typed, high-level wrapper around the Google Calendar API v3 service.

Handles timezone-aware datetimes throughout. Local timezone defaults to
America/New_York; override via the LOCAL_TZ class variable or constructor arg.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from .google_factory import GoogleServiceFactory
from .models import CalendarEvent

logger = logging.getLogger(__name__)

_DEFAULT_TZ = ZoneInfo("America/New_York")


def _parse_event_dt(dt_dict: dict, is_all_day: bool, tz: ZoneInfo) -> datetime:
    """
    Parse a Calendar API 'start' or 'end' dict into a timezone-aware datetime.

    All-day events have a 'date' key; timed events have 'dateTime'.
    """
    if is_all_day:
        d = date.fromisoformat(dt_dict["date"])
        return datetime(d.year, d.month, d.day, tzinfo=tz)
    dt_str = dt_dict.get("dateTime", "")
    return datetime.fromisoformat(dt_str).astimezone(timezone.utc)


class CalendarClient:
    """
    High-level Google Calendar operations.

    All returned CalendarEvent objects use UTC-aware datetimes for timed events
    and local-timezone-aware datetimes for all-day events.

    Usage:
        factory = GoogleServiceFactory()
        cal = CalendarClient(factory)
        events = cal.get_today_events()
    """

    def __init__(
        self,
        factory: GoogleServiceFactory,
        calendar_id: str = "primary",
        local_tz: ZoneInfo = _DEFAULT_TZ,
    ) -> None:
        self._svc = factory.calendar
        self.calendar_id = calendar_id
        self.local_tz = local_tz

    # ── Read events ───────────────────────────────────────────────────────────

    def get_events(
        self,
        start: datetime,
        end: datetime,
        max_results: int = 100,
        query: Optional[str] = None,
    ) -> list[CalendarEvent]:
        """
        Return events within [start, end), sorted by start time.

        Both datetimes must be timezone-aware.

        Args:
            start:       Window start (inclusive).
            end:         Window end (exclusive).
            max_results: API page size cap.
            query:       Optional free-text search within event titles/descriptions.
        """
        kwargs: dict = dict(
            calendarId=self.calendar_id,
            timeMin=start.isoformat(),
            timeMax=end.isoformat(),
            maxResults=max_results,
            singleEvents=True,   # expand recurring events
            orderBy="startTime",
        )
        if query:
            kwargs["q"] = query

        resp = self._svc.events().list(**kwargs).execute()
        return [self._parse_event(e) for e in resp.get("items", [])]

    def get_today_events(self) -> list[CalendarEvent]:
        """Return all events on today's date (local timezone)."""
        today = datetime.now(self.local_tz).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        tomorrow = today + timedelta(days=1)
        return self.get_events(today, tomorrow)

    def get_upcoming_events(self, days: int = 7) -> list[CalendarEvent]:
        """Return events starting from now through the next N days."""
        now = datetime.now(timezone.utc)
        return self.get_events(now, now + timedelta(days=days))

    def get_events_on_date(self, target_date: date) -> list[CalendarEvent]:
        """Return all events on a specific calendar date."""
        start = datetime(
            target_date.year, target_date.month, target_date.day, tzinfo=self.local_tz
        )
        return self.get_events(start, start + timedelta(days=1))

    # ── Create / modify events ────────────────────────────────────────────────

    def create_event(
        self,
        title: str,
        start: datetime,
        end: datetime,
        description: str = "",
        location: str = "",
        attendees: Optional[list[str]] = None,
        send_notifications: bool = False,
    ) -> str:
        """
        Create a calendar event and return the new event_id.

        Args:
            title:               Event title / summary.
            start:               Event start (timezone-aware datetime).
            end:                 Event end (timezone-aware datetime).
            description:         Optional body text.
            location:            Optional location string.
            attendees:           List of email addresses to invite.
            send_notifications:  Whether to email invitations to attendees.
        """
        body: dict = {
            "summary": title,
            "description": description,
            "location": location,
            "start": {"dateTime": start.isoformat(), "timeZone": str(self.local_tz)},
            "end":   {"dateTime": end.isoformat(),   "timeZone": str(self.local_tz)},
        }
        if attendees:
            body["attendees"] = [{"email": a} for a in attendees]

        event = self._svc.events().insert(
            calendarId=self.calendar_id,
            body=body,
            sendNotifications=send_notifications,
        ).execute()
        logger.info("Created event %s: %s", event["id"], title)
        return event["id"]

    def update_event_description(self, event_id: str, description: str) -> None:
        """Patch the description field of an existing event."""
        self._svc.events().patch(
            calendarId=self.calendar_id,
            eventId=event_id,
            body={"description": description},
        ).execute()
        logger.info("Updated description for event %s", event_id)

    def delete_event(self, event_id: str) -> None:
        """Delete a calendar event by ID."""
        self._svc.events().delete(
            calendarId=self.calendar_id, eventId=event_id
        ).execute()
        logger.info("Deleted event %s", event_id)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _parse_event(self, raw: dict) -> CalendarEvent:
        is_all_day = (
            "date" in raw.get("start", {})
            and "dateTime" not in raw.get("start", {})
        )
        start = _parse_event_dt(raw["start"], is_all_day, self.local_tz)
        end   = _parse_event_dt(raw["end"],   is_all_day, self.local_tz)

        # Exclude the calendar owner from the attendees list
        attendees = [
            a.get("email", "")
            for a in raw.get("attendees", [])
            if not a.get("self", False)
        ]

        return CalendarEvent(
            event_id=raw["id"],
            title=raw.get("summary", "(no title)"),
            start=start,
            end=end,
            description=raw.get("description", ""),
            location=raw.get("location", ""),
            attendees=attendees,
            organizer=raw.get("organizer", {}).get("email", ""),
            html_link=raw.get("htmlLink", ""),
            is_all_day=is_all_day,
        )
