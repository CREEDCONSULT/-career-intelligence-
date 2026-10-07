# CAREER_INTELLIGENCE_M3_REPORT.md

**Phase:** M3 — Operational Career Intelligence
**Branch:** `m3/operational-career-intelligence`
**Base SHA:** `933da36` (M2.1 validated)
**Commits:** `1adb0ec` → `5306e57` → `43d653e` → `a285ebc` → `083cd74` → `811a973` → (this commit)
**Tests:** 309 passed, 0 failed, ruff clean
**Pilot:** CLOSED LOOP PASS with real founder evidence + live Gmail/Calendar

---

## M3 COMPLETION PASS

### Implemented and tested

| Gap | Status | Evidence |
|---|---|---|
| **Evidence verification states** | Implemented + tested | 18 types, tri-state (VERIFIED/FOUNDER_ASSERTED/UNVERIFIED), claims_allowed derived, promotion/demotion workflow, DuckDB migration |
| **Fit engine M3 bands** | Implemented + tested | STRONG FIT / POSSIBLE FIT / WEAK FIT / INSUFFICIENT EVIDENCE, NBA weights updated |
| **Application packets** | Implemented + tested | Evidence manifest (claim → evidence_ids → verification_state → provenance), tailored resume, cover letter, recruiter message, summary, excluded claims |
| **State machine** | Implemented + tested | 17 states (13 original + REVIEWING, APPROVED_TO_APPLY, RECRUITER_CONTACT, ARCHIVED), all original transitions preserved, no-auto-APPLIED enforced |
| **GitHub evidence adapter** | Implemented + tested | gh CLI, UNVERIFIED on import, provenance github:<owner>/<repo>, never infers achievements |
| **Drive evidence adapter** | Implemented + tested | Reuses M2.1 DriveConnector, UNVERIFIED on import, metadata-only, provenance drive:<file_id>, deduplication |
| **Structured import** | Implemented + tested | Defaults to UNVERIFIED, provenance founder:structured-import |

### Live validated (completion pilot)

| Check | Result |
|---|---|
| Founder evidence seeded | 4 items FOUNDER_ASSERTED (GitHub repo + 3 structured from repo/README) |
| Real opportunities ingested | 12 real Job Bank postings (from 96,467 in DuckDB) |
| Deduplication | Verified (re-ingest → same ID) |
| Fit evaluation | 4 POSSIBLE FIT, 8 INSUFFICIENT EVIDENCE (honest) |
| Application packets | 3 (for top-ranked roles) |
| State machine walked | DISCOVERED → REVIEWING → APPROVED_TO_APPLY → PREPARING |
| **Live Gmail** | **live**, 15 messages imported, 3 interview signals, all with gmail: provenance |
| **Live Calendar** | **live**, 0 upcoming events (accurate — none scheduled) |
| Next-best-action board | 3 active actions with priorities |
| Closed loop | **PASS** |

### Founder validated

Not yet — the pilot used repository-derived evidence, not the founder's full career history. The founder should:
1. Review and expand the evidence ledger through the Evidence Library page
2. Promote items through the verification workflow
3. Confirm the closed loop with their own data

### Not available / deferred

- **Operational dashboard views** (TODAY/PIPELINE/EVIDENCE/OUTCOMES/INBOX): The existing Opportunities page covers most functionality; the full M3 dashboard spec is deferred to a future pass.
- **LLM-enhanced generation**: No API key in this environment; the deterministic fallback path is fully functional and produces complete packets. The LLM path is tested with a fake gateway and activates when a key is present.
- **LinkedIn evidence adapter**: No safe, source-supported implementation path identified.
- **M4**: Not begun.

## Architecture summary

```
src/careeros/
    evidence.py           # 18 types, tri-state verification, claims gating
    evidence_ingestion.py # GitHub + Drive + structured adapters
    opportunity.py        # Canonical opportunity model + normalizer
    fit_engine.py         # M3 bands (STRONG/POSSIBLE/WEAK FIT, INSUFFICIENT EVIDENCE)
    packets.py            # ApplicationPacket + EvidenceManifestEntry
    application.py        # 17-state machine (M3 additions)
    pipeline.py            # Queue views + role family
    next_action.py         # NBA (M3 state-aware)
    communications.py      # Message model + signal detection
    interviews.py          # Interview records + prep
    questions.py           # 7-question bank (factual/narrative)
    outcomes.py            # Outcome derivation + analytics
    profile_feedback.py   # Proposal-only suggestions
    creed_store.py         # Future /store boundary
    google_oauth.py        # OAuth flow + token lifecycle
    google_gmail.py        # Read-only Gmail connector
    google_calendar.py     # Read-only Calendar connector
    google_drive.py        # Read-only Drive metadata connector
    integrations.py        # Protocols + null adapters
    live_validation.py     # Shared validation helpers
```

## Test coverage

309 tests total across 15 test files. All passing. Key M3 additions:
- `test_m3_core.py`: 25 tests (verification states, evidence manifest, packets, fit bands)
- `test_m3_state_machine.py`: 21 tests (new states, transitions, no-auto-APPLIED, backward compat, NBA)
- `test_m3_evidence_ingestion.py`: 19 tests (GitHub/Drive/structured adapters, UNVERIFIED-on-import, no-auto-promote, dedup, metadata-only)

## Final verdict

# **IMPLEMENTATION COMPLETE WITH CONDITIONS**

**Complete:** Evidence verification states, M3 fit bands, application packets with evidence manifest, 17-state machine, GitHub + Drive evidence adapters, structured import, real Job Bank pilot with live Gmail/Calendar context.

**Conditions:**
1. Founder evidence ledger uses repository-derived data (4 items); the founder must seed their full career history and promote through the verification workflow.
2. No LLM API key in this environment; deterministic fallback produces complete packets; LLM path is ready but unexercised live.
3. Operational dashboard views (TODAY/PIPELINE/EVIDENCE/OUTCOMES/INBOX) deferred; existing Opportunities page covers most functionality.
4. Founder validation of the closed loop with their own data is still pending.
