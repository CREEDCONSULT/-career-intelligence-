"""Build a compact schema card for text-to-SQL prompting.

The card is the large, stable prompt prefix — cache it (Anthropic prompt caching)
so only the per-question text varies. It introspects the live DuckDB schema and
appends fixed domain notes (join keys, the title-based-skills limitation, wage
normalization, the long-format indeed_trends table) so the model generates correct,
honest SQL.
"""
from __future__ import annotations

import duckdb

from pipeline.market import load_market

_NOTES_TEMPLATE = """
Domain notes and query conventions (follow these):
- Join occupations across tables on `noc_code` (5-digit NOC 2021, zero-padded). When the question refers to a role/occupation by name, JOIN `noc_mapping` and use `noc_mapping.title`; do not return bare noc_code.
- To count or trend postings that involve a SKILL, use the `job_skills` table (filter/group by `job_skills.skill_name`, count DISTINCT job_id). Do NOT pattern-match `job_postings.title` for skills.
- `job_skills` rows are skills extracted from the job TITLE + NOC occupation name (postings have no requirements free-text). Treat as occupational/role demand, not a full skills census.
- Wage questions use `wages_job_bank` (normalized to HOURLY, annual/2080) and vacancy questions use `vacancies_statscan`; for both, filter `region = '{region}'` unless the question explicitly asks otherwise.
- `indeed_trends` is LONG-format: filter by `metric` in ('postings_index','wage_growth','ai_share'); `value` holds the number; `geography` is '{market}' (postings_index) or 'Canada' (wage_growth, ai_share).
- `posted_date` may be NULL; aggregate only over non-null dates (add `WHERE posted_date IS NOT NULL`).
- For "top N" / "which N" questions, add an explicit `ORDER BY ... DESC LIMIT N` (default N=10 if unspecified).
- All data is already filtered to the {market} market.
Only generate read-only SELECT queries.
"""


def build_schema_card(con: duckdb.DuckDBPyConnection) -> str:
    rows = con.execute(
        "SELECT table_name, column_name, data_type "
        "FROM information_schema.columns "
        "WHERE table_schema = 'main' "
        "ORDER BY table_name, ordinal_position"
    ).fetchall()

    tables: dict[str, list[str]] = {}
    for table, col, dtype in rows:
        tables.setdefault(table, []).append(f"{col} {dtype}")

    lines = ["Database: DuckDB. Tables and columns:"]
    for table, cols in tables.items():
        lines.append(f"- {table}({', '.join(cols)})")
    m = load_market()
    notes = _NOTES_TEMPLATE.format(region=m.economic_region_name, market=m.name)
    return "\n".join(lines) + "\n" + notes
