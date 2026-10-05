"""Page: Opportunities - discovery board + per-opportunity application workspace.

One workspace per opportunity (Job & Fit | Evidence Map | Prepare | Status &
Log) so a job is never scattered across unrelated pages. Everything shown is
backed by the careeros stores: opportunities, evidence, fit engine,
application state machine, and the next-best-action engine.
"""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from careeros.application import (
    ApplicationState,
    ApplicationStore,
    DocumentStore,
    TRANSITIONS,
)
from careeros.evidence import EvidenceStore
from careeros.fit_engine import evaluate_fit
from careeros.ingestion import ManualPasteAdapter, StructuredImportAdapter, ingest
from careeros.next_action import next_actions_for_store
from careeros.opportunity import OpportunityStore
from llm.features.evidence_resume import (
    cover_letter_evidence_based,
    deterministic_keyword_alignment,
    tailor_evidence_based,
)

_ROOT = Path(__file__).resolve().parents[2]
# Testable: point CAREEROS_DB at a temp database in UI tests. Resolved per
# call (not at import) so tests can point successive runs at different DBs.


def _db_path() -> Path:
    return Path(os.getenv("CAREEROS_DB") or (_ROOT / "data" / "processed" / "career_intel.duckdb"))


_EVIDENCE_HELP = "Evidence lives in the Evidence Library page."


def _stores():
    p = _db_path()
    return {
        "opps": OpportunityStore(p),
        "evs": EvidenceStore(p),
        "apps": ApplicationStore(p),
        "docs": DocumentStore(p),
    }


def _has_llm_key() -> bool:
    import os

    return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY"))


@st.cache_resource
def _gateway():
    from llm.cache import ResponseCache
    from llm.config import LLMConfig
    from llm.gateway import Gateway

    return Gateway(
        LLMConfig.from_env(), cache=ResponseCache(_ROOT / "data" / "processed" / "llm_cache.duckdb")
    )


# ---------------------------------------------------------------------------
# Add-opportunity forms
# ---------------------------------------------------------------------------


def _render_add_forms(store) -> None:
    with st.expander("Add opportunity - paste a job ad"):
        pasted = st.text_area(
            "Paste the ad",
            height=160,
            key="opp_paste",
            placeholder="First line: Role Title at Company\nThen the job description...",
        )
        url = st.text_input("Source URL (optional)", key="opp_url")
        if st.button("Add from paste", key="opp_add_paste", type="primary"):
            if not pasted.strip():
                st.warning("Paste the job ad text first.")
            else:
                opp = ingest(store["opps"], ManualPasteAdapter(), pasted)
                if url.strip():
                    store["opps"].update_fields(opp.opportunity_id, source_url=url.strip())
                st.success(
                    f"Added: {opp.role_title or '(untitled)'}"
                    + (f" at {opp.company}" if opp.company else "")
                )
                st.session_state["selected_opp"] = opp.opportunity_id
                st.rerun()

    with st.expander("Add opportunity - structured JSON"):
        st.caption(
            'Fields mirror the opportunity model, e.g. {"role_title": "...", '
            '"company": "...", "description_raw": "...", "closing_date": "2026-12-01"}. '
            "Unknown fields stay unknown."
        )
        raw = st.text_area("JSON", height=120, key="opp_json")
        if st.button("Import JSON", key="opp_add_json"):
            try:
                opp = ingest(store["opps"], StructuredImportAdapter(), raw)
                st.success(f"Imported: {opp.role_title or '(untitled)'}")
                st.session_state["selected_opp"] = opp.opportunity_id
                st.rerun()
            except ValueError as e:
                st.error(f"Could not parse: {e}")


# ---------------------------------------------------------------------------
# Board
# ---------------------------------------------------------------------------


