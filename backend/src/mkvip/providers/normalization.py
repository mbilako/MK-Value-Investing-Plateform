from dataclasses import dataclass

from pydantic import ValidationError

from mkvip.analysis.sector import normalize_gics_sector
from mkvip.providers.base import (
    FinancialDataProvider,
    ProviderBalanceSheet,
    ProviderCashFlow,
    ProviderDataError,
    ProviderDataIncompleteError,
    ProviderIncomeStatement,
    ProviderPricePoint,
)
from mkvip.schemas.financial import FinancialProfile, FinancialSnapshotCreate

MILLION = 1_000_000


@dataclass(frozen=True)
class NormalizedFinancialData:
    snapshots: list[FinancialSnapshotCreate]
    sector: str | None
    industry: str | None
    business_summary: str | None
    price_points: list[ProviderPricePoint]


@dataclass(frozen=True)
class NormalizedCompanyClassification:
    sector: str | None
    industry: str | None
    business_summary: str | None = None


@dataclass(frozen=True)
class NormalizedPriceHistory:
    points: list[ProviderPricePoint]
    currency: str
    source: str
    sector: str | None
    industry: str | None
    business_summary: str | None


def _to_millions(value: float) -> float:
    return round(value / MILLION, 6)


def _optional_millions(value: float | None) -> float | None:
    return _to_millions(value) if value is not None else None


def _business_summary(value: str | None) -> str | None:
    if not value:
        return None
    normalized = " ".join(value.split())
    return normalized[:5000] or None


def _financial_profile(sector: str | None, industry: str | None) -> FinancialProfile:
    classification = f"{sector or ''} {industry or ''}".casefold()
    financial_markers = (
        "financial services",
        "bank",
        "insurance",
        "reinsurance",
    )
    if any(marker in classification for marker in financial_markers):
        return FinancialProfile.FINANCIAL
    return FinancialProfile.STANDARD


async def load_price_history(
    provider: FinancialDataProvider,
    ticker: str,
    *,
    isin: str | None = None,
    cik: str | None = None,
    lei: str | None = None,
) -> NormalizedPriceHistory:
    candidates = getattr(provider, "providers", None) or (provider,)
    errors: list[str] = []
    for candidate in candidates:
        try:
            candidate_ticker = ticker
            resolver = getattr(candidate, "resolve_identifier", None)
            if resolver is not None:
                candidate_ticker = await resolver(
                    ticker,
                    isin=isin,
                    cik=cik,
                    lei=lei,
                )
            profile = await candidate.get_profile(candidate_ticker)
            points = await candidate.get_price_history(candidate_ticker)
            if points:
                return NormalizedPriceHistory(
                    points=points,
                    currency=profile.currency,
                    source=candidate.name,
                    sector=normalize_gics_sector(profile.sector),
                    industry=profile.industry.strip() if profile.industry else None,
                    business_summary=_business_summary(profile.business_summary),
                )
        except ProviderDataError as error:
            errors.append(f"{candidate.name}: {error}")
    raise ProviderDataIncompleteError(
        "Aucun historique de cours public n'est disponible. " + " | ".join(errors)
    )


async def load_company_classification(
    provider: FinancialDataProvider,
    ticker: str,
    *,
    isin: str | None = None,
    cik: str | None = None,
    lei: str | None = None,
) -> NormalizedCompanyClassification:
    candidates = getattr(provider, "providers", None) or (provider,)
    errors: list[str] = []
    fallback_industry = None
    fallback_business_summary = None
    profile_loaded = False
    for candidate in candidates:
        try:
            candidate_ticker = ticker
            resolver = getattr(candidate, "resolve_identifier", None)
            if resolver is not None:
                candidate_ticker = await resolver(
                    ticker,
                    isin=isin,
                    cik=cik,
                    lei=lei,
                )
            profile = await candidate.get_profile(candidate_ticker)
        except ProviderDataError as error:
            errors.append(f"{candidate.name}: {error}")
            continue
        profile_loaded = True
        industry = profile.industry.strip() if profile.industry else None
        business_summary = _business_summary(profile.business_summary)
        fallback_industry = fallback_industry or industry
        fallback_business_summary = fallback_business_summary or business_summary
        sector = normalize_gics_sector(profile.sector)
        if sector is not None:
            return NormalizedCompanyClassification(
                sector=sector,
                industry=industry,
                business_summary=business_summary,
            )

    if profile_loaded:
        return NormalizedCompanyClassification(
            sector=None,
            industry=fallback_industry,
            business_summary=fallback_business_summary,
        )
    raise ProviderDataIncompleteError(
        "Aucune source publique n'a fourni de classification exploitable. "
        + " | ".join(errors)
    )


