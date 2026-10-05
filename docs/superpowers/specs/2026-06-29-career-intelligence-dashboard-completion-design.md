# Career Intelligence Dashboard — Completion Design

**Date:** 2026-06-29
**Author:** Dante (Mr. C. Mezie), creedConsult
**Status:** Approved design, pending spec review
**Approach:** Hybrid (C) — rebuild the data layer rigorously, modularize the UI, keep working code.

---

## 1. Goal & Definition of Done

Complete the existing ~40%-built dashboard into a locally-verified, deploy-ready
portfolio artifact that turns **real Toronto open-data** into four insight views.

**Done when ALL are true:**

- [ ] Every data source pulls **real data** from a verified official endpoint (no fakes).
- [ ] `transform.py` runs clean and populates DuckDB; `validate.py` passes.
- [ ] All four dashboard pages render with real data: Skill Demand, Salary Ranges, Role Fit, Market Context.
- [ ] `streamlit run` works from a clean checkout with consistent imports.
- [ ] `pytest` suite passes (pipeline correctness + data quality).
- [ ] Repo is deploy-ready: themed `.streamlit/config.toml`, DB committed (<50 MB) or Git LFS, pinned deps, README quick-start filled.
- [ ] Final GitHub push + Streamlit Cloud deploy left to the user (requires their accounts).

**Data policy (user decision):** Real data, fixed at all costs. If a source's endpoint
or licence has changed since the June 2026 research, exhaust real options and surface
the finding rather than synthesize data.

---

## 2. Architecture & Structure

Keep the existing layout. Fix the import story — the current clash between
`from src.pipeline.X import …` (in `transform.py`, `insights.py`) and the
`sys.path.insert(... "src"/"pipeline")` hack (in `app.py`) is the root cause of breakage.

- Add `src/__init__.py` and `src/pipeline/__init__.py`.
- Install editable: `pip install -e .` (configure `pyproject.toml` package discovery for `src`).
- Standardize all imports to `from pipeline.X import …`. Remove `sys.path` hacks.
- `streamlit_app/app.py` becomes a thin router. Each page moves to a `render_*()` function
  under `streamlit_app/pages_impl/` (one file per page) sharing the existing brand CSS.

---

## 3. Data Layer — Source Verification & Rewrite (highest risk)

Replace HTML regex-scraping with the **CKAN Action API** for open.canada.ca datasets.
Verify each source live before wiring it in. Every downloader must: retry on failure,
emit clear error messages, and **assert a non-zero row count** so a silently-empty result
becomes a loud error.

| Source | Dataset / Endpoint | Verification task |
|--------|--------------------|-------------------|
| Job Bank postings | CKAN `package_show?id=ea639e28-c0fc-48bf-b5dd-b8899bd43072` → `result.resources[].url` | Inspect real CSV columns; **resolve OQ-1** (is there rich requirements text, or extract from title + NOC name only?). Report finding. |
| Job Bank wages | CKAN `package_show?id=adad580f-76b0-4502-bd05-20c125de9116` | Confirm Toronto economic-region filter (ER3530 / "Toronto"); identify wage columns + annual flag. |
| StatsCan JVWS | WDS `getFullTableDownloadCSV/14100444/en` → JSON `object` → ZIP → CSV | Verify live response shape; pivot `Statistics` rows (job vacancies vs. avg offered wage) into columns; filter Toronto GEO. |
| Indeed Hiring Lab | `github.com/hiring-lab/*` raw CSVs | Verify current repo paths/filenames (they move); pin to what resolves; Ontario filter. |
| Lightcast Open Skills | TBD — current `lightcast/openskills/main/skills.json` is wrong | Research real distribution (published CSV/API); cache locally. |
| NOC 2021 | TBD — current esdc URL marked `# Approximate` | Find verified NOC structure source; keep hardcoded map as fallback only. |

---

## 4. Schema Alignment & Transform Fixes

- Fix the `print("…")` literal-newline **syntax error** in `transform.py` (~line 281).
- **Denormalize `posted_date` and `noc_code` into `job_skills`** — `insights.py` queries
  `job_skills.posted_date`, which the current schema lacks (the Skill Demand crash).
- Reconcile real CSV headers (from §3) with the DuckDB schema; map columns explicitly.
- Parse salary text into `salary_min/max/median`; normalize hourly vs. annual
  (annual ÷ 2,080 → hourly equivalent).
- Make `transform.py` **idempotent** (drop/recreate or upsert) so re-runs don't duplicate.

---

## 5. Skill Extraction Redesign

Replace the per-n-gram fuzzy match (currently O(postings × ngrams × 34K) — hours of runtime,
over-matching) with a single-pass **spaCy `PhraseMatcher` / flashtext** exact-and-normalized scan:

- Build the matcher once from Lightcast skill names.
- Scan each posting's text in one pass → matched skill IDs.
- Curated synonym/acronym map for high-value terms (SQL, AWS, GCP, CI/CD, "power bi", React, etc.).
- Keep an honest precision caveat in the methodology expander.

---

## 6. Insights Layer

Structurally sound. Adjust queries to the reconciled schema, add empty-result guards,
and sanity-check each of the four functions against the real DB
(`get_skill_demand_trends`, `get_emerging_skills`, `get_salary_by_role`,
`compute_role_fit`, `get_market_context`).

---

## 7. UI — Complete All Four Pages

Reuse the brand CSS / design tokens already in `app.py`. Each page keeps the methodology
expander + confidence badge pattern.

- **Skill Demand** (exists) — finish the broken trailing string; verify against real data.
- **Salary Ranges** (accent-wealth) — range/box plot by role, searchable NOC lookup, salary histogram.
- **Role Fit** (accent-clarity) — skill multiselect → fit gauge, gap table, best-fit roles.
- **Market Context** (accent-signal) — Indeed Ontario momentum, StatsCan vacancy trend, wage growth.

---

## 8. Error Handling & Data Quality

`scripts/validate.py`, run as the final pipeline step, asserts:

- Row counts above minimum thresholds per table.
- Null rates below thresholds on key columns.
- Date freshness within expected range.
- Join integrity: every `job_skills.job_id` exists in `job_postings`; NOC join coverage.

Fails loudly on violation.

---

## 9. Testing

`pytest`, focused where correctness matters (not UI snapshots):

- Salary parsing / hourly-annual normalization.
- Skill matcher precision on fixture posting text.
- NOC mapping correctness.
- DuckDB data-quality assertions.

---

## 10. Deploy-Ready (user finishes the push)

- `.streamlit/config.toml` themed to brand palette.
- DuckDB committed if <50 MB, else Git LFS.
- `requirements.txt` pinned and matching `pyproject.toml`.
- README quick-start filled in; `streamlit run` verified from clean checkout.
- Final GitHub + Streamlit Cloud steps documented for the user to run.

---

## 11. Build Sequence (each phase gated on prior producing data)

1. Imports/package fix + data-layer verification → **real rows in DuckDB**.
2. Schema reconciliation + transform fixes.
3. Skill extraction.
4. Insights sanity-check.
5. UI pages.
6. Validation + tests.
7. Deploy-prep.

---

## 12. Open Questions / Risks

- **OQ-1:** Does the Job Bank postings CSV contain rich requirements text? If not, Skill
  Demand relies on title + NOC name, weakening that view. Resolve by inspecting a real CSV early.
- **Source drift:** Endpoints/licences may have changed since June 2026. Surface, don't fake.
- **Scope:** Multi-session build. Role Fit (P1 in original PRD) is in scope per this design.
- **DB size:** If committed DuckDB exceeds 50 MB, switch to Git LFS or a reproducible download script.
