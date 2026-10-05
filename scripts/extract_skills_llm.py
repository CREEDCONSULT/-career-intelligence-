#!/usr/bin/env python3
"""LLM skill extraction over distinct job titles -> job_skills_llm table.

Runs AFTER transform.py. Extracts implied skills per distinct title (Haiku tier,
cached instruction prefix, response cache => re-runs are ~free), maps names to
Lightcast taxonomy ids where possible, and expands back to every posting with
that title. Stored in its own table so the flashtext baseline stays untouched;
switch the dashboard with SKILLS_METHOD=llm.

CI / offline mode (--fixture): populates job_skills_llm with DETERMINISTIC
dictionary (flashtext) extraction over the same titles - NO LLM is called and
the data is NOT production LLM output. Every fixture run writes a
job_skills_llm_meta provenance table recording source='fixture:flashtext'
so downstream consumers can tell fixture data from real extraction. Production
population requires ANTHROPIC_API_KEY (or OPENAI_API_KEY) and a live run
WITHOUT --fixture.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb
import pandas as pd

from llm.cache import ResponseCache
from llm.config import LLMConfig
from llm.features.skills_llm import extract_titles
from llm.gateway import Gateway
from pipeline.skill_matcher import build_skill_index

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "processed" / "career_intel.duckdb"


def _fixture_extract(titles: list[str]) -> dict[str, list]:
    """Deterministic dictionary extraction over titles (no LLM, no network).

    Returns {title: [{"name": skill, "category": cat}, ...]} shaped like the
    LLM extractor's output so the downstream expansion is identical.
    """
    from pipeline.skill_matcher import SkillMatcher

    name_to_id, cat_by_id, name_by_id = build_skill_index()
    matcher = SkillMatcher(name_to_id)
    out: dict[str, list] = {}
    for title in titles:
        skills = []
        for sid in matcher.kp.extract_keywords(title):
            skills.append(
                {
                    "name": name_by_id.get(sid, sid),
                    "category": cat_by_id.get(sid, "Specialized Skill"),
                }
            )
        if skills:
            out[title] = skills
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="max distinct titles (0 = all)")
    ap.add_argument("--batch-size", type=int, default=25)
    ap.add_argument(
        "--fixture",
        action="store_true",
        help="CI/offline mode: deterministic dictionary extraction. "
        "NOT production LLM output; provenance is recorded in "
        "job_skills_llm_meta.",
    )
    args = ap.parse_args()

    # Read phase (read-only connection, released before the long extraction so the
    # live app / other readers are never blocked by this job).
    con = duckdb.connect(str(DB), read_only=True)
    limit_sql = f"LIMIT {args.limit}" if args.limit else ""
    titles = [
        r[0]
        for r in con.execute(f"""
        SELECT title FROM job_postings
        WHERE title IS NOT NULL AND title != ''
        GROUP BY title ORDER BY count(*) DESC {limit_sql}
    """).fetchall()
    ]
    postings = con.execute(
        "SELECT id, title, posted_date, noc_code FROM job_postings WHERE title IS NOT NULL"
    ).fetchall()
    con.close()

    if args.fixture:
        print("FIXTURE MODE: deterministic dictionary extraction (NO LLM call).")
        print("This data is for CI only; production requires a live run with an API key.")
        extracted = _fixture_extract(titles)
        source = "fixture:flashtext"
    else:
        if not (
            LLMConfig.from_env().provider
            and (
                __import__("os").getenv("ANTHROPIC_API_KEY")
                or __import__("os").getenv("OPENAI_API_KEY")
            )
        ):
            raise SystemExit(
                "Live extraction requires ANTHROPIC_API_KEY or OPENAI_API_KEY. "
                "For CI/offline table population use --fixture (deterministic, "
                "provenance-recorded, NOT production data)."
            )
        print(f"Extracting skills for {len(titles):,} distinct titles...")
        gw = Gateway(
            LLMConfig.from_env(),
            cache=ResponseCache(ROOT / "data" / "processed" / "llm_cache.duckdb"),
        )
        extracted = extract_titles(titles, gw, batch_size=args.batch_size)
        source = f"llm:{LLMConfig.from_env().provider}"

    name_to_id, _cat, _name = build_skill_index()
    rows = []
    for pid, title, posted_date, noc_code in postings:
        for item in extracted.get(title, []):
            name = item.name if hasattr(item, "name") else item["name"]
            category = (
                item.category
                if hasattr(item, "category")
                else item.get("category", "Specialized Skill")
            )
            sid = name_to_id.get(name.strip().lower(), f"LOCAL:{name.strip()}")
            rows.append(
                {
                    "job_id": pid,
                    "skill_id": sid,
                    "skill_name": name.strip(),
                    "category": category,
                    "posted_date": posted_date,
                    "noc_code": noc_code,
                }
            )

    # Write phase (brief write lock only for the table swap). Retry hard: losing a
    # paid extraction to a transient cloud-sync file lock is unacceptable.
    import time
    import datetime as _dt

    wcon = None
    for attempt in range(10):
        try:
            wcon = duckdb.connect(str(DB))
            break
        except Exception as e:  # noqa: BLE001
            print(f"  DB locked ({e}); retry {attempt + 1}/10 in 3s...")
            time.sleep(3)
    if wcon is None:
        raise SystemExit("Could not open DB for writing after retries.")
    wcon.execute("DROP TABLE IF EXISTS job_skills_llm")
    wcon.execute("""
        CREATE TABLE job_skills_llm (
            job_id INTEGER, skill_id VARCHAR, skill_name VARCHAR, category VARCHAR,
            posted_date DATE, noc_code VARCHAR)
    """)
    if rows:
        df = pd.DataFrame(rows)
        wcon.register("llm_df", df)
        wcon.execute(
            "INSERT INTO job_skills_llm SELECT job_id, skill_id, skill_name, category, posted_date, noc_code FROM llm_df"
        )
    # Provenance: consumers must be able to tell fixture data from live LLM output.
    wcon.execute("DROP TABLE IF EXISTS job_skills_llm_meta")
    wcon.execute("""
        CREATE TABLE job_skills_llm_meta (
            source VARCHAR, fixture_mode BOOLEAN, created_at TIMESTAMP)
    """)
    wcon.execute(
        "INSERT INTO job_skills_llm_meta VALUES (?, ?, ?)",
        [source, bool(args.fixture), _dt.datetime.now().isoformat(sep=" ")],
    )
    wcon.close()

    n_titles_with = sum(1 for t in titles if extracted.get(t))
    print(f"  titles with skills: {n_titles_with:,}/{len(titles):,}")
    print(f"  job_skills_llm rows: {len(rows):,}")
    if not args.fixture:
        print(f"  tokens used: {gw.tokens_used:,}")
    print(f"  provenance recorded: source={source}")


if __name__ == "__main__":
    main()
