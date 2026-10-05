#!/usr/bin/env python3
"""
Data-quality gate. Run after transform.py. Exits 1 on any failure.

Asserts row-count floors, null thresholds, join integrity, and freshness so a
silently-degraded pipeline fails loudly instead of shipping a hollow dashboard.
"""
import sys
from pathlib import Path

import duckdb

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "processed" / "career_intel.duckdb"


def main() -> int:
    if not DB_PATH.exists():
        print(f"FAIL: database not found at {DB_PATH}")
        return 1

    db = duckdb.connect(str(DB_PATH), read_only=True)
    checks = []  # (name, passed, detail)

    def q(sql):
        return db.execute(sql).fetchone()[0]

    # --- row-count floors ---
    floors = {
        "job_postings": 1000,
        "job_skills": 500,
        "wages_job_bank": 100,
        "indeed_trends": 100,
        "noc_mapping": 100,
    }
    for table, floor in floors.items():
        n = q(f"SELECT COUNT(*) FROM {table}")
        checks.append((f"{table} >= {floor} rows", n >= floor, f"{n:,} rows"))

    # vacancies_statscan is optional (host may be blocked outside Canada)
    vac = q("SELECT COUNT(*) FROM vacancies_statscan")
    checks.append(("vacancies_statscan present (optional)", True, f"{vac:,} rows"))

    # --- null thresholds ---
    noc_null = q("SELECT 100.0*SUM(CASE WHEN noc_code IS NULL OR noc_code='' THEN 1 ELSE 0 END)/COUNT(*) FROM job_postings")
    checks.append(("job_postings.noc_code null rate < 5%", noc_null < 5, f"{noc_null:.1f}%"))

    sal_present = q("SELECT 100.0*SUM(CASE WHEN salary_median IS NOT NULL THEN 1 ELSE 0 END)/COUNT(*) FROM job_postings")
    checks.append(("job_postings salary present > 20%", sal_present > 20, f"{sal_present:.1f}% have salary"))

    # --- join integrity ---
    orphans = q("SELECT COUNT(*) FROM job_skills s LEFT JOIN job_postings p ON s.job_id=p.id WHERE p.id IS NULL")
    checks.append(("no orphan job_skills", orphans == 0, f"{orphans} orphans"))

    noc_cov = q("""SELECT 100.0*COUNT(DISTINCT CASE WHEN m.noc_code IS NOT NULL THEN p.noc_code END)
                   / NULLIF(COUNT(DISTINCT p.noc_code),0)
                   FROM job_postings p LEFT JOIN noc_mapping m ON p.noc_code=m.noc_code""")
    checks.append(("NOC join coverage > 50%", (noc_cov or 0) > 50, f"{noc_cov:.1f}%"))

    # --- freshness ---
    maxd = q("SELECT max(posted_date) FROM job_postings")
    fresh = q("SELECT date_diff('day', max(posted_date), current_date) FROM job_postings")
    checks.append(("postings fresh (< 365 days)", (fresh or 9999) < 365, f"latest {maxd}, {fresh}d ago"))

    # --- report ---
    print(f"\nData-quality report ({DB_PATH.name})")
    print("-" * 60)
    failed = 0
    for name, passed, detail in checks:
        mark = "PASS" if passed else "FAIL"
        if not passed:
            failed += 1
        print(f"  [{mark}] {name:42} {detail}")
    print("-" * 60)
    if failed:
        print(f"{failed} check(s) FAILED")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
