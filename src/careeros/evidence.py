"""Structured evidence model — the "claims ledger" behind every generated document.

M3 upgrades:
- Three verification states: VERIFIED / FOUNDER_ASSERTED / UNVERIFIED
- claims_allowed is now derived from verification_state (backward-compatible field)
- Promotion mechanism: UNVERIFIED → FOUNDER_ASSERTED → VERIFIED
- Expanded evidence types (16 types covering the founder's full career surface)
- Only VERIFIED and explicitly permitted FOUNDER_ASSERTED evidence may appear
  in externally generated application materials.

Rules:
- No invention: evidence is user-entered or imported from the user's own materials.
- verification_state keeps honest labels; promotion is an explicit user action.
- Skills are extracted deterministically (33K-skill taxonomy whole-token matcher).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import duckdb

# ---------------------------------------------------------------------------
# Types and states
# ---------------------------------------------------------------------------

EVIDENCE_TYPES = (
    # M1 types (preserved)
    "employment",  # a job/role the user held
    "project",  # a discrete project (incl. consulting engagements)
    "skill",  # a demonstrated skill capability
    "technology",  # hands-on tool/platform experience
    "outcome",  # a quantified result
    "certification",  # credential
    "education",  # degree/course
    "portfolio",  # public artifact (writing, repo, talk, site)
    # M3 types
    "contract_work",  # contract/consulting engagement
    "founder_work",  # founder/co-founder work
    "product",  # a built/shipped product
    "case_study",  # a detailed case study
    "technical_skill",  # a specific technical skill with depth
    "business_consulting",  # business/strategy consulting work
    "github_repository",  # a public GitHub repository
    "report",  # a written report or analysis
    "presentation",  # a talk, workshop, or presentation
    "recommendation",  # a reference or recommendation letter
)

#: M3 verification states — the single source of truth for evidence trust.
VERIFICATION_STATES = ("UNVERIFIED", "FOUNDER_ASSERTED", "VERIFIED")

#: Backward-compat alias (M1 name)
VERIFICATION_STATUSES = VERIFICATION_STATES

#: Legacy statuses from M1 (mapped to the new states for backward compatibility)
_LEGACY_STATUS_MAP = {
    "verified": "VERIFIED",
    "documented": "FOUNDER_ASSERTED",
    "self_reported": "UNVERIFIED",
}

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
    verification_status: str = "self_reported"  # legacy field (kept for compat)
    artifacts: list[str] = field(default_factory=list)  # file paths / URLs
    claims_allowed: bool = True  # derived from verification_state
    notes: Optional[str] = None
    provenance: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # M3 fields
    verification_state: str = "UNVERIFIED"  # VERIFIED | FOUNDER_ASSERTED | UNVERIFIED
    founder_permits_external: bool = False  # FOUNDER_ASSERTED may be used externally
    target_role_families: list[str] = field(default_factory=list)  # which families this supports

    def __post_init__(self):
        """Sync verification_state with legacy verification_status and derive claims_allowed."""
        if self.verification_state not in VERIFICATION_STATES:
            # Try legacy mapping
            self.verification_state = _LEGACY_STATUS_MAP.get(self.verification_status, "UNVERIFIED")
        self._sync_claims_allowed()

    def _sync_claims_allowed(self) -> None:
        """Derive claims_allowed from verification_state.

        - VERIFIED: always claims-allowed
        - FOUNDER_ASSERTED: allowed only if founder_permits_external is True
        - UNVERIFIED: never claims-allowed
        """
        if self.verification_state == "VERIFIED":
            self.claims_allowed = True
        elif self.verification_state == "FOUNDER_ASSERTED":
            self.claims_allowed = self.founder_permits_external
        else:
            self.claims_allowed = False

    @property
    def external_use_allowed(self) -> bool:
        """True only if this evidence may appear in externally generated materials."""
        return self.claims_allowed

    @property
    def text(self) -> str:
        """Full searchable text of this evidence item (deterministic)."""
        parts = [self.title, self.organization or "", self.description or "", " ".join(self.skills)]
        for m in self.metrics:
            parts.append(f"{m.get('value', '')} {m.get('unit', '')} {m.get('context', '')}")
        return " ".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Schema (with M3 migration for existing databases)
# ---------------------------------------------------------------------------

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

_MIGRATION_COLUMNS = [
    ("verification_state", "VARCHAR DEFAULT 'UNVERIFIED'"),
    ("founder_permits_external", "BOOLEAN DEFAULT FALSE"),
    ("target_role_families", "VARCHAR DEFAULT '[]'"),
]


def _row_to_evidence(row, column_names: list[str]) -> Evidence:
    """Build an Evidence from a row, handling M3 columns that may be absent."""
    d = dict(zip(column_names, row))
    # Handle M3 columns with defaults for pre-M3 rows
    d.setdefault("verification_state", "UNVERIFIED")
    d.setdefault("founder_permits_external", False)
    d.setdefault("target_role_families", [])
    if isinstance(d.get("target_role_families"), str):
        try:
            d["target_role_families"] = json.loads(d["target_role_families"])
        except (json.JSONDecodeError, TypeError):
            d["target_role_families"] = []
    return Evidence(
        evidence_id=d["evidence_id"],
        type=d["type"],
        title=d["title"],
        organization=d.get("organization"),
        start_date=d.get("start_date"),
        end_date=d.get("end_date"),
        description=d.get("description"),
        metrics=json.loads(d.get("metrics") or "[]"),
        skills=json.loads(d.get("skills") or "[]"),
        verification_status=d.get("verification_status", "self_reported"),
        artifacts=json.loads(d.get("artifacts") or "[]"),
        claims_allowed=bool(d.get("claims_allowed", False)),
        notes=d.get("notes"),
        provenance=d.get("provenance"),
        created_at=d.get("created_at"),
        updated_at=d.get("updated_at"),
        verification_state=d.get("verification_state", "UNVERIFIED"),
        founder_permits_external=bool(d.get("founder_permits_external", False)),
        target_role_families=d.get("target_role_families", []),
    )


def _parse_date(value) -> Optional[date]:
    if value is None or isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


class EvidenceStore:
    """DuckDB-backed evidence ledger with M3 verification states."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)

    def _connect(self):
        conn = duckdb.connect(self.db_path)
        conn.execute(_SCHEMA)
        self._migrate(conn)
        return conn

    def _migrate(self, conn) -> None:
        """Add M3 columns to pre-M3 tables (idempotent)."""
        for col_name, col_def in _MIGRATION_COLUMNS:
            try:
                conn.execute(f"ALTER TABLE evidence_items ADD COLUMN {col_name} {col_def}")
            except Exception:
                pass  # column already exists

    @staticmethod
    def _column_names(conn) -> list[str]:
        return [
            d[0]
            for d in conn.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'evidence_items' ORDER BY ordinal_position"
            ).fetchall()
        ]

    # -- writes -----------------------------------------------------------
    def add(self, ev: Evidence) -> Evidence:
        if ev.type not in EVIDENCE_TYPES:
            raise ValueError(f"unknown evidence type: {ev.type!r}")
        ev.__post_init__()  # ensure claims_allowed is derived
        conn = self._connect()
        try:
            next_id = conn.execute(
                "SELECT COALESCE(MAX(evidence_id), 0) + 1 FROM evidence_items"
            ).fetchone()[0]
            d = asdict(ev)
            d.pop("evidence_id")
            now = datetime.now()
            if d.get("created_at") is None:
                d["created_at"] = now
            d["updated_at"] = now
            d["evidence_id"] = next_id
            conn.execute(
                """INSERT INTO evidence_items (
                    evidence_id, type, title, organization, start_date, end_date,
                    description, metrics, skills, verification_status, artifacts,
                    claims_allowed, notes, provenance, created_at, updated_at,
                    verification_state, founder_permits_external, target_role_families
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    d["evidence_id"],
                    d["type"],
                    d["title"],
                    d.get("organization"),
                    str(d["start_date"]) if d.get("start_date") else None,
                    str(d["end_date"]) if d.get("end_date") else None,
                    d.get("description"),
                    json.dumps(d.get("metrics", [])),
                    json.dumps(d.get("skills", [])),
                    d.get("verification_status", "self_reported"),
                    json.dumps(d.get("artifacts", [])),
                    d.get("claims_allowed", False),
                    d.get("notes"),
                    d.get("provenance"),
                    d["created_at"].isoformat(sep=" ") if d["created_at"] else None,
                    d["updated_at"].isoformat(sep=" ") if d["updated_at"] else None,
                    d.get("verification_state", "UNVERIFIED"),
                    d.get("founder_permits_external", False),
                    json.dumps(d.get("target_role_families", [])),
                ],
            )
        finally:
            conn.close()
        return self.get(next_id)  # type: ignore[return-value]

    # -- M3 verification state management --------------------------------------
    def promote_to_verified(
        self, evidence_id: int, provenance: str = "founder:verified"
    ) -> Optional[Evidence]:
        """Promote an item to VERIFIED (founder action, recorded)."""
        return self._set_verification(
            evidence_id, "VERIFIED", founder_permits=True, provenance=provenance
        )

    def promote_to_founder_asserted(
        self, evidence_id: int, permit_external: bool = False, provenance: str = "founder:asserted"
    ) -> Optional[Evidence]:
        """Promote to FOUNDER_ASSERTED. External use requires explicit permission."""
        return self._set_verification(
            evidence_id, "FOUNDER_ASSERTED", founder_permits=permit_external, provenance=provenance
        )

    def demote_to_unverified(
        self, evidence_id: int, provenance: str = "founder:demoted"
    ) -> Optional[Evidence]:
        """Demote to UNVERIFIED (blocks all external use)."""
        return self._set_verification(
            evidence_id, "UNVERIFIED", founder_permits=False, provenance=provenance
        )

    def _set_verification(
        self, evidence_id: int, state: str, *, founder_permits: bool, provenance: str
    ) -> Optional[Evidence]:
        if state not in VERIFICATION_STATES:
            raise ValueError(f"unknown verification state: {state!r}")
        ev = self.get(evidence_id)
        if ev is None:
            return None
        # Derive claims_allowed
        if state == "VERIFIED":
            claims = True
        elif state == "FOUNDER_ASSERTED":
            claims = founder_permits
        else:
            claims = False
        conn = self._connect()
        try:
            conn.execute(
                """UPDATE evidence_items SET
                   verification_state = ?, founder_permits_external = ?,
                   claims_allowed = ?,
                   updated_at = CURRENT_TIMESTAMP
                WHERE evidence_id = ?""",
                [state, founder_permits, claims, evidence_id],
            )
            # Append to provenance chain
            row = conn.execute(
                "SELECT provenance FROM evidence_items WHERE evidence_id = ?", [evidence_id]
            ).fetchone()
            if row and row[0]:
                conn.execute(
                    "UPDATE evidence_items SET provenance = ? WHERE evidence_id = ?",
                    [f"{row[0]} | {provenance}", evidence_id],
                )
            else:
                conn.execute(
                    "UPDATE evidence_items SET provenance = ? WHERE evidence_id = ?",
                    [provenance, evidence_id],
                )
        finally:
            conn.close()
        return self.get(evidence_id)

    # -- reads (updated for M3) -------------------------------------------------
    def get(self, evidence_id: int) -> Optional[Evidence]:
        conn = self._connect()
        try:
            cols = self._column_names(conn)
            row = conn.execute(
                "SELECT * FROM evidence_items WHERE evidence_id = ?", [evidence_id]
            ).fetchone()
            return _row_to_evidence(row, cols) if row else None
        finally:
            conn.close()

    def list_all(
        self, evidence_type: Optional[str] = None, verification_state: Optional[str] = None
    ) -> list[Evidence]:
        """List evidence, optionally filtered by type and/or verification state."""
        conn = self._connect()
        try:
            cols = self._column_names(conn)
            sql = "SELECT * FROM evidence_items"
            conditions = []
            params: list = []
            if evidence_type:
                conditions.append("type = ?")
                params.append(evidence_type)
            if verification_state and "verification_state" in cols:
                conditions.append("verification_state = ?")
                params.append(verification_state)
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            sql += " ORDER BY evidence_id"
            rows = conn.execute(sql, params).fetchall()
            return [_row_to_evidence(r, cols) for r in rows]
        finally:
            conn.close()

    def list_claimable(self) -> list[Evidence]:
        """All evidence with claims_allowed=True (VERIFIED + permitted FOUNDER_ASSERTED)."""
        return [e for e in self.list_all() if e.claims_allowed]

    def verification_summary(self) -> dict:
        """Count evidence by verification state."""
        summary = {"VERIFIED": 0, "FOUNDER_ASSERTED": 0, "UNVERIFIED": 0}
        for e in self.list_all():
            summary[e.verification_state] = summary.get(e.verification_state, 0) + 1
        return summary

    # -- derived views (M3) -------------------------------------------------------
    def supported_skills(self) -> dict[str, list[int]]:
        """skill_name (canonical) -> evidence IDs supporting it.

        Only claimable evidence (VERIFIED + permitted FOUNDER_ASSERTED) supports skills.
        """
        from careeros.fit_engine import extract_skills_from_text

        supported: dict[str, list[int]] = {}
        for ev in self.list_all():
            if not ev.claims_allowed:
                continue
            ids = set()
            for s in ev.skills:
                ids.add(s.strip().lower())
            for s in extract_skills_from_text(ev.text):
                ids.add(s)
            for s in ids:
                if s:
                    supported.setdefault(s, []).append(ev.evidence_id)
        return supported

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
            "founder_permits_external",
            "target_role_families",
        }
        bad = set(fields) - allowed
        if bad:
            raise ValueError(f"non-updatable fields: {sorted(bad)}")
        if not fields:
            return
        sets, vals = [], []
        for k, v in fields.items():
            if k in ("metrics", "skills", "artifacts", "target_role_families"):
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
            for k in ("metrics", "skills", "artifacts", "target_role_families"):
                if k in d and isinstance(d[k], str):
                    d[k] = json.loads(d[k])
            ev = Evidence(evidence_id=0, **d)
            out.append(self.add(ev))
        return out
