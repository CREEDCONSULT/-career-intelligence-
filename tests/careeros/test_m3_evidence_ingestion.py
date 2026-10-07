"""Tests: M3 evidence ingestion adapters (GitHub + Drive + structured import)."""

from unittest.mock import MagicMock, patch

import pytest

from careeros.evidence import EvidenceStore
from careeros.evidence_ingestion import (
    github_repo_to_evidence,
    ingest_github_evidence,
    drive_file_to_evidence,
    ingest_drive_evidence,
    ingest_structured,
)
from careeros.google_drive import DiscoveredFile


@pytest.fixture
def store(tmp_path):
    return EvidenceStore(tmp_path / "ei.duckdb")


# -- GitHub adapter ----------------------------------------------------------------


def _gh_data():
    return {
        "name": "career-intelligence",
        "description": "AI-powered career intelligence dashboard",
        "primaryLanguage": {"name": "Python"},
        "languages": {"edges": [{"name": "Python"}, {"name": "TypeScript"}]},
        "repositoryTopics": {"nodes": [{"name": "ai"}, {"name": "streamlit"}]},
        "createdAt": "2024-01-01T00:00:00Z",
    }


def test_github_repo_to_evidence_is_unverified():
    ev = github_repo_to_evidence("CREEDCONSULT", "career-intelligence", _gh_data())
    assert ev.verification_state == "UNVERIFIED"
    assert ev.claims_allowed is False


def test_github_repo_to_evidence_has_provenance():
    ev = github_repo_to_evidence("CREEDCONSULT", "career-intelligence", _gh_data())
    assert ev.provenance == "github:CREEDCONSULT/career-intelligence"


def test_github_repo_to_evidence_type():
    ev = github_repo_to_evidence("CREEDCONSULT", "career-intelligence", _gh_data())
    assert ev.type == "github_repository"


def test_github_repo_to_evidence_captures_skills():
    ev = github_repo_to_evidence("CREEDCONSULT", "career-intelligence", _gh_data())
    assert "Python" in ev.skills
    assert "TypeScript" in ev.skills
    assert "ai" in ev.skills


def test_github_repo_to_evidence_never_infers_achievement():
    """Repo existence does NOT imply expertise or achievements."""
    ev = github_repo_to_evidence("CREEDCONSULT", "career-intelligence", _gh_data())
    # No fabricated metrics
    assert ev.metrics == []
    # Description contains only factual repo metadata
    assert "expert" not in (ev.description or "").lower()
    assert "achieved" not in (ev.description or "").lower()
    assert "led " not in (ev.description or "").lower()


def test_github_ingest_adds_unverified(store):
    with patch("careeros.evidence_ingestion.fetch_github_repo", return_value=_gh_data()):
        ev = ingest_github_evidence(store, "CREEDCONSULT", "career-intelligence")
    assert ev is not None
    assert ev.verification_state == "UNVERIFIED"
    assert ev.claims_allowed is False


def test_github_ingest_handles_missing_repo(store):
    with patch("careeros.evidence_ingestion.fetch_github_repo", return_value=None):
        ev = ingest_github_evidence(store, "CREEDCONSULT", "nonexistent")
    assert ev is None


# -- Drive adapter -----------------------------------------------------------------


def _drive_artifact():
    return DiscoveredFile(
        file_id="abc123",
        name="my_resume_2026.pdf",
        mime_type="application/pdf",
        modified_time="2026-10-01",
    )


def test_drive_file_to_evidence_is_unverified():
    f = _drive_artifact()
    f.artifact_type = "resume"
    f.relevant = True
    ev = drive_file_to_evidence(f)
    assert ev.verification_state == "UNVERIFIED"
    assert ev.claims_allowed is False


def test_drive_file_to_evidence_has_provenance():
    f = _drive_artifact()
    f.artifact_type = "resume"
    ev = drive_file_to_evidence(f)
    assert ev.provenance == "drive:abc123"


def test_drive_file_to_evidence_type_mapping():
    f = _drive_artifact()
    f.artifact_type = "resume"
    ev = drive_file_to_evidence(f)
    assert ev.type == "employment"


def test_drive_file_to_evidence_certificate_mapping():
    f = _drive_artifact()
    f.artifact_type = "certificate"
    ev = drive_file_to_evidence(f)
    assert ev.type == "certification"


def test_drive_file_to_evidence_metadata_only():
    """Drive evidence contains metadata only — no content."""
    f = _drive_artifact()
    f.artifact_type = "resume"
    ev = drive_file_to_evidence(f)
    assert "Metadata only" in ev.description
    assert "content not read" in ev.description.lower()


def test_drive_ingest_deduplicates(store):
    """Re-importing the same Drive file doesn't create a duplicate."""
    f = _drive_artifact()
    f.artifact_type = "resume"
    f.relevant = True

    mock_connector = MagicMock()
    mock_connector.discover_career_artifacts.return_value = [f]

    # First import
    added1 = ingest_drive_evidence(store, mock_connector)
    assert len(added1) == 1

    # Second import (same file) — should skip
    added2 = ingest_drive_evidence(store, mock_connector)
    assert len(added2) == 0
    assert len(store.list_all()) == 1


def test_drive_ingest_skips_irrelevant(store):
    """Non-relevant files are not imported."""
    f = _drive_artifact()
    f.artifact_type = None
    f.relevant = False

    mock_connector = MagicMock()
    mock_connector.discover_career_artifacts.return_value = [f]

    added = ingest_drive_evidence(store, mock_connector)
    assert len(added) == 0


# -- Structured import ----------------------------------------------------------------


def test_structured_import_defaults_to_unverified(store):
    items = [{"type": "employment", "title": "Data Engineer"}]
    added = ingest_structured(store, items)
    assert added[0].verification_state == "UNVERIFIED"
    assert added[0].claims_allowed is False


def test_structured_import_respects_explicit_state(store):
    """If the founder explicitly sets VERIFIED, it's honored (their decision)."""
    items = [{"type": "employment", "title": "Data Engineer", "verification_state": "VERIFIED"}]
    added = ingest_structured(store, items)
    assert added[0].verification_state == "VERIFIED"
    assert added[0].claims_allowed is True


def test_structured_import_has_provenance(store):
    items = [{"type": "project", "title": "My Project"}]
    added = ingest_structured(store, items)
    assert "founder:structured-import" in added[0].provenance


# -- Cross-cutting: no auto-promotion ----------------------------------------------------


def test_no_auto_promote_from_github(store):
    """GitHub evidence NEVER auto-promotes to VERIFIED."""
    with patch("careeros.evidence_ingestion.fetch_github_repo", return_value=_gh_data()):
        ev = ingest_github_evidence(store, "CREEDCONSULT", "career-intelligence")
    assert ev.verification_state == "UNVERIFIED"
    # Even after re-reading from the store
    stored = store.get(ev.evidence_id)
    assert stored.verification_state == "UNVERIFIED"


def test_no_auto_promote_from_drive(store):
    """Drive evidence NEVER auto-promotes to VERIFIED."""
    f = _drive_artifact()
    f.artifact_type = "resume"
    f.relevant = True
    mock_connector = MagicMock()
    mock_connector.discover_career_artifacts.return_value = [f]

    added = ingest_drive_evidence(store, mock_connector)
    assert added[0].verification_state == "UNVERIFIED"
