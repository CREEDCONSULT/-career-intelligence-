# LLM Intelligence Layer — Implementation & Research Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a grounded, provider-agnostic LLM layer over the existing DuckDB analytics — text-to-SQL Q&A, monthly brief, LLM skill extraction, resume→role match, advisor chat — without the model ever inventing a number.

**Architecture:** A `src/llm/` foundation (LiteLLM gateway + SQLGlot SQL guard + deterministic numeric-grounding + DuckDB cache + eval harness) that all five features sit on. The LLM only generates SQL (validated + executed deterministically) or narrates over numbers we hand it (every prose number verified against the source result set).

**Tech Stack:** Python 3.11, LiteLLM, SQLGlot, DuckDB, Pydantic, pytest, datacompy; Claude tiers (Haiku/Sonnet/Opus) via env, provider-swappable; later: Qdrant + sentence-transformers.

**Grounding docs:** `docs/superpowers/specs/2026-06-30-llm-intelligence-layer-design.md` (spec), `…-llm-layer-research-findings.md` (research).

**Non-negotiable principle:** The LLM never emits a figure. Generated SQL is validated and executed; narrated numbers are verified to appear in the source result set, else regenerated.

---

## File structure

```
src/llm/
  __init__.py
  config.py       # env -> model tiers, provider, budget
  gateway.py      # LiteLLM wrapper: complete(), caching, cost/budget tracking
  schema.py       # schema card builder (cached prompt prefix)
  sql_guard.py    # SQLGlot validate (SELECT-only) + read-only guarded execute + self-correct
  grounding.py    # numbers_in(), grounded(), faithfulness(), verify()
  cache.py        # content-addressed DuckDB response cache
  features/
    __init__.py
    ask.py        # Phase 1: text-to-SQL Q&A orchestration
    brief.py      # Phase 2
    skills_llm.py # Phase 3
    role_match.py # Phase 4
    advisor.py    # Phase 5
  eval/
    runner.py     # execution-accuracy + faithfulness runners
    gold/
      ask_gold.json
tests/llm/
  test_config.py test_sql_guard.py test_grounding.py test_cache.py
  test_schema.py test_gateway.py test_ask.py test_eval_ask.py
streamlit_app/pages_impl/ ask.py  advisor.py
.env.example       # extended with LLM_* vars
```

Dependencies to add to `pyproject.toml` + `requirements.txt`: `litellm>=1.50`, `sqlglot>=25.0`, `pydantic>=2.0` (already transitive), `datacompy>=0.11`.

---

# PHASE 0 — Foundation

### Task 0.1: Dependencies + config

**Files:** Modify `pyproject.toml`, `requirements.txt`; Create `src/llm/__init__.py`, `src/llm/config.py`, `.env.example`; Test `tests/llm/__init__.py`, `tests/llm/test_config.py`

- [ ] **Step 1:** Add to `pyproject.toml` dependencies and `requirements.txt`: `litellm>=1.50.0`, `sqlglot>=25.0.0`, `datacompy>=0.11.0`. Install: `./.venv/Scripts/python.exe -m pip install litellm sqlglot datacompy`.
- [ ] **Step 2:** Create empty `src/llm/__init__.py` and `tests/llm/__init__.py`.
- [ ] **Step 3:** Write failing test `tests/llm/test_config.py`:
```python
import os
from llm.config import LLMConfig

def test_defaults_to_anthropic_tiers(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    cfg = LLMConfig.from_env()
    assert cfg.provider == "anthropic"
    assert "haiku" in cfg.model_for("batch").lower()
    assert cfg.token_budget > 0

def test_env_overrides(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL_INTERACTIVE", "gpt-4o")
    cfg = LLMConfig.from_env()
    assert cfg.provider == "openai"
    assert cfg.model_for("interactive") == "gpt-4o"
```
- [ ] **Step 4:** Run `./.venv/Scripts/python.exe -m pytest tests/llm/test_config.py -v` → FAIL.
- [ ] **Step 5:** Implement `src/llm/config.py`:
```python
"""LLM layer configuration, resolved from environment."""
from __future__ import annotations
import os
from dataclasses import dataclass

_DEFAULTS = {
    "anthropic": {
        "batch": "anthropic/claude-haiku-4-5-20251001",
        "interactive": "anthropic/claude-sonnet-4-6",
        "hard": "anthropic/claude-opus-4-8",
    },
    "openai": {"batch": "openai/gpt-4o-mini", "interactive": "openai/gpt-4o", "hard": "openai/gpt-4o"},
}

@dataclass(frozen=True)
class LLMConfig:
    provider: str
    models: dict
    token_budget: int

    @classmethod
    def from_env(cls) -> "LLMConfig":
        provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
        base = dict(_DEFAULTS.get(provider, _DEFAULTS["anthropic"]))
        base["batch"] = os.getenv("LLM_MODEL_BATCH", base["batch"])
        base["interactive"] = os.getenv("LLM_MODEL_INTERACTIVE", base["interactive"])
        base["hard"] = os.getenv("LLM_MODEL_HARD", base["hard"])
        budget = int(os.getenv("LLM_TOKEN_BUDGET", "2000000"))
        return cls(provider=provider, models=base, token_budget=budget)

    def model_for(self, tier: str) -> str:
        return self.models.get(tier, self.models["interactive"])
```
- [ ] **Step 6:** Run test → PASS. Add `.env.example` lines: `LLM_PROVIDER=anthropic`, `ANTHROPIC_API_KEY=`, `LLM_MODEL_BATCH=`, `LLM_MODEL_INTERACTIVE=`, `LLM_MODEL_HARD=`, `LLM_TOKEN_BUDGET=2000000`. Gitignore real `.env`.
- [ ] **Step 7:** Commit: `git add -A && git commit -m "feat(llm): config + deps (litellm, sqlglot, datacompy)"`

