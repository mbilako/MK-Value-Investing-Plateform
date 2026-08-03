import pytest

from mkvip.providers.base import ProviderDataIncompleteError
from mkvip.providers.sec import SecEdgarProvider


@pytest.mark.asyncio
async def test_sec_never_strips_a_foreign_exchange_suffix() -> None:
    fetch_calls: list[str] = []

    def fetch_json(url: str, user_agent: str) -> dict:
        del user_agent
        fetch_calls.append(url)
        return {}

    provider = SecEdgarProvider(
        object(),
        user_agent="MK-VIP test test@example.com",
        fetch_json=fetch_json,
    )

    with pytest.raises(
        ProviderDataIncompleteError,
        match="sans CIK explicite",
    ):
        await provider.resolve_identifier("ACA.PA")

    assert fetch_calls == []


@pytest.mark.asyncio
async def test_sec_accepts_an_explicit_cik_for_a_foreign_listing() -> None:
    provider = SecEdgarProvider(
        object(),
        user_agent="MK-VIP test test@example.com",
        fetch_json=lambda _url, _user_agent: {},
    )

    resolved = await provider.resolve_identifier("SAN.PA", cik="0000891478")

    assert resolved == "0000891478"
    assert provider._ticker_by_cik[resolved] == "SAN.PA"
