"""
send_email.py — Send or reply to an email via GmailClient.

Body input (pick one — checked in this order):
    --body "short text"          inline string (good for one-liners)
    --body-file /path/to/file    read body from a file (good for long emails)
    stdin                        pipe or redirect body if neither flag is given

Usage:
    # New email, inline body
    ~/life/.venv/bin/python3 ~/life/scripts/send_email.py \\
        --to person@example.com \\
        --subject "Hello" \\
        --body "Hi there"

    # New email, long body from file
    ~/life/.venv/bin/python3 ~/life/scripts/send_email.py \\
        --to person@example.com \\
        --subject "Hello" \\
        --body-file /tmp/email_body.txt

    # Reply into an existing thread
    ~/life/.venv/bin/python3 ~/life/scripts/send_email.py \\
        --to person@example.com \\
        --subject "Re: Hello" \\
        --body "My reply" \\
        --thread-id abc123

    # Multiple recipients
    ~/life/.venv/bin/python3 ~/life/scripts/send_email.py \\
        --to a@example.com b@example.com \\
        --subject "Hello everyone" \\
        --body "Hi"

    # HTML email (plain-text fallback auto-generated as stripped version)
    ~/life/.venv/bin/python3 ~/life/scripts/send_email.py \\
        --to person@example.com \\
        --subject "Hello" \\
        --html-file /tmp/email.html

Output (JSON to stdout):
    {
        "message_id": "...",
        "to": ["..."],
        "subject": "...",
        "thread_id": "..."   // null if new thread
    }
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Optional

_LIFE = Path("~/life").expanduser()
sys.path.insert(0, str(_LIFE))

from lib.gmail_client import GmailClient
from lib.google_factory import GoogleServiceFactory


def _strip_html(html: str) -> str:
    """Minimal HTML → plain-text for the fallback plain part."""
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send or reply to a Gmail message."
    )
    parser.add_argument(
        "--to", nargs="+", required=True, metavar="ADDRESS",
        help="Recipient address(es)."
    )
    parser.add_argument(
        "--subject", required=True,
        help="Email subject line."
    )

    body_group = parser.add_mutually_exclusive_group()
    body_group.add_argument(
        "--body", metavar="TEXT",
        help="Plain-text body (inline)."
    )
    body_group.add_argument(
        "--body-file", metavar="PATH",
        help="Path to a file containing the plain-text body."
    )
    body_group.add_argument(
        "--html-file", metavar="PATH",
        help="Path to an HTML file. A plain-text fallback is auto-generated."
    )

    parser.add_argument(
        "--thread-id", metavar="ID", default=None,
        help="Gmail thread ID to reply into (omit for a new thread)."
    )
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    # ── Resolve body ──────────────────────────────────────────────────────────
    plain_body: Optional[str] = None
    html_body:  Optional[str] = None

    if args.body:
        plain_body = args.body
    elif args.body_file:
        plain_body = Path(args.body_file).read_text(encoding="utf-8")
    elif args.html_file:
        html_body  = Path(args.html_file).read_text(encoding="utf-8")
        plain_body = _strip_html(html_body)
    else:
        # Fall back to stdin
        if sys.stdin.isatty():
            print("Reading body from stdin (Ctrl-D to finish)…", file=sys.stderr)
        plain_body = sys.stdin.read()

    if not plain_body and not html_body:
        print("Error: email body is empty.", file=sys.stderr)
        sys.exit(1)

    # ── Send ──────────────────────────────────────────────────────────────────
    factory = GoogleServiceFactory()
    gmail   = GmailClient(factory)

    message_id = gmail.send_message(
        to=args.to,
        subject=args.subject,
        body=plain_body or "",
        thread_id=args.thread_id,
        html_body=html_body,
    )

    print(json.dumps({
        "message_id": message_id,
        "to":         args.to,
        "subject":    args.subject,
        "thread_id":  args.thread_id,
    }, indent=2))


if __name__ == "__main__":
    main()
