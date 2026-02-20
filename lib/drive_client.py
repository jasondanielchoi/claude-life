"""
DriveClient — typed, high-level wrapper around the Google Drive API v3 service.

Covers listing/searching, folder creation, file upload/download,
and sharing (anyone-with-link or specific user).
"""
from __future__ import annotations

import logging
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

from .google_factory import GoogleServiceFactory
from .models import DriveFile

logger = logging.getLogger(__name__)

_FIELDS = "id,name,mimeType,createdTime,modifiedTime,webViewLink,size"


class DriveClient:
    """
    High-level Google Drive file and folder operations.

    Usage:
        factory = GoogleServiceFactory()
        drive   = DriveClient(factory)

        folder_id = drive.create_folder("Life Ops")
        file_id   = drive.upload_file(Path("report.pdf"), folder_id=folder_id)
        drive.share_with_anyone(file_id)
    """

    def __init__(self, factory: GoogleServiceFactory) -> None:
        self._svc = factory.drive

    # ── List / search ─────────────────────────────────────────────────────────

    def list_files(
        self,
        query: str = "",
        max_results: int = 20,
        order_by: str = "modifiedTime desc",
    ) -> list[DriveFile]:
        """
        List files in Drive.

        Args:
            query:       Drive search string. Examples:
                             "name contains 'budget'"
                             "mimeType='application/pdf'"
                             "trashed=false and '1ABC' in parents"
            max_results: Maximum number of files to return (API max: 1000).
            order_by:    Sort order. Common options: "name", "modifiedTime desc".
        """
        kwargs: dict = dict(
            pageSize=max_results,
            orderBy=order_by,
            fields=f"files({_FIELDS})",
        )
        if query:
            kwargs["q"] = query

        resp = self._svc.files().list(**kwargs).execute()
        return [_parse_file(f) for f in resp.get("files", [])]

    def get_file(self, file_id: str) -> DriveFile:
        """Fetch metadata for a single Drive file by ID."""
        raw = self._svc.files().get(fileId=file_id, fields=_FIELDS).execute()
        return _parse_file(raw)

    def find_folder(self, name: str) -> Optional[DriveFile]:
        """Return the first Drive folder matching name exactly, or None."""
        q = (
            f"mimeType='application/vnd.google-apps.folder' "
            f"and name='{name}' and trashed=false"
        )
        results = self.list_files(query=q, max_results=5)
        return results[0] if results else None

    # ── Create folders ────────────────────────────────────────────────────────

    def create_folder(
        self, name: str, parent_id: Optional[str] = None
    ) -> str:
        """Create a Drive folder and return its file_id."""
        body: dict = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        if parent_id:
            body["parents"] = [parent_id]

        folder = self._svc.files().create(body=body, fields="id").execute()
        logger.info("Created folder %s: %s", folder["id"], name)
        return folder["id"]

    def get_or_create_folder(self, name: str, parent_id: Optional[str] = None) -> str:
        """Return an existing folder's ID or create it if not found."""
        existing = self.find_folder(name)
        if existing:
            logger.debug("Folder already exists: %s (%s)", name, existing.file_id)
            return existing.file_id
        return self.create_folder(name, parent_id=parent_id)

    # ── Upload ────────────────────────────────────────────────────────────────

    def upload_file(
        self,
        local_path: Path | str,
        folder_id: Optional[str] = None,
        mime_type: Optional[str] = None,
        resumable: bool = True,
    ) -> str:
        """
        Upload a local file to Drive and return the Drive file_id.

        Args:
            local_path: Path to the file on disk.
            folder_id:  Drive folder to place the file in.
            mime_type:  MIME type override (auto-detected from extension if None).
            resumable:  Use resumable upload (recommended for files > 5 MB).
        """
        local_path = Path(local_path)
        if not local_path.exists():
            raise FileNotFoundError(f"File not found: {local_path}")

        detected, _ = mimetypes.guess_type(str(local_path))
        effective_mime = mime_type or detected or "application/octet-stream"

        metadata: dict = {"name": local_path.name}
        if folder_id:
            metadata["parents"] = [folder_id]

        media = MediaFileUpload(str(local_path), mimetype=effective_mime, resumable=resumable)
        file = self._svc.files().create(
            body=metadata, media_body=media, fields="id,name"
        ).execute()
        logger.info("Uploaded %s → Drive file %s", local_path.name, file["id"])
        return file["id"]

    # ── Download ──────────────────────────────────────────────────────────────

    def download_file(self, file_id: str, dest_path: Path | str) -> None:
        """Download a Drive file (binary content) to a local path."""
        dest_path = Path(dest_path)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        request = self._svc.files().get_media(fileId=file_id)
        import io
        fh = io.FileIO(str(dest_path), "wb")
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        logger.info("Downloaded Drive file %s → %s", file_id, dest_path)

    def export_google_doc(
        self, file_id: str, dest_path: Path | str, mime_type: str = "text/plain"
    ) -> None:
        """
        Export a Google Doc/Sheet/Slide to a local file.

        Common mime_type values:
            "text/plain"       → .txt
            "application/pdf"  → .pdf
            "text/csv"         → .csv (Sheets only)
        """
        dest_path = Path(dest_path)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        request = self._svc.files().export_media(fileId=file_id, mimeType=mime_type)
        dest_path.write_bytes(request.execute())
        logger.info("Exported Drive file %s → %s (%s)", file_id, dest_path, mime_type)

    # ── Sharing ───────────────────────────────────────────────────────────────

    def share_with_anyone(self, file_id: str, role: str = "reader") -> None:
        """Make a file accessible to anyone with the link."""
        self._svc.permissions().create(
            fileId=file_id,
            body={"type": "anyone", "role": role},
        ).execute()
        logger.info("Shared %s publicly (role=%s)", file_id, role)

    def share_with_user(
        self, file_id: str, email: str, role: str = "writer"
    ) -> None:
        """Grant a specific user access by email."""
        self._svc.permissions().create(
            fileId=file_id,
            body={"type": "user", "role": role, "emailAddress": email},
        ).execute()
        logger.info("Shared %s with %s (role=%s)", file_id, email, role)

    def get_web_link(self, file_id: str) -> str:
        """Return the shareable web view URL for a Drive file."""
        return f"https://drive.google.com/file/d/{file_id}/view"

    # ── Delete ────────────────────────────────────────────────────────────────

    def trash_file(self, file_id: str) -> None:
        """Move a file to trash (recoverable)."""
        self._svc.files().update(
            fileId=file_id, body={"trashed": True}
        ).execute()
        logger.info("Trashed Drive file %s", file_id)

    def delete_file(self, file_id: str) -> None:
        """Permanently delete a file. Irreversible — use with caution."""
        self._svc.files().delete(fileId=file_id).execute()
        logger.info("Permanently deleted Drive file %s", file_id)


# ── File parser (module-level) ────────────────────────────────────────────────

def _parse_file(raw: dict) -> DriveFile:
    def _dt(s: str) -> datetime:
        return (
            datetime.fromisoformat(s.replace("Z", "+00:00"))
            if s
            else datetime.now(timezone.utc)
        )

    return DriveFile(
        file_id=raw["id"],
        name=raw.get("name", ""),
        mime_type=raw.get("mimeType", ""),
        created_time=_dt(raw.get("createdTime", "")),
        modified_time=_dt(raw.get("modifiedTime", "")),
        web_view_link=raw.get("webViewLink", ""),
        size_bytes=int(raw["size"]) if raw.get("size") else None,
    )
