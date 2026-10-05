"""Tests: application state machine, event log, and document store."""

from datetime import datetime

import pytest

from careeros.application import (
    ApplicationStore,
    DocumentStore,
    InvalidTransition,
)


@pytest.fixture
def apps(tmp_path):
    return ApplicationStore(tmp_path / "apps.duckdb")


@pytest.fixture
def docs(tmp_path):
    return DocumentStore(tmp_path / "apps.duckdb")


@pytest.fixture
def app(apps):
    return apps.create_for_opportunity(opportunity_id=42)


# -- creation -----------------------------------------------------------------


def test_create_starts_discovered_with_creation_event(apps, app):
    assert app.current_state == "DISCOVERED"
    events = apps.events(app.application_id)
    assert len(events) == 1
    assert events[0].previous_state is None
    assert events[0].new_state == "DISCOVERED"
    assert events[0].trigger == "user:create"


def test_one_application_per_opportunity(apps):
    apps.create_for_opportunity(42)
    with pytest.raises(ValueError):
        apps.create_for_opportunity(42)


# -- valid transitions -----------------------------------------------------------


def test_full_happy_path(apps, app):
    path = [
        "REVIEWED",
        "SHORTLISTED",
        "PREPARING",
        "READY_TO_APPLY",
        "APPLIED",
        "SCREENING",
        "INTERVIEW",
        "OFFER",
    ]
    for st in path:
        app = apps.transition(app.application_id, st, trigger="user:test")
    assert app.current_state == "OFFER"
    # OFFER -> CLOSED (accepted)
    app = apps.transition(app.application_id, "CLOSED", trigger="user:accepted")
    assert app.current_state == "CLOSED"


def test_rejection_paths(apps, app):
    app = apps.transition(app.application_id, "REVIEWED", trigger="user:test")
    app = apps.transition(app.application_id, "SHORTLISTED", trigger="user:test")
    app = apps.transition(app.application_id, "CLOSED", trigger="user:expired")
    assert app.current_state == "CLOSED"
    # applied -> rejected
    app2 = apps.create_for_opportunity(43)
    for st in ("REVIEWED", "SHORTLISTED", "PREPARING", "READY_TO_APPLY", "APPLIED"):
        app2 = apps.transition(app2.application_id, st, trigger="user:test")
    app2 = apps.transition(app2.application_id, "REJECTED", trigger="auto:email")
    assert app2.current_state == "REJECTED"


def test_preparing_can_loop_back_to_shortlisted(apps, app):
    for st in ("REVIEWED", "SHORTLISTED", "PREPARING"):
        app = apps.transition(app.application_id, st, trigger="user:test")
    app = apps.transition(app.application_id, "SHORTLISTED", trigger="user:stalled")
    assert app.current_state == "SHORTLISTED"


# -- invalid transitions (explicit table is the only truth) ------------------------


@pytest.mark.parametrize(
    "frm,to",
    [
        ("DISCOVERED", "APPLIED"),
        ("DISCOVERED", "OFFER"),
        ("REVIEWED", "APPLIED"),
        ("SHORTLISTED", "INTERVIEW"),
        ("READY_TO_APPLY", "OFFER"),
        ("APPLIED", "DISCOVERED"),
        ("APPLIED", "INTERVIEW"),  # must pass through screening
        ("OFFER", "APPLIED"),
    ],
)
def test_invalid_transitions_raise(apps, app, frm, to):
    # walk to frm
    walk = {
        "DISCOVERED": [],
        "REVIEWED": ["REVIEWED"],
        "SHORTLISTED": ["REVIEWED", "SHORTLISTED"],
        "PREPARING": ["REVIEWED", "SHORTLISTED", "PREPARING"],
        "READY_TO_APPLY": ["REVIEWED", "SHORTLISTED", "PREPARING", "READY_TO_APPLY"],
        "APPLIED": ["REVIEWED", "SHORTLISTED", "PREPARING", "READY_TO_APPLY", "APPLIED"],
        "OFFER": [
            "REVIEWED",
            "SHORTLISTED",
            "PREPARING",
            "READY_TO_APPLY",
            "APPLIED",
            "SCREENING",
            "INTERVIEW",
            "OFFER",
        ],
    }[frm]
    for st in walk:
        app = apps.transition(app.application_id, st, trigger="user:test")
    with pytest.raises(InvalidTransition):
        apps.transition(app.application_id, to, trigger="user:test")


