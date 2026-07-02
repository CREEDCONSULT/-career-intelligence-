"""Phase 1: grounded text-to-SQL Q&A.

Pipeline: schema-linked prompt -> LLM SQL -> SQLGlot validate -> read-only execute
-> execution-guided self-correction (feed the error back) -> grounded narration
(every prose number must appear in the result set, else regenerate/flag).

The LLM never emits a figure: numbers come from the executed SQL, and narration is
verified against those numbers by `grounding.grounded`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import duckdb
import pandas as pd

from llm.grounding import grounded
from llm.schema import build_schema_card
from llm.sql_guard import GuardError, run_guarded

_MAX_SQL_RETRIES = 2
_FENCE_RE = re.compile(r"```(?:sql)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


@dataclass
class Answer:
    question: str
    sql: Optional[str]
    table: Optional[pd.DataFrame]
    prose: str
    grounded: bool
    error: Optional[str] = None


def _clean_sql(text: str) -> str:
    m = _FENCE_RE.search(text or "")
    sql = m.group(1) if m else (text or "")
    return sql.strip().rstrip(";").strip()


def _gen_sql(gw, card: str, question: str, prior_error: str | None = None) -> str:
    user = (
        f"Write a single DuckDB SELECT query that answers this question:\n{question}\n\n"
        "Return ONLY the SQL — no explanation, no markdown fences."
    )
    if prior_error:
        user += f"\n\nYour previous query failed with:\n{prior_error}\nFix it and return only the corrected SQL."
    resp = gw.complete(
        [{"role": "user", "content": user}], tier="interactive", cache_prefix=card
    )
    return _clean_sql(resp.text)


def _narrate(gw, question: str, df: pd.DataFrame) -> tuple[str, bool]:
    table_txt = df.head(50).to_string(index=False)
    base = (
        f"Question: {question}\n\nResult table:\n{table_txt}\n\n"
        "Answer in 1-2 sentences. Cite ONLY numbers that appear verbatim in the table above — "
        "do not compute new totals, percentages, or rounded values. Prefer naming the single "
        "headline figure that answers the question. If the table is empty, say so."
    )
    for _ in range(2):
        resp = gw.complete([{"role": "user", "content": base}], tier="interactive")
        prose = (resp.text or "").strip()
        ok, _unguarded = grounded(prose, df, allow_sums=True)
        if ok:
            return prose, True
    return prose, False


def ask(question: str, con: duckdb.DuckDBPyConnection, gw) -> Answer:
    card = build_schema_card(con)
    sql = _gen_sql(gw, card, question)
    error = None
    for attempt in range(_MAX_SQL_RETRIES + 1):
        try:
            table = run_guarded(con, sql, row_cap=1000)
            prose, is_grounded = _narrate(gw, question, table)
            return Answer(question, sql, table, prose, is_grounded)
        except GuardError as e:
            error = str(e)
            if attempt < _MAX_SQL_RETRIES:
                sql = _gen_sql(gw, card, question, prior_error=error)
    return Answer(question, sql, None, "", False, error=error)
