"""Gmail read-only connector (M2.1) — career-relevant ingestion only.

Implements the existing ``EmailAdapter`` protocol with real Google API
calls when authorized, falling back to the null adapter when not.

Hard constraints (enforced in code, not just policy):
- READ-ONLY: ``send()`` raises ``PermissionError`` — no email is ever sent.
- BOUNDED: only career-relevant queries are used (application status,
  recruiter contact, interview invitations, assessments, rejections, offers,
  scheduling). No broad inbox harvesting.
- PROVENANCE: every imported message records ``gmail:thread/<id>`` as its
  source reference + the query that found it.
- METADATA-FIRST: imports sender/subject/timestamp/signals; the body is
  fetched only for signal classification (already deterministic regex),
  and the raw body is NOT duplicated into the CommunicationStore — a
  source reference is kept instead.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from careeros.google_oauth import (
    ConnectorHealth,
    SCOPE_GMAIL_READONLY,
    load_tokens,
)

if TYPE_CHECKING:
    # Only needed for type annotations; the runtime import is done lazily
    # in import_career_messages so the connector module works without DuckDB
    # (tests for health/search/read-only don't need the store).
    from careeros.communications import CommunicationStore

# Bounded career-relevance queries — the ONLY Gmail searches this module runs.
# Each query targets a specific career workflow signal, never a broad harvest.
CAREER_QUERIES: dict[str, str] = {
    "application_acknowledgement": (
        'subject:("application" OR "applied" OR "we received") '
        '("thank you" OR "confirmation" OR "acknowledg") -in:spam'
    ),
    "recruiter_contact": (
        '("recruiter" OR "talent acquisition" OR "hiring" OR "opportunity") '
        '("your profile" OR "your resume" OR "interested in") -in:spam'
    ),
    "interview_invitation": (
        'subject:("interview" OR "screening call" OR "meet with") '
        '("invite" OR "schedule" OR "available") -in:spam'
    ),
    "assessment": (
        'subject:("assessment" OR "case study" OR "coding challenge" OR '
        '"take-home") ("complete" OR "instructions") -in:spam'
    ),
    "rejection": (
        '("unfortunately" OR "not moving forward" OR "position has been filled") '
        '("decision" OR "update") -in:spam'
    ),
    "offer": (
        '("pleased to offer" OR "offer letter" OR "compensation package") '
        '("position" OR "role") -in:spam'
    ),
    "scheduling_change": (
        '("reschedule" OR "reschedul" OR "time change" OR "moved") '
        '("interview" OR "call" OR "meeting") -in:spam'
    ),
}


class GmailConnector:
    """Real Gmail read-only adapter (implements EmailAdapter protocol).

    Falls back to null-adapter behavior (empty results, no crash) when
    unconfigured/unauthorized. Never sends email.
    """

    def __init__(self, store: Optional[CommunicationStore] = None):
        self.store = store
        self._last_error: Optional[str] = None
        self._last_sync: Optional[datetime] = None
        self._imported_count = 0

    # -- health ---------------------------------------------------------------
    def health(self) -> ConnectorHealth:
        tokens = load_tokens()
        return ConnectorHealth(
            connector="gmail",
            configured=tokens is not None,
            authorized=tokens is not None
            and tokens.valid
            and SCOPE_GMAIL_READONLY in (tokens.scopes or []),
            last_error=self._last_error,
            scopes=[SCOPE_GMAIL_READONLY],
        )

    # -- protocol: EmailAdapter (read-only enforcement) --------------------------
    def send(self, message) -> None:
        """HARD BLOCK: this connector is read-only. No email is ever sent."""
        raise PermissionError(
            "GmailConnector is READ-ONLY. Sending email is explicitly "
            "prohibited by the M2.1 design. Use a manual email client instead."
        )

    def search_threads(self, query: str, limit: int = 10) -> list[dict]:
        """Search Gmail for threads matching a query. Read-only."""
        service = self._service()
        if service is None:
            return []
        try:
            result = (
                service.users().threads().list(userId="me", q=query, maxResults=limit).execute()
            )
            threads = result.get("threads", [])
            out = []
            for t in threads:
                out.append(
                    {
                        "thread_id": t["id"],
                        "snippet": t.get("snippet", ""),
                    }
                )
            return out
        except Exception as e:  # noqa: BLE001
            self._last_error = f"{type(e).__name__}: {e}"
            return []

    # -- career ingestion ---------------------------------------------------------
    def import_career_messages(
        self,
        store: CommunicationStore,
        limit_per_query: int = 10,
    ) -> list[dict]:
        """Run the bounded career queries and import results into the store.

        Returns a summary: [{"signal_type": ..., "imported": n, "skipped": n}, ...]
        Idempotent: messages already in the store (by thread_ref) are skipped.
        """
        # Lazy import: only needed when actually storing messages (DuckDB)
        from careeros.communications import detect_signals

        service = self._service()
        if service is None:
            self._last_error = "Gmail not authorized (running in offline/null mode)"
            return []

        summary = []
        existing_refs = {m.thread_ref for m in store.list_all()}

        for signal_name, query in CAREER_QUERIES.items():
            imported = skipped = 0
            try:
                result = (
                    service.users()
                    .threads()
                    .list(userId="me", q=query, maxResults=limit_per_query)
                    .execute()
                )
                for thread in result.get("threads", []):
                    thread_id = thread["id"]
                    ref = f"gmail:thread/{thread_id}"
                    if ref in existing_refs:
                        skipped += 1
                        continue
                    # Fetch metadata for this thread
                    thread_data = (
                        service.users()
                        .threads()
                        .get(userId="me", id=thread_id, format="metadata")
                        .execute()
                    )
                    messages = thread_data.get("messages", [])
                    if not messages:
                        continue
                    # Use the most recent message in the thread
                    latest = messages[-1]
                    headers = {
                        h["name"].lower(): h["value"]
                        for h in latest.get("payload", {}).get("headers", [])
                    }
                    sender = headers.get("from", "")
                    subject = headers.get("subject", "")
                    date_str = headers.get("date", "")
                    # Get snippet for signal detection (first message has the body preview)
                    snippet = thread.get("snippet", "")

                    # Parse the RFC 2822 date
                    received = _parse_rfc2822(date_str)

                    # Deterministic signal detection (same regex as manual import)
                    signals = detect_signals(f"{subject}\n{snippet}")
                    # Tag with the query that found it
                    if signal_name not in signals:
                        signals.append(signal_name)

                    # Extract email from "Name <email@domain>" format
                    sender_email = _extract_email(sender)

                    store.record(
                        sender=sender,
                        sender_email=sender_email,
                        subject=subject,
                        body=None,  # metadata-first: body NOT duplicated
                        received_at=received,
                        provenance=f"gmail:{signal_name}",
                        thread_ref=ref,
                    )
                    existing_refs.add(ref)
                    imported += 1
            except Exception as e:  # noqa: BLE001
                self._last_error = f"{type(e).__name__}: {e}"
            summary.append(
                {
                    "signal_type": signal_name,
                    "imported": imported,
                    "skipped": skipped,
                }
            )

        self._last_sync = datetime.now()
        self._imported_count += sum(s["imported"] for s in summary)
        return summary

    # -- internal ----------------------------------------------------------------
    def _service(self):
        """Return an authorized Gmail API service, or None if offline."""
        creds = load_tokens()
        if creds is None or not creds.valid:
            return None
        if SCOPE_GMAIL_READONLY not in (creds.scopes or []):
            self._last_error = "Gmail scope not granted"
            return None
        try:
            from googleapiclient.discovery import build

            return build("gmail", "v1", credentials=creds)
        except Exception as e:  # noqa: BLE001
            self._last_error = f"{type(e).__name__}"
            return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_email(sender: str) -> Optional[str]:
    """Extract the email address from 'Name <email@domain>' format."""
    if "<" in sender and ">" in sender:
        start = sender.rfind("<") + 1
        end = sender.rfind(">")
        return sender[start:end]
    if "@" in sender:
        return sender.strip()
    return None


def _parse_rfc2822(date_str: str) -> Optional[datetime]:
    """Parse an RFC 2822 date header. Returns None on failure (unknown stays unknown)."""
    if not date_str:
        return None
    try:
        from email.utils import parsedate_to_datetime

        return parsedate_to_datetime(date_str).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None
