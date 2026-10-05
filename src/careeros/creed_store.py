"""Future Creed Intelligence /store adapter boundary (M2 §10).

Creed Intelligence owns durable cross-system memory and long-term
founder/career knowledge. Career Intelligence owns career-domain state.
When the Creed Intelligence store contract stabilizes, a real adapter will
implement this protocol; until then ``NullCreedStore`` is the default and
nothing couples to an unstable contract.

The future sync surface (deliberately minimal):
- outbound: opportunity summaries + application outcomes (facts Career
  Intelligence owns and can share as memory)
- inbound: none in M2 (Career Intelligence never takes orders from memory;
  suggestions there are a Creed-side concern)

No tight coupling: importing this module must never require a Creed client.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable

from careeros.opportunity import Opportunity
from careeros.outcomes import ApplicationOutcome


@dataclass
class OpportunitySummary:
    """Compact, shareable summary of an opportunity (no raw job text)."""

    opportunity_id: int
    role_title: Optional[str]
    company: Optional[str]
    status: str
    source: Optional[str]

    @classmethod
    def from_opportunity(cls, opp: Opportunity) -> "OpportunitySummary":
        return cls(
            opportunity_id=opp.opportunity_id,
            role_title=opp.role_title,
            company=opp.company,
            status=opp.status,
            source=opp.source,
        )


@runtime_checkable
class CreedStoreAdapter(Protocol):
    """Durable-memory boundary for career facts (future /store integration)."""

    def publish_opportunity(self, summary: OpportunitySummary) -> bool:
        """Share an opportunity summary with Creed Intelligence memory."""
        ...

    def publish_outcome(self, outcome: ApplicationOutcome) -> bool:
        """Share an application outcome with Creed Intelligence memory."""
        ...


@dataclass
class NullCreedStore:
    """No-op adapter until the Creed Intelligence store contract stabilizes.

    Returns False (not synced) rather than raising, so callers can surface
    'memory sync unavailable' without any conditional logic.
    """

    contract_version: str = "unstable:pending-creed-m1"

    def publish_opportunity(self, summary: OpportunitySummary) -> bool:
        return False

    def publish_outcome(self, outcome: ApplicationOutcome) -> bool:
        return False