async def load_latest_snapshot(
    provider: FinancialDataProvider,
    ticker: str,
    *,
    isin: str | None = None,
    cik: str | None = None,
    lei: str | None = None,
) -> FinancialSnapshotCreate:
    candidates = getattr(provider, "providers", None)
    if candidates is not None:
        errors: list[str] = []
        for candidate in candidates:
            try:
                candidate_ticker = ticker
                resolver = getattr(candidate, "resolve_identifier", None)
                if resolver is not None:
                    candidate_ticker = await resolver(
                        ticker,
                        isin=isin,
                        cik=cik,
                        lei=lei,
                    )
                return await _load_latest_snapshot(candidate, candidate_ticker)
            except ProviderDataError as error:
                errors.append(f"{candidate.name}: {error}")
        raise ProviderDataIncompleteError(
            "Aucune source publique n'a fourni un exercice annuel complet. " + " | ".join(errors)
        )
    return await _load_latest_snapshot(provider, ticker)


async def load_historical_snapshots(
    provider: FinancialDataProvider,
    ticker: str,
    *,
    isin: str | None = None,
    cik: str | None = None,
    lei: str | None = None,
    limit: int = 10,
) -> list[FinancialSnapshotCreate]:
    return (
        await load_historical_data(
            provider,
            ticker,
            isin=isin,
            cik=cik,
            lei=lei,
            limit=limit,
        )
    ).snapshots


async def load_historical_data(
    provider: FinancialDataProvider,
    ticker: str,
    *,
    isin: str | None = None,
    cik: str | None = None,
    lei: str | None = None,
    limit: int = 10,
) -> NormalizedFinancialData:
    candidates = getattr(provider, "providers", None)
    if candidates is None:
        return await _load_historical_data(provider, ticker, limit=limit)

    snapshots_by_year: dict[int, FinancialSnapshotCreate] = {}
    errors: list[str] = []
    sector = None
    industry = None
    business_summary = None
    price_points: list[ProviderPricePoint] = []
    for candidate in candidates:
        try:
            candidate_ticker = ticker
            resolver = getattr(candidate, "resolve_identifier", None)
            if resolver is not None:
                candidate_ticker = await resolver(
                    ticker,
                    isin=isin,
                    cik=cik,
                    lei=lei,
                )
            data = await _load_historical_data(
                candidate,
                candidate_ticker,
                limit=limit,
            )
            sector = sector or data.sector
            industry = industry or data.industry
            business_summary = business_summary or data.business_summary
            if len(data.price_points) > len(price_points):
                price_points = data.price_points
            for snapshot in data.snapshots:
                snapshots_by_year.setdefault(snapshot.fiscal_year, snapshot)
        except ProviderDataError as error:
            errors.append(f"{candidate.name}: {error}")

    if not snapshots_by_year:
        raise ProviderDataIncompleteError(
            "Aucune source publique n'a fourni d'historique annuel exploitable. "
            + " | ".join(errors)
        )
    return NormalizedFinancialData(
        snapshots=sorted(
            snapshots_by_year.values(),
            key=lambda snapshot: snapshot.fiscal_year,
            reverse=True,
        )[:limit],
        sector=sector,
        industry=industry,
        business_summary=business_summary,
        price_points=price_points,
    )


async def _load_latest_snapshot(
    provider: FinancialDataProvider,
    ticker: str,
) -> FinancialSnapshotCreate:
    return (await _load_historical_snapshots(provider, ticker, limit=1))[0]


def _year_end_prices(price_points: list) -> dict[int, float]:
    prices: dict[int, tuple[str, float]] = {}
    for point in price_points:
        try:
            year = int(point.timestamp[:4])
        except (TypeError, ValueError):
            continue
        if year not in prices or point.timestamp > prices[year][0]:
            prices[year] = (point.timestamp, point.close)
    return {year: close for year, (_, close) in prices.items()}


async def _load_historical_snapshots(
    provider: FinancialDataProvider,
    ticker: str,
    *,
    limit: int,
) -> list[FinancialSnapshotCreate]:
    return (await _load_historical_data(provider, ticker, limit=limit)).snapshots


