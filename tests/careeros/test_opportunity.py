"""Tests: opportunity model, normalizer, and store."""

import pytest

from careeros.opportunity import (
    OpportunityStore,
    normalize_opportunity,
    parse_salary,
    parse_closing_date,
    parse_seniority_from_years,
)
from careeros.ingestion import RawOpportunity, ingest, ManualPasteAdapter, StructuredImportAdapter


@pytest.fixture
def store(tmp_path):
    return OpportunityStore(tmp_path / "ops.duckdb")


def _raw(**kw):
    base = dict(
        source="manual",
        role_title="Data Engineer",
        company="Acme",
        description_raw="We need Python and SQL. Remote. Full-time.",
    )
    base.update(kw)
    return RawOpportunity(**base)


# -- creation ---------------------------------------------------------------


def test_add_assigns_id_and_roundtrips(store):
    opp = store.add(normalize_opportunity(_raw()))
    assert opp.opportunity_id == 1
    fetched = store.get(1)
    assert fetched is not None
    assert fetched.role_title == "Data Engineer"
    assert fetched.company == "Acme"
    assert fetched.created_at is not None
    assert fetched.provenance is None  # unknown stays unknown


def test_second_add_gets_next_id(store):
    store.add(normalize_opportunity(_raw()))
    opp2 = store.add(normalize_opportunity(_raw(role_title="Analyst")))
    assert opp2.opportunity_id == 2
    assert len(store.list_all()) == 2


def test_unknown_fields_stay_unknown(store):
    """No text cues at all -> every optional field stays None (never guessed)."""
    opp = store.add(normalize_opportunity(RawOpportunity(source="manual", role_title="Plain Role")))
    assert opp.company is None
    assert opp.work_mode is None
    assert opp.employment_type is None
    assert opp.seniority is None
    assert opp.salary_min is None
    assert opp.salary_max is None
    assert opp.currency is None
    assert opp.location is None
    assert opp.description_raw is None
    assert opp.closing_date is None
    assert opp.required_skills == []
    assert opp.status == "new"


# -- deterministic parsing ---------------------------------------------------


@pytest.mark.parametrize(
    "text,lo,hi,cur",
    [
        ("Salary: CAD 130k - 160k", 130_000.0, 160_000.0, "CAD"),
        ("$90,000 - $110,000 per year", 90_000.0, 110_000.0, None),
        ("$45 - $55 per hour", 45_000.0, 55_000.0, None),  # small numbers -> thousands heuristic
        ("no money mentioned", None, None, None),
    ],
)
def test_parse_salary_variants(text, lo, hi, cur):
    assert parse_salary(text) == (lo, hi, cur)


def test_parse_salary_reversed_range_is_normalized():
    lo, hi, _ = parse_salary("160k - 130k")
    assert (lo, hi) == (130_000.0, 160_000.0)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Apply by 2026-11-15", "2026-11-15"),
        ("Applications due Nov 15, 2026", "2026-11-15"),
        ("closing date: 15 Nov 2026", "2026-11-15"),
        ("no deadline at all", None),
    ],
)
def test_parse_closing_date_variants(text, expected):
    got = parse_closing_date(text)
    assert (got.isoformat() if got else None) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("7+ years experience", "senior"),
        ("5+ years experience", "mid"),  # conservative: 5 is not automatically senior
        ("3-5 years", "mid"),  # upper bound of the range decides
        ("1-2 years", "junior"),
        ("no years mentioned", None),
    ],
)
def test_seniority_from_years(text, expected):
    assert parse_seniority_from_years(text) == expected


def test_normalizer_extracts_modes_and_types():
    opp = normalize_opportunity(_raw(description_raw="Hybrid role, part-time"))
    assert opp.work_mode == "hybrid"
    assert opp.employment_type == "part-time"


def test_normalizer_seniority_title_wins_over_body():
    opp = normalize_opportunity(
        _raw(role_title="Senior Engineer", description_raw="junior mindset welcome")
    )
    assert opp.seniority == "senior"


def test_closing_date_extracted_from_body():
    opp = normalize_opportunity(_raw(description_raw="Apply by 2026-11-15. Python required."))
    assert opp.closing_date is not None
    assert opp.closing_date.isoformat() == "2026-11-15"


def test_description_normalized_collapses_whitespace():
    opp = normalize_opportunity(_raw(description_raw="line one\n\n   line   two"))
    assert opp.description_normalized == "Data Engineer Acme line one line two"


# -- updates / dedupe / provenance -------------------------------------------


def test_update_fields_whitelist_rejects_unknown(store):
    opp = store.add(normalize_opportunity(_raw()))
    with pytest.raises(ValueError):
        store.update_fields(opp.opportunity_id, bogus_column="x")


def test_update_and_remove(store):
    opp = store.add(normalize_opportunity(_raw()))
    store.update_fields(opp.opportunity_id, status="archived", notes="keep")
    assert store.get(opp.opportunity_id).status == "archived"
    store.remove(opp.opportunity_id)
    assert store.get(opp.opportunity_id) is None


def test_ingest_dedupe_on_external_id(store):
    payload = {"source": "import", "role_title": "X", "external_job_id": "J-1"}
    a = ingest(store, StructuredImportAdapter(), payload)
    b = ingest(store, StructuredImportAdapter(), payload)
    assert a.opportunity_id == b.opportunity_id
    assert len(store.list_all()) == 1


def test_ingest_records_provenance(store):
    opp = ingest(
        store,
        StructuredImportAdapter(),
        {"role_title": "Y"},
    )
    assert opp.provenance == "structured import"
    manual = ingest(store, ManualPasteAdapter(), "Role Z at Corp\nbody")
    assert manual.provenance == "manual paste"


def test_find_by_external_id(store):
    ingest(store, StructuredImportAdapter(), {"role_title": "Y", "external_job_id": "EXT-9"})
    assert store.find_by_external_id("import", "EXT-9") is not None
    assert store.find_by_external_id("import", "nope") is None
