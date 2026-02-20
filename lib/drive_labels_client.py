"""
DriveLabelsClient — typed wrapper around the Drive Labels API v2.

Drive Labels are metadata schemas that can be applied to files in Google Drive
(e.g. "Project", "Status", "Confidentiality"). Each label has typed fields
(text, integer, date, selection, user).

Applying a label to a file is done through the Drive API (files.modifyLabels),
not the Labels API itself. DriveLabelsClient handles label discovery; label
application is wired through DriveClient.apply_label() for ergonomics.

Requires:  https://www.googleapis.com/auth/drive.labels  (for label metadata)
           https://www.googleapis.com/auth/drive          (for applying to files)
"""
from __future__ import annotations

import logging
from typing import Optional

from .google_factory import GoogleServiceFactory
from .models import DriveLabel, LabelField

logger = logging.getLogger(__name__)


class DriveLabelsClient:
    """
    High-level Drive Labels read operations.

    Usage:
        factory = GoogleServiceFactory()
        labels  = DriveLabelsClient(factory)

        all_labels = labels.list_labels()
        label      = labels.get_label("labels/abc123")
    """

    def __init__(self, factory: GoogleServiceFactory) -> None:
        self._labels_svc = factory.drive_labels
        self._drive_svc  = factory.drive

    # ── List / get labels ─────────────────────────────────────────────────────

    def list_labels(
        self,
        published_only: bool = True,
        max_results: int = 50,
        language_code: str = "en",
    ) -> list[DriveLabel]:
        """
        List Drive Labels visible to the current user.

        Args:
            published_only:  If True, only return published (active) labels.
            max_results:     Page size cap.
            language_code:   BCP-47 language code for display names.
        """
        kwargs: dict = {
            "pageSize": max_results,
            "languageCode": language_code,
            "view": "LABEL_VIEW_FULL",
        }
        if published_only:
            kwargs["publishedOnly"] = True

        resp = self._labels_svc.labels().list(**kwargs).execute()
        return [_parse_label(lbl) for lbl in resp.get("labels", [])]

    def get_label(self, name: str, language_code: str = "en") -> DriveLabel:
        """
        Fetch a single label by resource name (e.g. 'labels/abc123').

        The name can also include a revision: 'labels/abc123@latest'.
        """
        raw = self._labels_svc.labels().get(
            name=name,
            view="LABEL_VIEW_FULL",
            languageCode=language_code,
        ).execute()
        return _parse_label(raw)

    def find_label_by_title(self, title: str) -> Optional[DriveLabel]:
        """Return the first label whose title matches (case-insensitive)."""
        title_lower = title.lower()
        for label in self.list_labels():
            if label.title.lower() == title_lower:
                return label
        return None

    # ── Apply labels to Drive files ───────────────────────────────────────────

    def apply_label(
        self,
        file_id: str,
        label_id: str,
        field_values: Optional[dict[str, str]] = None,
    ) -> None:
        """
        Apply a label (with optional field values) to a Drive file.

        This uses the Drive v3 files.modifyLabels endpoint, not the Labels API.

        Args:
            file_id:       Drive file ID.
            label_id:      Label resource name or ID (e.g. 'labels/abc123').
            field_values:  Dict of {field_id: value_str} to set on the label.
                           Pass None to apply the label without setting fields.
        """
        label_modification: dict = {"labelId": label_id.split("/")[-1]}

        if field_values:
            modifications = []
            for field_id, value in field_values.items():
                modifications.append({
                    "fieldId": field_id,
                    "setTextValues": {"values": [value]},
                })
            label_modification["fieldModifications"] = modifications

        self._drive_svc.files().modifyLabels(
            fileId=file_id,
            body={"labelModifications": [label_modification]},
        ).execute()
        logger.info("Applied label %s to file %s", label_id, file_id)

    def remove_label(self, file_id: str, label_id: str) -> None:
        """Remove a label from a Drive file."""
        self._drive_svc.files().modifyLabels(
            fileId=file_id,
            body={
                "labelModifications": [{
                    "labelId": label_id.split("/")[-1],
                    "removeLabel": True,
                }]
            },
        ).execute()
        logger.info("Removed label %s from file %s", label_id, file_id)

    def get_file_labels(self, file_id: str) -> list[dict]:
        """
        Return the raw label data currently applied to a Drive file.
        Returns a list of label dicts as returned by the Drive API.
        """
        raw = self._drive_svc.files().get(
            fileId=file_id,
            fields="labelInfo",
            includeLabels="*",
        ).execute()
        return raw.get("labelInfo", {}).get("labels", [])


# ── Parsers ───────────────────────────────────────────────────────────────────

def _parse_label(raw: dict) -> DriveLabel:
    fields: list[LabelField] = []
    for f in raw.get("fields", []):
        props = f.get("properties", {})
        # Determine field type from which sub-key is present
        field_type = next(
            (k for k in ("textOptions", "integerOptions", "dateOptions",
                         "selectionOptions", "userOptions")
             if k in f),
            "unknown",
        )
        fields.append(
            LabelField(
                field_id=f.get("id", ""),
                display_name=props.get("displayName", ""),
                field_type=field_type,
            )
        )

    props = raw.get("properties", {})
    return DriveLabel(
        label_id=raw.get("id", ""),
        name=raw.get("name", ""),
        title=props.get("title", ""),
        description=props.get("description", ""),
        label_type=raw.get("labelType", ""),
        fields=fields,
        is_published=raw.get("publishedLabelInfo") is not None,
    )
