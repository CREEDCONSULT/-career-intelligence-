# RECOVERY_AUDIT.md — Career Intelligence Forensic Repository Audit

**Audited by:** GLM-5.3 recovery session (replacing stuck Nemotron/Nemo session)
**Date:** 2026-10-05
**Scope:** Phase 1 forensic audit only — no files were modified during this audit.

---

## 1. Repository Root & Layout

- **Actual project root:** `C:\Users\daunt\Downloads\-career-intelligence--main\-career-intelligence--main`
- **Working directory (session):** `C:\Users\daunt\Downloads\-career-intelligence--main` (outer wrapper folder, one level above the repo root)
- **Origin:** GitHub zip download of `CREEDCONSULT/-career-intelligence-` (main branch). Referenced in README badge and successfully reachable — `scripts/transform.py` original was fetched from `raw.githubusercontent.com` during this audit.
- **Git:** ❌ **No `.git` directory.** Not a git repository. There is no commit history, no branch, no diff baseline. The "recovery branch" requirement must be satisfied by `git init` + file-level backups (done in Phase 2).

**Framework/runtime:** Streamlit (`streamlit>=1.28`) + DuckDB + Python 3.11. App entrypoint: `streamlit_app/app.py` (router). Docker/Railway deploy via `entrypoint.py` + `Dockerfile`.

