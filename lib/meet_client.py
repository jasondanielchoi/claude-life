"""
MeetClient — typed wrapper around the Google Meet REST API v2.

Creates and manages Google Meet "spaces" — persistent meeting rooms with
stable URIs. A space can host multiple conferences over time; the meeting
link never changes once created.

Note: This API creates meeting spaces but does NOT control in-progress
meetings (muting, kicking participants, etc.) — that requires the Meet
Add-ons SDK, which is a separate product.

Required scopes:
    https://www.googleapis.com/auth/meetings.space.settings   (create/update)
    https://www.googleapis.com/auth/meetings.space.readonly   (read)
"""
from __future__ import annotations

import logging

from .google_factory import GoogleServiceFactory
from .models import MeetingSpace

logger = logging.getLogger(__name__)


class MeetClient:
    """
    High-level Google Meet space management.

    Usage:
        factory = GoogleServiceFactory()
        meet    = MeetClient(factory)

        space = meet.create_space()
        print(space.meeting_uri)   # https://meet.google.com/abc-defg-hij
    """

    def __init__(self, factory: GoogleServiceFactory) -> None:
        self._svc = factory.meet

    # ── Spaces ────────────────────────────────────────────────────────────────

    def create_space(self) -> MeetingSpace:
        """
        Create a new Meet space and return its details.

        The space has a persistent URI — it can be reused for recurring meetings
        without creating a new link each time.
        """
        raw = self._svc.spaces().create(body={}).execute()
        space = _parse_space(raw)
        logger.info("Created Meet space %s: %s", space.space_id, space.meeting_uri)
        return space

    def get_space(self, space_name: str) -> MeetingSpace:
        """
        Fetch an existing Meet space by resource name.

        Args:
            space_name: Resource name (e.g. 'spaces/jEsU8RZgCRo') or
                        meeting code (e.g. 'abc-defg-hij').
        """
        raw = self._svc.spaces().get(name=space_name).execute()
        return _parse_space(raw)

    def end_active_conference(self, space_name: str) -> None:
        """
        End the currently active conference in a space.

        This kicks all participants and ends the call. The space itself
        (and its meeting link) persists and can be used again.
        """
        self._svc.spaces().endActiveConference(
            name=space_name, body={}
        ).execute()
        logger.info("Ended active conference in space %s", space_name)


# ── Parser ────────────────────────────────────────────────────────────────────

def _parse_space(raw: dict) -> MeetingSpace:
    return MeetingSpace(
        name=raw.get("name", ""),
        meeting_uri=raw.get("meetingUri", ""),
        meeting_code=raw.get("meetingCode", ""),
    )
