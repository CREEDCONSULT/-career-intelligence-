# CAREER_INTELLIGENCE_M2_REPORT.md — Live Operations + Application Intelligence

**Phase:** M2 — Live Career Operations + Application Intelligence
**Branch:** `m2/live-operations` (from `main @ 6f54ade`)
**Commits:** `cf0c5a1` (1A fixture path) → `5ea32f7` (1B live-model harness) → `8808de8` (M2 core) → `7cc209d` (M2 tests)
**Validation:** 301 passed / 1 known data-gap failure / 3 live-skip (no API key) / ruff clean / HTTP 200 live

---

## 1. M1 Conditions Status

| Condition | Status | Resolution |
|---|---|---|
| **A: job_skills_llm shipped-data gap** | **RESOLVED (CI fixture path)** | `scripts/extract_skills_llm.py --fixture` performs deterministic dictionary extraction (no LLM, provenance-recorded in `job_skills_llm_meta`). CI workflow runs it before tests → CI is green. Local demo DB intentionally contains NO fixture data (condition preserved honestly — one live run with an API key clears it permanently). Live path now refuses to run without a key (clear error → `--fixture`). |
| **B: Live-model validation** | **HARNESS BUILT, PENDING_KEY** | `scripts/validate_live_model.py` + auto-activating pytest cases (`test_live_model.py`) ready. No API key available in this environment → documented condition, not faked. **Required founder action:** set `ANTHROPIC_API_KEY` (or `LLM_PROVIDER=openai` + `OPENAI_API_KEY`) and run the script. Status: `PENDING_KEY`. |

## 2. Live Provider Status

Provider-agnostic LiteLLM gateway (unchanged from M1). Default: Anthropic (haiku-4-5 / sonnet-5 / opus-4-8 per tier). Switchable to OpenAI via `LLM_PROVIDER=openai`. The validation harness validates the full evidence-citation contract (cited IDs exist in ledger, excluded claims never woven in, evidence/excluded sets disjoint) + compares live output vs deterministic fallback.

## 3. Real Ingestion Status

| Source | Status | Implementation |
|---|---|---|
| Manual paste | **WORKING** (M1) | `ManualPasteAdapter` |
| Structured JSON | **WORKING** (M1) | `StructuredImportAdapter` |
| Job URL metadata/reference | **WORKING** (M1) | `source_url` field on every opportunity |
| **Job Bank open data** | **NEW, WORKING** | `JobBankImportAdapter` — converts postings from the existing `job_postings` table (government open data already in the system, policy-compliant, no scraping, no new credentials) into tracked opportunities with stable `jobbank:<id>` external IDs |
| LinkedIn / Indeed / Upwork / career pages / Gmail | **NOT IMPLEMENTED** (adapter boundary ready, no scraping per M2 rules) |

All sources normalize into the canonical Opportunity model. Duplicate detection: `ingest()` dedupes on `(source, external_job_id)`.

## 4. Opportunity Pipeline

Pipeline views (mapped onto the explicit state machine, no redesign):
`New | Review | Shortlisted | Preparing | Applied | Interview | Closed` + `All`.

Deterministic role-family taxonomy (13 families: ai/ml, finance, product, design, hr, healthcare, skilled trades, data, engineering, marketing, sales, consulting, operations). Family assignment is a display/analytics aid, never a job claim. Sort keys provided for closing date, company, and role family.

## 5. Gmail / Calendar / Drive Integration Status

| Integration | Status | Notes |
|---|---|---|
| Gmail | **BOUNDARY + FIXTURES** | `CommunicationStore` fully functional (messages, deterministic signal detection for interview/assessment/rejection/offer/recruiter, opportunity association, provenance). Gmail import arrives via fixture JSON or manual entry; no credential required. **Required authorization for live Gmail:** Google OAuth2 with `gmail.readonly` scope. No email is ever auto-sent. |
| Calendar | **BOUNDARY** | `CalendarAdapter` protocol + null adapter (M1). Interviews track date/time/location/participants natively; a real calendar adapter implements the same interface later. **Required authorization:** Google OAuth2 with `calendar` scope. |
| Drive | **BOUNDARY** | `DriveAdapter` protocol + null adapter (M1). **Required authorization:** Google OAuth2 with `drive.file` scope. |

