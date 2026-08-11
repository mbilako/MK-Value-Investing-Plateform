# Automatic Yahoo imports admit unbounded blocking work

## Executive Summary

MK Value Investing Platform exposes an authenticated automatic financial import
route that performs four synchronous Yahoo Finance operations before checking
whether the returned fiscal year already exists. The synchronous calls are
offloaded with `asyncio.to_thread`, but the application applies no explicit
transport timeout, end-to-end deadline, per-user quota, concurrency admission
limit, or work budget on this path. A standard authenticated user can therefore
send concurrent imports for a company they own and cause blocking Yahoo work to
accumulate in an API worker.

The strongest demonstrated impact is availability degradation for Yahoo imports
and other work sharing that worker's default executor. The source does not prove
an outage of every asynchronous API route, cross-account data access, or data
corruption. Authentication, owner scoping, sequential provider calls, a bounded
thread count, and assumed reverse-proxy limits all reduce practical impact, but
none of them bounds work admitted by the application or guarantees that a
thread already running through `asyncio.to_thread` is stopped.

This issue is **low severity (P3)**: impact is medium, because contention can
cross the attacker's account and consume a shared service resource, while
likelihood is medium because exploitation requires concurrent requests and
sufficient upstream latency. The weakness maps to CWE-400 and CWE-770.

I reviewed vulnerable revision
`f04addb86654c1f93758f936132cae0fe08c17f1` directly. No fixed revision was
available. I also prepared and statically reviewed the safe local demonstrator
distributed with this report, but I did not execute the application or the
demonstrator because a usable Python interpreter was unavailable in the review
environment. No live service or Yahoo endpoint was contacted.

## Background

The automatic import feature is reached through:

```text
POST /api/v1/companies/{company_id}/financials/automatic
```

The route is available to a normal authenticated user. The injected repository
is scoped to that user's data, so looking up `company_id` first enforces the
important ownership boundary. This prevents an attacker from importing into
another account, but the outbound Yahoo work and executor capacity remain
shared runtime resources.

The relevant route begins in
`backend/src/mkvip/api/routes/financials.py:92`:

```python
async def import_financials_automatically(
    company_id: uuid.UUID,
    repository: Repository,
    provider: Provider,
) -> FinancialAnalysisRead:
    company = await repository.get_by_id(company_id)
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entreprise introuvable.",
        )

    try:
        payload = await load_latest_snapshot(provider, company.ticker)
    except ProviderDataError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
```

We first resolve an owned company and carry its stored ticker into
`load_latest_snapshot`. The caller does not control an arbitrary URL, and the
ownership check is a meaningful mitigation. The attacker does control whether
the operation is triggered, how often it is repeated, and how many requests are
in flight concurrently.

The normal successful path needs a company profile plus income statement,
balance sheet, and cash-flow data. The normalization layer obtains these
datasets sequentially:

```python
# backend/src/mkvip/providers/normalization.py:19-26
async def load_latest_snapshot(
    provider: FinancialDataProvider,
    ticker: str,
) -> FinancialSnapshotCreate:
    profile = await provider.get_profile(ticker)
    income_statements = await provider.get_income_statements(ticker)
    balance_sheets = await provider.get_balance_sheet(ticker)
    cash_flows = await provider.get_cash_flow(ticker)
```

Sequential execution means a single request normally occupies at most one
executor thread at a time. It does not, however, stop many requests from each
occupying or waiting for one thread.

## Vulnerability Details

The root control failure is at
`backend/src/mkvip/api/routes/financials.py:105`. Once the company ownership
check passes, the route starts the full remote snapshot load without first
admitting the request against a user quota, a per-company single-flight guard,
a global Yahoo concurrency limit, or a bounded request budget.

Each of the four provider methods eventually reaches `_run_yahoo`:

```python
# backend/src/mkvip/providers/yahoo.py:75-88
async def _run_yahoo(
    ticker: str,
    operation: Callable[..., Any],
    *args: object,
    **kwargs: object,
) -> Any:
    try:
        return await asyncio.to_thread(operation, *args, **kwargs)
    except ProviderDataError:
        raise
    except Exception as error:
        raise ProviderDataError(
            f"Yahoo Finance est indisponible pour {ticker.upper()}."
        ) from error
```

`asyncio.to_thread` prevents the synchronous yfinance operation from directly
blocking the event-loop thread. That is useful for responsiveness, but it is
not an admission control. There is no application deadline around the await
and no explicit timeout passed to the underlying operation. Exception
translation only runs after the synchronous call has returned or raised, so it
does not help when the operation remains slow.

We can now follow one request through the complete state transition:

