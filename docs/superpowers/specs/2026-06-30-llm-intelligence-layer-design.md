# LLM Intelligence Layer — Design Spec

**Date:** 2026-06-30
**Author:** Dante (Mr. C. Mezie), creedConsult
**Status:** Approved design, pending spec review
**Decisions:** provider-agnostic gateway · foundation-first sequencing · real-research-informed.

Research backing: `docs/superpowers/specs/2026-06-30-llm-layer-research-findings.md` (deep-research
report, 23 verified claims).

---

## 1. Goal & Guiding Principle

Add a **grounded, provider-agnostic LLM layer** on top of the existing DuckDB analytics so the
dashboard gains language understanding (questions, messy titles, resumes) and language generation
(briefs, advice) — **without ever letting the model invent a number.**

**The non-negotiable principle (the auditability moat):**
> The LLM never emits a figure. It either (a) generates SQL that is validated and executed
> deterministically, or (b) narrates over numbers we hand it, where every number in the prose is
> verified to appear in the source result set. Ungrounded numbers are rejected and regenerated.

This is what separates this from a chatbot and preserves "every number is auditable."

## 2. Decisions locked (from research)

| Concern | Decision | Source |
|---------|----------|--------|
| Provider abstraction | **LiteLLM** (Claude + OpenAI + local, one interface, cost tracking, retries/fallbacks) | github.com/BerriAI/litellm |
| Default models | Claude tiers: Haiku (batch), Sonnet (interactive), Opus (hard narration) — swappable via config | — |
| Cost control | Anthropic prompt caching (reads 0.1×, writes 1.25×/2×) + Batch API (50%, stacks) | platform.claude.com/docs/.../prompt-caching |
| SQL validation | **SQLGlot** static parse (DuckDB dialect) + read-only execution guard | github.com/tobymao/sqlglot |
| Text-to-SQL accuracy | schema linking + execution-guided self-correction + schema-grounded guardrails | arxiv 2510.09014 |
| Grounding | faithfulness (supported/total claims) + CoVe 4-step + **deterministic numeric-grounding check** | ragas, arxiv 2309.11495 |
| Eval | execution accuracy (result-set compare via datacompy) + faithfulness | docs.ragas.io |
| Skill extraction | structured JSON/tool-use + Pydantic validation + Haiku + cache + Batch (fine-tune later) | arxiv 2410.12052 |
| Semantic match | Qdrant hybrid (dense + sparse BM25, RRF), retrieve→rerank, fuse with structured signals | qdrant.tech |

**Refuted / avoided:** GRPO/RL fine-tuning as a driver (out of scope); CoVe's "factored verification"
specific mechanism (use the 4-step structure, not that sub-claim).

## 3. Architecture

```
DuckDB (career_intel.duckdb) + src/pipeline/insights.py   ← numbers originate here, always
                    │ read-only
        ┌───────────┴──────────────── src/llm/ (NEW foundation) ───────────────┐
        │ gateway.py   LiteLLM wrapper: model tiers, prompt caching, retries,    │
        │              cost tracking, hard token-budget guard                    │
        │ sql_guard.py SQLGlot validate (SELECT-only, DuckDB) + read-only exec   │
        │              + execution-guided self-correction loop                   │
        │ grounding.py numeric-grounding check (every prose number ∈ result set) │
        │              + faithfulness scorer + CoVe verify helper                │
        │ schema.py    schema card (tables/columns/sample values) for prompts    │
        │ cache.py     DuckDB-backed response/result cache (idempotent reruns)   │
        │ eval/        gold sets + runners (execution accuracy, faithfulness)    │
        └───────────────────────────────┬──────────────────────────────────────┘
                    src/llm/features/ — one module per feature
                    streamlit_app/pages_impl/ — ask.py, advisor.py (UI)
```

Each foundation unit has one responsibility, a typed interface, and is independently testable.

## 4. Foundation components (Phase 0)

- **`gateway.py`** — thin LiteLLM wrapper. `complete(messages, tier, cache=True, schema=None) -> Response`.
  Reads `LLM_PROVIDER` + per-tier model IDs from env. Applies Anthropic cache breakpoints on the
  shared prefix. Tracks tokens/cost per call; enforces a per-run hard token budget (raises when hit).
  Provider-agnostic: same call works for Claude, OpenAI, or a local Ollama model.
- **`schema.py`** — builds a compact "schema card" (table names, columns, types, 2–3 sample values,
  the NOC/skill join keys, the title-only limitation note) cached as the shared prompt prefix.
- **`sql_guard.py`** — `validate(sql) -> ok|ParseError` via SQLGlot (reject non-SELECT, DDL/DML, multiple
  statements); `run_guarded(sql) -> df` on a **read-only** DuckDB connection with a row/time cap;
  `self_correct(question, sql, error) -> sql'` loop (max N attempts).
- **`grounding.py`** — `numbers_in(text) -> set`, `grounded(prose, result_df) -> (bool, unguarded[])`
  (every numeric token in prose must match a value/derivable aggregate in the result set, within
  tolerance); `faithfulness(prose, context) -> 0..1` (LLM-judge claim ratio); `verify(prose) -> prose'`
  (CoVe 4-step). Narration that fails grounding is regenerated or down-ranked.
