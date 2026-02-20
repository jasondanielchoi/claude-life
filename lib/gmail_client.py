"""
GmailClient — typed, high-level wrapper around the Gmail API v1 service.

All methods return lib.models objects rather than raw API dicts.
Supports searching, reading threads, sending, labelling, and basic mutations.
"""
from __future__ import annotations

import base64
import email as _email_lib
import logging
import re
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from .google_factory import GoogleServiceFactory
from .models import EmailMessage, EmailThread

logger = logging.getLogger(__name__)


# ── Parsing helpers ───────────────────────────────────────────────────────────

def _decode_payload(payload: dict) -> str:
    """
    Recursively walk a Gmail message payload and extract the first text/plain part.
    Handles simple messages (body.data) and multipart structures.
    """
    mime_type = payload.get("mimeType", "")

    if mime_type == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            # Gmail uses URL-safe base64; pad to multiple of 4
            padded = data + "=" * (-len(data) % 4)
            return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")

    if mime_type.startswith("multipart/"):
        for part in payload.get("parts", []):
            text = _decode_payload(part)
            if text:
                return text

    return ""


def _parse_date(date_str: str) -> datetime:
    """Parse an RFC 2822 date header into a UTC-aware datetime."""
    try:
        dt = _email_lib.utils.parsedate_to_datetime(date_str)
        return dt.astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def _split_addresses(header: str) -> list[str]:
    """Split a comma-separated To/CC header into a list of address strings."""
    return [a.strip() for a in re.split(r",\s*", header) if a.strip()]


def _parse_message(raw: dict) -> EmailMessage:
    """Convert a raw Gmail API message dict into a typed EmailMessage."""
    headers = {
        h["name"].lower(): h["value"]
        for h in raw.get("payload", {}).get("headers", [])
    }
    return EmailMessage(
        message_id=raw["id"],
        thread_id=raw.get("threadId", ""),
        subject=headers.get("subject", "(no subject)"),
        sender=headers.get("from", ""),
        recipients=_split_addresses(headers.get("to", "")),
        date=_parse_date(headers.get("date", "")),
        snippet=raw.get("snippet", ""),
        body_plain=_decode_payload(raw.get("payload", {})).strip(),
        labels=raw.get("labelIds", []),
    )


# ── Client class ──────────────────────────────────────────────────────────────

