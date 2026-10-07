"""Tests: evidence-based resume generation + traceability (fake gateway, no API)."""

import json


from careeros.evidence import Evidence
from careeros.opportunity import Opportunity
from llm.features.evidence_resume import (
    TailorResult,
    extract_job_keywords,
    tailor_evidence_based,
    cover_letter_evidence_based,
    deterministic_keyword_alignment,
    _parse_footer,
    _validate,
    _EVIDENCE_FOOTER,
)


def _opp(**kw):
    base = dict(
        opportunity_id=1,
        source="manual",
        role_title="Data Engineer",
        company="Acme",
        description_raw="Python, SQL, AWS required. Kubernetes preferred.",
        required_skills=["Python", "SQL"],
        preferred_skills=["Kubernetes"],
    )
    base.update(kw)
    return Opportunity(**base)


def _evidence():
    return [
        Evidence(
            evidence_id=1,
            type="employment",
            verification_state="VERIFIED",
            title="Data Engineer",
            organization="Beta",
            description="Python, SQL, Airflow on AWS.",
            skills=["Python", "SQL"],
        ),
        Evidence(
            evidence_id=2,
            type="project",
            title="Migration",
            description="Docker rollout.",
            skills=["Docker"],
            verification_state="VERIFIED",
        ),
    ]


class FakeGateway:
    """Canned-response gateway stand-in (never calls a provider)."""

    def __init__(self, markdown="", footer=None):
        self.markdown = markdown
        self.footer = footer or {}
        self.calls = []

    def complete(self, messages, tier="interactive"):
        self.calls.append((messages, tier))
        footer = f"\n\n{_EVIDENCE_FOOTER}\n{json.dumps(self.footer)}"

        class _R:
            text = self.markdown + footer

        return _R()


# -- deterministic keyword extraction --------------------------------------------


def test_extract_job_keywords_explicit_first_then_description():
    kws = extract_job_keywords(_opp())
    assert kws[0] == "Python" and kws[1] == "SQL"  # explicit required first
    assert "Kubernetes" in kws  # explicit preferred
    assert "amazon web services" in kws  # extracted from description (canonical name)


# -- footer parsing (deterministic validation of model output) ----------------------


def test_parse_footer_valid():
    md, ids, excluded = _parse_footer(
        "resume text\n"
        + _EVIDENCE_FOOTER
        + '\n{"evidence_used": [1, 2], "excluded_claims": ["Kubernetes"]}'
    )
    assert md == "resume text"
    assert ids == [1, 2]
    assert excluded == ["Kubernetes"]


def test_parse_footer_missing_means_no_trusted_citations():
    md, ids, excluded = _parse_footer("resume without footer")
    assert md == "resume without footer"
    assert ids == [] and excluded == []


def test_parse_footer_malformed_json_degrades_safely():
    text = "resume\n" + _EVIDENCE_FOOTER + "\n{not json at all"
    md, ids, excluded = _parse_footer(text)
    assert ids == []
    assert md.startswith("resume")


def test_validate_drops_bogus_citations():
    result = TailorResult(
        markdown="m", evidence_used=[1, 99], excluded_claims=[], keywords=[], model_used=True
    )
    out = _validate(result, valid_ids={1, 2})
    assert out.evidence_used == [1]
    assert "99" in (out.notes or "")


# -- LLM-constrained generation (fake gateway) ---------------------------------------


def test_tailor_evidence_based_returns_validated_result():
    gw = FakeGateway(
        "# Tailored resume", footer={"evidence_used": [1], "excluded_claims": ["Kubernetes"]}
    )
    out = tailor_evidence_based("base resume", _opp(), _evidence(), gw)
    assert out.model_used is True
    assert out.markdown.startswith("# Tailored resume")
    assert out.evidence_used == [1]
    assert out.excluded_claims == ["Kubernetes"]
    assert "Python" in out.keywords
    # anti-fabrication + evidence ledger are in the prompt actually sent
    sent = gw.calls[0][0][0]["content"]
    assert "do NOT invent" in sent
    assert "[E1]" in sent and "[E2]" in sent


def test_tailor_drops_citations_not_in_ledger():
    gw = FakeGateway("resume", footer={"evidence_used": [1, 777], "excluded_claims": []})
    out = tailor_evidence_based("base resume", _opp(), _evidence(), gw)
    assert out.evidence_used == [1]
    assert 777 not in out.evidence_used
    assert "777" in (out.notes or "")


def test_cover_letter_evidence_based_same_traceability():
    gw = FakeGateway("Dear Acme,", footer={"evidence_used": [2], "excluded_claims": ["Python"]})
    out = cover_letter_evidence_based("base resume", _opp(), _evidence(), gw)
    assert out.evidence_used == [2]
    assert out.excluded_claims == ["Python"]


# -- deterministic no-key fallback -----------------------------------------------------


def test_fallback_never_claims_model_or_fake_tailoring():
    out = deterministic_keyword_alignment("Python and SQL developer", _opp(), _evidence())
    assert out.model_used is False
    assert "no LLM" in out.markdown
    # supported/excluded split is honest
    assert "Python" in out.keywords
    assert "Kubernetes" in out.excluded_claims
    assert "Python" not in out.excluded_claims


def test_fallback_evidence_ids_all_real():
    out = deterministic_keyword_alignment("Python SQL AWS", _opp(), _evidence())
    valid = {e.evidence_id for e in _evidence()}
    assert set(out.evidence_used) <= valid


def test_unsupported_claim_rejection_is_recorded():
    """The M1 contract: job keywords with no support end up in excluded_claims,
    never silently woven into the resume. Evidence-backed keywords remain
    citable even when the base resume never mentions them - that is the point
    of evidence-led tailoring - so evidence_used may be non-empty, but every
    cited ID must be real."""
    out = deterministic_keyword_alignment("totally unrelated history", _opp(), _evidence())
    assert out.excluded_claims  # something honestly excluded
    assert "Kubernetes" in out.excluded_claims
    valid = {e.evidence_id for e in _evidence()}
    assert set(out.evidence_used) <= valid
    # supported and excluded sets must be disjoint (no claim counted twice)
    supported = [k for k in out.keywords if k not in out.excluded_claims]
    assert not (set(supported) & set(out.excluded_claims))