### Task 0.2: SQL guard (SQLGlot validation + read-only execution)

**Files:** Create `src/llm/sql_guard.py`; Test `tests/llm/test_sql_guard.py`

- [ ] **Step 1:** Write failing test `tests/llm/test_sql_guard.py`:
```python
import duckdb
import pytest
from llm.sql_guard import validate_select, run_guarded, GuardError

def test_accepts_select():
    validate_select("SELECT skill_name, count(*) FROM job_skills GROUP BY 1")

def test_rejects_non_select():
    for bad in ["DELETE FROM job_postings", "DROP TABLE job_skills",
                "UPDATE job_postings SET title='x'", "INSERT INTO job_skills VALUES (1)"]:
        with pytest.raises(GuardError):
            validate_select(bad)

def test_rejects_multiple_statements():
    with pytest.raises(GuardError):
        validate_select("SELECT 1; DROP TABLE job_postings")

def test_rejects_syntax_error():
    with pytest.raises(GuardError):
        validate_select("SELECT FROM WHERE GROUP")

def test_run_guarded_returns_df():
    con = duckdb.connect()
    con.execute("CREATE TABLE t (a INTEGER); INSERT INTO t VALUES (1),(2),(3)")
    df = run_guarded(con, "SELECT sum(a) AS s FROM t", row_cap=10)
    assert int(df.iloc[0]["s"]) == 6

def test_run_guarded_blocks_writes():
    con = duckdb.connect()
    con.execute("CREATE TABLE t (a INTEGER)")
    with pytest.raises(GuardError):
        run_guarded(con, "INSERT INTO t VALUES (1)", row_cap=10)
```
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement `src/llm/sql_guard.py`:
```python
"""Validate and safely execute LLM-generated SQL against DuckDB.

Static validation via SQLGlot (SELECT-only, single statement, parseable), then
execution on a read-only connection with a row cap. Research: SQLGlot catches
syntax/dialect errors pre-execution; execution-guard catches the rest.
"""
from __future__ import annotations
import duckdb
import pandas as pd
import sqlglot
from sqlglot import exp

class GuardError(Exception):
    pass

_ALLOWED_ROOT = (exp.Select, exp.Subquery, exp.With, exp.Union)

def validate_select(sql: str) -> sqlglot.Expression:
    try:
        statements = sqlglot.parse(sql, read="duckdb")
    except Exception as e:  # noqa: BLE001
        raise GuardError(f"unparseable SQL: {e}") from e
    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        raise GuardError("exactly one statement required")
    root = statements[0]
    if not isinstance(root, _ALLOWED_ROOT):
        raise GuardError(f"only SELECT queries allowed, got {type(root).__name__}")
    for node in root.walk():
        if isinstance(node, (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create,
                             exp.Alter, exp.Command, exp.TruncateTable)):
            raise GuardError(f"disallowed operation: {type(node).__name__}")
    return root

def run_guarded(con: duckdb.DuckDBPyConnection, sql: str, row_cap: int = 1000) -> pd.DataFrame:
    validate_select(sql)
    capped = f"SELECT * FROM ({sql.rstrip(';')}) AS _q LIMIT {row_cap}"
    try:
        return con.execute(capped).df()
    except Exception as e:  # noqa: BLE001
        raise GuardError(f"execution failed: {e}") from e
```
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit: `git add -A && git commit -m "feat(llm): SQLGlot SELECT-only guard + read-only execute"`

