"""Tests: Calendar connector (read-only, discovery, matching) + Drive connector (read-only metadata, artifact discovery)."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from careeros.google_calendar import (
    CalendarConnector,
    DiscoveredEvent,
    _parse_google_datetime,
)
from careeros.google_drive import (
    DriveConnector,
    DiscoveredFile,
    _ARTIFACT_PATTERNS,
)


# ============================================================================
# Calendar
# ============================================================================


def test_calendar_create_event_always_raises():
    """HARD BLOCK: no calendar writes."""
    cal = CalendarConnector()
    with pytest.raises(PermissionError, match="READ-ONLY"):
        cal.create_event(type("E", (), {"title": "t", "start": None})())


def test_calendar_list_upcoming_offline():
    with patch("careeros.google_calendar.load_tokens", return_value=None):
        cal = CalendarConnector()
        assert cal.list_upcoming() == []


def test_calendar_health_offline():
    with patch("careeros.google_calendar.load_tokens", return_value=None):
        cal = CalendarConnector()
        h = cal.health()
    assert h.connector == "calendar"
    assert h.to_dict()["status"] == "offline"


def test_discovered_event_provenance():
    ev = DiscoveredEvent("evt-123", "Interview with Acme", datetime(2026, 10, 10))
    assert ev.source_ref == "gcal:event/evt-123"
    assert ev.provenance == "google-calendar:readonly"
    assert ev.matched_opportunity_id is None
    assert ev.match_confidence == "unmatched"


def test_discover_interview_context_filters():
    """Only events with interview keywords are returned as relevant."""
    cal = CalendarConnector()
    events = [
        DiscoveredEvent("e1", "Interview with team", datetime(2026, 10, 10)),
        DiscoveredEvent("e2", "Lunch with friend", datetime(2026, 10, 11)),
        DiscoveredEvent("e3", "Technical assessment - Python", datetime(2026, 10, 12)),
        DiscoveredEvent("e4", "Weekly team sync", datetime(2026, 10, 13)),
    ]
    # Mock list_upcoming to return our test events
    with patch.object(CalendarConnector, "list_upcoming", return_value=events):
        relevant = cal.discover_interview_context()
    summaries = [e.summary for e in relevant]
    assert "Interview with team" in summaries
    assert "Technical assessment - Python" in summaries
    assert "Lunch with friend" not in summaries
    assert "Weekly team sync" not in summaries


def test_unmatched_events_stay_unmatched():
    """Events that don't match any opportunity stay unmatched — no guessing."""
    cal = CalendarConnector()
    mock_opp = MagicMock()
    mock_opp.opportunity_id = 1
    mock_opp.company = "Northwind"
    mock_opp.role_title = "Data Engineer"
    mock_store = MagicMock()
    mock_store.list_all.return_value = [mock_opp]

    events = [
        DiscoveredEvent("e1", "Interview at Northwind", datetime(2026, 10, 10)),
        DiscoveredEvent("e2", "Completely unrelated event", datetime(2026, 10, 11)),
    ]
    result = cal.associate_with_opportunities(events, mock_store)
    assert result[0].matched_opportunity_id == 1
    assert result[0].match_confidence == "company-matched"
    assert result[1].matched_opportunity_id is None
    assert result[1].match_confidence == "unmatched"


def test_parse_google_datetime():
    assert _parse_google_datetime("2026-10-10T14:00:00-04:00") is not None
    assert _parse_google_datetime("2026-10-10") is not None
    assert _parse_google_datetime(None) is None
    assert _parse_google_datetime("") is None
    assert _parse_google_datetime("garbage") is None


# ============================================================================
# Drive
# ============================================================================


def test_drive_upload_always_raises():
    """HARD BLOCK: no file mutation."""
    drive = DriveConnector()
    with pytest.raises(PermissionError, match="READ-ONLY"):
        drive.upload(type("F", (), {"name": "t", "content": b"", "mime_type": "text/plain"})())


