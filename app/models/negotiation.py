from typing import List
from pydantic import BaseModel, Field


class NegotiationResult(BaseModel):
    recommended_counter: float = Field(..., description="Recommended counter-offer base salary")
    floor: float = Field(..., description="Walk-away minimum — do not accept below this")
    stretch_goal: float = Field(..., description="Best-case ask if leverage is strong")
    email_subject: str
    email_body: str
    talking_points: List[str] = Field(..., description="Bullet points for the phone call")
    leverage_notes: str = Field(..., description="Your leverage points explained")