### Task 0.3: Numeric grounding + faithfulness scaffolding

**Files:** Create `src/llm/grounding.py`; Test `tests/llm/test_grounding.py`

- [ ] **Step 1:** Write failing test `tests/llm/test_grounding.py`:
```python
import pandas as pd
from llm.grounding import numbers_in, grounded

def test_numbers_in_extracts_numerics():
    nums = numbers_in("Sales leads with 665 postings, up 12.5% from $40.00/hr")
    assert 665 in nums and 12.5 in nums and 40.0 in nums

def test_grounded_passes_when_all_numbers_present():
    df = pd.DataFrame({"skill": ["Sales"], "postings": [665]})
    ok, unguarded = grounded("Sales had 665 postings.", df)
    assert ok and unguarded == []

def test_grounded_flags_invented_number():
    df = pd.DataFrame({"skill": ["Sales"], "postings": [665]})
    ok, unguarded = grounded("Sales had 999 postings.", df)
    assert not ok and 999 in unguarded

def test_grounded_allows_simple_derived_totals():
    df = pd.DataFrame({"skill": ["A", "B"], "postings": [100, 200]})
    ok, _ = grounded("Together they total 300 postings.", df, allow_sums=True)
    assert ok
```
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement `src/llm/grounding.py` (deterministic numeric check is the core moat; faithfulness/verify are LLM-judge helpers used later):
```python
"""Grounding guards for LLM narration.

`grounded()` is the deterministic guard: every number in the prose must appear in
the source result set (within tolerance), optionally allowing simple sums of cells.
Research flagged that claim-ratio faithfulness can miss numeric hallucinations, so
this deterministic check is the primary guard; faithfulness is secondary.
"""
from __future__ import annotations
import re
from itertools import combinations
import pandas as pd

_NUM_RE = re.compile(r"-?\$?\d[\d,]*\.?\d*%?")

def _to_float(token: str):
    t = token.replace("$", "").replace(",", "").replace("%", "")
    try:
        return float(t)
    except ValueError:
        return None

def numbers_in(text: str) -> set[float]:
    out = set()
    for m in _NUM_RE.findall(text or ""):
        v = _to_float(m)
        if v is not None:
            out.add(v)
    return out

def _cell_values(df: pd.DataFrame) -> set[float]:
    vals = set()
    for col in df.columns:
        for v in pd.to_numeric(df[col], errors="coerce").dropna().tolist():
            vals.add(round(float(v), 4))
    return vals

def grounded(prose: str, df: pd.DataFrame, allow_sums: bool = False, tol: float = 0.01):
    cells = _cell_values(df)
    # round-trip cells to allow $40 vs 40.0 etc.
    derived = set(cells)
    if allow_sums and len(cells) <= 12:
        for r in range(2, min(len(cells), 6) + 1):
            for combo in combinations(cells, r):
                derived.add(round(sum(combo), 4))
    unguarded = []
    for n in numbers_in(prose):
        if not any(abs(n - c) <= tol or (c != 0 and abs(n - c) / abs(c) <= tol) for c in derived):
            unguarded.append(n)
    return (len(unguarded) == 0, unguarded)
```
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Add (no test yet; exercised in Phase 1 integration) `faithfulness(prose, context, judge)` and `verify(prose, judge)` stubs that take a `judge` callable (the gateway) — documented as LLM-judge claim-ratio and CoVe 4-step respectively. Keep them small and typed.
- [ ] **Step 6:** Commit: `git add -A && git commit -m "feat(llm): deterministic numeric-grounding guard"`

### Task 0.4: Content-addressed response cache

**Files:** Create `src/llm/cache.py`; Test `tests/llm/test_cache.py`