```text
owned company lookup
  -> profile Yahoo operation
  -> income-statement Yahoo operation
  -> balance-sheet Yahoo operation
  -> cash-flow Yahoo operation
  -> determine latest shared fiscal year
  -> duplicate lookup
```

The duplicate lookup appears only after the payload has been assembled:

```python
# backend/src/mkvip/api/routes/financials.py:105-119
payload = await load_latest_snapshot(provider, company.ticker)

existing = await repository.get_financial_analysis(
    company_id,
    payload.fiscal_year,
)
if existing is not None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            f"Les données financières {payload.fiscal_year} existent déjà."
        ),
    )
```

This ordering is especially wasteful for repeated imports. Even when the latest
fiscal year is already present and the final response must be HTTP 409, every
request has already paid for four blocking provider operations.

With `R` concurrent requests reaching a worker that has `W` available executor
threads, up to `min(R, W)` first operations can run while the rest wait. When an
operation completes, that request submits its next operation. The application
has no code-level limit on `R`, no maximum waiting population, and no deadline
for the four-operation transaction. The number of threads may be bounded by the
executor, but bounded threads are not the same as bounded admitted work.

## Exploitability Analysis

The most realistic route is deliberately modest. We authenticate as an
ordinary user, create or select a company in our own account, and issue
concurrent automatic imports for that same company. A naturally slow or
degraded Yahoo response supplies the blocking interval. We do not need to
cross an object-authorization boundary, choose a destination URL, or control
the bytes returned by Yahoo.

If the concurrent request count exceeds available executor workers, we fill
the active slots and cause later operations to wait. The first practical
effect should be increased latency and failures for other Yahoo imports on the
same worker. Other code sharing that default executor may also be delayed.
Because worker count, executor sizing, load-balancer distribution, and proxy
limits are deployment-specific, extending this result to the entire service or
fleet would require measurement. Purely asynchronous routes need not stop
responding merely because the executor is busy.

Repeated imports for an already-present year are the cleanest amplification
case. They make the business result deterministic—a conflict—while retaining
all four upstream operations. Per-company single-flight handling would defeat
this route efficiently. Spreading requests over multiple owned companies could
avoid only a per-company guard, which is why the complete fix also needs a
per-user quota and a worker-wide Yahoo admission bound.

Several existing constraints matter:

- Authentication and owner scoping raise the cost above an anonymous request
  flood and preserve cross-account confidentiality.
- The four calls are sequential, so one import does not consume four threads
  simultaneously.
- The executor bounds active thread creation. The weakness is queued and
  long-lived work, not unlimited thread creation.
- A production reverse proxy is expected to apply rate and time limits, but no
  concrete values are established here. A client-side or proxy timeout also
  does not prove that a synchronous function already running in a thread has
  stopped.
- The attacker controls request frequency and concurrency, not Yahoo's response
  duration. Fast, reliable upstream responses reduce the contention window.

These constraints keep the finding at low severity. They do not remove the
shared-resource boundary: one standard account can still consume worker
capacity that serves other users. No evidence supports confidentiality,
integrity, secret exposure, or account compromise impact.

## Proof of Concept

The included `poc/safe_executor_queue_demo.py` is a local control-flow model. It
uses blocking stub functions and a two-thread executor; it sends no HTTP
requests, imports no application modules, and never contacts Yahoo. Each
simulated request performs four sequential blocking operations and checks for
an existing snapshot only afterward, matching the important ordering in the
vulnerable path.

From the report directory, run:

```sh
cd poc
python safe_executor_queue_demo.py --requests 12 --workers 2
```

Expected output for these arguments is:

```text
[+] safe local stub: no HTTP and no Yahoo traffic
[+] initial state: submitted=12 started=2 active=2 queued=10
[+] queue growth equals concurrent requests minus available executor workers
[+] completed blocking operations=48 (requests x four operations=48)
[+] late duplicate decisions=12 (modeled HTTP 409 responses)
[+] peak active executor workers=2
```

The initial snapshot is the important observation: two threads cap active
execution, yet all twelve requests have already submitted work, leaving ten
waiting. Increasing `--requests` grows the waiting population while
`--workers` remains fixed. The demonstrator caps requests at 200 and workers at
32 to keep accidental runs harmless.

On a corrected implementation, excess requests should be rejected before a
Yahoo task is submitted. A regression harness using the same blocking stub
should therefore observe at most the configured Yahoo capacity submitted, a
bounded or zero executor queue, and prompt HTTP 429/503 responses for requests
beyond the admission budget.

