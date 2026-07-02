#!/usr/bin/env python3
"""LLM skill extraction over distinct job titles -> job_skills_llm table.

Runs AFTER transform.py. Extracts implied skills per distinct title (Haiku tier,
cached instruction prefix, response cache => re-runs are ~free), maps names to
Lightcast taxonomy ids where possible, and expands back to every posting with
that title. Stored in its own table so the flashtext baseline stays untouched;
switch the dashboard with SKILLS_METHOD=llm.
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="max distinct titles (0 = all)")
    ap.add_argument("--batch-size", type=int, default=25)
    args = ap.parse_args()

    # Read phase (read-only connection, released before the long extraction so the
    # live app / other readers are never blocked by this job).
    con = duckdb.connect(str(DB), read_only=True)
    limit_sql = f"LIMIT {args.limit}" if args.limit else ""
    titles = [r[0] for r in con.execute(f"""
        SELECT title FROM job_postings
        WHERE title IS NOT NULL AND title != ''
        GROUP BY title ORDER BY count(*) DESC {limit_sql}
    """).fetchall()]
    postings = con.execute(
        "SELECT id, title, posted_date, noc_code FROM job_postings WHERE title IS NOT NULL"
    ).fetchall()
    con.close()
    print(f"Extracting skills for {len(titles):,} distinct titles...")

    gw = Gateway(
        LLMConfig.from_env(),
        cache=ResponseCache(ROOT / "data" / "processed" / "llm_cache.duckdb"),
    )
    extracted = extract_titles(titles, gw, batch_size=args.batch_size)

    name_to_id, _cat, _name = build_skill_index()
    rows = []
    for pid, title, posted_date, noc_code in postings:
        for item in extracted.get(title, []):
            sid = name_to_id.get(item.name.strip().lower(), f"LOCAL:{item.name.strip()}")
            rows.append({
                "job_id": pid, "skill_id": sid, "skill_name": item.name.strip(),
                "category": item.category, "posted_date": posted_date, "noc_code": noc_code,
            })

    # Write phase (brief write lock only for the table swap)
    wcon = duckdb.connect(str(DB))
    wcon.execute("DROP TABLE IF EXISTS job_skills_llm")
    wcon.execute("""
        CREATE TABLE job_skills_llm (
            job_id INTEGER, skill_id VARCHAR, skill_name VARCHAR, category VARCHAR,
            posted_date DATE, noc_code VARCHAR)
    """)
    if rows:
        df = pd.DataFrame(rows)
        wcon.register("llm_df", df)
        wcon.execute("INSERT INTO job_skills_llm SELECT job_id, skill_id, skill_name, category, posted_date, noc_code FROM llm_df")
    wcon.close()

    n_titles_with = sum(1 for t in titles if extracted.get(t))
    print(f"  titles with skills: {n_titles_with:,}/{len(titles):,}")
    print(f"  job_skills_llm rows: {len(rows):,}")
    print(f"  tokens used: {gw.tokens_used:,}")


if __name__ == "__main__":
    main()
