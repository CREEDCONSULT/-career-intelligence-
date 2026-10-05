"""Tests: next-best-action engine (deterministic)."""

from datetime import date, datetime, timedelta

import pytest

from careeros.application import Application
from careeros.fit_engine import FitResult
from careeros.next_action import (
    NextAction,
    compute_next_action,
    rank_next_actions,
    next_actions_for_store,
    FOLLOW_UP_AFTER_DAYS,
)


def _app(state, opp_id=1, app_id=1, updated=None):
    return Application(
        application_id=app_id,
        opportunity_id=opp_id,
        current_state=state,
        created_at=None,
        updated_at=updated or datetime(2026, 10, 5, 12, 0, 0),
    )


def _fit(band="Good match", urgency=1.0, gaps=None):
    from careeros.fit_engine import Gap

    return FitResult(
        opportunity_id=1,
        score=70,
        band=band,
        coverage_hard=1.0,
        overlap_preferred=1.0,
        domain_relevance=0.2,
        seniority_fit=0.75,
        experience_evidence=1.0,
        gaps=[Gap(skill=g) for g in (gaps or [])],
        closing_urgency=urgency,
    )


NOW = datetime(2026, 10, 5, 12, 0, 0)


# -- one clear action per state ------------------------------------------------


@pytest.mark.parametrize(
    "state,expect_fragment",
    [
        ("DISCOVERED", "Review"),
        ("REVIEWED", "shortlist"),  # a fit result is provided in this parametrization
        ("SHORTLISTED", "resume"),
        ("PREPARING", "resume"),
        ("READY_TO_APPLY", "Submit"),
        ("APPLIED", "Await"),  # recently applied -> waiting; follow-up due later
        ("SCREENING", "screening"),
        ("INTERVIEW", "interview"),
        ("ASSESSMENT", "assessment"),
        ("OFFER", "offer decision"),
    ],
)
def test_every_active_state_produces_one_action(state, expect_fragment):
    action = compute_next_action(_app(state), fit=_fit(), now=NOW)
    assert expect_fragment.lower() in action.action.lower()
    assert action.rationale
    assert action.priority_score > 0


def test_terminal_state_rejected_by_engine():
    with pytest.raises(ValueError):
        compute_next_action(_app("REJECTED"), fit=_fit(), now=NOW)


# -- state-specific rules ---------------------------------------------------------


def test_reviewed_without_fit_asks_to_run_fit():
    a = compute_next_action(_app("REVIEWED"), fit=None, now=NOW)
    assert "fit analysis" in a.action


def test_reviewed_weak_fit_suggests_archive_decision():
    a = compute_next_action(_app("REVIEWED"), fit=_fit(band="Weak match"), now=NOW)
    assert "archive" in a.action.lower()


def test_preparing_missing_evidence_first():
    a = compute_next_action(
        _app("PREPARING"),
        fit=_fit(gaps=["Kubernetes", "Go"]),
        has_base_resume=True,
        has_tailored_resume=False,
        now=NOW,
    )
    assert a.action.startswith("Add evidence for")
    assert "Kubernetes" in a.action


def test_preparing_no_base_resume():
    a = compute_next_action(_app("PREPARING"), fit=_fit(), has_base_resume=False, now=NOW)
    assert "base resume" in a.action


def test_preparing_ready_to_finalize():
    a = compute_next_action(
        _app("PREPARING"), fit=_fit(), has_base_resume=True, has_tailored_resume=True, now=NOW
    )
    assert "Finalize" in a.action


def test_ready_to_apply_urgent_when_closing_soon():
    soon = compute_next_action(
        _app("READY_TO_APPLY"), fit=_fit(), closing_date=NOW.date() + timedelta(days=2), now=NOW
    )
    assert "URGENT" in soon.action
    far = compute_next_action(
        _app("READY_TO_APPLY"), fit=_fit(), closing_date=NOW.date() + timedelta(days=30), now=NOW
    )
    assert "URGENT" not in far.action


