"""Tests: interview prep pack (evidence-grounded, no invention) + NBA updates."""

from datetime import datetime, timedelta

import pytest

from careeros.application import Application, ApplicationState, ApplicationStore, DocumentStore
from careeros.evidence import Evidence
from careeros.fit_engine import evaluate_fit
from careeros.interviews import InterviewStore
from careeros.next_action import compute_next_action, next_actions_for_store
from careeros.opportunity import Opportunity, OpportunityStore
from careeros.evidence import EvidenceStore
from llm.features.interview_prep import build_prep_pack, STAGE_THEMES


def _opp(**kw):
    base = dict(
        opportunity_id=1,
        source="manual",
        role_title="Senior Analytics Engineer",
        company="Northwind",
        location="Toronto",
        work_mode="hybrid",
        employment_type="full-time",
        seniority="senior",
        salary_min=120000.0,
        salary_max=145000.0,
        currency="CAD",
        description_raw=(
            "We need Python, SQL and Airflow. dbt and Docker are a plus. "
            "You will own the warehouse roadmap."
        ),
        required_skills=["Python", "SQL", "Airflow"],
        preferred_skills=["dbt", "Docker"],
    )
    base.update(kw)
    return Opportunity(**base)


def _evidence():
    return [
        Evidence(
            evidence_id=1,
            type="employment",
            title="Analytics Engineer",
            organization="Old Co",
            start_date="2020-01-01",
            end_date="2024-05-01",
            description="Built Python/SQL pipelines in Airflow.",
            metrics=[{"value": "40", "unit": "%", "context": "faster refreshes"}],
            skills=["Python", "SQL", "Airflow"],
        ),
        Evidence(
            evidence_id=2,
            type="project",
            title="dbt migration",
            description="Rebuilt warehouse with dbt and Docker.",
            skills=["dbt", "Docker"],
        ),
        Evidence(
            evidence_id=3,
            type="certification",
            title="Secret cert",
            description="must never be cited",
            claims_allowed=False,
        ),
    ]


# -- prep pack (deterministic base) ----------------------------------------------


def test_prep_pack_sections_present():
    fit = evaluate_fit(_opp(), _evidence())
    pack = build_prep_pack(_opp(), _evidence(), fit, stage="technical_case")
    md = pack.markdown
    for section in (
        "Company / role summary",
        "competency themes",
        "STAR",
        "Questions to ask them",
        "Gaps & risks",
        "Salary / negotiation",
    ):
        assert section.lower() in md.lower(), f"missing section: {section}"


def test_prep_pack_cites_only_real_evidence():
    fit = evaluate_fit(_opp(), _evidence())
    pack = build_prep_pack(_opp(), _evidence(), fit)
    valid = {1, 2}  # E3 has claims_allowed=False
    assert set(pack.evidence_used) <= valid
    assert 3 not in pack.evidence_used


def test_prep_pack_no_invented_company_facts():
    fit = evaluate_fit(_opp(), _evidence())
    pack = build_prep_pack(_opp(), _evidence(), fit)
    # the only company text allowed comes from the record itself
    assert "Northwind" in pack.markdown
    # no fabricated "About" beyond the record: description text is quoted, not expanded
    assert "founded in" not in pack.markdown.lower()
    assert "mission statement" not in pack.markdown.lower()


def test_prep_pack_salary_context_from_record_only():
    fit = evaluate_fit(_opp(), _evidence())
    pack = build_prep_pack(_opp(), _evidence(), fit)
    assert "120000.0" in pack.markdown or "120,000" in pack.markdown or "120000" in pack.markdown
    opp_no_salary = _opp(salary_min=None, salary_max=None, currency=None)
    pack2 = build_prep_pack(opp_no_salary, _evidence(), fit)
    assert "No posted range" in pack2.markdown


def test_prep_pack_stage_themes():
    fit = evaluate_fit(_opp(), _evidence())
    pack = build_prep_pack(_opp(), _evidence(), fit, stage="recruiter_screen")
    for theme in STAGE_THEMES["recruiter_screen"][:3]:
        assert theme in pack.markdown


def test_prep_pack_gaps_come_from_fit():
    fit = evaluate_fit(_opp(), [])  # nothing supported -> everything missing
    pack = build_prep_pack(_opp(), [], fit)
    assert pack.excluded_claims  # gap skills recorded as watch-outs
    for g in fit.gaps[:3]:
        assert g.skill in pack.markdown  # surfaced as questions to expect


# -- prep pack LLM polish (fake gateway) ------------------------------------------


class FakeGW:
    def complete(self, messages, tier="interactive"):
        class _R:
            text = (
                "Polished pack with citations [E1] [E2].\n\n===EVIDENCE-JSON===\n"
                '{"evidence_used": [1, 2], "excluded_claims": []}'
            )

        return _R()


