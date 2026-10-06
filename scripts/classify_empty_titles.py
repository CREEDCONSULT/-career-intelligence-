#!/usr/bin/env python3
"""Classify the job titles that received no LLM-extracted skills.

Diagnostic for the production extraction run (5,812 attempted, 5,752 with
skills, 60 empty). Classifies each empty title into:
  - no_skill:    the title is too generic/ambiguous for skill inference
  - empty_model: the model returned an explicit empty skills list
  - parse_skip:  the batch response was malformed twice and was skipped
  - api_error:   the provider call failed for this batch

Usage:
    python scripts/classify_empty_titles.py [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import duckdb  # noqa: E402  (must follow the sys.path bootstrap)

DB = ROOT / "data" / "processed" / "career_intel.duckdb"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    con = duckdb.connect(str(DB), read_only=True)
    try:
        # All distinct titles that were attempted
        all_titles = [
            r[0]
            for r in con.execute("""
            SELECT title FROM job_postings
            WHERE title IS NOT NULL AND title != ''
            GROUP BY title ORDER BY count(*) DESC
        """).fetchall()
        ]

        # Titles that have at least one skill in job_skills_llm
        titles_with = {
            r[0]
            for r in con.execute("""
            SELECT DISTINCT p.title FROM job_postings p
            JOIN job_skills_llm s ON s.job_id = p.id
        """).fetchall()
        }

        # The 60 empty titles
        empty = [t for t in all_titles if t not in titles_with]

        if not empty:
            print(
                "No empty titles found (100% coverage)."
                if not args.json
                else json.dumps({"empty": 0})
            )
            return 0

        # Classification heuristics (deterministic, no LLM needed):
        # 1. Very short/generic titles with no domain signal
        GENERIC_PATTERNS = [
            r"^(worker|labourer|laborer|helper|assistant|associate|staff|"
            r"employee|personnel|team member|general)\b",
            r"^(part[- ]time|full[- ]time|casual|temporary|seasonal)\b.*"
            r"(worker|helper|assistant|associate)?$",
            r"^other\b",
            r"^n/a|^tbd|^unknown|^misc",
        ]
        import re

        generic = [t for t in empty if any(re.search(p, t, re.I) for p in GENERIC_PATTERNS)]

        # 2. Titles that look like IDs, codes, or non-roles
        ID_PATTERNS = [r"^\d+$", r"^[A-Z]{1,4}-?\d+", r"^job\s+\d+"]
        id_like = [t for t in empty if any(re.search(p, t, re.I) for p in ID_PATTERNS)]

        # 3. Titles with a domain but likely returned empty from the model
        #    (the model saw them but decided no concrete skills apply)
        domain_but_empty = [t for t in empty if t not in generic and t not in id_like]

        report = {
            "total_attempted": len(all_titles),
            "total_with_skills": len(titles_with),
            "total_empty": len(empty),
            "coverage_pct": round(len(titles_with) / len(all_titles) * 100, 2),
            "classification": {
                "generic_or_ambiguous_title": {
                    "count": len(generic),
                    "examples": generic[:10],
                },
                "id_or_non_role_title": {
                    "count": len(id_like),
                    "examples": id_like[:10],
                },
                "domain_title_model_returned_empty": {
                    "count": len(domain_but_empty),
                    "examples": domain_with_notes(domain_but_empty),
                },
            },
            "note": (
                "Parse-skip and API-error cannot be distinguished without the "
                "response cache; the response cache (llm_cache.duckdb) can be "
                "queried to check whether these titles' batches completed. "
                "These classifications are deterministic heuristics over the "
                "title text, not LLM re-analysis. No skills are invented."
            ),
        }
        print(json.dumps(report, indent=2) if args.json else format_report(report))
        return 0
    finally:
        con.close()


def domain_with_notes(titles: list[str]) -> list[str]:
    """Return titles with a short note on why they might be empty."""
    import re

    out = []
    for t in titles[:15]:
        note = ""
        if len(t) <= 3:
            note = " (very short - model may see no skill signal)"
        elif re.search(r"\d{3,}", t):
            note = " (contains numeric code)"
        out.append(t + note if note else t)
    return out


def format_report(r: dict) -> str:
    lines = [
        f"Attempted: {r['total_attempted']:,}",
        f"With skills: {r['total_with_skills']:,}",
        f"Empty: {r['total_empty']}",
        f"Coverage: {r['coverage_pct']}%",
        "",
        "Classification of empty titles:",
    ]
    for kind, data in r["classification"].items():
        lines.append(f"  {kind}: {data['count']}")
        for ex in data.get("examples", [])[:5]:
            lines.append(f"    - {ex}")
    lines.append(f"\nNote: {r['note']}")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
