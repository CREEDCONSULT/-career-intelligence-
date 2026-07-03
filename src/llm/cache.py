"""Content-addressed response cache backed by DuckDB.

Keying on sha256(model + "\n" + prompt) makes LLM calls idempotent: reruns of the
monthly brief or batch skill extraction hit the cache and cost nothing. Stored in
its own DuckDB file so it never collides with the analytics database.

Resilience: cloud-sync agents (OneDrive/Google Drive) intermittently lock files in
synced folders, and DuckDB needs exclusive access. A cache must never kill a paid
run — every operation retries briefly, then degrades gracefully (miss / no-op).
"""
from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Optional

import duckdb


class ResponseCache:
    def __init__(self, path: Path | str, retries: int = 3, retry_wait: float = 0.5):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.retries = retries
        self.retry_wait = retry_wait
        self.disabled = False
        try:
            with self._connect() as con:
                con.execute(
                    "CREATE TABLE IF NOT EXISTS llm_cache "
                    "(key TEXT PRIMARY KEY, response TEXT, tokens INTEGER, created TIMESTAMP DEFAULT now())"
                )
        except Exception as e:  # noqa: BLE001 - locked file etc.
            print(f"ResponseCache disabled ({type(e).__name__}: {e}) — continuing without cache.")
            self.disabled = True

    def _connect(self, read_only: bool = False):
        last: Exception | None = None
        for i in range(self.retries):
            try:
                return duckdb.connect(str(self.path), read_only=read_only)
            except Exception as e:  # noqa: BLE001
                last = e
                time.sleep(self.retry_wait * (i + 1))
        assert last is not None
        raise last

    @staticmethod
    def key(model: str, prompt: str) -> str:
        return hashlib.sha256(f"{model}\n{prompt}".encode("utf-8")).hexdigest()

    def get(self, key: str) -> Optional[str]:
        if self.disabled:
            return None
        try:
            with self._connect(read_only=True) as con:
                row = con.execute("SELECT response FROM llm_cache WHERE key = ?", [key]).fetchone()
            return row[0] if row else None
        except Exception:  # noqa: BLE001 - transient lock -> treat as miss
            return None

    def put(self, key: str, response: str, tokens: int = 0) -> None:
        if self.disabled:
            return
        try:
            with self._connect() as con:
                con.execute(
                    "INSERT INTO llm_cache (key, response, tokens) VALUES (?, ?, ?) "
                    "ON CONFLICT (key) DO UPDATE SET response = excluded.response, tokens = excluded.tokens",
                    [key, response, tokens],
                )
        except Exception:  # noqa: BLE001 - transient lock -> skip write
            pass
