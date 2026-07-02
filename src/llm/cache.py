"""Content-addressed response cache backed by DuckDB.

Keying on sha256(model + "\n" + prompt) makes LLM calls idempotent: reruns of the
monthly brief or batch skill extraction hit the cache and cost nothing. Stored in
its own DuckDB file so it never collides with the analytics database.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

import duckdb


class ResponseCache:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with duckdb.connect(str(self.path)) as con:
            con.execute(
                "CREATE TABLE IF NOT EXISTS llm_cache "
                "(key TEXT PRIMARY KEY, response TEXT, tokens INTEGER, created TIMESTAMP DEFAULT now())"
            )

    @staticmethod
    def key(model: str, prompt: str) -> str:
        return hashlib.sha256(f"{model}\n{prompt}".encode("utf-8")).hexdigest()

    def get(self, key: str) -> Optional[str]:
        with duckdb.connect(str(self.path), read_only=True) as con:
            row = con.execute("SELECT response FROM llm_cache WHERE key = ?", [key]).fetchone()
        return row[0] if row else None

    def put(self, key: str, response: str, tokens: int = 0) -> None:
        with duckdb.connect(str(self.path)) as con:
            con.execute(
                "INSERT INTO llm_cache (key, response, tokens) VALUES (?, ?, ?) "
                "ON CONFLICT (key) DO UPDATE SET response = excluded.response, tokens = excluded.tokens",
                [key, response, tokens],
            )
