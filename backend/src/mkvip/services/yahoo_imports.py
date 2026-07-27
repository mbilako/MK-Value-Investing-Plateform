from __future__ import annotations

import threading
import uuid
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager


class YahooImportInProgressError(Exception):
    """Raised when an import already owns the same company slot."""


class YahooImportLimitError(Exception):
    """Raised when a user has reached their concurrent import limit."""


class YahooImportAdmission:
    def __init__(self, *, per_user_limit: int) -> None:
        self._per_user_limit = per_user_limit
        self._lock = threading.Lock()
        self._active_users: Counter[uuid.UUID] = Counter()
        self._active_companies: set[tuple[uuid.UUID, uuid.UUID]] = set()

    @contextmanager
    def admit(
        self,
        user_id: uuid.UUID,
        company_id: uuid.UUID,
    ) -> Iterator[None]:
        company_key = (user_id, company_id)
        with self._lock:
            if company_key in self._active_companies:
                raise YahooImportInProgressError
            if self._active_users[user_id] >= self._per_user_limit:
                raise YahooImportLimitError
            self._active_companies.add(company_key)
            self._active_users[user_id] += 1

        try:
            yield
        finally:
            with self._lock:
                self._active_companies.remove(company_key)
                self._active_users[user_id] -= 1
                if self._active_users[user_id] == 0:
                    del self._active_users[user_id]
