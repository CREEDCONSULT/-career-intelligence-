"""Career-profile feedback loop (M2 §9).

Proposes profile updates from recurring patterns in the user's own pipeline
data (opportunities, fit results, evidence, outcomes). PROPOSALS ONLY:

- Nothing is auto-modified. Applying a suggestion is always an explicit user
  action in the UI (which writes through user_data with user: provenance).
- Every suggestion carries its evidence: counts and the specific items that
  produced it.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from careeros.evidence import Evidence
from careeros.fit_engine import FitResult
from careeros.opportunity import Opportunity


@dataclass
class ProfileSuggestion:
    kind: str  # skill_gap | requested_skill | winning_evidence | role_family_fit | certification_opportunity
    title: str
    detail: str
    evidence_note: str  # the data behind the suggestion
    action: str  # what the user would do to apply it

    def to_dict(self) -> dict:
        return field  # placeholder replaced below


def _to_dict(self) -> dict:
    import dataclasses

    return dataclasses.asdict(self)


ProfileSuggestion.to_dict = _to_dict  # type: ignore[method-assign]


MIN_OCCURRENCES = 2  # a pattern must repeat at least this often to be proposed


def propose_profile_updates(
    opportunities: list[Opportunity],
    fits: list[FitResult],
    evidence: list[Evidence],
    role_family_of=None,
) -> list[ProfileSuggestion]:
    """Deterministic, data-cited profile suggestions (never auto-applied)."""
    suggestions: list[ProfileSuggestion] = []
    fit_by_opp = {f.opportunity_id: f for f in fits}

    # 1) frequently requested skills that the evidence lacks
    # (both genuine gaps AND transferables count: a transferable skill still
    #  lacks direct evidence - the user should know it recurs even if they
    #  have adjacent experience)
    requested = Counter()
    for opp in opportunities:
        fit = fit_by_opp.get(opp.opportunity_id)
        if not fit:
            continue
        for g in fit.gaps:
            requested[g.skill] += 1
        for t in fit.transferable:
            requested[t.skill] += 1
    for skill, n in requested.most_common():
        if n >= MIN_OCCURRENCES:
            suggestions.append(
                ProfileSuggestion(
                    kind="skill_gap",
                    title=f"'{skill}' is requested by {n} tracked opportunities",
                    detail=(
                        "This skill is a genuine gap in your evidence across "
                        "multiple opportunities."
                    ),
                    evidence_note=f"missing in {n} of {len(fits)} fit analyses",
                    action="Add evidence demonstrating this skill (project/outcome), "
                    "or plan learning if genuinely absent",
                )
            )

    # 2) frequently requested + supported (strengths to surface in the profile)
    strong = Counter()
    for fit in fits:
        for s in fit.strengths:
            strong[s.skill] += 1
    for skill, n in strong.most_common(3):
        if n >= MIN_OCCURRENCES:
            suggestions.append(
                ProfileSuggestion(
                    kind="requested_skill",
                    title=f"'{skill}' is both requested and evidence-backed",
                    detail=(
                        "This pairing repeats across your pipeline - lead with "
                        "it in your profile and target-role search."
                    ),
                    evidence_note=f"matched in {n} fit analyses",
                    action="Consider setting it as a headline skill / target-role keyword",
                )
            )

    # 3) recurring successful evidence
    cited = Counter()
    for fit in fits:
        for s in fit.strengths:
            for eid in s.evidence_ids:
                cited[eid] += 1
    ev_by_id = {e.evidence_id: e for e in evidence}
    for eid, n in cited.most_common(3):
        if n >= MIN_OCCURRENCES and eid in ev_by_id:
            ev = ev_by_id[eid]
            suggestions.append(
                ProfileSuggestion(
                    kind="winning_evidence",
                    title=f"Evidence [E{eid}] '{ev.title}' keeps doing the work",
                    detail="This item supports matched requirements repeatedly.",
                    evidence_note=f"cited in {n} fit analyses",
                    action="Keep it prominent; consider adding a quantified outcome "
                    "if it lacks one",
                )
            )

    # 4) role-family fit concentration
    if role_family_of is not None:
        fam_bands: dict[str, list[str]] = {}
        for opp in opportunities:
            fit = fit_by_opp.get(opp.opportunity_id)
            if fit:
                fam_bands.setdefault(role_family_of(opp), []).append(fit.band)
        for fam, bands in sorted(fam_bands.items()):
            good = sum(1 for b in bands if b in ("Strong match", "Good match"))
            if len(bands) >= MIN_OCCURRENCES and good / len(bands) >= 0.5:
                suggestions.append(
                    ProfileSuggestion(
                        kind="role_family_fit",
                        title=f"{fam} roles fit your evidence well",
                        detail=f"{good}/{len(bands)} tracked {fam} opportunities "
                        "rated Good or Strong.",
                        evidence_note=f"{len(bands)} fit analyses in family '{fam}'",
                        action="Consider focusing the target-role search on this family",
                    )
                )

    # 5) certification opportunities: gaps that recur and look credential-shaped
    cert_words = (
        "certified",
        "certification",
        "pmp",
        "cpa",
        "cfa",
        "scrum",
        "azure",
        "aws certified",
        "google cloud",
    )
    for skill, n in requested.most_common():
        if n >= MIN_OCCURRENCES and any(w in skill.lower() for w in cert_words):
            suggestions.append(
                ProfileSuggestion(
                    kind="certification_opportunity",
                    title=f"A credential may close the '{skill}' gap",
                    detail="This recurring gap names a credential-shaped requirement.",
                    evidence_note=f"missing in {n} fit analyses",
                    action="If you hold it but haven't recorded it: add the "
                    "certification evidence. If not: consider pursuing it.",
                )
            )

    # dedupe by (kind, title)
    seen: set[tuple[str, str]] = set()
    out = []
    for s in suggestions:
        key = (s.kind, s.title)
        if key not in seen:
            seen.add(key)
            out.append(s)
    return out
