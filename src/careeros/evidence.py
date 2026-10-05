"""Structured evidence model - the "claims ledger" behind every generated document.

Philosophy: a resume bullet or application answer is only as good as the
evidence beneath it. Every evidence item is a first-class record with type,
context, metrics, supported skills, verification status, and provenance.

Rules:
- No invention: evidence is either user-entered or imported from the user's own
  materials - never generated. ``verification_status`` keeps honest labels.
- ``claims_allowed`` gates whether an item may appear in resumes/applications.
- Skills are extracted deterministically from the evidence text using the
  same whole-token matcher the market pipeline uses (33K-skill taxonomy).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import duckdb

EVIDENCE_TYPES = (
    "employment",  # a job/role the user held
    "project",  # a discrete project (incl. consulting engagements)
    "skill",  # a demonstrated skill capability
    "technology",  # hands-on tool/platform experience
    "outcome",  # a quantified result
    "certification",  # credential
    "education",  # degree/course
    "portfolio",  # public artifact (writing, repo, talk, site)
)

VERIFICATION_STATUSES = ("self_reported", "documented", "verified")

# Metrics are stored as JSON: [{"value": 30, "unit": "%", "context": "cycle-time reduction"}]


@dataclass
class Evidence:
    evidence_id: int
    type: str  # one of EVIDENCE_TYPES
    title: str
    organization: Optional[str] = None  # employer / client / school / platform
    start_date: Optional[date] = None
    end_date: Optional[date] = None  # None = ongoing
    description: Optional[str] = None
    metrics: list[dict] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)  # explicit skill claims
    verification_status: str = "self_reported"
    artifacts: list[str] = field(default_factory=list)  # file paths / URLs
    claims_allowed: bool = True
    notes: Optional[str] = None
    provenance: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @property
    def text(self) -> str:
        """Full searchable text of this evidence item (deterministic)."""
        parts = [self.title, self.organization or "", self.description or "", " ".join(self.skills)]
        for m in self.metrics:
            parts.append(f"{m.get('value', '')} {m.get('unit', '')} {m.get('context', '')}")
        return " ".join(p for p in parts if p)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS evidence_items (
    evidence_id INTEGER PRIMARY KEY,
    type VARCHAR NOT NULL,
    title VARCHAR NOT NULL,
    organization VARCHAR,
    start_date DATE,
    end_date DATE,
    description VARCHAR,
    metrics VARCHAR,
    skills VARCHAR,
    verification_status VARCHAR,
    artifacts VARCHAR,
    claims_allowed BOOLEAN,
    notes VARCHAR,
    provenance VARCHAR,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
"""


def _row_to_evidence(row) -> Evidence:
    return Evidence(
        evidence_id=row[0],
        type=row[1],
        title=row[2],
        organization=row[3],
        start_date=row[4],
        end_date=row[5],
        description=row[6],
        metrics=json.loads(row[7] or "[]"),
        skills=json.loads(row[8] or "[]"),
        verification_status=row[9],
        artifacts=json.loads(row[10] or "[]"),
        claims_allowed=bool(row[11]),
        notes=row[12],
        provenance=row[13],
        created_at=row[14],
        updated_at=row[15],
    )


def _parse_date(value) -> Optional[date]:
    if value is None or isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


