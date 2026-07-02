"""Grounding guards for LLM narration.

``grounded()`` is the DETERMINISTIC guard and the core of the auditability moat:
every number that appears in the prose must be present in the source result set
(within tolerance), optionally allowing simple sums of cells. Research flagged that
claim-ratio *faithfulness* can miss numeric hallucinations (wrong/transposed
figures), so this deterministic check is the primary guard; ``faithfulness()`` and
``verify()`` (LLM-judge / Chain-of-Verification) are secondary, used in later phases.
"""
from __future__ import annotations

import re
from itertools import combinations
from typing import Callable, Optional

import pandas as pd

_NUM_RE = re.compile(r"-?\$?\d[\d,]*\.?\d*%?")


def _to_float(token: str) -> Optional[float]:
    t = token.replace("$", "").replace(",", "").replace("%", "")
    try:
        return float(t)
    except ValueError:
        return None


def numbers_in(text: str) -> set[float]:
    """Every numeric literal in ``text`` as floats ($, commas, % stripped)."""
    out: set[float] = set()
    for m in _NUM_RE.findall(text or ""):
        v = _to_float(m)
        if v is not None:
            out.add(v)
    return out


def _cell_values(df: pd.DataFrame) -> set[float]:
    vals: set[float] = set()
    for col in df.columns:
        for v in pd.to_numeric(df[col], errors="coerce").dropna().tolist():
            vals.add(round(float(v), 4))
    return vals


def grounded(prose: str, df: pd.DataFrame, allow_sums: bool = False, tol: float = 0.01):
    """Return (is_grounded, unguarded_numbers).

    Every number in ``prose`` must match a cell value (or, if ``allow_sums``, a
    small sum of cells) within absolute or relative tolerance ``tol``.
    """
    cells = _cell_values(df)
    derived = set(cells)
    if allow_sums and 0 < len(cells) <= 12:
        for r in range(2, min(len(cells), 6) + 1):
            for combo in combinations(cells, r):
                derived.add(round(sum(combo), 4))

    unguarded: list[float] = []
    for n in numbers_in(prose):
        if not any(abs(n - c) <= tol or (c != 0 and abs(n - c) / abs(c) <= tol) for c in derived):
            unguarded.append(n)
    return (len(unguarded) == 0, unguarded)


# --- LLM-judge helpers (exercised in later phases; need a `judge` callable) ---

def faithfulness(prose: str, context: str, judge: Callable[[str], str]) -> float:
    """Claim-ratio faithfulness: supported claims / total claims (0..1).

    ``judge`` is a callable (the gateway) that, given a prompt, returns text. This
    is a secondary check; the deterministic ``grounded()`` is authoritative for
    numbers. Implemented in Phase 2 where briefs need long-form scoring.
    """
    raise NotImplementedError("faithfulness scoring is implemented in Phase 2")


def verify(prose: str, judge: Callable[[str], str]) -> str:
    """Chain-of-Verification 4-step regeneration. Implemented in Phase 5 (advisor)."""
    raise NotImplementedError("CoVe verify is implemented in Phase 5")
