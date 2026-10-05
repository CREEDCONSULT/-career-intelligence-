#!/usr/bin/env python3
"""Live-model validation harness for evidence-grounded generation (M2 1B).

Runs the real opportunity + evidence fixture through the live model gateway,
validates the evidence-citation contract, and compares the live output with
the deterministic fallback. Prints provider/model/version and a validation
report. Exits non-zero on any contract violation.

Requires ANTHROPIC_API_KEY or OPENAI_API_KEY (provider-agnostic LiteLLM
gateway; per-tier models overridable via LLM_MODEL_* env vars).

Usage:
    python scripts/validate_live_model.py            # full validation
    python scripts/validate_live_model.py --json     # machine-readable report
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "streamlit_app"))


def _build_fixture():
    """Deterministic real-world-shaped opportunity + evidence ledger."""
    from careeros.evidence import Evidence
    from careeros.opportunity import Opportunity

    opportunity = Opportunity(
        opportunity_id=1,
        source="validation",
        role_title="Senior Analytics Engineer",
        company="Northwind Analytics",
        location="Toronto",
        work_mode="hybrid",
        employment_type="full-time",
        salary_min=120000.0,
        salary_max=145000.0,
        currency="CAD",
        description_raw=(
            "We need strong Python, SQL and Airflow skills; dbt and Docker are "
            "nice to have. You will own the warehouse and pipeline roadmap, "
            "partner with data science, and raise data quality. 5+ years."
        ),
        description_normalized=(
            "Senior Analytics Engineer Northwind Analytics Toronto hybrid "
            "Python SQL Airflow dbt Docker warehouse pipeline roadmap"
        ),
        required_skills=["Python", "SQL", "Airflow"],
        preferred_skills=["dbt", "Docker"],
        seniority="senior",
    )
    evidence = [
        Evidence(
            evidence_id=1,
            type="employment",
            title="Analytics Engineer",
            organization="Old Co",
            start_date="2020-01-01",
            end_date="2024-05-01",
            description=(
                "Built Python/SQL pipelines in Airflow; cut refresh "
                "times 40%. Owned the warehouse roadmap."
            ),
            skills=["Python", "SQL", "Airflow"],
            verification_status="documented",
        ),
        Evidence(
            evidence_id=2,
            type="project",
            title="dbt warehouse migration",
            description="Rebuilt the warehouse with dbt and Docker.",
            skills=["dbt", "Docker"],
            verification_status="self_reported",
        ),
        Evidence(
            evidence_id=3,
            type="certification",
            title="Empty certification slot",
            description="Placeholder that must never be cited.",
            claims_allowed=False,
            verification_status="self_reported",
        ),
    ]
    base_resume = (
        "Analytics engineer. Built and owned ETL pipelines (Python, SQL, Airflow) "
        "at Old Co. Led a dbt warehouse migration with Docker. Cut refresh times 40%."
    )
    return opportunity, evidence, base_resume


def _validate_contract(result, valid_ids: set[int], label: str) -> list[str]:
    """Return a list of contract violations (empty = valid)."""
    problems = []
    if not result.markdown or not result.markdown.strip():
        problems.append(f"{label}: empty markdown")
    bad = [i for i in result.evidence_used if i not in valid_ids]
    if bad:
        problems.append(f"{label}: cited evidence IDs not in ledger: {bad}")
    if set(result.evidence_used) & set(result.excluded_claims):
        problems.append(f"{label}: evidence/excluded sets overlap")
    # honesty check: excluded keywords must not appear as claims in the output
    for claim in result.excluded_claims:
        if claim.lower() in (result.markdown or "").lower():
            problems.append(f"{label}: excluded claim '{claim}' appears in output anyway")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    from llm.config import LLMConfig

    cfg = LLMConfig.from_env()
    has_key = bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY"))
    report = {
        "provider": cfg.provider,
        "models": cfg.models,
        "api_key_present": has_key,
        "checks": {},
        "violations": [],
        "comparison": {},
        "status": "PENDING_KEY",
    }
    if not has_key:
        report["required_action"] = (
            "Set ANTHROPIC_API_KEY (or OPENAI_API_KEY with LLM_PROVIDER=openai) "
            "and re-run this script to complete live validation."
        )
        print(
            json.dumps(report, indent=2)
            if args.json
            else "No LLM API key in environment. Live validation NOT performed.\n"
            f"Provider configured: {cfg.provider} (models: {cfg.models})\n"
            "Harness is ready; set ANTHROPIC_API_KEY or OPENAI_API_KEY and re-run."
        )
        return 0  # documented condition, not a failure

    from llm.cache import ResponseCache
    from llm.gateway import Gateway
    from llm.features.evidence_resume import (
        cover_letter_evidence_based,
        deterministic_keyword_alignment,
        tailor_evidence_based,
    )

    gw = Gateway(cfg, cache=ResponseCache(ROOT / "data" / "processed" / "llm_cache.duckdb"))
    opportunity, evidence, base_resume = _build_fixture()
    valid_ids = {e.evidence_id for e in evidence if e.claims_allowed}

    tailor = tailor_evidence_based(base_resume, opportunity, evidence, gw)
    letter = cover_letter_evidence_based(base_resume, opportunity, evidence, gw)
    fallback = deterministic_keyword_alignment(base_resume, opportunity, evidence)

    v1 = _validate_contract(tailor, valid_ids, "tailor")
    v2 = _validate_contract(letter, valid_ids, "cover_letter")
    report["violations"] = v1 + v2
    report["checks"] = {
        "tailor_schema": {
            "markdown_len": len(tailor.markdown or ""),
            "evidence_used": tailor.evidence_used,
            "excluded_claims": tailor.excluded_claims,
            "model_used": tailor.model_used,
        },
        "cover_letter_schema": {
            "markdown_len": len(letter.markdown or ""),
            "evidence_used": letter.evidence_used,
            "excluded_claims": letter.excluded_claims,
            "model_used": letter.model_used,
        },
    }
    # Compare live output vs deterministic fallback (same inputs)
    live_md, fb_md = tailor.markdown.lower(), fallback.markdown.lower()
    report["comparison"] = {
        "fallback_excluded": fallback.excluded_claims,
        "live_keywords_count": len(tailor.keywords),
        "live_cited_evidence": tailor.evidence_used,
        "fallback_cited_evidence": fallback.evidence_used,
        "live_covers_excluded_keyword_anyway": [
            c for c in fallback.excluded_claims if c.lower() in live_md
        ],
    }
    report["tokens_used"] = gw.tokens_used
    report["status"] = "PASS" if not (v1 + v2) else "FAIL"

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Provider: {cfg.provider} | models: {cfg.models}")
        print(
            f"Tailor: {len(tailor.markdown or '')} chars, cited evidence "
            f"{tailor.evidence_used}, excluded {tailor.excluded_claims}"
        )
        print(
            f"Cover letter: {len(letter.markdown or '')} chars, cited "
            f"{letter.evidence_used}, excluded {letter.excluded_claims}"
        )
        print(f"Tokens used: {gw.tokens_used}")
        print(f"STATUS: {report['status']}")
        for v in report["violations"]:
            print(f"  VIOLATION: {v}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
