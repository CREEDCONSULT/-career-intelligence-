"""Application outcomes + learning analytics (M2 §8).

An ApplicationOutcome is derived from the append-only event log when an
application reaches a terminal state (or is explicitly snapshotted), so
outcome facts are never hand-typed and never contradict history.

Analytics report funnel rates by source / fit band / resume version / role
family, with explicit low-sample labeling: any cell with n < MIN_SAMPLE is
reported as "insufficient sample" rather than a misleading percentage.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import duckdb

from careeros.application import Application, ApplicationStore, ApplicationState
from careeros.opportunity import Opportunity

OUTCOME_TYPES = ("no_response", "rejected", "withdrawn", "offer", "closed")

#: Below this sample size a rate is labeled instead of trusted.
MIN_SAMPLE = 5

#: Days after APPLIED with no further event before an outcome may be recorded
#: as no_response (must be explicit, never auto-inferred on snapshot).
NO_RESPONSE_AFTER_DAYS = 21


@dataclass
class ApplicationOutcome:
    outcome_id: int
    application_id: int
    opportunity_id: int
    final_state: str
    outcome_type: str  # OUTCOME_TYPES
    first_response_days: Optional[int] = None  # APPLIED -> first response event
    days_to_outcome: Optional[int] = None  # APPLIED -> terminal event
    fit_band: Optional[str] = None
    resume_version: Optional[int] = None
    cover_letter_version: Optional[int] = None
    source: Optional[str] = None
    role_family: Optional[str] = None
    recorded_at: Optional[datetime] = None
    provenance: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


def _terminal_outcome_type(final_state: str) -> str:
    return {
        ApplicationState.REJECTED.value: "rejected",
        ApplicationState.WITHDRAWN.value: "withdrawn",
        ApplicationState.CLOSED.value: "closed",
    }[final_state]


_SCHEMA = """
CREATE TABLE IF NOT EXISTS application_outcomes (
    outcome_id INTEGER PRIMARY KEY,
    application_id INTEGER NOT NULL,
    opportunity_id INTEGER NOT NULL,
    final_state VARCHAR NOT NULL,
    outcome_type VARCHAR NOT NULL,
    first_response_days INTEGER,
    days_to_outcome INTEGER,
    fit_band VARCHAR,
    resume_version INTEGER,
    cover_letter_version INTEGER,
    source VARCHAR,
    role_family VARCHAR,
    recorded_at TIMESTAMP,
    provenance VARCHAR
)
"""


def _row_to_outcome(row) -> ApplicationOutcome:
    return ApplicationOutcome(*row[:14])


class OutcomeStore:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)

    def _connect(self):
        conn = duckdb.connect(self.db_path)
        conn.execute(_SCHEMA)
        return conn

    # -- writes -----------------------------------------------------------
    def record_from_application(
        self,
        application: Application,
        app_store: ApplicationStore,
        opportunity: Opportunity,
        fit_band: Optional[str],
        resume_version: Optional[int],
        cover_letter_version: Optional[int],
        role_family: Optional[str],
        *,
        outcome_type_override: Optional[str] = None,
        provenance: str = "derived:event-log",
    ) -> ApplicationOutcome:
        """Derive + persist the outcome for a TERMINAL application.

        Days-to-response/outcome come from the event log timestamps, never
        from memory. ``outcome_type_override`` allows an explicit
        'no_response' closure (the only non-terminal-derived type).
        """
        final = application.current_state.upper()
        if final not in {
            s.value
            for s in (
                ApplicationState.REJECTED,
                ApplicationState.WITHDRAWN,
                ApplicationState.CLOSED,
            )
        }:
            raise ValueError(f"outcomes record only for terminal applications; this one is {final}")
        if outcome_type_override and outcome_type_override not in OUTCOME_TYPES:
            raise ValueError(f"unknown outcome type: {outcome_type_override!r}")
        outcome_type = outcome_type_override or _terminal_outcome_type(final)

        events = app_store.events(application.application_id)
        applied = next((e for e in events if e.new_state == "APPLIED"), None)
        terminal = events[-1] if events else None
        first_response_days = days_to_outcome = None
        if applied is not None:
            applied_dt = applied.timestamp
            if applied_dt is not None:
                # first response = first event AFTER APPLIED that changes state
                idx = events.index(applied)
                later = [e for e in events[idx + 1 :] if e.new_state != "APPLIED"]
                if later and later[0].timestamp:
                    first_response_days = (later[0].timestamp - applied_dt).days
                if terminal is not None and terminal.timestamp:
                    days_to_outcome = (terminal.timestamp - applied_dt).days

        conn = self._connect()
        try:
            oid = conn.execute(
                "SELECT COALESCE(MAX(outcome_id), 0) + 1 FROM application_outcomes"
            ).fetchone()[0]
            now = datetime.now().isoformat(sep=" ")
            conn.execute(
                "INSERT INTO application_outcomes VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    oid,
                    application.application_id,
                    application.opportunity_id,
                    final,
                    outcome_type,
                    first_response_days,
                    days_to_outcome,
                    fit_band,
                    resume_version,
                    cover_letter_version,
                    opportunity.source,
                    role_family,
                    now,
                    provenance,
                ],
            )
        finally:
            conn.close()
        return self.get(oid)  # type: ignore[return-value]

    # -- reads ------------------------------------------------------------
    def get(self, outcome_id: int) -> Optional[ApplicationOutcome]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM application_outcomes WHERE outcome_id = ?", [outcome_id]
            ).fetchone()
            return _row_to_outcome(row) if row else None
        finally:
            conn.close()

    def find_by_application(self, application_id: int) -> Optional[ApplicationOutcome]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM application_outcomes WHERE application_id = ?", [application_id]
            ).fetchone()
            return _row_to_outcome(row) if row else None
        finally:
            conn.close()

    def list_all(self) -> list[ApplicationOutcome]:
        conn = self._connect()
        try:
            rows = conn.execute("SELECT * FROM application_outcomes ORDER BY outcome_id").fetchall()
            return [_row_to_outcome(r) for r in rows]
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Analytics (honest: low samples labeled, never a bare misleading percentage)
# ---------------------------------------------------------------------------


@dataclass
class Metric:
    label: str
    numerator: int
    denominator: int
    rate: Optional[float] = None  # None when insufficient sample
    sample_note: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


def _rate(numerator: int, denominator: int) -> Metric:
    """Funnel metric with low-sample honesty."""
    if denominator < MIN_SAMPLE:
        return Metric(
            label="",
            numerator=numerator,
            denominator=denominator,
            sample_note=f"insufficient sample (n={denominator})",
        )
    return Metric(
        label="",
        numerator=numerator,
        denominator=denominator,
        rate=round(numerator / denominator, 3),
    )


def outcome_analytics(outcomes: list[ApplicationOutcome]) -> dict:
    """Compute funnel analytics over recorded outcomes."""
    report: dict = {"total_outcomes": len(outcomes), "metrics": {}}
    if not outcomes:
        report["metrics"]["overall"] = _rate(0, 0)
        report["note"] = (
            "No outcomes recorded yet - analytics appear once applications reach terminal states."
        )
        return report

    def group(key_fn) -> dict:
        buckets: dict[str, list[ApplicationOutcome]] = {}
        for o in outcomes:
            buckets.setdefault(str(key_fn(o) or "unknown"), []).append(o)
        return buckets

    def funnel(items: list[ApplicationOutcome]) -> dict:
        n = len(items)
        responded = sum(1 for o in items if o.outcome_type != "no_response")
        interviewed = sum(
            1
            for o in items
            if o.first_response_days is not None
            and o.outcome_type != "no_response"
            and o.outcome_type != "withdrawn"
        )
        offers = sum(
            1
            for o in items
            if o.outcome_type == "offer"
            or (
                o.outcome_type == "closed"
                and o.final_state == "CLOSED"
                and o.provenance
                and "offer" in (o.provenance or "").lower()
            )
        )
        return {
            "count": n,
            "response_rate": _rate(responded, n),
            "interview_rate": _rate(interviewed, n),
            "offer_rate": _rate(offers, n),
        }

    report["metrics"]["overall"] = funnel(outcomes)
    for name, key_fn in (
        ("by_source", lambda o: o.source),
        ("by_fit_band", lambda o: o.fit_band),
        (
            "by_resume_version",
            lambda o: f"v{o.resume_version}" if o.resume_version is not None else "none",
        ),
        ("by_role_family", lambda o: o.role_family),
    ):
        report["metrics"][name] = {k: funnel(v) for k, v in sorted(group(key_fn).items())}

    resp_days = [o.first_response_days for o in outcomes if o.first_response_days is not None]
    if resp_days:
        report["metrics"]["days_to_first_response"] = {
            "n": len(resp_days),
            "min": min(resp_days),
            "max": max(resp_days),
            "mean": round(sum(resp_days) / len(resp_days), 1),
            "sample_note": None
            if len(resp_days) >= MIN_SAMPLE
            else f"insufficient sample (n={len(resp_days)})",
        }
    return report
