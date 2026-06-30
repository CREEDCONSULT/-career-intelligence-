"""Build a compact schema card for text-to-SQL prompting.

The card is the large, stable prompt prefix — cache it (Anthropic prompt caching)
so only the per-question text varies. It introspects the live DuckDB schema and
appends fixed domain notes (join keys, the title-based-skills limitation, wage
normalization, the long-format indeed_trends table) so the model generates correct,
honest SQL.
"""
from __future__ import annotations

import duckdb

_NOTES = """
Domain notes:
- Join occupations across tables on `noc_code` (5-digit NOC 2021, zero-padded). `noc_mapping.title` gives readable role names.
- `job_skills` rows are skills extracted from the job TITLE + NOC occupation name (Job Bank postings have no requirements free-text). Treat as occupational/role demand, not a full skills census.
- Wages in `wages_job_bank` are normalized to an HOURLY equivalent (annual figures divided by 2080).
- `indeed_trends` is LONG-format: filter by `metric` in ('postings_index','wage_growth','ai_share'); `value` holds the number; `geography` is 'Toronto' or 'Canada'.
- `job_postings.posted_date` may be NULL for some rows; aggregate over non-null dates.
- All data is filtered to the Toronto / GTA market.
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
    return "\n".join(lines) + "\n" + _NOTES
