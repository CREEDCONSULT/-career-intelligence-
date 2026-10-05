"""Application state machine + stores (deterministic, append-only history).

Rules:
- Transitions are EXPLICIT: anything not in the table raises ``InvalidTransition``.
- Every transition appends an immutable event row (timestamp, previous state,
  new state, trigger, notes, artifacts, provenance) - history is never
  overwritten.
- Terminal states (REJECTED / WITHDRAWN / CLOSED) accept no further transitions.
- ``applications.current_state`` is a materialized view of the latest event.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

import duckdb


class ApplicationState(str, Enum):
    DISCOVERED = "DISCOVERED"
    REVIEWED = "REVIEWED"
    SHORTLISTED = "SHORTLISTED"
    PREPARING = "PREPARING"
    READY_TO_APPLY = "READY_TO_APPLY"
    APPLIED = "APPLIED"
    SCREENING = "SCREENING"
    INTERVIEW = "INTERVIEW"
    ASSESSMENT = "ASSESSMENT"
    OFFER = "OFFER"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"
    CLOSED = "CLOSED"


#: Explicit transition table. Terminal states map to an empty set.
TRANSITIONS: dict[ApplicationState, set[ApplicationState]] = {
    ApplicationState.DISCOVERED: {
        ApplicationState.REVIEWED,
        ApplicationState.WITHDRAWN,
        ApplicationState.CLOSED,
    },
    ApplicationState.REVIEWED: {
        ApplicationState.SHORTLISTED,
        ApplicationState.WITHDRAWN,
        ApplicationState.CLOSED,
    },
    ApplicationState.SHORTLISTED: {
        ApplicationState.PREPARING,
        ApplicationState.WITHDRAWN,
        ApplicationState.CLOSED,
    },
    ApplicationState.PREPARING: {
        ApplicationState.READY_TO_APPLY,
        ApplicationState.SHORTLISTED,  # loop back if prep stalls
        ApplicationState.WITHDRAWN,
        ApplicationState.CLOSED,
    },
    ApplicationState.READY_TO_APPLY: {
        ApplicationState.APPLIED,
        ApplicationState.SHORTLISTED,
        ApplicationState.WITHDRAWN,
        ApplicationState.CLOSED,
    },
    ApplicationState.APPLIED: {
        ApplicationState.SCREENING,
        ApplicationState.REJECTED,
        ApplicationState.WITHDRAWN,
        ApplicationState.CLOSED,
    },
    ApplicationState.SCREENING: {
        ApplicationState.INTERVIEW,
        ApplicationState.ASSESSMENT,
        ApplicationState.REJECTED,
        ApplicationState.WITHDRAWN,
        ApplicationState.CLOSED,
    },
    ApplicationState.INTERVIEW: {
        ApplicationState.ASSESSMENT,
        ApplicationState.OFFER,
        ApplicationState.REJECTED,
        ApplicationState.WITHDRAWN,
        ApplicationState.CLOSED,
    },
    ApplicationState.ASSESSMENT: {
        ApplicationState.INTERVIEW,
        ApplicationState.OFFER,
        ApplicationState.REJECTED,
        ApplicationState.WITHDRAWN,
        ApplicationState.CLOSED,
    },
    ApplicationState.OFFER: {
        ApplicationState.CLOSED,  # accepted -> close as filled
        ApplicationState.WITHDRAWN,  # declined
    },
    ApplicationState.REJECTED: set(),
    ApplicationState.WITHDRAWN: set(),
    ApplicationState.CLOSED: set(),
}

TERMINAL_STATES = {s for s, nxt in TRANSITIONS.items() if not nxt}
ACTIVE_STATES = [s for s in ApplicationState if s not in TERMINAL_STATES]


class InvalidTransition(ValueError):
    """Raised when a transition is not allowed by the explicit table."""


@dataclass
class ApplicationEvent:
    event_id: int
    application_id: int
    timestamp: datetime
    previous_state: Optional[str]  # None only for the creation event
    new_state: str
    trigger: str  # "user:<label>" | "auto:<label>" | "import"
    notes: Optional[str] = None
    artifacts: list[dict] = field(default_factory=list)  # [{"kind": ..., "ref": ...}]
    provenance: Optional[str] = None


@dataclass
class Application:
    application_id: int
    opportunity_id: int
    current_state: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS applications (
    application_id INTEGER PRIMARY KEY,
    opportunity_id INTEGER NOT NULL,
    current_state VARCHAR NOT NULL,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS application_events (
    event_id INTEGER PRIMARY KEY,
    application_id INTEGER NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    previous_state VARCHAR,
    new_state VARCHAR NOT NULL,
    trigger VARCHAR NOT NULL,
    notes VARCHAR,
    artifacts VARCHAR,
    provenance VARCHAR
);
CREATE TABLE IF NOT EXISTS application_documents (
    document_id INTEGER PRIMARY KEY,
    application_id INTEGER NOT NULL,
    doc_type VARCHAR NOT NULL,
    version INTEGER NOT NULL,
    content VARCHAR,
    job_keywords VARCHAR,
    evidence_used VARCHAR,
    excluded_claims VARCHAR,
    created_at TIMESTAMP
);
"""