- [ ] **Step 1:** Failing test:
```python
from llm.cache import ResponseCache

def test_cache_roundtrip(tmp_path):
    c = ResponseCache(tmp_path / "cache.duckdb")
    key = c.key("anthropic/claude", "prompt text")
    assert c.get(key) is None
    c.put(key, "the response", tokens=42)
    assert c.get(key) == "the response"

def test_key_is_stable_and_content_addressed(tmp_path):
    c = ResponseCache(tmp_path / "cache.duckdb")
    assert c.key("m", "abc") == c.key("m", "abc")
    assert c.key("m", "abc") != c.key("m", "abd")
```
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement `src/llm/cache.py` using a small DuckDB table keyed by `sha256(model + "\n" + prompt)`, columns `(key TEXT PRIMARY KEY, response TEXT, tokens INT, created TIMESTAMP)`. `key()`, `get()`, `put()`.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit: `git add -A && git commit -m "feat(llm): DuckDB response cache"`

### Task 0.5: Schema card builder

**Files:** Create `src/llm/schema.py`; Test `tests/llm/test_schema.py`

- [ ] **Step 1:** Failing test: `build_schema_card(con)` returns a string containing every table name (`job_postings`, `job_skills`, `wages_job_bank`, `vacancies_statscan`, `indeed_trends`, `noc_mapping`), the join keys, and the title-only limitation note.
```python
import duckdb
from llm.schema import build_schema_card

def test_schema_card_lists_tables_and_caveat():
    con = duckdb.connect()
    con.execute("CREATE TABLE job_skills (job_id INT, skill_name TEXT, posted_date DATE)")
    card = build_schema_card(con)
    assert "job_skills" in card and "skill_name" in card
    assert "title" in card.lower()  # the limitation note
```
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement `build_schema_card(con)`: introspect `information_schema.columns`, render `table(col type, ...)` lines, append a fixed notes block (join keys: `noc_code`; skills are title-derived; wages are hourly-normalized; indeed_trends is long-format `metric/value`). Keep under ~1.5K tokens so it caches cheaply.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit: `git add -A && git commit -m "feat(llm): schema card builder"`

### Task 0.6: LiteLLM gateway (interface + budget; live call behind a spike)

**Files:** Create `src/llm/gateway.py`; Test `tests/llm/test_gateway.py`

- [ ] **Step 1:** Failing unit test (mocks LiteLLM — no network):
```python
from llm.gateway import Gateway
from llm.config import LLMConfig

def test_gateway_tracks_tokens_and_budget(monkeypatch):
    cfg = LLMConfig(provider="anthropic", models={"interactive": "m", "batch": "m", "hard": "m"}, token_budget=100)
    calls = {}
    def fake_completion(**kw):
        calls["kw"] = kw
        class R:  # minimal litellm-like response
            choices = [type("C", (), {"message": type("M", (), {"content": "hi"})})]
            usage = type("U", (), {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
        return R()
    gw = Gateway(cfg, completion_fn=fake_completion)
    out = gw.complete([{"role": "user", "content": "x"}], tier="interactive")
    assert out.text == "hi"
    assert gw.tokens_used == 15

def test_gateway_enforces_budget(monkeypatch):
    cfg = LLMConfig(provider="anthropic", models={"interactive": "m"}, token_budget=10)
    def fake_completion(**kw):
        class R:
            choices = [type("C", (), {"message": type("M", (), {"content": "hi"})})]
            usage = type("U", (), {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
        return R()
    gw = Gateway(cfg, completion_fn=fake_completion)
    gw.complete([{"role": "user", "content": "x"}], tier="interactive")
    import pytest
    with pytest.raises(Exception):
        gw.complete([{"role": "user", "content": "y"}], tier="interactive")
```
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement `src/llm/gateway.py`: `Gateway(cfg, completion_fn=litellm.completion, cache=None)`. `complete(messages, tier, cache_prefix=None) -> Response(text, tokens)`. Inject `completion_fn` for testability. Track `tokens_used`; raise `BudgetExceeded` when over `cfg.token_budget`. When `cache_prefix` given and provider is anthropic, attach `cache_control` breakpoint to that system block (per Anthropic caching). Wire optional `ResponseCache`.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5 (SPIKE — needs `ANTHROPIC_API_KEY`):** Write `src/llm/_smoke.py` that does one real `gw.complete(...)` and prints text + tokens. Run once with a key to confirm LiteLLM + provider wiring. Record the working model IDs + the exact cache_control call shape in the spec's findings doc. Mark integration tests `@pytest.mark.skipif(no key)`.
- [ ] **Step 6:** Commit: `git add -A && git commit -m "feat(llm): LiteLLM gateway with budget + caching hooks"`

