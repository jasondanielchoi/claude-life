"""
ContactsClient — typed, high-level wrapper around the Google People API v1.

Supports full-text search, email lookup, and listing all contacts.
Note: requires the 'contacts.readonly' OAuth scope.
"""
from __future__ import annotations

import logging
from typing import Optional

from .google_factory import GoogleServiceFactory
from .models import Contact

logger = logging.getLogger(__name__)

# Fields to request in every People API call
_PERSON_FIELDS = "names,emailAddresses,phoneNumbers,organizations"


class ContactsClient:
    """
    High-level Google Contacts (People API v1) operations.

    Usage:
        factory  = GoogleServiceFactory()
        contacts = ContactsClient(factory)

        results = contacts.search("Dennis")
        contact = contacts.get_by_email("someone@example.com")
    """

    def __init__(self, factory: GoogleServiceFactory) -> None:
        self._svc = factory.people

    # ── Search ────────────────────────────────────────────────────────────────

    def search(self, query: str, max_results: int = 10) -> list[Contact]:
        """
        Full-text search across contact names, email addresses, and phone numbers.

        Args:
            query:       Any search string (name fragment, email, etc.)
            max_results: Maximum contacts to return.
        """
        resp = self._svc.people().searchContacts(
            query=query,
            readMask=_PERSON_FIELDS,
            pageSize=max_results,
        ).execute()
        return [
            _parse_person(r["person"])
            for r in resp.get("results", [])
            if "person" in r
        ]

    def get_by_email(self, email: str) -> Optional[Contact]:
        """
        Return the first contact whose email address matches (case-insensitive).
        Returns None if no match is found.
        """
        results = self.search(email, max_results=10)
        email_lower = email.lower()
        for contact in results:
            if email_lower in [e.lower() for e in contact.emails]:
                return contact
        return None

    def get_by_name(self, name: str) -> list[Contact]:
        """Return contacts whose display name contains the given string."""
        results = self.search(name)
        name_lower = name.lower()
        return [c for c in results if name_lower in c.name.lower()]

    # ── List all ──────────────────────────────────────────────────────────────

    def list_all(self, max_results: int = 200) -> list[Contact]:
        """
        Return up to max_results contacts from the connected Google account.
        Sorted by the API's default (typically display name alphabetically).
        """
        resp = self._svc.people().connections().list(
            resourceName="people/me",
            pageSize=min(max_results, 1000),
            personFields=_PERSON_FIELDS,
        ).execute()
        return [_parse_person(p) for p in resp.get("connections", [])]


# ── Parser (module-level) ─────────────────────────────────────────────────────

def _parse_person(raw: dict) -> Contact:
    """Convert a raw People API person dict into a typed Contact."""
    names = raw.get("names", [])
    name = names[0].get("displayName", "") if names else ""

    emails = [e["value"] for e in raw.get("emailAddresses", []) if e.get("value")]
    phones = [p["value"] for p in raw.get("phoneNumbers", [])  if p.get("value")]

    orgs = raw.get("organizations", [])
    org  = orgs[0].get("name", "") if orgs else ""

    return Contact(
        resource_name=raw.get("resourceName", ""),
        name=name,
        emails=emails,
        phones=phones,
        organization=org,
    )
