#!/usr/bin/env python3
"""Generate the monthly market brief -> docs/briefs/YYYY-MM.md.

Idempotent: LLM responses go through the response cache, so re-runs are free.
Requires an LLM API key in the environment (see .env.example).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

from llm.cache import ResponseCache
from llm.config import LLMConfig
from llm.features.brief import _latest_month, make_brief
from llm.gateway import Gateway

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "processed" / "career_intel.duckdb"
OUT_DIR = ROOT / "docs" / "briefs"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", help="YYYY-MM (default: latest month in the data)")
    args = ap.parse_args()

    con = duckdb.connect(str(DB), read_only=True)
    gw = Gateway(LLMConfig.from_env(), cache=ResponseCache(ROOT / "data" / "processed" / "llm_cache.duckdb"))
    month = args.month or _latest_month(con)
    md = make_brief(con, gw, month)
    con.close()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{month}.md"
    out.write_text(md, encoding="utf-8")
    print(f"Wrote {out}  ({gw.tokens_used:,} tokens)")


if __name__ == "__main__":
    main()
