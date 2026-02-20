"""
Email Triage — fetch and structure unread Gmail threads for Claude to review.

Retrieves the N most recent unread threads (full content, truncated), deduplicated
by thread_id, and emits structured JSON to stdout. Claude reads this output to
summarise, suggest replies, flag action items, or draft responses.

Usage (Claude calls this in a Bash tool):
    ~/life/.venv/bin/python3 ~/life/scripts/email_triage.py
    ~/life/.venv/bin/python3 ~/life/scripts/email_triage.py --limit 20
    ~/life/.venv/bin/python3 ~/life/scripts/email_triage.py --query "is:unread from:recruiter"
    ~/life/.venv/bin/python3 ~/life/scripts/email_triage.py --debug

Output schema:
    {
        "generated_at": "<ISO 8601 UTC>",
        "query": str,
        "thread_count": int,
        "threads": [
            {
                "thread_id": str,
                "subject": str,
                "participants": [str],
                "message_count": int,
                "is_unread": bool,
                "latest_date": str,
                "snippet": str,
                "messages": [
                    {
                        "message_id": str,
                        "sender": str,
                        "recipients": [str],
                        "date": str,
                        "body": str,        # truncated to 1500 chars
                        "is_unread": bool,
                        "is_important": bool,
                        "labels": [str]
                    }
                ]
            }
        ]
    }
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

_LIFE = Path("~/life").expanduser()
sys.path.insert(0, str(_LIFE))

from lib.base import BaseScript
from lib.gmail_client import GmailClient
from lib.google_factory import GoogleServiceFactory
from lib.models import EmailMessage, EmailThread

_BODY_TRUNCATE = 1500   # chars per message body in output


class EmailTriage(BaseScript):
    """
    Fetches recent unread Gmail threads in structured JSON for Claude to triage.

    De-duplicates by thread_id, fetches full thread content, and truncates bodies
    to keep output size manageable (~1 500 chars per message).
    """

    def __init__(
        self,
        log_level: int = logging.INFO,
        limit: int = 10,
        query: str = "is:unread",
    ) -> None:
        super().__init__(log_level=log_level)
        self.limit = limit
        self.query = query
        self._factory = GoogleServiceFactory()
        self._gmail   = GmailClient(self._factory)

    # ── run() ─────────────────────────────────────────────────────────────────

    def run(self) -> dict[str, Any]:
        self.logger.info(
            "Email triage: query=%r, limit=%d", self.query, self.limit
        )

        # Step 1: search for matching messages
        messages = self._gmail.search(self.query, max_results=self.limit)
        self.logger.info("Search returned %d messages", len(messages))

        # Step 2: deduplicate by thread_id, keep the latest message per thread
        thread_map: dict[str, EmailMessage] = {}
        for msg in messages:
            if (
                msg.thread_id not in thread_map
                or msg.date > thread_map[msg.thread_id].date
            ):
                thread_map[msg.thread_id] = msg

        thread_ids = list(thread_map.keys())
        self.logger.info("Fetching %d unique threads…", len(thread_ids))

        # Step 3: fetch full threads
        threads: list[EmailThread] = []
        for tid in thread_ids:
            try:
                threads.append(self._gmail.get_thread(tid))
            except Exception as exc:
                self.logger.warning("Could not fetch thread %s: %s", tid, exc)

        result: dict[str, Any] = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "query":        self.query,
            "thread_count": len(threads),
            "threads":      [_fmt_thread(t) for t in threads],
        }

        self.logger.info("Triage complete — %d threads", len(threads))
        return result

    # ── CLI entrypoint ────────────────────────────────────────────────────────

    @classmethod
    def main(cls) -> None:
        parser = argparse.ArgumentParser(
            description="Email Triage — structured unread threads for Claude"
        )
        parser.add_argument("--debug", action="store_true")
        parser.add_argument(
            "--limit", type=int, default=10, metavar="N",
            help="Max number of messages to search (default: 10)"
        )
        parser.add_argument(
            "--query", type=str, default="is:unread",
            help='Gmail search query (default: "is:unread")'
        )
        args = parser.parse_args()

        script = cls(
            log_level=logging.DEBUG if args.debug else logging.INFO,
            limit=args.limit,
            query=args.query,
        )
        t0 = time.monotonic()
        try:
            result = script.run()
            elapsed = time.monotonic() - t0
            script.logger.info("Completed in %.2fs", elapsed)
            print(json.dumps(result, indent=2, default=str))
        except Exception:
            script.logger.exception("EmailTriage failed")
            sys.exit(1)


# ── Formatters ────────────────────────────────────────────────────────────────

def _fmt_thread(thread: EmailThread) -> dict:
    latest = thread.latest
    return {
        "thread_id":     thread.thread_id,
        "subject":       thread.subject,
        "participants":  thread.participants,
        "message_count": thread.message_count,
        "is_unread":     thread.is_unread,
        "latest_date":   latest.date.isoformat() if latest else "",
        "snippet":       latest.snippet if latest else "",
        "messages":      [_fmt_message(m) for m in thread.messages],
    }


def _fmt_message(msg: EmailMessage) -> dict:
    return {
        "message_id":  msg.message_id,
        "sender":      msg.sender,
        "recipients":  msg.recipients,
        "date":        msg.date.isoformat(),
        "body":        msg.body_plain[:_BODY_TRUNCATE],
        "is_unread":   msg.is_unread,
        "is_important": msg.is_important,
        "labels":      msg.labels,
    }


if __name__ == "__main__":
    EmailTriage.main()