def test_prep_pack_llm_polish_validates_citations():
    fit = evaluate_fit(_opp(), _evidence())
    pack = build_prep_pack(_opp(), _evidence(), fit, gw=FakeGW())
    assert pack.model_used is True
    assert set(pack.evidence_used) <= {1, 2}
    assert "[E1]" in pack.markdown


class BadFakeGW:
    def complete(self, messages, tier="interactive"):
        class _R:
            text = (
                "Pack citing [E99].\n\n===EVIDENCE-JSON===\n"
                '{"evidence_used": [99], "excluded_claims": []}'
            )

        return _R()


def test_prep_pack_drops_bogus_citations():
    fit = evaluate_fit(_opp(), _evidence())
    pack = build_prep_pack(_opp(), _evidence(), fit, gw=BadFakeGW())
    assert 99 not in pack.evidence_used
    assert "99" in (pack.notes or "")


class BrokenGW:
    def complete(self, messages, tier="interactive"):
        raise RuntimeError("provider down")


def test_prep_pack_falls_back_when_provider_fails():
    fit = evaluate_fit(_opp(), _evidence())
    pack = build_prep_pack(_opp(), _evidence(), fit, gw=BrokenGW())
    assert pack.model_used is False
    assert pack.markdown  # deterministic base survives


# -- NBA interview-aware actions -------------------------------------------------------

NOW = datetime(2026, 10, 5, 12, 0)


def _app(state, opp_id=1, app_id=1):
    return Application(
        application_id=app_id,
        opportunity_id=opp_id,
        current_state=state,
        created_at=None,
        updated_at=NOW,
    )


def test_nba_interview_action_is_stage_specific():
    iv = type(
        "IV",
        (),
        {
            "stage": "technical_case",
            "scheduled_at": datetime(2026, 10, 8, 14, 0),
            "prep_status": "not_started",
        },
    )()
    action = compute_next_action(_app("INTERVIEW"), fit=None, upcoming_interview=iv, now=NOW)
    assert "technical case" in action.action.lower()
    assert action.due_date == datetime(2026, 10, 8, 14, 0).date()


def test_nba_past_interview_asks_to_record_outcome():
    iv = type(
        "IV",
        (),
        {
            "stage": "hiring_manager",
            "scheduled_at": datetime(2026, 10, 3, 14, 0),
            "prep_status": "ready",
        },
    )()
    action = compute_next_action(_app("INTERVIEW"), fit=None, upcoming_interview=iv, now=NOW)
    assert "record the outcome" in action.action.lower()


def test_nba_generic_interview_action_without_schedule():
    action = compute_next_action(_app("INTERVIEW"), fit=None, upcoming_interview=None, now=NOW)
    assert "interview" in action.action.lower()
    # generic, not stage-specific (no named stage like "recruiter screen")
    for stage_word in ("recruiter", "technical case", "hiring manager", "panel"):
        assert stage_word not in action.action.lower()


def test_nba_store_level_uses_interviews(tmp_path):
    db = tmp_path / "nba.duckdb"
    opps = OpportunityStore(db)
    evs = EvidenceStore(db)
    apps = ApplicationStore(db)
    docs = DocumentStore(db)
    ivs = InterviewStore(db)

    from careeros.ingestion import ingest, ManualPasteAdapter

    opp = ingest(opps, ManualPasteAdapter(), "Data Engineer at Acme\nPython SQL required. remote")
    evs.add(
        Evidence(
            evidence_id=0,
            type="employment",
            title="Dev",
            description="Python SQL",
            skills=["Python", "SQL"],
        )
    )
    app = apps.create_for_opportunity(opp.opportunity_id)
    for st in (
        "REVIEWED",
        "SHORTLISTED",
        "PREPARING",
        "READY_TO_APPLY",
        "APPLIED",
        "SCREENING",
        "INTERVIEW",
    ):
        apps.transition(app.application_id, st, trigger="user:test")
    ivs.schedule(
        app.application_id, "recruiter_screen", "INTERVIEW", scheduled_at=NOW + timedelta(days=2)
    )

    board = next_actions_for_store(apps, opps, evs, docs, interview_store=ivs, now=NOW)
    assert len(board) == 1
    assert "recruiter screen" in board[0].action.lower()
    assert board[0].due_date == (NOW + timedelta(days=2)).date()


def test_creed_store_boundary(tmp_path):
    from careeros.creed_store import NullCreedStore, OpportunitySummary

    store = NullCreedStore()
    summary = OpportunitySummary.from_opportunity(_opp())
    assert store.publish_opportunity(summary) is False  # honest: not synced
    from careeros.outcomes import ApplicationOutcome

    out = ApplicationOutcome(
        outcome_id=1,
        application_id=1,
        opportunity_id=1,
        final_state="REJECTED",
        outcome_type="rejected",
    )
    assert store.publish_outcome(out) is False
