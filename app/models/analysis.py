from typing import Literal, Optional
from pydantic import BaseModel, Field
from app.models.offer import OfferInput


class TotalCompBreakdown(BaseModel):
    base_salary: float
    annual_bonus: float
    equity_annualized: float
    total: float


class MarketBenchmark(BaseModel):
    p25: float
    p50: float
    p75: float
    your_percentile: Optional[float] = None
    data_source: str = "BLS Occupational Employment Statistics"


class CompanyHealth(BaseModel):
    layoff_risk: Literal["low", "medium", "high", "unknown"] = "unknown"
    recent_layoffs: bool = False
    founding_year: Optional[int] = None
    is_public: bool = False
    notes: Optional[str] = None


class DimensionScores(BaseModel):
    salary: float = Field(..., ge=0, le=100)
    equity: float = Field(..., ge=0, le=100)
    benefits: float = Field(..., ge=0, le=100)
    company_health: float = Field(..., ge=0, le=100)
    work_life_balance: float = Field(..., ge=0, le=100)


class OfferAnalysis(BaseModel):
    offer: OfferInput
    total_comp: TotalCompBreakdown
    col_adjusted_base: Optional[float] = Field(
        None, description="Base salary normalized to national average purchasing power"
    )
    market_benchmark: Optional[MarketBenchmark] = None
    company_health: Optional[CompanyHealth] = None
    dimension_scores: DimensionScores
    score: float = Field(..., ge=0, le=100)
    summary: str
