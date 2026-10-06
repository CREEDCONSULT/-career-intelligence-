"""Google Drive read-only metadata connector (M2.1) — career artifact discovery.

Implements the existing ``DriveAdapter`` protocol with real Google API calls
when authorized. Falls back to the null adapter when not.

Hard constraints:
- READ-ONLY METADATA: uses drive.metadata.readonly scope — can list file
  names, types, and folders but CANNOT read content.
- NO MUTATION: ``upload()`` raises ``PermissionError``.
- EXPLICIT RELEVANCE: only files whose names match known career-artifact
  patterns are returned. Not every Drive file becomes career evidence.
- PROVENANCE: every discovered file records ``gdrive:file/<id>``.
"""

from __future__ import annotations

import re
from typing import Optional

from careeros.google_oauth import (
    ConnectorHealth,
    SCOPE_DRIVE_METADATA_READONLY,
    load_tokens,
)

# Career-artifact filename patterns (deterministic, never guessed)
_ARTIFACT_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("resume", re.compile(r"resume|cv\b", re.I)),
    ("cover_letter", re.compile(r"cover[-_ ]letter", re.I)),
    ("certificate", re.compile(r"certificat|credential|diploma|degree", re.I)),
    ("portfolio", re.compile(r"portfolio|case[-_ ]study|project[-_ ]report", re.I)),
    (
        "employment_evidence",
        re.compile(r"employment|reference|recommendation|performance[-_ ]review", re.I),
    ),
]

# MimeTypes that are safe to reference (no executable content)
_SAFE_MIME_TYPES = {
    "application/pdf",
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.presentation",
    "application/vnd.google-apps.spreadsheet",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/markdown",
    "image/png",
    "image/jpeg",
}


class DiscoveredFile:
    """A Drive file discovered by the connector (metadata only, no content)."""

    def __init__(
        self, file_id: str, name: str, mime_type: str, modified_time: Optional[str] = None
    ):
        self.file_id = file_id
        self.name = name
        self.mime_type = mime_type
        self.modified_time = modified_time
        self.source_ref = f"gdrive:file/{file_id}"
        self.provenance = "google-drive:metadata.readonly"
        self.artifact_type: Optional[str] = None
        self.relevant: bool = False

    def to_dict(self) -> dict:
        return {
            "file_id": self.file_id,
            "name": self.name,
            "mime_type": self.mime_type,
            "modified_time": self.modified_time,
            "source_ref": self.source_ref,
            "provenance": self.provenance,
            "artifact_type": self.artifact_type,
            "relevant": self.relevant,
        }


class DriveConnector:
    """Real Drive read-only metadata adapter (implements DriveAdapter protocol)."""

    def __init__(self):
        self._last_error: Optional[str] = None

    # -- health ------------------------------------------------------------------
    def health(self) -> ConnectorHealth:
        tokens = load_tokens()
        return ConnectorHealth(
            connector="drive",
            configured=tokens is not None,
            authorized=tokens is not None
            and tokens.valid
            and SCOPE_DRIVE_METADATA_READONLY in (tokens.scopes or []),
            last_error=self._last_error,
            scopes=[SCOPE_DRIVE_METADATA_READONLY],
        )

    # -- protocol: DriveAdapter (read-only enforcement) --------------------------
    def upload(self, file, folder: Optional[str] = None) -> None:
        """HARD BLOCK: this connector is read-only. No file mutation."""
        raise PermissionError(
            "DriveConnector is READ-ONLY (metadata only). Uploading files "
            "is explicitly prohibited by the M2.1 design. Use Drive directly."
        )

    def list_files(self, folder: Optional[str] = None) -> list[dict]:
        """List Drive files (metadata only). Falls back to empty list offline."""
        service = self._service()
        if service is None:
            return []
        try:
            # List files visible to the user (no content read)
            results = (
                service.files()
                .list(
                    pageSize=100,
                    fields="files(id,name,mimeType,modifiedTime)",
                    q="trashed=false",
                )
                .execute()
            )
            files = results.get("files", [])
            out = []
            for f in files:
                out.append(
                    {
                        "file_id": f.get("id"),
                        "name": f.get("name", ""),
                        "mime_type": f.get("mimeType", ""),
                        "modified_time": f.get("modifiedTime"),
                    }
                )
            return out
        except Exception as e:  # noqa: BLE001
            self._last_error = f"{type(e).__name__}: {e}"
            return []

    # -- career artifact discovery --------------------------------------------------
    def discover_career_artifacts(self) -> list[DiscoveredFile]:
        """Find files whose names suggest career-evidence relevance.

        Deterministic: only files matching known artifact patterns AND
        having a safe mime-type are returned as relevant. Everything else
        is returned as relevant=False (not silently treated as evidence).
        """
        raw_files = self.list_files()
        out = []
        for raw in raw_files:
            df = DiscoveredFile(
                file_id=raw.get("file_id", ""),
                name=raw.get("name", ""),
                mime_type=raw.get("mime_type", ""),
                modified_time=raw.get("modified_time"),
            )
            # Classify by filename pattern
            for artifact_type, pattern in _ARTIFACT_PATTERNS:
                if pattern.search(df.name):
                    df.artifact_type = artifact_type
                    break
            # Relevance requires BOTH a pattern match AND a safe mime type
            df.relevant = df.artifact_type is not None and df.mime_type in _SAFE_MIME_TYPES
            out.append(df)
        return out

    # -- internal ------------------------------------------------------------------
    def _service(self):
        """Return an authorized Drive API service, or None if offline."""
        creds = load_tokens()
        if creds is None or not creds.valid:
            return None
        if SCOPE_DRIVE_METADATA_READONLY not in (creds.scopes or []):
            self._last_error = "Drive scope not granted"
            return None
        try:
            from googleapiclient.discovery import build

            return build("drive", "v3", credentials=creds)
        except Exception as e:  # noqa: BLE001
            self._last_error = f"{type(e).__name__}"
            return None