async def _load_historical_data(
    provider: FinancialDataProvider,
    ticker: str,
    *,
    limit: int,
) -> NormalizedFinancialData:
    profile = await provider.get_profile(ticker)
    income_statements = await provider.get_income_statements(ticker)
    balance_sheets = await provider.get_balance_sheet(ticker)
    analysis_profile = _financial_profile(profile.sector, profile.industry)
    try:
        cash_flows = await provider.get_cash_flow(ticker)
    except ProviderDataError:
        cash_flows = []
    price_points = []
    price_loader = getattr(provider, "get_price_history", None)
    if price_loader is not None:
        try:
            price_points = await price_loader(ticker)
        except ProviderDataError:
            price_points = []

    income_by_year: dict[int, ProviderIncomeStatement] = {
        statement.fiscal_year: statement for statement in income_statements
    }
    balance_by_year: dict[int, ProviderBalanceSheet] = {
        statement.fiscal_year: statement for statement in balance_sheets
    }
    cash_by_year: dict[int, ProviderCashFlow] = {
        statement.fiscal_year: statement for statement in cash_flows
    }
    shared_years = income_by_year.keys() & balance_by_year.keys()
    if not shared_years:
        raise ProviderDataIncompleteError(
            f"Aucun exercice annuel complet n'est disponible pour {ticker}."
        )

    prices_by_year = _year_end_prices(price_points)
    latest_year = max(shared_years)
    snapshots: list[FinancialSnapshotCreate] = []
    validation_errors: list[str] = []
    for fiscal_year in sorted(shared_years, reverse=True):
        income = income_by_year[fiscal_year]
        balance = balance_by_year[fiscal_year]
        cash_flow = cash_by_year.get(fiscal_year)
        shares = (
            balance.shares_outstanding
            or income.weighted_average_shares
            or profile.shares_outstanding
        )
        year_end_price = prices_by_year.get(fiscal_year)
        if shares is not None and shares > 0 and year_end_price is not None:
            market_cap = shares * year_end_price
        elif fiscal_year == latest_year:
            market_cap = profile.market_cap
        else:
            continue

        try:
            snapshots.append(
                _build_snapshot(
                    provider,
                    ticker,
                    profile.currency,
                    analysis_profile,
                    income,
                    balance,
                    cash_flow,
                    market_cap,
                    shares,
                    year_end_price,
                )
            )
        except ValidationError as error:
            fields = ", ".join(
                ".".join(str(part) for part in issue["loc"]) for issue in error.errors()
            )
            validation_errors.append(f"{fiscal_year}: {fields}")
        if len(snapshots) == limit:
            break

    if snapshots:
        return NormalizedFinancialData(
            snapshots=snapshots,
            sector=normalize_gics_sector(profile.sector),
            industry=profile.industry.strip() if profile.industry else None,
            business_summary=_business_summary(profile.business_summary),
            price_points=price_points,
        )
    detail = " | ".join(validation_errors) or "aucun exercice compatible"
    raise ProviderDataIncompleteError(
        f"Les données publiques de {ticker.upper()} ne peuvent pas être normalisées ({detail})."
    )


def _build_snapshot(
    provider: FinancialDataProvider,
    ticker: str,
    currency: str,
    analysis_profile: FinancialProfile,
    income: ProviderIncomeStatement,
    balance: ProviderBalanceSheet,
    cash_flow: ProviderCashFlow | None,
    market_cap: float,
    shares_outstanding: float | None,
    closing_price: float | None,
) -> FinancialSnapshotCreate:
    fiscal_year = income.fiscal_year
    depreciation = income.depreciation_amortization
    ebit = income.ebit
    ebitda = income.ebitda
    if analysis_profile is FinancialProfile.STANDARD:
        if depreciation is None and ebitda is not None and ebit is not None:
            depreciation = abs(ebitda - ebit)
        if ebitda is None and ebit is not None and depreciation is not None:
            ebitda = ebit + depreciation
        if ebit is None and ebitda is not None and depreciation is not None:
            ebit = ebitda - depreciation
    else:
        ebitda = None

    return FinancialSnapshotCreate(
        fiscal_year=fiscal_year,
        source=(f"{provider.name} · {ticker.upper()} · exercice {fiscal_year}"),
        currency=currency,
        analysis_profile=analysis_profile,
        revenue=_to_millions(income.revenue),
        ebitda=_optional_millions(ebitda),
        depreciation_amortization=_optional_millions(
            abs(depreciation) if depreciation is not None else None
        ),
        ebit=_optional_millions(ebit),
        interest_expense=_optional_millions(
            abs(income.interest_expense) if income.interest_expense is not None else None
        ),
        operating_cash_flow=(
            _to_millions(cash_flow.operating_cash_flow) if cash_flow is not None else None
        ),
        capex=(_to_millions(abs(cash_flow.capex)) if cash_flow is not None else None),
        net_income=_to_millions(income.net_income),
        pretax_income=_optional_millions(income.pretax_income),
        market_cap=_to_millions(market_cap),
        closing_price=(
            round(closing_price, 6)
            if closing_price is not None
            else (
                round(market_cap / shares_outstanding, 6)
                if shares_outstanding is not None and shares_outstanding > 0
                else None
            )
        ),
        shares_outstanding=_optional_millions(shares_outstanding),
        treasury_stock_value=_optional_millions(
            abs(balance.treasury_stock_value) if balance.treasury_stock_value is not None else None
        ),
        total_assets=_to_millions(balance.total_assets),
        current_assets=_optional_millions(balance.current_assets),
        current_liabilities=_optional_millions(balance.current_liabilities),
        financial_debt=_optional_millions(balance.financial_debt),
        cash=_optional_millions(balance.cash),
        total_equity=_to_millions(balance.total_equity),
        investing_cash_flow=(
            _to_millions(cash_flow.investing_cash_flow)
            if cash_flow is not None and cash_flow.investing_cash_flow is not None
            else None
        ),
    )
