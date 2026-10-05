"""Canonical job-opportunity model, normalizer, and store.

M1 rules:
- ``Unknown stays unknown``: the normalizer only fills a field when the source
  text clearly supports it; otherwise the field remains ``None``.
- Every opportunity records how it entered the system (``provenance``).
- Deterministic parsing only - no LLM, no scraping.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import duckdb

# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

OPPORTUNITY_STATUSES = ("new", "active", "archived")

WORK_MODES = ("remote", "hybrid", "on-site")
EMPLOYMENT_TYPES = ("full-time", "part-time", "contract", "temporary", "internship")
SENIORITIES = ("junior", "mid", "senior", "lead", "principal", "staff")


@dataclass
class Opportunity:
    """A single job opportunity the user may act on.

    All optional fields default to ``None`` - ``None`` means "unknown", never
    "empty string" or a guessed value.
    """

    opportunity_id: int
    source: str
    external_job_id: Optional[str] = None
    source_url: Optional[str] = None
    company: Optional[str] = None
    role_title: Optional[str] = None
    location: Optional[str] = None
    work_mode: Optional[str] = None  # remote | hybrid | on-site
    employment_type: Optional[str] = None  # full-time | part-time | ...
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    currency: Optional[str] = None  # ISO code when stated, else None
    posted_at: Optional[date] = None
    discovered_at: Optional[date] = None
    closing_date: Optional[date] = None
    description_raw: Optional[str] = None
    description_normalized: Optional[str] = None
    required_skills: list[str] = field(default_factory=list)
    preferred_skills: list[str] = field(default_factory=list)
    responsibilities: list[str] = field(default_factory=list)
    seniority: Optional[str] = None
    status: str = "new"
    notes: Optional[str] = None
    provenance: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Deterministic normalization (never fabricates)
# ---------------------------------------------------------------------------

_WORK_MODE_PATTERNS = [
    (re.compile(r"\bremote\b", re.I), "remote"),
    (re.compile(r"\bhybrid\b", re.I), "hybrid"),
    (re.compile(r"\bon[- ]site\b|\bin[- ]office\b|\bin person\b", re.I), "on-site"),
]

_EMPLOYMENT_PATTERNS = [
    (re.compile(r"\bfull[- ]time\b", re.I), "full-time"),
    (re.compile(r"\bpart[- ]time\b", re.I), "part-time"),
    (re.compile(r"\bcontract\b", re.I), "contract"),
    (re.compile(r"\btemporary\b|\btemp\b", re.I), "temporary"),
    (re.compile(r"\binternship\b|\bco[- ]op\b", re.I), "internship"),
]

_SENIORITY_PATTERNS = [
    (re.compile(r"\bprincipal\b", re.I), "principal"),
    (re.compile(r"\bstaff (engineer|developer|scientist|designer)\b", re.I), "staff"),
    (re.compile(r"\blead\b|\btech lead\b|\bteam lead\b", re.I), "lead"),
    (re.compile(r"\bsenior\b|\bsr\.?\b", re.I), "senior"),
    (re.compile(r"\bjunior\b|\bjr\.?\b|\bentry[- ]level\b|\bgraduate\b", re.I), "junior"),
]

# "6-8 years", "3+ years", "five years" (approx; only digits handled)
_YEARS_RE = re.compile(r"(\d{1,2})\s*\+?\s*(?:-|to)?\s*(\d{0,2})\s*\+?\s*years?", re.I)

# Closing date: "Apply by Nov 15, 2026" | "apply by 2026-11-15" | "closing date: 15 Nov 2026"
_CLOSING_RE = re.compile(
    r"(?:apply by|applications? due|closing date(?:\s*:)?|deadline(?:\s*:)?)\s*"
    r"(?P<d>\d{4}-\d{2}-\d{2}|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}|\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{4})",
    re.I,
)

_SALARY_PATTERNS = [
    # $90,000 - $110,000 | $90k-$110k | CAD 90k-110k
    re.compile(
        r"(?P<cur>cad|usd|eur)?\s*\$?\s*(?P<lo>[\d]{2,3}(?:,\d{3})?|\d+[km])"
        r"\s*(?:-|–|to)\s*\$?\s*(?P<hi>[\d]{2,3}(?:,\d{3})?|\d+[km])",
        re.I,
    ),
    # "$45 to $55 per hour" -> annualized? NO: store as-is (hourly unknown units kept raw)
]


def _parse_money(tok: str) -> Optional[float]:
    """'$110,000' | '110k' | '90k' -> float, else None."""
    tok = tok.strip().lower().replace(",", "").replace("$", "")
    if not tok:
        return None
    if tok.endswith("k"):
        try:
            return float(tok[:-1]) * 1_000
        except ValueError:
            return None
    if tok.endswith("m"):
        return None  # 'm' suffix too ambiguous for salary ranges
    try:
        v = float(tok)
        # Heuristic: a bare 2-digit number in a range like 90-110 means thousands
        return v * 1_000 if 0 < v < 1_000 else v
    except ValueError:
        return None


def _first_match(patterns, text: str) -> Optional[str]:
    for pattern, value in patterns:
        if pattern.search(text):
            return value
    return None


def _parse_date(value: Any) -> Optional[date]:
    if value is None or isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def parse_salary(text: str) -> tuple[Optional[float], Optional[float], Optional[str]]:
    """Extract (min, max, currency) from free text. Returns (None, None, None) when absent.

    Never guesses currency: only an explicit CAD/USD/EUR token sets it.
    """
    if not text:
        return None, None, None
    for pat in _SALARY_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        lo = _parse_money(m.group("lo"))
        hi = _parse_money(m.group("hi"))
        if lo is None or hi is None:
            continue
        if lo > hi:
            lo, hi = hi, lo
        cur = (m.group("cur") or "").upper() or None
        return lo, hi, cur
    return None, None, None


def parse_closing_date(text: str) -> Optional[date]:
    """Extract a closing/application deadline from free text, else None."""
    if not text:
        return None
    m = _CLOSING_RE.search(text)
    if not m:
        return None
    tok = m.group("d").strip()
    try:
        return date.fromisoformat(tok)
    except ValueError:
        pass
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%b %d %Y", "%B %d %Y", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(tok, fmt).date()
        except ValueError:
            continue
    return None


def parse_seniority_from_years(text: str) -> Optional[str]:
    """Years-of-experience requirement -> a conservative seniority band.

    For a range ("3-5 years") the UPPER bound decides - employers size the
    role at the top of the stated range. Deliberately coarse bands, never
    false precision: >=6y -> senior, >=3y -> mid, else junior. No match ->
    None (unknown stays unknown).
    """
    m = _YEARS_RE.search(text or "")
    if not m:
        return None
    lo_year = int(m.group(1))
    hi_raw = m.group(2)
    upper = int(hi_raw) if hi_raw else lo_year
    if upper >= 6:
        return "senior"
    if upper >= 3:
        return "mid"
    return "junior"


def normalize_opportunity(raw) -> Opportunity:
    """Build a canonical Opportunity from raw ingested input.

    Fills only what the raw text supports; every other field stays ``None``/empty.
    """
    from careeros.ingestion import RawOpportunity  # local import to avoid cycle

    assert isinstance(raw, RawOpportunity)
    now = datetime.now()

    title = (raw.role_title or "").strip() or None
    company = (raw.company or "").strip() or None
    body = (raw.description_raw or "").strip()
    # Description corpus = title + body (title often carries mode/seniority cues)
    corpus = " ".join(x for x in [raw.role_title, company, body] if x)

    work_mode = _first_match(_WORK_MODE_PATTERNS, corpus)
    employment_type = _first_match(_EMPLOYMENT_PATTERNS, corpus)
    # Seniority: title wins; fall back to description; then to years-of-experience
    seniority = _first_match(_SENIORITY_PATTERNS, raw.role_title or "")
    if seniority is None:
        seniority = _first_match(_SENIORITY_PATTERNS, body)
    if seniority is None:
        seniority = parse_seniority_from_years(body)

    sal_min, sal_max, sal_cur = parse_salary(corpus)

    # Closing date: structured value wins; else extract from text if stated
    closing_date = _parse_date(raw.closing_date)
    if closing_date is None:
        closing_date = parse_closing_date(corpus)

    return Opportunity(
        opportunity_id=0,  # assigned by the store on insert
        source=raw.source,
        external_job_id=(raw.external_job_id or None),
        source_url=(raw.source_url or None),
        company=company,
        role_title=title,
        location=(raw.location or None),
        work_mode=work_mode,
        employment_type=employment_type,
        salary_min=sal_min,
        salary_max=sal_max,
        currency=sal_cur,
        posted_at=_parse_date(raw.posted_at),
        discovered_at=_parse_date(raw.discovered_at) or now.date(),
        closing_date=closing_date,
        description_raw=(raw.description_raw or None),
        # Normalized description = whitespace-collapsed corpus (lossless, deterministic)
        description_normalized=" ".join(corpus.split()) if corpus else None,
        required_skills=list(raw.required_skills or []),
        preferred_skills=list(raw.preferred_skills or []),
        responsibilities=list(raw.responsibilities or []),
        seniority=seniority,
        status=(raw.status or "new"),
        notes=(raw.notes or None),
        provenance=raw.provenance,
        created_at=now,
        updated_at=now,
    )


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS opportunities (
    opportunity_id INTEGER PRIMARY KEY,
    source VARCHAR NOT NULL,
    external_job_id VARCHAR,
    source_url VARCHAR,
    company VARCHAR,
    role_title VARCHAR,
    location VARCHAR,
    work_mode VARCHAR,
    employment_type VARCHAR,
    salary_min DOUBLE,
    salary_max DOUBLE,
    currency VARCHAR,
    posted_at DATE,
    discovered_at DATE,
    closing_date DATE,
    description_raw VARCHAR,
    description_normalized VARCHAR,
    required_skills VARCHAR,
    preferred_skills VARCHAR,
    responsibilities VARCHAR,
    seniority VARCHAR,
    status VARCHAR,
    notes VARCHAR,
    provenance VARCHAR,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
"""


