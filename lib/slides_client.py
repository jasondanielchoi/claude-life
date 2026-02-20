"""
SlidesClient — typed, high-level wrapper around the Google Slides API v1.

Supports reading presentations (with per-slide text extraction), creating
presentations, and adding slides. Use batch_update() for advanced formatting.
"""
from __future__ import annotations

import logging
from typing import Optional

from .google_factory import GoogleServiceFactory
from .models import Presentation, Slide

logger = logging.getLogger(__name__)


def _extract_slide_text(page: dict) -> str:
    """Extract all text from a single slide's page elements."""
    texts: list[str] = []
    for element in page.get("pageElements", []):
        shape = element.get("shape", {})
        text_content = shape.get("text", {})
        for te in text_content.get("textElements", []):
            run = te.get("textRun", {})
            content = run.get("content", "").strip()
            if content:
                texts.append(content)
    return " ".join(texts)


def _extract_notes_text(page: dict) -> str:
    """Extract speaker notes text from a slide."""
    notes_page = page.get("slideProperties", {}).get("notesPage", {})
    texts: list[str] = []
    for element in notes_page.get("pageElements", []):
        shape = element.get("shape", {})
        # Speaker notes are in the shape with placeholder type BODY
        ph = shape.get("placeholder", {})
        if ph.get("type") == "BODY":
            for te in shape.get("text", {}).get("textElements", []):
                content = te.get("textRun", {}).get("content", "").strip()
                if content:
                    texts.append(content)
    return " ".join(texts)


class SlidesClient:
    """
    High-level Google Slides operations.

    Usage:
        factory = GoogleServiceFactory()
        slides  = SlidesClient(factory)

        pres  = slides.get_presentation("presentation_id")
        texts = [s.text_content for s in pres.slides]
    """

    def __init__(self, factory: GoogleServiceFactory) -> None:
        self._svc = factory.slides

    # ── Read ──────────────────────────────────────────────────────────────────

    def get_presentation(self, presentation_id: str) -> Presentation:
        """Fetch a presentation and return a typed Presentation with slide text."""
        raw = self._svc.presentations().get(
            presentationId=presentation_id
        ).execute()
        return _parse_presentation(raw)

    def get_text_content(self, presentation_id: str) -> list[str]:
        """Return a list of text strings, one per slide (in order)."""
        pres = self.get_presentation(presentation_id)
        return [s.text_content for s in pres.slides]

    # ── Create ────────────────────────────────────────────────────────────────

    def create_presentation(self, title: str) -> str:
        """Create a new blank presentation and return its presentation_id."""
        result = self._svc.presentations().create(
            body={"title": title}
        ).execute()
        pid = result["presentationId"]
        logger.info("Created presentation %s: %s", pid, title)
        return pid

    # ── Edit ──────────────────────────────────────────────────────────────────

    def add_slide(
        self,
        presentation_id: str,
        layout: str = "BLANK",
        insertion_index: Optional[int] = None,
    ) -> str:
        """
        Append a new slide and return its slide_id.

        Args:
            layout:          Predefined layout name. Common values:
                             'BLANK', 'CAPTION_ONLY', 'TITLE', 'TITLE_AND_BODY',
                             'TITLE_AND_TWO_COLUMNS', 'BIG_NUMBER'
            insertion_index: 0-based position. None = append at end.
        """
        slide_spec: dict = {"slideLayoutReference": {"predefinedLayout": layout}}
        if insertion_index is not None:
            slide_spec["insertionIndex"] = insertion_index

        result = self.batch_update(
            presentation_id,
            [{"duplicateObject": None}, {"insertText": None}],  # placeholder
        )
        # Use the proper request
        result = self._svc.presentations().batchUpdate(
            presentationId=presentation_id,
            body={"requests": [{"insertSlide": slide_spec}]},
        ).execute()
        replies = result.get("replies", [{}])
        new_slide_id = replies[0].get("insertSlide", {}).get("objectId", "")
        logger.info("Added slide %s to presentation %s", new_slide_id, presentation_id)
        return new_slide_id

    def add_text_to_slide(
        self, presentation_id: str, slide_id: str, text: str, shape_id: str
    ) -> None:
        """Insert text into an existing shape on a slide."""
        requests = [
            {
                "insertText": {
                    "objectId": shape_id,
                    "text": text,
                    "insertionIndex": 0,
                }
            }
        ]
        self.batch_update(presentation_id, requests)

    def batch_update(self, presentation_id: str, requests: list[dict]) -> dict:
        """
        Send a batchUpdate request directly to the Slides API.

        Use for advanced operations (formatting, charts, image insertion, etc.).
        Refer to: developers.google.com/slides/api/reference/rest/v1/presentations/batchUpdate
        """
        return self._svc.presentations().batchUpdate(
            presentationId=presentation_id,
            body={"requests": requests},
        ).execute()


# ── Parser ────────────────────────────────────────────────────────────────────

def _parse_presentation(raw: dict) -> Presentation:
    pid = raw["presentationId"]
    slides: list[Slide] = []
    for i, page in enumerate(raw.get("slides", [])):
        slides.append(
            Slide(
                slide_id=page["objectId"],
                index=i,
                text_content=_extract_slide_text(page),
                notes=_extract_notes_text(page),
            )
        )
    return Presentation(
        presentation_id=pid,
        title=raw.get("title", ""),
        slides=slides,
        url=f"https://docs.google.com/presentation/d/{pid}/edit",
    )