class GmailClient:
    """
    High-level Gmail operations.

    Instantiate with a GoogleServiceFactory so credentials are shared:
        factory = GoogleServiceFactory()
        client  = GmailClient(factory)
    """

    def __init__(self, factory: GoogleServiceFactory) -> None:
        self._svc = factory.gmail

    # ── Labels ────────────────────────────────────────────────────────────────

    def get_label_map(self) -> dict[str, str]:
        """Return {label_id: label_name} for all labels in the mailbox."""
        resp = self._svc.users().labels().list(userId="me").execute()
        return {lbl["id"]: lbl["name"] for lbl in resp.get("labels", [])}

    # ── Search / listing ──────────────────────────────────────────────────────

    def search(self, query: str, max_results: int = 20) -> list[EmailMessage]:
        """
        Search messages using a Gmail query string.

        Common query examples:
            "is:unread"
            "is:unread is:important"
            "from:boss@company.com"
            "subject:invoice after:2026/01/01"
        """
        resp = self._svc.users().messages().list(
            userId="me", q=query, maxResults=max_results
        ).execute()
        raw_list = resp.get("messages", [])

        results: list[EmailMessage] = []
        for item in raw_list:
            try:
                results.append(self.get_message(item["id"]))
            except Exception as exc:
                logger.warning("Skipping message %s: %s", item["id"], exc)
        return results

    def get_unread(self, max_results: int = 20) -> list[EmailMessage]:
        """Return the most recent unread messages."""
        return self.search("is:unread", max_results=max_results)

    def get_important_unread(self, max_results: int = 10) -> list[EmailMessage]:
        """Return messages marked important + unread."""
        return self.search("is:unread is:important", max_results=max_results)

    def get_inbox(self, max_results: int = 20) -> list[EmailMessage]:
        """Return recent inbox messages (read and unread)."""
        return self.search("in:inbox", max_results=max_results)

    # ── Single message / thread ───────────────────────────────────────────────

    def get_message(self, message_id: str) -> EmailMessage:
        """Fetch a single Gmail message by ID and return a typed EmailMessage."""
        raw = self._svc.users().messages().get(
            userId="me", id=message_id, format="full"
        ).execute()
        return _parse_message(raw)

    def get_thread(self, thread_id: str) -> EmailThread:
        """Fetch all messages in a Gmail thread and return a typed EmailThread."""
        raw = self._svc.users().threads().get(
            userId="me", id=thread_id, format="full"
        ).execute()
        messages = [_parse_message(m) for m in raw.get("messages", [])]
        subject = messages[0].subject if messages else ""
        return EmailThread(thread_id=thread_id, subject=subject, messages=messages)

    # ── Send ──────────────────────────────────────────────────────────────────

    def send_message(
        self,
        to: str | list[str],
        subject: str,
        body: str,
        thread_id: Optional[str] = None,
        reply_to_rfc_id: Optional[str] = None,
        html_body: Optional[str] = None,
    ) -> str:
        """
        Send an email and return the sent message ID.

        Args:
            to:              Recipient address or list of addresses.
            subject:         Subject line.
            body:            Plain-text body (always included).
            thread_id:       Attach to an existing Gmail thread.
            reply_to_rfc_id: RFC 2822 Message-ID for In-Reply-To / References headers.
            html_body:       Optional HTML alternative body.
        """
        recipients = [to] if isinstance(to, str) else to

        if html_body:
            mime: MIMEText | MIMEMultipart = MIMEMultipart("alternative")
            mime.attach(MIMEText(body, "plain", "utf-8"))
            mime.attach(MIMEText(html_body, "html", "utf-8"))
        else:
            mime = MIMEText(body, "plain", "utf-8")

        mime["to"] = ", ".join(recipients)
        mime["from"] = "me"
        mime["subject"] = subject
        if reply_to_rfc_id:
            mime["In-Reply-To"] = reply_to_rfc_id
            mime["References"] = reply_to_rfc_id

        raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
        body_dict: dict = {"raw": raw}
        if thread_id:
            body_dict["threadId"] = thread_id

        result = self._svc.users().messages().send(
            userId="me", body=body_dict
        ).execute()
        logger.info("Sent message %s to %s", result["id"], recipients)
        return result["id"]

    def create_draft(
        self,
        to: str | list[str],
        subject: str,
        body: str,
        thread_id: Optional[str] = None,
    ) -> str:
        """Create a Gmail draft (not sent). Returns the draft ID."""
        recipients = [to] if isinstance(to, str) else to
        mime = MIMEText(body, "plain", "utf-8")
        mime["to"] = ", ".join(recipients)
        mime["from"] = "me"
        mime["subject"] = subject

        raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
        msg_body: dict = {"raw": raw}
        if thread_id:
            msg_body["threadId"] = thread_id

        result = self._svc.users().drafts().create(
            userId="me", body={"message": msg_body}
        ).execute()
        logger.info("Created draft %s", result["id"])
        return result["id"]

    # ── Mutations ─────────────────────────────────────────────────────────────

    def mark_as_read(self, message_id: str) -> None:
        """Remove the UNREAD label from a message."""
        self._svc.users().messages().modify(
            userId="me",
            id=message_id,
            body={"removeLabelIds": ["UNREAD"]},
        ).execute()

    def mark_as_unread(self, message_id: str) -> None:
        """Add the UNREAD label to a message."""
        self._svc.users().messages().modify(
            userId="me",
            id=message_id,
            body={"addLabelIds": ["UNREAD"]},
        ).execute()

    def add_labels(self, message_id: str, label_ids: list[str]) -> None:
        """Add one or more label IDs to a message."""
        self._svc.users().messages().modify(
            userId="me",
            id=message_id,
            body={"addLabelIds": label_ids},
        ).execute()

    def remove_labels(self, message_id: str, label_ids: list[str]) -> None:
        """Remove one or more label IDs from a message."""
        self._svc.users().messages().modify(
            userId="me",
            id=message_id,
            body={"removeLabelIds": label_ids},
        ).execute()

    def archive(self, message_id: str) -> None:
        """Archive a message (remove from inbox, keep in All Mail)."""
        self.remove_labels(message_id, ["INBOX"])

    def trash_message(self, message_id: str) -> None:
        """Move a message to trash."""
        self._svc.users().messages().trash(
            userId="me", id=message_id
        ).execute()
