"""Tests: application questions (factual gating + narrative generation)."""

import pytest

from careeros.evidence import Evidence
from careeros.fit_engine import evaluate_fit
from careeros.opportunity import Opportunity
from careeros.questions import (
    QUESTION_BANK,
    QuestionStore,
    build_narrative_answer,
)


@pytest.fixture
def qs(tmp_path):
    return QuestionStore(tmp_path / "q.duckdb")


def _opp():
    return Opportunity(
        opportunity_id=1,
        source="t",
        role_title="Data Engineer",
        company="Acme",
        description_raw="Python SQL pipelines.",
        required_skills=["Python", "SQL"],
        preferred_skills=[],
    )


def _evidence():
    return [
        Evidence(
            evidence_id=1,
            type="employment",
            title="Data Engineer",
            description="Built Python/SQL pipelines.",
            skills=["Python", "SQL"],
        ),
    ]


# -- factual gating: user-confirmed only, work authorization never inferred ----


def test_factual_answer_is_user_text_only(qs):
    q = qs.set_factual(7, "work_authorization", "Canadian citizen - authorized to work in Canada")
    assert q.factual_answer.startswith("Canadian citizen")
    assert "user:confirmed" in q.provenance


def test_work_authorization_never_generated(qs):
    """The narrative generator must refuse work-authorization questions."""
    with pytest.raises(ValueError):
        qs.set_narrative(7, "work_authorization", "generated text")
    with pytest.raises(ValueError):
        build_narrative_answer(
            "work_authorization", _opp(), _evidence(), evaluate_fit(_opp(), _evidence())
        )


def test_narrative_not_allowed_on_factual_questions(qs):
    with pytest.raises(ValueError):
        qs.set_narrative(7, "salary_expectations", "$120k")


def test_unknown_question_key_rejected(qs):
    with pytest.raises(ValueError):
        qs.set_factual(7, "favorite_color", "blue")


def test_question_bank_has_the_required_keys():
    keys = {q["key"] for q in QUESTION_BANK}
    assert {
        "why_company",
        "why_role",
        "relevant_experience",
        "salary_expectations",
        "start_date",
        "work_authorization",
        "location_preferences",
    } <= keys
    wz = next(q for q in QUESTION_BANK if q["key"] == "work_authorization")
    assert wz["kind"] == "factual" and wz.get("never_infer") is True


# -- narrative generation (deterministic, evidence-cited) ------------------------


def test_narrative_deterministic_scaffold_cites_evidence(qs):
    opp, ev = _opp(), _evidence()
    fit = evaluate_fit(opp, ev)
    result = build_narrative_answer("why_role", opp, ev, fit)
    assert result["model_used"] is False
    assert result["evidence_used"]  # cited some evidence
    valid = {e.evidence_id for e in ev}
    assert set(result["evidence_used"]) <= valid
    assert result["markdown"].strip()


def test_narrative_excluded_claims_recorded(qs):
    opp, ev = _opp(), _evidence()
    fit = evaluate_fit(opp, ev)
    result = build_narrative_answer("why_company", opp, ev, fit)
    # anything the fit flagged as a genuine gap must land in excluded_claims
    assert set(g.skill for g in fit.gaps) <= set(result["excluded_claims"])


def test_set_narrative_persists_traceability(qs):
    opp, ev = _opp(), _evidence()
    fit = evaluate_fit(opp, ev)
    result = build_narrative_answer("relevant_experience", opp, ev, fit)
    q = qs.set_narrative(
        5,
        "relevant_experience",
        result["markdown"],
        evidence_used=result["evidence_used"],
        excluded_claims=result["excluded_claims"],
    )
    assert q.evidence_used == result["evidence_used"]
    assert q.excluded_claims == result["excluded_claims"]
    assert q.status == "draft"


def test_approve_marks_ready(qs):
    qs.set_factual(5, "start_date", "2026-11-01")
    q = qs.approve(5, "start_date", provenance="user:test")
    assert q.status == "approved"
    assert "user:test" in q.provenance


def test_list_for_application(qs):
    qs.set_factual(9, "salary_expectations", "$120k-$140k")
    qs.set_factual(9, "start_date", "immediately")
    items = qs.list_for_application(9)
    assert len(items) == 2
    assert all(i.application_id == 9 for i in items)
