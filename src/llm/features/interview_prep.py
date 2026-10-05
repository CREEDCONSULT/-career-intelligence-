"""Evidence-grounded interview preparation packs (M2 §6).

``build_prep_pack`` assembles a preparation pack for one opportunity from
ONLY: the opportunity's own fields, the user's evidence ledger, and the fit
result. The deterministic base needs no API key. When a gateway is supplied
(and a key configured), an LLM polish pass rewrites the narrative sections
under the same anti-fabrication + evidence-citation contract used by the
resume tailor.

Hard rules:
- No company facts beyond the opportunity record are invented (no "about the
  company" paragraphs from imagination).
- Every STAR story cites the evidence item it came from.
- Gaps/risks come from the fit result; salary context only from the
  opportunity's own salary fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from careeros.evidence import Evidence
from careeros.fit_engine import FitResult
from careeros.opportunity import Opportunity

_ANTI_FABRICATION = (
    "ABSOLUTE RULE: do NOT invent company facts, personal experience, metrics, "
    "technologies, or credentials. Use only the job record and the numbered "
    "evidence ledger. If something is unknown, leave it out."
)

STAGE_THEMES = {
    "recruiter_screen": [
        "Your background summary (2 minutes, evidence-anchored)",
        "Motivation for this specific role",
        "Salary expectations + logistics (location, work mode, start availability)",
    ],
    "hiring_manager": [
        "Ownership stories matching the role's core responsibilities",
        "How you would approach the first 90 days (grounded in your past work)",
        "Collaboration / stakeholder examples",
    ],
    "technical_case": [
        "Technical depth on the role's required skills",
        "A system/design walkthrough from your evidence",
        "Trade-off reasoning and failure-mode thinking",
    ],
    "assessment": [
        "Exercise format readiness (case / take-home / coding)",
        "Time-boxing and communication of assumptions",
    ],
    "panel_final": [
        "Consistency of your story across interviewers",
        "Leadership / influence evidence",
        "Your questions for the panel",
    ],
    "offer_discussion": [
        "Total-compensation framing from the posted range",
        "Decision criteria and start-date logistics",
    ],
}


@dataclass
class PrepPack:
    markdown: str
    evidence_used: list[int] = field(default_factory=list)
    excluded_claims: list[str] = field(default_factory=list)
    model_used: bool = False
    stage: Optional[str] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Deterministic base (no key required)
# ---------------------------------------------------------------------------


def _star_stories(items: list[Evidence]) -> list[tuple[int, str]]:
    """Format claimable evidence as STAR-shaped stories, cited by ID."""
    out = []
    for ev in items:
        if not ev.claims_allowed or ev.type in ("certification",):
            continue
        situation = (
            f"{ev.title}"
            + (f" at {ev.organization}" if ev.organization else "")
            + (
                f" ({ev.start_date or '?'} - {ev.end_date or 'ongoing'})"
                if (ev.start_date or ev.end_date)
                else ""
            )
        )
        action = ev.description or ""
        result = (
            "; ".join(
                f"{m.get('value', '')}{m.get('unit', '')} {m.get('context', '')}".strip()
                for m in ev.metrics
            )
            or None
        )
        story = f"**[E{ev.evidence_id}] {situation}**"
        if action:
            story += f"\n  - *Action:* {action}"
        if result:
            story += f"\n  - *Result:* {result}"
        if ev.skills:
            story += f"\n  - *Skills shown:* {', '.join(ev.skills)}"
        out.append((ev.evidence_id, story))
    return out


def build_prep_pack(
    opportunity: Opportunity,
    evidence: list[Evidence],
    fit: FitResult,
    stage: Optional[str] = None,
    gw=None,
) -> PrepPack:
    """Assemble the preparation pack (deterministic base + optional LLM polish)."""
    claimable = [e for e in evidence if e.claims_allowed]
    ev_by_id = {e.evidence_id: e for e in claimable}
    cited: set[int] = set()

    def cite(i: int) -> str:
        cited.add(i)
        return f"[E{i}]"

    lines: list[str] = []
    lines.append("## Interview preparation pack")
    role = opportunity.role_title or "(untitled role)"
    company = opportunity.company or "(company not recorded)"
    lines.append(f"**Role:** {role} - {company}")
    if opportunity.seniority:
        lines.append(f"**Seniority posted:** {opportunity.seniority}")
    if stage:
        lines.append(f"**Prepared for stage:** {stage.replace('_', ' ')}")

    # -- company/role summary (from the record only) ------------------------
    lines.append("\n### Company / role summary (from the job record)")
    if opportunity.description_raw:
        lines.append(f"> {opportunity.description_raw[:700]}")
    else:
        lines.append(
            "> No job description recorded - add the posting text to "
            "the opportunity for a fuller pack."
        )
    for label, val in (
        ("Location", opportunity.location),
        ("Work mode", opportunity.work_mode),
        ("Employment type", opportunity.employment_type),
    ):
        if val:
            lines.append(f"- {label}: {val}")

    # -- likely competency themes ------------------------------------------
    lines.append("\n### Likely competency themes")
    theme_pool = STAGE_THEMES.get(stage or "", []) if stage else []
    for t in theme_pool[:3]:
        lines.append(f"- {t}")
    for s in opportunity.required_skills[:5]:
        lines.append(f"- Depth on **{s}** (required)")
    for s in opportunity.preferred_skills[:3]:
        lines.append(f"- Familiarity with {s} (preferred)")

    # -- evidence-backed STAR stories ---------------------------------------
    lines.append("\n### Your evidence-backed stories (STAR, cited)")
    stories = _star_stories(claimable)
    if stories:
        for eid, story in stories:
            cite(eid)
            lines.append(f"- {story}")
    else:
        lines.append(
            "- No claimable evidence yet - add evidence in the library; stories must come from it."
        )

    # -- strengths recap from fit -------------------------------------------
    lines.append("\n### Evidence-backed strengths (from fit analysis)")
    if fit.strengths:
        for s in fit.strengths[:8]:
            for i in s.evidence_ids:
                if i in ev_by_id:
                    cite(i)
            lines.append(
                f"- **{s.skill}** - supported by "
                + ", ".join(cite(i) for i in s.evidence_ids if i in ev_by_id)
            )
    else:
        lines.append("- No matched strengths yet.")

    # -- technical refreshers -------------------------------------------------
    lines.append("\n### Technical / domain refreshers")
    for s in fit.strengths[:6]:
        lines.append(
            f"- Revisit {s.skill} - be ready to go one level deeper than your evidence describes"
        )
    for g in fit.gaps + fit.transferable:
        lines.append(
            f"- Expect probing on **{g.skill}**"
            + (
                f" (transferable from {g.transferable_from})"
                if getattr(g, "transferable_from", None)
                else ""
            )
        )

    # -- role-specific questions ----------------------------------------------
    lines.append("\n### Role-specific questions to expect")
    for s in opportunity.required_skills[:4]:
        lines.append(f"- Describe a time you used {s} in production (use a cited story)")
    if opportunity.seniority:
        lines.append(f"- Why this role at the {opportunity.seniority} level suits your trajectory")
    for g in fit.gaps[:3]:
        lines.append(f"- How you would ramp up on {g.skill} (honest gap answer)")

    # -- questions to ask ------------------------------------------------------
    lines.append("\n### Questions to ask them")
    if fit.gaps or fit.transferable:
        lines.append(
            "- What does the team use for: "
            + ", ".join(g.skill for g in (fit.gaps + fit.transferable)[:4])
            + "? (grounds your ramp-up answer)"
        )
    lines.append("- What does success in this role look like in the first 90 days?")
    if opportunity.work_mode:
        lines.append(f"- How does the team work in a {opportunity.work_mode} setup?")

    # -- gaps / risks ------------------------------------------------------------
    lines.append("\n### Gaps & risks (honest view)")
    lines.append(f"- Interview risk (fit engine): **{fit.interview_risk}**")
    if fit.gaps:
        lines.append("- Genuine gaps: " + ", ".join(g.skill for g in fit.gaps))
    if fit.transferable:
        lines.append(
            "- Possibly transferable: "
            + ", ".join(f"{g.skill} (from {g.transferable_from})" for g in fit.transferable)
        )
    lines.append(f"- {fit.seniority_note}")

    # -- salary / negotiation ------------------------------------------------------
    lines.append("\n### Salary / negotiation context")
    if opportunity.salary_min or opportunity.salary_max:
        cur = opportunity.currency or ""
        lines.append(
            f"- Posted range: {cur} {opportunity.salary_min or '?'} - "
            f"{opportunity.salary_max or '?'}"
            + (
                " (annualize hourly figures before comparing)"
                if (opportunity.salary_min or 0) < 1000
                else ""
            )
        )
        lines.append(
            "- Anchor on your quantified outcomes (cited above) when "
            "discussing compensation; no invented market claims."
        )
    else:
        lines.append(
            "- No posted range recorded - research before the call; "
            "no market data is asserted here."
        )

    base_md = "\n".join(lines)
    excluded = sorted({g.skill for g in fit.gaps})  # gap skills = watch-outs, never claimed

    # -- optional LLM polish (evidence-constrained) --------------------------------
    if gw is not None:
        polished = _llm_polish(base_md, opportunity, claimable, stage, gw)
        if polished:
            valid = {e.evidence_id for e in claimable}
            bad = [i for i in polished["evidence_used"] if i not in valid]
            used = [i for i in polished["evidence_used"] if i in valid]
            note = f" dropped unverified citations {bad}." if bad else ""
            return PrepPack(
                markdown=polished["markdown"],
                evidence_used=sorted(set(used) | cited),
                excluded_claims=excluded,
                model_used=True,
                stage=stage,
                notes=note or None,
            )

    return PrepPack(
        markdown=base_md,
        evidence_used=sorted(cited),
        excluded_claims=excluded,
        model_used=False,
        stage=stage,
    )


def _llm_polish(
    base_md: str, opportunity: Opportunity, evidence: list[Evidence], stage: Optional[str], gw
) -> Optional[dict]:
    """LLM polish pass. Returns {'markdown', 'evidence_used'} or None on any
    provider/config problem (never breaks the deterministic pack)."""
    try:
        from llm.features.evidence_resume import _evidence_block, _EVIDENCE_FOOTER

        prompt = (
            "Polish this interview preparation pack for clarity and flow.\n\n"
            f"STAGE: {(stage or 'general').replace('_', ' ')}\n\n"
            f"PACK (deterministic draft - keep every section and every [E#] citation):\n"
            f"{base_md}\n\n"
            f"EVIDENCE LEDGER (for reference; cite only these IDs):\n"
            f"{_evidence_block(evidence)}\n\n"
            f"{_ANTI_FABRICATION}\n"
            "Keep all [E#] citations, keep the Gaps & risks section intact, and do not "
            "add new factual claims. After the pack, output exactly this footer:\n"
            f"{_EVIDENCE_FOOTER}\n"
            '{"evidence_used": [<int IDs actually present in your output>], '
            '"excluded_claims": []}'
        )
        raw = gw.complete([{"role": "user", "content": prompt}], tier="interactive").text or ""
        if _EVIDENCE_FOOTER not in raw:
            return None
        md, _, footer = raw.rpartition(_EVIDENCE_FOOTER)
        import json

        data = json.loads(footer.strip().strip("`").strip())
        return {
            "markdown": md.strip(),
            "evidence_used": [int(i) for i in data.get("evidence_used", [])],
        }
    except Exception:  # noqa: BLE001 - polish is best-effort, never fatal
        return None