## 6. Interview Workflow

**First-class interview records** within the existing state machine (SCREENING/INTERVIEW/ASSESSMENT/OFFER states unchanged):
- 6 stages: `recruiter_screen`, `hiring_manager`, `technical_case`, `assessment`, `panel_final`, `offer_discussion`
- Tracks: scheduled_at, duration, location/meeting link, participants, prep status (not_started → in_progress → ready), notes, artifacts, follow-up date, provenance
- NBA is interview-aware: a scheduled interview overrides the generic action with a stage-specific one ("Prepare for the technical case interview (Mon Oct 08)"); past interviews ask to record the outcome
- **Interview prep pack** (`llm/features/interview_prep.py`): evidence-grounded pack with company/role summary (from the record only — no invented company facts), competency themes by stage, STAR stories cited by evidence ID, technical refreshers, questions to expect + to ask, honest gaps/risks from the fit engine, salary/negotiation context from the posted range only. Deterministic base (no key needed) + optional LLM polish with validated citations.

## 7. Application-Question Workflow

7-question bank with **hard factual/narrative separation**:

| Question | Kind | Rules |
|---|---|---|
| Why this company? | narrative | Evidence-cited generation |
| Why this role? | narrative | Evidence-cited generation |
| Relevant experience | narrative | Evidence-cited generation |
| Salary expectations | factual | User-confirmed text only |
| Earliest start date | factual | User-confirmed text only |
| **Work authorization** | factual | **NEVER inferred** — user-confirmed text only; narrative generation raises ValueError |
| Location/hybrid preferences | factual | User-confirmed text only |

Narrative answers (deterministic scaffold without key; LLM draft with one) record `evidence_used` + `excluded_claims` identically to resume tailoring. Per-question status: draft → approved (user action).

## 8. Outcome Learning

`ApplicationOutcome` derived from the append-only event log at terminal states (never hand-typed, never contradicts history):
- outcome_type (no_response | rejected | withdrawn | offer | closed)
- first_response_days + days_to_outcome measured from event-log timestamps
- fit_band, resume_version, cover_letter_version, source, role_family

**Analytics** (computed on demand, never precomputed): response rate, interview rate, offer rate by source / fit band / resume version / role family + days-to-first-response stats.

**Low-sample honesty:** any bucket with n < 5 reports `rate=None` + `"insufficient sample (n=X)"` — never a misleading percentage.

## 9. Career Profile Feedback Loop

`propose_profile_updates()` generates PROPOSALS ONLY (never auto-applies):
- **skill_gap**: skills missing/transferable across ≥2 tracked opportunities (cited with the count)
- **requested_skill**: skills both requested AND evidence-backed (headline candidates)
- **winning_evidence**: evidence items cited in ≥2 fit analyses (keep prominent)
- **role_family_fit**: families where ≥50% of tracked opportunities rate Good/Strong
- **certification_opportunity**: credential-shaped recurring gaps

Every suggestion carries its data note (counts, specific items). Applying is always an explicit user action.

## 10. Creed Integration

Boundary maintained exactly as specified:
- **Career Intelligence owns:** opportunities, application state, career evidence, application artifacts, interview state, career outcomes (all in `src/careeros/` + DuckDB)
- **Creed Intelligence owns:** durable memory — `NullCreedStore` boundary shipped (future /store adapter, no coupling to the unstable contract)
- **Hermes owns:** orchestration/scheduling (not needed for M2 — no cron jobs; future refresh jobs go there)
- **Creed Agent Runtime owns:** execution/checkpointing (used throughout this session)

## 11. Test Results

| Suite | Count | Status |
|---|---|---|
| careeros (M1 core + M2) | 202 collected | **199 passed, 3 skipped** (live-model tests auto-skip without a key) |
| Full suite (incl. market/LLM/eval) | 302 | **301 passed, 1 failed** (the known shipped-data gap, unchanged, CI-green via fixture) |
| Lint (`ruff check src scripts streamlit_app`) | — | **All checks passed** |
| Live startup | — | **HTTP 200** |

