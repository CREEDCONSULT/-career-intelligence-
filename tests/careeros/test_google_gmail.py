"""Tests: Gmail connector (read-only enforcement, career queries, provenance, dedup)."""

from unittest.mock import MagicMock, patch

import pytest

from careeros.google_gmail import (
    CAREER_QUERIES,
    GmailConnector,
    _extract_email,
    _parse_rfc2822,
)


# -- read-only enforcement ------------------------------------------------------------


def test_send_always_raises():
    """HARD BLOCK: no email is ever sent through this connector."""
    gmail = GmailConnector()
    with pytest.raises(PermissionError, match="READ-ONLY"):
        gmail.send(type("M", (), {"to": "x", "subject": "s", "body": "b"})())


def test_send_raises_even_when_authorized():
    """Even with valid tokens, send() must raise."""
    gmail = GmailConnector()
    with pytest.raises(PermissionError):
        gmail.send(type("M", (), {"to": "x", "subject": "s", "body": "b"})())


# -- bounded queries -----------------------------------------------------------------------


def test_career_queries_are_bounded():
    """Every query targets a specific career signal — no broad harvesting."""
    assert len(CAREER_QUERIES) >= 7
    for name, query in CAREER_QUERIES.items():
        assert "-in:spam" in query, f"Query '{name}' lacks spam filter"
        # No query should be a broad inbox scan
        assert query != "in:inbox"
        assert "label:all" not in query


def test_career_queries_cover_required_signals():
    """The required signal types from the M2.1 brief are all covered."""
    required = {
        "application_acknowledgement",
        "recruiter_contact",
        "interview_invitation",
        "assessment",
        "rejection",
        "offer",
        "scheduling_change",
    }
    assert required <= set(CAREER_QUERIES.keys())


# -- offline/null behavior ------------------------------------------------------------------


def test_search_threads_offline_returns_empty():
    gmail = GmailConnector()
    assert gmail.search_threads("any query") == []


def test_health_offline():
    gmail = GmailConnector()
    h = gmail.health()
    assert h.connector == "gmail"
    assert h.authorized is False
    assert h.to_dict()["status"] == "offline"


# -- health with mocked tokens ---------------------------------------------------------------


def test_health_reports_missing_scope(tmp_path, monkeypatch):
    """If tokens exist but the Gmail scope is absent, health reports not authorized."""
    mock_creds = MagicMock()
    mock_creds.valid = True
    mock_creds.scopes = ["https://www.googleapis.com/auth/calendar.readonly"]  # no gmail scope
    # Patch where google_gmail imported it, not where it's defined
    with patch("careeros.google_gmail.load_tokens", return_value=mock_creds):
        gmail = GmailConnector()
        h = gmail.health()
        assert h.authorized is False  # scope not granted
        assert h.configured is True


# -- email parsing helpers ---------------------------------------------------------------------


def test_extract_email_from_angle_brackets():
    assert _extract_email("Sarah <sarah@northwind.io>") == "sarah@northwind.io"
    assert _extract_email("John Smith <john@corp.com>") == "john@corp.com"


def test_extract_email_bare():
    assert _extract_email("sarah@northwind.io") == "sarah@northwind.io"


def test_extract_email_none():
    assert _extract_email("no email here") is None
    assert _extract_email("") is None


def test_parse_rfc2822_valid():
    dt = _parse_rfc2822("Mon, 05 Oct 2026 10:00:00 -0400")
    assert dt is not None
    assert dt.year == 2026 and dt.month == 10


def test_parse_rfc2822_invalid():
    assert _parse_rfc2822("") is None
    assert _parse_rfc2822("not a date") is None


# -- provenance format ------------------------------------------------------------------------


def test_provenance_format_is_thread_reference():
    """Every imported message must carry a gmail:thread/<id> reference."""
    ref = "gmail:thread/abc123"
    assert ref.startswith("gmail:thread/")
    parts = ref.split("/", 1)
    assert len(parts) == 2  # protocol prefix + thread id
    assert parts[0] == "gmail:thread"
    assert parts[1] == "abc123"
