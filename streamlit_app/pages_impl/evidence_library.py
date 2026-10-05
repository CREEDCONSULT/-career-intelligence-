"""Page: Evidence Library - the claims ledger behind every generated document.

Evidence is the only source of truth for what a resume/application may claim.
This page offers structured entry (per evidence type), bulk JSON import, and a
ledger view. Nothing here is ever auto-invented; items are user-entered or
imported from the user's own materials, with honest verification labels.
"""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

import streamlit as st

from careeros.evidence import (
    EVIDENCE_TYPES,
    Evidence,
    EvidenceStore,
    VERIFICATION_STATUSES,
)

_ROOT = Path(__file__).resolve().parents[2]
# Testable: point CAREEROS_DB at a temp database in UI tests. Resolved per
# call (not at import) so tests can point successive runs at different DBs.


def _db_path() -> Path:
    return Path(os.getenv("CAREEROS_DB") or (_ROOT / "data" / "processed" / "career_intel.duckdb"))


_TYPE_HELP = {
    "employment": "A job/role you held",
    "project": "A discrete project (incl. consulting engagements)",
    "skill": "A demonstrated capability",
    "technology": "Hands-on tool/platform experience",
    "outcome": "A quantified result",
    "certification": "A credential",
    "education": "A degree/course",
    "portfolio": "A public artifact (writing, repo, talk, site)",
}


def _store():
    return EvidenceStore(_db_path())


def _parse_date_or_none(value: str):
    try:
        return date.fromisoformat(value.strip())
    except (ValueError, AttributeError):
        return None


def _render_add_form(store: EvidenceStore) -> None:
    with st.expander("Add evidence item", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            ev_type = st.selectbox(
                "Type",
                EVIDENCE_TYPES,
                key="ev_type",
                format_func=lambda t: f"{t} - {_TYPE_HELP[t]}",
            )
            title = st.text_input(
                "Title *", key="ev_title", placeholder="e.g. Data Platform Migration"
            )
            organization = st.text_input("Organization / client / school", key="ev_org")
            start = st.text_input("Start date (YYYY-MM-DD, optional)", key="ev_start")
            end = st.text_input("End date (YYYY-MM-DD, optional; blank = ongoing)", key="ev_end")
        with col2:
            description = st.text_area(
                "Description - what you actually did", height=110, key="ev_desc"
            )
            skills = st.text_input(
                "Skills demonstrated (comma-separated)",
                key="ev_skills",
                placeholder="Python, SQL, Airflow",
            )
            metrics_raw = st.text_area(
                "Quantified outcomes - one per line: value unit context",
                height=60,
                key="ev_metrics",
                placeholder="30 % cycle-time reduction\n2x faster reporting",
            )
            verification = st.selectbox(
                "Verification status", VERIFICATION_STATUSES, key="ev_verification"
            )
            claims_allowed = st.checkbox(
                "May be used in resumes/applications", value=True, key="ev_claims"
            )
        notes = st.text_input("Notes (optional)", key="ev_notes")

        if st.button("Save evidence", key="ev_save", type="primary"):
            if not title.strip():
                st.warning("A title is required.")
                return
            metrics = []
            for line in (metrics_raw or "").strip().splitlines():
                parts = line.strip().split(None, 2)
                if not parts:
                    continue
                m = {
                    "value": parts[0],
                    "unit": parts[1] if len(parts) > 1 else "",
                    "context": parts[2] if len(parts) > 2 else "",
                }
                metrics.append(m)
            ev = store.add(
                Evidence(
                    evidence_id=0,
                    type=ev_type,
                    title=title.strip(),
                    organization=(organization or None),
                    start_date=_parse_date_or_none(start),
                    end_date=_parse_date_or_none(end),
                    description=(description or None),
                    metrics=metrics,
                    skills=[s.strip() for s in skills.split(",") if s.strip()],
                    verification_status=verification,
                    claims_allowed=claims_allowed,
                    notes=(notes or None),
                    provenance="manual entry",
                )
            )
            st.success(f"Saved evidence [E{ev.evidence_id}].")
            st.rerun()


def _render_import(store: EvidenceStore) -> None:
    with st.expander("Bulk import (JSON array)", expanded=False):
        st.caption(
            'Example: [{"type": "project", "title": "Portal", "skills": ["Docker"], '
            '"description": "...", "metrics": [{"value": "30", "unit": "%", '
            '"context": "faster"}]}]'
        )
        raw = st.text_area("JSON items", height=140, key="ev_json")
        if st.button("Import", key="ev_import"):
            try:
                items = json.loads(raw)
                if not isinstance(items, list):
                    raise ValueError("expected a JSON array")
                saved = store.import_fixture(items, provenance="JSON import")
                st.success(f"Imported {len(saved)} evidence item(s).")
                st.rerun()
            except (json.JSONDecodeError, ValueError, TypeError) as e:
                st.error(f"Import failed: {e}")


def _render_ledger(store: EvidenceStore) -> None:
    items = store.list_all()
    if not items:
        st.info(
            "No evidence yet. Everything the app generates for applications "
            "traces back to items here - add your first one above."
        )
        return
    st.subheader(f"Evidence ledger ({len(items)} items)")
    for ev in items:
        status_color = (
            "#0FA958"
            if ev.verification_status == "verified"
            else ("#0A72EF" if ev.verification_status == "documented" else "#D4A80D")
        )
        header = f"**[E{ev.evidence_id}] {ev.title}** - {ev.type}" + (
            f" @ {ev.organization}" if ev.organization else ""
        )
        date_chip = ""
        if ev.start_date or ev.end_date:
            date_chip = f" ({ev.start_date or '?'} - {ev.end_date or 'ongoing'})"
        claim_chip = (
            " | usable in applications" if ev.claims_allowed else " | NOT usable for claims"
        )
        st.markdown(
            f"<span style='color:{status_color};'>●</span> {header}{date_chip} "
            f"<small>({ev.verification_status}{claim_chip})</small>",
            unsafe_allow_html=True,
        )
        if ev.description:
            st.caption(ev.description)
        if ev.skills:
            st.caption("Skills: " + ", ".join(ev.skills))
        if ev.metrics:
            st.caption(
                "Metrics: "
                + "; ".join(
                    f"{m.get('value', '')}{m.get('unit', '')} {m.get('context', '')}".strip()
                    for m in ev.metrics
                )
            )
        if st.button(f"Delete [E{ev.evidence_id}]", key=f"ev_del_{ev.evidence_id}"):
            store.remove(ev.evidence_id)
            st.rerun()
        st.divider()


def render(date_range: str = "Last 12 months") -> None:
    st.header("Evidence Library")
    st.caption(
        "The claims ledger - every resume bullet and application answer "
        "traces back to items here. Nothing is invented."
    )
    store = _store()
    _render_add_form(store)
    _render_import(store)
    st.divider()
    _render_ledger(store)