New M2 tests cover: real-source adapter normalization, duplicate ingestion, communication-to-opportunity association, interview scheduling/transitions, factual gating (work authorization never inferred), unsupported-claim rejection in narrative generation, live-model schema validation (fake gateway), outcome metrics, low-sample labeling, NBA interview-aware updates, profile feedback proposals.

## 12. Remaining Blockers

1. **No LLM API key** — live-model validation + LLM-polish paths are harness-ready but unexercised. Deterministic fallbacks fully functional.
2. **No Gmail/Calendar/Drive credentials** — adapter boundaries + fixtures fully implemented; real integrations require Google OAuth2 authorization.
3. **No production job_skills_llm data** — CI fixture clears the test; production population requires one live run of `extract_skills_llm.py` (with key, no `--fixture`).
4. **Salary hourly/annual ambiguity** — the shared normalizer's thousands heuristic ($45-$60 → 45000-60000) doesn't distinguish hourly from annual when units are unstated. Documented + tested, not yet fixed.

## 13. Required Founder Actions

1. Set `ANTHROPIC_API_KEY` (or `LLM_PROVIDER=openai` + `OPENAI_API_KEY`) → run `python scripts/validate_live_model.py` → clears the live-model condition.
2. Run `python scripts/extract_skills_llm.py` (without `--fixture`) → populates production `job_skills_llm` → clears the data-gap condition permanently.
3. Authorize Gmail (OAuth2, `gmail.readonly`) if you want live email thread import.
4. Authorize Calendar (OAuth2, `calendar`) if you want interview events created automatically.
5. Authorize Drive (OAuth2, `drive.file`) if you want generated documents persisted to Drive.

## 14. Ranked M3 Recommendations (NOT begun)

1. **Live-provider quality pass** — once a key is set, exercise the full tailoring/cover-letter/prep/question generation chain against a real model and tune prompts for quality (contract enforcement is already in place).
2. **Gmail thread import** — implement the real Gmail adapter behind the existing `EmailAdapter` protocol; wire `CommunicationStore.import_fixture` to a live `messages.list` call with the same signal detection.
3. **One-click Job Bank browse** — UI to search/filter `job_postings` and promote any posting to a tracked opportunity via the existing `JobBankImportAdapter`.
4. **Interview calendar sync** — implement the real `CalendarAdapter`; create events when interviews are scheduled through the workspace.
5. **Drive document persistence** — implement the real `DriveAdapter`; upload generated documents as versioned files.
6. **Outcome auto-snapshot** — Hermes-scheduled job that walks APPLIED applications past the 21-day no-response threshold and proposes explicit no_response closures.
7. **Compensation comparison** — join posted ranges with the wages_job_bank market data to show offer vs. market median per NOC (salary context in prep packs already shows the posted range honestly).
8. **Content-level claim verification** — beyond ID-level validation, verify that LLM-generated prose doesn't introduce unsupported assertions (semantic check, not just citation matching).
9. **Multi-market support** — the pipeline is already config-driven (`config/market.yaml`); exercise it for a second market.
10. **Gamification foundation** — XP ledger sourced strictly from state-machine events (per the approved progression spec, evidence-gated only).

## 15. Status

# **M2 COMPLETE WITH CONDITIONS**

The operational layer is complete: real policy-compliant ingestion (Job Bank open data), first-class interview progression with evidence-grounded prep packs, factual/narrative question separation with work-authorization never inferred, event-log-derived outcome learning with honest low-sample analytics, and a proposal-only profile feedback loop — all tested (199 passing) and live-verified (HTTP 200).

**Conditions:**
1. Live-model validation is harness-ready but `PENDING_KEY` (no credentials in this environment; one command clears it).
2. Production `job_skills_llm` still requires one live run (CI fixture clears the test but is honestly labeled as non-production data).
3. Gmail/Calendar/Drive real integrations require Google OAuth2 authorization (boundaries and fixtures are fully implemented).
