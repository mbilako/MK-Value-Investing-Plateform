from mkvip.analysis.sector import (
    SectorCompanyInput,
    normalize_gics_sector,
    rank_sector_companies,
)


def company(
    company_id: str,
    *,
    sector: str | None = "Industrials",
    metrics: dict[str, float | None],
) -> SectorCompanyInput:
    return SectorCompanyInput(
        company_id=company_id,
        name=company_id,
        ticker=company_id,
        sector=sector,
        industry=None,
        is_favorite=False,
        index_memberships=[],
        absolute_score=None,
        fiscal_year=2025,
        updated_at=None,
        metrics=metrics,
    )


def test_normalizes_provider_sector_names_to_gics() -> None:
    assert normalize_gics_sector("Technology") == "Information Technology"
    assert normalize_gics_sector("Consumer Cyclical") == "Consumer Discretionary"
    assert normalize_gics_sector("Financial Services") == "Financials"
    assert normalize_gics_sector("Unknown") is None


def test_ranks_companies_against_their_sector_with_explanations() -> None:
    strong = company(
        "strong",
        metrics={
            "roe": 0.25,
            "roic": 0.20,
            "fcf_yield": 0.08,
            "operating_margin": 0.22,
            "pe": 12,
            "net_debt_ebitda": 1,
        },
    )
    weak = company(
        "weak",
        metrics={
            "roe": 0.10,
            "roic": 0.08,
            "fcf_yield": 0.03,
            "operating_margin": 0.08,
            "pe": 25,
            "net_debt_ebitda": 3,
        },
    )

    results = rank_sector_companies([strong, weak])
    by_id = {result.company.company_id: result for result in results}

    assert by_id["strong"].sector_score == 100
    assert by_id["strong"].sector_rank == 1
    assert by_id["strong"].status == "leader"
    assert by_id["weak"].sector_score == 0
    assert by_id["weak"].sector_rank == 2
    assert len(by_id["strong"].metrics) == 6
    assert by_id["strong"].metrics[0].sector_median == 0.175


def test_requires_a_classification_and_enough_comparable_peers() -> None:
    unclassified = company("unknown", sector=None, metrics={"roe": 0.2})
    alone = company("alone", metrics={"roe": 0.2, "roic": 0.15})

    results = rank_sector_companies([unclassified, alone])
    by_id = {result.company.company_id: result for result in results}

    assert by_id["unknown"].status == "unclassified"
    assert by_id["alone"].status == "insufficient_peers"
    assert by_id["alone"].sector_score is None
