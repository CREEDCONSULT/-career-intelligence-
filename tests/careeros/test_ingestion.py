"""Tests: ingestion boundary (manual paste + structured import, no scraping)."""

import pytest

from careeros.ingestion import (
    IngestionAdapter,
    ManualPasteAdapter,
    StructuredImportAdapter,
    ingest,
)
from careeros.opportunity import OpportunityStore


# -- adapter contract -----------------------------------------------------------


def test_adapters_implement_interface():
    for cls in (ManualPasteAdapter, StructuredImportAdapter):
        assert isinstance(cls(), IngestionAdapter)


# -- manual paste -----------------------------------------------------------------


def test_manual_parses_title_at_company_plus_body():
    a = ManualPasteAdapter()
    raw = a.parse("Senior Data Engineer at Acme Corp\nRemote role.\nPython required.")
    assert raw.role_title == "Senior Data Engineer"
    assert raw.company == "Acme Corp"
    assert raw.source == "manual"
    assert "Remote role." in raw.description_raw
    assert raw.provenance == "manual paste"


@pytest.mark.parametrize("sep", ["at", "@", "-", ":", "–", "—"])
def test_manual_separator_variants(sep):
    raw = ManualPasteAdapter().parse(f"Role {sep} Company\nbody")
    assert raw.role_title == "Role" and raw.company == "Company"


def test_manual_without_separator_keeps_company_unknown():
    raw = ManualPasteAdapter().parse("Just a long descriptive line that is really a sentence body")
    assert raw.company is None  # never invented
    assert raw.role_title is not None


def test_manual_long_first_line_treated_as_body():
    text = "This is an extremely long first line " * 10
    raw = ManualPasteAdapter().parse(text)
    assert raw.role_title is not None
    assert raw.company is None


def test_manual_rejects_empty():
    with pytest.raises(ValueError):
        ManualPasteAdapter().parse("   ")
    assert ManualPasteAdapter().can_parse("") is False


# -- structured import --------------------------------------------------------------


def test_structured_from_dict_and_json_string():
    a = StructuredImportAdapter()
    d = {"role_title": "X", "company": "Y", "required_skills": ["Python"]}
    r1 = a.parse(d)
    r2 = a.parse('{"role_title": "X", "company": "Y", "required_skills": ["Python"]}')
    assert r1.role_title == r2.role_title == "X"
    assert r1.required_skills == ["Python"]


def test_structured_ignores_unknown_keys_and_keeps_missing_unknown():
    r = StructuredImportAdapter().parse(
        {"role_title": "X", "future_field": "whatever", "salary_guess": 5}
    )
    assert r.role_title == "X"
    assert not hasattr(r, "future_field")
    assert r.location is None  # unknown stays unknown


def test_structured_can_parse_shapes():
    a = StructuredImportAdapter()
    assert a.can_parse({"x": 1})
    assert a.can_parse('{"x": 1}')
    assert not a.can_parse("not json {")
    assert not a.can_parse(42)


def test_structured_empty_strings_treated_as_absent():
    r = StructuredImportAdapter().parse({"role_title": "", "company": ""})
    assert r.role_title is None and r.company is None


# -- ingest end-to-end (normalizer in the loop) ----------------------------------------


def test_ingest_manual_full_pipeline(tmp_path):
    store = OpportunityStore(tmp_path / "s.duckdb")
    opp = ingest(
        store,
        ManualPasteAdapter(),
        "Data Scientist at Beta Corp\nHybrid. $110,000 - $130,000. Apply by 2026-12-01.",
    )
    assert opp.company == "Beta Corp"
    assert opp.work_mode == "hybrid"
    assert opp.salary_min == 110_000.0
    assert opp.closing_date is not None
    assert opp.provenance == "manual paste"


def test_ingest_never_fabricates_from_gibberish(tmp_path):
    store = OpportunityStore(tmp_path / "s.duckdb")
    opp = ingest(store, StructuredImportAdapter(), {"role_title": "???"})
    assert opp.company is None
    assert opp.work_mode is None
    assert opp.seniority is None
    assert opp.salary_min is None
    assert opp.status == "new"


def test_ingest_rejects_payload_wrong_for_adapter(tmp_path):
    store = OpportunityStore(tmp_path / "s.duckdb")
    with pytest.raises(ValueError):
        ingest(store, ManualPasteAdapter(), {"not": "text"})
    assert store.list_all() == []
