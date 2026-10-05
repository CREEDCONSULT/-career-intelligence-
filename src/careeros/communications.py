"""Communication records tied to opportunities (M2 §4).

Inbound application/recruiter correspondence is modeled, classified, and
associated with opportunities. Everything is deterministic here: signal
detection (interview / assessment / rejection / offer / recruiter) is
regex-based, never an LLM guess, and every message records provenance
(e.g. ``fixture:gmail-export``, ``manual entry``).

Boundary rules honored:
- No email is ever SENT by this module (sending lives behind the explicit
  EmailAdapter protocol and requires future user authorization).
- Gmail access is not required in M2: threads arrive via fixtures or manual
  entry; a real Gmail adapter implements the same interface later.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import duckdb

# ---------------------------------------------------------------------------
# Signal detection (deterministic)
# ---------------------------------------------------------------------------

SIGNALS = ("interview", "assessment", "rejection", "offer", "recruiter")

_SIGNAL_PATTERNS: dict[str, list[re.Pattern]] = {
    "interview": [
        re.compile(r"\binterview\b", re.I),
        re.compile(r"\bscreen(ing)? call\b", re.I),
        re.compile(r"\b(Zoom|Teams|Google Meet)\s+(link|call|meeting)\b", re.I),
        re.compile(r"\bwe (?:would|'d) like to (?:chat|speak|talk)\b", re.I),
        re.compile(r"\bmeet with\b.{0,40}\bteam\b", re.I),
    ],
    "assessment": [
        re.compile(r"\bassessment\b", re.I),
        re.compile(
            r"\b(take[- ]home|case study|coding challenge|technical (?:test|exercise))\b", re.I
        ),
        re.compile(r"\b(online )?test\b.{0,30}\b(invitation|link)\b", re.I),
    ],
    "rejection": [
        re.compile(r"\bunfortunately\b", re.I),
        re.compile(r"\bnot (?:moving forward|able to (?:offer|proceed)|selected)\b", re.I),
        re.compile(r"\bposition has been filled\b", re.I),
        re.compile(r"\bdecided to (?:move forward with (?:another|other)|pursue other)\b", re.I),
        re.compile(r"\bregret(ting)?\b", re.I),
    ],
    "offer": [
        re.compile(r"\bpleased to (?:offer|extend)\b", re.I),
        re.compile(r"\bwe('re| are)? (?:delighted|excited) to (?:offer|present)\b", re.I),
        re.compile(r"\boffer (?:of employment|letter|for the position)\b", re.I),
        re.compile(r"\bcompensation (?:package|details)\b", re.I),
        re.compile(r"\bstart date\b.{0,40}\b(confirm|discuss)\b", re.I),
    ],
    "recruiter": [
        re.compile(r"\brecruiter\b", re.I),
        re.compile(r"\btalent acquisition\b", re.I),
        re.compile(r"@(?:talent|recruiting|people|hiring)\.", re.I),
        re.compile(r"\bi (?:came across|found) your (?:profile|resume)\b", re.I),
        re.compile(r"\bopportunity (?:that )?(?:might|may) (?:interest|be of interest)\b", re.I),
    ],
}


def detect_signals(text: str) -> list[str]:
    """Deterministic signal list for a message body/subject (ordered, unique)."""
    found: list[str] = []
    for signal, patterns in _SIGNAL_PATTERNS.items():
        if any(p.search(text or "") for p in patterns):
            found.append(signal)
    return found


@dataclass
class CommunicationMessage:
    message_id: int
    sender: Optional[str] = None
    sender_email: Optional[str] = None
    company_guess: Optional[str] = None  # deterministic domain/name guess
    subject: Optional[str] = None
    body: Optional[str] = None
    received_at: Optional[datetime] = None
    signals: list[str] = field(default_factory=list)
    opportunity_id: Optional[int] = None  # association (None = unassociated)
    thread_ref: Optional[str] = None
    provenance: Optional[str] = None
    created_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return asdict(self)


def _company_from_email(email: Optional[str]) -> Optional[str]:
    """envelope: Deterministic company hint from a corporate-looking domain.

    Free-mail domains (gmail/outlook/etc.) carry no company signal -> None.
    """
    if not email or "@" not in email:
        return None
    domain = email.rsplit("@", 1)[1].lower()
    free = {
        "gmail.com",
        "outlook.com",
        "hotmail.com",
        "yahoo.com",
        "icloud.com",
        "aol.com",
        "protonmail.com",
        "proton.me",
        "live.com",
    }
    if domain in free:
        return None
    base = domain.split(".")[0]
    return base if base else None


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS communications (
    message_id INTEGER PRIMARY KEY,
    sender VARCHAR,
    sender_email VARCHAR,
    company_guess VARCHAR,
    subject VARCHAR,
    body VARCHAR,
    received_at TIMESTAMP,
    signals VARCHAR,
    opportunity_id INTEGER,
    thread_ref VARCHAR,
    provenance VARCHAR,
    created_at TIMESTAMP
)
"""


