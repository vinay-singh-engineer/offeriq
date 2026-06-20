from fastapi import APIRouter
from app.models.offer import AnalyzeRequest, CompareRequest, BenefitsInput, EquityInput, OfferInput
from app.services.analyzer import AnalyzerService

router = APIRouter(prefix="/demo", tags=["demo"])
_analyzer = AnalyzerService()

_APPLE_OFFER = OfferInput(
    company_name="Apple",
    role="Senior Site Reliability Engineer",
    level="ICT5",
    location="Cupertino, CA",
    base_salary=195000,
    signing_bonus=50000,
    annual_bonus_target_pct=15.0,
    equity=EquityInput(
        equity_type="rsu",
        total_grant_value=100000,
        vesting_years=4,
        cliff_months=12,
    ),
    benefits=BenefitsInput(
        healthcare_plan="ppo",
        employer_401k_match_pct=6.0,
        pto_days=20,
        remote_policy="hybrid",
    ),
)

_GOOGLE_OFFER = OfferInput(
    company_name="Google",
    role="Site Reliability Engineer",
    level="L6",
    location="Cupertino, CA",
    base_salary=210000,
    signing_bonus=60000,
    annual_bonus_target_pct=15.0,
    equity=EquityInput(
        equity_type="rsu",
        total_grant_value=500000,
        vesting_years=4,
        cliff_months=12,
    ),
    benefits=BenefitsInput(
        healthcare_plan="ppo",
        employer_401k_match_pct=4.0,
        pto_days=20,
        remote_policy="hybrid",
    ),
)


@router.get("/analyze",
            summary="Demo: analyze a pre-built Apple ICT5 SRE offer",
            description=(
                "Runs a realistic Apple SRE offer (15 YOE) through the full analysis pipeline. "
                "No payload required — great for a quick portfolio demo."
            ))
async def demo_analyze():
    return await _analyzer.analyze(AnalyzeRequest(offer=_APPLE_OFFER, years_of_experience=15))


@router.get("/compare",
            summary="Demo: compare Apple vs Google SRE offers",
            description=(
                "Runs a side-by-side comparison of Apple ICT5 vs Google L6 SRE offers. "
                "No payload required."
            ))
async def demo_compare():
    _, _, comparison = await _analyzer.compare(
        CompareRequest(offer_a=_APPLE_OFFER, offer_b=_GOOGLE_OFFER)
    )
    return comparison
