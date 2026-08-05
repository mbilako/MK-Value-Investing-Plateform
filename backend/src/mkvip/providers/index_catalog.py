from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from mkvip.providers.euronext import EuronextIndexProvider
from mkvip.providers.global_indices import PublicIndexProvider
from mkvip.schemas.index import IndexCompositionRead, IndexSummaryRead


class IndexProvider(Protocol):
    def list_indices(self) -> list[IndexSummaryRead]: ...

    async def get_composition(self, code: str) -> IndexCompositionRead: ...


class IndexCatalogProvider:
    def __init__(self, providers: Sequence[IndexProvider] | None = None) -> None:
        self.providers = tuple(
            providers or (EuronextIndexProvider(), PublicIndexProvider())
        )

    def list_indices(self) -> list[IndexSummaryRead]:
        return [
            index
            for provider in self.providers
            for index in provider.list_indices()
        ]

    async def get_composition(self, code: str) -> IndexCompositionRead:
        normalized = code.upper().replace("-", "").replace(" ", "")
        for provider in self.providers:
            if any(index.code == normalized for index in provider.list_indices()):
                return await provider.get_composition(normalized)
        raise KeyError(code)
