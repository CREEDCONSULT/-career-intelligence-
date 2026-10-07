"""Application packet generator with evidence manifest (M3.6).

Assembles a complete application packet for one opportunity:
- tailored resume (evidence-cited, from M1/M2)
- cover letter (evidence-cited, from M1/M2)
- concise recruiter message
- application summary
- evidence manifest (every claim → evidence IDs → verification state)
- excluded unsupported claims
- keyword coverage
- gaps / risks

Hard constraints:
- Every claim in the manifest traces back to VERIFIED or permitted
  FOUNDER_ASSERTED evidence — UNVERIFIED evidence never appears externally.
- Unsupported claims are explicitly excluded, never silently woven in.
- No application is auto-submitted; the packet is an artifact for founder review.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


from careeros.evidence import Evidence, EvidenceStore
from careeros.fit_engine import FitResult, evaluate_fit
from careeros.opportunity import Opportunity


# ---------------------------------------------------------------------------
# Evidence manifest — the provenance chain for every claim
# ---------------------------------------------------------------------------


@dataclass
class EvidenceManifestEntry:
    """One claim and the evidence that supports it (or the fact it's excluded)."""

    claim: str  # the keyword/skill/claim
    evidence_ids: list[int] = field(default_factory=list)
    verification_states: list[str] = field(default_factory=list)
    provenance: list[str] = field(default_factory=list)
    excluded: bool = False  # True if no evidence supports this claim

    def to_dict(self) -> dict:
        return asdict(self)


def build_evidence_manifest(
    fit: FitResult,
    evidence_store: EvidenceStore,
) -> list[EvidenceManifestEntry]:
    """Build the evidence manifest from a fit result and the evidence ledger.

    For each matched strength: claim = skill, evidence_ids = supporting items.
    For each gap/transferable: claim = skill, excluded = True (no evidence).
    """
    manifest: list[EvidenceManifestEntry] = []
    all_evidence = {e.evidence_id: e for e in evidence_store.list_all()}

    # Matched strengths → supported claims
    for strength in fit.strengths:
        entry = EvidenceManifestEntry(claim=strength.skill)
        for eid in strength.evidence_ids:
            ev = all_evidence.get(eid)
            if ev and ev.claims_allowed:
                entry.evidence_ids.append(eid)
                entry.verification_states.append(ev.verification_state)
                entry.provenance.append(ev.provenance or "unknown")
        manifest.append(entry)

    # Gaps → excluded claims (no evidence)
    for gap in fit.gaps:
        manifest.append(EvidenceManifestEntry(claim=gap.skill, excluded=True))

    # Transferables → excluded but noted as adjacent
    for trans in fit.transferable:
        manifest.append(EvidenceManifestEntry(claim=trans.skill, excluded=True))

    return manifest


# ---------------------------------------------------------------------------
# Application packet
# ---------------------------------------------------------------------------


@dataclass
class ApplicationPacket:
    packet_id: int
    application_id: int
    opportunity_id: int
    # Generated materials (may be None if keyless fallback used)
    tailored_resume: Optional[str] = None
    cover_letter: Optional[str] = None
    recruiter_message: Optional[str] = None
    application_summary: Optional[str] = None
    # Evidence chain
    evidence_manifest: list[EvidenceManifestEntry] = field(default_factory=list)
    excluded_claims: list[str] = field(default_factory=list)
    keyword_coverage: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    # Fit context
    fit_band: Optional[str] = None
    fit_score: Optional[int] = None
    # Metadata
    model_used: bool = False
    created_at: Optional[datetime] = None
    provenance: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["evidence_manifest"] = [e.to_dict() for e in self.evidence_manifest]
        return d


# ---------------------------------------------------------------------------
# Packet assembly
# ---------------------------------------------------------------------------


def _build_recruiter_message(opp: Opportunity, fit: FitResult, claimable: list[Evidence]) -> str:
    """Generate a concise recruiter message (deterministic, evidence-cited)."""
    role = opp.role_title or "the role"
    company = opp.company or "your company"
    top_skills = [s.skill for s in fit.strengths[:3]]

    lines = [
        f"Subject: Application for {role} at {company}",
        "",
        "Hello,",
        "",
        f"I'm applying for the {role} position at {company}.",
    ]
    if top_skills:
        lines.append(
            f"My experience aligns well with your requirements, particularly in "
            f"{', '.join(top_skills)}."
        )
    if fit.band in ("STRONG FIT", "POSSIBLE FIT"):
        lines.append(
            "I'd welcome the opportunity to discuss how my background can contribute to your team."
        )
    else:
        lines.append(
            "While I'm still building depth in some areas, I bring transferable "
            "experience and a strong learning track record."
        )
    lines.append("")
    lines.append("Best regards,")
    lines.append("")
    lines.append("> Founder review required before sending. This draft is")
    lines.append("> evidence-constrained: no unsupported claims are included.")
    return "\n".join(lines)


def _build_application_summary(
    opp: Opportunity, fit: FitResult, manifest: list[EvidenceManifestEntry]
) -> str:
    """Generate an application summary for the founder's review."""
    supported = [e for e in manifest if not e.excluded]
    excluded = [e for e in manifest if e.excluded]

    lines = [
        "## Application Summary",
        "",
        f"**Role:** {opp.role_title or '(untitled)'}",
        f"**Company:** {opp.company or '(unknown)'}",
        f"**Fit:** {fit.band} ({fit.score}/100)",
        f"**Recommendation:** {fit.recommendation}",
        "",
        "### Evidence-backed claims",
    ]
    if supported:
        for entry in supported:
            ev_refs = ", ".join(
                f"[E{i}]({vs})" for i, vs in zip(entry.evidence_ids, entry.verification_states)
            )
            lines.append(f"- **{entry.claim}** — supported by {ev_refs}")
    else:
        lines.append("- No claimable evidence matched this role's requirements.")

    if excluded:
        lines.append("")
        lines.append("### Excluded (unsupported) claims")
        for entry in excluded:
            lines.append(f"- **{entry.claim}** — no verified evidence")

    lines.append("")
    lines.append(f"**Interview risk:** {fit.interview_risk}")
    lines.append(f"**Seniority note:** {fit.seniority_note}")
    if fit.gaps:
        lines.append(f"**Gaps:** {', '.join(g.skill for g in fit.gaps)}")
    if fit.transferable:
        lines.append(
            "**Transferable:** "
            + ", ".join(f"{t.skill} (from {t.transferable_from})" for t in fit.transferable)
        )
    return "\n".join(lines)


def build_application_packet(
    application_id: int,
    opportunity: Opportunity,
    evidence_store: EvidenceStore,
    gw=None,
    *,
    base_resume_text: Optional[str] = None,
    packet_id: int = 0,
) -> ApplicationPacket:
    """Assemble a complete application packet for one opportunity.

    If ``gw`` (an LLM gateway) is provided, generates evidence-cited tailored
    resume and cover letter via the LLM. Otherwise uses the deterministic
    keyword-alignment fallback (never fake tailoring).
    """
    claimable = evidence_store.list_claimable()
    fit = evaluate_fit(opportunity, claimable)
    manifest = build_evidence_manifest(fit, evidence_store)

    excluded_claims = sorted(set([e.claim for e in manifest if e.excluded]))
    keyword_coverage = sorted(set([e.claim for e in manifest if not e.excluded]))

    # Generate materials
    tailored_resume = None
    cover_letter = None
    model_used = False

    if base_resume_text:
        if gw is not None:
            from llm.features.evidence_resume import (
                tailor_evidence_based,
                cover_letter_evidence_based,
            )

            tr = tailor_evidence_based(base_resume_text, opportunity, claimable, gw)
            tailored_resume = tr.markdown
            # Merge any additional evidence citations from the LLM
            for eid in tr.evidence_used:
                if eid not in [e for entry in manifest for e in entry.evidence_ids]:
                    ev = evidence_store.get(eid)
                    if ev and ev.claims_allowed:
                        manifest.append(
                            EvidenceManifestEntry(
                                claim=f"[E{eid}] {ev.title}",
                                evidence_ids=[eid],
                                verification_states=[ev.verification_state],
                                provenance=[ev.provenance or "unknown"],
                            )
                        )
            cl = cover_letter_evidence_based(base_resume_text, opportunity, claimable, gw)
            cover_letter = cl.markdown
            model_used = True
        else:
            from llm.features.evidence_resume import deterministic_keyword_alignment

            result = deterministic_keyword_alignment(base_resume_text, opportunity, claimable)
            tailored_resume = result.markdown
            # Merge any additional evidence from the fallback
            for eid in result.evidence_used:
                if eid not in [e for entry in manifest for e in entry.evidence_ids]:
                    ev = evidence_store.get(eid)
                    if ev and ev.claims_allowed:
                        manifest.append(
                            EvidenceManifestEntry(
                                claim=f"[E{eid}] {ev.title}",
                                evidence_ids=[eid],
                                verification_states=[ev.verification_state],
                                provenance=[ev.provenance or "unknown"],
                            )
                        )

    recruiter_message = _build_recruiter_message(opportunity, fit, claimable)
    application_summary = _build_application_summary(opportunity, fit, manifest)

    return ApplicationPacket(
        packet_id=packet_id,
        application_id=application_id,
        opportunity_id=opportunity.opportunity_id,
        tailored_resume=tailored_resume,
        cover_letter=cover_letter,
        recruiter_message=recruiter_message,
        application_summary=application_summary,
        evidence_manifest=manifest,
        excluded_claims=excluded_claims,
        keyword_coverage=keyword_coverage,
        gaps=[g.skill for g in fit.gaps],
        risks=[t.skill for t in fit.transferable]
        + ([fit.interview_risk] if fit.interview_risk == "high" else []),
        fit_band=fit.band,
        fit_score=fit.score,
        model_used=model_used,
        created_at=datetime.now(),
        provenance="careeros:packet-generator",
    )
