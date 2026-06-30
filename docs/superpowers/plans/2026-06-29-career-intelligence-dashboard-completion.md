# Career Intelligence Dashboard — Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the ~40%-built Toronto Career Intelligence Dashboard into a locally-verified, deploy-ready Streamlit app driven by real Canadian open-data.

**Architecture:** Editable-installed `pipeline` package (no more `sys.path` hacks). Downloaders pull verified real sources → DuckDB via an idempotent `transform.py` → `insights.py` queries → modular Streamlit app (one `render_*` per page). Validation + pytest gate correctness.

**Tech Stack:** Python 3.11, pandas, duckdb, rapidfuzz/flashtext, spaCy (PhraseMatcher), streamlit, plotly. Data: open.canada.ca CKAN, StatsCan NOC CSV, Lightcast gist, Indeed Hiring Lab (GitHub `master`).

**Grounding:** See `docs/superpowers/specs/2026-06-29-data-source-findings.md` for verified endpoints, encodings, and columns. Postings are **UTF-16/TAB**, **no requirements text** (skills from titles + NOC names).

---

## Phase 0 — Environment & package setup

### Task 0.1: Create venv and install deps
**Files:** Modify `pyproject.toml` (package discovery), add `src/__init__.py`, `src/pipeline/__init__.py`

- [ ] **Step 1:** Create venv: `python -m venv .venv` then activate (`.venv\Scripts\activate` on Windows).
- [ ] **Step 2:** Add to `pyproject.toml` after `[tool.mypy]`:
```toml
[tool.setuptools.packages.find]
where = ["src"]
```
Add `flashtext2>=1.0` to dependencies; pin `rapidfuzz` already present. Add `en_core_web_sm` note (installed separately).
- [ ] **Step 3:** Create empty `src/__init__.py` and `src/pipeline/__init__.py`.
- [ ] **Step 4:** `pip install -e .` then `pip install -e ".[dev]"`. Install spaCy model: `python -m spacy download en_core_web_sm`.
- [ ] **Step 5:** Verify: `python -c "from pipeline.skill_taxonomy import SkillTaxonomy; print('ok')"` → prints `ok`.
- [ ] **Step 6:** Commit: `git add -A && git commit -m "chore: package setup, editable install, package discovery"`

### Task 0.2: Standardize imports
**Files:** Modify `scripts/transform.py`, `src/pipeline/insights.py`, `streamlit_app/app.py`

- [ ] **Step 1:** In `transform.py` change `from src.pipeline.noc_mapper import NOCMapper` → `from pipeline.noc_mapper import NOCMapper`; same for `skill_taxonomy`.
- [ ] **Step 2:** In `insights.py` change `from src.pipeline.skill_taxonomy import get_taxonomy` → `from pipeline.skill_taxonomy import get_taxonomy`.
- [ ] **Step 3:** In `app.py` remove the `sys.path.insert(...)` block; change `from insights import (...)` → `from pipeline.insights import (...)`.
- [ ] **Step 4:** Fix `noc_mapper.py`: move `import pandas as pd` (currently last line) to the top with other imports.
- [ ] **Step 5:** Verify import graph: `python -c "from pipeline import insights, noc_mapper, skill_taxonomy, statscan_client; print('ok')"`.
- [ ] **Step 6:** Commit: `git add -A && git commit -m "refactor: consistent pipeline.* imports, fix noc_mapper import order"`

---

## Phase 1 — Data layer (verified real sources)

### Task 1.1: Shared download utilities
**Files:** Create `src/pipeline/io_utils.py`; Test `tests/test_io_utils.py`

