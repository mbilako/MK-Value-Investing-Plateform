# Final review fixes report — MK-VIP v0.9

Date: 2026-07-26

## Findings resolved

1. FastAPI's default request-validation response included Pydantic's submitted
   `input`, which could reflect registration or login passwords. A centralized
   handler now preserves the 422 `detail` contract while recursively removing
   every `input` key from all validation errors.
2. Same-owner company creation had a check-then-insert race. The SQLAlchemy
   repository now rolls back every create-time `IntegrityError`, translates
   only PostgreSQL constraint `uq_companies_owner_ticker` or SQLite's exact
   `companies.owner_id, companies.ticker` equivalent, and propagates unrelated
   integrity failures. The companies route maps the domain collision to 409.
3. An explicit unknown or foreign `valuation_id` returned 409. Explicit IDs now
   use an owner-and-company-scoped lookup and return the same non-leaking 404
   for unknown and foreign rows. The no-explicit-valuation path retains 409
   when no calculable latest valuation exists, and explicit cross-year
   valuations retain the prior 409 behavior.
4. Session duration and login lock settings now use Pydantic `PositiveInt`, so
   zero and negative values fail during settings construction.

## RED evidence

- Auth validation: 2 failures. Both register and login 422 responses contained
  the exact 129-character submitted password under `input`.
- Configuration: 6 failures. Zero and negative values were accepted for all
  three security settings.
- Duplicate ticker:
  - SQLite emitted the raw unique `IntegrityError`.
  - A non-target unique error remained pending because the repository did not
    roll back.
  - A repository domain collision escaped the API instead of returning 409.
- Valuation isolation:
  - Unknown explicit ID returned 409 instead of 404.
  - Foreign explicit ID returned 409 instead of 404.
  - During preservation review, an explicit valuation from another fiscal year
    incorrectly produced a score; its new regression failed with 201 instead
    of the existing 409 contract.

Each failure was observed before its corresponding production change.

## GREEN and verification evidence

Focused backend regressions:

```text
Auth secret sanitization: 2 passed
Positive configuration: 6 passed
Repository translation/rollback/pass-through: 2 passed
Companies API: 4 passed
Scores API: 4 passed
Isolation focus: 2 passed
PostgreSQL concurrency: 1 collected, 1 skipped locally
```

Frontend structured-error compatibility:

```text
src/api/client.test.ts: 8 passed
```

Static analysis:

```text
python -m ruff check .
All checks passed!
```

Fresh full backend suite, with pytest's cache provider disabled:

```text
105 passed, 3 skipped in 10.94s
```

The three skips are PostgreSQL-only integration cases guarded by
`MKVIP_TEST_POSTGRES_URL`: migration ownership, concurrent first registration,
and the new concurrent same-owner ticker creation.

`git diff --check` exited successfully before commit.

## PostgreSQL limitation

Docker and a local PostgreSQL service are unavailable in this managed
environment, so the new real PostgreSQL race could not execute locally. It is
collected and CI-ready. The existing backend CI job already supplies
PostgreSQL 17, sets `MKVIP_TEST_POSTGRES_URL`, upgrades Alembic to head, and
runs the complete pytest suite.

## Self-review

- PostgreSQL matching reads the exact constraint name from the driver
  diagnostic/cause chain; SQLite matching requires the exact composite unique
  error text.
- Near-match SQLite `companies.ticker` uniqueness is tested as pass-through.
- Both translated and unrelated integrity failures are rolled back, proven by
  successful writes and exact persisted contents after each failure.
- Valuation lookup includes valuation ID, company ID, and current owner ID.
- Sanitization is recursive and applies to every FastAPI request-validation
  error, while retaining `type`, `loc`, `msg`, `ctx`, and status 422.
- No design specification or implementation-plan file was modified.

## Commit

- Base SHA: `f51cd10`
- Fix-wave SHA: the single commit containing this report; record its resolved
  SHA with `git rev-parse HEAD` (a Git commit cannot contain its own hash
  without changing that hash).