@pytest.mark.parametrize("terminal", ["REJECTED", "WITHDRAWN", "CLOSED"])
def test_terminal_states_are_frozen(apps, app, terminal):
    if terminal == "REJECTED":
        for st in ("REVIEWED", "SHORTLISTED", "PREPARING", "READY_TO_APPLY", "APPLIED"):
            app = apps.transition(app.application_id, st, trigger="user:test")
        apps.transition(app.application_id, "REJECTED", trigger="auto:mail")
    else:
        apps.transition(app.application_id, terminal, trigger="user:test")
    for nxt in ("REVIEWED", "SHORTLISTED", "APPLIED", "OFFER", "DISCOVERED"):
        with pytest.raises(InvalidTransition):
            apps.transition(app.application_id, nxt, trigger="user:test")


def test_unknown_state_string_raises(apps, app):
    with pytest.raises(InvalidTransition):
        apps.transition(app.application_id, "VAPORIZED", trigger="user:test")


# -- event log integrity (append-only history) --------------------------------------


def test_event_log_is_append_only_and_ordered(apps, app):
    apps.transition(app.application_id, "REVIEWED", trigger="user:test", notes="read it")
    apps.transition(
        app.application_id,
        "SHORTLISTED",
        trigger="user:test",
        artifacts=[{"kind": "fit", "ref": "score: 73"}],
        provenance="workspace",
    )
    events = apps.events(app.application_id)
    assert [e.new_state for e in events] == ["DISCOVERED", "REVIEWED", "SHORTLISTED"]
    assert events[1].previous_state == "DISCOVERED"
    assert events[2].artifacts == [{"kind": "fit", "ref": "score: 73"}]
    assert events[2].provenance == "workspace"
    # earlier events untouched by later transitions
    assert events[0].notes is None
    ids = [e.event_id for e in events]
    assert ids == sorted(ids)


def test_last_transition_date(apps, app):
    assert apps.last_transition_date(app.application_id, "APPLIED") is None
    for st in ("REVIEWED", "SHORTLISTED", "PREPARING", "READY_TO_APPLY", "APPLIED"):
        app = apps.transition(app.application_id, st, trigger="user:test")
    got = apps.last_transition_date(app.application_id, "APPLIED")
    assert isinstance(got, datetime)


def test_list_all_active_only(apps):
    a1 = apps.create_for_opportunity(1)
    a2 = apps.create_for_opportunity(2)
    apps.transition(a2.application_id, "WITHDRAWN", trigger="user:test")
    active = apps.list_all(active_only=True)
    assert {a.application_id for a in active} == {a1.application_id}
    assert len(apps.list_all()) == 2


# -- document store -----------------------------------------------------------------


def test_document_versioning_never_overwrites(docs):
    d1 = docs.save(
        7, "tailored_resume", "v1 text", evidence_used=[1, 2], excluded_claims=["kubernetes"]
    )
    assert d1.version == 1
    d2 = docs.save(7, "tailored_resume", "v2 text", evidence_used=[1])
    assert d2.version == 2
    latest = docs.latest(7, "tailored_resume")
    assert latest.content == "v2 text" and latest.version == 2
    versions = docs.list_versions(7, "tailored_resume")
    assert [v.version for v in versions] == [1, 2]
    assert versions[0].content == "v1 text"  # history preserved
    assert versions[0].excluded_claims == ["kubernetes"]


def test_document_rejects_unknown_type(docs):
    with pytest.raises(ValueError):
        docs.save(7, "tweet", "x")


def test_latest_missing_returns_none(docs):
    assert docs.latest(999, "base_resume") is None