**Import architecture (intended):** `pip install -e .` installs `pipeline` and `llm` packages from `src/` (per `pyproject.toml` `[tool.setuptools.packages.find] where=["src"]` and the Dockerfile's `RUN pip install -e .`). CI (`.github/workflows/ci.yml`) runs `pip install -e ".[dev]"`, `ruff check src scripts streamlit_app`, then `pytest -q`.

**Data:** `data/processed/career_intel.duckdb` exists (15,216,640 bytes) with real Toronto market data. `data/raw/` is empty (raw CSVs not shipped in the zip).

## 2. Running Processes

No processes were running at takeover. The previous session repeatedly launched `streamlit run` in the foreground; those processes are gone (console showed `ConnectionResetError` when the piped stdin closed — a known artifact of piping `echo "" | streamlit run`, not an app error).

## 3. Files Modified / Created by the Previous Session

Timestamp forensics (baseline files all carry `2026-09-30 1:55:06–07 AM`; anything newer was touched by the previous session):

| File | State | Damage |
|---|---|---|
| `streamlit_app/app.py` | **CORRUPTED** (4,913 B, rewritten many times, last write Oct 5 06:10) | Orphan line 2 (`    career_profile,`), duplicate `)` line 20, broken string literal line 105 (`"Data not loaded ??" run the pipeline."` → unterminated string), mangled nav labels, ANSI-mojibake rewrites of emoji |
| `streamlit_app/app.py.backup` | Mid-session backup (4,712 B) | Already corrupted when captured — **not** a usable baseline |
| `scripts/transform.py` | **DESTROYED** (1,749 B vs original 12,725 B) | Truncated to a single `init_user_tables()` helper; the entire ETL pipeline (`init_db`, `load_noc_mapping`, `load_job_bank_postings`, `load_wages`, `load_statscan`, `load_indeed`, `extract_skills`, `main`) is gone |
| `src/user_data.py` | **NEW** (6,718 B) | Valid Python. DuckDB DAO layer for `career_profile`, `user_skills`, `user_evidence`, `user_applications` |
| `streamlit_app/pages_impl/career_profile.py` | **NEW** (1,657 B) | Valid Python, but `render()` takes no args while the router calls `render(date_range)` → latent TypeError |
| `Nemotron Career Checkpoint.txt` | NEW (session artifact) | Stale checkpoint claiming success; actual file state contradicts it |
| `streamlit_output.txt` | NEW (session artifact) | Debug log capturing the compile-error loop |

**Untouched and intact** (original timestamps, byte-identical to upstream): all of `tests/`, `src/pipeline/`, `src/llm/`, the 8 original `streamlit_app/pages_impl/*.py`, `_shared.py`, `entrypoint.py`, `Dockerfile`, `pyproject.toml`, `config/market.yaml`, `.streamlit/config.toml`, `.github/workflows/*`.

## 4. Root Cause of the Loop (Definitive)

1. **Display mojibake misdiagnosed as file corruption.** The repo uses UTF-8 emoji in UI strings. PowerShell 5.1's console (non-UTF-8 codepage) renders those bytes as garbage (`dY'`, `?`-runs). Proof: `tests/test_app_smoke.py` — untouched, original timestamp — contains **perfect UTF-8** (`💬 🧠 📈 💰 🎯 📄 📊 📰`, verified by codepoint dump: U+1F4AC, U+1F9E0, …). The *untouched* files were fine; only the *terminal view* was mojibake.
2. **"Repairs" caused real corruption.** The previous session ran `Get-Content`/`Set-Content` surgery on `app.py`. `Set-Content` in PS 5.1 defaults to ANSI encoding → UTF-8 emoji were rewritten as literal `?`/garbage bytes, and index-based line splicing introduced duplicated lines, orphan tokens, and unterminated string literals.
3. **Escalating retry loop.** Each attempted fix used the same failing strategy (PowerShell string surgery) against symptoms that were partly *caused by the tooling* (console rendering). The session never changed diagnosis after identical failures, violating the 2-failure rule, and left `transform.py` destroyed as collateral damage of a here-string rewrite gone wrong.
4. **Startup appeared to succeed while broken.** `streamlit run` prints "You can now view your app" *before* compiling the script, so the banner appeared even when every rerun ended in `SyntaxError` — reinforcing the false impression of near-success.

## 5. Corruption Classification

### 5.1 True source corruption (must repair)

| Location | Problem |
|---|---|
| `app.py:1–3` | Orphan `    career_profile,` + duplicated `import sys` |
| `app.py:20` | Duplicate closing `)` of the import block |
| `app.py:105` | `st.caption("Data not loaded ??" run the pipeline.")` — unterminated string literal (hard `SyntaxError`) |
| `app.py` PAGES dict | Mangled labels (`"dY\"^ Skill Demand"` etc.) — valid syntax but garbage UI keys; smoke test can no longer select pages |
| `app.py:27,110` | Emoji rewritten to literal `?` (ANSI re-encode) |
| `scripts/transform.py` | 98.6% of the file destroyed |
| `pages_impl/career_profile.py` | (New) `render()` signature mismatch with router contract `render(date_range)` |
| `tests/test_app_smoke.py` | (New-ish issue) PAGES list won't match the repaired canonical labels → parametrized smoke test would fail on selection |

### 5.2 Cosmetic / pre-existing (from original archive, valid Python)

- `pages_impl/_shared.py`: `st.expander("?? Methodology", ...)` — original archive already contained `??` here (emoji lost upstream, not session damage). Renders as "??" but is not a syntax problem.
- Similar benign `??`/`§`-style artifacts in a few other original UI strings (e.g. `salary_ranges.py`, `skill_demand.py` headers). Valid UTF-8, valid Python.

### 5.3 Encoding hygiene

- **No BOMs** found on any key file (verified by first-3-byte dump).
- Original repo files are UTF-8 (emoji verified by codepoint). Session-rewritten files (`app.py`, `transform.py`) are ANSI-safe ASCII now — meaning the rewrites *did* strip the emoji bytes.
- `read`/`Get-Content -Encoding UTF8` is required for inspection; console codepage must not be trusted for mojibake judgments.

## 6. Entrypoints & Validation Stack (for Phase 4)

- App: `streamlit run streamlit_app/app.py` (from repo root)
- Deploy: `python entrypoint.py` (Railway/Docker; runs Streamlit + optional background refresh)
- Tests: `pytest -q` — includes `tests/test_app_smoke.py` which renders every page via `streamlit.testing.v1.AppTest` against the committed DuckDB; live LLM tests self-skip without API keys
- Lint: `ruff check src scripts streamlit_app`
- Requires one-time `pip install -e .` for `pipeline`/`llm` imports (this was never done by the previous session — the actual cause of the original `ModuleNotFoundError: No module named 'pipeline'`)

## 7. Recovery Assets Confirmed Available

- ✅ Original `scripts/transform.py` — fetched verbatim from GitHub main during this audit
- ✅ Original `app.py` structure — fully reconstructible (router is small; CSS/sidebar blocks intact in the corrupted copy; canonical labels confirmed from `test_app_smoke.py` emoji set)
- ✅ Real processed DuckDB present → app and smoke tests have data
- ✅ All 8 original page modules intact with `def render(date_range)` contract

## 8. Audit Conclusion

The codebase is **recoverable to a known-good baseline** with four surgical repairs (app.py rewrite, transform.py restore, career_profile signature fix, smoke-test label alignment) plus one environment fix (`pip install -e .`). No evidence supports the previous session's checkpoint claim that "syntax errors are fixed" — `app.py` does not compile as of audit time.

**Status: AUDIT COMPLETE → proceed to Phase 2 (preserve state) before any modification.**
