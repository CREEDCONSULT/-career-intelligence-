"""Next-best-action engine (deterministic).

Produces exactly ONE clear action per active application, then ranks all
active applications by priority so the workspace can surface "what now?".

Priority = state weight (actionability) x fit weight (evidence-backed value)
x urgency (closing-date proximity). No LLM, no magic - the full formula and
per-state rule table are visible below and unit-tested.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

from careeros.application import Application, ApplicationState, DocumentStore
from careeros.fit_engine import FitResult

# ---------------------------------------------------------------------------
# Rule table: state -> action builder
# ---------------------------------------------------------------------------

#: How action-ready each state is (drives ranking, not the action itself).
_STATE_WEIGHT = {
    ApplicationState.DISCOVERED: 2.0,
    ApplicationState.REVIEWED: 2.5,
    ApplicationState.SHORTLISTED: 3.5,
    ApplicationState.PREPARING: 4.0,
    ApplicationState.READY_TO_APPLY: 5.0,
    ApplicationState.APPLIED: 2.5,  # waiting; jumps to 5.0 when follow-up due
    ApplicationState.SCREENING: 4.0,
    ApplicationState.INTERVIEW: 4.0,
    ApplicationState.ASSESSMENT: 4.0,
    ApplicationState.OFFER: 5.0,
}

_FIT_WEIGHT = {
    "STRONG FIT": 3.0,
    "POSSIBLE FIT": 2.0,
    "WEAK FIT": 1.0,
    "INSUFFICIENT EVIDENCE": 0.5,
}

FOLLOW_UP_AFTER_DAYS = 7


@dataclass
class NextAction:
    opportunity_id: int
    application_id: int
    state: str
    action: str
    rationale: str
    priority_score: float
    due_date: Optional[date] = None

    def to_dict(self) -> dict:
        import dataclasses

        return dataclasses.asdict(self)


def _state_of(app: Application) -> ApplicationState:
    return ApplicationState(app.current_state.upper())


def _fit_band_weight(fit: Optional[FitResult]) -> float:
    if fit is None:
        return 1.5  # not yet evaluated: neutral
    return _FIT_WEIGHT.get(fit.band, 1.5)


def _urgency(fit: Optional[FitResult], closing: Optional[date], today: date) -> float:
    if fit is not None:
        return fit.closing_urgency
    if closing is None:
        return 1.0
    days = (closing - today).days
    if days < 0:
        return 0.25
    if days <= 3:
        return 1.5
    if days <= 7:
        return 1.25
    if days <= 14:
        return 1.1
    return 1.0


def compute_next_action(
    application: Application,
    *,
    fit: Optional[FitResult] = None,
    closing_date: Optional[date] = None,
    has_base_resume: bool = False,
    has_tailored_resume: bool = False,
    has_cover_letter: bool = False,
    missing_required: Optional[list[str]] = None,
    upcoming_interview=None,
    now: Optional[datetime] = None,
) -> NextAction:
    """One clear next action for one active application (deterministic)."""
    now = now or datetime.now()
    today = now.date()
    state = _state_of(application)
    if state not in _STATE_WEIGHT:
        raise ValueError(f"compute_next_action is for active applications, got {state}")

    closing_date = closing_date
    urgency = _urgency(fit, closing_date, today)
    state_weight = _STATE_WEIGHT[state]
    fit_weight = _fit_band_weight(fit)

    due: Optional[date] = None

    # ---- per-state rules ----------------------------------------------------
    # Missing requirements: explicit argument wins; else derive from the fit
    # result's genuine gaps so callers don't have to recompute them.
    if missing_required is None and fit is not None:
        missing_required = [g.skill for g in fit.gaps]

    # Interview-stage states with a scheduled interview produce a stage-
    # specific prep action (the calendar fact overrides the generic one).
    if (
        state
        in (ApplicationState.SCREENING, ApplicationState.INTERVIEW, ApplicationState.ASSESSMENT)
        and upcoming_interview is not None
        and upcoming_interview.scheduled_at is not None
    ):
        stage_label = (upcoming_interview.stage or "interview").replace("_", " ")
        days_to = (upcoming_interview.scheduled_at.date() - today).days
        when = upcoming_interview.scheduled_at.strftime("%a %b %d")
        if days_to < 0:
            action = f"Record the outcome of the {stage_label} interview"
            rationale = (
                f"Scheduled for {when} ({abs(days_to)} day(s) ago) - update notes and follow up."
            )
            state_weight = 4.5
        else:
            action = f"Prepare for the {stage_label} interview ({when})"
            rationale = (
                f"Scheduled in {days_to} day(s); prep status is '{upcoming_interview.prep_status}'."
            )
        score = round(state_weight * fit_weight * urgency, 2)
        return NextAction(
            opportunity_id=application.opportunity_id,
            application_id=application.application_id,
            state=state.value,
            action=action,
            rationale=rationale,
            priority_score=score,
            due_date=upcoming_interview.scheduled_at.date(),
        )

    if state is ApplicationState.DISCOVERED:
        action = "Review the job description, then run the fit analysis"
        rationale = "New opportunity - nothing has been reviewed yet."

    elif state is ApplicationState.REVIEWED:
        if fit is None:
            action = "Run the evidence-based fit analysis"
            rationale = "Reviewed but not yet scored against your evidence."
        elif fit.band in ("STRONG FIT", "POSSIBLE FIT"):
            action = "Shortlist this opportunity"
            rationale = f"{fit.band} - worth pursuing."
        else:
            action = "Decide: shortlist as a stretch, or archive"
            rationale = f"{fit.band} - requirements are far from current evidence."

    elif state is ApplicationState.SHORTLISTED:
        action = "Start application prep: save your base resume"
        rationale = "Shortlisted - preparation has not started."
        if not has_base_resume:
            action = "Save your base resume to begin preparation"
            rationale = "Tailoring needs a base resume to work from."

    elif state is ApplicationState.PREPARING:
        if missing_required:
            top = ", ".join(missing_required[:2])
            action = f"Add evidence for: {top}"
            rationale = "Required skills lack evidence - close the gaps before tailoring."
        elif not has_base_resume:
            action = "Save your base resume"
            rationale = "Tailoring needs a base resume to work from."
        elif not has_tailored_resume:
            action = "Generate the evidence-based tailored resume"
            rationale = "Base resume is in place; tailored version not yet created."
        else:
            action = "Finalize materials and mark ready to apply"
            rationale = "Tailored resume exists - ready for final review."

    elif state is ApplicationState.READY_TO_APPLY:
        action = "Submit the application"
        rationale = "Materials are ready."
        if closing_date is not None:
            days = (closing_date - today).days
            if 0 <= days <= 3:
                action = "URGENT: submit the application"
                rationale = f"Closes in {days} day(s) ({closing_date.isoformat()})."
            elif days < 0:
                action = "Closing date has passed - confirm or archive"
                rationale = f"Listed closing date was {closing_date.isoformat()}."
            else:
                rationale = f"Materials ready; closes {closing_date.isoformat()}."

    elif state is ApplicationState.APPLIED:
        # Fallback clock: the application row's updated_at (the store-level
        # helper `next_actions_for_store` refines this with the exact APPLIED
        # event timestamp from the append-only log).
        applied_at = application.updated_at
        if applied_at is not None:
            days_since = (now - applied_at).days
            if days_since >= FOLLOW_UP_AFTER_DAYS:
                action = "Send a follow-up on your application"
                rationale = f"{days_since} days since last update - polite follow-up is due."
                state_weight = 5.0
            else:
                wait_until = (applied_at + timedelta(days=FOLLOW_UP_AFTER_DAYS)).date()
                action = "Await screening response"
                rationale = f"Applied recently; follow up on {wait_until.isoformat()} if silent."
                due = wait_until
        else:
            action = "Await screening response"
            rationale = "Application submitted."

    elif state is ApplicationState.SCREENING:
        action = "Prepare the screening conversation"
        rationale = "Rehearse your evidence-backed strengths and gap answers."

    elif state is ApplicationState.INTERVIEW:
        action = "Prepare for the interview"
        rationale = "Review strengths, gaps, and transferable-evidence talking points."

    elif state is ApplicationState.ASSESSMENT:
        action = "Complete the assessment"
        rationale = "Ground every answer in your evidence ledger."

    elif state is ApplicationState.OFFER:
        action = "Record your offer decision"
        rationale = "Accept (close as filled) or decline (withdraw) - update the record."

    else:  # pragma: no cover - guarded by _STATE_WEIGHT check
        action = "Review this application"
        rationale = ""

    score = round(state_weight * fit_weight * urgency, 2)
    return NextAction(
        opportunity_id=application.opportunity_id,
        application_id=application.application_id,
        state=state.value,
        action=action,
        rationale=rationale,
        priority_score=score,
        due_date=due or (closing_date if state is ApplicationState.READY_TO_APPLY else None),
    )


def rank_next_actions(actions: list[NextAction]) -> list[NextAction]:
    """Highest priority first; ties broken by due date then opportunity id."""
    return sorted(
        actions,
        key=lambda a: (
            -a.priority_score,
            a.due_date.toordinal() if a.due_date else 9999999,
            a.opportunity_id,
        ),
    )


def next_actions_for_store(
    app_store,
    opp_store,
    evidence_store,
    doc_store: DocumentStore,
    *,
    interview_store=None,
    fits: Optional[dict[int, FitResult]] = None,
    now: Optional[datetime] = None,
) -> list[NextAction]:
    """Compute + rank one action per active application across the board.

    ``fits`` may carry precomputed FitResults keyed by opportunity_id; any
    opportunity without an entry is treated as not-yet-evaluated.
    ``interview_store`` (optional) enables stage-specific interview prep
    actions when an interview is scheduled for interview-stage applications.
    """
    from careeros.fit_engine import evaluate_fit

    now = now or datetime.now()
    fits = fits or {}
    out: list[NextAction] = []
    for app in app_store.list_all(active_only=True):
        opp = opp_store.get(app.opportunity_id)
        if opp is None:
            continue
        fit = fits.get(app.opportunity_id)
        if fit is None or fit.opportunity_id != app.opportunity_id:
            fit = evaluate_fit(
                opp, [e for e in evidence_store.list_all() if e.claims_allowed], today=now.date()
            )
            fits[app.opportunity_id] = fit
        state = _state_of(app)
        has_base = doc_store.latest(app.application_id, "base_resume") is not None
        has_tailored = doc_store.latest(app.application_id, "tailored_resume") is not None
        has_cover = doc_store.latest(app.application_id, "cover_letter") is not None
        missing = [g.skill for g in fit.gaps][:3] if fit else None
        upcoming = None
        if interview_store is not None:
            upcoming = interview_store.next_upcoming(app.application_id, now=now)
        action = compute_next_action(
            app,
            fit=fit,
            closing_date=opp.closing_date,
            has_base_resume=has_base,
            has_tailored_resume=has_tailored,
            has_cover_letter=has_cover,
            missing_required=missing,
            upcoming_interview=upcoming,
            now=now,
        )
        # The APPLIED follow-up clock is measured from the actual APPLIED event,
        # not from the application row's updated_at.
        if state is ApplicationState.APPLIED:
            applied_at = app_store.last_transition_date(app.application_id, "APPLIED")
            if applied_at is not None:
                days_since = (now - applied_at).days
                fit_w = _fit_band_weight(fit)
                urg = fit.closing_urgency if fit else 1.0
                if days_since >= FOLLOW_UP_AFTER_DAYS:
                    action.action = "Send a follow-up on your application"
                    action.rationale = f"{days_since} days since applied - follow-up is due."
                    action.priority_score = round(5.0 * fit_w * urg, 2)
                else:
                    wait_until = (applied_at + timedelta(days=FOLLOW_UP_AFTER_DAYS)).date()
                    action.action = "Await screening response"
                    action.rationale = (
                        f"Applied {days_since} day(s) ago; follow up on "
                        f"{wait_until.isoformat()} if silent."
                    )
                    action.due_date = wait_until
                    action.priority_score = round(2.5 * fit_w * urg, 2)
        out.append(action)
    return rank_next_actions(out)
