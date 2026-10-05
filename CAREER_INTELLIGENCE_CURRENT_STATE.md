# CAREER_INTELLIGENCE_CURRENT_STATE.md — Functional Inventory (Post-Recovery)

**Assessed:** 2026-10-05, against commit `c1efacd` (branch `recovery/known-good-baseline`)
**Method:** full source read of every surface + live validation (`pytest` 100 passed, 9/9 AppTest page renders, HTTP 200 live startup, `ruff` clean).
**Data context:** `career_intel.duckdb` — 96,467 Job Bank postings (2025-08 → 2026-07-31), 474 occupations, 1,423 skills, Job Bank wages (2025), StatsCan JVWS (2026), Indeed trends (through 2026-08-28).

Legend: **WORKING** = renders, real data, error paths handled · **PARTIAL** = works but with material limitations · **STUB** = placeholder · **BROKEN** = fails · **UNKNOWN** = not verifiable in this environment.

---

## Surface-by-surface inventory

### 1. Ask the Data — **PARTIAL** (fully functional with an API key; degraded gracefully without)
- **Inputs:** free-text market question; example-question buttons
- **Data sources:** `career_intel.duckdb` via generated, SELECT-only DuckDB SQL
- **Outputs:** grounded prose answer (verified against query results), result table, auditable generated SQL expander
- **Model/provider deps:** LiteLLM gateway (`llm.gateway`), provider-agnostic (`LLM_PROVIDER=anthropic|openai`, tier models via env). Requires `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`; page shows an info notice and exits cleanly without one
- **Persistence:** response cache (`llm_cache.duckdb`), daily token usage (`llm_usage.json`)
- **Guardrails:** SELECT-only SQL validation (`llm.sql_guard`), numeric grounding check, session limit (10), daily token cap (200K)
- **Tests:** `tests/llm/test_ask.py`, `test_eval_ask.py`, `test_grounding.py`, `test_sql_guard.py` (live tests self-skip without keys)
- **Limitation:** no API key present in this environment → interactive answering not exercised here; everything up to the LLM call is verified by tests

### 2. Career Advisor — **PARTIAL** (same key-dependency profile as Ask)
- **Inputs:** natural-language career question via chat UI (with in-session history)
- **Data sources:** same DuckDB; plan → grounded-SQL fetches → composed advice → fact-check; declines out-of-scope questions
- **Outputs:** advice message + per-source SQL expanders (auditable provenance)
- **Model/provider deps:** LiteLLM gateway, same env keys
- **Persistence:** chat history in `st.session_state` only (not durable); token cache/usage shared with Ask
- **Guardrails:** session limit (12), shared daily cap, fact-check before display
- **Tests:** `tests/llm/test_advisor.py`, `test_faithfulness.py`

### 3. Skill Demand — **WORKING**
- **Inputs:** none (date filter from router is accepted but the underlying query is fixed-period)
- **Data sources:** `job_skills` (flashtext extraction vs Lightcast Open Skills taxonomy from job titles + NOC names)
- **Outputs:** top-20 skills table for latest month, top-10 emerging skills (MoM growth), monthly trend chart (Plotly)
- **Model/provider deps:** none
- **Persistence:** read-only DuckDB
- **Tests:** `test_skill_matcher.py`; rendered OK in AppTest
- **Known limitation (documented in-page):** title-based extraction under-counts body-text tools — occupational demand, not a skills census

### 4. Salary Ranges — **WORKING**
- **Inputs:** role lookup selectbox
- **Data sources:** `wages_job_bank` (annual→hourly normalized) joined to `vacancies_statscan` on NOC 2021
- **Outputs:** KPI row, per-role low/median/high/vacancies, top-15 wage-range chart
- **Model/provider deps:** none · **Persistence:** read-only DuckDB · **Tests:** `test_salary.py`

### 5. Role Fit — **PARTIAL**
- **Tab A — profile match:** paste profile → local fastembed (bge-small) + BM25 hybrid retrieval over ~320 occupation docs → ranked fits with wage/demand/matched skills. No API key needed.
- **Tab B — skill match:** multiselect skills → fit % gauge + top gap skills
- **Critical dependency:** `build_role_docs()` reads the optional `job_skills_llm` table — **absent from the shipped demo DB** (created only by `scripts/extract_skills_llm.py`, needs an API key). Until it is run, Tab A falls back: `src/llm/features/role_match.py` raises `CatalogException` → **this is the one currently failing test** (`test_role_match.py::test_build_role_docs_from_real_db`). Tab B is unaffected.
- **Tests:** `test_role_match.py` (1 of 2 failing on the missing table), page still renders in AppTest because index build is lazy (only on first profile paste)
- **Classification rationale:** WORKING for skill-match; PARTIAL because the flagship semantic-match path needs a one-time `extract_skills_llm.py` run to be truly usable

