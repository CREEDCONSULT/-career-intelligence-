# Productization Sprint + Brief + LLM Skills — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Harden the platform into a scalable, sellable product (Track A), then ship the monthly market brief (Phase 2) and LLM skill extraction (Phase 3) from the approved LLM-layer plan.

**Approved scope (user, 2026-07-02):** Track A → Phase 2 → Phase 3. Grounded in:
- Review findings (2026-07-02): DB holds only 2 months of postings; no CI; Toronto hardcoded; no cost/abuse guard on public Ask; freshness strings hardcoded; dead fuzzy-extractor code; no scheduled refresh.
- Market research (`research.txt`): sales line is "want one for your market?" (→ market config); briefs feed the LinkedIn strategy; honest methodology converts buyers.
- LLM research findings (`2026-06-30-llm-layer-research-findings.md`): Haiku + prompt caching + structured JSON for batch extraction; deterministic grounding as primary guard.

---

## Track A — Productization

### A1: Full 12-month data backfill (start FIRST, runs in background)
- [ ] Run `download_job_bank_postings.py --months 12`, `download_job_bank_wages.py --years 3`, `download_indeed_trends.py`, `download_statscan_jvws.py` (graceful skip ok).
- [ ] After A5 lands: `python scripts/transform.py` (idempotent rebuild) → `python scripts/validate.py` → all PASS.
- [ ] Confirm DB has 12 monthly posting buckets; check file size (<50 MB → commit; else Git LFS).
- [ ] Commit rebuilt DB.

### A2: CI
- [ ] Create `.github/workflows/ci.yml`: push/PR → setup Python 3.11 → `pip install -e ".[dev]"` → `ruff check src scripts streamlit_app` → `pytest -q`. Live-API tests already self-skip without keys; app smoke tests use the committed DB.
- [ ] Commit.

### A3: Ask-page cost/abuse guards
- [ ] Create `src/llm/usage.py`: `DailyUsage(path)` — JSON-file-backed daily token counter (`today() -> int`, `add(tokens)`, auto-reset on date change). Test: `tests/llm/test_usage.py` (roundtrip, date reset via injected clock).
- [ ] Ask page: per-session question cap (default 10, env `ASK_SESSION_LIMIT`), daily token cap (default 200K, env `ASK_DAILY_TOKEN_CAP`) checked before each call, tokens recorded after; wire `ResponseCache` into the page gateway so repeat questions are free. Friendly limit messages.
- [ ] Commit.

### A4: Dynamic data freshness
- [ ] `app.py` sidebar: replace hardcoded strings with `pipeline.insights.get_data_freshness()` (guarded for missing DB), showing actual max dates per source table.
- [ ] Commit.

### A5: Market config (de-hardcode Toronto)
- [ ] Create `config/market.yaml` (name, tagline, jobbank_cities, economic_region name+codes, statscan_geo_contains, indeed_metro) + `src/pipeline/market.py` loader (`load_market()`, env override `MARKET_CONFIG`, embedded Toronto defaults). Test: `tests/test_market.py`.
- [ ] Replace hardcoded values in the four downloaders, `transform.py` region literals, `llm/schema.py` note, and `app.py` title/tagline with market fields.
- [ ] Full pytest green. Commit.

### A6: Cleanup + scheduled refresh
- [ ] Delete dead `fuzzy_match`/`extract_skills_from_text` from `skill_taxonomy.py` (superseded by flashtext matcher); confirm no imports break; pytest green.
- [ ] Create `.github/workflows/refresh.yml`: monthly cron (+ manual dispatch), `contents: write` — run downloaders → transform → validate → commit updated DB if changed.
- [ ] Commit.

## Phase 2 — Monthly market brief

- [ ] Implement `grounding.faithfulness(prose, context, judge)`: LLM-judge claim-ratio (list claims, verify each against context, return supported/total). Test with fake judge.
- [ ] Create `src/llm/features/brief.py`: `make_brief(con, gw, month=None) -> str`. Sections: market overview (posting counts, MoM), skill demand (top + emerging), salary (top roles), macro (Indeed index, AI share, wage growth). Each section: compute stats via `pipeline.insights` → one short LLM paragraph → `grounded()` gate (retry once; on failure fall back to deterministic bullet stats). Assemble branded Markdown with attribution + date. Tests with FakeGW: sections grounded, fallback path, assembly.
- [ ] Create `scripts/make_brief.py`: writes `docs/briefs/YYYY-MM.md`; uses ResponseCache (idempotent reruns).
- [ ] Create `streamlit_app/pages_impl/brief.py` ("📰 Market Brief") rendering the latest brief file; wire into router + smoke test.
- [ ] Generate the real brief for the latest month (live key); verify 0 ungrounded numbers; measure faithfulness on it; record in `docs/llm-eval-results.md`. Commit brief + results.
- **Gate:** 0 ungrounded numbers in the shipped brief.

## Phase 3 — LLM skill extraction

- [ ] Spike: extract skills for ~300 sampled distinct titles with Haiku (batched JSON, Pydantic-validated); record parse-failure rate + $/1K titles; qualitative A/B vs flashtext on 25 titles. Document. Abort/adjust if quality poor.
- [ ] Add `method` column to `job_skills` (transform DDL + flashtext writer sets 'flashtext').
- [ ] Create `src/llm/features/skills_llm.py`: `SkillItem` Pydantic model; `extract_titles(titles, gw, batch_size=25)` — numbered-title batches, strict JSON array out, fence-strip + validate, one retry per failed batch. Tests with FakeGW (parse, validation, retry).
- [ ] Create `scripts/extract_skills_llm.py`: distinct (title, noc name) from DB → extract (tier=batch, cache_prefix instructions, ResponseCache) → map skill names to taxonomy ids (else `LOCAL:`) → expand to postings by title join → insert `job_skills` rows with method='llm'. Budget-guarded.
- [ ] Run full extraction on 12-month data; A/B report (counts, distinct skills, overlap, cost) → `docs/llm-eval-results.md`.
- [ ] `insights.py`: method-aware queries (env `SKILLS_METHOD`, default decided by A/B result). UI unchanged.
- **Gate:** LLM skills ≥ flashtext quality on sampled titles; cost within `LLM_TOKEN_BUDGET`.

## Final
- [ ] Full pytest + ruff sweep; fresh screenshots; merge to main; push (CI goes live on push).
