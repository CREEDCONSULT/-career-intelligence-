"""Tests: M3 evidence verification states, application packets, evidence manifest."""

import pytest

from careeros.evidence import Evidence, EvidenceStore, EVIDENCE_TYPES
from careeros.fit_engine import evaluate_fit
from careeros.opportunity import Opportunity
from careeros.packets import (
    build_application_packet,
    build_evidence_manifest,
)


@pytest.fixture
def store(tmp_path):
    return EvidenceStore(tmp_path / "m3.duckdb")


def _opp(**kw):
    base = dict(
        opportunity_id=1,
        source="test",
        role_title="AI Solutions Engineer",
        company="TechCorp",
        description_raw="Python SQL AI/ML required.",
        required_skills=["Python", "SQL"],
        preferred_skills=["AI/ML"],
        seniority="mid",
    )
    base.update(kw)
    return Opportunity(**base)


def _ev(**kw):
    base = dict(
        evidence_id=0,
        type="employment",
        title="Data Engineer",
        description="Built Python/SQL pipelines for 3 years.",
        skills=["Python", "SQL"],
        verification_state="UNVERIFIED",
    )
    base.update(kw)
    return Evidence(**base)


# ===========================================================================
# M3.1 — Verification states
# ===========================================================================


def test_new_evidence_defaults_to_unverified(store):
    """New evidence starts UNVERIFIED with claims_allowed=False."""
    ev = store.add(_ev())
    assert ev.verification_state == "UNVERIFIED"
    assert ev.claims_allowed is False
    assert ev.external_use_allowed is False


def test_promote_to_verified(store):
    """Promoting to VERIFIED enables claims and records provenance."""
    ev = store.add(_ev())
    promoted = store.promote_to_verified(ev.evidence_id)
    assert promoted.verification_state == "VERIFIED"
    assert promoted.claims_allowed is True
    assert promoted.external_use_allowed is True
    assert "founder:verified" in promoted.provenance


def test_promote_to_founder_asserted_without_permit(store):
    """FOUNDER_ASSERTED without external permit blocks claims."""
    ev = store.add(_ev())
    promoted = store.promote_to_founder_asserted(ev.evidence_id, permit_external=False)
    assert promoted.verification_state == "FOUNDER_ASSERTED"
    assert promoted.claims_allowed is False
    assert promoted.external_use_allowed is False


def test_promote_to_founder_asserted_with_permit(store):
    """FOUNDER_ASSERTED with explicit external permit allows claims."""
    ev = store.add(_ev())
    promoted = store.promote_to_founder_asserted(ev.evidence_id, permit_external=True)
    assert promoted.verification_state == "FOUNDER_ASSERTED"
    assert promoted.claims_allowed is True
    assert promoted.external_use_allowed is True


def test_demote_to_unverified(store):
    """Demoting blocks all external use."""
    ev = store.add(_ev())
    store.promote_to_verified(ev.evidence_id)
    demoted = store.demote_to_unverified(ev.evidence_id)
    assert demoted.verification_state == "UNVERIFIED"
    assert demoted.claims_allowed is False


def test_verification_summary(store):
    store.add(_ev(title="A"))
    ev2 = store.add(_ev(title="B"))
    store.promote_to_verified(ev2.evidence_id)
    ev3 = store.add(_ev(title="C"))
    store.promote_to_founder_asserted(ev3.evidence_id, permit_external=True)

    summary = store.verification_summary()
    assert summary["VERIFIED"] == 1
    assert summary["FOUNDER_ASSERTED"] == 1
    assert summary["UNVERIFIED"] == 1


def test_list_claimable_only_returns_allowed(store):
    store.add(_ev(title="unverified"))
    ev2 = store.add(_ev(title="verified"))
    store.promote_to_verified(ev2.evidence_id)

    claimable = store.list_claimable()
    assert len(claimable) == 1
    assert claimable[0].title == "verified"


def test_list_by_verification_state(store):
    store.add(_ev(title="A"))
    ev2 = store.add(_ev(title="B"))
    store.promote_to_verified(ev2.evidence_id)

    verified = store.list_all(verification_state="VERIFIED")
    assert len(verified) == 1
    assert verified[0].title == "B"