def _render_board(store) -> None:
    opps = store["opps"].list_all()
    if not opps:
        st.info("No opportunities yet - add one above (paste a job ad or import JSON).")
        return
    apps_by_opp = {a.opportunity_id: a for a in store["apps"].list_all()}
    actions = {
        n.opportunity_id: n
        for n in next_actions_for_store(store["apps"], store["opps"], store["evs"], store["docs"])
    }

    st.subheader("Active pipeline")
    rows = []
    for o in opps:
        app = apps_by_opp.get(o.opportunity_id)
        act = actions.get(o.opportunity_id)
        rows.append(
            {
                "ID": o.opportunity_id,
                "Role": o.role_title or "(untitled)",
                "Company": o.company or "-",
                "Status": app.current_state if app else "-",
                "Next action": act.action if act else "Start tracking",
                "Priority": act.priority_score if act else None,
                "Closes": str(o.closing_date) if o.closing_date else "-",
            }
        )
    st.dataframe(rows, hide_index=True, use_container_width=True)

    options = {
        f"#{o.opportunity_id} - {o.role_title or '(untitled)'}"
        + (f" at {o.company}" if o.company else ""): o.opportunity_id
        for o in opps
    }
    label = st.selectbox("Open workspace", list(options.keys()), key="opp_pick")
    if label:
        st.session_state["selected_opp"] = options[label]


# ---------------------------------------------------------------------------
# Workspace: Job & Fit
# ---------------------------------------------------------------------------


def _fit_for(store, opp):
    items = [e for e in store["evs"].list_all() if e.claims_allowed]
    return evaluate_fit(opp, items)


def _render_job_fit(store, opp) -> None:
    st.markdown("#### Job")
    left, right = st.columns(2)
    with left:
        st.markdown(f"**Role:** {opp.role_title or '*(unknown)*'}")
        st.markdown(f"**Company:** {opp.company or '*(unknown)*'}")
        st.markdown(
            f"**Location:** {opp.location or '*(unknown)*'}"
            + (f" ({opp.work_mode})" if opp.work_mode else "")
        )
        st.markdown(f"**Type:** {opp.employment_type or '*(unknown)*'}")
    with right:
        st.markdown(f"**Seniority:** {opp.seniority or '*(unknown)*'}")
        if opp.salary_min or opp.salary_max:
            cur = opp.currency or ""
            st.markdown(f"**Salary:** {cur} {opp.salary_min or '?'} - {opp.salary_max or '?'}")
        else:
            st.markdown("**Salary:** *(unknown)*")
        st.markdown(f"**Closes:** {opp.closing_date or '*(unknown)*'}")
        st.markdown(
            f"**Source:** {opp.source}" + (f" - [link]({opp.source_url})" if opp.source_url else "")
        )
    if opp.description_raw:
        with st.expander("Job description", expanded=False):
            st.markdown(opp.description_raw)

    st.divider()
    st.markdown("#### Evidence-based fit")
    fit = _fit_for(store, opp)
    c1, c2, c3 = st.columns(3)
    c1.metric("Fit", f"{fit.score} - {fit.band}")
    c2.metric("Hard-requirement coverage", f"{fit.coverage_hard * 100:.0f}%")
    c3.metric("Interview risk", fit.interview_risk)
    st.caption(
        f"Components - preferred overlap {fit.overlap_preferred:.2f}, "
        f"domain relevance {fit.domain_relevance:.2f}, "
        f"seniority fit {fit.seniority_fit:.2f}, "
        f"experience evidence {fit.experience_evidence:.2f}. "
        f"{fit.seniority_note}."
    )
    st.success(fit.recommendation)

    if fit.strengths:
        st.markdown("**Evidence-backed strengths** (every claim traces to evidence):")
        ev_by_id = {e.evidence_id: e for e in store["evs"].list_all()}
        for s in fit.strengths:
            titles = ", ".join(
                f"[E{i}] {ev_by_id[i].title}" if i in ev_by_id else f"[E{i}]"
                for i in s.evidence_ids
            )
            st.markdown(f"- **{s.skill}** - supported by {titles}")
    if fit.transferable:
        st.markdown("**Possibly transferable** (adjacent evidence, not proven):")
        for g in fit.transferable:
            st.markdown(f"- {g.skill} - adjacent experience: {g.transferable_from}")
    if fit.gaps:
        st.markdown("**Genuine gaps** (no evidence at all):")
        for g in fit.gaps:
            st.markdown(f"- {g.skill}")


# ---------------------------------------------------------------------------
# Workspace: Evidence Map
# ---------------------------------------------------------------------------


