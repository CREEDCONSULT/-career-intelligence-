"""Tests: M2 real-source ingestion + duplicate detection."""

import pytest

from careeros.ingestion import (
    JobBankImportAdapter,
    ManualPasteAdapter,
    StructuredImportAdapter,
    ingest,
)
from careeros.opportunity import OpportunityStore, normalize_opportunity
from careeros.pipeline import role_family, states_for_view, PIPELINE_VIEWS, ALL_VIEWS


@pytest.fixture
def store(tmp_path):
    return OpportunityStore(tmp_path / "ops.duckdb")


def _jobbank_row(**kw):
    base = dict(
        id=42,
        title="Data Engineer",
        location="Toronto, ON",
        salary_min=45.0,
        salary_max=60.0,
        posted_date="2026-09-01",
        requirements_text="Python SQL pipelines for government data.",
        noc_code="21231",
    )
    base.update(kw)
    return base


# -- JobBankImportAdapter ---------------------------------------------------


def test_jobbank_adapter_parses_posting_row(store):
    opp = ingest(store, JobBankImportAdapter(), _jobbank_row())
    assert opp.source == "jobbank"
    assert opp.external_job_id == "jobbank:42"
    assert opp.role_title == "Data Engineer"
    assert opp.location == "Toronto, ON"
    assert opp.posted_at is not None
    assert opp.provenance == "Job Bank open data posting 42"
    assert opp.notes == "NOC 21231"


def test_jobbank_adapter_never_fabricates(store):
    """Missing row fields stay unknown - no invented salary/company/seniority."""
    opp = ingest(store, JobBankImportAdapter(), dict(id=7, title="Cook", requirements_text=None))
    assert opp.salary_min is None
    assert opp.company is None  # Job Bank rows carry no company name
    assert opp.seniority is None
    assert opp.location is None
    assert opp.description_raw is None


def test_jobbank_rejects_bad_payload():
    a = JobBankImportAdapter()
    assert a.can_parse({"id": 1}) is False
    assert a.can_parse("text") is False
    with pytest.raises(ValueError):
        a.parse({"id": 1})


def test_jobbank_duplicate_ingestion_returns_same_opportunity(store):
    a = ingest(store, JobBankImportAdapter(), _jobbank_row())
    b = ingest(store, JobBankImportAdapter(), _jobbank_row(id=42))
    assert a.opportunity_id == b.opportunity_id
    assert len(store.list_all()) == 1


def test_jobbank_different_postings_are_distinct(store):
    a = ingest(store, JobBankImportAdapter(), _jobbank_row(id=42))
    b = ingest(store, JobBankImportAdapter(), _jobbank_row(id=43))
    assert a.opportunity_id != b.opportunity_id
    assert len(store.list_all()) == 2


def test_jobbank_salary_from_requirements_uses_thousands_heuristic(store):
    """DOCUMENTED DEBT: 'Wage $45 - $60 per hour' in requirements_text is parsed
    by the shared normalizer, which applies the small-number thousands heuristic
    (45 -> 45000). The JobBank adapter does not carry the row's salary columns
    into the Opportunity (government rows mix hourly/annual figures), so all
    salary parsing goes through requirements_text + the documented heuristic.
    This test pins the current honest behavior, not the ideal."""
    opp = ingest(
        store, JobBankImportAdapter(), _jobbank_row(requirements_text="Wage $45 - $60 per hour.")
    )
    # current documented behavior: the shared normalizer applies the heuristic
    assert opp.salary_min == 45_000.0
    assert opp.salary_max == 60_000.0


# -- pipeline views ------------------------------------------------------------


def test_all_views_cover_every_state():
    from careeros.application import ApplicationState

    covered = set()
    for states in PIPELINE_VIEWS.values():
        covered |= set(states)
    assert covered == set(ApplicationState)


def test_states_for_view_mapping():
    assert states_for_view("All") == list(states_for_view.__globals__["ApplicationState"])
    assert [s.value for s in states_for_view("Preparing")] == ["PREPARING", "READY_TO_APPLY"]
    assert [s.value for s in states_for_view("Interview")] == [
        "SCREENING",
        "RECRUITER_CONTACT",
        "INTERVIEW",
        "ASSESSMENT",
        "OFFER",
    ]


def test_unknown_view_rejected():
    with pytest.raises(ValueError):
        states_for_view("Bogus")


# -- role family -----------------------------------------------------------------


def test_role_family_buckets():
    from careeros.opportunity import Opportunity

    cases = [
        ("Senior Data Engineer", "data"),
        ("Machine Learning Engineer", "ai/ml"),
        ("Full Stack Developer", "engineering"),
        ("Product Manager", "product"),
        ("UX Designer", "design"),
        ("Marketing Coordinator", "marketing"),
        ("Account Executive - Sales", "sales"),
        ("Technical Consultant", "consulting"),
        ("Operations Manager", "operations"),
        ("Financial Analyst", "finance"),
        ("Recruiter", "hr"),
        ("Electrician", "skilled trades"),
        ("Registered Nurse", "healthcare"),
        ("Line Cook", "skilled trades"),
        ("Mystery Role", "other"),
        (None, "other"),
    ]
    for title, expected in cases:
        opp = Opportunity(opportunity_id=1, source="t", role_title=title)
        assert role_family(opp) == expected, f"{title} -> {role_family(opp)} != {expected}"