def test_drive_list_files_offline():
    with patch("careeros.google_drive.load_tokens", return_value=None):
        drive = DriveConnector()
        assert drive.list_files() == []


def test_drive_health_offline():
    with patch("careeros.google_drive.load_tokens", return_value=None):
        drive = DriveConnector()
        h = drive.health()
    assert h.connector == "drive"
    assert h.to_dict()["status"] == "offline"


def test_discovered_file_provenance():
    df = DiscoveredFile("f-123", "my_resume.pdf", "application/pdf")
    assert df.source_ref == "gdrive:file/f-123"
    assert df.provenance == "google-drive:metadata.readonly"


def test_artifact_patterns_cover_required_types():
    """The five career-artifact types from the brief are all recognized."""
    types = {t for t, _ in _ARTIFACT_PATTERNS}
    assert {"resume", "cover_letter", "certificate", "portfolio", "employment_evidence"} <= types


def test_career_artifact_discovery_filters_relevance():
    """Only files matching BOTH a pattern AND a safe mime-type are relevant."""
    drive = DriveConnector()
    test_files = [
        {
            "file_id": "1",
            "name": "my_resume_2026.pdf",
            "mime_type": "application/pdf",
            "modified_time": "2026-10-01",
        },
        {
            "file_id": "2",
            "name": "random_notes.txt",
            "mime_type": "text/plain",
            "modified_time": "2026-10-01",
        },
        {
            "file_id": "3",
            "name": "resume.exe",
            "mime_type": "application/x-msdownload",
            "modified_time": "2026-10-01",
        },  # pattern match but unsafe mime
        {
            "file_id": "4",
            "name": "cover_letter_acme.docx",
            "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "modified_time": "2026-10-01",
        },
    ]
    with patch.object(DriveConnector, "list_files", return_value=test_files):
        artifacts = drive.discover_career_artifacts()
    relevant = [a for a in artifacts if a.relevant]
    # resume.pdf: relevant (pattern + safe mime)
    # random_notes.txt: not relevant (no pattern)
    # resume.exe: not relevant (unsafe mime)
    # cover_letter_acme.docx: relevant (pattern + safe mime)
    relevant_ids = {a.file_id for a in relevant}
    assert relevant_ids == {"1", "4"}
    assert all(a.artifact_type is not None for a in relevant)


def test_not_every_file_is_career_evidence():
    """A random Drive file must NOT be silently treated as career evidence."""
    drive = DriveConnector()
    test_files = [
        {
            "file_id": "x",
            "name": "vacation_photo.jpg",
            "mime_type": "image/jpeg",
            "modified_time": None,
        },
    ]
    with patch.object(DriveConnector, "list_files", return_value=test_files):
        artifacts = drive.discover_career_artifacts()
    assert artifacts[0].relevant is False
    assert artifacts[0].artifact_type is None


# ============================================================================
# Null-adapter regression (existing M2 code still works)
# ============================================================================


def test_null_email_adapter_still_works():
    from careeros.integrations import NullEmailAdapter, EmailMessage

    null = NullEmailAdapter()
    msg = EmailMessage(to="x", subject="s", body="b")
    result = null.send(msg)
    assert result.sent_at is None
    assert null.search_threads("anything") == []


def test_null_calendar_adapter_still_works():
    from careeros.integrations import NullCalendarAdapter, CalendarEvent

    null = NullCalendarAdapter()
    ev = CalendarEvent(title="t", start=datetime(2026, 10, 10))
    result = null.create_event(ev)
    assert result.event_ref is None
    assert null.list_upcoming() == []


def test_null_drive_adapter_still_works():
    from careeros.integrations import NullDriveAdapter, DriveFile

    null = NullDriveAdapter()
    f = DriveFile(name="t", content=b"x")
    result = null.upload(f)
    assert result.file_ref is None
    assert null.list_files() == []
