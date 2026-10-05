# CAREER_INTELLIGENCE_RECOVERY_REPORT.md

**Recovery session:** GLM-5.3, 2026-10-05
**Branch:** `recovery/known-good-baseline` (recovery point `60268fe` → repaired baseline `c1efacd`)
**Companion documents:** `RECOVERY_AUDIT.md` (forensics), `CAREER_INTELLIGENCE_CURRENT_STATE.md` (inventory), `CAREER_INTELLIGENCE_GAP_ANALYSIS.md` (gaps)

---

## 1. What the previous Nemo session actually changed

| File | Change | Verdict |
|---|---|---|
| `streamlit_app/app.py` | Rewritten many times via PowerShell `Set-Content` surgery; ended syntactically invalid (orphan `    career_profile,` at line 2, duplicated `)` at line 20, unterminated string at line 105, mangled nav labels, ANSI-mangled emoji, wrong `parents[2]` path bootstrap) | Corrupted — replaced in recovery |
| `scripts/transform.py` | 12,725 B ETL pipeline truncated to a 56-line `init_user_tables()` fragment | Destroyed — restored verbatim from upstream GitHub |
| `src/user_data.py` | **New**: DuckDB DAO for career profile / skills / evidence / applications | Valid work — **preserved**, 3 bugs fixed (path off-by-one, impossible FK, unused imports) |
| `streamlit_app/pages_impl/career_profile.py` | **New**: Career Profile form page | Valid work — **preserved**, 1 contract fix (`render(date_range=None)`) |
| `Nemotron Career Checkpoint.txt`, `streamlit_output.txt`, `app.py.backup` | Session artifacts | Preserved in `.recovery/pre_repair_backup_20261005/` and git history |

## 2. Root cause of the loop

1. **Display mojibake misread as file corruption.** PowerShell 5.1's non-UTF-8 console codepage rendered the repo's UTF-8 emoji as `dY'?`-style garbage. Proof it was display-only: untouched `tests/test_app_smoke.py` contains intact `💬 🧠 📈 💰 🎯 📄 📊 📰` (verified by codepoint dump).
2. **The "fix" tool corrupted what it touched.** `Set-Content` in PS 5.1 defaults to ANSI: rewrites permanently replaced emoji bytes with `?`/garbage and string surgery introduced real syntax errors.
3. **Never changed diagnosis after repeated identical failures** — 2-failure rule violated for hours; each iteration targeted symptoms visible in the same unreliable console view.
4. **False success signal.** `streamlit run` prints "You can now view your app" *before* compiling, so the banner appeared even while every run died with `SyntaxError`.
5. **Environment confusion.** Bare `python` resolves to the Hermes agent venv (no deps); `pip`/`streamlit` resolve to system Python 3.11. The project was also never `pip install -e .`'d, which caused the very first `ModuleNotFoundError: No module named 'pipeline'` that started the hacking.

## 3. Files repaired (this recovery)

1. `streamlit_app/app.py` — clean UTF-8 rewrite: canonical ASCII nav labels, correct `parents[1]` bootstrap (repo root + `src` on `sys.path`), duplicate/orphan lines removed, both broken caption strings fixed, `import streamlit` restored to top with `# noqa: E402`, Career Profile wired into router.
2. `scripts/transform.py` — restored **verbatim** from `raw.githubusercontent.com/CREEDCONSULT/-career-intelligence-/main/scripts/transform.py`.
3. `streamlit_app/pages_impl/career_profile.py` — `render()` now satisfies the router contract.
4. `tests/test_app_smoke.py` — PAGES list aligned to canonical labels + Career Profile added.
5. `src/user_data.py` — `ROOT` path off-by-one fixed (`parents[2]`→`parents[1]`); impossible `user_applications` FK dropped (with explanatory comment); unused imports removed.
6. Environment — `pip install -e .` (mirrors Dockerfile/CI).

## 4. Validation results (evidence, not claims)

| Check | Result |
|---|---|
| `py_compile` on all repaired files + full-tree `compileall` | **OK** |
| `ruff check src scripts streamlit_app` (CI lint gate) | **All checks passed** |
| `pytest -q` | **100 passed, 1 failed** — sole failure is pre-existing upstream data gap (`test_role_match` needs the optional `job_skills_llm` table; shipped demo DB lacks it; created only by `scripts/extract_skills_llm.py`) |
| `tests/test_app_smoke.py` (Streamlit AppTest) | **9/9 pages render without exception** against the live 96K-posting DuckDB |
| Live startup (`streamlit run` on :8623, log-captured) | **HTTP 200, 7,260-byte page, zero exceptions in logs, clean shutdown** |
| `user_data.init_user_tables()` against real DB | **OK — all 4 user tables created** |

## 5. Current working surfaces

**WORKING:** Skill Demand, Salary Ranges, Market Context, Career Profile (new), plus the provider-agnostic LLM gateway/cache/guards, data pipeline (restored), lead capture, CI.
**PARTIAL:** Ask the Data and Career Advisor (fully built + tested; need an API key to interact — none in this environment), Resume Studio (fit path keyless; review/tailor/cover need key; nothing persisted), Role Fit (skill-match works; profile-match blocked until one-time `extract_skills_llm.py` run), Market Brief (one edition exists: 2026-05).

## 6. Broken / partial surfaces