def test_applied_recently_awaits_then_follows_up():
    recent = _app("APPLIED", updated=NOW)
    a = compute_next_action(recent, fit=_fit(), now=NOW)
    assert a.action == "Await screening response"
    assert a.due_date == (NOW + timedelta(days=FOLLOW_UP_AFTER_DAYS)).date()
    old = _app("APPLIED", updated=NOW - timedelta(days=FOLLOW_UP_AFTER_DAYS + 1))
    a2 = compute_next_action(old, fit=_fit(), now=NOW)
    assert "follow-up" in a2.action.lower()
    assert a2.priority_score > a.priority_score  # overdue follow-up outranks waiting


# -- ranking ------------------------------------------------------------------------


def test_rank_orders_by_priority_score():
    acts = [
        NextAction(1, 1, "DISCOVERED", "a", "r", 2.0),
        NextAction(2, 2, "READY_TO_APPLY", "b", "r", 12.0),
        NextAction(3, 3, "REVIEWED", "c", "r", 5.0),
    ]
    ranked = rank_next_actions(acts)
    assert [a.opportunity_id for a in ranked] == [2, 3, 1]


def test_rank_breaks_ties_by_due_date():
    acts = [
        NextAction(1, 1, "READY_TO_APPLY", "a", "r", 10.0, due_date=date(2026, 11, 1)),
        NextAction(2, 2, "READY_TO_APPLY", "b", "r", 10.0, due_date=date(2026, 10, 20)),
    ]
    assert rank_next_actions(acts)[0].opportunity_id == 2


# -- store-level engine ------------------------------------------------------------


def test_next_actions_for_store_end_to_end(tmp_path):
    from careeros.opportunity import OpportunityStore
    from careeros.evidence import EvidenceStore, Evidence
    from careeros.application import ApplicationStore, DocumentStore
    from careeros.ingestion import ingest, StructuredImportAdapter

    opps = OpportunityStore(tmp_path / "db.duckdb")
    evs = EvidenceStore(tmp_path / "db.duckdb")
    apps = ApplicationStore(tmp_path / "db.duckdb")
    docs = DocumentStore(tmp_path / "db.duckdb")

    o1 = ingest(
        opps,
        StructuredImportAdapter(),
        {
            "role_title": "Python Developer",
            "description_raw": "Python SQL required.",
            "required_skills": ["Python", "SQL"],
            "closing_date": "2026-10-08",
        },
    )
    o2 = ingest(
        opps,
        StructuredImportAdapter(),
        {
            "role_title": "Rust Developer",
            "description_raw": "Rust required.",
            "required_skills": ["Rust"],
        },
    )
    evs.add(
        Evidence(
            evidence_id=0, type="employment", title="Dev", description="Python and SQL shop work."
        )
    )

    a1 = apps.create_for_opportunity(o1.opportunity_id)
    for st in ("REVIEWED", "SHORTLISTED", "PREPARING", "READY_TO_APPLY"):
        apps.transition(a1.application_id, st, trigger="user:test")
    apps.create_for_opportunity(o2.opportunity_id)

    actions = next_actions_for_store(apps, opps, evs, docs, now=NOW)
    assert len(actions) == 2
    # closing-soon READY_TO_APPLY outranks fresh DISCOVERED
    assert actions[0].state == "READY_TO_APPLY"
    assert actions[0].opportunity_id == o1.opportunity_id
    assert "URGENT" in actions[0].action  # closes in 3 days
    assert actions[1].state == "DISCOVERED"


def test_terminal_applications_excluded_from_board(tmp_path):
    from careeros.opportunity import OpportunityStore
    from careeros.evidence import EvidenceStore
    from careeros.application import ApplicationStore, DocumentStore
    from careeros.ingestion import ingest, StructuredImportAdapter

    opps = OpportunityStore(tmp_path / "db.duckdb")
    apps = ApplicationStore(tmp_path / "db.duckdb")
    ingest(opps, StructuredImportAdapter(), {"role_title": "X"})
    a = apps.create_for_opportunity(1)
    apps.transition(a.application_id, "WITHDRAWN", trigger="user:test")
    actions = next_actions_for_store(
        apps,
        opps,
        EvidenceStore(tmp_path / "db.duckdb"),
        DocumentStore(tmp_path / "db.duckdb"),
        now=NOW,
    )
    assert actions == []
