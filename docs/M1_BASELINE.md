# M1 Baseline Verification

**Date:** 2026-10-05 · **Verified by:** GLM-5.3 M1 session
**Expected baseline:** `main @ 7e53eee` (recovery accepted as RECOVERED)

## Verification results

| Check | Expected | Actual | Status |
|---|---|---|---|
| HEAD commit | `7e53eee` | `7e53eee564ff69cf9d32eda109da0f363a6d084b` | ✅ |
| Branch | `main` | `main` | ✅ |
| Working tree | clean | clean (no modifications) | ✅ |
| Lint (`ruff check src scripts streamlit_app`) | all pass | "All checks passed!" | ✅ |
| Test suite (`pytest -q`) | 100 pass, 1 known failure | 100 passed, 1 failed | ✅ |
| Live app startup | HTTP 200 | HTTP 200 on :8624 | ✅ |
| 9/9 page rendering (`tests/test_app_smoke.py`) | 9 pass | 9 passed in 8.45s | ✅ |

## Interpreter environment (critical, machine-specific)

- **Intended project Python:** `C:\Users\daunt\AppData\Local\Programs\Python\Python311\python.exe` (3.11.9) — all deps installed, project installed editable (`pip install -e .`).
- **Hazard confirmed:** bare `python` on PATH resolves FIRST to the Hermes agent venv
  (`C:\Users\daunt\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe`), which has **no** project deps.
- **Rule for this machine:** every validation/build command uses the full system-Python path.
  A "ModuleNotFoundError" from bare `python` is an environment artifact, not a code problem.

## Known shipped-data gap (preserved, explicitly documented)

- `tests/llm/test_role_match.py::test_build_role_docs_from_real_db` fails because the optional
  `job_skills_llm` table is absent from the committed demo DuckDB. It is created only by
  `scripts/extract_skills_llm.py` (needs an LLM API key; response-cached so one run suffices).
- This gap predates M1, is unrelated to M1 scope, and remains the **only** red test.
- M1 must not mask it; the final M1 report must state whether it is still red.

## Reusable assets confirmed for M1

- `pipeline.skill_matcher.build_skill_index()` + `SkillMatcher`: 33,090-entry synonym-aware,
  whole-token skill index (Lightcast taxonomy + curated aliases). Verified working.
  The M1 fit engine reuses this instead of inventing a new normalization layer.
- `src/user_data.py`: career-profile DAO (kept; M1 narrows it to profile-only).
- `llm.gateway` / `llm.config`: provider-agnostic LLM access with tier models + response cache.
- Router contract: every page module exposes `render(date_range=None)`.

## M1 scope (from the phase brief)

Vertical slice only: opportunity model → evidence model → evidence-based fit engine →
application state machine → application workspace → Resume-Studio integration with evidence
traceability → next-best-action engine → ingestion boundary (manual paste + fixture, no scraping)
→ Creed integration adapters (interfaces only) → full test coverage → minimal UI.

**Explicitly out of scope:** gamification, M2 capabilities, scraping/automating job boards,
requiring Gmail/Calendar/Drive credentials, redesigning the Streamlit app.
