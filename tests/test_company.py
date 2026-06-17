import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.company import CompanyService


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def svc():
    return CompanyService()


@pytest.fixture
def wiki_stripe():
    return json.loads((FIXTURES / "wikipedia_stripe.json").read_text())


@pytest.fixture
def wiki_google():
    return json.loads((FIXTURES / "wikipedia_google.json").read_text())


# --- _find_layoffs() ---

def test_finds_google_layoffs(svc):
    result = svc._find_layoffs("Google")
    assert result is not None
    assert result["count"] == 12000


def test_finds_meta_layoffs(svc):
    result = svc._find_layoffs("Meta Platforms")
    assert result is not None


def test_finds_stripe_layoffs(svc):
    result = svc._find_layoffs("Stripe")
    assert result is not None


def test_unknown_company_no_layoffs(svc):
    result = svc._find_layoffs("Acme Corp")
    assert result is None


# --- _parse_founding_year() ---

def test_parses_founded_in_year(svc):
    assert svc._parse_founding_year("founded in 2010 by two brothers") == 2010


def test_parses_founded_year_no_in(svc):
    assert svc._parse_founding_year("The company was founded 1998 in California") == 1998


def test_ignores_future_year(svc):
    assert svc._parse_founding_year("founded in 2099") is None


def test_returns_none_if_no_year(svc):
    assert svc._parse_founding_year("A company that makes widgets") is None


# --- _parse_is_public() ---

def test_detects_nasdaq(svc):
    assert svc._parse_is_public("traded on the NASDAQ stock exchange") is True


def test_detects_nyse(svc):
    assert svc._parse_is_public("listed on the NYSE") is True


def test_detects_ipo(svc):
    assert svc._parse_is_public("completed an initial public offering in 2019") is True


def test_private_company_not_public(svc):
    assert svc._parse_is_public("It is a private company headquartered in SF") is False


def test_unknown_returns_false(svc):
    assert svc._parse_is_public("A software company making developer tools") is False


# --- _compute_risk() ---

def test_risk_public_no_layoffs_low(svc):
    assert svc._compute_risk(founding_year=2000, is_public=True, recent_layoffs=False) == "low"


def test_risk_young_startup_high(svc):
    assert svc._compute_risk(founding_year=2024, is_public=False, recent_layoffs=False) == "high"


def test_risk_mid_age_private_medium(svc):
    assert svc._compute_risk(founding_year=2020, is_public=False, recent_layoffs=False) == "medium"


def test_risk_public_with_layoffs_medium(svc):
    # Large public company restructuring = medium, not high
    assert svc._compute_risk(founding_year=2000, is_public=True, recent_layoffs=True) == "medium"


def test_risk_startup_with_layoffs_high(svc):
    assert svc._compute_risk(founding_year=2021, is_public=False, recent_layoffs=True) == "high"


def test_risk_unknown_founding_private(svc):
    assert svc._compute_risk(founding_year=None, is_public=False, recent_layoffs=False) == "unknown"


# --- get_health() async ---

@pytest.mark.asyncio
async def test_get_health_stripe(svc, wiki_stripe):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value=wiki_stripe)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("app.services.company.httpx.AsyncClient", return_value=mock_client):
        result = await svc.get_health("Stripe")

    assert result.founding_year == 2010
    assert result.is_public is False
    assert result.recent_layoffs is True        # Stripe is in KNOWN_LAYOFFS
    assert result.layoff_risk == "high"         # private + layoffs


@pytest.mark.asyncio
async def test_get_health_google(svc, wiki_google):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value=wiki_google)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("app.services.company.httpx.AsyncClient", return_value=mock_client):
        result = await svc.get_health("Google")

    assert result.founding_year == 1998
    assert result.is_public is True
    assert result.recent_layoffs is True
    assert result.layoff_risk == "medium"       # public + restructuring


@pytest.mark.asyncio
async def test_get_health_wikipedia_unavailable(svc):
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=Exception("timeout"))

    with patch("app.services.company.httpx.AsyncClient", return_value=mock_client):
        result = await svc.get_health("Acme Corp")

    # Graceful degradation: unknown risk, no data
    assert result.layoff_risk == "unknown"
    assert result.founding_year is None
    assert result.recent_layoffs is False
