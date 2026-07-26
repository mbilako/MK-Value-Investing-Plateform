import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from mkvip.analysis.valuation import ValuationAssumptions


class ValuationAssumptionsCreate(BaseModel):
    growth_rate: float = Field(default=0.05, gt=-1, le=0.5)
    terminal_growth_rate: float = Field(default=0.02, ge=-0.05, le=0.1)
    cost_of_equity: float = Field(default=0.10, gt=0, le=0.5)
    wacc: float = Field(default=0.08, gt=0, le=0.5)
    tax_rate: float = Field(default=0.25, ge=0, le=1)
    projection_years: int = Field(default=5, ge=1, le=10)
    target_pe: float = Field(default=15, gt=0, le=100)
    corporate_bond_yield: float = Field(default=0.044, gt=0, le=0.5)
    margin_of_safety: float = Field(default=0.25, ge=0, le=0.9)

    @model_validator(mode="after")
    def validate_terminal_growth(self) -> "ValuationAssumptionsCreate":
        if self.cost_of_equity <= self.terminal_growth_rate:
            raise ValueError(
                "Le coût des capitaux propres doit dépasser la croissance "
                "terminale."
            )
        return self

    def to_domain(self) -> ValuationAssumptions:
        return ValuationAssumptions(**self.model_dump())


class ValuationCreate(BaseModel):
    fiscal_year: int = Field(ge=1900, le=2100)
    assumptions: ValuationAssumptionsCreate = Field(
        default_factory=ValuationAssumptionsCreate
    )


class ValuationMethodRead(BaseModel):
    key: str
    label: str
    value: float | None
    category: str
    formula: str
    base_metric: str
    note: str


class ValuationAnalysisRead(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    financial_snapshot_id: uuid.UUID
    fiscal_year: int
    currency: str
    market_cap: float
    assumptions: ValuationAssumptionsCreate
    methods: list[ValuationMethodRead]
    central_estimate: float | None
    margin_of_safety_value: float | None
    market_gap: float | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
