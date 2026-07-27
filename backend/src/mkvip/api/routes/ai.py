from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError

from mkvip.api.dependencies import (
    CurrentUser,
    get_ai_analyst_provider,
    get_ai_usage_service,
    get_company_repository,
)
from mkvip.providers.ai import AIAnalystProvider, AIProviderError
from mkvip.repositories.company import CompanyRepository
from mkvip.schemas.ai import (
    AIAnalysisContext,
    AIAnalysisCreate,
    AIAnalysisDraft,
    AIAnalysisRead,
    AICompanyContext,
    AISourceRead,
)
from mkvip.services.ai_usage import AIQuotaExceededError, AIUsageService

router = APIRouter(prefix="/ai/analyses", tags=["ai"])
Repository = Annotated[CompanyRepository, Depends(get_company_repository)]
Provider = Annotated[AIAnalystProvider, Depends(get_ai_analyst_provider)]
Usage = Annotated[AIUsageService, Depends(get_ai_usage_service)]

DISCLAIMER = (
    "Analyse informative fondée uniquement sur les données MK-VIP ; "
    "elle ne constitue pas un conseil en investissement."
)


async def build_company_context(
    repository: CompanyRepository,
    company_id: uuid.UUID,
) -> tuple[AICompanyContext, list[AISourceRead]]:
    company = await repository.get_by_id(company_id)
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entreprise introuvable.",
        )
    financials = await repository.list_financial_analyses(company_id)
    if not financials:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Une analyse financière MK-VIP est requise pour interroger "
                "l’IA."
            ),
        )
    financial = financials[0]
    valuations = await repository.list_valuation_analyses(company_id)
    scores = await repository.list_scoring_analyses(company_id)
    valuation = valuations[0] if valuations else None
    scoring = scores[0] if scores else None

    sources = [
        AISourceRead(
            id=f"financial:{financial.id}",
            company_id=company.id,
            kind="financial",
            label=f"{company.name} — analyse financière {financial.fiscal_year}",
            fiscal_year=financial.fiscal_year,
            created_at=financial.created_at,
        )
    ]
    if valuation is not None:
        sources.append(
            AISourceRead(
                id=f"valuation:{valuation.id}",
                company_id=company.id,
                kind="valuation",
                label=f"{company.name} — valorisation {valuation.fiscal_year}",
                fiscal_year=valuation.fiscal_year,
                created_at=valuation.created_at,
            )
        )
    if scoring is not None:
        sources.append(
            AISourceRead(
                id=f"scoring:{scoring.id}",
                company_id=company.id,
                kind="scoring",
                label=f"{company.name} — scoring {scoring.fiscal_year}",
                fiscal_year=scoring.fiscal_year,
                created_at=scoring.created_at,
            )
        )
    return (
        AICompanyContext(
            company=company,
            financial=financial,
            valuation=valuation,
            scoring=scoring,
        ),
        sources,
    )


@router.post("", response_model=AIAnalysisRead)
async def create_ai_analysis(
    payload: AIAnalysisCreate,
    repository: Repository,
    provider: Provider,
    current_user: CurrentUser,
    usage: Usage,
) -> AIAnalysisRead:
    primary, sources = await build_company_context(
        repository,
        payload.company_id,
    )
    comparison = None
    if payload.comparison_company_id is not None:
        comparison, comparison_sources = await build_company_context(
            repository,
            payload.comparison_company_id,
        )
        sources.extend(comparison_sources)

    request = AIAnalysisContext(
        mode=payload.mode,
        question=payload.question,
        primary=primary,
        comparison=comparison,
        sources=sources,
    )
    cache_key = usage.cache_key(
        {
            "mode": payload.mode,
            "question": payload.question,
            "primary": {
                "company_id": str(primary.company.id),
                "sources": [
                    {
                        "id": source.id,
                        "created_at": source.created_at.isoformat(),
                    }
                    for source in sources
                    if source.company_id == primary.company.id
                ],
            },
            "comparison": (
                {
                    "company_id": str(comparison.company.id),
                    "sources": [
                        {
                            "id": source.id,
                            "created_at": source.created_at.isoformat(),
                        }
                        for source in sources
                        if source.company_id == comparison.company.id
                    ],
                }
                if comparison is not None
                else None
            ),
        }
    )
    cached = await usage.get_cached(current_user.id, cache_key)
    if cached is not None:
        return AIAnalysisRead.model_validate(cached)

    try:
        await usage.consume_quota(current_user.id)
    except AIQuotaExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Le quota quotidien de l’Analyste IA est épuisé.",
            headers={"Retry-After": "86400"},
        ) from exc

    try:
        draft = AIAnalysisDraft.model_validate(
            await provider.analyze(request)
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Le fournisseur IA a renvoyé une analyse invalide.",
        ) from exc
    except AIProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    allowed_source_ids = {source.id for source in sources}
    cited_source_ids = {
        source_id
        for evidence in draft.evidence
        for source_id in evidence.source_ids
    }
    invalid_source_ids = cited_source_ids - allowed_source_ids
    if invalid_source_ids:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "L’analyse IA cite une source absente du contexte MK-VIP."
            ),
        )

    result = AIAnalysisRead(
        **draft.model_dump(),
        mode=payload.mode,
        sources=sources,
        model=provider.model_name,
        generated_at=datetime.now(UTC),
        disclaimer=DISCLAIMER,
    )
    await usage.put_cached(
        current_user.id,
        cache_key,
        result.model_dump(mode="json"),
    )
    return result
