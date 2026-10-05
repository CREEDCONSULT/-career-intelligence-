# CAREER_INTELLIGENCE_M1_REPORT.md — M1 Vertical Slice Report

**Phase:** M1 — Opportunity → Evidence → Application State Machine → Next-Best-Action
**Branch:** `m1/opportunity-evidence-application` (from `main @ 7e53eee`)
**Commits:** `6ee2f39` (baseline) → `add280c` (careeros core + tests) → `9af132d` (workspace UI) → `29b367e` (migration fix)
**Scope discipline:** one vertical slice; no M2 work; no scraping; no duplicate infrastructure.

---

## 1. Baseline state (verified before any change)

Recorded in `docs/M1_BASELINE.md`: HEAD `7e53eee` on `main`, clean tree, ruff clean, 100 passed + the single known shipped-data-gap failure (`test_role_match` needs the optional `job_skills_llm` table), live startup HTTP 200, 9/9 pages rendered. Interpreter hazard confirmed and handled throughout (bare `python` on PATH resolves to the Hermes venv; every command used `C:\Users\daunt\AppData\Local\Programs\Python\Python311\python.exe`).

## 2. Architecture changes

- **New package `src/careeros/`** — the deterministic career-OS layer, kept strictly separate from LLM judgment (which stays in `llm/features`):
  - `opportunity.py` — canonical model + "unknown stays unknown" normalizer + store
  - `evidence.py` — evidence ledger + store + derived skill support
  - `fit_engine.py` — deterministic, banded, evidence-cited fit evaluation
  - `application.py` — explicit state machine, append-only event log, versioned document store
  - `next_action.py` — deterministic one-action-per-application engine + ranking
  - `ingestion.py` — adapter boundary (manual paste + structured JSON in M1)
  - `integrations.py` — Creed-system boundary protocols (Gmail/Calendar/Drive) with safe null adapters
- **`llm/features/evidence_resume.py`** — evidence-constrained tailor/cover-letter generation with a validated evidence-citation footer, plus a deterministic no-key fallback (keyword-alignment report; never fake tailoring).
- **`user_data.py` narrowed to profile-only**; the pre-M1 sketch tables (`user_skills`, `user_evidence`, `user_applications`) were superseded and migrated away (FK-aware, zero-row-only drops, verified against the real DB).
- **UI:** two new router surfaces (`Opportunities`, `Evidence Library`); 11 pages total. No redesign — existing surfaces untouched except wiring.

## 3. Opportunity model

All M1-mandated fields implemented (`opportunity_id` → `provenance`), stored in DuckDB. Deterministic parsing fills only what the source text supports: work mode, employment type, seniority (title → body → years-of-experience bands), salary ranges with stated currency, closing dates ("Apply by …", "Applications due …"). Anything unstated stays `None` — asserted by tests (`test_unknown_fields_stay_unknown`, `test_ingest_never_fabricates_from_gibberish`).

## 4. Evidence model

Eight evidence types (employment, project, skill, technology, outcome, certification, education, portfolio) with organization, dates, description, structured metrics, explicit skills, verification status (`self_reported`/`documented`/`verified`), artifact references, a `claims_allowed` gate, notes, and provenance. Supported skills combine explicit claims with the same whole-token 33K-skill matcher the market pipeline uses — so a project description mentioning Docker counts as Docker evidence, traced to that item. `claims_allowed=False` items are excluded from every claims path.

## 5. Fit engine

Deterministic five-component evaluation (hard-requirement coverage 0.45, preferred overlap 0.15, domain relevance 0.15, seniority fit 0.15, experience evidence 0.10) reported as a **band** (Strong/Good/Fair/Weak) with full component breakdown — no false precision. Outputs evidence-backed strengths (each matched requirement lists its supporting evidence IDs), genuine gaps, hedged "possibly transferable" adjacencies (same taxonomy category, never asserted as matches), interview risk, closing urgency, and a recommendation. Unknowns score neutrally. Non-taxonomy requirements (e.g. "Canadian work permit") are satisfied only by literal evidence mentions — still traceable.

## 6. Application state machine