### Task 0.7: Eval harness

**Files:** Create `src/llm/eval/runner.py`, `src/llm/eval/gold/ask_gold.json`; Test `tests/llm/test_eval_ask.py`

- [ ] **Step 1:** Create `ask_gold.json` with ≥20 `{question, reference_sql}` pairs over the real schema (mix of: top-N skills, salary by role, vacancy trend, emerging skills, joins, window/CTE queries — deliberately exercising DuckDB analytical SQL).
- [ ] **Step 2:** Failing test: `execution_accuracy(con, predicted_sql, reference_sql)` returns True when both result sets match (compare via datacompy / sorted DataFrame equality), False otherwise.
```python
import duckdb
from llm.eval.runner import execution_accuracy

def test_execution_accuracy_matches_equivalent_sql():
    con = duckdb.connect(); con.execute("CREATE TABLE t(a INT); INSERT INTO t VALUES (1),(2)")
    assert execution_accuracy(con, "SELECT sum(a) s FROM t", "SELECT (1+2) s")
    assert not execution_accuracy(con, "SELECT count(*) c FROM t", "SELECT sum(a) c FROM t")
```
- [ ] **Step 3:** Run → FAIL.
- [ ] **Step 4:** Implement `execution_accuracy` (run both via `run_guarded`, normalize column order + sort rows, compare). Add `run_ask_eval(con, gw, gold)` that, given the Phase-1 ask pipeline, computes execution accuracy % + numeric-grounding %.
- [ ] **Step 5:** Run → PASS.
- [ ] **Step 6:** Commit: `git add -A && git commit -m "feat(llm): eval harness (execution accuracy) + gold set"`

**Phase 0 gate:** `pytest tests/llm -q` green; `_smoke.py` confirmed a live call once.

---

# PHASE 1 — Text-to-SQL Q&A (first shippable)

### Research track (do first)
- **RQ1.1:** What execution accuracy does the chosen model reach on `ask_gold.json` (our DuckDB analytical schema) with schema-card prompting + self-correction? *(Spike: run `run_ask_eval`, record %.)*
- **RQ1.2:** Does the deterministic numeric-grounding guard catch invented/transposed numbers the LLM produces in narration? *(Spike: adversarially prompt for a wrong number, confirm guard rejects.)*
- **Eval gate:** execution accuracy ≥ 80% on gold set **and** numeric-grounding = 100% before Phase 1 is "done."

### Task 1.1: Ask orchestration
**Files:** Create `src/llm/features/ask.py`; Test `tests/llm/test_ask.py`

- [ ] **Step 1:** Failing test with a fake gateway returning a known-good SQL then a narration; assert `answer.sql`, `answer.table` (DataFrame), `answer.prose`, and `answer.grounded is True`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement `ask(question, con, gw) -> Answer`: build schema card (cached prefix) → prompt for SQL → `validate_select` → `run_guarded` → on `GuardError` run `self_correct` (≤2 retries, feed error back) → prompt for a narration constrained to the result rows → `grounded()`; if not grounded, one regeneration, else return prose with an "unverified" flag and show only the table.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit.

### Task 1.2: Ask page
**Files:** Create `streamlit_app/pages_impl/ask.py`; Modify `streamlit_app/app.py` (add "💬 Ask" page)

- [ ] **Step 1:** `render()`: text input → `ask(...)` → show prose, the result table, and an expander with **the generated SQL** (auditability) + grounding badge. Guard for missing API key (friendly message).
- [ ] **Step 2:** Add to `app.py` PAGES dict + dispatch. Run `streamlit run`, confirm a real question returns a grounded answer (needs key). Screenshot.
- [ ] **Step 3:** Extend `tests/test_app_smoke.py` to include the Ask page (skips if no key).
- [ ] **Step 4:** Commit.

### Task 1.3: Phase-1 eval gate
- [ ] **Step 1:** Run `run_ask_eval` over `ask_gold.json`; record execution accuracy % + grounding %.
- [ ] **Step 2:** If accuracy < 80%: error-analysis loop (improve schema card / add 2–3 schema-grounded guardrail examples — NOT case-specific few-shot), re-measure. Document final number in the research-findings doc.
- [ ] **Step 3:** Commit results + a short `docs/llm-eval-results.md`.

