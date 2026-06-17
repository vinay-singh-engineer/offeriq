import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.col import COLService, COL_INDEX


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def teleport_response():
    return json.loads((FIXTURES / "teleport_search.json").read_text())


@pytest.fixture
def svc():
    return COLService()


# --- adjust() math ---

def test_adjust_national_average(svc):
    # salary in a city with COL 100 (national avg) stays the same
    assert svc.adjust(150000, 100) == 150000.0


def test_adjust_high_col_city(svc):
    # $200K in SF (COL 270) → purchasing power of ~$74K nationally
    result = svc.adjust(200000, 270)
    assert abs(result - 74074.07) < 1.0


def test_adjust_low_col_city(svc):
    # $120K in Dallas (COL 115) → purchasing power of ~$104K nationally
    result = svc.adjust(120000, 115)
    assert abs(result - 104347.83) < 1.0


def test_adjust_austin_vs_sf_same_purchasing_power(svc):
    # $150K Austin (COL 130) → national PP ≈ $115,385
    # $311,538 SF (COL 270) → national PP ≈ $115,385
    austin_pp = svc.adjust(150000, 130)
    sf_equivalent = round(150000 * (270 / 130), 2)
    sf_pp = svc.adjust(sf_equivalent, 270)
    assert abs(austin_pp - sf_pp) < 1.0


# --- _slug_from_lookup() ---

def test_lookup_seattle(svc):
    assert svc._slug_from_lookup("Seattle, WA") == "seattle"


def test_lookup_san_francisco(svc):
    assert svc._slug_from_lookup("San Francisco, CA") == "san-francisco"


def test_lookup_nyc_abbreviation(svc):
    assert svc._slug_from_lookup("NYC") == "new-york"


def test_lookup_new_york_full(svc):
    assert svc._slug_from_lookup("New York, NY") == "new-york"


def test_lookup_unknown_returns_none(svc):
    assert svc._slug_from_lookup("Podunk, TX") is None


def test_lookup_case_insensitive(svc):
    assert svc._slug_from_lookup("AUSTIN, TX") == "austin"


# --- COL_INDEX coverage ---

def test_all_mapped_slugs_have_col_index():
    from app.services.col import CITY_SLUG_MAP
    for slug in CITY_SLUG_MAP.values():
        assert slug in COL_INDEX, f"Missing COL index for slug: {slug}"


# --- get_col() async: Teleport succeeds ---

@pytest.mark.asyncio
async def test_get_col_teleport_success(svc, teleport_response):
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value=teleport_response)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("app.services.col.httpx.AsyncClient", return_value=mock_client):
        result = await svc.get_col("Seattle, WA", 160000)

    assert result.city_slug == "seattle"
    assert result.col_index == 165.0
    assert result.source == "teleport"
    assert result.purchasing_power == round(160000 * (100 / 165), 2)


# --- get_col() async: Teleport fails, offline lookup succeeds ---

@pytest.mark.asyncio
async def test_get_col_falls_back_to_lookup(svc):
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=Exception("timeout"))

    with patch("app.services.col.httpx.AsyncClient", return_value=mock_client):
        result = await svc.get_col("Austin, TX", 150000)

    assert result.city_slug == "austin"
    assert result.col_index == 130.0
    assert result.source == "lookup"


# --- get_col() async: unknown city falls back to national average ---

@pytest.mark.asyncio
async def test_get_col_national_fallback(svc):
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=Exception("timeout"))

    with patch("app.services.col.httpx.AsyncClient", return_value=mock_client):
        result = await svc.get_col("Podunk, TX", 100000)

    assert result.city_slug == "national"
    assert result.col_index == 100.0
    assert result.source == "national_fallback"
    assert result.purchasing_power == 100000.0
