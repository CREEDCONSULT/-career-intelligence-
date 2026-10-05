"""Tests: evidence model, store, and derived skill support."""

import pytest

from careeros.evidence import Evidence, EvidenceStore, EVIDENCE_TYPES, VERIFICATION_STATUSES


@pytest.fixture
def store(tmp_path):
    return EvidenceStore(tmp_path / "ev.duckdb")


def _ev(**kw):
    base = dict(
        evidence_id=0,
        type="employment",
        title="Data Engineer",
        description="Built pipelines with Python and SQL.",
    )
    base.update(kw)
    return Evidence(**base)


# -- CRUD ----------------------------------------------------------------------


def test_add_assigns_ids_and_roundtrips(store):
    e1 = store.add(_ev())
    e2 = store.add(_ev(title="Second role"))
    assert e1.evidence_id == 1 and e2.evidence_id == 2
    got = store.get(1)
    assert got.title == "Data Engineer"
    assert got.type == "employment"
    assert got.created_at is not None


def test_add_rejects_unknown_type(store):
    with pytest.raises(ValueError):
        store.add(_ev(type="daydream"))


def test_add_rejects_unknown_verification_status(store):
    with pytest.raises(ValueError):
        store.add(_ev(verification_status="guaranteed"))


def test_valid_types_and_statuses_match_spec():
    assert set(EVIDENCE_TYPES) == {
        "employment",
        "project",
        "skill",
        "technology",
        "outcome",
        "certification",
        "education",
        "portfolio",
    }
    assert set(VERIFICATION_STATUSES) == {"self_reported", "documented", "verified"}


def test_update_fields_whitelist(store):
    e = store.add(_ev())
    with pytest.raises(ValueError):
        store.update_fields(e.evidence_id, bogus_field="x")
    store.update_fields(e.evidence_id, title="Updated", skills=["Python"])
    assert store.get(e.evidence_id).title == "Updated"
    assert store.get(e.evidence_id).skills == ["Python"]


def test_remove(store):
    e = store.add(_ev())
    store.remove(e.evidence_id)
    assert store.get(e.evidence_id) is None


# -- evidence <-> skill linkage ---------------------------------------------------


def test_supported_skills_includes_explicit_and_extracted(store):
    """Explicit skills count; skills mentioned only in the description also count
    (deterministic whole-token extraction), keeping traceability to the item."""
    store.add(_ev(skills=["Python"], description="Led Kubernetes rollout on AWS."))
    supported = store.supported_skills()
    assert "python" in supported
    assert "kubernetes" in supported
    assert "amazon web services" in supported
    # every supported skill maps to real evidence ids
    assert all(isinstance(ids, list) and ids for ids in supported.values())


def test_claims_not_allowed_excluded_from_supported_skills(store):
    store.add(
        _ev(title="Sidebar hobby", description="Hacked on Rust and Go.", claims_allowed=False)
    )
    supported = store.supported_skills()
    assert "rust" not in supported
    assert "go (programming language)" not in supported


def test_metrics_roundtrip(store):
    e = store.add(_ev(metrics=[{"value": 30, "unit": "%", "context": "cost reduction"}]))
    got = store.get(e.evidence_id)
    assert got.metrics == [{"value": 30, "unit": "%", "context": "cost reduction"}]
    assert "30 % cost reduction" in got.text


def test_import_fixture_bulk(store):
    items = store.import_fixture(
        [
            {"type": "project", "title": "Portal", "skills": ["Docker"]},
            {"type": "certification", "title": "PMP", "verification_status": "documented"},
        ]
    )
    assert len(items) == 2
    assert items[1].verification_status == "documented"
    assert all(i.provenance == "fixture import" for i in items)


def test_list_filter_by_type(store):
    store.add(_ev(type="education", title="BSc"))
    store.add(_ev())
    assert len(store.list_all()) == 2
    assert len(store.list_all(evidence_type="education")) == 1
