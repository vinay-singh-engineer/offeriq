from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator


class EquityInput(BaseModel):
    equity_type: Literal["rsu", "options", "none"] = "none"
    # RSU fields
    total_grant_value: Optional[float] = Field(
        None, ge=0, description="Total RSU grant value in USD at grant-date price"
    )
    # Options fields
    num_shares: Optional[int] = Field(None, ge=0)
    strike_price: Optional[float] = Field(None, ge=0)
    current_stock_price: Optional[float] = Field(None, ge=0)
    # Common
    vesting_years: int = Field(4, ge=1, le=10)
    cliff_months: int = Field(12, ge=0, le=24)
    vesting_schedule: Literal["monthly", "quarterly", "annual"] = "quarterly"

    @model_validator(mode="after")
    def validate_equity_fields(self) -> EquityInput:
        if self.equity_type == "rsu" and self.total_grant_value is None:
            raise ValueError("total_grant_value is required for RSU equity")
        if self.equity_type == "options":
            if self.num_shares is None or self.strike_price is None:
                raise ValueError("num_shares and strike_price are required for options")
        return self


class BenefitsInput(BaseModel):
    healthcare_plan: Optional[Literal["hmo", "ppo", "hdhp", "none"]] = None
    employer_401k_match_pct: Optional[float] = Field(None, ge=0, le=100)
    pto_days: Optional[int] = Field(None, ge=0, le=365)
    remote_policy: Optional[Literal["remote", "hybrid", "onsite"]] = None


class OfferInput(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=100)
    role: str = Field(..., min_length=1, max_length=100)
    level: Optional[str] = Field(None, max_length=50, description="e.g. Senior, L5, IC4")
    location: str = Field(
        ..., min_length=1, max_length=100, description="City, State or City, Country"
    )
    base_salary: float = Field(..., gt=0, description="Annual base salary in USD")
    signing_bonus: Optional[float] = Field(None, ge=0)
    annual_bonus_target_pct: Optional[float] = Field(
        None, ge=0, le=200, description="Annual bonus as % of base salary"
    )
    equity: Optional[EquityInput] = None
    benefits: Optional[BenefitsInput] = None


class PriorityWeights(BaseModel):
    """User-adjustable weights for offer scoring. Must sum to 1.0."""
    salary: float = Field(0.40, ge=0, le=1)
    equity: float = Field(0.25, ge=0, le=1)
    benefits: float = Field(0.15, ge=0, le=1)
    company_health: float = Field(0.10, ge=0, le=1)
    work_life_balance: float = Field(0.10, ge=0, le=1)

    @model_validator(mode="after")
    def weights_must_sum_to_one(self) -> PriorityWeights:
        total = round(
            self.salary + self.equity + self.benefits
            + self.company_health + self.work_life_balance, 6
        )
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Weights must sum to 1.0, got {total}")
        return self


class AnalyzeRequest(BaseModel):
    offer: OfferInput
    years_of_experience: Optional[int] = Field(None, ge=0, le=50)


class CompareRequest(BaseModel):
    offer_a: OfferInput
    offer_b: OfferInput
    years_of_experience: Optional[int] = Field(None, ge=0, le=50)
    weights: PriorityWeights = Field(default_factory=PriorityWeights)


class NegotiateRequest(BaseModel):
    offer: OfferInput
    years_of_experience: Optional[int] = Field(None, ge=0, le=50)
    competing_offer: Optional[OfferInput] = Field(
        None, description="A competing offer to use as leverage"
    )
    target_salary: Optional[float] = Field(
        None, gt=0, description="Your target base salary"
    )
