"""Pipeline views + role-family taxonomy (deterministic, M2).

- ``PIPELINE_VIEWS`` maps the queue views the user sees onto the explicit
  application states (one state may appear in more than one view; the
  mapping is the single source of truth for the board filters).
- ``role_family()`` groups opportunities into coarse role families by
  deterministic keyword matching on the title - a display/analytics aid,
  never a claim about the job itself.
"""

from __future__ import annotations


from careeros.application import ApplicationState
from careeros.opportunity import Opportunity

#: Queue view -> application states (order = board filter order).
PIPELINE_VIEWS: dict[str, list[ApplicationState]] = {
    "New": [ApplicationState.DISCOVERED],
    "Review": [ApplicationState.REVIEWED],
    "Shortlisted": [ApplicationState.SHORTLISTED],
    "Preparing": [ApplicationState.PREPARING, ApplicationState.READY_TO_APPLY],
    "Applied": [ApplicationState.APPLIED],
    "Interview": [
        ApplicationState.SCREENING,
        ApplicationState.INTERVIEW,
        ApplicationState.ASSESSMENT,
        ApplicationState.OFFER,
    ],
    "Closed": [ApplicationState.REJECTED, ApplicationState.WITHDRAWN, ApplicationState.CLOSED],
}
ALL_VIEWS = ["All"] + list(PIPELINE_VIEWS.keys())


def states_for_view(view: str) -> list[ApplicationState]:
    if view == "All":
        return list(ApplicationState)
    if view not in PIPELINE_VIEWS:
        raise ValueError(f"unknown pipeline view: {view!r}")
    return PIPELINE_VIEWS[view]


# ---------------------------------------------------------------------------
# Role family (deterministic keyword mapping, first match wins)
# ---------------------------------------------------------------------------

# Specific families are listed BEFORE generic ones so e.g. "Financial
# Analyst" hits finance before the generic "analyst" needle in data.
_ROLE_FAMILIES: list[tuple[str, list[str]]] = [
    (
        "ai/ml",
        [
            "machine learning",
            "artificial intelligence",
            " ml ",
            "llm",
            "nlp",
            "deep learning",
            "ai engineer",
            "ai scientist",
        ],
    ),
    (
        "finance",
        ["finance", "financial", "accounting", "controller", "audit", "cpa"],
    ),
    (
        "product",
        ["product manager", "product owner", "product lead", "head of product"],
    ),
    (
        "design",
        ["designer", " ux", "ux designer", " ui", "user experience"],
    ),
    (
        "hr",
        [
            "human resources",
            "recruiter",
            "recruiting",
            "talent acquisition",
            "people ops",
            "people partner",
        ],
    ),
    (
        "healthcare",
        ["nurse", "physician", "medical", "pharmacy", "dental", "health care", "healthcare"],
    ),
    (
        "skilled trades",
        [
            "technician",
            "electrician",
            "plumber",
            "mechanic",
            "welder",
            "carpenter",
            "chef",
            "cook",
        ],
    ),
    (
        "data",
        [
            "data",
            "analytics",
            "analyst",
            "business intelligence",
            "etl",
            "warehouse",
            "bi ",
            "scientist",
        ],
    ),
    (
        "engineering",
        [
            "engineer",
            "developer",
            "software",
            "backend",
            "frontend",
            "full stack",
            "full-stack",
            "devops",
            "sre",
            "architect",
            "programmer",
        ],
    ),
    (
        "marketing",
        ["marketing", "seo", "content strategist", "growth", "brand", "social media"],
    ),
    (
        "sales",
        ["sales", "account executive", "business development", "account manager", "bd "],
    ),
    (
        "consulting",
        ["consultant", "consulting", "advisor", "practice lead"],
    ),
    (
        "operations",
        [
            "operations",
            "ops manager",
            "supply chain",
            "logistics",
            "project manager",
            "program manager",
            "pmo",
            "scrum master",
            "agile coach",
        ],
    ),
]


def role_family(opportunity: Opportunity) -> str:
    """Deterministic role-family bucket from the role title (display aid)."""
    title = (opportunity.role_title or "").lower()
    if not title.strip():
        return "other"
    padded = f" {title} "
    for family, needles in _ROLE_FAMILIES:
        if any(n in padded for n in needles):
            return family
    return "other"


# Sorting keys for the board (deterministic, None-safe).
def sort_key_closing(opp: Opportunity):
    # Opportunities with a closing date sort by date (soonest first), then
    # by closeness-to-today via string; unknown closings sort last.
    return (opp.closing_date is None, opp.closing_date.toordinal() if opp.closing_date else 0)


def sort_key_company(opp: Opportunity):
    return (opp.company or "zzz-unknown").lower()


def sort_key_role_family(opportunity: Opportunity):
    return role_family(opportunity)
