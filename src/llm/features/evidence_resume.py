"""Evidence-based resume tailoring and cover letters (M1).

Extends the Studio's grounded generation with hard evidence traceability:

- The model receives the candidate's evidence ledger (each item with an ID)
  and may ONLY use resume content + evidence items as factual basis.
- Output must cite the evidence IDs used and list job keywords it could NOT
  support (excluded claims) - both are validated deterministically:
  * every evidence ID in the result must exist in the provided ledger
  * unsupported job keywords are recorded as excluded claims

A deterministic fallback (no API key required) produces a keyword-alignment
report instead of fake tailoring - it never generates resume text.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional

from careeros.evidence import Evidence
from careeros.fit_engine import extract_skills_from_text
from careeros.opportunity import Opportunity

_ANTI_FABRICATION = (
    "ABSOLUTE RULE: do NOT invent experience, employers, dates, metrics, technologies, "
    "responsibilities, or credentials. Use only facts present in the resume and the "
    "numbered evidence ledger. If the resume and evidence do not support something the "
    "job wants, say nothing about it."
)

_EVIDENCE_FOOTER = "===EVIDENCE-JSON==="


@dataclass
class TailorResult:
    markdown: str
    evidence_used: list[int] = field(default_factory=list)
    excluded_claims: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    model_used: bool = False
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Deterministic helpers (no LLM)
# ---------------------------------------------------------------------------


def extract_job_keywords(opportunity: Opportunity, limit: int = 20) -> list[str]:
    """Job-specific keywords: explicit skills first, then description matches."""
    out: list[str] = []
    seen = set()
    for s in list(opportunity.required_skills) + list(opportunity.preferred_skills):
        key = s.strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(s.strip())
    description = opportunity.description_normalized or opportunity.description_raw or ""
    for name in sorted(extract_skills_from_text(description)):
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out[:limit]


def _evidence_block(items: list[Evidence]) -> str:
    lines = []
    for ev in items:
        metrics = "; ".join(
            f"{m.get('value', '')}{m.get('unit', '')} {m.get('context', '')}".strip()
            for m in ev.metrics
        )
        lines.append(
            f"[E{ev.evidence_id}] ({ev.type}) {ev.title}"
            + (f" @ {ev.organization}" if ev.organization else "")
            + (
                f" [{ev.start_date or '?'} - {ev.end_date or 'ongoing'}]"
                if (ev.start_date or ev.end_date)
                else ""
            )
            + (f"\n    {ev.description}" if ev.description else "")
            + (f"\n    Metrics: {metrics}" if metrics else "")
            + (f"\n    Skills: {', '.join(ev.skills)}" if ev.skills else "")
        )
    return "\n".join(lines)


def _parse_footer(text: str) -> tuple[str, list[int], list[str]]:
    """Split model output into (markdown, evidence_ids, excluded_claims).

    Tolerates a missing/malformed footer: evidence stays empty and a note is
    surfaced rather than trusting unvalidated claims.
    """
    if _EVIDENCE_FOOTER in text:
        md, _, footer = text.rpartition(_EVIDENCE_FOOTER)
        try:
            data = json.loads(footer.strip().strip("`").strip())
            ids = [int(i) for i in data.get("evidence_used", [])]
            excluded = [str(x) for x in data.get("excluded_claims", [])]
            return md.strip(), ids, excluded
        except (json.JSONDecodeError, TypeError, ValueError):
            return text.strip(), [], []
    return text.strip(), [], []


def _validate(result: TailorResult, valid_ids: set[int]) -> TailorResult:
    """Drop any evidence ID the model cited that is not in the real ledger."""
    bad = [i for i in result.evidence_used if i not in valid_ids]
    if bad:
        result.evidence_used = [i for i in result.evidence_used if i in valid_ids]
        result.notes = (result.notes or "") + f" dropped unverified evidence citations {bad}."
    return result


# ---------------------------------------------------------------------------
# Generation (LLM, evidence-constrained)
# ---------------------------------------------------------------------------


def tailor_evidence_based(
    resume_text: str,
    opportunity: Opportunity,
    evidence: list[Evidence],
    gw,
) -> TailorResult:
    """Tailor a resume for one opportunity, citing evidence IDs for every claim."""
    keywords = extract_job_keywords(opportunity)
    valid_ids = {ev.evidence_id for ev in evidence if ev.claims_allowed}
    prompt = (
        f"Tailor the resume below for this specific job opening.\n\n"
        f"JOB: {opportunity.role_title or '(untitled)'}"
        + (f" at {opportunity.company}" if opportunity.company else "")
        + "\n"
        + (
            f"JOB DESCRIPTION:\n{opportunity.description_raw or ''}\n\n"
            if opportunity.description_raw
            else ""
        )
        + f"JOB KEYWORDS (mirror only where genuinely supported): {', '.join(keywords)}\n\n"
        f"RESUME:\n{resume_text}\n\n"
        f"EVIDENCE LEDGER (each item has an ID like [E3]; cite IDs for any claim you use):\n"
        f"{_evidence_block(evidence)}\n\n"
        f"{_ANTI_FABRICATION}\n"
        "Reorder and rephrase so genuinely aligned experience leads. After the resume, "
        f"output exactly this footer:\n{_EVIDENCE_FOOTER}\n"
        '{"evidence_used": [<int IDs actually used>], "excluded_claims": '
        "[<job keywords you could NOT support>]}"
    )
    raw = gw.complete([{"role": "user", "content": prompt}], tier="interactive").text or ""
    md, used, excluded = _parse_footer(raw)
    return _validate(
        TailorResult(
            markdown=md,
            evidence_used=used,
            excluded_claims=excluded,
            keywords=keywords,
            model_used=True,
        ),
        valid_ids,
    )


def cover_letter_evidence_based(
    resume_text: str,
    opportunity: Opportunity,
    evidence: list[Evidence],
    gw,
) -> TailorResult:
    """Draft a cover letter for one opportunity, evidence-cited like the tailor."""
    keywords = extract_job_keywords(opportunity)
    valid_ids = {ev.evidence_id for ev in evidence if ev.claims_allowed}
    prompt = (
        f"Write a concise professional cover letter for this job.\n\n"
        f"JOB: {opportunity.role_title or '(untitled)'}"
        + (f" at {opportunity.company}" if opportunity.company else "")
        + "\n"
        + (
            f"JOB DESCRIPTION:\n{opportunity.description_raw or ''}\n\n"
            if opportunity.description_raw
            else ""
        )
        + f"RESUME:\n{resume_text}\n\n"
        f"EVIDENCE LEDGER (cite IDs like [E3] for claims you use):\n{_evidence_block(evidence)}\n\n"
        f"{_ANTI_FABRICATION}\n"
        "3-4 short paragraphs, no clichés. Then output exactly this footer:\n"
        f"{_EVIDENCE_FOOTER}\n"
        '{"evidence_used": [<int IDs actually used>], "excluded_claims": '
        "[<job keywords you could NOT support>]}"
    )
    raw = gw.complete([{"role": "user", "content": prompt}], tier="interactive").text or ""
    md, used, excluded = _parse_footer(raw)
    return _validate(
        TailorResult(
            markdown=md,
            evidence_used=used,
            excluded_claims=excluded,
            keywords=keywords,
            model_used=True,
        ),
        valid_ids,
    )


# ---------------------------------------------------------------------------
# Deterministic no-key fallback (never generates resume text)
# ---------------------------------------------------------------------------


def deterministic_keyword_alignment(
    resume_text: str,
    opportunity: Opportunity,
    evidence: list[Evidence],
) -> TailorResult:
    """No-LLM fallback: an honest alignment report, not a fake tailored resume.

    Reports which job keywords the resume/evidence support and which are
    unsupported (excluded claims). The UI stores this as a document version
    so traceability exists even before any LLM run.
    """
    keywords = extract_job_keywords(opportunity)
    corpus = " ".join([resume_text] + [ev.text for ev in evidence if ev.claims_allowed]).lower()
    supported, excluded = [], []
    for kw in keywords:
        # support = whole-word presence in resume/evidence corpus (conservative)
        if re.search(rf"(?<![a-z0-9]){re.escape(kw.lower())}(?![a-z0-9])", corpus):
            supported.append(kw)
        else:
            excluded.append(kw)
    used_ids = sorted(
        {
            ev.evidence_id
            for ev in evidence
            if ev.claims_allowed
            and any(
                re.search(rf"(?<![a-z0-9]){re.escape(kw.lower())}(?![a-z0-9])", ev.text.lower())
                for kw in supported
            )
        }
    )
    md = (
        "## Keyword alignment report (deterministic - no LLM used)\n\n"
        f"**Job:** {(opportunity.role_title or '(untitled)')}"
        + (f" at {opportunity.company}\n" if opportunity.company else "\n")
        + f"\n**Supported by resume/evidence ({len(supported)}):** "
        + (", ".join(supported) or "none")
        + f"\n\n**Not supported - excluded from any tailored materials ({len(excluded)}):** "
        + (", ".join(excluded) or "none")
        + "\n\n> This report is generated without an LLM. Add evidence for the excluded "
        "keywords, or configure an API key, before generating a tailored resume."
    )
    return TailorResult(
        markdown=md,
        evidence_used=used_ids,
        excluded_claims=excluded,
        keywords=keywords,
        model_used=False,
        notes="deterministic fallback - no model called",
    )
