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


# --- LLM-judge helpers (secondary to the deterministic grounded() check) ---

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def faithfulness(prose: str, context: str, judge: Callable[[str], str]) -> float:
    """Claim-ratio faithfulness: supported claims / total claims (0..1).

    Ragas/DeepEval-style: decompose ``prose`` into atomic claims, verify each
    against ``context`` only. ``judge`` is a callable (e.g. a gateway wrapper)
    that maps a prompt to model text. Raises ValueError if the judge output is
    unparseable. Secondary check — ``grounded()`` stays authoritative for numbers.
    """
    import json as _json

    prompt = (
        "You are a strict fact-checker.\n\n"
        f"CONTEXT (the only source of truth):\n{context}\n\n"
        f"TEXT TO CHECK:\n{prose}\n\n"
        "List every factual claim in the TEXT. For each, decide if it is fully "
        "supported by the CONTEXT alone. Respond with ONLY JSON:\n"
        '{"claims": [{"claim": "...", "supported": true|false}, ...]}'
    )
    raw = judge(prompt) or ""
    m = _JSON_FENCE_RE.search(raw)
    payload = m.group(1) if m else raw
    try:
        data = _json.loads(payload.strip())
        claims = data["claims"]
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"unparseable judge output: {raw[:200]!r}") from e
    if not claims:
        return 1.0
    supported = sum(1 for c in claims if c.get("supported"))
    return supported / len(claims)


def verify(prose: str, context: str, judge: Callable[[str], str], threshold: float = 0.9) -> str:
    """Chain-of-Verification: fact-check the draft against context; if faithfulness
    is below ``threshold``, regenerate using only supported facts. Returns the
    verified prose. ``judge`` maps a prompt to model text (a gateway wrapper)."""
    score = faithfulness(prose, context, judge)
    if score >= threshold:
        return prose
    rewrite_prompt = (
        "Rewrite the following answer so that every statement is fully supported by the "
        "CONTEXT. Remove or correct anything not grounded in it. Keep it concise.\n\n"
        f"CONTEXT:\n{context}\n\nANSWER TO FIX:\n{prose}\n\nReturn only the corrected answer."
    )
    return (judge(rewrite_prompt) or prose).strip()