- [ ] **Step 1:** Write failing test `tests/test_io_utils.py`:
```python
from pipeline.io_utils import detect_encoding_sep

def test_detects_utf16_tab():
    raw = "﻿A\tB\tC\n1\t2\t3".encode("utf-16")
    enc, sep = detect_encoding_sep(raw)
    assert enc == "utf-16"
    assert sep == "\t"

def test_detects_utf8_comma():
    raw = "A,B,C\n1,2,3".encode("utf-8")
    enc, sep = detect_encoding_sep(raw)
    assert enc in ("utf-8", "utf-8-sig")
    assert sep == ","
```
- [ ] **Step 2:** Run `pytest tests/test_io_utils.py -v` → FAIL (module missing).
- [ ] **Step 3:** Implement `io_utils.py`:
```python
"""Shared HTTP + CSV helpers for the data pipeline."""
import io
import time
import requests
import pandas as pd

UA = {"User-Agent": "Mozilla/5.0 CareerIntelligenceDashboard/1.0", "Accept": "*/*"}

def http_get(url: str, timeout: int = 90, retries: int = 3, stream: bool = False) -> requests.Response:
    last = None
    for i in range(retries):
        try:
            r = requests.get(url, headers=UA, timeout=timeout, stream=stream)
            r.raise_for_status()
            return r
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 * (i + 1))
    raise last

def detect_encoding_sep(raw: bytes) -> tuple[str, str]:
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        enc = "utf-16"
    elif raw[:3] == b"\xef\xbb\xbf":
        enc = "utf-8-sig"
    else:
        enc = "utf-8"
    head = raw[:4000].decode(enc, errors="replace")
    first = head.splitlines()[0] if head.splitlines() else ""
    sep = "\t" if first.count("\t") > first.count(",") else ","
    return enc, sep

def read_csv_bytes(raw: bytes, **kw) -> pd.DataFrame:
    enc, sep = detect_encoding_sep(raw)
    return pd.read_csv(io.BytesIO(raw), encoding=enc, sep=sep, low_memory=False, **kw)

def ckan_csv_resources(dataset_id: str, lang: str = "en") -> list[dict]:
    """Return CKAN resources that are downloadable English CSVs."""
    url = f"https://open.canada.ca/data/api/action/package_show?id={dataset_id}"
    data = http_get(url).json()
    out = []
    for r in data["result"]["resources"]:
        u = (r.get("url") or "")
        if u.lower().endswith(".csv") and lang in (r.get("language") or ["en"]):
            out.append(r)
    return out
```
- [ ] **Step 4:** Run `pytest tests/test_io_utils.py -v` → PASS.
- [ ] **Step 5:** Commit: `git add -A && git commit -m "feat: shared io_utils (http retry, encoding/sep detection, CKAN resources)"`

### Task 1.2: Rewrite Job Bank postings downloader
**Files:** Modify `scripts/download_job_bank_postings.py`

- [ ] **Step 1:** Replace `get_resource_urls()` (HTML regex) with CKAN. New core:
```python
from pipeline.io_utils import ckan_csv_resources, http_get, read_csv_bytes

DATASET_ID = "ea639e28-c0fc-48bf-b5dd-b8899bd43072"
TORONTO_LOCATIONS = [...]  # keep existing GTA list

def fetch_and_filter(months: int = 12):
    resources = ckan_csv_resources(DATASET_ID, "en")
    # newest first; names contain month/year — take latest `months`
    resources = sorted(resources, key=lambda r: r.get("created", ""), reverse=True)[:months]
    for r in resources:
        raw = http_get(r["url"]).content
        df = read_csv_bytes(raw)               # UTF-16 / TAB handled automatically
        loc = next(c for c in df.columns if c.strip().lower() == "city")
        er  = next((c for c in df.columns if "economic" in c.lower()), None)
        mask = df[loc].astype(str).str.lower().apply(lambda x: any(t in x for t in TORONTO_LOCATIONS))
        if er: mask = mask | df[er].astype(str).str.contains("Toronto", case=False, na=False)
        out = df[mask]
        assert len(out) > 0, f"No Toronto rows in {r['name']}"  # loud failure
        out.to_csv(RAW_DIR / f"toronto_{r['url'].split('/')[-1]}", index=False)
```
- [ ] **Step 2:** Run `python scripts/download_job_bank_postings.py --months 3` (add argparse `--months`, default 12).
- [ ] **Step 3:** Verify: filtered files appear in `data/raw/job_bank_postings/`, each with >0 Toronto rows; print row counts.
- [ ] **Step 4:** Commit: `git add -A && git commit -m "feat: Job Bank postings downloader via CKAN (utf-16/tab, Toronto filter)"`

### Task 1.3: Rewrite Job Bank wages downloader
**Files:** Modify `scripts/download_job_bank_wages.py`

