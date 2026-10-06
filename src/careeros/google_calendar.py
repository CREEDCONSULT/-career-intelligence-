"""Google Calendar read-only connector (M2.1) — interview/event context.

Implements the existing ``CalendarAdapter`` protocol with real Google API
calls when authorized. Falls back to the null adapter when not.

Hard constraints:
- READ-ONLY: ``create_event()`` raises ``PermissionError`` — no calendar writes.
- BOUNDED: only lists upcoming events (interviews, assessments, offers);
  never reads historical events beyond the look-forward window.
- PROVENANCE: every discovered event records ``gcal:event/<id>``.
- UNKNOWN STAYS UNKNOWN: events that can't be confidently matched to an
  opportunity are returned as unmatched, never guessed.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from careeros.google_oauth import (
    ConnectorHealth,
    SCOPE_CALENDAR_READONLY,
    load_tokens,
)

# Event keywords that suggest interview/application relevance
_INTERVIEW_KEYWORDS = [
    "interview",
    "screening",
    "phone call",
    "video call",
    "zoom",
    "google meet",
    "teams meeting",
    "assessment",
    "case study",
    "panel",
    "final round",
    "offer discussion",
    "hiring",
]
_RECRUITER_KEYWORDS = ["recruiter", "talent", "hr"]


class DiscoveredEvent:
    """A calendar event discovered by the connector (metadata only)."""

    def __init__(
        self,
        event_id: str,
        summary: str,
        start: Optional[datetime],
        end: Optional[datetime] = None,
        location: Optional[str] = None,
        description_hint: Optional[str] = None,
    ):
        self.event_id = event_id
        self.summary = summary
        self.start = start
        self.end = end
        self.location = location
        self.description_hint = description_hint  # first 200 chars, metadata only
        self.source_ref = f"gcal:event/{event_id}"
        self.provenance = "google-calendar:readonly"
        self.matched_opportunity_id: Optional[int] = None
        self.match_confidence: str = "unmatched"

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "summary": self.summary,
            "start": self.start.isoformat() if self.start else None,
            "end": self.end.isoformat() if self.end else None,
            "location": self.location,
            "source_ref": self.source_ref,
            "provenance": self.provenance,
            "matched_opportunity_id": self.matched_opportunity_id,
            "match_confidence": self.match_confidence,
        }


class CalendarConnector:
    """Real Calendar read-only adapter (implements CalendarAdapter protocol)."""

    def __init__(self):
        self._last_error: Optional[str] = None

    # -- health ------------------------------------------------------------------
    def health(self) -> ConnectorHealth:
        tokens = load_tokens()
        return ConnectorHealth(
            connector="calendar",
            configured=tokens is not None,
            authorized=tokens is not None
            and tokens.valid
            and SCOPE_CALENDAR_READONLY in (tokens.scopes or []),
            last_error=self._last_error,
            scopes=[SCOPE_CALENDAR_READONLY],
        )

    # -- protocol: CalendarAdapter (read-only enforcement) --------------------------
    def create_event(self, event) -> None:
        """HARD BLOCK: this connector is read-only. No calendar writes."""
        raise PermissionError(
            "CalendarConnector is READ-ONLY. Creating events is explicitly "
            "prohibited by the M2.1 design. Use your calendar client directly."
        )

    def list_upcoming(self, within_days: int = 14) -> list:
        """List upcoming events within the look-forward window. Read-only."""
        service = self._service()
        if service is None:
            return []
        try:
            now = datetime.utcnow()
            time_min = now.isoformat() + "Z"
            time_max = (now + timedelta(days=within_days)).isoformat() + "Z"
            result = (
                service.events()
                .list(
                    calendarId="primary",
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=50,
                )
                .execute()
            )
            out = []
            for item in result.get("items", []):
                start_str = item.get("start", {}).get("dateTime") or item.get("start", {}).get(
                    "date"
                )
                end_str = item.get("end", {}).get("dateTime") or item.get("end", {}).get("date")
                event = DiscoveredEvent(
                    event_id=item["id"],
                    summary=item.get("summary", ""),
                    start=_parse_google_datetime(start_str),
                    end=_parse_google_datetime(end_str),
                    location=item.get("location"),
                    description_hint=(item.get("description") or "")[:200] or None,
                )
                out.append(event)
            return out
        except Exception as e:  # noqa: BLE001
            self._last_error = f"{type(e).__name__}: {e}"
            return []

    # -- career-context discovery ------------------------------------------------
    def discover_interview_context(self, within_days: int = 14) -> list[DiscoveredEvent]:
        """Find upcoming events that look interview/application-relevant.

        Returns only events whose summary or description contains known
        interview keywords. Unknown events are excluded (not guessed at).
        """
        all_events = self.list_upcoming(within_days)
        relevant = []
        for event in all_events:
            text = f"{event.summary} {event.description_hint or ''}".lower()
            if any(kw in text for kw in _INTERVIEW_KEYWORDS):
                event.match_confidence = "keyword-matched"
                relevant.append(event)
        return relevant

    def associate_with_opportunities(
        self,
        events: list[DiscoveredEvent],
        opp_store,
    ) -> list[DiscoveredEvent]:
        """Attempt to match discovered events to tracked opportunities.

        Deterministic matching: company name or role title in the event
        text. Unmatched events stay unmatched (unknown remains unknown).
        """
        opps = opp_store.list_all()
        for event in events:
            text = f"{event.summary} {event.description_hint or ''}".lower()
            for opp in opps:
                company = (opp.company or "").lower()
                role = (opp.role_title or "").lower()
                if company and company in text:
                    event.matched_opportunity_id = opp.opportunity_id
                    event.match_confidence = "company-matched"
                    break
                if role and role in text:
                    event.matched_opportunity_id = opp.opportunity_id
                    event.match_confidence = "role-matched"
                    break
        return events

    # -- internal ------------------------------------------------------------------
    def _service(self):
        """Return an authorized Calendar API service, or None if offline."""
        creds = load_tokens()
        if creds is None or not creds.valid:
            return None
        if SCOPE_CALENDAR_READONLY not in (creds.scopes or []):
            self._last_error = "Calendar scope not granted"
            return None
        try:
            from googleapiclient.discovery import build

            return build("calendar", "v3", credentials=creds)
        except Exception as e:  # noqa: BLE001
            self._last_error = f"{type(e).__name__}"
            return None


def _parse_google_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    """Parse a Google API ISO datetime. Returns None on failure."""
    if not dt_str:
        return None
    try:
        # Google returns "2026-10-10T14:00:00-04:00" or "2026-10-10"
        if "T" in dt_str:
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00")).replace(tzinfo=None)
        return datetime.fromisoformat(dt_str)
    except (ValueError, TypeError):
        return None