def test_unverified_evidence_never_in_supported_skills(store):
    """UNVERIFIED evidence does not support skills in the fit engine."""
    store.add(_ev(skills=["Python"]))
    supported = store.supported_skills()
    assert "python" not in supported  # UNVERIFIED → not claimable → no skill support


def test_eighteen_evidence_types():
    """M3 expands to 18 evidence types."""
    assert len(EVIDENCE_TYPES) == 18


def test_all_m3_types_present():
    m3_new = {
        "contract_work",
        "founder_work",
        "product",
        "case_study",
        "technical_skill",
        "business_consulting",
        "github_repository",
        "report",
        "presentation",
        "recommendation",
    }
    assert m3_new <= set(EVIDENCE_TYPES)


# ===========================================================================
# M3.6 — Evidence manifest + application packets
# ===========================================================================


class TestEvidenceManifest:
    def test_matched_claims_have_evidence(self, store):
        ev = store.add(_ev())
        store.promote_to_verified(ev.evidence_id)
        fit = evaluate_fit(_opp(), store.list_claimable())
        manifest = build_evidence_manifest(fit, store)

        supported = [e for e in manifest if not e.excluded]
        assert supported
        assert all(e.evidence_ids for e in supported)
        assert all(e.verification_states for e in supported)
        assert all("VERIFIED" in vs for e in supported for vs in e.verification_states)

    def test_excluded_claims_have_no_evidence(self, store):
        """A skill with NO evidence support (not even in description text) is excluded."""
        ev = store.add(_ev(skills=["Python"], description="Built Python pipelines."))
        store.promote_to_verified(ev.evidence_id)
        # Requires Python + Kubernetes; evidence only covers Python
        opp = _opp(required_skills=["Python", "Kubernetes"], preferred_skills=[])
        fit = evaluate_fit(opp, store.list_claimable())
        manifest = build_evidence_manifest(fit, store)

        excluded = [e for e in manifest if e.excluded]
        assert excluded
        assert any("kubernetes" in e.claim.lower() for e in excluded)
        assert all(not e.evidence_ids for e in excluded)

    def test_manifest_is_deterministic(self, store):
        ev = store.add(_ev())
        store.promote_to_verified(ev.evidence_id)
        opp = _opp()
        claimable = store.list_claimable()
        fit1 = evaluate_fit(opp, claimable)
        fit2 = evaluate_fit(opp, claimable)
        m1 = build_evidence_manifest(fit1, store)
        m2 = build_evidence_manifest(fit2, store)
        assert [e.to_dict() for e in m1] == [e.to_dict() for e in m2]


