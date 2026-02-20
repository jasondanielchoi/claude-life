"""
DocsClient — typed, high-level wrapper around the Google Docs API v1.

Supports reading, creating, and editing Google Docs. Body text is extracted
recursively from paragraphs, tables, and nested structures.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from .google_factory import GoogleServiceFactory
from .models import GoogleDoc

logger = logging.getLogger(__name__)


def _extract_text(body: dict) -> str:
    """
    Recursively extract plain text from a Google Docs document body.

    Walks StructuralElement trees including paragraphs, tables, and
    table-of-contents blocks. Returns text with paragraph newlines preserved.
    """
    parts: list[str] = []

    for element in body.get("content", []):
        if "paragraph" in element:
            for pe in element["paragraph"].get("elements", []):
                if "textRun" in pe:
                    parts.append(pe["textRun"].get("content", ""))

        elif "table" in element:
            for row in element["table"].get("tableRows", []):
                for cell in row.get("tableCells", []):
                    # Each cell has its own 'content' list of StructuralElements
                    cell_text = _extract_text({"content": cell.get("content", [])})
                    if cell_text.strip():
                        parts.append(cell_text)

        elif "tableOfContents" in element:
            toc_text = _extract_text(
                {"content": element["tableOfContents"].get("content", [])}
            )
            if toc_text.strip():
                parts.append(toc_text)

    return "".join(parts)


class DocsClient:
    """
    High-level Google Docs operations.

    Usage:
        factory = GoogleServiceFactory()
        docs    = DocsClient(factory)

        doc = docs.get_document("doc_id")
        print(doc.body_text)
    """

    def __init__(self, factory: GoogleServiceFactory) -> None:
        self._svc = factory.docs

    # ── Read ──────────────────────────────────────────────────────────────────

    def get_document(self, doc_id: str) -> GoogleDoc:
        """Fetch a Google Doc and return a typed GoogleDoc with extracted text."""
        raw = self._svc.documents().get(documentId=doc_id).execute()
        return _parse_doc(raw)

    def read_text(self, doc_id: str) -> str:
        """Return only the plain text content of a document."""
        return self.get_document(doc_id).body_text

    # ── Create ────────────────────────────────────────────────────────────────

    def create_document(self, title: str) -> str:
        """Create a new blank Google Doc and return its document_id."""
        result = self._svc.documents().create(body={"title": title}).execute()
        doc_id = result["documentId"]
        logger.info("Created document %s: %s", doc_id, title)
        return doc_id

    # ── Edit ──────────────────────────────────────────────────────────────────

    def append_text(self, doc_id: str, text: str) -> None:
        """
        Append plain text at the end of a document.

        A newline is prepended so the appended text starts on a fresh line.
        """
        requests: list[dict] = [
            {
                "insertText": {
                    "location": {"index": 1},
                    "text": "\n" + text,
                }
            }
        ]
        # insertText at index 1 inserts at the beginning; we need end-of-doc index.
        # Fetch the end index first.
        raw = self._svc.documents().get(documentId=doc_id).execute()
        body_content = raw.get("body", {}).get("content", [])
        end_index = body_content[-1]["endIndex"] - 1 if body_content else 1

        requests = [
            {
                "insertText": {
                    "location": {"index": end_index},
                    "text": "\n" + text,
                }
            }
        ]
        self.batch_update(doc_id, requests)
        logger.info("Appended %d chars to doc %s", len(text), doc_id)

    def replace_text(self, doc_id: str, find: str, replace_with: str) -> None:
        """Find and replace all occurrences of a string in the document."""
        requests = [
            {
                "replaceAllText": {
                    "containsText": {"text": find, "matchCase": True},
                    "replaceText": replace_with,
                }
            }
        ]
        self.batch_update(doc_id, requests)
        logger.info("Replaced %r → %r in doc %s", find, replace_with, doc_id)

    def batch_update(self, doc_id: str, requests: list[dict]) -> dict:
        """
        Send a batchUpdate request directly to the Docs API.

        Use this for advanced operations not covered by the higher-level methods.
        Refer to: developers.google.com/docs/api/reference/rest/v1/documents/batchUpdate
        """
        result = self._svc.documents().batchUpdate(
            documentId=doc_id, body={"requests": requests}
        ).execute()
        return result


# ── Parser (module-level) ─────────────────────────────────────────────────────

def _parse_doc(raw: dict) -> GoogleDoc:
    body_text = _extract_text(raw.get("body", {}))
    return GoogleDoc(
        doc_id=raw["documentId"],
        title=raw.get("title", ""),
        body_text=body_text.strip(),
        revision_id=raw.get("revisionId", ""),
        url=f"https://docs.google.com/document/d/{raw['documentId']}/edit",
    )