### 6. Resume Studio — **PARTIAL** (fit path works keyless; review/tailor/cover need an API key)
- **Inputs:** PDF/DOCX/TXT upload (markitdown token-free parsing) or pasted text (6,000-char cap)
- **Data sources:** uploaded resume + real demand/wage facts queried per target role (`_role_facts`)
- **Outputs:** Market fit & gaps (top occupations + missing skills, keyless), Review (LLM), Tailor to role (LLM → Markdown download), Cover letter (LLM → download)
- **Model/provider deps:** LiteLLM for Review/Tailor/Cover; local embeddings for fit
- **Persistence:** nothing stored — outputs are ephemeral downloads; no resume versioning
- **Guardrails:** anti-fabrication prompt constraints, token caps
- **Tests:** `test_resume.py`; AppTest render OK

### 7. Market Context — **WORKING**
- **Inputs:** none · **Data sources:** `indeed_trends` + `vacancies_statscan`
- **Outputs:** 4 charts — Toronto hiring momentum, AI share of postings (Canada), quarterly vacancies, posted wage growth YoY
- **Model/provider deps:** none · **Tests:** AppTest render OK; data confirmed present through 2026-08

### 8. Market Brief — **PARTIAL**
- **Inputs:** edition selectbox · **Data sources:** pre-generated markdown in `docs/briefs/`
- **Outputs:** rendered brief + Markdown download + lead-capture CTA
- **Current content:** exactly **one edition** (`2026-05.md`); generation requires `scripts/make_brief.py` + API key
- **Model/provider deps:** only at generation time (grounded narrative, every number verified)
- **Tests:** `test_brief.py`

### 9. Career Profile — **WORKING** *(new — added by the previous session, repaired + verified in this recovery)*
- **Inputs:** name, location, target role/location, salary min/max (Streamlit form)
- **Data sources/outputs:** persists to new DuckDB tables (`career_profile`, `user_skills`, `user_evidence`, `user_applications`) via `src/user_data.py` DAO; displays current profile as JSON
- **Model/provider deps:** none · **Persistence:** DuckDB (single-row profile, upsert semantics)
- **Tests:** AppTest render OK (9/9); no dedicated unit tests yet
- **Scope:** profile editing only — skills/evidence/applications have DAO functions but **no UI yet**

---

## Cross-cutting capabilities (actual, verified)

| Capability | State |
|---|---|
| Provider/model abstraction | **WORKING** — LiteLLM gateway, `LLM_PROVIDER` + per-tier model env overrides (`llm/config.py`), response cache, usage caps |
| Grounding / anti-fabrication | **WORKING** in Ask/Advisor/Brief (SQL validation + numeric verification); prompt-level only in Resume Studio |
| Auditability | **WORKING** for Ask/Advisor (generated SQL shown per answer) |
| Data pipeline (download → transform) | **RESTORED** — `transform.py` verbatim from upstream; raw CSVs not shipped in zip (downloads need re-run for refresh) |
| Persistence of user state | **PARTIAL** — 4 user tables + DAO exist; only Career Profile has UI; no history/versioning |
| Deployment | Dockerfile + `entrypoint.py` (Railway) — streams logs, optional background refresh; unverified here (no Docker in this environment) |
| Tests | 101 tests; 100 pass; 1 fails on missing optional `job_skills_llm` table |
| Lead capture | **WORKING** — webhook relay (`LEAD_WEBHOOK_URL`) + local CSV backup |
| Cosmetic mojibake | Minor: a few original-archive UI strings render `??` (e.g. "Stay in the loop" header, "Notify me" arrow, some page-tab emoji). Valid UTF-8, valid Python, display-only. |

## What does NOT exist yet (verified absent)

Application tracking UI, evidence library UI, opportunity/job ingestion beyond the government open-data pipeline, job-posting detail views, cover-letter persistence, interview prep, certifications tracking, gamification/XP, next-best-action engine, recruiter/company intelligence, multi-user support, durable memory beyond the DuckDB, calendar/email integrations, and any connector to job platforms.
