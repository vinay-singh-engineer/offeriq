from typing import Optional

from app.models.analysis import DimensionScores
from app.models.offer import BenefitsInput, PriorityWeights


class ScorerService:

    def score_salary(
        self, percentile: Optional[float], base_salary: float
    ) -> float:
        if percentile is not None:
            return round(min(100.0, max(0.0, percentile)), 1)
        # Fallback on absolute salary when no benchmark is available
        if base_salary >= 220000:
            return 92.0
        elif base_salary >= 180000:
            return 78.0
        elif base_salary >= 150000:
            return 65.0
        elif base_salary >= 120000:
            return 50.0
        elif base_salary >= 90000:
            return 36.0
        return 22.0

    def score_equity(
        self,
        equity_annualized: float,
        base_salary: float,
        cliff_risk: bool,
        is_underwater: bool,
    ) -> float:
        if base_salary == 0 or equity_annualized == 0:
            return 0.0
        ratio = equity_annualized / base_salary
        if ratio >= 0.50:
            score = 100.0
        elif ratio >= 0.25:
            score = 75.0 + (ratio - 0.25) / 0.25 * 25.0
        elif ratio >= 0.10:
            score = 50.0 + (ratio - 0.10) / 0.15 * 25.0
        elif ratio >= 0.05:
            score = 25.0 + (ratio - 0.05) / 0.05 * 25.0
        else:
            score = (ratio / 0.05) * 25.0
        if is_underwater:
            score = max(0.0, score - 30.0)
        if cliff_risk:
            score = max(0.0, score - 10.0)
        return round(min(100.0, score), 1)

    def score_benefits(
        self,
        benefits: Optional[BenefitsInput],
        signing_bonus: Optional[float],
    ) -> float:
        if benefits is None:
            return 50.0
        score = 0.0
        match = benefits.employer_401k_match_pct or 0.0
        if match >= 6.0:
            score += 40.0
        elif match >= 3.0:
            score += 25.0
        elif match >= 1.0:
            score += 12.0
        plan = benefits.healthcare_plan
        if plan == "ppo":
            score += 40.0
        elif plan in ("hmo", "hdhp"):
            score += 25.0
        elif plan is None:
            score += 20.0   # unknown gets a small credit
        if signing_bonus and signing_bonus >= 30000:
            score += 20.0
        elif signing_bonus and signing_bonus >= 10000:
            score += 10.0
        return round(min(100.0, score), 1)

    def score_company_health(self, layoff_risk: str) -> float:
        return {"low": 85.0, "medium": 50.0, "high": 20.0, "unknown": 45.0}.get(
            layoff_risk, 45.0
        )

    def score_wlb(self, benefits: Optional[BenefitsInput]) -> float:
        if benefits is None:
            return 50.0
        score = 0.0
        remote = benefits.remote_policy
        if remote == "remote":
            score += 70.0
        elif remote == "hybrid":
            score += 50.0
        elif remote == "onsite":
            score += 20.0
        else:
            score += 40.0
        pto = benefits.pto_days or 0
        if pto >= 25:
            score += 30.0
        elif pto >= 20:
            score += 20.0
        elif pto >= 15:
            score += 10.0
        elif pto >= 10:
            score += 5.0
        return round(min(100.0, score), 1)

    def compute(
        self,
        salary_score: float,
        equity_score: float,
        benefits_score: float,
        company_score: float,
        wlb_score: float,
        weights: PriorityWeights,
    ) -> DimensionScores:
        total = round(
            salary_score * weights.salary
            + equity_score * weights.equity
            + benefits_score * weights.benefits
            + company_score * weights.company_health
            + wlb_score * weights.work_life_balance,
            1,
        )
        return DimensionScores(
            salary=salary_score,
            equity=equity_score,
            benefits=benefits_score,
            company_health=company_score,
            work_life_balance=wlb_score,
        ), round(min(100.0, total), 1)
