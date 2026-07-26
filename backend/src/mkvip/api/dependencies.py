from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from mkvip.db.session import get_session
from mkvip.providers.base import FinancialDataProvider
from mkvip.providers.yahoo import YahooFinanceProvider
from mkvip.repositories.company import CompanyRepository
from mkvip.repositories.sqlalchemy import SqlAlchemyCompanyRepository


def get_company_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CompanyRepository:
    return SqlAlchemyCompanyRepository(session)


def get_financial_data_provider() -> FinancialDataProvider:
    return YahooFinanceProvider()
