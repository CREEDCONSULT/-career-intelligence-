"""Opportunity ingestion boundary (M1).

Defines the adapter interface every future source must implement, plus the
two M1-supported adapters:

- ``ManualPasteAdapter``     - a human pastes a job ad (title/company + body text)
- ``StructuredImportAdapter``- a JSON dict/fixture (tests, CSV exports, future bots)

M1 explicitly does NOT scrape or automate LinkedIn/Indeed/Upwork/career pages.
Those arrive later as additional adapters behind this same interface, feeding
``RawOpportunity`` objects - never touching the store directly.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

from careeros.opportunity import Opportunity, OpportunityStore, normalize_opportunity


@dataclass
class RawOpportunity:
    """Unvalidated opportunity data as received from a source.

    ``None``/empty means "not provided by the source" - the normalizer will
    keep it unknown rather than guess.
    """

    source: str
    role_title: Optional[str] = None
    company: Optional[str] = None
    description_raw: Optional[str] = None
    external_job_id: Optional[str] = None
    source_url: Optional[str] = None
    location: Optional[str] = None
    posted_at: Optional[str] = None
    discovered_at: Optional[str] = None
    closing_date: Optional[str] = None
    required_skills: Optional[list[str]] = None
    preferred_skills: Optional[list[str]] = None
    responsibilities: Optional[list[str]] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    provenance: Optional[str] = None


class IngestionAdapter(ABC):
    """Interface for opportunity sources."""

    source: str = "abstract"

    @abstractmethod
    def can_parse(self, payload: Any) -> bool:
        """True if this adapter understands the payload shape."""

    @abstractmethod
    def parse(self, payload: Any) -> RawOpportunity:
        """Convert a source payload into a RawOpportunity (no fabrication)."""


class ManualPasteAdapter(IngestionAdapter):
    """Human pastes a job posting.

    Expected payload (str):
        Line 1 (optional but recommended): "<Role Title> at <Company>" or "<Role Title> - <Company>"
        Everything after: the job-ad text.

    Only the first line is structurally parsed; the rest is kept raw. The
    adapter never invents a company if the "at/-" separator is absent.
    """

    source = "manual"

    _SEP = __import__("re").compile(r"^\s*(.+?)\s+(?:at|@|-|–|—|:)\s+(.+?)\s*$")

    def can_parse(self, payload: Any) -> bool:
        return isinstance(payload, str) and bool(payload.strip())

    def parse(self, payload: str) -> RawOpportunity:
        if not self.can_parse(payload):
            raise ValueError("ManualPasteAdapter expects non-empty text")
        lines = payload.strip().splitlines()
        first = lines[0].strip()
        body = "\n".join(lines[1:]).strip() or None
        m = self._SEP.match(first)
        if m and len(first) < 120:  # only treat line 1 as a header if it's short
            title, company = m.group(1).strip(), m.group(2).strip()
        else:
            title, company = first, None
        return RawOpportunity(
            source=self.source,
            role_title=title or None,
            company=company,
            description_raw=body or (first if not m else None),
            provenance="manual paste",
        )


class StructuredImportAdapter(IngestionAdapter):
    """JSON payload -> RawOpportunity. Keys mirror RawOpportunity fields.

    Used by the test fixtures and the "Import JSON" UI affordance. Unknown
    keys are ignored (forward-compatible), missing keys stay unknown.
    """

    source = "import"

    _ALLOWED = set(RawOpportunity.__dataclass_fields__.keys()) - {"source", "provenance"}

    def can_parse(self, payload: Any) -> bool:
        if isinstance(payload, (dict,)):
            return True
        if isinstance(payload, str):
            try:
                json.loads(payload)
                return True
            except (json.JSONDecodeError, TypeError):
                return False
        return False

    def parse(self, payload: Any) -> RawOpportunity:
        data = payload
        if isinstance(data, str):
            data = json.loads(data)
        if not isinstance(data, dict):
            raise ValueError("StructuredImportAdapter expects a JSON object")
        fields = {k: v for k, v in data.items() if k in self._ALLOWED and v not in (None, "", [])}
        return RawOpportunity(
            source=self.source,
            provenance=str(data.get("provenance") or "structured import"),
            **fields,
        )


class JobBankImportAdapter(IngestionAdapter):
    """Import a posting from the Job Bank open-data pipeline (M2 real source).

    This is the one policy-compliant real source already accessible without
    new credentials: the government open-data postings ingested by the
    market pipeline (``job_postings`` table). The caller reads the row and
    passes it here; the adapter converts it to a RawOpportunity with a
    stable external id (``jobbank:<posting_id>``) so duplicate detection
    works across imports. No scraping, no external network.
    """

    source = "jobbank"

    _ROW_FIELDS = (
        "id",
        "title",
        "location",
        "salary_min",
        "salary_max",
        "posted_date",
        "requirements_text",
        "noc_code",
    )

    def can_parse(self, payload: Any) -> bool:
        return isinstance(payload, dict) and "id" in payload and "title" in payload

    def parse(self, payload: Any) -> RawOpportunity:
        if not self.can_parse(payload):
            raise ValueError(
                "JobBankImportAdapter expects a job_postings row dict "
                "with at least 'id' and 'title'"
            )
        title = (payload.get("title") or "").strip() or None
        loc = (payload.get("location") or "").strip() or None
        posted = payload.get("posted_date")
        posted_s = str(posted)[:10] if posted is not None else None
        desc = (payload.get("requirements_text") or "").strip() or None
        return RawOpportunity(
            source=self.source,
            external_job_id=f"jobbank:{payload['id']}",
            role_title=title,
            location=loc,
            posted_at=posted_s,
            description_raw=desc,
            notes=(f"NOC {payload['noc_code']}" if payload.get("noc_code") else None),
            provenance=f"Job Bank open data posting {payload['id']}",
        )


# ---------------------------------------------------------------------------
# Ingestion entry point
# ---------------------------------------------------------------------------


def ingest(
    store: OpportunityStore,
    adapter: IngestionAdapter,
    payload: Any,
    *,
    dedupe: bool = True,
) -> Opportunity:
    """Parse a payload with an adapter and store the normalized opportunity.

    Dedupe: if the adapter produced an external_job_id that already exists
    for that source, return the existing opportunity instead of duplicating.
    """
    if not adapter.can_parse(payload):
        raise ValueError(f"adapter {type(adapter).__name__} cannot parse this payload")
    raw = adapter.parse(payload)
    if dedupe and raw.external_job_id:
        existing = store.find_by_external_id(raw.source, raw.external_job_id)
        if existing is not None:
            return existing
    raw.source = raw.source or adapter.source
    return store.add(normalize_opportunity(raw))
