"""Validate and safely execute LLM-generated SQL against DuckDB.

Two layers (per research):
  1. Static validation with SQLGlot (DuckDB dialect): parseable, exactly one
     statement, a SELECT at the root, and no write/DDL node anywhere in the tree.
  2. Execution guard: run on the caller's connection wrapped in an outer
     SELECT ... LIMIT cap. The connection should be opened read_only=True.

SQLGlot validates syntax/dialect, not semantics (missing columns) — those surface
as execution errors and are caught and surfaced for the self-correction loop.
"""
from __future__ import annotations

import duckdb
import pandas as pd
import sqlglot
from sqlglot import exp

_DISALLOWED = (
    exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create,
    exp.Alter, exp.Command, exp.TruncateTable,
)
_ALLOWED_ROOT = (exp.Select, exp.Union, exp.Subquery, exp.With)


class GuardError(Exception):
    pass


def validate_select(sql: str) -> exp.Expression:
    """Raise GuardError unless ``sql`` is a single read-only SELECT statement."""
    try:
        statements = [s for s in sqlglot.parse(sql, read="duckdb") if s is not None]
    except Exception as e:  # noqa: BLE001
        raise GuardError(f"unparseable SQL: {e}") from e

    if len(statements) != 1:
        raise GuardError(f"exactly one statement required (got {len(statements)})")

    root = statements[0]
    if not isinstance(root, _ALLOWED_ROOT):
        raise GuardError(f"only SELECT queries allowed, got {type(root).__name__}")

    hidden = list(root.find_all(*_DISALLOWED))
    if hidden:
        raise GuardError(f"disallowed operation: {type(hidden[0]).__name__}")
    return root


def run_guarded(con: duckdb.DuckDBPyConnection, sql: str, row_cap: int = 1000) -> pd.DataFrame:
    """Validate then execute, capping the result to ``row_cap`` rows."""
    validate_select(sql)
    capped = f"SELECT * FROM ({sql.rstrip().rstrip(';')}) AS _guarded_q LIMIT {row_cap}"
    try:
        return con.execute(capped).df()
    except Exception as e:  # noqa: BLE001
        raise GuardError(f"execution failed: {e}") from e
