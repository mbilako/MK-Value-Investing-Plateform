from pydantic import BaseModel, Field, field_validator, model_validator

from mkvip.schemas.company import CompanyRead


class IndexSummaryRead(BaseModel):
    code: str
    name: str
    isin: str | None = None
    market: str
    provider: str
    region: str = "Europe"
    country: str = "Non renseigné"


class IndexConstituentRead(BaseModel):
    name: str
    isin: str | None = None
    ticker: str | None = None
    mic: str
    trading_location: str
    country: str
    currency: str = "EUR"

    @model_validator(mode="after")
    def require_security_identifier(self):
        if not self.isin and not self.ticker:
            raise ValueError("Un ISIN ou un ticker est requis.")
        return self


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
    companies: list[IndexCompanySelection] = Field(min_length=1, max_length=600)


class IndexBulkAddError(BaseModel):
    name: str
    isin: str | None = None
    ticker: str | None = None
    detail: str


class IndexBulkAddRead(BaseModel):
    created: list[CompanyRead]
    existing: list[CompanyRead]
    errors: list[IndexBulkAddError]