# ---------------------------------------------------------------------------
# Application store
# ---------------------------------------------------------------------------


class ApplicationStore:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)

    def _connect(self):
        conn = duckdb.connect(self.db_path)
        conn.execute(_SCHEMA)
        return conn

    # -- lifecycle -----------------------------------------------------------
    def create_for_opportunity(
        self,
        opportunity_id: int,
        trigger: str = "user:create",
        notes: Optional[str] = None,
        provenance: Optional[str] = None,
    ) -> Application:
        """Create an application (state DISCOVERED) + its creation event."""
        conn = self._connect()
        try:
            existing = conn.execute(
                "SELECT application_id FROM applications WHERE opportunity_id = ?", [opportunity_id]
            ).fetchone()
            if existing:
                raise ValueError(
                    f"application already exists for opportunity {opportunity_id} "
                    f"(application_id={existing[0]})"
                )
            app_id = conn.execute(
                "SELECT COALESCE(MAX(application_id), 0) + 1 FROM applications"
            ).fetchone()[0]
            now = datetime.now()
            conn.execute(
                "INSERT INTO applications VALUES (?, ?, ?, ?, ?)",
                [
                    app_id,
                    opportunity_id,
                    ApplicationState.DISCOVERED.value,
                    now.isoformat(sep=" "),
                    now.isoformat(sep=" "),
                ],
            )
            conn.execute(
                "INSERT INTO application_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    conn.execute(
                        "SELECT COALESCE(MAX(event_id), 0) + 1 FROM application_events"
                    ).fetchone()[0],
                    app_id,
                    now.isoformat(sep=" "),
                    None,
                    ApplicationState.DISCOVERED.value,
                    trigger,
                    notes,
                    json.dumps([]),
                    provenance,
                ],
            )
        finally:
            conn.close()
        return self.get_by_opportunity(opportunity_id)  # type: ignore[return-value]

    def transition(
        self,
        application_id: int,
        new_state: ApplicationState | str,
        trigger: str,
        notes: Optional[str] = None,
        artifacts: Optional[list[dict]] = None,
        provenance: Optional[str] = None,
    ) -> Application:
        """Apply an explicit transition. Raises InvalidTransition when disallowed."""
        if isinstance(new_state, str):
            try:
                new_state = ApplicationState(new_state.upper())
            except ValueError:
                raise InvalidTransition(f"unknown state: {new_state!r}") from None
        app = self.get(application_id)
        if app is None:
            raise ValueError(f"no application {application_id}")
        current = ApplicationState(app.current_state.upper())
        if new_state not in TRANSITIONS[current]:
            raise InvalidTransition(
                f"cannot transition {current.value} -> {new_state.value}; allowed: "
                f"{sorted(s.value for s in TRANSITIONS[current]) or ['<terminal>']}"
            )
        conn = self._connect()
        try:
            now = datetime.now()
            conn.execute(
                "INSERT INTO application_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    conn.execute(
                        "SELECT COALESCE(MAX(event_id), 0) + 1 FROM application_events"
                    ).fetchone()[0],
                    application_id,
                    now.isoformat(sep=" "),
                    current.value,
                    new_state.value,
                    trigger,
                    notes,
                    json.dumps(artifacts or []),
                    provenance,
                ],
            )
            conn.execute(
                "UPDATE applications SET current_state = ?, updated_at = ? WHERE application_id = ?",
                [new_state.value, now.isoformat(sep=" "), application_id],
            )
        finally:
            conn.close()
        return self.get(application_id)  # type: ignore[return-value]

    # -- reads -----------------------------------------------------------------
    def get(self, application_id: int) -> Optional[Application]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT application_id, opportunity_id, current_state, created_at, updated_at "
                "FROM applications WHERE application_id = ?",
                [application_id],
            ).fetchone()
            return Application(*row) if row else None
        finally:
            conn.close()

    def get_by_opportunity(self, opportunity_id: int) -> Optional[Application]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT application_id, opportunity_id, current_state, created_at, updated_at "
                "FROM applications WHERE opportunity_id = ?",
                [opportunity_id],
            ).fetchone()
            return Application(*row) if row else None
        finally:
            conn.close()

    def list_all(self, active_only: bool = False) -> list[Application]:
        conn = self._connect()
        try:
            if active_only:
                marks = ", ".join("?" * len(ACTIVE_STATES))
                rows = conn.execute(
                    f"SELECT application_id, opportunity_id, current_state, created_at, updated_at "
                    f"FROM applications WHERE current_state IN ({marks}) "
                    f"ORDER BY application_id",
                    [s.value for s in ACTIVE_STATES],
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT application_id, opportunity_id, current_state, created_at, updated_at "
                    "FROM applications ORDER BY application_id"
                ).fetchall()
            return [Application(*r) for r in rows]
        finally:
            conn.close()

    def events(self, application_id: int) -> list[ApplicationEvent]:
        """Immutable history, oldest first."""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT event_id, application_id, timestamp, previous_state, new_state, "
                "trigger, notes, artifacts, provenance "
                "FROM application_events WHERE application_id = ? ORDER BY event_id",
                [application_id],
            ).fetchall()
            return [
                ApplicationEvent(
                    event_id=r[0],
                    application_id=r[1],
                    timestamp=r[2],
                    previous_state=r[3],
                    new_state=r[4],
                    trigger=r[5],
                    notes=r[6],
                    artifacts=json.loads(r[7] or "[]"),
                    provenance=r[8],
                )
                for r in rows
            ]
        finally:
            conn.close()

    def last_transition_date(
        self, application_id: int, to_state: Optional[str] = None
    ) -> Optional[datetime]:
        """Most recent event (optionally into a specific state) - drives follow-ups."""
        conn = self._connect()
        try:
            if to_state:
                row = conn.execute(
                    "SELECT MAX(timestamp) FROM application_events "
                    "WHERE application_id = ? AND new_state = ?",
                    [application_id, to_state],
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT MAX(timestamp) FROM application_events WHERE application_id = ?",
                    [application_id],
                ).fetchone()
            return row[0] if row and row[0] else None
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Document store (resume / cover-letter artifacts with evidence traceability)
# ---------------------------------------------------------------------------