---

# PHASES 2–5 — Research-then-build tracks

Each phase: **(a) research questions → (b) spike to measure → (c) TDD build on the foundation → (d) eval gate.** Each gets its own detailed task-level plan (via writing-plans) once its spike resolves the unknowns. Do not pre-write concrete code whose shape depends on spike outcomes.

### Phase 2 — Monthly market brief (`features/brief.py`, pipeline step)
- **Research:** best structure for grounded long-form narration; does faithfulness + numeric-grounding fully gate a multi-paragraph brief?
- **Spike:** generate one brief from the four views' numbers; run `grounded()` per paragraph + faithfulness; count ungrounded numbers.
- **Build:** `make_brief(con, gw)` → sectioned prose, each section grounded; render/export branded Markdown/PDF; cache by month.
- **Eval gate:** 0 ungrounded numbers; faithfulness ≥ 0.9 on a 5-brief sample.

### Phase 3 — LLM skill extraction (`features/skills_llm.py`, pipeline step)
- **Research (RQ from findings #2):** accuracy/cost crossover — Haiku structured-extraction + caching + Batch vs. flashtext baseline; is light fine-tuning worth it?
- **Spike:** extract skills for 500 sampled titles with Haiku (JSON/tool-use, Pydantic-validated); hand-label 100; compute precision/recall vs. flashtext; record $/1K postings with caching + Batch.
- **Build:** batch extractor writing to `job_skills` with a `method` column ('flashtext'|'llm'); A/B switch in transform; budget guard.
- **Eval gate:** precision ≥ flashtext on the labeled sample; cost/run within the configured budget.

### Phase 4 — Resume/profile → role match (`features/role_match.py`, page extension)
- **Research (RQ from findings #8):** embedding model for role semantics; fusion of Qdrant hybrid (dense+BM25 RRF) scores with structured demand/salary (re-rank vs. weighted vs. filter-then-rank).
- **Spike:** embed NOC/title corpus + 10 sample profiles in Qdrant; measure top-k role relevance for 2–3 embedding models; try the 3 fusion strategies.
- **Build:** resume parse (structured) → embed → Qdrant hybrid retrieve → fuse with demand/salary → ranked roles + gaps; new UI panel.
- **Eval gate:** top-5 role relevance on a held-out profile set beats the current set-overlap Role Fit.

### Phase 5 — Grounded advisor chat (`features/advisor.py`, page `advisor.py`)
- **Research:** RAG context assembly from DuckDB-derived facts; CoVe efficacy on advice answers; refusal behavior.
- **Spike:** 15 advice questions (5 out-of-scope) → measure faithfulness + correct refusals.
- **Build:** chat that retrieves facts + calls the Phase-1 `ask` tool; CoVe verify; refuse when unsupported.
- **Eval gate:** faithfulness ≥ 0.9 on in-scope; 100% correct refusal on out-of-scope.

---

## Cross-cutting
- **Cost guard:** every phase routes through `Gateway` (budget enforced); batch phases use Haiku + caching + Batch API.
- **Secrets:** `.env` (gitignored); deploy needs keys only for interactive phases (1, 5).
- **CI:** `pytest tests/llm -q` runs unit + eval (live-API tests skipped without a key).

## Self-review notes
- **Spec coverage:** §1 principle→grounding.py+ask grounding; §2 decisions→0.1/0.2/0.3/0.6; §4 foundation→Tasks 0.1–0.7; §5 features→Phase 1 tasks + Phase 2–5 tracks; §6 eval→0.7+1.3+each gate; §7 cost→config budget+gateway+0.6; §8 structure→file map; §10 risks→the per-phase research/spikes.
- **No placeholders:** Phase 0 + 1 have concrete code/tests; Phases 2–5 are deliberately research-tracks (each spawns its own detailed plan post-spike) — flagged as such, not hidden TODOs.
- **Type consistency:** `validate_select`/`run_guarded`/`GuardError` (sql_guard), `grounded`/`numbers_in` (grounding), `Gateway.complete`/`Response.text`/`tokens_used` (gateway), `LLMConfig.model_for` (config), `execution_accuracy` (eval) used consistently across tasks.
