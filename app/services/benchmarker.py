import httpx
from typing import Optional

from app.models.analysis import MarketBenchmark


# Standard Occupational Classification (SOC) codes
ROLE_SOC_MAP = {
    "software engineer": "151252",
    "software developer": "151252",
    "frontend engineer": "151252",
    "backend engineer": "151252",
    "full stack engineer": "151252",
    "fullstack engineer": "151252",
    "principal engineer": "151252",
    "staff engineer": "151252",
    "site reliability engineer": "151244",
    "sre": "151244",
    "devops engineer": "151244",
    "platform engineer": "151244",
    "infrastructure engineer": "151244",
    "data scientist": "152051",
    "machine learning engineer": "152051",
    "ml engineer": "152051",
    "data engineer": "151245",
    "product manager": "113021",
    "engineering manager": "113021",
    "default": "151252",
}

# BLS CBSA area codes (7-digit, zero-padded)
CITY_AREA_MAP = {
    "san francisco": "0041860",
    "san jose": "0041940",
    "seattle": "0042660",
    "new york": "0035620",
    "nyc": "0035620",
    "boston": "0014460",
    "chicago": "0016980",
    "los angeles": "0031080",
    "austin": "0012420",
    "denver": "0019740",
    "atlanta": "0012060",
    "miami": "0033100",
    "dallas": "0019100",
    "portland": "0038900",
    "san diego": "0041740",
    "phoenix": "0038060",
    "raleigh": "0039580",
    "minneapolis": "0033460",
}

_NATIONAL = "0000000"

# BLS OEWS annual wage data type codes
_P25 = "12"
_P50 = "13"
_P75 = "14"


class BenchmarkService:
    BLS_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key

    def map_role(self, role: str) -> str:
        role_lower = role.lower()
        for key, soc in ROLE_SOC_MAP.items():
            if key in role_lower:
                return soc
        return ROLE_SOC_MAP["default"]

    def map_location(self, location: str) -> str:
        location_lower = location.lower()
        for city, area in CITY_AREA_MAP.items():
            if city in location_lower:
                return area
        return _NATIONAL

    def make_series_ids(self, area_code: str, soc_code: str):
        return [
            f"OEU{area_code}{soc_code}{_P25}",
            f"OEU{area_code}{soc_code}{_P50}",
            f"OEU{area_code}{soc_code}{_P75}",
        ]

    async def _call_bls(self, series_ids: list) -> Optional[dict]:
        payload = {"seriesid": series_ids, "latest": "true"}
        if self.api_key:
            payload["registrationkey"] = self.api_key
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(self.BLS_URL, json=payload)
                resp.raise_for_status()
                data = resp.json()
                if data.get("status") != "REQUEST_SUCCEEDED":
                    return None
                return data
        except Exception:
            return None

    def _extract_value(self, bls_data: dict, series_id: str) -> Optional[float]:
        for series in bls_data.get("Results", {}).get("series", []):
            if series["seriesID"] == series_id:
                items = series.get("data", [])
                if items:
                    try:
                        return float(items[0]["value"])
                    except (KeyError, ValueError):
                        return None
        return None

    def interpolate_percentile(
        self, salary: float, p25: float, p50: float, p75: float
    ) -> float:
        """Estimate what percentile the salary falls at given p25/p50/p75 anchors."""
        if salary <= p25:
            return round(max(1.0, 25.0 * salary / p25), 1)
        elif salary <= p50:
            frac = (salary - p25) / (p50 - p25)
            return round(25.0 + frac * 25.0, 1)
        elif salary <= p75:
            frac = (salary - p50) / (p75 - p50)
            return round(50.0 + frac * 25.0, 1)
        else:
            extra = (salary - p75) / max(p75 - p50, 1)
            return round(min(99.0, 75.0 + extra * 25.0), 1)

    async def get_benchmark(
        self, role: str, location: str, base_salary: float
    ) -> Optional[MarketBenchmark]:
        soc_code = self.map_role(role)
        area_code = self.map_location(location)
        series_ids = self.make_series_ids(area_code, soc_code)

        bls_data = await self._call_bls(series_ids)

        # Fall back to national data if metro lookup fails
        if not bls_data and area_code != _NATIONAL:
            national_ids = self.make_series_ids(_NATIONAL, soc_code)
            bls_data = await self._call_bls(national_ids)
            series_ids = national_ids

        if not bls_data:
            return None

        p25 = self._extract_value(bls_data, series_ids[0])
        p50 = self._extract_value(bls_data, series_ids[1])
        p75 = self._extract_value(bls_data, series_ids[2])

        if not all([p25, p50, p75]):
            return None

        return MarketBenchmark(
            p25=p25,
            p50=p50,
            p75=p75,
            your_percentile=self.interpolate_percentile(base_salary, p25, p50, p75),
        )
