from pydantic import ValidationError

from mkvip.providers.base import (
    FinancialDataProvider,
    ProviderBalanceSheet,
    ProviderCashFlow,
    ProviderDataIncompleteError,
    ProviderIncomeStatement,
)
from mkvip.schemas.financial import FinancialSnapshotCreate

MILLION = 1_000_000


def _to_millions(value: float) -> float:
    return round(value / MILLION, 6)


async def load_latest_snapshot(
    provider: FinancialDataProvider,
    ticker: str,
) -> FinancialSnapshotCreate:
    profile = await provider.get_profile(ticker)
    income_statements = await provider.get_income_statements(ticker)
    balance_sheets = await provider.get_balance_sheet(ticker)
    cash_flows = await provider.get_cash_flow(ticker)

    income_by_year: dict[int, ProviderIncomeStatement] = {
        statement.fiscal_year: statement for statement in income_statements
    }
    balance_by_year: dict[int, ProviderBalanceSheet] = {
        statement.fiscal_year: statement for statement in balance_sheets
    }
    cash_by_year: dict[int, ProviderCashFlow] = {
        statement.fiscal_year: statement for statement in cash_flows
    }
    shared_years = (
        income_by_year.keys() & balance_by_year.keys() & cash_by_year.keys()
    )
    if not shared_years:
        raise ProviderDataIncompleteError(
            f"Aucun exercice annuel complet n'est disponible pour {ticker}."
        )

    fiscal_year = max(shared_years)
    income = income_by_year[fiscal_year]
    balance = balance_by_year[fiscal_year]
    cash_flow = cash_by_year[fiscal_year]

    try:
        return FinancialSnapshotCreate(
            fiscal_year=fiscal_year,
            source=(
                f"{provider.name} · {ticker.upper()} · exercice {fiscal_year}"
            ),
            currency=profile.currency,
            revenue=_to_millions(income.revenue),
            ebitda=_to_millions(income.ebitda),
            depreciation_amortization=_to_millions(
                abs(income.depreciation_amortization)
            ),
            ebit=_to_millions(income.ebit),
            interest_expense=_to_millions(abs(income.interest_expense)),
            capex=_to_millions(abs(cash_flow.capex)),
            net_income=_to_millions(income.net_income),
            market_cap=_to_millions(profile.market_cap),
            total_assets=_to_millions(balance.total_assets),
            current_assets=_to_millions(balance.current_assets),
            current_liabilities=_to_millions(balance.current_liabilities),
            financial_debt=_to_millions(balance.financial_debt),
            cash=_to_millions(balance.cash),
            total_equity=_to_millions(balance.total_equity),
        )
    except ValidationError as error:
        fields = ", ".join(
            ".".join(str(part) for part in issue["loc"])
            for issue in error.errors()
        )
        raise ProviderDataIncompleteError(
            f"Les données publiques de {ticker.upper()} ne peuvent pas être "
            f"normalisées ({fields})."
        ) from error
