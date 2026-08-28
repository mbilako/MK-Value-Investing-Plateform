from mkvip.analysis.financials import analyse_financials, calculate_financial_trend
from mkvip.providers.base import FinancialDataProvider
from mkvip.providers.normalization import (
    NormalizedCompanyClassification,
    load_company_classification,
    load_historical_data,
    load_price_history,
)
from mkvip.repositories.company import CompanyRepository
from mkvip.schemas.company import CompanyRead, CompanyUpdate
from mkvip.schemas.financial import FinancialHistoryRead
from mkvip.schemas.price import PriceHistoryRead, PricePointCreate


async def apply_company_classification(
    repository: CompanyRepository,
    company: CompanyRead,
    classification: NormalizedCompanyClassification,
) -> CompanyRead:
    changes = {
        key: value
        for key, value in {
            "sector": classification.sector,
            "industry": classification.industry,
            "business_summary": classification.business_summary,
        }.items()
        if value is not None
    }
    if not changes:
        return company
    return await repository.update(company.id, CompanyUpdate(**changes)) or company


async def refresh_company_classification(
    repository: CompanyRepository,
    provider: FinancialDataProvider,
    company: CompanyRead,
) -> CompanyRead:
    classification = await load_company_classification(
        provider,
        company.ticker,
        isin=company.isin,
        cik=company.cik,
        lei=company.lei,
    )
    return await apply_company_classification(repository, company, classification)


async def import_automatic_financial_history(
    repository: CompanyRepository,
    provider: FinancialDataProvider,
    company: CompanyRead,
    *,
    limit: int = 10,
) -> FinancialHistoryRead:
    normalized = await load_historical_data(
        provider,
        company.ticker,
        isin=company.isin,
        cik=company.cik,
        lei=company.lei,
        limit=limit,
    )
    await apply_company_classification(
        repository,
        company,
        NormalizedCompanyClassification(
            sector=normalized.sector,
            industry=normalized.industry,
            business_summary=normalized.business_summary,
        ),
    )
    await repository.create_financial_analyses(
        company.id,
        [(payload, analyse_financials(payload)) for payload in normalized.snapshots],
    )
    if normalized.price_points:
        await repository.replace_price_history(
            company.id,
            [
                PricePointCreate(
                    date=point.timestamp[:10],
                    close=point.close,
                    adjusted_close=point.adjusted_close,
                )
                for point in normalized.price_points
            ],
            currency=normalized.snapshots[0].currency,
            source="Yahoo Finance",
        )
    snapshots = await repository.list_financial_analyses(company.id)
    return FinancialHistoryRead(
        company_id=company.id,
        snapshots=snapshots,
        trend=calculate_financial_trend(snapshots),
        price_history=await repository.list_price_history(company.id),
    )


async def import_automatic_price_history(
    repository: CompanyRepository,
    provider: FinancialDataProvider,
    company: CompanyRead,
) -> PriceHistoryRead:
    normalized = await load_price_history(
        provider,
        company.ticker,
        isin=company.isin,
        cik=company.cik,
        lei=company.lei,
    )
    await apply_company_classification(
        repository,
        company,
        NormalizedCompanyClassification(
            sector=normalized.sector,
            industry=normalized.industry,
            business_summary=normalized.business_summary,
        ),
    )
    return await repository.replace_price_history(
        company.id,
        [
            PricePointCreate(
                date=point.timestamp[:10],
                close=point.close,
                adjusted_close=point.adjusted_close,
            )
            for point in normalized.points
        ],
        currency=normalized.currency,
        source=normalized.source,
    )
