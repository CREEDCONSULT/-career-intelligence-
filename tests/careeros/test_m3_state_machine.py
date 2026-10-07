"""Tests: M3 state machine additions (REVIEWING, APPROVED_TO_APPLY, RECRUITER_CONTACT, ARCHIVED)."""

import pytest

from careeros.application import (
    ApplicationState,
    ApplicationStore,
    InvalidTransition,
    TRANSITIONS,
    TERMINAL_STATES,
)


@pytest.fixture
def apps(tmp_path):
    return ApplicationStore(tmp_path / "sm.duckdb")


@pytest.fixture
def app(apps):
    return apps.create_for_opportunity(1)


class TestM3NewStates:
    """Tests for the four M3 additions to the state machine."""

    # -- REVIEWING -------------------------------------------------------------
    def test_reviewing_from_discovered(self, apps, app):
        """DISCOVERED → REVIEWING is a legal transition."""
        result = apps.transition(app.application_id, "REVIEWING", trigger="user:test")
        assert result.current_state == "REVIEWING"

    def test_reviewing_to_approved(self, apps, app):
        """REVIEWING → APPROVED_TO_APPLY is the founder-approval gate."""
        apps.transition(app.application_id, "REVIEWING", trigger="user:test")
        result = apps.transition(app.application_id, "APPROVED_TO_APPLY", trigger="user:approve")
        assert result.current_state == "APPROVED_TO_APPLY"

    def test_reviewed_to_reviewing(self, apps, app):
        """REVIEWED → REVIEWING (upgrade to the M3 name) is legal."""
        apps.transition(app.application_id, "REVIEWED", trigger="user:test")
        result = apps.transition(app.application_id, "REVIEWING", trigger="user:test")
        assert result.current_state == "REVIEWING"

    # -- APPROVED_TO_APPLY -------------------------------------------------------
    def test_approved_to_preparing(self, apps, app):
        """APPROVED_TO_APPLY → PREPARING is the normal path after approval."""
        for st in ("REVIEWING", "APPROVED_TO_APPLY"):
            app = apps.transition(app.application_id, st, trigger="user:test")
        result = apps.transition(app.application_id, "PREPARING", trigger="user:test")
        assert result.current_state == "PREPARING"

    def test_approved_to_ready(self, apps, app):
        """APPROVED_TO_APPLY → READY_TO_APPLY is legal (skip preparation if materials exist)."""
        for st in ("REVIEWED", "APPROVED_TO_APPLY"):
            app = apps.transition(app.application_id, st, trigger="user:test")
        result = apps.transition(app.application_id, "READY_TO_APPLY", trigger="user:test")
        assert result.current_state == "READY_TO_APPLY"

    def test_approved_to_apply_is_not_terminal(self):
        """APPROVED_TO_APPLY must have transitions (it's an active state)."""
        assert TRANSITIONS[ApplicationState.APPROVED_TO_APPLY]
        assert ApplicationState.APPROVED_TO_APPLY not in TERMINAL_STATES

    # -- RECRUITER_CONTACT ---------------------------------------------------------
    def test_recruiter_contact_from_applied(self, apps, app):
        """APPLIED → RECRUITER_CONTACT (recruiter reaches out) is legal."""
        for st in ("REVIEWED", "SHORTLISTED", "PREPARING", "READY_TO_APPLY", "APPLIED"):
            app = apps.transition(app.application_id, st, trigger="user:test")
        result = apps.transition(
            app.application_id, "RECRUITER_CONTACT", trigger="auto:gmail-signal"
        )
        assert result.current_state == "RECRUITER_CONTACT"

    def test_recruiter_contact_to_interview(self, apps, app):
        """RECRUITER_CONTACT → INTERVIEW is legal (advances to interview stage)."""
        for st in (
            "REVIEWED",
            "SHORTLISTED",
            "PREPARING",
            "READY_TO_APPLY",
            "APPLIED",
            "RECRUITER_CONTACT",
        ):
            app = apps.transition(app.application_id, st, trigger="user:test")
        result = apps.transition(app.application_id, "INTERVIEW", trigger="user:test")
        assert result.current_state == "INTERVIEW"

    # -- ARCHIVED ------------------------------------------------------------------
    def test_archived_is_terminal(self):
        """ARCHIVED must be terminal (no outgoing transitions)."""
        assert ApplicationState.ARCHIVED in TERMINAL_STATES
        assert not TRANSITIONS[ApplicationState.ARCHIVED]

    def test_any_active_state_can_archive(self, apps, app):
        """ARCHIVED is reachable from an active state."""
        # Walk to APPLIED (a valid active state)
        for st in ("REVIEWED", "SHORTLISTED", "PREPARING", "READY_TO_APPLY", "APPLIED"):
            app = apps.transition(app.application_id, st, trigger="user:test")
        # Then archive
        result = apps.transition(app.application_id, "ARCHIVED", trigger="user:stale")
        assert result.current_state == "ARCHIVED"
        # Terminal: further transitions are rejected
        with pytest.raises(InvalidTransition):
            apps.transition(app.application_id, "REVIEWED", trigger="user:test")

    # -- No automatic APPLIED ----------------------------------------------------------
    def test_discovered_cannot_jump_to_applied(self, apps, app):
        """DISCOVERED → APPLIED is illegal (founder approval required)."""
        with pytest.raises(InvalidTransition):
            apps.transition(app.application_id, "APPLIED", trigger="user:test")

    def test_reviewed_cannot_jump_to_applied(self, apps, app):
        """REVIEWED → APPLIED is illegal (must go through preparation)."""
        apps.transition(app.application_id, "REVIEWED", trigger="user:test")
        with pytest.raises(InvalidTransition):
            apps.transition(app.application_id, "APPLIED", trigger="user:test")

    def test_approved_cannot_jump_to_applied(self, apps, app):
        """APPROVED_TO_APPLY → APPLIED is illegal (must prepare first)."""
        apps.transition(app.application_id, "REVIEWING", trigger="user:test")
        apps.transition(app.application_id, "APPROVED_TO_APPLY", trigger="user:test")
        with pytest.raises(InvalidTransition):
            apps.transition(app.application_id, "APPLIED", trigger="user:test")

    # -- Backward compatibility ---------------------------------------------------------
    def test_old_transitions_still_work(self, apps, app):
        """All pre-M3 transitions must remain functional."""
        for st in ("REVIEWED", "SHORTLISTED", "PREPARING", "READY_TO_APPLY"):
            app = apps.transition(app.application_id, st, trigger="user:test")
        assert app.current_state == "READY_TO_APPLY"
        app = apps.transition(app.application_id, "APPLIED", trigger="user:submit")
        assert app.current_state == "APPLIED"

    def test_old_screening_still_works(self, apps, app):
        """SCREENING (pre-M3 name) is still reachable and functional."""
        for st in ("REVIEWED", "SHORTLISTED", "PREPARING", "READY_TO_APPLY", "APPLIED"):
            app = apps.transition(app.application_id, st, trigger="user:test")
        app = apps.transition(app.application_id, "SCREENING", trigger="auto:screen")
        assert app.current_state == "SCREENING"

    # -- 17 states total -----------------------------------------------------------------
    def test_state_count(self):
        """13 original + 4 new = 17 states total."""
        assert len(list(ApplicationState)) == 17

    def test_pipeline_views_cover_every_state(self):
        """Every state appears in at least one pipeline view."""
        from careeros.pipeline import PIPELINE_VIEWS

        covered = set()
        for states in PIPELINE_VIEWS.values():
            covered |= set(states)
        assert covered == set(ApplicationState)


