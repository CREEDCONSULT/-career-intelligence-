"""Phase 5: grounded career-advisor chat.

Plan → fetch → compose, with strict grounding:
  1. plan_queries: turn the user's question into up to 2 concrete data questions,
     or OUT_OF_SCOPE (refuse anything the dataset can't answer).
  2. For each, run the Phase-1 ask() pipeline → grounded SQL result tables.
  3. compose advice using ONLY those numbers; gate with the deterministic
     grounded() check (regenerate once) and the CoVe verify() faithfulness pass.

The advisor never invents a figure — advice is built strictly on retrieved,
executed data, and out-of-scope questions are refused rather than hallucinated.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from llm.features.ask import ask as _ask
from llm.grounding import grounded, verify

REFUSAL = (
    "I can only answer questions grounded in the Toronto job-market data (skills in demand, "
    "salaries, vacancies, hiring trends, and role fit). I don't have data to answer that one."
)


@dataclass
class Advice:
    question: str
    answer: str
    sources: list = field(default_factory=list)
    refused: bool = False


def _plan_queries(gw, question: str) -> list[str]:
    prompt = (
        "You route questions for a Toronto job-market assistant. Its data covers: skills in "
        "demand, salaries/wages by occupation, job vacancies, hiring trends, and AI-share of "
        "postings.\n\n"
        f"User question: {question}\n\n"
        "If it can be answered from that data, output 1-2 specific data questions (one per line) "
        "that would inform the answer. If it cannot, output exactly OUT_OF_SCOPE."
    )
    text = (gw.complete([{"role": "user", "content": prompt}], tier="interactive").text or "").strip()
    if "OUT_OF_SCOPE" in text.upper():
        return []
    queries = []
    for line in text.splitlines():
        line = line.strip().lstrip("0123456789.-) ").strip()
        if line and "OUT_OF_SCOPE" not in line.upper():
            queries.append(line)
    return queries[:2]


def _numbers_df(sources) -> pd.DataFrame:
    """Every number the advice may legitimately cite: numeric cells plus the
    years/months implied by any date column (so "in 2026" isn't false-flagged)."""
    vals = []
    for ans in sources:
        if ans.table is None:
            continue
        for col in ans.table.columns:
            series = ans.table[col]
            nums = pd.to_numeric(series, errors="coerce").dropna()
            vals.extend(nums.tolist())
            dt = pd.to_datetime(series, errors="coerce").dropna()
            if len(dt):
                vals.extend(dt.dt.year.unique().tolist())
                vals.extend(dt.dt.month.unique().tolist())
    return pd.DataFrame({"v": vals}) if vals else pd.DataFrame({"v": []})


def _compose(gw, question: str, context: str, corrective: str = "") -> str:
    prompt = (
        f"You are a concise Toronto career advisor. Using ONLY the data below, answer the user's "
        f"question in 2-4 sentences with a concrete recommendation. Cite figures verbatim from the "
        f"data — never invent or round to new numbers.{corrective}\n\n"
        f"USER QUESTION: {question}\n\nDATA:\n{context}"
    )
    return (gw.complete([{"role": "user", "content": prompt}], tier="interactive").text or "").strip()


def advise(question: str, con, gw, ask_fn=_ask) -> Advice:
    plan = _plan_queries(gw, question)
    if not plan:
        return Advice(question, REFUSAL, sources=[], refused=True)

    sources = []
    context_parts = []
    for q in plan:
        ans = ask_fn(q, con, gw)
        if ans is not None and ans.table is not None and not ans.table.empty:
            sources.append(ans)
            context_parts.append(f"[{q}]\n{ans.table.head(20).to_string(index=False)}")
    if not sources:
        return Advice(question, "I couldn't retrieve data for that — try rephrasing.", sources=[], refused=False)

    context = "\n\n".join(context_parts)
    numbers_df = _numbers_df(sources)

    draft = _compose(gw, question, context)
    ok, _ = grounded(draft, numbers_df, allow_sums=True)
    if not ok:
        draft = _compose(gw, question, context,
                         corrective=" Your previous answer used a number not in the data; use only the exact figures shown.")
        ok, _ = grounded(draft, numbers_df, allow_sums=True)

    judge = lambda p: gw.complete([{"role": "user", "content": p}], tier="interactive").text  # noqa: E731
    verified = verify(draft, context, judge, threshold=0.9)
    # final deterministic guard: if the verified rewrite reintroduced an ungrounded number, keep the grounded draft
    if grounded(verified, numbers_df, allow_sums=True)[0]:
        answer = verified
    elif ok:
        answer = draft
    else:
        answer = "Based on the data: " + "; ".join(context_parts[0].splitlines()[1:3])

    return Advice(question, answer, sources=sources, refused=False)
