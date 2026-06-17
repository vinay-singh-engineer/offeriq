import httpx
from dataclasses import dataclass
from typing import Optional


# COL index where 100 = US national average.
# Based on composite of ERI Salary Assessor and Numbeo data.
COL_INDEX: dict = {
    "san-francisco": 270,
    "san-jose": 255,
    "new-york": 240,
    "boston": 180,
    "los-angeles": 195,
    "san-diego": 185,
    "seattle": 165,
    "denver": 155,
    "portland": 150,
    "minneapolis": 135,
    "chicago": 140,
    "miami": 140,
    "austin": 130,
    "phoenix": 120,
    "raleigh": 115,
    "atlanta": 115,
    "dallas": 115,
    "national": 100,
}

# Fallback: map city keywords to slugs for offline lookup
CITY_SLUG_MAP: dict = {
    "san francisco": "san-francisco",
    "san jose": "san-jose",
    "new york": "new-york",
    "nyc": "new-york",
    "boston": "boston",
    "los angeles": "los-angeles",
    "san diego": "san-diego",
    "seattle": "seattle",
    "denver": "denver",
    "portland": "portland",
    "minneapolis": "minneapolis",
    "chicago": "chicago",
    "miami": "miami",
    "austin": "austin",
    "phoenix": "phoenix",
    "raleigh": "raleigh",
    "atlanta": "atlanta",
    "dallas": "dallas",
}

TELEPORT_SEARCH = "https://api.teleport.org/api/cities/?search={city}&embed=city:urban_area"
_NATIONAL_AVG = 100


@dataclass
class COLResult:
    city_slug: str
    col_index: float                # 100 = US national average
    purchasing_power: float         # salary normalized to national average
    source: str                     # "teleport" | "lookup" | "national_fallback"


class COLService:

    async def _slug_from_teleport(self, city: str) -> Optional[str]:
        """Ask Teleport API for the urban area slug for a city name."""
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(TELEPORT_SEARCH.format(city=city))
                resp.raise_for_status()
                data = resp.json()
                results = (
                    data.get("_embedded", {}).get("city:search-results", [])
                )
                for result in results:
                    ua = result.get("_links", {}).get("city:urban_area", {})
                    href = ua.get("href", "")
                    if "slug:" in href:
                        slug = href.split("slug:")[1].rstrip("/")
                        if slug in COL_INDEX:
                            return slug
        except Exception:
            pass
        return None

    def _slug_from_lookup(self, location: str) -> Optional[str]:
        """Offline keyword match against known city slugs."""
        location_lower = location.lower()
        for keyword, slug in CITY_SLUG_MAP.items():
            if keyword in location_lower:
                return slug
        return None

    def adjust(self, salary: float, col_index: float) -> float:
        """Convert salary to national-average purchasing power equivalent."""
        return round(salary * (_NATIONAL_AVG / col_index), 2)

    async def get_col(self, location: str, salary: float) -> COLResult:
        # 1. Try Teleport for an authoritative slug
        slug = await self._slug_from_teleport(location)
        source = "teleport"

        # 2. Fall back to offline keyword lookup
        if slug is None:
            slug = self._slug_from_lookup(location)
            source = "lookup"

        # 3. Fall back to national average
        if slug is None:
            slug = "national"
            source = "national_fallback"

        col_index = COL_INDEX.get(slug, _NATIONAL_AVG)
        return COLResult(
            city_slug=slug,
            col_index=float(col_index),
            purchasing_power=self.adjust(salary, col_index),
            source=source,
        )
