#!/usr/bin/env python3
"""Safely model the automatic Yahoo import's executor queue behavior.

This program performs no network or application requests. It uses local,
blocking stub functions to show how concurrent imports can submit more work
than a shared executor can run, even when every import will eventually be
rejected by a late duplicate check.
"""

from __future__ import annotations

import argparse
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable


class TrackingExecutor(ThreadPoolExecutor):
    def __init__(self, max_workers: int) -> None:
        super().__init__(max_workers=max_workers, thread_name_prefix="poc-yahoo")
        self._tracking_lock = threading.Lock()
        self.submitted = 0
        self.started = 0
        self.completed = 0
        self.active = 0
        self.peak_active = 0

    def submit(
        self,
        function: Callable[..., Any],
        /,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        with self._tracking_lock:
            self.submitted += 1

        def tracked() -> Any:
            with self._tracking_lock:
                self.started += 1
                self.active += 1
                self.peak_active = max(self.peak_active, self.active)
            try:
                return function(*args, **kwargs)
            finally:
                with self._tracking_lock:
                    self.active -= 1
                    self.completed += 1

        return super().submit(tracked)

    def snapshot(self) -> tuple[int, int, int, int, int]:
        with self._tracking_lock:
            queued = self.submitted - self.started
            return (
                self.submitted,
                self.started,
                self.active,
                queued,
                self.completed,
            )


def blocking_yahoo_stub(
    request_id: int,
    operation: str,
    release: threading.Event,
) -> tuple[int, str]:
    release.wait()
    return request_id, operation


async def vulnerable_like_import(
    request_id: int,
    release: threading.Event,
) -> bool:
    for operation in ("profile", "income", "balance", "cash-flow"):
        await asyncio.to_thread(
            blocking_yahoo_stub,
            request_id,
            operation,
            release,
        )

    # Model an already-imported fiscal year. The duplicate decision is made
    # only after all four blocking provider operations have completed.
    snapshot_already_exists = True
    return snapshot_already_exists


async def wait_for_initial_queue(
    executor: TrackingExecutor,
    request_count: int,
    worker_count: int,
) -> None:
    expected_started = min(request_count, worker_count)
    for _ in range(500):
        submitted, started, _, _, _ = executor.snapshot()
        if submitted == request_count and started == expected_started:
            return
        await asyncio.sleep(0.01)
    raise RuntimeError("the local executor did not reach the expected state")


async def demonstrate(request_count: int, worker_count: int) -> None:
    loop = asyncio.get_running_loop()
    executor = TrackingExecutor(max_workers=worker_count)
    loop.set_default_executor(executor)
    release = threading.Event()

    tasks = [
        asyncio.create_task(vulnerable_like_import(request_id, release))
        for request_id in range(request_count)
    ]

    await wait_for_initial_queue(executor, request_count, worker_count)
    submitted, started, active, queued, _ = executor.snapshot()
    print("[+] safe local stub: no HTTP and no Yahoo traffic")
    print(
        f"[+] initial state: submitted={submitted} started={started} "
        f"active={active} queued={queued}"
    )
    print(
        "[+] queue growth equals concurrent requests minus available "
        "executor workers"
    )

    release.set()
    duplicate_results = await asyncio.gather(*tasks)
    _, _, _, _, completed = executor.snapshot()
    print(
        f"[+] completed blocking operations={completed} "
        f"(requests x four operations={request_count * 4})"
    )
    print(
        f"[+] late duplicate decisions="
        f"{sum(duplicate_results)} (modeled HTTP 409 responses)"
    )
    print(f"[+] peak active executor workers={executor.peak_active}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Model unbounded admission to the Yahoo import executor."
    )
    parser.add_argument("--requests", type=int, default=12)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    if not 1 <= args.requests <= 200:
        parser.error("--requests must be between 1 and 200")
    if not 1 <= args.workers <= 32:
        parser.error("--workers must be between 1 and 32")
    return args


if __name__ == "__main__":
    options = parse_args()
    asyncio.run(demonstrate(options.requests, options.workers))
