"""Tests: communications (signals, association, provenance) + interviews."""

from datetime import datetime, timedelta

import pytest

from careeros.communications import (
    CommunicationStore,
    detect_signals,
    _company_from_email,
)
from careeros.interviews import InterviewStore, INTERVIEW_STAGES, PREP_STATUSES
from careeros.opportunity import OpportunityStore
from careeros.ingestion import ingest, ManualPasteAdapter


@pytest.fixture
def comms(tmp_path):
    return CommunicationStore(tmp_path / "c.duckdb")


@pytest.fixture
def opps(tmp_path):
    return OpportunityStore(tmp_path / "c.duckdb")


@pytest.fixture
def ivs(tmp_path):
    return InterviewStore(tmp_path / "c.duckdb")


# -- deterministic signal detection ------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("We would like to invite you to an interview", ["interview"]),
        ("Please complete the take-home assessment by Friday", ["assessment"]),
        ("Unfortunately we have decided to move forward with another candidate", ["rejection"]),
        ("We are pleased to offer you the position", ["offer"]),
        ("I came across your profile and have an opportunity", ["recruiter"]),
        ("Thanks for reaching out, sounds interesting", []),
    ],
)
def test_detect_signals(text, expected):
    assert set(detect_signals(text)) == set(expected)


def test_company_from_email_deterministic():
    assert _company_from_email("sarah@northwind.io") == "northwind"
    assert _company_from_email("sarah@gmail.com") is None
    assert _company_from_email(None) is None
    assert _company_from_email("not-an-email") is None


# -- recording + association --------------------------------------------------


def test_record_persists_signals_and_provenance(comms):
    msg = comms.record(
        sender="Sarah Chen",
        sender_email="sarah@northwind.io",
        subject="Interview invitation",
        body="We would like to invite you to an interview.",
        received_at=datetime(2026, 10, 5, 10, 0),
        provenance="fixture:gmail-export",
    )
    assert msg.signals == ["interview"]
    assert msg.company_guess == "northwind"
    assert msg.provenance == "fixture:gmail-export"
    assert comms.get(msg.message_id) is not None


def test_associate_and_suggestions(comms, opps):
    opp = ingest(opps, ManualPasteAdapter(), "Data Engineer at Northwind Analytics\nPython role.")
    msg = comms.record(
        sender="Sarah",
        sender_email="sarah@northwind.io",
        subject="Role update",
        body="Hello",
        received_at=None,
        provenance="fixture",
    )
    # suggestion by domain match before association
    suggestions = comms.suggest_associations(opps)
    assert suggestions.get(msg.message_id) == [opp.opportunity_id]
    # user confirms
    comms.associate(msg.message_id, opp.opportunity_id, provenance="user:test")
    got = comms.get(msg.message_id)
    assert got.opportunity_id == opp.opportunity_id
    assert "user:test" in (got.provenance or "")
    # no longer suggested (already associated)
    assert msg.message_id not in comms.suggest_associations(opps)


def test_associated_messages_listed_per_opportunity(comms, opps):
    opp = ingest(opps, ManualPasteAdapter(), "Dev at Acme\nx")
    m1 = comms.record("A", "a@acme.co", "s1", "b1", None, "fixture")
    comms.record("B", "b@acme.co", "s2", "b2", None, "fixture")
    comms.associate(m1.message_id, opp.opportunity_id)
    per_opp = comms.list_all(opportunity_id=opp.opportunity_id)
    assert len(per_opp) == 1
    assert len(comms.list_all()) == 2


def test_fixture_import_bulk(comms):
    msgs = comms.import_fixture(
        [
            {
                "sender": "R",
                "sender_email": "r@corp.io",
                "subject": "Interview?",
                "body": "let's do an interview",
                "received_at": "2026-10-05T10:00:00",
            },
            {
                "sender": "X",
                "sender_email": "x@corp.io",
                "subject": "Offer",
                "body": "pleased to offer",
                "received_at": None,
            },
        ]
    )
    assert len(msgs) == 2
    assert "interview" in msgs[0].signals
    assert "offer" in msgs[1].signals
    assert all(m.provenance == "fixture:gmail-export" for m in msgs)


def test_filter_by_signal(comms):
    comms.record("A", None, "Re: role", "unfortunately not moving forward", None, "f")
    comms.record("B", None, "Re: role", "let's schedule an interview", None, "f")
    rejections = comms.list_all(signal="rejection")
    assert len(rejections) == 1


# -- interviews -----------------------------------------------------------------


def test_schedule_interview_valid_stage(ivs):
    iv = ivs.schedule(
        1,
        "recruiter_screen",
        "SCREENING",
        scheduled_at=datetime(2026, 10, 10, 14, 0),
        duration_minutes=30,
        location="Google Meet",
        participants=["Sarah (Recruiter)"],
    )
    assert iv.stage == "recruiter_screen"
    assert iv.prep_status == "not_started"
    assert iv.participants == ["Sarah (Recruiter)"]


def test_schedule_rejects_unknown_stage(ivs):
    with pytest.raises(ValueError):
        ivs.schedule(1, "coffee_chat", "SCREENING")


def test_schedule_rejects_wrong_app_state(ivs):
    with pytest.raises(ValueError):
        ivs.schedule(1, "recruiter_screen", "DISCOVERED")


def test_prep_status_lifecycle(ivs):
    iv = ivs.schedule(1, "technical_case", "INTERVIEW")
    ivs.update_fields(iv.interview_id, prep_status="in_progress")
    assert ivs.get(iv.interview_id).prep_status == "in_progress"
    ivs.update_fields(iv.interview_id, prep_status="ready", notes="Reviewed system design stories")
    got = ivs.get(iv.interview_id)
    assert got.prep_status == "ready"
    assert got.notes == "Reviewed system design stories"


def test_next_upcoming_picks_soonest(ivs):
    now = datetime(2026, 10, 5)
    ivs.schedule(1, "hiring_manager", "INTERVIEW", scheduled_at=now + timedelta(days=7))
    ivs.schedule(1, "technical_case", "INTERVIEW", scheduled_at=now + timedelta(days=3))
    nxt = ivs.next_upcoming(1, now=now)
    assert nxt is not None
    assert nxt.stage == "technical_case"


def test_next_upcoming_ignores_past(ivs):
    now = datetime(2026, 10, 5)
    ivs.schedule(1, "recruiter_screen", "SCREENING", scheduled_at=now - timedelta(days=2))
    assert ivs.next_upcoming(1, now=now) is None


def test_update_fields_whitelist(ivs):
    iv = ivs.schedule(1, "panel_final", "INTERVIEW")
    with pytest.raises(ValueError):
        ivs.update_fields(iv.interview_id, bogus_field="x")
