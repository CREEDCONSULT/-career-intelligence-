"""Evidence-based role-fit engine (deterministic - no LLM).

Evaluates a specific opportunity against the user's evidence ledger and
produces an explainable, banded result. Design constraints:

- **No false precision**: the output is a band (Strong/Good/Fair/Weak) plus a
  component breakdown, never a bare authoritative number.
- **Evidence-backed strengths**: every matched requirement lists the evidence
  IDs that support it, so any downstream claim is traceable.
- **Unknown stays unknown**: a missing seniority or an empty required-skills
  list is scored neutrally, never guessed.
- **Deterministic**: same inputs -> same outputs; fully unit-testable.

Skill matching reuses the market pipeline's whole-token matcher (33K-skill
Lightcast taxonomy + curated synonyms), so "ML" evidence supports a
"Machine Learning" requirement via canonical IDs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from careeros.evidence import Evidence, EvidenceStore
from careeros.opportunity import Opportunity

# ---------------------------------------------------------------------------
# Skill matching (shared, cached)
# ---------------------------------------------------------------------------

_MATCHER = None
_CAT_BY_ID = None
_NAME_BY_ID = None


def _get_matcher():
    global _MATCHER, _CAT_BY_ID, _NAME_BY_ID
    if _MATCHER is None:
        from pipeline.skill_matcher import build_skill_index, SkillMatcher

        name_to_id, cat_by_id, name_by_id = build_skill_index()
        _MATCHER = SkillMatcher(name_to_id)
        _CAT_BY_ID = cat_by_id
        _NAME_BY_ID = name_by_id
    return _MATCHER, _CAT_BY_ID, _NAME_BY_ID


def extract_skills_from_text(text: str) -> set[str]:
    """Canonical lowercase skill names found in text (whole-token, synonym-aware)."""
    matcher, _, name_by_id = _get_matcher()
    if not text:
        return set()
    return {name_by_id.get(sid, sid).lower() for sid in matcher.kp.extract_keywords(text)}


def _skill_ids_from_text(text: str) -> dict[str, set[str]]:
    """skill_id -> set of canonical names seen, for a text."""
    matcher, _, name_by_id = _get_matcher()
    out: dict[str, set[str]] = {}
    if not text:
        return out
    for sid in matcher.kp.extract_keywords(text):
        out.setdefault(sid, set()).add(name_by_id.get(sid, sid).lower())
    return out


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

BANDS = ("Strong match", "Good match", "Fair match", "Weak match")


@dataclass
class MatchedStrength:
    skill: str
    evidence_ids: list[int]


@dataclass
class Gap:
    skill: str
    transferable_from: Optional[str] = None  # adjacent possessed skill, if any


@dataclass
class FitResult:
    opportunity_id: int
    score: int  # 0-100, always reported WITH its band
    band: str  # one of BANDS
    coverage_hard: float  # component: required-skills coverage
    overlap_preferred: float
    domain_relevance: float
    seniority_fit: float
    experience_evidence: float
    strengths: list[MatchedStrength] = field(default_factory=list)
    gaps: list[Gap] = field(default_factory=list)
    transferable: list[Gap] = field(default_factory=list)
    interview_risk: str = "medium"  # low | medium | high
    seniority_note: str = ""
    closing_urgency: float = 1.0  # 1.0 default; >1 means closing soon
    recommendation: str = ""

    def to_dict(self) -> dict:
        import dataclasses

        return dataclasses.asdict(self)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_WORD_RE = re.compile(r"[a-z0-9+#.]{2,}")
_STOP = set(
    """the a an and or to of for with in on at by is are as will be this that
