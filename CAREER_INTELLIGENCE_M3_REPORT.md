# CAREER_INTELLIGENCE_M3_REPORT.md

**Phase:** M3 — Operational Career Intelligence
**Branch:** `m3/operational-career-intelligence`
**Base SHA:** `933da36` (M2.1 validated)
**Commits:** `1adb0ec` (M3.1 evidence states) → `5306e57` (M3.4 fit bands) → `43d653e` (M3.6 packets)
**Tests:** 269 passed, 0 failed, ruff clean

---

## 1. Executive verdict

**IMPLEMENTATION COMPLETE WITH CONDITIONS** — The core M3 structural changes are implemented and tested (evidence verification states, M3 fit bands, application packets with evidence manifest). A real pilot with 15 Job Bank opportunities proves the closed loop works. The conditions are: (a) founder evidence ledger needs real founder data (currently seed/synthetic), (b) the pilot used only the deterministic path (no LLM key available), and (c) the operational dashboard extensions from the full M3 spec are not yet built.

## 2. What was built

### M3.1 — Evidence verification states (commit `1adb0ec`)

The Evidence model now has a tri-state verification system:

| State | Claims allowed | Promotion |
|---|---|---|
| `VERIFIED` | Yes (always) | `store.promote_to_verified(id)` |
| `FOUNDER_ASSERTED` | Only if `founder_permits_external=True` | `store.promote_to_founder_asserted(id, permit_external=)` |
| `UNVERIFIED` | No (never) | Default for new evidence |

- `claims_allowed` is derived from `verification_state` (no manual override)
- 18 evidence types (8 from M1 + 10 new for M3): contract_work, founder_work, product, case_study, technical_skill, business_consulting, github_repository, report, presentation, recommendation
- DuckDB migration adds M3 columns to pre-M3 tables (idempotent ALTER)
- Legacy `verification_status` values map to new states (backward compatible)
- New store methods: `promote_to_verified`, `promote_to_founder_asserted`, `demote_to_unverified`, `list_claimable`, `verification_summary`, `list_all(verification_state=)`

### M3.4 — Fit engine bands (commit `5306e57`)

Band labels aligned with the M3 spec:

| Old (M1/M2) | New (M3) |
|---|---|
| Strong match | STRONG FIT |
| Good match | POSSIBLE FIT |
| Fair match | WEAK FIT |
| Weak match | INSUFFICIENT EVIDENCE |

NBA fit weights and test fixtures updated accordingly.

### M3.6 — Application packets with evidence manifest (commit `43d653e`)

New module `src/careeros/packets.py`:

- `EvidenceManifestEntry`: claim → evidence_ids → verification_states → provenance → excluded
- `ApplicationPacket`: tailored_resume, cover_letter, recruiter_message, application_summary, evidence_manifest, excluded_claims, keyword_coverage, gaps, risks, fit context
- `build_application_packet()`: assembles the full packet from opportunity + evidence store; deterministic path works without an LLM key; LLM path enhances when available
- `build_evidence_manifest()`: builds the provenance chain from the fit result + evidence ledger; UNVERIFIED evidence never appears in the external manifest

## 3. Pilot results (real Job Bank data)

```
Real opportunities ingested: 15 (from 96,467 government postings)
Deduplication verified: Yes (same posting → same ID)
Fit evaluations: 15 (4 POSSIBLE FIT, 11 INSUFFICIENT EVIDENCE)
Application packets: 5 (for top-ranked opportunities)
State machine walked: DISCOVERED → REVIEWED → SHORTLISTED → PREPARING
Next-best-action board: 5 active actions with priorities
CLOSED LOOP: PASS
```

The 11 INSUFFICIENT EVIDENCE results are honest — the seeded sample evidence doesn't align with most aircraft maintenance, CAD, and retail job titles from the Job Bank. With real founder evidence (AI/data/consulting background), the distribution would shift toward POSSIBLE FIT and STRONG FIT for relevant roles.

## 4. Test coverage

269 tests total (244 existing + 25 new M3 tests):

- **Verification states (12 tests):** default-UNVERIFIED, promote-to-VERIFIED, promote-to-FOUNDER_ASSERTED (±permit), demote, verification_summary, list_claimable, list_by_state, UNVERIFIED-never-in-supported-skills, 18-types-present
- **Evidence manifest (3 tests):** matched-claims-have-evidence, excluded-claims-have-no-evidence, deterministic
- **Application packets (7 tests):** all-components-present, traceability-to-VERIFIED, excluded-claims-explicit, UNVERIFIED-not-in-manifest, no-auto-submission, keyword-coverage, fit-context
- **M3 fit bands (3 tests):** band-names-match-spec, strong-fit-coverage, insufficient-evidence-no-evidence, NBA-uses-new-names

## 5. What remains (conditions)

1. **Founder evidence ledger needs real data** — the pilot used 3 synthetic VERIFIED items; the founder must seed their actual career evidence (employment history, projects, certifications, GitHub repos, etc.) and promote items through the verification workflow.
2. **No LLM key in this environment** — the deterministic fallback path produces keyword-alignment reports and full packet structure; LLM-enhanced generation activates when a key is present (same contract, tested with fake gateway).
3. **Operational dashboard extensions** — the M3 spec calls for TODAY/PIPELINE/EVIDENCE/OUTCOMES/INBOX dashboard views; the existing Opportunities page covers most of this but the full spec dashboard is not yet built.
4. **Expanded state machine** — the M3 spec recommends additional states (REVIEWING, APPROVED_TO_APPLY, RECRUITER_CONTACT, ARCHIVED); the existing 13-state machine covers the critical path but hasn't been expanded.
5. **Evidence ingestion adapters** — GitHub/Drive/LinkedIn import adapters are specified but not yet built (the manual form and JSON import from M1/M2 work).

## 6. M2.1 boundaries preserved

- Google read-only boundaries intact (no writes, no sends, no mutations)
- All 48 Google tests pass (18 OAuth + 13 Gmail + 17 connectors)
- Secrets hygiene verified (tokens gitignored, no credential files tracked)
- Write prohibitions enforced (send/create_event/upload all raise PermissionError)

## 7. Recommendation

**IMPLEMENTATION COMPLETE WITH CONDITIONS** — The core M3 value (evidence-gated application packets with full provenance) is built, tested, and pilot-validated with real data. The founder should:
1. Seed real career evidence through the Evidence Library page
2. Promote evidence through the verification workflow (UNVERIFIED → FOUNDER_ASSERTED → VERIFIED)
3. Ingest relevant opportunities and generate packets
4. Confirm the closed loop with their own data

**Do not merge to main until founder validation. Do not tag. Do not begin M4.**
