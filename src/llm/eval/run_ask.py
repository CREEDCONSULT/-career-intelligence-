"""Run the live text-to-SQL eval over the gold set against the real DuckDB.

Usage: load .env first, then `python -m llm.eval.run_ask`.
Reports execution accuracy and numeric-grounding, plus per-question detail.
"""
from __future__ import annotations

from pathlib import Path

import duckdb

from llm.config import LLMConfig
from llm.eval.runner import execution_accuracy, load_gold
from llm.features.ask import ask
from llm.gateway import Gateway

DB = Path(__file__).resolve().parents[3] / "data" / "processed" / "career_intel.duckdb"


def main():
    con = duckdb.connect(str(DB), read_only=True)
    gw = Gateway(LLMConfig.from_env())
    gold = load_gold()
    correct = grounded_ok = errors = 0
    for i, item in enumerate(gold, 1):
        ans = ask(item["question"], con, gw)
        ok = bool(ans.sql) and ans.table is not None and execution_accuracy(
            con, ans.sql, item["reference_sql"]
        )
        correct += int(ok)
        grounded_ok += int(ans.grounded)
        errors += int(ans.error is not None)
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] Q{i:02d} grounded={ans.grounded} :: {item['question'][:55]}")
        if not ok and ans.sql:
            print(f"        got: {ans.sql[:90]}")
    n = len(gold)
    print("\n" + "=" * 50)
    print(f"execution accuracy : {correct}/{n} = {correct/n:.0%}")
    print(f"numeric grounding  : {grounded_ok}/{n} = {grounded_ok/n:.0%}")
    print(f"sql errors         : {errors}")
    print(f"tokens used        : {gw.tokens_used:,}")


if __name__ == "__main__":
    main()