None broken at baseline. Partials listed above. The 1 red test is a shipped-data gap, not code damage.

## 7. Architecture assessment

Solid analytics core worth keeping: Streamlit router + `pages_impl` page contract, `pipeline`/`llm` packages under `src/` installed via `pip install -e .`, grounded text-to-SQL with SELECT-guard + numeric verification, LiteLLM 3-tier provider abstraction, token/cost guardrails, config-driven market (Toronto default), DuckDB single-file storage, real open-data pipeline, 101-test suite + CI. The "Career OS" layer from the master spec (opportunities, evidence-enforced generation, application state machine, progression) is **greenfield** — see GAP_ANALYSIS. Vertical-slice score: **1.5–2 of 7 stages exist**.

## 8. Integrations currently present

- **LLM providers:** LiteLLM (Anthropic default, OpenAI alt, env-swappable per tier).
- **Open-data sources:** Job Bank (postings, wages), StatsCan JVWS, Indeed Hiring Lab — via CKAN/API downloaders.
- **Lead capture:** `LEAD_WEBHOOK_URL` relay (e.g. Google Apps Script → Sheet) + local CSV fallback.
- **Deployment:** Dockerfile/Railway `entrypoint.py` (Streamlit + optional background refresh).
- **Creed runtime (this session only):** git checkpointing under the Creed agent identity; nothing app-level.

## 9. Missing integrations (recommended to build via Creed systems, not in-app duplicates)

Per the integration-boundary decision: **do not** build a second memory, orchestration, or execution system inside Career Intelligence.
- **Creed Intelligence** → durable memory/context (user profile evolution, application history narratives) instead of growing ad-hoc DuckDB blobs.
- **Hermes** → orchestration of scheduled pipelines (downloaders → transform → briefs) and multi-step workflows; keep app logic thin.
- **Creed Agent Runtime** → execution, checkpoints, process management (this recovery already models the pattern).
- **Gmail API** (authorized) → application correspondence, follow-ups.
- **Google Calendar** → interview/deadline events from application state.
- **Google Drive** → resume/document storage with versioning (replaces ephemeral downloads).
- **Browser tooling** → job-platform workflows where policy-compliant; postings ingestion connectors should feed an `opportunities` table, not bypass the DB.
- **Future MCP surface** — expose `user_data` DAO + insights as MCP tools so any Creed agent can operate the career state machine.

## 10. Technical debt

See GAP_ANALYSIS §3 (8 items): no-PK `job_postings` vs `opportunity_id`, single-row profile, hardcoded DB path, non-whitelisted UPDATE column names, missing `job_skills_llm`, cosmetic mojibake strings, empty `data/raw` in zip, render-only smoke tests.

## 11. Recommended next milestone

**M1 — Evidence-grounded Opportunity → Application vertical slice** (the original objective, now on stable ground):
`opportunities` table + posting-detail/shortlist UI → evidence library UI (cruds `user_evidence`, links claims→artifacts) → per-opportunity qualification checklist (deterministic) + evidence-matched fit (LLM, provenance-kept) → Resume Studio gains per-opportunity tailoring with evidence-linked bullets → application record with event-log state machine (no in-place overwrites) → next-best-action derived from state. Gamification hooks attach **after** the state machine exists (events → XP), per the approved progression spec.

## 12. Exact top 10 tasks (dependency order)

1. Add `opportunities` table + DAO; backfill command from `job_postings`; posting-detail + shortlist UI in a new Opportunities surface.
2. Evidence library UI: CRUD over `user_evidence` with verification status, artifact paths, skill links; extend `user_skills` UI to manage the skill inventory.
3. Wire evidence into Resume Studio: tailor/cover-letter prompts receive selected evidence; output bullets carry evidence IDs; add persistence for generated materials keyed to opportunity.
4. Application state machine: `application_events` append-only table + deterministic transitions (`draft→prepared→submitted→screening→interviewing→offer|rejected|withdrawn`), human-approval gate before any "submitted" state.
5. Per-opportunity qualification checklist: deterministic requirement extraction vs. user skills/evidence, with explicit missing-evidence items.
6. Next-best-action engine: pure function over application + evidence + profile state (deterministic first; LLM explanation optional).
7. Run `scripts/extract_skills_llm.py` once with an API key to populate `job_skills_llm` (fixes the red test + unlocks Role Fit profile-match).
8. Interaction-level tests: AppTest form submits (profile save → DB row; shortlist add; application transition), and unit tests for the state machine + next-best-action.
9. Gamification foundation (only after 4–6): XP ledger sourced **only** from state-machine events + evidence verification — no click-counting; missions/achievements per the progression spec's evidence-gated rules.
10. Creed integrations behind interfaces: memory sync (Creed Intelligence), pipeline scheduling (Hermes), Drive/Gmail/Calendar adapters — each optional, app must run without them.

## 13. Status

# **RECOVERED**

- App compiles, lints (CI gate), starts (HTTP 200), and all 9 navigation surfaces render against real data.
- Test suite: 100/101 passing; the single failure is a pre-existing upstream data gap, documented, with a one-command remediation path (task 7).
- All prior corruption is preserved for forensics (`.recovery/` + git history); all valid prior work (user_data, Career Profile) is preserved and now actually working for the first time.
- The recovery branch should be merged to `main` (recommended) — see final session action.
