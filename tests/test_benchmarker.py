import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.benchmarker import BenchmarkService


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def bls_response():
    return json.loads((FIXTURES / "bls_response.json").read_text())


@pytest.fixture
def svc():
    return BenchmarkService(api_key="test-key")


# --- Role mapping ---

def test_maps_software_engineer(svc):
    assert svc.map_role("Software Engineer") == "151252"


def test_maps_senior_swe(svc):
    assert svc.map_role("Senior Software Engineer") == "151252"


def test_maps_sre(svc):
    assert svc.map_role("Site Reliability Engineer") == "151244"


def test_maps_sre_acronym(svc):
    assert svc.map_role("SRE") == "151244"


def test_maps_data_scientist(svc):
    assert svc.map_role("Data Scientist") == "152051"


def test_maps_unknown_role_to_default(svc):
    assert svc.map_role("Galactic Overlord") == "151252"


# --- Location mapping ---

def test_maps_seattle(svc):
    assert svc.map_location("Seattle, WA") == "0042660"


def test_maps_san_francisco(svc):
    assert svc.map_location("San Francisco, CA") == "0041860"


def test_maps_nyc(svc):
    assert svc.map_location("New York, NY") == "0035620"


def test_maps_unknown_city_to_national(svc):
    assert svc.map_location("Smalltown, AK") == "0000000"


# --- Series ID construction ---

def test_series_ids_format(svc):
    ids = svc.make_series_ids("0042660", "151252")
    assert ids == [
        "OEU004266015125212",
        "OEU004266015125213",
        "OEU004266015125214",
    ]


# --- Percentile interpolation ---

def test_percentile_below_p25(svc):
    pct = svc.interpolate_percentile(80000, 133690, 161840, 208000)
    assert pct < 25.0


def test_percentile_at_median(svc):
    pct = svc.interpolate_percentile(161840, 133690, 161840, 208000)
    assert pct == 50.0


def test_percentile_between_p50_and_p75(svc):
    pct = svc.interpolate_percentile(185000, 133690, 161840, 208000)
    assert 50.0 < pct < 75.0


def test_percentile_above_p75(svc):
    pct = svc.interpolate_percentile(250000, 133690, 161840, 208000)
    assert pct > 75.0
    assert pct <= 99.0


def test_percentile_capped_at_99(svc):
    pct = svc.interpolate_percentile(10_000_000, 133690, 161840, 208000)
    assert pct == 99.0


# --- BLS data extraction ---

def test_extract_value_found(svc, bls_response):
    val = svc._extract_value(bls_response, "OEU004266015125213")
    assert val == 161840.0


def test_extract_value_not_found(svc, bls_response):
    val = svc._extract_value(bls_response, "INVALID_SERIES")
    assert val is None


# --- Async: get_benchmark (mocked HTTP) ---

@pytest.mark.asyncio
async def test_get_benchmark_returns_data(svc, bls_response):
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value=bls_response)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("app.services.benchmarker.httpx.AsyncClient", return_value=mock_client):
        result = await svc.get_benchmark("Software Engineer", "Seattle, WA", 175000)

    assert result is not None
    assert result.p25 == 133690.0
    assert result.p50 == 161840.0
    assert result.p75 == 208000.0
    assert 50.0 < result.your_percentile < 75.0


@pytest.mark.asyncio
async def test_get_benchmark_returns_none_on_http_error(svc):
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=Exception("network error"))

    with patch("app.services.benchmarker.httpx.AsyncClient", return_value=mock_client):
        result = await svc.get_benchmark("Software Engineer", "Seattle, WA", 150000)

    assert result is None


@pytest.mark.asyncio
async def test_get_benchmark_national_fallback(svc):
    """Metro call fails, service retries with national data and succeeds."""
    call_count = 0

    def national_bls_response():
        return {
            "status": "REQUEST_SUCCEEDED",
            "Results": {
                "series": [
                    {"seriesID": "OEU000000015125212", "data": [{"value": "120000"}]},
                    {"seriesID": "OEU000000015125213", "data": [{"value": "150000"}]},
                    {"seriesID": "OEU000000015125214", "data": [{"value": "190000"}]},
                ]
            },
        }

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("metro data unavailable")
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=national_bls_response())
        return mock_resp

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = mock_post

    with patch("app.services.benchmarker.httpx.AsyncClient", return_value=mock_client):
        # Seattle maps to metro code, so fallback path is reachable
        result = await svc.get_benchmark("Software Engineer", "Seattle, WA", 150000)

    assert result is not None
    assert result.p50 == 150000.0
    assert call_count == 2
