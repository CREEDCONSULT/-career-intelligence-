# Phase 4 (Role Match) + Phase 5 (Advisor Chat) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Complete the final two LLM-layer features from the approved 2026-06-30 plan: semantic
resume→role matching and a grounded career-advisor chat.

**Key deployment decision (research-informed):** Qdrant in **embedded local mode**
(`QdrantClient(path=...)` — no server) + **fastembed** (ONNX, no torch) for dense+sparse BM25 hybrid
with RRF fusion, per the Qdrant-documented pattern. Keeps the app deployable on Streamlit
Cloud/Railway without a vector-DB service or a 2GB torch image. Role corpus = one document per NOC
occupation (title + top LLM-extracted skills + example posting titles), ~500-800 docs — trivially
indexable at startup.

---

## Phase 4 — Resume/profile → role match

- [ ] **4.1 Deps:** add `qdrant-client[fastembed]` to pyproject/requirements; verify local-mode +
  embedding roundtrip.
- [ ] **4.2 Role corpus** (`src/llm/features/role_match.py`): `build_role_docs(con)` — per noc_code
  with ≥20 postings: doc text = NOC title + top-10 `job_skills_llm` skills + top-3 example titles;
  carry demand (posting count) + median wage payload. Test vs real DB.
- [ ] **4.3 RoleIndex:** wraps embedded Qdrant; dense (bge-small ONNX) + sparse (BM25) hybrid, RRF
  fusion via Query API prefetch; built on demand into `data/processed/qdrant/` (gitignored runtime
  artifact); `scripts/build_role_index.py` for the pipeline. Test: index 3 synthetic docs, query,
  verify expected doc ranks first.
- [ ] **4.4 match_profile:** free-text profile → (optional Haiku skill/summary extraction) → hybrid
  retrieve top-10 → fuse: `score = 0.7·semantic(norm) + 0.3·demand(norm)`; return ranked roles with
  wage, demand, matching skills (explainability). Fusion weights documented; env-tunable.
- [ ] **4.5 UI:** Role Fit page gains a "Match my profile" mode (paste resume/summary) → ranked role
  cards (title, blended score, median wage, postings, matched skills).
- [ ] **4.6 Eval gate:** 8 test profiles with expected occupations → top-5 hit rate; record in
  docs/llm-eval-results.md. Gate: ≥6/8 profiles have an expected occupation in top-5.

## Phase 5 — Grounded advisor chat

- [ ] **5.1 verify():** implement in grounding.py as draft → faithfulness(claims vs context) →
  regenerate-once loop (CoVe-style, simplified: the verification questions are the claim checks).
  Test with fake judge.
- [ ] **5.2 advisor** (`src/llm/features/advisor.py`): two-step chain —
  (1) `plan_queries(question)` → up to 2 data questions or `OUT_OF_SCOPE`;
  (2) run each through the Phase-1 `ask()` pipeline (grounded SQL answers);
  (3) `compose(question, grounded_results)` → advice using ONLY retrieved numbers, gated by
  `grounded()` against the combined result tables + `verify()` loop. Refusal path for out-of-scope.
  Tests with FakeGW: happy path, refusal, ungrounded-regeneration.
- [ ] **5.3 Chat UI** (`streamlit_app/pages_impl/advisor.py`): st.chat_input history, per-session
  message cap + daily token cap (reuse usage guards), each answer shows its data sources (SQL
  expander). Router + smoke test.
- [ ] **5.4 Eval gate:** 15 live questions (10 in-scope, 5 out-of-scope). Gate: 100% correct
  refusals; faithfulness ≥0.9 avg on in-scope; 0 ungrounded numbers. Record results.

## Final
- [ ] Full pytest/ruff/validate sweep; screenshots; README update; merge to main; push.
