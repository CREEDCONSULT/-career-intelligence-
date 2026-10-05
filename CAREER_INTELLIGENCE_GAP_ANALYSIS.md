# CAREER_INTELLIGENCE_GAP_ANALYSIS.md — Supposed-to-Be vs. What-Exists

**Assessed:** 2026-10-05 against commit `c1efacd`.
**Intended-state reference:** the 10-document master specification produced in the prior planning phase (`C:\Users\daunt\Downloads\career_intelligence_master_spec\`, esp. `00_MASTER_SPECIFICATION.md`, `02_INFORMATION_MODEL.md`, `03_WORKFLOWS.md`, `06_GAMIFICATION_PROGRESSION.md`, `08_IMPLEMENTATION_ROADMAP.md`).
**Rule honored:** nothing is listed as existing unless verified in code or tests in this recovery.

---

## 1. Capability-by-capability assessment

### A. Market intelligence (supposed: foundational layer) — **LARGELY EXISTS**
- ✅ Skill demand, salary ranges, macro context, grounded Q&A, advisor, monthly brief — all real, tested, data-grounded (see CURRENT_STATE).
- ⚠️ Gaps: single market (Toronto; config-driven but untested elsewhere); data refresh is manual (downloaders → transform); no scheduled refresh outside the Railway entrypoint's optional background thread.

### B. Job discovery / opportunity ingestion (supposed: user-tracked opportunities, not just a market census) — **MOSTLY MISSING**
- What exists: a government open-data *market* pipeline (Job Bank postings as aggregate statistics). Postings are loaded and queryable, but there is **no notion of an "opportunity" the user acts on** — no posting detail view, no save/shortlist, no dedupe against user interest, no ingestion of postings from other boards.
- Missing per spec: opportunity records with lifecycle state, company/source metadata beyond NOC/NAICS codes, ingestion connectors, staleness handling, user-facing search/browse of individual postings.
- Foundation that helps: `job_postings` table and `pipeline.insights` already provide the query substrate; `user_applications` table (added in recovery) expects to reference `opportunity_id` — but nothing populates opportunities yet.

### C. Role matching / qualification & fit assessment — **PARTIAL**
- Exists: skill-match % + gap list (keyless), semantic profile→occupation match (needs one-time `extract_skills_llm.py` run for its corpus), resume→market fit in Resume Studio.
- Missing per spec: fit assessment against a *specific opportunity* (vs. an occupation), evidence-backed readiness scoring, requirement-by-requirement qualification checklists, confidence-weighted fit that separates "market-level" from "me-level" fit.

### D. Evidence & provenance (supposed: every AI claim traceable to evidence) — **PARTIAL / EARLY**
- Exists: answer-level provenance in Ask/Advisor/Brief (executed SQL shown; numbers verified against query results) — this is the strongest part of the codebase.
- Missing: user *evidence library* (accomplishments, metrics, artifacts with verification status). The `user_evidence` table + DAO exist but have **no UI, no schema for artifacts, no linkage from generated resume bullets back to evidence items**. Resume Studio's anti-fabrication is prompt-level, not evidence-enforced.

### E. Resume tailoring & cover letters — **PARTIAL**
- Exists: upload/parse, market-fit, LLM review/tailor/cover-letter with per-role grounded facts, Markdown downloads.
- Missing: no persistence of base resume or tailored variants, no versioning/diffing, no evidence-linked bullet generation, no per-opportunity tailoring (targets occupations from NOC mapping, not specific postings), no DOCX/PDF export.

### F. Application tracking (supposed: stateful pipeline per application) — **STUB-LEVEL**
- Exists: `user_applications` table + DAO (repaired in recovery), nothing else.
- Missing: application UI, status state machine (draft → prepared → submitted → interviewing → offer/rejected), history preservation (no event log; UPDATE-in-place only), materials snapshotting, deadlines/reminders, outcome analytics.

### G. Interview preparation, certifications, career narrative, recruiter/company intelligence, compensation comparison — **ABSENT**
- No code, tables, or UI for any of these. The spec describes all of them; none exist. (Interview prep = 0 files; certifications = 0; company intelligence = 0 beyond NAICS codes on postings.)

### H. Personal career profile / digital twin — **MINIMAL BUT REAL**
- Exists: single-row `career_profile` + form UI (name, location, target role/location, salary range), `user_skills`/`user_evidence` tables with DAOs.
- Missing: skills UI, evidence UI, goals beyond target-role text, work history, achievements, import-from-resume, multi-profile support.

### I. Gamification / progression (supposed: XP, skill progression, role-path readiness, missions, achievements, next-best-action) — **ABSENT**
- Zero implementation. The prior *planning* phase produced a 77K-word progression spec (`06_GAMIFICATION_PROGRESSION.md`); **no code exists**. The previous implementation session spent its entire budget on a corrupted PAGES-dict repair loop and never reached any of it. No XP ledger, no milestones, no missions, no achievements, no next-best-action engine.

### J. Workflow engine / deterministic-vs-LLM separation — **PARTIAL BY CONVENTION**
- Exists in the analytics layer: LLM only drafts; SQL execution + numeric verification are deterministic; SQL is SELECT-guarded; cost guards are deterministic.
- Missing: an explicit application/progression **state machine** (deterministic transitions, human approval gates for consequential actions). No workflow state exists to separate yet because application tracking is a stub.

### K. Memory / automation / integrations — **ABSENT**
- No durable memory beyond DuckDB tables; no scheduler beyond the entrypoint thread; no email/calendar/Drive/browser connectors in the codebase.

## 2. Vertical-slice scorecard (the recovery objective's own bar)

The stated first milestone was: *opportunity ingestion → role/company intelligence → qualification/fit → evidence matching → tailored materials → application record → next-best-action tracking*.

| Slice stage | State |
|---|---|
| Opportunity ingestion | ❌ (market census only) |
| Role/company intelligence | ⚠️ occupation-level only |
| Qualification/fit assessment | ⚠️ occupation-level only |
| Evidence matching | ❌ (tables only, no UI/logic) |
| Tailored material generation | ✅ (occupation-level, LLM, grounded facts) |
| Application record | ❌ (table only) |
| Next-best-action tracking | ❌ |

**Verdict: 1.5–2 of 7 stages genuinely exist.** The recovery restored a solid analytics/marketing foundation; the "career operating system" portion of the master spec is essentially greenfield.

## 3. Technical debt register (observed, not invented)

1. `user_applications.opportunity_id` has no FK target (job_postings lacks a PK and is rebuilt per transform) — documented in code; needs an `opportunities` table eventually.
2. `career_profile` single-row design with nullable id — fine for a demo, blocks multi-profile.
3. `src/user_data.py` hardcodes repo-relative DB path — works for editable install + local runs; breaks in a wheel install (acceptable: app ships with repo layout).
4. `user_data` UPDATE functions build SET clauses from dict keys without column whitelisting — internal-only today, but should be parameterized strictly before any user input reaches it.
5. Missing `job_skills_llm` in demo DB → 1 red test + degraded Role Fit profile-match until `extract_skills_llm.py` is run once with an API key.
6. Cosmetic mojibake (`??`) in a handful of original UI strings (lead form, tab labels).
7. `data/raw` empty in the zip — refresh requires re-running all downloaders.
8. Streamlit `AppTest` smoke asserts rendering only — no interaction-level tests (e.g., form submit → DB row).

## 4. What is NOT a gap (strengths to keep)

Grounded text-to-SQL with numeric verification, provider-agnostic LLM tiering, token/cost guardrails, per-answer SQL auditability, config-driven market definitions, a real 96K-posting dataset, 100 passing tests, and CI (lint + pytest) — these are genuinely strong and must be preserved, not rewritten.
