from fastapi import APIRouter, HTTPException
from app.config import settings
from app.models.offer import AnalyzeRequest, CompareRequest, NegotiateRequest
from app.services.analyzer import AnalyzerService
from app.services.negotiator import NegotiatorService

router = APIRouter(prefix="/api", tags=["offers"])
_analyzer = AnalyzerService()
_negotiator = NegotiatorService(api_key=settings.anthropic_api_key)


@router.post("/analyze")
async def analyze_offer(request: AnalyzeRequest):
    return await _analyzer.analyze(request)


@router.post("/compare")
async def compare_offers(request: CompareRequest):
    _, _, comparison = await _analyzer.compare(request)
    return comparison


@router.post("/negotiate")
async def negotiate(request: NegotiateRequest):
    analysis = await _analyzer.analyze(
        AnalyzeRequest(offer=request.offer, years_of_experience=request.years_of_experience)
    )
    try:
        return await _negotiator.get_script(request, analysis)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