def _render_evidence_map(store, opp) -> None:
    fit = _fit_for(store, opp)
    all_ev = store["evs"].list_all()
    st.markdown(f"{_EVIDENCE_HELP} Showing how your evidence maps to this job.")
    if not all_ev:
        st.info(
            "No evidence yet - add some in the Evidence Library, then the fit "
            "and any tailored materials become evidence-backed."
        )
        return
    cited = {i for s in fit.strengths for i in s.evidence_ids}
    for ev in all_ev:
        chip = "used-for-this-job" if ev.evidence_id in cited else "available"
        icon = "green" if ev.claims_allowed else "orange"
        st.markdown(
            f"<span style='border:1px solid;padding:0 6px;border-radius:8px;"
            f"border-color:{'#0FA958' if icon == 'green' else '#D4A80D'};'>{chip}</span> "
            f"**[E{ev.evidence_id}] {ev.title}** - {ev.type}"
            + (f" @ {ev.organization}" if ev.organization else "")
            + (f" - *{ev.verification_status}*" if ev.verification_status else ""),
            unsafe_allow_html=True,
        )
    if fit.gaps or fit.transferable:
        st.markdown("**Missing requirements** - add evidence to close these before applying:")
        for g in fit.gaps:
            st.markdown(f"- {g.skill}")
        for g in fit.transferable:
            st.markdown(f"- {g.skill} (transferable from {g.transferable_from})")


# ---------------------------------------------------------------------------
# Workspace: Prepare Application (Resume Studio integration)
# ---------------------------------------------------------------------------


def _render_prepare(store, opp, app) -> None:
    st.markdown("#### Base resume")
    base_doc = store["docs"].latest(app.application_id, "base_resume")
    with st.expander("Save / update base resume", expanded=base_doc is None):
        base_text = st.text_area(
            "Paste your current resume text",
            height=180,
            key="base_resume_text",
            value=base_doc.content if base_doc else "",
        )
        if st.button("Save base resume", key="save_base"):
            if not base_text.strip():
                st.warning("Paste the resume text first.")
            else:
                doc = store["docs"].save(app.application_id, "base_resume", base_text.strip())
                st.success(f"Saved as version {doc.version}.")
                st.rerun()
    if base_doc:
        st.caption(f"Base resume: version {base_doc.version}, saved {base_doc.created_at}.")

    st.markdown("#### Tailored resume (evidence-constrained)")
    tailored = store["docs"].latest(app.application_id, "tailored_resume")
    if tailored:
        with st.expander(
            f"Latest tailored resume (v{tailored.version}) - "
            f"{len(tailored.evidence_used)} evidence items cited, "
            f"{len(tailored.excluded_claims)} claims excluded",
            expanded=True,
        ):
            st.markdown(tailored.content or "")
            if tailored.excluded_claims:
                st.caption(
                    "Excluded (unsupported by your evidence): "
                    + ", ".join(tailored.excluded_claims)
                )
        versions = store["docs"].list_versions(app.application_id, "tailored_resume")
        st.caption(f"Version history: {len(versions)} - earlier versions are preserved.")
    else:
        st.info("No tailored resume yet.")

    if st.button("Generate tailored resume", key="gen_tailored", type="primary"):
        if not base_doc:
            st.warning("Save a base resume first.")
        else:
            evidence = [e for e in store["evs"].list_all() if e.claims_allowed]
            with st.spinner("Tailoring against your evidence..."):
                if _has_llm_key():
                    result = tailor_evidence_based(base_doc.content, opp, evidence, _gateway())
                else:
                    result = deterministic_keyword_alignment(base_doc.content, opp, evidence)
            doc = store["docs"].save(
                app.application_id,
                "tailored_resume",
                result.markdown,
                job_keywords=result.keywords,
                evidence_used=result.evidence_used,
                excluded_claims=result.excluded_claims,
            )
            note = "" if result.model_used else " (deterministic report - no LLM key set)"
            st.success(f"Saved version {doc.version}{note}.")
            st.rerun()

    st.markdown("#### Cover letter (evidence-constrained)")
    letter = store["docs"].latest(app.application_id, "cover_letter")
    if letter:
        with st.expander(f"Latest cover letter (v{letter.version})", expanded=False):
            st.markdown(letter.content or "")
    if st.button("Generate cover letter", key="gen_cover"):
        if not base_doc:
            st.warning("Save a base resume first.")
        else:
            evidence = [e for e in store["evs"].list_all() if e.claims_allowed]
            with st.spinner("Drafting..."):
                if _has_llm_key():
                    result = cover_letter_evidence_based(
                        base_doc.content, opp, evidence, _gateway()
                    )
                else:
                    result = deterministic_keyword_alignment(base_doc.content, opp, evidence)
            doc = store["docs"].save(
                app.application_id,
                "cover_letter",
                result.markdown,
                job_keywords=result.keywords,
                evidence_used=result.evidence_used,
                excluded_claims=result.excluded_claims,
            )
            st.success(f"Saved version {doc.version}.")
            st.rerun()

    st.download_button(
        "Download latest tailored resume (Markdown)",
        data=(tailored.content if tailored else (base_doc.content if base_doc else "")) or "",
        file_name=f"tailored-{opp.opportunity_id}.md",
        disabled=tailored is None and base_doc is None,
        key="dl_tailored",
    )