- [ ] **Step 1:** Replace HTML scrape with `ckan_csv_resources("adad580f-76b0-4502-bd05-20c125de9116")`; pick latest 1–3 years by name.
- [ ] **Step 2:** Read via `read_csv_bytes`; find region column (`ER_Name` or contains "region"); filter rows where region == "Toronto" OR code == "3530"/"ER3530".
- [ ] **Step 3:** Assert >0 rows; save `toronto_wages_<year>.csv`.
- [ ] **Step 4:** Run + verify row count printed.
- [ ] **Step 5:** Commit: `git add -A && git commit -m "feat: Job Bank wages downloader via CKAN, Toronto ER filter"`

### Task 1.4: Rewrite Indeed downloader (master branch, real files)
**Files:** Modify `scripts/download_indeed_trends.py`

- [ ] **Step 1:** Replace `FILES` with verified URLs:
```python
FILES = {
  "metro_postings":     "https://raw.githubusercontent.com/hiring-lab/job_postings_tracker/master/CA/metro_job_postings_CA.csv",
  "provincial_postings":"https://raw.githubusercontent.com/hiring-lab/job_postings_tracker/master/CA/provincial_postings_ca.csv",
  "sector_postings":    "https://raw.githubusercontent.com/hiring-lab/job_postings_tracker/master/CA/job_postings_by_sector_CA.csv",
  "wage_by_sector":     "https://raw.githubusercontent.com/hiring-lab/indeed-wage-tracker/main/posted-wage-growth-by-sector.csv",
  "ai_postings":        "https://raw.githubusercontent.com/hiring-lab/ai-tracker/main/AI_posting.csv",
}
```
(If a wage/ai URL 404s on `main`, retry with `master`; log which worked.)
- [ ] **Step 2:** For `metro_postings`, keep only rows where `Metro == "Toronto, ON"`. For provincial, keep `province` in {"on","ontario"}.
- [ ] **Step 3:** Assert Toronto metro rows > 0; save each as `indeed_<key>.csv`.
- [ ] **Step 4:** Run + verify `indeed_metro_postings.csv` has Toronto rows.
- [ ] **Step 5:** Commit: `git add -A && git commit -m "feat: Indeed downloader (master branch, Toronto metro + sector/ai)"`

### Task 1.5: NOC 2021 mapper from real CSV
**Files:** Modify `src/pipeline/noc_mapper.py`; Test `tests/test_noc_mapper.py`

- [ ] **Step 1:** Failing test:
```python
from pipeline.noc_mapper import normalize_noc
def test_normalize_noc_strips_prefix_and_pads():
    assert normalize_noc("NOC_21231") == "21231"
    assert normalize_noc("2123") == "02123"
    assert normalize_noc(21231) == "21231"
```
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement: add module-level `normalize_noc(code) -> str` (strip non-digits, left-pad to 5). Rewrite `_load` to download `https://www.statcan.gc.ca/en/subjects/standard/noc/2021/indexV1/noc-2021-v1.0-classification-structure.csv` via `http_get`, parse cols `Code - NOC 2021 V1.0` → title `Class title`, `Level`/`Hierarchical structure` → category. Cache to `data/processed/noc_2021.csv`. Keep hardcoded `_load_fallback` only on download failure.
- [ ] **Step 4:** Run test → PASS; also run `python -c "from pipeline.noc_mapper import NOCMapper; m=NOCMapper(); print(len(m.noc_to_title), m.get_title('21231'))"`.
- [ ] **Step 5:** Commit: `git add -A && git commit -m "feat: real NOC 2021 mapper + normalize_noc join key"`

### Task 1.6: Lightcast taxonomy from gist mirror
**Files:** Modify `src/pipeline/skill_taxonomy.py`

- [ ] **Step 1:** Change `TAXONOMY_URL` to `https://gist.githubusercontent.com/ThatGuySam/8a6e7bd152793ac12b7f60420d1017c8/raw`. In `_load`, the JSON is `{"data": [ {id,name,...} ]}` — iterate `data["data"]` (fallback to `data` if it is already a list). Keep caching to `data/processed/lightcast_skills.json`.
- [ ] **Step 2:** Verify: `python -c "from pipeline.skill_taxonomy import get_taxonomy; t=get_taxonomy(); print(len(t.by_name))"` → ~30k+.
- [ ] **Step 3:** Commit: `git add -A && git commit -m "feat: Lightcast taxonomy from verified gist mirror"`

