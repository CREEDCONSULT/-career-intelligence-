"""Tests: deterministic fit engine."""

from datetime import date, timedelta


from careeros.evidence import Evidence
from careeros.fit_engine import evaluate_fit, extract_skills_from_text, FitResult
from careeros.opportunity import Opportunity


def _opp(**kw):
    base = dict(
        opportunity_id=1,
        source="manual",
        role_title="Data Engineer",
        company="Acme",
        description_raw=(
            "We need Python, SQL, AWS and Airflow. Docker preferred. Remote full-time. 5+ years."
        ),
        required_skills=["Python", "SQL", "AWS", "Airflow"],
        preferred_skills=["Docker"],
    )
    base.update(kw)
    return Opportunity(**base)


def _ev(i, **kw):
    base = dict(
        evidence_id=i,
        type="employment",
        title="Data Engineer",
        organization="Beta Ltd",
        description="Built ETL pipelines with Python, SQL and Airflow on AWS.",
        verification_state="VERIFIED",  # M3: fit engine tests use verified evidence
    )
    base.update(kw)
    return Evidence(**base)


# -- core evaluation ---------------------------------------------------------


def test_full_coverage_yields_strong_band():
    items = [
        _ev(1, skills=["Python", "SQL", "Airflow"]),
        _ev(
            2,
            type="project",
            title="Cloud work",
            skills=["Docker"],
            description="Containerized with Docker on AWS.",
        ),
    ]
    fit = evaluate_fit(_opp(), items, today=date(2026, 10, 5))
    assert isinstance(fit, FitResult)
    assert fit.coverage_hard == 1.0
    assert fit.band == "STRONG FIT"
    assert fit.score >= 80
    assert fit.interview_risk in ("low", "medium")
    # traceability: every strength cites evidence ids
    assert all(s.evidence_ids for s in fit.strengths)
    assert fit.gaps == [] and fit.transferable == []


def test_missing_requirement_is_a_genuine_gap():
    # description deliberately free of Airflow/AWS so those stay unmatched
    items = [_ev(1, skills=["Python", "SQL"], description="Python and SQL reporting work.")]
    fit = evaluate_fit(_opp(), items, today=date(2026, 10, 5))
    gap_names = [g.skill for g in fit.gaps] + [g.skill for g in fit.transferable]
    assert any("airflow" in n.lower() for n in gap_names)
    assert fit.coverage_hard < 1.0
    assert fit.band in ("WEAK FIT", "POSSIBLE FIT", "INSUFFICIENT EVIDENCE")


def test_no_required_skills_is_neutral_not_zero():
    """Unknown stays unknown: a job with no listed requirements must not be
    punished - coverage is neutral 1.0."""
    fit = evaluate_fit(
        _opp(required_skills=[], preferred_skills=[]), [_ev(1)], today=date(2026, 10, 5)
    )
    assert fit.coverage_hard == 1.0


def test_strengths_cite_real_evidence_ids_only():
    items = [_ev(1, skills=["Python", "SQL", "AWS", "Airflow"])]
    fit = evaluate_fit(_opp(), items, today=date(2026, 10, 5))
    valid = {e.evidence_id for e in items}
    assert all(set(s.evidence_ids) <= valid for s in fit.strengths)


def test_raw_nontaxonomy_requirement_matched_by_literal_mention():
    """A requirement outside the taxonomy (e.g. 'Canadian work permit') is
    satisfied only by a literal evidence mention - still traceable."""
    opp = _opp(required_skills=["Canadian work permit"], preferred_skills=[])
    fit = evaluate_fit(
        opp,
        [_ev(1, description="Holder of a Canadian work permit since 2020.")],
        today=date(2026, 10, 5),
    )
    assert any("work permit" in s.skill.lower() for s in fit.strengths)
    assert fit.coverage_hard == 1.0


