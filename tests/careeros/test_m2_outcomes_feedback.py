"""Tests: outcomes derivation, analytics, low-sample labeling, profile feedback."""

from datetime import datetime, timedelta

import pytest

from careeros.application import ApplicationStore, DocumentStore, ApplicationState
from careeros.evidence import Evidence, EvidenceStore
from careeros.ingestion import ingest, ManualPasteAdapter
from careeros.opportunity import OpportunityStore
from careeros.outcomes import OutcomeStore, outcome_analytics, MIN_SAMPLE
from careeros.pipeline import role_family
from careeros.profile_feedback import propose_profile_updates
from careeros.fit_engine import evaluate_fit


def _seed_app(
    db, states, opp_title="Data Engineer at Acme\nPython SQL required.", source_payload=None
):
    opps = OpportunityStore(db)
    apps = ApplicationStore(db)
    opp = ingest(
        opps, ManualPasteAdapter(), source_payload or "Data Engineer at Acme\nPython SQL required."
    )
    app = apps.create_for_opportunity(opp.opportunity_id)
    for st in states:
        app = apps.transition(app.application_id, st, trigger="user:test")
    return opps, apps, opp, app


# -- outcome derivation from the event log -------------------------------------


def test_outcome_derived_from_event_log(tmp_path):
    db = tmp_path / "o.duckdb"
    opps, apps, opp, app = _seed_app(
        db,
        [
            "REVIEWED",
            "SHORTLISTED",
            "PREPARING",
            "READY_TO_APPLY",
            "APPLIED",
            "SCREENING",
            "INTERVIEW",
            "REJECTED",
        ],
    )
    outcomes = OutcomeStore(db)
    fit = evaluate_fit(opp, [])
    out = outcomes.record_from_application(
        app,
        apps,
        opp,
        fit.band,
        resume_version=1,
        cover_letter_version=None,
        role_family=role_family(opp),
    )
    assert out.outcome_type == "rejected"
    assert out.final_state == "REJECTED"
    assert out.fit_band == fit.band
    assert out.first_response_days is not None and out.first_response_days >= 0
    assert out.days_to_outcome is not None
    assert out.source == opp.source
    assert out.provenance == "derived:event-log"


def test_outcome_rejects_non_terminal(tmp_path):
    db = tmp_path / "o.duckdb"
    opps, apps, opp, app = _seed_app(db, ["REVIEWED"])
    with pytest.raises(ValueError):
        OutcomeStore(db).record_from_application(app, apps, opp, None, None, None, None)


def test_outcome_offer_via_closed(tmp_path):
    db = tmp_path / "o.duckdb"
    opps, apps, opp, app = _seed_app(
        db,
        [
            "REVIEWED",
            "SHORTLISTED",
            "PREPARING",
            "READY_TO_APPLY",
            "APPLIED",
            "SCREENING",
            "INTERVIEW",
            "OFFER",
            "CLOSED",
        ],
    )
    out = OutcomeStore(db).record_from_application(
        app,
        apps,
        opp,
        "POSSIBLE FIT",
        1,
        1,
        role_family(opp),
        provenance="derived:event-log | offer accepted",
    )
    assert out.outcome_type == "closed"


def test_no_response_override_is_explicit_only(tmp_path):
    db = tmp_path / "o.duckdb"
    opps, apps, opp, app = _seed_app(
        db, ["REVIEWED", "SHORTLISTED", "PREPARING", "READY_TO_APPLY", "APPLIED", "WITHDRAWN"]
    )
    out = OutcomeStore(db).record_from_application(
        app,
        apps,
        opp,
        "WEAK FIT",
        2,
        None,
        role_family(opp),
        outcome_type_override="no_response",
        provenance="user:explicit",
    )
    assert out.outcome_type == "no_response"
    assert "user:explicit" in out.provenance


def test_find_by_application(tmp_path):
    db = tmp_path / "o.duckdb"
    opps, apps, opp, app = _seed_app(db, ["WITHDRAWN"])
    store = OutcomeStore(db)
    o = store.record_from_application(app, apps, opp, None, None, None, None)
    assert store.find_by_application(app.application_id).outcome_id == o.outcome_id


# -- analytics + low-sample honesty ----------------------------------------------


def _mk_outcome(
    i,
    outcome_type,
    fit_band="POSSIBLE FIT",
    source="manual",
    resume_version=1,
    role_family="data",
    resp_days=7,
):
    from careeros.outcomes import ApplicationOutcome

    return ApplicationOutcome(
        outcome_id=i,
        application_id=i,
        opportunity_id=i,
        final_state="REJECTED" if outcome_type == "rejected" else "CLOSED",
        outcome_type=outcome_type,
        first_response_days=resp_days,
        days_to_outcome=resp_days + 5,
        fit_band=fit_band,
        resume_version=resume_version,
        cover_letter_version=1,
        source=source,
        role_family=role_family,
        recorded_at=datetime(2026, 10, 5),
        provenance="test",
    )


def test_analytics_low_sample_labeled():
    outcomes = [_mk_outcome(1, "rejected"), _mk_outcome(2, "offer")]
    report = outcome_analytics(outcomes)
    overall = report["metrics"]["overall"]
    assert overall["response_rate"].rate is None
    assert "insufficient sample" in (overall["response_rate"].sample_note or "")