### Task 1.7: StatsCan client (structurally correct; sandbox-blocked host)
**Files:** Modify `src/pipeline/statscan_client.py`, `scripts/download_statscan_jvws.py`

- [ ] **Step 1:** Route requests through `pipeline.io_utils.http_get` (retry). Add a clear note in module docstring: `www150.statcan.gc.ca` may be blocked in some egress environments; run from a Canadian connection. Wrap `main()` so a network failure prints a friendly skip message and exits 0 (pipeline continues with Indeed as Toronto source).
- [ ] **Step 2:** Add `--allow-skip` flag (default true) so transform never hard-blocks on StatsCan.
- [ ] **Step 3:** Verify it imports and runs without crashing the pipeline when the host is unreachable (prints skip message).
- [ ] **Step 4:** Commit: `git add -A && git commit -m "feat: resilient StatsCan client with graceful skip"`

---

## Phase 2 — Transform & schema

### Task 2.1: Fix transform syntax + schema denormalization
**Files:** Modify `scripts/transform.py`

- [ ] **Step 1:** Fix the literal-newline `print("\n=== ... ===")` bugs (use proper `\n` escapes), ~lines 281, 289, 293, 307.
- [ ] **Step 2:** Add `posted_date DATE` and `noc_code VARCHAR` columns to the `job_skills` table DDL (denormalized for `insights.py`).
- [ ] **Step 3:** Make idempotent: at start of `main()`, `DROP TABLE IF EXISTS` each table before recreate (or `DELETE FROM`). Prevents PK-duplicate errors on re-run.
- [ ] **Step 4:** Update postings column mapping to real headers (from findings doc): `Job Title`→title, `NOC21 Code`→noc_code (via `normalize_noc`), `City`→city/location, `Vacancy Count`→vacancies, `Salary Per/Minimum/Maximum`→salary fields, `First Posting Date`→posted_date, `Employment Type`→employment_terms. There is no requirements column — set `requirements_text = Original Job Title + " " + NOC21 Code Name`.
- [ ] **Step 5:** Commit: `git add -A && git commit -m "fix: transform syntax, idempotency, real column mapping, job_skills denorm"`

### Task 2.2: Salary parsing/normalization
**Files:** Create `src/pipeline/salary.py`; Test `tests/test_salary.py`

- [ ] **Step 1:** Failing test:
```python
from pipeline.salary import to_hourly, parse_salary_row
def test_annual_to_hourly():
    assert round(to_hourly(83200, "Year"), 2) == 40.0   # 83200/2080
def test_hourly_passthrough():
    assert to_hourly(40, "Hour") == 40.0
def test_parse_row_min_max_median():
    r = parse_salary_row({"Salary Minimum": "30", "Salary Maximum": "50", "Salary Per": "Hour"})
    assert r["salary_min"] == 30.0 and r["salary_max"] == 50.0 and r["salary_median"] == 40.0
def test_parse_row_handles_na():
    r = parse_salary_row({"Salary Minimum": "NA", "Salary Maximum": "", "Salary Per": "Hour"})
    assert r["salary_min"] is None
```
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement `to_hourly(value, per)` (Year→/2080, Week→/40, else passthrough) and `parse_salary_row(row)` returning `{salary_min, salary_max, salary_median}` with NA/empty→None, median = mean of min/max when both present.
- [ ] **Step 4:** Run → PASS. Wire `parse_salary_row` into `transform.py` postings loader.
- [ ] **Step 5:** Commit: `git add -A && git commit -m "feat: salary parsing/normalization + wire into transform"`

### Task 2.3: Fast skill matcher (replace n-gram fuzzy)
**Files:** Create `src/pipeline/skill_matcher.py`; Modify `transform.py` `extract_skills_for_postings`; Test `tests/test_skill_matcher.py`