class TestM3NBA:
    """NBA rules for the new M3 states."""

    def test_nba_reviewing_action(self, apps, app):
        apps.transition(app.application_id, "REVIEWING", trigger="user:test")
        from careeros.next_action import compute_next_action

        action = compute_next_action(app)
        assert "fit analysis" in action.action.lower() or "approve" in action.action.lower()

    def test_nba_approved_to_apply_action(self, apps, app):
        apps.transition(app.application_id, "REVIEWING", trigger="user:test")
        app = apps.transition(app.application_id, "APPROVED_TO_APPLY", trigger="user:test")
        from careeros.next_action import compute_next_action

        action = compute_next_action(app)
        assert "preparation" in action.action.lower() or "resume" in action.action.lower()

    def test_nba_recruiter_contact_action(self, apps, app):
        for st in (
            "REVIEWED",
            "SHORTLISTED",
            "PREPARING",
            "READY_TO_APPLY",
            "APPLIED",
            "RECRUITER_CONTACT",
        ):
            app = apps.transition(app.application_id, st, trigger="user:test")
        from careeros.next_action import compute_next_action

        action = compute_next_action(app)
        assert "recruiter" in action.action.lower() or "respond" in action.action.lower()

    def test_archived_not_in_nba(self, apps, app):
        """ARCHIVED is terminal; NBA should not produce an action for it."""
        app = apps.transition(app.application_id, "ARCHIVED", trigger="user:test")
        from careeros.next_action import compute_next_action

        with pytest.raises(ValueError):
            compute_next_action(app)