class EvidenceStore:
    """DuckDB-backed evidence ledger."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)

    def _connect(self):
        conn = duckdb.connect(self.db_path)
        conn.execute(_SCHEMA)
        return conn

    # -- writes -----------------------------------------------------------
    def add(self, ev: Evidence) -> Evidence:
        if ev.type not in EVIDENCE_TYPES:
            raise ValueError(f"unknown evidence type: {ev.type!r}")
        if ev.verification_status not in VERIFICATION_STATUSES:
            raise ValueError(f"unknown verification status: {ev.verification_status!r}")
        conn = self._connect()
        try:
            next_id = conn.execute(
                "SELECT COALESCE(MAX(evidence_id), 0) + 1 FROM evidence_items"
            ).fetchone()[0]
            d = asdict(ev)
            d.pop("evidence_id")
            d["evidence_id"] = next_id
            now = datetime.now()
            if d.get("created_at") is None:
                d["created_at"] = now
            d["updated_at"] = now
            conn.execute(
                """INSERT INTO evidence_items VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    d["evidence_id"],
                    d["type"],
                    d["title"],
                    d["organization"],
                    str(d["start_date"]) if d["start_date"] else None,
                    str(d["end_date"]) if d["end_date"] else None,
                    d["description"],
                    json.dumps(d["metrics"]),
                    json.dumps(d["skills"]),
                    d["verification_status"],
                    json.dumps(d["artifacts"]),
                    d["claims_allowed"],
                    d["notes"],
                    d["provenance"],
                    d["created_at"].isoformat(sep=" "),
                    d["updated_at"].isoformat(sep=" "),
                ],
            )
            return self.get(next_id)  # type: ignore[return-value]
        finally:
            conn.close()

    def update_fields(self, evidence_id: int, **fields) -> None:
        allowed = {
            "type",
            "title",
            "organization",
            "start_date",
            "end_date",
            "description",
            "metrics",
            "skills",
            "verification_status",
            "artifacts",
            "claims_allowed",
            "notes",
        }
        bad = set(fields) - allowed
        if bad:
            raise ValueError(f"non-updatable fields: {sorted(bad)}")
        if not fields:
            return
        sets, vals = [], []
        for k, v in fields.items():
            if k in ("metrics", "skills", "artifacts"):
                v = json.dumps(v)
            elif isinstance(v, date):
                v = str(v)
            sets.append(f"{k} = ?")
            vals.append(v)
        conn = self._connect()
        try:
            conn.execute(
                f"UPDATE evidence_items SET {', '.join(sets)}, updated_at = CURRENT_TIMESTAMP "
                f"WHERE evidence_id = ?",
                vals + [evidence_id],
            )
        finally:
            conn.close()

    def remove(self, evidence_id: int) -> None:
        conn = self._connect()
        try:
            conn.execute("DELETE FROM evidence_items WHERE evidence_id = ?", [evidence_id])
        finally:
            conn.close()

    # -- reads ------------------------------------------------------------
    def get(self, evidence_id: int) -> Optional[Evidence]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM evidence_items WHERE evidence_id = ?", [evidence_id]
            ).fetchone()
            return _row_to_evidence(row) if row else None
        finally:
            conn.close()

    def list_all(self, evidence_type: Optional[str] = None) -> list[Evidence]:
        conn = self._connect()
        try:
            if evidence_type:
                rows = conn.execute(
                    "SELECT * FROM evidence_items WHERE type = ? ORDER BY evidence_id",
                    [evidence_type],
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM evidence_items ORDER BY evidence_id").fetchall()
            return [_row_to_evidence(r) for r in rows]
        finally:
            conn.close()

    # -- derived views -----------------------------------------------------
    def supported_skills(self) -> dict[str, list[int]]:
        """skill_name (canonical) -> evidence IDs supporting it.

        Combines explicit ``skills`` claims with deterministic whole-token
        extraction from each item's text, so a project description mentioning
        "Docker" counts as Docker evidence even without an explicit tag.
        """
        from careeros.fit_engine import (
            extract_skills_from_text,
        )  # lazy: avoids import cycle at module load

        supported: dict[str, list[int]] = {}
        for ev in self.list_all():
            if not ev.claims_allowed:
                continue  # not usable for claims -> does not support any skill
            ids = set()
            for s in ev.skills:
                ids.add(s.strip().lower())
            for s in extract_skills_from_text(ev.text):
                ids.add(s)
            for s in ids:
                if s:
                    supported.setdefault(s, []).append(ev.evidence_id)
        return supported

    def import_fixture(
        self, items: list[dict], provenance: str = "fixture import"
    ) -> list[Evidence]:
        """Bulk-create evidence from structured dicts (tests / JSON import)."""
        out = []
        for item in items:
            d = dict(item)
            d.setdefault("provenance", provenance)
            for k in ("start_date", "end_date"):
                if k in d:
                    d[k] = _parse_date(d[k])
            if "metrics" in d and isinstance(d["metrics"], str):
                d["metrics"] = json.loads(d["metrics"])
            if "skills" in d and isinstance(d["skills"], str):
                d["skills"] = json.loads(d["skills"])
            ev = Evidence(evidence_id=0, **d)
            out.append(self.add(ev))
        return out
