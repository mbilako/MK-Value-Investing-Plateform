from mkvip.analysis.financials import analyse_financials, calculate_financial_trend
from mkvip.providers.base import FinancialDataProvider
from mkvip.providers.normalization import (
    NormalizedCompanyClassification,
    load_company_classification,
    load_historical_data,
)
from mkvip.repositories.company import CompanyRepository
from mkvip.schemas.company import CompanyRead, CompanyUpdate
from mkvip.schemas.financial import FinancialHistoryRead


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
        ),
    )
    await repository.create_financial_analyses(
        company.id,
        [(payload, analyse_financials(payload)) for payload in normalized.snapshots],
    )
    snapshots = await repository.list_financial_analyses(company.id)
    return FinancialHistoryRead(
        company_id=company.id,
        snapshots=snapshots,
        trend=calculate_financial_trend(snapshots),
    )