DOC_TYPES = ("base_resume", "tailored_resume", "cover_letter", "keywords", "evidence_map")


@dataclass
class ApplicationDocument:
    document_id: int
    application_id: int
    doc_type: str
    version: int
    content: Optional[str]
    job_keywords: list[str]
    evidence_used: list[int]
    excluded_claims: list[str]
    created_at: Optional[datetime]


class DocumentStore:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)

    def _connect(self):
        conn = duckdb.connect(self.db_path)
        conn.execute(_SCHEMA)
        return conn

    def save(
        self,
        application_id: int,
        doc_type: str,
        content: Optional[str],
        job_keywords: Optional[list[str]] = None,
        evidence_used: Optional[list[int]] = None,
        excluded_claims: Optional[list[str]] = None,
    ) -> ApplicationDocument:
        """Append a new version of a document (versions never overwrite)."""
        if doc_type not in DOC_TYPES:
            raise ValueError(f"unknown doc_type: {doc_type!r}")
        conn = self._connect()
        try:
            version = conn.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 FROM application_documents "
                "WHERE application_id = ? AND doc_type = ?",
                [application_id, doc_type],
            ).fetchone()[0]
            doc_id = conn.execute(
                "SELECT COALESCE(MAX(document_id), 0) + 1 FROM application_documents"
            ).fetchone()[0]
            now = datetime.now().isoformat(sep=" ")
            conn.execute(
                "INSERT INTO application_documents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    doc_id,
                    application_id,
                    doc_type,
                    version,
                    content,
                    json.dumps(job_keywords or []),
                    json.dumps(evidence_used or []),
                    json.dumps(excluded_claims or []),
                    now,
                ],
            )
        finally:
            conn.close()
        return self.latest(application_id, doc_type)  # type: ignore[return-value]

    def latest(self, application_id: int, doc_type: str) -> Optional[ApplicationDocument]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT document_id, application_id, doc_type, version, content, "
                "job_keywords, evidence_used, excluded_claims, created_at "
                "FROM application_documents WHERE application_id = ? AND doc_type = ? "
                "ORDER BY version DESC LIMIT 1",
                [application_id, doc_type],
            ).fetchone()
            if not row:
                return None
            return ApplicationDocument(
                document_id=row[0],
                application_id=row[1],
                doc_type=row[2],
                version=row[3],
                content=row[4],
                job_keywords=json.loads(row[5] or "[]"),
                evidence_used=json.loads(row[6] or "[]"),
                excluded_claims=json.loads(row[7] or "[]"),
                created_at=row[8],
            )
        finally:
            conn.close()

    def list_versions(self, application_id: int, doc_type: str) -> list[ApplicationDocument]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT document_id, application_id, doc_type, version, content, "
                "job_keywords, evidence_used, excluded_claims, created_at "
                "FROM application_documents WHERE application_id = ? AND doc_type = ? "
                "ORDER BY version",
                [application_id, doc_type],
            ).fetchall()
            return [
                ApplicationDocument(
                    document_id=r[0],
                    application_id=r[1],
                    doc_type=r[2],
                    version=r[3],
                    content=r[4],
                    job_keywords=json.loads(r[5] or "[]"),
                    evidence_used=json.loads(r[6] or "[]"),
                    excluded_claims=json.loads(r[7] or "[]"),
                    created_at=r[8],
                )
                for r in rows
            ]
        finally:
            conn.close()