No cleanup is required. The process releases the local gate, waits for every
stub call, and exits. This PoC is intentionally diagnostic; it does not attempt
to degrade a deployed service.

## Remediation

The invariant to restore is: **before any synchronous Yahoo work is submitted,
the application must prove that the caller and worker both have remaining
budget; every admitted operation must retain its capacity slot until the
underlying thread really finishes.** A response deadline alone is insufficient
because timing out an await does not reliably terminate a synchronous function
already running in another thread.

A safe provider shape uses a dedicated executor, fail-fast bounded admission,
and a logical response deadline. The completion callback—not the request
timeout—releases capacity:

```python
import asyncio
import functools
from concurrent.futures import ThreadPoolExecutor

YAHOO_CONCURRENCY = 8
YAHOO_ADMISSION_SECONDS = 0.05
YAHOO_RESPONSE_SECONDS = 10.0

_yahoo_executor = ThreadPoolExecutor(
    max_workers=YAHOO_CONCURRENCY,
    thread_name_prefix="mkvip-yahoo",
)
_yahoo_slots = asyncio.Semaphore(YAHOO_CONCURRENCY)


def _release_yahoo_slot(future: asyncio.Future[object]) -> None:
    _yahoo_slots.release()
    if not future.cancelled():
        future.exception()  # retrieve a late exception after caller timeout


async def _run_yahoo(ticker, operation, *args, **kwargs):
    try:
        await asyncio.wait_for(
            _yahoo_slots.acquire(),
            timeout=YAHOO_ADMISSION_SECONDS,
        )
    except TimeoutError as error:
        raise ProviderDataError("Yahoo Finance est occupé.") from error

    loop = asyncio.get_running_loop()
    future = loop.run_in_executor(
        _yahoo_executor,
        functools.partial(operation, *args, **kwargs),
    )
    future.add_done_callback(_release_yahoo_slot)

    try:
        return await asyncio.wait_for(
            asyncio.shield(future),
            timeout=YAHOO_RESPONSE_SECONDS,
        )
    except TimeoutError as error:
        raise ProviderDataError(
            f"Yahoo Finance a dépassé le délai pour {ticker.upper()}."
        ) from error
```

Because a permanently blocked thread keeps its slot, new calls fail fast
instead of creating more queued Yahoo work. This bounds damage but does not
recover stuck capacity. The Yahoo HTTP transport must also have connect and
read timeouts so blocked threads eventually return. The four calls should share
one end-to-end import deadline rather than each receiving a fresh full budget.

At the route layer, add all of the following:

1. A per-user token bucket or fixed-window quota for automatic imports.
2. A per-company single-flight key that rejects or joins a duplicate import
   already in progress.
3. An idempotency/freshness check before outbound work whenever persisted
   metadata can establish that no refresh is required.
4. A worker-wide or shared distributed admission limit, depending on whether
   the desired bound is per process or service-wide.
5. HTTP 429 or 503 responses with retry guidance when admission fails.

The database duplicate check must remain as a final race-safe integrity
control, even after earlier deduplication is added.

Regression coverage should include:

- a blocking provider with more concurrent imports than the configured
  capacity, proving excess requests fail before submitting executor work;
- two simultaneous imports for the same company, proving only one provider
  transaction starts;
- one user spreading requests across several owned companies, proving the
  per-user quota still applies;
- client cancellation and response timeout, proving the provider slot is not
  released until the synchronous future actually completes;
- an operation that exceeds the transport timeout, proving bounded recovery;
- an already-present fiscal year, proving the final duplicate check remains
  race-safe and that any available freshness shortcut avoids remote work;
- a full four-operation import, proving all calls consume one shared
  end-to-end deadline rather than four independent budgets.

## Summary

The automatic import route admits a user-controlled number of Yahoo
transactions before applying its duplicate control. Each transaction performs
four synchronous provider operations through `asyncio.to_thread`, with no
application timeout, quota, concurrency admission limit, or total work budget.
We showed how concurrent requests can therefore occupy a bounded executor and
accumulate waiting work, including requests whose only eventual result is a
duplicate conflict.

The demonstrated risk is shared availability degradation, not data compromise,
which supports low severity and P3 priority under the stated medium-impact,
medium-likelihood calibration. The durable fix is layered: fail-fast admission,
per-user and per-company controls, a dedicated bounded Yahoo execution domain,
real transport timeouts, and one end-to-end import budget.

Future variant analysis should review every call routed through `_run_yahoo`,
including company search and price history, for the same admission and timeout
invariants. Deployment testing should then measure executor sizing, proxy
behavior, cancellation semantics, and worker distribution to determine the
largest realistic cross-user impact without targeting a live service.
