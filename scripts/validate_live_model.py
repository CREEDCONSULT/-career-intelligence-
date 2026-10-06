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

# Shared helpers live in the installed careeros package so the pytest live
# tests can import them without path hacks.
from careeros.live_validation import (  # noqa: E402
    build_validation_fixture as _build_fixture,
    validate_evidence_contract as _validate_contract,
)


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
    live_md = tailor.markdown.lower()
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