- **`cache.py`** — content-addressed cache (hash of prompt+model) in a DuckDB table, so reruns and the
  monthly brief/skill-extraction batches are idempotent and cheap.
- **`eval/`** — gold question→SQL→result-set sets and a runner computing execution accuracy
  (datacompy result compare) and faithfulness; a CI-runnable `pytest` gate.

## 5. Features (each: research track → build → eval gate)

**Phase 1 — Text-to-SQL Q&A** (`features/ask.py`, page `ask.py`)
Schema-linked prompt → LLM SQL → `sql_guard.validate` → `run_guarded` → on error `self_correct` →
narrate result with `grounding.grounded` enforced. UI shows the answer, the numbers, **and the SQL**
(auditability). Eval gate: execution accuracy ≥ target on a ≥20-question gold set; 100% numeric-grounding.

**Phase 2 — Monthly market brief** (`features/brief.py`, pipeline step)
Feed the four computed views' numbers → grounded narration → faithfulness gate → render/export a
branded monthly "Toronto Job Market" brief. Batch/cached (cheap). Eval gate: faithfulness ≥ threshold,
zero ungrounded numbers.

**Phase 3 — LLM skill extraction** (`features/skills_llm.py`, pipeline step)
Batch structured extraction (JSON schema/tool-use) over titles → Pydantic-validated skills + seniority
+ implied competencies → written to `job_skills` alongside the flashtext baseline (A/B). Haiku + prompt
caching + Batch API. Eval gate: precision ≥ flashtext on a labeled sample; cost/run within budget.

**Phase 4 — Resume/profile → role match** (`features/role_match.py`, page extension)
Parse resume (structured) → embed → Qdrant hybrid retrieve (dense + BM25, RRF) → fuse with structured
demand/salary → ranked roles + gaps. Eval gate: top-k relevance on a held-out profile set.

**Phase 5 — Grounded advisor chat** (`features/advisor.py`, page `advisor.py`)
RAG over DuckDB-derived facts + the Q&A tool; CoVe on answers; refuses when unsupported. Eval gate:
faithfulness gate; correct refusal on out-of-scope asks.

## 6. Evaluation strategy

- **Text-to-SQL:** gold `question → reference SQL → result set`; metric = execution accuracy
  (result-set equality via datacompy), not string match. Plus numeric-grounding = 100%.
- **Narration/brief/advisor:** faithfulness (claim ratio) **and** deterministic numeric-grounding
  (catches transposed/invented figures the claim metric can miss — the research's key open question).
- **Skill extraction:** precision/recall vs. a hand-labeled sample of titles, A/B against flashtext.
- All eval sets live in `eval/gold/`; runners are `pytest`-gated so a phase can't be "done" while failing.

## 7. Cost & ops

- Hard per-run token budget in `gateway.py`; batch features default to Haiku + caching + Batch API.
- DuckDB response cache → reruns are free; only new postings/questions cost tokens.
- Secrets via `.env` (gitignored): `LLM_PROVIDER`, `ANTHROPIC_API_KEY`/`OPENAI_API_KEY`, per-tier model IDs.
- Interactive features (Q&A, advisor) need keys in the deploy env; batch features run in the pipeline.

## 8. Repository structure (additions)

```
src/llm/
  __init__.py  gateway.py  schema.py  sql_guard.py  grounding.py  cache.py
  features/  ask.py  brief.py  skills_llm.py  role_match.py  advisor.py
  eval/  runner.py  gold/ (*.json gold sets)
streamlit_app/pages_impl/  ask.py  advisor.py
tests/llm/  test_gateway.py test_sql_guard.py test_grounding.py test_eval_*.py
.env.example  (extended with LLM_* vars)
```

## 9. Phasing & stop points

One spec, **phased plan** — each phase ships working software and is independently valuable:
- **Phase 0** foundation (no user-facing change; unblocks everything).
- **Phase 1** Q&A is the natural first shippable and the strongest portfolio demo.
- Phases 2–5 layer on in value order; you can stop after any phase.

## 10. Risks & open questions (→ become research spikes in the plan)

1. **DuckDB analytical SQL** (window functions, CTEs) differs from BIRD/Spider's transactional schemas —
   measure text-to-SQL accuracy on *our* schema before trusting it (Phase 1 spike).
2. **Numeric hallucination detection** — confirm the deterministic numeric-grounding check catches
   transposed/invented numbers the faithfulness metric misses (Phase 0/1 spike). *Research says build it.*
3. **Skill-extraction cost/accuracy crossover** — few-shot+cache vs. light fine-tune; measure before
   committing to fine-tuning (Phase 3 spike).
4. **Embedding model + fusion** — which embedding best captures role semantics; re-rank vs. weighted vs.
   filter-then-rank for fusing with demand/salary (Phase 4 spike).
5. **Cost overrun** — mitigated by hard budget guard, caching, Batch API, Haiku tiering.