- [ ] **Step 1:** Failing test:
```python
from pipeline.skill_matcher import SkillMatcher
def test_matches_known_skills():
    m = SkillMatcher({"python": "KS1", "sql": "KS2", "power bi": "KS3"})
    found = m.extract("Senior Python Developer with SQL and Power BI")
    ids = {f["skill_id"] for f in found}
    assert {"KS1", "KS2", "KS3"} <= ids
def test_no_substring_false_positive():
    m = SkillMatcher({"r": "KS9"})        # single-letter skill must not match inside words
    assert m.extract("Strong communicator") == []
```
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement `SkillMatcher` using `flashtext2` KeywordProcessor (word-boundary aware, case-insensitive, single pass). Constructor takes `{skill_name_lower: skill_id}`; `extract(text)` returns list of `{skill_id, skill_name}`. Skip skill names shorter than 2 chars to avoid noise.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Rewrite `extract_skills_for_postings` in `transform.py` to: build matcher once from taxonomy (`{name: id}` + curated acronym map SQL/AWS/GCP/CI-CD/React/etc.), scan `requirements_text` (title+NOC name), insert rows incl. denormalized `posted_date`, `noc_code`, `category` (from taxonomy).
- [ ] **Step 6:** Commit: `git add -A && git commit -m "feat: flashtext skill matcher (single-pass), replace slow n-gram fuzzy"`

### Task 2.4: Run full pipeline → real DuckDB
**Files:** none (execution)

- [ ] **Step 1:** Run downloaders: postings (`--months 12`), wages, indeed. (StatsCan will gracefully skip in this env.)
- [ ] **Step 2:** Run `python scripts/transform.py`.
- [ ] **Step 3:** Verify printed row counts: `job_postings` (thousands), `job_skills` (>0), `wages_job_bank` (>0), `indeed_trends` (>0), `noc_mapping` (~500+).
- [ ] **Step 4:** Spot-check: `python -c "import duckdb; c=duckdb.connect('data/processed/career_intel.duckdb'); print(c.execute('select count(*) from job_postings').fetchone())"`.
- [ ] **Step 5:** Commit DB if <50MB else note Git LFS: `git add -A && git commit -m "data: first full pipeline run, real Toronto DuckDB"` (after .gitignore review — see Task 4.2).

---

## Phase 3 — Insights & UI

### Task 3.1: Align insights to real schema + indeed_trends shape
**Files:** Modify `src/pipeline/insights.py`

- [ ] **Step 1:** Confirm `get_skill_demand_trends`/`get_emerging_skills` work against denormalized `job_skills.posted_date` (now present). Run each function in a REPL against the real DB; fix column refs.
- [ ] **Step 2:** `get_market_context`: adapt to real Indeed schema — postings index from `indeed_metro_postings` (Toronto), wage growth from `indeed_wage_by_sector`, AI share from `indeed_ai_postings`. Adjust `indeed_trends` table columns in transform to carry `metric`/`value`/`geography` OR add per-source columns; keep insights + transform consistent.
- [ ] **Step 3:** Add guard: every function returns empty DataFrame/dict (not exception) when a table is missing.
- [ ] **Step 4:** Commit: `git add -A && git commit -m "fix: insights aligned to real schema + Indeed market context"`

### Task 3.2: Modularize app + finish Skill Demand page
**Files:** Create `streamlit_app/pages_impl/__init__.py`, `skill_demand.py`; Modify `streamlit_app/app.py`

- [ ] **Step 1:** Move the CSS + sidebar into `app.py` router; extract Skill Demand body into `pages_impl/skill_demand.py::render(date_range)`. Fix the truncated final line (`st.info("Run  to load data...")` → `st.info("Run \`python scripts/transform.py\` to load data.")`).
- [ ] **Step 2:** `app.py` dispatches: `if page=="📈 Skill Demand": skill_demand.render(...)` etc.
- [ ] **Step 3:** Run `streamlit run streamlit_app/app.py`, confirm Skill Demand renders real data (screenshot).
- [ ] **Step 4:** Commit: `git add -A && git commit -m "refactor: app router + Skill Demand page module"`

### Task 3.3: Salary Ranges page
**Files:** Create `streamlit_app/pages_impl/salary_ranges.py`

- [ ] **Step 1:** `render()` calls `get_salary_by_role()`; show: range/box plot (min/median/max by role, accent-wealth), searchable NOC dropdown → salary card, salary histogram. Methodology expander + confidence badge (reuse pattern from Skill Demand).
- [ ] **Step 2:** Wire into `app.py`. Run + screenshot.
- [ ] **Step 3:** Commit: `git add -A && git commit -m "feat: Salary Ranges page"`

