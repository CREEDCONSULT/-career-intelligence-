"""Salary parsing & normalization for Job Bank postings.

Job Bank postings carry ``Salary Minimum`` / ``Salary Maximum`` plus a
``Salary Per`` unit ("Hour", "Year", "Week", "Month"). We normalize everything
to an hourly equivalent so roles are comparable.
"""
from __future__ import annotations

from typing import Optional

HOURS_PER_YEAR = 2080  # 40h * 52w
HOURS_PER_MONTH = 173.33  # 2080 / 12
HOURS_PER_WEEK = 40


def _to_float(value) -> Optional[float]:
    if value is None:
        return None
    s = str(value).strip()
    if s == "" or s.upper() in ("NA", "N/A", "NAN", "NONE"):
        return None
    s = s.replace("$", "").replace(",", "")
    try:
        f = float(s)
    except ValueError:
        return None
    return f if f > 0 else None


def to_hourly(value: float, per: str) -> float:
    """Convert a salary figure to its hourly equivalent given the period unit."""
    p = (per or "").strip().lower()
    if p in ("year", "yearly", "annual", "annually"):
        return value / HOURS_PER_YEAR
    if p in ("month", "monthly"):
        return value / HOURS_PER_MONTH
    if p in ("week", "weekly"):
        return value / HOURS_PER_WEEK
    return float(value)  # hour / hourly / unknown -> treat as hourly


def parse_salary_row(row: dict) -> dict:
    """Return {salary_min, salary_max, salary_median} as hourly-normalized floats or None."""
    per = row.get("Salary Per") or row.get("salary_per") or "Hour"
    lo = _to_float(row.get("Salary Minimum", row.get("salary_min")))
    hi = _to_float(row.get("Salary Maximum", row.get("salary_max")))
    lo_h = to_hourly(lo, per) if lo is not None else None
    hi_h = to_hourly(hi, per) if hi is not None else None

    if lo_h is not None and hi_h is not None:
        median = (lo_h + hi_h) / 2
    else:
        median = lo_h if lo_h is not None else hi_h

    return {"salary_min": lo_h, "salary_max": hi_h, "salary_median": median}