def _row_to_message(row) -> CommunicationMessage:
    return CommunicationMessage(
        message_id=row[0],
        sender=row[1],
        sender_email=row[2],
        company_guess=row[3],
        subject=row[4],
        body=row[5],
        received_at=row[6],
        signals=json.loads(row[7] or "[]"),
        opportunity_id=row[8],
        thread_ref=row[9],
        provenance=row[10],
        created_at=row[11],
    )


class CommunicationStore:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)

    def _connect(self):
        conn = duckdb.connect(self.db_path)
        conn.execute(_SCHEMA)
        return conn

    # -- writes -----------------------------------------------------------
    def record(
        self,
        sender: Optional[str],
        sender_email: Optional[str],
        subject: Optional[str],
        body: Optional[str],
        received_at: Optional[datetime],
        provenance: str,
        thread_ref: Optional[str] = None,
        opportunity_id: Optional[int] = None,
    ) -> CommunicationMessage:
        """Persist one inbound message with deterministic signal detection."""
        signals = detect_signals(f"{subject or ''}\n{body or ''}")
        company = _company_from_email(sender_email)
        conn = self._connect()
        try:
            mid = conn.execute(
                "SELECT COALESCE(MAX(message_id), 0) + 1 FROM communications"
            ).fetchone()[0]
            now = datetime.now().isoformat(sep=" ")
            recv = received_at.isoformat(sep=" ") if received_at else None
            conn.execute(
                "INSERT INTO communications VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    mid,
                    sender,
                    sender_email,
                    company,
                    subject,
                    body,
                    recv,
                    json.dumps(signals),
                    opportunity_id,
                    thread_ref,
                    provenance,
                    now,
                ],
            )
        finally:
            conn.close()
        return self.get(mid)  # type: ignore[return-value]

    def associate(
        self, message_id: int, opportunity_id: int, provenance: str = "user:association"
    ) -> None:
        """Link a message to an opportunity (user-confirmed action)."""
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE communications SET opportunity_id = ? WHERE message_id = ?",
                [opportunity_id, message_id],
            )
            row = conn.execute(
                "SELECT provenance FROM communications WHERE message_id = ?", [message_id]
            ).fetchone()
            if row and row[0]:
                conn.execute(
                    "UPDATE communications SET provenance = ? WHERE message_id = ?",
                    [f"{row[0]} | {provenance}", message_id],
                )
        finally:
            conn.close()

    # -- reads ------------------------------------------------------------
    def get(self, message_id: int) -> Optional[CommunicationMessage]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM communications WHERE message_id = ?", [message_id]
            ).fetchone()
            return _row_to_message(row) if row else None
        finally:
            conn.close()

    def list_all(
        self, opportunity_id: Optional[int] = None, signal: Optional[str] = None
    ) -> list[CommunicationMessage]:
        conn = self._connect()
        try:
            if opportunity_id is not None:
                rows = conn.execute(
                    "SELECT * FROM communications WHERE opportunity_id = ? ORDER BY message_id",
                    [opportunity_id],
                ).fetchall()
            elif signal:
                rows = conn.execute("SELECT * FROM communications ORDER BY message_id").fetchall()
                rows = [r for r in rows if signal in json.loads(r[7] or "[]")]
            else:
                rows = conn.execute("SELECT * FROM communications ORDER BY message_id").fetchall()
            return [_row_to_message(r) for r in rows]
        finally:
            conn.close()

    def suggest_associations(self, opp_store) -> dict[int, list[int]]:
        """message_id -> candidate opportunity_ids by deterministic matching.

        Matches company name (email domain hint or sender name) against
        opportunity.company, case-insensitively. Suggestions only - the
        user confirms via ``associate``.
        """
        suggestions: dict[int, list[int]] = {}
        opps = opp_store.list_all()
        for msg in self.list_all():
            if msg.opportunity_id is not None:
                continue
            candidates = []
            for o in opps:
                hay = " ".join(x for x in (o.company, o.role_title) if x).lower()
                if not hay:
                    continue
                needles = [n for n in (msg.company_guess, msg.sender) if n]
                if any(n and n.lower() in hay for n in needles):
                    candidates.append(o.opportunity_id)
            if candidates:
                suggestions[msg.message_id] = candidates
        return suggestions

    def import_fixture(
        self, items: list[dict], provenance: str = "fixture:gmail-export"
    ) -> list[CommunicationMessage]:
        """Bulk-load exported thread dicts (tests / a future Gmail export)."""
        out = []
        for item in items:
            recv = item.get("received_at")
            if isinstance(recv, str):
                try:
                    recv = datetime.fromisoformat(recv)
                except ValueError:
                    recv = None
            out.append(
                self.record(
                    sender=item.get("sender"),
                    sender_email=item.get("sender_email"),
                    subject=item.get("subject"),
                    body=item.get("body"),
                    received_at=recv,
                    provenance=str(item.get("provenance") or provenance),
                    thread_ref=item.get("thread_ref"),
                    opportunity_id=item.get("opportunity_id"),
                )
            )
        return out