def test_anitics_enough_samples_show_rates():
    outcomes = [_mk_outcome(i, "rejected") for i in range(1, 8)] + [_mk_outcome(10, "offer")]
    report = outcome_analytics(outcomes)
    overall = report["metrics"]["overall"]
    assert overall["response_rate"].rate is not None
    assert overall["offer_rate"].rate == round(1 / 8, 3)
    assert overall["offer_rate"].numerator == 1
    assert overall["offer_rate"].denominator == 8


def test_analytics_by_fit_band_and_source():
    outcomes = [
        _mk_outcome(i, "rejected", fit_band="INSUFFICIENT EVIDENCE", source="jobbank") for i in range(1, 6)
    ] + [_mk_outcome(i, "offer", fit_band="STRONG FIT", source="manual") for i in range(11, 16)]
    report = outcome_analytics(outcomes)
    by_band = report["metrics"]["by_fit_band"]
    assert set(by_band.keys()) == {"INSUFFICIENT EVIDENCE", "STRONG FIT"}
    by_source = report["metrics"]["by_source"]
    assert set(by_source.keys()) == {"jobbank", "manual"}
    # each bucket has n>=5 so rates are computed, not labeled
    assert by_band["INSUFFICIENT EVIDENCE"]["response_rate"].rate is not None


def test_analytics_empty_is_honest():
    report = outcome_analytics([])
    assert report["total_outcomes"] == 0
    assert "No outcomes recorded" in report["note"]


def test_days_to_response_stats():
    outcomes = [
        _mk_outcome(i, "rejected", resp_days=d) for i, d in enumerate([3, 5, 7, 9], start=1)
    ]
    report = outcome_analytics(outcomes)
    stats = report["metrics"]["days_to_first_response"]
    assert stats["n"] == 4
    assert stats["min"] == 3 and stats["max"] == 9
    assert "insufficient sample" in (stats["sample_note"] or "")


# -- profile feedback (proposals only) -----------------------------------------------


def test_profile_feedback_proposes_recurring_gaps():
    from careeros.opportunity import Opportunity

    opp1 = Opportunity(
        opportunity_id=1,
        source="t",
        role_title="Data Engineer",
        required_skills=["Python", "Kubernetes", "Kafka"],
    )
    opp2 = Opportunity(
        opportunity_id=2,
        source="t",
        role_title="Platform Engineer",
        required_skills=["Kubernetes", "Kafka"],
    )
    ev = [
        Evidence(
            evidence_id=1,
            type="employment", verification_state="VERIFIED",
            title="Dev",
            description="Python work",
            skills=["Python"],
        )
    ]
    fits = [evaluate_fit(o, ev) for o in (opp1, opp2)]
    suggestions = propose_profile_updates([opp1, opp2], fits, ev)
    kinds = [s.kind for s in suggestions]
    assert "skill_gap" in kinds
    gap = next(s for s in suggestions if s.kind == "skill_gap")
    assert "kubernetes" in gap.title.lower() or "kafka" in gap.title.lower()
    assert "2" in gap.evidence_note  # cites the recurrence count


def test_profile_feedback_never_mutates():
    """The module returns proposals; nothing here writes to any store."""
    from careeros.opportunity import Opportunity

    opp = Opportunity(
        opportunity_id=1,
        source="t",
        role_title="Data Engineer",
        required_skills=["Python", "Python", "Python"],
    )
    ev = [
        Evidence(
            evidence_id=1, type="employment", title="Dev", description="Python", skills=["Python"]
        )
    ]
    fits = [evaluate_fit(opp, ev)]
    before = opp.status
    propose_profile_updates([opp], fits, ev)
    assert opp.status == before  # untouched


def test_single_occurrence_not_proposed():
    from careeros.opportunity import Opportunity

    opp = Opportunity(
        opportunity_id=1, source="t", role_title="X", required_skills=["Quantum Computing"]
    )
    ev = [
        Evidence(
            evidence_id=1, type="employment", title="Dev", description="Python", skills=["Python"]
        )
    ]
    fits = [evaluate_fit(opp, ev)]
    suggestions = propose_profile_updates([opp], fits, ev)
    assert all(s.kind != "skill_gap" for s in suggestions)


def test_winning_evidence_and_requested_strength_proposed():
    from careeros.opportunity import Opportunity

    opp1 = Opportunity(
        opportunity_id=1, source="t", role_title="Data Engineer", required_skills=["Python", "SQL"]
    )
    opp2 = Opportunity(
        opportunity_id=2, source="t", role_title="Analyst", required_skills=["Python", "SQL"]
    )
    ev = [
        Evidence(
            evidence_id=1,
            type="employment", verification_state="VERIFIED",
            title="Data platform lead",
            description="Python and SQL pipelines",
            skills=["Python", "SQL"],
        )
    ]
    fits = [evaluate_fit(o, ev) for o in (opp1, opp2)]
    suggestions = propose_profile_updates([opp1, opp2], fits, ev)
    kinds = [s.kind for s in suggestions]
    assert "requested_skill" in kinds
    assert "winning_evidence" in kinds