### Task 3.4: Role Fit page
**Files:** Create `streamlit_app/pages_impl/role_fit.py`

- [ ] **Step 1:** `render()`: `st.multiselect` of skill names (from taxonomy/top-demand), button → `compute_role_fit(user_skills)`; show fit gauge (Plotly indicator, accent-clarity), matched skills, ranked gap-skill table, recommendation text.
- [ ] **Step 2:** Wire into `app.py`. Run + screenshot.
- [ ] **Step 3:** Commit: `git add -A && git commit -m "feat: Role Fit page"`

### Task 3.5: Market Context page
**Files:** Create `streamlit_app/pages_impl/market_context.py`

- [ ] **Step 1:** `render()`: `get_market_context()`; Toronto Indeed postings-index line chart (accent-signal), sector wage-growth bar, AI-share line. Note StatsCan vacancy section renders only if that table is populated.
- [ ] **Step 2:** Wire into `app.py`. Run + screenshot.
- [ ] **Step 3:** Commit: `git add -A && git commit -m "feat: Market Context page"`

---

## Phase 4 — Validation, tests, deploy-prep

### Task 4.1: validate.py data-quality gate
**Files:** Create `scripts/validate.py`

- [ ] **Step 1:** Assert per-table min row counts; null-rate thresholds on `job_postings.noc_code`, `salary_*`; `posted_date` freshness (max within ~120 days); join integrity (every `job_skills.job_id` ∈ `job_postings.id`); NOC join coverage > 50%. Print a PASS/FAIL report; exit 1 on failure.
- [ ] **Step 2:** Run `python scripts/validate.py` against the real DB → PASS.
- [ ] **Step 3:** Commit: `git add -A && git commit -m "feat: validate.py data-quality gate"`

### Task 4.2: .gitignore / DB commit strategy
**Files:** Modify `.gitignore`

- [ ] **Step 1:** Ensure `data/raw/` ignored. Decide DB: if `data/processed/career_intel.duckdb` < 50MB, un-ignore and commit; else add Git LFS (`git lfs track "*.duckdb"`) or commit a `scripts/build_db.sh` + leave DB ignored. Document choice in README.
- [ ] **Step 2:** Commit.

### Task 4.3: Streamlit theme + README + clean-checkout verify
**Files:** Create `.streamlit/config.toml`; Modify `README.md`

- [ ] **Step 1:** `.streamlit/config.toml` themed to brand (primaryColor `#3B2F9E`, background `#F7F9FC`, etc.).
- [ ] **Step 2:** Fill README Quick Start: venv, `pip install -e .`, spaCy model, run downloaders, `transform.py`, `validate.py`, `streamlit run streamlit_app/app.py`.
- [ ] **Step 3:** Clean-checkout smoke test: fresh clone/venv, follow README, confirm app launches with data.
- [ ] **Step 4:** Commit: `git add -A && git commit -m "docs: README quick start + Streamlit brand theme"`

### Task 4.4: Final test sweep
- [ ] **Step 1:** `pytest -v` → all pass (`io_utils`, `noc_mapper`, `salary`, `skill_matcher`).
- [ ] **Step 2:** `ruff check .` clean (or documented ignores).
- [ ] **Step 3:** Final commit + summary of what user must do to deploy (GitHub push, Streamlit Cloud connect).

---

## Self-review notes
- **Spec coverage:** §2 imports→T0.2; §3 sources→T1.1–1.7 (each verified); §4 schema→T2.1–2.2; §5 skill extraction→T2.3; §6 insights→T3.1; §7 UI→T3.2–3.5; §8 validation→T4.1; §9 tests→T0/1/2 test tasks + T4.4; §10 deploy→T4.2–4.3.
- **OQ-1:** resolved in findings doc; reflected in T2.1 step 4 (requirements_text = title + NOC name) and Skill Demand methodology.
- **StatsCan risk:** handled by graceful-skip (T1.7) + Indeed metro as primary Toronto source (T1.4, T3.5).
- **Types:** `normalize_noc`, `parse_salary_row`/`to_hourly`, `SkillMatcher.extract`, `detect_encoding_sep`/`read_csv_bytes`/`ckan_csv_resources` used consistently across tasks.
