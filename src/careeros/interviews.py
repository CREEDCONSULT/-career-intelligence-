"""Interview records: first-class progression within interview-stage states (M2 §5).

Interviews are a detail layer *inside* the SCREENING / INTERVIEW / ASSESSMENT /
OFFER application states - the application state machine is untouched. Each
interview tracks stage, schedule, participants, preparation status, notes,
artifacts, and follow-up, with append-only provenance like everything else.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from pathlib import Path
from typing import Optional

import duckdb

INTERVIEW_STAGES = (
    "recruiter_screen",
    "hiring_manager",
    "technical_case",
    "assessment",
    "panel_final",
    "offer_discussion",
)

PREP_STATUSES = ("not_started", "in_progress", "ready")

#: Which application states an interview may be recorded against.
ALLOWED_APP_STATES = ("SCREENING", "INTERVIEW", "ASSESSMENT", "OFFER")


@dataclass
class Interview:
    interview_id: int
    application_id: int
    stage: str  # one of INTERVIEW_STAGES
    scheduled_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    location: Optional[str] = None  # address / meeting link
    participants: list[str] = field(default_factory=list)
    prep_status: str = "not_started"  # one of PREP_STATUSES
    notes: Optional[str] = None
    artifacts: list[dict] = field(default_factory=list)
    follow_up: Optional[date] = None  # planned follow-up date
    provenance: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return asdict(self)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS interviews (
    interview_id INTEGER PRIMARY KEY,
    application_id INTEGER NOT NULL,
    stage VARCHAR NOT NULL,
    scheduled_at TIMESTAMP,
    duration_minutes INTEGER,
    location VARCHAR,
    participants VARCHAR,
    prep_status VARCHAR,
    notes VARCHAR,
    artifacts VARCHAR,
    follow_up DATE,
    provenance VARCHAR,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
"""


def _row_to_interview(row) -> Interview:
    return Interview(
        interview_id=row[0],
        application_id=row[1],
        stage=row[2],
        scheduled_at=row[3],
        duration_minutes=row[4],
        location=row[5],
        participants=json.loads(row[6] or "[]"),
        prep_status=row[7],
        notes=row[8],
        artifacts=json.loads(row[9] or "[]"),
        follow_up=row[10],
        provenance=row[11],
        created_at=row[12],
        updated_at=row[13],
    )


class InterviewStore:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)

    def _connect(self):
        conn = duckdb.connect(self.db_path)
        conn.execute(_SCHEMA)
        return conn

    # -- writes -----------------------------------------------------------
    def schedule(
        self,
        application_id: int,
        stage: str,
        app_state: str,
        scheduled_at: Optional[datetime] = None,
        duration_minutes: Optional[int] = None,
        location: Optional[str] = None,
        participants: Optional[list[str]] = None,
        notes: Optional[str] = None,
        provenance: str = "user:workspace",
    ) -> Interview:
        """Record an interview. Validates stage + that the application is in
        an interview-stage state (the state machine stays the source of truth)."""
        if stage not in INTERVIEW_STAGES:
            raise ValueError(f"unknown interview stage: {stage!r}")
        if app_state.upper() not in ALLOWED_APP_STATES:
            raise ValueError(
                f"interviews may only be recorded in {ALLOWED_APP_STATES}, "
                f"application is in {app_state}"
            )
        conn = self._connect()
        try:
            iid = conn.execute(
                "SELECT COALESCE(MAX(interview_id), 0) + 1 FROM interviews"
            ).fetchone()[0]
            now = datetime.now().isoformat(sep=" ")
            sched = scheduled_at.isoformat(sep=" ") if scheduled_at else None
            conn.execute(
                "INSERT INTO interviews VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    iid,
                    application_id,
                    stage,
                    sched,
                    duration_minutes,
                    location,
                    json.dumps(participants or []),
                    "not_started",
                    notes,
                    json.dumps([]),
                    None,
                    provenance,
                    now,
                    now,
                ],
            )
        finally:
            conn.close()
        return self.get(iid)  # type: ignore[return-value]

    def update_fields(self, interview_id: int, **fields) -> None:
        allowed = {
            "scheduled_at",
            "duration_minutes",
            "location",
            "participants",
            "prep_status",
            "notes",
            "artifacts",
            "follow_up",
        }
        bad = set(fields) - allowed
        if bad:
            raise ValueError(f"non-updatable fields: {sorted(bad)}")
        if not fields:
            return
        sets, vals = [], []
        for k, v in fields.items():
            if k in ("participants", "artifacts"):
                v = json.dumps(v)
            elif isinstance(v, datetime):
                v = v.isoformat(sep=" ")
            elif isinstance(v, date):
                v = str(v)
            sets.append(f"{k} = ?")
            vals.append(v)
        conn = self._connect()
        try:
            conn.execute(
                f"UPDATE interviews SET {', '.join(sets)}, updated_at = CURRENT_TIMESTAMP "
                f"WHERE interview_id = ?",
                vals + [interview_id],
            )
        finally:
            conn.close()

    # -- reads ------------------------------------------------------------
    def get(self, interview_id: int) -> Optional[Interview]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM interviews WHERE interview_id = ?", [interview_id]
            ).fetchone()
            return _row_to_interview(row) if row else None
        finally:
            conn.close()

    def list_for_application(self, application_id: int) -> list[Interview]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM interviews WHERE application_id = ? "
                "ORDER BY scheduled_at NULLS LAST, interview_id",
                [application_id],
            ).fetchall()
            return [_row_to_interview(r) for r in rows]
        finally:
            conn.close()

    def next_upcoming(
        self, application_id: int, now: Optional[datetime] = None
    ) -> Optional[Interview]:
        """The soonest not-yet-completed interview (drives NBA + calendar)."""
        now = now or datetime.now()
        upcoming = [
            i
            for i in self.list_for_application(application_id)
            if i.scheduled_at and i.scheduled_at >= now
        ]
        return min(upcoming, key=lambda i: i.scheduled_at) if upcoming else None
