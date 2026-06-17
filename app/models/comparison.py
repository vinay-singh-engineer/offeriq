from typing import Literal
from pydantic import BaseModel
from app.models.analysis import OfferAnalysis


class OfferComparison(BaseModel):
    offer_a: OfferAnalysis
    offer_b: OfferAnalysis
    recommendation: Literal["offer_a", "offer_b", "comparable"]
    recommendation_reason: str
