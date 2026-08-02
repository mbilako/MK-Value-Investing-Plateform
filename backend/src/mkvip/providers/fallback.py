from mkvip.providers.base import FinancialDataProvider


class FallbackFinancialDataProvider:
    """Ordered public-data providers used one complete snapshot at a time."""

    name = "Sources publiques automatiques"

    def __init__(self, *providers: FinancialDataProvider) -> None:
        if not providers:
            raise ValueError("At least one financial provider is required")
        self.providers = providers

    async def search_company(self, query: str):
        return await self.providers[0].search_company(query)

    async def get_profile(self, ticker: str):
        return await self.providers[0].get_profile(ticker)

    async def get_income_statements(self, ticker: str):
        return await self.providers[0].get_income_statements(ticker)

    async def get_balance_sheet(self, ticker: str):
        return await self.providers[0].get_balance_sheet(ticker)

    async def get_cash_flow(self, ticker: str):
        return await self.providers[0].get_cash_flow(ticker)

    async def get_price_history(self, ticker: str):
        return await self.providers[0].get_price_history(ticker)
