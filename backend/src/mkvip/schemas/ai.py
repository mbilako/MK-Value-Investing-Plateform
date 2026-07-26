from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from mkvip.schemas.company import CompanyRead
from mkvip.schemas.financial import FinancialAnalysisRead
from mkvip.schemas.scoring import ScoringAnalysisRead
from mkvip.schemas.valuation import ValuationAnalysisRead

AIAnalysisMode = Literal["summary", "comparison", "question"]
AISourceKind = Literal["financial", "valuation", "scoring"]


class AIAnalysisCreate(BaseModel):
    mode: AIAnalysisMode
    company_id: uuid.UUID
    comparison_company_id: uuid.UUID | None = None
    question: str | None = Field(default=None, min_length=3, max_length=800)

    @model_validator(mode="after")
    def validate_mode_requirements(self) -> AIAnalysisCreate:
        if self.question is not None:
            self.question = self.question.strip()
        if self.mode == "question" and not self.question:
            raise ValueError("Une question est requise dans ce mode.")
        if self.mode == "comparison" and self.comparison_company_id is None:
            raise ValueError(
                "Une entreprise de comparaison est requise dans ce mode."
            )
        if (
            self.mode == "comparison"
            and self.comparison_company_id == self.company_id
        ):
            raise ValueError(
                "Les deux entreprises comparées doivent être distinctes."
            )
        return self


class AISourceRead(BaseModel):
    id: str
    company_id: uuid.UUID
    kind: AISourceKind
    label: str
    fiscal_year: int
    created_at: datetime


class AICompanyContext(BaseModel):
    company: CompanyRead
    financial: FinancialAnalysisRead
    valuation: ValuationAnalysisRead | None
    scoring: ScoringAnalysisRead | None


class AIAnalysisContext(BaseModel):
    mode: AIAnalysisMode
    question: str | None
    primary: AICompanyContext
    comparison: AICompanyContext | None
    sources: list[AISourceRead]


class AIEvidenceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=160)
    finding: str = Field(min_length=1, max_length=1_500)
    source_ids: list[str] = Field(min_length=1, max_length=6)


class AIAnalysisDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    headline: str = Field(min_length=1, max_length=180)
    conclusion: str = Field(min_length=1, max_length=2_000)
    evidence: list[AIEvidenceRead] = Field(min_length=1, max_length=8)
    risks: list[str] = Field(min_length=1, max_length=8)
    missing_information: list[str] = Field(min_length=1, max_length=8)


class AIAnalysisRead(AIAnalysisDraft):
    mode: AIAnalysisMode
    sources: list[AISourceRead]
    model: str
    generated_at: datetime
    disclaimer: str
