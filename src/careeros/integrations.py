"""Creed-system integration boundaries (interfaces, not implementations).

Career Intelligence owns career-domain state. It must NOT rebuild memory,
orchestration, or execution infrastructure. This module defines the narrow
adapter interfaces future integrations implement:

- **EmailAdapter**    - Gmail (authorized) for application correspondence
- **CalendarAdapter** - Google Calendar for interviews/deadlines
- **DriveAdapter**    - Google Drive for resumes/supporting documents

M1 ships only ``Null*`` implementations (safe no-ops) so the app runs with
zero external credentials. Real adapters arrive later behind these same
interfaces - call sites never change.

Separation of concerns (agreed boundaries):
- Career Intelligence -> career-domain state (this package)
- Creed Intelligence   -> durable cross-system memory/context
- Hermes               -> orchestration/scheduling
- Creed Agent Runtime   -> execution, checkpointing, process management
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol, runtime_checkable


@dataclass
class EmailMessage:
    to: str
    subject: str
    body: str
    thread_ref: Optional[str] = None  # e.g. gmail thread id
    sent_at: Optional[datetime] = None
    provenance: Optional[str] = None


@dataclass
class CalendarEvent:
    title: str
    start: datetime
    end: Optional[datetime] = None
    location: Optional[str] = None
    description: Optional[str] = None
    event_ref: Optional[str] = None  # provider event id
    provenance: Optional[str] = None


@dataclass
class DriveFile:
    name: str
    content: bytes
    mime_type: str = "text/markdown"
    file_ref: Optional[str] = None  # provider file id
    provenance: Optional[str] = None


@runtime_checkable
class EmailAdapter(Protocol):
    """Send/read recruiting correspondence (Gmail when authorized)."""

    def send(self, message: EmailMessage) -> EmailMessage: ...

    def search_threads(self, query: str, limit: int = 10) -> list[dict]: ...


@runtime_checkable
class CalendarAdapter(Protocol):
    """Create interview/deadline events (Google Calendar when authorized)."""

    def create_event(self, event: CalendarEvent) -> CalendarEvent: ...

    def list_upcoming(self, within_days: int = 14) -> list[CalendarEvent]: ...


@runtime_checkable
class DriveAdapter(Protocol):
    """Store resumes/supporting documents (Google Drive when authorized)."""

    def upload(self, file: DriveFile, folder: Optional[str] = None) -> DriveFile: ...

    def list_files(self, folder: Optional[str] = None) -> list[dict]: ...


# ---------------------------------------------------------------------------
# Null implementations (always available, never raise, record nothing)
# ---------------------------------------------------------------------------


@dataclass
class NullEmailAdapter:
    """No-op email adapter: marks messages as unsent instead of failing."""

    def send(self, message: EmailMessage) -> EmailMessage:
        message.sent_at = None
        message.provenance = "null-adapter (no email integration configured)"
        return message

    def search_threads(self, query: str, limit: int = 10) -> list[dict]:
        return []


@dataclass
class NullCalendarAdapter:
    """No-op calendar adapter: events are accepted and discarded."""

    def create_event(self, event: CalendarEvent) -> CalendarEvent:
        event.event_ref = None
        event.provenance = "null-adapter (no calendar integration configured)"
        return event

    def list_upcoming(self, within_days: int = 14) -> list[CalendarEvent]:
        return []


@dataclass
class NullDriveAdapter:
    """No-op drive adapter: uploads are accepted and discarded."""

    def upload(self, file: DriveFile, folder: Optional[str] = None) -> DriveFile:
        file.file_ref = None
        file.provenance = "null-adapter (no drive integration configured)"
        return file

    def list_files(self, folder: Optional[str] = None) -> list[dict]:
        return []
