"""Integration tests: full M1 vertical slice on a temp database.

Ingest -> evidence -> fit -> application state machine -> documents ->
next-best-action, i.e. the workspace data flow end-to-end.
"""

from datetime import datetime

import pytest

from careeros.application import (
    ApplicationStore,
    DocumentStore,
)
from careeros.evidence import Evidence, EvidenceStore
from careeros.fit_engine import evaluate_fit
from careeros.ingestion import ManualPasteAdapter, ingest
from careeros.next_action import next_actions_for_store
from careeros.opportunity import OpportunityStore
from llm.features.evidence_resume import deterministic_keyword_alignment


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "vertical.duckdb"
    return {
        "opps": OpportunityStore(p),
        "evs": EvidenceStore(p),
        "apps": ApplicationStore(p),
        "docs": DocumentStore(p),
    }


def test_full_vertical_slice(db):
    opps, evs, apps, docs = db["opps"], db["evs"], db["apps"], db["docs"]

    # 1. ingest an opportunity (manual paste, realistic ad text)
    opp = ingest(
        opps,
        ManualPasteAdapter(),
        (
            "Senior Analytics Engineer at Northwind\n"
            "Hybrid, full-time in Toronto. We need strong Python, SQL, and Airflow; "
            "dbt and Docker are nice to have. Salary CAD 120k - 145k. "
            "5+ years experience. Apply by 2026-12-15."
        ),
    )
    assert opp.work_mode == "hybrid"
    assert opp.employment_type == "full-time"
    assert opp.seniority == "senior"
    assert opp.currency == "CAD"

    # 2. seed evidence
    evs.add(
        Evidence(
            evidence_id=0,
            type="employment",
            verification_state="VERIFIED",
            title="Analytics Engineer",
            organization="Old Co",
            start_date="2020-01-01",
            end_date="2024-05-01",
            description="Built Python/SQL pipelines in Airflow; 40% faster refreshes.",
            skills=["Python", "SQL", "Airflow"],
        )
    )
    evs.add(
        Evidence(
            evidence_id=0,
            type="project",
            title="dbt migration",
            description="Rebuilt warehouse with dbt and Docker.",
            skills=["dbt", "Docker"],
            verification_state="VERIFIED",
        )
    )

    # 3. evidence-based fit
    fit = evaluate_fit(opp, evs.list_all(), today=datetime(2026, 10, 5).date())
    assert fit.band in ("STRONG FIT", "POSSIBLE FIT")
    assert fit.coverage_hard == 1.0
    assert all(s.evidence_ids for s in fit.strengths)

    # 4. application + explicit walk
    app = apps.create_for_opportunity(opp.opportunity_id)
    for st in ("REVIEWED", "SHORTLISTED", "PREPARING"):
        app = apps.transition(app.application_id, st, trigger="user:workspace")
    assert app.current_state == "PREPARING"

    # 5. documents with traceability (deterministic fallback: no API key needed)
    base = docs.save(
        app.application_id, "base_resume", "Analytics engineer: Python, SQL, Airflow, dbt, Docker."
    )
    result = deterministic_keyword_alignment(
        docs.latest(app.application_id, "base_resume").content, opp, evs.list_all()
    )
    tailored = docs.save(
        app.application_id,
        "tailored_resume",
        result.markdown,
        job_keywords=result.keywords,
        evidence_used=result.evidence_used,
        excluded_claims=result.excluded_claims,
    )
    assert base.version == 1 and tailored.version == 1
    assert set(tailored.evidence_used) <= {e.evidence_id for e in evs.list_all()}
    assert tailored.excluded_claims  # honest about unsupported keywords

    # 6. next-best-action reflects progress
    board = next_actions_for_store(apps, opps, evs, docs, now=datetime(2026, 10, 5, 9, 0))
    assert len(board) == 1
    assert board[0].state == "PREPARING"
    assert "Finalize" in board[0].action  # base + tailored exist -> finalize

    # 7. walk to READY_TO_APPLY -> urgency kicks in near closing date is far, fine
    for st in ("READY_TO_APPLY", "APPLIED"):
        app = apps.transition(app.application_id, st, trigger="user:workspace")
    board = next_actions_for_store(apps, opps, evs, docs, now=datetime(2026, 10, 5, 9, 0))
    assert board[0].state == "APPLIED"
    assert board[0].action == "Await screening response"

    # 8. event log preserves the whole history
    events = apps.events(app.application_id)
    assert [e.new_state for e in events] == [
        "DISCOVERED",
        "REVIEWED",
        "SHORTLISTED",
        "PREPARING",
        "READY_TO_APPLY",
        "APPLIED",
    ]
    assert all(e.trigger == "user:workspace" for e in events[1:])


def test_board_ranks_two_opportunities_by_state_and_urgency(db):
    opps, evs, apps, docs = db["opps"], db["evs"], db["apps"], db["docs"]
    now = datetime(2026, 10, 5, 9, 0)

    hot = ingest(
        opps,
        ManualPasteAdapter(),
        ("Data Engineer at HotCo\nRemote. Python SQL. Apply by 2026-10-07."),
    )
    cold = ingest(opps, ManualPasteAdapter(), "Analyst at ColdCo\nExcel work.")
    evs.add(
        Evidence(
            evidence_id=0,
            type="employment",
            verification_state="VERIFIED",
            title="Data Engineer",
            description="Python and SQL pipelines.",
            skills=["Python", "SQL"],
        )
    )

    a_hot = apps.create_for_opportunity(hot.opportunity_id)
    for st in ("REVIEWED", "SHORTLISTED", "PREPARING", "READY_TO_APPLY"):
        apps.transition(a_hot.application_id, st, trigger="user:test")
    apps.create_for_opportunity(cold.opportunity_id)

    board = next_actions_for_store(apps, opps, evs, docs, now=now)
    assert board[0].opportunity_id == hot.opportunity_id
    assert "URGENT" in board[0].action  # closes in 2 days
    assert board[1].state == "DISCOVERED"
    assert board[0].priority_score > board[1].priority_score


def test_document_history_survives_state_changes(db):
    opps, apps, docs = db["opps"], db["apps"], db["docs"]
    opp = ingest(opps, ManualPasteAdapter(), "Dev at Co\nPython.")
    app = apps.create_for_opportunity(opp.opportunity_id)
    docs.save(app.application_id, "base_resume", "v1")
    docs.save(app.application_id, "base_resume", "v2")
    for st in ("REVIEWED", "SHORTLISTED", "WITHDRAWN"):
        apps.transition(app.application_id, st, trigger="user:test")
    # documents outlive the application lifecycle
    assert [v.version for v in docs.list_versions(app.application_id, "base_resume")] == [1, 2]
    assert docs.latest(app.application_id, "base_resume").content == "v2"