# ---------------------------------------------------------------------------
# Workspace: Status & Log
# ---------------------------------------------------------------------------


def _render_status(store, opp, app) -> None:
    st.markdown(f"#### Application status: **{app.current_state}**")
    current = ApplicationState(app.current_state.upper())
    allowed = sorted(TRANSITIONS[current], key=lambda s: s.value)
    if not allowed:
        st.info("This application is closed (terminal state). History is preserved below.")
    else:
        cols = st.columns(min(len(allowed), 4))
        for i, nxt in enumerate(allowed):
            if cols[i % len(cols)].button(f"{nxt.value}", key=f"tr_{nxt.value}"):
                store["apps"].transition(
                    app.application_id,
                    nxt,
                    trigger="user:workspace-button",
                    provenance="opportunities workspace",
                )
                st.rerun()

    st.divider()
    st.markdown("#### Event log (append-only)")
    events = store["apps"].events(app.application_id)
    rows = [
        {
            "when": str(e.timestamp)[:19],
            "from": e.previous_state or "-",
            "to": e.new_state,
            "trigger": e.trigger,
            "notes": e.notes or "",
            "provenance": e.provenance or "",
        }
        for e in events
    ]
    st.dataframe(rows, hide_index=True, use_container_width=True)


# ---------------------------------------------------------------------------
# Page entry
# ---------------------------------------------------------------------------


def render(date_range: str = "Last 12 months") -> None:
    st.header("Opportunities")
    st.caption("Track real job opportunities from discovery through application")
    store = _stores()

    _render_add_forms(store)
    st.divider()

    _render_board(store)

    selected = st.session_state.get("selected_opp")
    if selected is None:
        return
    opp = store["opps"].get(selected)
    if opp is None:
        st.error(f"Opportunity {selected} not found.")
        return

    st.divider()
    st.subheader(
        f"Workspace - {opp.role_title or '(untitled)'}"
        + (f" at {opp.company}" if opp.company else "")
    )

    app = store["apps"].get_by_opportunity(opp.opportunity_id)
    if app is None:
        if st.button("Start tracking this opportunity", type="primary", key="start_tracking"):
            store["apps"].create_for_opportunity(
                opp.opportunity_id, trigger="user:workspace", provenance="opportunities workspace"
            )
            st.rerun()
        return

    # Next-best-action banner for this opportunity
    board = {
        n.opportunity_id: n
        for n in next_actions_for_store(store["apps"], store["opps"], store["evs"], store["docs"])
    }
    nba = board.get(opp.opportunity_id)
    if nba:
        due = f" - due {nba.due_date}" if nba.due_date else ""
        st.info(f"**Next action:** {nba.action}{due}\n\n{nba.rationale}")

    tab_fit, tab_ev, tab_prep, tab_status = st.tabs(
        ["Job & Fit", "Evidence Map", "Prepare Application", "Status & Log"]
    )
    with tab_fit:
        _render_job_fit(store, opp)
    with tab_ev:
        _render_evidence_map(store, opp)
    with tab_prep:
        _render_prepare(store, opp, app)
    with tab_status:
        _render_status(store, opp, app)
