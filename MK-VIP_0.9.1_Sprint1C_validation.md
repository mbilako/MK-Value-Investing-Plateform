# MK-VIP 0.9.1 — Sprint 1C validation report

Date: 2026-07-27

## Scope
Validation of the supplied `MK-VIP_0.9.1_backend_hardening.zip` after the Sprint 1C hardening work.

## Implemented controls verified from source
- Per-user daily AI quota, configurable via `AI_DAILY_QUOTA`, default 20.
- Persistent PostgreSQL quota table with a unique `(user_id, period_start)` constraint.
- Atomic quota increment guarded by `request_count < daily_limit`.
- HTTP 429 response with `Retry-After: 86400` when the daily quota is exhausted.
- Per-user AI cache with configurable TTL, default 3600 seconds.
- Cache key is deterministic and includes mode, question, company identifiers and source identifiers/timestamps.
- Cache is checked before quota consumption, so a cache hit does not consume quota.
- The three AI modes use the same guarded `/api/v1/ai/analyses` route.
- AI provider is constrained to MK-VIP context and validates cited source identifiers.

## Additional correction made
`tests/test_ai_analyst_api.py` referenced `uuid.UUID` without importing `uuid`. The missing import was added.

## Validation performed
- Python compilation of all backend source files: PASS.
- Python compilation of all backend test files: PASS.
- Static source inspection of quota, cache, migration, AI route, provider and tests: PASS.

## Test-suite blocker
The supplied execution environment is missing:
- `pwdlib`
- `aiosqlite`

Therefore the full pytest suite cannot be collected/executed in this environment. This is an environment/dependency blocker, not evidence of a test failure in the Sprint 1C code.

## Final status
Sprint 1C implementation: READY FOR DEPENDENCY-RESTORED CI
Full regression suite: NOT YET VERIFIED
GitHub push/merge: NOT performed