you your we our they their it its from per plus strong excellent good ability able
role job work working team teams company candidates candidate ideal must have
required requirements preferred responsibilities about join help using use new
years experience experienced etc within who what how why across including include
includes other others more most very also well closely deeply highly""".split()
)


def _content_tokens(text: str, limit: int = 120) -> set[str]:
    if not text:
        return set()
    toks = [t for t in _WORD_RE.findall(text.lower()) if t not in _STOP]
    # keep order of first appearance for a stable top-N
    seen: list[str] = []
    added = set()
    for t in toks:
        if t not in added:
            seen.append(t)
            added.add(t)
    return set(seen[:limit])


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


_SENIORITY_ORDER = ["junior", "mid", "senior", "lead", "principal", "staff"]


def _seniority_fit(
    job_seniority: Optional[str], evidence_seniority: Optional[str]
) -> tuple[float, str]:
    """(fit 0-1, note). Unknown on either side -> mild conservative neutral."""
    if job_seniority is None and evidence_seniority is None:
        return 0.75, "seniority unknown on both sides"
    if job_seniority is None:
        return 0.75, f"job seniority unknown; evidence suggests {evidence_seniority}"
    if evidence_seniority is None:
        return 0.75, f"job asks {job_seniority}; evidence level not established"
    if job_seniority == evidence_seniority:
        return 1.0, f"seniority aligned ({job_seniority})"
    try:
        dist = abs(
            _SENIORITY_ORDER.index(job_seniority) - _SENIORITY_ORDER.index(evidence_seniority)
        )
    except ValueError:
        return 0.75, "seniority comparison inconclusive"
    if dist == 1:
        return (
            0.6,
            f"seniority adjacent: job asks {job_seniority}, evidence shows {evidence_seniority}",
        )
    return (
        0.15,
        f"seniority mismatch: job asks {job_seniority}, evidence shows {evidence_seniority}",
    )


def _infer_evidence_seniority(items: list[Evidence]) -> Optional[str]:
    """Very conservative: senior only if an employment title says so explicitly."""
    for ev in items:
        if ev.type in ("employment", "project") and ev.title:
            t = ev.title.lower()
            if "senior" in t or "lead" in t or "principal" in t or "staff" in t:
                return "senior"
            if "junior" in t or "entry" in t:
                return "junior"
    return None


def _closing_urgency(closing: Optional[date], today: Optional[date] = None) -> float:
    if closing is None:
        return 1.0
    today = today or date.today()
    days = (closing - today).days
    if days < 0:
        return 0.25  # already closed: urgency collapses, mostly archive
    if days <= 3:
        return 1.5
    if days <= 7:
        return 1.25
    if days <= 14:
        return 1.1
    return 1.0


# ---------------------------------------------------------------------------
# Core evaluation
# ---------------------------------------------------------------------------

_WEIGHTS = {
    "coverage_hard": 0.45,
    "overlap_preferred": 0.15,
    "domain_relevance": 0.15,
    "seniority_fit": 0.15,
    "experience_evidence": 0.10,
}


def evaluate_fit(
    opportunity: Opportunity,
    evidence_items: list[Evidence],
    today: Optional[date] = None,
) -> FitResult:
    """Deterministically evaluate one opportunity against the evidence ledger."""
    today = today or date.today()
    matcher, cat_by_id, name_by_id = _get_matcher()

    # ---- opportunity-side skills ------------------------------------------
    # Explicit lists are authoritative; the description only ADDS discoveries.
    req_ids: dict[str, set[str]] = {}
    for s in opportunity.required_skills:
        ids = _skill_ids_from_text(s)
        if ids:
            for sid, names in ids.items():
                req_ids.setdefault(sid, set()).update(names)
        else:
            # Not in taxonomy (e.g. "Canadian work permit") - key by the raw string
            req_ids.setdefault(f"RAW::{s.strip().lower()}", {s.strip().lower()})
    for sid, names in _skill_ids_from_text(opportunity.description_normalized or "").items():
        req_ids.setdefault(sid, set()).update(names)
    # Preferred: explicit + description extras, excluding required overlaps
    pref_ids: dict[str, set[str]] = {}
    for s in opportunity.preferred_skills:
        ids = _skill_ids_from_text(s)
        if ids:
            for sid, names in ids.items():
                pref_ids.setdefault(sid, set()).update(names)
        else:
            pref_ids.setdefault(f"RAW::{s.strip().lower()}", {s.strip().lower()})
    for sid, names in _skill_ids_from_text(opportunity.description_normalized or "").items():
        if sid not in req_ids:
            pref_ids.setdefault(sid, set()).update(names)

    # ---- evidence-side skills ---------------------------------------------
    possessed_ids: dict[str, list[int]] = {}  # skill_id -> evidence IDs
    ev_text_by_skill: dict[str, set[str]] = {}
    for ev in evidence_items:
        if not ev.claims_allowed:
            continue
        ids = _skill_ids_from_text(ev.text)
        for sid in ids:
            possessed_ids.setdefault(sid, []).append(ev.evidence_id)
            ev_text_by_skill.setdefault(sid, set()).update(ids[sid])

    # ---- coverage ----------------------------------------------------------
    matched_req: list[MatchedStrength] = []
    missing: list[str] = []
    for sid, names in req_ids.items():
        label = sorted(names)[0]
        if sid in possessed_ids:
            matched_req.append(
                MatchedStrength(skill=label, evidence_ids=sorted(set(possessed_ids[sid])))
            )
        elif sid.startswith("RAW::"):
            # Requirement outside the taxonomy: satisfied only by a literal
            # (whole-phrase) mention in evidence text - still traceable.
            phrase = sid[5:]
            hit_ids = [
                e.evidence_id
                for e in evidence_items
                if e.claims_allowed and phrase in e.text.lower()
            ]
            if hit_ids:
                matched_req.append(MatchedStrength(skill=phrase, evidence_ids=sorted(set(hit_ids))))
            else:
                missing.append(label)
        else:
            missing.append(label)

    still_missing: list[str] = missing

    coverage_hard = (len(matched_req) / len(req_ids)) if req_ids else 1.0

    # ---- preferred overlap ---------------------------------------------------
    pref_matched = sum(1 for sid in pref_ids if sid in possessed_ids)
    overlap_preferred = (pref_matched / len(pref_ids)) if pref_ids else coverage_hard

    # ---- domain relevance ------------------------------------------------------
    job_tokens = _content_tokens(
        " ".join(
            x
            for x in [
                opportunity.role_title,
                opportunity.company,
                opportunity.description_normalized,
            ]
            if x
        )
    )
    ev_corpus = " ".join(e.text for e in evidence_items if e.claims_allowed)
    ev_tokens = _content_tokens(ev_corpus)
    domain_relevance = _jaccard(job_tokens, ev_tokens)

    # ---- seniority -------------------------------------------------------------
    job_sen = opportunity.seniority
    ev_sen = _infer_evidence_seniority(evidence_items)
    seniority_fit, seniority_note = _seniority_fit(job_sen, ev_sen)

    # ---- experience evidence ------------------------------------------------------
    job_skill_ids = set(req_ids) | set(pref_ids)
    relevant = [
        e
        for e in evidence_items
        if e.claims_allowed
        and e.type in ("employment", "project")
        and (
            set(_skill_ids_from_text(e.text)) & job_skill_ids
            or _jaccard(_content_tokens(e.text, 60), job_tokens) >= 0.05
        )
    ]
    experience_evidence = min(1.0, len(relevant) / 2)

    # ---- score + band ------------------------------------------------------------
    score = round(
        100
        * (
            _WEIGHTS["coverage_hard"] * coverage_hard
            + _WEIGHTS["overlap_preferred"] * overlap_preferred
            + _WEIGHTS["domain_relevance"] * domain_relevance
            + _WEIGHTS["seniority_fit"] * seniority_fit
            + _WEIGHTS["experience_evidence"] * experience_evidence
        )
    )
    if score >= 80:
        band, rec = "Strong match", "Apply - strong evidence-backed fit."
    elif score >= 60:
        band, rec = "Good match", "Prepare tailored materials, then apply."
    elif score >= 40:
        band, rec = "Fair match", "Stretch application - address the listed gaps first."
    else:
        band, rec = "Weak match", "Likely pass - requirements are far from current evidence."

    # ---- gaps + transferables -------------------------------------------------------
    # A missing requirement is "possibly transferable" when the user holds a
    # skill from the same taxonomy category (clearly hedged, never asserted).
    gaps: list[Gap] = []
    transferable: list[Gap] = []
    for label in still_missing:
        sid_guess = _skill_ids_from_text(label)
        adjacent = None
        if sid_guess:
            sid = next(iter(sid_guess))
            cat = cat_by_id.get(sid)
            for pid in possessed_ids:
                if cat and pid != sid and cat_by_id.get(pid) == cat:
                    names = ev_text_by_skill.get(pid)
                    if names:
                        adjacent = sorted(names)[0]
                        break
        if adjacent:
            transferable.append(Gap(skill=label, transferable_from=adjacent))
        else:
            gaps.append(Gap(skill=label))

    # ---- interview risk ------------------------------------------------------------
    missing_count = len(gaps) + len(transferable)
    if missing_count == 0 and seniority_fit >= 0.99 and relevant:
        interview_risk = "low"
    elif missing_count >= 3 or seniority_fit <= 0.2 or not relevant:
        interview_risk = "high"
    else:
        interview_risk = "medium"

    return FitResult(
        opportunity_id=opportunity.opportunity_id,
        score=score,
        band=band,
        coverage_hard=round(coverage_hard, 3),
        overlap_preferred=round(overlap_preferred, 3),
        domain_relevance=round(domain_relevance, 3),
        seniority_fit=round(seniority_fit, 3),
        experience_evidence=round(experience_evidence, 3),
        strengths=matched_req,
        gaps=gaps,
        transferable=transferable,
        interview_risk=interview_risk,
        seniority_note=seniority_note,
        closing_urgency=_closing_urgency(opportunity.closing_date, today),
        recommendation=rec,
    )


def evaluate_for_store(
    opportunity: Opportunity,
    store: EvidenceStore,
    today: Optional[date] = None,
) -> FitResult:
    """Convenience: evaluate against every claimable evidence item in a store."""
    return evaluate_fit(opportunity, [e for e in store.list_all() if e.claims_allowed], today)
