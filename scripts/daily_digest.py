"""
Daily Digest — morning briefing from Google Calendar + Gmail.

Fetches today's calendar events and recent important email, then emits a
single JSON dict to stdout for Claude to consume at session start.
Designed to be called by Claude at the start of a new session to orient
on what's on the calendar and what email needs attention.

Usage (Claude calls this in a Bash tool):
    ~/life/.venv/bin/python3 ~/life/scripts/daily_digest.py
    ~/life/.venv/bin/python3 ~/life/scripts/daily_digest.py --days-ahead 3
    ~/life/.venv/bin/python3 ~/life/scripts/daily_digest.py --debug
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure ~/life is on the path
_LIFE = Path("~/life").expanduser()
sys.path.insert(0, str(_LIFE))

from lib.base import BaseScript
from lib.calendar_client import CalendarClient
from lib.gmail_client import GmailClient
from lib.google_factory import GoogleServiceFactory
from lib.models import CalendarEvent, EmailMessage


class DailyDigest(BaseScript):
    """
    Pulls today's calendar events and recent important emails into one JSON digest.

    Output schema:
        {
            "generated_at": "<ISO 8601 UTC>",
            "calendar": {
                "window_days": int,
                "event_count": int,
                "events": [ { title, start, end, duration_minutes, location,
                               attendees, description, is_all_day, link } ]
            },
            "email": {
                "unread_count": int,
                "important_unread_count": int,
                "important_threads": [ { message_id, thread_id, subject, sender,
                                         date, snippet, body_preview, labels } ],
                "recent_senders": [ str ]   # top 10 unique senders in unread
            }
        }
    """

    def __init__(self, log_level: int = logging.INFO, days_ahead: int = 1) -> None:
        super().__init__(log_level=log_level)
        self.days_ahead = days_ahead
        self._factory = GoogleServiceFactory()
        self._gmail   = GmailClient(self._factory)
        self._cal     = CalendarClient(self._factory)

    # ── run() ─────────────────────────────────────────────────────────────────

    def run(self) -> dict[str, Any]:
        self.logger.info("Fetching daily digest (days_ahead=%d)…", self.days_ahead)

        # ── Calendar ──────────────────────────────────────────────────────────
        if self.days_ahead == 1:
            events = self._cal.get_today_events()
        else:
            events = self._cal.get_upcoming_events(days=self.days_ahead)
        self.logger.info("Calendar: %d event(s) fetched", len(events))

        # ── Email ─────────────────────────────────────────────────────────────
        unread = self._gmail.get_unread(max_results=30)
        important_unread = [m for m in unread if m.is_important]
        self.logger.info(
            "Email: %d unread total, %d important+unread",
            len(unread), len(important_unread),
        )

        # ── Assemble ──────────────────────────────────────────────────────────
        digest: dict[str, Any] = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "calendar": {
                "window_days": self.days_ahead,
                "event_count": len(events),
                "events": [_fmt_event(e) for e in events],
            },
            "email": {
                "unread_count": len(unread),
                "important_unread_count": len(important_unread),
                "important_threads": [_fmt_email(m) for m in important_unread[:10]],
                # Deduplicated sender list, insertion-ordered, capped at 10
                "recent_senders": list(dict.fromkeys(m.sender for m in unread[:20]))[:10],
            },
        }

        self.logger.info(
            "Digest ready — %d events, %d unread, %d important.",
            len(events), len(unread), len(important_unread),
        )
        return digest

    # ── CLI entrypoint ────────────────────────────────────────────────────────

    @classmethod
    def main(cls) -> None:
        parser = argparse.ArgumentParser(
            description="Daily Digest — calendar + Gmail briefing"
        )
        parser.add_argument("--debug", action="store_true")
        parser.add_argument(
            "--days-ahead", type=int, default=1, metavar="N",
            help="How many calendar days to look ahead (default: 1 = today only)"
        )
        args = parser.parse_args()

        script = cls(
            log_level=logging.DEBUG if args.debug else logging.INFO,
            days_ahead=args.days_ahead,
        )
        t0 = time.monotonic()
        try:
            result = script.run()
            elapsed = time.monotonic() - t0
            script.logger.info("Completed in %.2fs", elapsed)
            print(json.dumps(result, indent=2, default=str))
        except Exception:
            script.logger.exception("DailyDigest failed")
            sys.exit(1)


# ── Formatters ────────────────────────────────────────────────────────────────

def _fmt_event(event: CalendarEvent) -> dict:
    return {
        "title":            event.title,
        "start":            event.start.isoformat(),
        "end":              event.end.isoformat(),
        "duration_minutes": event.duration_minutes,
        "location":         event.location,
        "attendees":        event.attendees,
        "description":      event.description[:500] if event.description else "",
        "is_all_day":       event.is_all_day,
        "link":             event.html_link,
    }


def _fmt_email(msg: EmailMessage) -> dict:
    return {
        "message_id":   msg.message_id,
        "thread_id":    msg.thread_id,
        "subject":      msg.subject,
        "sender":       msg.sender,
        "date":         msg.date.isoformat(),
        "snippet":      msg.snippet,
        "body_preview": msg.body_plain[:800],
        "labels":       msg.labels,
    }


if __name__ == "__main__":
    DailyDigest.main()