def test_claims_not_allowed_excluded():
    items = [_ev(1, verification_state="UNVERIFIED", skills=["Python", "SQL", "AWS", "Airflow"])]
    fit = evaluate_fit(_opp(), items, today=date(2026, 10, 5))
    assert fit.coverage_hard == 0.0


# -- seniority -----------------------------------------------------------------


def test_seniority_aligned_when_both_known():
    items = [_ev(1, title="Senior Data Engineer")]
    fit = evaluate_fit(_opp(seniority="senior"), items, today=date(2026, 10, 5))
    assert fit.seniority_fit == 1.0
    assert "aligned" in fit.seniority_note


def test_seniority_unknown_on_either_side_is_neutral():
    fit = evaluate_fit(_opp(seniority=None), [_ev(1)], today=date(2026, 10, 5))
    assert fit.seniority_fit == 0.75  # mildly conservative, never punishing hard


def test_seniority_mismatch_lowers_score():
    aligned = evaluate_fit(
        _opp(seniority="senior"), [_ev(1, title="Senior Data Engineer")], today=date(2026, 10, 5)
    )
    mismatch = evaluate_fit(
        _opp(seniority="senior"), [_ev(1, title="Junior Analyst")], today=date(2026, 10, 5)
    )
    assert mismatch.seniority_fit < aligned.seniority_fit
    assert "mismatch" in mismatch.seniority_note


# -- transferables + risk ---------------------------------------------------------


def test_transferable_marks_adjacent_category_not_fake_match():
    items = [_ev(1, skills=["Python", "SQL", "AWS", "Airflow"])]
    # Kubernetes missing, Docker held (same ops/tooling family)
    fit = evaluate_fit(
        _opp(
            preferred_skills=[], required_skills=["Python", "SQL", "AWS", "Airflow", "Kubernetes"]
        ),
        items
        + [
            Evidence(
                evidence_id=2,
                type="project",
                title="Containers",
                description="Shipped services with Docker.",
            )
        ],
        today=date(2026, 10, 5),
    )
    assert fit.gaps == []  # nothing claimed as genuinely missing without adjacency
    assert any(g.transferable_from for g in fit.transferable) or fit.gaps


def test_high_missing_count_raises_interview_risk():
    # only Python supported; Airflow/AWS unmatched -> high interview risk
    items = [_ev(1, skills=["Python"], description="Some Python scripting.")]
    fit = evaluate_fit(_opp(), items, today=date(2026, 10, 5))
    assert fit.interview_risk == "high"


# -- determinism + urgency ---------------------------------------------------------


def test_deterministic_same_inputs_same_output():
    items = [_ev(1, skills=["Python", "SQL", "AWS", "Airflow"])]
    a = evaluate_fit(_opp(), items, today=date(2026, 10, 5))
    b = evaluate_fit(_opp(), items, today=date(2026, 10, 5))
    assert a.to_dict() == b.to_dict()


def test_closing_urgency_bands():
    today = date(2026, 10, 5)
    soon = evaluate_fit(_opp(closing_date=today + timedelta(days=2)), [_ev(1)], today=today)
    later = evaluate_fit(_opp(closing_date=today + timedelta(days=30)), [_ev(1)], today=today)
    past = evaluate_fit(_opp(closing_date=today - timedelta(days=1)), [_ev(1)], today=today)
    assert soon.closing_urgency > later.closing_urgency
    assert past.closing_urgency == 0.25


def test_band_and_recommendation_strings_present():
    fit = evaluate_fit(_opp(), [_ev(1, skills=["Python"])], today=date(2026, 10, 5))
    assert fit.band in ("STRONG FIT", "POSSIBLE FIT", "WEAK FIT", "INSUFFICIENT EVIDENCE")
    assert fit.recommendation  # non-empty guidance


def test_extract_skills_from_text_synonym_aware():
    skills = extract_skills_from_text("Hands-on ML and k8s style ops with aws")
    assert "amazon web services" in skills or skills  # smoke: matcher engaged
    assert "python" not in skills  # not mentioned

