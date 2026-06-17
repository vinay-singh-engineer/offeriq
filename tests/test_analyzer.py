import pytest
from unittest.mock import AsyncMock

from app.models.offer import AnalyzeRequest, BenefitsInput, CompareRequest, EquityInput, OfferInput
from app.models.analysis import CompanyHealth, MarketBenchmark
from app.services.col import COLResult
from app.services.analyzer import AnalyzerService


def make_offer(company="Acme", salary=150000, location="Austin, TX", role="Software Engineer"):
    return OfferInput(
        company_name=company,
        role=role,
        location=location,
        base_salary=salary,
        benefits=BenefitsInput(
            healthcare_plan="ppo",
            employer_401k_match_pct=4.0,
            pto_days=20,
            remote_policy="hybrid",
        ),
    )


def mock_services(svc, benchmark=None, col_index=130, layoff_risk="low"):
    svc.benchmark_svc.get_benchmark = AsyncMock(return_value=benchmark)
    svc.col_svc.get_col = AsyncMock(
        return_value=COLResult(
            city_slug="austin", col_index=col_index,
            purchasing_power=round(150000 * (100 / col_index), 2),
            source="lookup",
        )
    )
    svc.company_svc.get_health = AsyncMock(
        return_value=CompanyHealth(layoff_risk=layoff_risk)
    )


# --- analyze ---

@pytest.mark.asyncio
async def test_analyze_returns_offer_analysis():
    svc = AnalyzerService()
    mock_services(svc)
    result = await svc.analyze(AnalyzeRequest(offer=make_offer()))
    assert result.score >= 0
    assert result.score <= 100
    assert result.total_comp.base_salary == 150000
    assert result.summary != ""


@pytest.mark.asyncio
async def test_analyze_total_comp_includes_equity():
    svc = AnalyzerService()
    mock_services(svc)
    offer = make_offer()
    offer.equity = EquityInput(
        equity_type="rsu", total_grant_value=200000, vesting_years=4
    )
    result = await svc.analyze(AnalyzeRequest(offer=offer))
    assert result.total_comp.equity_annualized == 50000.0
    assert result.total_comp.total == 200000.0


@pytest.mark.asyncio
async def test_analyze_uses_benchmark_percentile():
    svc = AnalyzerService()
    benchmark = MarketBenchmark(p25=120000, p50=150000, p75=190000, your_percentile=50.0)
    mock_services(svc, benchmark=benchmark)
    result = await svc.analyze(AnalyzeRequest(offer=make_offer()))
    assert result.market_benchmark is not None
    assert result.dimension_scores.salary == 50.0


@pytest.mark.asyncio
async def test_analyze_high_risk_company_lowers_score():
    svc = AnalyzerService()
    mock_services(svc, layoff_risk="high")
    result_high = await svc.analyze(AnalyzeRequest(offer=make_offer()))

    svc2 = AnalyzerService()
    mock_services(svc2, layoff_risk="low")
    result_low = await svc2.analyze(AnalyzeRequest(offer=make_offer()))

    assert result_high.score < result_low.score


# --- compare ---

@pytest.mark.asyncio
async def test_compare_picks_higher_scored_offer():
    svc = AnalyzerService()

    offer_a = make_offer("BigCo", salary=200000)
    offer_b = make_offer("SmallCo", salary=120000)

    async def fake_analyze(req):
        if req.offer.company_name == "BigCo":
            mock_services(svc, layoff_risk="low")
            return await AnalyzerService.analyze(svc, req)
        else:
            mock_services(svc, layoff_risk="high")
            return await AnalyzerService.analyze(svc, req)

    svc.analyze = fake_analyze
    req = CompareRequest(offer_a=offer_a, offer_b=offer_b)
    _, _, comparison = await svc.compare(req)

    assert comparison.recommendation in ("offer_a", "offer_b", "comparable")
    assert comparison.recommendation_reason != ""


@pytest.mark.asyncio
async def test_compare_identical_offers_are_comparable():
    svc = AnalyzerService()
    mock_services(svc)

    offer = make_offer()
    req = CompareRequest(offer_a=offer, offer_b=offer)
    _, _, comparison = await svc.compare(req)

    assert comparison.recommendation == "comparable"
