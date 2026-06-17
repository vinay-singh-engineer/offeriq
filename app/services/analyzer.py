import asyncio
from typing import Optional, Tuple

from app.models.analysis import (
    CompanyHealth, OfferAnalysis, TotalCompBreakdown,
)
from app.models.comparison import OfferComparison
from app.models.offer import AnalyzeRequest, CompareRequest, PriorityWeights
from app.services.benchmarker import BenchmarkService
from app.services.col import COLService
from app.services.company import CompanyService
from app.services.equity import EquityService
from app.services.scorer import ScorerService


class AnalyzerService:

    def __init__(self):
        self.equity_svc = EquityService()
        self.benchmark_svc = BenchmarkService()
        self.col_svc = COLService()
        self.company_svc = CompanyService()
        self.scorer = ScorerService()

    def _total_comp(self, offer, equity_annualized: float) -> TotalCompBreakdown:
        annual_bonus = 0.0
        if offer.annual_bonus_target_pct is not None:
            annual_bonus = offer.base_salary * (offer.annual_bonus_target_pct / 100)
        total = offer.base_salary + annual_bonus + equity_annualized
        return TotalCompBreakdown(
            base_salary=offer.base_salary,
            annual_bonus=round(annual_bonus, 2),
            equity_annualized=round(equity_annualized, 2),
            total=round(total, 2),
        )

    def _build_summary(
        self,
        offer,
        total_comp: TotalCompBreakdown,
        benchmark,
        company_health: Optional[CompanyHealth],
        score: float,
    ) -> str:
        parts = [
            f"{offer.company_name} — ${offer.base_salary:,.0f} base"
            f" + ${total_comp.equity_annualized:,.0f} equity"
            f" = ${total_comp.total:,.0f} total comp/yr."
        ]
        if benchmark and benchmark.your_percentile is not None:
            parts.append(
                f"Salary is at the {benchmark.your_percentile:.0f}th percentile"
                f" for {offer.role} in {offer.location}."
            )
        if company_health:
            risk = company_health.layoff_risk
            parts.append(f"Company health: {risk} risk.")
        parts.append(f"Overall score: {score:.0f}/100.")
        return " ".join(parts)

    async def analyze(self, request: AnalyzeRequest) -> OfferAnalysis:
        offer = request.offer

        # Sync: equity (no I/O)
        equity_result = self.equity_svc.analyze(offer.equity)

        # Async: benchmark, COL, company in parallel
        benchmark, col_result, company_health = await asyncio.gather(
            self.benchmark_svc.get_benchmark(offer.role, offer.location, offer.base_salary),
            self.col_svc.get_col(offer.location, offer.base_salary),
            self.company_svc.get_health(offer.company_name),
        )

        total_comp = self._total_comp(offer, equity_result.annualized_value)

        percentile = benchmark.your_percentile if benchmark else None
        s_salary = self.scorer.score_salary(percentile, offer.base_salary)
        s_equity = self.scorer.score_equity(
            equity_result.annualized_value,
            offer.base_salary,
            equity_result.cliff_risk,
            equity_result.is_underwater,
        )
        s_benefits = self.scorer.score_benefits(offer.benefits, offer.signing_bonus)
        s_company = self.scorer.score_company_health(company_health.layoff_risk)
        s_wlb = self.scorer.score_wlb(offer.benefits)

        weights = PriorityWeights()
        dim_scores, score = self.scorer.compute(
            s_salary, s_equity, s_benefits, s_company, s_wlb, weights
        )

        summary = self._build_summary(offer, total_comp, benchmark, company_health, score)

        return OfferAnalysis(
            offer=offer,
            total_comp=total_comp,
            col_adjusted_base=col_result.purchasing_power if col_result else None,
            market_benchmark=benchmark,
            company_health=company_health,
            dimension_scores=dim_scores,
            score=score,
            summary=summary,
        )

    def _comparison_reason(
        self,
        a: OfferAnalysis,
        b: OfferAnalysis,
        recommendation: str,
    ) -> str:
        winner, loser = (a, b) if recommendation == "offer_a" else (b, a)
        w_name = winner.offer.company_name
        l_name = loser.offer.company_name
        tc_diff = winner.total_comp.total - loser.total_comp.total
        pct = abs(tc_diff / loser.total_comp.total * 100) if loser.total_comp.total else 0
        parts = [
            f"{w_name} scores {winner.score:.0f}/100 vs {l_name}'s {loser.score:.0f}/100."
        ]
        if tc_diff > 0:
            parts.append(
                f"Total comp is ${tc_diff:,.0f} ({pct:.0f}%) higher at {w_name}."
            )
        w_risk = winner.company_health.layoff_risk if winner.company_health else "unknown"
        l_risk = loser.company_health.layoff_risk if loser.company_health else "unknown"
        if w_risk != l_risk:
            parts.append(f"Company risk: {w_name} is {w_risk}, {l_name} is {l_risk}.")
        return " ".join(parts)

    async def compare(
        self, request: CompareRequest
    ) -> Tuple[OfferAnalysis, OfferAnalysis, OfferComparison]:
        from app.models.offer import AnalyzeRequest
        analysis_a, analysis_b = await asyncio.gather(
            self.analyze(AnalyzeRequest(
                offer=request.offer_a,
                years_of_experience=request.years_of_experience,
            )),
            self.analyze(AnalyzeRequest(
                offer=request.offer_b,
                years_of_experience=request.years_of_experience,
            )),
        )

        diff = analysis_a.score - analysis_b.score
        if diff > 5:
            recommendation = "offer_a"
        elif diff < -5:
            recommendation = "offer_b"
        else:
            recommendation = "comparable"

        if recommendation == "comparable":
            reason = (
                f"Both offers are closely matched "
                f"({analysis_a.score:.0f} vs {analysis_b.score:.0f}). "
                f"Consider non-financial factors: team, growth, and role scope."
            )
        else:
            reason = self._comparison_reason(analysis_a, analysis_b, recommendation)

        comparison = OfferComparison(
            offer_a=analysis_a,
            offer_b=analysis_b,
            recommendation=recommendation,
            recommendation_reason=reason,
        )
        return analysis_a, analysis_b, comparison
