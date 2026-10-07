# CAREER_INTELLIGENCE_M2_1_GOOGLE_OPERATIONS_REPORT.md

**Phase:** M2.1 — Google Operations (Gmail / Calendar / Drive read-only)
**Branch:** `m2.1/google-operations`
**Pre-finalization commit:** `b126860`
**Working tree:** clean after finalization commit
**Scope:** Smallest production-grade implementation that makes Google integration genuinely real while preserving deterministic/null-adapter fallbacks.

---

## 1. Executive verdict

**VALIDATED WITH CONDITIONS** — All three Google connectors (Gmail/Calendar/Drive) are live, read-only, least-privilege, provenance-tracking, and independently verified against the real Google APIs on this machine. 48/48 targeted tests pass. The two conditions are inherited (repo-wide lint debt and a local DuckDB data-gap), not M2.1 failures.

## 2. Branch and commits

| Item | Value |
|---|---|
| Branch | `m2.1/google-operations` |
| Commit before report update | `b126860` |
| Final validation commit | (set after commit) |
| Main merge commit | (set after merge) |

## 3. Targeted Google tests

```
pytest -q tests/careeros/test_google_connectors.py tests/careeros/test_google_gmail.py tests/careeros/test_google_oauth.py

48 passed in 0.49s
```

All 48 tests pass. Five offline-behavior tests were updated during finalization to mock `load_tokens` → `None`, making them deterministic regardless of whether the founder's real tokens are present on the execution machine (they are, which initially caused the offline tests to fail against live connectors — confirming the integration works).

## 4. Targeted Ruff

```
ruff check src/careeros/google_oauth.py src/careeros/google_gmail.py src/careeros/google_calendar.py src/careeros/google_drive.py scripts/google_authorize.py scripts/google_smoke_test.py tests/careeros/test_google_connectors.py tests/careeros/test_google_gmail.py tests/careeros/test_google_oauth.py

All checks passed!
```

## 5. OAuth live status (independently verified)

`python scripts/google_authorize.py --status` on this machine:

```
oauth:    configured=true, authorized=true, status=live
gmail:    configured=true, authorized=true, status=live
calendar: configured=true, authorized=true, status=live
drive:    configured=true, authorized=true, status=live
```

## 6. Actual granted scopes

```
https://www.googleapis.com/auth/gmail.readonly
https://www.googleapis.com/auth/calendar.readonly
https://www.googleapis.com/auth/drive.metadata.readonly
```

All three end in `.readonly`. No write-capable scope is present. Verified by unit tests.

## 7. Live smoke test (independently verified)

`python scripts/google_smoke_test.py` on this machine:

```
OAuth: live
Gmail: live | send blocked: True
Calendar: live | create blocked: True
Drive: live | upload blocked: True
Overall: PASS
  Gmail smoke: 7 queries, 15 threads found
  Calendar smoke: 0 events, 0 interview-relevant
  Drive smoke: 100 files, 1 career artifacts
```

## 8. Gmail bounded-query behavior

Seven bounded career-signal queries executed against live Gmail:
- application_acknowledgement, recruiter_contact, interview_invitation, assessment, rejection, offer, scheduling_change
- All queries include `-in:spam`
- No broad inbox harvesting (`in:inbox` / `label:all` never used)
- 15 threads found across all queries (live data)
- Metadata-first: body NOT duplicated; only sender/subject/timestamp/signals imported

## 9. Gmail → CommunicationStore proof (independently reproduced)

Isolated DuckDB (`data/processed/m2_1_google_live_validation.duckdb`), `limit_per_query=2`:

```
First import: 10 messages, 10 unique thread_refs
  provenance values: [gmail:application_acknowledgement, gmail:interview_invitation,
                     gmail:recruiter_contact, gmail:rejection, gmail:scheduling_change]
  all thread_refs start with gmail:: True
Second import: 10 messages, 10 unique thread_refs
  duplicates of first-import refs: 0
  no row-level duplicates: True
IDEMPOTENCY: PASS
OVERALL: PASS
```

## 10. Provenance proof

Every imported message carries:
- `thread_ref` = `gmail:thread/<thread_id>` (format verified, all unique)
- `provenance` = `gmail:<signal_name>` (5 distinct signal types observed in live data)

## 11. Idempotency / duplicate proof

- First import: 10 messages → 10 unique `thread_ref` values
- Second identical import: 0 new rows, 0 duplicates, row count stable
- Thread-level deduplication by `thread_ref` confirmed

## 12. Calendar live status

- Connector live, read-only
- 0 upcoming events in the 14-day window at time of smoke test (no interviews scheduled — correct behavior, not a failure)
- `create_event()` raises `PermissionError` (verified by live smoke + unit test)

## 13. Drive live status

- Connector live, metadata-only
- 100 files listed, 1 identified as a career artifact (deterministic pattern + safe mime-type)
- `upload()` raises `PermissionError` (verified by live smoke + unit test)

## 14. Write prohibition (code + tests + live smoke)

| Operation | Enforcement | Test | Live smoke |
|---|---|---|---|
| Gmail `send()` | raises `PermissionError` | `test_send_always_raises` | `send blocked: True` |
| Calendar `create_event()` | raises `PermissionError` | `test_calendar_create_event_always_raises` | `create blocked: True` |
| Drive `upload()` | raises `PermissionError` | `test_drive_upload_always_raises` | `upload blocked: True` |

No email was sent, no calendar event was created, no Drive file was mutated.

## 15. Secrets hygiene

| Check | Result |
|---|---|
| `data/processed/google_credentials.json` gitignored | ✓ (`git check-ignore` confirms) |
| `data/processed/google_tokens.json` gitignored | ✓ |
| No credential/token file in tracked files | ✓ (`git ls-files` confirms) |
| No credential/token file in staged diff | ✓ |
| Isolated validation DB not staged | ✓ (removed after proof) |
| No secrets printed in any validation output | ✓ (counts only) |

## 16. Inherited / non-M2.1 conditions

1. **Repo-wide lint debt**: `ruff check .` produces findings in `.recovery/` backups and older legacy code. This is pre-existing recovery/legacy debt, not an M2.1 failure. Targeted Ruff (M2.1 files only) passes cleanly.
2. **Local `job_skills_llm` gap**: The local DuckDB in this Downloads checkout does not contain the `job_skills_llm` table (the founder's production machine does — verified in the M2 founder validation). This causes one pre-existing test failure (`test_build_role_docs_from_real_db`). Not caused by M2.1.

## 17. Final verdict

# **VALIDATED WITH CONDITIONS**

**Validated:** All three Google connectors are live, independently verified against real Google APIs on this machine. Read-only enforcement confirmed in code, unit tests, and live smoke. Provenance, idempotency, and bounded queries all verified. Secrets hygiene confirmed. 48/48 targeted tests pass.

**Conditions (inherited, not M2.1 failures):**
1. Repo-wide inherited lint debt exists (not M2.1-scoped)
2. Local checkout lacks `job_skills_llm` table (known local data-state issue)

## 18. Recommendation on push/merge/tag

**Push, merge, and tag** — all targeted M2.1 acceptance gates are green. The implementation is production-grade and live-verified. The inherited conditions are documented and unrelated to Google Operations.
