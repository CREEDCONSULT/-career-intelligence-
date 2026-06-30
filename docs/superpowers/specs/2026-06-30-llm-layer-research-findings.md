# LLM Intelligence Layer — Deep-Research Findings (2026-06-30)

Source: deep-research harness (5 angles, 23 sources fetched, 108 claims, 25 verified via 3-vote
adversarial check → 23 confirmed, 2 refuted). Treat definitions/mechanisms as high-confidence; exact
benchmark/cost numbers as a 2025–2026 snapshot.

## Verified findings

1. **Text-to-SQL accuracy** is maximized by **vector-based schema linking + execution-guided
   self-correction + iterative schema-grounded prompt guardrails**. Small fine-tuned 7B-class models
   (LitE-SQL 72.1% BIRD / 88.45% Spider; Arctic-Text2SQL-R1) now rival far larger models. Guardrails
   from error analysis beat case-specific few-shot dumps.
   — arxiv.org/pdf/2510.09014 · snowflake.com/.../arctic-text2sql-r1 · docs.ragas.io/.../text2sql

2. **SQLGlot** — no-dependency Python SQL parser/transpiler/optimizer, **native DuckDB dialect**.
   Static syntax validation via `parse_one()` + try/except → pre-execution guarding. Caveat: validates
   syntax/dialect only, not semantics (won't catch nonexistent columns) → still need execution-guard.
   — github.com/tobymao/sqlglot

3. **Grounding** — claim decomposition + per-claim verification; **faithfulness = supported-claims /
   total-claims** (Ragas & DeepEval, identical reference-free definition). **Chain-of-Verification**
   (CoVe) 4-step (draft → plan checks → answer independently → regenerate) reduces hallucination with
   no tools. For analytics, the SQL result set IS the context.
   — arxiv.org/pdf/2309.11495 · docs.ragas.io/.../faithfulness · deepeval.com/docs/metrics-faithfulness

4. **Eval** — use **execution accuracy** (run predicted vs. gold SQL, compare *result sets* with
   datacompy — not SQL string match) for text-to-SQL; claim-ratio **faithfulness** for narration.
   — docs.ragas.io/.../text2sql · deepeval.com/docs/metrics-faithfulness

5. **LiteLLM** — recommended provider-agnostic gateway: one OpenAI-format interface to 100+ providers
   (Claude + OpenAI + local Ollama/vLLM/LM Studio), SDK or proxy, with cost tracking, retry/fallback
   routing, load balancing, guardrails.
   — github.com/BerriAI/litellm · docs.litellm.ai/docs/providers

6. **Anthropic prompt caching** — reads 0.1× (~10× cheaper), writes 1.25× (5-min) / 2× (1-hr). Cache
   the large shared prefix (schema/instructions/few-shot), vary per-item. **Batch API** = 50% off, and
   **stacks with caching** → primary levers for high-volume batch.
   — platform.claude.com/docs/en/build-with-claude/prompt-caching

7. **Skill extraction** — fine-tuned small LLM (Skill-LLM, LLaMA-3-8B 64.8% F1) ≥ supervised NER ≫
   few-shot GPT-4 (27.8% F1). Practical at-scale pattern: **structured JSON/tool-use + Pydantic
   validation + Haiku + caching + Batch**; consider light fine-tune only if accuracy demands it.
   — arxiv.org/html/2410.12052v1

8. **Semantic matching** — Qdrant **hybrid** (dense embeddings + sparse BM25, fused via **RRF**),
   two-stage retrieve→rerank; combine with structured demand/salary downstream (filter-then-rank or
   weighted). all-MiniLM-L6-v2 is a lightweight default; stronger models substitutable.
   — qdrant.tech/documentation/tutorials-basics/reranking-hybrid-search · qdrant.tech/articles/hybrid-search

## Refuted (did NOT survive verification)

- GRPO/RL with execution-aligned reward as **the** core driver of text-to-SQL gains (0–3). → not our approach anyway.
- CoVe "factored verification" (answers not attending to draft) as **the** key driver (1–2). → keep the
  4-step structure; don't rely on that single sub-mechanism.

## Open questions → become plan spikes

1. Text-to-SQL accuracy on **our DuckDB analytical schema** (window functions/CTEs) vs. transactional
   BIRD/Spider — measure on our own gold set (Phase 1).
2. Skill extraction **accuracy/cost crossover**: few-shot+caching vs. light fine-tune (Phase 3).
3. Best **embedding model** for job-role semantics + best **fusion** of hybrid scores with
   demand/salary (Phase 4).
4. Do faithfulness metrics catch **numeric** hallucinations (wrong/transposed figures) specifically, or
   is a **deterministic numeric-grounding check** required as a complement? → **Build the deterministic
   check** (Phase 0); treat faithfulness as secondary (Phase 1).

## Caveats

Benchmark leaderboards move fast (Agentar-Scale-SQL hit 81.67% BIRD by Sept 2025); several figures are
dev-set or vendor-reported (backed by arXiv). Skill-extraction evidence is one paper on harsh exact-span
F1. Qdrant fusion-with-structured-signals and CoVe→narration mapping are sound architectural
extrapolations, not separately benchmarked. Pricing multipliers are current but will drift.