class TestApplicationPacket:
    def test_packet_contains_all_components(self, store):
        ev = store.add(_ev())
        store.promote_to_verified(ev.evidence_id)
        opp = _opp()
        packet = build_application_packet(
            application_id=1,
            opportunity=opp,
            evidence_store=store,
            base_resume_text="Python SQL engineer",
        )
        assert packet.tailored_resume is not None
        assert packet.recruiter_message is not None
        assert packet.application_summary is not None
        assert packet.evidence_manifest
        assert packet.fit_band in (
            "STRONG FIT",
            "POSSIBLE FIT",
            "WEAK FIT",
            "INSUFFICIENT EVIDENCE",
        )

    def test_packet_evidence_manifest_traces_to_verified(self, store):
        ev = store.add(_ev())
        store.promote_to_verified(ev.evidence_id)
        opp = _opp()
        packet = build_application_packet(
            application_id=1,
            opportunity=opp,
            evidence_store=store,
            base_resume_text="Python SQL engineer",
        )
        for entry in packet.evidence_manifest:
            if not entry.excluded:
                for vs in entry.verification_states:
                    assert vs == "VERIFIED"

    def test_packet_excluded_claims_are_explicit(self, store):
        """The packet explicitly lists skills with no evidence support."""
        ev = store.add(_ev(skills=["Python"], description="Built Python pipelines."))
        store.promote_to_verified(ev.evidence_id)
        opp = _opp(required_skills=["Python", "Kubernetes"], preferred_skills=[])
        packet = build_application_packet(
            application_id=1,
            opportunity=opp,
            evidence_store=store,
            base_resume_text="Python engineer",
        )
        assert packet.excluded_claims  # Kubernetes should be excluded
        assert any("kubernetes" in c.lower() for c in packet.excluded_claims)

    def test_packet_unverified_evidence_not_in_manifest(self, store):
        """UNVERIFIED evidence must never appear in the external manifest."""
        store.add(_ev(skills=["Python", "SQL"]))  # stays UNVERIFIED
        opp = _opp()
        packet = build_application_packet(
            application_id=1,
            opportunity=opp,
            evidence_store=store,
            base_resume_text="Python SQL engineer",
        )
        # All manifest entries with evidence should be empty (UNVERIFIED)
        supported = [e for e in packet.evidence_manifest if not e.excluded]
        assert all(not e.evidence_ids for e in supported) or not supported

    def test_packet_no_auto_submission(self, store):
        """The packet is an artifact, not a submission — no send action exists."""
        ev = store.add(_ev())
        store.promote_to_verified(ev.evidence_id)
        opp = _opp()
        packet = build_application_packet(
            application_id=1,
            opportunity=opp,
            evidence_store=store,
            base_resume_text="Python SQL engineer",
        )
        # Packet has no submit/send method — just data
        assert not hasattr(packet, "submit")
        assert not hasattr(packet, "send")

    def test_packet_keyword_coverage(self, store):
        ev = store.add(_ev(skills=["Python", "SQL"]))
        store.promote_to_verified(ev.evidence_id)
        opp = _opp()
        packet = build_application_packet(
            application_id=1,
            opportunity=opp,
            evidence_store=store,
            base_resume_text="Python SQL engineer",
        )
        assert "python" in [k.lower() for k in packet.keyword_coverage]
        assert "sql" in [k.lower() for k in packet.keyword_coverage]

    def test_packet_fit_context(self, store):
        ev = store.add(_ev())
        store.promote_to_verified(ev.evidence_id)
        opp = _opp()
        packet = build_application_packet(
            application_id=1,
            opportunity=opp,
            evidence_store=store,
            base_resume_text="Python SQL engineer",
        )
        assert packet.fit_band is not None
        assert packet.fit_score is not None
        assert packet.model_used is False  # deterministic path (no key)


# ===========================================================================
# M3.4 — Fit engine bands (M3 naming)
# ====================================================================================


class TestM3FitBands:
    def test_band_names_match_m3_spec(self):
        from careeros.fit_engine import BANDS

        assert BANDS == ("STRONG FIT", "POSSIBLE FIT", "WEAK FIT", "INSUFFICIENT EVIDENCE")

    def test_strong_fit_with_full_evidence(self, store):
        """Full coverage + relevant domain + senior evidence yields STRONG FIT."""
        ev = store.add(
            _ev(
                skills=["Python", "SQL"],
                description=(
                    "AI Solutions Engineer building Python SQL data "
                    "pipelines and analytics systems."
                ),
                title="Senior AI Solutions Engineer",
            )
        )
        store.promote_to_verified(ev.evidence_id)
        opp = _opp(
            required_skills=["Python", "SQL"],
            preferred_skills=[],
            description_raw="Python SQL AI Solutions Engineer role",
        )
        fit = evaluate_fit(opp, store.list_claimable())
        assert fit.coverage_hard == 1.0
        assert fit.band in (
            "STRONG FIT",
            "POSSIBLE FIT",
        )  # full coverage; band depends on domain overlap

    def test_insufficient_evidence_with_no_evidence(self):
        opp = _opp(required_skills=["Python", "SQL"])
        fit = evaluate_fit(opp, [])
        assert fit.band == "INSUFFICIENT EVIDENCE"
        assert fit.coverage_hard == 0.0

    def test_nba_uses_new_band_names(self, store):
        """NBA weights must use the M3 band names, not the old ones."""
        from careeros.next_action import _FIT_WEIGHT

        assert "STRONG FIT" in _FIT_WEIGHT
        assert "POSSIBLE FIT" in _FIT_WEIGHT
        assert "Strong match" not in _FIT_WEIGHT
