"""Eval runners for the LLM layer.

`execution_accuracy` compares the RESULT SETS of predicted vs. reference SQL
(per Ragas guidance — not SQL string match), order-insensitive on rows and
tolerant of float rounding. `load_gold` / `validate_gold` work with the gold set.
`run_ask_eval` (needs a live gateway + the Phase-1 ask pipeline) reports execution
accuracy % and numeric-grounding %.
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd

from llm.sql_guard import GuardError, run_guarded

GOLD_PATH = Path(__file__).resolve().parent / "gold" / "ask_gold.json"


def load_gold(path: Path = GOLD_PATH) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _normalize(df: pd.DataFrame) -> list[tuple]:
    rows = []
    for row in df.itertuples(index=False):
        norm = []
        for v in row:
            if isinstance(v, float):
                norm.append(round(v, 2))
            else:
                norm.append(v)
        rows.append(tuple(norm))
    return sorted(rows, key=lambda t: str(t))


def execution_accuracy(con: duckdb.DuckDBPyConnection, predicted_sql: str, reference_sql: str) -> bool:
    """True iff predicted and reference SQL produce the same result set."""
    try:
        pred = run_guarded(con, predicted_sql, row_cap=5000)
        ref = run_guarded(con, reference_sql, row_cap=5000)
    except GuardError:
        return False
    if pred.shape[1] != ref.shape[1]:
        return False
    return _normalize(pred) == _normalize(ref)


def validate_gold(con: duckdb.DuckDBPyConnection, gold: list[dict]) -> list[str]:
    """Return a list of gold entries whose reference SQL fails to execute (empty = all valid)."""
    failures = []
    for item in gold:
        try:
            run_guarded(con, item["reference_sql"], row_cap=5000)
        except GuardError as e:
            failures.append(f"{item['question']!r}: {e}")
    return failures


def run_ask_eval(con, gw, ask_fn, gold: list[dict] | None = None) -> dict:
    """Run the ask pipeline over the gold set; report execution accuracy + grounding.

    ``ask_fn(question, con, gw)`` must return an object with `.sql`, `.table`,
    `.grounded`. Used in Phase 1 (needs a live gateway).
    """
    gold = gold or load_gold()
    correct = 0
    grounded_ok = 0
    for item in gold:
        ans = ask_fn(item["question"], con, gw)
        if ans.sql and execution_accuracy(con, ans.sql, item["reference_sql"]):
            correct += 1
        if getattr(ans, "grounded", False):
            grounded_ok += 1
    n = len(gold)
    return {
        "n": n,
        "execution_accuracy": round(correct / n, 3) if n else 0.0,
        "numeric_grounding": round(grounded_ok / n, 3) if n else 0.0,
    }
