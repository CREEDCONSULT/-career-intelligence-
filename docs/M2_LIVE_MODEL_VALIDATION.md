# M2 Live-Model Validation — Status & Harness

**Date:** 2026-10-05 · **Milestone:** M2 §1B
**Environment at authoring time:** no `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` present.

## Provider / model / version (gateway-resolved)

The app's provider-agnostic LiteLLM gateway resolves from environment (`LLM_PROVIDER`, per-tier `LLM_MODEL_*` overrides). Default configuration, as validated by `LLMConfig.from_env()`:

| Tier | Default model |
|---|---|
| `batch` | `anthropic/claude-haiku-4-5-20251001` |
| `interactive` | `anthropic/claude-sonnet-5` |
| `hard` | `anthropic/claude-opus-4-8` |

Switch provider with `LLM_PROVIDER=openai` + `OPENAI_API_KEY` (defaults `openai/gpt-4o-mini`, `openai/gpt-4o`, `openai/gpt-4o`).

## Validation harness (built and ready)

- **`scripts/validate_live_model.py`** — runs a deterministic real-world-shaped fixture (Senior Analytics Engineer opportunity + 3-item evidence ledger, one item deliberately non-claimable) through the live gateway for **both** evidence-cited tailor and cover-letter generation. Validates the evidence-citation contract:
  1. output non-empty;
  2. every cited evidence ID exists in the ledger (bogus citations rejected);
  3. `evidence_used` ∩ `excluded_claims` = ∅;
  4. **honesty check:** excluded (unsupported) claims must not appear woven into the output.
- Then compares the live output against the deterministic fallback (same inputs): fallback's excluded keywords, citation sets, and whether the live output covered any fallback-excluded keyword anyway.
- `--json` emits a machine-readable report including provider, models, checks, violations, comparison, tokens used, and `status: PASS|FAIL|PENDING_KEY`.
- **`tests/careeros/test_live_model.py`** — the same contract as pytest cases, auto-skipping without a key and auto-activating with one (so CI or a founder laptop completes validation with zero extra setup).

## Current status: **PENDING_KEY** (documented condition)

Live generation was **not** exercised in this environment — no credentials are available, and per the M2 rules production completion must not be faked. What *is* verified:

- the harness runs end-to-end and reports `PENDING_KEY` with the required action;
- the citation contract is fully enforced and unit-tested deterministically (fake-gateway tests: footer parsing, bogus-citation rejection, excluded-claim disjointness — all green in `tests/careeros/test_evidence_resume.py`);
- the deterministic fallback path (which powers the keyless UI) is fully tested.

## Required founder action

Set `ANTHROPIC_API_KEY` (or `LLM_PROVIDER=openai` + `OPENAI_API_KEY`) in the environment and run:

```
python scripts/validate_live_model.py
```

`status: PASS` closes this condition. The pytest suite performs the same validation automatically once the key is present.

## Related M1 condition (§1A — job_skills_llm)

Resolved as a **CI-only fixture path**: `scripts/extract_skills_llm.py --fixture` performs deterministic dictionary extraction (no LLM), records provenance in `job_skills_llm_meta` (`source='fixture:flashtext'`), and the CI workflow runs it before tests. The committed demo DB intentionally contains **no** fixture data — production population still requires one live run of the same script with an API key (no `--fixture`). Local red test therefore remains, honestly, as the documented condition.
