from pydantic import BaseModel, Field, field_validator

from mkvip.schemas.company import CompanyRead


class IndexSummaryRead(BaseModel):
    code: str
    name: str
    isin: str
    market: str
    provider: str


class IndexConstituentRead(BaseModel):
    name: str
    isin: str
    mic: str
    trading_location: str
    country: str


class IndexCompositionRead(IndexSummaryRead):
    as_of: str | None = None
    source_url: str
    constituents: list[IndexConstituentRead]


class IndexCompanySelection(IndexConstituentRead):
    index_code: str = Field(min_length=1, max_length=20)

    @field_validator("index_code")
    @classmethod
    def normalize_index_code(cls, value: str) -> str:
        return value.strip().upper()


class IndexBulkAddCreate(BaseModel):
    companies: list[IndexCompanySelection] = Field(min_length=1, max_length=120)


class IndexBulkAddError(BaseModel):
    name: str
    isin: str
    detail: str


class IndexBulkAddRead(BaseModel):
    created: list[CompanyRead]
    existing: list[CompanyRead]
    errors: list[IndexBulkAddError]
