"""File-backed daily LLM token usage counter.

Guards public deployments: the Ask page checks ``today()`` against a daily cap
before each call and ``add()``s the spent tokens after. JSON file keyed by date,
auto-resets when the date changes. Deliberately simple — a single-process
Streamlit deploy is the target; for multi-instance use, move to a shared store.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Callable


def _today_iso() -> str:
    return date.today().isoformat()


class DailyUsage:
    def __init__(self, path: Path | str, today_fn: Callable[[], str] = _today_iso):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._today_fn = today_fn

    def _load(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError
        except Exception:  # noqa: BLE001 - missing/corrupt file -> fresh state
            data = {}
        if data.get("date") != self._today_fn():
            data = {"date": self._today_fn(), "tokens": 0}
        return data

    def today(self) -> int:
        return int(self._load().get("tokens", 0))

    def add(self, tokens: int) -> None:
        data = self._load()
        data["tokens"] = int(data.get("tokens", 0)) + int(tokens)
        self.path.write_text(json.dumps(data), encoding="utf-8")