13 explicit states (DISCOVERED → REVIEWED → SHORTLISTED → PREPARING → READY_TO_APPLY → APPLIED → SCREENING → INTERVIEW → ASSESSMENT → OFFER, terminal REJECTED/WITHDRAWN/CLOSED) with a hard transition table — anything else raises `InvalidTransition`. Every transition appends an immutable event row (timestamp, previous state, new state, trigger, notes, artifacts, provenance); `applications.current_state` is a materialized view of the latest event. History is never overwritten (asserted by tests). OFFER resolves via CLOSED (accepted) or WITHDRAWN (declined).

## 7. Resume Studio integration

The workspace's **Prepare Application** tab connects the selected opportunity to the evidence model: save a base resume → generate an evidence-constrained tailored resume / cover letter. Every generated document version records: content, job keywords, `evidence_used` (validated against the real ledger — bogus model citations are dropped and noted), `excluded_claims` (job keywords with no support — the honest "unsupported claims rejected" ledger), version, created_at. Anti-fabrication is enforced in the prompt **and** deterministically audited at the ID level. Without an API key the deterministic fallback produces a keyword-alignment report instead of fabricated prose. Versions are append-only in `application_documents`.

## 8. Next-best-action engine

Exactly one action per active application from a visible per-state rule table (review → run fit → shortlist → prep, evidence-gap-first when required skills lack evidence → finalize → submit (URGENT ≤3 days to close) → await/follow-up after 7 days → screening/interview/assessment prep → offer decision). Ranking = state weight × fit-band weight × closing urgency, tie-broken by due date. The store-level engine reads the APPLIED timestamp from the event log, not the row. Terminal applications drop off the board.

## 9. Ingestion boundary

`IngestionAdapter` interface + two M1 adapters: `ManualPasteAdapter` (line-1 "Role at Company" convention, rest kept raw) and `StructuredImportAdapter` (JSON dict/fixture; unknown keys ignored, missing stays unknown). `ingest()` dedupes on (source, external_job_id). Future sources (LinkedIn, Indeed, career pages, Gmail opportunity messages) arrive as adapters behind this interface — **no scraping or automation was implemented in M1**, per the boundary.

## 10. Creed system boundaries

Career-domain state lives only in Career Intelligence (`careeros` + DuckDB). Memory/orchestration/execution remain with Creed Intelligence / Hermes / Creed Agent Runtime. `integrations.py` ships runtime-checkable protocols (`EmailAdapter`, `CalendarAdapter`, `DriveAdapter`) with no-op `Null*` adapters — the app runs to completion with zero credentials, and real Gmail/Calendar/Drive integrations later implement the same interfaces without call-site changes. Nothing in M1 required them.

## 11. Tests

**132 new tests in `tests/careeros/`** — opportunity creation/unknown-fields/normalization/dedupe/provenance; evidence CRUD, type/status validation, claims gate, fixture import; fit engine (coverage, gaps, transferables, seniority, raw-requirement fallback, determinism, urgency bands); state machine (full path, 8 invalid transitions, frozen terminals, append-only log, one-app-per-opportunity); NBA (per-state actions, urgency, follow-up jump, ranking, terminal exclusion); evidence-resume (footer parsing, bogus-citation rejection, fake-gateway tailor/cover-letter, honest fallback, supported/excluded disjointness); ingestion (separators, no-fabrication, JSON shapes); plus a 3-test AppTest UI suite that renders the board, asserts the fit panel + NBA banner, and clicks a real transition button end-to-end.

**Full suite: 234 passed, 1 failed** — the failure is the pre-existing shipped-data gap (`test_build_role_docs_from_real_db`, needs the optional `job_skills_llm` table), explicitly unrelated to M1 and unchanged from the accepted baseline. The original 9-page smoke now covers 11 surfaces. `ruff check src scripts streamlit_app tests/careeros`: all checks passed.

### Smoke evidence