def _row_to_opportunity(row) -> Opportunity:
    return Opportunity(
        opportunity_id=row[0],
        source=row[1],
        external_job_id=row[2],
        source_url=row[3],
        company=row[4],
        role_title=row[5],
        location=row[6],
        work_mode=row[7],
        employment_type=row[8],
        salary_min=row[9],
        salary_max=row[10],
        currency=row[11],
        posted_at=row[12],
        discovered_at=row[13],
        closing_date=row[14],
        description_raw=row[15],
        description_normalized=row[16],
        required_skills=json.loads(row[17] or "[]"),
        preferred_skills=json.loads(row[18] or "[]"),
        responsibilities=json.loads(row[19] or "[]"),
        seniority=row[20],
        status=row[21],
        notes=row[22],
        provenance=row[23],
        created_at=row[24],
        updated_at=row[25],
    )


class OpportunityStore:
    """DuckDB-backed store for opportunities. Single-user, local-first."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)

    def _connect(self):
        conn = duckdb.connect(self.db_path)
        conn.execute(_SCHEMA)
        return conn

    # -- writes -----------------------------------------------------------
    def add(self, opp: Opportunity) -> Opportunity:
        """Insert a new opportunity (id assigned here). Returns the stored copy."""
        conn = self._connect()
        try:
            next_id = conn.execute(
                "SELECT COALESCE(MAX(opportunity_id), 0) + 1 FROM opportunities"
            ).fetchone()[0]
            cols = [c for c in asdict(opp).keys() if c != "opportunity_id"]
            vals = [asdict(opp)[c] for c in cols]
            json_idx = [
                cols.index(c) for c in ("required_skills", "preferred_skills", "responsibilities")
            ]
            for i in json_idx:
                vals[i] = json.dumps(vals[i])
            date_idx = [cols.index(c) for c in ("posted_at", "discovered_at", "closing_date")]
            for i in date_idx:
                if vals[i] is not None:
                    vals[i] = str(vals[i])
            ts_idx = [cols.index(c) for c in ("created_at", "updated_at")]
            for i in ts_idx:
                if vals[i] is not None:
                    vals[i] = vals[i].isoformat(sep=" ")
            placeholders = ", ".join(["?"] * len(cols))
            conn.execute(
                f"INSERT INTO opportunities (opportunity_id, {', '.join(cols)}) "
                f"VALUES (?, {placeholders})",
                [next_id] + vals,
            )
            return self.get(next_id)  # type: ignore[return-value]
        finally:
            conn.close()

    def update_fields(self, opportunity_id: int, **fields) -> None:
        """Update specific columns (whitelisted) + touch updated_at."""
        allowed = {
            "source_url",
            "company",
            "role_title",
            "location",
            "work_mode",
            "employment_type",
            "salary_min",
            "salary_max",
            "currency",
            "posted_at",
            "closing_date",
            "description_raw",
            "description_normalized",
            "required_skills",
            "preferred_skills",
            "responsibilities",
            "seniority",
            "status",
            "notes",
            "external_job_id",
        }
        bad = set(fields) - allowed
        if bad:
            raise ValueError(f"non-updatable fields: {sorted(bad)}")
        if not fields:
            return
        sets, vals = [], []
        for k, v in fields.items():
            if k in ("required_skills", "preferred_skills", "responsibilities"):
                v = json.dumps(v)
            elif isinstance(v, date):
                v = str(v)
            sets.append(f"{k} = ?")
            vals.append(v)
        conn = self._connect()
        try:
            conn.execute(
                f"UPDATE opportunities SET {', '.join(sets)}, updated_at = CURRENT_TIMESTAMP "
                f"WHERE opportunity_id = ?",
                vals + [opportunity_id],
            )
        finally:
            conn.close()

    def remove(self, opportunity_id: int) -> None:
        conn = self._connect()
        try:
            conn.execute("DELETE FROM opportunities WHERE opportunity_id = ?", [opportunity_id])
        finally:
            conn.close()

    # -- reads ------------------------------------------------------------
    def get(self, opportunity_id: int) -> Optional[Opportunity]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM opportunities WHERE opportunity_id = ?", [opportunity_id]
            ).fetchone()
            return _row_to_opportunity(row) if row else None
        finally:
            conn.close()

    def list_all(self, status: Optional[str] = None) -> list[Opportunity]:
        conn = self._connect()
        try:
            if status:
                rows = conn.execute(
                    "SELECT * FROM opportunities WHERE status = ? ORDER BY opportunity_id", [status]
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM opportunities ORDER BY opportunity_id"
                ).fetchall()
            return [_row_to_opportunity(r) for r in rows]
        finally:
            conn.close()

    def find_by_external_id(self, source: str, external_job_id: str) -> Optional[Opportunity]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM opportunities WHERE source = ? AND external_job_id = ?",
                [source, external_job_id],
            ).fetchone()
            return _row_to_opportunity(row) if row else None
        finally:
            conn.close()