- Live `streamlit run`: **HTTP 200** (ports 8625/8626 during validation).
- AppTest UI: board renders seeded opportunity + fit band metric; NBA banner shows "Review the job description" for a fresh DISCOVERED application; clicking the **REVIEWED** button produces state DISCOVERED → REVIEWED with a 2-event log (`trigger=user:workspace-button`, `provenance=opportunities workspace`); Evidence Library lists the seeded `[E1]` item.
- DB migration verified against the real database: superseded `user_skills`/`user_evidence`/`user_applications` dropped (FK child-first), `opportunities`/`evidence_items` present and empty, pipeline tables untouched.

## 12. Remaining partial pages (unchanged from CURRENT_STATE, re-confirmed)

Ask the Data / Career Advisor (functional; need an LLM API key to interact — none in this environment), Resume Studio occupation-level studio (superseded for per-opportunity work by the workspace; both coexist), Role Fit (profile-match blocked by the same missing `job_skills_llm` corpus as the red test), Market Brief (one edition).

## 13. Technical debt

1. `job_skills_llm` still absent from the demo DB → 1 red test + degraded Role Fit profile-match (one `scripts/extract_skills_llm.py` run with an API key fixes both).
2. LLM generation paths (evidence-cited tailor/cover letter) are unit-tested with a fake gateway; a live-provider run is pending an API key. Deterministic fallback is fully wired and tested.
3. Salary parsing's "small numbers mean thousands" heuristic doesn't distinguish hourly from annual ranges when units are unstated.
4. Citation validation is ID-level; content-level semantic verification of model prose is M2.
5. Transferable detection is loose category-adjacency (hedged in UI copy, but coarse).
6. UI tests cover render + one click; full form-submit flows (add-opportunity via paste, evidence form save) are tested at store level, not yet through AppTest.
7. Pre-existing lint nits in `tests/llm/` (2 items; outside CI's lint scope).
8. `use_container_width` deprecation warnings across the pre-existing UI (Streamlit will remove after 2025-12-31).
9. No scheduler: data refresh, follow-up nudges, and board recomputation need Hermes orchestration (deliberately out of M1).

## 14. External integrations — present vs missing

**Present (interfaces only, by design):** Gmail/Calendar/Drive protocols + null adapters; ingestion adapter boundary for future job sources. **Missing:** real Gmail (application correspondence), Google Calendar (interview/deadline events), Google Drive (document storage), LinkedIn/Indeed/company-page connectors, Creed Intelligence memory sync, Hermes-scheduled jobs. None block M1; all have designated seams.

## 15. Top 10 next actions (M2 candidates — NOT begun)

1. Run `scripts/extract_skills_llm.py` once with an API key → clears the red test and unlocks Role Fit profile-match.
2. Live-provider validation of the evidence-cited tailor/cover-letter output quality (with the ID-validation already in place).
3. One-click "track this posting" from the existing `job_postings` table → opportunity backfill adapter.
4. Interview-prep generator from fit strengths/gaps + evidence (cited talking points, gap answers).
5. Application-question bank per opportunity with evidence-linked answers.
6. Follow-up email drafts via `EmailAdapter` (Gmail when authorized; drafts stored as application artifacts).
7. Deadline/interview events via `CalendarAdapter` when authorized.
8. DOCX/PDF export + `DriveAdapter` upload for tailored materials.
9. Hermes-scheduled daily job: refresh data, recompute board, surface due follow-ups.
10. Gamification foundation fed strictly by state-machine events (per the approved progression spec — evidence-gated only, no click-counting).

## 16. Recommendation

# M1 COMPLETE WITH CONDITIONS

The vertical slice is complete and verified end-to-end: a user can add a real opportunity (paste or JSON), maintain an evidence ledger, see an evidence-cited banded fit with genuine gaps and honest transferables, prepare application materials whose every citable claim traces to evidence (with unsupported claims excluded and recorded), walk an explicit state machine with an immutable history, and always see exactly one prioritized next action. All 234 passing tests, lint, live startup, and UI-interaction evidence back this.

**Conditions:**
1. The single pre-existing shipped-data-gap test remains red (documented, unrelated to M1, one-command fix listed above).
2. The LLM-constrained generation paths ran under a fake gateway in tests; a live-provider quality pass is the first recommended validation once an API key is available (the keyless deterministic path is complete and tested).
